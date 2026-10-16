from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from sqlalchemy import select, func, or_
from sqlalchemy.orm import Session
from ..db import get_db
from ..models import User, StudentProfile, Department, Resume, Invitation
from ..schemas import ProfileUpdate
from ..security import current_user, require, MANAGERS, scoped, student_access, audit, rate_limit
from ..storage import get_storage, document_response, MAX_FILE_SIZE, validate_document

router = APIRouter(tags=["Student records and resumes"])


def student_view(db, user):
    profile = db.scalar(
        select(StudentProfile).where(StudentProfile.user_id == user.id, StudentProfile.institution_id == user.institution_id)
    )
    department = db.get(Department, user.department_id) if user.department_id else None
    latest = db.scalar(select(Invitation).where(Invitation.user_id == user.id).order_by(Invitation.created_at.desc()))
    return {
        "id": user.id,
        "full_name": user.full_name,
        "email": user.email,
        "roll_no": user.roll_no,
        "active": user.active,
        "department": department.code if department else "",
        "invitation_status": latest.delivery_status if latest else "not_sent",
        **(
            {
                key: getattr(profile, key)
                for key in ("graduation_year", "cgpa", "active_backlogs", "phone", "bio", "projects", "internships", "section", "academic_year", "semester")
            }
            if profile
            else {}
        ),
        "resume_count": db.scalar(select(func.count()).select_from(Resume).where(Resume.user_id == user.id)),
    }


@router.get("/students")
def students(
    q: str = Query("", max_length=150),
    department: str = "",
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    sort: str = "full_name",
    order: str = "asc",
    user=Depends(current_user),
    db: Session = Depends(get_db),
):
    require(user, MANAGERS | {"hod"})
    query = select(User).where(User.institution_id == user.institution_id, User.role == "student")
    if user.role == "hod":
        query = query.where(User.department_id == (user.department_id or "none"))
    if department:
        query = query.join(Department, User.department_id == Department.id).where(Department.code == department.upper())
    if q:
        escaped = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        query = query.where(
            or_(
                User.full_name.ilike(f"%{escaped}%", escape="\\"),
                User.roll_no.ilike(f"%{escaped}%", escape="\\"),
                User.email.ilike(f"%{escaped}%", escape="\\"),
            )
        )
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    column = {"full_name": User.full_name, "roll_no": User.roll_no, "created_at": User.created_at}.get(sort, User.full_name)
    query = query.order_by(column.desc() if order == "desc" else column.asc(), User.id).offset((page - 1) * size).limit(size)
    return {"items": [student_view(db, s) for s in db.scalars(query)], "total": total, "page": page, "size": size}


@router.get("/students/{student_id}")
def student(student_id: str, user=Depends(current_user), db: Session = Depends(get_db)):
    return student_view(db, student_access(db, user, student_id))


@router.get("/profile")
def profile(user=Depends(current_user), db: Session = Depends(get_db)):
    require(user, {"student"})
    return student_view(db, user)


@router.put("/profile")
def update_profile(body: ProfileUpdate, user=Depends(current_user), db: Session = Depends(get_db)):
    require(user, {"student"})
    profile = db.scalar(
        select(StudentProfile).where(StudentProfile.user_id == user.id, StudentProfile.institution_id == user.institution_id)
    )
    if not profile:
        raise HTTPException(404, "Profile not found.")
    user.full_name = body.full_name
    for key, value in body.model_dump(exclude={"full_name"}).items():
        setattr(profile, key, value)
    audit(db, user, "profile.update", user.id)
    db.commit()
    return student_view(db, user)


@router.get("/resumes")
def resumes(student_id: str | None = None, user=Depends(current_user), db: Session = Depends(get_db)):
    query = select(Resume).where(Resume.institution_id == user.institution_id)
    if user.role == "student":
        if student_id and student_id != user.id:
            raise HTTPException(403, "You can only view your own resumes.")
        query = query.where(Resume.user_id == user.id)
    elif student_id:
        student_access(db, user, student_id)
        query = query.where(Resume.user_id == student_id)
    else:
        require(user, MANAGERS | {"hod"})
        if user.role == "hod":
            query = query.join(User, User.id == Resume.user_id).where(User.department_id == (user.department_id or "none"))
    return [
        {
            "id": r.id,
            "user_id": r.user_id,
            "student_name": db.get(User, r.user_id).full_name,
            "filename": r.filename,
            "size_bytes": r.size_bytes,
            "version": r.version,
            "created_at": r.created_at,
            "extraction_status": r.extraction_status,
        }
        for r in db.scalars(query.order_by(Resume.created_at.desc()).limit(200))
    ]


@router.post("/resumes")
async def upload_resume(file: UploadFile = File(...), user=Depends(current_user), db: Session = Depends(get_db)):
    require(user, {"student"})
    rate_limit(f"resume:{user.id}", 10, 300)
    content = await file.read(MAX_FILE_SIZE + 1)
    suffix, mime, text = validate_document(file.filename or "", content)
    db.scalar(select(User).where(User.id == user.id).with_for_update())
    version = (db.scalar(select(func.max(Resume.version)).where(Resume.user_id == user.id)) or 0) + 1
    storage = get_storage()
    key = storage.put(user.institution_id, content, suffix)
    text_key = storage.put(user.institution_id, text.encode("utf-8"), ".txt")
    try:
        resume = Resume(
            institution_id=user.institution_id,
            user_id=user.id,
            filename=Path(file.filename.replace("\\", "/")).name[:200],
            storage_key=key,
            text_key=text_key,
            mime_type=mime,
            size_bytes=len(content),
            version=version,
            extraction_status="complete" if text.strip() else "no_text",
        )
        db.add(resume)
        db.flush()
        audit(db, user, "resume.upload", resume.id)
        from ..intelligence.events import track

        track(db, user, "resume.uploaded", "Resume uploaded", resume_id=resume.id)
        db.commit()
    except Exception:
        storage.delete(key)
        storage.delete(text_key)
        raise
    return {"id": resume.id, "version": version, "extraction_status": resume.extraction_status}


@router.get("/resumes/{resume_id}/download")
def download_resume(resume_id: str, user=Depends(current_user), db: Session = Depends(get_db)):
    resume = scoped(db, Resume, user, resume_id)
    student_access(db, user, resume.user_id)
    audit(db, user, "resume.download", resume.id)
    db.commit()
    return document_response(resume.storage_key, resume.filename, resume.mime_type)


@router.get("/resumes/{resume_id}/text")
def resume_text(resume_id: str, user=Depends(current_user), db: Session = Depends(get_db)):
    resume = scoped(db, Resume, user, resume_id)
    student_access(db, user, resume.user_id)
    audit(db, user, "resume.text_read", resume.id)
    db.commit()
    return {"text": get_storage().read(resume.text_key).decode("utf-8"), "status": resume.extraction_status}

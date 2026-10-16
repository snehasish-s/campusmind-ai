import csv
import io
from pathlib import Path
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from fastapi.responses import Response
from sqlalchemy import select, func, or_, delete
from sqlalchemy.orm import Session
from ..db import get_db
from ..models import (
    Institution,
    Department,
    User,
    StaffRole,
    Resume,
    RecruitmentDrive,
    DriveApplication,
    Notification,
    AuditLog,
    ActivityEvent,
    InstitutionalDocument,
    AuthSession,
    now,
)
from ..schemas import DepartmentInput, StaffInput, InstitutionUpdate, StaffAccess
from ..security import current_user, require, MANAGERS, ADMINS, scoped, audit, csv_safe
from ..invitations import issue_invitation
from ..storage import get_storage, document_response, validate_document, MAX_FILE_SIZE

router = APIRouter(tags=["Institution operations"])


@router.get("/dashboard")
def dashboard(user=Depends(current_user), db: Session = Depends(get_db)):
    def count(model, *conditions):
        return db.scalar(select(func.count()).select_from(model).where(model.institution_id == user.institution_id, *conditions)) or 0

    if user.role == "student":
        return {
            "students": None,
            "resumes": count(Resume, Resume.user_id == user.id),
            "drives": count(RecruitmentDrive, RecruitmentDrive.status.in_(["published", "open"]), RecruitmentDrive.drive_date >= now()),
            "applications": count(DriveApplication, DriveApplication.user_id == user.id),
            "departments": [],
            "activity": [],
            "active": int(user.active),
        }
    student_filter = [User.role == "student"]
    if user.role == "hod":
        student_filter.append(User.department_id == (user.department_id or "none"))
    students = count(User, *student_filter)
    resume_query = (
        select(func.count(func.distinct(Resume.user_id)))
        .join(User, User.id == Resume.user_id)
        .where(Resume.institution_id == user.institution_id, *student_filter)
    )
    departments = []
    for d in db.scalars(select(Department).where(Department.institution_id == user.institution_id)):
        if user.role == "hod" and d.id != user.department_id:
            continue
        departments.append(
            {
                "name": d.code,
                "students": count(User, User.role == "student", User.department_id == d.id),
                "active": count(User, User.role == "student", User.department_id == d.id, User.active.is_(True)),
            }
        )
    return {
        "students": students,
        "active": count(User, *student_filter, User.active.is_(True)),
        "resumes": db.scalar(resume_query) or 0,
        "staff": count(User, User.role != "student"),
        "drives": count(RecruitmentDrive, RecruitmentDrive.status.in_(["published", "open"]), RecruitmentDrive.drive_date >= now()),
        "applications": count(DriveApplication),
        "offers": count(DriveApplication, DriveApplication.status == "offered"),
        "documents": count(InstitutionalDocument),
        "departments": departments,
        "activity": [
            {"id": a.id, "title": a.title, "kind": a.kind, "created_at": a.created_at}
            for a in db.scalars(
                select(ActivityEvent)
                .where(ActivityEvent.institution_id == user.institution_id)
                .order_by(ActivityEvent.created_at.desc())
                .limit(8)
            )
        ],
    }


@router.get("/departments")
def departments(user=Depends(current_user), db: Session = Depends(get_db)):
    return [
        {"id": d.id, "code": d.code, "name": d.name}
        for d in db.scalars(select(Department).where(Department.institution_id == user.institution_id).order_by(Department.code))
    ]


@router.post("/departments")
def create_department(body: DepartmentInput, user=Depends(current_user), db: Session = Depends(get_db)):
    require(user, ADMINS)
    d = Department(institution_id=user.institution_id, code=body.code.upper(), name=body.name)
    db.add(d)
    db.flush()
    audit(db, user, "department.create", d.id)
    db.commit()
    return {"id": d.id}


@router.put("/departments/{department_id}")
def edit_department(department_id: str, body: DepartmentInput, user=Depends(current_user), db: Session = Depends(get_db)):
    require(user, ADMINS)
    d = scoped(db, Department, user, department_id)
    d.code, d.name = body.code.upper(), body.name
    audit(db, user, "department.update", d.id)
    db.commit()
    return {"id": d.id}


@router.get("/staff")
def staff(user=Depends(current_user), db: Session = Depends(get_db)):
    require(user, ADMINS)
    return [
        {"id": u.id, "full_name": u.full_name, "email": u.email, "role": u.role, "active": u.active, "department_id": u.department_id}
        for u in db.scalars(select(User).where(User.institution_id == user.institution_id, User.role != "student"))
    ]


@router.post("/staff")
def add_staff(body: StaffInput, user=Depends(current_user), db: Session = Depends(get_db)):
    require(user, ADMINS)
    if body.department_id:
        scoped(db, Department, user, body.department_id)
    if body.role in {"hod", "faculty"} and not body.department_id:
        raise HTTPException(422, "Assign a department to a coordinator.")
    staff = User(
        institution_id=user.institution_id,
        **body.model_dump(exclude={"email", "roll_no"}),
        email=str(body.email).lower(),
        roll_no=body.roll_no.upper(),
    )
    db.add(staff)
    db.flush()
    db.add(StaffRole(institution_id=user.institution_id, user_id=staff.id, role=staff.role, department_id=staff.department_id))
    invitation, _ = issue_invitation(db, staff)
    audit(db, user, "staff.invite", staff.id)
    db.commit()
    return {"id": staff.id, "delivery_status": invitation.delivery_status}


@router.put("/institution")
def institution(body: InstitutionUpdate, user=Depends(current_user), db: Session = Depends(get_db)):
    require(user, ADMINS)
    institution = db.get(Institution, user.institution_id)
    for key, value in body.model_dump().items():
        setattr(institution, key, value)
    audit(db, user, "institution.update", institution.id)
    db.commit()
    return {"ok": True}


@router.put("/staff/{staff_id}/access")
def update_staff_access(staff_id: str, body: StaffAccess, user=Depends(current_user), db: Session = Depends(get_db)):
    require(user, ADMINS)
    target = scoped(db, User, user, staff_id)
    if target.role in {"student", "platform_admin"} or target.id == user.id:
        raise HTTPException(403, "You cannot change your own access or this account's role.")
    if body.department_id:
        scoped(db, Department, user, body.department_id)
    if body.role in {"hod", "faculty"} and not body.department_id:
        raise HTTPException(422, "Assign a department to a coordinator.")
    target.role, target.department_id = body.role, body.department_id
    role = db.scalar(select(StaffRole).where(StaffRole.user_id == target.id, StaffRole.institution_id == user.institution_id))
    if not role:
        role = StaffRole(user_id=target.id, institution_id=user.institution_id)
        db.add(role)
    role.role, role.department_id = body.role, body.department_id
    db.execute(delete(AuthSession).where(AuthSession.user_id == target.id))
    audit(db, user, "staff.access_update", target.id, body.model_dump())
    db.commit()
    return {"ok": True}


@router.get("/notifications")
def notifications(user=Depends(current_user), db: Session = Depends(get_db)):
    return [
        {"id": n.id, "title": n.title, "message": n.message, "created_at": n.created_at}
        for n in db.scalars(
            select(Notification)
            .where(Notification.institution_id == user.institution_id, or_(Notification.user_id == user.id, Notification.user_id.is_(None)))
            .order_by(Notification.created_at.desc())
            .limit(100)
        )
    ]


@router.get("/audit")
def audit_logs(user=Depends(current_user), db: Session = Depends(get_db)):
    require(user, ADMINS)
    return [
        {
            "id": a.id,
            "actor": db.get(User, a.actor_id).full_name if a.actor_id else "System",
            "action": a.action,
            "target_id": a.target_id,
            "created_at": a.created_at,
        }
        for a in db.scalars(
            select(AuditLog).where(AuditLog.institution_id == user.institution_id).order_by(AuditLog.created_at.desc()).limit(200)
        )
    ]


@router.get("/documents")
def documents(user=Depends(current_user), db: Session = Depends(get_db)):
    require(user, ADMINS | {"hod"})
    query = select(InstitutionalDocument).where(InstitutionalDocument.institution_id == user.institution_id)
    if user.role == "hod":
        query = query.where(InstitutionalDocument.department_id == (user.department_id or "none"))
    return [
        {
            "id": d.id,
            "title": d.title,
            "category": d.category,
            "filename": d.filename,
            "status": d.status,
            "size_bytes": d.size_bytes,
            "created_at": d.created_at,
        }
        for d in db.scalars(query.order_by(InstitutionalDocument.created_at.desc()).limit(500))
    ]


@router.post("/documents")
async def upload_document(
    file: UploadFile = File(...),
    title: str = Form(..., min_length=2, max_length=200),
    category: str = Form(..., min_length=2, max_length=100),
    user=Depends(current_user),
    db: Session = Depends(get_db),
):
    require(user, ADMINS | {"hod"})
    content = await file.read(MAX_FILE_SIZE + 1)
    suffix, mime, _ = validate_document(file.filename or "", content)
    storage = get_storage()
    key = storage.put(user.institution_id, content, suffix)
    document = InstitutionalDocument(
        institution_id=user.institution_id,
        title=title,
        category=category,
        filename=Path(file.filename.replace("\\", "/")).name[:200],
        storage_key=key,
        mime_type=mime,
        size_bytes=len(content),
        uploaded_by=user.id,
        department_id=user.department_id if user.role == "hod" else None,
        owner_id=user.id,
    )
    try:
        db.add(document)
        db.flush()
        audit(db, user, "document.upload", document.id)
        db.commit()
    except Exception:
        storage.delete(key)
        raise
    return {"id": document.id}


@router.get("/documents/{document_id}/download")
def download_document(document_id: str, user=Depends(current_user), db: Session = Depends(get_db)):
    require(user, ADMINS | {"hod"})
    document = scoped(db, InstitutionalDocument, user, document_id)
    if user.role == "hod" and document.department_id != user.department_id:
        raise HTTPException(404, "Document not found.")
    audit(db, user, "document.download", document.id)
    db.commit()
    return document_response(document.storage_key, document.filename, document.mime_type)


@router.get("/reports/placement.csv")
def placement_report(user=Depends(current_user), db: Session = Depends(get_db)):
    require(user, MANAGERS)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["position", "status", "applications", "offers"])
    for d in db.scalars(select(RecruitmentDrive).where(RecruitmentDrive.institution_id == user.institution_id)):
        apps = list(db.scalars(select(DriveApplication).where(DriveApplication.drive_id == d.id)))
        writer.writerow(
            [
                csv_safe(d.position),
                d.status,
                len(apps),
                sum(a.status == "offered" for a in apps),
            ]
        )
    audit(db, user, "report.export")
    db.commit()
    return Response(
        output.getvalue(), media_type="text/csv", headers={"Content-Disposition": 'attachment; filename="placement-report.csv"'}
    )

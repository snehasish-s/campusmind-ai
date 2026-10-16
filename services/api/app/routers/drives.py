from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from ..db import get_db
from ..models import Company, RecruitmentDrive, DriveApplication, Department, Notification, ActivityEvent, User, now
from ..schemas import DriveInput, CompanyInput
from ..security import current_user, require, MANAGERS, scoped, audit
from ..models import DriveReview, EligibilityAppeal, LearningRoadmap
from ..intelligence.preparation import objective_eligibility, adapt_after_event, eligibility_context
from ..intelligence.events import track
from ..intelligence.workflows import extract_recruitment
from pydantic import BaseModel, Field
from typing import Literal

router = APIRouter(tags=["Recruitment"])


def eligible(db, user, drive):
    return objective_eligibility(db, user, drive)["status"] in {"eligible", "eligible_by_review"}


def view(db, drive, user):
    fields = (
        "id",
        "position",
        "description",
        "employment_type",
        "location",
        "ctc",
        "required_skills",
        "min_cgpa",
        "max_backlogs",
        "eligible_branches",
        "graduation_year",
        "deadline",
        "drive_date",
        "selection_rounds",
        "additional_requirements",
        "status",
    )
    return {
        **{k: getattr(drive, k) for k in fields},
        "company_name": db.get(Company, drive.company_id).name,
        "applications": db.scalar(select(func.count()).select_from(DriveApplication).where(DriveApplication.drive_id == drive.id)),
        "eligible": eligible(db, user, drive) if user.role == "student" else None,
        "eligibility": objective_eligibility(db, user, drive) if user.role == "student" else None,
        "applied": bool(
            db.scalar(select(DriveApplication.id).where(DriveApplication.drive_id == drive.id, DriveApplication.user_id == user.id))
        ),
    }


@router.get("/companies")
def companies(user=Depends(current_user), db: Session = Depends(get_db)):
    require(user, MANAGERS | {"hod"})
    return [
        {"id": c.id, "name": c.name, "website": c.website, "sector": c.sector}
        for c in db.scalars(select(Company).where(Company.institution_id == user.institution_id).order_by(Company.name))
    ]


@router.post("/companies")
def create_company(body: CompanyInput, user=Depends(current_user), db: Session = Depends(get_db)):
    require(user, MANAGERS)
    company = Company(institution_id=user.institution_id, **body.model_dump())
    db.add(company)
    db.flush()
    audit(db, user, "company.create", company.id)
    db.commit()
    return {"id": company.id}


@router.get("/drives")
def drives(user=Depends(current_user), db: Session = Depends(get_db)):
    query = select(RecruitmentDrive).where(RecruitmentDrive.institution_id == user.institution_id)
    if user.role == "student":
        query = query.where(RecruitmentDrive.status.not_in(["draft", "reviewed"]))
    return [view(db, d, user) for d in db.scalars(query.order_by(RecruitmentDrive.drive_date).limit(500))]


def save_drive(db, actor, body, drive=None):
    if drive and drive.status in {"closed", "completed"}:
        raise HTTPException(409, "This drive is finalized. Create a new draft for a new recruitment cycle.")
    if body.status == "closed":
        raise HTTPException(422, "Save a draft or publish reviewed requirements. Close registration using the lifecycle action.")
    if body.status == "published" and body.deadline <= now():
        raise HTTPException(422, "A published drive needs a future registration deadline.")
    branches = set(db.scalars(select(Department.code).where(Department.institution_id == actor.institution_id)))
    if set(body.eligible_branches) - branches:
        raise HTTPException(422, "Eligible branches must belong to your institution.")
    company = db.scalar(select(Company).where(Company.institution_id == actor.institution_id, Company.name == body.company_name))
    if not company:
        company = Company(institution_id=actor.institution_id, name=body.company_name)
        db.add(company)
        db.flush()
    was_published = drive and drive.status in {"published", "open"}
    previous_requirements = (
        (drive.description, drive.required_skills, drive.min_cgpa, drive.max_backlogs, drive.deadline, drive.drive_date) if drive else None
    )
    if drive is None:
        drive = RecruitmentDrive(institution_id=actor.institution_id)
        db.add(drive)
    drive.company_id = company.id
    for key, value in body.model_dump(exclude={"company_name"}).items():
        setattr(drive, key, value)
    db.flush()
    review = db.scalar(select(DriveReview).where(DriveReview.drive_id == drive.id))
    if not review:
        review = DriveReview(institution_id=actor.institution_id, drive_id=drive.id, payload={})
        db.add(review)
    # The explicit officer-authored publish form is also a human review. Model extraction
    # never modifies these criteria. Draft edits invalidate earlier approval.
    if drive.status == "published":
        review.approved_by, review.approved_at = actor.id, now()
        review.payload = {
            **review.payload,
            "approved_skills": [{"skill": s, "priority": "required"} for s in drive.required_skills],
            "unresolved_conditions": [],
            "approval_method": "officer_authored_publish_form",
        }
    else:
        review.approved_at = None
        review.approved_by = None
    if drive.status == "published" and not was_published:
        publish_updates(db, actor, drive)
        db.add(ActivityEvent(institution_id=actor.institution_id, title=f"{company.name} recruitment drive published", kind="drive"))
    elif drive.status == "published" and previous_requirements != (
        drive.description,
        drive.required_skills,
        drive.min_cgpa,
        drive.max_backlogs,
        drive.deadline,
        drive.drive_date,
    ):
        publish_updates(db, actor, drive, "drive_requirements_updated")
    audit(db, actor, "drive.save", drive.id, {"status": drive.status})
    db.commit()
    return view(db, drive, actor)


@router.post("/drives")
def create_drive(body: DriveInput, user=Depends(current_user), db: Session = Depends(get_db)):
    require(user, MANAGERS)
    return save_drive(db, user, body)


@router.put("/drives/{drive_id}")
def edit_drive(drive_id: str, body: DriveInput, user=Depends(current_user), db: Session = Depends(get_db)):
    require(user, MANAGERS)
    return save_drive(db, user, body, scoped(db, RecruitmentDrive, user, drive_id))


@router.post("/drives/{drive_id}/close")
def close_drive(drive_id: str, user=Depends(current_user), db: Session = Depends(get_db)):
    require(user, MANAGERS)
    drive = scoped(db, RecruitmentDrive, user, drive_id)
    if drive.status not in {"published", "open"}:
        raise HTTPException(409, "Only a published or open drive can be closed.")
    drive.status = "closed"
    audit(db, user, "drive.close", drive.id)
    db.commit()
    return view(db, drive, user)


@router.post("/drives/{drive_id}/apply")
def apply(drive_id: str, user=Depends(current_user), db: Session = Depends(get_db)):
    require(user, {"student"})
    drive = scoped(db, RecruitmentDrive, user, drive_id)
    if drive.status not in {"published", "open"} or drive.deadline <= now():
        raise HTTPException(409, "Registration is not open.")
    if not eligible(db, user, drive):
        raise HTTPException(403, "Your profile does not match this drive's eligibility criteria.")
    application = db.scalar(select(DriveApplication).where(DriveApplication.drive_id == drive.id, DriveApplication.user_id == user.id))
    if not application:
        application = DriveApplication(institution_id=user.institution_id, drive_id=drive.id, user_id=user.id)
        db.add(application)
        audit(db, user, "drive.apply", drive.id)
        track(db, user, "drive.applied", "Recruitment application submitted", drive_id=drive.id)
        db.commit()
    return {"id": application.id, "status": application.status}


@router.get("/applications")
def applications(user=Depends(current_user), db: Session = Depends(get_db)):
    query = select(DriveApplication).where(DriveApplication.institution_id == user.institution_id)
    if user.role == "student":
        query = query.where(DriveApplication.user_id == user.id)
    else:
        require(user, MANAGERS | {"hod"})
        if user.role == "hod":
            query = query.join(User, User.id == DriveApplication.user_id).where(User.department_id == (user.department_id or "none"))
    result = []
    for a in db.scalars(query.order_by(DriveApplication.created_at.desc()).limit(1000)):
        drive = db.get(RecruitmentDrive, a.drive_id)
        result.append(
            {
                "id": a.id,
                "student": db.get(User, a.user_id).full_name,
                "position": drive.position,
                "company": db.get(Company, drive.company_id).name,
                "status": a.status,
                "created_at": a.created_at,
            }
        )
    return result


@router.patch("/applications/{application_id}")
def update_application(application_id: str, status: str, user=Depends(current_user), db: Session = Depends(get_db)):
    require(user, MANAGERS)
    if status not in {"registered", "shortlisted", "interview", "offered", "rejected"}:
        raise HTTPException(422, "Invalid application status.")
    application = scoped(db, DriveApplication, user, application_id)
    application.status = status
    audit(db, user, "application.status", application.id, {"status": status})
    db.commit()
    return {"ok": True}


def publish_updates(db, actor, drive, trigger="drive_published"):
    db.flush()
    context = eligibility_context(db, actor.institution_id)
    active_plans = {
        p.user_id
        for p in db.scalars(select(LearningRoadmap).where(LearningRoadmap.institution_id == actor.institution_id))
        if p.payload.get("status") == "active"
    }
    for student in db.scalars(select(User).where(User.institution_id == actor.institution_id, User.role == "student").order_by(User.id)):
        result = objective_eligibility(db, student, drive, context)
        db.add(
            Notification(
                institution_id=actor.institution_id,
                user_id=student.id,
                title="Recruitment preparation opportunity",
                message=f"{drive.position}: academic eligibility is {result['status'].replace('_', ' ')}. Review the criteria, request a correction if needed, and explore preparation.",
            )
        )
        if student.id in active_plans:
            adapt_after_event(db, student, trigger, drive)


class Approval(BaseModel):
    approved_skills: list[dict[str, str]] = Field(max_length=30)
    unresolved_conditions: list[str] = Field(default_factory=list, max_length=20)
    confirm_explicit_conditions: bool


@router.get("/drives/{drive_id}/review")
def drive_review(drive_id: str, user=Depends(current_user), db: Session = Depends(get_db)):
    require(user, MANAGERS)
    drive = scoped(db, RecruitmentDrive, user, drive_id)
    review = db.scalar(select(DriveReview).where(DriveReview.drive_id == drive.id))
    return {
        "extracted": extract_recruitment(drive),
        "review": review.payload if review else {},
        "approved_at": review.approved_at if review else None,
    }


@router.post("/drives/{drive_id}/review")
def approve_drive(drive_id: str, body: Approval, user=Depends(current_user), db: Session = Depends(get_db)):
    require(user, MANAGERS)
    drive = scoped(db, RecruitmentDrive, user, drive_id)
    if drive.status not in {"draft", "reviewed"}:
        raise HTTPException(409, "Save a draft revision before reviewing changed requirements.")
    if not body.confirm_explicit_conditions or any(
        set(s) - {"skill", "priority", "quote"} or not s.get("skill") or s.get("priority") not in {"required", "preferred"}
        for s in body.approved_skills
    ):
        raise HTTPException(422, "Confirm actual company conditions and required/preferred skills.")
    review = db.scalar(select(DriveReview).where(DriveReview.drive_id == drive.id))
    if not review:
        review = DriveReview(institution_id=user.institution_id, drive_id=drive.id)
        db.add(review)
    review.payload = body.model_dump()
    review.approved_by, review.approved_at = user.id, now()
    drive.status = "reviewed"
    audit(db, user, "drive.review", drive.id)
    db.commit()
    return view(db, drive, user)


@router.post("/drives/{drive_id}/transition")
def transition(
    drive_id: str, status: Literal["published", "open", "closed", "completed"], user=Depends(current_user), db: Session = Depends(get_db)
):
    require(user, MANAGERS)
    drive = scoped(db, RecruitmentDrive, user, drive_id)
    allowed = {"reviewed": {"published"}, "published": {"open", "closed"}, "open": {"closed"}, "closed": {"completed"}}
    if status not in allowed.get(drive.status, set()):
        raise HTTPException(409, "Invalid lifecycle transition.")
    if status in {"published", "open"} and drive.deadline <= now():
        raise HTTPException(409, "The registration deadline has passed.")
    drive.status = status
    if status == "published":
        publish_updates(db, user, drive)
    track(db, user, "drive." + status, "Drive moved to " + status, drive_id=drive.id)
    audit(db, user, "drive.transition", drive.id, {"status": status})
    db.commit()
    return view(db, drive, user)


class AppealInput(BaseModel):
    explanation: str = Field(min_length=10, max_length=2000)


@router.post("/drives/{drive_id}/view")
def record_view(drive_id: str, user=Depends(current_user), db: Session = Depends(get_db)):
    require(user, {"student"})
    drive = scoped(db, RecruitmentDrive, user, drive_id)
    if drive.status in {"draft", "reviewed"}:
        raise HTTPException(404, "Drive not found.")
    from ..security import rate_limit

    rate_limit("drive-view:" + user.id, 60, 60)
    track(db, user, "drive.viewed", "Recruitment drive details viewed", drive_id=drive.id)
    db.commit()
    return {"ok": True}


@router.post("/drives/{drive_id}/appeal")
def appeal(drive_id: str, body: AppealInput, user=Depends(current_user), db: Session = Depends(get_db)):
    require(user, {"student"})
    drive = scoped(db, RecruitmentDrive, user, drive_id)
    if drive.status in {"draft", "reviewed"}:
        raise HTTPException(404, "Drive not found.")
    row = EligibilityAppeal(institution_id=user.institution_id, user_id=user.id, drive_id=drive.id, payload=body.model_dump())
    db.add(row)
    audit(db, user, "eligibility.appeal", drive.id)
    db.commit()
    return {"id": row.id, "status": row.status}


@router.get("/eligibility-appeals")
def appeals(user=Depends(current_user), db: Session = Depends(get_db)):
    require(user, MANAGERS)
    return [
        {"id": a.id, "student": db.get(User, a.user_id).full_name, "drive_id": a.drive_id, "status": a.status, **a.payload}
        for a in db.scalars(select(EligibilityAppeal).where(EligibilityAppeal.institution_id == user.institution_id))
    ]


class AppealDecision(BaseModel):
    status: Literal["approved", "declined"]
    decision: str = Field(min_length=10, max_length=2000)


@router.put("/eligibility-appeals/{appeal_id}")
def decide(appeal_id: str, body: AppealDecision, user=Depends(current_user), db: Session = Depends(get_db)):
    require(user, MANAGERS)
    row = scoped(db, EligibilityAppeal, user, appeal_id)
    row.status = body.status
    row.payload = {**row.payload, "decision": body.decision, "reviewer_id": user.id}
    audit(db, user, "eligibility.review", row.id)
    db.commit()
    return {"ok": True}

import csv
import io
from statistics import mean, median
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..db import get_db
from ..models import (
    User,
    StudentProfile,
    Resume,
    TestAttempt,
    LearningRoadmap,
    LearningTask,
    DriveApplication,
    RecruitmentDrive,
    Conversation,
    DataRequest,
    ActivityEvent,
    Skill,
    SkillEvidence,
)
from ..security import current_user, require, MANAGERS, scoped, audit, rate_limit, student_access, csv_safe
from ..intelligence.preparation import evidence_profile, objective_eligibility, eligibility_context
from ..intelligence.coach import career_answer

router = APIRouter(tags=["Analytics, coach and privacy"])


def performance(
    db, actor, department="", batch=None, student_id="", assessment="", drive="", company="", date_from=None, date_to=None, topic="", q=""
):
    query = select(User).where(User.institution_id == actor.institution_id, User.role == "student")
    if actor.role == "student":
        query = query.where(User.id == actor.id)
    else:
        require(actor, MANAGERS | {"hod"})
        if actor.role == "hod":
            query = query.where(User.department_id == (actor.department_id or "none"))
    if department:
        query = query.where(User.department_id == department)
    if student_id:
        query = query.where(User.id == student_id)
    students = list(db.scalars(query.order_by(User.full_name)))
    ids = [u.id for u in students]
    profiles = {
        p.user_id: p
        for p in db.scalars(
            select(StudentProfile).where(StudentProfile.institution_id == actor.institution_id, StudentProfile.user_id.in_(ids))
        )
    }
    if batch:
        students = [u for u in students if u.id in profiles and profiles[u.id].graduation_year == batch]
    if q:
        students = [u for u in students if q.lower() in (u.full_name + " " + u.roll_no).lower()]
    drives = list(db.scalars(select(RecruitmentDrive).where(RecruitmentDrive.institution_id == actor.institution_id)))
    if drive:
        drives = [d for d in drives if d.id == drive]
    if company:
        drives = [d for d in drives if d.company_id == company]
    applications = list(
        db.scalars(
            select(DriveApplication).where(
                DriveApplication.institution_id == actor.institution_id, DriveApplication.drive_id.in_([d.id for d in drives])
            )
        )
    )
    attempts = list(db.scalars(select(TestAttempt).where(TestAttempt.institution_id == actor.institution_id, TestAttempt.user_id.in_(ids))))
    attempts = [
        a
        for a in attempts
        if a.payload["status"] == "submitted"
        and (not assessment or a.assessment_id == assessment)
        and (not date_from or a.created_at >= date_from)
        and (not date_to or a.created_at <= date_to)
    ]
    rows, scores, topic_values = [], [], {}
    active_plans = {
        p.user_id: p
        for p in db.scalars(
            select(LearningRoadmap).where(LearningRoadmap.institution_id == actor.institution_id, LearningRoadmap.user_id.in_(ids))
        )
        if p.payload.get("status") == "active"
    }
    all_tasks = list(
        db.scalars(
            select(LearningTask).where(
                LearningTask.institution_id == actor.institution_id, LearningTask.roadmap_id.in_([p.id for p in active_plans.values()])
            )
        )
    )
    resume_users = set(db.scalars(select(Resume.user_id).where(Resume.institution_id == actor.institution_id, Resume.user_id.in_(ids))))
    skill_names = {s.id: s.name for s in db.scalars(select(Skill).where(Skill.institution_id == actor.institution_id))}
    all_evidence = list(
        db.scalars(select(SkillEvidence).where(SkillEvidence.institution_id == actor.institution_id, SkillEvidence.user_id.in_(ids)))
    )
    context = eligibility_context(db, actor.institution_id)
    for u in students:
        taken = [a for a in attempts if a.user_id == u.id]
        values = [a.payload.get("topics", {}).get(topic, {}).get("score") if topic else a.payload.get("score") for a in taken]
        values = [v for v in values if v is not None]
        scores.extend(values)
        for a in taken:
            for name, value in a.payload.get("topics", {}).items():
                if not topic or topic == name:
                    topic_values.setdefault(name, []).append(value["score"])
        active = active_plans.get(u.id)
        tasks = [t for t in all_tasks if t.roadmap_id == active.id] if active else []
        resumes = u.id in resume_users
        apps = [a for a in applications if a.user_id == u.id]
        reasons = []
        if not resumes:
            reasons.append("No resume uploaded")
        if not taken:
            reasons.append("No submitted assessment evidence")
        if values and mean(values) < 50:
            reasons.append("Objective practice average below 50%; offer topic revision")
        rows.append(
            {
                "id": u.id,
                "name": u.full_name,
                "roll_no": u.roll_no,
                "active": u.active,
                "resume": bool(resumes),
                "attempts": len(taken),
                "average": round(mean(values), 2) if values else None,
                "completed_tasks": sum(t.payload["status"] == "completed" for t in tasks),
                "total_tasks": len(tasks),
                "applications": len(apps),
                "offers": sum(a.status == "offered" for a in apps),
                "support_reasons": reasons,
                "skills": [
                    {"id": e.id, "skill": skill_names[e.skill_id], **e.payload}
                    for e in all_evidence
                    if e.user_id == u.id and e.payload.get("status") not in {"rejected", "challenged", "superseded"}
                ],
                "trend": [{"date": a.created_at.isoformat(), "score": a.payload.get("score"), "title": a.payload["title"]} for a in taken],
            }
        )
    visible_ids = {r["id"] for r in rows}
    funnel = [
        {"status": status, "count": sum(a.status == status and a.user_id in visible_ids for a in applications)}
        for status in ["registered", "shortlisted", "interview", "offered", "rejected"]
    ]
    return {
        "students": rows,
        "total": len(rows),
        "activated": sum(r["active"] for r in rows),
        "resume_rate": round(100 * sum(r["resume"] for r in rows) / len(rows), 1) if rows else 0,
        "participation_rate": round(100 * sum(r["attempts"] > 0 for r in rows) / len(rows), 1) if rows else 0,
        "average": round(mean(scores), 2) if scores else None,
        "median": round(median(scores), 2) if scores else None,
        "topics": [{"topic": name, "average": round(mean(values), 2), "attempts": len(values)} for name, values in topic_values.items()],
        "funnel": funnel,
        "distribution": [
            {
                "band": f"{low}–{low + 19 if low < 80 else 100}",
                "count": sum(low <= s < low + 20 if low < 80 else 80 <= s <= 100 for s in scores),
            }
            for low in range(0, 100, 20)
        ],
        "drive_eligibility": [
            {
                "id": d.id,
                "position": d.position,
                "eligible": sum(objective_eligibility(db, u, d, context)["status"] in {"eligible", "eligible_by_review"} for u in students),
            }
            for d in drives
            if d.status not in {"draft", "reviewed"}
        ],
        "method": "Stored objective results only; support indicators are transparent coaching prompts, not hiring predictions.",
    }


@router.get("/analytics")
def analytics(
    department: str = "",
    batch: int | None = None,
    student_id: str = "",
    assessment: str = "",
    drive: str = "",
    company: str = "",
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    topic: str = "",
    q: str = Query("", max_length=150),
    user=Depends(current_user),
    db: Session = Depends(get_db),
):
    return performance(
        db,
        user,
        department,
        batch,
        student_id,
        assessment,
        drive,
        company,
        date_from.replace(tzinfo=None) if date_from else None,
        date_to.replace(tzinfo=None) if date_to else None,
        topic,
        q,
    )


@router.get("/analytics/export.csv")
def export(
    department: str = "",
    batch: int | None = None,
    student_id: str = "",
    assessment: str = "",
    drive: str = "",
    company: str = "",
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    topic: str = "",
    q: str = Query("", max_length=150),
    user=Depends(current_user),
    db: Session = Depends(get_db),
):
    require(user, MANAGERS | {"hod"})
    data = performance(
        db,
        user,
        department,
        batch,
        student_id,
        assessment,
        drive,
        company,
        date_from.replace(tzinfo=None) if date_from else None,
        date_to.replace(tzinfo=None) if date_to else None,
        topic,
        q,
    )
    output = io.StringIO()
    writer = csv.writer(output)
    keys = ["name", "roll_no", "active", "resume", "attempts", "average", "completed_tasks", "total_tasks", "applications", "offers"]
    writer.writerow(keys)
    for row in data["students"]:
        writer.writerow([csv_safe(row[k]) for k in keys])
    audit(db, user, "analytics.export")
    db.commit()
    return Response(
        output.getvalue(), media_type="text/csv", headers={"Content-Disposition": 'attachment; filename="student-performance.csv"'}
    )


class ChatInput(BaseModel):
    message: str = Field(min_length=2, max_length=2000)
    conversation_id: str | None = None


@router.get("/coach/conversations")
def conversations(user=Depends(current_user), db: Session = Depends(get_db)):
    require(user, {"student"})
    return [
        {"id": c.id, "title": c.title, "messages": c.payload.get("messages", [])}
        for c in db.scalars(
            select(Conversation)
            .where(Conversation.institution_id == user.institution_id, Conversation.user_id == user.id)
            .order_by(Conversation.created_at.desc())
            .limit(20)
        )
    ]


@router.post("/coach/chat")
def chat(body: ChatInput, user=Depends(current_user), db: Session = Depends(get_db)):
    require(user, {"student"})
    rate_limit("coach:" + user.id, 30, 300)
    conversation = scoped(db, Conversation, user, body.conversation_id) if body.conversation_id else None
    if conversation and conversation.user_id != user.id:
        raise HTTPException(404, "Conversation not found.")
    if not conversation:
        conversation = Conversation(institution_id=user.institution_id, user_id=user.id, title=body.message[:80], payload={"messages": []})
        db.add(conversation)
    result = career_answer(db, user, body.message)
    messages = conversation.payload["messages"][-38:] + [
        {"role": "user", "content": body.message},
        {"role": "assistant", "content": result["answer"], "provider": result["provider"]},
    ]
    conversation.payload = {"messages": messages}
    db.commit()
    return {"id": conversation.id, "messages": messages, **result}


@router.get("/activity")
def activity(user=Depends(current_user), db: Session = Depends(get_db)):
    query = select(ActivityEvent).where(ActivityEvent.institution_id == user.institution_id)
    if user.role == "student":
        query = query.where(ActivityEvent.user_id == user.id)
    else:
        require(user, MANAGERS | {"hod"})
        if user.role == "hod":
            query = query.join(User, User.id == ActivityEvent.user_id).where(User.department_id == (user.department_id or "none"))
    return [
        {"id": e.id, "title": e.title, "kind": e.kind, "created_at": e.created_at}
        for e in db.scalars(query.order_by(ActivityEvent.created_at.desc()).limit(100))
    ]


@router.get("/privacy/export")
def personal_export(user=Depends(current_user), db: Session = Depends(get_db)):
    require(user, {"student"})
    from .students import student_view
    from ..intelligence.assessments import attempt_view
    from ..intelligence.preparation import plan_view
    from ..models import AssignmentSubmission, FeeInvoice, PassportShare
    from .campus_life import submission_view
    from .fees import invoice_view

    audit(db, user, "privacy.export", user.id)
    db.commit()
    return {
        "profile": student_view(db, user),
        "skills": evidence_profile(db, user),
        "attempts": [attempt_view(a) for a in db.scalars(select(TestAttempt).where(TestAttempt.user_id == user.id))],
        "roadmaps": [plan_view(db, p) for p in db.scalars(select(LearningRoadmap).where(LearningRoadmap.user_id == user.id))],
        "assignments": [submission_view(db, s) for s in db.scalars(select(AssignmentSubmission).where(AssignmentSubmission.user_id == user.id))],
        "fee_invoices": [invoice_view(db, i) for i in db.scalars(select(FeeInvoice).where(FeeInvoice.user_id == user.id))],
        "passport_shares": [{"id": s.id, "expires_at": s.expires_at, "revoked_at": s.revoked_at} for s in db.scalars(select(PassportShare).where(PassportShare.user_id == user.id))],
    }


@router.post("/privacy/deletion-request")
def deletion_request(user=Depends(current_user), db: Session = Depends(get_db)):
    require(user, {"student"})
    existing = db.scalar(
        select(DataRequest).where(DataRequest.user_id == user.id, DataRequest.kind == "deletion", DataRequest.status == "pending")
    )
    if not existing:
        existing = DataRequest(
            institution_id=user.institution_id,
            user_id=user.id,
            kind="deletion",
            payload={"notice": "Institution administrator review required before erasure."},
        )
        db.add(existing)
    audit(db, user, "privacy.deletion_requested", user.id)
    db.commit()
    return {"id": existing.id, "status": existing.status}


@router.get("/privacy/requests")
def privacy_requests(user=Depends(current_user), db: Session = Depends(get_db)):
    require(user, {"institution_admin", "platform_admin"})
    return [
        {"id": r.id, "user_id": r.user_id, "name": db.get(User, r.user_id).full_name, "kind": r.kind, "status": r.status}
        for r in db.scalars(select(DataRequest).where(DataRequest.institution_id == user.institution_id))
    ]


class ErasureApproval(BaseModel):
    confirm_erasure: bool


@router.post("/privacy/requests/{request_id}/erase")
def erase(request_id: str, body: ErasureApproval, user=Depends(current_user), db: Session = Depends(get_db)):
    require(user, {"institution_admin", "platform_admin"})
    request = scoped(db, DataRequest, user, request_id)
    if request.status != "pending" or not body.confirm_erasure:
        raise HTTPException(409, "A pending request and explicit erasure confirmation are required.")
    student = student_access(db, user, request.user_id)
    from ..privacy import erase_student

    erase_student(db, student)
    request.status = "completed"
    audit(
        db,
        user,
        "privacy.erased",
        student.id,
        {"retained": "Pseudonymous account ID and privileged audit trail; backups follow institutional retention policy."},
    )
    db.commit()
    return {"ok": True}

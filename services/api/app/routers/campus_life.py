"""Academic work, evidence passports and explainable campus automation."""

import secrets
from datetime import timedelta
from pathlib import Path
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..db import get_db
from .. import models as m
from ..security import current_user, scoped, require, ADMINS, audit, digest, rate_limit, student_access, placement_access
from ..storage import get_storage, validate_document, document_response, MAX_FILE_SIZE
from ..campus_services import DEFAULT_RUBRIC, run_automations, student_timeline, notify
from ..intelligence.preparation import evidence_profile, skill_record, adapt_after_event
from ..intelligence.taxonomy import normalize, SKILLS
from .campus import visible_post, post_access

router = APIRouter(prefix="/campus", tags=["Campus daily life, assignments and evidence passports"])


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


def manage_assignment(db, actor, post_id):
    post = visible_post(db, actor, post_id)
    if post.kind != "assignment" or post.withdrawn:
        raise HTTPException(404, "Assignment not found.")
    if actor.role not in ADMINS and post.author_id != actor.id:
        raise HTTPException(403, "Only the assigned author or an administrator can review this assignment.")
    return post


@router.get("/today")
def today(user=Depends(current_user), db: Session = Depends(get_db)):
    require(user, {"student"})
    # Catch up missed reminders after a free hosting instance wakes.
    run_automations(db, user.institution_id)
    db.commit()
    return student_timeline(db, user)


class Criterion(Strict):
    label: str = Field(min_length=2, max_length=100)
    maximum: int = Field(ge=1, le=100)


class PolicyInput(Strict):
    rubric: list[Criterion] = Field(min_length=1, max_length=10)
    skills: list[str] = Field(default_factory=list, max_length=10)
    allow_late: bool = False


@router.put("/assignments/{post_id}/policy")
def policy(post_id: str, body: PolicyInput, user=Depends(current_user), db: Session = Depends(get_db)):
    post = manage_assignment(db, user, post_id)
    db.refresh(post, with_for_update=True)
    if db.scalar(select(m.AssignmentSubmission.id).where(m.AssignmentSubmission.post_id == post_id)):
        raise HTTPException(409, "The rubric is locked after the first submission to keep grading consistent.")
    labels = [c.label.casefold() for c in body.rubric]
    if len(labels) != len(set(labels)) or sum(c.maximum for c in body.rubric) != 100:
        raise HTTPException(422, "Use unique criteria adding up to 100 marks.")
    skills = [normalize(s) for s in body.skills]
    if any(s is None for s in skills):
        raise HTTPException(422, "Choose skills from the controlled taxonomy.")
    entry = db.scalar(select(m.AssignmentPolicy).where(m.AssignmentPolicy.post_id == post_id))
    if not entry:
        entry = m.AssignmentPolicy(institution_id=user.institution_id, post_id=post_id)
        db.add(entry)
    entry.rubric, entry.skills, entry.allow_late = [c.model_dump() for c in body.rubric], sorted(set(skills)), body.allow_late
    audit(db, user, "assignment.policy", post_id)
    db.commit()
    return {"ok": True}


def submission_view(db, entry):
    student = db.get(m.User, entry.user_id)
    return {
        "id": entry.id,
        "post_id": entry.post_id,
        "user_id": entry.user_id,
        "student": student.full_name,
        "roll_no": student.roll_no,
        "version": entry.version,
        "content": entry.content,
        "filename": entry.filename,
        "status": entry.status,
        "late": entry.late,
        "rubric": entry.rubric,
        "skills": entry.skills,
        "marks": entry.marks,
        "score": entry.score,
        "feedback": entry.feedback,
        "reviewed_at": entry.reviewed_at,
        "created_at": entry.created_at,
    }


@router.get("/assignments")
def assignments(user=Depends(current_user), db: Session = Depends(get_db)):
    posts = db.scalars(
        select(m.CampusPost)
        .where(m.CampusPost.institution_id == user.institution_id, m.CampusPost.kind == "assignment", m.CampusPost.withdrawn.is_(False))
        .order_by(m.CampusPost.created_at.desc())
    )
    result = []
    for post in posts:
        if not post_access(db, user, post):
            continue
        if user.role != "student" and user.role not in ADMINS and post.author_id != user.id:
            continue
        config = db.scalar(select(m.AssignmentPolicy).where(m.AssignmentPolicy.post_id == post.id))
        query = select(m.AssignmentSubmission).where(m.AssignmentSubmission.post_id == post.id)
        if user.role == "student":
            query = query.where(m.AssignmentSubmission.user_id == user.id)
        history = list(db.scalars(query.order_by(m.AssignmentSubmission.created_at.desc())))
        result.append(
            {
                "id": post.id,
                "title": post.title,
                "message": post.message,
                "subject": post.subject,
                "due_at": post.due_at,
                "filename": post.filename,
                "can_manage": user.role in ADMINS or post.author_id == user.id,
                "rubric": config.rubric if config else DEFAULT_RUBRIC,
                "skills": config.skills if config else [],
                "allow_late": config.allow_late if config else False,
                "submissions": [submission_view(db, entry) for entry in history],
            }
        )
        if len(result) >= 200:
            break
    return {"assignments": result, "taxonomy": list(SKILLS)}


@router.post("/assignments/{post_id}/submit")
async def submit(
    post_id: str,
    content: str = Form("", max_length=20000),
    file: UploadFile | None = File(None),
    user=Depends(current_user),
    db: Session = Depends(get_db),
):
    require(user, {"student"})
    rate_limit("assignment:" + user.id, 30, 3600)
    post = visible_post(db, user, post_id)
    if post.kind != "assignment":
        raise HTTPException(404, "Assignment not found.")
    # Serialize rubric edits and per-assignment revision numbers.
    db.refresh(post, with_for_update=True)
    config = db.scalar(select(m.AssignmentPolicy).where(m.AssignmentPolicy.post_id == post_id))
    previous = db.scalar(
        select(m.AssignmentSubmission)
        .where(m.AssignmentSubmission.post_id == post_id, m.AssignmentSubmission.user_id == user.id)
        .order_by(m.AssignmentSubmission.version.desc())
    )
    late = bool(post.due_at and post.due_at < m.now())
    if late and not (config and config.allow_late) and not (previous and previous.status == "returned"):
        raise HTTPException(409, "The deadline has passed. Ask your teacher to allow a late submission.")
    if not content.strip() and not file:
        raise HTTPException(422, "Write a response or attach your work.")
    key = filename = mime = None
    if file:
        data = await file.read(MAX_FILE_SIZE + 1)
        suffix, mime, _ = validate_document(file.filename or "", data, allow_text=True)
        key = get_storage().put(user.institution_id, data, suffix)
        filename = Path((file.filename or "work").replace("\\", "/")).name[:200]
    entry = m.AssignmentSubmission(
        institution_id=user.institution_id,
        post_id=post_id,
        user_id=user.id,
        version=previous.version + 1 if previous else 1,
        content=content.strip(),
        storage_key=key,
        filename=filename,
        mime=mime,
        late=late,
        rubric=config.rubric if config else DEFAULT_RUBRIC,
        skills=config.skills if config else [],
    )
    try:
        db.add(entry)
        db.flush()
        notify(
            db,
            user.institution_id,
            post.author_id,
            f"submission:{entry.id}",
            "Assignment work submitted",
            f"New work was submitted for {post.title}. Review it in Campus Hub → Assignments.",
            "assignment",
        )
        audit(db, user, "assignment.submitted", entry.id, {"post_id": post_id, "version": entry.version})
        db.add(
            m.ActivityEvent(
                institution_id=user.institution_id,
                user_id=user.id,
                kind="assignment.submitted",
                title="Assignment submitted",
                payload={"post_id": post_id},
            )
        )
        db.commit()
    except Exception:
        if key:
            get_storage().delete(key)
        raise
    return submission_view(db, entry)


@router.get("/assignments/submissions/{submission_id}/attachment")
def submission_file(submission_id: str, user=Depends(current_user), db: Session = Depends(get_db)):
    entry = scoped(db, m.AssignmentSubmission, user, submission_id)
    if user.id == entry.user_id:
        visible_post(db, user, entry.post_id)
    else:
        manage_assignment(db, user, entry.post_id)
    if not entry.storage_key:
        raise HTTPException(404, "No attachment.")
    audit(db, user, "assignment.download", entry.user_id, {"submission_id": entry.id})
    db.commit()
    return document_response(entry.storage_key, entry.filename, entry.mime)


class GradeInput(Strict):
    marks: list[int] = Field(default_factory=list, max_length=10)
    feedback: str = Field(min_length=5, max_length=5000)
    decision: Literal["graded", "returned"] = "graded"
    verify_skills: bool = False


@router.put("/assignments/submissions/{submission_id}/review")
def grade(submission_id: str, body: GradeInput, user=Depends(current_user), db: Session = Depends(get_db)):
    entry = scoped(db, m.AssignmentSubmission, user, submission_id)
    post = manage_assignment(db, user, entry.post_id)
    db.refresh(post, with_for_update=True)
    db.refresh(entry, with_for_update=True)
    latest = db.scalar(
        select(m.AssignmentSubmission)
        .where(m.AssignmentSubmission.post_id == entry.post_id, m.AssignmentSubmission.user_id == entry.user_id)
        .order_by(m.AssignmentSubmission.version.desc())
    )
    if latest.id != entry.id:
        raise HTTPException(409, "Review the latest submission version.")
    if body.decision == "graded" and (
        len(body.marks) != len(entry.rubric) or any(mark < 0 or mark > c["maximum"] for mark, c in zip(body.marks, entry.rubric))
    ):
        raise HTTPException(422, "Supply one valid mark per rubric criterion.")
    score = sum(body.marks) if body.decision == "graded" else None
    if body.verify_skills and (score is None or score < 60 or not entry.skills):
        raise HTTPException(422, "Faculty skill verification requires at least 60/100 and an assignment mapped to controlled skills.")
    entry.marks, entry.feedback, entry.score, entry.status = body.marks, body.feedback, score, body.decision
    entry.reviewed_by, entry.reviewed_at = user.id, m.now()
    student = db.get(m.User, entry.user_id)
    # Corrections revoke previous evidence without deleting its provenance.
    for evidence in db.scalars(
        select(m.SkillEvidence).where(m.SkillEvidence.user_id == student.id, m.SkillEvidence.institution_id == user.institution_id)
    ):
        if evidence.payload.get("post_id") == entry.post_id and evidence.payload.get("evidence_type") == "faculty_verified":
            evidence.payload = {**evidence.payload, "status": "superseded"}
    if body.verify_skills:
        for name in entry.skills:
            skill = skill_record(db, user.institution_id, name)
            db.add(
                m.SkillEvidence(
                    institution_id=user.institution_id,
                    user_id=student.id,
                    skill_id=skill.id,
                    payload={
                        "evidence_type": "faculty_verified",
                        "status": "confirmed",
                        "submission_id": entry.id,
                        "post_id": entry.post_id,
                        "score": score,
                        "quote": body.feedback,
                        "reviewer_id": user.id,
                        "provider": "faculty_rubric_v1",
                        "verified_at": m.now().isoformat(),
                    },
                )
            )
    db.flush()
    if placement_access(db, student)["allowed"]:
        adapt_after_event(db, student, "faculty_evidence_changed")
    notify(
        db,
        user.institution_id,
        student.id,
        f"review:{entry.id}:{secrets.token_hex(8)}",
        "Assignment feedback is ready",
        "Your teacher reviewed your submission. Open Assignments to read the feedback and rubric marks.",
        "assignment",
    )
    audit(db, user, "assignment.reviewed", entry.id, {"decision": body.decision, "score": score, "skills_verified": body.verify_skills})
    db.commit()
    return submission_view(db, entry)


@router.get("/passport")
def passport(student_id: str | None = None, user=Depends(current_user), db: Session = Depends(get_db)):
    student = student_access(db, user, student_id or user.id)
    evidence = evidence_profile(db, student)
    if student.id != user.id:
        audit(db, user, "passport.viewed", student.id)
        db.commit()
    return {
        "student": student.full_name,
        "roll_no": student.roll_no,
        "evidence": evidence,
        "method": "Evidence demonstrates a specific reviewed task or assessment; it does not guarantee general proficiency.",
        "counts": {
            kind: sum(e.get("evidence_type") == kind and e.get("status") not in {"rejected", "challenged", "superseded"} for e in evidence)
            for kind in ("resume_claim", "assessment_verified", "faculty_verified")
        },
    }


class ShareInput(Strict):
    evidence_ids: list[str] = Field(min_length=1, max_length=50)
    hours: int = Field(default=24, ge=1, le=168)
    consent: bool


@router.post("/passport/shares")
def share_passport(body: ShareInput, user=Depends(current_user), db: Session = Depends(get_db)):
    require(user, {"student"})
    rate_limit("passport-share:" + user.id, 20, 3600)
    if not body.consent:
        raise HTTPException(422, "Explicit sharing consent is required.")
    for evidence_id in body.evidence_ids:
        record = scoped(db, m.SkillEvidence, user, evidence_id)
        if record.user_id != user.id or record.payload.get("status") in {"challenged", "rejected", "superseded"}:
            raise HTTPException(422, "Choose only your current evidence.")
    token = secrets.token_urlsafe(40)
    entry = m.PassportShare(
        institution_id=user.institution_id,
        user_id=user.id,
        token_hash=digest(token),
        evidence_ids=sorted(set(body.evidence_ids)),
        expires_at=m.now() + timedelta(hours=body.hours),
    )
    db.add(entry)
    audit(db, user, "passport.share_created", user.id, {"count": len(body.evidence_ids), "hours": body.hours})
    db.commit()
    # Token is returned once. This is a bearer share link, never a public resume URL.
    return {"id": entry.id, "token": token, "expires_at": entry.expires_at}


@router.get("/passport/shares")
def shares(user=Depends(current_user), db: Session = Depends(get_db)):
    require(user, {"student"})
    return [
        {"id": s.id, "expires_at": s.expires_at, "revoked_at": s.revoked_at, "count": len(s.evidence_ids)}
        for s in db.scalars(select(m.PassportShare).where(m.PassportShare.user_id == user.id).order_by(m.PassportShare.created_at.desc()))
    ]


@router.delete("/passport/shares/{share_id}")
def revoke_share(share_id: str, user=Depends(current_user), db: Session = Depends(get_db)):
    entry = scoped(db, m.PassportShare, user, share_id)
    if entry.user_id != user.id:
        raise HTTPException(404, "Share not found.")
    entry.revoked_at = m.now()
    audit(db, user, "passport.share_revoked", user.id)
    db.commit()
    return {"ok": True}


@router.get("/passport/shared/{token}")
def public_passport(token: str, request: Request, db: Session = Depends(get_db)):
    rate_limit("public-passport:" + (request.client.host if request.client else "unknown"), 60, 60)
    entry = db.scalar(
        select(m.PassportShare).where(
            m.PassportShare.token_hash == digest(token), m.PassportShare.revoked_at.is_(None), m.PassportShare.expires_at > m.now()
        )
    )
    if not entry:
        raise HTTPException(404, "This share is invalid, revoked or expired.")
    student = db.get(m.User, entry.user_id)
    evidence = [
        e
        for e in evidence_profile(db, student)
        if e["id"] in entry.evidence_ids and e.get("status") not in {"rejected", "challenged", "superseded"}
    ]
    db.add(
        m.AuditLog(
            institution_id=entry.institution_id,
            actor_id=None,
            action="passport.share_accessed",
            target_id=student.id,
            details={"share_id": entry.id},
        )
    )
    db.commit()
    return {
        "student": student.full_name,
        "expires_at": entry.expires_at,
        "evidence": [{k: e.get(k) for k in ("skill", "evidence_type", "status", "score", "provider", "created_at")} for e in evidence],
    }


@router.get("/privacy/activity")
def privacy_activity(user=Depends(current_user), db: Session = Depends(get_db)):
    require(user, {"student"})
    logs = db.scalars(
        select(m.AuditLog)
        .where(m.AuditLog.institution_id == user.institution_id, m.AuditLog.target_id == user.id)
        .order_by(m.AuditLog.created_at.desc())
        .limit(100)
    )
    return [
        {
            "id": e.id,
            "action": e.action,
            "at": e.created_at,
            "actor": db.get(m.User, e.actor_id).full_name if e.actor_id else "Holder of your share link",
        }
        for e in logs
    ]


class AutomationInput(Strict):
    enabled: bool = True
    assignments: bool = True
    fees: bool = True
    evidence: bool = True


@router.get("/automations")
def automation_settings(user=Depends(current_user), db: Session = Depends(get_db)):
    require(user, ADMINS)
    entry = db.scalar(select(m.CampusAutomation).where(m.CampusAutomation.institution_id == user.institution_id))
    deliveries = list(
        db.scalars(
            select(m.AutomationDelivery)
            .where(m.AutomationDelivery.institution_id == user.institution_id)
            .order_by(m.AutomationDelivery.created_at.desc())
            .limit(50)
        )
    )
    return {
        "policy": {k: getattr(entry, k) if entry else True for k in ("enabled", "assignments", "fees", "evidence")},
        "last_run_at": entry.last_run_at if entry else None,
        "last_result": entry.last_result if entry else {},
        "deliveries": [{"id": d.id, "title": d.title, "source": d.source, "created_at": d.created_at} for d in deliveries],
    }


@router.put("/automations")
def configure_automation(body: AutomationInput, user=Depends(current_user), db: Session = Depends(get_db)):
    require(user, ADMINS)
    entry = db.scalar(select(m.CampusAutomation).where(m.CampusAutomation.institution_id == user.institution_id))
    if not entry:
        entry = m.CampusAutomation(institution_id=user.institution_id)
        db.add(entry)
    for key, value in body.model_dump().items():
        setattr(entry, key, value)
    audit(db, user, "automation.configured", details=body.model_dump())
    db.commit()
    return {"ok": True}


@router.post("/automations/run")
def run_automation(user=Depends(current_user), db: Session = Depends(get_db)):
    require(user, ADMINS)
    rate_limit("automation-run:" + user.id, 10, 60)
    result = run_automations(db, user.institution_id, force=True)
    audit(db, user, "automation.run", details=result)
    db.commit()
    return result


@router.get("/evidence-map")
def evidence_map(user=Depends(current_user), db: Session = Depends(get_db)):
    require(user, ADMINS | {"hod"})
    from ..intelligence.retrieval import allowed_documents

    documents = list(allowed_documents(db, user))
    ids = {d.id for d in documents}
    findings = list(db.scalars(select(m.EvidenceFinding).where(m.EvidenceFinding.institution_id == user.institution_id)))
    requirements = [
        r
        for r in db.scalars(select(m.EvidenceRequirement).where(m.EvidenceRequirement.institution_id == user.institution_id))
        if user.role != "hod" or r.payload.get("department_id") == user.department_id
    ]
    return {
        "requirements": [
            {
                "id": r.id,
                "title": r.title,
                "documents": [f.document_id for f in findings if f.requirement_id == r.id and f.document_id in ids],
            }
            for r in requirements
        ],
        "documents": [
            {
                "id": d.id,
                "title": d.title,
                "status": d.status,
                "version": d.version,
                "expires_at": d.expires_at,
                "owner": db.get(m.User, d.owner_id or d.uploaded_by).full_name,
                "department_id": d.department_id,
            }
            for d in documents
        ],
    }


class TranslationInput(Strict):
    text: str = Field(min_length=1, max_length=4000)


class TranslationOutput(Strict):
    translation: str = Field(min_length=1, max_length=10000)


@router.post("/translation-draft")
def translate(body: TranslationInput, user=Depends(current_user)):
    require(user, ADMINS | {"hod", "faculty", "campus_staff", "placement_officer"})
    rate_limit("translation:" + user.id, 5, 300)
    from ..intelligence.providers import structured

    try:
        result = structured(
            "Translate the supplied campus notice into Odia. Preserve names, dates, amounts and requirements exactly. Do not add instructions or facts. A staff member will review before publishing.",
            body.text,
            TranslationOutput,
        )
        return {"translation": result.translation, "provider": "ollama", "requires_review": True}
    except Exception:
        return {
            "translation": "",
            "provider": "unavailable",
            "requires_review": True,
            "message": "A local translation model is unavailable. Enter an Odia translation manually alongside the original notice.",
        }

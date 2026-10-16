from datetime import datetime, timedelta
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..db import get_db
from ..config import settings
from ..models import (
    SkillEvidence,
    Resume,
    RecruitmentDrive,
    CareerGoal,
    LearningRoadmap,
    LearningTask,
    AIWorkflowRun,
    TestQuestion,
    StudentAssessment,
    TestAttempt,
    now,
)
from ..security import current_user, require, scoped, student_access, audit, MANAGERS, rate_limit
from ..intelligence.preparation import evidence_profile, gap_analysis, plan_view, adapt_after_event
from ..intelligence.workflows import dispatch
from ..intelligence.providers import provider_health
from ..intelligence.taxonomy import resources, normalize
from ..intelligence.events import track
from ..intelligence.assessments import QuestionInput, AssessmentInput, start_attempt, attempt_view, finish_attempt

router = APIRouter(tags=["Preparation and assessments"])


def target_student(db, actor, student_id):
    return student_access(db, actor, student_id or actor.id)


def visible_drive(db, user, drive_id):
    drive = scoped(db, RecruitmentDrive, user, drive_id) if drive_id else None
    if drive and user.role == "student" and drive.status in {"draft", "reviewed"}:
        raise HTTPException(404, "Drive not found.")
    return drive


class WorkflowInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["resume", "recruitment", "gap", "learning", "adaptive", "evidence", "interview", "assessment_draft"]
    target_id: str | None = None
    question: str = Field(default="", max_length=2000)
    answer: str = Field(default="", max_length=8000)
    topic: str = Field(default="SQL", max_length=80)
    count: int = Field(default=2, ge=1, le=5)


@router.get("/intelligence/health")
def health(user=Depends(current_user)):
    return provider_health()


@router.post("/workflows")
def workflow(body: WorkflowInput, user=Depends(current_user), db: Session = Depends(get_db)):
    rate_limit("workflow:" + user.id, 20, 300)
    if body.kind == "resume":
        resume = scoped(db, Resume, user, body.target_id)
        student_access(db, user, resume.user_id)
    elif body.kind == "recruitment":
        require(user, MANAGERS)
        visible_drive(db, user, body.target_id)
    elif body.kind == "assessment_draft":
        require(user, MANAGERS)
    elif body.kind == "evidence":
        require(user, {"institution_admin", "platform_admin", "hod"})
    else:
        require(user, {"student"})
        visible_drive(db, user, body.target_id)
    run = dispatch(db, user, **body.model_dump())
    return {"id": run.id, "status": run.status, "provider": run.provider, **run.payload}


@router.get("/workflows/{run_id}")
def workflow_status(run_id: str, user=Depends(current_user), db: Session = Depends(get_db)):
    run = scoped(db, AIWorkflowRun, user, run_id)
    if run.payload["actor_id"] != user.id:
        raise HTTPException(404, "Workflow not found.")
    return {"id": run.id, "status": run.status, "provider": run.provider, **run.payload}


@router.get("/workflows")
def workflow_history(user=Depends(current_user), db: Session = Depends(get_db)):
    runs = list(
        db.scalars(
            select(AIWorkflowRun)
            .where(AIWorkflowRun.institution_id == user.institution_id, AIWorkflowRun.payload["actor_id"].as_string() == user.id)
            .order_by(AIWorkflowRun.created_at.desc())
            .limit(20)
        )
    )
    return [
        {
            "id": r.id,
            "status": r.status,
            "provider": r.provider,
            "kind": r.payload["kind"],
            "error": r.payload.get("error"),
            "latency_ms": r.payload.get("latency_ms"),
            "stages": r.payload.get("stages", []),
            "recoverable": r.status == "failed"
            or (
                r.status == "running"
                and datetime.fromisoformat(r.payload.get("started_at", now().isoformat())) < now() - timedelta(minutes=10)
            ),
        }
        for r in runs
        if r.payload.get("actor_id") == user.id
    ][:20]


@router.post("/workflows/{run_id}/retry")
def retry_workflow(run_id: str, user=Depends(current_user), db: Session = Depends(get_db)):
    rate_limit("workflow-retry:" + user.id, 10, 300)
    run = scoped(db, AIWorkflowRun, user, run_id)
    db.refresh(run, with_for_update=True)
    if run.payload["actor_id"] != user.id:
        raise HTTPException(404, "Workflow not found.")
    if run.status == "running" and datetime.fromisoformat(run.payload.get("started_at", now().isoformat())) < now() - timedelta(minutes=10):
        run.status = "failed"
    if run.status != "failed" or run.payload.get("retries", 0) >= 2:
        raise HTTPException(409, "This workflow is active, complete, or has reached its retry limit.")
    run.payload = {**run.payload, "retries": run.payload.get("retries", 0) + 1, "error": None}
    run.status = "queued"
    audit(db, user, "workflow.retry", run.id)
    db.commit()
    # Retrying keeps the original checkpoint thread and revalidates current permissions.
    from ..intelligence.workflows import execute_run

    if settings().queue_mode == "rq":
        from redis import Redis
        from rq import Queue
        from rq.job import Callback
        from ..intelligence.workflows import mark_workflow_failed

        try:
            Queue("campusmind-ai", connection=Redis.from_url(settings().redis_url)).enqueue(
                execute_run, run.id, job_timeout=180, on_failure=Callback(mark_workflow_failed, timeout=30)
            )
        except Exception:
            run.status = "failed"
            run.payload = {**run.payload, "error": "The AI queue is unavailable. Start Redis and retry."}
            db.commit()
    else:
        execute_run(run.id)
    db.refresh(run)
    return {"id": run.id, "status": run.status}


@router.get("/skills")
def skills(student_id: str | None = None, user=Depends(current_user), db: Session = Depends(get_db)):
    return evidence_profile(db, target_student(db, user, student_id))


class EvidenceReview(BaseModel):
    status: Literal["confirmed", "rejected", "challenged"]
    note: str = Field(default="", max_length=2000)


@router.put("/skills/{evidence_id}/review")
def review_skill(evidence_id: str, body: EvidenceReview, user=Depends(current_user), db: Session = Depends(get_db)):
    evidence = scoped(db, SkillEvidence, user, evidence_id)
    if evidence.user_id != user.id or evidence.payload.get("evidence_type") in {"assessment_verified", "faculty_verified"}:
        raise HTTPException(403, "Only your extracted claims can be reviewed here.")
    evidence.payload = {**evidence.payload, **body.model_dump(), "reviewed_at": now().isoformat()}
    track(db, user, "skills.reviewed", "Resume skill claim reviewed", evidence_id=evidence.id)
    adapt_after_event(db, user, "skill_evidence_changed")
    db.commit()
    return {"ok": True}


class GoalInput(BaseModel):
    role: str = Field(min_length=2, max_length=150)
    skills: list[str] = Field(min_length=1, max_length=20)
    hours_per_week: int = Field(default=6, ge=1, le=40)


@router.put("/career-goal")
def goal(body: GoalInput, user=Depends(current_user), db: Session = Depends(get_db)):
    require(user, {"student"})
    if any(not normalize(s) for s in body.skills):
        raise HTTPException(422, "Choose skills from the resource catalog taxonomy.")
    row = db.scalar(select(CareerGoal).where(CareerGoal.user_id == user.id))
    if not row:
        row = CareerGoal(institution_id=user.institution_id, user_id=user.id)
        db.add(row)
    row.payload = {**body.model_dump(), "skills": [normalize(s) for s in body.skills]}
    db.flush()
    adapt_after_event(db, user, "career_goal_changed")
    db.commit()
    return row.payload


@router.get("/matching")
def matching(drive_id: str | None = None, student_id: str | None = None, user=Depends(current_user), db: Session = Depends(get_db)):
    return gap_analysis(db, target_student(db, user, student_id), visible_drive(db, user, drive_id))


@router.get("/resources")
def catalog(user=Depends(current_user)):
    return resources()


@router.get("/roadmaps")
def roadmaps(student_id: str | None = None, user=Depends(current_user), db: Session = Depends(get_db)):
    student = target_student(db, user, student_id)
    return [
        plan_view(db, p)
        for p in db.scalars(
            select(LearningRoadmap).where(LearningRoadmap.user_id == student.id).order_by(LearningRoadmap.created_at.desc())
        )
    ]


@router.post("/roadmaps/{plan_id}/accept")
def accept(plan_id: str, user=Depends(current_user), db: Session = Depends(get_db)):
    db.refresh(user, with_for_update=True)
    plan = scoped(db, LearningRoadmap, user, plan_id)
    if plan.user_id != user.id:
        raise HTTPException(403, "Only the student can accept a roadmap.")
    if plan.payload["status"] != "proposed":
        raise HTTPException(409, "This proposal is no longer pending.")
    # Preserve work completed after the proposal was originally generated.
    plans = list(db.scalars(select(LearningRoadmap).where(LearningRoadmap.user_id == user.id)))
    copied = {t.payload.get("preserved_from") for t in db.scalars(select(LearningTask).where(LearningTask.roadmap_id == plan.id))}
    for old in plans:
        if old.payload["status"] == "active":
            for task in db.scalars(select(LearningTask).where(LearningTask.roadmap_id == old.id)):
                if task.payload.get("status") == "completed" and task.id not in copied:
                    db.add(
                        LearningTask(
                            institution_id=user.institution_id, roadmap_id=plan.id, payload={**task.payload, "preserved_from": task.id}
                        )
                    )
            old.payload = {**old.payload, "status": "archived"}
    plan.payload = {**plan.payload, "status": "active", "accepted_at": now().isoformat()}
    track(db, user, "roadmap.accepted", "Preparation roadmap accepted", roadmap_id=plan.id)
    db.commit()
    return plan_view(db, plan)


@router.post("/learning-tasks/{task_id}/complete")
def complete(task_id: str, user=Depends(current_user), db: Session = Depends(get_db)):
    db.refresh(user, with_for_update=True)
    task = scoped(db, LearningTask, user, task_id)
    plan = scoped(db, LearningRoadmap, user, task.roadmap_id)
    if plan.user_id != user.id or plan.payload["status"] != "active":
        raise HTTPException(403, "Only your active roadmap can be updated.")
    if task.payload.get("status") == "completed":
        return {"ok": True}
    task.payload = {**task.payload, "status": "completed", "completed_at": now().isoformat()}
    track(db, user, "learning.completed", "Learning task completed", task_id=task.id)
    db.commit()
    return {"ok": True}


@router.get("/questions")
def questions(user=Depends(current_user), db: Session = Depends(get_db)):
    require(user, MANAGERS)
    return [{"id": q.id, **q.payload} for q in db.scalars(select(TestQuestion).where(TestQuestion.institution_id == user.institution_id))]


@router.post("/questions")
def create_question(body: QuestionInput, user=Depends(current_user), db: Session = Depends(get_db)):
    require(user, MANAGERS)
    q = TestQuestion(institution_id=user.institution_id, payload={**body.model_dump(), "status": "draft", "created_by": user.id})
    db.add(q)
    db.commit()
    return {"id": q.id}


@router.post("/questions/{qid}/approve")
def approve_question(qid: str, user=Depends(current_user), db: Session = Depends(get_db)):
    require(user, MANAGERS)
    q = scoped(db, TestQuestion, user, qid)
    QuestionInput.model_validate({k: v for k, v in q.payload.items() if k in QuestionInput.model_fields})
    q.payload = {**q.payload, "status": "approved", "approved_by": user.id}
    audit(db, user, "question.approve", q.id)
    db.commit()
    return {"ok": True}


@router.get("/assessments")
def assessments(user=Depends(current_user), db: Session = Depends(get_db)):
    return [
        {"id": a.id, "title": a.title, "duration_minutes": a.payload["duration_minutes"], "question_count": len(a.payload["question_ids"])}
        for a in db.scalars(select(StudentAssessment).where(StudentAssessment.institution_id == user.institution_id))
    ]


@router.post("/assessments")
def create_assessment(body: AssessmentInput, user=Depends(current_user), db: Session = Depends(get_db)):
    require(user, MANAGERS)
    if len(set(body.question_ids)) != len(body.question_ids):
        raise HTTPException(422, "Each question can appear once.")
    for qid in body.question_ids:
        if scoped(db, TestQuestion, user, qid).payload.get("status") != "approved":
            raise HTTPException(409, "Approve all questions before publishing an assessment.")
    a = StudentAssessment(institution_id=user.institution_id, title=body.title, payload={**body.model_dump(), "approved_by": user.id})
    db.add(a)
    db.flush()
    audit(db, user, "assessment.publish", a.id)
    db.commit()
    return {"id": a.id}


@router.post("/assessments/{aid}/start")
def start(aid: str, user=Depends(current_user), db: Session = Depends(get_db)):
    require(user, {"student"})
    rate_limit("attempt:" + user.id, 30, 3600)
    a = start_attempt(db, user, scoped(db, StudentAssessment, user, aid))
    db.commit()
    return attempt_view(a)


class ManualMark(BaseModel):
    question_id: str
    points: float = Field(ge=0, le=10)
    feedback: str = Field(min_length=5, max_length=3000)


@router.put("/attempts/{attempt_id}/manual-review")
def manual_review(attempt_id: str, body: ManualMark, user=Depends(current_user), db: Session = Depends(get_db)):
    require(user, MANAGERS)
    attempt = scoped(db, TestAttempt, user, attempt_id)
    db.refresh(attempt, with_for_update=True)
    if attempt.payload["status"] != "submitted":
        raise HTTPException(409, "Wait until the attempt is submitted.")
    question = next((q for q in attempt.payload["questions"] if q["id"] == body.question_id), None)
    if not question or question["kind"] in {"single", "multiple"} or body.points > question["points"]:
        raise HTTPException(422, "Only subjective questions can receive valid examiner marks.")
    reviews = {
        **attempt.payload.get("manual_reviews", {}),
        body.question_id: {**body.model_dump(), "examiner_id": user.id, "reviewed_at": now().isoformat()},
    }
    subjective = [q for q in attempt.payload["questions"] if q["kind"] not in {"single", "multiple"}]
    pending = any(q["id"] not in reviews for q in subjective)
    earned = attempt.payload["earned"] + sum(v["points"] for v in reviews.values())
    maximum = attempt.payload["maximum"] + sum(q["points"] for q in subjective)
    attempt.payload = {
        **attempt.payload,
        "manual_reviews": reviews,
        "manual_review_pending": pending,
        "examiner_total_score": round(100 * earned / maximum, 2) if not pending and maximum else None,
    }
    audit(db, user, "assessment.manual_review", attempt.id)
    db.commit()
    return attempt_view(attempt)


@router.get("/attempts")
def attempts(student_id: str | None = None, user=Depends(current_user), db: Session = Depends(get_db)):
    student = target_student(db, user, student_id)
    rows = list(db.scalars(select(TestAttempt).where(TestAttempt.user_id == student.id).order_by(TestAttempt.created_at.desc())))
    for a in rows:
        if a.payload["status"] == "active" and datetime.fromisoformat(a.payload["expires_at"]) <= now():
            db.refresh(a, with_for_update=True)
            finish_attempt(db, student, a)
    db.commit()
    return [attempt_view(a) for a in rows]


class Answers(BaseModel):
    answers: dict[str, list[int] | str] = Field(default_factory=dict, max_length=100)


@router.put("/attempts/{attempt_id}/answers")
def answers(attempt_id: str, body: Answers, submit: bool = False, user=Depends(current_user), db: Session = Depends(get_db)):
    a = scoped(db, TestAttempt, user, attempt_id)
    db.refresh(a, with_for_update=True)
    if a.user_id != user.id:
        raise HTTPException(403, "Only your own attempt can be submitted.")
    if a.payload["status"] != "active":
        raise HTTPException(409, "This attempt is already submitted.")
    if datetime.fromisoformat(a.payload["expires_at"]) > now():
        questions = {q["id"]: q for q in a.payload["questions"]}
        for qid, value in body.answers.items():
            q = questions.get(qid)
            if not q or (isinstance(value, str) and len(value) > 12000):
                raise HTTPException(422, "Invalid answer.")
            if q["kind"] in {"single", "multiple"} and (
                not isinstance(value, list)
                or len(set(value)) != len(value)
                or any(i < 0 or i >= len(q["options"]) for i in value)
                or (q["kind"] == "single" and len(value) > 1)
            ):
                raise HTTPException(422, "Invalid answer selection.")
            if q["kind"] not in {"single", "multiple"} and not isinstance(value, str):
                raise HTTPException(422, "A written response is required.")
        a.payload = {**a.payload, "answers": {**a.payload["answers"], **body.answers}}
    else:
        submit = True
    if submit:
        finish_attempt(db, user, a)
    db.commit()
    return attempt_view(a)

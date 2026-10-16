"""Server-owned snapshots and deterministic objective marking; never execute student code."""

from typing import Literal
from datetime import timedelta
import secrets
from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select
from ..models import TestAttempt, TestQuestion, SkillEvidence, now
from .preparation import skill_record, adapt_after_event
from .taxonomy import normalize
from .events import track


class QuestionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    prompt: str = Field(min_length=5, max_length=4000)
    kind: Literal["single", "multiple", "short", "code", "interview"] = "single"
    topic: str = Field(min_length=2, max_length=100)
    difficulty: Literal["foundation", "intermediate", "advanced"] = "foundation"
    options: list[str] = Field(default_factory=list, max_length=8)
    correct: list[int] = Field(default_factory=list, max_length=8)
    explanation: str = Field(default="", max_length=3000)
    points: int = Field(default=1, ge=1, le=10)

    @model_validator(mode="after")
    def objective(self):
        if self.kind in {"single", "multiple"}:
            if len(self.options) < 2 or not self.correct or any(i < 0 or i >= len(self.options) for i in self.correct):
                raise ValueError("Objective questions need options and valid answer indexes.")
            if self.kind == "single" and len(self.correct) != 1:
                raise ValueError("Single choice needs one correct answer.")
            if len(set(self.correct)) != len(self.correct):
                raise ValueError("Duplicate answer indexes are not allowed.")
        elif self.correct:
            raise ValueError("Free text uses examiner review, not automatic answer matching.")
        return self


class AssessmentInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=3, max_length=150)
    question_ids: list[str] = Field(min_length=1, max_length=100)
    duration_minutes: int = Field(default=20, ge=1, le=180)
    randomize: bool = True


def start_attempt(db, user, assessment):
    db.refresh(user, with_for_update=True)
    existing = list(db.scalars(select(TestAttempt).where(TestAttempt.user_id == user.id, TestAttempt.assessment_id == assessment.id)))
    for attempt in existing:
        if attempt.payload["status"] == "active":
            return attempt
    questions = []
    for qid in assessment.payload["question_ids"]:
        q = db.get(TestQuestion, qid)
        if not q or q.institution_id != user.institution_id or q.payload.get("status") != "approved":
            raise HTTPException(409, "An approved question is unavailable.")
        questions.append({"id": q.id, **q.payload})
    if assessment.payload.get("randomize"):
        secrets.SystemRandom().shuffle(questions)
    attempt = TestAttempt(
        institution_id=user.institution_id,
        user_id=user.id,
        assessment_id=assessment.id,
        payload={
            "status": "active",
            "started_at": now().isoformat(),
            "expires_at": (now() + timedelta(minutes=assessment.payload["duration_minutes"])).isoformat(),
            "questions": questions,
            "answers": {},
            "title": assessment.title,
            "marking_version": "exact-set-v1",
        },
    )
    db.add(attempt)
    db.flush()
    track(db, user, "assessment.started", "Assessment started", attempt_id=attempt.id)
    return attempt


def attempt_view(attempt):
    p = attempt.payload
    questions = [{k: v for k, v in q.items() if k not in {"correct", "explanation", "approved_by"}} for q in p["questions"]]
    # Explanations and answer keys are available only after the attempt is finalized.
    if p["status"] != "active":
        questions = p["questions"]
    return {"id": attempt.id, **p, "questions": questions, "server_time": now().isoformat()}


def grade(questions, answers):
    rows, topics = [], {}
    earned = maximum = 0
    pending = False
    for q in questions:
        answer = answers.get(q["id"])
        objective = q["kind"] in {"single", "multiple"}
        valid = isinstance(answer, list) and all(type(i) is int for i in answer)
        correct = objective and valid and set(answer) == set(q["correct"])
        points = q["points"] if correct else 0
        if objective:
            earned += points
            maximum += q["points"]
            topic = topics.setdefault(q["topic"], {"earned": 0, "maximum": 0, "questions": 0})
            topic["earned"] += points
            topic["maximum"] += q["points"]
            topic["questions"] += 1
        else:
            pending = True
        rows.append(
            {
                "question_id": q["id"],
                "points": points if objective else None,
                "correct": correct if objective else None,
                "manual_review": not objective,
            }
        )
    return {
        "results": rows,
        "earned": earned,
        "maximum": maximum,
        "score": round(100 * earned / maximum, 2) if maximum else None,
        "topics": {name: {**v, "score": round(100 * v["earned"] / v["maximum"], 2)} for name, v in topics.items()},
        "manual_review_pending": pending,
    }


def finish_attempt(db, user, attempt):
    if attempt.payload["status"] != "active":
        return
    result = grade(attempt.payload["questions"], attempt.payload["answers"])
    attempt.payload = {
        **attempt.payload,
        **result,
        "status": "submitted",
        "submitted_at": now().isoformat(),
        "score_basis": "Objective questions only. Free-text and code require examiner review; no code is executed.",
    }
    for topic, value in result["topics"].items():
        name = normalize(topic)
        if name and value["questions"] >= 2 and value["score"] >= 70:
            skill = skill_record(db, user.institution_id, name)
            db.add(
                SkillEvidence(
                    institution_id=user.institution_id,
                    user_id=user.id,
                    skill_id=skill.id,
                    payload={
                        "skill": name,
                        "evidence_type": "assessment_verified",
                        "status": "verified",
                        "attempt_id": attempt.id,
                        "score": value["score"],
                        "scope": "Demonstrated on this approved question set; not a general proficiency certification.",
                        "provider": "deterministic_marking",
                    },
                )
            )
    db.flush()
    track(db, user, "assessment.submitted", "Assessment submitted and objective score recorded", attempt_id=attempt.id)
    adapt_after_event(db, user, "assessment_completed")

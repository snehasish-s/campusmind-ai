"""Authorized student erasure; retain a pseudonymous account ID for audit integrity."""

import secrets
from sqlalchemy import select, delete
from fastapi import HTTPException
from . import models as m
from .storage import get_storage
from .intelligence.workflows import checkpointer


def erase_student(db, student):
    for entry in db.scalars(select(m.AssignmentSubmission).where(m.AssignmentSubmission.user_id == student.id)):
        if entry.storage_key:
            get_storage().delete(entry.storage_key)
        db.delete(entry)
    db.execute(delete(m.PassportShare).where(m.PassportShare.user_id == student.id))
    db.execute(delete(m.AutomationDelivery).where(m.AutomationDelivery.user_id == student.id))
    for plan in db.scalars(select(m.FeePlan).where(m.FeePlan.institution_id == student.institution_id)):
        if plan.audience.get("student_id") == student.id or plan.audience.get("student_roll_no", "").upper() == student.roll_no.upper():
            plan.audience = {"redacted_after_erasure": True}
    # Accounting entries remain attached to a pseudonymous account for reconciliation.
    # They contain no copied student name/email. Institutional retention policy governs them.
    active_jobs = db.scalars(
        select(m.ImportJob).where(m.ImportJob.institution_id == student.institution_id, m.ImportJob.status.in_(["queued", "running"]))
    )
    if any(any(row.get("roll_no") == student.roll_no for row in j.rows) for j in active_jobs):
        raise HTTPException(409, "Wait for the student's active import job to finish before erasure.")
    resumes = list(db.scalars(select(m.Resume).where(m.Resume.user_id == student.id)))
    resume_ids = {r.id for r in resumes}
    runs = [
        r
        for r in db.scalars(select(m.AIWorkflowRun).where(m.AIWorkflowRun.institution_id == student.institution_id))
        if r.payload.get("actor_id") == student.id or r.payload.get("target_id") in resume_ids
    ]
    if any(r.status in {"queued", "running"} for r in runs):
        raise HTTPException(409, "Wait for the student's active workflow to finish before erasure.")
    if runs:
        with checkpointer() as saver:
            for run in runs:
                saver.delete_thread(f"{run.institution_id}:{run.payload['actor_id']}:{run.id}")
                db.delete(run)
    for resume in resumes:
        get_storage().delete(resume.storage_key)
        get_storage().delete(resume.text_key)
        db.execute(delete(m.ResumeAnalysis).where(m.ResumeAnalysis.resume_id == resume.id))
        db.delete(resume)
    for plan in db.scalars(select(m.LearningRoadmap).where(m.LearningRoadmap.user_id == student.id)):
        db.execute(delete(m.LearningTask).where(m.LearningTask.roadmap_id == plan.id))
        db.delete(plan)
    for model in (
        m.AuthSession,
        m.Invitation,
        m.SkillEvidence,
        m.TestAttempt,
        m.Conversation,
        m.CareerGoal,
        m.DriveApplication,
        m.EligibilityAppeal,
        m.Notification,
        m.ActivityEvent,
        m.StudentProfile,
        m.CampusReceipt,
    ):
        db.execute(delete(model).where(model.user_id == student.id))
    for job in db.scalars(select(m.ImportJob).where(m.ImportJob.institution_id == student.institution_id)):
        if any(row.get("roll_no") == student.roll_no for row in job.rows):
            # Retain completed job counters and idempotency fingerprint, not personal CSV rows.
            job.rows = [row for row in job.rows if row.get("roll_no") != student.roll_no]
    for request in db.scalars(select(m.DataRequest).where(m.DataRequest.user_id == student.id)):
        request.payload = {"erased": True}
    for job in db.scalars(
        select(m.CampusImport).where(m.CampusImport.institution_id == student.institution_id, m.CampusImport.kind == "cohorts")
    ):
        job.rows = [r for r in job.rows if r.get("user_id") != student.id]
    for post in db.scalars(select(m.CampusPost).where(m.CampusPost.institution_id == student.institution_id)):
        if post.audience.get("student_id") == student.id or post.audience.get("student_roll_no", "").upper() == student.roll_no.upper():
            if post.storage_key:
                get_storage().delete(post.storage_key)
                post.storage_key = None
            post.message = "Removed following student erasure request."
            post.title = "Removed private update"
            post.audience = {}
            post.withdrawn = True
    student.full_name = "Deleted student account"
    student.email = secrets.token_hex(16) + "@deleted.invalid"
    student.roll_no = "DELETED-" + secrets.token_hex(12)
    student.password_hash = None
    student.active = False
    student.department_id = None
    student.consent_at = None

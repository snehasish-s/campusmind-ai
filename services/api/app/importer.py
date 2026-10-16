import csv
import hashlib
import io
import json
import secrets
from datetime import timedelta
from pydantic import ValidationError
from sqlalchemy import select, or_
from sqlalchemy.exc import IntegrityError
from .db import SessionLocal
from .models import ImportJob, ImportError, User, StudentProfile, Department, ActivityEvent, now
from .schemas import StudentRow
from .invitations import issue_invitation

OPTIONAL_COHORT = ["section", "academic_year", "semester"]
COLUMNS = ["roll_no", "full_name", "email", "department", "graduation_year", "cgpa", "active_backlogs", "phone"]


def mark_import_failed(rq_job, connection, *exc_info):
    """RQ failure callback also covers worker timeouts, outside the import transaction."""
    with SessionLocal() as db:
        job = db.get(ImportJob, rq_job.args[0])
        if job and job.status != "completed" and (not rq_job.meta.get("lease") or rq_job.meta["lease"] == job.lease_token):
            job.status = "failed"
            job.failure = "Background worker stopped. Retry to resume from the last committed batch."
            db.commit()


def build_preview(db, actor, filename, content, mapping, policy):
    from fastapi import HTTPException

    if len(content) > 8 * 1024 * 1024:
        raise HTTPException(422, "CSV exceeds 8 MB.")
    try:
        reader = csv.DictReader(io.StringIO(content.decode("utf-8-sig")))
        headers = reader.fieldnames or []
        if len(headers) != len(set(headers)):
            raise HTTPException(422, "CSV contains duplicate column headers.")
        mapping = mapping or {column: column for column in COLUMNS}
        if set(mapping) - set(COLUMNS + OPTIONAL_COHORT) or any(mapping.get(c, c) not in headers for c in COLUMNS[:-1]):
            raise HTTPException(422, "Map all required columns to existing CSV headers.")
        raw_rows = list(reader)
    except (UnicodeDecodeError, csv.Error):
        raise HTTPException(422, "Upload a UTF-8 CSV file.")
    if not raw_rows or len(raw_rows) > 20000:
        raise HTTPException(422, "Import between 1 and 20,000 rows.")
    fingerprint = hashlib.sha256(content + json.dumps(mapping, sort_keys=True).encode() + policy.encode()).hexdigest()
    existing_job = db.scalar(
        select(ImportJob).where(ImportJob.institution_id == actor.institution_id, ImportJob.fingerprint == fingerprint)
    )
    if existing_job:
        return existing_job
    departments = set(db.scalars(select(Department.code).where(Department.institution_id == actor.institution_id)))
    users = list(db.scalars(select(User).where(User.institution_id == actor.institution_id)))
    by_roll, by_email = {u.roll_no: u for u in users}, {u.email: u for u in users}
    seen_roll, seen_email, rows, errors = set(), set(), [], []
    for number, raw in enumerate(raw_rows, 2):
        try:
            values = {c: (raw.get(mapping.get(c, c)) or "").strip() for c in COLUMNS}
            values.update({c: raw.get(mapping.get(c, c)) for c in OPTIONAL_COHORT if raw.get(mapping.get(c, c))})
            row = StudentRow.model_validate(values).model_dump(mode="json")
            for optional in OPTIONAL_COHORT:
                if optional not in values:
                    row.pop(optional, None)
            if row["department"] not in departments:
                raise ValueError("Unknown department code; create the department first")
            if row["roll_no"] in seen_roll or row["email"] in seen_email:
                raise ValueError("Duplicate roll number or email within CSV")
            seen_roll.add(row["roll_no"])
            seen_email.add(row["email"])
            roll_user, email_user = by_roll.get(row["roll_no"]), by_email.get(row["email"])
            if email_user and (not roll_user or email_user.id != roll_user.id):
                raise ValueError("Email belongs to another account")
            if roll_user and roll_user.role != "student":
                raise ValueError("Roll number belongs to a staff account")
            if roll_user and roll_user.email != row["email"]:
                raise ValueError("Changing an existing account email through CSV is not allowed")
            row["_row"] = number
            row["_action"] = ("skip" if policy == "skip" else "update") if roll_user else "create"
            rows.append(row)
        except (ValidationError, ValueError) as exc:
            if isinstance(exc, ValidationError):
                message = "; ".join(f"{e['loc'][0]}: {e['msg']}" for e in exc.errors())
            else:
                message = str(exc)
            errors.append((number, message))
    job = ImportJob(
        institution_id=actor.institution_id,
        actor_id=actor.id,
        filename=filename[:200],
        fingerprint=fingerprint,
        policy=policy,
        rows=rows,
        total=len(raw_rows),
        errors=len(errors),
    )
    db.add(job)
    db.flush()
    for number, message in errors:
        db.add(ImportError(institution_id=actor.institution_id, job_id=job.id, row_number=number, message=message))
    return job


def process_import(job_id):
    # One transaction per batch. Progress and accounts commit together; retries resume at the checkpoint.
    with SessionLocal() as db:
        job = db.scalar(select(ImportJob).where(ImportJob.id == job_id).with_for_update())
        if not job or job.status not in {"queued", "failed"}:
            return
        job.status = "running"
        job.failure = None
        lease = secrets.token_hex(24)
        job.lease_token = lease
        job.lease_expires_at = now() + timedelta(minutes=15)
        from rq import get_current_job

        current_job = get_current_job()
        if current_job:
            current_job.meta["lease"] = lease
            current_job.save_meta()
        db.commit()
        try:
            departments = {d.code: d.id for d in db.scalars(select(Department).where(Department.institution_id == job.institution_id))}
            rows = job.rows
            for start in range(job.processed, len(rows), 100):
                # Fence a recovered/stale process before each batch. PostgreSQL keeps
                # this row locked until the account batch and checkpoint commit.
                db.refresh(job, with_for_update=True)
                if job.lease_token != lease or job.status != "running":
                    return
                new_users = []
                for row in rows[start : start + 100]:
                    try:
                        with db.begin_nested():
                            user = db.scalar(
                                select(User).where(
                                    User.institution_id == job.institution_id,
                                    or_(User.roll_no == row["roll_no"], User.email == row["email"]),
                                )
                            )
                            if user and (user.role != "student" or user.roll_no != row["roll_no"] or user.email != row["email"]):
                                raise ValueError("Account changed since preview; identity conflict")
                            if user and job.policy == "skip":
                                job.skipped += 1
                                continue
                            if not user:
                                user = User(
                                    institution_id=job.institution_id,
                                    roll_no=row["roll_no"],
                                    full_name=row["full_name"],
                                    email=row["email"],
                                    department_id=departments[row["department"]],
                                )
                                db.add(user)
                                db.flush()
                                profile = StudentProfile(
                                    institution_id=job.institution_id, user_id=user.id, graduation_year=row["graduation_year"]
                                )
                                db.add(profile)
                                new_users.append(user.id)
                                job.created += 1
                            else:
                                profile = db.scalar(select(StudentProfile).where(StudentProfile.user_id == user.id))
                                job.updated += 1
                            user.full_name = row["full_name"]
                            user.department_id = departments[row["department"]]
                            for field in ("graduation_year", "cgpa", "active_backlogs", "phone", "section", "academic_year", "semester"):
                                if field in row:
                                    setattr(profile, field, row[field])
                            db.flush()
                    except (IntegrityError, ValueError, KeyError):
                        db.add(
                            ImportError(
                                institution_id=job.institution_id,
                                job_id=job.id,
                                row_number=row["_row"],
                                message="Record conflicts with current institution data.",
                            )
                        )
                        job.errors += 1
                job.processed = min(start + 100, len(rows))
                job.lease_expires_at = now() + timedelta(minutes=15)
                db.commit()
                # Delivery is deliberately separate from account persistence. Failed delivery is recoverable by resend.
                for user_id in new_users:
                    db.refresh(job, with_for_update=True)
                    if job.lease_token != lease or job.status != "running":
                        return
                    issue_invitation(db, db.get(User, user_id))
                    job.lease_expires_at = now() + timedelta(minutes=15)
                    db.commit()
            job.status = "completed"
            job.lease_expires_at = None
            db.add(
                ActivityEvent(
                    institution_id=job.institution_id,
                    title=f"Student import completed: {job.created} created, {job.updated} updated",
                    kind="import",
                )
            )
            db.commit()
        except Exception:
            db.rollback()
            job = db.get(ImportJob, job_id)
            if job.lease_token != lease:
                return
            job.status = "failed"
            job.failure = "Import interrupted. Retry to resume from the last committed batch."
            db.commit()
            raise

import csv
import io
import json
from datetime import timedelta
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from fastapi.responses import Response
from sqlalchemy import select, update
from sqlalchemy.orm import Session
from redis import Redis
from rq import Queue
from rq.job import Callback
from ..config import settings
from ..db import get_db
from ..models import ImportJob, ImportError, now
from ..security import current_user, require, MANAGERS, scoped, audit, rate_limit, csv_safe
from ..importer import COLUMNS, OPTIONAL_COHORT, build_preview, process_import, mark_import_failed

router = APIRouter(prefix="/imports", tags=["Bulk onboarding"])


def job_view(job):
    return {
        "recoverable": job.status in {"queued", "running"} and bool(job.lease_expires_at and job.lease_expires_at < now()),
        **{
            key: getattr(job, key)
            for key in (
                "id",
                "filename",
                "policy",
                "status",
                "total",
                "processed",
                "created",
                "updated",
                "skipped",
                "errors",
                "failure",
                "created_at",
            )
        },
    }


@router.get("/template")
def template(user=Depends(current_user)):
    require(user, MANAGERS)
    return Response(
        ",".join(COLUMNS + OPTIONAL_COHORT) + "\nSYN20270001,Synthetic Student 1,student0001@example.com,CSE,2027,8.1,0,,A,4,7\n",
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="campusmind-students-template.csv"'},
    )


@router.get("")
def history(user=Depends(current_user), db: Session = Depends(get_db)):
    require(user, MANAGERS)
    return [
        job_view(j)
        for j in db.scalars(
            select(ImportJob).where(ImportJob.institution_id == user.institution_id).order_by(ImportJob.created_at.desc()).limit(100)
        )
    ]


@router.post("/preview")
async def preview(
    file: UploadFile = File(...),
    mapping: str = Form("{}"),
    policy: str = Form("skip"),
    user=Depends(current_user),
    db: Session = Depends(get_db),
):
    require(user, MANAGERS)
    rate_limit(f"import:{user.id}", 10, 60)
    if policy not in {"skip", "update"} or not (file.filename or "").lower().endswith(".csv"):
        raise HTTPException(422, "Choose a CSV and a skip or update policy.")
    try:
        parsed = json.loads(mapping)
        if not isinstance(parsed, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in parsed.items()):
            raise ValueError()
    except (ValueError, TypeError):
        raise HTTPException(422, "Invalid column mapping.")
    job = build_preview(db, user, file.filename, await file.read(8 * 1024 * 1024 + 1), parsed, policy)
    audit(db, user, "import.preview", job.id)
    db.commit()
    return {
        **job_view(job),
        "preview": job.rows[:25],
        "actions": {action: sum(1 for r in job.rows if r["_action"] == action) for action in ("create", "update", "skip")},
    }


@router.get("/{job_id}")
def detail(job_id: str, user=Depends(current_user), db: Session = Depends(get_db)):
    require(user, MANAGERS)
    job = scoped(db, ImportJob, user, job_id)
    errors = db.scalars(
        select(ImportError).where(ImportError.job_id == job.id, ImportError.institution_id == user.institution_id).limit(200)
    )
    return {**job_view(job), "preview": job.rows[:25], "row_errors": [{"row": e.row_number, "message": e.message} for e in errors]}


@router.post("/{job_id}/confirm")
def confirm(job_id: str, user=Depends(current_user), db: Session = Depends(get_db)):
    require(user, MANAGERS)
    job = scoped(db, ImportJob, user, job_id)
    result = db.execute(
        update(ImportJob)
        .where(ImportJob.id == job.id, ImportJob.status.in_(["preview", "failed"]))
        .values(status="queued", lease_expires_at=now() + timedelta(minutes=15))
    )
    if result.rowcount:
        audit(db, user, "import.confirm", job.id)
        db.commit()
        if settings().queue_mode == "sync":
            process_import(job.id)
        else:
            try:
                Queue("campusmind", connection=Redis.from_url(settings().redis_url)).enqueue(
                    process_import,
                    job.id,
                    job_timeout=7200,
                    result_ttl=86400,
                    on_failure=Callback(mark_import_failed, timeout=30),
                )
            except Exception:
                job.status = "failed"
                job.failure = "Worker queue is unavailable. Start Redis and retry."
                db.commit()
                raise HTTPException(503, job.failure)
    db.expire_all()
    return job_view(db.get(ImportJob, job_id))


@router.post("/{job_id}/recover")
def recover(job_id: str, user=Depends(current_user), db: Session = Depends(get_db)):
    require(user, MANAGERS)
    scoped(db, ImportJob, user, job_id)
    job = db.scalar(select(ImportJob).where(ImportJob.id == job_id, ImportJob.institution_id == user.institution_id).with_for_update())
    if job.status not in {"queued", "running"} or not job.lease_expires_at or job.lease_expires_at >= now():
        raise HTTPException(409, "This job has no expired processing lease. Wait for active processing to finish.")
    job.status = "failed"
    job.lease_token = None
    job.failure = "An expired processing lease was recovered. Retry from the last committed batch."
    audit(db, user, "import.recover", job.id)
    db.commit()
    return job_view(job)


@router.get("/{job_id}/errors.csv")
def error_report(job_id: str, user=Depends(current_user), db: Session = Depends(get_db)):
    require(user, MANAGERS)
    job = scoped(db, ImportJob, user, job_id)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["row", "error"])
    for error in db.scalars(select(ImportError).where(ImportError.job_id == job.id, ImportError.institution_id == user.institution_id)):
        message = error.message
        writer.writerow([error.row_number, csv_safe(message)])
    return Response(output.getvalue(), media_type="text/csv", headers={"Content-Disposition": 'attachment; filename="import-errors.csv"'})

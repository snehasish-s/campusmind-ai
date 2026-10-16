"""Explicit operator maintenance; default dry run. Does not delete source evidence or scores."""

import argparse
import sys
from pathlib import Path
from datetime import timedelta
from sqlalchemy import select, delete

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "services/api"))
from app.db import SessionLocal  # noqa: E402
from app.config import settings  # noqa: E402
from app.models import AuthSession, RateLimitBucket, Invitation, ImportJob, AIWorkflowRun, Conversation, CampusImport, now  # noqa: E402
from app.intelligence.workflows import checkpointer  # noqa: E402

parser = argparse.ArgumentParser()
parser.add_argument("--apply", action="store_true")
args = parser.parse_args()
cutoff = now() - timedelta(days=settings().retention_days)
with SessionLocal() as db:
    jobs = list(db.scalars(select(ImportJob).where(ImportJob.created_at < cutoff, ImportJob.status.in_(["completed", "failed"]))))
    campus_jobs = list(db.scalars(select(CampusImport).where(CampusImport.created_at < cutoff, CampusImport.kind == "cohorts")))
    runs = list(
        db.scalars(select(AIWorkflowRun).where(AIWorkflowRun.created_at < cutoff, AIWorkflowRun.status.in_(["completed", "failed"])))
    )
    chats = list(db.scalars(select(Conversation).where(Conversation.created_at < cutoff)))
    print(
        {
            "mode": "apply" if args.apply else "dry_run",
            "retention_days": settings().retention_days,
            "import_payloads": len(jobs),
            "workflow_checkpoints": len(runs),
            "campus_cohort_payloads": len(campus_jobs),
            "conversations": len(chats),
        }
    )
    if args.apply:
        for model in (AuthSession, RateLimitBucket, Invitation):
            db.execute(delete(model).where(model.expires_at < cutoff))
        for job in jobs + campus_jobs:
            job.rows = []
        if runs:
            with checkpointer() as saver:
                for run in runs:
                    saver.delete_thread(f"{run.institution_id}:{run.payload['actor_id']}:{run.id}")
                    db.delete(run)
        for chat in chats:
            db.delete(chat)
        db.commit()

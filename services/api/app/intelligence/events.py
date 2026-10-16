from ..models import ActivityEvent


def track(db, actor, kind, title, **metadata):
    db.add(
        ActivityEvent(
            institution_id=actor.institution_id,
            user_id=actor.id,
            kind=kind,
            title=title,
            payload={
                k: v
                for k, v in metadata.items()
                if k in {"drive_id", "attempt_id", "roadmap_id", "document_id", "resume_id", "skill", "source", "version"}
            },
        )
    )

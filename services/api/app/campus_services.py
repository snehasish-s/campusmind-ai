"""Deterministic campus actions. No model controls recipients, money or grades."""

from datetime import timedelta
from zoneinfo import ZoneInfo
from datetime import datetime, timezone
from sqlalchemy import select
from . import models as m
from .routers.campus import matches

DEFAULT_RUBRIC = [{"label": "Correctness", "maximum": 60}, {"label": "Explanation", "maximum": 40}]


def notify(db, tenant, user_id, key, title, message, source):
    from sqlalchemy.dialects.postgresql import insert as pg_insert
    from sqlalchemy.dialects.sqlite import insert as sqlite_insert

    insert = pg_insert if db.bind.dialect.name == "postgresql" else sqlite_insert
    delivered = db.execute(
        insert(m.AutomationDelivery)
        .values(institution_id=tenant, user_id=user_id, event_key=key, title=title, source=source)
        .on_conflict_do_nothing(index_elements=["institution_id", "event_key", "user_id"])
        .returning(m.AutomationDelivery.id)
    ).scalar_one_or_none()
    if delivered:
        db.add(m.Notification(institution_id=tenant, user_id=user_id, title=title, message=message))
    return bool(delivered)


def run_automations(db, tenant, force=False, at=None):
    at = at or m.now()
    # Insert once, then lock the tenant policy; multiple API replicas cannot duplicate deliveries.
    from sqlalchemy.dialects.postgresql import insert as pg_insert
    from sqlalchemy.dialects.sqlite import insert as sqlite_insert

    insert = pg_insert if db.bind.dialect.name == "postgresql" else sqlite_insert
    db.execute(insert(m.CampusAutomation).values(institution_id=tenant).on_conflict_do_nothing(index_elements=["institution_id"]))
    policy = db.scalar(select(m.CampusAutomation).where(m.CampusAutomation.institution_id == tenant).with_for_update())
    if not policy.enabled or (not force and policy.last_run_at and at - policy.last_run_at < timedelta(minutes=15)):
        return {"delivered": 0, "skipped": True}
    students = list(
        db.execute(
            select(m.User, m.StudentProfile)
            .join(m.StudentProfile, m.StudentProfile.user_id == m.User.id)
            .where(m.User.institution_id == tenant, m.User.role == "student", m.User.active.is_(True))
        )
    )
    delivered = 0
    if policy.assignments:
        posts = list(
            db.scalars(
                select(m.CampusPost).where(
                    m.CampusPost.institution_id == tenant,
                    m.CampusPost.kind == "assignment",
                    m.CampusPost.withdrawn.is_(False),
                    m.CampusPost.due_at > at,
                    m.CampusPost.due_at <= at + timedelta(hours=24),
                )
            )
        )
        latest = {}
        for entry in db.scalars(
            select(m.AssignmentSubmission).where(m.AssignmentSubmission.institution_id == tenant).order_by(m.AssignmentSubmission.version)
        ):
            latest[(entry.post_id, entry.user_id)] = entry.status
        submitted = {key for key, status in latest.items() if status != "returned"}
        for post in posts:
            for student, profile in students:
                if matches(student, profile, post.audience) and (post.id, student.id) not in submitted:
                    delivered += notify(
                        db,
                        tenant,
                        student.id,
                        f"assignment:{post.id}:24h",
                        "Assignment due within 24 hours",
                        f"{post.title}. Open Campus Hub → Assignments to submit your work.",
                        "assignment",
                    )
    if policy.fees:
        rows = db.execute(
            select(m.FeeInvoice, m.FeePlan)
            .join(m.FeePlan, m.FeePlan.id == m.FeeInvoice.plan_id)
            .join(m.User, m.User.id == m.FeeInvoice.user_id)
            .where(
                m.FeeInvoice.institution_id == tenant,
                m.FeeInvoice.status == "unpaid",
                m.User.active.is_(True),
                m.FeePlan.due_at <= at + timedelta(days=7),
            )
        )
        for invoice, plan in rows:
            days = (plan.due_at.date() - at.date()).days
            stage = "overdue" if days < 0 else "1d" if days <= 1 else "3d" if days <= 3 else "7d"
            delivered += notify(
                db,
                tenant,
                invoice.user_id,
                f"fee:{invoice.id}:{stage}",
                "Fee payment overdue" if days < 0 else "Upcoming fee deadline",
                f"{plan.title}: INR {invoice.amount_paise / 100:.2f}. Review your invoice in Campus Hub → Fees.",
                "fee",
            )
    if policy.evidence:
        documents = db.scalars(
            select(m.InstitutionalDocument).where(
                m.InstitutionalDocument.institution_id == tenant,
                m.InstitutionalDocument.expires_at <= at + timedelta(days=7),
                m.InstitutionalDocument.status != "superseded",
            )
        )
        for document in documents:
            stage = "expired" if document.expires_at <= at else "7d"
            delivered += notify(
                db,
                tenant,
                document.owner_id or document.uploaded_by,
                f"evidence:{document.id}:{stage}",
                "Evidence needs renewal",
                f"{document.title}: review its expiry and upload a new version in CollegeOps.",
                "evidence",
            )
    policy.last_run_at = at
    policy.last_result = {"delivered": delivered, "method": "deterministic_rules_v1", "at": at.isoformat()}
    return policy.last_result


def automatic_tick():
    from .db import SessionLocal

    with SessionLocal() as db:
        tenant_ids = list(db.scalars(select(m.Institution.id)))
    for tenant in tenant_ids:
        with SessionLocal() as db:
            run_automations(db, tenant)
            db.commit()


def student_timeline(db, user):
    from .security import placement_access
    from .intelligence.preparation import objective_eligibility

    profile = db.scalar(
        select(m.StudentProfile).where(m.StudentProfile.user_id == user.id, m.StudentProfile.institution_id == user.institution_id)
    )
    at = m.now()
    local = datetime.now(ZoneInfo("Asia/Kolkata"))
    items, conflicts = [], []
    latest_submissions = {}
    for entry in db.scalars(
        select(m.AssignmentSubmission).where(m.AssignmentSubmission.user_id == user.id).order_by(m.AssignmentSubmission.version)
    ):
        latest_submissions[entry.post_id] = entry.status
    submissions = {post_id for post_id, status in latest_submissions.items() if status != "returned"}
    receipts = {
        r.post_id
        for r in db.scalars(select(m.CampusReceipt).where(m.CampusReceipt.user_id == user.id, m.CampusReceipt.read_at.is_not(None)))
    }
    for post in db.scalars(
        select(m.CampusPost).where(m.CampusPost.institution_id == user.institution_id, m.CampusPost.withdrawn.is_(False))
    ):
        if not matches(user, profile, post.audience):
            continue
        if post.kind == "assignment" and post.id not in submissions:
            items.append(
                {
                    "id": post.id,
                    "title": post.title,
                    "kind": "assignment",
                    "due_at": post.due_at,
                    "href": "/app/assignments",
                    "reason": "Your current academic cohort matches the teacher's assignment.",
                    "priority": 0 if post.due_at and post.due_at <= at + timedelta(days=2) else 2,
                }
            )
        elif post.id not in receipts:
            items.append(
                {
                    "id": post.id,
                    "title": post.title,
                    "kind": "notice",
                    "due_at": None,
                    "href": "/app/campus",
                    "reason": "An official update matches your current cohort and awaits acknowledgement.",
                    "priority": 3,
                }
            )
    slots = []
    for slot in db.scalars(
        select(m.TeachingSlot).where(
            m.TeachingSlot.institution_id == user.institution_id,
            m.TeachingSlot.active.is_(True),
            m.TeachingSlot.valid_from <= local.date().isoformat(),
            m.TeachingSlot.valid_until >= local.date().isoformat(),
        )
    ):
        audience = {k: getattr(slot, k) for k in ("department_id", "graduation_year", "academic_year", "semester", "section")}
        if matches(user, profile, audience):
            teacher = db.get(m.User, slot.teacher_id)
            slots.append(
                {
                    "id": slot.id,
                    "subject": slot.subject,
                    "weekday": slot.weekday,
                    "starts": slot.starts,
                    "ends": slot.ends,
                    "room": slot.room,
                    "teacher": teacher.full_name,
                    "valid_from": slot.valid_from,
                    "valid_until": slot.valid_until,
                }
            )
            if slot.weekday == local.weekday():
                items.append(
                    {
                        "id": slot.id,
                        "title": slot.subject,
                        "kind": "class",
                        "due_at": datetime.combine(
                            local.date(), datetime.strptime(slot.starts, "%H:%M").time(), tzinfo=ZoneInfo("Asia/Kolkata")
                        )
                        .astimezone(timezone.utc)
                        .replace(tzinfo=None),
                        "href": "/app/timetable",
                        "reason": f"Today's timetable · {slot.starts}–{slot.ends} · {slot.room}",
                        "priority": 1,
                    }
                )
    for invoice, plan in db.execute(
        select(m.FeeInvoice, m.FeePlan)
        .join(m.FeePlan, m.FeePlan.id == m.FeeInvoice.plan_id)
        .where(m.FeeInvoice.institution_id == user.institution_id, m.FeeInvoice.user_id == user.id, m.FeeInvoice.status == "unpaid")
    ):
        items.append(
            {
                "id": invoice.id,
                "title": plan.title,
                "kind": "fee",
                "due_at": plan.due_at,
                "href": "/app/fees",
                "reason": f"Issued invoice · INR {invoice.amount_paise / 100:.2f}. Payment is always initiated by you.",
                "priority": 0 if plan.due_at <= at else 2,
            }
        )
    if placement_access(db, user)["allowed"]:
        attempts = list(
            db.scalars(select(m.TestAttempt).where(m.TestAttempt.user_id == user.id, m.TestAttempt.institution_id == user.institution_id))
        )
        for assessment in db.scalars(select(m.StudentAssessment).where(m.StudentAssessment.institution_id == user.institution_id)):
            related = [a for a in attempts if a.assessment_id == assessment.id]
            active = next((a for a in related if a.payload.get("status") == "active"), None)
            if active or not related:
                items.append(
                    {
                        "id": assessment.id,
                        "title": assessment.title,
                        "kind": "assessment",
                        "due_at": datetime.fromisoformat(active.payload["expires_at"]) if active else None,
                        "href": "/app/mock-tests",
                        "reason": "Continue your saved timed attempt."
                        if active
                        else "An approved assessment is available for your institution.",
                        "priority": 0 if active else 4,
                    }
                )
        for drive in db.scalars(
            select(m.RecruitmentDrive).where(
                m.RecruitmentDrive.institution_id == user.institution_id,
                m.RecruitmentDrive.status.in_(["published", "open"]),
                m.RecruitmentDrive.deadline > at,
            )
        ):
            eligible = objective_eligibility(db, user, drive)["status"]
            items.append(
                {
                    "id": drive.id,
                    "title": drive.position,
                    "kind": "drive",
                    "due_at": drive.deadline,
                    "href": "/app/drives",
                    "reason": "Objective eligibility: " + eligible.replace("_", " "),
                    "priority": 2,
                }
            )
            drive_local = drive.drive_date.replace(tzinfo=timezone.utc).astimezone(ZoneInfo("Asia/Kolkata"))
            for slot in slots:
                if (
                    slot["valid_from"] <= drive_local.date().isoformat() <= slot["valid_until"]
                    and slot["weekday"] == drive_local.weekday()
                    and slot["starts"] <= drive_local.strftime("%H:%M") < slot["ends"]
                ):
                    conflicts.append(
                        {
                            "kind": "schedule",
                            "message": f"{drive.position} starts during {slot['subject']} on {drive_local.date()}. Contact your coordinator to resolve this overlap.",
                        }
                    )
        for plan in db.scalars(select(m.LearningRoadmap).where(m.LearningRoadmap.user_id == user.id)):
            if plan.payload.get("status") == "proposed":
                items.append(
                    {
                        "id": plan.id,
                        "title": "Review your proposed preparation plan",
                        "kind": "roadmap",
                        "due_at": None,
                        "href": "/app/roadmap",
                        "reason": plan.payload.get("explanation", "New evidence changed your preparation priorities."),
                        "priority": 2,
                    }
                )
            elif plan.payload.get("status") == "active":
                for task in db.scalars(select(m.LearningTask).where(m.LearningTask.roadmap_id == plan.id)):
                    if task.payload.get("status") != "completed":
                        items.append(
                            {
                                "id": task.id,
                                "title": task.payload.get("title", "Learning task"),
                                "kind": "learning",
                                "due_at": None,
                                "href": "/app/roadmap",
                                "reason": "Your accepted learning plan · " + str(task.payload.get("hours", 0)) + " hours",
                                "priority": 4,
                            }
                        )
    deadlines = {}
    for item in items:
        if item["kind"] in {"assignment", "drive"} and item["due_at"] and item["due_at"] >= at:
            day = item["due_at"].replace(tzinfo=timezone.utc).astimezone(ZoneInfo("Asia/Kolkata")).date().isoformat()
            deadlines.setdefault(day, []).append(item["title"])
    for day, titles in deadlines.items():
        if len(titles) >= 2:
            conflicts.append(
                {
                    "kind": "workload",
                    "message": f"{len(titles)} deadlines on {day}: {', '.join(titles)}. Start early or ask your coordinator for help.",
                }
            )
    items.sort(key=lambda i: (i["priority"], i["due_at"] or datetime.max, i["title"]))
    return {
        "items": items[:150],
        "conflicts": conflicts,
        "timetable": slots,
        "timezone": "Asia/Kolkata",
        "method": "deterministic_priority_v1",
        "generated_at": at,
    }

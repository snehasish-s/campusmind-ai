import hashlib
import json
from sqlalchemy import select
from ..models import (
    Skill,
    SkillEvidence,
    StudentProfile,
    Department,
    CareerGoal,
    LearningRoadmap,
    LearningTask,
    DriveReview,
    RecruitmentDrive,
    EligibilityAppeal,
    Notification,
    now,
)
from .taxonomy import SKILLS, normalize
from .events import track


def skill_record(db, tenant, name):
    from sqlalchemy.dialects.postgresql import insert as pg_insert
    from sqlalchemy.dialects.sqlite import insert as sqlite_insert

    insert = pg_insert if db.bind.dialect.name == "postgresql" else sqlite_insert
    db.execute(
        insert(Skill)
        .values(institution_id=tenant, name=name, payload={}, schema_version=1)
        .on_conflict_do_nothing(index_elements=["institution_id", "name"])
    )
    return db.scalar(select(Skill).where(Skill.institution_id == tenant, Skill.name == name))


def evidence_profile(db, user):
    output = []
    for e in db.scalars(select(SkillEvidence).where(SkillEvidence.institution_id == user.institution_id, SkillEvidence.user_id == user.id)):
        skill = db.get(Skill, e.skill_id)
        output.append({"id": e.id, "skill": skill.name, **e.payload, "created_at": e.created_at.isoformat()})
    return output


def eligibility_context(db, tenant):
    """Constant-query cohort inputs; publication never makes 1,000 model calls."""
    return {
        "profiles": {p.user_id: p for p in db.scalars(select(StudentProfile).where(StudentProfile.institution_id == tenant))},
        "departments": {d.id: d for d in db.scalars(select(Department).where(Department.institution_id == tenant))},
        "reviews": {r.drive_id: r for r in db.scalars(select(DriveReview).where(DriveReview.institution_id == tenant))},
        "appeals": {
            (a.user_id, a.drive_id): a
            for a in db.scalars(
                select(EligibilityAppeal)
                .where(EligibilityAppeal.institution_id == tenant, EligibilityAppeal.status == "approved")
                .order_by(EligibilityAppeal.created_at)
            )
        },
    }


def objective_eligibility(db, user, drive, context=None):
    if user.institution_id != drive.institution_id:
        raise ValueError("Eligibility requires matching institutions")
    profile = (
        context["profiles"].get(user.id)
        if context
        else db.scalar(
            select(StudentProfile).where(StudentProfile.user_id == user.id, StudentProfile.institution_id == user.institution_id)
        )
    )
    department = (
        context["departments"].get(user.department_id)
        if context
        else (db.get(Department, user.department_id) if user.department_id else None)
    )
    checks = [
        {
            "rule": "Minimum CGPA",
            "expected": drive.min_cgpa,
            "actual": profile.cgpa if profile else None,
            "passes": profile.cgpa >= drive.min_cgpa if profile else None,
        },
        {
            "rule": "Maximum active backlogs",
            "expected": drive.max_backlogs,
            "actual": profile.active_backlogs if profile else None,
            "passes": profile.active_backlogs <= drive.max_backlogs if profile else None,
        },
        {
            "rule": "Graduation batch",
            "expected": drive.graduation_year,
            "actual": profile.graduation_year if profile else None,
            "passes": profile.graduation_year == drive.graduation_year if profile else None,
        },
        {
            "rule": "Eligible department",
            "expected": drive.eligible_branches or ["All"],
            "actual": department.code if department else None,
            "passes": not drive.eligible_branches or (department.code in drive.eligible_branches if department else None),
        },
    ]
    status = (
        "review_required"
        if any(c["passes"] is None for c in checks)
        else "eligible"
        if all(c["passes"] for c in checks)
        else "criteria_not_met"
    )
    review = (
        context["reviews"].get(drive.id)
        if context
        else db.scalar(select(DriveReview).where(DriveReview.drive_id == drive.id, DriveReview.institution_id == user.institution_id))
    )
    if review and review.payload.get("unresolved_conditions"):
        status = "review_required"
    appeal = (
        context["appeals"].get((user.id, drive.id))
        if context
        else db.scalar(
            select(EligibilityAppeal)
            .where(EligibilityAppeal.user_id == user.id, EligibilityAppeal.drive_id == drive.id, EligibilityAppeal.status == "approved")
            .order_by(EligibilityAppeal.created_at.desc())
        )
    )
    if appeal:
        status = "eligible_by_review"
    return {
        "status": status,
        "checks": checks,
        "basis": "Explicit officer-approved academic conditions; student values are self-reported.",
        "review_note": appeal.payload.get("decision") if appeal else None,
        "ai_used": False,
    }


def gap_analysis(db, user, drive=None):
    evidence = evidence_profile(db, user)
    review = db.scalar(select(DriveReview).where(DriveReview.drive_id == drive.id)) if drive else None
    goal = db.scalar(select(CareerGoal).where(CareerGoal.user_id == user.id))
    requested = review.payload.get("approved_skills", []) if review and review.approved_at else []
    if not requested:
        names = drive.required_skills if drive else (goal.payload.get("skills", ["Python", "SQL"]) if goal else ["Python", "SQL"])
        requested = [{"skill": normalize(name) or name, "priority": "required"} for name in names]
    comparisons = []
    for requirement in requested:
        name = requirement["skill"]
        records = [e for e in evidence if e["skill"] == name and e.get("status") not in {"rejected", "challenged", "superseded"}]
        demonstrated = [e for e in records if e.get("evidence_type") in {"assessment_verified", "faculty_verified"}]
        claims = [e for e in records if e.get("evidence_type") in {"resume_claim", "student_claim"} and not e.get("ambiguous")]
        value = 1.0 if demonstrated else 0.35 if claims else 0.0
        state = (
            "demonstrated" if demonstrated else "needs_validation" if claims else "needs_clarification" if records else "missing_evidence"
        )
        comparisons.append(
            {
                "skill": name,
                "priority": requirement.get("priority", "required"),
                "state": state,
                "evidence": records,
                "coverage": value,
                "recommendation": "Maintain and practice"
                if demonstrated
                else "Validate with an approved assessment"
                if claims
                else "Clarify ambiguous or negated wording before treating it as skill evidence."
                if records
                else "Explore the topic and provide evidence; absence is not proof of lacking skill.",
            }
        )
    required = [c for c in comparisons if c["priority"] != "preferred"]
    score = round(100 * sum(c["coverage"] for c in required) / len(required)) if required else None
    role = drive.position if drive else (goal.payload.get("role") if goal else "General preparation")
    fingerprint = hashlib.sha256(
        json.dumps(
            {
                "role": role,
                "goal": goal.payload if goal else {},
                "deadline": drive.drive_date.isoformat() if drive else None,
                "evidence": [(c["skill"], c["priority"], c["state"], [e["id"] for e in c["evidence"]]) for c in comparisons],
            },
            sort_keys=True,
        ).encode()
    ).hexdigest()
    return {
        "drive_id": drive.id if drive else None,
        "role": role,
        "skills": comparisons,
        "alignment_score": score,
        "score_explanation": "Evidence coverage only: approved assessment or faculty-reviewed assignment evidence = 1.0; unambiguous unverified claim = 0.35; missing or ambiguous evidence = 0.0. Equal weighting of required skills. Not hiring eligibility or placement probability.",
        "method": "deterministic_evidence_coverage_v2",
        "fingerprint": fingerprint,
        "eligibility": objective_eligibility(db, user, drive) if drive else None,
        "strengths": [c["skill"] for c in comparisons if c["state"] == "demonstrated"],
        "validation_needed": [c["skill"] for c in comparisons if c["state"] in {"needs_validation", "needs_clarification"}],
        "gaps": [c["skill"] for c in comparisons if c["state"] == "missing_evidence"],
    }


def propose_roadmap(db, user, drive=None, trigger="student_request"):
    db.refresh(user, with_for_update=True)
    gap = gap_analysis(db, user, drive)
    plans = list(
        db.scalars(
            select(LearningRoadmap)
            .where(LearningRoadmap.user_id == user.id, LearningRoadmap.institution_id == user.institution_id)
            .order_by(LearningRoadmap.created_at.desc())
        )
    )
    previous = next((p for p in plans if p.payload.get("status") == "active"), None)
    # Same input/reason should not spam duplicate proposals.
    prior = next(
        (
            p
            for p in plans
            if p.payload.get("status") == "proposed"
            and p.payload.get("fingerprint") == gap["fingerprint"]
            and p.payload.get("trigger") == trigger
            and p.payload.get("drive_id") == (drive.id if drive else None)
        ),
        None,
    )
    if prior:
        return prior
    goal = db.scalar(select(CareerGoal).where(CareerGoal.user_id == user.id))
    hours = float(goal.payload.get("hours_per_week", 6)) if goal else 6
    days = max(1, (drive.drive_date - now()).days) if drive else 28
    budget = max(1, min(40, round(hours * min(days, 28) / 7)))
    urgent = days <= 7
    completed = []
    if previous:
        completed = [
            t
            for t in db.scalars(select(LearningTask).where(LearningTask.roadmap_id == previous.id))
            if t.payload.get("status") == "completed"
        ]
    version = max([p.payload.get("version", 1) for p in plans] + [0]) + 1
    explanation = f"Triggered by {trigger.replace('_', ' ')}. Prioritize {', '.join(gap['gaps'] + gap['validation_needed']) or 'revision of demonstrated skills'}. Preserve {len(completed)} completed tasks."
    if urgent:
        explanation += f" Only {days} days remain: this plan recommends revision and focused practice, not framework mastery."
    plan = LearningRoadmap(
        institution_id=user.institution_id,
        user_id=user.id,
        payload={
            "version": version,
            "status": "proposed",
            "previous_id": previous.id if previous else None,
            "drive_id": drive.id if drive else None,
            "role": gap["role"],
            "trigger": trigger,
            "explanation": explanation,
            "hours_budget": budget,
            "days_remaining": days,
            "fingerprint": gap["fingerprint"],
            "method": "deterministic_curriculum_v1",
            "created_at": now().isoformat(),
        },
    )
    db.add(plan)
    db.flush()
    for task in completed:
        db.add(LearningTask(institution_id=user.institution_id, roadmap_id=plan.id, payload={**task.payload, "preserved_from": task.id}))

    def depth(name, visited=None):
        visited = set(visited or ())
        if name in visited or name not in SKILLS:
            return 0
        return 1 + max([depth(p, visited | {name}) for p in SKILLS[name]["prerequisites"]] or [0])

    ordered = sorted(
        gap["skills"], key=lambda x: (x["priority"] == "preferred", x["state"] == "demonstrated", depth(x["skill"]), x["skill"])
    )
    remaining = budget
    scheduled = []
    completed_skills = {t.payload.get("skill") for t in completed}
    for index, item in enumerate(ordered):
        if remaining <= 0:
            break
        skill = item["skill"]
        info = SKILLS.get(skill)
        if not info:
            continue
        if skill in completed_skills and item["state"] == "demonstrated":
            continue
        validation_only = skill in completed_skills
        effort = min(1 if validation_only else 2 if urgent else 4, remaining)
        scheduled.append(skill)
        remaining -= effort
        title = (
            f"Validate {skill} with an approved assessment"
            if validation_only
            else f"{'Revise and practice' if urgent or item['state'] == 'demonstrated' else 'Learn and validate'} {skill}"
        )
        db.add(
            LearningTask(
                institution_id=user.institution_id,
                roadmap_id=plan.id,
                payload={
                    "title": title,
                    "skill": skill,
                    "status": "pending",
                    "priority": index + 1,
                    "objective": "Your completed lesson is preserved. Use an approved assessment to demonstrate learning."
                    if validation_only
                    else item["recommendation"],
                    "hours": effort,
                    "week": 1 + index // 3,
                    "difficulty": "focused revision" if urgent else "foundation",
                    "prerequisites": info["prerequisites"],
                    "resource": {"title": info["title"], "url": info["resource"]},
                    "practice": f"Write a short explanation and solve two {skill} exercises. Use an approved assessment to demonstrate learning.",
                    "assessment_topic": skill,
                },
            )
        )
    plan.payload = {**plan.payload, "estimated_hours": budget - remaining}
    deferred = [
        s["skill"] for s in ordered if s["skill"] not in scheduled and not (s["skill"] in completed_skills and s["state"] == "demonstrated")
    ]
    if deferred:
        plan.payload = {
            **plan.payload,
            "deferred_skills": deferred,
            "explanation": explanation
            + " Outside the available study budget: "
            + ", ".join(deferred)
            + ". Seek additional preparation time or focus on revision.",
        }
    db.add(
        Notification(
            institution_id=user.institution_id,
            user_id=user.id,
            title="A preparation update is ready",
            message=f"Roadmap v{version} is proposed for {gap['role']}. Review the changes before accepting.",
        )
    )
    track(db, user, "roadmap.proposed", "Preparation roadmap proposed", roadmap_id=plan.id, version=version)
    db.flush()
    return plan


def plan_view(db, plan):
    tasks = list(
        db.scalars(
            select(LearningTask)
            .where(LearningTask.roadmap_id == plan.id, LearningTask.institution_id == plan.institution_id)
            .order_by(LearningTask.created_at)
        )
    )
    return {
        "id": plan.id,
        **plan.payload,
        "tasks": [{"id": t.id, **t.payload} for t in tasks],
        "completed": sum(t.payload.get("status") == "completed" for t in tasks),
        "total": len(tasks),
    }


def adapt_after_event(db, user, trigger, drive=None):
    active = next(
        (p for p in db.scalars(select(LearningRoadmap).where(LearningRoadmap.user_id == user.id)) if p.payload.get("status") == "active"),
        None,
    )
    if active and drive is None and active.payload.get("drive_id"):
        drive = db.scalar(
            select(RecruitmentDrive).where(
                RecruitmentDrive.id == active.payload["drive_id"], RecruitmentDrive.institution_id == user.institution_id
            )
        )
    if active:
        return propose_roadmap(db, user, drive, trigger)

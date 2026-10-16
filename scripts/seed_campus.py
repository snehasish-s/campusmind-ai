"""Extend the fictional demo institution; never reset existing credentials."""

import hashlib
import secrets
import sys
from pathlib import Path
from datetime import timedelta
from sqlalchemy import select

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "services/api"))
from app.db import SessionLocal  # noqa: E402
from app import models as m  # noqa: E402
from app.security import password_hash  # noqa: E402
from app.campus_services import notify, DEFAULT_RUBRIC  # noqa: E402


def seed():
    with SessionLocal() as db:
        institution = db.scalar(select(m.Institution).where(m.Institution.slug == "demo"))
        if not institution or not any(w in institution.name.lower() for w in ("fictional", "synthetic", "demo")):
            raise SystemExit("Run scripts/seed.py first. Campus seeding requires an explicitly fictional institution with slug demo.")
        tenant = institution.id
        department = db.scalar(select(m.Department).where(m.Department.institution_id == tenant, m.Department.code == "CSE"))
        accounts = {}
        for roll, role in (("CAMPUSSTUDENT", "student"), ("TEACHER001", "faculty")):
            user = db.scalar(select(m.User).where(m.User.institution_id == tenant, m.User.roll_no == roll))
            if not user:
                password = secrets.token_urlsafe(20)
                user = m.User(
                    institution_id=tenant,
                    department_id=department.id,
                    roll_no=roll,
                    role=role,
                    full_name="Synthetic Campus Student" if role == "student" else "Synthetic Database Teacher",
                    email=roll.lower() + "@demo.example.invalid",
                    active=True,
                    password_hash=password_hash(password),
                )
                db.add(user)
                db.flush()
                if role == "student":
                    db.add(
                        m.StudentProfile(
                            institution_id=tenant, user_id=user.id, graduation_year=2027, academic_year=4, semester=7, section="A", cgpa=8.0
                        )
                    )
                else:
                    db.add(m.StaffRole(institution_id=tenant, user_id=user.id, role=role, department_id=department.id))
                print(f"{roll}: {password} (unique synthetic password; save privately)")
            accounts[roll] = user
        teacher, student = accounts["TEACHER001"], accounts["CAMPUSSTUDENT"]
        admin = db.scalar(select(m.User).where(m.User.institution_id == tenant, m.User.role == "institution_admin"))
        audience = {"department_id": department.id, "graduation_year": 2027, "academic_year": 4, "semester": 7, "section": "A"}
        fingerprint = hashlib.sha256(b"synthetic-campus-demo-v1").hexdigest()
        if not db.scalar(select(m.CampusImport).where(m.CampusImport.institution_id == tenant, m.CampusImport.fingerprint == fingerprint)):
            imported = m.CampusImport(
                institution_id=tenant,
                actor_id=admin.id,
                kind="timetable",
                fingerprint=fingerprint,
                rows=[],
                errors=[],
                confirmed_at=m.now(),
            )
            db.add(imported)
            db.flush()
            db.add(
                m.TeachingSlot(
                    institution_id=tenant,
                    import_id=imported.id,
                    teacher_id=teacher.id,
                    subject="Database Systems",
                    **audience,
                    weekday=m.now().weekday(),
                    starts="09:00",
                    ends="10:00",
                    room="Synthetic Lab A",
                    valid_from=m.now().date().isoformat(),
                    valid_until=(m.now() + timedelta(days=90)).date().isoformat(),
                )
            )
            post = m.CampusPost(
                institution_id=tenant,
                author_id=teacher.id,
                office="teacher",
                title="SQL joins · synthetic assignment",
                message="Write an INNER JOIN query and explain the result using fictional tables. Submit your text or a PDF/DOCX/TXT document.",
                kind="assignment",
                subject="Database Systems",
                audience=audience,
                due_at=m.now() + timedelta(hours=22),
            )
            db.add(post)
            db.flush()
            db.add(m.AssignmentPolicy(institution_id=tenant, post_id=post.id, rubric=DEFAULT_RUBRIC, skills=["SQL"], allow_late=True))
            notify(
                db,
                tenant,
                student.id,
                "seed:assignment",
                "SQL assignment is ready",
                "Open Campus Hub → Assignments to submit synthetic work.",
                "assignment",
            )
        if not db.scalar(select(m.FeePlan).where(m.FeePlan.institution_id == tenant, m.FeePlan.reference == "SYNTHETIC-TUITION-DEMO")):
            plan = m.FeePlan(
                institution_id=tenant,
                created_by=admin.id,
                reference="SYNTHETIC-TUITION-DEMO",
                title="Synthetic tuition instalment",
                category="tuition",
                term="Demo semester",
                audience={"student_id": student.id},
                amount_paise=125050,
                due_at=m.now() + timedelta(days=3),
            )
            db.add(plan)
            db.flush()
            db.add(m.FeeInvoice(institution_id=tenant, plan_id=plan.id, user_id=student.id, amount_paise=plan.amount_paise))
            notify(
                db,
                tenant,
                student.id,
                "seed:fee",
                "Synthetic fee invoice ready",
                "Review Fees. Default demonstration mode collects no money.",
                "fee",
            )
        db.commit()
        print("Synthetic campus demo is ready. Existing credentials and completed work were preserved.")


if __name__ == "__main__":
    seed()

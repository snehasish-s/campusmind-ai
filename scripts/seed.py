"""Idempotent synthetic institution bootstrap. Passwords are entered or randomly generated, never stored in source."""

import argparse
import getpass
import secrets
import sys
from pathlib import Path
from datetime import timedelta

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "services/api"))
from sqlalchemy import select  # noqa: E402
from app.db import SessionLocal  # noqa: E402
from app.models import Institution, Department, User, StaffRole, Company, RecruitmentDrive, ActivityEvent, now  # noqa: E402
from app.security import password_hash  # noqa: E402


def bootstrap(slug, name, password=None):
    with SessionLocal() as db:
        if db.scalar(select(Institution).where(Institution.slug == slug)):
            print(f"Institution '{slug}' already exists; credentials were not changed.")
            return
        institution = Institution(slug=slug, name=name)
        db.add(institution)
        db.flush()
        for code, title in [
            ("CSE", "Computer Science & Engineering"),
            ("ECE", "Electronics & Communication"),
            ("EE", "Electrical Engineering"),
            ("ME", "Mechanical Engineering"),
            ("CE", "Civil Engineering"),
        ]:
            db.add(Department(institution_id=institution.id, code=code, name=title))
        credentials = []
        for login, role, full_name in [
            ("ADMIN", "institution_admin", "Demo Institution Admin"),
            ("PLACEMENT", "placement_officer", "Demo Placement Officer"),
        ]:
            chosen = password if login == "ADMIN" and password else secrets.token_urlsafe(20)
            user = User(
                institution_id=institution.id,
                roll_no=login,
                email=f"{login.lower()}@{slug}.example.com",
                full_name=full_name,
                role=role,
                active=True,
                password_hash=password_hash(chosen),
            )
            db.add(user)
            db.flush()
            db.add(StaffRole(institution_id=institution.id, user_id=user.id, role=role))
            credentials.append((login, None if login == "ADMIN" and password else chosen))
        company = Company(institution_id=institution.id, name="Northstar Labs (Synthetic)", sector="Software engineering")
        db.add(company)
        db.flush()
        db.add(
            RecruitmentDrive(
                institution_id=institution.id,
                company_id=company.id,
                position="Graduate Software Engineer",
                description="A synthetic recruitment opportunity for demonstrating the placement workflow. Build reliable applications and collaborate with a small engineering team.",
                employment_type="Full-time",
                location="Bhubaneswar / Hybrid",
                ctc="₹4–6 LPA · illustrative",
                required_skills=["Python", "SQL", "Problem solving"],
                min_cgpa=6.5,
                max_backlogs=0,
                eligible_branches=["CSE", "ECE", "EE"],
                graduation_year=2027,
                deadline=now() + timedelta(days=21),
                drive_date=now() + timedelta(days=28),
                selection_rounds=["Aptitude", "Technical interview", "HR conversation"],
                status="published",
            )
        )
        db.add(ActivityEvent(institution_id=institution.id, title="Synthetic demonstration institution configured", kind="institution"))
        db.commit()
        print(f"Institution code: {slug}")
        for login, chosen in credentials:
            print(f"{login}: {chosen if chosen else 'Use the password you entered (not displayed).'}")
        print("Save these unique local demo passwords securely. They will not be displayed again.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--slug", default="demo")
    parser.add_argument("--name", default="Fictional Odisha Engineering Institute · Demo")
    parser.add_argument("--choose-admin-password", action="store_true")
    args = parser.parse_args()
    bootstrap(args.slug, args.name, getpass.getpass("Admin password (12+ characters): ") if args.choose_admin_password else None)

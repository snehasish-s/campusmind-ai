"""One-time, credential-gated first institution setup for hosts without a shell."""

import secrets
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, EmailStr
from sqlalchemy import select, text
from sqlalchemy.orm import Session
from ..config import settings
from ..db import get_db
from ..models import Institution, Department, User, StaffRole
from ..security import password_hash, rate_limit

router = APIRouter(tags=["Initial setup"])


class SetupInput(BaseModel):
    token: str = Field(min_length=32, max_length=200)
    institution_name: str = Field(min_length=3, max_length=200)
    slug: str = Field(pattern=r"^[a-z0-9-]{3,60}$")
    admin_name: str = Field(min_length=2, max_length=150)
    admin_email: EmailStr
    password: str = Field(min_length=12, max_length=128)


@router.post("/setup")
def setup(body: SetupInput, request: Request, db: Session = Depends(get_db)):
    rate_limit("setup:" + (request.client.host if request.client else "unknown"), 5, 3600)
    configured = settings().bootstrap_token
    if not configured or not secrets.compare_digest(configured, body.token):
        raise HTTPException(403, "Initial setup is unavailable or the setup token is invalid.")
    if db.bind.dialect.name == "postgresql":
        db.execute(text("SELECT pg_advisory_xact_lock(72419521)"))
    if db.scalar(select(Institution.id).limit(1)):
        raise HTTPException(409, "Initial setup has already been completed. Sign in with the existing institution account.")
    institution = Institution(slug=body.slug, name=body.institution_name)
    db.add(institution)
    db.flush()
    department = Department(institution_id=institution.id, code="CSE", name="Computer Science and Engineering")
    db.add(department)
    user = User(
        institution_id=institution.id,
        full_name=body.admin_name,
        email=str(body.admin_email).lower(),
        roll_no="ADMIN",
        role="institution_admin",
        active=True,
        password_hash=password_hash(body.password),
    )
    db.add(user)
    db.flush()
    db.add(StaffRole(institution_id=institution.id, user_id=user.id, role=user.role))
    db.commit()
    return {
        "institution": institution.slug,
        "identifier": "ADMIN",
        "message": "Setup completed. Sign in, then remove BOOTSTRAP_TOKEN from the hosting environment.",
    }

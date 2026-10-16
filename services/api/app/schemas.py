import re
from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field, EmailStr, ConfigDict, field_validator, model_validator


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Login(Strict):
    institution: str = Field(min_length=1, max_length=80)
    identifier: str = Field(min_length=1, max_length=254)
    password: str = Field(min_length=1, max_length=128)


class Activate(Strict):
    token: str = Field(min_length=20, max_length=200)
    password: str = Field(min_length=12, max_length=128)
    consent: bool = False


class ResetRequest(Strict):
    institution: str = Field(max_length=80)
    identifier: str = Field(max_length=254)


class StudentRow(Strict):
    roll_no: str = Field(min_length=2, max_length=80)
    full_name: str = Field(min_length=2, max_length=150)
    email: EmailStr
    department: str = Field(min_length=1, max_length=40)
    graduation_year: int = Field(ge=2020, le=2100)
    cgpa: float = Field(ge=0, le=10, allow_inf_nan=False)
    active_backlogs: int = Field(ge=0, le=50)
    phone: str = Field(default="", max_length=30)

    section: str = Field(default="", max_length=30)
    academic_year: int | None = Field(default=None, ge=1, le=6)
    semester: int | None = Field(default=None, ge=1, le=12)

    @field_validator("roll_no", "department", "section")
    @classmethod
    def normalize_code(cls, value):
        value = value.strip().upper()
        if value and not re.fullmatch(r"[A-Z0-9_\- /]+", value):
            raise ValueError("Only letters, digits, spaces, /, - and _ are allowed")
        return value

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value):
        return value.lower()


class Experience(Strict):
    title: str = Field(min_length=1, max_length=160)
    description: str = Field(default="", max_length=2000)


class ProfileUpdate(Strict):
    full_name: str = Field(min_length=2, max_length=150)
    graduation_year: int = Field(ge=2020, le=2100)
    cgpa: float = Field(ge=0, le=10, allow_inf_nan=False)
    active_backlogs: int = Field(ge=0, le=50)
    phone: str = Field(max_length=30)
    bio: str = Field(default="", max_length=2000)
    projects: list[Experience] = Field(default_factory=list, max_length=30)
    internships: list[Experience] = Field(default_factory=list, max_length=30)


class DepartmentInput(Strict):
    code: str = Field(min_length=1, max_length=40, pattern=r"^[A-Za-z0-9_-]+$")
    name: str = Field(min_length=2, max_length=150)


class StaffInput(Strict):
    full_name: str = Field(min_length=2, max_length=150)
    email: EmailStr
    roll_no: str = Field(min_length=2, max_length=80)
    role: Literal["institution_admin", "placement_officer", "hod", "faculty", "campus_staff"]
    department_id: str | None = None


class InstitutionUpdate(Strict):
    name: str = Field(min_length=2, max_length=200)
    city: str = Field(min_length=2, max_length=100)
    privacy_notice: str = Field(min_length=20, max_length=5000)


class StaffAccess(Strict):
    role: Literal["institution_admin", "placement_officer", "hod", "faculty", "campus_staff"]
    department_id: str | None = None


class CompanyInput(Strict):
    name: str = Field(min_length=2, max_length=150)
    website: str = Field(default="", max_length=300, pattern=r"^(https?://[^\s]+)?$")
    sector: str = Field(default="Technology", max_length=100)


class DriveInput(Strict):
    company_name: str = Field(min_length=2, max_length=150)
    position: str = Field(min_length=2, max_length=160)
    description: str = Field(min_length=20, max_length=20000)
    employment_type: Literal["Full-time", "Internship", "Internship + PPO"]
    location: str = Field(min_length=2, max_length=200)
    ctc: str = Field(min_length=1, max_length=150)
    required_skills: list[str] = Field(default_factory=list, max_length=50)
    min_cgpa: float = Field(ge=0, le=10, allow_inf_nan=False)
    max_backlogs: int = Field(ge=0, le=50)
    eligible_branches: list[str] = Field(default_factory=list, max_length=50)
    graduation_year: int = Field(ge=2020, le=2100)
    deadline: datetime
    drive_date: datetime
    selection_rounds: list[str] = Field(default_factory=list, max_length=20)
    additional_requirements: str = Field(default="", max_length=5000)
    status: Literal["draft", "published", "closed"] = "draft"

    @field_validator("deadline", "drive_date")
    @classmethod
    def utc_naive(cls, value):
        from datetime import timezone

        if value.tzinfo:
            value = value.astimezone(timezone.utc).replace(tzinfo=None)
        return value

    @model_validator(mode="after")
    def dates(self):
        if self.deadline > self.drive_date:
            raise ValueError("Registration deadline must precede the drive date")
        return self

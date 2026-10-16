import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Text, ForeignKey, UniqueConstraint, Index, JSON, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column
from .db import Base


def now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Identity:
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    created_at: Mapped[datetime] = mapped_column(default=now)


class Tenant(Identity):
    institution_id: Mapped[str] = mapped_column(ForeignKey("institutions.id"), index=True)


class Institution(Identity, Base):
    __tablename__ = "institutions"
    slug: Mapped[str] = mapped_column(String(80), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    city: Mapped[str] = mapped_column(default="Bhubaneswar")
    privacy_notice: Mapped[str] = mapped_column(
        Text,
        default="Your institution uses your profile and resume for placement coordination. Contact your institution administrator for access, correction or deletion requests.",
    )


class Department(Tenant, Base):
    __tablename__ = "departments"
    __table_args__ = (UniqueConstraint("institution_id", "code"),)
    code: Mapped[str] = mapped_column(String(40))
    name: Mapped[str] = mapped_column(String(150))


class User(Tenant, Base):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("institution_id", "roll_no"),
        UniqueConstraint("institution_id", "email"),
        CheckConstraint("role IN ('platform_admin','institution_admin','placement_officer','hod','faculty','campus_staff','student')"),
    )
    email: Mapped[str] = mapped_column(String(254))
    roll_no: Mapped[str] = mapped_column(String(80))
    full_name: Mapped[str] = mapped_column(String(150))
    role: Mapped[str] = mapped_column(String(30), default="student")
    password_hash: Mapped[str | None] = mapped_column(String(255))
    active: Mapped[bool] = mapped_column(default=False)
    department_id: Mapped[str | None] = mapped_column(ForeignKey("departments.id"))
    consent_at: Mapped[datetime | None]


class StaffRole(Tenant, Base):
    __tablename__ = "staff_roles"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), unique=True)
    role: Mapped[str] = mapped_column(String(30))
    department_id: Mapped[str | None] = mapped_column(ForeignKey("departments.id"))


class StudentProfile(Tenant, Base):
    __tablename__ = "student_profiles"
    __table_args__ = (CheckConstraint("cgpa >= 0 AND cgpa <= 10"), CheckConstraint("active_backlogs >= 0"))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), unique=True)
    graduation_year: Mapped[int]
    cgpa: Mapped[float] = mapped_column(default=0)
    active_backlogs: Mapped[int] = mapped_column(default=0)
    phone: Mapped[str] = mapped_column(String(30), default="")
    section: Mapped[str] = mapped_column(String(30), default="", server_default="")
    academic_year: Mapped[int | None]
    semester: Mapped[int | None]
    bio: Mapped[str] = mapped_column(Text, default="")
    projects: Mapped[list] = mapped_column(JSON, default=list)
    internships: Mapped[list] = mapped_column(JSON, default=list)


class AuthSession(Tenant, Base):
    __tablename__ = "auth_sessions"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    csrf_hash: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime]


class Invitation(Tenant, Base):
    __tablename__ = "invitations"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    purpose: Mapped[str] = mapped_column(default="activation")
    expires_at: Mapped[datetime]
    used_at: Mapped[datetime | None]
    revoked_at: Mapped[datetime | None]
    delivery_status: Mapped[str] = mapped_column(default="pending")


class ImportJob(Tenant, Base):
    __tablename__ = "import_jobs"
    __table_args__ = (UniqueConstraint("institution_id", "fingerprint"),)
    actor_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    filename: Mapped[str]
    fingerprint: Mapped[str] = mapped_column(String(64))
    policy: Mapped[str] = mapped_column(default="skip")
    status: Mapped[str] = mapped_column(default="preview")
    rows: Mapped[list] = mapped_column(JSON, default=list)
    total: Mapped[int] = mapped_column(default=0)
    processed: Mapped[int] = mapped_column(default=0)
    created: Mapped[int] = mapped_column(default=0)
    updated: Mapped[int] = mapped_column(default=0)
    skipped: Mapped[int] = mapped_column(default=0)
    errors: Mapped[int] = mapped_column(default=0)
    failure: Mapped[str | None] = mapped_column(Text)
    lease_expires_at: Mapped[datetime | None]
    lease_token: Mapped[str | None] = mapped_column(String(64))


class ImportError(Tenant, Base):
    __tablename__ = "import_errors"
    job_id: Mapped[str] = mapped_column(ForeignKey("import_jobs.id"), index=True)
    row_number: Mapped[int]
    message: Mapped[str] = mapped_column(Text)


class Resume(Tenant, Base):
    __tablename__ = "resumes"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    filename: Mapped[str]
    storage_key: Mapped[str]
    text_key: Mapped[str]
    mime_type: Mapped[str]
    size_bytes: Mapped[int]
    version: Mapped[int]
    extraction_status: Mapped[str] = mapped_column(default="complete")
    __table_args__ = (UniqueConstraint("user_id", "version"),)


class Company(Tenant, Base):
    __tablename__ = "companies"
    __table_args__ = (UniqueConstraint("institution_id", "name"),)
    name: Mapped[str] = mapped_column(String(150))
    website: Mapped[str] = mapped_column(default="")
    sector: Mapped[str] = mapped_column(default="Technology")


class RecruitmentDrive(Tenant, Base):
    __tablename__ = "recruitment_drives"
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"))
    position: Mapped[str] = mapped_column(String(160))
    description: Mapped[str] = mapped_column(Text)
    employment_type: Mapped[str]
    location: Mapped[str]
    ctc: Mapped[str]
    required_skills: Mapped[list] = mapped_column(JSON, default=list)
    min_cgpa: Mapped[float] = mapped_column(default=0)
    max_backlogs: Mapped[int] = mapped_column(default=0)
    eligible_branches: Mapped[list] = mapped_column(JSON, default=list)
    graduation_year: Mapped[int]
    deadline: Mapped[datetime]
    drive_date: Mapped[datetime]
    selection_rounds: Mapped[list] = mapped_column(JSON, default=list)
    additional_requirements: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(default="draft")
    __table_args__ = (
        CheckConstraint("status IN ('draft','reviewed','published','open','closed','completed')", name="ck_drive_lifecycle"),
        Index("ix_drives_tenant_status", "institution_id", "status"),
    )


class DriveApplication(Tenant, Base):
    __tablename__ = "drive_applications"
    drive_id: Mapped[str] = mapped_column(ForeignKey("recruitment_drives.id"))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    status: Mapped[str] = mapped_column(default="registered")
    __table_args__ = (UniqueConstraint("drive_id", "user_id"),)


class Notification(Tenant, Base):
    __tablename__ = "notifications"
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str]
    message: Mapped[str] = mapped_column(Text)
    read_at: Mapped[datetime | None]


class ActivityEvent(Tenant, Base):
    __tablename__ = "activity_events"
    title: Mapped[str]
    kind: Mapped[str]
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), index=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict, server_default="{}")


class AuditLog(Tenant, Base):
    __tablename__ = "audit_logs"
    actor_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    action: Mapped[str]
    target_id: Mapped[str | None]
    details: Mapped[dict] = mapped_column(JSON, default=dict)


class InstitutionalDocument(Tenant, Base):
    __tablename__ = "institutional_documents"
    title: Mapped[str]
    category: Mapped[str]
    storage_key: Mapped[str]
    filename: Mapped[str]
    size_bytes: Mapped[int]
    mime_type: Mapped[str]
    uploaded_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    status: Mapped[str] = mapped_column(default="submitted")
    content_hash: Mapped[str | None] = mapped_column(String(64), index=True)
    version: Mapped[int] = mapped_column(default=1, server_default="1")
    parent_id: Mapped[str | None] = mapped_column(ForeignKey("institutional_documents.id"))
    department_id: Mapped[str | None] = mapped_column(ForeignKey("departments.id"))
    owner_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    expires_at: Mapped[datetime | None]
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict, server_default="{}")


# Versioned, tenant-owned integration records. Phase 2 adds domain validation and APIs.
class Extension(Tenant):
    schema_version: Mapped[int] = mapped_column(default=1)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)


class Skill(Extension, Base):
    __tablename__ = "skills"
    __table_args__ = (UniqueConstraint("institution_id", "name", name="uq_skills_tenant_name"),)
    name: Mapped[str]


class SkillEvidence(Extension, Base):
    __tablename__ = "skill_evidence"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    skill_id: Mapped[str] = mapped_column(ForeignKey("skills.id"))


class ResumeAnalysis(Extension, Base):
    __tablename__ = "resume_analysis"
    resume_id: Mapped[str] = mapped_column(ForeignKey("resumes.id"))


class StudentAssessment(Extension, Base):
    __tablename__ = "student_assessments"
    title: Mapped[str]


class TestQuestion(Extension, Base):
    __tablename__ = "test_questions"
    assessment_id: Mapped[str | None] = mapped_column(ForeignKey("student_assessments.id"))


class TestAttempt(Extension, Base):
    __tablename__ = "test_attempts"
    assessment_id: Mapped[str] = mapped_column(ForeignKey("student_assessments.id"))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))


class LearningRoadmap(Extension, Base):
    __tablename__ = "learning_roadmaps"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))


class LearningTask(Extension, Base):
    __tablename__ = "learning_tasks"
    roadmap_id: Mapped[str] = mapped_column(ForeignKey("learning_roadmaps.id"))


class AIWorkflowRun(Extension, Base):
    __tablename__ = "ai_workflow_runs"
    status: Mapped[str] = mapped_column(default="pending")
    provider: Mapped[str] = mapped_column(default="ollama")


class EvidenceRequirement(Extension, Base):
    __tablename__ = "evidence_requirements"
    title: Mapped[str]


class EvidenceFinding(Extension, Base):
    __tablename__ = "evidence_findings"
    document_id: Mapped[str] = mapped_column(ForeignKey("institutional_documents.id"))
    requirement_id: Mapped[str] = mapped_column(ForeignKey("evidence_requirements.id"))


class DriveReview(Extension, Base):
    __tablename__ = "drive_reviews"
    drive_id: Mapped[str] = mapped_column(ForeignKey("recruitment_drives.id"), unique=True)
    approved_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    approved_at: Mapped[datetime | None]


class EligibilityAppeal(Extension, Base):
    __tablename__ = "eligibility_appeals"
    drive_id: Mapped[str] = mapped_column(ForeignKey("recruitment_drives.id"))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    status: Mapped[str] = mapped_column(default="pending")


class CareerGoal(Extension, Base):
    __tablename__ = "career_goals"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), unique=True)


class DocumentChunk(Tenant, Base):
    __tablename__ = "document_chunks"
    document_id: Mapped[str] = mapped_column(ForeignKey("institutional_documents.id"), index=True)
    chunk_index: Mapped[int]
    page: Mapped[int | None]
    content: Mapped[str] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String(64))
    vector_status: Mapped[str] = mapped_column(default="keyword")
    __table_args__ = (UniqueConstraint("document_id", "chunk_index"),)


class Conversation(Extension, Base):
    __tablename__ = "conversations"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str]


class DataRequest(Extension, Base):
    __tablename__ = "data_requests"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    kind: Mapped[str]
    status: Mapped[str] = mapped_column(default="pending")


class RateLimitBucket(Base):
    __tablename__ = "rate_limit_buckets"
    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    count: Mapped[int] = mapped_column(default=0)
    expires_at: Mapped[datetime]


class InstitutionalTask(Extension, Base):
    __tablename__ = "institutional_tasks"
    title: Mapped[str]
    assigned_to: Mapped[str] = mapped_column(ForeignKey("users.id"))
    department_id: Mapped[str | None] = mapped_column(ForeignKey("departments.id"))
    status: Mapped[str] = mapped_column(default="pending")


class CampusAuthority(Tenant, Base):
    __tablename__ = "campus_authorities"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), unique=True)
    office: Mapped[str] = mapped_column(String(40))
    department_id: Mapped[str | None] = mapped_column(ForeignKey("departments.id"))


class CampusImport(Tenant, Base):
    __tablename__ = "campus_imports"
    __table_args__ = (UniqueConstraint("institution_id", "fingerprint"),)
    actor_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    kind: Mapped[str] = mapped_column(String(20))
    fingerprint: Mapped[str] = mapped_column(String(64))
    rows: Mapped[list] = mapped_column(JSON)
    errors: Mapped[list] = mapped_column(JSON)
    confirmed_at: Mapped[datetime | None]


class TeachingSlot(Tenant, Base):
    __tablename__ = "teaching_slots"
    import_id: Mapped[str] = mapped_column(ForeignKey("campus_imports.id"))
    department_id: Mapped[str] = mapped_column(ForeignKey("departments.id"), index=True)
    graduation_year: Mapped[int]
    academic_year: Mapped[int]
    semester: Mapped[int]
    section: Mapped[str] = mapped_column(String(30))
    subject: Mapped[str] = mapped_column(String(100))
    teacher_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    weekday: Mapped[int]
    starts: Mapped[str] = mapped_column(String(5))
    ends: Mapped[str] = mapped_column(String(5))
    room: Mapped[str] = mapped_column(String(80), default="")
    valid_from: Mapped[str] = mapped_column(String(10))
    valid_until: Mapped[str] = mapped_column(String(10))
    active: Mapped[bool] = mapped_column(default=True)


class CampusPost(Tenant, Base):
    __tablename__ = "campus_posts"
    author_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    office: Mapped[str] = mapped_column(String(40))
    title: Mapped[str] = mapped_column(String(200))
    message: Mapped[str] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(String(20))
    audience: Mapped[dict] = mapped_column(JSON)
    subject: Mapped[str] = mapped_column(String(100), default="")
    due_at: Mapped[datetime | None]
    storage_key: Mapped[str | None]
    filename: Mapped[str | None]
    mime: Mapped[str | None]
    withdrawn: Mapped[bool] = mapped_column(default=False)


class CampusReceipt(Tenant, Base):
    __tablename__ = "campus_receipts"
    __table_args__ = (UniqueConstraint("post_id", "user_id"),)
    post_id: Mapped[str] = mapped_column(ForeignKey("campus_posts.id"))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    read_at: Mapped[datetime | None]

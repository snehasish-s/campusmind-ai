"""Deterministic campus distribution: no LLM sees rosters or controls recipients."""

import csv
import hashlib
import io
import json
import re
import zipfile
from datetime import date, datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..db import get_db
from ..models import (
    User,
    Department,
    StudentProfile,
    CampusAuthority,
    CampusImport,
    TeachingSlot,
    CampusPost,
    CampusReceipt,
    Notification,
    now,
)
from ..security import current_user, require, ADMINS, scoped, audit
from ..storage import get_storage, validate_document, document_response, MAX_FILE_SIZE

router = APIRouter(prefix="/campus", tags=["Campus communication and timetable routing"])
OFFICES = {"principal", "dean", "director", "department", "placement", "teacher"}


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Audience(Strict):
    department_id: str | None = None
    graduation_year: int | None = Field(default=None, ge=2020, le=2100)
    academic_year: int | None = Field(default=None, ge=1, le=6)
    semester: int | None = Field(default=None, ge=1, le=12)
    section: str = Field(default="", max_length=30)
    student_id: str | None = None
    student_roll_no: str = Field(default="", max_length=80)


class PostInput(Strict):
    title: str = Field(min_length=3, max_length=200)
    message: str = Field(min_length=1, max_length=15000)
    kind: str = "announcement"
    subject: str = Field(default="", max_length=100)
    audience: Audience = Field(default_factory=Audience)
    due_at: datetime | None = None


class AuthorityInput(Strict):
    user_id: str
    office: str
    department_id: str | None = None


class SlotInput(Strict):
    department: str = Field(min_length=1, max_length=40)
    graduation_year: int = Field(ge=2020, le=2100)
    academic_year: int = Field(ge=1, le=6)
    semester: int = Field(ge=1, le=12)
    section: str = Field(min_length=1, max_length=30)
    subject: str = Field(min_length=1, max_length=100)
    teacher_roll_no: str = Field(min_length=2, max_length=80)
    weekday: int = Field(ge=0, le=6)
    starts: str
    ends: str
    room: str = Field(default="", max_length=80)
    valid_from: date
    valid_until: date


class CohortInput(Strict):
    roll_no: str
    department: str
    graduation_year: int = Field(ge=2020, le=2100)
    academic_year: int = Field(ge=1, le=6)
    semester: int = Field(ge=1, le=12)
    section: str = Field(min_length=1, max_length=30)


def authority(db, user):
    if user.role in ADMINS:
        return "administration", None
    grant = db.scalar(
        select(CampusAuthority).where(CampusAuthority.institution_id == user.institution_id, CampusAuthority.user_id == user.id)
    )
    if grant:
        return grant.office, grant.department_id
    if user.role == "faculty" and user.department_id:
        return "teacher", user.department_id
    if user.role == "hod" and user.department_id:
        return "department", user.department_id
    if user.role == "placement_officer":
        return "placement", None
    raise HTTPException(403, "An administrator must grant campus publishing authority first.")


def matches(student, profile, audience):
    if audience.get("student_roll_no") and audience["student_roll_no"].upper() != student.roll_no.upper():
        return False
    if audience.get("student_id") and audience["student_id"] != student.id:
        return False
    if audience.get("department_id") and audience["department_id"] != student.department_id:
        return False
    for key in ("graduation_year", "academic_year", "semester", "section"):
        value = audience.get(key)
        if value not in (None, "") and (not profile or str(getattr(profile, key)).upper() != str(value).upper()):
            return False
    return True


def cohort(slot):
    return {key: getattr(slot, key) for key in ("department_id", "graduation_year", "academic_year", "semester", "section")}


def valid_slots(db, user):
    today = date.today().isoformat()
    return list(
        db.scalars(
            select(TeachingSlot).where(
                TeachingSlot.institution_id == user.institution_id,
                TeachingSlot.active.is_(True),
                TeachingSlot.valid_from <= today,
                TeachingSlot.valid_until >= today,
            )
        )
    )


def allowed_audience(db, user, target, subject, assignment=False):
    office, department_id = authority(db, user)
    target.section = target.section.upper()
    if target.department_id:
        scoped(db, Department, user, target.department_id)
    if department_id and target.department_id != department_id:
        raise HTTPException(403, "Select your assigned department; institution-wide publishing is not permitted.")
    if target.student_roll_no:
        student = db.scalar(
            select(User).where(
                User.institution_id == user.institution_id, User.roll_no == target.student_roll_no.upper(), User.role == "student"
            )
        )
        if not student or (department_id and student.department_id != department_id):
            raise HTTPException(404, "Student not found in your publishing scope.")
    if target.student_id:
        student = scoped(db, User, user, target.student_id)
        if student.role != "student" or (department_id and student.department_id != department_id):
            raise HTTPException(403, "This student is outside your publishing scope.")
    if office == "teacher" or assignment:
        if not subject or not all((target.department_id, target.graduation_year, target.academic_year, target.semester, target.section)):
            raise HTTPException(422, "Subject updates need the exact branch, graduation year, academic year, semester and section.")
        found = any(
            s.teacher_id == user.id
            and s.subject.casefold() == subject.casefold()
            and cohort(s) == target.model_dump(exclude={"student_id", "student_roll_no"})
            for s in valid_slots(db, user)
        )
        if user.role not in ADMINS and not found:
            raise HTTPException(403, "The current timetable does not assign you this subject and cohort.")
    return office


def recipients(db, user, audience):
    query = (
        select(User, StudentProfile)
        .join(StudentProfile, StudentProfile.user_id == User.id)
        .where(User.institution_id == user.institution_id, User.role == "student")
    )
    return [s for s, p in db.execute(query) if matches(s, p, audience)]


def post_access(db, user, post):
    if user.role == "student":
        p = db.scalar(select(StudentProfile).where(StudentProfile.user_id == user.id, StudentProfile.institution_id == user.institution_id))
        return not post.withdrawn and matches(user, p, post.audience)
    if user.role in ADMINS or post.author_id == user.id:
        return True
    try:
        office, department = authority(db, user)
    except HTTPException:
        return False
    return office != "teacher" and (not department or post.audience.get("department_id") == department)


def visible_post(db, user, post_id):
    post = scoped(db, CampusPost, user, post_id)
    if not post_access(db, user, post):
        raise HTTPException(404, "Update not found.")
    return post


@router.get("/context")
def context(user=Depends(current_user), db: Session = Depends(get_db)):
    own = db.scalar(select(StudentProfile).where(StudentProfile.user_id == user.id)) if user.role == "student" else None
    try:
        office, department = authority(db, user)
    except HTTPException:
        office, department = None, None
    return {
        "office": office,
        "department_id": department,
        "cohort": {k: getattr(own, k) for k in ("section", "academic_year", "semester", "graduation_year")} if own else None,
    }


@router.get("/authorities")
def authorities(user=Depends(current_user), db: Session = Depends(get_db)):
    require(user, ADMINS)
    return [
        {"id": g.id, "user_id": g.user_id, "office": g.office, "department_id": g.department_id}
        for g in db.scalars(select(CampusAuthority).where(CampusAuthority.institution_id == user.institution_id))
    ]


@router.put("/authorities")
def grant(body: AuthorityInput, user=Depends(current_user), db: Session = Depends(get_db)):
    require(user, ADMINS)
    target = scoped(db, User, user, body.user_id)
    if target.role == "student" or body.office not in OFFICES:
        raise HTTPException(422, "Choose a staff account and a supported publishing office.")
    if body.office in {"department", "teacher"} and not body.department_id:
        raise HTTPException(422, "Department and teacher authorities require a department.")
    if body.department_id:
        scoped(db, Department, user, body.department_id)
    entry = db.scalar(select(CampusAuthority).where(CampusAuthority.user_id == target.id))
    if not entry:
        entry = CampusAuthority(institution_id=user.institution_id, user_id=target.id)
        db.add(entry)
    entry.office, entry.department_id = body.office, body.department_id
    audit(db, user, "campus.authority.grant", target.id, {"office": body.office, "department_id": body.department_id})
    db.commit()
    return {"id": entry.id}


@router.delete("/authorities/{grant_id}")
def revoke(grant_id: str, user=Depends(current_user), db: Session = Depends(get_db)):
    require(user, ADMINS)
    entry = scoped(db, CampusAuthority, user, grant_id)
    audit(db, user, "campus.authority.revoke", entry.user_id)
    db.delete(entry)
    db.commit()
    return {"ok": True}


@router.get("/posts")
def posts(user=Depends(current_user), db: Session = Depends(get_db)):
    rows = db.scalars(
        select(CampusPost).where(CampusPost.institution_id == user.institution_id).order_by(CampusPost.created_at.desc())
    ).all()
    receipts = {
        r.post_id: r
        for r in db.scalars(
            select(CampusReceipt).where(CampusReceipt.institution_id == user.institution_id, CampusReceipt.user_id == user.id)
        )
    }
    result = []
    for p in rows:
        if not post_access(db, user, p):
            continue
        author = db.get(User, p.author_id)
        result.append(
            {
                "id": p.id,
                "title": p.title,
                "message": p.message,
                "office": p.office,
                "kind": p.kind,
                "subject": p.subject,
                "audience": p.audience,
                "due_at": p.due_at,
                "filename": p.filename,
                "author": author.full_name,
                "created_at": p.created_at,
                "withdrawn": p.withdrawn,
                "read_at": receipts[p.id].read_at if p.id in receipts else None,
                "can_manage": user.role in ADMINS or p.author_id == user.id,
            }
        )
        if len(result) >= 200:
            break
    return result


@router.post("/posts/preview")
def preview_post(body: PostInput, user=Depends(current_user), db: Session = Depends(get_db)):
    allowed_audience(db, user, body.audience, body.subject, body.kind == "assignment")
    return {"recipients": len(recipients(db, user, body.audience.model_dump()))}


@router.post("/posts")
async def publish(
    payload: str = Form(...), file: UploadFile | None = File(None), user=Depends(current_user), db: Session = Depends(get_db)
):
    try:
        body = PostInput.model_validate_json(payload)
    except ValidationError:
        raise HTTPException(422, "Invalid update. Check title, message and audience fields.")
    if body.kind not in {"announcement", "assignment", "resource"}:
        raise HTTPException(422, "Choose announcement, assignment or resource.")
    body.audience.section = body.audience.section.upper()
    office = allowed_audience(db, user, body.audience, body.subject, body.kind == "assignment")
    due = (body.due_at.astimezone(timezone.utc).replace(tzinfo=None) if body.due_at.tzinfo else body.due_at) if body.due_at else None
    if due and due <= now():
        raise HTTPException(422, "The deadline must be in the future.")
    audience = body.audience.model_dump()
    targets = recipients(db, user, audience)
    key, filename, mime = None, None, None
    if file:
        content = await file.read(MAX_FILE_SIZE + 1)
        suffix, mime, _ = validate_document(file.filename or "", content, allow_text=True)
        key = get_storage().put(user.institution_id, content, suffix)
        filename = Path(file.filename).name
    post = CampusPost(
        institution_id=user.institution_id,
        author_id=user.id,
        office=office,
        title=body.title,
        message=body.message,
        kind=body.kind,
        subject=body.subject,
        audience=audience,
        due_at=due,
        storage_key=key,
        filename=filename,
        mime=mime,
    )
    try:
        db.add(post)
        db.flush()
        for student in targets:
            db.add(CampusReceipt(institution_id=user.institution_id, post_id=post.id, user_id=student.id))
            db.add(
                Notification(
                    institution_id=user.institution_id,
                    user_id=student.id,
                    title=body.title,
                    message=f"New {body.kind} from {office}. Open Campus Hub to read the update.",
                )
            )
        audit(db, user, "campus.post.publish", post.id, {"recipients": len(targets), "audience": audience})
        db.commit()
    except Exception:
        db.rollback()
        if key:
            get_storage().delete(key)
        raise
    return {"id": post.id, "recipients": len(targets)}


@router.get("/posts/{post_id}/attachment")
def attachment(post_id: str, user=Depends(current_user), db: Session = Depends(get_db)):
    post = visible_post(db, user, post_id)
    if not post.storage_key or post.withdrawn:
        raise HTTPException(404, "Attachment not found.")
    return document_response(post.storage_key, post.filename, post.mime)


@router.post("/posts/{post_id}/acknowledge")
def acknowledge(post_id: str, user=Depends(current_user), db: Session = Depends(get_db)):
    require(user, {"student"})
    post = visible_post(db, user, post_id)
    receipt = db.scalar(select(CampusReceipt).where(CampusReceipt.post_id == post.id, CampusReceipt.user_id == user.id))
    if not receipt:
        receipt = CampusReceipt(institution_id=user.institution_id, post_id=post.id, user_id=user.id)
        db.add(receipt)
    receipt.read_at = receipt.read_at or now()
    db.commit()
    return {"ok": True}


@router.get("/posts/{post_id}/delivery")
def delivery(post_id: str, user=Depends(current_user), db: Session = Depends(get_db)):
    post = visible_post(db, user, post_id)
    if user.role not in ADMINS and post.author_id != user.id:
        raise HTTPException(403, "Only the publisher or administrator can view acknowledgements.")
    entries = list(db.scalars(select(CampusReceipt).where(CampusReceipt.post_id == post.id)))
    return {"delivered": len(entries), "acknowledged": sum(r.read_at is not None for r in entries)}


@router.delete("/posts/{post_id}")
def withdraw(post_id: str, user=Depends(current_user), db: Session = Depends(get_db)):
    post = scoped(db, CampusPost, user, post_id)
    if user.role not in ADMINS and post.author_id != user.id:
        raise HTTPException(403, "Only the publisher or administrator can withdraw this update.")
    post.withdrawn = True
    audit(db, user, "campus.post.withdraw", post.id)
    db.commit()
    return {"ok": True}


def sheet_rows(filename, content):
    if not content or len(content) > MAX_FILE_SIZE:
        raise ValueError("Upload a non-empty CSV or XLSX no larger than 8 MB.")
    if filename.lower().endswith(".csv"):
        reader = csv.DictReader(io.StringIO(content.decode("utf-8-sig")))
        headers = reader.fieldnames or []
        if len(headers) != len(set(headers)):
            raise ValueError("Duplicate headers are not allowed.")
        rows = []
        for row in reader:
            rows.append({k: str(v or "").strip() for k, v in row.items() if k is not None})
            if len(rows) > 20000:
                raise ValueError("Maximum 20,000 rows.")
        return rows
    if not filename.lower().endswith(".xlsx"):
        raise ValueError("Use CSV or XLSX; legacy XLS and macro-enabled files are not supported.")
    with zipfile.ZipFile(io.BytesIO(content)) as z:
        if sum(i.file_size for i in z.infolist()) > 32 * 1024 * 1024 or len(z.infolist()) > 500:
            raise ValueError("Workbook exceeds extraction limits.")
        ns = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}

        def xml(name):
            raw = z.read(name)
            if b"<!DOCTYPE" in raw.upper() or b"<!ENTITY" in raw.upper():
                raise ValueError("XML entities are not supported.")
            return ET.fromstring(raw)

        strings = []
        if "xl/sharedStrings.xml" in z.namelist():
            strings = ["".join(t.text or "" for t in si.findall(".//m:t", ns)) for si in xml("xl/sharedStrings.xml").findall("m:si", ns)]
        names = sorted(n for n in z.namelist() if re.fullmatch(r"xl/worksheets/sheet\d+\.xml", n))
        if len(names) != 1:
            raise ValueError("Upload a workbook with exactly one worksheet.")
        matrix = []
        for row in xml(names[0]).findall(".//m:sheetData/m:row", ns):
            values = {}
            for cell in row.findall("m:c", ns):
                if cell.find("m:f", ns) is not None:
                    raise ValueError("Replace formulas with values before importing.")
                ref = cell.get("r", "")
                letters = re.match("[A-Z]+", ref)
                if not letters:
                    raise ValueError("Invalid worksheet cell.")
                index = 0
                for ch in letters[0]:
                    index = index * 26 + ord(ch) - 64
                if index > 100:
                    raise ValueError("Maximum 100 columns.")
                value = cell.findtext("m:v", "", ns)
                if cell.get("t") == "s":
                    value = strings[int(value)]
                elif cell.get("t") == "inlineStr":
                    value = "".join(t.text or "" for t in cell.findall(".//m:t", ns))
                values[index - 1] = value.strip()
            if values:
                matrix.append([values.get(i, "") for i in range(max(values) + 1)])
            if len(matrix) > 20001:
                raise ValueError("Maximum 20,000 rows.")
        if not matrix or len(matrix[0]) != len(set(matrix[0])):
            raise ValueError("Missing or duplicate headers.")
        return [dict(zip(matrix[0], row)) for row in matrix[1:]]


TIMETABLE_HEADER = (
    "department,graduation_year,academic_year,semester,section,subject,teacher_roll_no,weekday,starts,ends,room,valid_from,valid_until"
)
COHORT_HEADER = "roll_no,department,graduation_year,academic_year,semester,section"


@router.get("/template/{kind}")
def template(kind: str, user=Depends(current_user)):
    require(user, ADMINS)
    if kind not in {"timetable", "cohorts"}:
        raise HTTPException(404, "Template not found.")
    header = TIMETABLE_HEADER if kind == "timetable" else COHORT_HEADER
    return Response(header + "\n", media_type="text/csv", headers={"Content-Disposition": f'attachment; filename="{kind}.csv"'})


@router.post("/imports/preview")
async def preview_import(kind: str = Form(...), file: UploadFile = File(...), user=Depends(current_user), db: Session = Depends(get_db)):
    require(user, ADMINS)
    if kind not in {"timetable", "cohorts"}:
        raise HTTPException(422, "Choose timetable or cohorts.")
    try:
        raw = sheet_rows(file.filename or "", await file.read(MAX_FILE_SIZE + 1))
    except (ValueError, UnicodeError, csv.Error, zipfile.BadZipFile, ET.ParseError, KeyError, IndexError):
        raise HTTPException(422, "Invalid sheet. Use the template, one worksheet, plain values and UTF-8 CSV or XLSX.")
    if not raw:
        raise HTTPException(422, "The sheet has no records.")
    departments = {d.code: d.id for d in db.scalars(select(Department).where(Department.institution_id == user.institution_id))}
    users = {u.roll_no: u for u in db.scalars(select(User).where(User.institution_id == user.institution_id))}
    rows, errors, seen, slots = [], [], set(), []
    for line, record in enumerate(raw, 2):
        try:
            item = (SlotInput if kind == "timetable" else CohortInput).model_validate(record)
            data = item.model_dump(mode="json")
            department = departments.get(item.department.upper())
            if not department:
                raise ValueError("Unknown department code.")
            data["department_id"] = department
            data["section"] = item.section.upper()
            if kind == "cohorts":
                student = users.get(item.roll_no.upper())
                if not student or student.role != "student":
                    raise ValueError("Student account not found; onboard students first.")
                if not db.scalar(select(StudentProfile.id).where(StudentProfile.user_id == student.id)):
                    raise ValueError("Student profile is missing.")
                if student.id in seen:
                    raise ValueError("Duplicate student in sheet.")
                seen.add(student.id)
                data["user_id"] = student.id
            else:
                teacher = users.get(item.teacher_roll_no.upper())
                if not teacher or teacher.role == "student":
                    raise ValueError("Teacher must have an existing staff account.")
                if item.valid_until < item.valid_from:
                    raise ValueError("Validity end precedes start.")
                if not all(re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", t) for t in (item.starts, item.ends)) or item.ends <= item.starts:
                    raise ValueError("Use HH:MM with end after start.")
                data["teacher_id"] = teacher.id
                for other in slots:
                    overlap = (
                        data["weekday"] == other["weekday"]
                        and data["valid_from"] <= other["valid_until"]
                        and other["valid_from"] <= data["valid_until"]
                        and data["starts"] < other["ends"]
                        and other["starts"] < data["ends"]
                    )
                    same_group = all(
                        data[k] == other[k] for k in ("department_id", "graduation_year", "academic_year", "semester", "section")
                    )
                    if overlap and (
                        data["teacher_id"] == other["teacher_id"] or same_group or (data["room"] and data["room"] == other["room"])
                    ):
                        raise ValueError("Conflicting teacher, room or cohort time slot.")
                # Existing slots in other cohorts remain active after this import.
                for existing in db.scalars(
                    select(TeachingSlot).where(TeachingSlot.institution_id == user.institution_id, TeachingSlot.active.is_(True))
                ):
                    same_group = all(
                        data[k] == getattr(existing, k)
                        for k in ("department_id", "graduation_year", "academic_year", "semester", "section")
                    )
                    if (
                        not same_group
                        and data["weekday"] == existing.weekday
                        and data["valid_from"] <= existing.valid_until
                        and existing.valid_from <= data["valid_until"]
                        and data["starts"] < existing.ends
                        and existing.starts < data["ends"]
                        and (data["teacher_id"] == existing.teacher_id or (data["room"] and data["room"] == existing.room))
                    ):
                        raise ValueError("Conflicts with an active timetable in another cohort.")
                slots.append(data)
            rows.append(data)
        except (ValueError, ValidationError) as exc:
            errors.append({"row": line, "error": str(exc)[:500]})
    fingerprint = hashlib.sha256(json.dumps({"kind": kind, "raw": raw}, sort_keys=True).encode()).hexdigest()
    job = db.scalar(select(CampusImport).where(CampusImport.institution_id == user.institution_id, CampusImport.fingerprint == fingerprint))
    if not job:
        job = CampusImport(
            institution_id=user.institution_id, actor_id=user.id, kind=kind, fingerprint=fingerprint, rows=rows, errors=errors
        )
        db.add(job)
        db.commit()
    elif not job.confirmed_at:
        job.rows, job.errors = rows, errors
        db.commit()
    return {
        "id": job.id,
        "kind": job.kind,
        "valid_rows": len(job.rows),
        "errors": job.errors,
        "preview": job.rows[:20],
        "confirmed": job.confirmed_at is not None,
    }


@router.post("/imports/{job_id}/confirm")
def confirm_import(job_id: str, user=Depends(current_user), db: Session = Depends(get_db)):
    require(user, ADMINS)
    # Institution lock serializes timetable replacement and cohort reassignment on PostgreSQL.
    from ..models import Institution

    db.scalar(select(Institution).where(Institution.id == user.institution_id).with_for_update())
    job = scoped(db, CampusImport, user, job_id)
    if job.confirmed_at:
        return {"ok": True, "already_confirmed": True}
    if job.errors or not job.rows:
        raise HTTPException(422, "Correct all row errors and upload again; nothing has been applied.")
    if job.kind == "cohorts":
        for row in job.rows:
            student = scoped(db, User, user, row["user_id"])
            if student.role != "student":
                raise HTTPException(409, "Student account changed. Upload a fresh sheet.")
            profile = db.scalar(select(StudentProfile).where(StudentProfile.user_id == student.id))
            if not profile:
                raise HTTPException(409, "Student profile changed. Upload a fresh sheet.")
            student.department_id = row["department_id"]
            for key in ("graduation_year", "academic_year", "semester", "section"):
                setattr(profile, key, row[key])
            db.add(
                Notification(
                    institution_id=user.institution_id,
                    user_id=student.id,
                    title="Academic cohort updated",
                    message="Your branch, section and semester routing has been updated. Check Campus Hub and My Timetable.",
                )
            )
    else:
        # Validate again at confirmation; another admin might have imported since preview.
        existing = list(
            db.scalars(select(TeachingSlot).where(TeachingSlot.institution_id == user.institution_id, TeachingSlot.active.is_(True)))
        )
        keys = ("department_id", "graduation_year", "academic_year", "semester", "section")
        replaced = {tuple(r[k] for k in keys) for r in job.rows}
        for slot in existing:
            if tuple(getattr(slot, k) for k in keys) in replaced:
                slot.active = False
        for row in job.rows:
            teacher = scoped(db, User, user, row["teacher_id"])
            if teacher.role == "student":
                raise HTTPException(409, "Teacher account changed. Upload a fresh sheet.")
            for old in existing:
                if (
                    old.active
                    and row["weekday"] == old.weekday
                    and row["valid_from"] <= old.valid_until
                    and old.valid_from <= row["valid_until"]
                    and row["starts"] < old.ends
                    and old.starts < row["ends"]
                    and (row["teacher_id"] == old.teacher_id or (row["room"] and row["room"] == old.room))
                ):
                    raise HTTPException(409, "Timetable changed since preview; resolve the new conflict and re-upload.")
            allowed = {k: v for k, v in row.items() if k not in {"department", "teacher_roll_no"}}
            db.add(TeachingSlot(institution_id=user.institution_id, import_id=job.id, **allowed))
        affected = {s.id for row in job.rows for s in recipients(db, user, {k: row[k] for k in keys})}
        for student_id in affected:
            db.add(
                Notification(
                    institution_id=user.institution_id,
                    user_id=student_id,
                    title="Timetable updated",
                    message="Your teaching schedule has changed. Open My Timetable for the current subjects, teachers and rooms.",
                )
            )
    job.confirmed_at = now()
    audit(db, user, "campus.import.confirm", job.id, {"kind": job.kind, "rows": len(job.rows)})
    db.commit()
    return {"ok": True, "rows": len(job.rows)}


@router.get("/imports")
def import_history(user=Depends(current_user), db: Session = Depends(get_db)):
    require(user, ADMINS)
    return [
        {
            "id": j.id,
            "kind": j.kind,
            "rows": len(j.rows),
            "errors": len(j.errors),
            "confirmed_at": j.confirmed_at,
            "created_at": j.created_at,
        }
        for j in db.scalars(
            select(CampusImport)
            .where(CampusImport.institution_id == user.institution_id)
            .order_by(CampusImport.created_at.desc())
            .limit(50)
        )
    ]


@router.get("/timetable")
def timetable(user=Depends(current_user), db: Session = Depends(get_db)):
    profile = db.scalar(select(StudentProfile).where(StudentProfile.user_id == user.id)) if user.role == "student" else None
    slots = []
    for s in db.scalars(
        select(TeachingSlot)
        .where(TeachingSlot.institution_id == user.institution_id, TeachingSlot.active.is_(True))
        .order_by(TeachingSlot.weekday, TeachingSlot.starts)
    ):
        if user.role == "student" and not matches(user, profile, cohort(s)):
            continue
        if user.role not in ADMINS and user.role != "student":
            try:
                office, department = authority(db, user)
            except HTTPException:
                continue
            if (department and department != s.department_id) or (office == "teacher" and s.teacher_id != user.id):
                continue
        slots.append(
            {
                "id": s.id,
                **cohort(s),
                "subject": s.subject,
                "teacher": db.get(User, s.teacher_id).full_name,
                "teacher_id": s.teacher_id,
                "weekday": s.weekday,
                "starts": s.starts,
                "ends": s.ends,
                "room": s.room,
                "valid_from": s.valid_from,
                "valid_until": s.valid_until,
            }
        )
    return slots

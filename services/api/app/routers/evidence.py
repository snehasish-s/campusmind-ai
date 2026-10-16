import csv
import hashlib
import io
from datetime import datetime
from pathlib import Path
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, File, Form, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import select, delete
from sqlalchemy.orm import Session
from ..db import get_db
from ..models import InstitutionalDocument, DocumentChunk, EvidenceRequirement, EvidenceFinding, Department, User, InstitutionalTask, now
from ..security import current_user, require, scoped, audit, ADMINS, csv_safe
from ..storage import get_storage, validate_document, MAX_FILE_SIZE
from ..intelligence.retrieval import allowed_documents, index_document, answer_evidence, delete_vectors
from ..intelligence.events import track

router = APIRouter(tags=["CollegeOps evidence"])


def document_access(db, actor, doc_id):
    require(actor, ADMINS | {"hod"})
    doc = scoped(db, InstitutionalDocument, actor, doc_id)
    if actor.role == "hod" and doc.department_id != actor.department_id:
        raise HTTPException(404, "Document not found.")
    return doc


def doc_view(d):
    return {
        "id": d.id,
        "title": d.title,
        "filename": d.filename,
        "category": d.category,
        "status": d.status,
        "version": d.version,
        "parent_id": d.parent_id,
        "department_id": d.department_id,
        "owner_id": d.owner_id,
        "expires_at": d.expires_at,
        "expired": bool(d.expires_at and d.expires_at <= now()),
        **d.metadata_json,
    }


@router.get("/evidence/documents")
def documents(user=Depends(current_user), db: Session = Depends(get_db)):
    require(user, ADMINS | {"hod"})
    return [doc_view(d) for d in allowed_documents(db, user)]


@router.post("/evidence/documents")
async def upload(
    file: UploadFile = File(...),
    title: str = Form(..., min_length=2, max_length=200),
    category: str = Form("Academic evidence"),
    department_id: str = Form(""),
    owner_id: str = Form(""),
    parent_id: str = Form(""),
    expires_at: str = Form(""),
    user=Depends(current_user),
    db: Session = Depends(get_db),
):
    require(user, ADMINS | {"hod"})
    department_id = user.department_id if user.role == "hod" else department_id or None
    if department_id:
        scoped(db, Department, user, department_id)
    owner = scoped(db, User, user, owner_id) if owner_id else user
    if user.role == "hod" and owner.id != user.id and owner.department_id != department_id:
        raise HTTPException(403, "Owner must belong to your department.")
    parent = document_access(db, user, parent_id) if parent_id else None
    if parent:
        db.refresh(parent, with_for_update=True)
        if db.scalar(select(InstitutionalDocument.id).where(InstitutionalDocument.parent_id == parent.id)):
            raise HTTPException(409, "A newer version already exists. Select the latest version as the parent.")
    expiry = None
    if expires_at:
        try:
            expiry = datetime.fromisoformat(expires_at).replace(tzinfo=None)
        except ValueError:
            raise HTTPException(422, "Invalid expiry date.")
    content = await file.read(MAX_FILE_SIZE + 1)
    suffix, mime, _ = validate_document(file.filename or "", content, allow_text=True)
    fingerprint = hashlib.sha256(content).hexdigest()
    duplicate = next((d for d in allowed_documents(db, user) if d.content_hash == fingerprint), None)
    if duplicate:
        return {**doc_view(duplicate), "duplicate": True}
    key = get_storage().put(user.institution_id, content, suffix)
    document = InstitutionalDocument(
        institution_id=user.institution_id,
        title=title,
        category=category[:100],
        filename=Path((file.filename or "evidence").replace("\\", "/")).name[:200],
        storage_key=key,
        mime_type=mime,
        size_bytes=len(content),
        uploaded_by=user.id,
        content_hash=fingerprint,
        department_id=department_id,
        owner_id=owner.id,
        parent_id=parent.id if parent else None,
        version=parent.version + 1 if parent else 1,
        expires_at=expiry,
        metadata_json={},
    )
    try:
        db.add(document)
        db.flush()
        index_document(db, document)
        audit(db, user, "evidence.upload", document.id)
        db.commit()
    except Exception:
        get_storage().delete(key)
        raise
    return doc_view(document)


@router.post("/evidence/documents/{doc_id}/reindex")
def reindex(doc_id: str, user=Depends(current_user), db: Session = Depends(get_db)):
    document = document_access(db, user, doc_id)
    result = index_document(db, document)
    audit(db, user, "evidence.reindex", doc_id)
    db.commit()
    return result


class Review(BaseModel):
    status: Literal["approved", "rejected", "submitted"]
    note: str = Field(min_length=3, max_length=2000)


@router.put("/evidence/documents/{doc_id}/review")
def review(doc_id: str, body: Review, user=Depends(current_user), db: Session = Depends(get_db)):
    require(user, ADMINS)
    document = document_access(db, user, doc_id)
    if body.status == "approved":
        if db.scalar(select(InstitutionalDocument.id).where(InstitutionalDocument.parent_id == document.id)):
            raise HTTPException(409, "Approve the current document version. Restore older content as a new version if needed.")
        parent_id = document.parent_id
        while parent_id:
            parent = scoped(db, InstitutionalDocument, user, parent_id)
            parent.status = "superseded"
            parent_id = parent.parent_id
    document.status = body.status
    decision = {"status": body.status, "note": body.note, "reviewer_id": user.id, "at": now().isoformat()}
    document.metadata_json = {
        **document.metadata_json,
        "review_note": body.note,
        "reviewer_id": user.id,
        "reviewed_at": now().isoformat(),
        "reviews": [*document.metadata_json.get("reviews", [])[-19:], decision],
    }
    track(db, user, "evidence." + body.status, "Institutional evidence reviewed", document_id=doc_id)
    audit(db, user, "evidence.review", doc_id, {"status": body.status})
    db.commit()
    return doc_view(document)


@router.delete("/evidence/documents/{doc_id}")
def remove(doc_id: str, user=Depends(current_user), db: Session = Depends(get_db)):
    require(user, ADMINS)
    doc = document_access(db, user, doc_id)
    if db.scalar(select(InstitutionalDocument.id).where(InstitutionalDocument.parent_id == doc.id)):
        raise HTTPException(409, "Remove later versions first to preserve the version chain.")
    delete_vectors(doc)
    get_storage().delete(doc.storage_key)
    db.execute(delete(DocumentChunk).where(DocumentChunk.document_id == doc.id))
    db.execute(delete(EvidenceFinding).where(EvidenceFinding.document_id == doc.id))
    db.delete(doc)
    audit(db, user, "evidence.delete", doc_id)
    db.commit()
    return {"ok": True}


class RequirementInput(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    description: str = Field(min_length=3, max_length=3000)
    department_id: str | None = None
    document_ids: list[str] = Field(default_factory=list, max_length=100)


@router.post("/evidence/requirements")
def requirement(body: RequirementInput, user=Depends(current_user), db: Session = Depends(get_db)):
    return save_requirement(db, user, body)


def save_requirement(db, user, body, row=None):
    require(user, ADMINS | {"hod"})
    if row and user.role == "hod" and row.payload.get("department_id") != user.department_id:
        raise HTTPException(404, "Requirement not found.")
    if user.role == "hod":
        body.department_id = user.department_id
    if body.department_id:
        scoped(db, Department, user, body.department_id)
    if row is None:
        row = EvidenceRequirement(institution_id=user.institution_id, title=body.title, payload=body.model_dump())
        db.add(row)
    else:
        row.title, row.payload = body.title, body.model_dump()
        db.execute(delete(EvidenceFinding).where(EvidenceFinding.requirement_id == row.id))
    db.flush()
    for doc_id in set(body.document_ids):
        document_access(db, user, doc_id)
        db.add(
            EvidenceFinding(
                institution_id=user.institution_id,
                document_id=doc_id,
                requirement_id=row.id,
                payload={"mapped_by": user.id, "human_mapping": True},
            )
        )
    audit(db, user, "requirement.save", row.id)
    db.commit()
    return {"id": row.id}


@router.put("/evidence/requirements/{requirement_id}")
def edit_requirement(requirement_id: str, body: RequirementInput, user=Depends(current_user), db: Session = Depends(get_db)):
    return save_requirement(db, user, body, scoped(db, EvidenceRequirement, user, requirement_id))


def requirement_report(db, user):
    docs = {d.id: d for d in allowed_documents(db, user)}
    output = []
    for row in db.scalars(select(EvidenceRequirement).where(EvidenceRequirement.institution_id == user.institution_id)):
        if user.role == "hod" and row.payload.get("department_id") != user.department_id:
            continue
        mapped = [docs[did] for did in row.payload.get("document_ids", []) if did in docs]
        good = [d for d in mapped if d.status == "approved" and (not d.expires_at or d.expires_at > now())]
        output.append(
            {
                "id": row.id,
                "title": row.title,
                "description": row.payload["description"],
                "status": "evidence_available" if good else "coordinator_review" if mapped else "missing_evidence",
                "sources": [doc_view(d) for d in mapped],
                "finding": "Approved, unexpired evidence is mapped; adequacy still requires human review."
                if good
                else "No approved, unexpired evidence supports this requirement.",
            }
        )
    return output


@router.get("/evidence/requirements")
def requirements(user=Depends(current_user), db: Session = Depends(get_db)):
    require(user, ADMINS | {"hod"})
    return requirement_report(db, user)


class Question(BaseModel):
    question: str = Field(min_length=3, max_length=2000)


@router.post("/evidence/ask")
def ask(body: Question, user=Depends(current_user), db: Session = Depends(get_db)):
    require(user, ADMINS | {"hod"})
    result = answer_evidence(db, user, body.question)
    db.commit()
    return result


@router.get("/evidence/report.csv")
def report(user=Depends(current_user), db: Session = Depends(get_db)):
    require(user, ADMINS | {"hod"})
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Draft preparation report - human review required", "status", "finding", "source_document_ids"])
    for row in requirement_report(db, user):
        title = row["title"]
        writer.writerow(
            [
                csv_safe(title),
                row["status"],
                row["finding"],
                ";".join(d["id"] for d in row["sources"]),
            ]
        )
    audit(db, user, "evidence.report_export")
    db.commit()
    return Response(
        output.getvalue(), media_type="text/csv", headers={"Content-Disposition": 'attachment; filename="draft-evidence-report.csv"'}
    )


class TaskInput(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    description: str = Field(default="", max_length=3000)
    assigned_to: str
    department_id: str | None = None
    due_date: str = ""


@router.get("/institutional-tasks")
def tasks(user=Depends(current_user), db: Session = Depends(get_db)):
    require(user, ADMINS | {"hod"})
    query = select(InstitutionalTask).where(InstitutionalTask.institution_id == user.institution_id)
    if user.role == "hod":
        query = query.where(InstitutionalTask.department_id == (user.department_id or "none"))
    return [{"id": t.id, "title": t.title, "status": t.status, "assigned_to": t.assigned_to, **t.payload} for t in db.scalars(query)]


@router.post("/institutional-tasks")
def create_task(body: TaskInput, user=Depends(current_user), db: Session = Depends(get_db)):
    require(user, ADMINS | {"hod"})
    owner = scoped(db, User, user, body.assigned_to)
    if owner.role not in ADMINS | {"hod"}:
        raise HTTPException(422, "Assign evidence tasks to an administrator or coordinator.")
    department = user.department_id if user.role == "hod" else (body.department_id or owner.department_id)
    if department:
        scoped(db, Department, user, department)
    if user.role == "hod" and owner.department_id != department:
        raise HTTPException(403, "Assign tasks within your department.")
    if owner.role == "hod" and owner.department_id != department:
        raise HTTPException(422, "A coordinator's task must belong to their assigned department.")
    task = InstitutionalTask(
        institution_id=user.institution_id,
        title=body.title,
        assigned_to=owner.id,
        department_id=department,
        payload={"description": body.description, "due_date": body.due_date, "created_by": user.id},
    )
    db.add(task)
    db.flush()
    audit(db, user, "institutional_task.create", task.id)
    db.commit()
    return {"id": task.id}


@router.put("/institutional-tasks/{task_id}")
def task_status(
    task_id: str,
    status: Literal["pending", "in_progress", "submitted", "approved"],
    user=Depends(current_user),
    db: Session = Depends(get_db),
):
    require(user, ADMINS | {"hod"})
    task = scoped(db, InstitutionalTask, user, task_id)
    if user.role == "hod" and (task.assigned_to != user.id or status == "approved"):
        raise HTTPException(403, "Coordinators can submit their assigned tasks; administrators approve them.")
    task.status = status
    audit(db, user, "institutional_task.status", task.id, {"status": status})
    db.commit()
    return {"ok": True}

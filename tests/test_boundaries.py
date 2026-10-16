import io
import secrets
from datetime import timedelta
from pypdf import PdfWriter
from sqlalchemy import select
from fastapi.testclient import TestClient
from app.main import app
from app.db import SessionLocal
from app.models import AuthSession, Department, User
from conftest import login, secure
from test_acceptance import import_students, document_bytes, drive_payload


def test_department_scope_and_staff_role_changes(setup):
    admin, password, mail, ids = setup
    login(admin, password, identifier="ADMIN")
    import_students(admin, 2)
    students = admin.get("/api/students").json()["items"]
    department = admin.post("/api/departments", json={"code": "EE", "name": "Electrical Engineering"}, headers=secure(admin))
    assert department.status_code == 200
    with SessionLocal() as db:
        student = db.get(User, students[1]["id"])
        student.department_id = department.json()["id"]
        db.commit()
    coordinator = TestClient(app)
    login(coordinator, password, identifier="HOD")
    assert coordinator.get("/api/students").json()["total"] == 1
    assert coordinator.get(f"/api/students/{students[1]['id']}").status_code == 404
    assert (
        admin.put(f"/api/staff/{ids[('alpha', 'ADMIN')]}/access", json={"role": "placement_officer"}, headers=secure(admin)).status_code
        == 403
    )
    change = admin.put(f"/api/staff/{ids[('alpha', 'HOD')]}/access", json={"role": "placement_officer"}, headers=secure(admin))
    assert change.status_code == 200
    assert coordinator.get("/api/auth/me").status_code == 401
    login(coordinator, password, identifier="HOD")
    assert coordinator.get("/api/students").json()["total"] == 2
    coordinator.close()


def test_documents_drafts_closed_drives_and_session_expiry(setup):
    admin, password, mail, ids = setup
    login(admin, password, identifier="ADMIN")
    upload = admin.post(
        "/api/documents",
        data={"title": "Synthetic Academic Evidence", "category": "Academic records"},
        files={"file": ("evidence.docx", document_bytes())},
        headers=secure(admin),
    )
    assert upload.status_code == 200
    assert len(admin.get("/api/documents").json()) == 1
    other = TestClient(app)
    login(other, password, institution="beta", identifier="ADMIN")
    assert other.get(f"/api/documents/{upload.json()['id']}/download").status_code == 404
    assert other.get("/api/documents").json() == []
    import_students(admin)
    target = admin.get("/api/students").json()["items"][0]["id"]
    link = admin.post(f"/api/auth/invitations/{target}/distribute", headers=secure(admin)).json()["activation_url"]
    student = TestClient(app)
    chosen = secrets.token_urlsafe(20)
    assert (
        student.post("/api/auth/activate", json={"token": link.split("#token=")[1], "password": chosen, "consent": True}).status_code == 200
    )
    login(student, chosen, identifier="SYN00000")
    payload = {**drive_payload(), "status": "draft"}
    draft = admin.post("/api/drives", json=payload, headers=secure(admin)).json()
    assert student.get("/api/drives").json() == []
    assert student.post(f"/api/drives/{draft['id']}/apply", headers=secure(student)).status_code == 409
    assert admin.put(f"/api/drives/{draft['id']}", json=drive_payload(), headers=secure(admin)).status_code == 200
    assert len(student.get("/api/drives").json()) == 1
    assert admin.post(f"/api/drives/{draft['id']}/close", headers=secure(admin)).status_code == 200
    assert student.post(f"/api/drives/{draft['id']}/apply", headers=secure(student)).status_code == 409
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    content = io.BytesIO()
    writer.write(content)
    pdf = student.post("/api/resumes", files={"file": ("synthetic.pdf", content.getvalue())}, headers=secure(student))
    assert pdf.status_code == 200 and pdf.json()["extraction_status"] == "no_text"
    with SessionLocal() as db:
        session = db.scalar(select(AuthSession).where(AuthSession.user_id == target))
        session.expires_at -= timedelta(days=5)
        db.commit()
    assert student.get("/api/profile").status_code == 401
    student.close()
    other.close()


def test_chunked_body_is_bounded_and_unknown_fields_rejected(setup):
    client, password, mail, ids = setup
    login(client, password, identifier="ADMIN")
    chunks = (b"x" * 1024 * 1024 for _ in range(11))
    assert (
        client.post(
            "/api/imports/preview", content=chunks, headers={**secure(client), "Content-Type": "application/octet-stream"}
        ).status_code
        == 413
    )
    assert (
        client.post("/api/drives", json={**drive_payload(), "institution_id": "other-college"}, headers=secure(client)).status_code == 422
    )
    with SessionLocal() as db:
        other_department = db.scalar(
            select(Department).join(User, User.department_id == Department.id).where(User.id == ids[("beta", "HOD")])
        )
        wrong_department = other_department.id
    assert (
        client.post(
            "/api/staff",
            json={
                "full_name": "Synthetic Staff",
                "email": "staff@example.com",
                "roll_no": "NEWSTAFF",
                "role": "hod",
                "department_id": wrong_department,
            },
            headers=secure(client),
        ).status_code
        == 404
    )

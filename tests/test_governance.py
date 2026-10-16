import httpx
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import select
from app.main import app
from app.config import settings
from app.db import SessionLocal
from app.models import AuthSession, Resume, User
from app.security import rate_limit
from app.storage import SupabaseStorage
from conftest import login, secure
from test_intelligence import student_account, post
from test_acceptance import document_bytes


def test_privacy_request_and_authorized_erasure(setup):
    officer, password, _, _ = setup
    student, uid = student_account(officer, password)
    resume = student.post("/api/resumes", files={"file": ("resume.docx", document_bytes())}, headers=secure(student)).json()
    post(student, "/workflows", {"kind": "resume", "target_id": resume["id"]})
    request = post(student, "/privacy/deletion-request")
    assert post(student, "/privacy/deletion-request")["id"] == request["id"]
    assert (
        officer.post(f"/api/privacy/requests/{request['id']}/erase", json={"confirm_erasure": True}, headers=secure(officer)).status_code
        == 403
    )
    other = TestClient(app)
    login(other, password, institution="beta", identifier="ADMIN")
    assert (
        other.post(f"/api/privacy/requests/{request['id']}/erase", json={"confirm_erasure": True}, headers=secure(other)).status_code == 404
    )
    login(officer, password, identifier="ADMIN")
    assert (
        officer.post(f"/api/privacy/requests/{request['id']}/erase", json={"confirm_erasure": False}, headers=secure(officer)).status_code
        == 409
    )
    post(officer, f"/privacy/requests/{request['id']}/erase", {"confirm_erasure": True})
    assert student.get("/api/auth/me").status_code == 401
    assert officer.get(f"/api/resumes/{resume['id']}/download").status_code == 404
    with SessionLocal() as db:
        assert db.get(User, uid).full_name == "Deleted student account"
        assert db.scalar(select(AuthSession).where(AuthSession.user_id == uid)) is None
        assert db.scalar(select(Resume).where(Resume.user_id == uid)) is None
    student.close()
    other.close()


def test_subjective_review_and_coordinator_task_approval(setup):
    officer, password, _, ids = setup
    student, uid = student_account(officer, password)
    q = post(officer, "/questions", {"prompt": "Explain a SQL index and one trade-off.", "kind": "short", "topic": "SQL", "points": 2})
    post(officer, f"/questions/{q['id']}/approve")
    assessment = post(officer, "/assessments", {"title": "Written SQL explanation", "question_ids": [q["id"]], "duration_minutes": 10})
    attempt = post(student, f"/assessments/{assessment['id']}/start")
    result = student.put(
        f"/api/attempts/{attempt['id']}/answers?submit=true",
        json={"answers": {q["id"]: "An index speeds lookup but costs storage and write maintenance."}},
        headers=secure(student),
    ).json()
    assert result["score"] is None and result["manual_review_pending"]
    body = {"question_id": q["id"], "points": 2, "feedback": "Correctly explains lookup and maintenance cost."}
    assert student.put(f"/api/attempts/{attempt['id']}/manual-review", json=body, headers=secure(student)).status_code == 403
    reviewed = officer.put(f"/api/attempts/{attempt['id']}/manual-review", json=body, headers=secure(officer))
    assert reviewed.status_code == 200, reviewed.text
    assert reviewed.json()["examiner_total_score"] == 100 and not reviewed.json()["manual_review_pending"]
    login(officer, password, identifier="ADMIN")
    task = post(officer, "/institutional-tasks", {"title": "Review faculty evidence", "assigned_to": ids[("alpha", "HOD")]})
    coordinator = TestClient(app)
    login(coordinator, password, identifier="HOD")
    # Institution-wide tasks do not leak to unrelated department lists.
    assert coordinator.put(f"/api/institutional-tasks/{task['id']}?status=submitted", headers=secure(coordinator)).status_code == 200
    assert coordinator.put(f"/api/institutional-tasks/{task['id']}?status=approved", headers=secure(coordinator)).status_code == 403
    assert officer.put(f"/api/institutional-tasks/{task['id']}?status=approved", headers=secure(officer)).status_code == 200
    coordinator.close()
    student.close()


def test_database_rate_limiter_and_hosted_configuration(setup, monkeypatch):
    monkeypatch.setattr(settings(), "rate_limit_backend", "database")
    rate_limit("durable-test", 2, 60)
    rate_limit("durable-test", 2, 60)
    with pytest.raises(HTTPException) as error:
        rate_limit("durable-test", 2, 60)
    assert error.value.status_code == 429
    from app.config import Settings

    with pytest.raises(ValueError):
        Settings(_env_file=None, deployment_mode="render", database_url="sqlite://")


def test_supabase_private_storage_transport(monkeypatch):
    monkeypatch.setattr(settings(), "supabase_url", "https://fictional.supabase.co")
    monkeypatch.setattr(settings(), "supabase_service_role_key", "synthetic-test-key")
    requests = []

    def response(method, url, **kwargs):
        requests.append((method, url, kwargs))
        return httpx.Response(200, content=b"private bytes", request=httpx.Request(method, url))

    monkeypatch.setattr(httpx, "post", lambda url, **kw: response("POST", url, **kw))
    monkeypatch.setattr(httpx, "get", lambda url, **kw: response("GET", url, **kw))
    monkeypatch.setattr(httpx, "request", response)
    storage = SupabaseStorage()
    key = storage.put("synthetic-tenant", b"private bytes", ".txt")
    assert storage.read(key) == b"private bytes"
    storage.delete(key)
    assert "/authenticated/campusmind-private/synthetic-tenant/" in requests[1][1]
    assert requests[1][2]["headers"]["Authorization"] == "Bearer synthetic-test-key"
    assert requests[2][2]["json"] == {"prefixes": [key]}
    with pytest.raises(ValueError):
        storage.read("../other/private.txt")


def test_expired_import_lease_recovery_is_scoped_and_guarded(setup):
    from datetime import timedelta
    from app.models import ImportJob, now
    from test_acceptance import preview, csv_data

    client, password, _, _ = setup
    login(client, password)
    job = preview(client, csv_data(2))
    with SessionLocal() as db:
        record = db.get(ImportJob, job["id"])
        record.status = "running"
        record.lease_token = "synthetic-old-lease"
        record.lease_expires_at = now() + timedelta(minutes=5)
        db.commit()
    assert client.post(f"/api/imports/{job['id']}/recover", headers=secure(client)).status_code == 409
    with SessionLocal() as db:
        record = db.get(ImportJob, job["id"])
        record.lease_expires_at = now() - timedelta(seconds=1)
        db.commit()
    assert client.get(f"/api/imports/{job['id']}").json()["recoverable"]
    other = TestClient(app)
    login(other, password, institution="beta")
    assert other.post(f"/api/imports/{job['id']}/recover", headers=secure(other)).status_code == 404
    recovered = post(client, f"/imports/{job['id']}/recover")
    assert recovered["status"] == "failed"
    completed = post(client, f"/imports/{job['id']}/confirm")
    assert completed["created"] == 2 and completed["status"] == "completed"
    other.close()


def test_bootstrap_cannot_reinitialize_existing_institutions(setup, monkeypatch):
    client, _, _, _ = setup
    monkeypatch.setattr(settings(), "bootstrap_token", "synthetic-setup-token-that-is-long-enough")
    body = {
        "token": "synthetic-wrong-token-that-is-long-enough",
        "institution_name": "Fictional Setup Institute",
        "slug": "fictional-setup",
        "admin_name": "Synthetic Admin",
        "admin_email": "synthetic@example.com",
        "password": "synthetic-chosen-password-only-for-tests",
    }
    assert client.post("/api/setup", json=body).status_code == 403
    body["token"] = settings().bootstrap_token
    assert client.post("/api/setup", json=body).status_code == 409


def test_suggested_questions_need_approval_and_workflow_retries_are_bounded(setup):
    officer, password, _, _ = setup
    student, _ = student_account(officer, password)
    run = post(officer, "/workflows", {"kind": "assessment_draft", "topic": "SQL", "count": 2})
    assert run["status"] == "completed" and run["provider"] == "curated_synthetic_catalog"
    questions = officer.get("/api/questions").json()
    assert len(questions) == 2 and all(q["status"] == "draft" for q in questions)
    assert (
        officer.post(
            "/api/assessments",
            json={"title": "Unreviewed questions", "question_ids": [q["id"] for q in questions], "duration_minutes": 10},
            headers=secure(officer),
        ).status_code
        == 409
    )
    assert student.post("/api/workflows", json={"kind": "assessment_draft", "topic": "SQL"}, headers=secure(student)).status_code == 403
    failed = post(officer, "/workflows", {"kind": "assessment_draft", "topic": "unknown-topic"})
    assert failed["status"] == "failed"
    for _ in range(2):
        assert post(officer, f"/workflows/{failed['id']}/retry")["status"] == "failed"
    assert officer.post(f"/api/workflows/{failed['id']}/retry", headers=secure(officer)).status_code == 409
    assert student.get("/api/workflows").json() == []
    assert student.get(f"/api/workflows/{run['id']}").status_code == 404
    student.close()


def test_document_versions_replace_retrieval_sources_and_keep_history(setup):
    client, password, _, _ = setup
    login(client, password, identifier="ADMIN")

    def upload(text, parent=""):
        r = client.post(
            "/api/evidence/documents",
            files={"file": ("report.txt", text.encode())},
            data={"title": "Synthetic versioned report", "parent_id": parent},
            headers=secure(client),
        )
        assert r.status_code == 200, r.text
        return r.json()

    old = upload("Faculty workshop evidence: obsolete synthetic curriculum.")
    body = {"status": "approved", "note": "Reviewed the synthetic source version."}
    assert client.put(f"/api/evidence/documents/{old['id']}/review", json=body, headers=secure(client)).status_code == 200
    new = upload("Faculty workshop evidence: revised synthetic database curriculum.", old["id"])
    assert new["version"] == 2
    assert client.put(f"/api/evidence/documents/{new['id']}/review", json=body, headers=secure(client)).status_code == 200
    assert client.post(f"/api/evidence/documents/{new['id']}/reindex", headers=secure(client)).status_code == 200
    answer = post(client, "/evidence/ask", {"question": "faculty workshop curriculum"})
    assert {s["document_id"] for s in answer["sources"]} == {new["id"]}
    documents = client.get("/api/evidence/documents").json()
    assert next(d for d in documents if d["id"] == old["id"])["status"] == "superseded"
    assert client.delete(f"/api/evidence/documents/{old['id']}", headers=secure(client)).status_code == 409


def test_manual_reset_requires_admin_and_invalidates_student_session(setup):
    import secrets

    client, password, _, _ = setup
    student, uid = student_account(client, password)
    assert client.post(f"/api/auth/password-reset/{uid}/distribute", headers=secure(client)).status_code == 403
    login(client, password, identifier="ADMIN")
    reset = post(client, f"/auth/password-reset/{uid}/distribute")
    chosen = secrets.token_urlsafe(20)
    token = reset["activation_url"].split("#token=")[1]
    assert student.post("/api/auth/activate", json={"token": token, "password": chosen}).status_code == 200
    assert student.get("/api/auth/me").status_code == 401
    login(student, chosen, identifier="SYN00000")
    student.close()


def test_local_model_adapter_disables_external_tracing_and_validates_schema(monkeypatch):
    from app.intelligence.providers import structured
    from app.intelligence.contracts import AdvisoryAnswer
    from langsmith.run_helpers import get_tracing_context

    monkeypatch.setattr(settings(), "ai_mode", "ollama")
    monkeypatch.setenv("LANGSMITH_TRACING", "true")

    class LocalModel:
        def __init__(self, **kwargs):
            assert kwargs["base_url"].startswith("http://localhost:")
            assert kwargs["reasoning"] is False

        def with_structured_output(self, schema, method):
            assert schema is AdvisoryAnswer and method == "json_schema"
            return self

        def invoke(self, messages):
            assert get_tracing_context()["enabled"] is False
            assert "<untrusted-data>" in messages[1].content
            return {"answer": "Synthetic advisory response.", "source_ids": []}

    monkeypatch.setattr("langchain_ollama.ChatOllama", LocalModel)
    result = structured("Practice feedback", {"response": "Synthetic input"}, AdvisoryAnswer)
    assert result.answer == "Synthetic advisory response."


def test_student_supplied_csv_formula_prefixes_are_escaped(setup):
    import csv
    import io
    from app.security import csv_safe

    client, password, _, _ = setup
    student, _ = student_account(client, password)
    profile = student.get("/api/profile").json()
    fields = ["full_name", "graduation_year", "cgpa", "active_backlogs", "phone", "bio", "projects", "internships"]
    body = {k: profile[k] for k in fields}
    body["full_name"] = "\t=SUM(1,1)"
    assert student.put("/api/profile", json=body, headers=secure(student)).status_code == 200
    rows = list(csv.DictReader(io.StringIO(client.get("/api/analytics/export.csv").text)))
    # Profile validation strips surrounding whitespace; the remaining formula
    # prefix must still be escaped in the officer's actual CSV response.
    assert rows[0]["name"] == "'" + body["full_name"].strip()
    assert csv_safe("\t=1+1").startswith("'\t=")
    assert csv_safe("  =1+1").startswith("'")
    assert csv_safe("Synthetic Name") == "Synthetic Name"
    student.close()

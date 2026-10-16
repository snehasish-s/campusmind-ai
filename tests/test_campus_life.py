import hashlib
import hmac
import io
import json
from datetime import timedelta
from sqlalchemy import select
from app import models as m
from app.db import SessionLocal
from app.config import settings
from app.campus_services import run_automations
from app.intelligence.preparation import gap_analysis
from conftest import login, secure
from test_campus import add_students


def assignment(client, department, **extra):
    body = {
        "title": "SQL evidence assignment",
        "message": "Write joins and explain the result.",
        "kind": "assignment",
        "subject": "Database Systems",
        "audience": {"department_id": department, "academic_year": 4, "semester": 7, "graduation_year": 2027, "section": "A"},
        "due_at": (m.now() + timedelta(hours=20)).isoformat(),
        **extra,
    }
    response = client.post("/api/campus/posts", data={"payload": json.dumps(body)}, headers=secure(client))
    assert response.status_code == 200, response.text
    return response.json()["id"]


def plan(client, department, **extra):
    return {
        "reference": "CSE-2026-TERM7",
        "title": "Semester tuition instalment",
        "term": "2026-27 Semester 7",
        "category": "tuition",
        "amount_paise": 1250050,
        "due_at": (m.now() + timedelta(days=2)).isoformat(),
        "audience": {"department_id": department, "section": "A"},
        **extra,
    }


def test_assignment_submission_grade_passport_share_and_isolation(setup):
    client, password, _, identities = setup
    ids = add_students(password)
    login(client, password, identifier="ADMIN")
    post_id = assignment(client, ids["department"])
    config = {
        "rubric": [{"label": "Correctness", "maximum": 60}, {"label": "Explanation", "maximum": 40}],
        "skills": ["SQL"],
        "allow_late": False,
    }
    assert client.put(f"/api/campus/assignments/{post_id}/policy", json=config, headers=secure(client)).status_code == 200
    login(client, password, identifier="S001")
    with SessionLocal() as db:
        profile = db.scalar(select(m.StudentProfile).where(m.StudentProfile.user_id == ids["S001"]))
        profile.academic_year = 2
        db.commit()
    # Campus academics and passports remain available before PlacementOS admission.
    assert client.get("/api/drives").status_code == 403
    assert client.get("/api/campus/passport").status_code == 200
    # Current cohort must still match: restore year for this assignment.
    with SessionLocal() as db:
        p = db.scalar(select(m.StudentProfile).where(m.StudentProfile.user_id == ids["S001"]))
        p.academic_year = 4
        db.commit()
    response = client.post(
        f"/api/campus/assignments/{post_id}/submit",
        data={"content": "SELECT * FROM students JOIN projects USING (student_id);"},
        files={"file": ("work.txt", b"Synthetic SQL explanation", "text/plain")},
        headers=secure(client),
    )
    assert response.status_code == 200, response.text
    entry = response.json()
    entry_id = entry["id"]
    assert entry["version"] == 1
    # A second student and a different institution cannot access the private work.
    login(client, password, identifier="S002")
    assert client.get(f"/api/campus/assignments/submissions/{entry_id}/attachment").status_code in {403, 404}
    assert (
        client.post(f"/api/campus/assignments/{post_id}/submit", data={"content": "Unassigned"}, headers=secure(client)).status_code == 404
    )
    login(client, password, institution="beta", identifier="ADMIN")
    assert client.get(f"/api/campus/assignments/submissions/{entry_id}/attachment").status_code == 404
    login(client, password, identifier="TEACHER")
    assert client.put(
        f"/api/campus/assignments/submissions/{entry_id}/review",
        json={"marks": [60, 40], "feedback": "Unassigned reviewer"},
        headers=secure(client),
    ).status_code in {403, 404}
    login(client, password, identifier="ADMIN")
    assert client.put(f"/api/campus/assignments/{post_id}/policy", json=config, headers=secure(client)).status_code == 409
    grade = {"marks": [55, 35], "feedback": "Correct joins and a clear explanation of the matching keys.", "verify_skills": True}
    r = client.put(f"/api/campus/assignments/submissions/{entry_id}/review", json=grade, headers=secure(client))
    assert r.status_code == 200 and r.json()["score"] == 90, r.text
    login(client, password, identifier="S001")
    passport = client.get("/api/campus/passport").json()
    evidence = passport["evidence"][0]
    assert passport["counts"]["faculty_verified"] == 1
    assert client.put(f"/api/skills/{evidence['id']}/review", json={"status": "rejected"}, headers=secure(client)).status_code == 403
    with SessionLocal() as db:
        gap = gap_analysis(db, db.get(m.User, ids["S001"]))
        assert "SQL" in gap["strengths"]
    share = client.post(
        "/api/campus/passport/shares", json={"evidence_ids": [evidence["id"]], "consent": True}, headers=secure(client)
    ).json()
    public = client.get(f"/api/campus/passport/shared/{share['token']}")
    assert public.status_code == 200
    assert "quote" not in public.json()["evidence"][0] and "roll_no" not in public.json()
    with SessionLocal() as db:
        assert db.get(m.PassportShare, share["id"]).token_hash != share["token"]
    assert client.get("/api/campus/privacy/activity").json()
    assert client.delete(f"/api/campus/passport/shares/{share['id']}", headers=secure(client)).status_code == 200
    assert client.get(f"/api/campus/passport/shared/{share['token']}").status_code == 404
    exported = client.get("/api/privacy/export").json()
    assert len(exported["assignments"]) == 1
    # A revised grade supersedes evidence instead of allowing obsolete verification.
    login(client, password, identifier="ADMIN")
    grade.update(marks=[10, 10], verify_skills=False)
    assert client.put(f"/api/campus/assignments/submissions/{entry_id}/review", json=grade, headers=secure(client)).status_code == 200
    login(client, password, identifier="S001")
    assert client.get("/api/campus/passport").json()["counts"]["faculty_verified"] == 0


def test_deadlines_versions_validation_and_today(setup):
    client, password, _, _ = setup
    ids = add_students(password)
    login(client, password, identifier="ADMIN")
    first = assignment(client, ids["department"])
    second = assignment(client, ids["department"], title="Database revision")
    login(client, password, identifier="S001")
    day = client.get("/api/campus/today")
    assert day.status_code == 200, day.text
    assert {first, second} <= {item["id"] for item in day.json()["items"]}
    assert day.json()["conflicts"][0]["kind"] == "workload"
    assert client.post(f"/api/campus/assignments/{first}/submit", data={"content": ""}, headers=secure(client)).status_code == 422
    assert (
        client.post(
            f"/api/campus/assignments/{first}/submit",
            files={"file": ("virus.pdf", b"not a pdf", "application/pdf")},
            headers=secure(client),
        ).status_code
        == 422
    )
    for version in (1, 2):
        r = client.post(f"/api/campus/assignments/{first}/submit", data={"content": "Reviewed-safe exercise text"}, headers=secure(client))
        assert r.status_code == 200 and r.json()["version"] == version
    with SessionLocal() as db:
        db.get(m.CampusPost, first).due_at = m.now() - timedelta(minutes=1)
        db.commit()
    assert client.post(f"/api/campus/assignments/{first}/submit", data={"content": "late"}, headers=secure(client)).status_code == 409


def test_reminder_idempotency_and_fee_demo_flow(setup):
    client, password, _, _ = setup
    ids = add_students(password)
    login(client, password, identifier="ADMIN")
    assignment(client, ids["department"])
    payload = plan(client, ids["department"])
    assert client.post("/api/campus/fees/plans/preview", json=payload, headers=secure(client)).json()["students"] == 1
    issue = client.post("/api/campus/fees/plans", json=payload, headers=secure(client))
    assert issue.status_code == 200 and issue.json()["invoices"] == 1
    assert client.post("/api/campus/fees/plans", json=payload, headers=secure(client)).json()["already_issued"]
    first = client.post("/api/campus/automations/run", headers=secure(client)).json()
    second = client.post("/api/campus/automations/run", headers=secure(client)).json()
    assert first["delivered"] == 2 and second["delivered"] == 0
    invoice = client.get("/api/campus/fees").json()["invoices"][0]
    login(client, password, identifier="S002")
    assert client.get("/api/campus/fees").json()["invoices"] == []
    assert (
        client.post(
            f"/api/campus/fees/{invoice['id']}/orders", json={"idempotency_key": "synthetic-request-key"}, headers=secure(client)
        ).status_code
        == 404
    )
    assert client.get("/api/campus/automations").status_code == 403
    login(client, password, identifier="S001")
    path = f"/api/campus/fees/{invoice['id']}/orders"
    created = client.post(path, json={"idempotency_key": "synthetic-request-key"}, headers=secure(client)).json()
    assert client.post(path, json={"idempotency_key": "another-request-key"}, headers=secure(client)).json()["id"] == created["id"]
    for _ in range(2):
        assert client.post(f"/api/campus/fees/orders/{created['id']}/demo-complete", headers=secure(client)).status_code == 200
    ledger = client.get("/api/campus/fees").json()
    assert ledger["totals"]["collected_paise"] == 0 and ledger["totals"]["demo_paid_paise"] == payload["amount_paise"]
    assert "NO MONEY COLLECTED" in client.get(f"/api/campus/fees/receipts/{created['id']}").text
    login(client, password, institution="beta", identifier="ADMIN")
    assert client.get(f"/api/campus/fees/receipts/{created['id']}").status_code == 404
    login(client, password, identifier="TEACHER")
    assert client.get("/api/campus/fees").status_code == 403


def test_razorpay_signature_capture_webhook_and_environment_boundaries(setup, monkeypatch):
    client, password, _, _ = setup
    ids = add_students(password)
    login(client, password, identifier="ADMIN")
    response = client.post("/api/campus/fees/plans", json=plan(client, ids["department"]), headers=secure(client))
    assert response.status_code == 200
    invoice = client.get("/api/campus/fees").json()["invoices"][0]
    with SessionLocal() as db:
        tenant = db.get(m.User, ids["S001"]).institution_id
    config = settings()
    for key, value in {
        "payment_provider": "razorpay",
        "razorpay_key_id": "rzp_test_synthetic",
        "razorpay_key_secret": "synthetic-test-secret",
        "razorpay_webhook_secret": "synthetic-webhook-secret",
        "payment_institution_id": tenant,
    }.items():
        monkeypatch.setattr(config, key, value)
    captured = {"captured": True, "status": "captured", "order_id": "order_synthetic", "amount": invoice["amount_paise"], "currency": "INR"}

    def provider(method, path, **kwargs):
        return {"id": "order_synthetic", "amount": invoice["amount_paise"], "currency": "INR"} if path == "orders" else captured

    monkeypatch.setattr("app.routers.fees.gateway", provider)
    login(client, password, identifier="S001")
    order = client.post(
        f"/api/campus/fees/{invoice['id']}/orders", json={"idempotency_key": "razorpay-test-request"}, headers=secure(client)
    ).json()
    body = {"razorpay_order_id": "order_synthetic", "razorpay_payment_id": "pay_synthetic", "razorpay_signature": "0" * 64}
    assert client.post(f"/api/campus/fees/orders/{order['id']}/verify", json=body, headers=secure(client)).status_code == 400
    body["razorpay_signature"] = hmac.new(config.razorpay_key_secret.encode(), b"order_synthetic|pay_synthetic", hashlib.sha256).hexdigest()
    captured["amount"] += 1
    assert client.post(f"/api/campus/fees/orders/{order['id']}/verify", json=body, headers=secure(client)).status_code == 409
    captured["amount"] -= 1
    captured["status"] = "authorized"
    assert client.post(f"/api/campus/fees/orders/{order['id']}/verify", json=body, headers=secure(client)).status_code == 409
    captured["status"] = "captured"
    assert client.post(f"/api/campus/fees/orders/{order['id']}/verify", json=body, headers=secure(client)).status_code == 200
    assert client.get("/api/campus/fees").json()["totals"]["collected_paise"] == 0
    event = json.dumps(
        {"event": "payment.captured", "payload": {"payment": {"entity": {"id": "pay_synthetic", "order_id": "order_synthetic"}}}}
    ).encode()
    signature = hmac.new(config.razorpay_webhook_secret.encode(), event, hashlib.sha256).hexdigest()
    assert client.post("/api/campus/fees/webhook", content=event, headers={"x-razorpay-signature": "wrong"}).status_code == 400
    for duplicate in (False, True):
        r = client.post("/api/campus/fees/webhook", content=event, headers={"x-razorpay-signature": signature})
        assert r.status_code == 200, r.text
        assert r.json().get("duplicate", False) == duplicate
    assert client.post(f"/api/campus/fees/orders/{order['id']}/demo-complete", headers=secure(client)).status_code == 403
    # Test receipts cannot settle real fees after switching to live keys.
    monkeypatch.setattr(config, "razorpay_key_id", "rzp_live_synthetic")
    assert client.post(f"/api/campus/fees/orders/{order['id']}/verify", json=body, headers=secure(client)).status_code == 409


def test_fee_bulk_issue_1000_and_export(setup):
    client, password, _, identities = setup
    login(client, password, identifier="ADMIN")
    with SessionLocal() as db:
        tenant = db.get(m.User, identities[("alpha", "ADMIN")]).institution_id
        for i in range(1000):
            student = m.User(
                institution_id=tenant,
                role="student",
                roll_no=f"SYN-{i}",
                full_name=f"Synthetic fee student {i}",
                email=f"synthetic-fee-{i}@example.invalid",
            )
            db.add(student)
            db.flush()
            db.add(m.StudentProfile(institution_id=tenant, user_id=student.id, graduation_year=2027))
        db.commit()
    payload = plan(client, None, audience={})
    r = client.post("/api/campus/fees/plans", json=payload, headers=secure(client))
    assert r.status_code == 200 and r.json()["invoices"] == 1000, r.text
    ledger = client.get("/api/campus/fees").json()
    assert len(ledger["invoices"]) == 1000
    assert ledger["totals"]["billed_paise"] == 1000 * payload["amount_paise"]
    export = client.get("/api/campus/fees/export")
    assert export.status_code == 200 and len(list(__import__("csv").reader(io.StringIO(export.text)))) == 1001


def test_reminder_optout_csrf_and_expired_share(setup):
    client, password, _, _ = setup
    ids = add_students(password)
    login(client, password, identifier="ADMIN")
    assignment(client, ids["department"])
    assert client.put("/api/campus/automations", json={"enabled": False}).status_code == 403
    assert client.put("/api/campus/automations", json={"enabled": False}, headers=secure(client)).status_code == 200
    assert client.post("/api/campus/automations/run", headers=secure(client)).json()["skipped"]
    with SessionLocal() as db:
        tenant = db.get(m.User, ids["S001"]).institution_id
        db.add(
            m.PassportShare(
                institution_id=tenant,
                user_id=ids["S001"],
                token_hash=hashlib.sha256(b"expired").hexdigest(),
                evidence_ids=[],
                expires_at=m.now() - timedelta(seconds=1),
            )
        )
        db.commit()
    assert client.get("/api/campus/passport/shared/expired").status_code == 404
    login(client, password, identifier="S001")
    assert client.get("/api/campus/today").status_code == 200
    with SessionLocal() as db:
        assert run_automations(db, tenant, force=True)["delivered"] == 0


def test_live_payment_refresh_uses_provider_and_not_browser_amount(setup, monkeypatch):
    client, password, _, _ = setup
    ids = add_students(password)
    login(client, password, identifier="ADMIN")
    assert client.post("/api/campus/fees/plans", json=plan(client, ids["department"]), headers=secure(client)).status_code == 200
    invoice = client.get("/api/campus/fees").json()["invoices"][0]
    with SessionLocal() as db:
        tenant = db.get(m.User, ids["S001"]).institution_id
    for key, value in {
        "payment_provider": "razorpay",
        "razorpay_key_id": "rzp_live_synthetic",
        "razorpay_key_secret": "synthetic-only",
        "payment_institution_id": tenant,
    }.items():
        monkeypatch.setattr(settings(), key, value)

    def provider(method, path, **kwargs):
        if path == "orders":
            assert kwargs["json"]["amount"] == invoice["amount_paise"]
            return {"id": "order_syntheticlive", "amount": invoice["amount_paise"], "currency": "INR"}
        if path.endswith("/payments"):
            return {"items": [{"id": "pay_syntheticlive", "status": "captured"}]}
        return {
            "status": "captured",
            "captured": True,
            "order_id": "order_syntheticlive",
            "amount": invoice["amount_paise"],
            "currency": "INR",
        }

    monkeypatch.setattr("app.routers.fees.gateway", provider)
    login(client, password, identifier="S001")
    path = f"/api/campus/fees/{invoice['id']}/orders"
    assert client.post(path, json={"idempotency_key": "synthetic-live-request", "amount": 1}, headers=secure(client)).status_code == 422
    order = client.post(path, json={"idempotency_key": "synthetic-live-request"}, headers=secure(client)).json()
    assert client.post(f"/api/campus/fees/orders/{order['id']}/refresh", headers=secure(client)).json()["status"] == "paid"
    ledger = client.get("/api/campus/fees").json()
    assert ledger["totals"]["collected_paise"] == invoice["amount_paise"]
    assert ledger["totals"]["demo_paid_paise"] == 0
    assert "TEST-" not in client.get(f"/api/campus/fees/receipts/{order['id']}").text
    assert client.post(path, json={"idempotency_key": "synthetic-live-request"}, headers=secure(client)).status_code == 409


def test_erasure_removes_private_work_and_preserves_pseudonymous_accounting(setup):
    client, password, _, identities = setup
    ids = add_students(password)
    login(client, password, identifier="ADMIN")
    post = assignment(client, ids["department"])
    assert client.post("/api/campus/fees/plans", json=plan(client, ids["department"]), headers=secure(client)).status_code == 200
    translation = client.post("/api/campus/translation-draft", json={"text": "Synthetic notice."}, headers=secure(client))
    assert translation.status_code == 200 and translation.json()["provider"] == "unavailable"
    login(client, password, identifier="S001")
    response = client.post(
        f"/api/campus/assignments/{post}/submit",
        data={"content": "Private explanation"},
        files={"file": ("work.txt", b"Private fictional work", "text/plain")},
        headers=secure(client),
    )
    assert response.status_code == 200
    with SessionLocal() as db:
        entry = db.get(m.AssignmentSubmission, response.json()["id"])
        from app.storage import get_storage

        path = get_storage().path(entry.storage_key)
        assert path.exists()
    request = client.post("/api/privacy/deletion-request", headers=secure(client)).json()
    login(client, password, identifier="ADMIN")
    erased = client.post(f"/api/privacy/requests/{request['id']}/erase", json={"confirm_erasure": True}, headers=secure(client))
    assert erased.status_code == 200, erased.text
    assert not path.exists()
    with SessionLocal() as db:
        assert db.scalar(select(m.AssignmentSubmission).where(m.AssignmentSubmission.user_id == ids["S001"])) is None
        assert db.scalar(select(m.FeeInvoice).where(m.FeeInvoice.user_id == ids["S001"])) is not None
        assert db.get(m.User, ids["S001"]).full_name == "Deleted student account"
        tenant = db.get(m.User, identities[("alpha", "ADMIN")]).institution_id
        result = run_automations(db, tenant, force=True)
        assert result["delivered"] == 0

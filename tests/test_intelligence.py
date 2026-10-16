import secrets
from datetime import timedelta
from fastapi.testclient import TestClient
from app.main import app
from app.db import SessionLocal
from app.models import TestAttempt as AttemptRecord, now
from app.intelligence.assessments import grade
from app.intelligence.workflows import extract_resume
from conftest import login, secure
from test_acceptance import import_students, document_bytes, drive_payload


def post(client, path, body=None):
    response = client.post("/api" + path, json=body, headers=secure(client))
    assert response.status_code == 200, response.text
    return response.json()


def student_account(officer, password):
    login(officer, password)
    import_students(officer)
    uid = officer.get("/api/students").json()["items"][0]["id"]
    token = post(officer, f"/auth/invitations/{uid}/distribute")["activation_url"].split("#token=")[1]
    student = TestClient(app)
    chosen = secrets.token_urlsafe(20)
    assert student.post("/api/auth/activate", json={"token": token, "password": chosen, "consent": True}).status_code == 200
    login(student, chosen, identifier="SYN00000")
    return student, uid


def approved_assessment(officer):
    questions = []
    for prompt, options, correct in [
        ("Which SQL clause filters rows?", ["WHERE", "ORDER BY", "SELECT"], [0]),
        ("Which SQL clause groups rows?", ["LIMIT", "GROUP BY", "DISTINCT"], [1]),
    ]:
        q = post(
            officer,
            "/questions",
            {
                "prompt": prompt,
                "topic": "SQL",
                "options": options,
                "correct": correct,
                "explanation": "Use the SQL clause appropriate to the requested operation.",
            },
        )
        post(officer, f"/questions/{q['id']}/approve")
        questions.append(q["id"])
    return post(
        officer, "/assessments", {"title": "SQL foundations", "question_ids": questions, "duration_minutes": 10, "randomize": False}
    ), questions


def test_resume_graph_assessment_adaptation_and_boundaries(setup):
    officer, password, _, _ = setup
    student, uid = student_account(officer, password)
    resume = student.post("/api/resumes", files={"file": ("resume.docx", document_bytes())}, headers=secure(student)).json()
    run = post(student, "/workflows", {"kind": "resume", "target_id": resume["id"]})
    assert run["status"] == "completed", run
    assert run["provider"] == "deterministic_fallback"
    assert run["stages"] == ["authorized", "validated", "persisted"]
    evidence = student.get("/api/skills").json()
    assert {"Python", "SQL"} <= {e["skill"] for e in evidence}
    assert all(e["evidence_type"] == "resume_claim" for e in evidence)
    e = evidence[0]
    assert (
        student.put(
            f"/api/skills/{e['id']}/review",
            json={"status": "confirmed", "note": "This is supported by my project."},
            headers=secure(student),
        ).status_code
        == 200
    )
    assert student.get("/api/skills").json()[0]["evidence_type"] == "resume_claim"
    post(student, "/workflows", {"kind": "learning"})
    plan = student.get("/api/roadmaps").json()[0]
    post(student, f"/roadmaps/{plan['id']}/accept")
    post(student, f"/learning-tasks/{plan['tasks'][0]['id']}/complete")
    assessment, questions = approved_assessment(officer)
    attempt = post(student, f"/assessments/{assessment['id']}/start")
    assert all("correct" not in q and "explanation" not in q for q in attempt["questions"])
    assert "correct" not in student.get("/api/privacy/export").text
    # Tampering cannot introduce a question or select an out-of-range answer.
    assert (
        student.put(f"/api/attempts/{attempt['id']}/answers", json={"answers": {questions[0]: [99]}}, headers=secure(student)).status_code
        == 422
    )
    result = student.put(
        f"/api/attempts/{attempt['id']}/answers?submit=true",
        json={"answers": {questions[0]: [0], questions[1]: [1]}},
        headers=secure(student),
    )
    assert result.status_code == 200, result.text
    assert result.json()["score"] == 100
    assert result.json()["topics"]["SQL"]["score"] == 100
    assert all("correct" in q for q in result.json()["questions"])
    assert any(e["evidence_type"] == "assessment_verified" and e["skill"] == "SQL" for e in student.get("/api/skills").json())
    plans = student.get("/api/roadmaps").json()
    proposed = next(p for p in plans if p["status"] == "proposed")
    assert proposed["completed"] >= 1 and proposed["trigger"] == "assessment_completed"
    completed_titles = {t["title"] for t in proposed["tasks"] if t["status"] == "completed"}
    assert not any(t["title"] in completed_titles for t in proposed["tasks"] if t["status"] != "completed")
    assert len([p for p in plans if p["status"] == "active"]) == 1
    accepted = post(student, f"/roadmaps/{proposed['id']}/accept")
    assert accepted["completed"] >= 1
    assert officer.get(f"/api/analytics?student_id={uid}").json()["average"] == 100
    assert officer.get(f"/api/skills?student_id={uid}").status_code == 200
    other = TestClient(app)
    login(other, password, institution="beta")
    assert other.get(f"/api/skills?student_id={uid}").status_code == 404
    assert other.get(f"/api/workflows/{run['id']}").status_code == 404
    assert other.put(f"/api/attempts/{attempt['id']}/answers", json={"answers": {}}, headers=secure(other)).status_code == 404
    assert other.get("/api/analytics").json()["total"] == 0
    assert student.get("/api/questions").status_code == 403
    student.close()
    other.close()


def test_drive_lifecycle_eligibility_appeal_and_realistic_plan(setup):
    officer, password, _, _ = setup
    student, _ = student_account(officer, password)
    body = {
        **drive_payload(),
        "status": "draft",
        "position": ".NET Developer",
        "description": "Required: C#, .NET and SQL Server. Build maintained services.",
        "required_skills": ["C#", ".NET", "SQL Server"],
        "min_cgpa": 9,
        "deadline": (now() + timedelta(days=4)).isoformat(),
        "drive_date": (now() + timedelta(days=5)).isoformat(),
    }
    drive = post(officer, "/drives", body)
    did = drive["id"]
    assert student.get("/api/drives").json() == []
    assert officer.post(f"/api/drives/{did}/transition?status=published", headers=secure(officer)).status_code == 409
    extracted = officer.get(f"/api/drives/{did}/review").json()["extracted"]
    assert {".NET", "C#", "SQL Server"} <= {s["skill"] for s in extracted["skills"]}
    post(
        officer,
        f"/drives/{did}/review",
        {
            "approved_skills": [{"skill": s, "priority": "required"} for s in ["C#", ".NET", "SQL Server"]],
            "confirm_explicit_conditions": True,
        },
    )
    assert student.get(f"/api/matching?drive_id={did}").status_code == 404
    post(officer, f"/drives/{did}/transition?status=published")
    gap = student.get(f"/api/matching?drive_id={did}").json()
    assert gap["eligibility"]["status"] == "criteria_not_met"
    appeal = post(
        student, f"/drives/{did}/appeal", {"explanation": "Please review the documented company exception for this academic criterion."}
    )
    assert (
        officer.put(
            f"/api/eligibility-appeals/{appeal['id']}",
            json={"status": "approved", "decision": "Company coordinator explicitly confirmed this student exception."},
            headers=secure(officer),
        ).status_code
        == 200
    )
    post(student, f"/drives/{did}/apply")
    post(student, "/workflows", {"kind": "adaptive", "target_id": did})
    plan = student.get("/api/roadmaps").json()[0]
    assert "not framework mastery" in plan["explanation"] and plan["hours_budget"] <= 6
    assert any(t["skill"] == ".NET" for t in plan["tasks"])
    post(officer, f"/drives/{did}/transition?status=open")
    post(officer, f"/drives/{did}/transition?status=closed")
    post(officer, f"/drives/{did}/transition?status=completed")
    assert officer.post(f"/api/drives/{did}/close", headers=secure(officer)).status_code == 409
    student.close()


def test_evidence_sources_approval_expiry_and_tenant_filters(setup):
    admin, password, _, _ = setup
    login(admin, password, identifier="ADMIN")
    content = b"Synthetic faculty development report. In September the CSE department conducted a database workshop for faculty."
    doc = admin.post(
        "/api/evidence/documents",
        files={"file": ("faculty.txt", content)},
        data={"title": "Faculty workshop report"},
        headers=secure(admin),
    )
    assert doc.status_code == 200, doc.text
    did = doc.json()["id"]
    assert doc.json()["chunks"] > 0
    assert post(admin, "/evidence/ask", {"question": "faculty database workshop"})["insufficient_evidence"]
    assert (
        admin.put(
            f"/api/evidence/documents/{did}/review",
            json={"status": "approved", "note": "Source checked by the fictional administrator."},
            headers=secure(admin),
        ).status_code
        == 200
    )
    answer = post(admin, "/evidence/ask", {"question": "faculty database workshop"})
    assert answer["sources"][0]["document_id"] == did
    assert answer["sources"][0]["quote"] in content.decode()
    assert answer["provider"] == "deterministic_extractive_retrieval"
    duplicate = admin.post(
        "/api/evidence/documents", files={"file": ("faculty.txt", content)}, data={"title": "Duplicate"}, headers=secure(admin)
    ).json()
    assert duplicate["id"] == did and duplicate["duplicate"]
    post(
        admin,
        "/evidence/requirements",
        {
            "title": "Faculty development evidence",
            "description": "Institution-defined workshop evidence requirement",
            "document_ids": [did],
        },
    )
    assert admin.get("/api/evidence/requirements").json()[0]["status"] == "evidence_available"
    assert admin.get("/api/evidence/report.csv").status_code == 200
    other = TestClient(app)
    login(other, password, institution="beta", identifier="ADMIN")
    assert post(other, "/evidence/ask", {"question": "faculty database workshop"})["sources"] == []
    assert other.post(f"/api/evidence/documents/{did}/reindex", headers=secure(other)).status_code == 404
    assert other.get(f"/api/documents/{did}/download").status_code == 404
    login(admin, password, identifier="HOD")
    assert admin.get("/api/evidence/documents").json() == []
    login(admin, password, identifier="ADMIN")
    assert admin.delete(f"/api/evidence/documents/{did}", headers=secure(admin)).status_code == 200
    assert post(admin, "/evidence/ask", {"question": "faculty database workshop"})["sources"] == []
    other.close()


def test_expired_attempt_uses_saved_answers_and_subjective_is_ungraded(setup):
    officer, password, _, _ = setup
    student, _ = student_account(officer, password)
    assessment, questions = approved_assessment(officer)
    attempt = post(student, f"/assessments/{assessment['id']}/start")
    student.put(f"/api/attempts/{attempt['id']}/answers", json={"answers": {questions[0]: [0]}}, headers=secure(student))
    with SessionLocal() as db:
        a = db.get(AttemptRecord, attempt["id"])
        a.payload = {**a.payload, "expires_at": (now() - timedelta(seconds=1)).isoformat()}
        db.commit()
    result = student.put(
        f"/api/attempts/{attempt['id']}/answers?submit=true", json={"answers": {questions[1]: [1]}}, headers=secure(student)
    ).json()
    assert result["score"] == 50 and questions[1] not in result["answers"]
    assert grade([{"id": "q", "kind": "short", "topic": "SQL", "points": 2}], {"q": "DROP TABLE users;"})["score"] is None
    assert grade([{"id": "q", "kind": "multiple", "topic": "SQL", "points": 2, "correct": [0, 2]}], {"q": [0]})["score"] == 0
    student.close()


def test_extraction_does_not_claim_proficiency_or_fabricate():
    result = extract_resume("Learning Python. No Java experience. SQL project: used joins.", use_model=False)
    assert result["provider"] == "deterministic_fallback"
    assert result["projects"] == [] and result["certifications"] == []
    assert all(c["quote"] and c["evidence_type"] == "resume_claim" for c in result["claims"])
    assert any(c["ambiguous"] for c in result["claims"])

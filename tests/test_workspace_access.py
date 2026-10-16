import pytest
from sqlalchemy import select
from app.db import SessionLocal
from app.models import StudentProfile
from conftest import login, secure
from test_campus import add_students


@pytest.mark.parametrize("year,allowed", [(None, False), (1, False), (2, False), (3, True), (4, True), (5, False)])
def test_placement_year_gate_is_enforced_on_every_sensitive_route(setup, year, allowed):
    client, password, _, _ = setup
    students = add_students(password)
    with SessionLocal() as db:
        profile = db.scalar(select(StudentProfile).where(StudentProfile.user_id == students["S001"]))
        profile.academic_year = year
        db.commit()
    identity = login(client, password, identifier="S001")
    assert identity["placement_access"]["allowed"] == allowed
    assert identity["placement_access"]["academic_year"] == year
    assert client.get("/api/campus/posts").status_code == 200
    assert client.get("/api/campus/timetable").status_code == 200
    assert client.get("/api/profile").status_code == 200
    assert client.get("/api/privacy/export").status_code == 200
    for path in ("/api/drives", "/api/resumes", "/api/skills", "/api/assessments", "/api/analytics", "/api/workflows"):
        response = client.get(path)
        assert response.status_code == (200 if allowed else 403), (path, response.text)
    if not allowed:
        assert client.post("/api/workflows", json={"kind": "roadmap"}, headers=secure(client)).status_code == 403
        profile = client.get("/api/profile").json()
        body = {
            k: profile[k] for k in ("full_name", "graduation_year", "cgpa", "active_backlogs", "phone", "bio", "projects", "internships")
        }
        body["academic_year"] = 4
        assert client.put("/api/profile", json=body, headers=secure(client)).status_code == 422


def test_placement_gate_refreshes_after_administrator_cohort_update(setup):
    client, password, _, _ = setup
    students = add_students(password)
    login(client, password, identifier="S001")
    assert client.get("/api/drives").status_code == 200
    with SessionLocal() as db:
        p = db.scalar(select(StudentProfile).where(StudentProfile.user_id == students["S001"]))
        p.academic_year = 2
        db.commit()
    assert client.get("/api/auth/me").json()["placement_access"]["allowed"] is False
    assert client.get("/api/drives").status_code == 403
    assert client.get("/api/campus/posts").status_code == 200

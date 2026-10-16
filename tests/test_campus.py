import io
import zipfile
from datetime import date, timedelta
from xml.sax.saxutils import escape
from sqlalchemy import select
from app.db import SessionLocal
from app.models import User, StudentProfile, Department, TeachingSlot, Institution
from app.security import password_hash
from app.routers.campus import TIMETABLE_HEADER, COHORT_HEADER, sheet_rows
from conftest import login, secure


def add_students(password):
    ids = {}
    with SessionLocal() as db:
        dep = db.scalar(
            select(Department).where(
                Department.institution_id == select(Institution.id).where(Institution.slug == "alpha").scalar_subquery()
            )
        )
        for roll, section in [("S001", "A"), ("S002", "B")]:
            u = User(
                institution_id=dep.institution_id,
                department_id=dep.id,
                roll_no=roll,
                email=f"{roll}@alpha.example.com",
                full_name=f"Synthetic {roll}",
                role="student",
                active=True,
                password_hash=password_hash(password),
            )
            db.add(u)
            db.flush()
            db.add(
                StudentProfile(
                    institution_id=u.institution_id, user_id=u.id, graduation_year=2027, academic_year=4, semester=7, section=section
                )
            )
            ids[roll] = u.id
        teacher = User(
            institution_id=dep.institution_id,
            department_id=dep.id,
            roll_no="TEACHER",
            email="teacher@alpha.example.com",
            full_name="Synthetic Subject Teacher",
            role="faculty",
            active=True,
            password_hash=password_hash(password),
        )
        db.add(teacher)
        db.flush()
        ids["TEACHER"] = teacher.id
        ids["department"] = dep.id
        db.commit()
    return ids


def preview(client, kind, text):
    return client.post(
        "/api/campus/imports/preview", data={"kind": kind}, files={"file": ("sheet.csv", text.encode(), "text/csv")}, headers=secure(client)
    )


def timetable_text(section="A", teacher="TEACHER", start="09:00", end="10:00", room="R101"):
    return (
        TIMETABLE_HEADER
        + f"\nCSE,2027,4,7,{section},Database Systems,{teacher},0,{start},{end},{room},{date.today() - timedelta(days=1)},{date.today() + timedelta(days=60)}\n"
    )


def test_campus_end_to_end_routing_and_private_attachment(setup):
    client, password, _, _ = setup
    ids = add_students(password)
    login(client, password, identifier="ADMIN")
    imported = preview(client, "timetable", timetable_text()).json()
    assert imported["valid_rows"] == 1 and imported["errors"] == []
    r = client.post(f"/api/campus/imports/{imported['id']}/confirm", headers=secure(client))
    assert r.status_code == 200, r.text
    assert client.post(f"/api/campus/imports/{imported['id']}/confirm", headers=secure(client)).json()["already_confirmed"]
    login(client, password, identifier="TEACHER")
    assert client.get("/api/students").status_code == 403
    assert client.get("/api/dashboard").status_code == 403
    body = {
        "title": "SQL assignment",
        "message": "Practice joins and explain your queries.",
        "kind": "assignment",
        "subject": "Database Systems",
        "audience": {"department_id": ids["department"], "graduation_year": 2027, "academic_year": 4, "semester": 7, "section": "A"},
    }
    count = client.post("/api/campus/posts/preview", json=body, headers=secure(client))
    assert count.status_code == 200 and count.json()["recipients"] == 1
    import json

    posted = client.post(
        "/api/campus/posts",
        data={"payload": json.dumps(body)},
        files={"file": ("assignment.txt", b"Write an INNER JOIN query.", "text/plain")},
        headers=secure(client),
    )
    assert posted.status_code == 200, posted.text
    post = posted.json()["id"]
    body["audience"]["section"] = "B"
    assert client.post("/api/campus/posts/preview", json=body, headers=secure(client)).status_code == 403
    login(client, password, identifier="S001")
    assert any(p["id"] == post for p in client.get("/api/campus/posts").json())
    assert len(client.get("/api/campus/timetable").json()) == 1
    assert client.get(f"/api/campus/posts/{post}/attachment").content == b"Write an INNER JOIN query."
    assert client.post(f"/api/campus/posts/{post}/acknowledge", headers=secure(client)).status_code == 200
    assert client.post(f"/api/campus/posts/{post}/acknowledge", headers=secure(client)).status_code == 200
    assert client.post("/api/campus/posts/preview", json=body, headers=secure(client)).status_code == 403
    login(client, password, identifier="S002")
    assert not client.get("/api/campus/posts").json()
    assert not client.get("/api/campus/timetable").json()
    assert client.get(f"/api/campus/posts/{post}/attachment").status_code == 404
    login(client, password, institution="beta", identifier="ADMIN")
    assert client.get(f"/api/campus/posts/{post}/attachment").status_code == 404
    assert client.post(f"/api/campus/imports/{imported['id']}/confirm", headers=secure(client)).status_code == 404
    login(client, password, identifier="TEACHER")
    assert client.get(f"/api/campus/posts/{post}/delivery").json() == {"delivered": 1, "acknowledged": 1}
    assert client.delete(f"/api/campus/posts/{post}", headers=secure(client)).status_code == 200
    login(client, password, identifier="S001")
    assert client.get(f"/api/campus/posts/{post}/attachment").status_code == 404


def test_cohort_import_is_atomic_and_retains_timetable_versions(setup):
    client, password, _, _ = setup
    add_students(password)
    login(client, password, identifier="ADMIN")
    bad = preview(client, "cohorts", COHORT_HEADER + "\nS001,CSE,2027,4,7,B\nUNKNOWN,CSE,2027,4,7,B\n").json()
    assert len(bad["errors"]) == 1
    assert client.post(f"/api/campus/imports/{bad['id']}/confirm", headers=secure(client)).status_code == 422
    with SessionLocal() as db:
        assert db.scalar(select(StudentProfile.section).join(User, User.id == StudentProfile.user_id).where(User.roll_no == "S001")) == "A"
    good = preview(client, "cohorts", COHORT_HEADER + "\nS001,CSE,2027,4,7,B\n").json()
    assert client.post(f"/api/campus/imports/{good['id']}/confirm", headers=secure(client)).status_code == 200
    for text in [timetable_text("B"), timetable_text("B", start="11:00", end="12:00")]:
        job = preview(client, "timetable", text).json()
        assert not job["errors"], job
        assert client.post(f"/api/campus/imports/{job['id']}/confirm", headers=secure(client)).status_code == 200
    with SessionLocal() as db:
        slots = list(db.scalars(select(TeachingSlot)))
        assert len(slots) == 2 and sum(s.active for s in slots) == 1
    login(client, password, identifier="S001")
    assert client.get("/api/campus/timetable").json()[0]["starts"] == "11:00"


def test_timetable_conflicts_and_publishing_authority(setup):
    client, password, _, ids = setup
    own = add_students(password)
    login(client, password, identifier="ADMIN")
    text = timetable_text() + timetable_text("B").split("\n", 1)[1]
    bad = preview(client, "timetable", text).json()
    assert bad["errors"] and "Conflicting" in bad["errors"][0]["error"]
    assert (
        client.put("/api/campus/authorities", json={"user_id": own["S001"], "office": "principal"}, headers=secure(client)).status_code
        == 422
    )
    assert (
        client.put(
            "/api/campus/authorities", json={"user_id": ids[("beta", "HOD")], "office": "principal"}, headers=secure(client)
        ).status_code
        == 404
    )
    login(client, password, identifier="HOD")
    assert (
        client.post(
            "/api/campus/posts/preview", json={"title": "Department notice", "message": "Hello"}, headers=secure(client)
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/api/campus/posts/preview",
            json={"title": "Department notice", "message": "Hello", "audience": {"department_id": own["department"]}},
            headers=secure(client),
        ).json()["recipients"]
        == 2
    )
    assert client.post("/api/campus/posts/preview", json={"title": "Missing CSRF", "message": "Hello"}).status_code == 403


def workbook(rows):
    stream = io.BytesIO()
    xml = '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>'
    for i, row in enumerate(rows, 1):
        xml += (
            f'<row r="{i}">'
            + "".join(f'<c r="{chr(65 + j)}{i}" t="inlineStr"><is><t>{escape(str(value))}</t></is></c>' for j, value in enumerate(row))
            + "</row>"
        )
    xml += "</sheetData></worksheet>"
    with zipfile.ZipFile(stream, "w") as z:
        z.writestr("xl/worksheets/sheet1.xml", xml)
    return stream.getvalue()


def test_xlsx_values_and_formula_rejection():
    rows = sheet_rows("students.xlsx", workbook([["roll_no", "section"], ["S001", "A"]]))
    assert rows == [{"roll_no": "S001", "section": "A"}]
    raw = workbook([["roll_no"], ["S001"]])
    source = zipfile.ZipFile(io.BytesIO(raw))
    target = io.BytesIO()
    with zipfile.ZipFile(target, "w") as z:
        z.writestr(
            "xl/worksheets/sheet1.xml", source.read("xl/worksheets/sheet1.xml").replace(b"<is><t>S001</t></is>", b"<f>1+1</f><v>2</v>")
        )
    import pytest

    with pytest.raises(ValueError, match="formulas"):
        sheet_rows("formula.xlsx", target.getvalue())


def test_bulk_onboarding_preserves_optional_academic_fields(setup):
    from app.importer import build_preview, process_import

    client, password, _, ids = setup
    own = add_students(password)
    with SessionLocal() as db:
        admin = db.get(User, ids[("alpha", "ADMIN")])
        text = b"roll_no,full_name,email,department,graduation_year,cgpa,active_backlogs,phone\nS001,Synthetic Student,S001@alpha.example.com,CSE,2027,8,0,\n"
        job = build_preview(db, admin, "update.csv", text, {}, "update")
        job_id = job.id
    process_import(job_id)
    with SessionLocal() as db:
        profile = db.scalar(select(StudentProfile).where(StudentProfile.user_id == own["S001"]))
        assert profile.section == "A" and profile.semester == 7 and profile.academic_year == 4


def test_leadership_targeted_notice_and_revoked_grant(setup):
    import json

    client, password, _, ids = setup
    students = add_students(password)
    with SessionLocal() as db:
        tenant = db.get(User, ids[("alpha", "ADMIN")]).institution_id
        officer = User(
            institution_id=tenant,
            roll_no="PRINCIPAL",
            full_name="Synthetic Principal",
            email="principal@alpha.example.com",
            role="campus_staff",
            active=True,
            password_hash=password_hash(password),
        )
        db.add(officer)
        db.commit()
        officer_id = officer.id
    login(client, password, identifier="PRINCIPAL")
    assert client.get("/api/campus/context").json()["office"] is None
    assert (
        client.post(
            "/api/campus/posts/preview", json={"title": "Private notice", "message": "Please contact the office."}, headers=secure(client)
        ).status_code
        == 403
    )
    login(client, password, identifier="ADMIN")
    grant = client.put("/api/campus/authorities", json={"user_id": officer_id, "office": "principal"}, headers=secure(client))
    assert grant.status_code == 200
    login(client, password, identifier="PRINCIPAL")
    assert client.get("/api/students/" + students["S001"]).status_code == 403
    body = {"title": "Private office notice", "message": "Please contact the principal office.", "audience": {"student_roll_no": "S001"}}
    post = client.post("/api/campus/posts", data={"payload": json.dumps(body)}, headers=secure(client))
    assert post.status_code == 200 and post.json()["recipients"] == 1
    login(client, password, identifier="S002")
    assert not client.get("/api/campus/posts").json()
    login(client, password, identifier="S001")
    assert client.get("/api/campus/posts").json()[0]["office"] == "principal"
    login(client, password, identifier="ADMIN")
    assert client.delete(f"/api/campus/authorities/{grant.json()['id']}", headers=secure(client)).status_code == 200
    login(client, password, identifier="PRINCIPAL")
    assert client.post("/api/campus/posts/preview", json=body, headers=secure(client)).status_code == 403

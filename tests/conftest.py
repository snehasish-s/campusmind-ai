import os
import tempfile
from pathlib import Path
import secrets
import pytest

Path("data").mkdir(exist_ok=True)
TEST_ROOT = tempfile.TemporaryDirectory(prefix="campusmind-tests-", dir=Path("data").resolve(), ignore_cleanup_errors=True)
os.environ.update(
    DATABASE_URL="sqlite:///" + str(Path(TEST_ROOT.name) / "test.db"),
    STORAGE_ROOT=str(Path(TEST_ROOT.name) / "storage"),
    QUEUE_MODE="sync",
    RATE_LIMIT_BACKEND="memory",
    TESTING="true",
    DEPLOYMENT_MODE="local",
    APP_ORIGIN="http://localhost:3000",
    SECURE_COOKIES="false",
    AI_MODE="fallback",
    EMBEDDING_MODE="keyword",
    STORAGE_BACKEND="local",
    GRAPH_CHECKPOINT_URL="",
    OLLAMA_URL="http://localhost:11434",
    BOOTSTRAP_TOKEN="",
)
from fastapi.testclient import TestClient  # noqa: E402
from app.main import app  # noqa: E402
from app.db import Base, engine, SessionLocal  # noqa: E402
from app.models import Institution, Department, User, StaffRole  # noqa: E402
from app.security import password_hash, _buckets  # noqa: E402


@pytest.fixture
def setup(monkeypatch):
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    _buckets.clear()
    messages = []

    class Mailbox:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def send_message(self, message):
            messages.append(message)

    monkeypatch.setattr("app.invitations.smtplib.SMTP", Mailbox)
    password = secrets.token_urlsafe(20)
    identities = {}
    with SessionLocal() as db:
        for slug in ("alpha", "beta"):
            tenant = Institution(slug=slug, name=f"Synthetic {slug} Institute")
            db.add(tenant)
            db.flush()
            department = Department(institution_id=tenant.id, code="CSE", name="Computer Science")
            db.add(department)
            db.flush()
            for login, role in [("ADMIN", "institution_admin"), ("OFFICER", "placement_officer"), ("HOD", "hod")]:
                u = User(
                    institution_id=tenant.id,
                    roll_no=login,
                    email=f"{login.lower()}@{slug}.example.com",
                    full_name=f"Synthetic {login}",
                    role=role,
                    active=True,
                    password_hash=password_hash(password),
                    department_id=department.id if role == "hod" else None,
                )
                db.add(u)
                db.flush()
                db.add(StaffRole(institution_id=tenant.id, user_id=u.id, role=role, department_id=u.department_id))
                identities[(slug, login)] = u.id
        db.commit()
    client = TestClient(app)
    yield client, password, messages, identities
    client.close()


def login(client, password, institution="alpha", identifier="OFFICER"):
    response = client.post("/api/auth/login", json={"institution": institution, "identifier": identifier, "password": password})
    assert response.status_code == 200, response.text
    return response.json()


def secure(client):
    return {"X-CSRF-Token": client.cookies.get("cm_csrf")}

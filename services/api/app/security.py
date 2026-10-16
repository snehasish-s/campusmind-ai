import hashlib
import secrets
import time
from collections import defaultdict
from datetime import timedelta
from threading import Lock
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, InvalidHashError
from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session
from redis import Redis
from redis.exceptions import RedisError
from .config import settings
from .db import get_db
from .models import AuthSession, User, AuditLog, StudentProfile, now

hasher = PasswordHasher()
_dummy_hash = hasher.hash(secrets.token_urlsafe(32))
_buckets = defaultdict(list)
_lock = Lock()
MANAGERS = {"platform_admin", "institution_admin", "placement_officer"}
ADMINS = {"platform_admin", "institution_admin"}


def csv_safe(value):
    """Prevent spreadsheet formula interpretation, including whitespace prefixes."""
    if isinstance(value, str) and (value.lstrip().startswith(("=", "+", "-", "@")) or value.startswith(("\t", "\r", "\n"))):
        return "'" + value
    return value


def digest(token: str):
    return hashlib.sha256(token.encode()).hexdigest()


def password_hash(password: str):
    if len(password) < 12 or len(password) > 128:
        raise HTTPException(422, "Use a password between 12 and 128 characters.")
    return hasher.hash(password)


def verify_password(stored, password):
    try:
        return hasher.verify(stored or _dummy_hash, password)
    except (VerificationError, InvalidHashError):
        return False


def rate_limit(key: str, limit: int = 10, seconds: int = 60):
    key = "campusmind:rate:" + digest(key)
    if settings().rate_limit_backend == "redis":
        try:
            client = Redis.from_url(settings().redis_url)
            count = client.eval(
                "local n=redis.call('INCR',KEYS[1]); if n==1 then redis.call('EXPIRE',KEYS[1],ARGV[1]) end; return n", 1, key, seconds
            )
        except RedisError:
            raise HTTPException(503, "Authentication service is temporarily unavailable.")
    elif settings().rate_limit_backend == "database":
        from .db import SessionLocal
        from .models import RateLimitBucket
        from sqlalchemy.dialects.postgresql import insert as pg_insert
        from sqlalchemy.dialects.sqlite import insert as sqlite_insert
        from sqlalchemy import case

        with SessionLocal() as limiter_db:
            insert = pg_insert if limiter_db.bind.dialect.name == "postgresql" else sqlite_insert
            current = now()
            statement = insert(RateLimitBucket).values(key=key, count=1, expires_at=current + timedelta(seconds=seconds))
            statement = statement.on_conflict_do_update(
                index_elements=["key"],
                set_={
                    "count": case((RateLimitBucket.expires_at <= current, 1), else_=RateLimitBucket.count + 1),
                    "expires_at": case(
                        (RateLimitBucket.expires_at <= current, current + timedelta(seconds=seconds)), else_=RateLimitBucket.expires_at
                    ),
                },
            ).returning(RateLimitBucket.count)
            count = limiter_db.scalar(statement)
            limiter_db.commit()
    else:
        with _lock:
            current = time.monotonic()
            _buckets[key] = [t for t in _buckets[key] if current - t < seconds]
            _buckets[key].append(current)
            count = len(_buckets[key])
    if count > limit:
        raise HTTPException(429, "Too many attempts. Please try again later.", headers={"Retry-After": str(seconds)})


def placement_access(db, user):
    """B.Tech PlacementOS admission uses institution-managed academic year, never batch guesses."""
    if user.role != "student":
        return {"allowed": user.role in MANAGERS | {"hod"}, "academic_year": None, "reason": "staff_role"}
    profile = db.scalar(
        select(StudentProfile).where(StudentProfile.user_id == user.id, StudentProfile.institution_id == user.institution_id)
    )
    year = profile.academic_year if profile else None
    return {
        "allowed": year in {3, 4},
        "academic_year": year,
        "reason": "eligible_year" if year in {3, 4} else "academic_year_unassigned" if year is None else "third_or_final_year_required",
    }


def current_user(request: Request, db: Session = Depends(get_db)):
    token = request.cookies.get("cm_session", "")
    auth = db.scalar(select(AuthSession).where(AuthSession.token_hash == digest(token), AuthSession.expires_at > now()))
    if not auth:
        raise HTTPException(401, "Please sign in.")
    user = db.get(User, auth.user_id)
    if not user or not user.active or user.institution_id != auth.institution_id:
        raise HTTPException(401, "Please sign in.")
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        csrf = request.headers.get("x-csrf-token", "")
        if not csrf or not secrets.compare_digest(auth.csrf_hash, digest(csrf)):
            raise HTTPException(403, "Invalid security token. Refresh and try again.")
    if user.role in {"faculty", "campus_staff"} and not (
        request.url.path.startswith("/api/campus/")
        or request.url.path.startswith("/api/auth/")
        or (request.method == "GET" and request.url.path in {"/api/departments", "/api/notifications"})
    ):
        raise HTTPException(403, "This account has campus communication access only.")
    campus_student_paths = {
        "/api/profile",
        "/api/departments",
        "/api/notifications",
        "/api/privacy/export",
        "/api/privacy/deletion-request",
    }
    if (
        user.role == "student"
        and not (
            request.url.path.startswith("/api/campus/")
            or request.url.path.startswith("/api/auth/")
            or request.url.path in campus_student_paths
        )
        and not placement_access(db, user)["allowed"]
    ):
        raise HTTPException(
            403,
            "PlacementOS is available to third-year and final-year students. Contact your institution if your academic year needs updating.",
        )
    request.state.auth = auth
    return user


def require(user, roles):
    if user.role not in roles:
        raise HTTPException(403, "You do not have permission for this action.")
    if user.role == "hod" and not user.department_id:
        raise HTTPException(403, "A coordinator needs an assigned department for this action.")


def scoped(db, model, user, record_id):
    record = db.scalar(select(model).where(model.id == record_id, model.institution_id == user.institution_id))
    if not record:
        raise HTTPException(404, "Record not found.")
    return record


def student_access(db, actor, student_id):
    target = scoped(db, User, actor, student_id)
    if target.role != "student":
        raise HTTPException(404, "Student not found.")
    if actor.id != target.id:
        require(actor, MANAGERS | {"hod"})
        if actor.role == "hod" and (not actor.department_id or actor.department_id != target.department_id):
            raise HTTPException(404, "Student not found.")
    return target


def audit(db, actor, action, target=None, details=None):
    db.add(AuditLog(institution_id=actor.institution_id, actor_id=actor.id, action=action, target_id=target, details=details or {}))


def make_session(db, user, response):
    token, csrf = secrets.token_urlsafe(48), secrets.token_urlsafe(32)
    age = settings().session_hours * 3600
    db.add(
        AuthSession(
            institution_id=user.institution_id,
            user_id=user.id,
            token_hash=digest(token),
            csrf_hash=digest(csrf),
            expires_at=now() + timedelta(seconds=age),
        )
    )
    response.set_cookie("cm_session", token, httponly=True, secure=settings().secure_cookies, samesite="lax", max_age=age, path="/")
    response.set_cookie("cm_csrf", csrf, httponly=False, secure=settings().secure_cookies, samesite="lax", max_age=age, path="/")

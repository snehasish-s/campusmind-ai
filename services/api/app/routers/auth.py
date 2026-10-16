from fastapi import APIRouter, Depends, Request, Response, HTTPException
from sqlalchemy import select, or_, delete, update
from sqlalchemy.orm import Session
from ..db import get_db
from ..models import User, Institution, Invitation, AuthSession, now
from ..schemas import Login, Activate, ResetRequest
from ..security import (
    current_user,
    placement_access,
    rate_limit,
    verify_password,
    make_session,
    password_hash,
    digest,
    audit,
    require,
    scoped,
    MANAGERS,
    ADMINS,
)
from ..invitations import issue_invitation

router = APIRouter(prefix="/auth", tags=["Authentication"])


def user_view(db, user):
    institution = db.get(Institution, user.institution_id)
    return {
        "id": user.id,
        "full_name": user.full_name,
        "email": user.email,
        "roll_no": user.roll_no,
        "role": user.role,
        "department_id": user.department_id,
        "placement_access": placement_access(db, user),
        "institution": {
            "id": institution.id,
            "name": institution.name,
            "slug": institution.slug,
            "city": institution.city,
            "privacy_notice": institution.privacy_notice,
        },
    }


@router.post("/login")
def login(body: Login, request: Request, response: Response, db: Session = Depends(get_db)):
    rate_limit(f"login-ip:{request.client.host}", 30, 60)
    rate_limit(f"login:{body.institution}:{body.identifier.lower()}", 10, 300)
    institution = db.scalar(select(Institution).where(Institution.slug == body.institution.lower()))
    user = (
        db.scalar(
            select(User).where(
                User.institution_id == institution.id, or_(User.roll_no == body.identifier.upper(), User.email == body.identifier.lower())
            )
        )
        if institution
        else None
    )
    valid = verify_password(user.password_hash if user else None, body.password)
    if not user or not user.active or not valid:
        raise HTTPException(401, "Institution, login ID or password is incorrect.")
    make_session(db, user, response)
    audit(db, user, "auth.login")
    db.commit()
    return user_view(db, user)


@router.get("/me")
def me(user=Depends(current_user), db: Session = Depends(get_db)):
    return user_view(db, user)


@router.post("/logout")
def logout(request: Request, response: Response, user=Depends(current_user), db: Session = Depends(get_db)):
    db.delete(request.state.auth)
    db.commit()
    response.delete_cookie("cm_session", path="/")
    response.delete_cookie("cm_csrf", path="/")
    return {"ok": True}


@router.post("/activate")
def activate(body: Activate, request: Request, db: Session = Depends(get_db)):
    rate_limit(f"activate:{request.client.host}", 20, 300)
    invitation = db.scalar(select(Invitation).where(Invitation.token_hash == digest(body.token)).with_for_update())
    if not invitation or invitation.used_at or invitation.revoked_at or invitation.expires_at <= now():
        raise HTTPException(400, "This invitation is invalid or expired. Ask your institution for a new one.")
    if invitation.purpose == "activation" and not body.consent:
        raise HTTPException(422, "Please acknowledge the institution privacy notice.")
    user = db.get(User, invitation.user_id)
    encoded = password_hash(body.password)
    consumed = db.execute(
        update(Invitation)
        .where(Invitation.id == invitation.id, Invitation.used_at.is_(None), Invitation.revoked_at.is_(None), Invitation.expires_at > now())
        .values(used_at=now())
    )
    if consumed.rowcount != 1:
        raise HTTPException(400, "This invitation has already been used.")
    user.password_hash, user.active = encoded, True
    if body.consent:
        user.consent_at = now()
    db.execute(delete(AuthSession).where(AuthSession.user_id == user.id))
    db.execute(
        update(Invitation)
        .where(Invitation.user_id == user.id, Invitation.id != invitation.id, Invitation.used_at.is_(None))
        .values(revoked_at=now())
    )
    audit(db, user, f"auth.{invitation.purpose}")
    from ..intelligence.events import track

    track(db, user, "account." + invitation.purpose, "Account activated" if invitation.purpose == "activation" else "Password reset")
    db.commit()
    return {"ok": True, "institution": db.get(Institution, user.institution_id).slug, "roll_no": user.roll_no}


@router.post("/password-reset")
def reset(body: ResetRequest, request: Request, db: Session = Depends(get_db)):
    rate_limit(f"reset:{request.client.host}", 5, 300)
    institution = db.scalar(select(Institution).where(Institution.slug == body.institution.lower()))
    if institution:
        user = db.scalar(
            select(User).where(
                User.institution_id == institution.id,
                User.active.is_(True),
                or_(User.email == body.identifier.lower(), User.roll_no == body.identifier.upper()),
            )
        )
        if user:
            issue_invitation(db, user, "reset")
            db.commit()
    return {
        "message": "If the account exists, reset instructions have been requested. Contact your institution administrator if email is unavailable."
    }


@router.post("/password-reset/{user_id}/distribute")
def manual_password_reset(user_id: str, actor=Depends(current_user), db: Session = Depends(get_db)):
    require(actor, ADMINS)
    target = scoped(db, User, actor, user_id)
    if not target.active:
        raise HTTPException(409, "Inactive accounts need an activation invitation.")
    rate_limit("manual-reset:" + target.id, 5, 300)
    invitation, link = issue_invitation(db, target, purpose="reset", send=False)
    audit(db, actor, "auth.reset_distribute", target.id)
    db.commit()
    return {"activation_url": link, "expires_at": invitation.expires_at, "purpose": "reset"}


@router.post("/invitations/{user_id}/{action}")
def invitation_action(user_id: str, action: str, actor=Depends(current_user), db: Session = Depends(get_db)):
    require(actor, MANAGERS)
    target = scoped(db, User, actor, user_id)
    if target.role != "student" and actor.role not in {"institution_admin", "platform_admin"}:
        raise HTTPException(403, "Only institution administrators can invite staff.")
    if target.active:
        raise HTTPException(409, "Active users should use password reset.")
    rate_limit(f"invite:{target.id}", 5, 300)
    if action == "revoke":
        db.execute(update(Invitation).where(Invitation.user_id == target.id, Invitation.used_at.is_(None)).values(revoked_at=now()))
        result = {"ok": True}
    elif action in {"resend", "distribute"}:
        invitation, link = issue_invitation(db, target, send=action == "resend")
        result = {"delivery_status": invitation.delivery_status, "expires_at": invitation.expires_at}
        if action == "distribute":
            result["activation_url"] = link
    else:
        raise HTTPException(404, "Action not found.")
    audit(db, actor, f"invitation.{action}", target.id)
    db.commit()
    return result

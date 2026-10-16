import secrets
import smtplib
from datetime import timedelta
from email.message import EmailMessage
from sqlalchemy import select
from .config import settings
from .models import Invitation, Institution, now
from .security import digest


def issue_invitation(db, user, purpose="activation", send=True):
    for old in db.scalars(
        select(Invitation).where(Invitation.user_id == user.id, Invitation.used_at.is_(None), Invitation.revoked_at.is_(None))
    ):
        old.revoked_at = now()
    token = secrets.token_urlsafe(48)
    invitation = Invitation(
        institution_id=user.institution_id,
        user_id=user.id,
        purpose=purpose,
        token_hash=digest(token),
        expires_at=now() + timedelta(hours=1 if purpose == "reset" else settings().invitation_hours),
    )
    db.add(invitation)
    db.flush()
    link = f"{settings().app_origin}/activate#token={token}"
    invitation.delivery_status = "manual" if not send else "pending"
    if send and not settings().smtp_host:
        invitation.delivery_status = "unavailable"
    elif send:
        institution = db.get(Institution, user.institution_id)
        message = EmailMessage()
        message["From"] = settings().mail_from
        message["To"] = user.email
        message["Subject"] = "CampusMind: reset your password" if purpose == "reset" else "Activate your CampusMind account"
        message.set_content(
            f"Hello {user.full_name},\n\nInstitution: {institution.name}\nInstitution code: {institution.slug}\nLogin ID: {user.roll_no}\n\nChoose your own password using this single-use link:\n{link}\n\nExpires: {invitation.expires_at.isoformat()} UTC.\nIf this was unexpected, contact your institution administrator."
        )
        try:
            with smtplib.SMTP(settings().smtp_host, settings().smtp_port, timeout=3) as smtp:
                if settings().smtp_starttls:
                    smtp.starttls()
                if settings().smtp_user:
                    smtp.login(settings().smtp_user, settings().smtp_password)
                smtp.send_message(message)
            invitation.delivery_status = "sent"
        except (OSError, smtplib.SMTPException):
            invitation.delivery_status = "failed"
    return invitation, link

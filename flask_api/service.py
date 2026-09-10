import secrets

from flask import current_app

from email_service import send_code_email, send_invitation_email
from extensions import db
from models import AccountInvitation, EmailVerificationCode, User
from security import utcnow


def generate_code(length=6):
    return "".join(secrets.choice("0123456789") for _ in range(length))


def send_otp_to_email(user: User, purpose: str, purpose_label: str):
    code = generate_code()
    expires = utcnow() + timedelta_minutes(current_app.config["OTP_TTL_MINUTES"])
    record = EmailVerificationCode(
        user_id=user.id,
        purpose=purpose,
        code=code,
        expires_at=expires,
        attempts=0,
    )
    db.session.add(record)
    db.session.commit()
    send_code_email(user.email, code, user.first_name, purpose_label)
    return record


def verify_last_code(user_id: str, purpose: str, submitted_code: str) -> tuple:
    latest = (
        EmailVerificationCode.query.filter_by(user_id=user_id, purpose=purpose)
        .order_by(EmailVerificationCode.created_at.desc())
        .first()
    )
    if not latest:
        return False, "Aucun code de vérification trouvé. Demandez un nouveau code."
    if latest.verified_at:
        return False, "Ce code a déjà été utilisé. Demandez un nouveau code."
    if _ensure_aware(latest.expires_at) < utcnow():
        return False, "Ce code a expiré. Cliquez sur « Renvoyer le code »."
    if latest.attempts >= current_app.config["OTP_MAX_ATTEMPTS"]:
        return False, "Trop de tentatives incorrectes. Cliquez sur « Renvoyer le code »."
    if submitted_code.strip() != latest.code:
        latest.attempts = latest.attempts + 1
        db.session.commit()
        return False, "Code incorrect. Vérifiez le dernier code reçu par e-mail."
    latest.verified_at = utcnow()
    db.session.commit()
    return True, "Code vérifié."


def create_invitation(user: User):
    token = secrets.token_urlsafe(32)
    expires = utcnow() + timedelta_hours(current_app.config["INVITATION_TTL_HOURS"])
    inv = AccountInvitation(user_id=user.id, token=token, expires_at=expires)
    db.session.add(inv)
    db.session.commit()
    return token


def send_invitation_for(user: User, org_name: str = None):
    token = create_invitation(user)
    link = f"{current_app.config['FRONTEND_URL']}/set-password?token={token}"
    send_invitation_email(user.email, user.first_name, link, org_name)
    return link


def timedelta_minutes(mins):
    from datetime import timedelta

    return timedelta(minutes=mins)


def _ensure_aware(dt):
    if dt is not None and dt.tzinfo is None:
        from datetime import timezone

        return dt.replace(tzinfo=timezone.utc)
    return dt


def timedelta_hours(hours):
    from datetime import timedelta

    return timedelta(hours=hours)


def validate_invitation_token(token: str):
    inv = AccountInvitation.query.filter_by(token=token).first()
    if not inv:
        return None, "Ce lien d'invitation est invalide."
    if inv.used_at:
        return None, "Ce lien d'invitation a déjà été utilisé."
    if _ensure_aware(inv.expires_at) < utcnow():
        return None, "Ce lien d'invitation a expiré (48h)."
    user = db.session.get(User, inv.user_id)
    if not user or user.account_status != "INVITED":
        return None, "Ce compte n'est plus en attente d'activation."
    return (inv, user), None


def consume_invitation(user: User, inv, password: str):
    user.password = secrets_hash_password(password)
    user.account_status = "ACTIVE"
    user.is_active = True
    user.email_verified = True
    user.email_verified_at = utcnow()
    inv.used_at = utcnow()
    db.session.commit()


def secrets_hash_password(password: str):
    from security import hash_password

    return hash_password(password)


def record_audit(action: str, actor=None, target_type: str = None, target_id: str = None, details: str = None, ip: str = None):
    from models import AuditLog
    entry = AuditLog(
        actor_id=actor.id if actor else None,
        actor_email=actor.email if actor else None,
        action=action,
        target_type=target_type,
        target_id=target_id,
        ip_address=ip,
        details=details,
    )
    db.session.add(entry)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
    return entry
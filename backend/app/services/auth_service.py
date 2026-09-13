"""
Service d'authentification et d'inscription.
Aligne sur le nouveau schéma DB (migration c5909ddd17aa) :
  - users : first_name, last_name, job_title, phone, email_verified, account_status
  - organizations : legal_id, country, city, phone, address, website, email, status
  - email_verification_codes : OTP 6 chiffres, TTL 10 min
"""
import random
import secrets
import string
from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload


from app.core.security import (
    create_password_token,
    decode_access_token,
    hash_password,
    verify_password,
)
from app.db.models.account_invitations import AccountInvitation
from app.db.models.email_verification_codes import EmailVerificationCode
from app.db.models.organizations import Organization
from app.db.models.users import User
from app.schemas.auth import ManagerRegisterRequest

# Nombre maximum de tentatives OTP avant blocage
OTP_MAX_ATTEMPTS = 5
# Durée de validité OTP en minutes
OTP_TTL_MINUTES = 10
# Durée de validité d'un lien d'invitation en heures
INVITATION_TTL_HOURS = 48


# ─────────────────────────────────────────────
# Helpers OTP
# ─────────────────────────────────────────────

def _generate_otp(length: int = 6) -> str:
    return "".join(random.choices(string.digits, k=length))


async def _create_otp(db: AsyncSession, user_id: UUID) -> str:
    """Invalide les anciens codes non-vérifiés et en crée un nouveau."""
    # On ne supprime pas les anciens pour garder l'audit ; on laisse expirer naturellement.
    code = _generate_otp()
    otp = EmailVerificationCode(
        user_id=user_id,
        code=code,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=OTP_TTL_MINUTES),
        attempts=0,
    )
    db.add(otp)
    await db.flush()
    return code


# ─────────────────────────────────────────────
# Login
# ─────────────────────────────────────────────

async def authenticate_user(db: AsyncSession, email: str, password: str) -> User | None:
    result = await db.execute(
        select(User)
        .options(selectinload(User.organization))
        .where(User.email == email)
    )
    user = result.scalar_one_or_none()

    if user is None or not user.is_active or user.password is None or user.account_status != "ACTIVE":
        return None
    if not verify_password(password, user.password):
        return None

    # Pour MANAGER et DRIVER : l'organisation doit exister et être approuvée
    if user.role in ("MANAGER", "DRIVER"):
        if user.organization_id is None:
            return None
        org_result = await db.execute(
            select(Organization).where(Organization.id == user.organization_id)
        )
        org = org_result.scalar_one_or_none()
        if org is None or org.status != "APPROVED":
            return None

    # Pour le MANAGER : l'email doit obligatoirement avoir été vérifié par OTP
    if user.role == "MANAGER":
        if not user.email_verified:
            return None

    return user


# ─────────────────────────────────────────────
# Inscription manager (self-service)
# ─────────────────────────────────────────────

async def register_manager(
    db: AsyncSession,
    payload: ManagerRegisterRequest,
) -> tuple[User, str]:
    """
    Crée l'organisation (status=PENDING) + le manager (email_verified=False,
    account_status=ACTIVE) puis génère un OTP.

    Retourne (user, otp_code) pour que l'appelant puisse envoyer l'email.
    """
    # Vérifier l'unicité de l'email
    existing_user = await db.execute(select(User).where(User.email == str(payload.manager.email)))
    if existing_user.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email address already exists.",
        )

    # 1. Créer l'organisation
    org = Organization(
        name=payload.organization.name,
        legal_id=payload.organization.legal_id,
        country=payload.organization.country,
        city=payload.organization.city,
        phone=payload.organization.phone,
        address=payload.organization.address,
        website=payload.organization.website,
        email=str(payload.organization.email),
        status="PENDING",
    )
    db.add(org)
    await db.flush()   # obtenir org.id sans commit

    # 2. Créer le manager
    has_pwd = bool(payload.manager.password)
    manager = User(
        organization_id=org.id,
        first_name=payload.manager.first_name,
        last_name=payload.manager.last_name,
        job_title=payload.manager.job_title,
        email=str(payload.manager.email),
        phone=payload.manager.phone,
        password=hash_password(payload.manager.password) if has_pwd else None,
        role="MANAGER",
        email_verified=False,
        account_status="ACTIVE" if has_pwd else "INVITED",
        is_active=True,
    )
    db.add(manager)
    await db.flush()   # obtenir manager.id

    # 3. Générer l'OTP
    otp_code = await _create_otp(db, manager.id)

    await db.commit()
    await db.refresh(manager)
    return manager, otp_code


async def complete_manager_registration(
    db: AsyncSession,
    password_token: str,
    password: str,
) -> User:
    """
    Valide le password_token, enregistre le mot de passe du manager,
    et active son compte (account_status='ACTIVE', is_active=True).
    """
    token_payload = decode_access_token(password_token)
    if not token_payload or token_payload.get("type") != "password":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired completion token.",
        )

    user_id_str = token_payload.get("sub")
    if not user_id_str:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid token.",
        )

    result = await db.execute(
        select(User)
        .options(selectinload(User.organization))
        .where(User.id == UUID(user_id_str))
    )
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Account not found.",
        )

    user.password = hash_password(password)
    user.account_status = "ACTIVE"
    user.is_active = True
    user.email_verified = True
    if not user.email_verified_at:
        user.email_verified_at = datetime.now(timezone.utc)

    await db.commit()

    # Recharger l'utilisateur avec son organisation chargée explicitement
    reloaded_result = await db.execute(
        select(User)
        .options(selectinload(User.organization))
        .where(User.id == user.id)
    )
    return reloaded_result.scalar_one()



# ─────────────────────────────────────────────
# Vérification OTP
# ─────────────────────────────────────────────

async def verify_otp(
    db: AsyncSession,
    user_id: UUID,
    code: str,
) -> tuple[bool, str, UUID | None]:
    """
    Vérifie le code OTP pour un utilisateur.

    Retourne (success: bool, message: str, organization_id: UUID | None).
    """
    # Récupérer le dernier code valide (non expiré, non encore vérifié)
    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(EmailVerificationCode)
        .where(
            EmailVerificationCode.user_id == user_id,
            EmailVerificationCode.verified_at.is_(None),
            EmailVerificationCode.expires_at > now,
        )
        .order_by(EmailVerificationCode.created_at.desc())
        .limit(1)
    )
    otp = result.scalar_one_or_none()

    if otp is None:
        return False, "Expired or invalid code. Please request a new one.", None

    otp.attempts += 1

    if otp.attempts > OTP_MAX_ATTEMPTS:
        await db.commit()
        return False, "Too many attempts. Please request a new code.", None

    if otp.code != code:
        await db.commit()
        return False, "Incorrect code.", None

    # Marquer le code comme vérifié
    otp.verified_at = now

    # Marquer l'utilisateur comme vérifié
    result2 = await db.execute(select(User).where(User.id == user_id))
    user = result2.scalar_one_or_none()
    if user is None:
        return False, "User not found.", None

    user.email_verified = True
    user.email_verified_at = now

    await db.commit()
    return True, "Email verified successfully.", user.organization_id


# ─────────────────────────────────────────────
# Renvoi OTP
# ─────────────────────────────────────────────

async def resend_otp(db: AsyncSession, user_id: UUID) -> tuple[str | None, str]:
    """
    Génère un nouveau code OTP.

    Retourne (otp_code | None, message).
    """
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if user is None:
        return None, "User not found."
    if user.email_verified:
        return None, "Email is already verified."

    otp_code = await _create_otp(db, user_id)
    await db.commit()
    return otp_code, "A new verification code has been sent."


# ─────────────────────────────────────────────
# Admin : création manuelle d'organisation
# ─────────────────────────────────────────────

async def create_organization(
    db: AsyncSession,
    name: str,
    legal_id: str,
    country: str,
    city: str,
    phone: str,
    address: str,
    email: str,
    website: str | None = None,
) -> Organization:
    org = Organization(
        name=name,
        legal_id=legal_id,
        country=country,
        city=city,
        phone=phone,
        address=address,
        email=email,
        website=website,
        status="APPROVED",      # créé directement par l'admin = approuvé
    )
    db.add(org)
    await db.commit()
    await db.refresh(org)
    return org


# ─────────────────────────────────────────────
# Admin : création manuelle d'un manager
# ─────────────────────────────────────────────

async def create_manager(
    db: AsyncSession,
    organization_id: UUID,
    first_name: str,
    last_name: str,
    email: str,
    password: str,
    job_title: str | None = None,
    phone: str | None = None,
) -> User:
    manager = User(
        organization_id=organization_id,
        first_name=first_name,
        last_name=last_name,
        job_title=job_title,
        email=email,
        phone=phone,
        password=hash_password(password),
        role="MANAGER",
        email_verified=True,        # créé par l'admin : pas besoin de vérification
        account_status="ACTIVE",
        is_active=True,
    )
    db.add(manager)
    await db.flush()
    await db.refresh(manager)
    return manager


# ─────────────────────────────────────────────
# Manager : création de drivers (invitation sécurisée)
# ─────────────────────────────────────────────

async def create_driver(
    db: AsyncSession,
    organization_id: UUID,
    first_name: str,
    last_name: str,
    email: str,
    phone: str | None = None,
) -> tuple[User, str]:
    """
    Crée le compte driver avec password=None, account_status='INVITED',
    génère un token d'invitation sécurisé valide 48h et le stocke dans account_invitations.
    Retourne (driver, token).
    """
    # Vérifier l'unicité de l'email
    existing_user = await db.execute(select(User).where(User.email == email))
    if existing_user.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email address already exists.",
        )

    # 1. Créer l'utilisateur avec password=None et statut INVITED
    driver = User(
        organization_id=organization_id,
        first_name=first_name,
        last_name=last_name,
        email=email,
        phone=phone,
        password=None,
        role="DRIVER",
        email_verified=False,
        account_status="INVITED",
        is_active=True,
    )
    db.add(driver)
    await db.flush()

    # 2. Générer le token d'invitation sécurisé
    token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=INVITATION_TTL_HOURS)

    invitation = AccountInvitation(
        user_id=driver.id,
        token=token,
        expires_at=expires_at,
    )
    db.add(invitation)
    await db.commit()
    await db.refresh(driver)

    return driver, token


# ─────────────────────────────────────────────
# Driver : validation de token et définition du mot de passe
# ─────────────────────────────────────────────

async def validate_invitation_token(
    db: AsyncSession,
    token: str,
) -> tuple[User, Organization | None]:
    """
    Vérifie qu'un token d'invitation est valide, non expiré et non encore utilisé.
    Retourne l'utilisateur et son organisation.
    """
    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(AccountInvitation).where(AccountInvitation.token == token)
    )
    invitation = result.scalar_one_or_none()

    if invitation is None or invitation.used_at is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This invitation link is invalid or has already been used.",
        )

    if invitation.expires_at <= now:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This invitation link has expired. Please contact your manager.",
        )

    user_result = await db.execute(select(User).where(User.id == invitation.user_id))
    user = user_result.scalar_one_or_none()

    if user is None or user.account_status != "INVITED":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Account not found or already activated.",
        )

    org = None
    if user.organization_id:
        org_res = await db.execute(
            select(Organization).where(Organization.id == user.organization_id)
        )
        org = org_res.scalar_one_or_none()

    return user, org


async def set_driver_password(
    db: AsyncSession,
    token: str,
    new_password: str,
) -> User:
    """
    Valide le token d'invitation, définit le mot de passe, active le compte
    (account_status='ACTIVE', email_verified=True) et marque l'invitation comme utilisée.
    """
    now = datetime.now(timezone.utc)

    # Récupérer l'invitation
    inv_res = await db.execute(
        select(AccountInvitation).where(AccountInvitation.token == token)
    )
    invitation = inv_res.scalar_one_or_none()

    if invitation is None or invitation.used_at is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This invitation link is invalid or has already been used.",
        )

    if invitation.expires_at <= now:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This invitation link has expired. Please contact your manager.",
        )

    user_result = await db.execute(select(User).where(User.id == invitation.user_id))
    user = user_result.scalar_one_or_none()

    if user is None or user.account_status != "INVITED":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Account not found or already activated.",
        )

    # Mettre à jour l'utilisateur et l'invitation
    user.password = hash_password(new_password)
    user.account_status = "ACTIVE"
    user.email_verified = True
    user.email_verified_at = now
    invitation.used_at = now

    await db.commit()
    await db.refresh(user)
    return user

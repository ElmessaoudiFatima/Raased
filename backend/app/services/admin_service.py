"""
Service de gestion administrative des organisations :
  - lister par statut
  - approuver (PENDING → APPROVED)
  - rejeter  (PENDING → REJECTED)
"""
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models.organization_documents import OrganizationDocument
from app.db.models.organizations import Organization
from app.db.models.users import User
from sqlalchemy import delete, select, func
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from app.db.models.audit_logs import AuditLog
from app.db.models.cargos import Cargo
from app.db.models.organizations import Organization
from app.db.models.users import User
from app.db.models.account_invitations import AccountInvitation
from app.services.audit import write_audit_log

async def list_organizations(
    db: AsyncSession,
    status: str | None = None,
) -> list[Organization]:
    """Retourne toutes les organisations, filtrées par statut si fourni."""
    stmt = select(Organization).order_by(Organization.created_at.desc())
    if status:
        stmt = stmt.where(Organization.status == status.upper())
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_organization_with_manager(
    db: AsyncSession,
    org_id: UUID,
) -> tuple[Organization, User | None] | None:
    """Retourne l'organisation (avec documents chargés) + son premier manager (rôle MANAGER)."""
    result = await db.execute(
        select(Organization)
        .options(selectinload(Organization.documents))
        .where(Organization.id == org_id)
    )
    org = result.scalar_one_or_none()
    if org is None:
        return None

    manager_result = await db.execute(
        select(User)
        .where(User.organization_id == org_id, User.role == "MANAGER")
        .limit(1)
    )
    manager = manager_result.scalar_one_or_none()
    return org, manager


async def get_document_by_id(
    db: AsyncSession,
    document_id: UUID,
) -> OrganizationDocument | None:
    """Récupère un document par son identifiant unique."""
    result = await db.execute(
        select(OrganizationDocument).where(OrganizationDocument.id == document_id)
    )
    return result.scalar_one_or_none()


async def approve_organization(
    db: AsyncSession,
    org_id: UUID,
    reviewed_by_id: UUID,
) -> Organization | None:
    """
    Passe l'organisation en APPROVED et active le compte du manager
    (account_status reste ACTIVE, déjà positionné à l'inscription).
    """
    result = await db.execute(
        select(Organization).where(Organization.id == org_id)
    )
    org = result.scalar_one_or_none()
    if org is None:
        return None

    if org.status != "PENDING":
        return org  # idempotent si déjà traité

    now = datetime.now(timezone.utc)
    org.status = "APPROVED"
    org.reviewed_by = reviewed_by_id
    org.reviewed_at = now
    org.rejection_reason = None

    await db.commit()
    await db.refresh(org)
    return org


async def reject_organization(
    db: AsyncSession,
    org_id: UUID,
    reviewed_by_id: UUID,
    rejection_reason: str,
) -> Organization | None:
    """
    Passe l'organisation en REJECTED et désactive le manager associé
    (is_active=False) pour bloquer toute connexion ultérieure.
    """
    result = await db.execute(
        select(Organization).where(Organization.id == org_id)
    )
    org = result.scalar_one_or_none()
    if org is None:
        return None

    if org.status != "PENDING":
        return org  # idempotent

    now = datetime.now(timezone.utc)
    org.status = "REJECTED"
    org.reviewed_by = reviewed_by_id
    org.reviewed_at = now
    org.rejection_reason = rejection_reason

    # Désactiver tous les managers de cette organisation
    managers = await db.execute(
        select(User).where(
            User.organization_id == org_id,
            User.role == "MANAGER",
        )
    )
    for manager in managers.scalars().all():
        manager.is_active = False
        manager.account_status = "DISABLED"

    await db.commit()
    await db.refresh(org)
    return org
# ─────────────────────────────────────────────
# Dashboard stats
# ─────────────────────────────────────────────

async def get_admin_stats(db: AsyncSession) -> dict:
    pending = await db.scalar(select(func.count(Organization.id)).where(Organization.status == "PENDING")) or 0
    approved = await db.scalar(select(func.count(Organization.id)).where(Organization.status == "APPROVED")) or 0
    rejected = await db.scalar(select(func.count(Organization.id)).where(Organization.status == "REJECTED")) or 0

    managers = await db.scalar(select(func.count(User.id)).where(User.role == "MANAGER")) or 0
    drivers = await db.scalar(select(func.count(User.id)).where(User.role == "DRIVER")) or 0
    admins = await db.scalar(select(func.count(User.id)).where(User.role == "ADMIN")) or 0

    cargos = await db.scalar(select(func.count(Cargo.id))) or 0
    in_transit = await db.scalar(select(func.count(Cargo.id)).where(Cargo.status == "IN_TRANSIT")) or 0

    country_res = await db.execute(
        select(Organization.country, func.count(Organization.id))
        .where(Organization.status == "APPROVED")
        .group_by(Organization.country)
    )
    mena_distribution = [{"country": c or "Unknown", "count": n} for c, n in country_res.all()]

    audit_res = await db.execute(
        select(AuditLog, User.email)
        .outerjoin(User, AuditLog.user_id == User.id)
        .order_by(AuditLog.created_at.desc())
        .limit(8)
    )
    recent_audits = [
        {
            "id": str(log.id),
            "action": log.action,
            "actor_email": actor_email,
            "details": f"{log.entity_type} · {log.result}",
            "created_at": log.created_at.isoformat() if log.created_at else None,
        }
        for log, actor_email in audit_res.all()
    ]

    return {
        "pending": pending,
        "approved": approved,
        "rejected": rejected,
        "total_organizations": pending + approved + rejected,
        "managers": managers,
        "drivers": drivers,
        "admins": admins,
        "total_users": managers + drivers + admins,
        "cargos": cargos,
        "in_transit": in_transit,
        "mena_distribution": mena_distribution,
        "recent_audits": recent_audits,
    }


# ─────────────────────────────────────────────
# Users
# ─────────────────────────────────────────────

async def list_all_users(db: AsyncSession) -> list[dict]:
    res = await db.execute(select(User).order_by(User.created_at.desc()))
    users = res.scalars().all()

    org_ids = {u.organization_id for u in users if u.organization_id}
    org_map = {}
    if org_ids:
        org_res = await db.execute(select(Organization).where(Organization.id.in_(org_ids)))
        org_map = {o.id: o for o in org_res.scalars().all()}

    return [
        {
            "id": str(u.id),
            "first_name": u.first_name,
            "last_name": u.last_name,
            "email": u.email,
            "phone": u.phone,
            "job_title": u.job_title,
            "role": u.role,
            "avatar_url": getattr(u, "avatar_url", None),
            "account_status": u.account_status,
            "is_active": u.is_active,
            "email_verified": u.email_verified,
            "created_at": u.created_at.isoformat() if u.created_at else None,
            "organization": (
                {
                    "id": str(org.id),
                    "name": org.name,
                    "city": org.city,
                    "country": org.country,
                    "status": org.status,
                }
                if (org := org_map.get(u.organization_id))
                else None
            ),
        }
        for u in users
    ]


async def update_user_status(db: AsyncSession, user_id: UUID, action: str, actor: User) -> User | None:
    if action not in ("enable", "disable"):
        raise ValueError("action must be 'enable' or 'disable'.")
    if user_id == actor.id:
        raise ValueError("You cannot change the status of your own account.")

    res = await db.execute(select(User).where(User.id == user_id))
    user = res.scalar_one_or_none()
    if not user:
        return None

    user.is_active = action == "enable"
    await db.commit()
    await db.refresh(user)

    await write_audit_log(
        db,
        organization_id=user.organization_id,
        user_id=actor.id,
        actor_type="admin",
        action=f"USER_{action.upper()}D",
        entity_type="user",
        entity_id=user.id,
        result="SUCCESS",
    )
    return user


async def delete_user(db: AsyncSession, user_id: UUID, actor: User) -> bool:
    if user_id == actor.id:
        raise ValueError("You cannot delete your own account.")

    res = await db.execute(select(User).where(User.id == user_id))
    user = res.scalar_one_or_none()
    if not user:
        return False

    await db.execute(delete(AccountInvitation).where(AccountInvitation.user_id == user_id))
    await db.delete(user)
    await db.commit()

    await write_audit_log(
        db,
        organization_id=None,
        user_id=actor.id,
        actor_type="admin",
        action="USER_DELETED",
        entity_type="user",
        entity_id=user_id,
        result="SUCCESS",
    )
    return True


# ─────────────────────────────────────────────
# Audit log
# ─────────────────────────────────────────────

async def list_audit_logs(db: AsyncSession, limit: int = 200) -> list[dict]:
    res = await db.execute(
        select(AuditLog, User.email)
        .outerjoin(User, AuditLog.user_id == User.id)
        .order_by(AuditLog.created_at.desc())
        .limit(limit)
    )
    return [
        {
            "id": str(log.id),
            "actor_id": str(log.user_id) if log.user_id else None,
            "actor_email": actor_email,
            "action": log.action,
            "target_type": log.entity_type,
            "target_id": str(log.entity_id) if log.entity_id else None,
            "ip_address": None,
            "details": f"{log.result}" + (f" · corr={log.correlation_id}" if log.correlation_id else ""),
            "created_at": log.created_at.isoformat() if log.created_at else None,
        }
        for log, actor_email in res.all()
    ]

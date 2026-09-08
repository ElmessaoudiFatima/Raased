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

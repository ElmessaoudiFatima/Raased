"""
Cargo service: CRUD operations scoped to a manager's organisation.
"""
import uuid
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.cargos import Cargo
from app.schemas.cargo import CargoCreate, CargoStatusUpdate, CargoUpdate

# Valid status transitions: what status can move to what
ALLOWED_TRANSITIONS = {
    "PENDING":    {"IN_TRANSIT", "CANCELLED"},
    "IN_TRANSIT": {"DELIVERED", "DELAYED", "CANCELLED"},
    "DELAYED":    {"IN_TRANSIT", "CANCELLED"},
    "DELIVERED":  {"ARCHIVED"},
    "CANCELLED":  set(),   # terminal
    "ARCHIVED":   set(),   # terminal
}


async def create_cargo(
    db: AsyncSession,
    organization_id: uuid.UUID,
    payload: CargoCreate,
) -> Cargo:
    """Create a new cargo entry for the manager's organisation."""
    cargo = Cargo(
        organization_id=organization_id,
        reference=payload.reference,
        type=payload.type,
        criticality=payload.criticality.upper(),
        status="PENDING",
        origin=payload.origin,
        destination=payload.destination,
        deadline=payload.deadline,
    )
    db.add(cargo)
    await db.commit()
    await db.refresh(cargo)
    return cargo


async def list_cargos(
    db: AsyncSession,
    organization_id: uuid.UUID,
    *,
    status_filter: Optional[str] = None,
) -> List[Cargo]:
    """List all cargos belonging to the manager's organisation, optionally filtered by status."""
    stmt = select(Cargo).where(Cargo.organization_id == organization_id)
    if status_filter:
        stmt = stmt.where(Cargo.status == status_filter.upper())
    stmt = stmt.order_by(Cargo.created_at.desc())
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_cargo(
    db: AsyncSession,
    cargo_id: uuid.UUID,
    organization_id: uuid.UUID,
) -> Optional[Cargo]:
    """Retrieve a single cargo that belongs to the manager's organisation. Returns None if not found."""
    stmt = select(Cargo).where(
        Cargo.id == cargo_id,
        Cargo.organization_id == organization_id,
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def update_cargo(
    db: AsyncSession,
    cargo: Cargo,
    payload: CargoUpdate,
) -> Cargo:
    """Update editable cargo fields (caller must own the cargo)."""
    if payload.reference is not None:
        cargo.reference = payload.reference
    if payload.type is not None:
        cargo.type = payload.type
    if payload.criticality is not None:
        cargo.criticality = payload.criticality.upper()
    if payload.origin is not None:
        cargo.origin = payload.origin
    if payload.destination is not None:
        cargo.destination = payload.destination
    if payload.deadline is not None:
        cargo.deadline = payload.deadline

    db.add(cargo)
    await db.commit()
    await db.refresh(cargo)
    return cargo


async def update_cargo_status(
    db: AsyncSession,
    cargo: Cargo,
    new_status: str,
) -> Cargo:
    """
    Update the status of a cargo, enforcing allowed transitions.
    Raises ValueError if the transition is invalid.
    """
    new_status = new_status.upper()
    current = cargo.status.upper()

    allowed = ALLOWED_TRANSITIONS.get(current, set())
    if new_status not in allowed:
        raise ValueError(
            f"Cannot transition cargo from '{current}' to '{new_status}'. "
            f"Allowed: {allowed or 'none (terminal state)'}."
        )

    cargo.status = new_status
    db.add(cargo)
    await db.commit()
    await db.refresh(cargo)
    return cargo


async def archive_cargo(
    db: AsyncSession,
    cargo: Cargo,
) -> Cargo:
    """
    Archive a delivered cargo.
    Shortcut for update_cargo_status(cargo, "ARCHIVED").
    Only DELIVERED cargos can be archived.
    """
    return await update_cargo_status(db, cargo, "ARCHIVED")

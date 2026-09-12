"""
Cargo service: CRUD operations scoped to a manager's organisation.
"""
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models.cargos import Cargo
from app.db.models.corridors import Corridor
from app.db.models.users import User
from app.db.models.trackers import Tracker
from app.db.models.cargo_trackers import CargoTracker
from app.services import tracker_service
from app.schemas.cargo import CargoCreate, CargoStatusUpdate, CargoUpdate

ALLOWED_TRANSITIONS = {
    "PENDING":    {"IN_TRANSIT", "CANCELLED"},
    "IN_TRANSIT": {"DELIVERED", "DELAYED", "CANCELLED"},
    "DELAYED":    {"IN_TRANSIT", "CANCELLED"},
    "DELIVERED":  {"ARCHIVED"},
    "CANCELLED":  set(),
    "ARCHIVED":   set(),
}


async def _generate_reference(db: AsyncSession, organization_id: uuid.UUID) -> str:
    """
    Génère une référence au format CARGO-<ANNÉE>-<NUMÉRO SÉQUENTIEL>,
    incrémentée par organisation et par année (ex: CARGO-2026-007).

    Note : pour un hackathon, un COUNT() suffit. En production, préférer
    une séquence PostgreSQL dédiée ou un verrou (SELECT ... FOR UPDATE)
    pour éviter une collision en cas de créations simultanées.
    """
    current_year = datetime.now(timezone.utc).year

    count = await db.scalar(
        select(func.count(Cargo.id)).where(
            Cargo.organization_id == organization_id,
            func.extract("year", Cargo.created_at) == current_year,
        )
    ) or 0

    next_number = count + 1
    return f"CARGO-{current_year}-{next_number:03d}"


async def create_cargo(
    db: AsyncSession,
    organization_id: uuid.UUID,
    payload: CargoCreate,
) -> Cargo:
    """
    Create a new cargo entry for the manager's organisation.
    Validates that the corridor belongs to the organisation (or is global),
    and auto-generates the reference. Also handles driver and tracker assignment if provided.
    """
    # Vérifie que le corridor existe et est accessible (org ou global)
    corridor_res = await db.execute(
        select(Corridor).where(
            Corridor.id == payload.corridor_id,
            (Corridor.organization_id == organization_id) | (Corridor.organization_id.is_(None)),
        )
    )
    corridor = corridor_res.scalar_one_or_none()
    if corridor is None:
        raise ValueError("Corridor introuvable ou non accessible pour cette organisation.")

    driver_user = None
    if payload.driver_id:
        driver_res = await db.execute(
            select(User).where(
                User.id == payload.driver_id,
                User.organization_id == organization_id,
            )
        )
        driver_user = driver_res.scalar_one_or_none()
        if not driver_user:
            raise ValueError("Chauffeur introuvable ou non associé à cette organisation.")

    reference = await _generate_reference(db, organization_id)

    cargo = Cargo(
        organization_id=organization_id,
        reference=reference,
        type=payload.type,
        criticality=payload.criticality.upper(),
        status="PENDING",
        corridor_id=payload.corridor_id,
        driver_id=driver_user.id if driver_user else None,
        driver=driver_user,
        deadline=payload.deadline,
    )
    db.add(cargo)
    await db.commit()

    if payload.tracker_id:
        tracker = await tracker_service.get_tracker(db, payload.tracker_id, organization_id)
        if tracker:
            await tracker_service.assign_tracker_to_cargo(db, tracker, cargo.id)

    refreshed_cargo = await get_cargo(db, cargo.id, organization_id)
    return refreshed_cargo or cargo


async def list_cargos(
    db: AsyncSession,
    organization_id: uuid.UUID,
    *,
    status_filter: Optional[str] = None,
) -> List[Cargo]:
    stmt = (
        select(Cargo)
        .options(
            selectinload(Cargo.driver),
            selectinload(Cargo.corridor),
            selectinload(Cargo.cargo_trackers).selectinload(CargoTracker.tracker),
        )
        .where(Cargo.organization_id == organization_id)
    )
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
    stmt = (
        select(Cargo)
        .options(
            selectinload(Cargo.driver),
            selectinload(Cargo.corridor),
            selectinload(Cargo.cargo_trackers).selectinload(CargoTracker.tracker),
        )
        .where(
            Cargo.id == cargo_id,
            Cargo.organization_id == organization_id,
        )
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def update_cargo(
    db: AsyncSession,
    cargo: Cargo,
    payload: CargoUpdate,
) -> Cargo:
    """Update editable cargo fields including driver and tracker assignment."""
    fields_set = payload.model_fields_set

    if "corridor_id" in fields_set and payload.corridor_id is not None:
        corridor_res = await db.execute(
            select(Corridor).where(
                Corridor.id == payload.corridor_id,
                (Corridor.organization_id == cargo.organization_id) | (Corridor.organization_id.is_(None)),
            )
        )
        if not corridor_res.scalar_one_or_none():
            raise ValueError("Corridor introuvable ou non accessible pour cette organisation.")
        cargo.corridor_id = payload.corridor_id

    if "type" in fields_set and payload.type is not None:
        cargo.type = payload.type
    if "criticality" in fields_set and payload.criticality is not None:
        cargo.criticality = payload.criticality.upper()
    if "deadline" in fields_set:
        cargo.deadline = payload.deadline

    # Driver assignment
    if "driver_id" in fields_set:
        if payload.driver_id is None:
            cargo.driver_id = None
            cargo.driver = None
        else:
            driver_res = await db.execute(
                select(User).where(
                    User.id == payload.driver_id,
                    User.organization_id == cargo.organization_id,
                )
            )
            driver_user = driver_res.scalar_one_or_none()
            if not driver_user:
                raise ValueError("Chauffeur introuvable ou non associé à cette organisation.")
            cargo.driver_id = payload.driver_id
            cargo.driver = driver_user

    # Tracker assignment
    if "tracker_id" in fields_set:
        current_active_ct_res = await db.execute(
            select(CargoTracker).where(
                CargoTracker.cargo_id == cargo.id,
                CargoTracker.unassigned_at.is_(None),
            )
        )
        current_active_cts = current_active_ct_res.scalars().all()

        if payload.tracker_id is None:
            for ct in current_active_cts:
                ct.unassigned_at = datetime.utcnow()
                trk = await db.get(Tracker, ct.tracker_id)
                if trk:
                    trk.status = "ACTIVE"
                    db.add(trk)
                db.add(ct)
        else:
            already_assigned = any(ct.tracker_id == payload.tracker_id for ct in current_active_cts)
            if not already_assigned:
                for ct in current_active_cts:
                    ct.unassigned_at = datetime.utcnow()
                    trk = await db.get(Tracker, ct.tracker_id)
                    if trk:
                        trk.status = "ACTIVE"
                        db.add(trk)
                    db.add(ct)

                tracker = await tracker_service.get_tracker(db, payload.tracker_id, cargo.organization_id)
                if not tracker:
                    raise ValueError("Tracker / véhicule introuvable.")
                await tracker_service.assign_tracker_to_cargo(db, tracker, cargo.id)

    db.add(cargo)
    await db.commit()

    refreshed = await get_cargo(db, cargo.id, cargo.organization_id)
    return refreshed or cargo



async def update_cargo_status(
    db: AsyncSession,
    cargo: Cargo,
    new_status: str,
) -> Cargo:
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


async def archive_cargo(db: AsyncSession, cargo: Cargo) -> Cargo:
    return await update_cargo_status(db, cargo, "ARCHIVED")
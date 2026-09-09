"""
Tracker service: register, list, assign/unassign, and locate trackers
scoped to a manager's organisation.
"""
import uuid
from datetime import datetime
from typing import List, Optional, Tuple

from geoalchemy2.functions import ST_X, ST_Y
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.trackers import Tracker
from app.db.models.cargo_trackers import CargoTracker
from app.db.models.tracker_locations import TrackerLocation
from app.schemas.tracker import TrackerCreate, TrackerUpdate


# ─────────────────────────────────────────────────────────────────────────────
# Register / Create
# ─────────────────────────────────────────────────────────────────────────────

async def create_tracker(
    db: AsyncSession,
    organization_id: uuid.UUID,
    payload: TrackerCreate,
) -> Tracker:
    """Register a new tracker device for the organisation."""
    # Check for duplicate device_id within the org
    existing = await db.execute(
        select(Tracker).where(Tracker.device_id == payload.device_id)
    )
    if existing.scalar_one_or_none():
        raise ValueError(f"A tracker with device_id '{payload.device_id}' already exists.")

    tracker = Tracker(
        organization_id=organization_id,
        device_id=payload.device_id,
        msisdn=payload.msisdn,
        status=payload.status.upper(),
    )
    db.add(tracker)
    await db.commit()
    await db.refresh(tracker)
    return tracker


# ─────────────────────────────────────────────────────────────────────────────
# List
# ─────────────────────────────────────────────────────────────────────────────

async def list_trackers(
    db: AsyncSession,
    organization_id: uuid.UUID,
    *,
    status_filter: Optional[str] = None,
) -> List[Tracker]:
    """List all trackers belonging to the organisation."""
    stmt = select(Tracker).where(Tracker.organization_id == organization_id)
    if status_filter:
        stmt = stmt.where(Tracker.status == status_filter.upper())
    stmt = stmt.order_by(Tracker.created_at.desc())
    result = await db.execute(stmt)
    return list(result.scalars().all())


# ─────────────────────────────────────────────────────────────────────────────
# Get single
# ─────────────────────────────────────────────────────────────────────────────

async def get_tracker(
    db: AsyncSession,
    tracker_id: uuid.UUID,
    organization_id: uuid.UUID,
) -> Optional[Tracker]:
    """Retrieve a single tracker owned by the organisation."""
    result = await db.execute(
        select(Tracker).where(
            Tracker.id == tracker_id,
            Tracker.organization_id == organization_id,
        )
    )
    return result.scalar_one_or_none()


# ─────────────────────────────────────────────────────────────────────────────
# Update
# ─────────────────────────────────────────────────────────────────────────────

async def update_tracker(
    db: AsyncSession,
    tracker: Tracker,
    payload: TrackerUpdate,
) -> Tracker:
    """Update editable tracker fields."""
    if payload.msisdn is not None:
        tracker.msisdn = payload.msisdn
    if payload.status is not None:
        tracker.status = payload.status.upper()
    db.add(tracker)
    await db.commit()
    await db.refresh(tracker)
    return tracker


# ─────────────────────────────────────────────────────────────────────────────
# Assign tracker to cargo
# ─────────────────────────────────────────────────────────────────────────────

async def assign_tracker_to_cargo(
    db: AsyncSession,
    tracker: Tracker,
    cargo_id: uuid.UUID,
) -> CargoTracker:
    """
    Assign a tracker to a cargo. The tracker must be ACTIVE and not already
    assigned to another active cargo.
    """
    # Check for existing active assignment for this tracker
    existing = await db.execute(
        select(CargoTracker).where(
            CargoTracker.tracker_id == tracker.id,
            CargoTracker.unassigned_at.is_(None),
        )
    )
    if existing.scalar_one_or_none():
        raise ValueError(
            "This tracker is already assigned to a cargo. "
            "Remove it first before reassigning."
        )

    assignment = CargoTracker(
        cargo_id=cargo_id,
        tracker_id=tracker.id,
        assigned_at=datetime.utcnow(),
    )
    tracker.status = "ASSIGNED"
    db.add(assignment)
    db.add(tracker)
    await db.commit()
    await db.refresh(assignment)
    return assignment


# ─────────────────────────────────────────────────────────────────────────────
# Remove tracker from cargo
# ─────────────────────────────────────────────────────────────────────────────

async def remove_tracker_from_cargo(
    db: AsyncSession,
    tracker: Tracker,
    cargo_id: uuid.UUID,
) -> CargoTracker:
    """
    Unassign a tracker from a specific cargo by setting unassigned_at.
    """
    result = await db.execute(
        select(CargoTracker).where(
            and_(
                CargoTracker.tracker_id == tracker.id,
                CargoTracker.cargo_id == cargo_id,
                CargoTracker.unassigned_at.is_(None),
            )
        )
    )
    assignment = result.scalar_one_or_none()
    if not assignment:
        raise ValueError("No active assignment found for this tracker/cargo combination.")

    assignment.unassigned_at = datetime.utcnow()
    tracker.status = "ACTIVE"
    db.add(assignment)
    db.add(tracker)
    await db.commit()
    await db.refresh(assignment)
    return assignment


# ─────────────────────────────────────────────────────────────────────────────
# Last known position
# ─────────────────────────────────────────────────────────────────────────────

async def get_last_position(
    db: AsyncSession,
    tracker_id: uuid.UUID,
) -> Optional[dict]:
    """
    Return the most recent TrackerLocation for a tracker as a dict with
    latitude, longitude, accuracy, source, and timestamp.
    Returns None if no locations have been recorded.
    """
    result = await db.execute(
        select(
            TrackerLocation.tracker_id,
            ST_Y(TrackerLocation.location).label("latitude"),
            ST_X(TrackerLocation.location).label("longitude"),
            TrackerLocation.accuracy,
            TrackerLocation.source,
            TrackerLocation.timestamp,
        )
        .where(TrackerLocation.tracker_id == tracker_id)
        .order_by(TrackerLocation.timestamp.desc())
        .limit(1)
    )
    row = result.mappings().first()
    if row is None:
        return None
    return dict(row)

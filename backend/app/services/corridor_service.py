"""
Corridor service: CRUD operations scoped to a manager's organisation.

Corridors with organization_id = None are global (admin-managed) and are
visible to all managers in read-only mode.
"""
import json
import uuid
from typing import List, Optional

from geoalchemy2.shape import from_shape
from shapely.geometry import LineString
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.corridors import Corridor
from app.schemas.corridor import CorridorCreate, CorridorUpdate


def _geometry_from_payload(coords: List[List[float]]):
    """Convert a list of [lon, lat] pairs into a PostGIS WKBElement."""
    line = LineString([(c[0], c[1]) for c in coords])
    return from_shape(line, srid=4326)


async def create_corridor(
    db: AsyncSession,
    organization_id: uuid.UUID,
    payload: CorridorCreate,
) -> Corridor:
    """Create a new corridor owned by the manager's organisation."""
    corridor = Corridor(
        organization_id=organization_id,
        name=payload.name,
        origin=payload.origin,
        destination=payload.destination,
        geometry=_geometry_from_payload(payload.geometry.coordinates),
        risk_level=payload.risk_level.upper(),
        is_active=True,
    )
    db.add(corridor)
    await db.commit()
    await db.refresh(corridor)
    return corridor


async def list_corridors(
    db: AsyncSession,
    organization_id: uuid.UUID,
    *,
    active_only: bool = False,
) -> List[Corridor]:
    """
    List corridors visible to a manager:
      - corridors owned by their organisation
      - global corridors (organization_id IS NULL)
    """
    stmt = select(Corridor).where(
        or_(
            Corridor.organization_id == organization_id,
            Corridor.organization_id.is_(None),
        )
    )
    if active_only:
        stmt = stmt.where(Corridor.is_active.is_(True))
    stmt = stmt.order_by(Corridor.created_at.desc())
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_corridor(
    db: AsyncSession,
    corridor_id: uuid.UUID,
    organization_id: uuid.UUID,
) -> Optional[Corridor]:
    """
    Retrieve a single corridor if it belongs to the organisation or is global.
    Returns None if not found / not accessible.
    """
    stmt = select(Corridor).where(
        Corridor.id == corridor_id,
        or_(
            Corridor.organization_id == organization_id,
            Corridor.organization_id.is_(None),
        ),
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def update_corridor(
    db: AsyncSession,
    corridor: Corridor,
    payload: CorridorUpdate,
) -> Corridor:
    """
    Update a corridor. Only the owning organisation can mutate its corridors
    (the caller is responsible for verifying ownership before calling this).
    """
    if payload.name is not None:
        corridor.name = payload.name
    if payload.origin is not None:
        corridor.origin = payload.origin
    if payload.destination is not None:
        corridor.destination = payload.destination
    if payload.geometry is not None:
        corridor.geometry = _geometry_from_payload(payload.geometry.coordinates)
    if payload.risk_level is not None:
        corridor.risk_level = payload.risk_level.upper()
    if payload.is_active is not None:
        corridor.is_active = payload.is_active

    db.add(corridor)
    await db.commit()
    await db.refresh(corridor)
    return corridor


async def delete_corridor(
    db: AsyncSession,
    corridor: Corridor,
) -> None:
    """
    Permanently delete a corridor.
    Only the owning organisation can delete its corridors
    (caller is responsible for verifying ownership).
    """
    await db.delete(corridor)
    await db.commit()

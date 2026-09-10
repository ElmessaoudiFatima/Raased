"""
Helpers géospatiaux partagés (PostGIS).

Actuellement : extraction d'un point (lat/lon) représentatif d'une
géométrie de corridor (LINESTRING), pour les modules qui ont besoin d'un
point unique (météo, etc.) plutôt que de toute la trajectoire.
"""
from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.corridors import Corridor


async def get_corridor_centroid(db: AsyncSession, corridor_id: UUID) -> tuple[float, float]:
    """
    Retourne (latitude, longitude) du centroïde du corridor.

    Note SRID 4326 : ST_X = longitude, ST_Y = latitude (ordre X/Y, pas
    lat/lon — source d'erreur classique avec PostGIS si on l'oublie).
    """
    stmt = select(
        func.ST_Y(func.ST_Centroid(Corridor.geometry)),
        func.ST_X(func.ST_Centroid(Corridor.geometry)),
    ).where(Corridor.id == corridor_id)

    result = await db.execute(stmt)
    row = result.one_or_none()
    if row is None:
        raise ValueError(f"Corridor {corridor_id} introuvable")

    latitude, longitude = row
    return float(latitude), float(longitude)

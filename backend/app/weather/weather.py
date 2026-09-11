"""
Intégration météo pour les corridors surveillés (Open-Meteo).

get_corridor_weather() récupère les conditions au centroïde du corridor,
avec un cache applicatif : un WeatherSnapshot persisté plus récent que
settings.WEATHER_CACHE_MINUTES est réutilisé tel quel plutôt que de
déclencher un nouvel appel Open-Meteo.

Persistance : chaque relevé (qu'il vienne du cache ou d'un appel frais)
correspond à une ligne unique dans weather_snapshots, pour que toute
décision qui s'appuie sur ces données reste traçable après coup — voir la
docstring de app/db/models/weather_snapshots.py.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models.weather_snapshots import WeatherSnapshot
from app.services.geospatial import get_corridor_centroid
from app.weather.client import WeatherAPIError, get_forecast

logger = logging.getLogger(__name__)
settings = get_settings()

_DEGRADED_CONDITION_CODES = {45, 48, 65, 67, 75, 82, 86, 95, 96, 99}


async def _get_fresh_snapshot(db: AsyncSession, corridor_id: UUID) -> WeatherSnapshot | None:
    """Retourne le relevé le plus récent pour ce corridor s'il est encore dans la fenêtre de cache."""
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=settings.WEATHER_CACHE_MINUTES)
    stmt = (
        select(WeatherSnapshot)
        .where(WeatherSnapshot.corridor_id == corridor_id, WeatherSnapshot.recorded_at >= cutoff)
        .order_by(WeatherSnapshot.recorded_at.desc())
        .limit(1)
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


def _snapshot_to_dict(snapshot: WeatherSnapshot, *, from_cache: bool) -> dict:
    return {
        "corridor_id": str(snapshot.corridor_id),
        "latitude": snapshot.latitude,
        "longitude": snapshot.longitude,
        "temperature_c": snapshot.temperature_c,
        "wind_speed_kmh": snapshot.wind_speed_kmh,
        "visibility_m": snapshot.visibility_m,
        "weather_code": snapshot.weather_code,
        "degraded_conditions": snapshot.degraded_conditions,
        "recorded_at": snapshot.recorded_at.isoformat(),
        "from_cache": from_cache,
    }


async def get_corridor_weather(db: AsyncSession, corridor_id: UUID) -> dict:
    """
    Récupère et interprète les conditions météo actuelles pour un corridor.

    Réutilise un relevé récent s'il existe (voir WEATHER_CACHE_MINUTES),
    sinon appelle Open-Meteo, persiste un nouveau WeatherSnapshot, et le
    retourne.
    """
    cached = await _get_fresh_snapshot(db, corridor_id)
    if cached is not None:
        return _snapshot_to_dict(cached, from_cache=True)

    latitude, longitude = await get_corridor_centroid(db, corridor_id)

    try:
        forecast = await get_forecast(latitude, longitude)
    except WeatherAPIError as exc:
        logger.error("Échec récupération météo pour corridor %s : %s", corridor_id, exc)
        raise

    current = forecast.get("current", {})
    weather_code = current.get("weather_code")

    snapshot = WeatherSnapshot(
        corridor_id=corridor_id,
        latitude=latitude,
        longitude=longitude,
        temperature_c=current.get("temperature_2m"),
        wind_speed_kmh=current.get("wind_speed_10m"),
        visibility_m=current.get("visibility"),
        weather_code=weather_code,
        degraded_conditions=weather_code in _DEGRADED_CONDITION_CODES,
        recorded_at=datetime.now(timezone.utc),
    )
    db.add(snapshot)
    await db.commit()
    await db.refresh(snapshot)

    return _snapshot_to_dict(snapshot, from_cache=False)

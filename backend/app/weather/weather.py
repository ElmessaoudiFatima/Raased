"""
Weather service integration using Open-Meteo for corridor tracking.
"""
from __future__ import annotations

import time
import uuid
from typing import Any, Dict, Optional

import httpx
from geoalchemy2.shape import to_shape
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.corridors import Corridor


class WeatherAPIError(Exception):
    """Raised when the Open-Meteo API fails or returns invalid response."""
    pass


# Cache mémoire simple : corridor_id -> (timestamp, data)
_WEATHER_CACHE: Dict[str, tuple[float, Dict[str, Any]]] = {}
_CACHE_TTL_SECONDS = 600.0  # 10 minutes


WMO_WEATHER_CODES: Dict[int, Dict[str, str]] = {
    0: {"description": "Ciel dégagé", "icon": "clear"},
    1: {"description": "Principalement dégagé", "icon": "mostly_clear"},
    2: {"description": "Partiellement nuageux", "icon": "partly_cloudy"},
    3: {"description": "Couvert", "icon": "overcast"},
    45: {"description": "Brouillard", "icon": "fog"},
    48: {"description": "Brouillard givrant", "icon": "fog"},
    51: {"description": "Bruine légère", "icon": "drizzle"},
    53: {"description": "Bruine modérée", "icon": "drizzle"},
    55: {"description": "Bruine dense", "icon": "drizzle"},
    61: {"description": "Pluie faible", "icon": "rain"},
    63: {"description": "Pluie modérée", "icon": "rain"},
    65: {"description": "Pluie forte", "icon": "heavy_rain"},
    71: {"description": "Chute de neige légère", "icon": "snow"},
    73: {"description": "Chute de neige modérée", "icon": "snow"},
    75: {"description": "Chute de neige forte", "icon": "heavy_snow"},
    80: {"description": "Averses faibles", "icon": "rain"},
    81: {"description": "Averses modérées", "icon": "rain"},
    82: {"description": "Averses violentes", "icon": "heavy_rain"},
    95: {"description": "Orage modéré", "icon": "thunderstorm"},
    96: {"description": "Orage avec grêle faible", "icon": "thunderstorm"},
    99: {"description": "Orage avec grêle forte", "icon": "thunderstorm"},
}


def _describe_wmo(code: Optional[int]) -> Dict[str, str]:
    if code is None or code not in WMO_WEATHER_CODES:
        return {"description": "Inconnu", "icon": "cloud"}
    return WMO_WEATHER_CODES[code]


async def _fetch_point_weather(client: httpx.AsyncClient, lat: float, lon: float) -> Dict[str, Any]:
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": round(lat, 4),
        "longitude": round(lon, 4),
        "current": "temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m,precipitation",
    }
    try:
        resp = await client.get(url, params=params, timeout=5.0)
        if resp.status_code != 200:
            raise WeatherAPIError(f"Open-Meteo HTTP {resp.status_code}: {resp.text[:100]}")
        data = resp.json()
        curr = data.get("current", {})
        wcode = curr.get("weather_code")
        info = _describe_wmo(wcode)
        return {
            "temperature_c": curr.get("temperature_2m"),
            "humidity_pct": curr.get("relative_humidity_2m"),
            "wind_speed_kmh": curr.get("wind_speed_10m"),
            "precipitation_mm": curr.get("precipitation"),
            "weather_code": wcode,
            "description": info["description"],
            "icon": info["icon"],
            "time": curr.get("time"),
        }
    except httpx.RequestError as exc:
        raise WeatherAPIError(f"Erreur réseau Open-Meteo : {exc}") from exc


async def get_corridor_weather(db: AsyncSession, corridor_id: uuid.UUID) -> Dict[str, Any]:
    """
    Récupère la météo actuelle pour un corridor aux points d'origine, milieu et destination.
    Utilise un cache en mémoire de 10 minutes.
    """
    cache_key = str(corridor_id)
    now = time.time()
    if cache_key in _WEATHER_CACHE:
        cached_time, cached_data = _WEATHER_CACHE[cache_key]
        if now - cached_time < _CACHE_TTL_SECONDS:
            return cached_data

    stmt = select(Corridor).where(Corridor.id == corridor_id)
    res = await db.execute(stmt)
    corridor = res.scalar_one_or_none()
    if not corridor:
        raise WeatherAPIError("Corridor introuvable en base.")

    # Extrait les coordonnées
    geom = to_shape(corridor.geometry)
    coords = list(geom.coords)
    if not coords:
        raise WeatherAPIError("Le corridor ne possède aucune coordonnée.")

    # coords sont des (lon, lat)
    orig_lon, orig_lat = coords[0]
    dest_lon, dest_lat = coords[-1]
    mid_lon, mid_lat = coords[len(coords) // 2]

    async with httpx.AsyncClient() as client:
        orig_w = await _fetch_point_weather(client, orig_lat, orig_lon)
        dest_w = await _fetch_point_weather(client, dest_lat, dest_lon)
        mid_w = await _fetch_point_weather(client, mid_lat, mid_lon)

    result = {
        "corridor_id": str(corridor.id),
        "corridor_name": corridor.name,
        "origin": {
            "name": corridor.origin,
            "latitude": orig_lat,
            "longitude": orig_lon,
            **orig_w,
        },
        "destination": {
            "name": corridor.destination,
            "latitude": dest_lat,
            "longitude": dest_lon,
            **dest_w,
        },
        "midpoint": {
            "name": "Mi-parcours",
            "latitude": mid_lat,
            "longitude": mid_lon,
            **mid_w,
        },
        "cached_at": now,
    }

    _WEATHER_CACHE[cache_key] = (now, result)
    return result

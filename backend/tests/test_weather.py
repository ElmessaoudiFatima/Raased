"""
Tests pour app.weather.weather (get_corridor_weather + cache).

La session DB, la géométrie du corridor, et l'appel Open-Meteo sont
mockés : ces tests valident la logique de cache et l'interprétation des
codes météo sans dépendre d'une vraie base PostGIS ni d'un accès réseau.
"""
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.db.models.weather_snapshots import WeatherSnapshot
from app.weather.client import WeatherAPIError
from app.weather.weather import get_corridor_weather


def _make_snapshot(corridor_id, *, recorded_at, weather_code=0, degraded=False):
    return WeatherSnapshot(
        id=uuid4(),
        corridor_id=corridor_id,
        latitude=31.5,
        longitude=-7.6,
        temperature_c=28.0,
        wind_speed_kmh=12.0,
        visibility_m=10000.0,
        weather_code=weather_code,
        degraded_conditions=degraded,
        recorded_at=recorded_at,
    )


def _mock_db(execute_return):
    db = AsyncMock()
    result = AsyncMock()
    result.scalar_one_or_none = lambda: execute_return
    db.execute = AsyncMock(return_value=result)
    db.add = lambda obj: None
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    return db


@pytest.mark.asyncio
async def test_returns_cached_snapshot_without_calling_api():
    corridor_id = uuid4()
    fresh = _make_snapshot(corridor_id, recorded_at=datetime.now(timezone.utc) - timedelta(minutes=5))
    db = _mock_db(fresh)

    with patch("app.weather.weather.get_forecast", new=AsyncMock()) as mock_forecast:
        result = await get_corridor_weather(db, corridor_id)

    mock_forecast.assert_not_awaited()
    assert result["from_cache"] is True
    assert result["temperature_c"] == 28.0


@pytest.mark.asyncio
async def test_calls_api_and_persists_when_no_fresh_snapshot():
    corridor_id = uuid4()
    db = _mock_db(None)

    with patch(
        "app.weather.weather.get_corridor_centroid",
        new=AsyncMock(return_value=(31.5, -7.6)),
    ), patch(
        "app.weather.weather.get_forecast",
        new=AsyncMock(return_value={
            "current": {
                "temperature_2m": 22.0,
                "wind_speed_10m": 15.0,
                "visibility": 8000.0,
                "weather_code": 0,
            }
        }),
    ):
        result = await get_corridor_weather(db, corridor_id)

    assert result["from_cache"] is False
    assert result["temperature_c"] == 22.0
    assert result["degraded_conditions"] is False
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_thunderstorm_code_marks_degraded_conditions():
    corridor_id = uuid4()
    db = _mock_db(None)

    with patch(
        "app.weather.weather.get_corridor_centroid",
        new=AsyncMock(return_value=(31.5, -7.6)),
    ), patch(
        "app.weather.weather.get_forecast",
        new=AsyncMock(return_value={"current": {"weather_code": 95}}),
    ):
        result = await get_corridor_weather(db, corridor_id)

    assert result["degraded_conditions"] is True
    assert result["weather_code"] == 95


@pytest.mark.asyncio
async def test_stale_snapshot_is_not_reused():
    corridor_id = uuid4()
    db = _mock_db(None)

    with patch(
        "app.weather.weather.get_corridor_centroid",
        new=AsyncMock(return_value=(31.5, -7.6)),
    ), patch(
        "app.weather.weather.get_forecast",
        new=AsyncMock(return_value={"current": {"weather_code": 0}}),
    ) as mock_forecast:
        await get_corridor_weather(db, corridor_id)

    mock_forecast.assert_awaited_once()


@pytest.mark.asyncio
async def test_weather_api_error_propagates_without_persisting():
    corridor_id = uuid4()
    db = _mock_db(None)

    with patch(
        "app.weather.weather.get_corridor_centroid",
        new=AsyncMock(return_value=(31.5, -7.6)),
    ), patch(
        "app.weather.weather.get_forecast",
        new=AsyncMock(side_effect=WeatherAPIError("boom")),
    ):
        with pytest.raises(WeatherAPIError):
            await get_corridor_weather(db, corridor_id)

    db.commit.assert_not_awaited()

"""
Tests pour la détection d'usurpation de position (app.services.spoofing).

La session DB et la création d'alerte sont mockées : ces tests valident la
logique de seuil et les cas limites (position manquante, tracker inconnu)
sans dépendre d'une vraie base PostGIS.
"""
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.db.models.tracker_locations import TrackerLocation
from app.db.models.trackers import Tracker
from app.services.spoofing import detect_position_spoofing


def _make_tracker():
    return Tracker(
        id=uuid4(), organization_id=uuid4(), device_id="dev-1",
        msisdn="+212600000000", status="active",
    )


def _make_location(source):
    return TrackerLocation(id=1, tracker_id=uuid4(), location="POINT(0 0)", source=source, timestamp=None)


def _result(value):
    """Mock du retour de db.execute() : un objet exposant scalar_one / scalar_one_or_none."""
    result = MagicMock()
    result.scalar_one_or_none = lambda: value
    result.scalar_one = lambda: value
    return result


@pytest.mark.asyncio
async def test_raises_for_unknown_tracker():
    db = AsyncMock()
    db.execute = AsyncMock(side_effect=[_result(None)])

    with pytest.raises(ValueError):
        await detect_position_spoofing(db, uuid4())


@pytest.mark.asyncio
async def test_returns_none_when_declared_location_missing():
    tracker = _make_tracker()
    network = _make_location("network")
    db = AsyncMock()
    db.execute = AsyncMock(side_effect=[_result(tracker), _result(None), _result(network)])

    result = await detect_position_spoofing(db, tracker.id)
    assert result is None


@pytest.mark.asyncio
async def test_returns_none_when_network_location_missing():
    tracker = _make_tracker()
    declared = _make_location("declared")
    db = AsyncMock()
    db.execute = AsyncMock(side_effect=[_result(tracker), _result(declared), _result(None)])

    result = await detect_position_spoofing(db, tracker.id)
    assert result is None


@pytest.mark.asyncio
async def test_no_alert_when_distance_within_threshold():
    tracker = _make_tracker()
    declared = _make_location("declared")
    network = _make_location("network")
    db = AsyncMock()
    # 4e appel = la requête de distance ; 2.0 km < seuil par défaut (5.0 km)
    db.execute = AsyncMock(side_effect=[_result(tracker), _result(declared), _result(network), _result(2.0)])

    with patch("app.services.spoofing.create_security_alert", new=AsyncMock()) as mock_create:
        result = await detect_position_spoofing(db, tracker.id)

    assert result is None
    mock_create.assert_not_awaited()


@pytest.mark.asyncio
async def test_alert_created_when_distance_exceeds_threshold():
    tracker = _make_tracker()
    declared = _make_location("declared")
    network = _make_location("network")
    db = AsyncMock()
    # 42.0 km > seuil par défaut (5.0 km)
    db.execute = AsyncMock(side_effect=[_result(tracker), _result(declared), _result(network), _result(42.0)])

    with patch(
        "app.services.spoofing.create_security_alert",
        new=AsyncMock(return_value="ALERT"),
    ) as mock_create:
        result = await detect_position_spoofing(db, tracker.id)

    assert result == "ALERT"
    mock_create.assert_awaited_once()
    _, kwargs = mock_create.call_args
    assert kwargs["check_type"] == "position_spoofing"
    assert kwargs["organization_id"] == tracker.organization_id
    assert kwargs["tracker_id"] == tracker.id

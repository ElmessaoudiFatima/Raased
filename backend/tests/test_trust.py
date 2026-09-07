"""
Tests pour les wrappers CAMARA Trust (verify_number, check_sim_swap, check_device_swap).

La session DB et l'appel CAMARA sont mockés : ces tests valident la logique
(status persisté, détection de swap, gestion d'erreur) sans dépendre d'une
vraie base Postgres ni d'un accès réseau.
"""
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.camara.client import CamaraAPIError
from app.camara.trust import check_device_swap, check_sim_swap, verify_number
from app.db.models.trackers import Tracker


def _make_tracker(msisdn="+212600000000"):
    return Tracker(
        id=uuid4(),
        organization_id=uuid4(),
        device_id="dev-001",
        msisdn=msisdn,
        status="active",
    )


def _mock_db_with_tracker(tracker):
    db = AsyncMock()
    result = AsyncMock()
    result.scalar_one_or_none = lambda: tracker
    db.execute = AsyncMock(return_value=result)
    db.add = lambda obj: None
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    return db


@pytest.mark.asyncio
async def test_verify_number_marks_verified():
    tracker = _make_tracker()
    db = _mock_db_with_tracker(tracker)

    with patch(
        "app.camara.trust.camara_post",
        new=AsyncMock(return_value={"devicePhoneNumberVerified": True, "requestId": "r1"}),
    ):
        check = await verify_number(db, tracker.id)

    assert check.status == "verified"
    assert check.check_type == "number_verification"
    assert check.tracker_id == tracker.id


@pytest.mark.asyncio
async def test_verify_number_marks_mismatch():
    tracker = _make_tracker()
    db = _mock_db_with_tracker(tracker)

    with patch(
        "app.camara.trust.camara_post",
        new=AsyncMock(return_value={"devicePhoneNumberVerified": False}),
    ):
        check = await verify_number(db, tracker.id)

    assert check.status == "mismatch"


@pytest.mark.asyncio
async def test_verify_number_raises_for_tracker_without_msisdn():
    tracker = _make_tracker(msisdn=None)
    db = _mock_db_with_tracker(tracker)

    with pytest.raises(ValueError):
        await verify_number(db, tracker.id)


@pytest.mark.asyncio
async def test_sim_swap_detected_triggers_alert_hook():
    tracker = _make_tracker()
    db = _mock_db_with_tracker(tracker)

    with patch(
        "app.camara.trust.camara_post",
        new=AsyncMock(return_value={"swapped": True, "requestId": "r2"}),
    ), patch(
        "app.camara.trust._trigger_security_alert", new=AsyncMock()
    ) as mock_alert:
        check = await check_sim_swap(db, tracker.id)

    assert check.status == "swap_detected"
    mock_alert.assert_awaited_once()


@pytest.mark.asyncio
async def test_sim_swap_clean_does_not_trigger_alert():
    tracker = _make_tracker()
    db = _mock_db_with_tracker(tracker)

    with patch(
        "app.camara.trust.camara_post",
        new=AsyncMock(return_value={"swapped": False}),
    ), patch(
        "app.camara.trust._trigger_security_alert", new=AsyncMock()
    ) as mock_alert:
        check = await check_sim_swap(db, tracker.id)

    assert check.status == "clean"
    mock_alert.assert_not_awaited()


@pytest.mark.asyncio
async def test_device_swap_camara_error_persists_error_status():
    tracker = _make_tracker()
    db = _mock_db_with_tracker(tracker)

    with patch(
        "app.camara.trust.camara_post",
        new=AsyncMock(side_effect=CamaraAPIError("boom")),
    ):
        check = await check_device_swap(db, tracker.id)

    assert check.status == "error"

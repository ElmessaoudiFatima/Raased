"""
Tests pour les wrappers CAMARA Trust (verify_number, check_sim_swap, check_device_swap).

La session DB et l'appel CAMARA sont mockés : ces tests valident la logique
(status persisté, détection de swap, gestion d'erreur, atomicité
check+alerte, écriture d'audit) sans dépendre d'une vraie base Postgres ni
d'un accès réseau.
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
    db.flush = AsyncMock()
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
async def test_verify_number_writes_audit_log():
    """La vérification (même sans alerte) doit journaliser un audit_log."""
    tracker = _make_tracker()
    db = _mock_db_with_tracker(tracker)

    with patch(
        "app.camara.trust.camara_post",
        new=AsyncMock(return_value={"devicePhoneNumberVerified": True}),
    ), patch(
        "app.camara.trust.write_audit_log", new=AsyncMock()
    ) as mock_audit:
        await verify_number(db, tracker.id)

    mock_audit.assert_awaited_once()
    _, kwargs = mock_audit.call_args
    assert kwargs["action"] == "security_check_performed"
    assert kwargs["organization_id"] == tracker.organization_id
    assert kwargs["commit"] is False


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
async def test_sim_swap_clean_commits_immediately():
    """
    Cas sans swap : un seul écrit (SecurityCheck + son audit) donc un seul
    commit, exécuté directement par _persist_check (pas de report).
    """
    tracker = _make_tracker()
    db = _mock_db_with_tracker(tracker)

    with patch(
        "app.camara.trust.camara_post",
        new=AsyncMock(return_value={"swapped": False}),
    ):
        await check_sim_swap(db, tracker.id)

    assert db.commit.await_count == 1


@pytest.mark.asyncio
async def test_sim_swap_detected_commits_exactly_once():
    """
    Test d'atomicité réel : quand un swap est détecté, on laisse le vrai
    chemin _trigger_security_alert -> create_security_alert s'exécuter
    (rien n'est mocké dans cette chaîne, seul CAMARA et db.execute le
    sont), et on vérifie qu'un SEUL commit a lieu au total pour
    SecurityCheck + AuditLog + SecurityAlert + AuditLog. Deux commits
    signifierait une fenêtre où le SecurityCheck pourrait être persisté
    sans sa SecurityAlert correspondante.
    """
    tracker = _make_tracker()
    db = _mock_db_with_tracker(tracker)

    with patch(
        "app.camara.trust.camara_post",
        new=AsyncMock(return_value={"swapped": True, "requestId": "r3"}),
    ):
        check = await check_sim_swap(db, tracker.id)

    assert check.status == "swap_detected"
    assert db.commit.await_count == 1
    assert db.flush.await_count == 2  # un flush dans _persist_check, un dans create_security_alert


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

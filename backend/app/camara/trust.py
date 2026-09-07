"""
Wrappers CAMARA Trust : Number Verification, SIM Swap, Device Swap.

Chaque fonction :
1. appelle l'API CAMARA correspondante via `app.camara.client`,
2. persiste systématiquement le résultat dans `SecurityCheck`
   (check_type = "number_verification" / "sim_swap" / "device_swap"),
3. pour sim_swap / device_swap, crée une `SecurityAlert` si un swap
   récent est détecté (table dédiée, distincte de `Alert` qui est
   réservée aux alertes de risque congestion — voir
   app/db/models/security_alerts.py pour la justification).
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.camara.client import CamaraAPIError, camara_post
from app.core.config import get_settings
from app.db.models.security_checks import SecurityCheck
from app.db.models.trackers import Tracker
from app.services.security_alerts import create_security_alert

logger = logging.getLogger(__name__)
settings = get_settings()


async def _get_tracker_or_raise(db: AsyncSession, tracker_id: UUID) -> Tracker:
    result = await db.execute(select(Tracker).where(Tracker.id == tracker_id))
    tracker = result.scalar_one_or_none()
    if tracker is None:
        raise ValueError(f"Tracker {tracker_id} introuvable")
    if not tracker.msisdn:
        raise ValueError(f"Tracker {tracker_id} n'a pas de msisdn renseigné")
    return tracker


async def _persist_check(
    db: AsyncSession,
    *,
    tracker_id: UUID,
    check_type: str,
    status_value: str,
    provider: str = "nokia-camara",
    request_id: str | None = None,
    details: dict | None = None,
) -> SecurityCheck:
    check = SecurityCheck(
        tracker_id=tracker_id,
        check_type=check_type,
        status=status_value,
        provider=provider,
        request_id=request_id,
        details=details,
        timestamp=datetime.now(timezone.utc),
    )
    db.add(check)
    await db.commit()
    await db.refresh(check)
    return check


async def _trigger_security_alert(
    db: AsyncSession,
    *,
    organization_id: UUID,
    tracker_id: UUID,
    security_check_id: UUID,
    check_type: str,
    details: dict,
    severity: str = "high",
):
    """Crée une SecurityAlert pour un événement de sécurité tracker (sim_swap, device_swap, ...)."""
    message = f"{check_type} détecté sur le tracker {tracker_id}"
    return await create_security_alert(
        db,
        organization_id=organization_id,
        tracker_id=tracker_id,
        check_type=check_type,
        message=message,
        severity=severity,
        security_check_id=security_check_id,
    )


async def verify_number(db: AsyncSession, tracker_id: UUID) -> SecurityCheck:
    """
    Vérifie que le MSISDN déclaré pour ce tracker correspond bien à la
    ligne active côté réseau (CAMARA Number Verification).
    """
    tracker = await _get_tracker_or_raise(db, tracker_id)

    try:
        response = await camara_post(
            "/number-verification/v0/verify",
            {"phoneNumber": tracker.msisdn},
        )
    except CamaraAPIError as exc:
        logger.error("Échec number_verification pour tracker %s : %s", tracker_id, exc)
        return await _persist_check(
            db, tracker_id=tracker_id, check_type="number_verification",
            status_value="error", details={"error": str(exc)},
        )

    verified = bool(response.get("devicePhoneNumberVerified"))
    return await _persist_check(
        db,
        tracker_id=tracker_id,
        check_type="number_verification",
        status_value="verified" if verified else "mismatch",
        request_id=response.get("requestId"),
        details=response,
    )


async def check_sim_swap(db: AsyncSession, tracker_id: UUID) -> SecurityCheck:
    """
    Interroge CAMARA SIM Swap pour savoir si la carte SIM associée à ce
    tracker a été échangée récemment. Crée une SecurityAlert si oui.
    """
    tracker = await _get_tracker_or_raise(db, tracker_id)

    try:
        response = await camara_post(
            "/sim-swap/v0/check",
            {"phoneNumber": tracker.msisdn, "maxAge": 240},
        )
    except CamaraAPIError as exc:
        logger.error("Échec sim_swap check pour tracker %s : %s", tracker_id, exc)
        return await _persist_check(
            db, tracker_id=tracker_id, check_type="sim_swap",
            status_value="error", details={"error": str(exc)},
        )

    swapped_recently = bool(response.get("swapped"))
    check = await _persist_check(
        db,
        tracker_id=tracker_id,
        check_type="sim_swap",
        status_value="swap_detected" if swapped_recently else "clean",
        request_id=response.get("requestId"),
        details=response,
    )

    if swapped_recently:
        await _trigger_security_alert(
            db,
            organization_id=tracker.organization_id,
            tracker_id=tracker_id,
            security_check_id=check.id,
            check_type="sim_swap",
            details=response,
        )

    return check


async def check_device_swap(db: AsyncSession, tracker_id: UUID) -> SecurityCheck:
    """
    Interroge CAMARA Device Swap pour savoir si l'appareil associé à ce
    tracker a changé récemment côté réseau. Crée une SecurityAlert si oui.
    """
    tracker = await _get_tracker_or_raise(db, tracker_id)

    try:
        response = await camara_post(
            "/device-swap/v0/check",
            {"phoneNumber": tracker.msisdn, "maxAge": 240},
        )
    except CamaraAPIError as exc:
        logger.error("Échec device_swap check pour tracker %s : %s", tracker_id, exc)
        return await _persist_check(
            db, tracker_id=tracker_id, check_type="device_swap",
            status_value="error", details={"error": str(exc)},
        )

    swapped_recently = bool(response.get("swapped"))
    check = await _persist_check(
        db,
        tracker_id=tracker_id,
        check_type="device_swap",
        status_value="swap_detected" if swapped_recently else "clean",
        request_id=response.get("requestId"),
        details=response,
    )

    if swapped_recently:
        await _trigger_security_alert(
            db,
            organization_id=tracker.organization_id,
            tracker_id=tracker_id,
            security_check_id=check.id,
            check_type="device_swap",
            details=response,
        )

    return check

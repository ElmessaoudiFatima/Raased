"""
Wrappers CAMARA Trust : Number Verification, SIM Swap, Device Swap.

Chaque fonction :
1. appelle l'API CAMARA correspondante via `app.camara.client`,
2. persiste systématiquement le résultat dans `SecurityCheck`
   (check_type = "number_verification" / "sim_swap" / "device_swap"),
   et journalise l'événement dans `audit_logs` (action="security_check_performed"),
3. pour sim_swap / device_swap, crée une `SecurityAlert` si un swap
   récent est détecté (table dédiée, distincte de `Alert` qui est
   réservée aux alertes de risque congestion — voir
   app/db/models/security_alerts.py pour la justification).

Garantie transactionnelle : quand un swap est détecté, le SecurityCheck,
la SecurityAlert et leurs deux entrées d'audit associées sont committés
ensemble en une seule transaction (via le paramètre commit=False propagé
jusqu'au commit final dans create_security_alert). Cela évite qu'un crash
entre les deux écritures ne laisse un SecurityCheck "swap_detected" orphelin,
sans SecurityAlert correspondante.
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
from app.services.audit import write_audit_log
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
    organization_id: UUID,
    check_type: str,
    status_value: str,
    provider: str = "nokia-camara",
    request_id: str | None = None,
    details: dict | None = None,
    commit: bool = True,
) -> SecurityCheck:
    """
    Persiste un SecurityCheck et journalise l'événement dans audit_logs.

    Si `commit=False`, l'appelant doit committer explicitement (utilisé
    quand un swap détecté va déclencher une SecurityAlert dans la même
    transaction, cf. check_sim_swap / check_device_swap ci-dessous).
    """
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
    await db.flush()

    await write_audit_log(
        db,
        organization_id=organization_id,
        actor_type="system",
        action="security_check_performed",
        entity_type="tracker",
        entity_id=tracker_id,
        result=status_value,
        payload={
            "check_type": check_type,
            "check_id": str(check.id),
            "provider": provider,
        },
        commit=False,
    )

    if commit:
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
    """
    Crée une SecurityAlert pour un événement de sécurité tracker. commit=True
    ici finalise la transaction englobant le SecurityCheck (committé en
    amont avec commit=False) et cette alerte.
    """
    message = f"{check_type} détecté sur le tracker {tracker_id}"
    return await create_security_alert(
        db,
        organization_id=organization_id,
        tracker_id=tracker_id,
        check_type=check_type,
        message=message,
        severity=severity,
        security_check_id=security_check_id,
        commit=True,
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
            db, tracker_id=tracker_id, organization_id=tracker.organization_id,
            check_type="number_verification",
            status_value="error", details={"error": str(exc)},
        )

    verified = bool(response.get("devicePhoneNumberVerified"))
    return await _persist_check(
        db,
        tracker_id=tracker_id,
        organization_id=tracker.organization_id,
        check_type="number_verification",
        status_value="verified" if verified else "mismatch",
        request_id=response.get("requestId"),
        details=response,
    )


async def check_sim_swap(db: AsyncSession, tracker_id: UUID) -> SecurityCheck:
    """
    Interroge CAMARA SIM Swap pour savoir si la carte SIM associée à ce
    tracker a été échangée récemment. Crée une SecurityAlert si oui, dans
    la même transaction que le SecurityCheck.
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
            db, tracker_id=tracker_id, organization_id=tracker.organization_id,
            check_type="sim_swap",
            status_value="error", details={"error": str(exc)},
        )

    swapped_recently = bool(response.get("swapped"))
    check = await _persist_check(
        db,
        tracker_id=tracker_id,
        organization_id=tracker.organization_id,
        check_type="sim_swap",
        status_value="swap_detected" if swapped_recently else "clean",
        request_id=response.get("requestId"),
        details=response,
        commit=not swapped_recently,
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
        await db.refresh(check)

    return check


async def check_device_swap(db: AsyncSession, tracker_id: UUID) -> SecurityCheck:
    """
    Interroge CAMARA Device Swap pour savoir si l'appareil associé à ce
    tracker a changé récemment côté réseau. Crée une SecurityAlert si oui,
    dans la même transaction que le SecurityCheck.
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
            db, tracker_id=tracker_id, organization_id=tracker.organization_id,
            check_type="device_swap",
            status_value="error", details={"error": str(exc)},
        )

    swapped_recently = bool(response.get("swapped"))
    check = await _persist_check(
        db,
        tracker_id=tracker_id,
        organization_id=tracker.organization_id,
        check_type="device_swap",
        status_value="swap_detected" if swapped_recently else "clean",
        request_id=response.get("requestId"),
        details=response,
        commit=not swapped_recently,
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
        await db.refresh(check)

    return check

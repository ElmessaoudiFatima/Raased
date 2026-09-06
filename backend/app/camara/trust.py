"""
Wrappers CAMARA Trust : Number Verification, SIM Swap, Device Swap.

Chaque fonction :
1. appelle l'API CAMARA correspondante via `app.camara.client`,
2. persiste systématiquement le résultat dans `SecurityCheck`
   (check_type = "number_verification" / "sim_swap" / "device_swap"),
3. pour sim_swap / device_swap, déclenche une alerte si un swap récent
   est détecté.

Note (bloquant, à trancher avant de considérer cette tâche terminée) :
`Alert.risk_assessment_id` et `Alert.cargo_id` sont NOT NULL, et
`RiskAssessment` lui-même requiert `corridor_id` + `congestion_event_id`.
Un événement de sécurité (SIM swap, device swap) n'est pas naturellement
rattaché à une évaluation de risque congestion : inventer un
`RiskAssessment` fictif pour satisfaire la contrainte polluerait cette
table avec des données sans sens métier.

En attendant ta décision, `_trigger_security_alert` NE crée PAS de ligne
dans `alerts` : elle journalise l'événement (logger applicatif) pour
qu'aucune détection ne soit perdue, et le détail reste consultable dans
`SecurityCheck.details`. Deux options pour débloquer :
  1) Ajouter une table dédiée, ex. `security_alerts` (organization_id,
     tracker_id, check_type, severity, message, status...), sans les
     colonnes congestion-spécifiques — recommandé.
  2) Rendre `Alert.risk_assessment_id` et `Alert.cargo_id` nullable pour
     que la même table serve aussi aux alertes purement sécurité.
Dis-moi laquelle tu préfères et j'ajoute la migration + le code de
création d'alerte correspondants.
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


async def _trigger_security_alert(tracker_id: UUID, check_type: str, details: dict) -> None:
    """
    Point d'entrée unique pour déclencher une alerte de sécurité distincte.
    Voir la note en tête de module : ne crée pas encore de ligne `Alert`
    tant que la question de schéma n'est pas tranchée.
    """
    logger.warning(
        "ALERTE SÉCURITÉ (non persistée, en attente de décision schéma) : "
        "tracker_id=%s check_type=%s details=%s",
        tracker_id, check_type, details,
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
    tracker a été échangée récemment.
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
        await _trigger_security_alert(tracker_id, "sim_swap", response)

    return check


async def check_device_swap(db: AsyncSession, tracker_id: UUID) -> SecurityCheck:
    """
    Interroge CAMARA Device Swap pour savoir si l'appareil associé à ce
    tracker a changé récemment côté réseau.
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
        await _trigger_security_alert(tracker_id, "device_swap", response)

    return check

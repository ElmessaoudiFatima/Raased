"""
Détection d'usurpation de position (spoofing).

Compare la dernière position déclarée par un tracker (TrackerLocation avec
source="declared") à sa dernière position résolue côté réseau
(source="network", obtenue via CAMARA Location Verification par le module
qui écrit ces lignes). Si l'écart dépasse `POSITION_SPOOFING_THRESHOLD_KM`,
une SecurityAlert est créée (check_type="position_spoofing").

La distance est calculée côté PostGIS (`ST_Distance` sur les géométries
castées en `geography`) pour obtenir une distance sphéroïdale correcte en
mètres, plutôt qu'une approximation euclidienne sur des degrés.
"""
from __future__ import annotations

import logging
from uuid import UUID

from geoalchemy2 import Geography
from sqlalchemy import cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models.security_alerts import SecurityAlert
from app.db.models.tracker_locations import TrackerLocation
from app.db.models.trackers import Tracker
from app.services.security_alerts import create_security_alert

logger = logging.getLogger(__name__)
settings = get_settings()


async def _latest_location(db: AsyncSession, tracker_id: UUID, source: str) -> TrackerLocation | None:
    stmt = (
        select(TrackerLocation)
        .where(TrackerLocation.tracker_id == tracker_id, TrackerLocation.source == source)
        .order_by(TrackerLocation.timestamp.desc())
        .limit(1)
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def _distance_km(db: AsyncSession, declared: TrackerLocation, network: TrackerLocation) -> float:
    """Distance sphéroïdale en kilomètres entre deux positions, via PostGIS."""
    stmt = select(
        func.ST_Distance(
            cast(declared.location, Geography),
            cast(network.location, Geography),
        )
        / 1000.0
    )
    result = await db.execute(stmt)
    return float(result.scalar_one())


async def detect_position_spoofing(db: AsyncSession, tracker_id: UUID) -> SecurityAlert | None:
    """
    Compare la position déclarée la plus récente à la position réseau la
    plus récente pour ce tracker.

    Retourne la SecurityAlert créée si l'écart dépasse le seuil configuré,
    sinon None (y compris quand l'une des deux positions manque encore
    pour effectuer la comparaison — ce n'est pas une erreur, juste un état
    transitoire tant que les deux sources n'ont pas encore rapporté).
    """
    result = await db.execute(select(Tracker).where(Tracker.id == tracker_id))
    tracker = result.scalar_one_or_none()
    if tracker is None:
        raise ValueError(f"Tracker {tracker_id} introuvable")

    declared = await _latest_location(db, tracker_id, "declared")
    network = await _latest_location(db, tracker_id, "network")

    if declared is None or network is None:
        logger.debug(
            "Comparaison spoofing impossible pour tracker %s : position(s) manquante(s) "
            "(declared=%s, network=%s)",
            tracker_id, declared is not None, network is not None,
        )
        return None

    distance_km = await _distance_km(db, declared, network)

    if distance_km <= settings.POSITION_SPOOFING_THRESHOLD_KM:
        return None

    message = (
        f"Écart de position détecté pour le tracker {tracker_id} : "
        f"{distance_km:.2f} km entre la position déclarée et la position réseau "
        f"(seuil configuré : {settings.POSITION_SPOOFING_THRESHOLD_KM} km)."
    )
    return await create_security_alert(
        db,
        organization_id=tracker.organization_id,
        tracker_id=tracker_id,
        check_type="position_spoofing",
        message=message,
        severity="high",
    )

"""
Création centralisée des `SecurityAlert`.

Point d'entrée unique utilisé par tous les détecteurs de sécurité
(app/camara/trust.py pour SIM/device swap, app/services/spoofing.py pour
l'usurpation de position, etc.), pour éviter que chaque détecteur ne
réimplémente sa propre logique de persistance.
"""
from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.security_alerts import SecurityAlert

logger = logging.getLogger(__name__)


async def create_security_alert(
    db: AsyncSession,
    *,
    organization_id: UUID,
    tracker_id: UUID,
    check_type: str,
    message: str,
    severity: str = "high",
    security_check_id: UUID | None = None,
    status: str = "open",
) -> SecurityAlert:
    """Crée et persiste une SecurityAlert."""
    alert = SecurityAlert(
        organization_id=organization_id,
        tracker_id=tracker_id,
        security_check_id=security_check_id,
        check_type=check_type,
        severity=severity,
        message=message,
        status=status,
    )
    db.add(alert)
    await db.commit()
    await db.refresh(alert)
    logger.warning(
        "SecurityAlert créée : id=%s tracker_id=%s check_type=%s",
        alert.id, tracker_id, check_type,
    )
    return alert

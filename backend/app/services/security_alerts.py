"""
Création centralisée des `SecurityAlert`.

Point d'entrée unique utilisé par tous les détecteurs de sécurité
(app/camara/trust.py pour SIM/device swap, app/services/spoofing.py pour
l'usurpation de position, etc.), pour éviter que chaque détecteur ne
réimplémente sa propre logique de persistance.

Chaque alerte créée écrit également une entrée dans `audit_logs` (via
`write_audit_log`), pour que le journal d'audit couvre systématiquement
tout événement de sécurité.

Le paramètre `commit` permet à un appelant de regrouper la création de
l'alerte avec d'autres écritures dans une seule transaction atomique.
"""
from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.security_alerts import SecurityAlert
from app.services.audit import write_audit_log

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
    commit: bool = True,
) -> SecurityAlert:
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
    await db.flush()

    await write_audit_log(
        db,
        organization_id=organization_id,
        actor_type="system",
        action="security_alert_created",
        entity_type="security_alert",
        entity_id=alert.id,
        result=severity,
        payload={
            "tracker_id": str(tracker_id),
            "check_type": check_type,
            "message": message,
            "security_check_id": str(security_check_id) if security_check_id else None,
        },
        commit=False,
    )

    if commit:
        await db.commit()
        await db.refresh(alert)

    logger.warning(
        "SecurityAlert créée : id=%s tracker_id=%s check_type=%s",
        alert.id, tracker_id, check_type,
    )
    return alert

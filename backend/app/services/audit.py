"""
Service d'audit append-only.

Toute écriture dans `audit_logs` doit passer par `write_audit_log`. Ce module
ne fournit volontairement AUCUNE fonction d'update/delete : l'immuabilité
sera aussi renforcée au niveau PostgreSQL par la migration de la Tâche 4b
(révocation UPDATE/DELETE sur la table), pour tenir même en cas de bug
applicatif.

Le contenu brut (`payload`) n'est jamais stocké : seule son empreinte
SHA-256 (`payload_hash`) est persistée.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.audit_logs import AuditLog


def _hash_payload(payload: dict[str, Any] | None) -> str | None:
    if payload is None:
        return None
    canonical = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


async def write_audit_log(
    db: AsyncSession,
    *,
    organization_id: UUID,
    action: str,
    entity_type: str,
    result: str,
    user_id: UUID | None = None,
    actor_type: str = "system",
    entity_id: UUID | None = None,
    correlation_id: UUID | None = None,
    payload: dict[str, Any] | None = None,
    commit: bool = True,
) -> AuditLog:
    """Insère une unique ligne dans `audit_logs`. Jamais d'update/delete."""
    entry = AuditLog(
        organization_id=organization_id,
        user_id=user_id,
        actor_type=actor_type,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        result=result,
        correlation_id=correlation_id,
        payload_hash=_hash_payload(payload),
    )
    db.add(entry)
    if commit:
        await db.commit()
        await db.refresh(entry)
    return entry

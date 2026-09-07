"""
Service d'audit append-only.

Toute écriture dans la table `audit_logs` doit passer par `write_audit_log`.
Ce module ne fournit volontairement AUCUNE fonction d'update ou de delete :
la garantie d'immuabilité est également renforcée au niveau PostgreSQL par
une migration Alembic dédiée qui révoque les droits UPDATE/DELETE sur cette
table (voir Tâche 4b), afin que l'append-only tienne même en cas de bug
applicatif ou d'accès direct à la base.

Par design, le contenu brut (`payload`) n'est jamais stocké : seule son
empreinte SHA-256 (`payload_hash`) est persistée, ce qui permet de détecter
une falsification a posteriori sans dupliquer des données potentiellement
sensibles dans le journal.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.audit_logs import AuditLog


def _hash_payload(payload: dict[str, Any] | None) -> str | None:
    """Empreinte SHA-256 canonique et déterministe d'un payload JSON-sérialisable."""
    if payload is None:
        return None
    canonical = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


async def write_audit_log(
    db: AsyncSession,
    *,
    organization_id: UUID | None,
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
    """
    Insère une unique ligne dans `audit_logs`. N'update et ne supprime jamais
    de ligne existante (append-only par construction).

    `organization_id` est nullable : un événement système/plateforme (ex.
    webhook rejeté avant toute vérification de signature) n'a pas encore
    d'organisation résolue au moment du log.
    """
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

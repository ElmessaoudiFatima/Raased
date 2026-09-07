"""
Tests pour app/services/audit.py.

Objectif : garantir que write_audit_log() ne fait jamais que des insertions
(jamais d'update ni de delete), et que payload_hash est bien un hash SHA-256
du payload canonicalisé, jamais le payload brut.
"""
import hashlib
import json
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.audit import write_audit_log
from app.db.models.audit_logs import AuditLog


def _mock_db():
    """
    Simule une AsyncSession SQLAlchemy sans connexion réelle à Postgres,
    dans le même style que tests/test_trust.py : db.add() est synchrone
    (jamais awaited par SQLAlchemy), db.commit()/db.refresh() sont awaited.
    """
    db = AsyncMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    return db


@pytest.mark.asyncio
async def test_write_audit_log_only_calls_add_commit_refresh():
    """
    write_audit_log() ne doit jamais appeler autre chose que
    add() + commit() + refresh(). En particulier, aucune opération
    ressemblant à une modification (UPDATE/DELETE via execute(), merge())
    ne doit être invoquée.
    """
    db = _mock_db()

    await write_audit_log(
        db,
        organization_id=uuid.uuid4(),
        action="security_check_performed",
        entity_type="tracker",
        result="success",
    )

    db.add.assert_called_once()
    db.commit.assert_awaited_once()
    db.refresh.assert_awaited_once()
    assert not hasattr(db, "execute") or not db.execute.called
    assert not hasattr(db, "merge") or not db.merge.called


@pytest.mark.asyncio
async def test_write_audit_log_inserts_an_auditlog_instance():
    """L'objet passé à db.add() doit être une instance de AuditLog."""
    db = _mock_db()

    await write_audit_log(
        db,
        organization_id=uuid.uuid4(),
        action="camara_webhook_rejected",
        entity_type="camara_event",
        result="rejected_invalid_signature",
    )

    added_obj = db.add.call_args[0][0]
    assert isinstance(added_obj, AuditLog)


@pytest.mark.asyncio
async def test_write_audit_log_allows_null_organization_id():
    """
    Cas du webhook non authentifié (Tâche 1) : organization_id=None doit
    être accepté, puisque audit_logs.organization_id est nullable.
    """
    db = _mock_db()

    await write_audit_log(
        db,
        organization_id=None,
        action="camara_webhook_rejected",
        entity_type="camara_event",
        result="rejected_invalid_signature",
    )

    added_obj = db.add.call_args[0][0]
    assert added_obj.organization_id is None


@pytest.mark.asyncio
async def test_payload_hash_is_sha256_of_canonical_payload():
    """
    payload_hash doit être un hash SHA-256 hexadécimal du payload
    canonicalisé (json.dumps trié, default=str), jamais le payload brut.
    """
    db = _mock_db()
    payload = {"tracker_id": "abc-123", "check_type": "sim_swap", "status": "detected"}

    await write_audit_log(
        db,
        organization_id=uuid.uuid4(),
        action="security_check_performed",
        entity_type="tracker",
        result="success",
        payload=payload,
    )

    added_obj = db.add.call_args[0][0]
    expected_hash = hashlib.sha256(
        json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()

    assert added_obj.payload_hash == expected_hash
    assert len(added_obj.payload_hash) == 64
    assert all(c in "0123456789abcdef" for c in added_obj.payload_hash)


@pytest.mark.asyncio
async def test_write_audit_log_does_not_store_raw_payload():
    """
    Le payload brut ne doit être stocké nulle part sur l'objet inséré —
    seul le hash doit être présent (évite de journaliser des données
    potentiellement sensibles en clair, ex. un numéro de téléphone).
    """
    db = _mock_db()
    payload = {"phone_number": "+212600000000", "secret_looking_field": "xyz"}

    await write_audit_log(
        db,
        organization_id=uuid.uuid4(),
        action="security_check_performed",
        entity_type="tracker",
        result="success",
        payload=payload,
    )

    added_obj = db.add.call_args[0][0]
    assert not hasattr(added_obj, "payload")
    assert "+212600000000" not in str(added_obj.payload_hash)


@pytest.mark.asyncio
async def test_write_audit_log_respects_commit_flag():
    """
    Si commit=False, ni commit() ni refresh() ne doivent être appelés
    (permet d'englober l'écriture d'audit dans une transaction plus large,
    gérée par l'appelant).
    """
    db = _mock_db()

    await write_audit_log(
        db,
        organization_id=uuid.uuid4(),
        action="security_check_performed",
        entity_type="tracker",
        result="success",
        commit=False,
    )

    db.add.assert_called_once()
    db.commit.assert_not_awaited()
    db.refresh.assert_not_awaited()

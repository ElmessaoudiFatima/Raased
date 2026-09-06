"""
Mémoire persistante de l'agent SENTRY (Raased).

Role : stocker et retrouver des expériences passées de l'agent (situations,
décisions, résultats) dans ChromaDB pour enrichir le raisonnement futur via
une recherche sémantique.

Contraintes absolues
--------------------
- Aucune donnée métier PostgreSQL ici ; ChromaDB = mémoire épisodique de
  l'agent uniquement.
- Aucun appel CAMARA, aucun LLM, aucune clé secrète dans ce module.
- Aucune donnée inventée : seuls les champs présents dans AgentState sont
  utilisés ; les champs absents sont simplement omis.
- Direction des dépendances : nodes.py → memory.py → ChromaDB (jamais
  l'inverse).
"""

from __future__ import annotations

import logging
import os
from typing import Any

import chromadb
from chromadb.utils import embedding_functions

from app.agent.state import AgentState, is_available

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Collection
# ---------------------------------------------------------------------------
_COLLECTION_NAME = "sentry_agent_experiences"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _flat_metadata(raw: dict[str, Any]) -> dict[str, str | int | float | bool]:
    """
    ChromaDB only accepts str / int / float / bool in metadata.
    Unknown types are coerced to str; None values become empty string.
    """
    result: dict[str, str | int | float | bool] = {}
    for k, v in raw.items():
        if isinstance(v, bool):
            result[k] = v
        elif isinstance(v, (int, float)):
            result[k] = v
        elif v is None:
            result[k] = ""
        else:
            result[k] = str(v)
    return result


def build_situation_text(state: AgentState) -> str:
    """
    Build a human-readable semantic document from real AgentState fields only.
    No invented data – fields absent from state are simply skipped.
    This text is what ChromaDB embeds for semantic similarity search.
    """
    parts: list[str] = []

    if is_available(state, "cargo_type"):
        parts.append(f"Cargo type: {state['cargo_type']}")
    if is_available(state, "criticality"):
        parts.append(f"Criticality: {state['criticality']}")
    if is_available(state, "cargo_status"):
        parts.append(f"Cargo status: {state['cargo_status']}")

    if is_available(state, "incident_detected") and state.get("incident_detected"):
        if is_available(state, "incident_type"):
            parts.append(f"Incident type: {state['incident_type']}")
        if is_available(state, "incident_severity"):
            parts.append(f"Incident severity: {state['incident_severity']}")

    if is_available(state, "risk_level"):
        parts.append(f"Risk level: {state['risk_level']}")
    if is_available(state, "risk_score"):
        parts.append(f"Risk score: {state['risk_score']}")

    if is_available(state, "decision"):
        parts.append(f"Decision: {state['decision']}")
    if is_available(state, "justification"):
        parts.append(f"Justification: {state['justification']}")
    if is_available(state, "reasoning"):
        parts.append(f"Reasoning: {state['reasoning']}")
    if is_available(state, "confidence"):
        parts.append(f"Confidence: {state['confidence']}")

    if is_available(state, "origin"):
        parts.append(f"Origin: {state['origin']}")
    if is_available(state, "destination"):
        parts.append(f"Destination: {state['destination']}")

    return " | ".join(parts) if parts else "No situation details available."


# ---------------------------------------------------------------------------
# AgentMemory
# ---------------------------------------------------------------------------

class AgentMemory:
    """
    Persistent episodic memory for the SENTRY agent backed by ChromaDB.

    Only agent experiences (situations → decisions → outcomes) are stored here.
    Business data stays in PostgreSQL.
    """

    def __init__(self) -> None:
        persist_dir = os.environ.get("CHROMA_PERSIST_DIRECTORY", "./data/chroma")

        self._client = chromadb.PersistentClient(path=persist_dir)

        # Use ChromaDB's built-in embedding (sentence-transformers all-MiniLM-L6-v2)
        # so no external API key is needed.
        self._ef = embedding_functions.DefaultEmbeddingFunction()

        self._collection = self._client.get_or_create_collection(
            name=_COLLECTION_NAME,
            embedding_function=self._ef,
            metadata={"hnsw:space": "cosine"},
        )
        logger.info(
            "AgentMemory initialised | dir=%s | collection=%s",
            persist_dir,
            _COLLECTION_NAME,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def store_memory(
        self,
        memory_id: str,
        situation: str,
        metadata: dict[str, Any],
    ) -> None:
        """
        Upsert one experience document.

        Parameters
        ----------
        memory_id:
            Deterministic identifier built by the caller, e.g.
            ``f"{trip_id}__{incident_type}__{evaluated_at}"``.
        situation:
            The semantic text to embed (use ``build_situation_text``).
        metadata:
            Flat dict with the expected fields (trip_id, cargo_id, …).
            All values are coerced to ChromaDB-compatible types.
        """
        safe_meta = _flat_metadata(metadata)
        try:
            self._collection.upsert(
                ids=[memory_id],
                documents=[situation],
                metadatas=[safe_meta],
            )
            logger.debug("Memory stored | id=%s", memory_id)
        except Exception:
            logger.exception("Failed to store memory id=%s", memory_id)
            raise

    def search_similar(
        self,
        query: str,
        n_results: int = 3,
    ) -> list[dict]:
        """
        Return the n_results most semantically similar past experiences.

        Returns [] when the collection is empty or query yields no match.

        Return format
        -------------
        [
            {
                "id": str,
                "document": str,
                "metadata": dict,
                "distance": float,
            },
            ...
        ]
        """
        try:
            count = self._collection.count()
            if count == 0:
                return []

            actual_n = min(n_results, count)
            results = self._collection.query(
                query_texts=[query],
                n_results=actual_n,
                include=["documents", "metadatas", "distances"],
            )
        except Exception:
            logger.exception("search_similar failed | query=%.120s", query)
            return []

        ids = results.get("ids", [[]])[0]
        documents = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]

        output: list[dict] = []
        for mem_id, doc, meta, dist in zip(ids, documents, metadatas, distances):
            output.append(
                {
                    "id": mem_id,
                    "document": doc,
                    "metadata": meta,
                    "distance": dist,
                }
            )
        return output

    def get_memory(self, memory_id: str) -> dict | None:
        """
        Retrieve a single memory by its deterministic ID.
        Returns None if not found.
        """
        try:
            result = self._collection.get(
                ids=[memory_id],
                include=["documents", "metadatas"],
            )
        except Exception:
            logger.exception("get_memory failed | id=%s", memory_id)
            return None

        ids = result.get("ids", [])
        if not ids:
            return None

        return {
            "id": ids[0],
            "document": result["documents"][0],
            "metadata": result["metadatas"][0],
        }

    def delete_memory(self, memory_id: str) -> None:
        """
        Delete one memory by its ID. No-op if the ID does not exist.
        """
        try:
            self._collection.delete(ids=[memory_id])
            logger.debug("Memory deleted | id=%s", memory_id)
        except Exception:
            logger.exception("delete_memory failed | id=%s", memory_id)
            raise


# ---------------------------------------------------------------------------
# Module-level singleton (lazy, created once per process)
# ---------------------------------------------------------------------------
_memory_instance: AgentMemory | None = None


def get_agent_memory() -> AgentMemory:
    """Return the process-wide AgentMemory singleton (created on first call)."""
    global _memory_instance
    if _memory_instance is None:
        _memory_instance = AgentMemory()
    return _memory_instance

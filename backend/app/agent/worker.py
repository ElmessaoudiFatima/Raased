"""
Worker de surveillance continue de l'agent SENTRY (Raased).

Contexte : le graphe LangGraph (app/agent/graph.py) ne se déclenche jamais
tout seul, et aucun node ne remplit camara_requests ni qod_parameters
(confirmé par grep sur app/agent/). Ce worker est le mécanisme assumé qui
fait tourner l'agent en continu pour la démo :
  - sélectionne les trackers en trajet actif (Cargo.status == IN_TRANSIT)
    avec un msisdn exploitable,
  - fournit explicitement camara_requests (politique de surveillance par
    défaut) et qod_parameters (config technique, ne peut pas être déduite
    d'un tracker GPS),
  - respecte un cooldown pour éviter de spammer CAMARA/le LLM à chaque cycle.

En production réelle, ce polling naïf serait remplacé par un déclenchement
event-driven (webhook Nokia) ou un polling à fréquence adaptative — présenté
comme tel dans le README de l'agent ("Next Steps").
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.agent.graph import build_graph
from app.agent.state import create_initial_state
from app.core.config import get_settings
from app.db.models.agent_decisions import AgentDecision
from app.db.models.cargo_trackers import CargoTracker
from app.db.models.cargos import Cargo
from app.db.models.trackers import Tracker
from app.db.session import AsyncSessionLocal  # à confirmer via head -30 nodes.py

logger = logging.getLogger(__name__)
settings = get_settings()


async def _get_active_trackers() -> list[Tracker]:
    """Trackers assignés à une cargaison IN_TRANSIT, avec un msisdn exploitable."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Tracker)
            .join(CargoTracker, CargoTracker.tracker_id == Tracker.id)
            .join(Cargo, Cargo.id == CargoTracker.cargo_id)
            .where(
                Cargo.status == "IN_TRANSIT",
                CargoTracker.unassigned_at.is_(None),
                Tracker.msisdn.is_not(None),
            )
            .distinct()
        )
        return list(result.scalars().all())


async def _recently_evaluated(tracker_id: str, cooldown_seconds: int) -> bool:
    """Évite de ré-évaluer un tracker déjà traité il y a moins de cooldown_seconds."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(AgentDecision.created_at)
            .where(AgentDecision.tracker_id == tracker_id)
            .order_by(AgentDecision.created_at.desc())
            .limit(1)
        )
        last = result.scalar_one_or_none()
    if last is None:
        return False
    if last.tzinfo is None:
        last = last.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - last) < timedelta(seconds=cooldown_seconds)


async def _has_pending_decision(tracker_id: str) -> bool:
    """Bloque un nouveau cycle si une décision non résolue existe déjà pour ce tracker."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(AgentDecision.id)
            .where(
                AgentDecision.tracker_id == tracker_id,
                AgentDecision.requires_human_approval.is_(True),
                AgentDecision.approved_by.is_(None),
            )
            .limit(1)
        )
        return result.scalar_one_or_none() is not None


def _default_qod_parameters() -> dict:
    """
    Paramètres QoD de démonstration : ces IP techniques ne peuvent pas être
    déduites automatiquement d'un tracker GPS (voir QoDParameters, state.py)
    — c'est une config produit fournie explicitement, pas un calcul du graphe.
    """
    return {
        "device_public_ip": settings.AGENT_DEMO_DEVICE_PUBLIC_IP,
        "device_private_ip": settings.AGENT_DEMO_DEVICE_PRIVATE_IP,
        "application_server_ip": settings.AGENT_DEMO_APP_SERVER_IP,
        "qos_profile": settings.AGENT_DEMO_QOS_PROFILE,
        "duration": settings.AGENT_DEMO_QOD_DURATION,
    }


async def _run_cycle_for_tracker(tracker: Tracker) -> None:
    state = create_initial_state(tracker_id=str(tracker.id))
    state["camara_requests"] = {"congestion": True, "location": True}
    state["qod_parameters"] = _default_qod_parameters()

    logger.info(" Cycle agent — tracker %s (%s)", tracker.msisdn, tracker.id)
    try:
        result = await build_graph().ainvoke(state)
    except Exception:
        logger.exception("Échec du cycle agent pour tracker %s", tracker.id)
        return

    logger.info(
        "   → decision=%s | requires_human_approval=%s | missing=%s | errors=%s",
        result.get("decision"),
        result.get("requires_human_approval"),
        result.get("missing_information"),
        result.get("errors"),
    )


async def agent_loop() -> None:
    """Boucle de surveillance continue. Lancée comme tâche de fond FastAPI (lifespan)."""
    logger.info(
        " Agent loop démarrée (intervalle=%ss, cooldown=%ss)",
        settings.AGENT_LOOP_INTERVAL_SECONDS,
        settings.AGENT_LOOP_COOLDOWN_SECONDS,
    )
    while True:
        try:
            trackers = await _get_active_trackers()
            for tracker in trackers:
                if await _recently_evaluated(str(tracker.id), settings.AGENT_LOOP_COOLDOWN_SECONDS):
                    continue
                if await _has_pending_decision(str(tracker.id)):
                    logger.info("⏸️  Tracker %s ignoré : décision déjà en attente d'approbation", tracker.id)
                    continue
                await _run_cycle_for_tracker(tracker)
        except asyncio.CancelledError:
            logger.info(" Agent loop arrêtée.")
            raise
        except Exception:
            logger.exception(
                "Erreur inattendue dans agent_loop, cycle suivant dans %ss",
                settings.AGENT_LOOP_INTERVAL_SECONDS,
            )
        await asyncio.sleep(settings.AGENT_LOOP_INTERVAL_SECONDS)
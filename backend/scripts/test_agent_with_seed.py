"""Scénario d'intégration isolé pour l'agent SENTRY.

Crée des lignes PostgreSQL explicitement marquées ``SENTRY_AGENT_TEST-*``,
exécute le graphe sans plan CAMARA, puis affiche le résultat. Les données sont
conservées par défaut afin de pouvoir les inspecter ; ``--cleanup <TAG>`` ne
supprime que les lignes créées par ce script et la mémoire Chroma associée.
"""
from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from geoalchemy2.elements import WKTElement
from sqlalchemy import delete, select

from app.agent.graph import build_graph
from app.agent.memory import get_agent_memory
from app.agent.state import create_initial_state
from app.db.models.agent_decisions import AgentDecision
from app.db.models.alerts import Alert
from app.db.models.audit_logs import AuditLog
from app.db.models.cargo_trackers import CargoTracker
from app.db.models.cargos import Cargo
from app.db.models.congestion_events import CongestionEvent
from app.db.models.corridor_congestion_baselines import CorridorCongestionBaseline
from app.db.models.corridors import Corridor
from app.db.models.network_actions import NetworkAction
from app.db.models.organizations import Organization
from app.db.models.risk_assessments import RiskAssessment
from app.db.models.risk_zones import RiskZone
from app.db.models.tracker_locations import TrackerLocation
from app.db.models.trackers import Tracker
from app.db.session import AsyncSessionLocal


async def cleanup(run_tag: str) -> None:
    """Supprime exclusivement les lignes liées à une organisation de test."""
    if not run_tag.startswith("SENTRY_AGENT_TEST_"):
        raise ValueError("Le nettoyage accepte uniquement un tag SENTRY_AGENT_TEST_.")
    async with AsyncSessionLocal() as db:
        organization = (await db.execute(
            select(Organization).where(Organization.legal_id == run_tag)
        )).scalar_one_or_none()
        if organization is None:
            print(f"Aucune donnée de test trouvée pour {run_tag}.")
            return

        tracker_ids = select(Tracker.id).where(Tracker.organization_id == organization.id)
        assessment_ids = select(RiskAssessment.id).where(RiskAssessment.tracker_id.in_(tracker_ids))
        decision_ids = (await db.execute(
            select(AgentDecision.id).where(AgentDecision.risk_assessment_id.in_(assessment_ids))
        )).scalars().all()

        # ChromaDB n'est pas relationnel : on retire explicitement les souvenirs
        # associés aux décisions de cette exécution de test.
        for decision_id in decision_ids:
            try:
                get_agent_memory().delete_memory(str(decision_id))
            except Exception as exc:  # le nettoyage SQL doit rester possible
                print(f"Mémoire ChromaDB non supprimée pour {decision_id}: {exc}")

        await db.execute(delete(NetworkAction).where(NetworkAction.risk_assessment_id.in_(assessment_ids)))
        await db.execute(delete(Alert).where(Alert.risk_assessment_id.in_(assessment_ids)))
        await db.execute(delete(AgentDecision).where(AgentDecision.risk_assessment_id.in_(assessment_ids)))
        await db.execute(delete(RiskAssessment).where(RiskAssessment.tracker_id.in_(tracker_ids)))
        await db.execute(delete(CongestionEvent).where(CongestionEvent.tracker_id.in_(tracker_ids)))
        await db.execute(delete(TrackerLocation).where(TrackerLocation.tracker_id.in_(tracker_ids)))
        await db.execute(delete(CargoTracker).where(CargoTracker.tracker_id.in_(tracker_ids)))
        await db.execute(delete(AuditLog).where(AuditLog.organization_id == organization.id))
        await db.execute(delete(Cargo).where(Cargo.organization_id == organization.id))
        await db.execute(delete(Tracker).where(Tracker.organization_id == organization.id))

        corridor_ids = select(Corridor.id).where(Corridor.name == f"{run_tag} Corridor")
        await db.execute(delete(RiskZone).where(RiskZone.corridor_id.in_(corridor_ids)))
        await db.execute(delete(CorridorCongestionBaseline).where(
            CorridorCongestionBaseline.corridor_id.in_(corridor_ids)
        ))
        await db.execute(delete(Corridor).where(Corridor.name == f"{run_tag} Corridor"))
        await db.execute(delete(Organization).where(Organization.id == organization.id))
        await db.commit()
    print(f"Données de test supprimées : {run_tag}")


async def seed_and_run() -> None:
    """Crée un scénario critique entièrement local, sans appel CAMARA."""
    run_tag = f"SENTRY_AGENT_TEST_{uuid4().hex[:10].upper()}"
    now = datetime.now(timezone.utc)

    async with AsyncSessionLocal() as db:
        organization = Organization(
            name=f"{run_tag} Organisation", legal_id=run_tag, country="Maroc",
            city="Rabat", phone="TEST_ONLY", address="Données de test locales",
            email=f"{run_tag.lower()}@invalid.test", status="APPROVED",
        )
        corridor = Corridor(
            name=f"{run_tag} Corridor", origin="Rabat", destination="Casablanca",
            geometry=WKTElement("LINESTRING(-6.85 34.02, -6.75 34.05)", srid=4326),
            risk_level="CRITICAL", is_active=True,
        )
        db.add_all((organization, corridor))
        await db.flush()

        tracker = Tracker(
            organization_id=organization.id, device_id=f"{run_tag}-TRACKER",
            msisdn=None, status="ACTIVE", last_seen_at=now,
        )
        cargo = Cargo(
            organization_id=organization.id, reference=f"{run_tag}-CARGO",
            type="TEST_ONLY", criticality="CRITICAL", status="IN_TRANSIT",
            origin="Rabat", destination="Casablanca", deadline=now + timedelta(hours=1),
        )
        db.add_all((tracker, cargo))
        await db.flush()

        db.add_all((
            CargoTracker(cargo_id=cargo.id, tracker_id=tracker.id, assigned_at=now),
            TrackerLocation(
                tracker_id=tracker.id,
                location=WKTElement("POINT(-6.80 34.03)", srid=4326),
                accuracy=25.0, source="TEST_SEED", timestamp=now,
            ),
            RiskZone(
                corridor_id=corridor.id, name=f"{run_tag} Zone", type="TEST_ONLY",
                risk_level="CRITICAL",
                geometry=WKTElement(
                    "POLYGON((-6.82 34.01, -6.78 34.01, -6.78 34.05, -6.82 34.05, -6.82 34.01))",
                    srid=4326,
                ),
                is_active=True,
            ),
            CorridorCongestionBaseline(
                corridor_id=corridor.id, hour_of_day=now.hour, day_of_week=now.weekday(),
                typical_congestion_level="low", sample_count=1,
            ),
            CongestionEvent(
                tracker_id=tracker.id, corridor_id=corridor.id, congestion_level="high",
                confidence_level=0.95, timestamp=now, source="TEST_SEED", raw_event_id=run_tag,
            ),
        ))
        await db.commit()

    # Aucun ``camara_requests`` : CAMARA ne peut pas être appelé par ce scénario.
    result = await build_graph().ainvoke(create_initial_state(tracker_id=str(tracker.id)))
    print(f"\nTag de nettoyage : {run_tag}")
    print(f"Tracker : {tracker.id}")
    print(f"Cargo : {cargo.id}")
    print(f"Décision : {result.get('decision')}")
    print(f"Niveau de risque : {result.get('risk_level')}")
    print(f"Approbation humaine requise : {result.get('requires_human_approval')}")
    print(f"RiskAssessment : {result.get('risk_assessment_id')}")
    print(f"AgentDecision : {result.get('agent_decision_id')}")
    print(f"Informations manquantes : {result.get('missing_information', [])}")
    print(f"Erreurs : {result.get('errors', [])}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Teste le graphe SENTRY avec des données PostgreSQL isolées.")
    parser.add_argument("--cleanup", metavar="TAG", help="supprime les données créées pour ce tag")
    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    if args.cleanup:
        await cleanup(args.cleanup)
    else:
        await seed_and_run()


if __name__ == "__main__":
    asyncio.run(main())

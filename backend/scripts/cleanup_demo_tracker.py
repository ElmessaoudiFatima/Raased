"""
Nettoie toutes les données générées par l'agent pour un tracker donné
(alerts, decisions, risk_assessments, network_actions, congestion_events),
sans toucher au tracker lui-même ni à sa dernière position.

Usage: PYTHONPATH=. python scripts/cleanup_demo_tracker.py +99999991000
"""
import asyncio
import sys

from sqlalchemy import delete, select

from app.db.models.trackers import Tracker
from app.db.models.alerts import Alert
from app.db.models.agent_decisions import AgentDecision
from app.db.models.risk_assessments import RiskAssessment
from app.db.models.network_actions import NetworkAction
from app.db.models.congestion_events import CongestionEvent
from app.db.session import AsyncSessionLocal


async def cleanup(msisdn: str) -> None:
    async with AsyncSessionLocal() as db:
        tracker = (
            await db.execute(select(Tracker).where(Tracker.msisdn == msisdn))
        ).scalar_one_or_none()
        if tracker is None:
            print(f"❌ Aucun tracker trouvé pour {msisdn}")
            return

        tracker_id = tracker.id

        # Ordre important : respecter les FK (enfants avant parents)
        await db.execute(delete(Alert).where(Alert.tracker_id == tracker_id))
        await db.execute(delete(NetworkAction).where(NetworkAction.tracker_id == tracker_id))
        await db.execute(delete(AgentDecision).where(AgentDecision.tracker_id == tracker_id))
        await db.execute(delete(RiskAssessment).where(RiskAssessment.tracker_id == tracker_id))
        await db.execute(delete(CongestionEvent).where(CongestionEvent.tracker_id == tracker_id))

        await db.commit()
        print(f"✅ Nettoyage terminé pour tracker {msisdn} ({tracker_id})")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python scripts/cleanup_demo_tracker.py <msisdn>")
        sys.exit(1)
    asyncio.run(cleanup(sys.argv[1]))
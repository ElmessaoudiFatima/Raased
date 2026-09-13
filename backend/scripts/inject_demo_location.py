"""
Script de démo : injecte une position (TrackerLocation) au centroïde
d'une RiskZone active existante, pour un tracker donné.

Nécessaire car TrackerLocation n'est jamais écrit ailleurs dans le code
actuel (ni via l'UI, ni via le webhook Nokia — TODO "Tâche 3" jamais fait,
confirmé dans webhooks.py). Sans cette étape, corridor_id reste toujours
None dans le state de l'agent, et aucun appel Congestion Insights réel
ne peut jamais se déclencher.

Usage:
    PYTHONPATH=. python scripts/inject_demo_location.py <tracker_msisdn>
"""
import asyncio
import sys
from datetime import datetime, timezone

from sqlalchemy import select, func

from app.db.session import AsyncSessionLocal
from app.db.models.trackers import Tracker
from app.db.models.risk_zones import RiskZone
from app.db.models.tracker_locations import TrackerLocation


async def main(msisdn: str) -> None:
    async with AsyncSessionLocal() as db:
        tracker = (await db.execute(
            select(Tracker).where(Tracker.msisdn == msisdn)
        )).scalar_one_or_none()
        if tracker is None:
            print(f"❌ Aucun tracker trouvé avec msisdn={msisdn}")
            return

        zone = (await db.execute(
            select(RiskZone).where(RiskZone.is_active.is_(True))
            .order_by(RiskZone.updated_at.desc()).limit(1)
        )).scalar_one_or_none()
        if zone is None:
            print("❌ Aucune RiskZone active trouvée. Crée-en une via l'UI d'abord.")
            return

        centroid = (await db.execute(
            select(func.ST_Centroid(RiskZone.geometry)).where(RiskZone.id == zone.id)
        )).scalar_one()

        location = TrackerLocation(
            tracker_id=tracker.id,
            location=centroid,
            accuracy=10.0,
            source="DEMO_SCRIPT",
            timestamp=datetime.now(timezone.utc),
        )
        db.add(location)
        await db.commit()

        print(f"✅ Position injectée pour tracker {msisdn} au centroïde de la zone '{zone.name}' (id={zone.id})")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python scripts/inject_demo_location.py <msisdn>")
        sys.exit(1)
    asyncio.run(main(sys.argv[1]))
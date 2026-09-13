"""
Endpoints réservés aux chauffeurs (rôle DRIVER).
Tous les résultats sont scopés au chauffeur connecté (current_user.id)
et à son organisation.
"""
from __future__ import annotations

import json as _json
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from geoalchemy2.functions import ST_AsGeoJSON

from app.api.deps import require_role
from app.db.session import get_db
from app.db.models.users import User
from app.db.models.cargos import Cargo
from app.db.models.corridors import Corridor
from app.db.models.alerts import Alert
from app.db.models.cargo_trackers import CargoTracker
from app.services import tracker_service

router = APIRouter(
    prefix="/drivers",
    tags=["driver"],
    dependencies=[Depends(require_role("DRIVER"))],
)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

ACTIVE_STATUSES = {"PENDING", "IN_TRANSIT", "DELAYED"}


async def _get_active_cargo(db: AsyncSession, driver_id: UUID) -> Cargo | None:
    """Retourne la cargaison active (non terminée) actuellement assignée au chauffeur."""
    stmt = (
        select(Cargo)
        .options(
            selectinload(Cargo.corridor),
            selectinload(Cargo.cargo_trackers).selectinload(CargoTracker.tracker),
        )
        .where(
            Cargo.driver_id == driver_id,
            Cargo.status.in_(ACTIVE_STATUSES),
        )
        .order_by(Cargo.created_at.desc())
        .limit(1)
    )
    res = await db.execute(stmt)
    return res.scalar_one_or_none()


async def _build_trip_payload(db: AsyncSession, cargo: Cargo) -> dict:
    """Construit le payload trip (route + position) pour une cargaison donnée."""
    route_points: list[list[float]] = []
    origin_str = "Origin"
    dest_str = "Destination"

    if cargo.corridor_id:
        corr_res = await db.execute(
            select(Corridor, ST_AsGeoJSON(Corridor.geometry).label("geojson")).where(
                Corridor.id == cargo.corridor_id
            )
        )
        row = corr_res.first()
        if row:
            corridor, geojson_str = row
            origin_str = corridor.origin
            dest_str = corridor.destination
            if geojson_str:
                try:
                    geom = _json.loads(geojson_str)
                    route_points = [
                        [float(p[1]), float(p[0])] for p in geom.get("coordinates", [])
                    ]
                except Exception:
                    route_points = []

    active_tracker = None
    for ct in cargo.cargo_trackers:
        if ct.unassigned_at is None and ct.tracker:
            active_tracker = ct.tracker
            break

    position = None
    if active_tracker:
        pos_dict = await tracker_service.get_last_position(db, active_tracker.id)
        if pos_dict:
            progress_pct = 65 if cargo.status == "IN_TRANSIT" else (100 if cargo.status == "DELIVERED" else 0)
            eta_min = max(15, int((100 - progress_pct) * 2))
            position = {
                "lat": float(pos_dict["latitude"]),
                "lng": float(pos_dict["longitude"]),
                "progress_pct": progress_pct,
                "eta_minutes": eta_min,
            }

    if position is None and route_points:
        if cargo.status == "IN_TRANSIT":
            pt = route_points[len(route_points) // 2]
            position = {"lat": pt[0], "lng": pt[1], "progress_pct": 50, "eta_minutes": 75}
        elif cargo.status == "PENDING":
            pt = route_points[0]
            position = {"lat": pt[0], "lng": pt[1], "progress_pct": 0, "eta_minutes": 180}
        elif cargo.status == "DELIVERED":
            pt = route_points[-1]
            position = {"lat": pt[0], "lng": pt[1], "progress_pct": 100, "eta_minutes": 0}

    veh_reg = active_tracker.label or active_tracker.device_id if active_tracker else None

    return {
        "cargo": {
            "id": str(cargo.id),
            "reference": cargo.reference,
            "type": cargo.type,
            "criticality": cargo.criticality,
            "origin": origin_str,
            "destination": dest_str,
            "deadline": cargo.deadline.isoformat() if cargo.deadline else None,
            "vehicle_registration": veh_reg,
            "device_id": active_tracker.device_id if active_tracker else None,
        },
        "route": route_points,
        "position": position,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Overview (dashboard)
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/overview", summary="Driver dashboard stats + current mission")
async def get_driver_overview(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("DRIVER")),
):
    active_trips = await db.scalar(
        select(func.count(Cargo.id)).where(
            Cargo.driver_id == current_user.id,
            Cargo.status.in_(ACTIVE_STATUSES),
        )
    ) or 0

    delivered = await db.scalar(
        select(func.count(Cargo.id)).where(
            Cargo.driver_id == current_user.id,
            Cargo.status.in_(("DELIVERED", "ARCHIVED")),
        )
    ) or 0

    open_alerts = 0
    if current_user.organization_id:
        open_alerts = await db.scalar(
            select(func.count(Alert.id)).where(
                Alert.organization_id == current_user.organization_id,
                Alert.status != "ACKNOWLEDGED",
            )
        ) or 0

    cargo = await _get_active_cargo(db, current_user.id)
    current = None
    if cargo:
        trip = await _build_trip_payload(db, cargo)
        current = {"cargo": trip["cargo"], "position": trip["position"]}

    return {
        "stats": {
            "active_trips": active_trips,
            "delivered": delivered,
            "open_alerts": open_alerts,
            "current": current,
        }
    }


# ─────────────────────────────────────────────────────────────────────────────
# Trip (map)
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/trip", summary="Driver's current active trip (route + live position)")
async def get_driver_trip(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("DRIVER")),
):
    cargo = await _get_active_cargo(db, current_user.id)
    if not cargo:
        return {"trip": None}
    trip = await _build_trip_payload(db, cargo)
    return {"trip": trip}


# ─────────────────────────────────────────────────────────────────────────────
# Deliveries (history)
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/deliveries", summary="List all cargos ever assigned to this driver")
async def list_driver_deliveries(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("DRIVER")),
):
    stmt = (
        select(Cargo)
        .options(selectinload(Cargo.corridor))
        .where(Cargo.driver_id == current_user.id)
        .order_by(Cargo.created_at.desc())
    )
    res = await db.execute(stmt)
    cargos = res.scalars().all()

    return {
        "deliveries": [
            {
                "id": str(c.id),
                "reference": c.reference,
                "type": c.type,
                "criticality": c.criticality,
                "status": c.status,
                "origin": c.corridor.origin if c.corridor else None,
                "destination": c.corridor.destination if c.corridor else None,
                "deadline": c.deadline.isoformat() if c.deadline else None,
                "created_at": c.created_at.isoformat() if c.created_at else None,
            }
            for c in cargos
        ]
    }


# ─────────────────────────────────────────────────────────────────────────────
# Alerts
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/alerts", summary="List alerts for the driver's organization")
async def list_driver_alerts(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("DRIVER")),
):
    if not current_user.organization_id:
        return {"alerts": []}

    stmt = (
        select(Alert, Cargo.reference)
        .outerjoin(Cargo, Alert.cargo_id == Cargo.id)
        .where(Alert.organization_id == current_user.organization_id)
        .order_by(Alert.created_at.desc())
    )
    res = await db.execute(stmt)
    rows = res.all()

    return {
        "alerts": [
            {
                "id": str(a.id),
                "severity": a.severity,
                "title": a.title,
                "message": a.message,
                "status": a.status,
                "created_at": a.created_at.isoformat() if a.created_at else None,
                "cargo_reference": cargo_ref,
            }
            for a, cargo_ref in rows
        ]
    }


@router.patch("/alerts/{alert_id}/acknowledge", summary="Acknowledge an alert")
async def acknowledge_driver_alert(
    alert_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("DRIVER")),
):
    res = await db.execute(
        select(Alert).where(
            Alert.id == alert_id,
            Alert.organization_id == current_user.organization_id,
        )
    )
    alert = res.scalar_one_or_none()
    if not alert:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found.")

    from datetime import datetime, timezone
    alert.status = "ACKNOWLEDGED"
    alert.acknowledged_at = datetime.now(timezone.utc)
    alert.acknowledged_by = current_user.id
    await db.commit()
    return {"message": "Alert acknowledged.", "status": alert.status}
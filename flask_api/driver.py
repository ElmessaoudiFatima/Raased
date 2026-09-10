from flask import Blueprint, jsonify

from extensions import db
from models import Alert, Cargo, Organization, User
from security import require_role, utcnow
from map_tools import cargo_route, compute_live_position

driver_bp = Blueprint("driver", __name__, url_prefix="/api/drivers")


def _org_of(user):
    return db.session.get(Organization, user.organization_id)


def _trip_dict(cargo):
    position = compute_live_position(cargo)
    return {
        "cargo": {
            "id": cargo.id,
            "reference": cargo.reference,
            "type": cargo.type,
            "criticality": cargo.criticality,
            "origin": cargo.origin,
            "destination": cargo.destination,
            "deadline": cargo.deadline.isoformat() if cargo.deadline else None,
            "vehicle_registration": cargo.tracker.vehicle_registration if cargo.tracker else None,
            "device_id": cargo.tracker.device_id if cargo.tracker else None,
        },
        "route": cargo_route(cargo),
        "position": position,
    }


def _cargo_dict(cargo):
    return {
        "id": cargo.id,
        "reference": cargo.reference,
        "type": cargo.type,
        "criticality": cargo.criticality,
        "status": cargo.status,
        "origin": cargo.origin,
        "destination": cargo.destination,
        "deadline": cargo.deadline.isoformat() if cargo.deadline else None,
    }


@driver_bp.get("/me")
@require_role("DRIVER")
def me(current_user):
    org = _org_of(current_user)
    return jsonify(user=current_user.to_dict(include_org=True))


@driver_bp.get("/overview")
@require_role("DRIVER")
def overview(current_user):
    org = _org_of(current_user)
    active = Cargo.query.filter_by(
        organization_id=org.id, assigned_driver_id=current_user.id, status="IN_TRANSIT"
    ).all()
    delivered = (
        Cargo.query.filter_by(organization_id=org.id, assigned_driver_id=current_user.id)
        .filter(Cargo.status == "DELIVERED")
        .count()
    )
    alerts = Alert.query.filter_by(organization_id=org.id).filter(Alert.status != "CLOSED").count()
    return jsonify(
        stats={
            "active_trips": len(active),
            "delivered": delivered,
            "open_alerts": alerts,
            "current": _trip_dict(active[0]) if active else None,
        }
    )


@driver_bp.get("/trip")
@require_role("DRIVER")
def trip(current_user):
    org = _org_of(current_user)
    active = Cargo.query.filter_by(
        organization_id=org.id, assigned_driver_id=current_user.id, status="IN_TRANSIT"
    ).first()
    if not active:
        return jsonify(trip=None)
    return jsonify(trip=_trip_dict(active))


@driver_bp.get("/history")
@require_role("DRIVER")
def history(current_user):
    org = _org_of(current_user)
    rows = (
        Cargo.query.filter_by(organization_id=org.id, assigned_driver_id=current_user.id)
        .filter(Cargo.status == "DELIVERED")
        .order_by(Cargo.updated_at.desc())
        .all()
    )
    return jsonify(cargos=[_cargo_dict(c) for c in rows])


@driver_bp.get("/alerts")
@require_role("DRIVER")
def alerts(current_user):
    org = _org_of(current_user)
    rows = (
        Alert.query.filter_by(organization_id=org.id)
        .order_by(Alert.created_at.desc())
        .limit(50)
        .all()
    )
    return jsonify(alerts=[a.to_dict() for a in rows])


@driver_bp.patch("/alerts/<alert_id>/acknowledge")
@require_role("DRIVER")
def acknowledge_alert(alert_id, current_user):
    org = _org_of(current_user)
    alert = db.session.get(Alert, alert_id)
    if not alert or alert.organization_id != org.id:
        return jsonify(error="Alerte introuvable."), 404
    alert.status = "ACKNOWLEDGED"
    alert.acknowledged_at = utcnow()
    alert.acknowledged_by = current_user.id
    db.session.commit()
    return jsonify(alert=alert.to_dict(), message="Alerte prise en compte.")
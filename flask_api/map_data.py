from flask import Blueprint, jsonify

from extensions import db
from models import Organization
from security import require_role
from map_tools import all_live_cargos, cargo_route, compute_live_position, corridors_payload, risk_zones_payload

map_bp = Blueprint("map", __name__, url_prefix="/api/map")


def _trip_payload(cargo):
    position = compute_live_position(cargo)
    return {
        "cargo_id": cargo.id,
        "reference": cargo.reference,
        "type": cargo.type,
        "criticality": cargo.criticality,
        "origin": cargo.origin,
        "destination": cargo.destination,
        "vehicle_registration": cargo.tracker.vehicle_registration if cargo.tracker else None,
        "driver": (
            f"{cargo.driver.first_name} {cargo.driver.last_name}" if cargo.driver else None
        ),
        "route": cargo_route(cargo),
        "position": position,
    }


@map_bp.get("/live")
@require_role("MANAGER", "DRIVER")
def live(current_user):
    org = db.session.get(Organization, current_user.organization_id)
    trips = []
    for cargo in all_live_cargos():
        if org and cargo.organization_id != org.id:
            continue
        if current_user.role == "DRIVER" and cargo.assigned_driver_id != current_user.id:
            continue
        trips.append(_trip_payload(cargo))

    return jsonify(
        trips=trips,
        corridors=corridors_payload(),
        risk_zones=risk_zones_payload(),
    )
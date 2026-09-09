import json
import math
import random
import time

from models import Cargo, Corridor, RiskZone


def haversine_meters(lat1, lng1, lat2, lng2):
    r = 6371000.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lng2 - lng1)
    a = (
        math.sin(dphi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlmb / 2) ** 2
    )
    return 2 * r * math.asin(math.sqrt(a))


def _bezier_path(lat1, lng1, lat2, lng2, steps=60, bulge=0.18):
    mid_lat = (lat1 + lat2) / 2
    mid_lng = (lng1 + lng2) / 2

    dlat = lat2 - lat1
    dlng = lng2 - lng1
    norm = math.hypot(dlat, dlng) or 1
    ctrl_lat = mid_lat - dlng / norm * bulge * norm
    ctrl_lng = mid_lng + dlat / norm * bulge * norm

    points = []
    for i in range(steps + 1):
        t = i / steps
        inv = 1 - t
        bx = inv * inv * lat1 + 2 * inv * t * ctrl_lat + t * t * lat2
        by = inv * inv * lng1 + 2 * inv * t * ctrl_lng + t * t * lng2
        points.append([round(bx, 6), round(by, 6)])
    return points


def cargo_route(cargo: Cargo):
    return _bezier_path(
        cargo.origin_lat,
        cargo.origin_lng,
        cargo.destination_lat,
        cargo.destination_lng,
    )


def cargo_route_length_meters(cargo: Cargo):
    route = cargo_route(cargo)
    total = 0.0
    for i in range(len(route) - 1):
        total += haversine_meters(route[i][0], route[i][1], route[i + 1][0], route[i + 1][1])
    return total


def compute_live_position(cargo: Cargo):
    if cargo.status != "IN_TRANSIT" or not cargo.departed_at:
        return None
    if not (cargo.origin_lat and cargo.destination_lat):
        return None

    length = cargo_route_length_meters(cargo)
    speed_ms = (cargo.speed_kmh or 70) / 3.6
    elapsed = max(0.0, (time.time() - cargo.departed_at.timestamp()))

    if length <= 0 or length / speed_ms <= 0:
        return None

    progress = min(max(elapsed * speed_ms / length, 0.0), 1.0)
    route = cargo_route(cargo)

    if progress >= 1.0:
        lat, lng = route[-1]
    else:
        idx = progress * (len(route) - 1)
        i = min(int(idx), len(route) - 2)
        frac = idx - i
        lat = route[i][0] + (route[i + 1][0] - route[i][0]) * frac
        lng = route[i][1] + (route[i + 1][1] - route[i][1]) * frac

    jitter = 0.00025
    lat += random.uniform(-jitter, jitter)
    lng += random.uniform(-jitter, jitter)

    remaining_km = (1 - progress) * length / 1000.0
    eta_minutes = int(remaining_km / max((cargo.speed_kmh or 70), 1) * 60)

    return {
        "lat": round(lat, 6),
        "lng": round(lng, 6),
        "progress_pct": round(progress * 100),
        "eta_minutes": eta_minutes,
        "speed_kmh": cargo.speed_kmh,
        "heading": round((progress * 360) % 360, 1),
    }


def all_live_cargos():
    return Cargo.query.filter_by(status="IN_TRANSIT").all()


def corridors_payload():
    rows = Corridor.query.filter_by(is_active=True).all()
    return [
        {
            "id": c.id,
            "name": c.name,
            "origin": c.origin,
            "destination": c.destination,
            "risk_level": c.risk_level,
            "points": json.loads(c.points_json or "[]"),
        }
        for c in rows
    ]


def risk_zones_payload():
    rows = RiskZone.query.filter_by(is_active=True).all()
    return [
        {
            "id": z.id,
            "name": z.name,
            "type": z.type,
            "risk_level": z.risk_level,
            "description": z.description,
            "points": json.loads(z.points_json or "[]"),
        }
        for z in rows
    ]
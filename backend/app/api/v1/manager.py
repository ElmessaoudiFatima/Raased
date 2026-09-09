"""
Manager API — endpoints reserved for users with the MANAGER role.

All routes are prefixed with /manager and require a valid JWT for a MANAGER account
whose organisation has been APPROVED.
"""
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from geoalchemy2.elements import WKTElement
from geoalchemy2.functions import ST_AsGeoJSON
from pydantic import BaseModel
from shapely.geometry import shape as shapely_shape
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models.corridors import Corridor
from app.db.models.organizations import Organization
from app.db.models.risk_zones import RiskZone
from app.db.models.risk_assessments import RiskAssessment
from app.db.models.agent_decisions import AgentDecision
from app.db.models.cargos import Cargo
from app.db.models.trackers import Tracker
from app.db.models.users import User
from app.db.session import get_db
from app.api.deps import require_role
from app.schemas.auth import DriverCreate, DriverCreateResponse
from app.schemas.corridor import CorridorCreate, CorridorOut, CorridorUpdate
from app.schemas.cargo import CargoCreate, CargoOut, CargoStatusUpdate, CargoUpdate
from app.schemas.tracker import (
    TrackerCreate,
    TrackerOut,
    TrackerUpdate,
    TrackerAssign,
    CargoTrackerOut,
    TrackerLocationOut,
)
from app.services.auth_service import create_driver
from app.services.email_service import send_invitation_email
from app.services import corridor_service, cargo_service, tracker_service

router = APIRouter(
    prefix="/manager",
    tags=["manager"],
)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _require_org(current_user: User) -> UUID:
    """Return the manager's organisation ID or raise 400."""
    if current_user.organization_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The manager is not linked to any organisation.",
        )
    return current_user.organization_id


# ─────────────────────────────────────────────────────────────────────────────
# Drivers
# ─────────────────────────────────────────────────────────────────────────────

@router.post(
    "/drivers",
    response_model=DriverCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Invite and create a driver account for the manager's organisation",
)
async def create_org_driver(
    payload: DriverCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("MANAGER")),
):
    """
    Creates a new driver user with account_status='INVITED' and sends an invitation
    link by email so the driver can set their own password.
    """
    org_id = _require_org(current_user)

    org_res = await db.execute(select(Organization).where(Organization.id == org_id))
    org = org_res.scalar_one_or_none()
    org_name = org.name if org else None

    driver, invitation_token = await create_driver(
        db,
        organization_id=org_id,
        first_name=payload.first_name,
        last_name=payload.last_name,
        email=str(payload.email),
        phone=payload.phone,
    )

    settings = get_settings()
    invitation_link = f"{settings.FRONTEND_URL}/set-password?token={invitation_token}"

    send_invitation_email(
        to_email=driver.email,
        first_name=driver.first_name,
        invitation_link=invitation_link,
        org_name=org_name,
    )

    return driver


# ─────────────────────────────────────────────────────────────────────────────
# Corridors
# ─────────────────────────────────────────────────────────────────────────────

@router.post(
    "/corridors",
    response_model=CorridorOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new corridor for the manager's organisation",
)
async def create_corridor(
    payload: CorridorCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("MANAGER")),
):
    """
    Creates an organisation-scoped transport corridor.
    The geometry must be provided as a GeoJSON LineString.
    """
    org_id = _require_org(current_user)
    corridor = await corridor_service.create_corridor(db, org_id, payload)
    return corridor


@router.get(
    "/corridors",
    response_model=List[CorridorOut],
    summary="List corridors accessible to the manager's organisation",
)
async def list_corridors(
    active_only: bool = Query(False, description="Return only active corridors"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("MANAGER")),
):
    """
    Returns all corridors owned by the manager's organisation plus any global
    corridors (organisation_id = NULL) shared across the platform.
    """
    org_id = _require_org(current_user)
    corridors = await corridor_service.list_corridors(db, org_id, active_only=active_only)
    return corridors


@router.get(
    "/corridors/{corridor_id}",
    response_model=CorridorOut,
    summary="Get details of a specific corridor",
)
async def get_corridor(
    corridor_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("MANAGER")),
):
    """
    Returns details of a corridor if it belongs to the manager's organisation
    or is a global corridor.
    """
    org_id = _require_org(current_user)
    corridor = await corridor_service.get_corridor(db, corridor_id, org_id)
    if not corridor:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Corridor not found.")
    return corridor


@router.patch(
    "/corridors/{corridor_id}",
    response_model=CorridorOut,
    summary="Update an organisation corridor",
)
async def update_corridor(
    corridor_id: UUID,
    payload: CorridorUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("MANAGER")),
):
    """
    Updates a corridor. Only the owning organisation can modify its corridors;
    global corridors (organisation_id = NULL) are read-only for managers.
    """
    org_id = _require_org(current_user)
    corridor = await corridor_service.get_corridor(db, corridor_id, org_id)
    if not corridor:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Corridor not found.")
    if corridor.organization_id != org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You cannot modify a global corridor.",
        )
    corridor = await corridor_service.update_corridor(db, corridor, payload)
    return corridor


@router.delete(
    "/corridors/{corridor_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an organisation corridor",
)
async def delete_corridor(
    corridor_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("MANAGER")),
):
    """
    Permanently deletes a corridor owned by the manager's organisation.
    Global corridors cannot be deleted by managers.
    """
    org_id = _require_org(current_user)
    corridor = await corridor_service.get_corridor(db, corridor_id, org_id)
    if not corridor:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Corridor not found.")
    if corridor.organization_id != org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You cannot delete a global corridor.",
        )
    await corridor_service.delete_corridor(db, corridor)


# ─────────────────────────────────────────────────────────────────────────────
# Cargos
# ─────────────────────────────────────────────────────────────────────────────

@router.post(
    "/cargos",
    response_model=CargoOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new cargo shipment",
)
async def create_cargo(
    payload: CargoCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("MANAGER")),
):
    """
    Creates a new cargo entry for the manager's organisation.
    Initial status is always PENDING.
    """
    org_id = _require_org(current_user)
    cargo = await cargo_service.create_cargo(db, org_id, payload)
    return cargo


@router.get(
    "/cargos",
    response_model=List[CargoOut],
    summary="List cargos for the manager's organisation",
)
async def list_cargos(
    status_filter: Optional[str] = Query(
        None,
        alias="status",
        description="Filter by status: PENDING | IN_TRANSIT | DELIVERED | DELAYED | CANCELLED | ARCHIVED",
    ),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("MANAGER")),
):
    """
    Returns all cargos belonging to the manager's organisation.
    Optionally filter by status using the `status` query parameter.
    """
    org_id = _require_org(current_user)
    cargos = await cargo_service.list_cargos(db, org_id, status_filter=status_filter)
    return cargos


@router.get(
    "/cargos/{cargo_id}",
    response_model=CargoOut,
    summary="Get details of a specific cargo",
)
async def get_cargo(
    cargo_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("MANAGER")),
):
    """Returns the details of a single cargo belonging to the manager's organisation."""
    org_id = _require_org(current_user)
    cargo = await cargo_service.get_cargo(db, cargo_id, org_id)
    if not cargo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cargo not found.")
    return cargo


@router.patch(
    "/cargos/{cargo_id}",
    response_model=CargoOut,
    summary="Update cargo details",
)
async def update_cargo(
    cargo_id: UUID,
    payload: CargoUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("MANAGER")),
):
    """
    Updates editable fields of a cargo (reference, type, criticality, origin,
    destination, deadline). To change the status, use the dedicated status endpoint.
    """
    org_id = _require_org(current_user)
    cargo = await cargo_service.get_cargo(db, cargo_id, org_id)
    if not cargo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cargo not found.")
    cargo = await cargo_service.update_cargo(db, cargo, payload)
    return cargo


@router.patch(
    "/cargos/{cargo_id}/status",
    response_model=CargoOut,
    summary="Update the status of a cargo",
)
async def update_cargo_status(
    cargo_id: UUID,
    payload: CargoStatusUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("MANAGER")),
):
    """
    Updates the status of a cargo following allowed transitions:
    - PENDING -> IN_TRANSIT | CANCELLED
    - IN_TRANSIT -> DELIVERED | DELAYED | CANCELLED
    - DELAYED -> IN_TRANSIT | CANCELLED
    - DELIVERED -> ARCHIVED
    - CANCELLED / ARCHIVED -> (terminal, no further transitions)
    """
    org_id = _require_org(current_user)
    cargo = await cargo_service.get_cargo(db, cargo_id, org_id)
    if not cargo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cargo not found.")
    try:
        cargo = await cargo_service.update_cargo_status(db, cargo, payload.status)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    return cargo


@router.post(
    "/cargos/{cargo_id}/archive",
    response_model=CargoOut,
    summary="Archive a delivered cargo",
)
async def archive_cargo(
    cargo_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("MANAGER")),
):
    """
    Closes/archives a cargo that has been delivered.
    Shortcut for PATCH /cargos/{id}/status with status=ARCHIVED.
    The cargo must have status DELIVERED to be archived.
    """
    org_id = _require_org(current_user)
    cargo = await cargo_service.get_cargo(db, cargo_id, org_id)
    if not cargo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cargo not found.")
    try:
        cargo = await cargo_service.archive_cargo(db, cargo)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    return cargo


# ─────────────────────────────────────────────────────────────────────────────
# Trackers
# ─────────────────────────────────────────────────────────────────────────────

@router.post(
    "/trackers",
    response_model=TrackerOut,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new tracker device",
)
async def register_tracker(
    payload: TrackerCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("MANAGER")),
):
    """
    Registers a new GPS/cellular tracker device for the manager's organisation.
    The device_id (IMEI or similar) must be globally unique.
    """
    org_id = _require_org(current_user)
    try:
        tracker = await tracker_service.create_tracker(db, org_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return tracker


@router.get(
    "/trackers",
    response_model=List[TrackerOut],
    summary="List trackers for the manager's organisation",
)
async def list_trackers(
    status_filter: Optional[str] = Query(
        None,
        alias="status",
        description="Filter by status: ACTIVE | INACTIVE | ASSIGNED | MAINTENANCE",
    ),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("MANAGER")),
):
    """Returns all trackers registered by the manager's organisation."""
    org_id = _require_org(current_user)
    trackers = await tracker_service.list_trackers(db, org_id, status_filter=status_filter)
    return trackers


@router.get(
    "/trackers/{tracker_id}",
    response_model=TrackerOut,
    summary="Get details of a specific tracker",
)
async def get_tracker(
    tracker_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("MANAGER")),
):
    """Returns details of a tracker owned by the manager's organisation."""
    org_id = _require_org(current_user)
    tracker = await tracker_service.get_tracker(db, tracker_id, org_id)
    if not tracker:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tracker not found.")
    return tracker


@router.patch(
    "/trackers/{tracker_id}",
    response_model=TrackerOut,
    summary="Update a tracker",
)
async def update_tracker(
    tracker_id: UUID,
    payload: TrackerUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("MANAGER")),
):
    """Update the MSISDN or status of a registered tracker."""
    org_id = _require_org(current_user)
    tracker = await tracker_service.get_tracker(db, tracker_id, org_id)
    if not tracker:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tracker not found.")
    tracker = await tracker_service.update_tracker(db, tracker, payload)
    return tracker


@router.post(
    "/trackers/{tracker_id}/assign",
    response_model=CargoTrackerOut,
    status_code=status.HTTP_201_CREATED,
    summary="Assign a tracker to a cargo",
)
async def assign_tracker(
    tracker_id: UUID,
    payload: TrackerAssign,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("MANAGER")),
):
    """
    Assigns a tracker to a cargo shipment.
    The tracker must be ACTIVE and not already assigned to another cargo.
    """
    org_id = _require_org(current_user)
    tracker = await tracker_service.get_tracker(db, tracker_id, org_id)
    if not tracker:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tracker not found.")
    try:
        assignment = await tracker_service.assign_tracker_to_cargo(db, tracker, payload.cargo_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return assignment


@router.post(
    "/trackers/{tracker_id}/unassign",
    response_model=CargoTrackerOut,
    summary="Remove a tracker from a cargo",
)
async def unassign_tracker(
    tracker_id: UUID,
    payload: TrackerAssign,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("MANAGER")),
):
    """
    Removes (unassigns) a tracker from a cargo by recording the unassigned_at timestamp.
    The tracker status reverts to ACTIVE.
    """
    org_id = _require_org(current_user)
    tracker = await tracker_service.get_tracker(db, tracker_id, org_id)
    if not tracker:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tracker not found.")
    try:
        assignment = await tracker_service.remove_tracker_from_cargo(db, tracker, payload.cargo_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return assignment


@router.get(
    "/trackers/{tracker_id}/position",
    response_model=TrackerLocationOut,
    summary="Get the last known position of a tracker",
)
async def get_tracker_position(
    tracker_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("MANAGER")),
):
    """
    Returns the most recent recorded GPS position of the tracker.
    Returns 404 if no position data has been recorded yet.
    """
    org_id = _require_org(current_user)
    tracker = await tracker_service.get_tracker(db, tracker_id, org_id)
    if not tracker:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tracker not found.")
    position = await tracker_service.get_last_position(db, tracker_id)
    if position is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No position data available for this tracker.",
        )
    return position


# ─────────────────────────────────────────────────────────────────────────────
# Helpers — geometry
# ─────────────────────────────────────────────────────────────────────────────

def _geojson_to_wkt(geojson: Dict[str, Any]) -> WKTElement:
    """Convert a GeoJSON dict (Polygon) to a PostGIS WKTElement (SRID 4326)."""
    try:
        geom = shapely_shape(geojson)
        return WKTElement(geom.wkt, srid=4326)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Géométrie GeoJSON invalide : {exc}",
        )


async def _get_corridor_for_manager(
    db: AsyncSession,
    corridor_id: UUID,
    org_id: UUID,
) -> Corridor:
    """Return corridor owned by org_id, or raise 404."""
    res = await db.execute(
        select(Corridor).where(
            Corridor.id == corridor_id,
            Corridor.organization_id == org_id,
        )
    )
    corridor = res.scalar_one_or_none()
    if not corridor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Corridor introuvable ou non accessible.",
        )
    return corridor


# ─────────────────────────────────────────────────────────────────────────────
# Risk Zones
# ─────────────────────────────────────────────────────────────────────────────

class RiskZoneCreate(BaseModel):
    name: str
    type: str                        # e.g. ACCIDENT, FLOOD, ROADBLOCK, CRIME
    risk_level: str                  # LOW | MEDIUM | HIGH | CRITICAL
    geometry: Dict[str, Any]         # GeoJSON Polygon
    description: Optional[str] = None
    is_active: bool = True


class RiskZoneUpdate(BaseModel):
    name: Optional[str] = None
    type: Optional[str] = None
    risk_level: Optional[str] = None
    geometry: Optional[Dict[str, Any]] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None


def _zone_out(zone: RiskZone, geojson_str: Optional[str] = None) -> dict:
    return {
        "id": str(zone.id),
        "corridor_id": str(zone.corridor_id),
        "name": zone.name,
        "type": zone.type,
        "risk_level": zone.risk_level,
        "description": zone.description,
        "is_active": zone.is_active,
        "geometry": geojson_str,
        "created_at": zone.created_at.isoformat() if zone.created_at else None,
        "updated_at": zone.updated_at.isoformat() if zone.updated_at else None,
    }


@router.post(
    "/corridors/{corridor_id}/zones",
    status_code=status.HTTP_201_CREATED,
    summary="Créer une zone à risque dans un corridor",
)
async def create_risk_zone(
    corridor_id: UUID,
    payload: RiskZoneCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("MANAGER")),
):
    """
    Crée une zone à risque (polygone GeoJSON) associée à un corridor
    appartenant à l'organisation du manager.
    """
    org_id = _require_org(current_user)
    await _get_corridor_for_manager(db, corridor_id, org_id)

    zone = RiskZone(
        corridor_id=corridor_id,
        name=payload.name,
        type=payload.type.upper(),
        risk_level=payload.risk_level.upper(),
        geometry=_geojson_to_wkt(payload.geometry),
        description=payload.description,
        is_active=payload.is_active,
    )
    db.add(zone)
    await db.commit()
    await db.refresh(zone)

    # Fetch geometry as GeoJSON string
    geo_res = await db.execute(
        select(ST_AsGeoJSON(RiskZone.geometry)).where(RiskZone.id == zone.id)
    )
    geojson_str = geo_res.scalar_one_or_none()
    return _zone_out(zone, geojson_str)


@router.get(
    "/corridors/{corridor_id}/zones",
    summary="Lister les zones à risque d'un corridor",
)
async def list_risk_zones(
    corridor_id: UUID,
    active_only: bool = Query(False),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("MANAGER")),
):
    """Retourne toutes les zones à risque du corridor (filtrable par is_active)."""
    org_id = _require_org(current_user)
    await _get_corridor_for_manager(db, corridor_id, org_id)

    stmt = select(RiskZone, ST_AsGeoJSON(RiskZone.geometry).label("geojson")).where(
        RiskZone.corridor_id == corridor_id
    )
    if active_only:
        stmt = stmt.where(RiskZone.is_active.is_(True))
    stmt = stmt.order_by(RiskZone.created_at.desc())

    res = await db.execute(stmt)
    rows = res.all()
    return {"zones": [_zone_out(zone, geojson) for zone, geojson in rows]}


@router.get(
    "/zones/{zone_id}",
    summary="Détail d'une zone à risque",
)
async def get_risk_zone(
    zone_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("MANAGER")),
):
    """Retourne les détails d'une zone à risque accessible au manager."""
    org_id = _require_org(current_user)

    # Join via corridor to enforce org ownership
    res = await db.execute(
        select(RiskZone, ST_AsGeoJSON(RiskZone.geometry).label("geojson"))
        .join(Corridor, RiskZone.corridor_id == Corridor.id)
        .where(
            RiskZone.id == zone_id,
            Corridor.organization_id == org_id,
        )
    )
    row = res.first()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Zone introuvable.")
    zone, geojson = row
    return _zone_out(zone, geojson)


@router.patch(
    "/zones/{zone_id}",
    summary="Modifier une zone à risque",
)
async def update_risk_zone(
    zone_id: UUID,
    payload: RiskZoneUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("MANAGER")),
):
    """Met à jour les champs d'une zone à risque (tous optionnels)."""
    org_id = _require_org(current_user)

    res = await db.execute(
        select(RiskZone)
        .join(Corridor, RiskZone.corridor_id == Corridor.id)
        .where(RiskZone.id == zone_id, Corridor.organization_id == org_id)
    )
    zone = res.scalar_one_or_none()
    if not zone:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Zone introuvable.")

    if payload.name is not None:
        zone.name = payload.name
    if payload.type is not None:
        zone.type = payload.type.upper()
    if payload.risk_level is not None:
        zone.risk_level = payload.risk_level.upper()
    if payload.description is not None:
        zone.description = payload.description
    if payload.is_active is not None:
        zone.is_active = payload.is_active
    if payload.geometry is not None:
        zone.geometry = _geojson_to_wkt(payload.geometry)

    await db.commit()
    await db.refresh(zone)

    geo_res = await db.execute(
        select(ST_AsGeoJSON(RiskZone.geometry)).where(RiskZone.id == zone.id)
    )
    geojson_str = geo_res.scalar_one_or_none()
    return _zone_out(zone, geojson_str)


@router.delete(
    "/zones/{zone_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Supprimer une zone à risque",
)
async def delete_risk_zone(
    zone_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("MANAGER")),
):
    """Supprime définitivement une zone à risque appartenant à l'organisation du manager."""
    org_id = _require_org(current_user)

    res = await db.execute(
        select(RiskZone)
        .join(Corridor, RiskZone.corridor_id == Corridor.id)
        .where(RiskZone.id == zone_id, Corridor.organization_id == org_id)
    )
    zone = res.scalar_one_or_none()
    if not zone:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Zone introuvable.")

    await db.delete(zone)
    await db.commit()


# ─────────────────────────────────────────────────────────────────────────────
# Risk Assessments (lecture seule)
# ─────────────────────────────────────────────────────────────────────────────

def _assessment_out(a: RiskAssessment) -> dict:
    return {
        "id": str(a.id),
        "cargo_id": str(a.cargo_id),
        "tracker_id": str(a.tracker_id),
        "corridor_id": str(a.corridor_id),
        "risk_level": a.risk_level,
        "risk_score": float(a.risk_score) if a.risk_score is not None else None,
        "confidence_score": float(a.confidence_score) if a.confidence_score is not None else None,
        "reason": a.reason,
        "factors": a.factors,
        "created_at": a.created_at.isoformat() if a.created_at else None,
    }


@router.get(
    "/risk-assessments",
    summary="Lister les évaluations de risque de l'organisation",
)
async def list_risk_assessments(
    risk_level: Optional[str] = Query(None, description="Filtrer par niveau : LOW | MEDIUM | HIGH | CRITICAL"),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("MANAGER")),
):
    """
    Retourne les évaluations de risque associées aux cargaisons de l'organisation,
    par ordre chronologique décroissant.
    """
    org_id = _require_org(current_user)

    stmt = (
        select(RiskAssessment)
        .join(Cargo, RiskAssessment.cargo_id == Cargo.id)
        .where(Cargo.organization_id == org_id)
        .order_by(RiskAssessment.created_at.desc())
        .limit(limit)
    )
    if risk_level:
        stmt = stmt.where(RiskAssessment.risk_level == risk_level.upper())

    res = await db.execute(stmt)
    assessments = res.scalars().all()
    return {"risk_assessments": [_assessment_out(a) for a in assessments]}


@router.get(
    "/risk-assessments/{assessment_id}",
    summary="Détail d'une évaluation de risque",
)
async def get_risk_assessment(
    assessment_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("MANAGER")),
):
    """Retourne une évaluation de risque, si elle concerne une cargaison de l'organisation."""
    org_id = _require_org(current_user)

    res = await db.execute(
        select(RiskAssessment)
        .join(Cargo, RiskAssessment.cargo_id == Cargo.id)
        .where(
            RiskAssessment.id == assessment_id,
            Cargo.organization_id == org_id,
        )
    )
    assessment = res.scalar_one_or_none()
    if not assessment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Évaluation de risque introuvable.",
        )
    return _assessment_out(assessment)


# ─────────────────────────────────────────────────────────────────────────────
# Agent Decisions (lecture seule — historique)
# ─────────────────────────────────────────────────────────────────────────────

def _decision_out(d: AgentDecision) -> dict:
    if d.approved_by is not None:
        approval_status = "APPROVED"
    elif d.requires_human_approval:
        approval_status = "PENDING_APPROVAL"
    else:
        approval_status = "AUTO_EXECUTED"

    return {
        "id": str(d.id),
        "cargo_id": str(d.cargo_id),
        "tracker_id": str(d.tracker_id),
        "risk_assessment_id": str(d.risk_assessment_id),
        "decision": d.decision,
        "reasoning_summary": d.reasoning_summary,
        "confidence": float(d.confidence) if d.confidence is not None else None,
        "requires_human_approval": d.requires_human_approval,
        "approval_status": approval_status,
        "approved_by": str(d.approved_by) if d.approved_by else None,
        "approved_at": d.approved_at.isoformat() if d.approved_at else None,
        "created_at": d.created_at.isoformat() if d.created_at else None,
    }


@router.get(
    "/agent-decisions",
    summary="Historique des décisions de l'agent IA",
)
async def list_agent_decisions(
    decision_type: Optional[str] = Query(None, description="Filtrer par type de décision"),
    requires_approval: Optional[bool] = Query(None, description="Filtrer par approbation requise"),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("MANAGER")),
):
    """
    Retourne l'historique des décisions prises par l'agent IA pour les cargaisons
    de l'organisation, par ordre chronologique décroissant.
    """
    org_id = _require_org(current_user)

    stmt = (
        select(AgentDecision)
        .join(Cargo, AgentDecision.cargo_id == Cargo.id)
        .where(Cargo.organization_id == org_id)
        .order_by(AgentDecision.created_at.desc())
        .limit(limit)
    )
    if decision_type:
        stmt = stmt.where(AgentDecision.decision == decision_type.upper())
    if requires_approval is not None:
        stmt = stmt.where(AgentDecision.requires_human_approval.is_(requires_approval))

    res = await db.execute(stmt)
    decisions = res.scalars().all()
    return {"agent_decisions": [_decision_out(d) for d in decisions]}


@router.get(
    "/agent-decisions/{decision_id}",
    summary="Détail d'une décision de l'agent IA",
)
async def get_agent_decision(
    decision_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("MANAGER")),
):
    """Retourne le détail d'une décision de l'agent, si elle concerne une cargaison de l'organisation."""
    org_id = _require_org(current_user)

    res = await db.execute(
        select(AgentDecision)
        .join(Cargo, AgentDecision.cargo_id == Cargo.id)
        .where(
            AgentDecision.id == decision_id,
            Cargo.organization_id == org_id,
        )
    )
    decision = res.scalar_one_or_none()
    if not decision:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Décision introuvable.",
        )
    return _decision_out(decision)

"""
Manager API — endpoints reserved for users with the MANAGER role.

All routes are prefixed with /manager and require a valid JWT for a MANAGER account
whose organisation has been APPROVED.
"""
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models.corridors import Corridor
from app.db.models.organizations import Organization
from app.db.models.users import User
from app.db.session import get_db
from app.api.deps import require_role
from app.schemas.auth import DriverCreate, DriverCreateResponse
from app.schemas.corridor import CorridorCreate, CorridorOut, CorridorUpdate
from app.schemas.cargo import CargoCreate, CargoOut, CargoStatusUpdate, CargoUpdate
from app.services.auth_service import create_driver
from app.services.email_service import send_invitation_email
from app.services import corridor_service, cargo_service

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

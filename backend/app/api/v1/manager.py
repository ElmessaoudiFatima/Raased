"""
Manager API — endpoints reserved for users with the MANAGER role.

All routes are prefixed with /manager and require a valid JWT for a MANAGER account
whose organisation has been APPROVED.
"""

import secrets
import uuid
from datetime import datetime, timezone, timedelta
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, delete, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models.corridors import Corridor
from app.db.models.organizations import Organization
from app.db.models.users import User
from app.db.models.alerts import Alert
from app.db.models.cargos import Cargo
from app.db.models.trackers import Tracker
from app.db.models.agent_decisions import AgentDecision
from app.db.models.account_invitations import AccountInvitation
from app.db.session import get_db
from app.api.deps import require_role
from app.schemas.auth import DriverCreate, DriverCreateResponse
from app.schemas.corridor import CorridorCreate, CorridorOut, CorridorUpdate
from app.schemas.cargo import CargoCreate, CargoOut, CargoStatusUpdate, CargoUpdate
from app.services.auth_service import create_driver
from app.services.email_service import send_invitation_email
from app.services import corridor_service, cargo_service

router = APIRouter(tags=["manager"])


# ─────────────────────────────────────────────
# Conducteurs (Drivers)
# ─────────────────────────────────────────────

@router.get("/drivers")
async def list_drivers(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("MANAGER")),
):
    if not current_user.organization_id:
        return {"drivers": []}

    query = (
        select(User)
        .where(
            User.organization_id == current_user.organization_id,
            User.role == "DRIVER",
        )
        .order_by(User.created_at.desc())
    )
    res = await db.execute(query)
    drivers = res.scalars().all()

    return {
        "drivers": [
            {
                "id": str(d.id),
                "first_name": d.first_name,
                "last_name": d.last_name,
                "email": d.email,
                "phone": d.phone,
                "account_status": d.account_status,
                "is_active": d.is_active,
                "email_verified": d.email_verified,
                "created_at": d.created_at.isoformat() if d.created_at else None,
            }
            for d in drivers
        ]
    }


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

    try:
        send_invitation_email(
            to_email=driver.email,
            first_name=driver.first_name,
            invitation_link=invitation_link,
            org_name=org_name,
        )
    except Exception:
        pass

    driver_data = {
        "id": str(driver.id),
        "first_name": driver.first_name,
        "last_name": driver.last_name,
        "email": driver.email,
        "phone": driver.phone,
        "account_status": driver.account_status,
        "is_active": driver.is_active,
        "email_verified": driver.email_verified,
        "created_at": driver.created_at.isoformat() if driver.created_at else None,
    }

    return {
        "id": driver.id,
        "first_name": driver.first_name,
        "last_name": driver.last_name,
        "email": driver.email,
        "phone": driver.phone,
        "role": driver.role,
        "account_status": driver.account_status,
        "is_active": driver.is_active,
        "email_verified": driver.email_verified,
        "invitation_link": invitation_link,
        "driver": driver_data,
        "message": "Compte conducteur créé et email d'invitation envoyé.",
    }


class DriverUpdate(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    email: EmailStr | None = None
    phone: str | None = None


@router.patch("/drivers/{driver_id}")
async def update_org_driver(
    driver_id: uuid.UUID,
    payload: DriverUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("MANAGER")),
):
    res = await db.execute(
        select(User).where(
            User.id == driver_id,
            User.organization_id == current_user.organization_id,
            User.role == "DRIVER",
        )
    )
    driver = res.scalar_one_or_none()
    if not driver:
        raise HTTPException(status_code=404, detail="Conducteur introuvable.")

    if payload.first_name is not None:
        driver.first_name = payload.first_name
    if payload.last_name is not None:
        driver.last_name = payload.last_name
    if payload.email is not None:
        driver.email = str(payload.email)
    if payload.phone is not None:
        driver.phone = payload.phone

    await db.commit()
    await db.refresh(driver)
    return {
        "id": str(driver.id),
        "first_name": driver.first_name,
        "last_name": driver.last_name,
        "email": driver.email,
        "phone": driver.phone,
        "account_status": driver.account_status,
        "is_active": driver.is_active,
    }


@router.delete("/drivers/{driver_id}")
async def delete_org_driver(
    driver_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("MANAGER")),
):
    res = await db.execute(
        select(User).where(
            User.id == driver_id,
            User.organization_id == current_user.organization_id,
            User.role == "DRIVER",
        )
    )
    driver = res.scalar_one_or_none()
    if not driver:
        raise HTTPException(status_code=404, detail="Conducteur introuvable.")

    await db.execute(delete(AccountInvitation).where(AccountInvitation.user_id == driver_id))
    await db.delete(driver)
    await db.commit()
    return {"message": "Conducteur supprimé avec succès."}


@router.post("/drivers/{driver_id}/resend-invitation")
async def resend_driver_invitation(
    driver_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("MANAGER")),
):
    res = await db.execute(
        select(User).where(
            User.id == driver_id,
            User.organization_id == current_user.organization_id,
            User.role == "DRIVER",
        )
    )
    driver = res.scalar_one_or_none()
    if not driver:
        raise HTTPException(status_code=404, detail="Conducteur introuvable.")

    token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=48)

    invitation = AccountInvitation(
        user_id=driver.id,
        token=token,
        expires_at=expires_at,
    )
    db.add(invitation)
    await db.commit()

    settings = get_settings()
    invitation_link = f"{settings.FRONTEND_URL}/set-password?token={token}"

    org_res = await db.execute(
        select(Organization).where(Organization.id == current_user.organization_id)
    )
    org = org_res.scalar_one_or_none()
    org_name = org.name if org else None

    try:
        send_invitation_email(
            to_email=driver.email,
            first_name=driver.first_name,
            invitation_link=invitation_link,
            org_name=org_name,
        )
    except Exception:
        pass

    return {
        "invitation_link": invitation_link,
        "message": "Invitation renvoyée avec succès.",
    }


class DriverStatusUpdate(BaseModel):
    is_active: bool


@router.patch("/drivers/{driver_id}/status")
async def update_driver_status(
    driver_id: uuid.UUID,
    payload: DriverStatusUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("MANAGER")),
):
    res = await db.execute(
        select(User).where(
            User.id == driver_id,
            User.organization_id == current_user.organization_id,
            User.role == "DRIVER",
        )
    )
    driver = res.scalar_one_or_none()
    if not driver:
        raise HTTPException(status_code=404, detail="Conducteur introuvable.")

    driver.is_active = payload.is_active
    await db.commit()
    return {"message": "Statut mis à jour.", "is_active": driver.is_active}


# ─────────────────────────────────────────────
# Alertes
# ─────────────────────────────────────────────

@router.get("/alerts")
async def list_alerts(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("MANAGER", "DRIVER")),
):
    if not current_user.organization_id:
        return {"alerts": []}

    query = (
        select(Alert)
        .where(Alert.organization_id == current_user.organization_id)
        .order_by(Alert.created_at.desc())
    )
    res = await db.execute(query)
    alerts = res.scalars().all()

    return {
        "alerts": [
            {
                "id": str(a.id),
                "severity": a.severity,
                "title": a.title,
                "message": a.message,
                "status": a.status,
                "created_at": a.created_at.isoformat() if a.created_at else None,
                "cargo": {"reference": str(a.cargo_id)[:8]} if a.cargo_id else None,
                "tracker": {"device_id": str(a.tracker_id)[:8]} if a.tracker_id else None,
            }
            for a in alerts
        ]
    }


@router.patch("/alerts/{alert_id}/acknowledge")
async def acknowledge_alert(
    alert_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("MANAGER", "DRIVER")),
):
    res = await db.execute(
        select(Alert).where(
            Alert.id == alert_id,
            Alert.organization_id == current_user.organization_id,
        )
    )
    alert = res.scalar_one_or_none()
    if not alert:
        raise HTTPException(status_code=404, detail="Alerte introuvable.")

    alert.status = "ACKNOWLEDGED"
    alert.acknowledged_at = datetime.now(timezone.utc)
    alert.acknowledged_by = current_user.id
    await db.commit()
    return {"message": "Alerte prise en compte.", "status": alert.status}


# ─────────────────────────────────────────────
# Organisation / Overview
# ─────────────────────────────────────────────

@router.get("/me")
async def get_manager_me(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("MANAGER")),
):
    if not current_user.organization_id:
        return {"organization": None}

    res = await db.execute(
        select(Organization).where(Organization.id == current_user.organization_id)
    )
    org = res.scalar_one_or_none()
    if not org:
        return {"organization": None}

    return {
        "organization": {
            "id": str(org.id),
            "name": org.name,
            "status": org.status,
        }
    }


@router.get("/overview")
async def get_manager_overview(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("MANAGER")),
):
    org_id = current_user.organization_id
    if not org_id:
        return {
            "stats": {
                "drivers": 0,
                "active_drivers": 0,
                "invited_drivers": 0,
                "in_transit": 0,
                "delivered": 0,
                "trackers": 0,
                "active_trackers": 0,
                "open_alerts": 0,
                "co_managers": 0,
            }
        }

    d_total = await db.scalar(
        select(func.count(User.id)).where(User.organization_id == org_id, User.role == "DRIVER")
    ) or 0
    d_active = await db.scalar(
        select(func.count(User.id)).where(
            User.organization_id == org_id,
            User.role == "DRIVER",
            User.account_status == "ACTIVE",
        )
    ) or 0
    d_invited = await db.scalar(
        select(func.count(User.id)).where(
            User.organization_id == org_id,
            User.role == "DRIVER",
            User.account_status == "INVITED",
        )
    ) or 0

    in_transit = await db.scalar(
        select(func.count(Cargo.id)).where(
            Cargo.organization_id == org_id,
            Cargo.status == "IN_TRANSIT",
        )
    ) or 0
    delivered = await db.scalar(
        select(func.count(Cargo.id)).where(
            Cargo.organization_id == org_id,
            Cargo.status == "DELIVERED",
        )
    ) or 0

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
# ─────────────────────────────────────────────
# Trackers
# ─────────────────────────────────────────────

@router.get("/trackers")
async def list_trackers(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("MANAGER")),
):
    if not current_user.organization_id:
        return {"trackers": []}

    res = await db.execute(
        select(Tracker)
        .where(Tracker.organization_id == current_user.organization_id)
        .order_by(Tracker.created_at.desc())
    )
    trackers = res.scalars().all()
    return {
        "trackers": [
            {
                "id": str(t.id),
                "device_id": t.device_id,
                "msisdn": t.msisdn,
                "status": t.status,
                "last_seen_at": t.last_seen_at.isoformat() if t.last_seen_at else None,
                "created_at": t.created_at.isoformat() if t.created_at else None,
            }
            for t in trackers
        ]
    }


class TrackerCreate(BaseModel):
    device_id: str
    vehicle_registration: str | None = None
    msisdn: str | None = None


@router.post("/trackers", status_code=status.HTTP_201_CREATED)
async def create_tracker(
    payload: TrackerCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("MANAGER")),
):
    if not current_user.organization_id:
        raise HTTPException(status_code=400, detail="Manager sans organisation.")

    tracker = Tracker(
        organization_id=current_user.organization_id,
        device_id=payload.device_id,
        msisdn=payload.msisdn,
        status="ACTIVE",
    )
    db.add(tracker)
    await db.commit()
    await db.refresh(tracker)
    return {
        "message": "Tracker enregistré.",
        "tracker": {
            "id": str(tracker.id),
            "device_id": tracker.device_id,
            "status": tracker.status,
        },
    }


# ─────────────────────────────────────────────
# Co-Managers
# ─────────────────────────────────────────────

@router.get("/managers")
async def list_managers(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("MANAGER")),
):
    if not current_user.organization_id:
        return {"managers": []}

    res = await db.execute(
        select(User)
        .where(
            User.organization_id == current_user.organization_id,
            User.role == "MANAGER",
        )
        .order_by(User.created_at.desc())
    )
    managers = res.scalars().all()

    return {
        "managers": [
            {
                "id": str(m.id),
                "first_name": m.first_name,
                "last_name": m.last_name,
                "email": m.email,
                "job_title": m.job_title,
                "phone": m.phone,
                "email_verified": m.email_verified,
                "is_active": m.is_active,
                "account_status": m.account_status,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in managers
        ]
    }


class ManagerInvite(BaseModel):
    first_name: str
    last_name: str
    email: EmailStr
    job_title: str | None = None
    phone: str | None = None


@router.post("/managers/invite", status_code=status.HTTP_201_CREATED)
async def invite_co_manager(
    payload: ManagerInvite,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("MANAGER")),
):
    if not current_user.organization_id:
        raise HTTPException(status_code=400, detail="Manager sans organisation.")

    existing = await db.execute(
        select(User).where(User.email == str(payload.email))
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=409,
            detail="Un compte avec cet email existe déjà."
        )

    token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=48)

    new_mgr = User(
        organization_id=current_user.organization_id,
        first_name=payload.first_name,
        last_name=payload.last_name,
        email=str(payload.email),
        job_title=payload.job_title,
        phone=payload.phone,
        role="MANAGER",
        account_status="INVITED",
        email_verified=False,
        is_active=True,
    )

    db.add(new_mgr)
    await db.flush()

    invitation = AccountInvitation(
        user_id=new_mgr.id,
        token=token,
        expires_at=expires_at,
    )

    db.add(invitation)
    await db.commit()

    settings = get_settings()
    invitation_link = f"{settings.FRONTEND_URL}/set-password?token={token}"

    org_res = await db.execute(
        select(Organization).where(
            Organization.id == current_user.organization_id
        )
    )
    org = org_res.scalar_one_or_none()
    org_name = org.name if org else None

    try:
        send_invitation_email(
            to_email=new_mgr.email,
            first_name=new_mgr.first_name,
            invitation_link=invitation_link,
            org_name=org_name,
        )
    except Exception:
        pass

    return {
        "message": "Invitation envoyée au gestionnaire.",
        "invitation_link": invitation_link,
    }


# ─────────────────────────────────────────────
# Décisions IA (AI Decisions)
# ─────────────────────────────────────────────

@router.get("/ai-decisions")
async def list_ai_decisions(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("MANAGER")),
):
    if not current_user.organization_id:
        return {"decisions": []}

    res = await db.execute(
        select(AgentDecision)
        .join(Cargo, AgentDecision.cargo_id == Cargo.id)
        .where(Cargo.organization_id == current_user.organization_id)
        .order_by(AgentDecision.created_at.desc())
    )

    decisions = res.scalars().all()

    return {
        "decisions": [
            {
                "id": str(d.id),
                "decision": d.decision,
                "reasoning_summary": d.reasoning_summary,
                "confidence": float(d.confidence) if d.confidence else 0.85,
                "requires_human_approval": d.requires_human_approval,
                "status": (
                    "APPROVED"
                    if d.approved_by
                    else (
                        "PENDING"
                        if d.requires_human_approval
                        else "EXECUTED"
                    )
                ),
                "created_at": (
                    d.created_at.isoformat()
                    if d.created_at
                    else None
                ),
                "cargo_reference": str(d.cargo_id)[:8],
                "driver_name": "Conducteur",
            }
            for d in decisions
        ]
    }

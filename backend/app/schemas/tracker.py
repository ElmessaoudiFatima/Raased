"""
Pydantic schemas for Tracker management (manager-scoped).
"""
import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


TRACKER_STATUSES = {"ACTIVE", "INACTIVE", "ASSIGNED", "MAINTENANCE"}


# ─────────────────────────────────────────────
# Create / Register
# ─────────────────────────────────────────────

class TrackerCreate(BaseModel):
    """
    Payload to register a new tracker device.
    Status is always ACTIVE at creation — never chosen by the manager.
    """
    device_id: str                          # IMEI / numéro de série du boîtier physique
    msisdn: str                             # obligatoire — indispensable pour les appels CAMARA
    label: Optional[str] = None             # nom convivial, ex: "Camion Renault 1"


# ─────────────────────────────────────────────
# Update (statut non modifiable ici — voir endpoints dédiés)
# ─────────────────────────────────────────────

class TrackerUpdate(BaseModel):
    """Payload to update tracker fields (all optional). Status changes go through dedicated actions."""
    msisdn: Optional[str] = None
    label: Optional[str] = None


class TrackerMaintenanceUpdate(BaseModel):
    """Dedicated payload to put a tracker in/out of maintenance."""
    in_maintenance: bool


# ─────────────────────────────────────────────
# Assign to cargo
# ─────────────────────────────────────────────

class TrackerAssign(BaseModel):
    cargo_id: uuid.UUID


# ─────────────────────────────────────────────
# Location response
# ─────────────────────────────────────────────

class TrackerLocationOut(BaseModel):
    tracker_id: uuid.UUID
    latitude: float
    longitude: float
    accuracy: Optional[float]
    source: str
    timestamp: datetime

    class Config:
        from_attributes = True


# ─────────────────────────────────────────────
# Response
# ─────────────────────────────────────────────

class CargoTrackerOut(BaseModel):
    id: uuid.UUID
    cargo_id: uuid.UUID
    tracker_id: uuid.UUID
    assigned_at: datetime
    unassigned_at: Optional[datetime]

    class Config:
        from_attributes = True


class TrackerOut(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    device_id: str
    msisdn: str
    label: Optional[str]
    status: str
    last_seen_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
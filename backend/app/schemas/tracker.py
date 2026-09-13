"""
Pydantic schemas for Tracker management (manager-scoped).
"""
import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


# ─────────────────────────────────────────────
# Tracker status values
# ─────────────────────────────────────────────

TRACKER_STATUSES = {"ACTIVE", "INACTIVE", "ASSIGNED", "MAINTENANCE"}


# ─────────────────────────────────────────────
# Create / Register
# ─────────────────────────────────────────────

class TrackerCreate(BaseModel):
    """Payload to register a new tracker device."""
    device_id: str              # Unique device identifier (IMEI or similar)
    msisdn: Optional[str] = None  # Phone number associated with the SIM card
    status: str = "ACTIVE"      # ACTIVE | INACTIVE | MAINTENANCE


# ─────────────────────────────────────────────
# Update
# ─────────────────────────────────────────────

class TrackerUpdate(BaseModel):
    """Payload to update tracker fields (all optional)."""
    msisdn: Optional[str] = None
    status: Optional[str] = None


# ─────────────────────────────────────────────
# Assign to cargo
# ─────────────────────────────────────────────

class TrackerAssign(BaseModel):
    """Payload to assign a tracker to a cargo."""
    cargo_id: uuid.UUID


# ─────────────────────────────────────────────
# Location response
# ─────────────────────────────────────────────

class TrackerLocationOut(BaseModel):
    """Last known location of a tracker."""
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
    """Assignment record between tracker and cargo."""
    id: uuid.UUID
    cargo_id: uuid.UUID
    tracker_id: uuid.UUID
    assigned_at: datetime
    unassigned_at: Optional[datetime]

    class Config:
        from_attributes = True


class TrackerOut(BaseModel):
    """Tracker response representation."""
    id: uuid.UUID
    organization_id: uuid.UUID
    device_id: Optional[str]
    msisdn: Optional[str]
    status: str
    last_seen_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

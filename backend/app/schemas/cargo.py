"""
Pydantic schemas for Cargo management (manager-scoped).
"""
import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


CARGO_STATUSES = {"PENDING", "IN_TRANSIT", "DELIVERED", "DELAYED", "CANCELLED", "ARCHIVED"}
CARGO_CRITICALITIES = {"LOW", "MEDIUM", "HIGH", "CRITICAL"}


# ─────────────────────────────────────────────
# Sub-models for driver & tracker display
# ─────────────────────────────────────────────

class CargoDriverOut(BaseModel):
    id: uuid.UUID
    first_name: str
    last_name: str
    email: Optional[str] = None
    phone: Optional[str] = None

    class Config:
        from_attributes = True


class CargoTrackerOutInfo(BaseModel):
    id: uuid.UUID
    device_id: str
    label: Optional[str] = None
    vehicle_registration: Optional[str] = None
    status: str

    class Config:
        from_attributes = True


# ─────────────────────────────────────────────
# Create
# ─────────────────────────────────────────────

class CargoCreate(BaseModel):
    """Payload to create a new cargo shipment. Reference is auto-generated server-side."""
    corridor_id: uuid.UUID                 # ✏️ le manager sélectionne un corridor existant
    type: str                              # e.g. "MERCHANDISE", "PHARMACEUTICALS", "FUEL"
    criticality: str = "MEDIUM"            # LOW | MEDIUM | HIGH | CRITICAL
    deadline: Optional[datetime] = None
    driver_id: Optional[uuid.UUID] = None
    tracker_id: Optional[uuid.UUID] = None


# ─────────────────────────────────────────────
# Status update
# ─────────────────────────────────────────────

class CargoStatusUpdate(BaseModel):
    status: str


# ─────────────────────────────────────────────
# General update (partial)
# ─────────────────────────────────────────────

class CargoUpdate(BaseModel):
    """Payload to update cargo fields (all optional). Reference is never editable."""
    corridor_id: Optional[uuid.UUID] = None
    type: Optional[str] = None
    criticality: Optional[str] = None
    deadline: Optional[datetime] = None
    driver_id: Optional[uuid.UUID] = None
    tracker_id: Optional[uuid.UUID] = None


# ─────────────────────────────────────────────
# Response
# ─────────────────────────────────────────────

class CargoOut(BaseModel):
    """Cargo response representation."""
    id: uuid.UUID
    organization_id: uuid.UUID
    reference: str
    type: str
    criticality: str
    status: str
    corridor_id: uuid.UUID
    driver_id: Optional[uuid.UUID] = None
    deadline: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    driver: Optional[CargoDriverOut] = None
    tracker: Optional[CargoTrackerOutInfo] = None

    class Config:
        from_attributes = True
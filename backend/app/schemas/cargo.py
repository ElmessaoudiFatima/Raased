"""
Pydantic schemas for Cargo management (manager-scoped).
"""
import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


# ─────────────────────────────────────────────
# Cargo status values
# ─────────────────────────────────────────────

CARGO_STATUSES = {"PENDING", "IN_TRANSIT", "DELIVERED", "DELAYED", "CANCELLED", "ARCHIVED"}
CARGO_CRITICALITIES = {"LOW", "MEDIUM", "HIGH", "CRITICAL"}


# ─────────────────────────────────────────────
# Create
# ─────────────────────────────────────────────

class CargoCreate(BaseModel):
    """Payload to create a new cargo shipment."""
    reference: Optional[str] = None        # Optional unique reference number
    type: str                              # e.g. "MERCHANDISE", "PHARMACEUTICALS", "FUEL"
    criticality: str = "MEDIUM"            # LOW | MEDIUM | HIGH | CRITICAL
    origin: str
    destination: str
    deadline: Optional[datetime] = None    # Expected delivery deadline


# ─────────────────────────────────────────────
# Status update
# ─────────────────────────────────────────────

class CargoStatusUpdate(BaseModel):
    """Payload to update only the status of a cargo."""
    status: str  # PENDING | IN_TRANSIT | DELIVERED | DELAYED | CANCELLED | ARCHIVED


# ─────────────────────────────────────────────
# General update (partial)
# ─────────────────────────────────────────────

class CargoUpdate(BaseModel):
    """Payload to update cargo fields (all optional)."""
    reference: Optional[str] = None
    type: Optional[str] = None
    criticality: Optional[str] = None
    origin: Optional[str] = None
    destination: Optional[str] = None
    deadline: Optional[datetime] = None
    status: Optional[str] = None


# ─────────────────────────────────────────────
# Response
# ─────────────────────────────────────────────

class CargoOut(BaseModel):
    """Cargo response representation."""
    id: uuid.UUID
    organization_id: uuid.UUID
    reference: Optional[str]
    type: str
    criticality: str
    status: str
    origin: str
    destination: str
    deadline: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

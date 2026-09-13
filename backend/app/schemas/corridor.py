"""
Pydantic schemas for Corridor management (manager-scoped).
"""
import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


# ─────────────────────────────────────────────
# GeoJSON helpers (LineString only)
# ─────────────────────────────────────────────

class LineStringGeometry(BaseModel):
    """GeoJSON LineString geometry."""
    type: str = "LineString"
    coordinates: List[List[float]]  # [[lon, lat], [lon, lat], ...]


# ─────────────────────────────────────────────
# Risk level allowed values
# ─────────────────────────────────────────────

RISK_LEVELS = {"LOW", "MEDIUM", "HIGH", "CRITICAL"}


# ─────────────────────────────────────────────
# Create
# ─────────────────────────────────────────────

class CorridorCreate(BaseModel):
    """Payload to create a new corridor for the manager's organisation."""
    name: str
    origin: str
    destination: str
    geometry: LineStringGeometry  # GeoJSON LineString
    risk_level: str = "LOW"


# ─────────────────────────────────────────────
# Update (partial - all fields optional)
# ─────────────────────────────────────────────

class CorridorUpdate(BaseModel):
    """Payload to update an existing corridor (all fields optional)."""
    name: str | None = None
    origin: str | None = None
    destination: str | None = None
    geometry: LineStringGeometry | None = None
    risk_level: str | None = None
    is_active: bool | None = None


# ─────────────────────────────────────────────
# Response
# ─────────────────────────────────────────────

class CorridorOut(BaseModel):
    """Corridor response representation."""
    id: uuid.UUID
    organization_id: uuid.UUID | None
    name: str
    origin: str
    destination: str
    risk_level: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
    geometry: Optional[LineStringGeometry] = None  # GeoJSON LineString, populated by API layer

    class Config:
        from_attributes = True

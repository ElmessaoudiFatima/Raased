from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from geoalchemy2 import Geometry
from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class RiskZone(Base):
    __tablename__ = "risk_zones"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    corridor_id: Mapped[UUID] = mapped_column(ForeignKey("corridors.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    risk_level: Mapped[str] = mapped_column(String(20), nullable=False)
    geometry: Mapped[Geometry] = mapped_column(Geometry(geometry_type="POLYGON", srid=4326), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    corridor: Mapped["Corridor"] = relationship(back_populates="risk_zones")
    known_context_events: Mapped[list["KnownContextEvent"]] = relationship(back_populates="zone")
    geofence_subscriptions: Mapped[list["GeofenceSubscription"]] = relationship(back_populates="zone")

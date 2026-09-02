from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from geoalchemy2 import Geometry
from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Corridor(Base):
    __tablename__ = "corridors"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    origin: Mapped[str] = mapped_column(String(150), nullable=False)
    destination: Mapped[str] = mapped_column(String(150), nullable=False)
    geometry: Mapped[Geometry] = mapped_column(Geometry(geometry_type="LINESTRING", srid=4326), nullable=False)
    risk_level: Mapped[str] = mapped_column(String(20), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    risk_zones: Mapped[list["RiskZone"]] = relationship(back_populates="corridor")
    baselines: Mapped[list["CorridorCongestionBaseline"]] = relationship(back_populates="corridor")
    congestion_events: Mapped[list["CongestionEvent"]] = relationship(back_populates="corridor")
    risk_assessments: Mapped[list["RiskAssessment"]] = relationship(back_populates="corridor")
    original_route_suggestions: Mapped[list["RouteSuggestion"]] = relationship(
        back_populates="original_corridor",
        foreign_keys="RouteSuggestion.original_corridor_id",
    )
    suggested_route_suggestions: Mapped[list["RouteSuggestion"]] = relationship(
        back_populates="suggested_corridor",
        foreign_keys="RouteSuggestion.suggested_corridor_id",
    )

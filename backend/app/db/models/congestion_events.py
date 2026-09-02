from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from geoalchemy2 import Geometry
from sqlalchemy import DECIMAL, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class CongestionEvent(Base):
    __tablename__ = "congestion_events"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tracker_id: Mapped[UUID] = mapped_column(ForeignKey("trackers.id"), nullable=False)
    corridor_id: Mapped[UUID] = mapped_column(ForeignKey("corridors.id"), nullable=False)
    congestion_level: Mapped[str] = mapped_column(String(30), nullable=False)
    confidence_level: Mapped[Decimal | None] = mapped_column(DECIMAL(precision=5, scale=4), nullable=True)
    location: Mapped[Geometry | None] = mapped_column(Geometry(geometry_type="POINT", srid=4326), nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    raw_event_id: Mapped[str | None] = mapped_column(String(150), nullable=True)

    tracker: Mapped["Tracker"] = relationship(back_populates="congestion_events")
    corridor: Mapped["Corridor"] = relationship(back_populates="congestion_events")
    risk_assessments: Mapped[list["RiskAssessment"]] = relationship(back_populates="congestion_event")

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Tracker(Base):
    __tablename__ = "trackers"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False)
    device_id: Mapped[str | None] = mapped_column(String(100), unique=True)
    msisdn: Mapped[str | None] = mapped_column(String(30), nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    organization: Mapped["Organization"] = relationship(back_populates="trackers")
    cargo_trackers: Mapped[list["CargoTracker"]] = relationship(back_populates="tracker")
    tracker_locations: Mapped[list["TrackerLocation"]] = relationship(back_populates="tracker")
    congestion_events: Mapped[list["CongestionEvent"]] = relationship(back_populates="tracker")
    risk_assessments: Mapped[list["RiskAssessment"]] = relationship(back_populates="tracker")
    agent_decisions: Mapped[list["AgentDecision"]] = relationship(back_populates="tracker")
    security_checks: Mapped[list["SecurityCheck"]] = relationship(back_populates="tracker")
    geofence_subscriptions: Mapped[list["GeofenceSubscription"]] = relationship(back_populates="tracker")
    alerts: Mapped[list["Alert"]] = relationship(back_populates="tracker")
    network_actions: Mapped[list["NetworkAction"]] = relationship(back_populates="tracker")

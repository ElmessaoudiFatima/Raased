from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import DECIMAL, DateTime, ForeignKey, JSON, String, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class RiskAssessment(Base):
    __tablename__ = "risk_assessments"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tracker_id: Mapped[UUID] = mapped_column(ForeignKey("trackers.id"), nullable=False)
    cargo_id: Mapped[UUID] = mapped_column(ForeignKey("cargos.id"), nullable=False)
    corridor_id: Mapped[UUID] = mapped_column(ForeignKey("corridors.id"), nullable=False)
    congestion_event_id: Mapped[int] = mapped_column(ForeignKey("congestion_events.id"), nullable=False)
    risk_level: Mapped[str] = mapped_column(String(20), nullable=False)
    risk_score: Mapped[Decimal] = mapped_column(DECIMAL(precision=5, scale=4), nullable=False)
    confidence_score: Mapped[Decimal | None] = mapped_column(DECIMAL(precision=5, scale=4), nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    factors: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    security_snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    tracker: Mapped["Tracker"] = relationship(back_populates="risk_assessments")
    cargo: Mapped["Cargo"] = relationship(back_populates="risk_assessments")
    corridor: Mapped["Corridor"] = relationship(back_populates="risk_assessments")
    congestion_event: Mapped["CongestionEvent"] = relationship(back_populates="risk_assessments")
    agent_decisions: Mapped[list["AgentDecision"]] = relationship(back_populates="risk_assessment")
    alerts: Mapped[list["Alert"]] = relationship(back_populates="risk_assessment")
    network_actions: Mapped[list["NetworkAction"]] = relationship(back_populates="risk_assessment")

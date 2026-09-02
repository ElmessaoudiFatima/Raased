from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DECIMAL, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class AgentDecision(Base):
    __tablename__ = "agent_decisions"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    risk_assessment_id: Mapped[UUID] = mapped_column(ForeignKey("risk_assessments.id"), nullable=False)
    tracker_id: Mapped[UUID] = mapped_column(ForeignKey("trackers.id"), nullable=False)
    cargo_id: Mapped[UUID] = mapped_column(ForeignKey("cargos.id"), nullable=False)
    decision: Mapped[str] = mapped_column(String(40), nullable=False)
    reasoning_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[Decimal | None] = mapped_column(DECIMAL(precision=5, scale=4), nullable=True)
    requires_human_approval: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    approved_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    risk_assessment: Mapped["RiskAssessment"] = relationship(back_populates="agent_decisions")
    tracker: Mapped["Tracker"] = relationship(back_populates="agent_decisions")
    cargo: Mapped["Cargo"] = relationship(back_populates="agent_decisions")
    approved_by_user: Mapped["User | None"] = relationship(
        back_populates="approved_decisions",
        foreign_keys=["AgentDecision.approved_by"],
    )
    route_suggestions: Mapped[list["RouteSuggestion"]] = relationship(back_populates="agent_decision")

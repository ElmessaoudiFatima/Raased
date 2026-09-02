from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, JSON, String, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class NetworkAction(Base):
    __tablename__ = "network_actions"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tracker_id: Mapped[UUID] = mapped_column(ForeignKey("trackers.id"), nullable=False)
    risk_assessment_id: Mapped[UUID] = mapped_column(ForeignKey("risk_assessments.id"), nullable=False)
    action_type: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    executed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    request_id: Mapped[str | None] = mapped_column(String(150), nullable=True)
    response: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    tracker: Mapped["Tracker"] = relationship(back_populates="network_actions")
    risk_assessment: Mapped["RiskAssessment"] = relationship(back_populates="network_actions")

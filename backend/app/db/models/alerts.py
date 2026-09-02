from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False)
    cargo_id: Mapped[UUID] = mapped_column(ForeignKey("cargos.id"), nullable=False)
    tracker_id: Mapped[UUID] = mapped_column(ForeignKey("trackers.id"), nullable=False)
    risk_assessment_id: Mapped[UUID] = mapped_column(ForeignKey("risk_assessments.id"), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    acknowledged_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)

    organization: Mapped["Organization"] = relationship(back_populates="alerts")
    cargo: Mapped["Cargo"] = relationship(back_populates="alerts")
    tracker: Mapped["Tracker"] = relationship(back_populates="alerts")
    risk_assessment: Mapped["RiskAssessment"] = relationship(back_populates="alerts")
    acknowledged_by_user: Mapped["User | None"] = relationship(
        back_populates="acknowledged_alerts",
        foreign_keys=["Alert.acknowledged_by"],
    )

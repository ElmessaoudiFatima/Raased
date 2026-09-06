"""
Alerte de sécurité, distincte des alertes de risque congestion (`Alert`).

Une `SecurityAlert` naît d'un `SecurityCheck` (SIM swap, device swap, etc.)
et concerne l'intégrité d'un tracker, pas une évaluation de risque de
congestion : elle n'a donc ni cargo_id ni risk_assessment_id.
"""
from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class SecurityAlert(Base):
    __tablename__ = "security_alerts"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False)
    tracker_id: Mapped[UUID] = mapped_column(ForeignKey("trackers.id"), nullable=False)
    security_check_id: Mapped[UUID | None] = mapped_column(ForeignKey("security_checks.id"), nullable=True)
    check_type: Mapped[str] = mapped_column(String(30), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    organization: Mapped["Organization"] = relationship(back_populates="security_alerts")
    tracker: Mapped["Tracker"] = relationship(back_populates="security_alerts")
    security_check: Mapped["SecurityCheck | None"] = relationship(back_populates="security_alerts")

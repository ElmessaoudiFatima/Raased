from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Cargo(Base):
    __tablename__ = "cargos"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False)
    reference: Mapped[str | None] = mapped_column(String(100), unique=True)
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    criticality: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    origin: Mapped[str] = mapped_column(String(150), nullable=False)
    destination: Mapped[str] = mapped_column(String(150), nullable=False)
    deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    organization: Mapped["Organization"] = relationship(back_populates="cargos")
    cargo_trackers: Mapped[list["CargoTracker"]] = relationship(back_populates="cargo")
    risk_assessments: Mapped[list["RiskAssessment"]] = relationship(back_populates="cargo")
    agent_decisions: Mapped[list["AgentDecision"]] = relationship(back_populates="cargo")
    alerts: Mapped[list["Alert"]] = relationship(back_populates="cargo")

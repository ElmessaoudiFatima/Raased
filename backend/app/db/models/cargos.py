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

    
    reference: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)

    type: Mapped[str] = mapped_column(String(50), nullable=False)
    criticality: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)

    
    corridor_id: Mapped[UUID] = mapped_column(ForeignKey("corridors.id"), nullable=False)
    driver_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    organization: Mapped["Organization"] = relationship(back_populates="cargos")
    corridor: Mapped["Corridor"] = relationship(back_populates="cargos")
    driver: Mapped["User | None"] = relationship(foreign_keys=[driver_id], lazy="selectin")
    cargo_trackers: Mapped[list["CargoTracker"]] = relationship(back_populates="cargo", lazy="selectin")
    risk_assessments: Mapped[list["RiskAssessment"]] = relationship(back_populates="cargo")
    agent_decisions: Mapped[list["AgentDecision"]] = relationship(back_populates="cargo")
    alerts: Mapped[list["Alert"]] = relationship(back_populates="cargo")

    @property
    def tracker(self) -> "Tracker | None":
        """Retourne le tracker actif actuellement associé à ce cargo."""
        for ct in self.cargo_trackers:
            if ct.unassigned_at is None and ct.tracker is not None:
                return ct.tracker
        return None
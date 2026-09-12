from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class CargoTracker(Base):
    __tablename__ = "cargo_trackers"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    cargo_id: Mapped[UUID] = mapped_column(ForeignKey("cargos.id"), nullable=False)
    tracker_id: Mapped[UUID] = mapped_column(ForeignKey("trackers.id"), nullable=False)
    assigned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    unassigned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    cargo: Mapped["Cargo"] = relationship(back_populates="cargo_trackers")
    tracker: Mapped["Tracker"] = relationship(back_populates="cargo_trackers", lazy="selectin")

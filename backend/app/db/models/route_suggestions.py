from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class RouteSuggestion(Base):
    __tablename__ = "route_suggestions"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    agent_decision_id: Mapped[UUID] = mapped_column(ForeignKey("agent_decisions.id"), nullable=False)
    original_corridor_id: Mapped[UUID] = mapped_column(ForeignKey("corridors.id"), nullable=False)
    suggested_corridor_id: Mapped[UUID] = mapped_column(ForeignKey("corridors.id"), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    accepted: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    agent_decision: Mapped["AgentDecision"] = relationship(back_populates="route_suggestions")
    original_corridor: Mapped["Corridor"] = relationship(
        back_populates="original_route_suggestions",
        foreign_keys="RouteSuggestion.original_corridor_id",
    )
    suggested_corridor: Mapped["Corridor"] = relationship(
        back_populates="suggested_route_suggestions",
        foreign_keys="RouteSuggestion.suggested_corridor_id",
    )

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, String, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)

    # --- Informations entreprise ---
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    legal_id: Mapped[str] = mapped_column(String(50), nullable=False)          
    country: Mapped[str] = mapped_column(String(100), nullable=False, default="Maroc")
    city: Mapped[str] = mapped_column(String(100), nullable=False)
    phone: Mapped[str] = mapped_column(String(30), nullable=False)
    address: Mapped[str] = mapped_column(Text, nullable=False)
    website: Mapped[str | None] = mapped_column(String(255), nullable=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False)            

    # --- Statut de validation de la demande d'inscription ---
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="PENDING")
    # PENDING | APPROVED | REJECTED
    reviewed_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow,
    )

    users: Mapped[list["User"]] = relationship(back_populates="organization", foreign_keys="User.organization_id")
    corridors: Mapped[list["Corridor"]] = relationship(back_populates="organization")
    cargos: Mapped[list["Cargo"]] = relationship(back_populates="organization")
    trackers: Mapped[list["Tracker"]] = relationship(back_populates="organization")
    alerts: Mapped[list["Alert"]] = relationship(back_populates="organization")
    security_alerts: Mapped[list["SecurityAlert"]] = relationship(back_populates="organization")
    audit_logs: Mapped[list["AuditLog"]] = relationship(back_populates="organization")
    documents: Mapped[list["OrganizationDocument"]] = relationship(back_populates="organization")
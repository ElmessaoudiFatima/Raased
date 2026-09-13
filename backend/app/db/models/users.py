from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)

    organization_id: Mapped[UUID | None] = mapped_column(ForeignKey("organizations.id"), nullable=True)

    # --- Identité ---
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    job_title: Mapped[str | None] = mapped_column(String(100), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(30), nullable=True)

    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)

    
    password: Mapped[str | None] = mapped_column(String, nullable=True)

    role: Mapped[str] = mapped_column(String(30), nullable=False)

    # --- Vérification email  ---
    email_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

     
    account_status: Mapped[str] = mapped_column(String(20), nullable=False, default="ACTIVE")
    # INVITED | ACTIVE | DISABLED

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow,
    )

    # =========================
    # Relationships
    # =========================

    organization: Mapped["Organization"] = relationship(
        back_populates="users", foreign_keys=[organization_id], lazy="selectin"
    )

    acknowledged_alerts: Mapped[list["Alert"]] = relationship(back_populates="acknowledged_by_user")

    approved_decisions: Mapped[list["AgentDecision"]] = relationship(
        back_populates="approved_by_user",
        foreign_keys="AgentDecision.approved_by",
    )

    audit_logs: Mapped[list["AuditLog"]] = relationship(back_populates="user")

    verification_codes: Mapped[list["EmailVerificationCode"]] = relationship(back_populates="user")

    invitations: Mapped[list["AccountInvitation"]] = relationship(back_populates="user")

    __table_args__ = (
        CheckConstraint(
            """
            (role = 'ADMIN' AND organization_id IS NULL)
            OR
            (role IN ('MANAGER', 'DRIVER') AND organization_id IS NOT NULL)
            """,
            name="ck_user_role_organization",
        ),
        CheckConstraint(
            """
            (account_status = 'INVITED' AND password IS NULL)
            OR
            (account_status IN ('ACTIVE', 'DISABLED') AND password IS NOT NULL)
            """,
            name="ck_user_account_status_password",
        ),
    )
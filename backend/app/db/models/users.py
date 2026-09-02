from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    # ADMIN => NULL
    # MANAGER / DRIVER => organization obligatoire
    organization_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("organizations.id"),
        nullable=True,
    )

    name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )

    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
    )

    password: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )

    role: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    # =========================
    # Relationships
    # =========================

    organization: Mapped["Organization"] = relationship(
        back_populates="users"
    )

    acknowledged_alerts: Mapped[list["Alert"]] = relationship(
        back_populates="acknowledged_by_user"
    )

    approved_decisions: Mapped[list["AgentDecision"]] = relationship(
        back_populates="approved_by_user",
        foreign_keys="AgentDecision.approved_by",
    )

    audit_logs: Mapped[list["AuditLog"]] = relationship(
        back_populates="user"
    )

    # =========================
    # Database constraints
    # =========================

    __table_args__ = (
        CheckConstraint(
            """
            (role = 'ADMIN' AND organization_id IS NULL)
            OR
            (role IN ('MANAGER', 'DRIVER') AND organization_id IS NOT NULL)
            """,
            name="ck_user_role_organization",
        ),
    )
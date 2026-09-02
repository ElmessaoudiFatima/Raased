from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class GeofenceSubscription(Base):
    __tablename__ = "geofence_subscriptions"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tracker_id: Mapped[UUID] = mapped_column(ForeignKey("trackers.id"), nullable=False)
    zone_id: Mapped[UUID] = mapped_column(ForeignKey("risk_zones.id"), nullable=False)
    webhook_url: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    external_subscription_id: Mapped[str | None] = mapped_column(String(150), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    tracker: Mapped["Tracker"] = relationship(back_populates="geofence_subscriptions")
    zone: Mapped["RiskZone"] = relationship(back_populates="geofence_subscriptions")

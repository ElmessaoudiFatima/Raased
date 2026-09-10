"""
Relevé météo ponctuel pour un corridor (Open-Meteo).

Persisté plutôt que consommé à la volée, pour deux raisons :
1. Traçabilité : si une décision du Decision Engine tient compte de la
   météo, on doit pouvoir reconstituer après coup ce qui a été observé au
   moment de la décision — un appel API live ne le permet pas.
2. Cache : Open-Meteo ne change pas minute par minute ; on évite des appels
   redondants en réutilisant un relevé récent (voir app/weather/weather.py).
"""
from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class WeatherSnapshot(Base):
    __tablename__ = "weather_snapshots"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    corridor_id: Mapped[UUID] = mapped_column(ForeignKey("corridors.id"), nullable=False)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    temperature_c: Mapped[float | None] = mapped_column(Float, nullable=True)
    wind_speed_kmh: Mapped[float | None] = mapped_column(Float, nullable=True)
    visibility_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    weather_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    degraded_conditions: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    corridor: Mapped["Corridor"] = relationship(back_populates="weather_snapshots")
    risk_assessments: Mapped[list["RiskAssessment"]] = relationship(back_populates="weather_snapshot")

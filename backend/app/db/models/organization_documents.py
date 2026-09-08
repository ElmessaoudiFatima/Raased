"""
Documents optionnels uploadés (certificat entreprise, CNI/passeport
du responsable) — utilisés uniquement pour la vérification manuelle de la demande.
"""
from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class OrganizationDocument(Base):
    __tablename__ = "organization_documents"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False)

    document_type: Mapped[str] = mapped_column(String(50), nullable=False)
    # COMPANY_CERTIFICATE | RESPONSIBLE_ID
    file_url: Mapped[str] = mapped_column(Text, nullable=False)

    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    organization: Mapped["Organization"] = relationship(back_populates="documents")
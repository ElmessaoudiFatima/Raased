"""
Service de gestion des documents justificatifs pour l'inscription des organisations :
  - Validation du format (PDF, JPG, PNG) et de la taille (max 10 Mo)
  - Stockage local sécurisé
  - Enregistrement dans la table organization_documents
"""
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.organization_documents import OrganizationDocument
from app.db.models.organizations import Organization

# Contraintes de validation
MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10 Mo
ALLOWED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png"}
ALLOWED_MIME_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/png",
    "image/pjpeg",
}

VALID_DOCUMENT_TYPES = {
    "COMPANY_CERTIFICATE",
    "RESPONSIBLE_ID",
}

# Dossier de base de stockage
UPLOAD_ROOT_DIR = Path("uploads/documents")


def _sanitize_extension(filename: str) -> str:
    """Extrait et valide l'extension du fichier."""
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file format ({ext}). Allowed formats: PDF, JPG, PNG.",
        )
    return ext


async def validate_and_read_file(file: UploadFile) -> tuple[bytes, str]:
    """
    Vérifie le type MIME, l'extension et la taille du fichier.
    Retourne le contenu binaire et l'extension validée.
    """
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provided file does not have a valid name.",
        )

    ext = _sanitize_extension(file.filename)

    # Vérification MIME type si fourni
    if file.content_type and file.content_type.lower() not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"MIME type '{file.content_type}' is not supported. Allowed formats: PDF, JPG, PNG.",
        )

    content = await file.read()
    if len(content) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File is empty.",
        )

    if len(content) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File size ({len(content) / (1024 * 1024):.1f} MB) exceeds allowed limit of 10 MB.",
        )

    return content, ext


async def save_organization_document(
    db: AsyncSession,
    organization_id: UUID,
    document_type: str,
    file: UploadFile,
) -> OrganizationDocument:
    """
    Sauvegarde un document sur le disque et en base de données.
    Si un document du même type existe déjà pour cette organisation,
    il est remplacé (ancien fichier supprimé du disque).
    """
    if document_type not in VALID_DOCUMENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid document type '{document_type}'. Allowed values: {list(VALID_DOCUMENT_TYPES)}",
        )

    # Vérifier que l'organisation existe
    org_result = await db.execute(select(Organization).where(Organization.id == organization_id))
    org = org_result.scalar_one_or_none()
    if org is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found.",
        )

    content, ext = await validate_and_read_file(file)

    # Créer le répertoire cible uploads/documents/{org_id}/
    target_dir = UPLOAD_ROOT_DIR / str(organization_id)
    target_dir.mkdir(parents=True, exist_ok=True)

    # Nom de fichier unique pour éviter toute collision
    unique_name = f"{document_type.lower()}_{uuid.uuid4().hex[:8]}{ext}"
    file_path = target_dir / unique_name

    # Écriture du fichier sur disque
    with open(file_path, "wb") as f:
        f.write(content)

    rel_file_url = str(file_path.as_posix())

    # Vérifier si un document du même type existait déjà pour le remplacer
    existing_result = await db.execute(
        select(OrganizationDocument).where(
            OrganizationDocument.organization_id == organization_id,
            OrganizationDocument.document_type == document_type,
        )
    )
    existing_doc = existing_result.scalar_one_or_none()

    if existing_doc:
        # Supprimer l'ancien fichier physique si existant
        try:
            old_path = Path(existing_doc.file_url)
            if old_path.exists():
                old_path.unlink()
        except Exception:
            pass

        existing_doc.file_url = rel_file_url
        existing_doc.uploaded_at = datetime.now(timezone.utc)
        doc = existing_doc
    else:
        doc = OrganizationDocument(
            organization_id=organization_id,
            document_type=document_type,
            file_url=rel_file_url,
            uploaded_at=datetime.now(timezone.utc),
        )
        db.add(doc)

    await db.commit()
    await db.refresh(doc)
    return doc


def get_document_file_path(doc: OrganizationDocument) -> Path:
    """Retourne le chemin Path absolu et vérifie l'existence du fichier physique."""
    path = Path(doc.file_url)
    if not path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Requested file was not found on server.",
        )
    return path

"""
Endpoints réservés à l'admin :
  GET  /admin/organizations              → liste (filtrable par ?status=)
  GET  /admin/organizations/{id}         → détail org + manager
  PATCH /admin/organizations/{id}/approve → approuver la demande
  PATCH /admin/organizations/{id}/reject  → rejeter la demande
"""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.api.deps import get_current_user, require_role
from app.db.models.organization_documents import OrganizationDocument
from app.db.models.users import User
from app.db.session import get_db

from app.schemas.auth import (
    OrganizationDetailOut,
    OrganizationDocumentOut,
    OrganizationOut,
    OrganizationRejectRequest,
    ManagerSummary,
)
from app.services.admin_service import (
    approve_organization,
    get_document_by_id,
    get_organization_with_manager,
    list_organizations,
    reject_organization,
)
from app.services.document_service import get_document_file_path

router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    dependencies=[Depends(require_role("ADMIN"))],
)

from app.db.models.users import User
from app.services import admin_service

# ─────────────────────────────────────────────
# Liste des organisations
# ─────────────────────────────────────────────

@router.get(
    "/organizations",
    summary="List organizations (filterable by status)",
)
async def list_orgs(
    status: str | None = Query(
        default=None,
        description="Filter by status: PENDING | APPROVED | REJECTED",
        pattern="^(PENDING|APPROVED|REJECTED)$",
    ),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns all organizations.
    Use `?status=PENDING` to list only pending registration requests.
    """
    orgs = await list_organizations(db, status=status)
    data = []
    for org in orgs:
        res_m = await db.execute(
            select(User).where(User.organization_id == org.id, User.role == "MANAGER").limit(1)
        )
        mgr = res_m.scalar_one_or_none()

        res_d = await db.execute(
            select(func.count(OrganizationDocument.id)).where(OrganizationDocument.organization_id == org.id)
        )
        doc_count = res_d.scalar() or 0

        item = {
            "id": org.id,
            "name": org.name,
            "legal_id": org.legal_id,
            "country": org.country,
            "city": org.city,
            "phone": org.phone,
            "address": org.address,
            "website": org.website,
            "email": org.email,
            "status": org.status,
            "rejection_reason": org.rejection_reason,
            "reviewed_at": org.reviewed_at,
            "created_at": org.created_at,
            "manager": {
                "id": mgr.id,
                "first_name": mgr.first_name,
                "last_name": mgr.last_name,
                "email": mgr.email,
                "job_title": mgr.job_title,
                "phone": mgr.phone,
                "email_verified": mgr.email_verified,
            } if mgr else None,
            "documents_count": doc_count,
        }
        data.append(item)
    return {"organizations": data}


# ─────────────────────────────────────────────
# Détail d'une organisation
# ─────────────────────────────────────────────

@router.get(
    "/organizations/{org_id}",
    summary="Get organization details with manager and supporting documents",
)
async def get_org(org_id: UUID, db: AsyncSession = Depends(get_db)):
    """
    Returns detailed organization information including primary manager details
    and uploaded verification documents.
    """
    result = await get_organization_with_manager(db, org_id)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found.",
        )
    org, manager = result

    docs_out = [
        {
            "id": d.id,
            "organization_id": d.organization_id,
            "document_type": d.document_type,
            "file_url": d.file_url,
            "download_url": f"/api/v1/admin/documents/{d.id}/download",
            "uploaded_at": d.uploaded_at,
        }
        for d in (org.documents or [])
    ]

    item = {
        "id": org.id,
        "name": org.name,
        "legal_id": org.legal_id,
        "country": org.country,
        "city": org.city,
        "phone": org.phone,
        "address": org.address,
        "website": org.website,
        "email": org.email,
        "status": org.status,
        "rejection_reason": org.rejection_reason,
        "reviewed_at": org.reviewed_at,
        "created_at": org.created_at,
        "manager": {
            "id": manager.id,
            "first_name": manager.first_name,
            "last_name": manager.last_name,
            "email": manager.email,
            "job_title": manager.job_title,
            "phone": manager.phone,
            "email_verified": manager.email_verified,
        } if manager else None,
        "documents": docs_out,
    }

    return {"organization": item}



# ─────────────────────────────────────────────
# Téléchargement d'un document justificatif
# ─────────────────────────────────────────────

@router.get(
    "/documents/{document_id}/download",
    summary="Download or preview a supporting document (Admin only)",
)
async def download_document(
    document_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    Download or preview an uploaded verification document by document ID.
    Returns the file inline with appropriate content type for previewing.
    """
    doc = await get_document_by_id(db, document_id)
    if doc is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found.",
        )

    file_path = get_document_file_path(doc)

    ext = file_path.suffix.lower()
    media_type = "application/octet-stream"
    if ext == ".pdf":
        media_type = "application/pdf"
    elif ext in [".jpg", ".jpeg"]:
        media_type = "image/jpeg"
    elif ext == ".png":
        media_type = "image/png"

    return FileResponse(
        path=str(file_path),
        media_type=media_type,
        filename=file_path.name,
        headers={"Content-Disposition": f'inline; filename="{file_path.name}"'},
    )


# ─────────────────────────────────────────────
# Approuver une organisation
# ─────────────────────────────────────────────

@router.patch(
    "/organizations/{org_id}/approve",
    response_model=OrganizationOut,
    summary="Approve organization registration request",
)
async def approve_org(
    org_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Approves a pending organization registration request and activates manager access.
    """
    org = await approve_organization(db, org_id, reviewed_by_id=current_user.id)
    if org is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found.",
        )
    if org.status != "APPROVED":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Organization is already in status '{org.status}'.",
        )
    return org


# ─────────────────────────────────────────────
# Rejeter une organisation
# ─────────────────────────────────────────────

@router.patch(
    "/organizations/{org_id}/reject",
    response_model=OrganizationOut,
    summary="Reject organization registration request",
)
async def reject_org(
    org_id: UUID,
    payload: OrganizationRejectRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Rejects a pending organization registration request with a reason
    and deactivates associated manager accounts.
    """
    org = await reject_organization(
        db,
        org_id,
        reviewed_by_id=current_user.id,
        rejection_reason=payload.rejection_reason,
    )
    if org is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found.",
        )
    if org.status != "REJECTED":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Organization is already in status '{org.status}'.",
        )
    return org
class UserStatusUpdate(BaseModel):
    action: str  # "enable" | "disable"


@router.get("/stats", summary="Global admin dashboard stats")
async def get_stats(db: AsyncSession = Depends(get_db)):
    return {"stats": await admin_service.get_admin_stats(db)}


@router.get("/users", summary="List all platform users")
async def list_users(db: AsyncSession = Depends(get_db)):
    return {"users": await admin_service.list_all_users(db)}


@router.patch("/users/{user_id}/status", summary="Enable or disable a user account")
async def patch_user_status(
    user_id: UUID,
    payload: UserStatusUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        user = await admin_service.update_user_status(db, user_id, payload.action, current_user)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    return {"message": "Status updated.", "is_active": user.is_active}


@router.delete("/users/{user_id}", summary="Permanently delete a user account")
async def remove_user(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        deleted = await admin_service.delete_user(db, user_id, current_user)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    return {"message": "User deleted successfully."}


@router.get("/audit", summary="Full audit log")
async def get_audit_log(db: AsyncSession = Depends(get_db)):
    return {"logs": await admin_service.list_audit_logs(db)}
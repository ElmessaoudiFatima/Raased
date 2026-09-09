from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models.organizations import Organization
from app.db.models.users import User
from app.db.session import get_db
from app.api.deps import require_role
from app.schemas.auth import DriverCreate, DriverCreateResponse
from app.services.auth_service import create_driver
from app.services.email_service import send_invitation_email

router = APIRouter(
    prefix="/manager",
    tags=["manager"],
)


@router.post(
    "/drivers",
    response_model=DriverCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Invite and create a driver account for the manager's organization",
)
async def create_org_driver(
    payload: DriverCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("MANAGER")),
):
    """
    Creates a new driver user with account_status='INVITED' and sends an invitation
    link by email to set up their password.
    """
    if current_user.organization_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Le manager n'est rattaché à aucune organisation.",
        )

    # Récupérer le nom de l'organisation pour personnaliser l'email
    org_res = await db.execute(
        select(Organization).where(Organization.id == current_user.organization_id)
    )
    org = org_res.scalar_one_or_none()
    org_name = org.name if org else None

    driver, invitation_token = await create_driver(
        db,
        organization_id=current_user.organization_id,
        first_name=payload.first_name,
        last_name=payload.last_name,
        email=str(payload.email),
        phone=payload.phone,
    )

    settings = get_settings()
    invitation_link = f"{settings.FRONTEND_URL}/set-password?token={invitation_token}"

    send_invitation_email(
        to_email=driver.email,
        first_name=driver.first_name,
        invitation_link=invitation_link,
        org_name=org_name,
    )

    return driver
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.api.deps import require_role
from app.schemas.auth import DriverCreate, UserOut
from app.services.auth_service import create_driver
from app.db.models.users import User

router = APIRouter(prefix="/manager", tags=["manager"], dependencies=[Depends(require_role("MANAGER"))])


@router.post("/drivers", response_model=UserOut)
async def create_org_driver(
    payload: DriverCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("MANAGER")),
):
    # organization_id imposé = celle du manager connecté, jamais depuis le body
    driver = await create_driver(
        db,
        organization_id=current_user.organization_id,
        name=payload.name,
        email=payload.email,
        password=payload.password,
    )
    return driver
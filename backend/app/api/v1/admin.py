from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.api.deps import require_role
from app.schemas.auth import OrganizationCreate, OrganizationOut, ManagerCreate, UserOut
from app.services.auth_service import create_organization, create_manager

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_role("ADMIN"))])


@router.post("/organizations", response_model=OrganizationOut)
async def create_org(payload: OrganizationCreate, db: AsyncSession = Depends(get_db)):
    org = await create_organization(db, payload.name)
    return org


@router.post("/managers", response_model=UserOut)
async def create_org_manager(payload: ManagerCreate, db: AsyncSession = Depends(get_db)):
    manager = await create_manager(
        db,
        organization_id=payload.organization_id,
        name=payload.name,
        email=payload.email,
        password=payload.password,
    )
    return manager
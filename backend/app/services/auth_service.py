from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password, verify_password
from app.db.models.organizations import Organization
from app.db.models.users import User


async def authenticate_user(db: AsyncSession, email: str, password: str) -> User | None:
	result = await db.execute(select(User).where(User.email == email))
	user = result.scalar_one_or_none()
	if user is None or not user.is_active or not verify_password(password, user.password):
		return None
	return user


async def create_organization(db: AsyncSession, name: str) -> Organization:
	organization = Organization(name=name)
	db.add(organization)
	await db.commit()   
	await db.refresh(organization)
	return organization


async def create_manager(
	db: AsyncSession,
	organization_id: UUID,
	name: str,
	email: str,
	password: str,
) -> User:
	manager = User(
		organization_id=organization_id,
		name=name,
		email=email,
		password=hash_password(password),
		role="MANAGER",
		is_active=True,
	)
	db.add(manager)
	await db.flush()
	await db.refresh(manager)
	return manager


async def create_driver(
	db: AsyncSession,
	organization_id: UUID,
	name: str,
	email: str,
	password: str,
) -> User:
	driver = User(
		organization_id=organization_id,
		name=name,
		email=email,
		password=hash_password(password),
		role="DRIVER",
		is_active=True,
	)
	db.add(driver)
	await db.flush()
	await db.refresh(driver)
	return driver

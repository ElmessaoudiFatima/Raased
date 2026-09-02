"""
Moteur SQLAlchemy async + fabrique de sessions (PostgreSQL + PostGIS).
"""
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.core.config import get_settings

settings = get_settings()

engine = create_async_engine(settings.DATABASE_URL, echo=settings.DEBUG, future=True)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
    class_=AsyncSession,
)


async def get_db() -> AsyncSession:
    """Dépendance FastAPI qui fournit une session DB par requête."""
    async with AsyncSessionLocal() as session:
        yield session
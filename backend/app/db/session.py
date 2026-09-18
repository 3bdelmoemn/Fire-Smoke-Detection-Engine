"""
Async SQLAlchemy engine and session factory.

Usage in FastAPI dependencies::

    async def get_db() -> AsyncGenerator[AsyncSession, None]:
        async with async_session_factory() as session:
            yield session
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings

settings = get_settings()

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    future=True,
    # SQLite-specific: allow same connection across threads for dev simplicity
    connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {},
)

async_session_factory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def init_db() -> None:
    """Create all tables (used for quick startup; prefer Alembic in production)."""
    from app.db.base import Base
    # Import all models so they register on Base.metadata
    import app.models.user  # noqa: F401
    import app.models.detection_event  # noqa: F401
    import app.models.alert  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

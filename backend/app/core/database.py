"""Async SQLAlchemy engine setup with read/write separation."""

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings

settings = get_settings()


def _create_engine(url: str) -> AsyncEngine:
    """Create an async engine with connection pooling."""
    return create_async_engine(
        url,
        pool_size=settings.DB_POOL_SIZE,
        max_overflow=settings.DB_MAX_OVERFLOW,
        pool_recycle=settings.DB_POOL_RECYCLE,
        echo=settings.DB_ECHO,
        pool_pre_ping=True,
    )


# Write engine (primary)
write_engine: AsyncEngine = _create_engine(settings.DATABASE_URL)

# Read engine (replica or fallback to primary)
read_engine: AsyncEngine = _create_engine(settings.database_read_url)

# Session factories
WriteSession = async_sessionmaker(
    bind=write_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

ReadSession = async_sessionmaker(
    bind=read_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""

    pass


async def get_write_session() -> AsyncSession:
    """Yield a write session and ensure cleanup."""
    async with WriteSession() as session:
        try:
            yield session  # type: ignore[misc]
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_read_session() -> AsyncSession:
    """Yield a read-only session."""
    async with ReadSession() as session:
        yield session  # type: ignore[misc]


async def close_engines() -> None:
    """Dispose of all engine connections (used during shutdown)."""
    await write_engine.dispose()
    await read_engine.dispose()

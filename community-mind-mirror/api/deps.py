"""Dependency injection for FastAPI routes."""

from sqlalchemy.ext.asyncio import AsyncSession

from database.connection import async_session


async def get_db() -> AsyncSession:
    """Yield an async database session."""
    async with async_session() as session:
        yield session

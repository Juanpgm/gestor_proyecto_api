"""FastAPI dependency that yields a managed AsyncSession."""

from __future__ import annotations

from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from core_db.engine import AsyncSessionLocal


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield a database session, committing on success and rolling back on error."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

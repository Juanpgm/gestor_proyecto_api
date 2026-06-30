"""Async SQLAlchemy engine and session factory."""

from __future__ import annotations

import functools

from sqlalchemy.pool import NullPool
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from core_db.settings import get_db_settings


@functools.lru_cache(maxsize=1)
def get_engine():
    """Return a cached async engine built from DbSettings.

    Uses NullPool: connections are opened per-checkout and closed on return.
    This is the recommended setup behind an external pooler (PgBouncer / Neon's
    pooled endpoint), and it also avoids asyncpg connections being reused across
    different event loops (which breaks under repeated asyncio.run, e.g. tests).
    connect_args statement_cache_size=0 keeps compatibility with transaction
    pooling.
    """
    settings = get_db_settings()
    return create_async_engine(
        settings.database_url,
        echo=settings.db_echo,
        poolclass=NullPool,
        connect_args={"statement_cache_size": 0},
    )


def _make_session_factory() -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(
        bind=get_engine(),
        expire_on_commit=False,
        class_=AsyncSession,
    )


# Module-level session factory; bound lazily so the engine is only created
# when first accessed (respects lru_cache on get_engine).
AsyncSessionLocal: async_sessionmaker[AsyncSession] = _make_session_factory()

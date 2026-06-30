"""Fixtures for integration tests that need a live Postgres + PostGIS.

These tests run against the database from ``back/docker-compose.dev.yml``.
If the database is not reachable they SKIP (not fail), so the unit suite stays
runnable without Docker. Bring the DB up with:

    docker compose -f docker-compose.dev.yml up -d
    DATABASE_URL=postgresql+asyncpg://calitrack:calitrack@localhost:5433/calitrack_dev \\
        python -m alembic upgrade head
"""

import asyncio
import os

import pytest

try:
    import asyncpg
except ImportError:  # pragma: no cover - asyncpg is a project dependency
    asyncpg = None

DEFAULT_URL = "postgresql+asyncpg://calitrack:calitrack@localhost:5433/calitrack_dev"


def dsn() -> str:
    """Plain (driver-less) DSN for asyncpg from DATABASE_URL."""
    url = os.environ.get("DATABASE_URL", DEFAULT_URL)
    return url.replace("+asyncpg", "")


def run(coro):
    """Run a coroutine to completion in a throwaway event loop."""
    return asyncio.run(coro)


async def _can_connect() -> bool:
    if asyncpg is None:
        return False
    try:
        conn = await asyncpg.connect(dsn())
        await conn.close()
        return True
    except Exception:
        return False


@pytest.fixture(scope="session")
def pg_available():
    """Skip the whole integration test if Postgres is not reachable."""
    if not run(_can_connect()):
        pytest.skip(
            "Postgres+PostGIS not reachable. Start it with "
            "`docker compose -f docker-compose.dev.yml up -d` and run alembic."
        )
    return True

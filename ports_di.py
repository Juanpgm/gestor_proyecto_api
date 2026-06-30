"""Dependency-injection seam for the data backend.

Lets callers obtain a repository for the active backend. Today it wires the
Postgres adapter (used by the isolated local app `pg_app.py`); the dual-read
composite and the Firestore adapter plug in here in later waves.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from core_db.engine import AsyncSessionLocal
from core_db.settings import get_db_settings
from infrastructure.postgres.intervenciones_repo import PostgresIntervencionesRepository
from infrastructure.postgres.unidades_proyecto_repo import PostgresUnidadesProyectoRepository


def postgres_enabled() -> bool:
    """True when the active data backend reads from Postgres."""
    return get_db_settings().data_backend in ("postgres", "dual")


@asynccontextmanager
async def unidades_repo() -> AsyncIterator[PostgresUnidadesProyectoRepository]:
    async with AsyncSessionLocal() as session:
        yield PostgresUnidadesProyectoRepository(session)


@asynccontextmanager
async def intervenciones_repo() -> AsyncIterator[PostgresIntervencionesRepository]:
    async with AsyncSessionLocal() as session:
        yield PostgresIntervencionesRepository(session)

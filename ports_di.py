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


def dual_enabled() -> bool:
    """True only when the active data backend runs BOTH sides (observe-only)."""
    return get_db_settings().data_backend == "dual"


def firestore_enabled() -> bool:
    """True when the active data backend reads from Firestore."""
    return get_db_settings().data_backend in ("firestore", "dual")


def firestore_unidades_repo():
    """Construct the read-only Firestore unidades adapter.

    Imported lazily so a missing Firestore/Google client stack never breaks
    module import for Postgres-only or test environments.
    """
    from infrastructure.firestore.unidades_proyecto_repo import (
        FirestoreUnidadesProyectoRepository,
    )

    return FirestoreUnidadesProyectoRepository()


def firestore_intervenciones_repo():
    """Construct the read-only Firestore intervenciones adapter (lazy import)."""
    from infrastructure.firestore.intervenciones_repo import (
        FirestoreIntervencionesRepository,
    )

    return FirestoreIntervencionesRepository()


@asynccontextmanager
async def unidades_repo() -> AsyncIterator[PostgresUnidadesProyectoRepository]:
    async with AsyncSessionLocal() as session:
        yield PostgresUnidadesProyectoRepository(session)


@asynccontextmanager
async def intervenciones_repo() -> AsyncIterator[PostgresIntervencionesRepository]:
    async with AsyncSessionLocal() as session:
        yield PostgresIntervencionesRepository(session)

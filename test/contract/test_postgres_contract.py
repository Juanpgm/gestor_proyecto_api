"""Run the repository contract against the real Postgres adapters.

A thin session-per-operation wrapper adapts the session-scoped repositories to
the contract's per-call style (each call opens its own AsyncSession; NullPool
keeps connections from leaking across event loops). Skips when the DB is down.
"""

from __future__ import annotations

import asyncio

import pytest

from core_db.engine import AsyncSessionLocal
from domain.geospatial.entities import UnidadProyecto, UPQuery
from infrastructure.postgres.intervenciones_repo import PostgresIntervencionesRepository
from infrastructure.postgres.unidades_proyecto_repo import PostgresUnidadesProyectoRepository
from sqlalchemy import text

from .repo_contract import IntervencionesContract, UnidadesProyectoContract

pytestmark = [pytest.mark.contract, pytest.mark.integration]


def _run(coro):
    return asyncio.run(coro)


async def _can_connect() -> bool:
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


async def _cleanup(prefix: str) -> None:
    async with AsyncSessionLocal() as session:
        await session.execute(
            text("DELETE FROM unidades_proyecto WHERE upid LIKE :p"), {"p": prefix}
        )
        await session.commit()


@pytest.fixture(scope="session")
def _db():
    if not _run(_can_connect()):
        pytest.skip("Postgres not reachable; start docker-compose.dev.yml + alembic.")
    return True


class _SessionPerOpUnidades:
    async def _op(self, fn):
        async with AsyncSessionLocal() as session:
            result = await fn(PostgresUnidadesProyectoRepository(session))
            await session.commit()
            return result

    async def get(self, upid):
        return await self._op(lambda r: r.get(upid))

    async def list(self, query=UPQuery()):
        return await self._op(lambda r: r.list(query))

    async def count(self, query=UPQuery()):
        return await self._op(lambda r: r.count(query))

    async def upsert(self, up):
        return await self._op(lambda r: r.upsert(up))

    async def as_feature_collection(self, query=UPQuery()):
        return await self._op(lambda r: r.as_feature_collection(query))


class _SessionPerOpIntervenciones:
    async def _op(self, fn):
        async with AsyncSessionLocal() as session:
            result = await fn(PostgresIntervencionesRepository(session))
            await session.commit()
            return result

    async def list_by_up(self, upid):
        return await self._op(lambda r: r.list_by_up(upid))

    async def upsert(self, intervencion):
        return await self._op(lambda r: r.upsert(intervencion))

    async def list_avances(self, intervencion_id):
        return await self._op(lambda r: r.list_avances(intervencion_id))

    async def record_avance(self, avance):
        return await self._op(lambda r: r.record_avance(avance))


class TestPostgresUnidadesProyecto(UnidadesProyectoContract):
    @pytest.fixture
    def up_repo(self, _db):
        _run(_cleanup("UNP-95%"))
        yield _SessionPerOpUnidades()
        _run(_cleanup("UNP-95%"))


class TestPostgresIntervenciones(IntervencionesContract):
    @pytest.fixture
    def int_repo(self, _db):
        # Intervenciones FK -> unidades_proyecto; the parent UP must exist.
        _run(_cleanup("UNP-95%"))

        async def _seed_parent():
            async with AsyncSessionLocal() as session:
                await PostgresUnidadesProyectoRepository(session).upsert(
                    UnidadProyecto(upid="UNP-95001", centro_gestor="Contract")
                )
                await session.commit()

        _run(_seed_parent())
        yield _SessionPerOpIntervenciones()
        _run(_cleanup("UNP-95%"))

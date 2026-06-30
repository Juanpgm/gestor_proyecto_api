"""Integration tests for Postgres repository adapters.

Each test runs all its async operations inside a SINGLE asyncio.run() call so
that SQLAlchemy's asyncpg connection pool is never used across event-loop
boundaries (which would make pool connections stale).

Usage:
    pytest -m integration test/integration/test_postgres_repo.py

Requires a live Postgres + PostGIS instance (see conftest.py for the skip
logic when the DB is not reachable).
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import func, select, text

from core_db.engine import AsyncSessionLocal
from domain.geospatial.entities import Avance, Intervencion, UnidadProyecto, UPQuery
from infrastructure.postgres.intervenciones_repo import PostgresIntervencionesRepository
from infrastructure.postgres.models.geospatial import UnidadProyecto as UnidadProyectoORM
from infrastructure.postgres.unidades_proyecto_repo import PostgresUnidadesProyectoRepository

pytestmark = pytest.mark.integration

# Upids reserved for this suite -- no collision with seed (UNP-1001..UNP-1005).
_T_UPIDS = [
    "UNP-91001",
    "UNP-91002",
    "UNP-91003",
    "UNP-91004",
    "UNP-91005",
]

# ---------------------------------------------------------------------------
# Module helpers
# ---------------------------------------------------------------------------


def run(coro):
    """Run a coroutine to completion in a fresh event loop."""
    return asyncio.run(coro)


async def _async_cleanup(upids: list[str]) -> None:
    """Delete the given upids and their cascading children."""
    async with AsyncSessionLocal() as session:
        ids = ", ".join(f"'{u}'" for u in upids)
        await session.execute(
            text(f"DELETE FROM unidades_proyecto WHERE upid IN ({ids})")
        )
        await session.commit()


async def _with_session(coro_fn):
    """Open a session, run coro_fn(session), commit, return result."""
    async with AsyncSessionLocal() as session:
        result = await coro_fn(session)
        await session.commit()
        return result


# ---------------------------------------------------------------------------
# Fixture builders
# ---------------------------------------------------------------------------


def _make_up(upid: str, **kwargs) -> UnidadProyecto:
    defaults: dict = dict(
        nombre_up=f"Test UP {upid}",
        municipio="Cali",
        departamento="Valle del Cauca",
        centro_gestor="Secretaria de Infraestructura",
        presupuesto_base=Decimal("100000000"),
        ano=2024,
        geometry={
            "type": "LineString",
            "coordinates": [[-76.53, 3.40], [-76.52, 3.41]],
        },
    )
    defaults.update(kwargs)
    return UnidadProyecto(upid=upid, **defaults)


def _make_intervencion(intervencion_id: str, upid: str, **kwargs) -> Intervencion:
    defaults: dict = dict(
        ano=2024,
        tipo_intervencion="Construccion",
        presupuesto_base=Decimal("100000000"),
        avance_obra=Decimal("0"),
    )
    defaults.update(kwargs)
    return Intervencion(intervencion_id=intervencion_id, upid=upid, **defaults)


def _make_avance(
    upid: str,
    intervencion_id: str,
    avance: Decimal,
    fecha: datetime,
    **kwargs,
) -> Avance:
    return Avance(
        upid=upid,
        intervencion_id=intervencion_id,
        avance_obra=avance,
        fecha=fecha,
        **kwargs,
    )


# ---------------------------------------------------------------------------
# Tests -- UnidadesProyectoRepository
# ---------------------------------------------------------------------------


class TestUnidadesProyectoRepository:
    """Tests for PostgresUnidadesProyectoRepository."""

    def test_upsert_and_get(self, pg_available):
        """Fields and geometry round-trip correctly through upsert -> get."""

        async def _body():
            await _async_cleanup(_T_UPIDS)

            upid = "UNP-91001"
            up = _make_up(
                upid,
                centro_gestor="Secretaria de Infraestructura",
                geometry={
                    "type": "LineString",
                    "coordinates": [[-76.53, 3.40], [-76.52, 3.41]],
                },
            )

            async with AsyncSessionLocal() as session:
                repo = PostgresUnidadesProyectoRepository(session)
                await repo.upsert(up)
                await session.commit()

            async with AsyncSessionLocal() as session:
                repo = PostgresUnidadesProyectoRepository(session)
                fetched = await repo.get(upid)

            assert fetched is not None
            assert fetched.upid == upid
            assert fetched.nombre_up == up.nombre_up
            assert fetched.centro_gestor == "Secretaria de Infraestructura"
            assert fetched.geometry is not None
            assert fetched.geometry["type"] == "LineString"
            assert fetched.has_valid_geometry is True
            assert fetched.geometry_type is not None

            await _async_cleanup(_T_UPIDS)

        run(_body())

    def test_upsert_is_idempotent_update(self, pg_available):
        """Upserting the same upid twice updates the row (no duplicates)."""

        async def _body():
            await _async_cleanup(_T_UPIDS)

            upid = "UNP-91002"
            original = _make_up(upid, nombre_up="Nombre Original")
            updated = _make_up(upid, nombre_up="Nombre Actualizado")

            async with AsyncSessionLocal() as session:
                repo = PostgresUnidadesProyectoRepository(session)
                await repo.upsert(original)
                await session.flush()
                await repo.upsert(updated)
                await session.commit()

            async with AsyncSessionLocal() as session:
                repo = PostgresUnidadesProyectoRepository(session)
                fetched = await repo.get(upid)

                # Direct count to verify no duplicate rows.
                count_result = await session.execute(
                    select(func.count())
                    .select_from(UnidadProyectoORM)
                    .where(UnidadProyectoORM.upid == upid)
                )
                row_count = count_result.scalar_one()

            assert fetched is not None
            assert fetched.nombre_up == "Nombre Actualizado"
            assert row_count == 1

            await _async_cleanup(_T_UPIDS)

        run(_body())

    def test_placeholder_geometry_flagged_invalid(self, pg_available):
        """A Point [0,0] placeholder results in has_valid_geometry == False."""

        async def _body():
            await _async_cleanup(_T_UPIDS)

            upid = "UNP-91003"
            up = _make_up(
                upid,
                geometry={"type": "Point", "coordinates": [0.0, 0.0]},
            )

            async with AsyncSessionLocal() as session:
                repo = PostgresUnidadesProyectoRepository(session)
                await repo.upsert(up)
                await session.commit()

            async with AsyncSessionLocal() as session:
                repo = PostgresUnidadesProyectoRepository(session)
                fetched = await repo.get(upid)

            assert fetched is not None
            assert fetched.has_valid_geometry is False

            await _async_cleanup(_T_UPIDS)

        run(_body())

    def test_list_and_count_filter_by_centro(self, pg_available):
        """Filtering by centro_gestor returns only matching rows."""

        async def _body():
            await _async_cleanup(_T_UPIDS)

            up_infra = _make_up(
                "UNP-91004",
                nombre_up="UP Infraestructura",
                centro_gestor="CentroFiltroA",
            )
            up_otro = _make_up(
                "UNP-91005",
                nombre_up="UP Otro",
                centro_gestor="CentroFiltroB",
            )

            async with AsyncSessionLocal() as session:
                repo = PostgresUnidadesProyectoRepository(session)
                await repo.upsert(up_infra)
                await repo.upsert(up_otro)
                await session.commit()

            query = UPQuery(centro_gestor="CentroFiltroA")

            async with AsyncSessionLocal() as session:
                repo = PostgresUnidadesProyectoRepository(session)
                listed = await repo.list(query)
                count = await repo.count(query)

            upids_returned = {u.upid for u in listed}
            assert "UNP-91004" in upids_returned, "UNP-91004 should match CentroFiltroA"
            assert "UNP-91005" not in upids_returned, "UNP-91005 has a different centro"
            assert count >= 1

            await _async_cleanup(_T_UPIDS)

        run(_body())

    def test_as_feature_collection_shape(self, pg_available):
        """as_feature_collection returns a valid GeoJSON FeatureCollection."""

        async def _body():
            await _async_cleanup(_T_UPIDS)

            upid = "UNP-91001"
            up = _make_up(upid)

            async with AsyncSessionLocal() as session:
                repo = PostgresUnidadesProyectoRepository(session)
                await repo.upsert(up)
                await session.commit()

            async with AsyncSessionLocal() as session:
                repo = PostgresUnidadesProyectoRepository(session)
                fc = await repo.as_feature_collection(UPQuery())

            assert fc["type"] == "FeatureCollection"
            assert isinstance(fc["features"], list)

            matching = [f for f in fc["features"] if f["properties"]["upid"] == upid]
            assert len(matching) == 1, f"Expected exactly 1 feature for {upid}"

            feat = matching[0]
            assert feat["type"] == "Feature"
            assert feat["geometry"] is not None
            assert feat["geometry"]["type"] == "LineString"
            props = feat["properties"]
            assert "upid" in props
            assert props["upid"] == upid
            # presupuesto_base should be float (not Decimal) in properties.
            if props["presupuesto_base"] is not None:
                assert isinstance(props["presupuesto_base"], float)

            await _async_cleanup(_T_UPIDS)

        run(_body())


# ---------------------------------------------------------------------------
# Tests -- IntervencionesRepository
# ---------------------------------------------------------------------------


class TestIntervencionesRepository:
    """Tests for PostgresIntervencionesRepository."""

    def test_record_avance_updates_cache_and_estado(self, pg_available):
        """record_avance refreshes avance_obra cache; estado is derived correctly."""

        async def _body():
            await _async_cleanup(_T_UPIDS)

            upid = "UNP-91001"
            intervencion_id = "INT-91001-A"
            up = _make_up(upid)
            intervencion = _make_intervencion(intervencion_id, upid, avance_obra=Decimal("0"))

            # Setup: UP + intervencion.
            async with AsyncSessionLocal() as session:
                up_repo = PostgresUnidadesProyectoRepository(session)
                int_repo = PostgresIntervencionesRepository(session)
                await up_repo.upsert(up)
                await int_repo.upsert(intervencion)
                await session.commit()

            # Record older avance (10%) -- cache becomes 10.
            avance_older = _make_avance(
                upid, intervencion_id, Decimal("10"),
                datetime(2024, 1, 1, tzinfo=timezone.utc),
            )
            async with AsyncSessionLocal() as session:
                repo = PostgresIntervencionesRepository(session)
                cache = await repo.record_avance(avance_older)
                await session.commit()
            assert cache == Decimal("10")

            # Record newer avance (80%) with later fecha -- cache becomes 80.
            avance_newer = _make_avance(
                upid, intervencion_id, Decimal("80"),
                datetime(2024, 2, 1, tzinfo=timezone.utc),
            )
            async with AsyncSessionLocal() as session:
                repo = PostgresIntervencionesRepository(session)
                cache = await repo.record_avance(avance_newer)
                await session.commit()
            assert cache == Decimal("80")

            # Verify the persisted intervencion reflects the cache and derived estado.
            async with AsyncSessionLocal() as session:
                repo = PostgresIntervencionesRepository(session)
                intervenciones = await repo.list_by_up(upid)

            assert len(intervenciones) == 1
            iv = intervenciones[0]
            assert iv.avance_obra == Decimal("80")
            # 0.5 <= 80 < 99.5 -> "En ejecucion"
            assert iv.estado == "En ejecución"

            # Now record 100% -- estado should become "Terminado".
            avance_100 = _make_avance(
                upid, intervencion_id, Decimal("100"),
                datetime(2024, 3, 1, tzinfo=timezone.utc),
            )
            async with AsyncSessionLocal() as session:
                repo = PostgresIntervencionesRepository(session)
                cache = await repo.record_avance(avance_100)
                await session.commit()
            assert cache == Decimal("100")

            async with AsyncSessionLocal() as session:
                repo = PostgresIntervencionesRepository(session)
                intervenciones_final = await repo.list_by_up(upid)
            assert intervenciones_final[0].estado == "Terminado"

            await _async_cleanup(_T_UPIDS)

        run(_body())

    def test_estado_manual_whitelist_respected(self, pg_available):
        """estado_manual='Suspendido' overrides avance-derived estado even at 100%."""

        async def _body():
            await _async_cleanup(_T_UPIDS)

            upid = "UNP-91002"
            intervencion_id = "INT-91002-A"
            up = _make_up(upid)
            intervencion = _make_intervencion(
                intervencion_id, upid,
                avance_obra=Decimal("100"),
                estado_manual="Suspendido",
            )

            async with AsyncSessionLocal() as session:
                up_repo = PostgresUnidadesProyectoRepository(session)
                int_repo = PostgresIntervencionesRepository(session)
                await up_repo.upsert(up)
                await int_repo.upsert(intervencion)
                await session.commit()

            async with AsyncSessionLocal() as session:
                repo = PostgresIntervencionesRepository(session)
                intervenciones = await repo.list_by_up(upid)

            assert len(intervenciones) == 1
            iv = intervenciones[0]
            assert iv.avance_obra == Decimal("100")
            # estado_manual whitelist wins over avance-derived "Terminado".
            assert iv.estado == "Suspendido"

            await _async_cleanup(_T_UPIDS)

        run(_body())

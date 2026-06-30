"""Integration tests against the live PostGIS schema (migration 0001).

Proves three things the migration must guarantee:
  1. the schema objects exist (tables, view, function),
  2. the SQL `calcular_estado` agrees byte-for-byte with the Python domain rule,
  3. geometry round-trips through PostGIS with correct validity flags.
"""

import asyncio
import os

import pytest

from domain.geospatial.estado import calcular_estado as py_calcular_estado

pytestmark = pytest.mark.integration

DEFAULT_URL = "postgresql+asyncpg://calitrack:calitrack@localhost:5433/calitrack_dev"


def dsn() -> str:
    return os.environ.get("DATABASE_URL", DEFAULT_URL).replace("+asyncpg", "")


def run(coro):
    return asyncio.run(coro)


async def _fetchval(sql, *args):
    import asyncpg

    conn = await asyncpg.connect(dsn())
    try:
        return await conn.fetchval(sql, *args)
    finally:
        await conn.close()


async def _fetch(sql, *args):
    import asyncpg

    conn = await asyncpg.connect(dsn())
    try:
        return await conn.fetch(sql, *args)
    finally:
        await conn.close()


async def _execute(sql, *args):
    import asyncpg

    conn = await asyncpg.connect(dsn())
    try:
        return await conn.execute(sql, *args)
    finally:
        await conn.close()


def test_core_tables_exist(pg_available):
    count = run(_fetchval(
        "select count(*) from information_schema.tables "
        "where table_schema='public' and table_type='BASE TABLE' "
        "and table_name in ('unidades_proyecto','intervenciones_unidades_proyecto',"
        "'avances_unidades_proyecto','reconocimiento_360','centros_gestores')"
    ))
    assert count == 5


def test_view_and_function_exist(pg_available):
    view = run(_fetchval(
        "select 1 from information_schema.views where table_name='v_intervenciones'"
    ))
    fn = run(_fetchval("select 1 from pg_proc where proname='calcular_estado'"))
    assert view == 1 and fn == 1


@pytest.mark.parametrize(
    "avance, estado",
    [
        (None, None), (0, None), (0.4, None), (0.5, None), (50, None),
        (99.4, None), (99.5, None), (100, None),
        (100, "Suspendido"), (100, "inaugurado"), (0, "Terminado"),
        (100, "En ejecución"), (0, "Liquidado"),
    ],
)
def test_sql_calcular_estado_matches_domain(pg_available, avance, estado):
    sql_result = run(_fetchval("select calcular_estado($1::numeric, $2::text)", avance, estado))
    assert sql_result == py_calcular_estado(avance, estado)


def test_geometry_roundtrip_and_validity(pg_available):
    # Clean any leftovers, then insert representative geometries.
    run(_execute("delete from unidades_proyecto where upid in ('UNP-90001','UNP-90002','UNP-90003','UNP-90004')"))
    run(_execute(
        """
        insert into unidades_proyecto (upid, geom) values
          ('UNP-90001', ST_GeomFromText('LINESTRING(-76.5 3.4,-76.4 3.5)',4326)),
          ('UNP-90002', ST_GeomFromText('POLYGON((-76.5 3.4,-76.4 3.4,-76.4 3.5,-76.5 3.5,-76.5 3.4))',4326)),
          ('UNP-90003', ST_SetSRID(ST_MakePoint(0,0),4326)),
          ('UNP-90004', NULL)
        """
    ))
    rows = run(_fetch(
        "select upid, geometry_type, has_geometry, has_valid_geometry, "
        "ST_AsGeoJSON(geom) as gj, ST_SRID(geom) as srid "
        "from unidades_proyecto where upid in ('UNP-90001','UNP-90002','UNP-90003','UNP-90004') order by upid"
    ))
    by_id = {r["upid"]: r for r in rows}

    assert by_id["UNP-90001"]["geometry_type"] == "LINESTRING"
    assert by_id["UNP-90001"]["has_valid_geometry"] is True
    assert by_id["UNP-90001"]["srid"] == 4326

    assert by_id["UNP-90002"]["geometry_type"] == "POLYGON"
    assert by_id["UNP-90002"]["has_valid_geometry"] is True

    # Placeholder [0,0] is stored but flagged invalid.
    assert by_id["UNP-90003"]["has_geometry"] is True
    assert by_id["UNP-90003"]["has_valid_geometry"] is False

    # NULL geometry -> not present, not valid.
    assert by_id["UNP-90004"]["has_geometry"] is False
    assert by_id["UNP-90004"]["has_valid_geometry"] is False

    run(_execute("delete from unidades_proyecto where upid in ('UNP-90001','UNP-90002','UNP-90003','UNP-90004')"))

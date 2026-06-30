"""Contract + parity tests for the dual-read composite repository.

Two layers of guarantees are exercised here, both using the in-memory fakes so
the suite stays pure (no Firestore, no Postgres):

1. Behavioural parity: a ``DualUnidadesProyectoRepository`` wrapping two fakes
   still satisfies the SAME ``UnidadesProyectoContract`` read assertions every
   other adapter must honour. ``primary="postgres"`` so the contract's own
   upserts (which the composite routes to Postgres) are read back.
2. Divergence detection: identical seeds produce ``last_report.ok is True``; a
   single divergent field produces ``last_report.ok is False`` while the
   composite still returns the configured primary side.

Router-path coverage (FIX 2): ``fetch_enriched_dual`` and
``fetch_intervenciones_enriched_dual`` are also exercised directly — these are
exactly what the router calls — using injected in-memory fakes and a fake
Postgres callable so no live backend is needed.

Marked ``unit`` (pure in-memory, no I/O) AND ``contract`` (same assertions run
against multiple adapters) so it runs under ``-m "unit or integration"``.
"""

from __future__ import annotations

import asyncio
import logging
import types as _types
from dataclasses import replace
from decimal import Decimal

import pytest

import infrastructure.composite.unidades_read_dual as _dual_mod
from domain.geospatial.entities import Intervencion, UnidadProyecto, UPQuery
from infrastructure.composite.unidades_proyecto_repo import (
    DualUnidadesProyectoRepository,
)
from infrastructure.composite.unidades_read_dual import (
    fetch_enriched_dual,
    fetch_intervenciones_enriched_dual,
)

from .fakes import InMemoryIntervencionesRepository, InMemoryUnidadesProyectoRepository
from .repo_contract import UnidadesProyectoContract, _run

pytestmark = [pytest.mark.contract, pytest.mark.unit]


def _make_up(upid: str = "UNP-90001", **overrides) -> UnidadProyecto:
    base = dict(
        upid=upid,
        nombre_up="Parque Central",
        centro_gestor="DAGMA",
        presupuesto_base=Decimal("1000.00"),
        ano=2024,
        geometry={"type": "Point", "coordinates": [-76.5, 3.4]},
        geometry_type="POINT",
        has_valid_geometry=True,
    )
    base.update(overrides)
    return UnidadProyecto(**base)


class TestDualUnidadesProyecto(UnidadesProyectoContract):
    """Run the shared read contract against the dual composite.

    ``primary="postgres"`` mirrors production writes (composite ``upsert`` goes
    to Postgres), so the contract's upsert-then-read assertions hold.
    """

    @pytest.fixture
    def up_repo(self):
        return DualUnidadesProyectoRepository(
            InMemoryUnidadesProyectoRepository(),
            InMemoryUnidadesProyectoRepository(),
            primary="postgres",
        )


def _seed_pair(primary: str):
    fs = InMemoryUnidadesProyectoRepository()
    pg = InMemoryUnidadesProyectoRepository()
    composite = DualUnidadesProyectoRepository(fs, pg, primary=primary)
    return fs, pg, composite


def test_identical_seed_has_no_divergence():
    fs, pg, composite = _seed_pair(primary="firestore")
    up = _make_up()
    _run(fs.upsert(up))
    _run(pg.upsert(up))

    result = _run(composite.list())

    assert [u.upid for u in result] == ["UNP-90001"]
    assert composite.last_report is not None
    assert composite.last_report.ok is True


def test_divergent_field_is_recorded_and_primary_returned():
    fs, pg, composite = _seed_pair(primary="firestore")
    up_fs = _make_up(nombre_up="Parque Central")
    up_pg = replace(up_fs, nombre_up="Parque Central RENOMBRADO")
    _run(fs.upsert(up_fs))
    _run(pg.upsert(up_pg))

    result = _run(composite.list(UPQuery()))

    # Primary is Firestore: the composite returns the Firestore-side value...
    assert result[0].nombre_up == "Parque Central"
    # ...while still recording the divergence in the parity report.
    assert composite.last_report is not None
    assert composite.last_report.ok is False
    assert "UNP-90001" in composite.last_report.changed


# ---------------------------------------------------------------------------
# Router-path tests: fetch_enriched_dual / fetch_intervenciones_enriched_dual
# (FIX 2) — exercise the actual functions the router dispatches to, not just
# the entity-level DualUnidadesProyectoRepository composite.
# ---------------------------------------------------------------------------

def _settings_getter(primary: str = "firestore"):
    """Return a get_db_settings() replacement that controls dual_read_primary."""
    ns = _types.SimpleNamespace(dual_read_primary=primary, data_backend="dual")
    return lambda: ns


def _expected_enriched_row(up: UnidadProyecto) -> dict:
    """Build the enriched UP dict that _fetch_enriched_firestore produces for a
    UP with no intervenciones, using the same helpers as the real path."""
    from domain.geospatial.consolidation import consolidate_intervenciones
    from infrastructure.postgres.unidades_read import CONSOLIDATED_KEYS, up_to_dict

    cons = consolidate_intervenciones(up, [])
    d = up_to_dict(up)
    d.update({k: cons[k] for k in CONSOLIDATED_KEYS})
    d["n_intervenciones"] = d.get("num_intervenciones")
    return d


@pytest.mark.unit
def test_fetch_enriched_dual_identical_no_divergence_warning(monkeypatch, caplog):
    """Both sides return identical enriched rows → primary returned, no WARNING."""
    up = _make_up()
    fs_up_repo = InMemoryUnidadesProyectoRepository()
    fs_int_repo = InMemoryIntervencionesRepository()
    asyncio.run(fs_up_repo.upsert(up))

    expected_rows = [_expected_enriched_row(up)]

    async def pg_fake(q: UPQuery) -> tuple[list[dict], int]:
        return list(expected_rows), len(expected_rows)

    monkeypatch.setattr(_dual_mod, "get_db_settings", _settings_getter("firestore"))

    with caplog.at_level(logging.WARNING, logger="dual.unidades"):
        rows, _ = asyncio.run(
            fetch_enriched_dual(
                UPQuery(limit=100),
                _fs_up_factory=lambda: fs_up_repo,
                _fs_int_factory=lambda: fs_int_repo,
                _pg_fetch_fn=pg_fake,
            )
        )

    assert len(rows) == 1
    assert rows[0]["upid"] == "UNP-90001"
    divergence_warns = [
        r for r in caplog.records
        if r.levelno >= logging.WARNING
        and "dual" in r.name
        and "DIVERGENCE" in r.message
    ]
    assert not divergence_warns, f"Unexpected DIVERGENCE warning: {divergence_warns}"


@pytest.mark.unit
def test_fetch_enriched_dual_divergent_estado_emits_warning(monkeypatch, caplog):
    """Divergent 'estado' on the pg side → primary (firestore) returned + WARNING."""
    up = _make_up()
    fs_up_repo = InMemoryUnidadesProyectoRepository()
    fs_int_repo = InMemoryIntervencionesRepository()
    asyncio.run(fs_up_repo.upsert(up))

    expected_rows = [_expected_enriched_row(up)]
    # Force a divergence: pg side has a different estado
    pg_rows = [{**row, "estado": "En ejecucion"} for row in expected_rows]

    async def pg_fake_divergent(q: UPQuery) -> tuple[list[dict], int]:
        return pg_rows, len(pg_rows)

    monkeypatch.setattr(_dual_mod, "get_db_settings", _settings_getter("firestore"))

    with caplog.at_level(logging.WARNING, logger="dual.unidades"):
        rows, _ = asyncio.run(
            fetch_enriched_dual(
                UPQuery(limit=100),
                _fs_up_factory=lambda: fs_up_repo,
                _fs_int_factory=lambda: fs_int_repo,
                _pg_fetch_fn=pg_fake_divergent,
            )
        )

    # Primary is firestore → rows from the firestore side (estado = "Sin estado")
    assert rows[0]["estado"] == "Sin estado"
    divergence_warns = [
        r for r in caplog.records
        if r.levelno >= logging.WARNING
        and "dual" in r.name
        and "DIVERGENCE" in r.message
    ]
    assert divergence_warns, "Expected a DIVERGENCE WARNING from dual.unidades"


@pytest.mark.unit
def test_fetch_intervenciones_enriched_dual_identical_no_divergence_warning(
    monkeypatch, caplog
):
    """Identical intervencion seeds → primary returned, no DIVERGENCE warning."""
    from infrastructure.postgres.unidades_read import intervencion_to_record

    up = _make_up()
    interv = Intervencion(intervencion_id="INT-90001", upid="UNP-90001")
    fs_up_repo = InMemoryUnidadesProyectoRepository()
    fs_int_repo = InMemoryIntervencionesRepository()
    asyncio.run(fs_up_repo.upsert(up))
    asyncio.run(fs_int_repo.upsert(interv))

    parent = {
        "nombre_centro_gestor": up.centro_gestor,
        "clase_up": up.clase_up,
        "tipo_equipamiento": up.tipo_equipamiento,
    }
    expected_records = [intervencion_to_record(interv, parent)]

    async def pg_fake() -> list[dict]:
        return list(expected_records)

    monkeypatch.setattr(_dual_mod, "get_db_settings", _settings_getter("firestore"))

    with caplog.at_level(logging.WARNING, logger="dual.intervenciones"):
        records = asyncio.run(
            fetch_intervenciones_enriched_dual(
                _fs_up_factory=lambda: fs_up_repo,
                _fs_int_factory=lambda: fs_int_repo,
                _pg_fetch_fn=pg_fake,
            )
        )

    assert len(records) == 1
    assert records[0]["intervencion_id"] == "INT-90001"
    divergence_warns = [
        r for r in caplog.records
        if r.levelno >= logging.WARNING
        and "dual" in r.name
        and "DIVERGENCE" in r.message
    ]
    assert not divergence_warns, f"Unexpected DIVERGENCE warning: {divergence_warns}"


@pytest.mark.unit
def test_fetch_intervenciones_enriched_dual_divergent_estado_emits_warning(
    monkeypatch, caplog
):
    """Divergent 'estado' on pg side → primary (firestore) returned + WARNING."""
    from infrastructure.postgres.unidades_read import intervencion_to_record

    up = _make_up()
    interv = Intervencion(intervencion_id="INT-90002", upid="UNP-90001")
    fs_up_repo = InMemoryUnidadesProyectoRepository()
    fs_int_repo = InMemoryIntervencionesRepository()
    asyncio.run(fs_up_repo.upsert(up))
    asyncio.run(fs_int_repo.upsert(interv))

    parent = {
        "nombre_centro_gestor": up.centro_gestor,
        "clase_up": up.clase_up,
        "tipo_equipamiento": up.tipo_equipamiento,
    }
    expected_records = [intervencion_to_record(interv, parent)]
    pg_records = [{**r, "estado": "Terminado"} for r in expected_records]

    async def pg_fake_divergent() -> list[dict]:
        return pg_records

    monkeypatch.setattr(_dual_mod, "get_db_settings", _settings_getter("firestore"))

    with caplog.at_level(logging.WARNING, logger="dual.intervenciones"):
        records = asyncio.run(
            fetch_intervenciones_enriched_dual(
                _fs_up_factory=lambda: fs_up_repo,
                _fs_int_factory=lambda: fs_int_repo,
                _pg_fetch_fn=pg_fake_divergent,
            )
        )

    # Primary is firestore — records come from the firestore side
    assert records[0]["intervencion_id"] == "INT-90002"
    divergence_warns = [
        r for r in caplog.records
        if r.levelno >= logging.WARNING
        and "dual" in r.name
        and "DIVERGENCE" in r.message
    ]
    assert divergence_warns, "Expected a DIVERGENCE WARNING from dual.intervenciones"

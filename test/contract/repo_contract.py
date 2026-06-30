"""Backend-agnostic contract assertions for the geospatial repositories.

Subclasses bind a concrete adapter (in-memory fake, Postgres) by overriding the
`up_repo` / `int_repo` fixtures. The SAME assertions then run against every
adapter, so behavioural parity is enforced by construction.

Each test makes one or more `run()` calls on the repo; the repo must persist
state across calls (the fake holds a dict; the Postgres wrapper hits the DB).
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from domain.geospatial.entities import Avance, Intervencion, UnidadProyecto, UPQuery


def _run(coro):
    return asyncio.run(coro)


class UnidadesProyectoContract:
    """Override `up_repo` in a subclass to return a fresh repository."""

    def test_upsert_then_get(self, up_repo):
        up = UnidadProyecto(
            upid="UNP-95001", nombre_up="Parque A", centro_gestor="DAGMA",
            presupuesto_base=Decimal("1000.00"), ano=2024,
            geometry={"type": "Point", "coordinates": [-76.5, 3.4]},
            geometry_type="POINT", has_valid_geometry=True,
        )
        _run(up_repo.upsert(up))
        got = _run(up_repo.get("UNP-95001"))
        assert got is not None
        assert got.upid == "UNP-95001"
        assert got.nombre_up == "Parque A"
        assert got.centro_gestor == "DAGMA"

    def test_get_missing_returns_none(self, up_repo):
        assert _run(up_repo.get("UNP-99999")) is None

    def test_count_reflects_inserts(self, up_repo):
        before = _run(up_repo.count())
        _run(up_repo.upsert(UnidadProyecto(upid="UNP-95002", centro_gestor="X")))
        _run(up_repo.upsert(UnidadProyecto(upid="UNP-95003", centro_gestor="X")))
        after = _run(up_repo.count())
        assert after - before == 2

    def test_filter_by_centro_gestor(self, up_repo):
        _run(up_repo.upsert(UnidadProyecto(upid="UNP-95004", centro_gestor="Alpha")))
        _run(up_repo.upsert(UnidadProyecto(upid="UNP-95005", centro_gestor="Beta")))
        only_alpha = _run(up_repo.list(UPQuery(centro_gestor="Alpha")))
        upids = {u.upid for u in only_alpha}
        assert "UNP-95004" in upids
        assert "UNP-95005" not in upids

    def test_feature_collection_shape(self, up_repo):
        _run(up_repo.upsert(UnidadProyecto(
            upid="UNP-95006", centro_gestor="Geo",
            geometry={"type": "Point", "coordinates": [-76.5, 3.4]},
            geometry_type="POINT", has_valid_geometry=True,
        )))
        fc = _run(up_repo.as_feature_collection(UPQuery(centro_gestor="Geo")))
        assert fc["type"] == "FeatureCollection"
        assert isinstance(fc["features"], list) and fc["features"]
        feat = fc["features"][0]
        assert feat["type"] == "Feature"
        assert "geometry" in feat
        assert feat["properties"]["upid"] == "UNP-95006"


class IntervencionesContract:
    """Override `int_repo` in a subclass to return a fresh repository."""

    def test_record_avance_updates_cache(self, int_repo):
        _run(int_repo.upsert(Intervencion(
            intervencion_id="INT-95001", upid="UNP-95001", avance_obra=Decimal("0"),
        )))
        t0 = datetime(2024, 1, 1, tzinfo=timezone.utc)
        _run(int_repo.record_avance(Avance(
            upid="UNP-95001", intervencion_id="INT-95001",
            avance_obra=Decimal("10"), fecha=t0,
        )))
        cache = _run(int_repo.record_avance(Avance(
            upid="UNP-95001", intervencion_id="INT-95001",
            avance_obra=Decimal("80"), fecha=t0 + timedelta(days=5),
        )))
        assert Decimal(cache) == Decimal("80")
        interv = _run(int_repo.list_by_up("UNP-95001"))
        target = next(i for i in interv if i.intervencion_id == "INT-95001")
        assert Decimal(target.avance_obra) == Decimal("80")
        assert target.estado == "En ejecución"

    def test_latest_avance_to_100_makes_terminado(self, int_repo):
        _run(int_repo.upsert(Intervencion(
            intervencion_id="INT-95002", upid="UNP-95001", avance_obra=Decimal("0"),
        )))
        t0 = datetime(2024, 2, 1, tzinfo=timezone.utc)
        _run(int_repo.record_avance(Avance(
            upid="UNP-95001", intervencion_id="INT-95002",
            avance_obra=Decimal("100"), fecha=t0,
        )))
        target = next(i for i in _run(int_repo.list_by_up("UNP-95001"))
                      if i.intervencion_id == "INT-95002")
        assert target.estado == "Terminado"

    def test_estado_manual_whitelist_respected(self, int_repo):
        _run(int_repo.upsert(Intervencion(
            intervencion_id="INT-95003", upid="UNP-95001",
            avance_obra=Decimal("100"), estado_manual="Suspendido",
        )))
        target = next(i for i in _run(int_repo.list_by_up("UNP-95001"))
                      if i.intervencion_id == "INT-95003")
        assert target.estado == "Suspendido"

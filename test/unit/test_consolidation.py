"""Unit tests for UP-level intervención consolidation."""

from decimal import Decimal

import pytest

from domain.geospatial.consolidation import consolidate_intervenciones
from domain.geospatial.entities import Intervencion, UnidadProyecto

pytestmark = pytest.mark.unit

UP_VIAL = UnidadProyecto(upid="UNP-1", clase_up="Obra vial", tipo_equipamiento="Vías")


def _i(iid, avance, pres, tipo="Obras", estado_manual=None):
    return Intervencion(
        intervencion_id=iid, upid="UNP-1",
        avance_obra=Decimal(str(avance)), presupuesto_base=Decimal(str(pres)),
        tipo_intervencion=tipo, estado_manual=estado_manual,
    )


def test_no_intervenciones():
    r = consolidate_intervenciones(UP_VIAL, [])
    assert r["estado"] == "Sin estado"
    assert r["avance_obra"] is None
    assert r["frente_activo"] == "No aplica"
    assert r["num_intervenciones"] == 0


def test_weighted_avance_by_presupuesto():
    # 0% on 300M and 100% on 100M -> weighted 25%, NOT the 50% arithmetic mean.
    r = consolidate_intervenciones(UP_VIAL, [_i("a", 0, 300_000_000), _i("b", 100, 100_000_000)])
    assert r["avance_obra"] == 25.0
    assert r["estado"] == "Varios estados"  # alistamiento + terminado


def test_arithmetic_mean_when_no_presupuesto():
    r = consolidate_intervenciones(UP_VIAL, [_i("a", 20, 0), _i("b", 60, 0)])
    assert r["avance_obra"] == 40.0


def test_single_estado_when_all_agree():
    r = consolidate_intervenciones(UP_VIAL, [_i("a", 50, 100), _i("b", 60, 100)])
    assert r["estado"] == "En ejecución"
    assert r["tipo_intervencion"] == "Obras"


def test_frente_activo_takes_highest_priority():
    # One eligible active front (en ejecución, >100M, obra vial) wins over a small one.
    r = consolidate_intervenciones(
        UP_VIAL, [_i("a", 50, 200_000_000), _i("b", 50, 10_000_000)]
    )
    assert r["frente_activo"] == "Frente activo"


def test_tipo_varios_when_mixed():
    r = consolidate_intervenciones(
        UP_VIAL, [_i("a", 50, 100, tipo="Obras"), _i("b", 50, 100, tipo="Mantenimiento")]
    )
    assert r["tipo_intervencion"] == "Varios"

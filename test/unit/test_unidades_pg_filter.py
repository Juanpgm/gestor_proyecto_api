"""Unit tests for the Postgres read-path client-side filters.

Pure functions over enriched dicts — no DB, no Firebase. Mirrors the filter
parity the full backend relies on when DATA_BACKEND=postgres.
"""

from decimal import Decimal

from domain.geospatial.entities import Intervencion
from infrastructure.postgres.unidades_read import (
    _norm,
    filter_intervenciones,
    filter_unidades,
    intervencion_to_record,
)


def _rows():
    return [
        {
            "upid": "UNP-1",
            "nombre_centro_gestor": "Secretaría de Infraestructura",
            "estado": "En ejecución",
            "clase_up": "Construcción",
            "tipo_equipamiento": "Vías",
            "comuna_corregimiento": "Comuna 1",
            "barrio_vereda": "El Centro",
            "frente_activo": "Sí",
            "fuente_financiacion": "Ordinario",
            "tipo_intervencion": "Mantenimiento",
            "ano": 2024,
        },
        {
            "upid": "UNP-2",
            "nombre_centro_gestor": "DAGRD",
            "estado": "Suspendido",
            "clase_up": "Dotación",
            "tipo_equipamiento": "Parques",
            "comuna_corregimiento": "Comuna 2",
            "barrio_vereda": "San Antonio",
            "frente_activo": "No",
            "fuente_financiacion": "SGP",
            "tipo_intervencion": "Construcción",
            "ano": 2023,
        },
    ]


def test_no_filters_returns_all():
    rows = _rows()
    assert filter_unidades(rows) == rows


def test_text_filter_is_accent_and_case_insensitive():
    # "En ejecucion" (no accent, lowercase) must match "En ejecución".
    out = filter_unidades(_rows(), estado="en ejecucion")
    assert len(out) == 1
    assert out[0]["upid"] == "UNP-1"


def test_ano_filter_is_exact_int():
    out = filter_unidades(_rows(), ano=2023)
    assert len(out) == 1
    assert out[0]["upid"] == "UNP-2"


def test_multiple_filters_are_anded():
    out = filter_unidades(_rows(), clase_up="Construcción", tipo_equipamiento="Vías")
    assert len(out) == 1
    assert out[0]["upid"] == "UNP-1"


def test_conflicting_filters_yield_empty():
    out = filter_unidades(_rows(), clase_up="Construcción", ano=2023)
    assert out == []


def test_upid_filter():
    out = filter_unidades(_rows(), upid="UNP-2")
    assert [r["upid"] for r in out] == ["UNP-2"]


def test_non_dict_rows_are_dropped():
    assert filter_unidades([None, "x", {"upid": "UNP-1", "ano": 2024}]) == [
        {"upid": "UNP-1", "ano": 2024}
    ]


def test_norm_helper():
    assert _norm("  Inauguración  ") == "inauguracion"
    assert _norm(None) == ""
    assert _norm("En   Ejecución") == "en ejecucion"


# --- intervenciones path ----------------------------------------------------


def test_intervencion_to_record_derives_estado_and_inherits_parent():
    i = Intervencion(
        intervencion_id="INT-1",
        upid="UNP-1",
        tipo_intervencion="Construcción",
        presupuesto_base=Decimal("200000000"),
        avance_obra=Decimal("50"),
    )
    parent = {
        "nombre_centro_gestor": "DAGRD",
        "clase_up": "Obra vial",
        "tipo_equipamiento": "Vías",
    }
    rec = intervencion_to_record(i, parent)
    # estado derived from avance (0.5 <= 50 < 99.5 -> "En ejecución")
    assert rec["estado"] == "En ejecución"
    # parent props inherited onto the intervención record
    assert rec["nombre_centro_gestor"] == "DAGRD"
    assert rec["clase_up"] == "Obra vial"
    assert rec["tipo_equipamiento"] == "Vías"
    # active civil-works front (budget >= 100M, valid clase, en ejecución)
    assert rec["frente_activo"] == "Frente activo"


def test_intervencion_to_record_handles_missing_parent():
    i = Intervencion(intervencion_id="INT-2", upid="UNP-X", avance_obra=Decimal("0"))
    rec = intervencion_to_record(i, None)
    assert rec["nombre_centro_gestor"] is None
    assert rec["estado"] == "En alistamiento"  # avance < 0.5
    assert rec["frente_activo"] == "No aplica"


def _interv_rows():
    return [
        {"intervencion_id": "INT-1", "upid": "UNP-1", "estado": "En ejecución",
         "tipo_intervencion": "Construcción", "presupuesto_base": 200000000.0},
        {"intervencion_id": "INT-2", "upid": "UNP-2", "estado": "Terminado",
         "tipo_intervencion": "Mantenimiento", "presupuesto_base": 5000000.0},
    ]


def test_filter_intervenciones_by_estado_normalized():
    out = filter_intervenciones(_interv_rows(), estado="terminado")
    assert [r["intervencion_id"] for r in out] == ["INT-2"]


def test_filter_intervenciones_text_and_numeric():
    out = filter_intervenciones(_interv_rows(), tipo_intervencion="construcción")
    assert [r["intervencion_id"] for r in out] == ["INT-1"]
    out2 = filter_intervenciones(_interv_rows(), presupuesto_base=5000000)
    assert [r["intervencion_id"] for r in out2] == ["INT-2"]


def test_filter_intervenciones_no_filters_returns_all():
    rows = _interv_rows()
    assert filter_intervenciones(rows) == rows

"""
Unit tests for the pure domain estado/frente-activo rules.

These functions are the v3 ports of the legacy derivation logic that currently
lives in api/scripts/unidades_proyecto.py (_calcular_estado, _clasificar_frente_activo).
The domain layer must reproduce the legacy behaviour EXACTLY so that the
Firestore and Postgres adapters agree at the data boundary.

Contract (must match front/src/utils/estadoUP.ts and the SQL calcular_estado):
    - avance < 0.5  (or None / non-numeric)  -> "En alistamiento"
    - avance >= 99.5                          -> "Terminado"
    - otherwise                               -> "En ejecución"
    - stored estado is honoured ONLY if it is a manual whitelist value
      ("Suspendido", "Inaugurado"), case/accent-insensitive.
"""

import pytest

from domain.geospatial.estado import (
    calcular_estado,
    clasificar_frente_activo,
    normalizar_estado,
)

pytestmark = pytest.mark.unit


class TestCalcularEstado:
    @pytest.mark.parametrize(
        "avance, expected",
        [
            (None, "En alistamiento"),
            (0, "En alistamiento"),
            (0.4, "En alistamiento"),
            ("abc", "En alistamiento"),
            (0.5, "En ejecución"),
            (50, "En ejecución"),
            (99.4, "En ejecución"),
            (99.5, "Terminado"),
            (100, "Terminado"),
            ("99.8", "Terminado"),
        ],
    )
    def test_derives_from_avance(self, avance, expected):
        assert calcular_estado(avance, None) == expected

    @pytest.mark.parametrize("estado_manual", ["Suspendido", "suspendido", "INAUGURADO", "Inaugurado"])
    def test_respects_whitelist_regardless_of_avance(self, estado_manual):
        # avance would otherwise force "Terminado"; the whitelist value must win
        # and be returned verbatim (original casing preserved).
        result = calcular_estado(100, estado_manual)
        assert normalizar_estado(result) == normalizar_estado(estado_manual)

    def test_re_derives_non_canonical_stored_estado(self):
        assert calcular_estado(0, "Terminado") == "En alistamiento"
        assert calcular_estado(100, "En ejecución") == "Terminado"
        assert calcular_estado(0, "Liquidado") == "En alistamiento"


class TestClasificarFrenteActivo:
    UP_VIAL = {"clase_up": "Obra vial", "tipo_equipamiento": "Vías"}

    def test_active_front_when_en_ejecucion_and_eligible(self):
        interv = {"avance_obra": 50, "presupuesto_base": 200_000_000, "tipo_intervencion": "Obras"}
        assert clasificar_frente_activo(interv, self.UP_VIAL) == "Frente activo"

    def test_inactivo_when_suspendido_and_eligible(self):
        interv = {
            "avance_obra": 50,
            "presupuesto_base": 200_000_000,
            "tipo_intervencion": "Obras",
            "estado": "Suspendido",
        }
        assert clasificar_frente_activo(interv, self.UP_VIAL) == "Inactivo"

    def test_no_aplica_below_minimum_budget(self):
        interv = {"avance_obra": 50, "presupuesto_base": 50_000_000, "tipo_intervencion": "Obras"}
        assert clasificar_frente_activo(interv, self.UP_VIAL) == "No aplica"

    def test_no_aplica_for_subsidio_class(self):
        interv = {"avance_obra": 50, "presupuesto_base": 200_000_000, "tipo_intervencion": "Obras"}
        up = {"clase_up": "Subsidios", "tipo_equipamiento": "Vivienda nueva"}
        assert clasificar_frente_activo(interv, up) == "No aplica"

    def test_no_aplica_for_excluded_intervention_type(self):
        interv = {"avance_obra": 50, "presupuesto_base": 200_000_000, "tipo_intervencion": "Mantenimiento"}
        assert clasificar_frente_activo(interv, self.UP_VIAL) == "No aplica"


class TestLegacyParity:
    """Three-way oracle: the new pure port must equal the legacy implementation
    for every representative case. This is the gate that proves the migration
    preserved the estado contract."""

    @pytest.mark.parametrize(
        "avance, estado",
        [
            (None, None), (0, None), (0.4, None), (0.5, None), (50, None),
            (99.4, None), (99.5, None), (100, None), ("99.8", None), ("abc", None),
            (100, "Suspendido"), (100, "inaugurado"), (0, "Terminado"),
            (100, "En ejecución"), (0, "Liquidado"), (50, "Suspendido"),
        ],
    )
    def test_calcular_estado_matches_legacy(self, avance, estado):
        from api.scripts.unidades_proyecto import _calcular_estado as legacy

        doc = {"avance_obra": avance}
        if estado is not None:
            doc["estado"] = estado
        assert calcular_estado(avance, estado) == legacy(doc)

    @pytest.mark.parametrize(
        "interv, up",
        [
            ({"avance_obra": 50, "presupuesto_base": 200_000_000, "tipo_intervencion": "Obras"},
             {"clase_up": "Obra vial", "tipo_equipamiento": "Vías"}),
            ({"avance_obra": 50, "presupuesto_base": 50_000_000, "tipo_intervencion": "Obras"},
             {"clase_up": "Obra vial", "tipo_equipamiento": "Vías"}),
            ({"avance_obra": 50, "presupuesto_base": 200_000_000, "tipo_intervencion": "Mantenimiento"},
             {"clase_up": "Obra vial", "tipo_equipamiento": "Vías"}),
            ({"avance_obra": 50, "presupuesto_base": 200_000_000, "tipo_intervencion": "Obras", "estado": "Suspendido"},
             {"clase_up": "Obras equipamientos", "tipo_equipamiento": "Parques"}),
            ({"avance_obra": 50, "presupuesto_base": 200_000_000, "tipo_intervencion": "Obras"},
             {"clase_up": "Subsidios", "tipo_equipamiento": "Vivienda nueva"}),
        ],
    )
    def test_frente_activo_matches_legacy(self, interv, up):
        from api.scripts.unidades_proyecto import _clasificar_frente_activo as legacy

        assert clasificar_frente_activo(interv, up) == legacy(interv, up)

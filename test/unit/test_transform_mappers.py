"""Unit tests for the Firestore-document -> domain-entity mappers."""

from decimal import Decimal

import pytest

from etl.transform import (
    firestore_to_avance,
    firestore_to_intervencion,
    firestore_to_unidad,
)

pytestmark = pytest.mark.unit


class TestUnidadMapper:
    def test_maps_core_fields_and_geometry(self):
        doc = {
            "upid": "UNP-1",
            "nombre_up": "Parque",
            "nombre_centro_gestor": "DAGMA",
            "presupuesto_base": "1000.50",
            "ano": "2024",
            "geometry": '{"type": "Point", "coordinates": [-76.5, 3.4]}',
        }
        up = firestore_to_unidad(doc)
        assert up.upid == "UNP-1"
        assert up.centro_gestor == "DAGMA"
        assert up.presupuesto_base == Decimal("1000.50")
        assert up.ano == 2024
        assert up.geometry == {"type": "Point", "coordinates": [-76.5, 3.4]}

    def test_falls_back_to_doc_id(self):
        up = firestore_to_unidad({"_id": "UNP-9"})
        assert up.upid == "UNP-9"


class TestIntervencionMapper:
    def test_whitelist_estado_kept_as_manual(self):
        i = firestore_to_intervencion({"intervencion_id": "I1", "upid": "UNP-1",
                                       "estado": "Suspendido", "avance_obra": "100"})
        assert i.estado_manual == "Suspendido"
        assert i.estado == "Suspendido"

    def test_non_whitelist_estado_dropped_and_rederived(self):
        i = firestore_to_intervencion({"intervencion_id": "I1", "upid": "UNP-1",
                                       "estado": "Terminado", "avance_obra": "0"})
        assert i.estado_manual is None
        assert i.estado == "En alistamiento"  # re-derived from avance 0


class TestAvanceMapper:
    def test_maps_fields(self):
        a = firestore_to_avance({"upid": "UNP-1", "intervencion_id": "I1",
                                 "avance_obra": "45.5", "fecha_avance": "2024-03-01T00:00:00Z"})
        assert a.avance_obra == Decimal("45.5")
        assert a.fecha.year == 2024 and a.fecha.month == 3

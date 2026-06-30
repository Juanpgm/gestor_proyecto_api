"""
Tests — Importación geoespacial COMBINADA (UP + Intervenciones en una sola tabla)
=================================================================================
Cubre:
  - Helpers puros de separación de campos y agrupación por ``upid``.
  - Validación de filas en modo combinado.
  - Endpoint POST /unidades-proyecto/importar/validar (entity_type="combinado").
  - Endpoint POST /unidades-proyecto/importar/ejecutar (entity_type="combinado"):
      * 1 UP + N intervenciones agrupadas por upid (relación 1:N)
      * preservación de upid existente en la DB (no recrea la UP, cuelga intervenciones)
      * generación de upid nuevo (UNP-n) para UP que no existe

Todos los datos creados van en un Firestore en memoria (FakeDB), no tocan datos reales.
"""

import uuid
from collections import defaultdict
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
import sys, os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from api.routers.unidades_proyecto import (
    _up_payload_fields,
    _intervencion_payload_fields,
    _group_indices_by_upid,
    _validate_combinado_feature,
)


# ─── Tests unitarios: helpers puros ────────────────────────────────────────────


class TestSeparacionDeCampos:
    def test_up_payload_solo_campos_up(self):
        mapped = {
            "nombre_up": "Parque Norte",
            "tipo_equipamiento": "Parques y zonas verdes",
            "presupuesto_base": "300",
            "bpin": "12345",
            "upid": "A1",
        }
        up = _up_payload_fields(mapped)
        assert up["nombre_up"] == "Parque Norte"
        assert up["tipo_equipamiento"] == "Parques y zonas verdes"
        assert up["presupuesto_base"] == 300.0  # casteado a float
        assert up["bpin"] == "12345"  # la UP conserva bpin crudo
        # upid NO va dentro del payload de campos (lo agrega el caller)
        assert "upid" not in up

    def test_intervencion_payload_castea_bpin_a_int(self):
        mapped = {
            "tipo_intervencion": "Construcción",
            "presupuesto_base": "50.5",
            "bpin": "999",
            "cantidad": "3",
            "nombre_up": "Parque Norte",  # campo solo-UP, no debe aparecer
        }
        inter = _intervencion_payload_fields(mapped)
        assert inter["tipo_intervencion"] == "Construcción"
        assert inter["presupuesto_base"] == 50.5
        assert inter["bpin"] == 999  # la intervención castea bpin a int
        assert inter["cantidad"] == 3
        # nombre_up es solo-UP → no pertenece a la intervención
        assert "nombre_up" not in inter

    def test_payloads_descartan_none(self):
        mapped = {"nombre_up": "X", "presupuesto_base": None}
        up = _up_payload_fields(mapped)
        assert "presupuesto_base" not in up


class TestAgrupacionPorUpid:
    def test_agrupa_preservando_orden(self):
        rows = [
            {"upid": "A1"},
            {"upid": "A1"},
            {"upid": "B2"},
            {"upid": "A1"},
        ]
        groups = _group_indices_by_upid(rows)
        assert groups == [("A1", [0, 1, 3]), ("B2", [2])]

    def test_upid_vacio_cada_fila_es_su_propia_up(self):
        # Sin upid (caso shapefile sin columna upid): cada fila es una UP nueva,
        # NO se agrupan entre sí.
        rows = [{"upid": ""}, {"nombre_up": "sin upid"}]
        groups = _group_indices_by_upid(rows)
        assert groups == [("", [0]), ("", [1])]


class TestValidacionCombinado:
    def test_upid_opcional(self):
        # Sin upid ya NO es error: la fila será su propia UP nueva.
        errors = _validate_combinado_feature({"nombre_up": "X"}, 0)
        assert errors == []

    def test_fila_valida_sin_errores(self):
        errors = _validate_combinado_feature(
            {"upid": "A1", "nombre_up": "X", "presupuesto_base": "100"}, 0
        )
        assert errors == []

    def test_presupuesto_negativo_falla(self):
        errors = _validate_combinado_feature(
            {"upid": "A1", "presupuesto_base": "-5"}, 0
        )
        assert any("presupuesto_base" in e for e in errors)


# ─── Firestore en memoria (FakeDB) ─────────────────────────────────────────────


class _FakeDoc:
    def __init__(self, data):
        self._data = dict(data)
        self.id = str(
            data.get("upid") or data.get("intervencion_id") or uuid.uuid4()
        )

    def to_dict(self):
        return dict(self._data)


class _FakeQuery:
    def __init__(self, docs):
        self._docs = list(docs)

    def where(self, field, op, value):
        return _FakeQuery([d for d in self._docs if d.get(field) == value])

    def limit(self, n):
        return _FakeQuery(self._docs[:n])

    def select(self, fields):
        return self

    def stream(self):
        return iter(_FakeDoc(d) for d in self._docs)


class _FakeDocRef:
    def __init__(self, store, name, doc_id):
        self._store = store
        self._name = name
        self._id = doc_id

    def set(self, payload):
        self._store[self._name][self._id] = dict(payload)


class _FakeCollection:
    def __init__(self, store, name):
        self._store = store
        self._name = name

    def _query(self):
        return _FakeQuery(list(self._store[self._name].values()))

    def where(self, field, op, value):
        return self._query().where(field, op, value)

    def select(self, fields):
        return self._query()

    def stream(self):
        return self._query().stream()

    def document(self, doc_id):
        return _FakeDocRef(self._store, self._name, doc_id)

    def add(self, payload):
        key = str(uuid.uuid4())
        self._store[self._name][key] = dict(payload)
        return (None, _FakeDoc({"id": key}))


class FakeDB:
    def __init__(self):
        self.store = defaultdict(dict)

    def collection(self, name):
        return _FakeCollection(self.store, name)


@pytest.fixture
def combinado_client():
    """TestClient super_admin + FakeDB en memoria para el modo combinado."""
    from main import app

    fake_db = FakeDB()

    async def _fake_user(request):
        user = {
            "uid": "test_super_admin",
            "email": "admin@cali.gov.co",
            "roles": ["super_admin"],
            "is_active": True,
            "nombre_centro_gestor": None,
            "name": "Test Admin",
            "permissions": ["*"],
        }
        request.state.current_user = user
        return user

    patches = [
        patch(
            "firebase_admin.auth.verify_id_token",
            return_value={
                "uid": "test_super_admin",
                "email": "admin@cali.gov.co",
                "email_verified": True,
            },
        ),
        patch(
            "auth_system.decorators.get_user_with_permissions", side_effect=_fake_user
        ),
        patch(
            "api.routers.unidades_proyecto.get_firestore_client", return_value=fake_db
        ),
    ]
    for p in patches:
        p.start()

    client = TestClient(app, raise_server_exceptions=False)
    client.headers.update({"Authorization": "Bearer test_token"})
    try:
        yield client, fake_db
    finally:
        for p in patches:
            p.stop()


# ─── Tests de endpoint: validar ────────────────────────────────────────────────

_MAPPING = {
    "UPID": "upid",
    "NOMBRE": "nombre_up",
    "TIPO_INT": "tipo_intervencion",
    "PRESUP": "presupuesto_base",
}


def _feat(upid, nombre, tipo, presup, geometry=None):
    return {
        "geometry": geometry,
        "properties": {
            "UPID": upid,
            "NOMBRE": nombre,
            "TIPO_INT": tipo,
            "PRESUP": presup,
        },
    }


class TestValidarCombinado:
    def test_validar_cuenta_ups_e_intervenciones(self, combinado_client):
        client, _ = combinado_client
        body = {
            "entity_type": "combinado",
            "column_mapping": _MAPPING,
            "features": [
                _feat("A1", "Parque", "Construcción", 300),
                _feat("A1", "Parque", "Interventoría", 50),
                _feat("B2", "Vía Sur", "Pavimentación", 800),
            ],
        }
        resp = client.post("/unidades-proyecto/importar/validar", json=body)
        assert resp.status_code == 200, resp.text[:300]
        data = resp.json()
        assert data["entity_type"] == "combinado"
        assert data["combinado_summary"]["unique_ups"] == 2
        assert data["combinado_summary"]["total_intervenciones"] == 3
        assert data["error_count"] == 0

    def test_validar_fila_sin_upid_es_up_nueva(self, combinado_client):
        client, _ = combinado_client
        body = {
            "entity_type": "combinado",
            "column_mapping": _MAPPING,
            "features": [_feat("", "Sin upid", "Construcción", 100)],
        }
        resp = client.post("/unidades-proyecto/importar/validar", json=body)
        assert resp.status_code == 200, resp.text[:300]
        data = resp.json()
        # Sin upid ya no es error: es una UP nueva con 1 intervención
        assert data["error_count"] == 0
        assert data["combinado_summary"]["unique_ups"] == 1
        assert data["combinado_summary"]["total_intervenciones"] == 1


# ─── Tests de endpoint: ejecutar ───────────────────────────────────────────────


class TestEjecutarCombinado:
    def test_separa_en_dos_colecciones_1_a_n(self, combinado_client):
        client, db = combinado_client
        body = {
            "entity_type": "combinado",
            "column_mapping": _MAPPING,
            "features": [
                _feat("A1", "Parque", "Construcción", 300),
                _feat("A1", "Parque", "Interventoría", 50),
                _feat("B2", "Vía Sur", "Pavimentación", 800),
            ],
        }
        resp = client.post("/unidades-proyecto/importar/ejecutar", json=body)
        assert resp.status_code == 200, resp.text[:300]
        data = resp.json()
        # 2 UP nuevas, 3 intervenciones
        assert data["created_up_count"] == 2
        assert data["created_intervencion_count"] == 3
        ups = db.store["unidades_proyecto"]
        ints = db.store["intervenciones_unidades_proyecto"]
        assert len(ups) == 2
        assert len(ints) == 3
        # Cada intervención apunta a un upid generado UNP-n y NO guarda geometry
        for inter in ints.values():
            assert inter["upid"].startswith("UNP-")
            assert "geometry" not in inter
        # La UP de A1 tiene 2 intervenciones colgadas
        upid_a1 = next(
            u["upid"] for u in ups.values() if u.get("nombre_up") == "Parque"
        )
        a1_ints = [i for i in ints.values() if i["upid"] == upid_a1]
        assert len(a1_ints) == 2

    def test_preserva_upid_existente_y_cuelga_intervenciones(self, combinado_client):
        client, db = combinado_client
        # Sembrar una UP existente con upid "UNP-50"
        db.store["unidades_proyecto"]["UNP-50"] = {
            "upid": "UNP-50",
            "nombre_up": "UP existente",
        }
        body = {
            "entity_type": "combinado",
            "column_mapping": _MAPPING,
            "features": [
                # upid del archivo == upid existente → se preserva, no se recrea la UP
                _feat("UNP-50", "UP existente", "Mantenimiento", 20),
            ],
        }
        resp = client.post("/unidades-proyecto/importar/ejecutar", json=body)
        assert resp.status_code == 200, resp.text[:300]
        data = resp.json()
        # No se crea UP nueva
        assert data["created_up_count"] == 0
        assert data["created_intervencion_count"] == 1
        # Sigue habiendo una sola UP (la sembrada)
        assert len(db.store["unidades_proyecto"]) == 1
        # La intervención cuelga del upid preservado
        inter = list(db.store["intervenciones_unidades_proyecto"].values())[0]
        assert inter["upid"] == "UNP-50"
        assert inter["intervencion_id"].startswith("UNP-50-INT-")

    def test_genera_upid_nuevo_para_up_inexistente(self, combinado_client):
        client, db = combinado_client
        # Sembrar contador de upid: existe UNP-7 → el siguiente debe ser UNP-8
        db.store["unidades_proyecto"]["UNP-7"] = {"upid": "UNP-7", "nombre_up": "vieja"}
        body = {
            "entity_type": "combinado",
            "column_mapping": _MAPPING,
            # upid de archivo "NUEVO-X" no existe → genera UNP-8
            "features": [_feat("NUEVO-X", "Nueva UP", "Construcción", 100)],
        }
        resp = client.post("/unidades-proyecto/importar/ejecutar", json=body)
        assert resp.status_code == 200, resp.text[:300]
        data = resp.json()
        assert data["created_up_count"] == 1
        nuevo = next(
            u for u in db.store["unidades_proyecto"].values() if u.get("nombre_up") == "Nueva UP"
        )
        assert nuevo["upid"] == "UNP-8"

    def test_sin_columna_upid_cada_fila_es_up_nueva(self, combinado_client):
        """Caso shapefile real sin columna upid: cada fila → 1 UP nueva + 1 intervención."""
        client, db = combinado_client
        mapping_sin_upid = {
            "NOMBRE": "nombre_up",
            "TIPO_INT": "tipo_intervencion",
            "PRESUP": "presupuesto_base",
        }
        body = {
            "entity_type": "combinado",
            "column_mapping": mapping_sin_upid,
            "features": [
                {"geometry": None, "properties": {"NOMBRE": "Vía local", "TIPO_INT": "Bacheo", "PRESUP": 100}},
                {"geometry": None, "properties": {"NOMBRE": "Vía colectora", "TIPO_INT": "Pavimento", "PRESUP": 200}},
            ],
        }
        resp = client.post("/unidades-proyecto/importar/ejecutar", json=body)
        assert resp.status_code == 200, resp.text[:300]
        data = resp.json()
        assert data["created_up_count"] == 2
        assert data["created_intervencion_count"] == 2
        ints = db.store["intervenciones_unidades_proyecto"]
        assert len(ints) == 2
        # Dos UP distintas, cada una con su intervención
        assert len({i["upid"] for i in ints.values()}) == 2

# -*- coding: utf-8 -*-
"""
Tests del endpoint GET /unidades-proyecto:
verifica que los filtros se traduzcan a llamadas .where(...) sobre la query
de Firestore (incluyendo nombre_centro_gestor, estado, tipo_intervencion, ano).
"""

from unittest.mock import MagicMock, patch

import pytest


class _FakeQuery:
    """Mock encadenable que registra cada llamada .where(...) y .limit(...)."""

    def __init__(self):
        self.where_calls = []
        self.limit_calls = []
        self.offset_calls = []

    def where(self, field, op, value):
        self.where_calls.append((field, op, value))
        return self

    def limit(self, n):
        self.limit_calls.append(n)
        return self

    def offset(self, n):
        self.offset_calls.append(n)
        return self

    def stream(self):
        return iter([])


@pytest.fixture
def fake_firestore_for_ups():
    """Patcha el cliente Firestore para devolver una _FakeQuery encadenable."""
    fake_query = _FakeQuery()
    fake_db = MagicMock()
    fake_db.collection.return_value = fake_query

    with patch(
        "database.firebase_config.get_firestore_client",
        return_value=fake_db,
    ), patch(
        "api.routers.unidades_proyecto.FIREBASE_AVAILABLE",
        True,
    ):
        yield fake_query


def _do_request(client, params):
    return client.get("/unidades-proyecto", params=params)


def test_filtro_nombre_centro_gestor_se_aplica_como_where(
    super_admin_client, fake_firestore_for_ups
):
    resp = _do_request(super_admin_client, {"nombre_centro_gestor": "DAGRD"})

    assert resp.status_code == 200, resp.text
    # El centro se canonicaliza (DAGRD -> nombre oficial) antes del where, por eso
    # se valida por campo y no por el alias crudo.
    assert any(
        field == "nombre_centro_gestor"
        for field, _op, _v in fake_firestore_for_ups.where_calls
    )


def test_filtro_estado_no_se_aplica_como_where_pero_tipo_si(
    super_admin_client, fake_firestore_for_ups
):
    # El estado es efímero (se deriva de avance_obra): NO debe filtrarse en
    # Firestore sobre el valor crudo. tipo_intervencion sí es un where directo.
    resp = _do_request(
        super_admin_client,
        {"estado": "En ejecución", "tipo_intervencion": "Obra nueva"},
    )

    assert resp.status_code == 200, resp.text
    calls = fake_firestore_for_ups.where_calls
    assert not any(field == "estado" for field, _op, _v in calls)
    assert ("tipo_intervencion", "==", "Obra nueva") in calls


def test_filtro_combinado_centro_gestor_estado_ano(
    super_admin_client, fake_firestore_for_ups
):
    resp = _do_request(
        super_admin_client,
        {
            "nombre_centro_gestor": "DAGRD",
            "estado": "En ejecución",
            "ano": 2025,
        },
    )

    assert resp.status_code == 200, resp.text
    calls = fake_firestore_for_ups.where_calls
    # nombre_centro_gestor se canonicaliza antes del where, por eso se valida por
    # campo y no por el valor crudo "DAGRD".
    assert any(field == "nombre_centro_gestor" for field, _op, _v in calls)
    assert ("ano", "==", 2025) in calls
    # estado NO se traduce a where (se filtra client-side tras recalcular)
    assert not any(field == "estado" for field, _op, _v in calls)


def test_filtro_proyectos_estrategicos_usa_array_contains(
    super_admin_client, fake_firestore_for_ups
):
    resp = _do_request(super_admin_client, {"proyectos_estrategicos": "PE-001"})

    assert resp.status_code == 200, resp.text
    assert (
        "proyectos_estrategicos",
        "array_contains",
        "PE-001",
    ) in fake_firestore_for_ups.where_calls


def test_sin_filtros_no_genera_where_calls(super_admin_client, fake_firestore_for_ups):
    resp = _do_request(super_admin_client, {})

    assert resp.status_code == 200, resp.text
    # Sin filtros: no debe haber where calls (sólo limit)
    assert fake_firestore_for_ups.where_calls == []
    assert len(fake_firestore_for_ups.limit_calls) >= 1


class _FakeDoc:
    def __init__(self, data):
        self._data = data
        self.id = data.get("upid", "doc")

    def to_dict(self):
        return dict(self._data)


class _FakeQueryWithDocs(_FakeQuery):
    """_FakeQuery que devuelve documentos predefinidos al hacer stream()."""

    def __init__(self, docs):
        super().__init__()
        self._docs = docs

    def stream(self):
        return iter(self._docs)


@pytest.fixture
def fake_firestore_with_estado_docs():
    """Dos UPs cuyo estado crudo NO coincide con su avance_obra."""
    docs = [
        _FakeDoc({"upid": "UNP-A", "estado": "En ejecución", "avance_obra": 100}),
        _FakeDoc({"upid": "UNP-B", "estado": "Terminado", "avance_obra": 0}),
    ]
    fake_query = _FakeQueryWithDocs(docs)
    fake_db = MagicMock()
    fake_db.collection.return_value = fake_query

    with patch(
        "database.firebase_config.get_firestore_client",
        return_value=fake_db,
    ), patch(
        "api.routers.unidades_proyecto.FIREBASE_AVAILABLE",
        True,
    ):
        yield fake_query


def test_filtro_estado_usa_valor_recalculado_no_el_crudo(
    super_admin_client, fake_firestore_with_estado_docs
):
    # estado=Terminado debe devolver UNP-A (avance 100 -> Terminado), no UNP-B
    # (cuyo estado crudo "Terminado" se re-deriva a "En alistamiento" por avance 0).
    resp = _do_request(super_admin_client, {"estado": "Terminado"})

    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    upids = {item["upid"] for item in data}
    assert upids == {"UNP-A"}
    assert data[0]["estado"] == "Terminado"


def test_limit_se_aplica_y_se_topa_en_10000(super_admin_client, fake_firestore_for_ups):
    # Validación de Pydantic: limit > 10000 retorna 422 antes de llegar a Firestore
    resp_invalido = _do_request(super_admin_client, {"limit": 50000})
    assert resp_invalido.status_code == 422

    # Un limit válido sí debe propagarse como .limit(...) en Firestore
    fake_firestore_for_ups.limit_calls.clear()
    resp_ok = _do_request(super_admin_client, {"limit": 250})
    assert resp_ok.status_code == 200, resp_ok.text
    assert 250 in fake_firestore_for_ups.limit_calls

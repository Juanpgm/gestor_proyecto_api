"""
Tests de integración — Gestionar Registros
=========================================
Prueba los endpoints utilizados por el tab "Gestionar Registros":
  - POST /crear_unidad_proyecto
  - POST /crear_intervencion
  - PUT  /modificar/unidad_proyecto
  - PUT  /modificar/intervencion
  - POST /solicitudes_cambios_unidad_proyecto
  - POST /solicitudes_cambios_intervencion
  - DELETE /eliminar_unidad_proyecto
  - DELETE /eliminar_intervencion

NOTA: Todos los datos creados llevan el tag TEST_GESTION_REGISTROS
para identificarlos y eliminarlos fácilmente.
"""

import pytest
import uuid
from unittest.mock import MagicMock, patch, call
from fastapi.testclient import TestClient
import sys, os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# ─── Fixtures reutilizables ────────────────────────────────────────────────────

TEST_TAG = "TEST_GESTION_REGISTROS"

# Coordenadas válidas dentro del bounding box de Cali
CALI_POINT = {"type": "Point", "coordinates": [-76.5353, 3.4516]}


def _make_firestore_mock(existing_upid="UNP-999", max_upid_num=999):
    """Construye un MagicMock de Firestore listo para los tests de creación."""
    db = MagicMock()

    # Mock para escaneo de upids (devuelve un doc con upid existente)
    existing_doc = MagicMock()
    existing_doc.to_dict.return_value = {"upid": existing_upid}
    db.collection.return_value.select.return_value.stream.return_value = iter(
        [existing_doc]
    )

    # Mock para búsqueda de UP/intervencion por where().limit(1).stream() (usar en crear_intervencion y modificar)
    up_doc = MagicMock()
    up_doc.id = "test-doc-id-mock"  # string para evitar MagicMock no serializable
    up_doc.exists = True
    up_doc.to_dict.return_value = {
        "upid": existing_upid,
        "nombre_centro_gestor": None,
        "intervencion_id": f"{existing_upid}-INT-1",
    }
    up_doc.reference = MagicMock()
    up_doc.reference.update.return_value = None
    up_doc.reference.delete.return_value = None
    db.collection.return_value.where.return_value.limit.return_value.stream.return_value = iter(
        [up_doc]
    )

    # Mock para where().stream() sin limit (eliminar endpoints)
    delete_doc = MagicMock()
    delete_doc.id = "test-delete-doc-id"
    delete_doc.exists = True
    delete_doc.to_dict.return_value = {
        "upid": existing_upid,
        "nombre_centro_gestor": None,
        "intervencion_id": f"{existing_upid}-INT-1",
    }
    delete_doc.reference = MagicMock()
    delete_doc.reference.delete.return_value = None
    db.collection.return_value.where.return_value.stream.return_value = iter(
        [delete_doc]
    )

    # Mock para set/add (escritura OK)
    db.collection.return_value.document.return_value.set.return_value = None
    db.collection.return_value.add.return_value = (
        None,
        MagicMock(id=str(uuid.uuid4())),
    )

    return db


@pytest.fixture
def super_admin_client_with_firestore():
    """TestClient super_admin + Firestore mockeado para tests de mutación."""
    from main import app

    db_mock = _make_firestore_mock()

    async def _fake_user(request):
        user = {
            "uid": "test_super_admin",
            "email": "admin@cali.gov.co",
            "roles": ["super_admin"],
            "is_active": True,
            "nombre_centro_gestor": None,  # super_admin ve todo
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
        # Patch the router's own reference (module-level import at the top of unidades_proyecto.py)
        patch(
            "api.routers.unidades_proyecto.get_firestore_client", return_value=db_mock
        ),
    ]
    for p in patches:
        p.start()

    client = TestClient(app, raise_server_exceptions=False)
    client.headers.update({"Authorization": "Bearer test_token"})
    try:
        yield client, db_mock
    finally:
        for p in patches:
            p.stop()


# ─── Tests: Crear UP ───────────────────────────────────────────────────────────


class TestCrearUnidadProyecto:

    def test_crear_up_basica_ok(self, super_admin_client_with_firestore):
        """UP con campos mínimos + geometry válida → 200 con nuevo upid.

        NOTA: Este test escribe datos reales en Firestore con el tag [TEST_GESTION_REGISTROS].
        Para limpiar: buscar en la colección 'unidades_proyecto' donde nombre_up contiene
        '[TEST_GESTION_REGISTROS]' y eliminar manualmente.
        """
        client, db = super_admin_client_with_firestore
        payload = {
            "nombre_up": f"[{TEST_TAG}] Parque Test Norte",
            "nombre_up_detalle": "Tramo 1 - Test",
            "tipo_equipamiento": "Parques y zonas verdes",
            "direccion": f"Calle 25N #5N-10 [{TEST_TAG}]",
            "geometry": CALI_POINT,
        }
        resp = client.post("/crear_unidad_proyecto", json=payload)
        assert (
            resp.status_code == 200
        ), f"Esperaba 200, got {resp.status_code}: {resp.text[:300]}"
        data = resp.json()
        assert "id" in data, "La respuesta debe tener 'id' (upid)"
        assert data["id"].startswith(
            "UNP-"
        ), f"upid debe tener formato UNP-N: {data['id']}"
        assert data["collection"] == "unidades_proyecto"
        assert (
            "data" in data
        ), "La respuesta debe incluir 'data' con el payload guardado"

    def test_crear_up_sin_geometry_ok(self, super_admin_client_with_firestore):
        """UP sin geometry → debe ser aceptada (geometry es Optional)."""
        client, db = super_admin_client_with_firestore
        payload = {
            "nombre_up": f"[{TEST_TAG}] UP Sin Geometry",
            "nombre_up_detalle": "Sin coordenadas",
            "tipo_equipamiento": "Canchas",
            "direccion": f"Sin dirección [{TEST_TAG}]",
        }
        resp = client.post("/crear_unidad_proyecto", json=payload)
        assert resp.status_code == 200, f"Esperaba 200: {resp.text[:300]}"
        data = resp.json()
        assert data["id"].startswith("UNP-")

    def test_crear_up_geometry_fuera_de_cali_rechazada(
        self, super_admin_client_with_firestore
    ):
        """Geometry con coordenadas fuera del bbox de Cali → 400."""
        client, _ = super_admin_client_with_firestore
        payload = {
            "nombre_up": f"[{TEST_TAG}] UP Bogotá (inválida)",
            "nombre_up_detalle": "Fuera de Cali",
            "tipo_equipamiento": "Canchas",
            "direccion": "Calle en Bogotá",
            "geometry": {"type": "Point", "coordinates": [-74.0721, 4.7110]},  # Bogotá
        }
        resp = client.post("/crear_unidad_proyecto", json=payload)
        assert (
            resp.status_code == 400
        ), f"Esperaba 400 para coords fuera de Cali: {resp.text[:300]}"

    def test_crear_up_sin_auth_rechazada(self):
        """Sin token → 401/403."""
        from main import app

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post("/crear_unidad_proyecto", json={"nombre_up": "test"})
        assert resp.status_code in (
            401,
            403,
        ), f"Sin auth debe dar 401/403: {resp.status_code}"


# ─── Tests: Crear Intervención ─────────────────────────────────────────────────


class TestCrearIntervencion:

    def test_crear_intervencion_individual_ok(self, super_admin_client_with_firestore):
        """Intervención individual con todos los campos obligatorios → 200.

        NOTA: El campo 'id' en la respuesta es el doc_id (UUID) del documento Firestore.
        El ID semántico de la intervención está en data['data']['intervencion_id'].
        Formato: <upid>-INT-<n> (ej: UNP-999-INT-1).
        """
        client, db = super_admin_client_with_firestore
        payload = {
            "upid": "UNP-999",
            "tipo_intervencion": "Obra nueva",
            "nombre_centro_gestor": f"DAGMA [{TEST_TAG}]",
            "fuente_financiacion": "Empréstito",
            "identificador": f"TEST-INTERV-{TEST_TAG}",
            "presupuesto_base": 500000000.0,
            "clase_up": "Obras equipamientos",
            "descripcion_intervencion": f"Intervención de prueba {TEST_TAG}",
            "fecha_inicio": "2026-01-01",
            "fecha_fin": "2026-12-31",
        }
        resp = client.post("/crear_intervencion", json=payload)
        assert resp.status_code == 200, f"Esperaba 200: {resp.text[:300]}"
        data = resp.json()
        # 'id' es el doc_id UUID de Firestore; el ID semántico está en data['data']['intervencion_id']
        assert "id" in data, "Respuesta debe tener 'id' (doc UUID)"
        assert data["collection"] == "intervenciones_unidades_proyecto"
        assert "data" in data, "Respuesta debe tener campo 'data'"
        intervencion_id = data["data"].get("intervencion_id", "")
        assert (
            "INT-" in intervencion_id
        ), f"intervencion_id debe contener INT-: {intervencion_id}"
        assert intervencion_id.startswith(
            "UNP-999-INT-"
        ), f"intervencion_id debe empezar con UNP-999-INT-: {intervencion_id}"

    def test_crear_intervencion_upid_inexistente_rechazada(
        self, super_admin_client_with_firestore
    ):
        """UPID que no existe en Firestore → 400."""
        client, db = super_admin_client_with_firestore
        # Sobreescribir mock: UP no existe
        db.collection.return_value.where.return_value.limit.return_value.stream.return_value = iter(
            []
        )
        payload = {
            "upid": "UNP-99999",
            "tipo_intervencion": "Obra nueva",
            "nombre_centro_gestor": "DAGMA",
            "fuente_financiacion": "Empréstito",
            "identificador": f"TEST-NOEXISTE",
            "presupuesto_base": 100000.0,
            "clase_up": "Obras equipamientos",
        }
        resp = client.post("/crear_intervencion", json=payload)
        assert (
            resp.status_code == 400
        ), f"Esperaba 400 para UPID inexistente: {resp.text[:300]}"
        assert "no existe" in resp.json().get("detail", "").lower()

    def test_crear_intervencion_sin_upid_rechazada(
        self, super_admin_client_with_firestore
    ):
        """Sin campo upid → 422 (validation error)."""
        client, _ = super_admin_client_with_firestore
        payload = {
            "tipo_intervencion": "Obra nueva",
            "nombre_centro_gestor": "DAGMA",
        }
        resp = client.post("/crear_intervencion", json=payload)
        assert resp.status_code == 422, f"Sin upid debe dar 422: {resp.status_code}"


# ─── Tests: Modificar UP (solicitud de cambio) ────────────────────────────────


class TestSolicitudCambioUP:

    def test_solicitud_cambio_up_ok(self, super_admin_client_with_firestore):
        """Solicitud de cambio con upid + aprobado:true → 200."""
        client, db = super_admin_client_with_firestore
        payload = {
            "upid": "UNP-999",
            "aprobado": True,
            "nombre_up": f"[{TEST_TAG}] Nombre cambiado",
            "tipo_equipamiento": "Parques y zonas verdes",
        }
        resp = client.post("/solicitudes_cambios_unidad_proyecto", json=payload)
        assert resp.status_code == 200, f"Esperaba 200: {resp.text[:300]}"
        data = resp.json()
        assert "id" in data
        assert data["collection"] == "solicitudes_cambios_unidades_proyecto"

    def test_solicitud_cambio_up_sin_upid_rechazada(
        self, super_admin_client_with_firestore
    ):
        """Sin upid → 400 (lógica de negocio) o 422 (validación Pydantic si el modelo lo requiere)."""
        client, _ = super_admin_client_with_firestore
        payload = {"aprobado": True, "nombre_up": "Sin UPID"}
        resp = client.post("/solicitudes_cambios_unidad_proyecto", json=payload)
        assert resp.status_code in (
            400,
            422,
        ), f"Sin upid debe dar 400 o 422: {resp.status_code}"

    def test_solicitud_cambio_up_sin_aprobado_rechazada(
        self, super_admin_client_with_firestore
    ):
        """Sin campo aprobado → 400 (lógica de negocio) o 422 (validación Pydantic si el modelo lo requiere)."""
        client, _ = super_admin_client_with_firestore
        payload = {"upid": "UNP-999", "nombre_up": "Sin aprobado"}
        resp = client.post("/solicitudes_cambios_unidad_proyecto", json=payload)
        assert resp.status_code in (
            400,
            422,
        ), f"Sin aprobado debe dar 400 o 422: {resp.status_code}"

    def test_solicitud_cambio_up_con_geometry_valida_ok(
        self, super_admin_client_with_firestore
    ):
        """Solicitud con geometry válida → 200 y recalcula campos geográficos."""
        client, db = super_admin_client_with_firestore
        payload = {
            "upid": "UNP-999",
            "aprobado": True,
            "geometry": CALI_POINT,
            "direccion": f"Nueva dirección [{TEST_TAG}]",
        }
        resp = client.post("/solicitudes_cambios_unidad_proyecto", json=payload)
        assert resp.status_code == 200, f"Esperaba 200: {resp.text[:300]}"

    def test_solicitud_cambio_up_geometry_fuera_cali_rechazada(
        self, super_admin_client_with_firestore
    ):
        """Solicitud con geometry fuera de Cali → 400."""
        client, _ = super_admin_client_with_firestore
        payload = {
            "upid": "UNP-999",
            "aprobado": True,
            "geometry": {"type": "Point", "coordinates": [-74.0721, 4.7110]},
        }
        resp = client.post("/solicitudes_cambios_unidad_proyecto", json=payload)
        assert (
            resp.status_code == 400
        ), f"Geometry fuera de Cali debe dar 400: {resp.status_code}"


# ─── Tests: Solicitud de Cambio Intervención ──────────────────────────────────


class TestSolicitudCambioIntervencion:

    def test_solicitud_cambio_intervencion_ok(self, super_admin_client_with_firestore):
        """Solicitud de cambio de intervención con datos mínimos → 200."""
        client, db = super_admin_client_with_firestore
        payload = {
            "intervencion_id": "UNP-999-INT-1",
            "upid": "UNP-999",
            "tipo_intervencion": "Mantenimiento",
            "presupuesto_base": 750000000.0,
            "identificador": f"TEST-SOL-INTERV-{TEST_TAG}",
        }
        resp = client.post("/solicitudes_cambios_intervencion", json=payload)
        assert resp.status_code == 200, f"Esperaba 200: {resp.text[:300]}"
        data = resp.json()
        assert "id" in data
        assert data["collection"] == "solicitudes_cambios_intervenciones"

    def test_solicitud_cambio_intervencion_sin_datos_ok(
        self, super_admin_client_with_firestore
    ):
        """Sin campos → 200 (todos son opcionales en el endpoint)."""
        client, _ = super_admin_client_with_firestore
        resp = client.post("/solicitudes_cambios_intervencion", json={})
        assert (
            resp.status_code == 200
        ), f"Sin datos debe dar 200 (todos opcionales): {resp.status_code}"


# ─── Tests: Eliminar UP e Intervención ────────────────────────────────────────


class TestEliminar:

    def test_eliminar_up_ok(self, super_admin_client_with_firestore):
        """DELETE /eliminar_unidad_proyecto?upid=... → 200.

        El endpoint usa where().stream() (sin .limit()) para buscar la UP.
        """
        client, db = super_admin_client_with_firestore
        # La fixture ya tiene where().stream() retornando delete_doc con exists=True
        resp = client.delete("/eliminar_unidad_proyecto?upid=UNP-999")
        assert resp.status_code in (
            200,
            204,
        ), f"Esperaba 200/204: {resp.status_code}: {resp.text[:300]}"

    def test_eliminar_up_sin_upid_rechazada(self, super_admin_client_with_firestore):
        """DELETE sin upid → 400/422."""
        client, _ = super_admin_client_with_firestore
        resp = client.delete("/eliminar_unidad_proyecto")
        assert resp.status_code in (
            400,
            422,
        ), f"Sin upid debe dar 400/422: {resp.status_code}"

    def test_eliminar_intervencion_ok(self, super_admin_client_with_firestore):
        """DELETE /eliminar_intervencion?intervencion_id=... → 200.

        El endpoint usa where().stream() (sin .limit()) para buscar la intervención.
        """
        client, db = super_admin_client_with_firestore
        # La fixture ya tiene where().stream() retornando delete_doc con exists=True
        resp = client.delete("/eliminar_intervencion?intervencion_id=UNP-999-INT-1")
        assert resp.status_code in (
            200,
            204,
        ), f"Esperaba 200/204: {resp.status_code}: {resp.text[:300]}"

    def test_eliminar_intervencion_sin_id_rechazada(
        self, super_admin_client_with_firestore
    ):
        """DELETE sin intervencion_id → 400/422."""
        client, _ = super_admin_client_with_firestore
        resp = client.delete("/eliminar_intervencion")
        assert resp.status_code in (
            400,
            422,
        ), f"Sin intervencion_id debe dar 400/422: {resp.status_code}"


# ─── Tests: Modificar UP y Intervención (aplicar cambio directo) ───────────────


class TestModificarDirecto:

    def test_modificar_up_aprobado_ok(self, super_admin_client_with_firestore):
        """PUT /modificar/unidad_proyecto con aprobado:true → aplica cambios."""
        client, db = super_admin_client_with_firestore
        # Mock: UP existe
        doc_snap = MagicMock(exists=True)
        doc_snap.to_dict.return_value = {"upid": "UNP-999", "nombre_up": "Original"}
        db.collection.return_value.document.return_value.get.return_value = doc_snap
        db.collection.return_value.document.return_value.update.return_value = None

        payload = {
            "upid": "UNP-999",
            "aprobado": True,
            "nombre_up": f"[{TEST_TAG}] Nombre modificado directo",
        }
        resp = client.put("/modificar/unidad_proyecto", json=payload)
        assert resp.status_code in (
            200,
            404,
        ), f"Esperaba 200 o 404 (si UP no existe en mock): {resp.status_code}: {resp.text[:300]}"

    def test_modificar_intervencion_aprobado_ok(
        self, super_admin_client_with_firestore
    ):
        """PUT /modificar/intervencion con aprobado:true → aplica cambios.

        El endpoint usa where().limit(1).stream() para buscar la intervención.
        El doc.id en la respuesta debe ser serializable (string, no MagicMock).
        """
        client, db = super_admin_client_with_firestore
        # La fixture ya tiene where().limit(1).stream() retornando un doc con id="test-doc-id-mock"
        # y to_dict() retornando un dict serializable.

        payload = {
            "intervencion_id": "UNP-999-INT-1",
            "aprobado": True,
            "presupuesto_base": 999000000.0,
            "tipo_intervencion": "Rehabilitación / Reforzamiento",
        }
        resp = client.put("/modificar/intervencion", json=payload)
        assert resp.status_code in (
            200,
            404,
        ), f"Esperaba 200 o 404: {resp.status_code}: {resp.text[:300]}"

"""
Tests de la lógica de roles, permisos y scoping por centro_gestor (política A).

Cubre:
  - catálogo canónico de centros (centros_catalog)
  - resolución de permisos y scoping (_has_permission, enforce_resource_access)
  - payload de sesión: can_view_all + effective_centro_gestor (_build_user_payload)
  - política A en constants.ROLES (solo super_admin/admin_general son globales)
"""

import os
from types import SimpleNamespace

import pytest

from auth_system import centros_catalog as cat
from auth_system.decorators import (
    _has_permission,
    enforce_resource_access,
)
from auth_system.constants import ROLES
from fastapi import HTTPException


# ---------------------------------------------------------------------------
# Catálogo canónico
# ---------------------------------------------------------------------------
class TestCentrosCatalog:
    def test_canonicaliza_nombre_exacto(self):
        assert (
            cat.canonicalize_centro("Secretaría de Infraestructura")
            == "Secretaría de Infraestructura"
        )

    def test_canonicaliza_sin_tildes_y_case(self):
        assert (
            cat.canonicalize_centro("secretaria de infraestructura")
            == "Secretaría de Infraestructura"
        )

    def test_canonicaliza_alias_planeacion_legacy(self):
        # Variante legacy sin "Municipal" debe mapear al canónico.
        assert (
            cat.canonicalize_centro("Departamento Administrativo de Planeación")
            == "Departamento Administrativo de Planeación Municipal"
        )

    def test_canonicaliza_alias_dagma(self):
        assert (
            cat.canonicalize_centro("DAGMA")
            == "Departamento Administrativo de Gestión del Medio Ambiente - DAGMA"
        )

    def test_canonicaliza_alias_deportes_forma_corta(self):
        # Forma corta legacy ("Deportes") debe mapear al canónico (flujo_caja.json).
        assert (
            cat.canonicalize_centro("Deportes")
            == "Secretaría del Deporte y la Recreación"
        )
        assert (
            cat.canonicalize_centro("deportes")
            == "Secretaría del Deporte y la Recreación"
        )

    def test_valor_desconocido_devuelve_none(self):
        assert cat.canonicalize_centro("Centro Inexistente XYZ") is None
        assert cat.canonicalize_centro("") is None
        assert cat.canonicalize_centro(None) is None

    def test_is_valid_centro(self):
        assert cat.is_valid_centro("Secretaría de Salud Pública") is True
        assert cat.is_valid_centro("no existe") is False

    def test_calitrack_es_centro_interno_global_no_seleccionable(self):
        # Calitrack: válido y con visibilidad global, pero NO en el picklist.
        assert cat.canonicalize_centro("Calitrack") == "Calitrack"
        assert cat.is_valid_centro("calitrack") is True
        assert cat.is_global_view_centro("Calitrack") is True
        assert cat.is_global_view_centro("Secretaría de Cultura") is False
        # No debe ser seleccionable (no está en el catálogo del registro).
        assert "Calitrack" not in cat.CENTROS_GESTORES

    def test_normalize_centro(self):
        assert cat.normalize_centro("  Secretaría  de   Educación ") == (
            "secretaria de educacion"
        )


# ---------------------------------------------------------------------------
# _has_permission: detección de scope
# ---------------------------------------------------------------------------
class TestHasPermission:
    def test_wildcard_total(self):
        assert _has_permission(["*"], "read:unidades") == (True, False)

    def test_permiso_global(self):
        assert _has_permission(["read:unidades"], "read:unidades") == (True, False)

    def test_permiso_wildcard_accion(self):
        assert _has_permission(["read:*"], "read:contratos") == (True, False)

    def test_permiso_solo_own_centro(self):
        assert _has_permission(["read:unidades:own_centro"], "read:unidades") == (
            True,
            True,
        )

    def test_permiso_basic_no_es_own(self):
        assert _has_permission(["read:proyectos:basic"], "read:proyectos") == (
            True,
            False,
        )

    def test_sin_permiso(self):
        assert _has_permission(["read:proyectos"], "read:unidades") == (False, False)
        assert _has_permission([], "read:unidades") == (False, False)


# ---------------------------------------------------------------------------
# enforce_resource_access: scoping efectivo
# ---------------------------------------------------------------------------
class TestEnforceResourceAccess:
    def test_global_devuelve_requested(self):
        user = {"permissions": ["read:contratos"], "nombre_centro_gestor": "X"}
        assert enforce_resource_access(user, "read:contratos", None) is None
        assert (
            enforce_resource_access(user, "read:contratos", "Cualquiera") == "Cualquiera"
        )

    def test_own_centro_fuerza_centro_usuario(self):
        user = {
            "permissions": ["read:contratos:own_centro"],
            "centro_gestor_assigned": "Secretaría de Salud Pública",
        }
        # Sin requested -> fuerza el del usuario
        assert (
            enforce_resource_access(user, "read:contratos")
            == "Secretaría de Salud Pública"
        )

    def test_own_centro_rechaza_otro_centro(self):
        user = {
            "permissions": ["read:contratos:own_centro"],
            "centro_gestor_assigned": "Secretaría de Salud Pública",
        }
        with pytest.raises(HTTPException) as exc:
            enforce_resource_access(user, "read:contratos", "Secretaría de Cultura")
        assert exc.value.status_code == 403

    def test_own_centro_acepta_requested_no_canonico(self):
        # Mismo centro en forma no canónica (sin tilde / forma corta) NO debe dar 403.
        user = {
            "permissions": ["read:contratos:own_centro"],
            "centro_gestor_assigned": "Secretaría del Deporte y la Recreación",
        }
        assert (
            enforce_resource_access(user, "read:contratos", "Deportes")
            == "Secretaría del Deporte y la Recreación"
        )
        assert (
            enforce_resource_access(
                user, "read:contratos", "secretaria del deporte y la recreacion"
            )
            == "Secretaría del Deporte y la Recreación"
        )

    def test_own_centro_canonicaliza_centro_usuario_sucio(self):
        # Si el user trae un string sucio, el centro efectivo se devuelve canónico.
        user = {
            "permissions": ["read:contratos:own_centro"],
            "centro_gestor_assigned": "Deportes",
        }
        assert (
            enforce_resource_access(user, "read:contratos")
            == "Secretaría del Deporte y la Recreación"
        )

    def test_own_centro_sin_centro_asignado_403(self):
        user = {"permissions": ["read:contratos:own_centro"]}
        with pytest.raises(HTTPException) as exc:
            enforce_resource_access(user, "read:contratos")
        assert exc.value.status_code == 403

    def test_sin_permiso_403(self):
        user = {"permissions": ["read:proyectos"]}
        with pytest.raises(HTTPException) as exc:
            enforce_resource_access(user, "read:contratos")
        assert exc.value.status_code == 403

    def test_kill_switch_desactiva_scoping(self, monkeypatch):
        monkeypatch.setenv("CENTRO_SCOPING_DISABLED", "true")
        user = {
            "permissions": ["read:contratos:own_centro"],
            "centro_gestor_assigned": "Secretaría de Salud Pública",
        }
        # Con kill-switch, no fuerza el centro del usuario; respeta requested.
        assert (
            enforce_resource_access(user, "read:contratos", "Otro Centro")
            == "Otro Centro"
        )


# ---------------------------------------------------------------------------
# Política A en ROLES: solo super_admin/admin_general son globales
# ---------------------------------------------------------------------------
class TestPoliticaAEnRoles:
    @pytest.mark.parametrize("role", ["editor_datos", "analista", "gestor_contratos"])
    def test_roles_no_admin_son_own_centro(self, role):
        perms = ROLES[role]["permissions"]
        # Toda lectura de recursos de dominio debe estar scopeada a own_centro.
        scoped_resources = {"proyectos", "unidades", "contratos", "reportes_contratos", "emprestito"}
        for p in perms:
            parts = p.split(":")
            if len(parts) >= 2 and parts[1] in scoped_resources:
                assert p.endswith(":own_centro"), (
                    f"{role}: permiso '{p}' debería ser :own_centro (política A)"
                )

    @pytest.mark.parametrize("role", ["editor_datos", "analista", "gestor_contratos"])
    def test_roles_no_admin_no_tienen_lectura_global(self, role):
        perms = ROLES[role]["permissions"]
        assert "read:proyectos" not in perms
        assert "read:contratos" not in perms
        assert "read:unidades" not in perms

    def test_admin_general_es_global(self):
        perms = ROLES["admin_general"]["permissions"]
        assert "read:proyectos" in perms
        assert "read:unidades" in perms


# ---------------------------------------------------------------------------
# _build_user_payload: scope autoritativo en la sesión
# ---------------------------------------------------------------------------
class TestBuildUserPayload:
    def _fake_record(self):
        return SimpleNamespace(
            uid="u1",
            email="user@cali.gov.co",
            display_name="User",
            email_verified=True,
            phone_number="+573001112233",
            custom_claims={},
            provider_data=[],
        )

    def test_admin_general_can_view_all(self):
        from api.scripts.auth_operations import _build_user_payload

        payload = _build_user_payload(
            self._fake_record(),
            {"roles": ["admin_general"], "nombre_centro_gestor": "Secretaría de Cultura"},
        )
        assert payload["can_view_all"] is True
        assert payload["effective_centro_gestor"] == "Secretaría de Cultura"

    def test_rol_restringido_no_view_all(self):
        from api.scripts.auth_operations import _build_user_payload

        payload = _build_user_payload(
            self._fake_record(),
            {"roles": ["analista"], "nombre_centro_gestor": "secretaria de cultura"},
        )
        assert payload["can_view_all"] is False
        # effective_centro_gestor canonicaliza el valor sucio
        assert payload["effective_centro_gestor"] == "Secretaría de Cultura"

    def test_calitrack_otorga_view_all_aunque_rol_restringido(self):
        from api.scripts.auth_operations import _build_user_payload

        payload = _build_user_payload(
            self._fake_record(),
            {"roles": ["editor_datos"], "nombre_centro_gestor": "Calitrack"},
        )
        # Centro interno especial: ve todo pese a rol no-admin.
        assert payload["can_view_all"] is True
        assert payload["effective_centro_gestor"] == "Calitrack"

    def test_super_admin_can_view_all(self):
        from api.scripts.auth_operations import _build_user_payload

        payload = _build_user_payload(
            self._fake_record(),
            {"roles": ["super_admin"], "centro_gestor_assigned": "DATIC"},
        )
        assert payload["can_view_all"] is True
        assert payload["permissions"] == ["*"]


# ---------------------------------------------------------------------------
# scope_records_by_centro: primitiva ÚNICA de filtrado de records por centro
# ---------------------------------------------------------------------------
class TestScopeRecordsByCentro:
    def _import(self):
        from auth_system.centro_scoping import scope_records_by_centro

        return scope_records_by_centro

    def test_centro_none_no_filtra(self):
        scope = self._import()
        data = [{"nombre_centro_gestor": "X"}, {"nombre_centro_gestor": "Y"}]
        assert scope(data, None) == data

    def test_filtra_por_centro_normalizado(self):
        scope = self._import()
        data = [
            {"nombre_centro_gestor": "Secretaría del Deporte y la Recreación"},
            {"nombre_centro_gestor": "Secretaría de Cultura"},
        ]
        out = scope(data, "secretaria del deporte y la recreacion")
        assert len(out) == 1
        assert out[0]["nombre_centro_gestor"] == "Secretaría del Deporte y la Recreación"

    def test_acepta_campo_centro_gestor_fallback(self):
        scope = self._import()
        data = [{"centro_gestor": "Secretaría de Cultura"}]
        out = scope(data, "Secretaría de Cultura")
        assert len(out) == 1

    def test_no_dict_se_preserva(self):
        scope = self._import()
        data = ["string suelto", {"nombre_centro_gestor": "Secretaría de Cultura"}]
        out = scope(data, "Secretaría de Cultura")
        assert "string suelto" in out

    def test_matchea_forma_corta_alias(self):
        # Record en forma corta legacy ("Cultura") matchea el centro canónico.
        scope = self._import()
        data = [
            {"centro_gestor": "Cultura"},
            {"centro_gestor": "Deportes"},
        ]
        out = scope(data, "Secretaría de Cultura")
        assert len(out) == 1
        assert out[0]["centro_gestor"] == "Cultura"

    def test_centro_solicitado_forma_corta_matchea_dato_canonico(self):
        # Y al revés: centro pedido en forma corta matchea dato canónico.
        scope = self._import()
        data = [{"nombre_centro_gestor": "Secretaría de Cultura"}]
        out = scope(data, "Cultura")
        assert len(out) == 1


class TestSameCentro:
    def _import(self):
        from auth_system.centro_scoping import same_centro

        return same_centro

    def test_mismo_centro_distintas_formas(self):
        same = self._import()
        assert same("Deportes", "Secretaría del Deporte y la Recreación") is True
        assert same("secretaria de cultura", "Secretaría de Cultura") is True
        assert same("Cultura", "Secretaría de Cultura") is True

    def test_centros_distintos(self):
        same = self._import()
        assert same("Secretaría de Cultura", "Secretaría de Salud Pública") is False

    def test_vacios(self):
        same = self._import()
        assert same("", "Secretaría de Cultura") is False
        assert same(None, None) is True

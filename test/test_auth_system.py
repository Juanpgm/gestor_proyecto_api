"""
Tests para el Sistema de Autenticación y Autorización
Verifica roles, permisos, middlewares y endpoints de administración
"""

import pytest
import sys
import os
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch, MagicMock

# Agregar el directorio raíz al path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from auth_system.constants import (
    ROLES, 
    DEFAULT_USER_ROLE, 
    ROLE_HIERARCHY,
    FIREBASE_COLLECTIONS,
    PUBLIC_PATHS
)
from auth_system.permissions import (
    get_user_permissions,
    validate_permission,
    has_permission,
    has_role,
    check_scope_access
)
from auth_system.utils import (
    sanitize_user_data,
    validate_role_assignment,
    calculate_permission_diff
)


class TestRolesConstants:
    """Tests para las constantes de roles"""
    
    def test_all_roles_defined(self):
        """Verificar que todos los roles estén definidos"""
        assert len(ROLES) == 8, "Deben existir exactamente 8 roles"
        
        expected_roles = [
            'super_admin', 'admin_general', 'admin_centro_gestor',
            'editor_datos', 'gestor_contratos', 'analista',
            'visualizador', 'publico'
        ]
        
        for role_id in expected_roles:
            assert role_id in ROLES, f"Rol {role_id} no está definido"
    
    def test_default_role(self):
        """Verificar que el rol por defecto sea publico"""
        assert DEFAULT_USER_ROLE == "publico"
    
    def test_role_hierarchy(self):
        """Verificar que la jerarquía de roles sea correcta"""
        assert ROLES['super_admin']['level'] == 0
        assert ROLES['admin_general']['level'] == 1
        assert ROLES['admin_centro_gestor']['level'] == 2
        assert ROLES['editor_datos']['level'] == 3
        assert ROLES['gestor_contratos']['level'] == 3
        assert ROLES['analista']['level'] == 4
        assert ROLES['visualizador']['level'] == 5
        assert ROLES['publico']['level'] == 6
    
    def test_super_admin_has_all_permissions(self):
        """Verificar que super_admin tenga el permiso '*'"""
        super_admin_perms = ROLES['super_admin']['permissions']
        assert '*' in super_admin_perms
        assert 'manage:users' in super_admin_perms
    
    def test_visualizador_limited_permissions(self):
        """Verificar que visualizador solo tenga permisos de lectura básicos"""
        visualizador_perms = ROLES['visualizador']['permissions']
        
        # Debe tener permisos de lectura básicos
        assert any('read' in perm for perm in visualizador_perms)
        
        # NO debe tener permisos de escritura
        assert not any('write:' in perm for perm in visualizador_perms)
        assert not any('delete:' in perm for perm in visualizador_perms)
        assert not any('export:' in perm for perm in visualizador_perms)
    
    def test_public_paths_defined(self):
        """Verificar que las rutas públicas estén definidas"""
        assert '/docs' in PUBLIC_PATHS
        assert '/openapi.json' in PUBLIC_PATHS
        assert '/auth/login' in PUBLIC_PATHS
        assert '/auth/register' in PUBLIC_PATHS


class TestPermissions:
    """Tests para el sistema de permisos"""
    
    @patch('database.firebase_config.get_firestore_client')
    def test_get_user_permissions_with_roles(self, mock_firestore):
        """Test obtener permisos de un usuario con roles"""
        # Mock Firestore
        mock_db = MagicMock()
        mock_firestore.return_value = mock_db
        
        # Mock documento de usuario
        mock_user_doc = MagicMock()
        mock_user_doc.exists = True
        mock_user_doc.to_dict.return_value = {
            'roles': ['editor_datos'],
            'temporary_permissions': []
        }
        
        mock_db.collection().document().get.return_value = mock_user_doc
        
        # Obtener permisos
        permissions = get_user_permissions('test_uid')
        
        # Verificar que tenga permisos del rol editor_datos
        editor_perms = ROLES['editor_datos']['permissions']
        assert all(perm in permissions for perm in editor_perms)
    
    def test_validate_permission_exact_match(self):
        """Test validación de permiso exacto"""
        user_perms = ['read:proyectos', 'write:contratos']
        
        assert validate_permission(user_perms, 'read:proyectos') == True
        assert validate_permission(user_perms, 'write:contratos') == True
        assert validate_permission(user_perms, 'delete:proyectos') == False
    
    def test_validate_permission_wildcard_all(self):
        """Test validación con wildcard '*' (super_admin)"""
        user_perms = ['*']
        
        assert validate_permission(user_perms, 'read:proyectos') == True
        assert validate_permission(user_perms, 'delete:anything') == True
        assert validate_permission(user_perms, 'manage:users') == True
    
    def test_validate_permission_wildcard_action(self):
        """Test validación con wildcard de acción 'read:*'"""
        user_perms = ['read:*']
        
        assert validate_permission(user_perms, 'read:proyectos') == True
        assert validate_permission(user_perms, 'read:contratos') == True
        assert validate_permission(user_perms, 'write:proyectos') == False
    
    @patch('database.firebase_config.get_firestore_client')
    def test_has_permission(self, mock_firestore):
        """Test función has_permission"""
        mock_db = MagicMock()
        mock_firestore.return_value = mock_db
        
        mock_user_doc = MagicMock()
        mock_user_doc.exists = True
        mock_user_doc.to_dict.return_value = {
            'roles': ['analista'],
            'temporary_permissions': []
        }
        
        mock_db.collection().document().get.return_value = mock_user_doc

        # Política A: analista tiene lectura/exportación scopeadas a su centro.
        # validate_permission verifica el permiso exacto (con scope own_centro).
        assert has_permission('test_uid', 'read:proyectos:own_centro') == True
        assert has_permission('test_uid', 'export:proyectos:own_centro') == True
        # No tiene lectura global ni escritura.
        assert has_permission('test_uid', 'read:proyectos') == False
        assert has_permission('test_uid', 'write:proyectos') == False
    
    @patch('database.firebase_config.get_firestore_client')
    def test_has_role(self, mock_firestore):
        """Test función has_role"""
        mock_db = MagicMock()
        mock_firestore.return_value = mock_db
        
        mock_user_doc = MagicMock()
        mock_user_doc.exists = True
        mock_user_doc.to_dict.return_value = {
            'roles': ['editor_datos', 'analista']
        }
        
        mock_db.collection().document().get.return_value = mock_user_doc
        
        assert has_role('test_uid', 'editor_datos') == True
        assert has_role('test_uid', 'analista') == True
        assert has_role('test_uid', 'super_admin') == False
    
    def test_check_scope_access_own_centro(self):
        """Test verificación de scope :own_centro"""
        # Mock usuario con centro gestor asignado
        user_data = {
            'centro_gestor_assigned': 'SECRETARIA DE SALUD'
        }
        
        # Usuario puede acceder a recursos de su centro
        assert check_scope_access(
            user_data,
            'SECRETARIA DE SALUD',
            'write:proyectos:own_centro'
        ) == True
        
        # Usuario NO puede acceder a recursos de otro centro
        assert check_scope_access(
            user_data,
            'SECRETARIA DE EDUCACION',
            'write:proyectos:own_centro'
        ) == False
    
    @patch('database.firebase_config.get_firestore_client')
    def test_temporary_permissions(self, mock_firestore):
        """Test permisos temporales"""
        mock_db = MagicMock()
        mock_firestore.return_value = mock_db
        
        # Permiso temporal vigente
        future_date = datetime.now(timezone.utc) + timedelta(days=1)
        
        mock_user_doc = MagicMock()
        mock_user_doc.exists = True
        mock_user_doc.to_dict.return_value = {
            'roles': ['visualizador'],
            'temporary_permissions': [
                {
                    'permission': 'export:proyectos',
                    'expires_at': future_date,
                    'granted_by': 'admin_uid',
                    'reason': 'Exportación urgente'
                }
            ]
        }
        
        mock_db.collection().document().get.return_value = mock_user_doc
        
        permissions = get_user_permissions('test_uid')
        
        # Debe tener el permiso temporal además de los de su rol
        assert 'export:proyectos' in permissions
        # Visualizador tiene permisos básicos de lectura
        assert any('read' in perm for perm in permissions)


class TestUtils:
    """Tests para funciones utilitarias"""
    
    def test_sanitize_user_data(self):
        """Test sanitización de datos de usuario"""
        user_data = {
            'uid': 'test_uid',
            'email': 'test@example.com',
            'full_name': 'Test User',
            'roles': ['visualizador'],
            'password_hash': 'secret_hash',
            'temporary_permissions': [],
            'is_active': True
        }
        
        sanitized = sanitize_user_data(user_data)
        
        # Debe incluir campos seguros
        assert 'uid' in sanitized
        assert 'email' in sanitized
        assert 'full_name' in sanitized
        assert 'roles' in sanitized
        
        # NO debe incluir campos sensibles
        assert 'password_hash' not in sanitized
        assert 'temporary_permissions' not in sanitized
    
    def test_validate_role_assignment_super_admin(self):
        """Test validación de asignación de super_admin"""
        # Super admin puede asignar cualquier rol a otros
        result = validate_role_assignment(
            user_uid='admin_uid',
            target_uid='user_uid',
            roles=['admin_general', 'editor_datos']
        )
        
        assert result == True
    
    def test_validate_role_assignment_self_elevation(self):
        """Test prevención de auto-elevación"""
        # Usuario no puede asignarse super_admin a sí mismo
        result = validate_role_assignment(
            user_uid='user_uid',
            target_uid='user_uid',
            roles=['super_admin']
        )
        
        assert result == False
    
    def test_validate_role_assignment_different_users(self):
        """Test asignación entre usuarios diferentes"""
        # Usuario puede asignar roles a otros (validación básica)
        result = validate_role_assignment(
            user_uid='editor_uid',
            target_uid='user_uid',
            roles=['analista']
        )
        
        assert result == True
    
    def test_calculate_permission_diff(self):
        """Test cálculo de diferencias de permisos"""
        old_perms = ['read:proyectos', 'write:proyectos', 'read:contratos']
        new_perms = ['read:proyectos', 'delete:proyectos', 'read:contratos']
        
        diff = calculate_permission_diff(old_perms, new_perms)
        
        assert 'delete:proyectos' in diff['added']
        assert 'write:proyectos' in diff['removed']
        assert 'read:proyectos' in diff['unchanged']
        assert 'read:contratos' in diff['unchanged']


class TestMiddleware:
    """Tests para middlewares"""
    
    def test_public_paths_bypass_auth(self):
        """Test que rutas públicas no requieren autenticación"""
        public_endpoints = [
            '/docs',
            '/openapi.json',
            '/auth/login',
            '/auth/register',
            '/auth/google'
        ]
        
        for endpoint in public_endpoints:
            assert endpoint in PUBLIC_PATHS or any(
                endpoint.startswith(path) for path in PUBLIC_PATHS
            )
    
    def test_protected_paths_require_auth(self):
        """Test que rutas protegidas requieren autenticación"""
        protected_endpoints = [
            '/proyectos-presupuestales/all',
            '/unidades-proyecto/cargar-geojson',
            '/contratos/init_contratos_seguimiento',
            '/auth/admin/users'
        ]
        
        for endpoint in protected_endpoints:
            assert endpoint not in PUBLIC_PATHS


class TestRoleHierarchy:
    """Tests para jerarquía de roles"""
    
    def test_hierarchy_levels(self):
        """Test niveles jerárquicos correctos"""
        hierarchy = ROLE_HIERARCHY
        
        assert hierarchy['super_admin'] == 0
        assert hierarchy['admin_general'] == 1
        assert hierarchy['admin_centro_gestor'] == 2
        assert hierarchy['visualizador'] == 5
        assert hierarchy['publico'] == 6
    
    def test_higher_role_has_lower_level(self):
        """Test que roles superiores tienen niveles menores"""
        super_admin_level = ROLE_HIERARCHY['super_admin']
        visualizador_level = ROLE_HIERARCHY['visualizador']
        
        assert super_admin_level < visualizador_level
    
    def test_role_comparison(self):
        """Test comparación de roles"""
        def has_higher_authority(role1, role2):
            return ROLE_HIERARCHY[role1] < ROLE_HIERARCHY[role2]
        
        assert has_higher_authority('super_admin', 'admin_general') == True
        assert has_higher_authority('admin_general', 'visualizador') == True
        assert has_higher_authority('visualizador', 'super_admin') == False


class TestPermissionScopes:
    """Tests para scopes de permisos"""
    
    def test_permission_with_scope_format(self):
        """Test formato de permisos con scope"""
        permission = 'write:proyectos:own_centro'
        parts = permission.split(':')
        
        assert len(parts) == 3
        assert parts[0] == 'write'  # action
        assert parts[1] == 'proyectos'  # resource
        assert parts[2] == 'own_centro'  # scope
    
    def test_permission_without_scope_format(self):
        """Test formato de permisos sin scope"""
        permission = 'read:proyectos'
        parts = permission.split(':')
        
        assert len(parts) == 2
        assert parts[0] == 'read'  # action
        assert parts[1] == 'proyectos'  # resource


class TestFirebaseCollections:
    """Tests para nombres de colecciones"""
    
    def test_collections_defined(self):
        """Test que todas las colecciones estén definidas"""
        assert 'users' in FIREBASE_COLLECTIONS
        assert 'roles' in FIREBASE_COLLECTIONS
        assert 'audit_logs' in FIREBASE_COLLECTIONS
    
    def test_collection_names(self):
        """Test nombres correctos de colecciones"""
        assert FIREBASE_COLLECTIONS['users'] == 'users'
        assert FIREBASE_COLLECTIONS['roles'] == 'roles'
        assert FIREBASE_COLLECTIONS['audit_logs'] == 'audit_logs'


class TestRolePermissionsCoverage:
    """Tests para cobertura de permisos por rol"""
    
    def test_admin_general_permissions(self):
        """Test permisos de admin_general"""
        perms = ROLES['admin_general']['permissions']
        
        # Debe tener permisos completos de CRUD
        assert 'read:proyectos' in perms
        assert 'write:proyectos' in perms
        assert 'delete:proyectos' in perms
        assert 'export:proyectos' in perms
        
        # Pero NO debe poder gestionar usuarios
        assert 'manage:users' not in perms
    
    def test_admin_centro_gestor_permissions(self):
        """Test permisos de admin_centro_gestor"""
        perms = ROLES['admin_centro_gestor']['permissions']
        
        # Debe tener permisos con scope de su centro
        assert 'write:proyectos:own_centro' in perms
        assert 'write:contratos:own_centro' in perms
        
        # NO debe tener permisos globales de escritura
        assert 'delete:proyectos' not in perms
    
    def test_gestor_contratos_permissions(self):
        """Test permisos de gestor_contratos (política A: scope own_centro)"""
        perms = ROLES['gestor_contratos']['permissions']

        # Debe tener permisos de contratos/empréstito scopeados a su centro
        assert 'read:contratos:own_centro' in perms
        assert 'write:contratos:own_centro' in perms
        assert 'read:emprestito:own_centro' in perms
        assert 'write:emprestito:own_centro' in perms
        # NO debe tener lectura global (solo admins ven todo)
        assert 'read:contratos' not in perms

    def test_analista_permissions(self):
        """Test permisos de analista (política A: scope own_centro)"""
        perms = ROLES['analista']['permissions']

        # Lectura y exportación scopeadas a su centro
        assert 'read:proyectos:own_centro' in perms
        assert 'export:proyectos:own_centro' in perms
        assert any('reportes' in p for p in perms)

        # NO debe tener lectura global ni escritura
        assert 'read:proyectos' not in perms
        assert 'write:proyectos' not in perms
        assert 'write:proyectos:own_centro' not in perms
        assert 'delete:proyectos' not in perms


# Ejecutar tests si se corre directamente
if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])

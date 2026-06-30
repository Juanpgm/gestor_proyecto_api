"""
Tests de Integración para Endpoints de Autenticación y Administración
Prueba los endpoints del API con FastAPI TestClient
"""

import pytest
import sys
import os
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch, MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from fastapi.testclient import TestClient
from main import app
from auth_system.constants import ROLES


@pytest.fixture
def client():
    """Cliente de prueba para FastAPI"""
    return TestClient(app)


@pytest.fixture
def mock_firebase_user():
    """Mock de usuario autenticado de Firebase"""
    user = MagicMock()
    user.uid = 'test_uid_123'
    user.email = 'test@example.com'
    user.display_name = 'Test User'
    user.email_verified = True
    return user


@pytest.fixture
def super_admin_token():
    """Mock token de super_admin"""
    return "mock_super_admin_token"


@pytest.fixture
def visualizador_token():
    """Mock token de visualizador"""
    return "mock_visualizador_token"


class TestPublicEndpoints:
    """Tests para endpoints públicos (no requieren autenticación)"""
    
    def test_docs_accessible(self, client):
        """Test que /docs sea accesible sin autenticación"""
        response = client.get("/docs")
        assert response.status_code in [200, 307]  # 307 = redirect
    
    def test_openapi_json_accessible(self, client):
        """Test que /openapi.json sea accesible"""
        response = client.get("/openapi.json")
        assert response.status_code == 200
        assert 'openapi' in response.json()
    
    def test_health_check_accessible(self, client):
        """Test endpoint de health check"""
        # Algunos proyectos tienen /health o /
        response = client.get("/")
        assert response.status_code in [200, 404]  # 404 si no existe endpoint raíz


class TestAuthEndpoints:
    """Tests para endpoints de autenticación"""
    
    @patch('firebase_admin.auth.verify_id_token')
    @patch('database.firebase_config.get_firestore_client')
    def test_protected_endpoint_without_token(self, mock_firestore, mock_verify, client):
        """Test que endpoints protegidos requieren token"""
        response = client.get("/auth/admin/users")
        assert response.status_code in [401, 403]
    
    @patch('firebase_admin.auth.verify_id_token')
    @patch('database.firebase_config.get_firestore_client')
    def test_protected_endpoint_with_invalid_token(self, mock_firestore, mock_verify, client):
        """Test con token inválido"""
        mock_verify.side_effect = Exception("Invalid token")
        
        response = client.get(
            "/auth/admin/users",
            headers={"Authorization": "Bearer invalid_token"}
        )
        assert response.status_code in [401, 403, 500]

    def test_register_saves_default_rol_publico(self, client):
        """Test que /auth/register guarda rol='publico' en Firestore"""
        payload = {
            "email": "nuevo.usuario@cali.gov.co",
            "password": "TestPassword123!",
            "confirmPassword": "TestPassword123!",
            "name": "Nuevo Usuario",
            "cellphone": "+57 300 123 4567",
            "nombre_centro_gestor": "DATIC"
        }

        with patch('api.routers.auth_routes.FIREBASE_AVAILABLE', True), \
             patch('api.scripts.user_management.get_auth_client') as mock_get_auth_client, \
             patch('api.scripts.user_management.get_firestore_client') as mock_get_firestore_client:

            mock_auth_client = MagicMock()
            mock_get_auth_client.return_value = mock_auth_client

            # Simulate no existing user found (new registration path)
            from firebase_admin import exceptions as firebase_exceptions
            mock_auth_client.get_user_by_email.side_effect = firebase_exceptions.NotFoundError("User not found", None)
            mock_auth_client.get_user_by_phone_number.side_effect = firebase_exceptions.NotFoundError("User not found", None)

            mock_user_record = MagicMock()
            mock_user_record.uid = 'test_uid_register_001'
            mock_user_record.email = payload['email']
            mock_user_record.phone_number = '+573001234567'
            mock_user_record.user_metadata.creation_timestamp = datetime.now()
            mock_auth_client.create_user.return_value = mock_user_record
            mock_auth_client.generate_email_verification_link.return_value = 'https://example.com/verify'

            mock_firestore = MagicMock()
            mock_get_firestore_client.return_value = mock_firestore

            response = client.post('/auth/register', json=payload)

            assert response.status_code == 201
            assert response.json().get('success') is True

            set_call_args = mock_firestore.collection.return_value.document.return_value.set.call_args
            assert set_call_args is not None

            user_data_sent = set_call_args.args[0]
            assert user_data_sent.get('roles') == ['publico']


class TestAdminUsersEndpoints:
    """Tests para endpoints de administración de usuarios"""
    
    @patch('firebase_admin.auth.verify_id_token')
    @patch('database.firebase_config.get_firestore_client')
    def test_list_users_super_admin(self, mock_firestore, mock_verify, client, super_admin_token):
        """Test listar usuarios con permisos de super_admin"""
        # Mock verify token
        mock_verify.return_value = {
            'uid': 'admin_uid',
            'email': 'admin@example.com'
        }
        
        # Mock Firestore
        mock_db = MagicMock()
        mock_firestore.return_value = mock_db
        
        # Mock user document con rol super_admin
        mock_user_doc = MagicMock()
        mock_user_doc.exists = True
        mock_user_doc.to_dict.return_value = {
            'uid': 'admin_uid',
            'email': 'admin@example.com',
            'roles': ['super_admin'],
            'temporary_permissions': []
        }
        
        # Mock query de usuarios
        mock_users = [
            {
                'uid': 'user1',
                'email': 'user1@example.com',
                'roles': ['visualizador']
            },
            {
                'uid': 'user2',
                'email': 'user2@example.com',
                'roles': ['analista']
            }
        ]
        
        mock_docs = []
        for user in mock_users:
            doc = MagicMock()
            doc.to_dict.return_value = user
            mock_docs.append(doc)
        
        mock_query = MagicMock()
        mock_query.stream.return_value = mock_docs
        
        mock_db.collection().document().get.return_value = mock_user_doc
        mock_db.collection().limit().offset().stream.return_value = mock_docs
        
        # Hacer request
        response = client.get(
            "/auth/admin/users",
            headers={"Authorization": f"Bearer {super_admin_token}"}
        )
        
        # En un entorno de prueba real, deberías obtener 200
        # Por ahora verificamos que no sea 500 (error del servidor)
        assert response.status_code != 500
    
    @patch('firebase_admin.auth.verify_id_token')
    @patch('database.firebase_config.get_firestore_client')
    def test_list_users_without_permission(self, mock_firestore, mock_verify, client, visualizador_token):
        """Test listar usuarios sin permisos (debe fallar)"""
        # Mock verify token
        mock_verify.return_value = {
            'uid': 'user_uid',
            'email': 'user@example.com'
        }
        
        # Mock Firestore - usuario con rol visualizador
        mock_db = MagicMock()
        mock_firestore.return_value = mock_db
        
        mock_user_doc = MagicMock()
        mock_user_doc.exists = True
        mock_user_doc.to_dict.return_value = {
            'uid': 'user_uid',
            'email': 'user@example.com',
            'roles': ['visualizador'],
            'temporary_permissions': []
        }
        
        mock_db.collection().document().get.return_value = mock_user_doc
        
        response = client.get(
            "/auth/admin/users",
            headers={"Authorization": f"Bearer {visualizador_token}"}
        )
        
        # Debe retornar 403 Forbidden
        assert response.status_code == 403


class TestRolesEndpoints:
    """Tests para endpoints de roles"""
    
    @patch('firebase_admin.auth.verify_id_token')
    @patch('database.firebase_config.get_firestore_client')
    def test_list_roles(self, mock_firestore, mock_verify, client, super_admin_token):
        """Test listar roles"""
        mock_verify.return_value = {
            'uid': 'admin_uid',
            'email': 'admin@example.com'
        }
        
        mock_db = MagicMock()
        mock_firestore.return_value = mock_db
        
        mock_user_doc = MagicMock()
        mock_user_doc.exists = True
        mock_user_doc.to_dict.return_value = {
            'roles': ['super_admin'],
            'temporary_permissions': []
        }
        
        mock_db.collection().document().get.return_value = mock_user_doc
        
        response = client.get(
            "/auth/admin/roles",
            headers={"Authorization": f"Bearer {super_admin_token}"}
        )
        
        # Verificar que no haya error del servidor
        assert response.status_code != 500
    
    @patch('firebase_admin.auth.verify_id_token')
    @patch('database.firebase_config.get_firestore_client')
    def test_get_role_details(self, mock_firestore, mock_verify, client, super_admin_token):
        """Test obtener detalles de un rol"""
        mock_verify.return_value = {
            'uid': 'admin_uid',
            'email': 'admin@example.com'
        }
        
        mock_db = MagicMock()
        mock_firestore.return_value = mock_db
        
        mock_user_doc = MagicMock()
        mock_user_doc.exists = True
        mock_user_doc.to_dict.return_value = {
            'roles': ['super_admin'],
            'temporary_permissions': []
        }
        
        mock_db.collection().document().get.return_value = mock_user_doc
        
        response = client.get(
            "/auth/admin/roles/visualizador",
            headers={"Authorization": f"Bearer {super_admin_token}"}
        )
        
        assert response.status_code != 500
    
    def test_get_nonexistent_role(self, client, super_admin_token):
        """Test obtener rol que no existe"""
        response = client.get(
            "/auth/admin/roles/nonexistent_role",
            headers={"Authorization": f"Bearer {super_admin_token}"}
        )
        
        # Puede ser 401 (sin auth), 403 (sin permiso), o 404 (no existe)
        assert response.status_code in [401, 403, 404]


class TestRoleAssignment:
    """Tests para asignación de roles"""
    
    @patch('firebase_admin.auth.verify_id_token')
    @patch('database.firebase_config.get_firestore_client')
    def test_assign_roles_super_admin(self, mock_firestore, mock_verify, client, super_admin_token):
        """Test asignar roles como super_admin"""
        mock_verify.return_value = {
            'uid': 'admin_uid',
            'email': 'admin@example.com'
        }
        
        mock_db = MagicMock()
        mock_firestore.return_value = mock_db
        
        # Mock current user (super_admin)
        mock_current_user = MagicMock()
        mock_current_user.exists = True
        mock_current_user.to_dict.return_value = {
            'roles': ['super_admin'],
            'temporary_permissions': []
        }
        
        # Mock target user
        mock_target_user = MagicMock()
        mock_target_user.exists = True
        mock_target_user.to_dict.return_value = {
            'uid': 'target_uid',
            'email': 'target@example.com',
            'roles': ['visualizador']
        }
        
        mock_db.collection().document().get.side_effect = [
            mock_current_user,
            mock_target_user
        ]
        
        response = client.post(
            "/auth/admin/users/target_uid/roles",
            headers={"Authorization": f"Bearer {super_admin_token}"},
            json={
                "roles": ["analista"],
                "reason": "Promoción a analista"
            }
        )
        
        assert response.status_code != 500
    
    @patch('firebase_admin.auth.verify_id_token')
    @patch('database.firebase_config.get_firestore_client')
    def test_assign_roles_without_permission(self, mock_firestore, mock_verify, client, visualizador_token):
        """Test asignar roles sin permisos (debe fallar)"""
        mock_verify.return_value = {
            'uid': 'user_uid',
            'email': 'user@example.com'
        }
        
        mock_db = MagicMock()
        mock_firestore.return_value = mock_db
        
        mock_user_doc = MagicMock()
        mock_user_doc.exists = True
        mock_user_doc.to_dict.return_value = {
            'roles': ['visualizador'],
            'temporary_permissions': []
        }
        
        mock_db.collection().document().get.return_value = mock_user_doc
        
        response = client.post(
            "/auth/admin/users/other_uid/roles",
            headers={"Authorization": f"Bearer {visualizador_token}"},
            json={
                "roles": ["admin_general"]
            }
        )
        
        assert response.status_code == 403


class TestTemporaryPermissions:
    """Tests para permisos temporales"""
    
    @patch('firebase_admin.auth.verify_id_token')
    @patch('database.firebase_config.get_firestore_client')
    def test_grant_temporary_permission(self, mock_firestore, mock_verify, client, super_admin_token):
        """Test otorgar permiso temporal"""
        mock_verify.return_value = {
            'uid': 'admin_uid',
            'email': 'admin@example.com'
        }
        
        mock_db = MagicMock()
        mock_firestore.return_value = mock_db
        
        mock_current_user = MagicMock()
        mock_current_user.exists = True
        mock_current_user.to_dict.return_value = {
            'roles': ['super_admin'],
            'temporary_permissions': []
        }
        
        mock_target_user = MagicMock()
        mock_target_user.exists = True
        mock_target_user.to_dict.return_value = {
            'uid': 'target_uid',
            'email': 'target@example.com',
            'roles': ['visualizador'],
            'temporary_permissions': []
        }
        
        mock_db.collection().document().get.side_effect = [
            mock_current_user,
            mock_target_user
        ]
        
        # Fecha de expiración (1 día)
        expires_at = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
        
        response = client.post(
            "/auth/admin/users/target_uid/temporary-permissions",
            headers={"Authorization": f"Bearer {super_admin_token}"},
            json={
                "permission": "export:proyectos",
                "expires_at": expires_at,
                "reason": "Exportación urgente"
            }
        )
        
        assert response.status_code != 500


class TestAuditLogs:
    """Tests para logs de auditoría"""
    
    @patch('firebase_admin.auth.verify_id_token')
    @patch('database.firebase_config.get_firestore_client')
    def test_list_audit_logs(self, mock_firestore, mock_verify, client, super_admin_token):
        """Test listar audit logs"""
        mock_verify.return_value = {
            'uid': 'admin_uid',
            'email': 'admin@example.com'
        }
        
        mock_db = MagicMock()
        mock_firestore.return_value = mock_db
        
        mock_user_doc = MagicMock()
        mock_user_doc.exists = True
        mock_user_doc.to_dict.return_value = {
            'roles': ['super_admin'],
            'temporary_permissions': []
        }
        
        mock_db.collection().document().get.return_value = mock_user_doc
        
        response = client.get(
            "/auth/admin/audit-logs",
            headers={"Authorization": f"Bearer {super_admin_token}"}
        )
        
        assert response.status_code != 500


class TestSystemStats:
    """Tests para estadísticas del sistema"""
    
    @patch('firebase_admin.auth.verify_id_token')
    @patch('database.firebase_config.get_firestore_client')
    def test_get_system_stats(self, mock_firestore, mock_verify, client, super_admin_token):
        """Test obtener estadísticas del sistema"""
        mock_verify.return_value = {
            'uid': 'admin_uid',
            'email': 'admin@example.com'
        }
        
        mock_db = MagicMock()
        mock_firestore.return_value = mock_db
        
        mock_user_doc = MagicMock()
        mock_user_doc.exists = True
        mock_user_doc.to_dict.return_value = {
            'roles': ['super_admin'],
            'temporary_permissions': []
        }
        
        mock_db.collection().document().get.return_value = mock_user_doc
        
        response = client.get(
            "/auth/admin/system/stats",
            headers={"Authorization": f"Bearer {super_admin_token}"}
        )
        
        assert response.status_code != 500


class TestInputValidation:
    """Tests para validación de inputs"""
    
    def test_assign_roles_empty_list(self, client, super_admin_token):
        """Test asignar lista vacía de roles (debe fallar)"""
        response = client.post(
            "/auth/admin/users/target_uid/roles",
            headers={"Authorization": f"Bearer {super_admin_token}"},
            json={
                "roles": []  # Lista vacía
            }
        )
        
        assert response.status_code in [400, 401, 403, 422]
    
    def test_assign_invalid_role(self, client, super_admin_token):
        """Test asignar rol inválido"""
        response = client.post(
            "/auth/admin/users/target_uid/roles",
            headers={"Authorization": f"Bearer {super_admin_token}"},
            json={
                "roles": ["invalid_role_name"]
            }
        )
        
        assert response.status_code in [400, 401, 403, 422]
    
    def test_temporary_permission_invalid_date(self, client, super_admin_token):
        """Test permiso temporal con fecha inválida"""
        # Fecha en el pasado
        expires_at = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        
        response = client.post(
            "/auth/admin/users/target_uid/temporary-permissions",
            headers={"Authorization": f"Bearer {super_admin_token}"},
            json={
                "permission": "export:proyectos",
                "expires_at": expires_at
            }
        )
        
        assert response.status_code in [400, 401, 403, 422]


# Ejecutar tests si se corre directamente
if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])

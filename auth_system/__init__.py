"""
Sistema de Autenticación y Autorización
Gestor de Proyectos Cali - API

Sistema completo de gestión de usuarios, roles y permisos basado en Firebase
"""

from .constants import (
    ROLES,
    DEFAULT_USER_ROLE,
    ROLE_HIERARCHY,
    PUBLIC_PATHS
)

from .models import (
    AssignRolesRequest,
    GrantTemporaryPermissionRequest,
    UserResponse
)

from .permissions import (
    get_user_permissions,
    validate_permission,
    has_permission,
    has_role,
    check_scope_access
)

from .decorators import (
    require_permission,
    require_role,
    get_current_user
)

from .middleware import (
    AuthorizationMiddleware,
    AuditLogMiddleware
)

__version__ = "1.0.0"
__all__ = [
    # Constantes
    "ROLES",
    "DEFAULT_USER_ROLE",
    "ROLE_HIERARCHY",
    "PUBLIC_PATHS",
    
    # Modelos
    "AssignRolesRequest",
    "GrantTemporaryPermissionRequest",
    "UserResponse",
    
    # Permisos
    "get_user_permissions",
    "validate_permission",
    "has_permission",
    "has_role",
    "check_scope_access",
    
    # Decoradores
    "require_permission",
    "require_role",
    "get_current_user",
    
    # Middleware
    "AuthorizationMiddleware",
    "AuditLogMiddleware"
]

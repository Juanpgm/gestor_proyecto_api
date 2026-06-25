"""
Constantes del Sistema de Autenticación y Autorización
Define roles, permisos y configuraciones por defecto
"""

# ROL POR DEFECTO
# Rol asignado automáticamente a todos los usuarios nuevos (excepto super_admin)
DEFAULT_USER_ROLE = "publico"

# JERARQUÍA DE ROLES
# Nivel 0 = máximo privilegio, Nivel 6 = mínimo privilegio
ROLE_HIERARCHY = {
    "super_admin": 0,
    "admin_general": 1,
    "admin_centro_gestor": 2,
    "editor_datos": 3,
    "gestor_contratos": 3,
    "analista": 4,
    "visualizador": 5,
    "publico": 6,
}

# DEFINICIÓN COMPLETA DE ROLES Y SUS PERMISOS
ROLES = {
    "super_admin": {
        "name": "Super Administrador",
        "level": 0,
        "description": "Control total del sistema, incluyendo gestión de usuarios",
        "permissions": [
            "*",  # Wildcard: todos los permisos
            # Gestión de usuarios (exclusivo)
            "manage:users",
            "create:users",
            "update:users",
            "delete:users",
            "assign:roles",
            # Gestión de roles
            "manage:roles",
            "create:roles",
            "update:roles",
            "delete:roles",
            # Auditoría
            "view:audit_logs",
            "export:audit_logs",
            # Proyectos
            "read:proyectos",
            "write:proyectos",
            "delete:proyectos",
            "upload:proyectos",
            "export:proyectos",
            # Unidades
            "read:unidades",
            "write:unidades",
            "delete:unidades",
            "upload:unidades",
            # Contratos
            "read:contratos",
            "write:contratos",
            "delete:contratos",
            # GeoJSON
            "download:geojson",
            "upload:geojson",
        ],
    },
    "admin_general": {
        "name": "Administrador General",
        "level": 1,
        "description": "Administración de datos y roles (sin gestión de usuarios)",
        "permissions": [
            # Roles (consulta y asignación limitada)
            "manage:roles",
            "view:roles",
            # Auditoría
            "view:audit_logs",
            # Proyectos (todos los centros gestores)
            "read:proyectos",
            "write:proyectos",
            "delete:proyectos",
            "upload:proyectos",
            "export:proyectos",
            # Unidades (todos los centros gestores)
            "read:unidades",
            "write:unidades",
            "delete:unidades",
            "upload:unidades",
            # Contratos
            "read:contratos",
            "write:contratos",
            "delete:contratos",
            # Reportes
            "read:reportes_contratos",
            "write:reportes_contratos",
            # GeoJSON
            "download:geojson",
            "upload:geojson",
        ],
    },
    "admin_centro_gestor": {
        "name": "Administrador de Centro Gestor",
        "level": 2,
        "description": "Administración completa de su centro gestor asignado",
        "permissions": [
            # Proyectos (solo su centro gestor)
            "read:proyectos:own_centro",
            "write:proyectos:own_centro",
            "delete:proyectos:own_centro",
            "upload:proyectos:own_centro",
            "export:proyectos:own_centro",
            # Unidades (solo su centro gestor)
            "read:unidades:own_centro",
            "write:unidades:own_centro",
            "delete:unidades:own_centro",
            "upload:unidades:own_centro",
            # Contratos (solo su centro gestor)
            "read:contratos:own_centro",
            "write:contratos:own_centro",
            # Reportes
            "read:reportes_contratos:own_centro",
            "write:reportes_contratos:own_centro",
            # GeoJSON
            "download:geojson:own_centro",
            "upload:geojson:own_centro",
        ],
    },
    "editor_datos": {
        "name": "Editor de Datos",
        "level": 3,
        "description": "Edición de datos de su centro gestor, sin eliminación",
        "permissions": [
            # Proyectos (lectura y escritura sobre su centro gestor)
            "read:proyectos:own_centro",
            "write:proyectos:own_centro",
            "upload:proyectos:own_centro",
            # Unidades (lectura y escritura sobre su centro gestor)
            "read:unidades:own_centro",
            "write:unidades:own_centro",
            "upload:unidades:own_centro",
            # Contratos (lectura de su centro gestor)
            "read:contratos:own_centro",
            # GeoJSON
            "download:geojson",
            "upload:geojson",
        ],
    },
    "gestor_contratos": {
        "name": "Gestor de Contratos",
        "level": 3,
        "description": "Gestión de contratos de empréstito de su centro gestor",
        "permissions": [
            # Proyectos (solo lectura de su centro gestor)
            "read:proyectos:own_centro",
            # Contratos (gestión completa sobre su centro gestor)
            "read:contratos:own_centro",
            "write:contratos:own_centro",
            "delete:contratos:own_centro",
            "export:contratos:own_centro",
            # Reportes de contratos (su centro gestor)
            "read:reportes_contratos:own_centro",
            "write:reportes_contratos:own_centro",
            "export:reportes_contratos:own_centro",
            # Empréstito (su centro gestor)
            "read:emprestito:own_centro",
            "write:emprestito:own_centro",
            "process:emprestito:own_centro",
        ],
    },
    "analista": {
        "name": "Analista",
        "level": 4,
        "description": "Análisis y exportación de datos de su centro gestor",
        "permissions": [
            # Proyectos (lectura y exportación de su centro gestor)
            "read:proyectos:own_centro",
            "export:proyectos:own_centro",
            # Unidades (lectura de su centro gestor)
            "read:unidades:own_centro",
            # Contratos (lectura de su centro gestor)
            "read:contratos:own_centro",
            "export:contratos:own_centro",
            # Reportes (lectura de su centro gestor)
            "read:reportes_contratos:own_centro",
            # GeoJSON (descarga)
            "download:geojson",
            # Dashboard
            "view:dashboard",
        ],
    },
    "visualizador": {
        "name": "Visualizador",
        "level": 5,
        "description": "Solo lectura de datos básicos sin capacidad de exportación",
        "permissions": [
            # Proyectos (lectura básica)
            "read:proyectos:basic",
            # Unidades (lectura básica)
            "read:unidades:basic",
            # Contratos (lectura básica)
            "read:contratos:basic",
            # Dashboard básico
            "view:dashboard:basic",
        ],
    },
    "publico": {
        "name": "Público",
        "level": 6,
        "description": "Acceso público muy limitado",
        "permissions": [
            # Solo datos públicos
            "read:proyectos:public",
            "view:dashboard:public",
            "read:unidades:public",
        ],
    },
}

# RUTAS PÚBLICAS QUE NO REQUIEREN AUTENTICACIÓN
PUBLIC_PATHS = [
    "/",
    "/docs",
    "/openapi.json",
    "/redoc",
    "/ping",
    "/health",
    "/cors-test",
    "/test/utf8",
    "/debug/railway",
    "/metrics",
    "/auth/login",
    "/auth/register",
    "/auth/google",
    "/auth/config",
    "/auth/validate-session",
    "/auth/forgot-password",
    "/auth/workload-identity/status",
    "/centros-gestores/",
    "/unidades-proyecto/captura-estado-360",
]

# PERMISOS DISPONIBLES EN EL SISTEMA
# Formato: action:resource[:scope]
AVAILABLE_PERMISSIONS = {
    # Acciones
    "actions": [
        "read",  # Lectura de datos
        "write",  # Creación y actualización
        "delete",  # Eliminación de datos
        "manage",  # Gestión administrativa
        "upload",  # Carga de archivos
        "download",  # Descarga de archivos
        "export",  # Exportación de datos
        "view",  # Visualización
        "create",  # Creación específica
        "update",  # Actualización específica
        "assign",  # Asignación
        "process",  # Procesamiento
    ],
    # Recursos
    "resources": [
        "proyectos",  # Proyectos presupuestales
        "unidades",  # Unidades de proyecto
        "contratos",  # Contratos de empréstito
        "reportes_contratos",  # Reportes de seguimiento
        "emprestito",  # Gestión de empréstito
        "users",  # Usuarios del sistema
        "roles",  # Roles y permisos
        "audit_logs",  # Logs de auditoría
        "geojson",  # Archivos GeoJSON
        "dashboard",  # Dashboard
    ],
    # Scopes (opcional)
    "scopes": [
        "own_centro",  # Solo datos del centro gestor del usuario
        "public",  # Solo datos públicos
        "basic",  # Solo información básica
    ],
}

# COLECCIONES DE FIREBASE
FIREBASE_COLLECTIONS = {
    "users": "users",
    "roles": "roles",
    "permissions": "permissions",
    "audit_logs": "audit_logs",
    "proyectos": "proyectos_presupuestales",
    "unidades": "unidades_proyecto",
    "intervenciones": "intervenciones_unidades_proyecto",
    "avances_up": "avances_unidades_proyecto",
    "cambios_unidades": "cambios_implementados_unidades_proyecto",
    "cambios_intervenciones": "cambios_implementados_intervenciones",
    "solicitudes_unidades": "solicitudes_cambios_unidades_proyecto",
    "solicitudes_intervenciones": "solicitudes_cambios_intervenciones",
    "contratos": "contratos_emprestito",
}

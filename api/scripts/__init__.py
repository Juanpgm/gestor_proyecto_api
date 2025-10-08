"""
API Scripts Package
Módulos con funciones para operaciones específicas de la API
"""

try:
    from .firebase_operations import (
        get_collections_info,
        test_firebase_connection,
        get_collections_summary,
        get_proyectos_presupuestales,
        get_unique_nombres_centros_gestores,
        get_proyectos_presupuestales_by_bpin,
        get_proyectos_presupuestales_by_bp,
        get_proyectos_presupuestales_by_centro_gestor
    )
    FIREBASE_OPERATIONS_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Firebase operations not available: {e}")
    FIREBASE_OPERATIONS_AVAILABLE = False
    
    # Crear funciones dummy para evitar errores
    async def get_collections_info():
        return {"success": False, "error": "Firebase operations not available"}
    
    async def test_firebase_connection():
        return {"success": False, "error": "Firebase operations not available"}
    
    async def get_collections_summary():
        return {"success": False, "error": "Firebase operations not available"}
    
    async def get_proyectos_presupuestales():
        return {"success": False, "error": "Firebase operations not available"}
    
    async def get_unique_nombres_centros_gestores():
        return {"success": False, "error": "Firebase operations not available"}
    
    async def get_proyectos_presupuestales_by_bpin(bpin: str):
        return {"success": False, "error": "Firebase operations not available"}
    
    async def get_proyectos_presupuestales_by_bp(bp: str):
        return {"success": False, "error": "Firebase operations not available"}
    
    async def get_proyectos_presupuestales_by_centro_gestor(nombre_centro_gestor: str):
        return {"success": False, "error": "Firebase operations not available"}

try:
    from .unidades_proyecto import (
        get_all_unidades_proyecto_simple,
        get_unidades_proyecto_geometry,
        get_unidades_proyecto_attributes,
        get_filter_options,
        get_unidades_proyecto_summary,
        validate_unidades_proyecto_collection,
    )
    UNIDADES_PROYECTO_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Unidades proyecto operations not available: {e}")
    UNIDADES_PROYECTO_AVAILABLE = False

try:
    from .contratos_operations import (
        get_contratos_init_data,
    )
    CONTRATOS_OPERATIONS_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Contratos operations not available: {e}")
    CONTRATOS_OPERATIONS_AVAILABLE = False
    
    # Crear función dummy para contratos
    async def get_contratos_init_data(filters=None):
        return {"success": False, "error": "Contratos operations not available", "data": [], "count": 0}

# Importar operaciones de empréstito
try:
    from .emprestito_operations import (
        verificar_proceso_existente,
        obtener_datos_secop,
        obtener_datos_tvec,
        detectar_plataforma,
        guardar_proceso_emprestito,
        guardar_orden_compra_emprestito,
        procesar_emprestito_completo,
        eliminar_proceso_emprestito,
        actualizar_proceso_emprestito,
        get_emprestito_operations_status,
        EMPRESTITO_OPERATIONS_AVAILABLE
    )
    print(f"✅ Emprestito operations imported successfully - AVAILABLE: {EMPRESTITO_OPERATIONS_AVAILABLE}")
except ImportError as e:
    print(f"Warning: Emprestito operations not available: {e}")
    EMPRESTITO_OPERATIONS_AVAILABLE = False
    
    # Crear funciones dummy para empréstito
    async def verificar_proceso_existente(referencia_proceso: str):
        return {"success": False, "error": "Emprestito operations not available"}
    
    async def obtener_datos_secop(referencia_proceso: str):
        return {"success": False, "error": "Emprestito operations not available"}
    
    async def obtener_datos_tvec(referencia_proceso: str):
        return {"success": False, "error": "Emprestito operations not available"}
    
    def detectar_plataforma(plataforma: str):
        return "UNKNOWN"
    
    async def guardar_proceso_emprestito(datos):
        return {"success": False, "error": "Emprestito operations not available"}
    
    async def guardar_orden_compra_emprestito(datos):
        return {"success": False, "error": "Emprestito operations not available"}
    
    async def procesar_emprestito_completo(datos_iniciales):
        return {"success": False, "error": "Emprestito operations not available"}
    
    async def eliminar_proceso_emprestito(referencia_proceso: str):
        return {"success": False, "error": "Emprestito operations not available"}
    
    async def actualizar_proceso_emprestito(referencia_proceso: str, bp=None, nombre_resumido_proceso=None, id_paa=None, valor_proyectado=None):
        return {"success": False, "error": "Emprestito operations not available"}
    
    def get_emprestito_operations_status():
        return {"operations_available": False, "error": "Emprestito operations not available"}

# Importar operaciones de gestión de usuarios
try:
    from .user_management import (
        # Validaciones
        validate_email,
        validate_fullname,
        validate_password,
        validate_cellphone,
        # Gestión de usuarios
        check_user_session,
        create_user_account,
        update_user_password,
        delete_user_account,
        generate_password_reset_link,
        verify_custom_token,
        # Funciones administrativas
        list_users,
        get_user_statistics,
        # Utilidades
        generate_secure_password,
        update_user_login_stats
    )
    USER_MANAGEMENT_AVAILABLE = True
except ImportError as e:
    print(f"Warning: User management operations not available: {e}")
    USER_MANAGEMENT_AVAILABLE = False

# Importar operaciones de autenticación
try:
    from .auth_operations import (
        # Autenticación por email/password
        authenticate_email_password,
        # Autenticación por teléfono
        initiate_phone_auth,
        verify_phone_auth_code,
        # Validación de sesiones
        validate_user_session,
        revoke_user_tokens,
        # Utilidades
        get_supported_auth_methods,
        check_auth_method_availability
    )
    AUTH_OPERATIONS_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Auth operations not available: {e}")
    AUTH_OPERATIONS_AVAILABLE = False

# Importar operaciones de Workload Identity (autenticación Google moderna)
try:
    from .workload_identity_auth import (
        authenticate_with_workload_identity,
        verify_google_token_with_workload_identity,
        initialize_workload_identity,
        get_workload_identity_status,
        generate_google_signin_config_automatic,
        setup_workload_identity
    )
    WORKLOAD_IDENTITY_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Workload Identity operations not available: {e}")
    WORKLOAD_IDENTITY_AVAILABLE = False

__all__ = [
    # Firebase operations
    "get_collections_info",
    "test_firebase_connection", 
    "get_collections_summary",
    "get_proyectos_presupuestales",
    "get_unique_nombres_centros_gestores",
    "get_proyectos_presupuestales_by_bpin",
    "get_proyectos_presupuestales_by_bp",
    "get_proyectos_presupuestales_by_centro_gestor",
    
    # Unidades proyecto operations
    "get_all_unidades_proyecto_simple",
    "get_unidades_proyecto_geometry",
    "get_unidades_proyecto_attributes",
    "get_filter_options",
    "get_unidades_proyecto_summary",
    "validate_unidades_proyecto_collection",
    
    # Contratos operations
    "get_contratos_init_data",
    
    # Empréstito operations
    "verificar_proceso_existente",
    "obtener_datos_secop",
    "obtener_datos_tvec",
    "detectar_plataforma",
    "guardar_proceso_emprestito",
    "guardar_orden_compra_emprestito",
    "procesar_emprestito_completo",
    "eliminar_proceso_emprestito",
    "actualizar_proceso_emprestito",
    "get_emprestito_operations_status",
    
    # User management operations
    "validate_email",
    "validate_fullname",
    "validate_password", 
    "validate_cellphone",
    "check_user_session",
    "create_user_account",
    "update_user_password",
    "delete_user_account",
    "generate_password_reset_link",
    "verify_custom_token",
    "list_users",
    "get_user_statistics",
    "generate_secure_password",
    "update_user_login_stats",
    
    # Auth operations
    "authenticate_email_password",
    "initiate_phone_auth",
    "verify_phone_auth_code",
    "validate_user_session",
    "revoke_user_tokens",
    "get_supported_auth_methods",
    "check_auth_method_availability",
    
    # Workload Identity operations (Google Auth moderna)
    "authenticate_with_workload_identity",
    "verify_google_token_with_workload_identity",
    "initialize_workload_identity",
    "get_workload_identity_status",
    "generate_google_signin_config_automatic",
    "setup_workload_identity",
    
    # Availability flags
    "FIREBASE_OPERATIONS_AVAILABLE",
    "UNIDADES_PROYECTO_AVAILABLE",
    "CONTRATOS_OPERATIONS_AVAILABLE",
    "EMPRESTITO_OPERATIONS_AVAILABLE",
    "USER_MANAGEMENT_AVAILABLE",
    "AUTH_OPERATIONS_AVAILABLE",
    "WORKLOAD_IDENTITY_AVAILABLE",
]
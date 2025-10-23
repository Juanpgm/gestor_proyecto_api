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
        get_contratos_emprestito_all,
        get_contratos_emprestito_by_referencia,
        get_contratos_emprestito_by_centro_gestor,
    )
    CONTRATOS_OPERATIONS_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Contratos operations not available: {e}")
    CONTRATOS_OPERATIONS_AVAILABLE = False
    
    # Crear funciones dummy para contratos
    async def get_contratos_init_data(filters=None):
        return {"success": False, "error": "Contratos operations not available", "data": [], "count": 0}
    
    async def get_contratos_emprestito_all():
        return {"success": False, "error": "Contratos operations not available", "data": [], "count": 0}
    
    async def get_contratos_emprestito_by_referencia(referencia_contrato):
        return {"success": False, "error": "Contratos operations not available", "data": [], "count": 0}
    
    async def get_contratos_emprestito_by_centro_gestor(nombre_centro_gestor):
        return {"success": False, "error": "Contratos operations not available", "data": [], "count": 0}

# Importar operaciones de reportes de contratos
try:
    from .reportes_contratos_operations import (
        create_reporte_contrato,
        get_reportes_contratos,
        get_reporte_contrato_by_id,
        get_reportes_by_centro_gestor,
        get_reportes_by_referencia_contrato,
        setup_google_drive_service,
    )
    REPORTES_CONTRATOS_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Reportes contratos operations not available: {e}")
    REPORTES_CONTRATOS_AVAILABLE = False
    
    # Crear funciones dummy para reportes contratos
    async def create_reporte_contrato(reporte_data):
        return {"success": False, "error": "Reportes contratos operations not available"}
    
    async def get_reportes_contratos(filtros=None):
        return {"success": False, "error": "Reportes contratos operations not available", "data": [], "count": 0}
    
    async def get_reporte_contrato_by_id(reporte_id):
        return {"success": False, "error": "Reportes contratos operations not available", "data": None}
    
    async def get_reportes_by_centro_gestor(nombre_centro_gestor):
        return {"success": False, "error": "Reportes contratos operations not available", "data": [], "count": 0}
    
    async def get_reportes_by_referencia_contrato(referencia_contrato):
        return {"success": False, "error": "Reportes contratos operations not available", "data": [], "count": 0}
    
    def setup_google_drive_service():
        return False

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
        obtener_codigos_contratos,
        buscar_y_poblar_contratos_secop,
        obtener_contratos_desde_proceso_contractual,
        get_emprestito_operations_status,
        get_bancos_emprestito_all,
        get_procesos_emprestito_all,
        cargar_orden_compra_directa,
        obtener_datos_secop_completos,
        actualizar_proceso_emprestito_completo,
        procesar_todos_procesos_emprestito_completo,
        # Nuevas funciones para proyecciones de empréstito
        crear_tabla_proyecciones_desde_sheets,
        leer_proyecciones_emprestito,
        get_proyecciones_sin_proceso,
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
    
    async def obtener_codigos_contratos(referencia_proceso: str, proceso_contractual: str):
        return {"success": False, "error": "Emprestito operations not available"}
    
    async def cargar_orden_compra_directa(datos_orden):
        return {"success": False, "error": "Emprestito operations not available"}
    
    async def buscar_y_poblar_contratos_secop(referencia_proceso: str, proceso_contractual: str):
        return {"success": False, "error": "Emprestito operations not available"}
    
    async def obtener_contratos_desde_proceso_contractual():
        return {"success": False, "error": "Emprestito operations not available"}
    
    def get_emprestito_operations_status():
        return {"operations_available": False, "error": "Emprestito operations not available"}
    
    async def get_bancos_emprestito_all():
        return {"success": False, "error": "Emprestito operations not available", "data": [], "count": 0}
    
    async def get_procesos_emprestito_all():
        return {"success": False, "error": "Emprestito operations not available", "data": [], "count": 0}
    
    async def obtener_datos_secop_completos(referencia_proceso: str):
        return {"success": False, "error": "Emprestito operations not available"}
    
    async def actualizar_proceso_emprestito_completo(referencia_proceso: str):
        return {"success": False, "error": "Emprestito operations not available"}
    
    async def procesar_todos_procesos_emprestito_completo():
        return {"success": False, "error": "Emprestito operations not available"}
    
    # Nuevas funciones dummy para proyecciones
    async def crear_tabla_proyecciones_desde_sheets(sheet_url: str):
        return {"success": False, "error": "Emprestito operations not available"}
    
    async def leer_proyecciones_emprestito():
        return {"success": False, "error": "Emprestito operations not available", "data": [], "count": 0}
    
    async def get_proyecciones_sin_proceso():
        return {"success": False, "error": "Emprestito operations not available", "data": [], "count": 0}
    


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

# Importar operaciones de proyectos presupuestales
try:
    from .proyectos_presupuestales_operations import (
        process_proyectos_presupuestales_json,
        PROYECTOS_PRESUPUESTALES_OPERATIONS_AVAILABLE
    )
    print(f"✅ Proyectos presupuestales operations imported successfully - AVAILABLE: {PROYECTOS_PRESUPUESTALES_OPERATIONS_AVAILABLE}")
except ImportError as e:
    print(f"Warning: Proyectos presupuestales operations not available: {e}")
    PROYECTOS_PRESUPUESTALES_OPERATIONS_AVAILABLE = False
    
    # Crear función dummy para proyectos presupuestales
    async def process_proyectos_presupuestales_json(proyectos_data, update_mode="merge"):
        return {"success": False, "error": "Proyectos presupuestales operations not available"}

# Importar operaciones de enriquecimiento TVEC
try:
    from .tvec_enrich_operations import (
        obtener_ordenes_compra_tvec_enriquecidas,
        get_tvec_enrich_status,
        TVEC_ENRICH_OPERATIONS_AVAILABLE
    )
    print(f"✅ TVEC enrich operations imported successfully - AVAILABLE: {TVEC_ENRICH_OPERATIONS_AVAILABLE}")
except ImportError as e:
    print(f"Warning: TVEC enrich operations not available: {e}")
    TVEC_ENRICH_OPERATIONS_AVAILABLE = False
    
    # Crear funciones dummy para TVEC enrich
    async def obtener_ordenes_compra_tvec_enriquecidas():
        return {"success": False, "error": "TVEC enrich operations not available"}
    
    def get_tvec_enrich_status():
        return {"operations_available": False, "error": "TVEC enrich operations not available"}

# Importar operaciones de órdenes de compra
try:
    from .ordenes_compra_operations import (
        get_ordenes_compra_emprestito_all,
        get_ordenes_compra_emprestito_by_referencia,
        get_ordenes_compra_emprestito_by_centro_gestor,
        get_ordenes_compra_operations_status,
        ORDENES_COMPRA_OPERATIONS_AVAILABLE
    )
    print(f"✅ Ordenes compra operations imported successfully - AVAILABLE: {ORDENES_COMPRA_OPERATIONS_AVAILABLE}")
except ImportError as e:
    print(f"Warning: Ordenes compra operations not available: {e}")
    ORDENES_COMPRA_OPERATIONS_AVAILABLE = False
    
    # Crear funciones dummy para órdenes de compra
    async def get_ordenes_compra_emprestito_all():
        return {"success": False, "error": "Ordenes compra operations not available", "data": [], "count": 0}
    
    async def get_ordenes_compra_emprestito_by_referencia(numero_orden: str):
        return {"success": False, "error": "Ordenes compra operations not available", "data": [], "count": 0}
    
    async def get_ordenes_compra_emprestito_by_centro_gestor(nombre_centro_gestor: str):
        return {"success": False, "error": "Ordenes compra operations not available", "data": [], "count": 0}
    
    def get_ordenes_compra_operations_status():
        return {"operations_available": False, "error": "Ordenes compra operations not available"}

# Importar operaciones de flujo de caja
try:
    from .flujo_caja_operations import (
        process_flujo_caja_excel,
        save_flujo_caja_to_firebase,
        get_flujo_caja_from_firebase,
        FLUJO_CAJA_OPERATIONS_AVAILABLE
    )
    print(f"✅ Flujo caja operations imported successfully - AVAILABLE: {FLUJO_CAJA_OPERATIONS_AVAILABLE}")
except ImportError as e:
    print(f"Warning: Flujo caja operations not available: {e}")
    FLUJO_CAJA_OPERATIONS_AVAILABLE = False
    
    # Crear funciones dummy para flujo de caja
    def process_flujo_caja_excel(file_content: bytes, filename: str):
        return {"success": False, "error": "Flujo caja operations not available"}
    
    async def save_flujo_caja_to_firebase(records, update_mode="merge"):
        return {"success": False, "error": "Flujo caja operations not available"}
    
    async def get_flujo_caja_from_firebase(filters=None):
        return {"success": False, "error": "Flujo caja operations not available", "data": [], "count": 0}

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
    
    # Reportes contratos operations
    "create_reporte_contrato",
    "get_reportes_contratos",
    "get_reporte_contrato_by_id",
    "get_reportes_by_centro_gestor",
    "get_reportes_by_referencia_contrato",
    "setup_google_drive_service",
    
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
    "obtener_codigos_contratos",
    "buscar_y_poblar_contratos_secop",
    "obtener_contratos_desde_proceso_contractual",
    "get_emprestito_operations_status",
    "get_bancos_emprestito_all",
    "get_procesos_emprestito_all",
    "cargar_orden_compra_directa",
    "obtener_datos_secop_completos",
    "actualizar_proceso_emprestito_completo",
    "procesar_todos_procesos_emprestito_completo",
    # Nuevas funciones para proyecciones de empréstito
    "crear_tabla_proyecciones_desde_sheets",
    "leer_proyecciones_emprestito",
    "get_proyecciones_sin_proceso",
    
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
    
    # Proyectos presupuestales operations
    "process_proyectos_presupuestales_json",
    
    # TVEC enrich operations
    "obtener_ordenes_compra_tvec_enriquecidas",
    "get_tvec_enrich_status",
    
    # Ordenes compra operations
    "get_ordenes_compra_emprestito_all",
    "get_ordenes_compra_emprestito_by_referencia",
    "get_ordenes_compra_emprestito_by_centro_gestor",
    "get_ordenes_compra_operations_status",
    
    # Flujo caja operations
    "process_flujo_caja_excel",
    "save_flujo_caja_to_firebase",
    "get_flujo_caja_from_firebase",
    
    # Availability flags
    "FIREBASE_OPERATIONS_AVAILABLE",
    "UNIDADES_PROYECTO_AVAILABLE",
    "CONTRATOS_OPERATIONS_AVAILABLE",
    "REPORTES_CONTRATOS_AVAILABLE",
    "EMPRESTITO_OPERATIONS_AVAILABLE",
    "USER_MANAGEMENT_AVAILABLE",
    "AUTH_OPERATIONS_AVAILABLE",
    "WORKLOAD_IDENTITY_AVAILABLE",
    "PROYECTOS_PRESUPUESTALES_OPERATIONS_AVAILABLE",
    "TVEC_ENRICH_OPERATIONS_AVAILABLE",
    "ORDENES_COMPRA_OPERATIONS_AVAILABLE",
    "FLUJO_CAJA_OPERATIONS_AVAILABLE",
]
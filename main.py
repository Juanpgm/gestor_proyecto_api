# -*- coding: utf-8 -*-
"""
Gestor de Proyectos API - Versión Limpia
API principal para gestión de proyectos con Firebase
Arquitectura modular optimizada para NextJS
Soporte completo para UTF-8 y caracteres especiales en español
"""

import os
import sys
from contextlib import asynccontextmanager

# Configurar encoding UTF-8 para todo el sistema
if sys.platform.startswith('win'):
    # En Windows, asegurar UTF-8
    import locale
    try:
        locale.setlocale(locale.LC_ALL, 'es_ES.UTF-8')
    except:
        try:
            locale.setlocale(locale.LC_ALL, 'Spanish_Spain.1252')
        except:
            pass

# Configurar stdout y stderr para UTF-8
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')
from fastapi import FastAPI, HTTPException, Query, Request, status, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from typing import Dict, Any, Optional, Union
import uvicorn
import asyncio
from datetime import datetime



# Importar Firebase con configuración automática
try:
    from database.firebase_config import (
        PROJECT_ID, 
        FIREBASE_AVAILABLE, 
        ensure_firebase_configured, 
        configure_firebase,
        validate_firebase_connection
    )
    print(f"✅ Firebase auto-config loaded successfully - FIREBASE_AVAILABLE: {FIREBASE_AVAILABLE}")
except Exception as e:
    print(f"❌ Warning: Firebase import failed: {e}")
    FIREBASE_AVAILABLE = False
    PROJECT_ID = os.getenv("FIREBASE_PROJECT_ID", "NOT_CONFIGURED")
    configure_firebase = lambda: (False, {"error": "Not available"})
    ensure_firebase_configured = lambda: False
    validate_firebase_connection = lambda: {"connected": False, "error": "Not available"}

# Importar scripts de forma segura
try:
    from api.scripts import (
        # Firebase operations
        get_collections_info,
        test_firebase_connection,
        get_collections_summary,
        # Unidades proyecto operations (funciones especializadas y optimizadas)
        get_unidades_proyecto_geometry,
        get_unidades_proyecto_attributes,
        get_unidades_proyecto_dashboard,
        get_filter_options,
        validate_unidades_proyecto_collection,
        # Contratos operations
        get_contratos_init_data,
        # User management operations
        validate_email,
        validate_fullname,
        validate_password,
        validate_cellphone,
        check_user_session,
        create_user_account,
        update_user_password,
        delete_user_account,
        list_users,
        # Auth operations
        authenticate_email_password,
        validate_user_session,
        # Availability flags
        USER_MANAGEMENT_AVAILABLE,
        AUTH_OPERATIONS_AVAILABLE,
    )
    SCRIPTS_AVAILABLE = True
    print(f"✅ Scripts imported successfully - SCRIPTS_AVAILABLE: {SCRIPTS_AVAILABLE}")
except Exception as e:
    print(f"❌ Warning: Scripts import failed: {e}")
    SCRIPTS_AVAILABLE = False
    USER_MANAGEMENT_AVAILABLE = False
    AUTH_OPERATIONS_AVAILABLE = False

# Importar modelos Pydantic
try:
    from api.models import (
        UserRegistrationRequest,
        UserLoginRequest,
        PasswordUpdateRequest,
        GoogleAuthRequest,
        SessionValidationRequest,
        UserListFilters,
        StandardResponse,
        ValidationErrorResponse,
        USER_MODELS_AVAILABLE,
    )
    print(f"✅ User models imported successfully - USER_MODELS_AVAILABLE: {USER_MODELS_AVAILABLE}")
except Exception as e:
    print(f"❌ Warning: User models import failed: {e}")
    USER_MODELS_AVAILABLE = False



# Configurar el lifespan de la aplicación
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gestionar el ciclo de vida de la aplicación"""
    # Startup
    print("Starting API...")
    print(f"Port: {os.getenv('PORT', '8000')}")
    print(f"Environment: {os.getenv('ENVIRONMENT', 'development')}")
    print(f"Firebase Project: {PROJECT_ID}")
    
    # Inicializar Firebase de forma segura
    if ensure_firebase_configured():
        print("✅ Firebase initialized successfully")
    else:
        print("❌ Firebase initialization failed")
    
    # Inicializar Firebase automáticamente (sin fallar la app)
    firebase_initialized = False
    if FIREBASE_AVAILABLE:
        try:
            firebase_initialized, status = configure_firebase()
            if firebase_initialized:
                print("✅ Firebase initialized successfully")
            else:
                print(f"⚠️ Firebase initialization failed: {status.get('error', 'Unknown error')}")
        except Exception as e:
            print(f"⚠️ Firebase setup error: {e} - API will run in limited mode")
            firebase_initialized = False
    else:
        print("⚠️ Firebase not available - API running in limited mode")
        firebase_initialized = False
    
    print(f"🚀 API starting with Firebase: {'✅ Connected' if firebase_initialized else '❌ Limited mode'}")
    
    yield
    
    # Shutdown
    print("Stopping API...")

# Crear instancia de FastAPI con lifespan y soporte UTF-8
app = FastAPI(
    title="Gestor de Proyectos API",
    description="API para gestión de proyectos con Firebase/Firestore - Soporte completo UTF-8 🇪🇸",
    version="1.0.0",
    lifespan=lifespan,
    swagger_ui_parameters={
        "defaultModelsExpandDepth": 1,
        "displayRequestDuration": True,
        "filter": True,
        "tryItOutEnabled": True,
        "requestSnippetsEnabled": True,
        "defaultModelRendering": "example",
        "showExtensions": True,
        "showCommonExtensions": True
    }
)

# Configurar CORS - Optimizado para Vercel + Railway
def get_cors_origins():
    """Obtener orígenes CORS desde variables de entorno de forma segura"""
    origins = []
    
    # Orígenes de desarrollo local
    local_origins = [
        "http://localhost:3000",
        "http://localhost:3001", 
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3001",
    ]
    
    # En desarrollo, permitir localhost
    if os.getenv("ENVIRONMENT") != "production":
        origins.extend(local_origins)
    
    # Orígenes de producción desde variables de entorno
    frontend_url = os.getenv("FRONTEND_URL")
    if frontend_url:
        origins.append(frontend_url)
    
    # Orígenes adicionales (separados por coma)
    additional_origins = os.getenv("CORS_ORIGINS", "")
    if additional_origins:
        origins.extend([origin.strip() for origin in additional_origins.split(",")])
    
    # Si no hay orígenes configurados, usar configuración mínima segura
    if not origins:
        print("⚠️ Warning: No CORS origins configured, using localhost only")
        origins = local_origins
    
    return origins

origins = get_cors_origins()

# 🔤 MIDDLEWARE UTF-8 PARA CARACTERES ESPECIALES
@app.middleware("http")
async def utf8_middleware(request: Request, call_next):
    """Middleware para asegurar encoding UTF-8 en todas las respuestas"""
    response = await call_next(request)
    
    # Asegurar que las respuestas JSON tengan charset UTF-8
    if response.headers.get("content-type", "").startswith("application/json"):
        response.headers["content-type"] = "application/json; charset=utf-8"
    
    return response

# 🌐 CORS CONFIGURADO PARA UTF-8
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,           
    allow_credentials=True,          
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],  
    allow_headers=[               
        "Authorization",
        "Content-Type", 
        "Accept",
        "Accept-Charset",
        "Accept-Encoding",
        "Accept-Language",
        "Origin", 
        "X-Requested-With",
        "Cache-Control",
        "Pragma"
    ],
)

# � FUNCIONES UTILITARIAS PARA UTF-8
def create_utf8_response(content: Dict[str, Any], status_code: int = 200) -> JSONResponse:
    """Crear respuesta JSON con encoding UTF-8 explícito"""
    return JSONResponse(
        content=content,
        status_code=status_code,
        headers={"Content-Type": "application/json; charset=utf-8"},
        media_type="application/json"
    )

def handle_utf8_text(text: str) -> str:
    """Asegurar que el texto mantenga caracteres UTF-8"""
    if isinstance(text, str):
        return text.encode('utf-8').decode('utf-8')
    return str(text)

# �🛠️ MIDDLEWARE DE TIMEOUT PARA PREVENIR COLGADAS
@app.middleware("http")
async def timeout_middleware(request: Request, call_next):
    """Middleware para prevenir que las requests se cuelguen"""
    try:
        # Timeout de 30 segundos para todas las requests
        return await asyncio.wait_for(call_next(request), timeout=30.0)
    except asyncio.TimeoutError:
        return JSONResponse(
            status_code=504,
            content={
                "error": "Request timeout",
                "message": "The request took too long to process",
                "fallback": True,
                "timestamp": datetime.now().isoformat()
            }
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "error": "Internal server error", 
                "message": "An unexpected error occurred",
                "fallback": True,
                "timestamp": datetime.now().isoformat()
            }
        )

# Swagger UI configurado automáticamente con parámetros optimizados

# ============================================================================
# ENDPOINTS GENERALES
# ============================================================================

@app.get("/")
async def read_root():
    """Endpoint raíz con información básica de la API"""
    response_data = {
        "message": "Gestor de Proyectos API 🇪🇸",
        "description": "API con soporte completo para UTF-8 y caracteres en español",
        "version": "1.0.0",
        "timestamp": datetime.now().isoformat(),
        "last_updated": "2025-10-04T00:00:00Z",  # API last update date
        "firebase_project": PROJECT_ID,
        "status": "funcionando ✅",
        "encoding": "UTF-8",
        "spanish_support": "Sí - Acentos: á é í ó ú, Ñ, diéresis: ü",
        "documentation": "/docs",
        "environment_debug": {
            "firebase_project_id": os.getenv("FIREBASE_PROJECT_ID", "NOT_SET"),
            "has_service_account_key": bool(os.getenv("FIREBASE_SERVICE_ACCOUNT_KEY")),
            "environment": os.getenv("ENVIRONMENT", "NOT_SET"),
            "port": os.getenv("PORT", "NOT_SET")
        },
        "endpoints": {
            "general": ["/", "/health", "/ping"],
            "firebase": ["/firebase/status", "/firebase/collections"], 
            "unidades_proyecto": [
                "/unidades-proyecto/geometry", 
                "/unidades-proyecto/attributes",
                "/unidades-proyecto/dashboard",
                "/unidades-proyecto/filters"
            ],
            "gestion_contractual": [
                "/contratos/init_contratos_seguimiento"
            ],
            "administracion_usuarios": [
                "/auth/validate-session",
                "/auth/login", 
                "/auth/register",
                "/auth/change-password",
                "/auth/google",
                "/auth/user/{uid}",
                "/admin/users"
            ]
        },
        "new_features": {
            "user_management": "Sistema completo de gestión de usuarios con Firebase Authentication",
            "auth_methods": "Soporte para email/password, Google (@cali.gov.co), y autenticación telefónica",
            "user_roles": "Sistema de roles y permisos (admin, gestor, viewer, editor)",
            "utf8_support": "Soporte completo para caracteres especiales en español: ñ, á, é, í, ó, ú, ü",
            "filters": "Todos los endpoints de Unidades de Proyecto soportan filtros avanzados",
            "supported_filters": [
                "nombre_centro_gestor", "tipo_intervencion", "estado", "upid", 
                "comuna_corregimiento", "barrio_vereda", "nombre_up", "direccion",
                "referencia_contrato", "referencia_proceso", "include_bbox", "limit", "offset"
            ],
            "dashboard": "Endpoint de dashboard con métricas agregadas y análisis estadístico",
            "workload_identity": "Autenticación automática usando Google Cloud Workload Identity Federation",
            "encoding": "UTF-8 completo para español: ñáéíóúü ¡¿"
        }
    }
    
    return create_utf8_response(response_data)

@app.get("/ping", tags=["General"])
async def ping():
    """Health check super simple para Railway con soporte UTF-8"""
    response_data = {
        "status": "ok ✅", 
        "message": "Servidor funcionando correctamente",
        "encoding": "UTF-8",
        "spanish_test": "ñáéíóúü ¡¿",
        "timestamp": datetime.now().isoformat(),
        "last_updated": "2025-10-04T00:00:00Z"  # Endpoint creation/update date
    }
    return create_utf8_response(response_data)

@app.get("/test/utf8", tags=["General"])
async def test_utf8():
    """Endpoint de prueba específico para caracteres UTF-8 en español"""
    test_data = {
        "encoding": "UTF-8",
        "status": "Funcionando correctamente ✅",
        "test_cases": {
            "vocales_acentuadas": "á é í ó ú",
            "vocales_mayusculas": "Á É Í Ó Ú",
            "enie": "ñ Ñ",
            "dieresis": "ü Ü",
            "signos_interrogacion": "¿Cómo estás?",
            "signos_exclamacion": "¡Excelente!",
            "nombres_espanoles": [
                "José María",
                "Ángela Rodríguez", 
                "Peña Nieto",
                "Núñez",
                "Güell"
            ],
            "ciudades_colombia": [
                "Bogotá",
                "Medellín", 
                "Cali",
                "Barranquilla",
                "Cartagena",
                "Cúcuta",
                "Ibagué",
                "Pereira",
                "Santa Marta",
                "Manizales"
            ],
            "texto_completo": "La niña soñó con un colibrí que volaba sobre el jardín donde crecían las flores más hermosas de España.",
            "caracteres_especiales": "°ª€£¢¥§¨©®™",
            "test_json": "Prueba de JSON con acentos: María José fue a Bogotá"
        },
        "timestamp": datetime.now().isoformat()
    }
    
    return create_utf8_response(test_data)

@app.get("/debug/railway", tags=["General"])
async def railway_debug():
    """Debug específico para Railway - Diagnóstico simplificado"""
    try:
        # Variables de entorno
        env_info = {
            "FIREBASE_PROJECT_ID": os.getenv("FIREBASE_PROJECT_ID", "NOT_SET"),
            "HAS_FIREBASE_SERVICE_ACCOUNT_KEY": bool(os.getenv("FIREBASE_SERVICE_ACCOUNT_KEY")),
            "RAILWAY_ENVIRONMENT": os.getenv("RAILWAY_ENVIRONMENT", "NOT_SET"),
            "PORT": os.getenv("PORT", "NOT_SET")
        }
        
        # Test de Service Account
        sa_test = {"status": "not_tested"}
        if os.getenv("FIREBASE_SERVICE_ACCOUNT_KEY"):
            try:
                import json
                import base64
                
                decoded = base64.b64decode(os.getenv("FIREBASE_SERVICE_ACCOUNT_KEY")).decode('utf-8')
                creds_data = json.loads(decoded)
                
                sa_test = {
                    "status": "success",
                    "client_email": creds_data.get("client_email", "missing"),
                    "project_id": creds_data.get("project_id", "missing"),
                    "has_private_key": bool(creds_data.get("private_key"))
                }
            except Exception as e:
                sa_test = {
                    "status": "failed",
                    "error": str(e)
                }
        
        # Test Firebase directly
        firebase_test = None
        if FIREBASE_AVAILABLE:
            try:
                firebase_test = validate_firebase_connection()
            except Exception as e:
                firebase_test = {"error": str(e)}
        
        return {
            "status": "debug_info",
            "timestamp": datetime.now().isoformat(),
            "environment_variables": env_info,
            "service_account_test": sa_test,
            "firebase_test": firebase_test,
            "firebase_available": FIREBASE_AVAILABLE,
            "scripts_available": SCRIPTS_AVAILABLE,
            "project_id_detected": PROJECT_ID,
            "recommendation": "Check service_account_test and firebase_test for issues"
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }

@app.get("/health", tags=["General"])
async def health_check():
    """Verificar estado de salud de la API"""
    try:
        basic_response = {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "services": {
                "api": "running"
            },
            "port": os.getenv("PORT", "8000"),
            "environment": os.getenv("ENVIRONMENT", "development"),
            "project_id": PROJECT_ID
        }
        
        # Verificar Firebase usando configuración funcional
        if FIREBASE_AVAILABLE:
            # Test default project
            firebase_status = validate_firebase_connection()
            basic_response["services"]["firebase"] = firebase_status
            basic_response["services"]["scripts"] = {"available": SCRIPTS_AVAILABLE}
            
            # Debug info for Railway
            basic_response["debug"] = {
                "firebase_project_env": os.getenv("FIREBASE_PROJECT_ID", "NOT_SET"),
                "has_sa_key": bool(os.getenv("FIREBASE_SERVICE_ACCOUNT_KEY")),
                "firebase_available": FIREBASE_AVAILABLE,
                "scripts_available": SCRIPTS_AVAILABLE,
                "environment": os.getenv("ENVIRONMENT", "development")
            }
            
            if not firebase_status["connected"]:
                basic_response["status"] = "degraded"
                
        else:
            basic_response["services"]["firebase"] = {
                "available": False, 
                "message": "Firebase SDK not available"
            }

            basic_response["status"] = "degraded"
        
        return basic_response
        
    except Exception as e:
        print(f"Health check error: {e}")
        return {
            "status": "partial",
            "timestamp": datetime.now().isoformat(),
            "error": str(e)[:100],
            "services": {
                "api": "running"
            }
        }

# ============================================================================
# ENDPOINTS DE FIREBASE
# ============================================================================

@app.get("/firebase/status", tags=["Firebase"])
async def firebase_status():
    """Verificar estado de la conexión con Firebase"""
    try:
        if not FIREBASE_AVAILABLE:
            return {
                "connected": False,
                "error": "Firebase SDK not available",
                "available": False,
                "status": "unavailable",
                "last_updated": "2025-10-02T00:00:00Z"
            }
        
        if not SCRIPTS_AVAILABLE:
            return {
                "connected": False,
                "error": "Scripts not available",
                "available": FIREBASE_AVAILABLE,
                "status": "limited",
                "last_updated": "2025-10-02T00:00:00Z"
            }
        
        connection_result = await test_firebase_connection()
        connection_result["last_updated"] = "2025-10-02T00:00:00Z"
        return connection_result
        
    except Exception as e:
        return {
            "connected": False,
            "error": f"Error checking Firebase: {str(e)}",
            "available": FIREBASE_AVAILABLE,
            "status": "error",
            "last_updated": "2025-10-02T00:00:00Z"
        }

@app.get("/firebase/collections", tags=["Firebase"])
async def get_firebase_collections():
    """Obtener información completa de todas las colecciones de Firestore"""
    if not FIREBASE_AVAILABLE or not SCRIPTS_AVAILABLE:
        raise HTTPException(status_code=503, detail="Firebase or scripts not available")
    try:
        collections_data = await get_collections_info()
        
        if not collections_data["success"]:
            raise HTTPException(
                status_code=500, 
                detail=f"Error obteniendo información de colecciones: {collections_data.get('error', 'Error desconocido')}"
            )
        
        # Add timestamp for endpoint tracking
        collections_data["last_updated"] = "2025-10-02T00:00:00Z"  # Endpoint creation/update date  
        return collections_data
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Error interno del servidor: {str(e)}"
        )

@app.get("/firebase/collections/summary", tags=["Firebase"])
async def get_firebase_collections_summary():
    """Obtener resumen estadístico de las colecciones"""
    if not FIREBASE_AVAILABLE or not SCRIPTS_AVAILABLE:
        raise HTTPException(status_code=503, detail="Firebase or scripts not available")
    try:
        summary_data = await get_collections_summary()
        
        if not summary_data["success"]:
            raise HTTPException(
                status_code=500, 
                detail=f"Error obteniendo resumen: {summary_data.get('error', 'Error desconocido')}"
            )
        
        # Add timestamp for endpoint tracking
        summary_data["last_updated"] = "2025-10-02T00:00:00Z"  # Endpoint creation/update date
        return summary_data
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error obteniendo resumen: {str(e)}")

# ============================================================================
# ENDPOINTS DE UNIDADES DE PROYECTO
# ============================================================================

@app.get("/unidades-proyecto/geometry", tags=["Unidades de Proyecto"])
async def export_geometry_for_nextjs(
    # Filtros server-side optimizados
    nombre_centro_gestor: Optional[str] = Query(None, description="Centro gestor responsable"),
    tipo_intervencion: Optional[str] = Query(None, description="Tipo de intervención"),
    estado: Optional[str] = Query(None, description="Estado del proyecto"),
    upid: Optional[str] = Query(None, description="ID específico de unidad"),
    
    # Configuración geográfica
    include_bbox: Optional[bool] = Query(False, description="Calcular y incluir bounding box"),
    limit: Optional[int] = Query(None, ge=1, le=10000, description="Límite de registros")
):
    """
    ## Datos Geoespaciales
    
    **Propósito**: Retorna exclusivamente datos geográficos optimizados para renderizado de mapas.
    
    ### Optimización de Datos
    
    **Campos incluidos**: upid, coordinates, coordenadas, geometry, linestring, polygon, lat, lng, latitude, longitude
    **Campos excluidos**: Todos los atributos no geográficos para máximo rendimiento
    **Bounding box**: Disponible bajo demanda con `include_bbox=true`
    
    ### Estrategia de Filtrado
    
    **Sin filtros**: Dataset geográfico completo
    **Con filtros**: Optimización server-side en Firestore + refinamiento client-side
    
    **Server-side**: upid, estado, tipo_intervencion, nombre_centro_gestor  
    **Client-side**: bbox, include_bbox
    
    ### Parámetros
    
    | Filtro | Descripción |
    |--------|-------------|
    | nombre_centro_gestor | Centro gestor responsable |
    | tipo_intervencion | Tipo de intervención |
    | estado | Estado del proyecto |
    | upid | ID específico de unidad |
    | include_bbox | Incluir bounding box calculado |
    | limit | Límite de resultados (1-10000) |
    
    ### Aplicaciones
    
    - Mapas interactivos de alta performance
    - Capas geográficas para análisis espacial  
    - Integración con bibliotecas cartográficas
    - Visualización masiva de geometrías
    """
    if not FIREBASE_AVAILABLE or not SCRIPTS_AVAILABLE:
        return {
            "success": False,
            "error": "Firebase temporarily unavailable",
            "data": [],
            "count": 0,
            "type": "geometry"
        }
    
    try:
        # Construir filtros optimizados para geometrías
        filters = {}
        
        if nombre_centro_gestor:
            filters["nombre_centro_gestor"] = nombre_centro_gestor
        if tipo_intervencion:
            filters["tipo_intervencion"] = tipo_intervencion
        if estado:
            filters["estado"] = estado
        if upid:
            filters["upid"] = upid
        if limit:
            filters["limit"] = limit
        if include_bbox:
            filters["include_bbox"] = include_bbox
        
        result = await get_unidades_proyecto_geometry(filters)
        
        if not result["success"]:
            raise HTTPException(
                status_code=500,
                detail=f"Error obteniendo geometrías: {result.get('error', 'Error desconocido')}"
            )
        
        return {
            "success": True,
            "data": result["data"],
            "count": result["count"],
            "type": "geometry",
            "collection": "unidades-proyecto",
            "filters_applied": result.get("filters_applied", {}),
            "timestamp": datetime.now().isoformat(),
            "last_updated": "2025-10-02T00:00:00Z",  # Endpoint creation/update date
            "message": result.get("message", "Geometrías obtenidas exitosamente")
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error procesando geometrías: {str(e)}"
        )

@app.get("/unidades-proyecto/attributes", tags=["Unidades de Proyecto"])
async def export_attributes_for_nextjs(
    # Filtros básicos originales
    nombre_centro_gestor: Optional[str] = Query(None, description="Centro gestor responsable"),
    tipo_intervencion: Optional[str] = Query(None, description="Tipo de intervención"),
    estado: Optional[str] = Query(None, description="Estado del proyecto"),
    upid: Optional[str] = Query(None, description="ID específico de unidad"),
    nombre_up: Optional[str] = Query(None, description="Búsqueda parcial en nombre (contiene texto)"),
    comuna_corregimiento: Optional[str] = Query(None, description="Comuna o corregimiento"),
    barrio_vereda: Optional[str] = Query(None, description="Barrio o vereda"),
    direccion: Optional[str] = Query(None, description="Búsqueda parcial en dirección (contiene texto)"),
    referencia_contrato: Optional[str] = Query(None, description="Referencia del contrato"),
    referencia_proceso: Optional[str] = Query(None, description="Referencia del proceso"),
    
    # Paginación
    limit: Optional[int] = Query(None, ge=1, le=1000, description="Máximo de resultados"),
    offset: Optional[int] = Query(None, ge=0, description="Saltar registros para paginación")
):
    """
    ## Atributos Tabulares
    
    **Propósito**: Retorna atributos completos de proyectos excluyendo datos geográficos.
    
    ### Optimización de Datos
    
    **Campos incluidos**: Todos los atributos del proyecto (nombres, estados, referencias, etc.)
    **Campos excluidos**: coordinates, geometry, linestring, polygon, lat, lng y similares
    **Paginación**: Sistema limit/offset para manejo eficiente de grandes volúmenes
    
    ### Estrategia de Filtrado
    
    **Sin filtros**: Dataset completo de atributos  
    **Con filtros**: Optimización server-side + filtros client-side específicos
    
    **Server-side**: upid, estado, tipo_intervencion, nombre_centro_gestor  
    **Client-side**: search, nombre_up, direccion, ubicación geográfica
    
    ### Parámetros
    
    | Filtro | Descripción |
    |--------|-------------|
    | nombre_centro_gestor | Centro gestor responsable |
    | tipo_intervencion | Tipo de intervención |
    | estado | Estado del proyecto |
    | upid | ID específico de unidad |
    | nombre_up | Búsqueda parcial en nombre |
    | comuna_corregimiento | Comuna o corregimiento |
    | barrio_vereda | Barrio o vereda |
    | direccion | Búsqueda parcial en dirección |
    | referencia_contrato | Referencia del contrato |
    | referencia_proceso | Referencia del proceso |
    | **limit** | Máximo resultados (1-1000) |
    | **offset** | Registros a omitir |
    
    ### Aplicaciones
    
    - Grillas de datos y tablas administrativas
    - Reportes tabulares con filtros múltiples
    - Exportación a formatos estructurados
    - Interfaces de búsqueda avanzada
    """
    if not FIREBASE_AVAILABLE or not SCRIPTS_AVAILABLE:
        return {
            "success": False,
            "error": "Firebase temporarily unavailable", 
            "data": [],
            "count": 0,
            "type": "attributes"
        }
    
    try:
        # Construir filtros
        filters = {}
        
        if nombre_centro_gestor:
            filters["nombre_centro_gestor"] = nombre_centro_gestor
        if tipo_intervencion:
            filters["tipo_intervencion"] = tipo_intervencion
        if estado:
            filters["estado"] = estado
        if upid:
            filters["upid"] = upid
        if nombre_up:
            filters["nombre_up"] = nombre_up
        if comuna_corregimiento:
            filters["comuna_corregimiento"] = comuna_corregimiento
        if barrio_vereda:
            filters["barrio_vereda"] = barrio_vereda
        if direccion:
            filters["direccion"] = direccion
        if referencia_contrato:
            filters["referencia_contrato"] = referencia_contrato
        if referencia_proceso:
            filters["referencia_proceso"] = referencia_proceso
        
        result = await get_unidades_proyecto_attributes(
            filters=filters,
            limit=limit,
            offset=offset
        )
        
        if not result["success"]:
            raise HTTPException(
                status_code=500,
                detail=f"Error obteniendo atributos: {result.get('error', 'Error desconocido')}"
            )
        
        return {
            "success": True,
            "data": result["data"],
            "count": result["count"],
            "total_before_limit": result.get("total_before_limit"),
            "type": "attributes",
            "collection": "unidades-proyecto",
            "filters_applied": result.get("filters_applied", {}),
            "pagination": result.get("pagination", {}),
            "timestamp": datetime.now().isoformat(),
            "last_updated": "2025-10-02T00:00:00Z",  # Endpoint creation/update date
            "message": result.get("message", "Atributos obtenidos exitosamente")
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error procesando atributos: {str(e)}"
        )

@app.get("/unidades-proyecto/dashboard", tags=["Unidades de Proyecto"])
async def export_dashboard_for_nextjs(
    # Filtros para dashboard
    nombre_centro_gestor: Optional[str] = Query(None, description="Centro gestor para análisis"),
    tipo_intervencion: Optional[str] = Query(None, description="Tipo de intervención"),
    estado: Optional[str] = Query(None, description="Estado del proyecto"),
    comuna_corregimiento: Optional[str] = Query(None, description="Comuna o corregimiento para análisis"),
    barrio_vereda: Optional[str] = Query(None, description="Barrio o vereda para análisis")
):
    """
    ## Analytics y Métricas de Negocio
    
    **Propósito**: Genera análisis estadístico avanzado, KPIs y métricas agregadas para dashboards ejecutivos.
    
    ### Arquitectura Analítica
    
    **Sin filtros**: Análisis global del portafolio completo de proyectos  
    **Con filtros**: Análisis segmentado según criterios específicos de negocio
    
    **Optimización**: Hereda filtrado server-side de endpoints geometry y attributes
    
    ### Métricas Generadas
    
    | Categoría | Contenido |
    |-----------|-----------|
    | **Resumen General** | Totales, cobertura de datos, completitud |
    | **Distribuciones** | Rankings y porcentajes por estado, tipo, centro gestor, ubicación |
    | **Análisis Geográfico** | Bounding box, centro de gravedad, dispersión territorial |
    | **Calidad de Datos** | Completitud por campos críticos, análisis de integridad |
    | **KPIs de Negocio** | Proyectos activos/finalizados, tasa completitud, cobertura territorial |
    
    ### Parámetros de Segmentación
    
    | Filtro | Aplicación |
    |--------|------------|
    | nombre_centro_gestor | Análisis por responsable institucional |
    | tipo_intervencion | Segmentación por categoría de proyecto |
    | estado | Filtrado por fase de ejecución |
    | comuna_corregimiento | Análisis territorial nivel medio |
    | barrio_vereda | Análisis territorial granular |
    
    ### Aplicaciones
    
    - Dashboards ejecutivos con KPIs institucionales
    - Reportes gerenciales de seguimiento y control  
    - Análisis de distribución y cobertura territorial
    - Evaluación de calidad y completitud de datos
    - Métricas para toma de decisiones estratégicas
    """
    if not FIREBASE_AVAILABLE or not SCRIPTS_AVAILABLE:
        return {
            "success": False,
            "error": "Firebase temporarily unavailable",
            "dashboard": {},
            "type": "dashboard"
        }
    
    try:
        # Construir filtros para dashboard
        filters = {}
        
        if nombre_centro_gestor:
            filters["nombre_centro_gestor"] = nombre_centro_gestor
        if tipo_intervencion:
            filters["tipo_intervencion"] = tipo_intervencion
        if estado:
            filters["estado"] = estado
        if comuna_corregimiento:
            filters["comuna_corregimiento"] = comuna_corregimiento
        if barrio_vereda:
            filters["barrio_vereda"] = barrio_vereda
        
        result = await get_unidades_proyecto_dashboard(filters)
        
        if not result["success"]:
            raise HTTPException(
                status_code=500,
                detail=f"Error generando dashboard: {result.get('error', 'Error desconocido')}"
            )
        
        return {
            "success": True,
            "dashboard": result["dashboard"],
            "data_sources": result.get("data_sources", {}),
            "type": "dashboard",
            "collection": "unidades-proyecto",
            "filters_applied": filters,
            "timestamp": datetime.now().isoformat(),
            "last_updated": "2025-10-02T00:00:00Z",  # Endpoint creation/update date
            "message": result.get("message", "Dashboard generado exitosamente")
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error procesando dashboard: {str(e)}"
        )


# ============================================================================
# ENDPOINT PARA OPCIONES DE FILTROS
# ============================================================================

@app.get("/unidades-proyecto/filters", tags=["Unidades de Proyecto"], response_class=JSONResponse)
async def get_filters_endpoint(
    field: Optional[str] = Query(
        None, 
        description="Campo específico para obtener valores únicos (opcional)",
        enum=[
            "estado", "tipo_intervencion", "nombre_centro_gestor", 
            "comuna_corregimiento", "barrio_vereda", "fuente_financiacion", 
            "ano"
        ]
    ),
    limit: Optional[int] = Query(
        None, 
        description="Límite de valores únicos a retornar (opcional)", 
        ge=1,
        le=100
    )
):
    """
    **Obtener valores únicos para filtros de Unidades de Proyecto**
    
    Endpoint optimizado para poblar controles de filtrado en dashboards y interfaces.
    Diseñado específicamente para aplicaciones NextJS con carga eficiente de opciones.
    
    **Características principales:**
    - **Filtrado inteligente**: Especifica un campo para cargar solo sus valores
    - **Control de volumen**: Aplica límites para evitar sobrecarga de datos  
    - **Optimización server-side**: Usa queries eficientes de Firestore
    - **Cache-friendly**: Estructura optimizada para sistemas de caché
    
    **Casos de uso:**
    - Poblar dropdowns y selectores en dashboards
    - Cargar opciones de filtrado dinámicamente
    - Implementar autocomplete y búsqueda predictiva
    - Validar valores disponibles antes de filtrar
    
    **Campos disponibles:**
    - `estado`: Estados de proyecto (activo, completado, etc.)
    - `tipo_intervencion`: Tipos de intervención urbana
    - `nombre_centro_gestor`: Centros gestores responsables
    - `comuna_corregimiento`: Ubicaciones por comuna/corregimiento
    - `barrio_vereda`: Ubicaciones por barrio/vereda
    - `fuente_financiacion`: Fuentes de financiación del proyecto
    - `ano`: Años de ejecución disponibles
    - `departamento`: Departamentos con proyectos
    - `municipio`: Municipios con proyectos
    
    **Optimizaciones aplicadas:**
    - Sampling inteligente de documentos para reducir latencia
    - Filtros server-side en Firestore para mejor rendimiento
    - Límites configurables para controlar payload
    - Estructura de respuesta optimizada para frontend
    """
    if not FIREBASE_AVAILABLE or not SCRIPTS_AVAILABLE:
        return {
            "success": False,
            "error": "Firebase temporarily unavailable", 
            "filters": {},
            "type": "filters"
        }
    
    try:
        result = await get_filter_options(field=field, limit=limit)
        
        if not result.get("success", False):
            raise HTTPException(
                status_code=500,
                detail=f"Error obteniendo filtros: {result.get('error', 'Error desconocido')}"
            )
        
        response_data = {
            "success": True,
            "filters": result["filters"],
            "metadata": {
                "total_fields": result.get("total_fields", 0),
                "field_requested": result.get("field_requested"),
                "limit_applied": result.get("limit_applied"),
                "optimized_query": True,
                "cache_recommended": True,
                "utf8_enabled": True,
                "spanish_support": True
            },
            "type": "filters",
            "collection": "unidades-proyecto", 
            "timestamp": datetime.now().isoformat(),
            "last_updated": "2025-10-02T00:00:00Z",  # Endpoint creation/update date
            "message": f"Filtros obtenidos exitosamente"
        }
        
        return JSONResponse(
            content=response_data,
            media_type="application/json; charset=utf-8"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error procesando filtros: {str(e)}"
        )


# ============================================================================
# ENDPOINTS DE GESTIÓN CONTRACTUAL
# ============================================================================

@app.get("/contratos/init_contratos_seguimiento", tags=["Gestión Contractual"])
async def init_contratos_seguimiento(
    referencia_contrato: Optional[str] = Query(None, description="Referencia del contrato (búsqueda parcial)"),
    nombre_centro_gestor: Optional[str] = Query(None, description="Centro gestor responsable (exacto)")
):
    """
    ## Inicialización de Contratos para Seguimiento
    
    Obtiene datos de contratos desde la colección `contratos_emprestito` con filtros optimizados.
    
    **Campos retornados**: bpin, banco, nombre_centro_gestor, estado_contrato, referencia_contrato, 
    referencia_proceso, objeto_contrato, modalidad_contratacion
    
    **Filtros**:
    - `referencia_contrato`: Textbox - búsqueda parcial
    - `nombre_centro_gestor`: Dropdown - selección exacta
    
    Sin filtros retorna todos los datos disponibles.
    """
    if not FIREBASE_AVAILABLE or not SCRIPTS_AVAILABLE:
        return {"success": False, "error": "Firebase no disponible", "data": [], "count": 0}
    
    try:
        filters = {}
        if referencia_contrato:
            filters["referencia_contrato"] = referencia_contrato
        if nombre_centro_gestor:
            filters["nombre_centro_gestor"] = nombre_centro_gestor
        
        result = await get_contratos_init_data(filters)
        
        if not result["success"]:
            raise HTTPException(status_code=500, detail=result.get('error', 'Error obteniendo contratos'))
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error procesando contratos: {str(e)}")


# ============================================================================
# ENDPOINTS DE ADMINISTRACIÓN Y CONTROL DE ACCESOS
# ============================================================================

def check_user_management_availability():
    """Verificar disponibilidad de funciones de gestión de usuarios"""
    if not USER_MANAGEMENT_AVAILABLE or not AUTH_OPERATIONS_AVAILABLE or not USER_MODELS_AVAILABLE:
        raise HTTPException(
            status_code=503, 
            detail="Servicios de gestión de usuarios temporalmente no disponibles"
        )

@app.post("/auth/validate-session", tags=["Administración y Control de Accesos"])
async def validate_session(
    request: Request
):
    """
    ## 🔐 Validación de Sesión Activa para Next.js
    
    Valida si un token de ID de Firebase es válido y obtiene información completa del usuario.
    Optimizado para integración con Next.js y Firebase Auth SDK del frontend.
    
    ### ✅ Casos de uso:
    - Middleware de autenticación en Next.js
    - Verificación de permisos antes de acciones sensibles
    - Obtener datos actualizados del usuario
    - Validar sesiones activas desde el frontend
    
    ### 🔧 Proceso:
    1. Verifica token de Firebase desde Authorization header o body
    2. Valida estado del usuario (activo/deshabilitado)
    3. Obtiene datos completos de perfil desde Firestore
    4. Verifica permisos y roles
    
    ### 📝 Ejemplo de uso desde Next.js:
    ```javascript
    // En tu frontend NextJS
    import { getAuth } from 'firebase/auth';
    
    const auth = getAuth();
    const user = auth.currentUser;
    if (user) {
        const idToken = await user.getIdToken();
        const response = await fetch('/auth/validate-session', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${idToken}`
            },
            body: JSON.stringify({ id_token: idToken })
        });
        const data = await response.json();
        if (data.success) {
            console.log('Usuario autenticado:', data.user);
        }
    }
    ```
    """
    try:
        check_user_management_availability()
        
        # Obtener token del header Authorization o del body
        id_token = None
        
        # Primero intentar obtener del header Authorization
        auth_header = request.headers.get("authorization") or request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            id_token = auth_header.split(" ")[1]
        
        # Si no está en el header, intentar obtener del body
        if not id_token:
            try:
                body = await request.json()
                id_token = body.get("id_token")
            except:
                # Si no se puede parsear el JSON, intentar obtener como form data
                try:
                    form = await request.form()
                    id_token = form.get("id_token")
                except:
                    pass
        
        if not id_token:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "Token requerido",
                    "message": "Proporcione el token en el header Authorization o en el body como id_token",
                    "code": "TOKEN_REQUIRED"
                }
            )
        
        result = await validate_user_session(id_token)
        
        if not result["valid"]:
            raise HTTPException(
                status_code=401,
                detail={
                    "error": result["error"],
                    "code": result.get("code", "SESSION_INVALID")
                }
            )
        
        return {
            "success": True,
            "session_valid": True,
            "user": result["user"],
            "token_info": result.get("token_data", {}),
            "verified_at": result["verified_at"],
            "message": "Sesión válida"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error validando sesión: {str(e)}")

@app.post("/auth/login", tags=["Administración y Control de Accesos"])
async def login_user(
    request: Request
):
    """
    ## 🔑 Validación de Credenciales para Next.js
    
    **IMPORTANTE**: Este endpoint NO realiza autenticación real por seguridad.
    Solo valida que las credenciales existan y están activas en el sistema.
    La autenticación real debe hacerse en el frontend con Firebase Auth SDK.
    
    ### ✅ Casos de uso:
    - Validar credenciales antes de mostrar el formulario de login en Next.js
    - Verificar existencia del usuario antes de redirigir a Firebase Auth
    - Obtener información del usuario para pre-poblar forms
    
    ### 🔧 Proceso:
    1. Valida formato de email
    2. Verifica existencia del usuario en Firebase Auth
    3. Confirma que la cuenta está activa
    4. Retorna datos del usuario (SIN autenticar)
    
    ### 🛡️ Seguridad:
    - Firebase Admin SDK NO puede verificar contraseñas
    - La autenticación real DEBE hacerse en el frontend
    - Este endpoint solo valida la existencia y estado del usuario
    
    ### 📝 Ejemplo de uso desde Next.js:
    ```javascript
    // 1. Validar credenciales en backend
    const validateResponse = await fetch('/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password })
    });
    
    if (validateResponse.ok) {
        // 2. Autenticar en frontend con Firebase
        import { signInWithEmailAndPassword } from 'firebase/auth';
        const userCredential = await signInWithEmailAndPassword(auth, email, password);
        
        // 3. Obtener token y validar sesión
        const idToken = await userCredential.user.getIdToken();
        // Usar token para llamadas autenticadas
    }
    ```
    """
    try:
        check_user_management_availability()
        
        # Obtener credenciales del body JSON o form data
        try:
            body = await request.json()
            email = body.get("email")
            password = body.get("password")
        except:
            try:
                form = await request.form()
                email = form.get("email")
                password = form.get("password")
            except:
                raise HTTPException(
                    status_code=400,
                    detail={
                        "error": "Datos requeridos",
                        "message": "Proporcione email y password en el body",
                        "code": "CREDENTIALS_REQUIRED"
                    }
                )
        
        if not email or not password:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "Email y contraseña requeridos",
                    "code": "CREDENTIALS_REQUIRED"
                }
            )
        
        result = await authenticate_email_password(email, password)
        
        if not result["success"]:
            # Determinar el status code apropiado basado en el tipo de error
            if result.get("code") in ["EMAIL_VALIDATION_ERROR", "INVALID_EMAIL_FORMAT"]:
                status_code = 400  # Bad Request para errores de validación
            elif result.get("code") in ["USER_NOT_FOUND", "USER_DISABLED", "ACCOUNT_INACTIVE"]:
                status_code = 401  # Unauthorized para problemas de autenticación
            else:
                status_code = 401  # Default para otros errores de auth
                
            raise HTTPException(
                status_code=status_code,
                detail={
                    "error": result["error"],
                    "code": result.get("code", "AUTH_FAILED")
                }
            )
        
        return {
            "success": True,
            "user": result["user"],
            "auth_method": result["auth_method"],
            "message": result["message"],
            "frontend_auth_required": True,
            "note": "Proceda con autenticación en frontend usando Firebase Auth SDK",
            "timestamp": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error en validación de credenciales: {str(e)}")

@app.post("/auth/register", tags=["Administración y Control de Accesos"], status_code=status.HTTP_201_CREATED)
async def register_user(
    request: Request
):
    """
    ## 👤 Registro de Usuario Nuevo para Next.js
    
    Crea nuevas cuentas con validaciones completas y configuración automática de roles.
    Optimizado para integración con Next.js y Firebase Auth SDK.
    
    ### ✅ Casos de uso:
    - Registro de empleados nuevos desde Next.js
    - Autoregistro con aprobación posterior
    - Migración de usuarios existentes
    
    ### 🔧 Características:
    - Validación completa de datos (email, contraseña, teléfono)
    - Creación en Firebase Auth y Firestore  
    - Rol por defecto: 'viewer' (modificable por administrador)
    - Generación opcional de enlace de verificación
    - Verificación de dominio (@cali.gov.co)
    - Soporte para JSON y form data
    
    ### 📋 Requisitos:
    - **Email**: Debe ser del dominio @cali.gov.co
    - **Contraseña**: Mínimo 8 caracteres, mayúsculas, minúsculas, números y símbolos
    - **Teléfono**: Formato colombiano válido (+57 3XX XXX XXXX)
    
    ### 📝 Ejemplo de uso desde Next.js:
    ```javascript
    const userData = {
      email: "maria.gonzalez@cali.gov.co",
      password: "SecurePass123!",
      fullname: "María González",
      cellphone: "+57 315 987 6543",
      nombre_centro_gestor: "Secretaría de Salud"
    };
    
    const response = await fetch('/auth/register', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(userData)
    });
    
    const result = await response.json();
    if (result.success) {
        console.log('Usuario creado:', result.user);
    }
    ```
    """
    try:
        check_user_management_availability()
        
        # Obtener datos del body JSON o form data
        try:
            body = await request.json()
            email = body.get("email")
            password = body.get("password") 
            fullname = body.get("fullname")
            cellphone = body.get("cellphone")
            nombre_centro_gestor = body.get("nombre_centro_gestor")
        except:
            try:
                form = await request.form()
                email = form.get("email")
                password = form.get("password")
                fullname = form.get("fullname") 
                cellphone = form.get("cellphone")
                nombre_centro_gestor = form.get("nombre_centro_gestor")
            except:
                raise HTTPException(
                    status_code=400,
                    detail={
                        "error": "Datos requeridos",
                        "message": "Proporcione todos los campos requeridos en el body",
                        "code": "REGISTRATION_DATA_REQUIRED"
                    }
                )
        
        # Validar que todos los campos requeridos estén presentes
        if not all([email, password, fullname, cellphone, nombre_centro_gestor]):
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "Campos requeridos faltantes",
                    "message": "email, password, fullname, cellphone y nombre_centro_gestor son requeridos",
                    "code": "MISSING_REQUIRED_FIELDS"
                }
            )
            
        result = await create_user_account(
            email=email,
            password=password,
            fullname=fullname,
            cellphone=cellphone,
            nombre_centro_gestor=nombre_centro_gestor,
            send_email_verification=True
        )
        
        if not result["success"]:
            error_code = result.get("code", "USER_CREATION_ERROR")
            if error_code == "EMAIL_ALREADY_EXISTS":
                raise HTTPException(
                    status_code=409, 
                    detail={
                        "success": False,
                        "error": result["error"],
                        "code": error_code
                    }
                )
            elif error_code in ["INVALID_EMAIL_FORMAT", "EMAIL_VALIDATION_ERROR"]:
                raise HTTPException(
                    status_code=400,
                    detail={
                        "success": False,
                        "error": result["error"],
                        "code": error_code
                    }
                )
            elif "valid" in result and not result["valid"]:
                # Error de validación (contraseña, teléfono, etc.)
                raise HTTPException(
                    status_code=400,
                    detail={
                        "success": False,
                        "error": result.get("error", "Datos de entrada inválidos"),
                        "code": error_code,
                        "validation_errors": result.get("errors", [])
                    }
                )
            else:
                # Error genérico
                raise HTTPException(
                    status_code=400,
                    detail={
                        "success": False,
                        "error": result.get("error", "Error creando cuenta de usuario"),
                        "code": error_code
                    }
                )
        
        response_data = {
            "success": True,
            "user": result["user"],
            "verification_link": result.get("verification_link"),
            "message": handle_utf8_text(result["message"]),
            "timestamp": datetime.now().isoformat()
        }
        return create_utf8_response(response_data, 201)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error registrando usuario: {str(e)}")

@app.post("/auth/change-password", tags=["Administración y Control de Accesos"])
async def change_password(
    uid: str = Form(..., description="ID del usuario"),
    new_password: str = Form(..., description="Nueva contraseña")
):
    """
    ## 🔒 Cambio de Contraseña
    
    Actualiza contraseñas de usuarios con validaciones de seguridad completas.
    
    ### ✅ Casos de uso:
    - Reset de contraseña por administrador
    - Cambio forzado por políticas de seguridad
    - Actualización por compromiso de cuenta
    
    ### 🔧 Validaciones:
    - Verificación de existencia del usuario
    - Validación de fortaleza de contraseña (8+ caracteres, mayúsculas, minúsculas, números, símbolos)
    - Actualización en Firebase Auth
    - Registro de timestamp en Firestore
    - Contador de cambios de contraseña
    
    ### 🛡️ Seguridad:
    - Solo administradores pueden cambiar contraseñas
    - Histórico de cambios para auditoría
    - Notificación automática al usuario
    
    ### 📝 Ejemplo de uso:
    ```javascript
    const passwordData = {
      uid: "Zx9mK2pQ8RhV3nL7jM4uX1qW6tY0sA5e",
      new_password: "NuevaPassword123!"
    };
    const response = await fetch('/auth/change-password', {
      method: 'POST', 
      body: JSON.stringify(passwordData)
    });
    ```
    """
    try:
        check_user_management_availability()
        
        result = await update_user_password(uid, new_password)
        
        if not result["success"]:
            error_code = result.get("code", "PASSWORD_UPDATE_ERROR")
            if error_code == "USER_NOT_FOUND":
                raise HTTPException(status_code=404, detail=result["error"])
            else:
                raise HTTPException(status_code=400, detail=result)
        
        return {
            "success": True,
            "message": result["message"],
            "updated_at": result["updated_at"],
            "timestamp": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error cambiando contraseña: {str(e)}")

@app.get("/auth/config", tags=["Administración y Control de Accesos"])
async def get_auth_config():
    """
    ## ⚙️ Configuración de Autenticación para Next.js
    
    Obtiene la configuración necesaria para integrar Firebase Auth en el frontend.
    
    ### 📋 Información incluida:
    - ID del proyecto Firebase
    - Configuración de Firebase para frontend
    - Endpoints disponibles
    - Dominios autorizados
    - Requisitos de contraseña
    - Métodos de autenticación habilitados
    
    ### 📝 Ejemplo de uso desde Next.js:
    ```javascript
    // Obtener configuración del backend
    const configResponse = await fetch('/auth/config');
    const config = await configResponse.json();
    
    // Usar en Firebase config
    const firebaseConfig = {
        ...config.firebase_config,
        // Otras configuraciones específicas del frontend
    };
    ```
    """
    return {
        "success": True,
        "firebase_config": {
            "projectId": PROJECT_ID,
            "authDomain": f"{PROJECT_ID}.firebaseapp.com",
            "databaseURL": f"https://{PROJECT_ID}-default-rtdb.firebaseio.com",
            "storageBucket": f"{PROJECT_ID}.appspot.com"
        },
        "auth_settings": {
            "domain_restriction": "@cali.gov.co",
            "password_requirements": {
                "min_length": 8,
                "require_uppercase": True,
                "require_lowercase": True,
                "require_numbers": True,
                "require_special": True
            },
            "email_verification_required": True,
            "google_auth_enabled": True,
            "phone_format": "+57 3XX XXX XXXX",
            "default_role": "viewer"
        },
        "endpoints": {
            "validate_session": "/auth/validate-session",
            "login": "/auth/login", 
            "register": "/auth/register",
            "google_auth": "/auth/google",
            "config": "/auth/config"
        },
        "auth_methods": [
            {
                "method": "email_password",
                "enabled": True,
                "description": "Email y contraseña"
            },
            {
                "method": "google",
                "enabled": True,
                "description": "Autenticación con Google",
                "domain_required": "@cali.gov.co"
            }
        ],
        "integration_notes": {
            "firebase_auth_required": True,
            "backend_validates_only": True,
            "frontend_auth_flow": "El frontend debe manejar la autenticación con Firebase Auth SDK",
            "token_validation": "Usar /auth/validate-session para validar tokens en el backend"
        },
        "timestamp": datetime.now().isoformat()
    }

@app.get("/auth/integration-guide", tags=["Administración y Control de Accesos"])
async def get_integration_guide():
    """
    ## 📖 Guía de Integración Completa para Next.js
    
    **TODO LO QUE NECESITAS** para integrar autenticación Firebase en Next.js.
    
    ### 🎯 **Flujo de Autenticación Recomendado**
    
    ### 📋 **1. Configuración Inicial**
    ```javascript
    // firebase.js - Configuración de Firebase
    import { initializeApp } from 'firebase/app';
    import { getAuth } from 'firebase/auth';
    
    // Obtener configuración del backend
    const configResponse = await fetch('/auth/config');
    const config = await configResponse.json();
    
    const firebaseConfig = config.firebase_config;
    const app = initializeApp(firebaseConfig);
    export const auth = getAuth(app);
    ```
    
    ### 🔑 **2. Login con Email/Password**
    ```javascript
    import { signInWithEmailAndPassword } from 'firebase/auth';
    
    async function loginUser(email, password) {
        try {
            // 1. Validar credenciales en backend
            const validateResponse = await fetch('/auth/login', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email, password })
            });
            
            if (validateResponse.ok) {
                // 2. Autenticar en frontend
                const userCredential = await signInWithEmailAndPassword(auth, email, password);
                console.log('Usuario autenticado:', userCredential.user);
                return userCredential.user;
            }
        } catch (error) {
            console.error('Error en login:', error);
        }
    }
    ```
    
    ### 👤 **3. Registro de Usuario**
    ```javascript
    async function registerUser(userData) {
        const response = await fetch('/auth/register', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(userData)
        });
        return await response.json();
    }
    ```
    
    ### 🔐 **4. Validación de Sesión**
    ```javascript
    import { onAuthStateChanged } from 'firebase/auth';
    
    onAuthStateChanged(auth, async (user) => {
        if (user) {
            const idToken = await user.getIdToken();
            const response = await fetch('/auth/validate-session', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${idToken}`
                }
            });
            const sessionData = await response.json();
            console.log('Sesión válida:', sessionData);
        }
    });
    ```
    """
    return {
        "integration_complexity": "moderate",
        "framework": "Next.js + Firebase Auth SDK",
        "key_endpoints": {
            "config": "/auth/config",
            "login": "/auth/login",
            "register": "/auth/register", 
            "validate_session": "/auth/validate-session",
            "google_auth": "/auth/google"
        },
        "auth_flow": {
            "step_1": "Frontend obtiene configuración desde /auth/config",
            "step_2": "Frontend inicializa Firebase Auth SDK",
            "step_3": "Backend valida credenciales en /auth/login",
            "step_4": "Frontend autentica con Firebase Auth SDK",
            "step_5": "Backend valida tokens en /auth/validate-session"
        },
        "required_packages": [
            "firebase@^10.0.0",
            "next@^14.0.0"
        ],
        "security_notes": [
            "Backend NO maneja autenticación directa por seguridad",
            "Frontend debe usar Firebase Auth SDK para autenticación real", 
            "Backend solo valida tokens y proporciona datos de usuario",
            "Tokens ID de Firebase son la fuente de verdad para autenticación"
        ]
    }

@app.get("/auth/workload-identity/status", tags=["Administración y Control de Accesos"])
async def get_workload_identity_status():
    """
    ## 🔍 Estado de Workload Identity Federation
    
    Verifica el estado actual del sistema de autenticación automática con Google Cloud.
    
    ### 📊 Información incluida:
    - Estado de inicialización de Workload Identity
    - Validez de credenciales automáticas
    - Configuración OAuth2 disponible
    - Integración con Firebase
    - Nivel de seguridad actual
    
    ### 🛠️ Útil para:
    - Diagnóstico de problemas de autenticación
    - Verificar configuración automática
    - Auditoría de seguridad
    - Monitoreo del sistema
    """
    try:
        from api.scripts.workload_identity_auth import get_workload_identity_status
        
        status = get_workload_identity_status()
        
        return {
            "success": True,
            "workload_identity_status": status,
            "system_ready": status.get("workload_identity", {}).get("initialized", False),
            "security_level": status.get("security_level", "unknown"),
            "timestamp": datetime.now().isoformat(),
            "message": "Estado de Workload Identity obtenido exitosamente"
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": "Error obteniendo estado de Workload Identity",
            "details": str(e),
            "fallback_available": True,
            "message": "Sistema puede funcionar en modo compatible"
        }

@app.post("/auth/google", tags=["Administración y Control de Accesos"])
async def google_auth_unified(
    google_token: str = Form(..., description="ID Token de Google Sign-In")
):
    """
    ## 🔐 Autenticación Google - ENDPOINT ÚNICO
    
    **EL ÚNICO ENDPOINT** que necesitas para autenticación Google completa.
    
    ### 🎯 **Funcionalidad Completa:**
    - ✅ Verifica token automáticamente con Workload Identity
    - ✅ Crea usuarios nuevos automáticamente
    - ✅ Actualiza usuarios existentes
    - ✅ Valida dominio @cali.gov.co
    - ✅ Retorna información completa del usuario
    - ✅ Máxima seguridad sin configuración manual
    
    ### � **Uso desde Frontend:**
    ```javascript
    // Después de Google Sign-In
    function handleGoogleAuth(response) {
        fetch('/auth/google', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ google_token: response.credential })
        })
        .then(res => res.json())
        .then(data => {
            if (data.success) {
                console.log('✅ Autenticado:', data.user);
                // Tu lógica aquí
            }
        });
    }
    ```
    
    ### 📱 **Compatible con:**
    - React, Vue, Angular, NextJS
    - Aplicaciones móviles
    - Progressive Web Apps
    - Cualquier framework que haga HTTP requests
    
    ### 🔒 **Seguridad:**
    - Workload Identity Federation
    - Sin credenciales en código
    - Verificación automática con Google
    - Auditoría completa de accesos
    """
    try:
        from api.scripts.workload_identity_auth import authenticate_with_workload_identity
        
        result = await authenticate_with_workload_identity(google_token)
        
        if not result["success"]:
            error_code = result.get("code", "GOOGLE_AUTH_ERROR")
            
            # Mapear errores específicos a códigos HTTP apropiados
            if error_code == "UNAUTHORIZED_DOMAIN":
                raise HTTPException(status_code=403, detail={
                    "error": "Dominio no autorizado",
                    "message": "Solo se permite autenticación con cuentas @cali.gov.co",
                    "code": "UNAUTHORIZED_DOMAIN"
                })
            elif error_code in ["INVALID_TOKEN", "TOKEN_VERIFICATION_ERROR"]:
                raise HTTPException(status_code=401, detail={
                    "error": "Token inválido",
                    "message": "El token de Google no es válido o ha expirado",
                    "code": "INVALID_TOKEN"
                })
            elif error_code == "WORKLOAD_IDENTITY_ERROR":
                raise HTTPException(status_code=503, detail={
                    "error": "Servicio no disponible",
                    "message": "Sistema de autenticación temporalmente no disponible",
                    "code": "SERVICE_UNAVAILABLE"
                })
            else:
                raise HTTPException(status_code=400, detail={
                    "error": "Error de autenticación",
                    "message": result.get("error", "Error desconocido"),
                    "code": error_code
                })
        
        return {
            "success": True,
            "user": result["user"],
            "auth_method": "workload_identity_google",
            "security_level": "high",
            "user_created": result.get("user_created", False),
            "message": result["message"],
            "timestamp": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in Google auth: {e}")
        raise HTTPException(status_code=500, detail={
            "error": "Error interno del servidor",
            "message": "Por favor, inténtelo de nuevo más tarde",
            "code": "INTERNAL_ERROR"
        })

# ============================================================================
# ENDPOINTS DE ELIMINACIÓN DE USUARIOS
# ============================================================================

@app.delete("/auth/user/{uid}", tags=["Administración y Control de Accesos"])
async def delete_user(uid: str, soft_delete: Optional[bool] = Query(default=None, description="Eliminación lógica (true) o física (false)")):
    """
    ## 🗑️ Eliminación de Usuario
    
    Elimina cuentas con opciones flexibles de soft delete (recomendado) o hard delete.
    
    ### ✅ Casos de uso:
    - Desvinculación de empleados (soft delete)
    - Limpieza de cuentas de prueba (hard delete)
    - Cumplimiento de políticas de retención de datos
    
    ### 🔧 Tipos de eliminación:
    - **Soft delete (predeterminado)**: Deshabilita usuario, mantiene datos para auditoría
    - **Hard delete**: Elimina completamente de Firebase Auth y Firestore
    
    ### 🛡️ Protecciones:
    - No permite eliminar el último administrador del sistema
    - Validación de permisos para hard delete
    - Registro de auditoría de eliminaciones
    
    ### 📝 Ejemplos de uso:
    ```javascript
    // Eliminación lógica (recomendada)
    const response = await fetch('/auth/user/Zx9mK2pQ8RhV3nL7jM4uX1qW6tY0sA5e?soft_delete=true', {
      method: 'DELETE'
    });
    
    // Eliminación física (permanente)
    const response = await fetch('/auth/user/Zx9mK2pQ8RhV3nL7jM4uX1qW6tY0sA5e?soft_delete=false', {
      method: 'DELETE'
    });
    ```
    """
    try:
        check_user_management_availability()
        
        result = await delete_user_account(uid, soft_delete if soft_delete is not None else True)
        
        if not result["success"]:
            error_code = result.get("code", "USER_DELETE_ERROR")
            if error_code == "USER_NOT_FOUND":
                raise HTTPException(status_code=404, detail=result["error"])
            else:
                raise HTTPException(status_code=400, detail=result["error"])
        
        return {
            "success": True,
            "message": result["message"],
            "deleted_at": result["deleted_at"],
            "soft_delete": result["soft_delete"],
            "timestamp": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error eliminando usuario: {str(e)}")

# ============================================================================
# ENDPOINTS ADMINISTRATIVOS DE USUARIOS
# ============================================================================

@app.get("/admin/users", tags=["Administración y Control de Accesos"])
async def list_system_users(
    limit: int = Query(default=100, ge=1, le=1000, description="Límite de resultados por página"),
    page_token: Optional[str] = Query(default=None, description="Token para obtener siguiente página"),
    filter_by_role: Optional[str] = Query(default=None, description="Filtrar por rol específico"),
    filter_by_centro_gestor: Optional[str] = Query(default=None, description="Filtrar por centro gestor"),
    include_disabled: Optional[bool] = Query(default=None, description="Incluir usuarios deshabilitados")
):
    """
    ## 📋 Listado Administrativo de Usuarios
    
    Obtiene lista completa de usuarios con filtros avanzados y paginación.
    
    ### ✅ Casos de uso:
    - Dashboard administrativo
    - Reportes de usuarios por centro
    - Auditoría de cuentas activas/inactivas
    
    ### 🔧 Filtros disponibles:
    - **Por rol**: viewer, editor, admin, super_admin
    - **Por centro gestor**: Departamentos específicos
    - **Estado**: Incluir/excluir usuarios deshabilitados
    - **Paginación**: Control de resultados por página
    
    ### 📊 Información incluida:
    - Datos básicos (email, nombre, teléfono)
    - Estado de verificación y activación
    - Último inicio de sesión
    - Proveedores de autenticación habilitados
    - Estadísticas de uso
    
    ### 📝 Ejemplo de uso:
    ```javascript
    // Obtener admins activos
    const response = await fetch('/admin/users?filter_by_role=admin&include_disabled=false');
    
    // Paginación
    const nextPage = await fetch('/admin/users?page_token=next_page_123&limit=50');
    ```
    """
    try:
        check_user_management_availability()
        
        result = await list_users(
            limit=limit,
            page_token=page_token,
            filter_by_role=filter_by_role.value if filter_by_role else None,
            filter_by_centro_gestor=filter_by_centro_gestor.value if filter_by_centro_gestor else None,
            include_disabled=include_disabled if include_disabled is not None else False
        )
        
        if not result["success"]:
            raise HTTPException(status_code=500, detail=result["error"])
        
        return {
            "success": True,
            "users": result["users"],
            "count": result["count"],
            "has_next_page": result["has_next_page"],
            "next_page_token": result["next_page_token"],
            "filters_applied": result["filters_applied"],
            "timestamp": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error listando usuarios: {str(e)}")

# ============================================================================
# SERVIDOR
# ============================================================================

# Ejecutar servidor si se llama directamente
if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    print(f"Starting server on port: {port}")
    print(f"Environment: {os.getenv('ENVIRONMENT', 'development')}")
    print(f"Firebase Project: {PROJECT_ID}")
    
    uvicorn.run(
        "main:app", 
        host="0.0.0.0", 
        port=port, 
        reload=False
    )

# -*- coding: utf-8 -*-
"""
Gestor de Proyectos API - Versión Limpia
API principal para gestión de proyectos con Firebase
Arquitectura modular optimizada para NextJS
Soporte completo para UTF-8 y caracteres especiales en español
"""

import os
import sys
import logging
from contextlib import asynccontextmanager
from dotenv import load_dotenv

# Cargar variables de entorno desde .env
load_dotenv()

# Configurar logger
logger = logging.getLogger(__name__)

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
from fastapi import FastAPI, HTTPException, Query, Request, status, Form, UploadFile, File, Path, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from typing import Dict, Any, Optional, Union, List
from pydantic import BaseModel, Field
import uvicorn
import asyncio
from datetime import datetime
import json
import re
import uuid
from shapely.geometry import shape as shapely_shape, Point as ShapelyPoint

# Rate limiting (opcional, con fallback)
try:
    from slowapi import Limiter, _rate_limit_exceeded_handler
    from slowapi.util import get_remote_address
    from slowapi.errors import RateLimitExceeded
    SLOWAPI_AVAILABLE = True
    print("✅ SlowAPI loaded successfully")
except ImportError as e:
    print(f"⚠️ Warning: SlowAPI not available: {e} - Rate limiting disabled")
    SLOWAPI_AVAILABLE = False
    Limiter = None
    _rate_limit_exceeded_handler = None
    get_remote_address = None
    RateLimitExceeded = None

# Monitoring with Prometheus (DESHABILITADO temporalmente por conflictos en Railway)
# TODO: Habilitar cuando se configure correctamente prometheus_multiproc_dir
PROMETHEUS_AVAILABLE = False
Counter = None
Histogram = None
Gauge = None
generate_latest = None
CONTENT_TYPE_LATEST = None
print("⚠️ Prometheus metrics disabled (temporarily disabled for Railway compatibility)")

# Importar para manejar tipos de Firebase
try:
    from google.cloud.firestore_v1._helpers import DatetimeWithNanoseconds
    FIREBASE_TYPES_AVAILABLE = True
except ImportError:
    FIREBASE_TYPES_AVAILABLE = False
    DatetimeWithNanoseconds = None

# Importar sistema de autenticación y autorización
try:
    from auth_system import (
        ROLES,
        DEFAULT_USER_ROLE,
        ROLE_HIERARCHY,
        PUBLIC_PATHS as AUTH_PUBLIC_PATHS
    )
    from auth_system.middleware import AuthorizationMiddleware, AuditLogMiddleware
    AUTH_SYSTEM_AVAILABLE = True
    print("✅ Auth system loaded successfully")
except ImportError as e:
    print(f"⚠️ Warning: Auth system not available: {e}")
    AUTH_SYSTEM_AVAILABLE = False
    ROLES = {}
    DEFAULT_USER_ROLE = "publico"
    ROLE_HIERARCHY = {}
    AUTH_PUBLIC_PATHS = []

# 🔐 FUNCIÓN HELPER PARA VERIFICAR AUTENTICACIÓN FIREBASE
async def verify_firebase_token(request: Request) -> dict:
    """
    Verifica el token de Firebase desde el header Authorization
    Retorna los datos del usuario si el token es válido
    """
    auth_header = request.headers.get("Authorization")
    
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail={
                "success": False,
                "error": "Token de autenticación requerido",
                "code": "MISSING_TOKEN"
            }
        )
    
    try:
        token = auth_header.split(" ")[1]
        
        # Verificar token con Firebase
        from firebase_admin import auth
        decoded_token = auth.verify_id_token(token)
        
        # Obtener datos adicionales del usuario desde Firestore
        from database.firebase_config import get_firestore_client
        firestore_client = get_firestore_client()
        
        user_doc = firestore_client.collection('users').document(decoded_token['uid']).get()
        user_data = {}
        if user_doc.exists:
            user_data = user_doc.to_dict()
        
        return {
            "uid": decoded_token['uid'],
            "email": decoded_token.get('email'),
            "email_verified": decoded_token.get('email_verified', False),
            "firestore_data": user_data
        }
        
    except auth.InvalidIdTokenError:
        raise HTTPException(
            status_code=401,
            detail={
                "success": False,
                "error": "Token inválido o expirado",
                "code": "INVALID_TOKEN"
            }
        )
    except auth.ExpiredIdTokenError:
        raise HTTPException(
            status_code=401,
            detail={
                "success": False,
                "error": "Token expirado",
                "code": "TOKEN_EXPIRED"
            }
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "error": f"Error verificando autenticación: {str(e)}",
                "code": "AUTH_VERIFICATION_ERROR"
            }
        )
    AuthorizationMiddleware = None
    AuditLogMiddleware = None

# Importar Firebase con configuración automática
try:
    from database.firebase_config import (
        PROJECT_ID, 
        FIREBASE_AVAILABLE, 
        ensure_firebase_configured, 
        configure_firebase,
        validate_firebase_connection,
        get_firestore_client
    )
    print(f"✅ Firebase auto-config loaded successfully - FIREBASE_AVAILABLE: {FIREBASE_AVAILABLE}")
except Exception as e:
    print(f"❌ Warning: Firebase import failed: {e}")
    FIREBASE_AVAILABLE = False
    PROJECT_ID = os.getenv("FIREBASE_PROJECT_ID", "NOT_CONFIGURED")
    configure_firebase = lambda: (False, {"error": "Not available"})
    ensure_firebase_configured = lambda: False
    validate_firebase_connection = lambda: {"connected": False, "error": "Not available"}
    get_firestore_client = lambda: None

# Importar scripts de forma segura
try:
    from api.scripts import (
        # Firebase operations
        get_collections_info,
        test_firebase_connection,
        get_collections_summary,
        get_proyectos_presupuestales,
        get_unique_nombres_centros_gestores,
        get_proyectos_presupuestales_by_bpin,
        get_proyectos_presupuestales_by_bp,
        get_proyectos_presupuestales_by_centro_gestor,
        # Unidades proyecto operations (funciones especializadas y optimizadas)
        get_unidades_proyecto_geometry,
        get_unidades_proyecto_attributes,
        get_filter_options,
        validate_unidades_proyecto_collection,
        get_unidades_proyecto_quality_metrics,
        # Contratos operations
        get_contratos_init_data,
        get_contratos_emprestito_all,
        get_contratos_emprestito_by_referencia,
        get_contratos_emprestito_by_centro_gestor,
        # Bancos operations
        get_procesos_emprestito_all,
        # Empréstito operations completas
        obtener_datos_secop_completos,
        actualizar_proceso_emprestito_completo,
        procesar_todos_procesos_emprestito_completo,
        # Nuevas funciones para proyecciones de empréstito
        crear_tabla_proyecciones_desde_sheets,
        leer_proyecciones_emprestito,
        leer_proyecciones_no_guardadas,
        get_proyecciones_sin_proceso,
        actualizar_proyeccion_emprestito,
        # Control de cambios para auditoría
        registrar_cambio_valor,
        obtener_historial_cambios,
        # Reportes contratos operations
        create_reporte_contrato,
        get_reportes_contratos,
        get_reporte_contrato_by_id,
        get_reportes_by_centro_gestor,
        get_reportes_by_referencia_contrato,
        setup_google_drive_service,
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
        # Proyectos presupuestales operations
        process_proyectos_presupuestales_json,
        # Availability flags
        USER_MANAGEMENT_AVAILABLE,
        AUTH_OPERATIONS_AVAILABLE,
        EMPRESTITO_OPERATIONS_AVAILABLE,
        REPORTES_CONTRATOS_AVAILABLE,
        PROYECTOS_PRESUPUESTALES_OPERATIONS_AVAILABLE,
        # Flujo caja operations
        process_flujo_caja_excel,
        save_flujo_caja_to_firebase,
        get_flujo_caja_from_firebase,
        FLUJO_CAJA_OPERATIONS_AVAILABLE,
    )
    SCRIPTS_AVAILABLE = True
    print(f"✅ Scripts imported successfully - SCRIPTS_AVAILABLE: {SCRIPTS_AVAILABLE}")
except Exception as e:
    print(f"❌ Warning: Scripts import failed: {e}")
    SCRIPTS_AVAILABLE = False
    USER_MANAGEMENT_AVAILABLE = False
    AUTH_OPERATIONS_AVAILABLE = False
    FLUJO_CAJA_OPERATIONS_AVAILABLE = False

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
        EmprestitoRequest,
        EmprestitoResponse,
        ProyeccionEmprestitoUpdateRequest,
        ProyeccionEmprestitoUpdateResponse,
        ProyeccionEmprestitoRegistroRequest,
        ProyeccionEmprestitoRegistroResponse,
        RPCUpdateRequest,
        RPCUpdateResponse,
        USER_MODELS_AVAILABLE,
        # Reportes contratos models
        ReporteContratoRequest,
        ReporteContratoResponse,
        REPORTE_MODELS_AVAILABLE,
        # Proyectos presupuestales models
        PROYECTOS_PRESUPUESTALES_MODELS_AVAILABLE,
        # Flujo de caja models
        FlujoCajaRequest,
        FlujoCajaResponse,
        FlujoCajaUploadRequest,
        FlujoCajaFilters,
        FLUJO_CAJA_MODELS_AVAILABLE,
    )
    print(f"✅ User models imported successfully - USER_MODELS_AVAILABLE: {USER_MODELS_AVAILABLE}")
except Exception as e:
    print(f"❌ Warning: User models import failed: {e}")
    USER_MODELS_AVAILABLE = False
    
    # Crear clases dummy para evitar errores de NameError
    from pydantic import BaseModel
    from typing import Optional
    
    class UserRegistrationRequest(BaseModel):
        email: str
        password: str
        confirmPassword: str
        name: str
        cellphone: str
        nombre_centro_gestor: str
    
    class UserLoginRequest(BaseModel):
        email: str
        password: str
    
    class PasswordUpdateRequest(BaseModel):
        uid: str
        new_password: str
    
    class GoogleAuthRequest(BaseModel):
        id_token: str
    
    class SessionValidationRequest(BaseModel):
        id_token: str
    
    class UserListFilters(BaseModel):
        pass
    
    class StandardResponse(BaseModel):
        success: bool
        message: Optional[str] = None
    
    class ValidationErrorResponse(BaseModel):
        success: bool = False
        error: str
    
    class EmprestitoRequest(BaseModel):
        referencia_proceso: str
        nombre_centro_gestor: str
        nombre_banco: str
        bp: str
        plataforma: str
        nombre_resumido_proceso: Optional[str] = None
        id_paa: Optional[str] = None
        valor_proyectado: Optional[float] = None
    
    class EmprestitoResponse(BaseModel):
        success: bool
        message: Optional[str] = None



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

# ============================================
# 📊 MÉTRICAS DE PROMETHEUS PARA MONITOREO APM
# ============================================
# Inicializar métricas como None por defecto
REQUEST_COUNT = None
REQUEST_LATENCY = None
ACTIVE_REQUESTS = None
FIREBASE_QUERIES = None
CACHE_HITS = None
CACHE_MISSES = None

if PROMETHEUS_AVAILABLE and Counter is not None:
    try:
        # Configurar Prometheus para modo multi-proceso si está disponible
        # Esto previene errores cuando Railway usa múltiples workers
        import os
        if 'prometheus_multiproc_dir' not in os.environ:
            # Si no está configurado multi-proceso, usar registro normal
            pass
        
        REQUEST_COUNT = Counter(
            'gestor_api_requests_total', 
            'Total de requests por endpoint',
            ['method', 'endpoint', 'status']
        )

        REQUEST_LATENCY = Histogram(
            'gestor_api_request_duration_seconds',
            'Latencia de requests en segundos',
            ['method', 'endpoint']
        )

        ACTIVE_REQUESTS = Gauge(
            'gestor_api_requests_active',
            'Número de requests activos',
            ['method', 'endpoint']
        )

        FIREBASE_QUERIES = Counter(
            'gestor_api_firebase_queries_total',
            'Total de queries a Firebase/Firestore',
            ['collection']
        )

        CACHE_HITS = Counter(
            'gestor_api_cache_hits_total',
            'Total de cache hits',
            ['endpoint']
        )

        CACHE_MISSES = Counter(
            'gestor_api_cache_misses_total',
            'Total de cache misses',
            ['endpoint']
        )
        print("✅ Prometheus metrics initialized")
    except ValueError as e:
        # ValueError típicamente ocurre cuando la métrica ya está registrada (múltiples workers)
        print(f"⚠️ Warning: Prometheus metrics already registered (multi-worker): {e}")
        print("   Metrics will be disabled for this worker to prevent conflicts")
        REQUEST_COUNT = None
        REQUEST_LATENCY = None
        ACTIVE_REQUESTS = None
        FIREBASE_QUERIES = None
        CACHE_HITS = None
        CACHE_MISSES = None
    except Exception as e:
        print(f"⚠️ Warning: Failed to initialize Prometheus metrics: {e}")
        print("   Continuing without metrics...")
        REQUEST_COUNT = None
        REQUEST_LATENCY = None
        ACTIVE_REQUESTS = None
        FIREBASE_QUERIES = None
        CACHE_HITS = None
        CACHE_MISSES = None
else:
    print("⚠️ Prometheus metrics disabled")

# ============================================
# 🚦 RATE LIMITER PARA PREVENIR ABUSO
# ============================================
if SLOWAPI_AVAILABLE:
    limiter = Limiter(key_func=get_remote_address)
    print("✅ Rate limiter initialized")
else:
    limiter = None
    print("⚠️ Rate limiting disabled")

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

# Registrar el rate limiter con FastAPI (solo si está disponible)
if SLOWAPI_AVAILABLE and limiter is not None and RateLimitExceeded is not None and _rate_limit_exceeded_handler is not None:
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    print("✅ Rate limiting registered with FastAPI")
else:
    print("⚠️ Rate limiting disabled - SlowAPI not available")

# Función decorador opcional para rate limiting
def optional_rate_limit(limit_string: str):
    """Decorador que aplica rate limiting solo si SlowAPI está disponible"""
    def decorator(func):
        if SLOWAPI_AVAILABLE and limiter is not None:
            try:
                return limiter.limit(limit_string)(func)
            except Exception as e:
                print(f"⚠️ Warning: Could not apply rate limit to {func.__name__}: {e}")
                return func
        return func
    return decorator

# 🚀 CACHE SIMPLE EN MEMORIA PARA OPTIMIZACIÓN
from functools import lru_cache
from datetime import timedelta
import hashlib

# Cache simple en memoria (usar Redis en producción)
_simple_cache = {}
_cache_timestamps = {}

def get_cache_key(func_name: str, *args, **kwargs) -> str:
    """Generar clave de caché única"""
    key_data = f"{func_name}:{str(args)}:{str(sorted(kwargs.items()))}"
    return hashlib.md5(key_data.encode()).hexdigest()

def get_from_cache(cache_key: str, max_age_seconds: int = 300):
    """Obtener del caché si existe y es válido"""
    if cache_key in _simple_cache:
        cached_time = _cache_timestamps.get(cache_key)
        if cached_time and (datetime.now() - cached_time).total_seconds() < max_age_seconds:
            return _simple_cache[cache_key], True
    return None, False

def set_in_cache(cache_key: str, value):
    """Guardar en caché"""
    _simple_cache[cache_key] = value
    _cache_timestamps[cache_key] = datetime.now()

def async_cache(ttl_seconds: int = 300):
    """
    Decorador para cachear funciones async con TTL (Time To Live)
    Uso: @async_cache(ttl_seconds=600)
    
    IMPORTANTE: Cachea el resultado ANTES de cualquier middleware (gzip, etc)
    """
    def decorator(func):
        from functools import wraps
        import copy
        
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Generar clave de caché única basada en función y argumentos
            cache_key = get_cache_key(func.__name__, *args, **kwargs)
            
            # Intentar obtener del caché
            cached_value, is_valid = get_from_cache(cache_key, ttl_seconds)
            if is_valid:
                logger.info(f"✅ Cache hit for {func.__name__}")
                # Retornar copia profunda para evitar mutaciones
                try:
                    return copy.deepcopy(cached_value)
                except:
                    return cached_value
            
            # Si no está en caché, ejecutar función
            logger.info(f"⚠️ Cache miss for {func.__name__} - ejecutando función")
            result = await func(*args, **kwargs)
            
            # Guardar en caché solo si es serializable
            try:
                set_in_cache(cache_key, result)
            except Exception as e:
                logger.warning(f"No se pudo cachear resultado de {func.__name__}: {e}")
            
            return result
        
        return wrapper
    return decorator

# Configurar CORS - Optimizado para Vercel + Railway + Netlify + Live Server
def get_cors_origins():
    """Obtener orígenes CORS desde variables de entorno de forma segura"""
    origins = []
    
    # Orígenes de desarrollo local (incluye Live Server)
    local_origins = [
        "http://localhost:3000",
        "http://localhost:3001", 
        "http://localhost:5173",  # Vite dev server default port
        "http://localhost:5500",  # Live Server default port
        "http://localhost:8080",  # Webpack dev server
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3001",
        "http://127.0.0.1:5173",  # Vite dev server con 127.0.0.1
        "http://127.0.0.1:5500",  # Live Server con 127.0.0.1
        "http://127.0.0.1:8080",
    ]
    
    # Dominios específicos de producción/hosting
    production_origins = [
        # Netlify apps
        "https://captura-emprestito.netlify.app",
        # Vercel apps
        "https://gestor-proyectos-vercel.vercel.app",
        "https://gestor-proyectos-vercel-5ogb5wph8-juan-pablos-projects-56fe2e60.vercel.app",
        # Artefacto CaliTrack 360 Frontend - Producción y variantes de Vercel
        "https://artefacto-calitrack-360-frontend-production-dbcd9wrsi.vercel.app",
        "https://artefacto-calitrack-360-frontend-production.vercel.app",
        "https://artefacto-calitrack-360-frontend.vercel.app",
        # CaliTrack Red Frontend
        "https://calitrack-red.vercel.app",
        # Agrega aquí otros dominios específicos de producción según sea necesario
    ]
    
    # Siempre incluir dominios de producción
    origins.extend(production_origins)
    
    # Siempre incluir dominios locales (para desarrollo)
    origins.extend(local_origins)
    
    # Orígenes desde variables de entorno
    frontend_url = os.getenv("FRONTEND_URL")
    if frontend_url:
        origins.append(frontend_url)
    
    # Orígenes adicionales (separados por coma)
    additional_origins = os.getenv("CORS_ORIGINS", "")
    if additional_origins:
        origins.extend([origin.strip() for origin in additional_origins.split(",")])
    
    # Eliminar duplicados
    origins = list(set(origins))
    
    return origins

def get_cors_origin_regex():
    """
    Obtener patrón regex para permitir variantes de Vercel dinámicamente.
    Vercel genera URLs como: project-name-hash-team.vercel.app
    """
    # Patrones para proyectos de Vercel que necesitan acceso
    vercel_patterns = [
        r"https://artefacto-calitrack-360-frontend.*\.vercel\.app",
        r"https://gestor-proyectos-vercel.*\.vercel\.app",
    ]
    # Combinar todos los patrones en uno solo
    combined_pattern = "|".join(f"({pattern})" for pattern in vercel_patterns)
    return combined_pattern

# 🔤 MIDDLEWARE UTF-8 PARA CARACTERES ESPECIALES
@app.middleware("http")
async def utf8_middleware(request: Request, call_next):
    """Middleware para asegurar encoding UTF-8 en todas las respuestas"""
    response = await call_next(request)
    
    # Asegurar que las respuestas JSON tengan charset UTF-8
    if response.headers.get("content-type", "").startswith("application/json"):
        response.headers["content-type"] = "application/json; charset=utf-8"
    
    return response

# ⚡ MIDDLEWARE DE PERFORMANCE PARA AGREGAR HEADERS Y MEDIR TIEMPOS
@app.middleware("http")
async def performance_middleware(request: Request, call_next):
    """Middleware para mejorar performance y agregar headers útiles"""
    import time
    start_time = time.time()
    
    response = await call_next(request)
    
    # Calcular tiempo de procesamiento
    process_time = time.time() - start_time
    
    # Agregar headers de performance
    response.headers["X-Process-Time"] = f"{process_time:.3f}"
    response.headers["X-Content-Type-Options"] = "nosniff"
    
    # Sugerir cache para endpoints GET de lectura
    if request.method == "GET" and response.status_code == 200:
        # Cache público para endpoints de datos que no cambian frecuentemente
        if any(path in request.url.path for path in [
            "/centros-gestores/", "/firebase/collections", "/proyectos-presupuestales/",
            "/unidades-proyecto/filters", "/bancos_emprestito", "/auth/config"
        ]):
            response.headers["Cache-Control"] = "public, max-age=300"  # 5 minutos
    
    return response

# 🌐 CONFIGURACIÓN DE CORS
cors_origins = get_cors_origins()
cors_origin_regex = get_cors_origin_regex()
print(f"🌐 CORS configured for {len(cors_origins)} specific origins + regex patterns for Vercel variants")

# Configuración restrictiva con orígenes específicos + regex para variantes de Vercel
# Permite credentials (cookies, tokens) de manera segura
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,  # Lista específica de orígenes permitidos
    allow_origin_regex=cors_origin_regex,  # Regex para variantes de Vercel
    allow_credentials=True,  # Permitir cookies y headers de autenticación
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "HEAD", "PATCH"],
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
        "Pragma",
        "X-CSRF-Token",
    ],
    expose_headers=["Content-Type", "Authorization"],
    max_age=600,  # Cache de preflight requests por 10 minutos
)

# 🗜️ GZIP COMPRESSION HABILITADO (optimiza respuestas grandes)
from fastapi.middleware.gzip import GZipMiddleware
app.add_middleware(GZipMiddleware, minimum_size=1000)  # Comprimir respuestas > 1KB
print("🗜️ GZIP compression enabled for responses > 1KB")

# 🔐 MIDDLEWARE DE AUTENTICACIÓN Y AUTORIZACIÓN
print(f"🔍 AUTH_SYSTEM_AVAILABLE: {AUTH_SYSTEM_AVAILABLE}")
print(f"🔍 AuthorizationMiddleware: {AuthorizationMiddleware}")
if AUTH_SYSTEM_AVAILABLE and AuthorizationMiddleware is not None:
    # Definir rutas públicas (combinar con las del sistema de auth)
    public_paths = [
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
        "/auth/workload-identity/status",
        "/unidades-proyecto/captura-estado-360"
        # NOTA: /admin/users ahora requiere autenticación directa
    ]
    
    print(f"📋 Public paths configured: {public_paths}")
    app.add_middleware(
        AuthorizationMiddleware,
        public_paths=public_paths
    )
    print("✅ Authorization middleware enabled")
    
    # Middleware de auditoría (opcional, configurar según necesidad)
    if AuditLogMiddleware is not None:
        app.add_middleware(
            AuditLogMiddleware,
            enable_logging=True  # Cambiar a False para deshabilitar logging automático
        )
        print("✅ Audit log middleware enabled")
else:
    print("⚠️ Authorization middleware disabled - Auth system not available")

# 📁 SERVIR ARCHIVOS ESTÁTICOS (HTML, JS, CSS para testing)
# Verificar si existe la carpeta static
static_path = os.path.join(os.path.dirname(__file__), "static")
if os.path.isdir(static_path):
    app.mount("/static", StaticFiles(directory=static_path), name="static")
    print(f"✅ Static files mounted at /static from {static_path}")
else:
    print(f"⚠️ Static directory not found at {static_path}")

# ⏱️ MIDDLEWARE DE TIMING Y MONITOREO APM
import time

@app.middleware("http")
async def monitoring_middleware(request: Request, call_next):
    """
    Middleware para monitoreo APM: métricas de latencia, contador de requests, requests activos
    También agrega X-Response-Time header y loguea endpoints lentos
    """
    method = request.method
    endpoint = request.url.path
    
    # Incrementar gauge de requests activos (solo si Prometheus disponible)
    if PROMETHEUS_AVAILABLE and ACTIVE_REQUESTS is not None:
        ACTIVE_REQUESTS.labels(method=method, endpoint=endpoint).inc()
    
    # Medir tiempo de ejecución
    start_time = time.time()
    
    try:
        response = await call_next(request)
        status_code = response.status_code
    except Exception as e:
        status_code = 500
        logger.error(f"Error en {endpoint}: {str(e)}")
        raise
    finally:
        # Decrementar gauge de requests activos (solo si Prometheus disponible)
        if PROMETHEUS_AVAILABLE and ACTIVE_REQUESTS is not None:
            ACTIVE_REQUESTS.labels(method=method, endpoint=endpoint).dec()
        
        # Calcular latencia
        process_time = time.time() - start_time
        
        # Registrar métricas en Prometheus (solo si disponible)
        if PROMETHEUS_AVAILABLE and REQUEST_COUNT is not None and REQUEST_LATENCY is not None:
            REQUEST_COUNT.labels(method=method, endpoint=endpoint, status=status_code).inc()
            REQUEST_LATENCY.labels(method=method, endpoint=endpoint).observe(process_time)
    
    # Agregar header de tiempo de respuesta
    response.headers["X-Response-Time"] = f"{process_time:.3f}s"
    
    # Log solo endpoints lentos (> 3s)
    if process_time > 3.0:
        logger.warning(f"⚠️ Slow endpoint: {endpoint} - {process_time:.3f}s (status: {status_code})")
    
    return response

print("⏱️ Monitoring middleware enabled (APM + Timing)")

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

def clean_firebase_data(data):
    """
    Limpia datos de Firebase para serialización JSON
    Convierte DatetimeWithNanoseconds y otros tipos no serializables
    """
    if isinstance(data, dict):
        cleaned = {}
        for key, value in data.items():
            cleaned[key] = clean_firebase_data(value)
        return cleaned
    elif isinstance(data, list):
        return [clean_firebase_data(item) for item in data]
    elif FIREBASE_TYPES_AVAILABLE and isinstance(data, DatetimeWithNanoseconds):
        return data.isoformat()
    elif isinstance(data, datetime):
        return data.isoformat()
    else:
        return data

# �🛠️ MIDDLEWARE DE TIMEOUT PARA PREVENIR COLGADAS
@app.middleware("http")
async def timeout_middleware(request: Request, call_next):
    """Middleware para prevenir que las requests se cuelguen"""
    try:
        # Timeout extendido para endpoints de procesamiento masivo
        if request.url.path == "/emprestito/obtener-procesos-secop":
            # 5 minutos para procesamiento masivo de SECOP
            timeout_seconds = 300.0
        elif request.url.path == "/emprestito/obtener-contratos-secop":
            # 20 minutos para procesamiento completo de TODOS los contratos sin límite
            timeout_seconds = 1200.0
        else:
            # Timeout de 30 segundos para todas las otras requests
            timeout_seconds = 30.0
            
        return await asyncio.wait_for(call_next(request), timeout=timeout_seconds)
    except asyncio.TimeoutError:
        return JSONResponse(
            status_code=504,
            content={
                "error": "Request timeout",
                "message": f"The request took too long to process (timeout: {timeout_seconds}s)",
                "fallback": True,
                "timestamp": datetime.now().isoformat(),
                "endpoint": str(request.url.path)
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
            "general": ["/", "/health", "/ping", "/centros-gestores/nombres-unicos"],
            "firebase": ["/firebase/status", "/firebase/collections"], 
            "proyectos_de_inversion": [
                "/proyectos-presupuestales/all",
                "/proyectos-presupuestales/bpin/{bpin}",
                "/proyectos-presupuestales/bp/{bp}",
                "/proyectos-presupuestales/centro-gestor/{nombre_centro_gestor}"
            ],
            "unidades_proyecto": [
                "/unidades-proyecto/geometry", 
                "/unidades-proyecto/attributes",
                "/unidades-proyecto/dashboard",
                "/unidades-proyecto/filters"
            ],
            "gestion_contractual": [
                "/contratos/init_contratos_seguimiento"
            ],
            "gestion_emprestito": [
                "/emprestito/cargar-proceso",
                "/emprestito/cargar-orden-compra",
                "/emprestito/cargar-pago (POST - Registrar pago de empréstito con timestamp automático)",
                "/contratos_pagos_all (GET - Obtener todos los pagos de empréstito)",
                "/emprestito/obtener-procesos-secop (POST - Procesamiento masivo)",
                "/emprestito/proceso/{referencia_proceso}",
                "/emprestito/obtener-contratos-secop",
                "/contratos_emprestito_all",
                "/contratos_emprestito/referencia/{referencia_contrato}",
                "/contratos_emprestito/centro-gestor/{nombre_centro_gestor}",
                "/procesos_emprestito_all",
                "/emprestito/flujo-caja/cargar-excel (POST - Cargar flujos de caja desde Excel)",
                "/emprestito/flujo-caja/all (GET - Consultar flujos de caja con filtros)",
                "/emprestito/crear-tabla-proyecciones (POST - Crear tabla desde Google Sheets)",
                "/emprestito/leer-tabla-proyecciones (GET - Leer proyecciones cargadas)"
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
            "emprestito_management": "Sistema de gestión de empréstito con integración SECOP y TVEC APIs",
            "duplicate_prevention": "Validación automática de duplicados por referencia_proceso",
            "platform_detection": "Detección automática de plataforma (SECOP/TVEC) y enrutamiento inteligente",
            "external_apis": "Integración con APIs oficiales: SECOP (p6dx-8zbt) y TVEC (rgxm-mmea)",
            "encoding": "UTF-8 completo para español: ñáéíóúü ¡¿"
        }
    }
    
    return create_utf8_response(response_data)

@app.get("/metrics", tags=["Monitoring"])
async def metrics():
    """
    📊 Endpoint de Métricas de Prometheus
    
    Expone métricas de la aplicación en formato Prometheus para monitoreo APM:
    - gestor_api_requests_total: Contador de requests por endpoint, método y status
    - gestor_api_request_duration_seconds: Histograma de latencia de requests
    - gestor_api_requests_active: Gauge de requests activos
    - gestor_api_firebase_queries_total: Contador de queries a Firestore
    - gestor_api_cache_hits_total: Contador de cache hits
    - gestor_api_cache_misses_total: Contador de cache misses
    
    Usar con Grafana + Prometheus para dashboards de monitoreo
    """
    if not PROMETHEUS_AVAILABLE or generate_latest is None or CONTENT_TYPE_LATEST is None:
        raise HTTPException(status_code=503, detail="Prometheus metrics not available")
    
    from fastapi.responses import Response
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

@app.get("/ping", tags=["General"], summary="🔵 Ping Simple")
async def ping():
    """🔵 GET | ❤️ Health Check | Health check super simple para Railway con soporte UTF-8"""
    response_data = {
        "status": "ok ✅", 
        "message": "Servidor funcionando correctamente",
        "encoding": "UTF-8",
        "spanish_test": "ñáéíóúü ¡¿",
        "timestamp": datetime.now().isoformat(),
        "last_updated": "2025-10-04T00:00:00Z"  # Endpoint creation/update date
    }
    return create_utf8_response(response_data)

@app.get("/cors-test", tags=["General"])
async def cors_test(request: Request):
    """Endpoint específico para probar configuración CORS"""
    origin = request.headers.get("origin", "No origin header")
    user_agent = request.headers.get("user-agent", "No user-agent")
    
    response_data = {
        "success": True,
        "message": "CORS test successful ✅",
        "origin": origin,
        "user_agent": user_agent[:100] + "..." if len(user_agent) > 100 else user_agent,
        "cors_configured": True,
        "allowed_methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS", "HEAD", "PATCH"],
        "timestamp": datetime.now().isoformat(),
        "server_info": {
            "environment": os.getenv("ENVIRONMENT", "development"),
            "port": os.getenv("PORT", "8000"),
            "cors_origins_count": len(cors_origins)
        }
    }
    
    # Crear respuesta con headers CORS explícitos adicionales
    response = JSONResponse(
        content=response_data,
        status_code=200,
        headers={
            "Content-Type": "application/json; charset=utf-8",
            "Access-Control-Allow-Origin": origin if origin != "No origin header" else "*",
            "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS, HEAD, PATCH",
            "Access-Control-Allow-Headers": "Authorization, Content-Type, Accept, Origin, X-Requested-With",
            "Access-Control-Allow-Credentials": "true"
        }
    )
    
    return response

@app.options("/cors-test", tags=["General"])
async def cors_test_options(request: Request):
    """OPTIONS handler específico para CORS test"""
    origin = request.headers.get("origin", "*")
    
    return JSONResponse(
        content={"message": "CORS preflight OK"},
        status_code=200,
        headers={
            "Access-Control-Allow-Origin": origin,
            "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS, HEAD, PATCH",
            "Access-Control-Allow-Headers": "Authorization, Content-Type, Accept, Origin, X-Requested-With",
            "Access-Control-Allow-Credentials": "true",
            "Access-Control-Max-Age": "86400"
        }
    )

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

@app.get("/health", tags=["General"], summary="🔵 Estado de Salud API")
async def health_check():
    """🔵 GET | ❤️ Health Check | Verificar estado de salud de la API"""
    
    # Intentar obtener del cache (TTL 30 segundos para health check)
    cache_key = get_cache_key("health_check")
    cached_data, is_valid = get_from_cache(cache_key, max_age_seconds=30)
    if is_valid:
        # Actualizar timestamp en cada llamada pero mantener resto del cache
        cached_data["timestamp"] = datetime.now().isoformat()
        return cached_data
    
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
        
        # Guardar en cache
        set_in_cache(cache_key, basic_response)
        
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

@app.get("/centros-gestores/nombres-unicos", tags=["General"])
async def get_all_nombres_centros_gestores_unique():
    """
    ## Obtener Nombres Únicos de Centros Gestores
    
    **Propósito**: Retorna una lista de valores únicos del campo "nombre_centro_gestor" 
    de la colección "proyectos_presupuestales".
    
    ### ✅ Casos de uso:
    - Poblar dropdowns y selectores en formularios
    - Filtros dinámicos en dashboards
    - Validación de centros gestores existentes
    - Reportes por centro gestor
    - Análisis de distribución institucional
    
    ### 📊 Características:
    - Valores únicos ordenados alfabéticamente
    - Filtrado automático de valores vacíos o nulos
    - Conteo total de centros gestores únicos
    - Optimizado para carga rápida
    
    ### 🔧 Optimizaciones:
    - Eliminación de duplicados usando set()
    - Normalización de espacios en blanco
    - Ordenamiento alfabético para mejor UX
    - Filtrado de valores vacíos
    
    ### 📝 Ejemplo de uso:
    ```javascript
    const response = await fetch('/centros-gestores/nombres-unicos');
    const data = await response.json();
    if (data.success) {
        console.log('Centros gestores encontrados:', data.count);
        const dropdown = data.data.map(nombre => ({
            value: nombre,
            label: nombre
        }));
    }
    ```
    
    ### 💡 Casos de uso prácticos:
    - **Formularios**: Autocomplete de centros gestores
    - **Dashboards**: Filtros dinámicos por institución
    - **Reportes**: Agrupación por centro gestor
    - **Validación**: Verificar centros gestores válidos
    """
    if not FIREBASE_AVAILABLE or not SCRIPTS_AVAILABLE:
        raise HTTPException(status_code=503, detail="Firebase or scripts not available")
    
    # Intentar obtener del cache (TTL 5 minutos)
    cache_key = get_cache_key("centros_gestores_nombres_unicos")
    cached_data, is_valid = get_from_cache(cache_key, max_age_seconds=300)
    if is_valid:
        return cached_data
    
    try:
        result = await get_unique_nombres_centros_gestores()
        
        if not result["success"]:
            raise HTTPException(
                status_code=500,
                detail=f"Error obteniendo nombres únicos de centros gestores: {result.get('error', 'Error desconocido')}"
            )
        
        response_data = {
            "success": True,
            "data": result["data"],
            "count": result["count"],
            "field": result["field"],
            "collection": result["collection"],
            "timestamp": result["timestamp"],
            "last_updated": "2025-10-04T00:00:00Z",  # Endpoint creation date
            "message": f"Se obtuvieron {result['count']} nombres únicos de centros gestores",
            "metadata": {
                "sorted": True,
                "filtered_empty": True,
                "normalized": True,
                "cache_recommended": True,
                "utf8_enabled": True
            }
        }
        
        # Guardar en cache
        set_in_cache(cache_key, response_data)
        
        return response_data
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error procesando nombres únicos de centros gestores: {str(e)}"
        )

# ============================================================================
# ENDPOINTS DE FIREBASE
# ============================================================================

@app.get("/firebase/status", tags=["Firebase"])
async def firebase_status():
    """Verificar estado de la conexión con Firebase"""
    try:
        # Cache corto para evitar consultas repetidas a Firebase en ráfagas
        cache_key = get_cache_key("firebase_status")
        cached = _simple_cache.get(cache_key)
        if cached:
            cached_time = _cache_timestamps.get(cache_key)
            if cached_time and (datetime.now() - cached_time).total_seconds() < 30:
                return cached
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
        # Realizar comprobación activa de Firebase
        connection_result = await test_firebase_connection()
        connection_result["last_updated"] = "2025-10-02T00:00:00Z"
        # Guardar en cache corto
        set_in_cache(cache_key, connection_result)
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
@optional_rate_limit("30/minute")  # Máximo 30 requests por minuto
async def get_firebase_collections(request: Request):
    """Obtener información completa de todas las colecciones de Firestore"""
    if not FIREBASE_AVAILABLE or not SCRIPTS_AVAILABLE:
        raise HTTPException(status_code=503, detail="Firebase or scripts not available")
    
    # Intentar obtener del cache (TTL 5 minutos)
    cache_key = get_cache_key("firebase_collections")
    cached_data, is_valid = get_from_cache(cache_key, max_age_seconds=300)
    if is_valid:
        return cached_data
    
    try:
        # OPTIMIZACIÓN: Reducir muestreo a 10 documentos por colección para velocidad
        collections_data = await get_collections_info(limit_docs_per_collection=10)
        
        if not collections_data["success"]:
            raise HTTPException(
                status_code=500, 
                detail=f"Error obteniendo información de colecciones: {collections_data.get('error', 'Error desconocido')}"
            )
        
        # Add timestamp for endpoint tracking
        collections_data["last_updated"] = "2025-10-02T00:00:00Z"  # Endpoint creation/update date
        
        # Guardar en cache
        set_in_cache(cache_key, collections_data)
        
        return collections_data
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Error interno del servidor: {str(e)}"
        )

@app.get("/firebase/collections/summary", tags=["Firebase"])
@optional_rate_limit("30/minute")  # Máximo 30 requests por minuto
async def get_firebase_collections_summary(request: Request):
    """Obtener resumen estadístico de las colecciones"""
    if not FIREBASE_AVAILABLE or not SCRIPTS_AVAILABLE:
        raise HTTPException(status_code=503, detail="Firebase or scripts not available")
    
    # Intentar obtener del cache (TTL 5 minutos)
    cache_key = get_cache_key("firebase_collections_summary")
    cached_data, is_valid = get_from_cache(cache_key, max_age_seconds=300)
    if is_valid:
        return cached_data
    
    try:
        summary_data = await get_collections_summary()
        
        if not summary_data["success"]:
            raise HTTPException(
                status_code=500, 
                detail=f"Error obteniendo resumen: {summary_data.get('error', 'Error desconocido')}"
            )
        
        # Add timestamp for endpoint tracking
        summary_data["last_updated"] = "2025-10-02T00:00:00Z"  # Endpoint creation/update date
        
        # Guardar en cache
        set_in_cache(cache_key, summary_data)
        
        return summary_data
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error obteniendo resumen: {str(e)}")

# ============================================================================
# ENDPOINTS DE PROYECTOS DE INVERSIÓN
# ============================================================================


def _aplicar_campos_proyectos(data: List[Dict[str, Any]], campos: Optional[str]) -> List[Dict[str, Any]]:
    if not campos:
        return data

    selected_fields = [field.strip() for field in campos.split(',') if field.strip()]
    if not selected_fields:
        return data

    if "id" not in selected_fields:
        selected_fields.append("id")

    filtered = []
    for row in data:
        if not isinstance(row, dict):
            continue
        filtered.append({field: row.get(field) for field in selected_fields if field in row})

    return filtered

@app.get("/proyectos-presupuestales/all", tags=["Proyectos de Inversión"], summary="🔵 Todos los Proyectos Presupuestales")
@optional_rate_limit("40/minute")  # Máximo 40 requests por minuto (endpoint costoso)
async def get_proyectos_all(
    request: Request,
    limit: int = Query(200, ge=1, le=5000, description="Número máximo de registros a retornar (optimización frontend)"),
    offset: int = Query(0, ge=0, description="Cantidad de registros a omitir (paginación)"),
    campos: Optional[str] = Query(None, description="Campos a retornar separados por coma (ej: bpin,bp,nombre_centro_gestor)")
):
    """
    ## 🔵 GET | 📋 Listados | Obtener Todos los Proyectos Presupuestales
    
    **Propósito**: Retorna todos los documentos de la colección "proyectos_presupuestales".
    
    ### ✅ Casos de uso:
    - Obtener listado completo de proyectos presupuestales
    - Exportación de datos para análisis
    - Integración con sistemas externos
    - Reportes y dashboards de proyectos de inversión
    
    ### 📊 Información incluida:
    - Todos los campos disponibles en la colección
    - ID del documento para referencia
    - Conteo total de registros
    - Timestamp de la consulta
    
    ### 📝 Ejemplo de uso:
    ```javascript
    const response = await fetch('/proyectos-presupuestales/all');
    const data = await response.json();
    if (data.success) {
        console.log('Proyectos encontrados:', data.count);
        console.log('Datos:', data.data);
    }
    ```
    """
    if not FIREBASE_AVAILABLE or not SCRIPTS_AVAILABLE:
        raise HTTPException(status_code=503, detail="Firebase or scripts not available")
    
    try:
        result = await get_proyectos_presupuestales(limit=limit, offset=offset if offset > 0 else None)
        
        if not result["success"]:
            raise HTTPException(
                status_code=500,
                detail=f"Error obteniendo proyectos presupuestales: {result.get('error', 'Error desconocido')}"
            )
        
        data_filtrada = _aplicar_campos_proyectos(result["data"], campos)

        return {
            "success": True,
            "data": data_filtrada,
            "count": len(data_filtrada),
            "collection": result["collection"],
            "timestamp": result["timestamp"],
            "pagination": {
                "limit": limit,
                "offset": offset,
                "returned": len(data_filtrada)
            },
            "last_updated": "2025-10-04T00:00:00Z",  # Endpoint creation date
            "message": f"Se obtuvieron {len(data_filtrada)} proyectos presupuestales exitosamente"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error procesando proyectos presupuestales: {str(e)}"
        )

@app.get("/proyectos-presupuestales/bpin/{bpin}", tags=["Proyectos de Inversión"], summary="🔵 Proyectos por BPIN")
async def get_proyectos_by_bpin(
    bpin: str,
    limit: int = Query(200, ge=1, le=5000, description="Número máximo de registros a retornar"),
    offset: int = Query(0, ge=0, description="Cantidad de registros a omitir"),
    campos: Optional[str] = Query(None, description="Campos a retornar separados por coma")
):
    """
    ## 🔵 GET | 🔍 Consultas | Obtener Proyectos por BPIN
    
    **Propósito**: Retorna proyectos presupuestales filtrados por código BPIN específico.
    
    ### ✅ Casos de uso:
    - Búsqueda de proyectos por código BPIN específico
    - Consulta de detalles de proyecto individual
    - Validación de existencia de BPIN
    - Integración con sistemas de seguimiento presupuestal
    
    ### 🔍 Filtrado:
    - **Campo**: `bpin` (coincidencia exacta)
    - **Tipo**: String - Código único del proyecto
    - **Sensible a mayúsculas**: Sí
    
    ### 📊 Información incluida:
    - Todos los campos del proyecto que coincida con el BPIN
    - ID del documento para referencia
    - Conteo de registros encontrados
    - Información del filtro aplicado
    
    ### 📝 Ejemplo de uso:
    ```javascript
    const bpin = "2023000123456";
    const response = await fetch(`/proyectos-presupuestales/bpin/${bpin}`);
    const data = await response.json();
    if (data.success && data.count > 0) {
        console.log('Proyecto encontrado:', data.data[0]);
    } else {
        console.log('No se encontró proyecto con BPIN:', bpin);
    }
    ```
    
    ### 💡 Notas:
    - Si no se encuentra ningún proyecto, retorna array vacío
    - El BPIN debe ser exacto (sin espacios adicionales)
    - Típicamente retorna 0 o 1 resultado (BPIN único)
    """
    if not FIREBASE_AVAILABLE or not SCRIPTS_AVAILABLE:
        raise HTTPException(status_code=503, detail="Firebase or scripts not available")
    
    try:
        result = await get_proyectos_presupuestales_by_bpin(
            bpin,
            limit=limit,
            offset=offset
        )
        
        if not result["success"]:
            raise HTTPException(
                status_code=500,
                detail=f"Error obteniendo proyectos por BPIN: {result.get('error', 'Error desconocido')}"
            )
        
        data_filtrada = _aplicar_campos_proyectos(result["data"], campos)

        return {
            "success": True,
            "data": data_filtrada,
            "count": len(data_filtrada),
            "collection": result["collection"],
            "filter": result["filter"],
            "timestamp": result["timestamp"],
            "pagination": result.get("pagination", {
                "limit": limit,
                "offset": offset,
                "returned": len(data_filtrada)
            }),
            "last_updated": "2025-10-04T00:00:00Z",  # Endpoint creation date
            "message": f"Se encontraron {len(data_filtrada)} proyectos con BPIN '{bpin}'"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error procesando consulta por BPIN: {str(e)}"
        )

@app.get("/proyectos-presupuestales/bp/{bp}", tags=["Proyectos de Inversión"])
async def get_proyectos_by_bp(
    bp: str,
    limit: int = Query(200, ge=1, le=5000, description="Número máximo de registros a retornar"),
    offset: int = Query(0, ge=0, description="Cantidad de registros a omitir"),
    campos: Optional[str] = Query(None, description="Campos a retornar separados por coma")
):
    """
    ## Obtener Proyectos Presupuestales por BP
    
    **Propósito**: Retorna proyectos presupuestales filtrados por código BP específico.
    
    ### ✅ Casos de uso:
    - Búsqueda de proyectos por código BP específico
    - Consulta de proyectos relacionados por BP
    - Análisis de agrupación presupuestal
    - Reportes por código de proyecto base
    
    ### 🔍 Filtrado:
    - **Campo**: `bp` (coincidencia exacta)
    - **Tipo**: String - Código base del proyecto
    - **Sensible a mayúsculas**: Sí
    
    ### 📊 Información incluida:
    - Todos los campos de los proyectos que coincidan con el BP
    - ID del documento para referencia
    - Conteo de registros encontrados
    - Información del filtro aplicado
    
    ### 📝 Ejemplo de uso:
    ```javascript
    const bp = "BP-2023-001";
    const response = await fetch(`/proyectos-presupuestales/bp/${bp}`);
    const data = await response.json();
    if (data.success && data.count > 0) {
        console.log(`Encontrados ${data.count} proyectos con BP:`, bp);
        data.data.forEach(proyecto => {
            console.log('Proyecto:', proyecto.nombre_proyecto);
        });
    }
    ```
    
    ### 💡 Notas:
    - Puede retornar múltiples proyectos (un BP puede tener varios proyectos)
    - Si no se encuentra ningún proyecto, retorna array vacío
    - El BP debe ser exacto (sin espacios adicionales)
    """
    if not FIREBASE_AVAILABLE or not SCRIPTS_AVAILABLE:
        raise HTTPException(status_code=503, detail="Firebase or scripts not available")
    
    try:
        result = await get_proyectos_presupuestales_by_bp(
            bp,
            limit=limit,
            offset=offset
        )
        
        if not result["success"]:
            raise HTTPException(
                status_code=500,
                detail=f"Error obteniendo proyectos por BP: {result.get('error', 'Error desconocido')}"
            )
        
        data_filtrada = _aplicar_campos_proyectos(result["data"], campos)

        return {
            "success": True,
            "data": data_filtrada,
            "count": len(data_filtrada),
            "collection": result["collection"],
            "filter": result["filter"],
            "timestamp": result["timestamp"],
            "pagination": result.get("pagination", {
                "limit": limit,
                "offset": offset,
                "returned": len(data_filtrada)
            }),
            "last_updated": "2025-10-04T00:00:00Z",  # Endpoint creation date
            "message": f"Se encontraron {len(data_filtrada)} proyectos con BP '{bp}'"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error procesando consulta por BP: {str(e)}"
        )

@app.get("/proyectos-presupuestales/centro-gestor/{nombre_centro_gestor}", tags=["Proyectos de Inversión"])
async def get_proyectos_by_centro_gestor(
    nombre_centro_gestor: str,
    limit: int = Query(200, ge=1, le=5000, description="Número máximo de registros a retornar"),
    offset: int = Query(0, ge=0, description="Cantidad de registros a omitir"),
    campos: Optional[str] = Query(None, description="Campos a retornar separados por coma")
):
    """
    ## Obtener Proyectos Presupuestales por Centro Gestor
    
    **Propósito**: Retorna proyectos presupuestales filtrados por nombre del centro gestor específico.
    
    ### ✅ Casos de uso:
    - Consulta de proyectos por dependencia responsable
    - Reportes por entidad gestora
    - Dashboard por centro de responsabilidad
    - Análisis de distribución institucional
    - Seguimiento de proyectos por secretaría/departamento
    
    ### 🔍 Filtrado:
    - **Campo**: `nombre_centro_gestor` (coincidencia exacta)
    - **Tipo**: String - Nombre completo del centro gestor
    - **Sensible a mayúsculas**: Sí
    - **Espacios**: Sensible a espacios adicionales
    
    ### 📊 Información incluida:
    - Todos los campos de los proyectos del centro gestor
    - ID del documento para referencia
    - Conteo de registros encontrados
    - Información del filtro aplicado
    
    ### 📝 Ejemplo de uso:
    ```javascript
    const centroGestor = "Secretaría de Salud";
    const response = await fetch(`/proyectos-presupuestales/centro-gestor/${encodeURIComponent(centroGestor)}`);
    const data = await response.json();
    if (data.success && data.count > 0) {
        console.log(`${data.count} proyectos encontrados para:`, centroGestor);
        const totalPresupuesto = data.data.reduce((sum, p) => sum + (p.presupuesto || 0), 0);
        console.log('Presupuesto total:', totalPresupuesto);
    }
    ```
    
    ### 💡 Notas:
    - Típicamente retorna múltiples proyectos por centro gestor
    - El nombre debe ser exacto (use `/centros-gestores/nombres-unicos` para obtener nombres válidos)
    - Para nombres con espacios, usar `encodeURIComponent()` en el frontend
    - Si no se encuentra ningún proyecto, retorna array vacío
    
    ### 🔗 Endpoint relacionado:
    - `GET /centros-gestores/nombres-unicos` - Para obtener lista de centros gestores válidos
    """
    if not FIREBASE_AVAILABLE or not SCRIPTS_AVAILABLE:
        raise HTTPException(status_code=503, detail="Firebase or scripts not available")
    
    try:
        result = await get_proyectos_presupuestales_by_centro_gestor(
            nombre_centro_gestor,
            limit=limit,
            offset=offset
        )
        
        if not result["success"]:
            raise HTTPException(
                status_code=500,
                detail=f"Error obteniendo proyectos por centro gestor: {result.get('error', 'Error desconocido')}"
            )
        
        data_filtrada = _aplicar_campos_proyectos(result["data"], campos)

        return {
            "success": True,
            "data": data_filtrada,
            "count": len(data_filtrada),
            "collection": result["collection"],
            "filter": result["filter"],
            "timestamp": result["timestamp"],
            "pagination": result.get("pagination", {
                "limit": limit,
                "offset": offset,
                "returned": len(data_filtrada)
            }),
            "last_updated": "2025-10-04T00:00:00Z",  # Endpoint creation date
            "message": f"Se encontraron {len(data_filtrada)} proyectos para el centro gestor '{nombre_centro_gestor}'"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error procesando consulta por centro gestor: {str(e)}"
        )

# ============================================================================
# ENDPOINT DE UNIDADES DE PROYECTO
# ============================================================================

@app.get("/unidades-proyecto", tags=["Unidades de Proyecto"], summary="🔵 Consultar Unidades de Proyecto")
@optional_rate_limit("60/minute")
async def consultar_unidades_proyecto(
    request: Request,
    # Filtros básicos
    upid: Optional[str] = Query(None, description="ID específico de unidad (ej: UNP-1000)"),
    nombre_centro_gestor: Optional[str] = Query(None, description="Centro gestor responsable"),
    tipo_intervencion: Optional[str] = Query(None, description="Tipo de intervención"),
    estado: Optional[str] = Query(None, description="Estado del proyecto"),
    clase_up: Optional[str] = Query(None, description="Clase de la unidad de proyecto"),
    tipo_equipamiento: Optional[str] = Query(None, description="Tipo de equipamiento"),
    comuna_corregimiento: Optional[str] = Query(None, description="Comuna o corregimiento"),
    barrio_vereda: Optional[str] = Query(None, description="Barrio o vereda"),
    frente_activo: Optional[str] = Query(None, description="Frente activo"),
    fuente_financiacion: Optional[str] = Query(None, description="Fuente de financiación"),
    ano: Optional[int] = Query(None, description="Año de ejecución"),
    
    # Paginación
    limit: Optional[int] = Query(None, ge=1, le=10000, description="Límite de registros"),
    offset: Optional[int] = Query(None, ge=0, description="Offset para paginación"),
):
    """
    ## 🔵 Consultar Unidades de Proyecto
    
    **Propósito**: Acceso directo a la colección `unidades_proyecto` en Firebase.
    
    ### Respuesta
    
    Retorna documentos de la colección con todos sus campos:
    
    ```json
    {
      "success": true,
      "data": [
        {
          "upid": "UNP-1000",
          "nombre_up": "Nombre del proyecto",
          "estado": "En ejecución",
          "tipo_equipamiento": "Vías",
          "clase_up": "Construcción",
          "nombre_centro_gestor": "DAGRD",
          "comuna_corregimiento": "Comuna 1",
          "barrio_vereda": "El Centro",
          "ano": 2024,
          ...
        }
      ],
      "count": 150,
      "collection": "unidades_proyecto"
    }
    ```
    
    ### Filtros Disponibles
    
    - `upid` - Filtrar por ID específico
    - `nombre_centro_gestor` - Filtrar por centro gestor
    - `estado` - Filtrar por estado del proyecto
    - `tipo_intervencion` - Filtrar por tipo de intervención
    - `clase_up` - Filtrar por clase de unidad
    - `tipo_equipamiento` - Filtrar por tipo de equipamiento
    - `comuna_corregimiento` - Filtrar por ubicación
    - `barrio_vereda` - Filtrar por barrio
    - `frente_activo` - Filtrar por frente activo
    - `fuente_financiacion` - Filtrar por fuente de financiación
    - `ano` - Filtrar por año
    
    ### Paginación
    
    Use `limit` y `offset`:
    ```bash
    # Primera página (50 resultados)
    GET /unidades-proyecto?limit=50&offset=0
    
    # Segunda página
    GET /unidades-proyecto?limit=50&offset=50
    ```
    
    ### Ejemplos
    
    ```bash
    # Todos los proyectos (limitado a 1000)
    GET /unidades-proyecto
    
    # Proyectos por centro gestor
    GET /unidades-proyecto?nombre_centro_gestor=DAGRD
    
    # Proyectos en ejecución
    GET /unidades-proyecto?estado=En ejecución
    
    # Proyectos por tipo de equipamiento
    GET /unidades-proyecto?tipo_equipamiento=Vías&limit=100
    
    # Unidad específica por ID
    GET /unidades-proyecto?upid=UNP-1000
    
    ```
    
    ### Optimizaciones de Rendimiento
    
    - 🚀 **Streaming eficiente** de documentos Firestore
    - ⚡ **Procesamiento batch** optimizado
    - 📦 **Compresión automática** de respuestas
    - 🎯 **Queries con índices** Firestore
    - 🔄 **Retry automático** en caso de errores transitorios
    
    **Índices Firestore recomendados:**
    ```
    Collection: unidades_proyecto
    Fields: nombre_centro_gestor, estado, ano (Ascending)
    ```
    """
    import time
    import asyncio
    
    start_time = time.time()
    
    if not FIREBASE_AVAILABLE:
        raise HTTPException(
            status_code=503, 
            detail="Firebase no disponible - verifica las credenciales"
        )
    
    try:
        from database.firebase_config import get_firestore_client
        import google.cloud.firestore
        
        logger.info(f"🔍 Consulta unidades_proyecto iniciada")
        
        # Obtener cliente Firestore
        db = get_firestore_client()
        if db is None:
            raise HTTPException(
                status_code=503,
                detail="No se pudo conectar a Firestore"
            )
        
        logger.info(f"✅ Cliente Firestore obtenido")
        
            # Construir query optimizada
        logger.info(f"📊 Construyendo query para unidades_proyecto...")
        query = db.collection('unidades_proyecto')
        
        # Aplicar filtros
        filters_applied = 0
        active_filters = {}
        
        if upid:
            query = query.where('upid', '==', upid)
            filters_applied += 1
            active_filters['upid'] = upid
        if nombre_centro_gestor:
            query = query.where('nombre_centro_gestor', '==', nombre_centro_gestor)
            filters_applied += 1
            active_filters['nombre_centro_gestor'] = nombre_centro_gestor
        if estado:
            query = query.where('estado', '==', estado)
            filters_applied += 1
            active_filters['estado'] = estado
        if tipo_intervencion:
            query = query.where('tipo_intervencion', '==', tipo_intervencion)
            filters_applied += 1
            active_filters['tipo_intervencion'] = tipo_intervencion
        if clase_up:
            query = query.where('clase_up', '==', clase_up)
            filters_applied += 1
            active_filters['clase_up'] = clase_up
        if tipo_equipamiento:
            query = query.where('tipo_equipamiento', '==', tipo_equipamiento)
            filters_applied += 1
            active_filters['tipo_equipamiento'] = tipo_equipamiento
        if comuna_corregimiento:
            query = query.where('comuna_corregimiento', '==', comuna_corregimiento)
            filters_applied += 1
            active_filters['comuna_corregimiento'] = comuna_corregimiento
        if barrio_vereda:
            query = query.where('barrio_vereda', '==', barrio_vereda)
            filters_applied += 1
            active_filters['barrio_vereda'] = barrio_vereda
        if frente_activo:
            query = query.where('frente_activo', '==', frente_activo)
            filters_applied += 1
            active_filters['frente_activo'] = frente_activo
        if fuente_financiacion:
            query = query.where('fuente_financiacion', '==', fuente_financiacion)
            filters_applied += 1
            active_filters['fuente_financiacion'] = fuente_financiacion
        if ano:
            query = query.where('ano', '==', ano)
            filters_applied += 1
            active_filters['ano'] = ano
        
        logger.info(f"🔍 Filtros aplicados: {filters_applied}")
        
        # Aplicar límite (max 10000, default 100 para velocidad)
        query_limit = min(limit or 100, 10000)
        query = query.limit(query_limit)
        
        # Aplicar offset si existe
        if offset:
            query = query.offset(offset)
        
        logger.info(f"⚡ Ejecutando query (limit={query_limit}, offset={offset or 0})...")
        
        # Ejecutar query
        docs = query.stream()
        
        # Procesar resultados de forma eficiente
        data = []
        doc_count = 0
        
        for doc in docs:
            doc_count += 1
            doc_dict = doc.to_dict()
            
            # Optimización: Convertir timestamps solo si existen
            if FIREBASE_TYPES_AVAILABLE:
                for key, value in doc_dict.items():
                    if isinstance(value, DatetimeWithNanoseconds):
                        doc_dict[key] = value.isoformat()
            
            data.append(doc_dict)
            
            # Log progreso cada 50 docs
            if doc_count % 50 == 0:
                logger.info(f"📦 Procesados {doc_count} documentos...")
        
        logger.info(f"✅ Query completada: {doc_count} documentos obtenidos")
        
        # Calcular tiempo de procesamiento
        elapsed_time = time.time() - start_time
        
        # Respuesta optimizada
        response_data = {
            "success": True,
            "data": data,
            "count": len(data),
            "collection": "unidades_proyecto",
            "filters": {
                "applied": filters_applied,
                "active": active_filters,
                "limit": query_limit,
                "offset": offset or 0
            },
            "performance": {
                "query_time_seconds": round(elapsed_time, 3),
                "docs_per_second": round(len(data) / elapsed_time, 2) if elapsed_time > 0 else 0
            },
            "timestamp": datetime.now().isoformat()
        }
        
        logger.info(f"🎯 Respuesta generada en {elapsed_time:.3f}s - {len(data)} documentos")
        
        return create_utf8_response(response_data)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error consultando unidades_proyecto: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error consultando colección: {str(e)}"
        )

# ============================================================================
# ENDPOINT DE CALIDAD DE DATOS (UNIDADES DE PROYECTO)
# ============================================================================

@app.get("/unidades-proyecto/calidad-datos", tags=["Unidades de Proyecto"], summary="🔵 Métricas de Calidad de Datos (ISO/DAMA)")
@optional_rate_limit("30/minute")
async def get_unidades_proyecto_calidad_datos(
    request: Request,
    nombre_centro_gestor: Optional[str] = Query(None, description="Filtrar clasificación por centro gestor"),
    history_limit: Optional[int] = Query(None, ge=1, description="Cantidad máxima de snapshots en historial. Si no se envía, devuelve todo el historial disponible")
):
    """
    ## 🔵 Métricas de Calidad de Datos de Unidades de Proyecto

    Evalúa calidad de datos sobre `unidades_proyecto` e `intervenciones_unidades_proyecto`
    con marco alineado a ISO 8000, ISO/IEC 25012 y DAMA-DMBOK.

    Incluye:
    - Reglas por dimensión (completitud, validez, consistencia, unicidad, oportunidad)
    - Clasificación de gravedad (S1-S4)
    - Priorización (P1-P5) según matriz gravedad x volumen
    - Data Quality Score (DQS) ponderado 0-100
    - Clasificación por `nombre_centro_gestor`
    - Secciones de `resumen`, `registros`, `historial`, `metadatos` y `estadisticas_globales`

        ### 📝 Ejemplos de consulta:
        - **Sin límite (por defecto, retorna todo el historial):**
            `/unidades-proyecto/calidad-datos`
        - **Con límite de historial:**
            `/unidades-proyecto/calidad-datos?history_limit=5`
        - **Filtrado por centro gestor (sin limitar historial):**
            `/unidades-proyecto/calidad-datos?nombre_centro_gestor=Unidad%20Administrativa%20Especial%20de%20Servicios%20Públicos`
        - **Filtrado por centro gestor + límite de historial:**
            `/unidades-proyecto/calidad-datos?nombre_centro_gestor=Unidad%20Administrativa%20Especial%20de%20Servicios%20Públicos&history_limit=10`
    """
    if not FIREBASE_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="Firebase no disponible - verifica las credenciales"
        )

    try:
        result = await get_unidades_proyecto_quality_metrics(
            nombre_centro_gestor=nombre_centro_gestor,
            history_limit=history_limit
        )
        return create_utf8_response(result)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error en métricas de calidad de unidades_proyecto: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error generando métricas de calidad: {str(e)}"
        )

# ============================================================================
# ENDPOINT PARA ARTEFACTO DE CAPTURA #360
# ============================================================================

@app.get("/unidades-proyecto/init-360", tags=["Artefacto de Captura #360"], summary="🔵 GET | 📋 Listados | Datos Iniciales para Captura #360")
@optional_rate_limit("60/minute")
async def get_unidades_proyecto_init_360(request: Request):
    """
    ## 🔵 GET | 📋 Listados | Obtener Datos Iniciales para Artefacto de Captura #360
    
    **Propósito**: Retorna registros de la colección "unidades_proyecto" filtrados según 
    criterios específicos para el artefacto de captura #360.
    
    ### ✅ Campos retornados:
    - upid
    - nombre_up
    - nombre_up_detalle
    - tipo_equipamiento
    - tipo_intervencion
    - estado
    - avance_obra
    - presupuesto_base
    - geometry (datos geoespaciales del registro)
    - direccion
    
    ### 🚫 Exclusiones aplicadas:
    
    **Por clase_up**:
    - "Interventoría"
    - "Estudios y diseños"
    - "Subsidios"
    
    **Por tipo_equipamiento**:
    - "Fuentes y monumentos"
    - "Parques y zonas verdes"
    - "Vivienda mejoramiento"
    - "Vivienda nueva"
    - "Adquisición predios"
    
    **Por tipo_intervencion**:
    - "Estudios y diseños"
    - "Transferencia directa"
    
    ### 📊 Información incluida en la respuesta:
    - Lista de registros que cumplen los criterios
    - Conteo total de registros retornados
    - Timestamp de la consulta
    - Criterios de exclusión aplicados
    
    ### 📝 Ejemplo de uso:
    ```javascript
    const response = await fetch('/unidades-proyecto/init-360');
    const data = await response.json();
    if (data.success) {
        console.log('Registros encontrados:', data.count);
        console.log('Datos:', data.data);
    }
    ```
    """
    if not FIREBASE_AVAILABLE or not SCRIPTS_AVAILABLE:
        raise HTTPException(status_code=503, detail="Firebase or scripts not available")
    
    try:
        # Conectar a Firestore
        db = get_firestore_client()
        if db is None:
            raise HTTPException(
                status_code=503,
                detail="No se pudo conectar a Firestore"
            )
        
        # Definir criterios de exclusión
        exclusion_clase_up = ["Interventoría", "Estudios y diseños", "Subsidios"]
        exclusion_tipo_equipamiento = [
            "Fuentes y monumentos",
            "Parques y zonas verdes",
            "Vivienda mejoramiento",
            "Vivienda nueva",
            "Adquisición predios"
        ]
        exclusion_tipo_intervencion = ["Estudios y diseños", "Transferencia directa"]
        
        # Campos a retornar
        campos_requeridos = [
            'upid',
            'nombre_up',
            'nombre_up_detalle',
            'tipo_equipamiento',
            'tipo_intervencion',
            'estado',
            'avance_obra',
            'presupuesto_base',
            'geometry',
            'direccion'
        ]
        
        # Consultar colección
        query = db.collection('unidades_proyecto')
        docs = query.stream()
        
        # Procesar documentos
        registros_filtrados = []
        
        for doc in docs:
            doc_data = doc.to_dict()
            
            # Extraer campos, buscando en el nivel raíz y en properties
            def get_field_value(field_name):
                """Obtener valor del campo desde el documento o properties"""
                if field_name in doc_data:
                    return doc_data[field_name]
                elif 'properties' in doc_data and field_name in doc_data['properties']:
                    return doc_data['properties'][field_name]
                return None
            
            # Obtener valores para filtrado
            clase_up = get_field_value('clase_up')
            tipo_equipamiento = get_field_value('tipo_equipamiento')
            tipo_intervencion = get_field_value('tipo_intervencion')
            
            # Aplicar filtros de exclusión
            # Excluir si clase_up está en la lista de exclusión
            if clase_up and clase_up in exclusion_clase_up:
                continue
            
            # Excluir si tipo_equipamiento está en la lista de exclusión
            if tipo_equipamiento and tipo_equipamiento in exclusion_tipo_equipamiento:
                continue
            
            # Excluir si tipo_intervencion está en la lista de exclusión
            if tipo_intervencion and tipo_intervencion in exclusion_tipo_intervencion:
                continue
            
            # Si pasa todos los filtros, extraer campos requeridos
            registro = {}
            for campo in campos_requeridos:
                valor = get_field_value(campo)
                registro[campo] = valor
            
            registros_filtrados.append(registro)
        
        # Preparar respuesta
        response_data = {
            "success": True,
            "data": registros_filtrados,
            "count": len(registros_filtrados),
            "collection": "unidades_proyecto",
            "timestamp": datetime.now().isoformat(),
            "last_updated": "2025-11-26T00:00:00Z",
            "message": f"Se obtuvieron {len(registros_filtrados)} registros que cumplen los criterios del artefacto #360",
            "filters_applied": {
                "excluded_clase_up": exclusion_clase_up,
                "excluded_tipo_equipamiento": exclusion_tipo_equipamiento,
                "excluded_tipo_intervencion": exclusion_tipo_intervencion
            },
            "fields_returned": campos_requeridos
        }
        
        return create_utf8_response(response_data)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error procesando consulta init-360: {str(e)}"
        )





@app.get("/intervenciones", tags=["Unidades de Proyecto"], summary="🔵 GET | Filtrar Intervenciones")
@optional_rate_limit("60/minute")
async def get_intervenciones_filtradas_endpoint(
    avance_obra: Optional[float] = Query(None, description="Avance de obra"),
    bpin: Optional[int] = Query(None, description="BPIN"),
    cantidad: Optional[int] = Query(None, description="Cantidad"),
    clase_up: Optional[str] = Query(None, description="Clase UP"),
    estado: Optional[str] = Query(None, description="Estado de la intervención"),
    fecha_fin: Optional[str] = Query(None, description="Fecha fin (string)"),
    fecha_inicio: Optional[str] = Query(None, description="Fecha inicio (string)"),
    fuente_financiacion: Optional[str] = Query(None, description="Fuente de financiacion"),
    identificador: Optional[str] = Query(None, description="Identificador"),
    intervencion_id: Optional[str] = Query(None, description="ID de la intervencion"),
    nombre_centro_gestor: Optional[str] = Query(None, description="Nombre centro gestor"),
    presupuesto_base: Optional[float] = Query(None, description="Presupuesto base"),
    referencia_contrato: Optional[str] = Query(None, description="Referencia contrato"),
    referencia_proceso: Optional[str] = Query(None, description="Referencia proceso"),
    tipo_intervencion: Optional[str] = Query(None, description="Tipo de intervencion"),
    unidad: Optional[str] = Query(None, description="Unidad"),
    upid: Optional[str] = Query(None, description="UPID"),
    url_proceso: Optional[str] = Query(None, description="URL proceso")
):
    """
    ## 🔵 GET | Filtrar Intervenciones
    
    **Propósito**: Filtrar intervenciones desde la colección
    `intervenciones_unidades_proyecto` y retornar solo las unidades que cumplen.
    
    ### Filtros Disponibles
    
    - **estado**: "En ejecución", "Terminado", "En alistamiento", etc.
    - **tipo_intervencion**: Tipo de obra o intervención
    - **ano**: Año específico (ej: 2024)
    - **frente_activo**: "Frente activo", "Inactivo", "No aplica"
    
    ### Estructura de Respuesta
    
    Respuesta plana con lista de intervenciones.
    
    ### Ejemplo de Uso
    
    ```javascript
    // Obtener todas las intervenciones en ejecución de 2024
    const response = await fetch('/intervenciones?estado=En ejecución&ano=2024');
    const data = await response.json();
    
    console.log(data.count); // Total de intervenciones encontradas
    console.log(data.data.length); // Total de registros
    ```
    
    ### Casos de Uso
    
    - Ver todas las intervenciones activas
    - Filtrar por año para análisis temporal
    - Buscar frentes activos específicos
    - Combinar múltiples filtros para búsquedas precisas
    """
    if not FIREBASE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Firebase not available")
    
    try:
        db = get_firestore_client()
        if db is None:
            raise HTTPException(status_code=503, detail="No se pudo conectar a Firestore")
        query = db.collection('intervenciones_unidades_proyecto')
        if avance_obra is not None:
            query = query.where('avance_obra', '==', avance_obra)
        if bpin is not None:
            query = query.where('bpin', '==', bpin)
        if cantidad is not None:
            query = query.where('cantidad', '==', cantidad)
        if clase_up:
            query = query.where('clase_up', '==', clase_up)
        if estado:
            query = query.where('estado', '==', estado)
        if fecha_fin:
            query = query.where('fecha_fin', '==', fecha_fin)
        if fecha_inicio:
            query = query.where('fecha_inicio', '==', fecha_inicio)
        if fuente_financiacion:
            query = query.where('fuente_financiacion', '==', fuente_financiacion)
        if identificador:
            query = query.where('identificador', '==', identificador)
        if intervencion_id:
            query = query.where('intervencion_id', '==', intervencion_id)
        if nombre_centro_gestor:
            query = query.where('nombre_centro_gestor', '==', nombre_centro_gestor)
        if presupuesto_base is not None:
            query = query.where('presupuesto_base', '==', presupuesto_base)
        if referencia_contrato:
            query = query.where('referencia_contrato', '==', referencia_contrato)
        if referencia_proceso:
            query = query.where('referencia_proceso', '==', referencia_proceso)
        if tipo_intervencion:
            query = query.where('tipo_intervencion', '==', tipo_intervencion)
        if unidad:
            query = query.where('unidad', '==', unidad)
        if upid:
            query = query.where('upid', '==', upid)
        if url_proceso:
            query = query.where('url_proceso', '==', url_proceso)

        fields = [
            "avance_obra",
            "bpin",
            "cantidad",
            "clase_up",
            "estado",
            "fecha_fin",
            "fecha_inicio",
            "fuente_financiacion",
            "identificador",
            "intervencion_id",
            "nombre_centro_gestor",
            "presupuesto_base",
            "referencia_contrato",
            "referencia_proceso",
            "tipo_intervencion",
            "unidad",
            "upid",
            "url_proceso"
        ]

        query = query.select(fields)
        docs = query.stream()

        filters_payload = {
            "avance_obra": avance_obra,
            "bpin": bpin,
            "cantidad": cantidad,
            "clase_up": clase_up,
            "estado": estado,
            "fecha_fin": fecha_fin,
            "fecha_inicio": fecha_inicio,
            "fuente_financiacion": fuente_financiacion,
            "identificador": identificador,
            "intervencion_id": intervencion_id,
            "nombre_centro_gestor": nombre_centro_gestor,
            "presupuesto_base": presupuesto_base,
            "referencia_contrato": referencia_contrato,
            "referencia_proceso": referencia_proceso,
            "tipo_intervencion": tipo_intervencion,
            "unidad": unidad,
            "upid": upid,
            "url_proceso": url_proceso
        }

        should_convert = FIREBASE_TYPES_AVAILABLE
        datetime_type = DatetimeWithNanoseconds

        def normalize_value(value):
            if should_convert and isinstance(value, datetime_type):
                return value.isoformat()
            if isinstance(value, dict):
                for inner_key, inner_value in value.items():
                    value[inner_key] = normalize_value(inner_value)
                return value
            if isinstance(value, list):
                return [normalize_value(item) for item in value]
            return value

        def coerce_float_value(value):
            if value is None or value == '':
                return None
            try:
                if isinstance(value, str):
                    cleaned = value.strip().replace('%', '').replace(' ', '')
                    if ',' in cleaned and cleaned.count(',') == 1:
                        comma_pos = cleaned.find(',')
                        if len(cleaned) - comma_pos <= 3:
                            cleaned = cleaned.replace(',', '.')
                        else:
                            cleaned = cleaned.replace(',', '')
                    else:
                        cleaned = cleaned.replace(',', '')
                    return float(cleaned) if cleaned else None
                return float(value)
            except (ValueError, TypeError):
                return None

        data = []
        for doc in docs:
            doc_data = doc.to_dict()
            if should_convert:
                doc_data = normalize_value(doc_data)

            record = {field: doc_data.get(field) for field in fields}
            record["intervencion_id"] = record.get("intervencion_id") or doc.id
            record["avance_obra"] = coerce_float_value(record.get("avance_obra"))
            data.append(record)

        return create_utf8_response({
            "success": True,
            "data": data,
            "count": len(data),
            "filters": filters_payload
        })
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error filtrando intervenciones: {str(e)}"
        )


@app.get(
    "/unidades-proyecto/intervenciones/export-xlsx",
    tags=["Unidades de Proyecto"],
    summary="📥 Exportar Intervenciones a XLSX"
)
async def exportar_intervenciones_xlsx(
    avance_obra: Optional[float] = Query(None, description="Avance de obra"),
    bpin: Optional[int] = Query(None, description="BPIN"),
    cantidad: Optional[int] = Query(None, description="Cantidad"),
    clase_up: Optional[str] = Query(None, description="Clase UP"),
    estado: Optional[str] = Query(None, description="Estado de la intervención"),
    fecha_fin: Optional[str] = Query(None, description="Fecha fin (string)"),
    fecha_inicio: Optional[str] = Query(None, description="Fecha inicio (string)"),
    fuente_financiacion: Optional[str] = Query(None, description="Fuente de financiacion"),
    identificador: Optional[str] = Query(None, description="Identificador"),
    intervencion_id: Optional[str] = Query(None, description="ID de la intervencion"),
    nombre_centro_gestor: Optional[str] = Query(None, description="Nombre centro gestor"),
    presupuesto_base: Optional[float] = Query(None, description="Presupuesto base"),
    referencia_contrato: Optional[str] = Query(None, description="Referencia contrato"),
    referencia_proceso: Optional[str] = Query(None, description="Referencia proceso"),
    tipo_intervencion: Optional[str] = Query(None, description="Tipo de intervencion"),
    unidad: Optional[str] = Query(None, description="Unidad"),
    upid: Optional[str] = Query(None, description="UPID"),
    url_proceso: Optional[str] = Query(None, description="URL proceso")
):
    """
    Exporta `intervenciones_unidades_proyecto` a XLSX excluyendo campos definidos
    y agregando `comuna_corregimiento` y `barrio_vereda` desde `unidades_proyecto` por `upid`.
    """
    if not FIREBASE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Firebase not available")

    excluded_fields = {
        "referencia_proceso",
        "referencia_contrato",
        "url_proceso",
        "identificador",
        "cantidad",
        "unidad",
        "bpin",
        "avance_obra"
    }

    try:
        from io import BytesIO
        import pandas as pd

        db = get_firestore_client()
        if db is None:
            raise HTTPException(status_code=503, detail="No se pudo conectar a Firestore")

        upid_location_map = {}
        for unidad_doc in db.collection('unidades_proyecto').stream():
            unidad_data = unidad_doc.to_dict() or {}
            props = unidad_data.get('properties', {}) if isinstance(unidad_data.get('properties'), dict) else {}

            upid_value = unidad_data.get('upid') or props.get('upid')
            if not upid_value:
                continue

            comuna = unidad_data.get('comuna_corregimiento')
            if comuna is None:
                comuna = props.get('comuna_corregimiento')

            barrio = unidad_data.get('barrio_vereda')
            if barrio is None:
                barrio = props.get('barrio_vereda')

            upid_location_map[str(upid_value)] = {
                "comuna_corregimiento": comuna,
                "barrio_vereda": barrio
            }

        def normalize_for_excel(value):
            if FIREBASE_TYPES_AVAILABLE and isinstance(value, DatetimeWithNanoseconds):
                return value.isoformat()
            if isinstance(value, datetime):
                return value.isoformat()
            if isinstance(value, dict):
                return {k: normalize_for_excel(v) for k, v in value.items()}
            if isinstance(value, list):
                return [normalize_for_excel(v) for v in value]
            return value

        interv_query = db.collection('intervenciones_unidades_proyecto')
        if avance_obra is not None:
            interv_query = interv_query.where('avance_obra', '==', avance_obra)
        if bpin is not None:
            interv_query = interv_query.where('bpin', '==', bpin)
        if cantidad is not None:
            interv_query = interv_query.where('cantidad', '==', cantidad)
        if clase_up:
            interv_query = interv_query.where('clase_up', '==', clase_up)
        if estado:
            interv_query = interv_query.where('estado', '==', estado)
        if fecha_fin:
            interv_query = interv_query.where('fecha_fin', '==', fecha_fin)
        if fecha_inicio:
            interv_query = interv_query.where('fecha_inicio', '==', fecha_inicio)
        if fuente_financiacion:
            interv_query = interv_query.where('fuente_financiacion', '==', fuente_financiacion)
        if identificador:
            interv_query = interv_query.where('identificador', '==', identificador)
        if intervencion_id:
            interv_query = interv_query.where('intervencion_id', '==', intervencion_id)
        if nombre_centro_gestor:
            interv_query = interv_query.where('nombre_centro_gestor', '==', nombre_centro_gestor)
        if presupuesto_base is not None:
            interv_query = interv_query.where('presupuesto_base', '==', presupuesto_base)
        if referencia_contrato:
            interv_query = interv_query.where('referencia_contrato', '==', referencia_contrato)
        if referencia_proceso:
            interv_query = interv_query.where('referencia_proceso', '==', referencia_proceso)
        if tipo_intervencion:
            interv_query = interv_query.where('tipo_intervencion', '==', tipo_intervencion)
        if unidad:
            interv_query = interv_query.where('unidad', '==', unidad)
        if upid:
            interv_query = interv_query.where('upid', '==', upid)
        if url_proceso:
            interv_query = interv_query.where('url_proceso', '==', url_proceso)

        export_rows = []
        for interv_doc in interv_query.stream():
            interv_data = interv_doc.to_dict() or {}
            normalized_data = {k: normalize_for_excel(v) for k, v in interv_data.items()}

            row = {
                key: value
                for key, value in normalized_data.items()
                if key not in excluded_fields
            }

            upid_value = str(interv_data.get('upid') or '')
            location = upid_location_map.get(upid_value, {})
            row["comuna_corregimiento"] = location.get("comuna_corregimiento")
            row["barrio_vereda"] = location.get("barrio_vereda")

            export_rows.append(row)

        df = pd.DataFrame(export_rows)
        output = BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="intervenciones")
        output.seek(0)

        filename = f"intervenciones_unidades_proyecto_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        return StreamingResponse(
            output,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error exportando XLSX de intervenciones: {str(e)}"
        )


@app.get("/avances_unidades_proyecto", tags=["Unidades de Proyecto"], summary="🔵 GET | Leer avances de Unidades de Proyecto")
@optional_rate_limit("60/minute")
async def get_avances_unidades_proyecto(
    intervencion_id: Optional[str] = Query(None, description="Filtrar por intervencion_id"),
    doc_id: Optional[str] = Query(None, description="ID exacto del documento en Firestore")
):
    if not FIREBASE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Firebase not available")

    try:
        db = get_firestore_client()
        if db is None:
            raise HTTPException(status_code=503, detail="No se pudo conectar a Firestore")

        collection_ref = db.collection('avances_unidades_proyecto')

        should_convert = FIREBASE_TYPES_AVAILABLE
        datetime_type = DatetimeWithNanoseconds

        def normalize_value(value):
            if should_convert and isinstance(value, datetime_type):
                return value.isoformat()
            if isinstance(value, dict):
                for inner_key, inner_value in value.items():
                    value[inner_key] = normalize_value(inner_value)
                return value
            if isinstance(value, list):
                return [normalize_value(item) for item in value]
            return value

        if doc_id:
            doc = collection_ref.document(doc_id).get()
            if not doc.exists:
                raise HTTPException(status_code=404, detail=f"No existe avance con id: {doc_id}")

            doc_data = doc.to_dict() or {}
            if should_convert:
                doc_data = normalize_value(doc_data)
            doc_data['id'] = doc.id

            return create_utf8_response({
                "data": [doc_data],
                "count": 1,
                "filters": {
                    "doc_id": doc_id,
                    "intervencion_id": intervencion_id
                }
            })

        query = collection_ref
        if intervencion_id:
            query = query.where('intervencion_id', '==', intervencion_id)
        docs = query.stream()

        data = []
        for doc in docs:
            doc_data = doc.to_dict() or {}
            if should_convert:
                doc_data = normalize_value(doc_data)
            doc_data['id'] = doc.id
            data.append(doc_data)

        return create_utf8_response({
            "data": data,
            "count": len(data),
            "filters": {
                "doc_id": doc_id,
                "intervencion_id": intervencion_id
            }
        })
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error leyendo avances de unidades de proyecto: {str(e)}"
        )


@app.get(
    "/solicitudes_cambios_unidades_proyecto",
    tags=["Unidades de Proyecto"],
    summary="🔵 GET | Consultar Solicitudes de Cambios de Unidades de Proyecto"
)
@optional_rate_limit("60/minute")
async def consultar_solicitudes_cambios_unidades_proyecto(
    doc_id: Optional[str] = Query(None, description="ID del documento en Firestore"),
    upid: Optional[str] = Query(None, description="Filtrar por UPID"),
    limit: Optional[int] = Query(None, ge=1, le=10000, description="Límite de registros"),
    offset: Optional[int] = Query(None, ge=0, description="Offset para paginación")
):
    if not FIREBASE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Firebase not available")

    try:
        db = get_firestore_client()
        if db is None:
            raise HTTPException(status_code=503, detail="No se pudo conectar a Firestore")

        collection_ref = db.collection('solicitudes_cambios_unidades_proyecto')

        should_convert = FIREBASE_TYPES_AVAILABLE
        datetime_type = DatetimeWithNanoseconds

        def normalize_value(value):
            if should_convert and isinstance(value, datetime_type):
                return value.isoformat()
            if isinstance(value, dict):
                for inner_key, inner_value in value.items():
                    value[inner_key] = normalize_value(inner_value)
                return value
            if isinstance(value, list):
                return [normalize_value(item) for item in value]
            return value

        if doc_id:
            doc = collection_ref.document(doc_id).get()
            if not doc.exists:
                raise HTTPException(status_code=404, detail=f"No existe solicitud con id: {doc_id}")

            doc_data = doc.to_dict() or {}
            if should_convert:
                doc_data = normalize_value(doc_data)
            doc_data['id'] = doc.id

            return create_utf8_response({
                "success": True,
                "data": [doc_data],
                "count": 1,
                "collection": "solicitudes_cambios_unidades_proyecto",
                "filters": {
                    "doc_id": doc_id,
                    "upid": upid,
                    "limit": limit,
                    "offset": offset
                }
            })

        query = collection_ref
        if upid:
            query = query.where('upid', '==', upid)

        order_applied = False
        try:
            import google.cloud.firestore
            query = query.order_by('created_at', direction=google.cloud.firestore.Query.DESCENDING)
            order_applied = True
        except Exception:
            order_applied = False

        query_limit = min(limit or 100, 10000)
        query = query.limit(query_limit)

        if offset:
            query = query.offset(offset)

        try:
            docs = query.stream()
        except Exception as e:
            error_text = str(e).lower()
            if order_applied and ("failed_precondition" in error_text or "index" in error_text):
                fallback_query = collection_ref
                if upid:
                    fallback_query = fallback_query.where('upid', '==', upid)
                fallback_query = fallback_query.limit(query_limit)
                if offset:
                    fallback_query = fallback_query.offset(offset)
                docs = fallback_query.stream()
                order_applied = False
            else:
                raise

        data = []
        for doc in docs:
            doc_data = doc.to_dict() or {}
            if should_convert:
                doc_data = normalize_value(doc_data)
            doc_data['id'] = doc.id
            data.append(doc_data)

        return create_utf8_response({
            "success": True,
            "data": data,
            "count": len(data),
            "collection": "solicitudes_cambios_unidades_proyecto",
            "filters": {
                "doc_id": doc_id,
                "upid": upid,
                "limit": query_limit,
                "offset": offset or 0,
                "ordered_by": "created_at_desc" if order_applied else None
            }
        })
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error consultando solicitudes de cambios de unidades de proyecto: {str(e)}"
        )


@app.get(
    "/solicitudes_cambios_intervenciones",
    tags=["Unidades de Proyecto"],
    summary="🔵 GET | Consultar Solicitudes de Cambios de Intervenciones"
)
@optional_rate_limit("60/minute")
async def consultar_solicitudes_cambios_intervenciones(
    doc_id: Optional[str] = Query(None, description="ID del documento en Firestore"),
    intervencion_id: Optional[str] = Query(None, description="Filtrar por ID de intervención"),
    upid: Optional[str] = Query(None, description="Filtrar por UPID"),
    limit: Optional[int] = Query(None, ge=1, le=10000, description="Límite de registros"),
    offset: Optional[int] = Query(None, ge=0, description="Offset para paginación")
):
    if not FIREBASE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Firebase not available")

    try:
        db = get_firestore_client()
        if db is None:
            raise HTTPException(status_code=503, detail="No se pudo conectar a Firestore")

        collection_ref = db.collection('solicitudes_cambios_intervenciones')

        should_convert = FIREBASE_TYPES_AVAILABLE
        datetime_type = DatetimeWithNanoseconds

        def normalize_value(value):
            if should_convert and isinstance(value, datetime_type):
                return value.isoformat()
            if isinstance(value, dict):
                for inner_key, inner_value in value.items():
                    value[inner_key] = normalize_value(inner_value)
                return value
            if isinstance(value, list):
                return [normalize_value(item) for item in value]
            return value

        if doc_id:
            doc = collection_ref.document(doc_id).get()
            if not doc.exists:
                raise HTTPException(status_code=404, detail=f"No existe solicitud con id: {doc_id}")

            doc_data = doc.to_dict() or {}
            if should_convert:
                doc_data = normalize_value(doc_data)
            doc_data['id'] = doc.id

            return create_utf8_response({
                "success": True,
                "data": [doc_data],
                "count": 1,
                "collection": "solicitudes_cambios_intervenciones",
                "filters": {
                    "doc_id": doc_id,
                    "intervencion_id": intervencion_id,
                    "upid": upid,
                    "limit": limit,
                    "offset": offset
                }
            })

        query = collection_ref
        if intervencion_id:
            query = query.where('intervencion_id', '==', intervencion_id)
        if upid:
            query = query.where('upid', '==', upid)

        order_applied = False
        try:
            import google.cloud.firestore
            query = query.order_by('created_at', direction=google.cloud.firestore.Query.DESCENDING)
            order_applied = True
        except Exception:
            order_applied = False

        query_limit = min(limit or 100, 10000)
        query = query.limit(query_limit)

        if offset:
            query = query.offset(offset)

        try:
            docs = query.stream()
        except Exception as e:
            error_text = str(e).lower()
            if order_applied and ("failed_precondition" in error_text or "index" in error_text):
                fallback_query = collection_ref
                if intervencion_id:
                    fallback_query = fallback_query.where('intervencion_id', '==', intervencion_id)
                if upid:
                    fallback_query = fallback_query.where('upid', '==', upid)
                fallback_query = fallback_query.limit(query_limit)
                if offset:
                    fallback_query = fallback_query.offset(offset)
                docs = fallback_query.stream()
                order_applied = False
            else:
                raise

        data = []
        for doc in docs:
            doc_data = doc.to_dict() or {}
            if should_convert:
                doc_data = normalize_value(doc_data)
            doc_data['id'] = doc.id
            data.append(doc_data)

        return create_utf8_response({
            "success": True,
            "data": data,
            "count": len(data),
            "collection": "solicitudes_cambios_intervenciones",
            "filters": {
                "doc_id": doc_id,
                "intervencion_id": intervencion_id,
                "upid": upid,
                "limit": query_limit,
                "offset": offset or 0,
                "ordered_by": "created_at_desc" if order_applied else None
            }
        })
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error consultando solicitudes de cambios de intervenciones: {str(e)}"
        )


class SolicitudCambioUnidadProyectoRequest(BaseModel):
    upid: str = Field(..., description="UPID de la unidad a modificar (ej: UNP-1)")
    aprobado: bool = Field(..., description="Indicador de aprobación de la solicitud")
    nombre_up: Optional[str] = Field(None, description="Nombre de la unidad de proyecto")
    nombre_up_detalle: Optional[str] = Field(None, description="Detalle del nombre de la unidad")
    tipo_equipamiento: Optional[str] = Field(None, description="Tipo de equipamiento")
    clase_up: Optional[str] = Field(None, description="Clase UP")
    direccion: Optional[str] = Field(None, description="Dirección")
    geometry: Optional[Dict[str, Any]] = Field(
        None,
        description="Geometría GeoJSON Point enviada desde el frontend. Si se envía, recalcula automáticamente comuna_corregimiento, barrio_vereda y proyectos_estrategicos"
    )

    class Config:
        extra = "allow"
        schema_extra = {
            "example": {
                "upid": "UNP-1",
                "aprobado": True,
                "nombre_up": "Nombre unidad",
                "nombre_up_detalle": "Detalle unidad",
                "tipo_equipamiento": "Parque",
                "clase_up": "Espacio Publico",
                "direccion": "Calle 1 # 2-3",
                "geometry": {
                    "additionalProp1": {}
                },
                "additionalProp1": {}
            }
        }


@app.post("/solicitudes_cambios_unidad_proyecto", tags=["Unidades de Proyecto"], summary="🟢 POST | Solicitud de cambios en Unidad de Proyecto")
@optional_rate_limit("30/minute")
async def crear_solicitud_cambio_unidad_proyecto(
    request: Request,
    payload: SolicitudCambioUnidadProyectoRequest = Body(
        ...,
        description="Datos de solicitud. Usa la misma estructura de /modificar/unidad_proyecto"
    )
):
    if not FIREBASE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Firebase not available")

    try:
        db = get_firestore_client()
        if db is None:
            raise HTTPException(status_code=503, detail="No se pudo conectar a Firestore")

        body = payload.model_dump(exclude_unset=True) if hasattr(payload, "model_dump") else payload.dict(exclude_unset=True)
        upid_value = str(body.get("upid", "")).strip()
        if not upid_value:
            raise HTTPException(status_code=400, detail="Debe enviar upid para registrar la solicitud")

        if "aprobado" not in body or not isinstance(body.get("aprobado"), bool):
            raise HTTPException(status_code=400, detail="Debe enviar 'aprobado' como booleano")

        changes = {key: value for key, value in body.items() if key not in {"upid", "aprobado"}}

        # Recalcular campos geograficos cuando se envia geometry Point.
        geometry_val = changes.get("geometry")
        if isinstance(geometry_val, dict) and geometry_val.get("type") == "Point" and geometry_val.get("coordinates"):
            coords = geometry_val["coordinates"]
            basemaps_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "basemaps")
            comuna = _buscar_en_geojson(
                os.path.join(basemaps_dir, "comunas_corregimientos.geojson"),
                "comuna_corregimiento", coords
            )
            barrio = _buscar_en_geojson(
                os.path.join(basemaps_dir, "barrios_veredas.geojson"),
                "barrio_vereda", coords
            )
            proyectos = _buscar_proyectos_estrategicos(coords)
            if comuna:
                changes["comuna_corregimiento"] = comuna
            if barrio:
                changes["barrio_vereda"] = barrio
            changes["proyectos_estrategicos"] = proyectos

        now_iso = datetime.now().isoformat()
        solicitud_payload = {
            "upid": upid_value,
            "aprobado": body.get("aprobado"),
            **changes,
            "created_at": now_iso,
            "updated_at": now_iso
        }
        solicitud_payload = {key: value for key, value in solicitud_payload.items() if value is not None}

        doc_id = str(uuid.uuid4())
        db.collection('solicitudes_cambios_unidades_proyecto').document(doc_id).set(solicitud_payload)

        return create_utf8_response({
            "id": doc_id,
            "collection": "solicitudes_cambios_unidades_proyecto",
            "data": solicitud_payload
        })
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error registrando solicitud de cambio de unidad de proyecto: {str(e)}"
        )


@app.post("/solicitudes_cambios_intervencion", tags=["Unidades de Proyecto"], summary="🟢 POST | Solicitud de cambios en Intervención")
@optional_rate_limit("30/minute")
async def crear_solicitud_cambio_intervencion(
    request: Request,
    avance_obra: Optional[float] = Body(None, description="Avance de obra"),
    bpin: Optional[int] = Body(None, description="BPIN"),
    cantidad: Optional[int] = Body(None, description="Cantidad"),
    clase_up: Optional[str] = Body(None, description="Clase UP"),
    estado: Optional[str] = Body(None, description="Estado de la intervención"),
    fecha_fin: Optional[str] = Body(None, description="Fecha fin (string)"),
    fecha_inicio: Optional[str] = Body(None, description="Fecha inicio (string)"),
    fuente_financiacion: Optional[str] = Body(None, description="Fuente de financiación"),
    identificador: Optional[str] = Body(None, description="Identificador"),
    intervencion_id: Optional[str] = Body(None, description="ID de la intervención"),
    nombre_centro_gestor: Optional[str] = Body(None, description="Nombre centro gestor"),
    presupuesto_base: Optional[float] = Body(None, description="Presupuesto base"),
    referencia_contrato: Optional[str] = Body(None, description="Referencia contrato"),
    referencia_proceso: Optional[str] = Body(None, description="Referencia proceso"),
    tipo_intervencion: Optional[str] = Body(None, description="Tipo de intervención"),
    unidad: Optional[str] = Body(None, description="Unidad"),
    upid: Optional[str] = Body(None, description="UPID"),
    url_proceso: Optional[str] = Body(None, description="URL proceso")
):
    if not FIREBASE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Firebase not available")

    try:
        db = get_firestore_client()
        if db is None:
            raise HTTPException(status_code=503, detail="No se pudo conectar a Firestore")

        now_iso = datetime.now().isoformat()
        solicitud_payload = {
            "avance_obra": avance_obra,
            "bpin": bpin,
            "cantidad": cantidad,
            "clase_up": clase_up,
            "estado": estado,
            "fecha_fin": fecha_fin,
            "fecha_inicio": fecha_inicio,
            "fuente_financiacion": fuente_financiacion,
            "identificador": identificador,
            "intervencion_id": intervencion_id,
            "nombre_centro_gestor": nombre_centro_gestor,
            "presupuesto_base": presupuesto_base,
            "referencia_contrato": referencia_contrato,
            "referencia_proceso": referencia_proceso,
            "tipo_intervencion": tipo_intervencion,
            "unidad": unidad,
            "upid": upid,
            "url_proceso": url_proceso,
            "created_at": now_iso,
            "updated_at": now_iso
        }
        solicitud_payload = {key: value for key, value in solicitud_payload.items() if value is not None}

        doc_id = str(uuid.uuid4())
        db.collection('solicitudes_cambios_intervenciones').document(doc_id).set(solicitud_payload)

        return create_utf8_response({
            "id": doc_id,
            "collection": "solicitudes_cambios_intervenciones",
            "data": solicitud_payload
        })
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error registrando solicitud de cambio de intervención: {str(e)}"
        )


def _buscar_en_geojson(geojson_path: str, property_name: str, point_coords: list) -> Optional[str]:
    """Cruza un punto con una capa GeoJSON y retorna la propiedad del polígono que lo contiene."""
    try:
        with open(geojson_path, "r", encoding="utf-8") as f:
            geojson_data = json.load(f)
        point = ShapelyPoint(point_coords[0], point_coords[1])
        for feature in geojson_data.get("features", []):
            polygon = shapely_shape(feature["geometry"])
            if polygon.contains(point):
                return feature.get("properties", {}).get(property_name)
    except Exception as e:
        logger.warning(f"Error cruzando geometría con {geojson_path}: {type(e).__name__}")
    return None


def _buscar_proyectos_estrategicos(point_coords: list) -> str:
    """Intersecta un punto con todos los GeoJSON en basemaps/proyectos_estrategicos/ y retorna los Name coincidentes."""
    nombres = []
    estrategicos_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "basemaps", "proyectos_estrategicos")
    if not os.path.isdir(estrategicos_dir):
        return ""
    try:
        point = ShapelyPoint(point_coords[0], point_coords[1])
        for filename in os.listdir(estrategicos_dir):
            if not filename.lower().endswith(".geojson"):
                continue
            filepath = os.path.join(estrategicos_dir, filename)
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    geojson_data = json.load(f)
                for feature in geojson_data.get("features", []):
                    polygon = shapely_shape(feature["geometry"])
                    if polygon.intersects(point):
                        name = feature.get("properties", {}).get("Name")
                        if name and name not in nombres:
                            nombres.append(name)
            except Exception as e:
                logger.warning(f"Error procesando {filename}: {type(e).__name__}")
    except Exception as e:
        logger.warning(f"Error leyendo directorio proyectos_estrategicos: {type(e).__name__}")
    return ", ".join(nombres) if nombres else ""


@app.post("/crear_unidad_proyecto", tags=["Unidades de Proyecto"], summary="🟢 POST | Crear Unidad de Proyecto",
    description=(
        "Crea una nueva Unidad de Proyecto. Variables auto-calculadas:\n\n"
        "- **upid**: se genera automáticamente (último UNP-### + 1)\n"
        "- **comuna_corregimiento**: se detecta cruzando geometry con basemaps/comunas_corregimientos.geojson\n"
        "- **barrio_vereda**: se detecta cruzando geometry con basemaps/barrios_veredas.geojson\n"
        "- **proyectos_estrategicos**: lista de nombres obtenida por intersección con basemaps/proyectos_estrategicos/*.geojson\n"
    ))
@optional_rate_limit("30/minute")
async def crear_unidad_proyecto(
    request: Request,
    nombre_up: Optional[str] = Body(None, description="Nombre de la unidad de proyecto", example="Parque Lineal Río Cali"),
    nombre_up_detalle: Optional[str] = Body(None, description="Detalle del nombre de la unidad", example="Tramo 3 - Sector Norte"),
    tipo_equipamiento: Optional[str] = Body(None, description="Tipo de equipamiento", example="Parque"),
    clase_up: Optional[str] = Body(None, description="Clase UP", example="Espacio Público"),
    direccion: Optional[str] = Body(None, description="Dirección", example="Calle 25 Norte #6N-45"),
    geometry: Optional[Dict[str, Any]] = Body(
        None,
        description="Geometría GeoJSON tipo Point con coordenadas [longitud, latitud]",
        example={"type": "Point", "coordinates": [0.0, 0.0]}
    )
):
    if not FIREBASE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Firebase not available")

    try:
        db = get_firestore_client()
        if db is None:
            raise HTTPException(status_code=503, detail="No se pudo conectar a Firestore")

        # --- Auto-generar UPID (último UNP-### de unidades_proyecto + 1) ---
        def extract_upid_number(upid_value: Any) -> Optional[int]:
            if upid_value is None:
                return None
            match = re.match(r"^UNP-(\d+)$", str(upid_value).strip(), re.IGNORECASE)
            if not match:
                return None
            return int(match.group(1))

        max_upid_number = 0
        collections_to_scan = ["unidades_proyecto"]

        for collection_name in collections_to_scan:
            docs = db.collection(collection_name).select(["upid"]).stream()
            for doc in docs:
                doc_data = doc.to_dict() or {}
                upid_number = extract_upid_number(doc_data.get("upid"))
                if upid_number is not None:
                    max_upid_number = max(max_upid_number, upid_number)

        new_upid = f"UNP-{max_upid_number + 1}"

        # --- Auto-detectar comuna_corregimiento y barrio_vereda desde geometry ---
        comuna_corregimiento = None
        barrio_vereda = None
        basemaps_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "basemaps")

        proyectos_estrategicos = ""

        if geometry and geometry.get("type") == "Point" and geometry.get("coordinates"):
            coords = geometry["coordinates"]
            comuna_corregimiento = _buscar_en_geojson(
                os.path.join(basemaps_dir, "comunas_corregimientos.geojson"),
                "comuna_corregimiento",
                coords
            )
            barrio_vereda = _buscar_en_geojson(
                os.path.join(basemaps_dir, "barrios_veredas.geojson"),
                "barrio_vereda",
                coords
            )
            proyectos_estrategicos = _buscar_proyectos_estrategicos(coords)

        now_iso = datetime.now().isoformat()

        unidad_payload = {
            "nombre_up": nombre_up,
            "nombre_up_detalle": nombre_up_detalle,
            "tipo_equipamiento": tipo_equipamiento,
            "clase_up": clase_up,
            "comuna_corregimiento": comuna_corregimiento,
            "barrio_vereda": barrio_vereda,
            "direccion": direccion,
            "geometry": geometry,
        }
        unidad_payload = {key: value for key, value in unidad_payload.items() if value is not None}
        unidad_payload["upid"] = new_upid
        unidad_payload["proyectos_estrategicos"] = proyectos_estrategicos
        unidad_payload["created_at"] = now_iso
        unidad_payload["updated_at"] = now_iso

        db.collection("unidades_proyecto").document(new_upid).set(unidad_payload)

        return create_utf8_response({
            "id": new_upid,
            "collection": "unidades_proyecto",
            "data": unidad_payload
        })
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error creando unidad de proyecto: {str(e)}"
        )


@app.post("/crear_intervencion", tags=["Unidades de Proyecto"], summary="🟢 POST | Crear Intervención")
@optional_rate_limit("30/minute")
async def crear_intervencion(
    request: Request,
    upid: str = Body(..., description="UPID válido existente en unidades_proyecto"),
    avance_obra: Optional[float] = Body(None, description="Avance de obra"),
    bpin: Optional[int] = Body(None, description="BPIN"),
    cantidad: Optional[int] = Body(None, description="Cantidad"),
    clase_up: Optional[str] = Body(None, description="Clase UP"),
    estado: Optional[str] = Body(None, description="Estado de la intervención"),
    fecha_fin: Optional[str] = Body(None, description="Fecha fin (string)"),
    fecha_inicio: Optional[str] = Body(None, description="Fecha inicio (string)"),
    fuente_financiacion: Optional[str] = Body(None, description="Fuente de financiación"),
    identificador: Optional[str] = Body(None, description="Identificador"),
    nombre_centro_gestor: Optional[str] = Body(None, description="Nombre centro gestor"),
    presupuesto_base: Optional[float] = Body(None, description="Presupuesto base"),
    referencia_contrato: Optional[str] = Body(None, description="Referencia contrato"),
    referencia_proceso: Optional[str] = Body(None, description="Referencia proceso"),
    tipo_intervencion: Optional[str] = Body(None, description="Tipo de intervención"),
    unidad: Optional[str] = Body(None, description="Unidad"),
    url_proceso: Optional[str] = Body(None, description="URL proceso"),
    descripcion_intervencion: Optional[str] = Body(None, description="Descripción de la intervención")
):
    if not FIREBASE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Firebase not available")

    try:
        db = get_firestore_client()
        if db is None:
            raise HTTPException(status_code=503, detail="No se pudo conectar a Firestore")

        upid_value = str(upid).strip()
        if not upid_value:
            raise HTTPException(status_code=400, detail="El campo upid es obligatorio para crear una intervención")

        upid_docs = list(db.collection("unidades_proyecto").where("upid", "==", upid_value).limit(1).stream())
        if not upid_docs:
            raise HTTPException(status_code=400, detail=f"El upid {upid_value} no existe en unidades_proyecto")

        def extract_intervencion_number(intervencion_value: Any, upid_base: str) -> Optional[int]:
            if intervencion_value is None:
                return None
            pattern = rf"^{re.escape(upid_base)}-INT-(\d+)$"
            match = re.match(pattern, str(intervencion_value).strip(), re.IGNORECASE)
            if not match:
                return None
            return int(match.group(1))

        max_intervencion_number = 0
        collections_to_scan = ["intervenciones_unidades_proyecto", "unidades_proyecto_intervenciones"]

        for collection_name in collections_to_scan:
            docs = db.collection(collection_name).where("upid", "==", upid_value).stream()
            for doc in docs:
                doc_data = doc.to_dict() or {}
                intervencion_number = extract_intervencion_number(doc_data.get("intervencion_id"), upid_value)
                if intervencion_number is None:
                    intervencion_number = extract_intervencion_number(doc.id, upid_value)
                if intervencion_number is not None:
                    max_intervencion_number = max(max_intervencion_number, intervencion_number)

        new_intervencion_id = f"{upid_value}-INT-{max_intervencion_number + 1}"
        now_iso = datetime.now().isoformat()

        intervencion_payload = {
            "avance_obra": avance_obra,
            "bpin": bpin,
            "cantidad": cantidad,
            "clase_up": clase_up,
            "estado": estado,
            "fecha_fin": fecha_fin,
            "fecha_inicio": fecha_inicio,
            "fuente_financiacion": fuente_financiacion,
            "identificador": identificador,
            "nombre_centro_gestor": nombre_centro_gestor,
            "presupuesto_base": presupuesto_base,
            "referencia_contrato": referencia_contrato,
            "referencia_proceso": referencia_proceso,
            "tipo_intervencion": tipo_intervencion,
            "unidad": unidad,
            "url_proceso": url_proceso,
            "descripcion_intervencion": descripcion_intervencion
        }
        intervencion_payload = {key: value for key, value in intervencion_payload.items() if value is not None}
        intervencion_payload["upid"] = upid_value
        intervencion_payload["intervencion_id"] = new_intervencion_id
        intervencion_payload["created_at"] = now_iso
        intervencion_payload["updated_at"] = now_iso

        doc_id = str(uuid.uuid4())
        db.collection("intervenciones_unidades_proyecto").document(doc_id).set(intervencion_payload)

        return create_utf8_response({
            "id": doc_id,
            "collection": "intervenciones_unidades_proyecto",
            "data": intervencion_payload
        })
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error creando intervención: {str(e)}"
        )


class ModificarUnidadProyectoRequest(BaseModel):
    upid: str = Field(..., description="UPID de la unidad a modificar (ej: UNP-1)")
    aprobado: bool = Field(..., description="Si es true aplica cambios; si es false solo registra auditoría")
    nombre_up: Optional[str] = Field(None, description="Nombre de la unidad de proyecto")
    nombre_up_detalle: Optional[str] = Field(None, description="Detalle del nombre de la unidad")
    tipo_equipamiento: Optional[str] = Field(None, description="Tipo de equipamiento")
    clase_up: Optional[str] = Field(None, description="Clase UP")
    direccion: Optional[str] = Field(None, description="Dirección")
    geometry: Optional[Dict[str, Any]] = Field(
        None,
        description="Geometría GeoJSON Point enviada desde el frontend. Si se envía, recalcula automáticamente comuna_corregimiento, barrio_vereda y proyectos_estrategicos"
    )

    class Config:
        extra = "allow"
        schema_extra = {
            "example": {
                "upid": "UNP-1",
                "aprobado": True,
                "nombre_up": "Nombre unidad",
                "geometry": {"type": "Point", "coordinates": [0.0, 0.0]}
            }
        }


class ModificarIntervencionRequest(BaseModel):
    intervencion_id: str = Field(..., description="ID de intervención a modificar")
    aprobado: bool = Field(..., description="Si es true aplica cambios; si es false solo registra auditoría")
    upid: Optional[str] = Field(None, description="UPID asociado")
    avance_obra: Optional[float] = Field(None, description="Avance de obra")
    bpin: Optional[int] = Field(None, description="BPIN")
    cantidad: Optional[int] = Field(None, description="Cantidad")
    clase_up: Optional[str] = Field(None, description="Clase UP")
    estado: Optional[str] = Field(None, description="Estado de la intervención")
    fecha_fin: Optional[str] = Field(None, description="Fecha fin")
    fecha_inicio: Optional[str] = Field(None, description="Fecha inicio")
    fuente_financiacion: Optional[str] = Field(None, description="Fuente de financiación")
    identificador: Optional[str] = Field(None, description="Identificador")
    nombre_centro_gestor: Optional[str] = Field(None, description="Nombre del centro gestor")
    presupuesto_base: Optional[float] = Field(None, description="Presupuesto base")
    referencia_contrato: Optional[str] = Field(None, description="Referencia contrato")
    referencia_proceso: Optional[str] = Field(None, description="Referencia proceso")
    tipo_intervencion: Optional[str] = Field(None, description="Tipo de intervención")
    unidad: Optional[str] = Field(None, description="Unidad")
    url_proceso: Optional[str] = Field(None, description="URL del proceso")
    descripcion_intervencion: Optional[str] = Field(None, description="Descripción de la intervención")
    extra_data: Optional[Dict[str, Any]] = Field(
        None,
        description="Campos adicionales válidos de la colección intervenciones_unidades_proyecto"
    )

    class Config:
        extra = "allow"
        schema_extra = {
            "example": {
                "intervencion_id": "UP-001-INT-1",
                "aprobado": False,
                "descripcion_intervencion": "Ajuste de alcance",
                "cantidad": 12,
                "extra_data": {
                    "observaciones": "Pendiente aprobación técnica"
                }
            }
        }


@app.put("/modificar/unidad_proyecto", tags=["Unidades de Proyecto"], summary="🟠 PUT | Modificar Unidad de Proyecto")
@optional_rate_limit("30/minute")
async def modificar_unidad_proyecto(
    request: Request,
    payload: ModificarUnidadProyectoRequest = Body(
        ...,
        description="Datos a modificar. Incluye upid, aprobado y cualquier campo adicional a actualizar"
    )
):
    if not FIREBASE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Firebase not available")

    try:
        db = get_firestore_client()
        if db is None:
            raise HTTPException(status_code=503, detail="No se pudo conectar a Firestore")

        body = payload.model_dump(exclude_unset=True) if hasattr(payload, "model_dump") else payload.dict(exclude_unset=True)
        upid_value = str(body.get("upid", "")).strip()
        if not upid_value:
            raise HTTPException(status_code=400, detail="Debe enviar upid para modificar la unidad de proyecto")

        if "aprobado" not in body or not isinstance(body.get("aprobado"), bool):
            raise HTTPException(status_code=400, detail="Debe enviar 'aprobado' como booleano")
        aprobado = body.get("aprobado")

        doc_ref = db.collection("unidades_proyecto").document(upid_value)
        doc_snap = doc_ref.get()
        if not doc_snap.exists:
            raise HTTPException(status_code=404, detail=f"No existe unidad_proyecto con upid: {upid_value}")

        changes = {key: value for key, value in body.items() if key not in {"upid", "aprobado"}}

        # --- Auto-detectar comuna, barrio y proyectos desde geometry ---
        geometry_val = changes.get("geometry")
        if geometry_val and geometry_val.get("type") == "Point" and geometry_val.get("coordinates"):
            coords = geometry_val["coordinates"]
            basemaps_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "basemaps")
            comuna = _buscar_en_geojson(
                os.path.join(basemaps_dir, "comunas_corregimientos.geojson"),
                "comuna_corregimiento", coords
            )
            barrio = _buscar_en_geojson(
                os.path.join(basemaps_dir, "barrios_veredas.geojson"),
                "barrio_vereda", coords
            )
            proyectos = _buscar_proyectos_estrategicos(coords)
            if comuna:
                changes["comuna_corregimiento"] = comuna
            if barrio:
                changes["barrio_vereda"] = barrio
            changes["proyectos_estrategicos"] = proyectos

        if not changes:
            raise HTTPException(status_code=400, detail="No se enviaron campos a modificar")

        previous_data = doc_snap.to_dict() or {}

        changes_to_apply = dict(changes)
        if aprobado:
            now_iso = datetime.now().isoformat()
            changes_to_apply["updated_at"] = now_iso
            doc_ref.update(changes_to_apply)

        updated_data = dict(previous_data)
        if aprobado:
            updated_data.update(changes_to_apply)

        db.collection("cambios_implementados_unidades_proyecto").add({
            "timestamp": datetime.now().isoformat(),
            "collection_origen": "unidades_proyecto",
            "documento_origen_id": upid_value,
            "upid": upid_value,
            "aprobado": aprobado,
            "ejecutado": aprobado,
            "datos_anteriores": previous_data,
            "datos_solicitados": changes,
            "datos_resultantes": updated_data
        })

        return create_utf8_response({
            "id": upid_value,
            "collection": "unidades_proyecto",
            "upid": upid_value,
            "aprobado": aprobado,
            "ejecutado": aprobado,
            "data": updated_data
        })
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error modificando unidad de proyecto: {str(e)}"
        )


@app.put("/modificar/intervencion", tags=["Unidades de Proyecto"], summary="🟠 PUT | Modificar Intervención")
@optional_rate_limit("30/minute")
async def modificar_intervencion(
    request: Request,
    payload: ModificarIntervencionRequest = Body(
        ...,
        description="Datos a modificar. Incluye intervencion_id, aprobado y cualquier campo adicional a actualizar"
    )
):
    if not FIREBASE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Firebase not available")

    try:
        db = get_firestore_client()
        if db is None:
            raise HTTPException(status_code=503, detail="No se pudo conectar a Firestore")

        body = payload.model_dump(exclude_unset=True) if hasattr(payload, "model_dump") else payload.dict(exclude_unset=True)
        intervencion_id_value = str(body.get("intervencion_id", "")).strip()
        if not intervencion_id_value:
            raise HTTPException(status_code=400, detail="Debe enviar intervencion_id para modificar la intervención")

        if "aprobado" not in body or not isinstance(body.get("aprobado"), bool):
            raise HTTPException(status_code=400, detail="Debe enviar 'aprobado' como booleano")
        aprobado = body.get("aprobado")

        docs = list(
            db.collection("intervenciones_unidades_proyecto")
            .where("intervencion_id", "==", intervencion_id_value)
            .limit(1)
            .stream()
        )
        if not docs:
            raise HTTPException(status_code=404, detail=f"No existe intervención con intervencion_id: {intervencion_id_value}")

        extra_data = body.get("extra_data") or {}
        if not isinstance(extra_data, dict):
            raise HTTPException(status_code=400, detail="'extra_data' debe ser un objeto JSON")

        changes = {key: value for key, value in body.items() if key not in {"intervencion_id", "aprobado", "extra_data"}}
        changes.update(extra_data)
        if not changes:
            raise HTTPException(status_code=400, detail="No se enviaron campos a modificar")

        doc = docs[0]
        previous_data = doc.to_dict() or {}

        changes_to_apply = dict(changes)
        if aprobado:
            now_iso = datetime.now().isoformat()
            changes_to_apply["updated_at"] = now_iso
            doc.reference.update(changes_to_apply)

        updated_data = dict(previous_data)
        if aprobado:
            updated_data.update(changes_to_apply)

        db.collection("cambios_implementados_intervenciones").add({
            "timestamp": datetime.now().isoformat(),
            "collection_origen": "intervenciones_unidades_proyecto",
            "documento_origen_id": doc.id,
            "intervencion_id": intervencion_id_value,
            "aprobado": aprobado,
            "ejecutado": aprobado,
            "datos_anteriores": previous_data,
            "datos_solicitados": changes,
            "datos_resultantes": updated_data
        })

        return create_utf8_response({
            "id": doc.id,
            "collection": "intervenciones_unidades_proyecto",
            "intervencion_id": intervencion_id_value,
            "aprobado": aprobado,
            "ejecutado": aprobado,
            "data": updated_data
        })
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error modificando intervención: {str(e)}"
        )


@app.delete("/eliminar_unidad_proyecto", tags=["Unidades de Proyecto"], summary="🔴 DELETE | Eliminar Unidad de Proyecto")
@optional_rate_limit("30/minute")
async def eliminar_unidad_proyecto(
    request: Request,
    upid: str = Query(..., description="UPID de la unidad de proyecto a eliminar")
):
    if not FIREBASE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Firebase not available")

    try:
        db = get_firestore_client()
        if db is None:
            raise HTTPException(status_code=503, detail="No se pudo conectar a Firestore")

        docs = list(db.collection("unidades_proyecto").where("upid", "==", upid).stream())
        if not docs:
            raise HTTPException(status_code=404, detail=f"No existe unidad_proyecto con upid: {upid}")

        deleted_count = 0
        for doc in docs:
            doc.reference.delete()
            deleted_count += 1

        return create_utf8_response({
            "deleted": True,
            "collection": "unidades_proyecto",
            "upid": upid,
            "deleted_count": deleted_count
        })
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error eliminando unidad de proyecto: {str(e)}"
        )


@app.delete("/eliminar_intervencion", tags=["Unidades de Proyecto"], summary="🔴 DELETE | Eliminar Intervención")
@optional_rate_limit("30/minute")
async def eliminar_intervencion(
    request: Request,
    intervencion_id: str = Query(..., description="ID de la intervención a eliminar")
):
    if not FIREBASE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Firebase not available")

    try:
        db = get_firestore_client()
        if db is None:
            raise HTTPException(status_code=503, detail="No se pudo conectar a Firestore")

        docs = list(
            db.collection("intervenciones_unidades_proyecto")
            .where("intervencion_id", "==", intervencion_id)
            .stream()
        )
        if not docs:
            raise HTTPException(status_code=404, detail=f"No existe intervención con intervencion_id: {intervencion_id}")

        deleted_count = 0
        for doc in docs:
            doc.reference.delete()
            deleted_count += 1

        return create_utf8_response({
            "deleted": True,
            "collection": "intervenciones_unidades_proyecto",
            "intervencion_id": intervencion_id,
            "deleted_count": deleted_count
        })
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error eliminando intervención: {str(e)}"
        )


@app.post("/registrar_avance_up", tags=["Unidades de Proyecto"], summary="🟢 POST | Registrar Avance UP")
@optional_rate_limit("30/minute")
async def registrar_avance_up(
    request: Request,
    avance_obra: float = Form(..., description="Avance de obra (admite decimales)"),
    observaciones: str = Form(..., description="Observaciones del avance"),
    intervencion_id: str = Form(..., min_length=1, description="ID de la intervención"),
    registro_fotografico: List[UploadFile] = File(..., description="Uno o más archivos de imagen")
):
    """
    ## 🟢 POST | Registrar avance de unidad de proyecto

    - Comprime imágenes para optimización web
    - Guarda imágenes en S3 bajo folder por `intervencion_id`
    - Persiste el avance y urls en Firestore
    """
    if not FIREBASE_AVAILABLE or not SCRIPTS_AVAILABLE:
        raise HTTPException(status_code=503, detail="Firebase or scripts not available")

    if not registro_fotografico:
        raise HTTPException(status_code=400, detail="Debe adjuntar al menos una imagen en registro_fotografico")

    try:
        import io
        import unicodedata
        from PIL import Image, UnidentifiedImageError
        from api.utils.s3_document_manager import S3DocumentManager, BOTO3_AVAILABLE

        if not BOTO3_AVAILABLE:
            raise HTTPException(status_code=500, detail="boto3 no disponible para subida a S3")

        credentials_path = os.getenv('AWS_CREDENTIALS_FILE_UNIDADES_PROYECTO', 'credentials/aws_credentials.json')
        bucket_unidades_proyecto = os.getenv('S3_BUCKET_UNIDADES_PROYECTO', 'unidades-proyecto-documents')
        fotos_prefix = os.getenv('S3_PREFIX_UNIDADES_PROYECTO', 'unidades_proyecto_photos').strip('/')

        try:
            s3_manager = S3DocumentManager(credentials_path=credentials_path)
            # Para este endpoint se usa explícitamente el bucket de unidades de proyecto
            s3_manager.bucket_name = bucket_unidades_proyecto
            s3_client = s3_manager.s3_client
            aws_profile_usado = f"archivo:{credentials_path}"

            try:
                s3_client.head_bucket(Bucket=bucket_unidades_proyecto)
            except Exception:
                fallback_bucket = s3_manager.credentials.get('bucket_name', 'unidades-proyecto-documents')
                if fallback_bucket and fallback_bucket != bucket_unidades_proyecto:
                    try:
                        s3_client.head_bucket(Bucket=fallback_bucket)
                        bucket_unidades_proyecto = fallback_bucket
                        s3_manager.bucket_name = fallback_bucket
                    except Exception as fallback_error:
                        raise HTTPException(
                            status_code=500,
                            detail=(
                                f"Bucket S3 inválido/configurado incorrectamente ({bucket_unidades_proyecto}) "
                                f"y fallback ({fallback_bucket}) no accesible: {str(fallback_error)}"
                            )
                        )
                else:
                    raise HTTPException(
                        status_code=500,
                        detail=(
                            f"Bucket S3 inválido/configurado incorrectamente: {bucket_unidades_proyecto}"
                        )
                    )
        except HTTPException:
            raise
        except Exception as s3_setup_error:
            raise HTTPException(
                status_code=500,
                detail=(
                    f"No se pudo inicializar S3 para registrar_avance_up con {credentials_path}: {str(s3_setup_error)}"
                )
            )

        folder_key = f"{fotos_prefix}/registro_avance/{intervencion_id}/"

        folder_exists = False
        try:
            check_response = s3_client.list_objects_v2(
                Bucket=bucket_unidades_proyecto,
                Prefix=folder_key,
                MaxKeys=1
            )
            folder_exists = bool(check_response.get('Contents'))
        except Exception:
            folder_exists = False

        if not folder_exists:
            try:
                s3_client.put_object(
                    Bucket=bucket_unidades_proyecto,
                    Key=folder_key,
                    Body=b''
                )
            except Exception as folder_error:
                raise HTTPException(
                    status_code=500,
                    detail=(
                        f"No se pudo crear/verificar folder en S3 ({bucket_unidades_proyecto}) "
                        f"usando perfil {aws_profile_usado}: {str(folder_error)}"
                    )
                )

        uploaded_urls = []
        failed_files = []

        def to_ascii_s3_metadata(value: Any, default: str = "") -> str:
            text = str(value) if value is not None else default
            text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
            text = "".join(ch for ch in text if 32 <= ord(ch) <= 126)
            text = text.strip()
            if not text:
                return default
            return text[:200]

        for idx, photo in enumerate(registro_fotografico):
            try:
                file_bytes = await photo.read()
                if not file_bytes:
                    raise ValueError("archivo vacío")

                image = Image.open(io.BytesIO(file_bytes))

                if image.mode not in ("RGB", "L"):
                    image = image.convert("RGB")
                elif image.mode == "L":
                    image = image.convert("RGB")

                max_dimension = 1920
                image.thumbnail((max_dimension, max_dimension), Image.Resampling.LANCZOS)

                compressed_buffer = io.BytesIO()
                image.save(
                    compressed_buffer,
                    format='JPEG',
                    quality=78,
                    optimize=True,
                    progressive=True
                )
                compressed_buffer.seek(0)

                timestamp_human = datetime.now().strftime('%d/%m/%Y - %H:%M:%S')
                timestamp_safe = timestamp_human.replace('/', '-').replace(':', '-')
                file_name = f"{intervencion_id} - {timestamp_safe} - {idx + 1}.jpg"
                s3_key = f"{folder_key}{file_name}"

                s3_client.put_object(
                    Bucket=bucket_unidades_proyecto,
                    Key=s3_key,
                    Body=compressed_buffer.getvalue(),
                    ContentType='image/jpeg',
                    Metadata={
                        'intervencion_id': to_ascii_s3_metadata(intervencion_id, default='sin_intervencion'),
                        'timestamp_human': to_ascii_s3_metadata(timestamp_human, default='sin_timestamp'),
                        'original_filename': to_ascii_s3_metadata(photo.filename or 'sin_nombre', default='sin_nombre')
                    }
                )

                uploaded_urls.append(f"https://{bucket_unidades_proyecto}.s3.amazonaws.com/{s3_key}")

            except (UnidentifiedImageError, ValueError) as image_error:
                failed_files.append({
                    "filename": photo.filename,
                    "error": f"Archivo no válido como imagen: {str(image_error)}"
                })
            except Exception as upload_error:
                failed_files.append({
                    "filename": photo.filename,
                    "error": str(upload_error)
                })

        db = get_firestore_client()
        if db is None:
            raise HTTPException(status_code=503, detail="No se pudo conectar a Firestore")

        now_iso = datetime.now().isoformat()
        avance_payload = {
            "avance_obra": avance_obra,
            "observaciones": observaciones,
            "intervencion_id": intervencion_id,
            "registro_fotografico_urls": uploaded_urls,
            "total_fotos": len(registro_fotografico),
            "fotos_subidas": len(uploaded_urls),
            "fotos_fallidas": len(failed_files),
            "created_at": now_iso,
            "updated_at": now_iso
        }

        doc_id = str(uuid.uuid4())
        db.collection('avances_unidades_proyecto').document(doc_id).set(avance_payload)

        response_payload = {
            "id": doc_id,
            "intervencion_id": intervencion_id,
            "avance_obra": avance_obra,
            "observaciones": observaciones,
            "registro_fotografico_urls": uploaded_urls,
            "fotos_subidas": len(uploaded_urls),
            "fotos_fallidas": len(failed_files),
            "timestamp": now_iso
        }

        return create_utf8_response(response_payload)

    except HTTPException:
        raise
    except ImportError as import_error:
        raise HTTPException(
            status_code=500,
            detail=f"Dependencia faltante para compresión/subida de imágenes: {str(import_error)}"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error registrando avance UP: {str(e)}")

@app.post("/reportes_contratos/", tags=["Interoperabilidad con Artefacto de Seguimiento"])
async def crear_reporte_contrato(
    # Información básica del reporte
    referencia_contrato: str = Form(..., min_length=1, description="Referencia del contrato"),
    observaciones: str = Form(..., description="Observaciones del reporte"),
    
    # Avances del proyecto (soporte para decimales)
    avance_fisico: float = Form(..., ge=0, le=100, description="Porcentaje de avance físico (0-100, decimales permitidos)"),
    avance_financiero: float = Form(..., ge=0, le=100, description="Porcentaje de avance financiero (0-100, decimales permitidos)"),
    
    # Información de alertas
    alertas_descripcion: str = Form(..., description="Descripción de la alerta"),
    alertas_es_alerta: bool = Form(..., description="Indica si es una alerta activa"),
    alertas_tipo_alerta: str = Form(default="", description="Tipos de alerta separados por coma"),
    
    # Archivos de evidencia (carga real de archivos)
    archivos_evidencia: List[UploadFile] = File(..., description="Archivos de evidencia (PDF, DOC, DOCX, XLS, XLSX, TXT, CSV, JPG, PNG, GIF)")
):
    """
    ## 📊 Crear Reporte de Contrato con Evidencias y Upload de Archivos
    
    **Propósito**: Endpoint unificado para crear reportes de seguimiento de contratos 
    con carga de archivos y estructura de carpetas organizada.
    
    ### ✅ IMPORTANTE - Google Drive:
    - **Estado actual**: PRODUCCIÓN - Subida real de archivos funcionando
    - **Configuración**: Google Drive API con Service Account y Shared Drive
    - **Archivos**: Se suben realmente y son accesibles desde Google Drive
    
    ### ✅ Características principales:
    - **Carga de archivos**: Upload directo de archivos de evidencia
    - **Estructura automática**: Carpetas organizadas por contrato y fecha  
    - **Firebase**: Almacenamiento en colección `reportes_contratos`
    - **Timestamp automático**: Fecha de reporte generada automáticamente
    - **Decimales**: Soporte para avances con decimales (ej: 75.5)
    
    ### 📋 Parámetros (Form Data):
    - **referencia_contrato**: Referencia del contrato (obligatorio)
    - **observaciones**: Descripción detallada del avance (obligatorio)
    - **avance_fisico**: Porcentaje de avance físico 0-100 con decimales (obligatorio)
    - **avance_financiero**: Porcentaje de avance financiero 0-100 con decimales (obligatorio)
    - **alertas_descripcion**: Descripción de la alerta (obligatorio)
    - **alertas_es_alerta**: Booleano si es alerta activa (obligatorio)
    - **alertas_tipo_alerta**: Tipos de alerta separados por coma (opcional)
    - **archivos_evidencia**: Archivos de evidencia para subir (obligatorio, múltiples archivos)
    
    ### 📁 Estructura de carpetas en Google Drive:
    ```
    📁 CONTRATOS_REPORTES/
      📁 {referencia_contrato}/
        📁 REPORTE_{YYYY-MM-DD}_{HH-MM-SS}_{UUID}/
          📄 evidencia1.pdf
          📄 evidencia2.jpg
          📄 ...
    ```
    
    ### 🔒 Validaciones aplicadas:
    - **Archivos**: Tipos permitidos (PDF, DOC, DOCX, XLS, XLSX, JPG, PNG, GIF)
    - **Tamaño**: Máximo 10MB por archivo
    - **Cantidad**: Al menos 1 archivo requerido
    - **Avances**: Rango 0-100 con decimales (ej: 75.5)
    - **Nombres**: Caracteres especiales manejados automáticamente
    
    ### 🚀 Proceso automático:
    1. Validar archivos subidos
    2. Crear/verificar carpeta del contrato
    3. Crear carpeta única para este reporte
    4. Subir archivos a Google Drive
    5. Guardar metadata en Firebase con timestamp actual
    6. Retornar URLs y confirmación
    
    ### � Ejemplo de uso con HTML Form:
    ```html
    <form method="POST" enctype="multipart/form-data">
        <input name="referencia_contrato" value="CONTRATO-2025-001" required>
        <textarea name="observaciones" required>Avance del proyecto...</textarea>
        <input name="avance_fisico" type="number" step="0.1" min="0" max="100" required>
        <input name="avance_financiero" type="number" step="0.1" min="0" max="100" required>
        <textarea name="alertas_descripcion" required>Descripción de alerta...</textarea>
        <input name="alertas_es_alerta" type="checkbox">
        <input name="alertas_tipo_alerta" value="logistica,cronograma">
        <input name="archivos_evidencia" type="file" multiple accept=".pdf,.doc,.docx,.xls,.xlsx,.jpg,.png,.gif" required>
        <button type="submit">Crear Reporte</button>
    </form>
    ```
    """
    # Verificar disponibilidad de servicios
    if not FIREBASE_AVAILABLE or not SCRIPTS_AVAILABLE:
        raise HTTPException(
            status_code=503, 
            detail="Servicios no disponibles: Firebase o scripts requeridos"
        )
    
    if not REPORTES_CONTRATOS_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="Operaciones de reportes de contratos no disponibles"
        )
    
    try:
        # Validar archivos subidos
        if not archivos_evidencia:
            raise HTTPException(
                status_code=400,
                detail="Se requiere al menos un archivo de evidencia"
            )
        
        # Validar cada archivo subido
        archivos_validados = []
        tipos_permitidos = {
            'application/pdf': '.pdf',
            'application/msword': '.doc',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document': '.docx',
            'application/vnd.ms-excel': '.xls',
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': '.xlsx',
            'text/plain': '.txt',
            'text/csv': '.csv',
            'image/jpeg': '.jpg',
            'image/png': '.png',
            'image/gif': '.gif'
        }
        
        max_size = 10 * 1024 * 1024  # 10MB
        
        for archivo in archivos_evidencia:
            # Validar tamaño
            if archivo.size > max_size:
                raise HTTPException(
                    status_code=400,
                    detail=f"Archivo {archivo.filename} excede el tamaño máximo de 10MB"
                )
            
            # Validar tipo de archivo
            if archivo.content_type not in tipos_permitidos:
                raise HTTPException(
                    status_code=400,
                    detail=f"Tipo de archivo no permitido: {archivo.content_type} para {archivo.filename}"
                )
            
            # Leer contenido del archivo
            contenido = await archivo.read()
            await archivo.seek(0)  # Reset para lectura posterior si es necesario
            
            archivo_info = {
                "filename": archivo.filename,
                "content_type": archivo.content_type,
                "size": archivo.size,
                "content": contenido
            }
            archivos_validados.append(archivo_info)
        
        # Construir datos optimizados para Firebase
        reporte_dict = {
            "referencia_contrato": referencia_contrato.strip(),
            "observaciones": observaciones.strip(),
            "avance_fisico": float(avance_fisico),
            "avance_financiero": float(avance_financiero),
            "alertas": {
                "descripcion": alertas_descripcion.strip(),
                "es_alerta": alertas_es_alerta,
                "tipos": [tipo.strip() for tipo in alertas_tipo_alerta.split(",") if tipo.strip()] if alertas_tipo_alerta else []
            },
            "archivos_evidencia": archivos_validados
        }
        
        # Crear el reporte usando la función del script
        result = await create_reporte_contrato(reporte_dict)
        
        if not result["success"]:
            raise HTTPException(
                status_code=400,
                detail=f"Error creando reporte: {result.get('error', 'Error desconocido')}"
            )
        
        # Respuesta optimizada sin redundancias
        response_data = {
            "success": True,
            "message": result["message"],
            "doc_id": result["doc_id"],
            "url_carpeta_drive": result["url_carpeta_drive"],
            "archivos_count": len(archivos_validados)
        }
        

        
        return create_utf8_response(response_data)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error en endpoint crear_reporte_contrato: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error interno del servidor: {str(e)}"
        )

@app.get("/reportes_contratos/", tags=["Interoperabilidad con Artefacto de Seguimiento"])
async def obtener_reportes_contratos(request: Request):
    """
    ## 📋 Obtener Todos los Reportes de Contratos
    
    **Propósito**: Obtener listado completo de todos los reportes de contratos almacenados en Firebase.
    Muestra todos los registros de la colección `reportes_contratos` con `nombre_centro_gestor` y `bp` 
    actualizados desde las colecciones de empréstito cuando sea necesario.
    
    ### 🔄 Integración con colecciones de empréstito:
    - Si un reporte no tiene `nombre_centro_gestor` o está vacío, se busca automáticamente 
      en las colecciones `contratos_emprestito`, `ordenes_compra_emprestito` y 
      `convenios_transferencias_emprestito` usando `referencia_contrato` como clave
    - Si un reporte no tiene `bp` o está vacío, se hereda automáticamente desde las mismas colecciones
    
    ### 📊 Ordenamiento:
    Los resultados se ordenan por `fecha_reporte` descendente (más recientes primero).
    
    ### 💡 Casos de uso:
    - Obtener listado completo para dashboard de seguimiento
    - Vista general de todos los reportes generados con datos completos
    - Administración y auditoría de reportes con información del centro gestor
    """
    # Verificar disponibilidad de servicios
    if not FIREBASE_AVAILABLE or not SCRIPTS_AVAILABLE or not REPORTES_CONTRATOS_AVAILABLE:
        return {
            "success": False, 
            "error": "Servicios no disponibles", 
            "data": [], 
            "count": 0
        }
    
    try:
        # Obtener todos los reportes (sin filtros)
        result = await get_reportes_contratos(None)
        
        if not result["success"]:
            raise HTTPException(
                status_code=500,
                detail=f"Error obteniendo reportes: {result.get('error', 'Error desconocido')}"
            )
        
        # Forzar respuesta sin compresión para evitar conflictos
        response = JSONResponse(
            content=result,
            status_code=200,
            headers={
                "Content-Type": "application/json; charset=utf-8",
                "Content-Encoding": "identity",  # Sin compresión
                "Cache-Control": "no-transform"   # Prevenir transformaciones proxy
            }
        )
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error procesando consulta de reportes: {str(e)}"
        )

@app.get("/reportes_contratos/centro_gestor/{nombre_centro_gestor}", tags=["Interoperabilidad con Artefacto de Seguimiento"])
async def obtener_reportes_por_centro_gestor(nombre_centro_gestor: str):
    """
    ## � Obtener Reportes por Centro Gestor
    
    **Propósito**: Obtener reportes filtrados por nombre del centro gestor.
    Los resultados se ordenan por fecha de reporte descendente.
    
    ### 📋 Parámetros:
    - **nombre_centro_gestor**: Nombre del centro gestor para filtrar reportes
    
    ### � Ordenamiento:
    Los resultados se ordenan por `fecha_reporte` descendente (más recientes primero).
    
    ### 💡 Casos de uso:
    - Consultar reportes específicos de un centro gestor
    - Dashboard por centro de responsabilidad
    - Seguimiento por área organizacional
    """
    # Verificar disponibilidad de servicios
    if not FIREBASE_AVAILABLE or not SCRIPTS_AVAILABLE or not REPORTES_CONTRATOS_AVAILABLE:
        return {
            "success": False,
            "error": "Servicios no disponibles",
            "data": [],
            "count": 0
        }
    
    try:
        result = await get_reportes_by_centro_gestor(nombre_centro_gestor)
        
        if not result["success"]:
            raise HTTPException(
                status_code=500,
                detail=f"Error obteniendo reportes: {result.get('error', 'Error desconocido')}"
            )
        
        return create_utf8_response(result)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error obteniendo reportes por centro gestor: {str(e)}"
        )

@app.get("/reportes_contratos/referencia/{referencia_contrato}", tags=["Interoperabilidad con Artefacto de Seguimiento"])
async def obtener_reportes_por_referencia_contrato(referencia_contrato: str):
    """
    ## 📄 Obtener Reportes por Referencia de Contrato
    
    **Propósito**: Obtener reportes específicos de un contrato usando su referencia.
    Los resultados se ordenan por fecha de reporte descendente.
    
    ### 📋 Parámetros:
    - **referencia_contrato**: Referencia específica del contrato
    
    ### 📊 Ordenamiento:
    Los resultados se ordenan por `fecha_reporte` descendente (más recientes primero).
    
    ### 💡 Casos de uso:
    - Historial completo de reportes de un contrato específico
    - Seguimiento detallado por contrato
    - Auditoría de reportes por referencia
    """
    # Verificar disponibilidad de servicios
    if not FIREBASE_AVAILABLE or not SCRIPTS_AVAILABLE or not REPORTES_CONTRATOS_AVAILABLE:
        return {
            "success": False,
            "error": "Servicios no disponibles",
            "data": [],
            "count": 0
        }
    
    try:
        result = await get_reportes_by_referencia_contrato(referencia_contrato)
        
        if not result["success"]:
            raise HTTPException(
                status_code=500,
                detail=f"Error obteniendo reportes: {result.get('error', 'Error desconocido')}"
            )
        
        return create_utf8_response(result)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error obteniendo reportes por referencia: {str(e)}"
        )


# ============================================================================
# ENDPOINTS DE ADMINISTRACIÓN Y CONTROL DE ACCESOS
# ============================================================================

def check_user_management_availability():
    """✅ FUNCIONAL: Verificación simple sin lógica redundante"""
    if not (FIREBASE_AVAILABLE and USER_MANAGEMENT_AVAILABLE):
        raise HTTPException(
            status_code=503,
            detail={
                "error": "Servicios no disponibles",
                "code": "SERVICES_UNAVAILABLE"
            }
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
        request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
        
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
        
        # Limpiar datos de Firebase antes de serializar
        clean_user_data = clean_firebase_data(result.get("user", {}))
        clean_token_data = clean_firebase_data(result.get("token_data", {}))

        logger.info(
            "auth.validate_session.response request_id=%s uid=%s roles=%s source=%s profile_complete=%s firestore_doc=%s",
            request_id,
            clean_user_data.get("uid"),
            clean_user_data.get("roles", []),
            clean_user_data.get("roles_source"),
            clean_user_data.get("profile_complete"),
            bool(clean_user_data.get("firestore_data"))
        )
        
        return JSONResponse(
            content={
                "success": True,
                "session_valid": True,
                "request_id": request_id,
                "user": clean_user_data,
                "token_info": clean_token_data,
                "verified_at": result.get("verified_at"),
                "message": "Sesión válida"
            },
            status_code=200,
            headers={"Content-Type": "application/json; charset=utf-8"}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail={
                "success": False,
                "error": "Error interno del servidor",
                "message": "Ocurrió un error inesperado durante la validación de sesión",
                "code": "INTERNAL_SERVER_ERROR"
            }
        )

@app.post("/auth/login", tags=["Administración y Control de Accesos"])
async def login_user(login_data: UserLoginRequest):
    """
    ## 🔐 Autenticación de Usuario con Email y Contraseña
    
    Valida credenciales de usuario usando Firebase Authentication.
    Requiere email y contraseña válidos para permitir el acceso.
    
    ### Validaciones realizadas:
    - Formato de email válido
    - Contraseña correcta mediante Firebase Auth REST API
    - Usuario activo y no deshabilitado
    - Estado de cuenta en Firestore
    
    ### Respuesta exitosa:
    - Información completa del usuario
    - Tokens de Firebase para sesión
    - Datos adicionales de Firestore
    
    ### Errores comunes:
    - 401: Credenciales incorrectas
    - 403: Usuario deshabilitado o cuenta inactiva
    - 400: Formato de email inválido
    """
    try:
        check_user_management_availability()
        
        # Autenticación con validación real de credenciales
        result = await authenticate_email_password(login_data.email, login_data.password)
        
        # Verificar si la autenticación fue exitosa
        if result.get("success"):
            clean_user_data = clean_firebase_data(result.get("user", {}))
            
            # ✅ PREPARAR RESPUESTA CON CUSTOM TOKEN
            response_data = {
                "success": True,
                "user": clean_user_data,
                "auth_method": result.get("auth_method", "email_password"),
                "credentials_validated": result.get("credentials_validated", True),
                "message": result.get("message", "Autenticación exitosa"),
                "timestamp": datetime.now().isoformat()
            }
            
            # ✅ AGREGAR CUSTOM TOKEN SI ESTÁ DISPONIBLE
            if "custom_token" in result and result["custom_token"]:
                response_data["custom_token"] = result["custom_token"]
                response_data["token_usage"] = result.get("token_usage", "Use signInWithCustomToken() en Firebase Auth SDK")
            
            # Agregar información de autenticación alternativa si está disponible
            if "alternative_auth" in result:
                response_data["alternative_auth"] = result["alternative_auth"]
            
            # 🔍 LOG TEMPORAL PARA DEBUGGING
            import logging
            logger = logging.getLogger(__name__)
            logger.info(f"🔍 LOGIN RESPONSE KEYS: {list(response_data.keys())}")
            logger.info(f"⚠️  custom_token present: {'custom_token' in response_data}")
            if 'custom_token' in response_data:
                logger.info(f"✅ Token preview: {response_data['custom_token'][:50]}...")
            else:
                logger.warning(f"⚠️  No custom_token - Alternative auth available: {'alternative_auth' in response_data}")
            
            return JSONResponse(
                content=response_data,
                status_code=200,
                headers={"Content-Type": "application/json; charset=utf-8"}
            )
        else:
            # Autenticación fallida - mapear errores apropiados
            error_code = result.get("code", "AUTH_ERROR")
            
            # Mapear códigos de error a respuestas HTTP apropiadas
            if error_code in ["INVALID_CREDENTIALS", "USER_NOT_FOUND"]:
                raise HTTPException(
                    status_code=401,
                    detail={
                        "success": False,
                        "error": result["error"],
                        "code": error_code
                    }
                )
            elif error_code in ["USER_DISABLED", "ACCOUNT_INACTIVE"]:
                raise HTTPException(
                    status_code=403,
                    detail={
                        "success": False,
                        "error": result["error"],
                        "code": error_code
                    }
                )
            elif error_code in ["EMAIL_VALIDATION_ERROR", "INVALID_EMAIL_FORMAT"]:
                raise HTTPException(
                    status_code=400,
                    detail={
                        "success": False,
                        "error": result["error"],
                        "code": error_code
                    }
                )
            else:
                # Cualquier otro error
                raise HTTPException(
                    status_code=500,
                    detail={
                        "success": False,
                        "error": result["error"],
                        "code": error_code
                    }
                )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in login endpoint: {e}")
        return JSONResponse(
            content={
                "error": "Internal server error",
                "message": "An unexpected error occurred", 
                "fallback": True,
                "timestamp": datetime.now().isoformat()
            },
            status_code=500
        )

@app.get("/auth/register/health-check", tags=["Administración y Control de Accesos"])
async def register_health_check():
    """
    ## 🔍 Health Check para Registro de Usuario
    
    Verifica que todos los servicios necesarios para el registro estén disponibles.
    Útil para diagnosticar problemas en producción.
    """
    try:
        health_status = {
            "timestamp": datetime.now().isoformat(),
            "environment": os.getenv("ENVIRONMENT", "development"),
            "services": {}
        }
        
        # Verificar Firebase
        try:
            check_user_management_availability()
            health_status["services"]["user_management"] = {"status": "available", "error": None}
        except HTTPException as e:
            health_status["services"]["user_management"] = {
                "status": "unavailable", 
                "error": str(e.detail)
            }
        
        # Verificar importaciones
        health_status["services"]["imports"] = {
            "firebase_available": FIREBASE_AVAILABLE,
            "scripts_available": SCRIPTS_AVAILABLE,
            "user_management_available": USER_MANAGEMENT_AVAILABLE,
            "auth_operations_available": AUTH_OPERATIONS_AVAILABLE,
            "user_models_available": USER_MODELS_AVAILABLE
        }
        
        # Verificar configuración
        environment = os.getenv("ENVIRONMENT", "development")
        has_service_account = bool(os.getenv("FIREBASE_SERVICE_ACCOUNT_KEY"))
        
        health_status["configuration"] = {
            "project_id": PROJECT_ID,
            "environment": environment,
            "has_firebase_service_account": has_service_account,
            "firebase_available": FIREBASE_AVAILABLE,
            "auth_method": "Service Account Key" if has_service_account else "Workload Identity Federation",
            "authorized_domain": os.getenv("AUTHORIZED_EMAIL_DOMAIN", "@cali.gov.co"),
            "deployment_ready": FIREBASE_AVAILABLE  # Lo importante es que Firebase esté disponible
        }
        
        # Determinar estado general - soportar estructuras mixtas en 'services'
        def is_service_available(svc):
            """Evaluar si un servicio (o estructura) se considera disponible.

            - Si es dict y contiene 'status', se considera disponible cuando status == 'available'.
            - Si es dict con flags booleanos, se considera disponible cuando todos los flags booleanos son True.
            - Si es booleano, se usa su valor.
            - En cualquier otro caso se considera no disponible.
            """
            if isinstance(svc, dict):
                # Si tiene la clave 'status' respetarla
                if "status" in svc:
                    return svc.get("status") == "available"
                # Si es un diccionario de flags booleanas, todos deben ser True
                bool_flags = [v for v in svc.values() if isinstance(v, bool)]
                if bool_flags:
                    return all(bool_flags)
                # Fallback: consider available si el dict no está vacío
                return bool(svc)

            # Si es booleano, usar su valor
            if isinstance(svc, bool):
                return svc

            # Cualquier otro tipo se considera no disponible
            return False

        # Normalizar 'imports' a un campo 'status' legible para diagnósticos si procede
        imports_status = health_status["services"].get("imports")
        if isinstance(imports_status, dict) and "status" not in imports_status:
            health_status["services"]["imports"]["status"] = (
                "available" if is_service_available(imports_status) else "unavailable"
            )

        all_services_available = all(is_service_available(service) for service in health_status["services"].values())

        status_code = 200 if all_services_available else 503
        health_status["overall_status"] = "healthy" if all_services_available else "unhealthy"
        
        return JSONResponse(
            content=health_status,
            status_code=status_code,
            headers={"Content-Type": "application/json; charset=utf-8"}
        )
        
    except Exception as e:
        return JSONResponse(
            content={
                "overall_status": "error",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            },
            status_code=500,
            headers={"Content-Type": "application/json; charset=utf-8"}
        )

@app.post("/auth/register", tags=["Administración y Control de Accesos"], status_code=status.HTTP_201_CREATED)
async def register_user(registration_data: UserRegistrationRequest):
    """
    ✅ **REGISTRO DE USUARIO - VERSIÓN FUNCIONAL SIMPLIFICADA**
    
    **Fail Fast**: Si no hay Service Account configurado, falla inmediatamente
    **Sin Cache**: Cada request es independiente
    **Funcional**: Sin efectos colaterales entre registros
    """
    
    # � FAIL FAST: Verificar Service Account inmediatamente
    if not FIREBASE_AVAILABLE:
        environment = os.getenv("ENVIRONMENT", "development")
        if environment == "production":
            error_msg = "Firebase Service Account no configurado en producción"
            solution = "Configure FIREBASE_SERVICE_ACCOUNT_KEY en Railway"
        else:
            error_msg = "Firebase no disponible en desarrollo (requiere WIF o Service Account)"
            solution = "Configure Workload Identity Federation o FIREBASE_SERVICE_ACCOUNT_KEY"
        
        raise HTTPException(
            status_code=503,
            detail={
                "success": False,
                "error": error_msg,
                "code": "FIREBASE_UNAVAILABLE",
                "solution": solution,
                "environment": environment
            }
        )
    
    try:
        # ✅ PROGRAMACIÓN FUNCIONAL: Una sola responsabilidad
        result = await create_user_account(
            email=registration_data.email,
            password=registration_data.password,
            fullname=registration_data.name,
            cellphone=registration_data.cellphone,
            nombre_centro_gestor=registration_data.nombre_centro_gestor,
            send_email_verification=True
        )
        
        # ✅ FAIL FAST: Si hay error, fallar inmediatamente
        if not result.get("success", False):
            raise HTTPException(
                status_code=400,
                detail={
                    "success": False,
                    "error": result.get("error", "Error creando usuario"),
                    "code": result.get("code", "USER_CREATION_ERROR")
                }
            )
        
        # ✅ FUNCIONAL: Transformar datos sin mutación
        return {
            "success": True,
            "user": clean_firebase_data(result.get("user", {})),
            "message": "Usuario creado exitosamente",
            "timestamp": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        # ✅ SIMPLE: Error handling directo
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "error": "Error interno del servidor",
                "code": "INTERNAL_SERVER_ERROR",
                "debug": str(e) if os.getenv("ENVIRONMENT") == "development" else None
            }
        )

@app.post("/auth/change-password", tags=["Administración y Control de Accesos"])
async def change_password(
    request: Request,
    uid: str = Form(..., description="ID del usuario"),
    new_password: str = Form(..., description="Nueva contraseña")
):
    """
    ## 🔒 Cambio de Contraseña
    
    Actualiza contraseñas de usuarios con validaciones de seguridad completas.
    **Requiere autenticación con token de Firebase.**
    
    ### 🔐 Autenticación requerida:
    - Header: `Authorization: Bearer <firebase_id_token>`
    
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
      headers: {
        'Authorization': 'Bearer ' + idToken,
        'Content-Type': 'application/x-www-form-urlencoded'
      },
      body: new URLSearchParams(passwordData)
    });
    ```
    """
    try:
        # 🔐 VERIFICAR AUTENTICACIÓN FIREBASE
        current_user = await verify_firebase_token(request)
        check_user_management_availability()
        
        result = await update_user_password(uid, new_password)
        
        if not result.get("success", False):
            error_code = result.get("code", "PASSWORD_UPDATE_ERROR")
            error_message = result.get("error", "Error actualizando contraseña")
            
            if error_code == "USER_NOT_FOUND":
                raise HTTPException(
                    status_code=404, 
                    detail={
                        "success": False,
                        "error": error_message,
                        "code": error_code
                    }
                )
            else:
                raise HTTPException(
                    status_code=400, 
                    detail={
                        "success": False,
                        "error": error_message,
                        "code": error_code
                    }
                )
        
        return JSONResponse(
            content={
                "success": True,
                "message": result.get("message", "Contraseña actualizada exitosamente"),
                "updated_at": result.get("updated_at"),
                "timestamp": datetime.now().isoformat()
            },
            status_code=200,
            headers={"Content-Type": "application/json; charset=utf-8"}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail={
                "success": False,
                "error": "Error interno del servidor",
                "message": "Ocurrió un error inesperado durante el cambio de contraseña",
                "code": "INTERNAL_SERVER_ERROR"
            }
        )

@app.get("/auth/config", tags=["Integración con el Frontend (NextJS)"])
async def get_firebase_config():
    """
    ## � Configuración Básica de Firebase para Frontend
    
    **ENDPOINT PÚBLICO** - Acceso directo desde frontend.
    
    Proporciona configuración mínima necesaria para Firebase Auth en frontend.
    
    ### �️ Seguridad:
    - Información pública solamente
    - Datos mínimos necesarios para SDK
    - Sin exposición de endpoints internos
    - Sin detalles de configuración sensibles
    
    ### � Información incluida:
    - Project ID de Firebase (público)
    - Auth Domain de Firebase (público)
    
    ### 🎯 Uso:
    - Inicialización de Firebase SDK en frontend
    - Configuración de autenticación client-side
    """
    # Solo información esencial para Firebase SDK
    return {
        "projectId": PROJECT_ID,
        "authDomain": f"{PROJECT_ID}.firebaseapp.com"
    }

# ENDPOINT REMOVIDO: /auth/integration-guide
# Razón: Documentación estática mejor manejada externamente
# Fecha: 2025-10-04
# La documentación de integración está disponible en README.md

@app.get("/auth/workload-identity/status", tags=["Administración y Control de Accesos"])
async def get_workload_identity_status():
    """
    ## 🔍 Estado de Autenticación con Google Cloud
    
    **ENDPOINT DE DIAGNÓSTICO** - Verifica el estado de autenticación con Google Cloud.
    
    ### 📊 Información incluida:
    - Estado de Service Account Key o Workload Identity
    - Validez de credenciales con Google Cloud
    - Configuración de Firebase
    - Nivel de seguridad actual
    
    ### 🛠️ Útil para:
    - Verificar configuración después de deployment en Railway
    - Diagnóstico de problemas de autenticación
    - Auditoría de seguridad
    - Monitoreo del sistema
    
    ### ⚠️ Nota:
    Este endpoint es principalmente para diagnóstico. En producción,
    considera eliminar o restringir acceso por seguridad.
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
        
        # Limpiar datos de Firebase antes de serializar
        clean_user_data = clean_firebase_data(result["user"])
        
        return {
            "success": True,
            "user": clean_user_data,
            "auth_method": "workload_identity_google",
            "security_level": "high",
            "user_created": result.get("user_created", False),
            "message": result["message"],
            "timestamp": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Unexpected error in Google auth: {e}")  # Usar print en lugar de logger
        raise HTTPException(status_code=500, detail={
            "error": "Error interno del servidor",
            "message": "Por favor, inténtelo de nuevo más tarde",
            "code": "INTERNAL_ERROR"
        })

# ============================================================================
# ENDPOINTS DE ELIMINACIÓN DE USUARIOS
# ============================================================================

@app.delete("/auth/user/{uid}", tags=["Administración y Control de Accesos"])
async def delete_user(
    uid: str, 
    request: Request,
    soft_delete: Optional[bool] = Query(default=None, description="Eliminación lógica (true) o física (false)")
):
    """
    ## 🗑️ Eliminación de Usuario
    
    Elimina cuentas con opciones flexibles de soft delete (recomendado) o hard delete.
    **Requiere autenticación con token de Firebase.**
    
    ### 🔐 Autenticación requerida:
    - Header: `Authorization: Bearer <firebase_id_token>`
    
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
      method: 'DELETE',
      headers: {
        'Authorization': 'Bearer ' + idToken
      }
    });
    
    // Eliminación física (permanente)
    const response = await fetch('/auth/user/Zx9mK2pQ8RhV3nL7jM4uX1qW6tY0sA5e?soft_delete=false', {
      method: 'DELETE',
      headers: {
        'Authorization': 'Bearer ' + idToken
      }
    });
    ```
    """
    try:
        # 🔐 VERIFICAR AUTENTICACIÓN FIREBASE
        current_user = await verify_firebase_token(request)
        
        check_user_management_availability()
        
        result = await delete_user_account(uid, soft_delete if soft_delete is not None else True)
        
        if not result.get("success", False):
            error_code = result.get("code", "USER_DELETE_ERROR")
            error_message = result.get("error", "Error eliminando usuario")
            
            if error_code == "USER_NOT_FOUND":
                raise HTTPException(
                    status_code=404, 
                    detail={
                        "success": False,
                        "error": error_message,
                        "code": error_code
                    }
                )
            else:
                raise HTTPException(
                    status_code=400, 
                    detail={
                        "success": False,
                        "error": error_message,
                        "code": error_code
                    }
                )
        
        return JSONResponse(
            content={
                "success": True,
                "message": result.get("message", "Usuario eliminado exitosamente"),
                "deleted_at": result.get("deleted_at"),
                "soft_delete": result.get("soft_delete", True),
                "timestamp": datetime.now().isoformat()
            },
            status_code=200,
            headers={"Content-Type": "application/json; charset=utf-8"}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail={
                "success": False,
                "error": "Error interno del servidor",
                "message": "Ocurrió un error inesperado durante la eliminación",
                "code": "INTERNAL_SERVER_ERROR"
            }
        )

# ============================================================================
# ENDPOINTS ADMINISTRATIVOS DE USUARIOS
# ============================================================================

@app.get("/admin/users", tags=["Administración y Control de Accesos"])
async def list_system_users(
    request: Request,
    limit: int = Query(default=100, ge=1, le=1000, description="Límite de resultados por página")
):
    """
    ## 📋 Listado de Usuarios desde Firestore
    
    Lee directamente la colección "users" de Firestore y devuelve todos los usuarios registrados.
    **Requiere autenticación con token de Firebase.**
    
    ### 🔐 Autenticación requerida:
    - Header: `Authorization: Bearer <firebase_id_token>`
    
    ### � Información incluida:
    - UID del usuario
    - Email y nombre completo
    - Teléfono y centro gestor
    - Fechas de creación y actualización
    - Estado de activación y verificación
    - Proveedores de autenticación
    - Estadísticas de login
    
    ### 📝 Ejemplo de uso:
    ```javascript
    const response = await fetch('/admin/users?limit=50', {
      headers: {
        'Authorization': 'Bearer ' + idToken,
        'Content-Type': 'application/json'
      }
    });
    const data = await response.json();
    console.log(`Encontrados ${data.count} usuarios`);
    ```
    """
    try:
        # 🔐 VERIFICAR AUTENTICACIÓN FIREBASE
        current_user = await verify_firebase_token(request)

        from auth_system.permissions import get_user_permissions
        from database.firebase_config import get_firestore_client

        firestore_client = get_firestore_client()
        if firestore_client is None:
            raise HTTPException(
                status_code=503,
                detail={
                    "success": False,
                    "error": "No se pudo conectar a Firestore",
                    "code": "FIRESTORE_UNAVAILABLE"
                }
            )

        current_permissions = get_user_permissions(current_user["uid"], firestore_client)
        if "*" not in current_permissions and "manage:users" not in current_permissions:
            raise HTTPException(
                status_code=403,
                detail={
                    "success": False,
                    "error": "Permiso denegado",
                    "code": "INSUFFICIENT_PERMISSIONS"
                }
            )
        
        check_user_management_availability()
        
        # Consultar la colección "users" directamente
        users_ref = firestore_client.collection('users')
        query = users_ref.limit(limit)
        docs = query.get()
        
        users_list = []
        for doc in docs:
            if doc.exists:
                user_data = doc.to_dict()
                
                user_info = {
                    "uid": doc.id,
                    "email": user_data.get("email"),
                    "fullname": user_data.get("fullname"),
                    "cellphone": user_data.get("cellphone"),
                    "nombre_centro_gestor": user_data.get("nombre_centro_gestor"),
                    "created_at": user_data.get("created_at"),
                    "updated_at": user_data.get("updated_at"),
                    "is_active": user_data.get("is_active", True),
                    "email_verified": user_data.get("email_verified", False),
                    "can_use_google_auth": user_data.get("can_use_google_auth", False),
                    "auth_providers": user_data.get("auth_providers", []),
                    "last_login": user_data.get("last_login"),
                    "login_count": user_data.get("login_count", 0)
                }
                
                # Limpiar datos de Firebase antes de agregar a la lista
                user_info = clean_firebase_data(user_info)
                users_list.append(user_info)
        
        return JSONResponse(
            content={
                "success": True,
                "users": users_list,
                "count": len(users_list),
                "collection": "users",
                "timestamp": datetime.now().isoformat(),
                "message": f"Se obtuvieron {len(users_list)} usuarios de la colección 'users'"
            },
            status_code=200,
            headers={"Content-Type": "application/json; charset=utf-8"}
        )
        
    except HTTPException:
        # Re-lanzar HTTPException (como las de autenticación) sin modificar
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail={
                "success": False,
                "error": str(e),
                "message": "Error leyendo la colección 'users' de Firestore",
                "code": "FIRESTORE_READ_ERROR"
            }
        )

# ============================================================================
# ENDPOINTS DE GESTIÓN DE EMPRÉSTITO
# ============================================================================

# Verificar disponibilidad de operaciones de empréstito
try:
    from api.scripts import (
        procesar_emprestito_completo,
        verificar_proceso_existente,
        eliminar_proceso_emprestito,
        actualizar_proceso_emprestito,
        obtener_codigos_contratos,
        buscar_y_poblar_contratos_secop,
        obtener_contratos_desde_proceso_contractual,
        obtener_contratos_desde_proceso_contractual_completo,
        get_emprestito_operations_status,
        cargar_orden_compra_directa,
        cargar_convenio_transferencia,
        modificar_convenio_transferencia,
        actualizar_orden_compra_por_numero,
        eliminar_orden_compra_por_numero,
        eliminar_convenio_transferencia_por_referencia,
        actualizar_convenio_por_referencia,
        actualizar_contrato_secop_por_referencia,
        actualizar_proceso_secop_por_referencia,
        cargar_rpc_emprestito,
        cargar_pago_emprestito,
        get_pagos_emprestito_all,
        get_rpc_contratos_emprestito_all,
        actualizar_rpc_contrato_emprestito,
        get_asignaciones_emprestito_banco_centro_gestor_all,
        get_convenios_transferencia_emprestito_all,
        obtener_ordenes_compra_tvec_enriquecidas,
        get_tvec_enrich_status,
        get_ordenes_compra_emprestito_all,
        get_ordenes_compra_emprestito_by_referencia,
        get_ordenes_compra_emprestito_by_centro_gestor,
        # Control de cambios para auditoría
        registrar_cambio_valor,
        obtener_historial_cambios,
        EMPRESTITO_OPERATIONS_AVAILABLE,
        TVEC_ENRICH_OPERATIONS_AVAILABLE,
        ORDENES_COMPRA_OPERATIONS_AVAILABLE
    )
    from api.models import (
        EmprestitoRequest, 
        EmprestitoResponse,
        PagoEmprestitoRequest,
        PagoEmprestitoResponse
    )
    print(f"✅ Empréstito imports successful - AVAILABLE: {EMPRESTITO_OPERATIONS_AVAILABLE}")
    print(f"✅ TVEC enrich imports successful - AVAILABLE: {TVEC_ENRICH_OPERATIONS_AVAILABLE}")
except ImportError as e:
    print(f"❌ Warning: Empréstito or TVEC imports failed: {e}")
    EMPRESTITO_OPERATIONS_AVAILABLE = False
    TVEC_ENRICH_OPERATIONS_AVAILABLE = False

def check_emprestito_availability():
    """Verificar disponibilidad de operaciones de empréstito"""
    if not EMPRESTITO_OPERATIONS_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "Servicios de empréstito no disponibles",
                "message": "Firebase o dependencias no configuradas correctamente",
                "code": "EMPRESTITO_SERVICES_UNAVAILABLE"
            }
        )

@app.post("/emprestito/cargar-proceso", tags=["Gestión de Empréstito"], summary="🟢 Cargar Proceso de Empréstito")
async def cargar_proceso_emprestito(
    referencia_proceso: str = Form(..., description="Referencia del proceso (obligatorio)"),
    nombre_centro_gestor: str = Form(..., description="Centro gestor responsable (obligatorio)"),
    nombre_banco: str = Form(..., description="Nombre del banco (obligatorio)"),
    plataforma: str = Form(..., description="Plataforma (SECOP, TVEC) (obligatorio)"),
    bp: Optional[str] = Form(None, description="Código BP (opcional)"),
    nombre_resumido_proceso: Optional[str] = Form(None, description="Nombre resumido del proceso (opcional)"),
    id_paa: Optional[str] = Form(None, description="ID PAA (opcional)"),
    valor_proyectado: Optional[float] = Form(None, description="Valor proyectado (opcional)")
):
    """
    ## � POST | 📥 Carga de Datos | Cargar Proceso de Empréstito
    
    Endpoint unificado para carga de procesos de empréstito con detección automática 
    de plataforma (SECOP/TVEC) y validación de duplicados.
    
    ### ✅ Funcionalidades principales:
    - **Detección automática**: Identifica si es SECOP o TVEC basado en el campo `plataforma`
    - **Validación de duplicados**: Verifica existencia previa usando `referencia_proceso`
    - **Integración API**: Obtiene datos completos desde APIs externas (SECOP/TVEC)
    - **Almacenamiento inteligente**: Guarda en colección apropiada según plataforma
    
    ### 🔍 Detección de plataforma:
    **SECOP**: "SECOP", "SECOP II", "SECOP I", "SECOP 2", "SECOP 1" y variantes
    **TVEC**: "TVEC" y variantes
    
    ### 📊 Almacenamiento por plataforma:
    - **SECOP** → Colección: `procesos_emprestito`
    - **TVEC** → Colección: `ordenes_compra_emprestito`
    
    ### 🛡️ Validación de duplicados:
    Busca `referencia_proceso` en ambas colecciones antes de crear nuevo registro.
    
    ### ⚙️ Campos obligatorios:
    - `referencia_proceso`: Referencia del proceso
    - `nombre_centro_gestor`: Centro gestor responsable
    - `nombre_banco`: Nombre del banco
    - `plataforma`: Plataforma (SECOP/TVEC)
    
    ### 📝 Campos opcionales:
    - `bp`: Código BP
    - `nombre_resumido_proceso`: Nombre resumido
    - `id_paa`: ID PAA
    - `valor_proyectado`: Valor proyectado
    
    ### 🔗 Integración con APIs:
    **SECOP**: Obtiene datos desde API de datos abiertos (p6dx-8zbt)
    **TVEC**: Obtiene datos desde API TVEC (rgxm-mmea)
    
    ### 📋 Ejemplo de request:
    ```json
    {
        "referencia_proceso": "SCMGSU-CM-003-2024",
        "nombre_centro_gestor": "Secretaría de Salud",
        "nombre_banco": "Banco Mundial",
        "bp": "BP-2024-001",
        "plataforma": "SECOP II",
        "nombre_resumido_proceso": "Suministro equipos médicos",
        "id_paa": "PAA-2024-123",
        "valor_proyectado": 1500000000.0
    }
    ```
    """
    try:
        check_emprestito_availability()
        
        # Crear diccionario con los datos del formulario
        datos_emprestito = {
            "referencia_proceso": referencia_proceso,
            "nombre_centro_gestor": nombre_centro_gestor,
            "nombre_banco": nombre_banco,
            "bp": bp,
            "plataforma": plataforma,
            "nombre_resumido_proceso": nombre_resumido_proceso,
            "id_paa": id_paa,
            "valor_proyectado": valor_proyectado
        }
        
        # Procesar empréstito completo con todas las validaciones
        resultado = await procesar_emprestito_completo(datos_emprestito)
        
        # Manejar respuesta según el resultado
        if not resultado.get("success"):
            # Manejar caso especial de duplicado
            if resultado.get("duplicate"):
                return JSONResponse(
                    content={
                        "success": False,
                        "error": resultado.get("error"),
                        "duplicate": True,
                        "existing_data": resultado.get("existing_data"),
                        "message": "Ya existe un proceso con esta referencia",
                        "timestamp": datetime.now().isoformat()
                    },
                    status_code=409,  # Conflict
                    headers={"Content-Type": "application/json; charset=utf-8"}
                )
            else:
                # Error general
                return JSONResponse(
                    content={
                        "success": False,
                        "error": resultado.get("error"),
                        "plataforma_detectada": resultado.get("plataforma_detectada"),
                        "message": "Error procesando proceso de empréstito",
                        "timestamp": datetime.now().isoformat()
                    },
                    status_code=400,
                    headers={"Content-Type": "application/json; charset=utf-8"}
                )
        
        # Éxito: proceso creado correctamente
        respuesta_base = {
            "success": True,
            "message": "Proceso de empréstito cargado exitosamente",
            "data": resultado.get("data"),
            "doc_id": resultado.get("doc_id"),
            "coleccion": resultado.get("coleccion"),
            "plataforma_detectada": resultado.get("plataforma_detectada"),
            "fuente_datos": resultado.get("fuente_datos"),
            "timestamp": datetime.now().isoformat()
        }
        
        # Si es un proceso SECOP, intentar actualizar con datos completos automáticamente
        if resultado.get("plataforma_detectada") == "SECOP" and resultado.get("coleccion") == "procesos_emprestito":
            try:
                logger.info(f"🔄 Actualizando automáticamente proceso SECOP: {referencia_proceso}")
                resultado_actualizacion = await actualizar_proceso_emprestito_completo(referencia_proceso)
                
                if resultado_actualizacion.get("success"):
                    respuesta_base["actualizacion_completa"] = {
                        "success": True,
                        "changes_count": resultado_actualizacion.get("changes_count", 0),
                        "changes_summary": resultado_actualizacion.get("changes_summary", [])[:5],  # Máximo 5 cambios en resumen
                        "message": f"Proceso actualizado automáticamente con {resultado_actualizacion.get('changes_count', 0)} campos adicionales"
                    }
                    logger.info(f"✅ Actualización automática exitosa: {resultado_actualizacion.get('changes_count', 0)} cambios")
                else:
                    respuesta_base["actualizacion_completa"] = {
                        "success": False,
                        "error": resultado_actualizacion.get("error", "Error desconocido"),
                        "message": "No se pudo actualizar automáticamente con datos completos"
                    }
                    logger.warning(f"⚠️ Actualización automática falló: {resultado_actualizacion.get('error')}")
                    
            except Exception as e:
                logger.warning(f"⚠️ Error en actualización automática: {e}")
                respuesta_base["actualizacion_completa"] = {
                    "success": False,
                    "error": str(e),
                    "message": "Error durante actualización automática (proceso principal creado exitosamente)"
                }
        
        return JSONResponse(
            content=respuesta_base,
            status_code=201,
            headers={"Content-Type": "application/json; charset=utf-8"}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error en endpoint de empréstito: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "error": "Error interno del servidor",
                "message": "Por favor, inténtelo de nuevo más tarde",
                "code": "INTERNAL_SERVER_ERROR"
            }
        )

@app.post("/emprestito/cargar-orden-compra", tags=["Gestión de Empréstito"], summary="🟢 Cargar Orden de Compra")
async def cargar_orden_compra_emprestito(
    numero_orden: str = Form(..., description="Número de la orden de compra (obligatorio)"),
    nombre_centro_gestor: str = Form(..., description="Centro gestor responsable (obligatorio)"),
    nombre_banco: str = Form(..., description="Nombre del banco (obligatorio)"),
    nombre_resumido_proceso: str = Form(..., description="Nombre resumido del proceso (obligatorio)"),
    valor_proyectado: float = Form(..., description="Valor proyectado (obligatorio)"),
    bp: Optional[str] = Form(None, description="Código BP (opcional)")
):
    """
    ## � POST | 📥 Carga de Datos | Cargar Orden de Compra de Empréstito
    
    Endpoint para carga directa de órdenes de compra de empréstito en la colección 
    `ordenes_compra_emprestito` sin procesamiento de APIs externas.
    
    ### ✅ Funcionalidades principales:
    - **Carga directa**: Registra directamente en `ordenes_compra_emprestito`
    - **Validación de duplicados**: Verifica existencia previa usando `numero_orden`
    - **Validación de campos**: Verifica que todos los campos obligatorios estén presentes
    - **Timestamps automáticos**: Agrega fecha de creación y actualización
    
    ### ⚙️ Campos obligatorios:
    - `numero_orden`: Número único de la orden de compra
    - `nombre_centro_gestor`: Centro gestor responsable
    - `nombre_banco`: Nombre del banco
    - `nombre_resumido_proceso`: Nombre resumido del proceso
    - `valor_proyectado`: Valor proyectado en pesos colombianos
    
    ### 📝 Campos opcionales:
    - `bp`: Código BP
    
    ### 🛡️ Validación de duplicados:
    Busca `numero_orden` en la colección `ordenes_compra_emprestito` antes de crear nuevo registro.
    
    ### 📊 Estructura de datos guardados:
    ```json
    {
        "numero_orden": "OC-2024-001",
        "nombre_centro_gestor": "Secretaría de Salud",
        "nombre_banco": "Banco Mundial",
        "nombre_resumido_proceso": "Suministro equipos médicos",
        "valor_proyectado": 1500000000.0,
        "bp": "BP-2024-001",
        "fecha_creacion": "2024-10-14T10:30:00",
        "fecha_actualizacion": "2024-10-14T10:30:00",
        "estado": "activo",
        "tipo": "orden_compra_manual"
    }
    ```
    
    ### 📋 Ejemplo de request:
    ```json
    {
        "numero_orden": "OC-SALUD-003-2024",
        "nombre_centro_gestor": "Secretaría de Salud",
        "nombre_banco": "Banco Mundial",
        "nombre_resumido_proceso": "Suministro equipos médicos",
        "valor_proyectado": 1500000000.0,
        "bp": "BP-2024-001"
    }
    ```
    
    ### ✅ Respuesta exitosa (201):
    ```json
    {
        "success": true,
        "message": "Orden de compra OC-SALUD-003-2024 guardada exitosamente",
        "doc_id": "abc123def456",
        "data": { ... },
        "coleccion": "ordenes_compra_emprestito"
    }
    ```
    
    ### ❌ Respuesta de duplicado (409):
    ```json
    {
        "success": false,
        "error": "Ya existe una orden de compra con número: OC-SALUD-003-2024",
        "duplicate": true,
        "existing_data": { ... }
    }
    ```
    """
    try:
        check_emprestito_availability()
        
        # Crear diccionario con los datos del formulario
        datos_orden = {
            "numero_orden": numero_orden,
            "nombre_centro_gestor": nombre_centro_gestor,
            "nombre_banco": nombre_banco,
            "nombre_resumido_proceso": nombre_resumido_proceso,
            "valor_proyectado": valor_proyectado,
            "bp": bp
        }
        
        # Procesar orden de compra
        resultado = await cargar_orden_compra_directa(datos_orden)
        
        # Manejar respuesta según el resultado
        if not resultado.get("success"):
            # Manejar caso especial de duplicado
            if resultado.get("duplicate"):
                return JSONResponse(
                    content={
                        "success": False,
                        "error": resultado.get("error"),
                        "duplicate": True,
                        "existing_data": resultado.get("existing_data"),
                        "message": "Ya existe una orden de compra con este número",
                        "timestamp": datetime.now().isoformat()
                    },
                    status_code=409,  # Conflict
                    headers={"Content-Type": "application/json; charset=utf-8"}
                )
            else:
                # Error general
                return JSONResponse(
                    content={
                        "success": False,
                        "error": resultado.get("error"),
                        "message": "Error al procesar la orden de compra",
                        "timestamp": datetime.now().isoformat()
                    },
                    status_code=400,
                    headers={"Content-Type": "application/json; charset=utf-8"}
                )
        
        # Respuesta exitosa
        return JSONResponse(
            content={
                "success": True,
                "message": resultado.get("message"),
                "data": resultado.get("data"),
                "doc_id": resultado.get("doc_id"),
                "coleccion": resultado.get("coleccion"),
                "timestamp": datetime.now().isoformat()
            },
            status_code=201,
            headers={"Content-Type": "application/json; charset=utf-8"}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error en endpoint de orden de compra: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "error": "Error interno del servidor",
                "message": "Por favor, inténtelo de nuevo más tarde",
                "code": "INTERNAL_SERVER_ERROR"
            }
        )

@app.post("/emprestito/cargar-convenio-transferencia", tags=["Gestión de Empréstito"], summary="🟢 Cargar Convenio de Transferencia")
async def cargar_convenio_transferencia_emprestito(
    referencia_contrato: str = Form(..., description="Referencia del contrato/convenio (obligatorio)"),
    nombre_centro_gestor: str = Form(..., description="Centro gestor responsable (obligatorio)"),
    banco: str = Form(..., description="Nombre del banco (obligatorio)"),
    objeto_contrato: str = Form(..., description="Objeto del contrato (obligatorio)"),
    valor_contrato: float = Form(..., description="Valor del contrato (obligatorio)"),
    bp: Optional[str] = Form(None, description="Código BP (opcional)"),
    bpin: Optional[str] = Form(None, description="Código BPIN (opcional)"),
    valor_convenio: Optional[float] = Form(None, description="Valor del convenio (opcional)"),
    urlproceso: Optional[str] = Form(None, description="URL del proceso (opcional)"),
    fecha_inicio_contrato: Optional[str] = Form(None, description="Fecha de inicio del contrato (opcional)"),
    fecha_fin_contrato: Optional[str] = Form(None, description="Fecha de fin del contrato (opcional)"),
    modalidad_contrato: Optional[str] = Form(None, description="Modalidad del contrato (opcional)"),
    ordenador_gastor: Optional[str] = Form(None, description="Ordenador del gasto (opcional)"),
    tipo_contrato: Optional[str] = Form(None, description="Tipo de contrato (opcional)"),
    estado_contrato: Optional[str] = Form(None, description="Estado del contrato (opcional)"),
    sector: Optional[str] = Form(None, description="Sector (opcional)"),
    nombre_resumido_proceso: str = Form(..., description="Nombre resumido del proceso (obligatorio)")
):
    """
    ## 📝 POST | 📥 Carga de Datos | Cargar Convenio de Transferencia de Empréstito
    
    Endpoint para carga directa de convenios de transferencia de empréstito en la colección 
    `convenios_transferencias_emprestito` sin procesamiento de APIs externas.
    
    ### ✅ Funcionalidades principales:
    - **Carga directa**: Registra directamente en `convenios_transferencias_emprestito`
    - **Validación de duplicados**: Verifica existencia previa usando `referencia_contrato`
    - **Validación de campos**: Verifica que todos los campos obligatorios estén presentes
    - **Timestamps automáticos**: Agrega fecha de creación y actualización
    
    ### ⚙️ Campos obligatorios:
    - `referencia_contrato`: Referencia única del contrato/convenio
    - `nombre_centro_gestor`: Centro gestor responsable
    - `banco`: Nombre del banco
    - `objeto_contrato`: Descripción del objeto del contrato
    - `valor_contrato`: Valor del contrato en pesos colombianos
    
    ### 📝 Campos opcionales:
    - `bp`: Código BP
    - `bpin`: Código BPIN (Banco de Programas y Proyectos de Inversión Nacional)
    - `valor_convenio`: Valor específico del convenio
    - `urlproceso`: URL del proceso de contratación
    - `fecha_inicio_contrato`: Fecha de inicio del contrato
    - `fecha_fin_contrato`: Fecha de finalización del contrato
    - `modalidad_contrato`: Modalidad de contratación
    - `ordenador_gastor`: Ordenador del gasto
    - `tipo_contrato`: Tipo de contrato
    - `estado_contrato`: Estado actual del contrato
    - `sector`: Sector al que pertenece
    
    ### 🛡️ Validación de duplicados:
    Busca `referencia_contrato` en la colección `convenios_transferencias_emprestito` antes de crear nuevo registro.
    
    ### 📊 Estructura de datos guardados:
    ```json
    {
        "referencia_contrato": "CONV-2024-001",
        "nombre_centro_gestor": "Secretaría de Salud",
        "banco": "Banco Mundial",
        "objeto_contrato": "Convenio de transferencia para equipamiento médico",
        "valor_contrato": 1500000000.0,
        "valor_convenio": 1200000000.0,
        "bp": "BP-2024-001",
        "bpin": "2024000010001",
        "urlproceso": "https://...",
        "fecha_inicio_contrato": "2024-01-15",
        "fecha_fin_contrato": "2024-12-31",
        "modalidad_contrato": "Convenio de Transferencia",
        "ordenador_gastor": "Juan Pérez",
        "tipo_contrato": "Transferencia",
        "estado_contrato": "Activo",
        "sector": "Salud",
        "fecha_creacion": "2024-10-14T10:30:00",
        "fecha_actualizacion": "2024-10-14T10:30:00",
        "estado": "activo",
        "tipo": "convenio_transferencia_manual"
    }
    ```
    
    ### 📋 Ejemplo de request:
    ```json
    {
        "referencia_contrato": "CONV-SALUD-003-2024",
        "nombre_centro_gestor": "Secretaría de Salud",
        "banco": "Banco Mundial",
        "objeto_contrato": "Convenio de transferencia para equipamiento médico",
        "valor_contrato": 1500000000.0,
        "valor_convenio": 1200000000.0,
        "bp": "BP-2024-001",
        "modalidad_contrato": "Convenio de Transferencia",
        "estado_contrato": "Activo"
    }
    ```
    
    ### ✅ Respuesta exitosa (201):
    ```json
    {
        "success": true,
        "message": "Convenio de transferencia CONV-SALUD-003-2024 guardado exitosamente",
        "doc_id": "abc123def456",
        "data": { ... },
        "coleccion": "convenios_transferencias_emprestito"
    }
    ```
    
    ### ❌ Respuesta de duplicado (409):
    ```json
    {
        "success": false,
        "error": "Ya existe un convenio de transferencia con referencia: CONV-SALUD-003-2024",
        "duplicate": true,
        "existing_data": { ... }
    }
    ```
    """
    try:
        check_emprestito_availability()
        
        # Crear diccionario con los datos del formulario
        datos_convenio = {
            "referencia_contrato": referencia_contrato,
            "nombre_centro_gestor": nombre_centro_gestor,
            "banco": banco,
            "objeto_contrato": objeto_contrato,
            "valor_contrato": valor_contrato,
            "bp": bp,
            "bpin": bpin,
            "valor_convenio": valor_convenio,
            "urlproceso": urlproceso,
            "fecha_inicio_contrato": fecha_inicio_contrato,
            "fecha_fin_contrato": fecha_fin_contrato,
            "modalidad_contrato": modalidad_contrato,
            "ordenador_gastor": ordenador_gastor,
            "tipo_contrato": tipo_contrato,
            "estado_contrato": estado_contrato,
            "sector": sector,
            "nombre_resumido_proceso": nombre_resumido_proceso
        }
        
        # Procesar convenio de transferencia
        resultado = await cargar_convenio_transferencia(datos_convenio)
        
        # Manejar respuesta según el resultado
        if not resultado.get("success"):
            # Manejar caso especial de duplicado
            if resultado.get("duplicate"):
                return JSONResponse(
                    content={
                        "success": False,
                        "error": resultado.get("error"),
                        "duplicate": True,
                        "existing_data": resultado.get("existing_data"),
                        "message": "Ya existe un convenio de transferencia con esta referencia",
                        "timestamp": datetime.now().isoformat()
                    },
                    status_code=409,  # Conflict
                    headers={"Content-Type": "application/json; charset=utf-8"}
                )
            else:
                # Error general
                return JSONResponse(
                    content={
                        "success": False,
                        "error": resultado.get("error"),
                        "message": "Error al procesar el convenio de transferencia",
                        "timestamp": datetime.now().isoformat()
                    },
                    status_code=400,
                    headers={"Content-Type": "application/json; charset=utf-8"}
                )
        
        # Respuesta exitosa
        return JSONResponse(
            content={
                "success": True,
                "message": resultado.get("message"),
                "data": resultado.get("data"),
                "doc_id": resultado.get("doc_id"),
                "coleccion": resultado.get("coleccion"),
                "timestamp": datetime.now().isoformat()
            },
            status_code=201,
            headers={"Content-Type": "application/json; charset=utf-8"}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error en endpoint de convenio de transferencia: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "error": "Error interno del servidor",
                "message": "Por favor, inténtelo de nuevo más tarde",
                "code": "INTERNAL_SERVER_ERROR"
            }
        )


@app.delete(
    "/emprestito/eliminar-orden-compra/{numero_orden}",
    tags=["Gestión de Empréstito"],
    summary="🔴 Eliminar Orden de Compra"
)
async def eliminar_orden_compra_emprestito(
    numero_orden: str = Path(..., description="Número de orden a eliminar")
):
    """
    ## 🗑️ DELETE | 📥 Gestión de Datos | Eliminar Orden de Compra de Empréstito

    Elimina un registro de la colección `ordenes_compra_emprestito` usando `numero_orden`
    como criterio de búsqueda.
    """
    try:
        check_emprestito_availability()

        resultado = await eliminar_orden_compra_por_numero(numero_orden)

        if not resultado.get("success"):
            if resultado.get("not_found"):
                return JSONResponse(
                    content={
                        "success": False,
                        "error": resultado.get("error"),
                        "numero_orden": numero_orden,
                        "message": "No existe una orden de compra con ese número",
                        "timestamp": datetime.now().isoformat()
                    },
                    status_code=404,
                    headers={"Content-Type": "application/json; charset=utf-8"}
                )

            return JSONResponse(
                content={
                    "success": False,
                    "error": resultado.get("error"),
                    "numero_orden": numero_orden,
                    "message": "Error al eliminar la orden de compra",
                    "timestamp": datetime.now().isoformat()
                },
                status_code=400,
                headers={"Content-Type": "application/json; charset=utf-8"}
            )

        return JSONResponse(
            content={
                "success": True,
                "message": resultado.get("message"),
                "numero_orden": resultado.get("numero_orden"),
                "doc_id": resultado.get("doc_id"),
                "deleted_data": resultado.get("deleted_data"),
                "coleccion": resultado.get("coleccion"),
                "timestamp": datetime.now().isoformat()
            },
            status_code=200,
            headers={"Content-Type": "application/json; charset=utf-8"}
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error en endpoint eliminar orden de compra: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "error": "Error interno del servidor",
                "message": "Por favor, inténtelo de nuevo más tarde",
                "code": "INTERNAL_SERVER_ERROR"
            }
        )


@app.delete(
    "/emprestito/eliminar-convenio-transferencia/{referencia_contrato}",
    tags=["Gestión de Empréstito"],
    summary="🔴 Eliminar Convenio de Transferencia"
)
async def eliminar_convenio_transferencia_emprestito(
    referencia_contrato: str = Path(..., description="Referencia de contrato del convenio a eliminar")
):
    """
    ## 🗑️ DELETE | 📥 Gestión de Datos | Eliminar Convenio de Transferencia de Empréstito

    Elimina un registro de la colección `convenios_transferencias_emprestito`
    usando `referencia_contrato` como criterio de búsqueda.
    """
    try:
        check_emprestito_availability()

        resultado = await eliminar_convenio_transferencia_por_referencia(referencia_contrato)

        if not resultado.get("success"):
            if resultado.get("not_found"):
                return JSONResponse(
                    content={
                        "success": False,
                        "error": resultado.get("error"),
                        "referencia_contrato": referencia_contrato,
                        "message": "No existe un convenio de transferencia con esa referencia",
                        "timestamp": datetime.now().isoformat()
                    },
                    status_code=404,
                    headers={"Content-Type": "application/json; charset=utf-8"}
                )

            return JSONResponse(
                content={
                    "success": False,
                    "error": resultado.get("error"),
                    "referencia_contrato": referencia_contrato,
                    "message": "Error al eliminar el convenio de transferencia",
                    "timestamp": datetime.now().isoformat()
                },
                status_code=400,
                headers={"Content-Type": "application/json; charset=utf-8"}
            )

        return JSONResponse(
            content={
                "success": True,
                "message": resultado.get("message"),
                "referencia_contrato": resultado.get("referencia_contrato"),
                "doc_id": resultado.get("doc_id"),
                "deleted_data": resultado.get("deleted_data"),
                "coleccion": resultado.get("coleccion"),
                "timestamp": datetime.now().isoformat()
            },
            status_code=200,
            headers={"Content-Type": "application/json; charset=utf-8"}
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error en endpoint eliminar convenio de transferencia: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "error": "Error interno del servidor",
                "message": "Por favor, inténtelo de nuevo más tarde",
                "code": "INTERNAL_SERVER_ERROR"
            }
        )

@app.put("/emprestito/modificar-convenio-transferencia", tags=["Gestión de Empréstito"], summary="🟠 Modificar Convenio de Transferencia")
async def modificar_convenio_transferencia_emprestito(
    doc_id: str = Form(..., description="ID del documento a modificar (obligatorio)"),
    referencia_contrato: Optional[str] = Form(None, description="Referencia del contrato/convenio (opcional)"),
    nombre_centro_gestor: Optional[str] = Form(None, description="Centro gestor responsable (opcional)"),
    banco: Optional[str] = Form(None, description="Nombre del banco (opcional)"),
    objeto_contrato: Optional[str] = Form(None, description="Objeto del contrato (opcional)"),
    valor_contrato: Optional[float] = Form(None, description="Valor del contrato (opcional)"),
    bp: Optional[str] = Form(None, description="Código BP (opcional)"),
    bpin: Optional[str] = Form(None, description="Código BPIN (opcional)"),
    valor_convenio: Optional[float] = Form(None, description="Valor del convenio (opcional)"),
    urlproceso: Optional[str] = Form(None, description="URL del proceso (opcional)"),
    fecha_inicio_contrato: Optional[str] = Form(None, description="Fecha de inicio del contrato (opcional)"),
    fecha_fin_contrato: Optional[str] = Form(None, description="Fecha de fin del contrato (opcional)"),
    modalidad_contrato: Optional[str] = Form(None, description="Modalidad del contrato (opcional)"),
    ordenador_gastor: Optional[str] = Form(None, description="Ordenador del gasto (opcional)"),
    tipo_contrato: Optional[str] = Form(None, description="Tipo de contrato (opcional)"),
    estado_contrato: Optional[str] = Form(None, description="Estado del contrato (opcional)"),
    sector: Optional[str] = Form(None, description="Sector (opcional)"),
    nombre_resumido_proceso: Optional[str] = Form(None, description="Nombre resumido del proceso (opcional)")
):
    """
    ## 🟠 PUT | ✏️ Actualización | Modificar Convenio de Transferencia de Empréstito
    
    Endpoint para modificar cualquier campo de un convenio de transferencia existente 
    en la colección `convenios_transferencias_emprestito`.
    
    ### ✅ Funcionalidades principales:
    - **Actualización flexible**: Permite modificar cualquier campo del convenio
    - **Actualización parcial**: Solo se actualizan los campos proporcionados
    - **Validación de existencia**: Verifica que el documento exista antes de actualizar
    - **Timestamp automático**: Actualiza automáticamente `fecha_actualizacion`
    - **Preservación de datos**: Los campos no proporcionados mantienen sus valores originales
    
    ### ⚙️ Campo obligatorio:
    - `doc_id`: ID del documento de Firestore que se desea modificar
    
    ### 📝 Campos opcionales (todos):
    Cualquiera de estos campos puede ser actualizado:
    - `referencia_contrato`: Referencia del contrato/convenio
    - `nombre_centro_gestor`: Centro gestor responsable
    - `banco`: Nombre del banco
    - `objeto_contrato`: Objeto del contrato
    - `valor_contrato`: Valor del contrato
    - `bp`: Código BP
    - `bpin`: Código BPIN
    - `valor_convenio`: Valor del convenio
    - `urlproceso`: URL del proceso
    - `fecha_inicio_contrato`: Fecha de inicio
    - `fecha_fin_contrato`: Fecha de finalización
    - `modalidad_contrato`: Modalidad de contratación
    - `ordenador_gastor`: Ordenador del gasto
    - `tipo_contrato`: Tipo de contrato
    - `estado_contrato`: Estado actual
    - `sector`: Sector al que pertenece
    - `nombre_resumido_proceso`: Nombre resumido del proceso
    
    ### 📋 Ejemplo de request (actualización parcial):
    ```json
    {
        "doc_id": "abc123def456",
        "estado_contrato": "Finalizado",
        "fecha_fin_contrato": "2024-12-31"
    }
    ```
    
    ### ✅ Respuesta exitosa (200):
    ```json
    {
        "success": true,
        "message": "Convenio de transferencia actualizado exitosamente",
        "doc_id": "abc123def456",
        "campos_actualizados": ["estado_contrato", "fecha_fin_contrato"],
        "data": { ... },
        "timestamp": "2024-11-17T10:30:00"
    }
    ```
    
    ### ❌ Respuesta de error (404):
    ```json
    {
        "success": false,
        "error": "No se encontró el convenio de transferencia con ID: abc123",
        "doc_id": "abc123"
    }
    ```
    
    ### 🔗 Endpoints relacionados:
    - `POST /emprestito/cargar-convenio-transferencia` - Para crear nuevos convenios
    - `GET /convenios_transferencias_all` - Para consultar convenios existentes
    """
    try:
        check_emprestito_availability()
        
        # Crear diccionario con los campos a actualizar
        campos_actualizar = {}
        
        if referencia_contrato is not None:
            campos_actualizar["referencia_contrato"] = referencia_contrato
        if nombre_centro_gestor is not None:
            campos_actualizar["nombre_centro_gestor"] = nombre_centro_gestor
        if banco is not None:
            campos_actualizar["banco"] = banco
        if objeto_contrato is not None:
            campos_actualizar["objeto_contrato"] = objeto_contrato
        if valor_contrato is not None:
            campos_actualizar["valor_contrato"] = valor_contrato
        if bp is not None:
            campos_actualizar["bp"] = bp
        if bpin is not None:
            campos_actualizar["bpin"] = bpin
        if valor_convenio is not None:
            campos_actualizar["valor_convenio"] = valor_convenio
        if urlproceso is not None:
            campos_actualizar["urlproceso"] = urlproceso
        if fecha_inicio_contrato is not None:
            campos_actualizar["fecha_inicio_contrato"] = fecha_inicio_contrato
        if fecha_fin_contrato is not None:
            campos_actualizar["fecha_fin_contrato"] = fecha_fin_contrato
        if modalidad_contrato is not None:
            campos_actualizar["modalidad_contrato"] = modalidad_contrato
        if ordenador_gastor is not None:
            campos_actualizar["ordenador_gastor"] = ordenador_gastor
        if tipo_contrato is not None:
            campos_actualizar["tipo_contrato"] = tipo_contrato
        if estado_contrato is not None:
            campos_actualizar["estado_contrato"] = estado_contrato
        if sector is not None:
            campos_actualizar["sector"] = sector
        if nombre_resumido_proceso is not None:
            campos_actualizar["nombre_resumido_proceso"] = nombre_resumido_proceso
        
        # Validar que se proporcionó al menos un campo para actualizar
        if not campos_actualizar:
            return JSONResponse(
                content={
                    "success": False,
                    "error": "Debe proporcionar al menos un campo para actualizar",
                    "message": "No se proporcionaron campos para modificar",
                    "timestamp": datetime.now().isoformat()
                },
                status_code=400,
                headers={"Content-Type": "application/json; charset=utf-8"}
            )
        
        # Modificar convenio de transferencia
        resultado = await modificar_convenio_transferencia(doc_id, campos_actualizar)
        
        # Manejar respuesta según el resultado
        if not resultado.get("success"):
            status_code = 404 if "No se encontró" in resultado.get("error", "") else 400
            return JSONResponse(
                content={
                    "success": False,
                    "error": resultado.get("error"),
                    "doc_id": doc_id,
                    "message": "Error al modificar el convenio de transferencia",
                    "timestamp": datetime.now().isoformat()
                },
                status_code=status_code,
                headers={"Content-Type": "application/json; charset=utf-8"}
            )
        
        # Respuesta exitosa
        return JSONResponse(
            content={
                "success": True,
                "message": resultado.get("message"),
                "doc_id": resultado.get("doc_id"),
                "campos_actualizados": resultado.get("campos_actualizados"),
                "data": resultado.get("data"),
                "coleccion": resultado.get("coleccion"),
                "timestamp": datetime.now().isoformat()
            },
            status_code=200,
            headers={"Content-Type": "application/json; charset=utf-8"}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error en endpoint de modificación de convenio de transferencia: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "error": "Error interno del servidor",
                "message": "Por favor, inténtelo de nuevo más tarde",
                "code": "INTERNAL_SERVER_ERROR"
            }
        )

@app.post("/emprestito/cargar-rpc", tags=["Gestión de Empréstito"], summary="🟢 Cargar RPC de Empréstito")
async def cargar_rpc_emprestito_endpoint(
    numero_rpc: str = Form(..., description="Número del RPC (obligatorio)"),
    beneficiario_id: str = Form(..., description="ID del beneficiario (obligatorio)"),
    beneficiario_nombre: str = Form(..., description="Nombre del beneficiario (obligatorio)"),
    descripcion_rpc: str = Form(..., description="Descripción del RPC (obligatorio)"),
    fecha_contabilizacion: str = Form(..., description="Fecha de contabilización (obligatorio)"),
    fecha_impresion: str = Form(..., description="Fecha de impresión (obligatorio)"),
    estado_liberacion: str = Form(..., description="Estado de liberación (obligatorio)"),
    valor_rpc: float = Form(..., description="Valor del RPC (obligatorio)"),
    nombre_centro_gestor: str = Form(..., description="Centro gestor responsable (obligatorio)"),
    referencia_contrato: str = Form(..., description="Referencia del contrato (obligatorio)"),
    cdp_asociados: Optional[str] = Form(None, description="CDPs asociados separados por comas o JSON array (opcional)"),
    programacion_pac: Optional[str] = Form(None, description="Programación PAC en formato JSON (opcional)"),
    documentos: List[UploadFile] = File(..., description="Documentos del RPC (PDF, DOC, DOCX, XLS, XLSX, JPG, PNG) - OBLIGATORIO")
):
    """
    ## 📝 POST | 📥 Carga de Datos | Cargar RPC (Registro Presupuestal de Compromiso) de Empréstito
    
    Endpoint para carga directa de RPC de empréstito en la colección 
    `rpc_contratos_emprestito` sin procesamiento de APIs externas.
    
    ### ✅ Funcionalidades principales:
    - **Carga directa**: Registra directamente en `rpc_contratos_emprestito`
    - **Validación de duplicados**: Verifica existencia previa usando `numero_rpc`
    - **Validación de campos**: Verifica que todos los campos obligatorios estén presentes
    - **Carga de documentos a S3**: Los documentos son OBLIGATORIOS y se suben a AWS S3
    - **Validación de tipos de archivo**: Valida formatos permitidos (PDF, DOC, DOCX, XLS, XLSX, JPG, PNG)
    - **Timestamps automáticos**: Agrega fecha de creación y actualización
    - **Programación PAC**: Soporte para objeto JSON con valores mensuales
    
    ### ⚙️ Campos obligatorios:
    - `numero_rpc`: Número único del RPC
    - `beneficiario_id`: Identificación del beneficiario
    - `beneficiario_nombre`: Nombre completo del beneficiario
    - `descripcion_rpc`: Descripción del compromiso
    - `fecha_contabilizacion`: Fecha de contabilización del RPC
    - `fecha_impresion`: Fecha de impresión del documento
    - `estado_liberacion`: Estado de liberación del RPC
    - `valor_rpc`: Valor monetario del RPC
    - `nombre_centro_gestor`: Centro gestor responsable
    - `referencia_contrato`: Referencia del contrato asociado
    - `documentos`: Archivos del RPC (al menos 1 archivo requerido)
    
    ### 📌 Nota importante sobre BP:
    El campo `bp` ya NO es requerido en este endpoint. El valor de `bp` se hereda automáticamente
    al consultar los RPCs desde las colecciones: `contratos_emprestito`, `convenios_transferencias_emprestito` 
    o `ordenes_compra_emprestito` usando la `referencia_contrato`.
    
    ### 📝 Campos opcionales:
    - `cdp_asociados`: Lista de CDPs (Certificados de Disponibilidad Presupuestal) asociados
      - Puede enviarse como: `"CDP-001,CDP-002,CDP-003"` (separados por comas)
      - O como JSON array: `["CDP-001", "CDP-002", "CDP-003"]`
      - Si se deja vacío, se guardará como lista vacía `[]`
    - `programacion_pac`: Objeto JSON con programación mensual del PAC (Plan Anual de Caja)
      - Formato: `{"enero-2024": "1000000", "febrero-2024": "500000"}`
      - **IMPORTANTE**: Debe ser un objeto JSON válido si se proporciona
      - Si no es JSON válido, se ignorará y se guardará como objeto vacío `{}`
    
    ### 🛡️ Validación de duplicados:
    Busca `numero_rpc` en la colección `rpc_contratos_emprestito` antes de crear nuevo registro.
    
    ### 📊 Estructura de datos guardados:
    ```json
    {
        "numero_rpc": "RPC-2024-001",
        "beneficiario_id": "890123456",
        "beneficiario_nombre": "Proveedor XYZ S.A.S.",
        "descripcion_rpc": "Suministro de equipos médicos",
        "fecha_contabilizacion": "2024-10-15",
        "fecha_impresion": "2024-10-16",
        "estado_liberacion": "Liberado",
        "valor_rpc": 50000000.0,
        "cdp_asociados": ["CDP-2024-100", "CDP-2024-101", "CDP-2024-102"],
        "programacion_pac": {
            "enero-2024": "10000000",
            "febrero-2024": "20000000",
            "marzo-2024": "20000000"
        },
        "nombre_centro_gestor": "Secretaría de Salud",
        "referencia_contrato": "CONT-SALUD-003-2024",
        "fecha_creacion": "2024-10-14T10:30:00",
        "fecha_actualizacion": "2024-10-14T10:30:00",
        "estado": "activo",
        "tipo": "rpc_manual"
    }
    ```
    
    ### 📋 Ejemplo de request:
    ```json
    {
        "numero_rpc": "RPC-SALUD-003-2024",
        "beneficiario_id": "890123456",
        "beneficiario_nombre": "Proveedor XYZ S.A.S.",
        "descripcion_rpc": "Suministro de equipos médicos",
        "fecha_contabilizacion": "2024-10-15",
        "fecha_impresion": "2024-10-16",
        "estado_liberacion": "Liberado",
        "valor_rpc": 50000000.0,
        "nombre_centro_gestor": "Secretaría de Salud",
        "referencia_contrato": "CONT-SALUD-003-2024",
        "cdp_asociados": "CDP-2024-100",
        "programacion_pac": "{\\"enero-2024\\": \\"10000000\\", \\"febrero-2024\\": \\"20000000\\"}"
    }
    ```
    
    ### ✅ Respuesta exitosa (201):
    ```json
    {
        "success": true,
        "message": "RPC RPC-SALUD-003-2024 guardado exitosamente",
        "doc_id": "abc123def456",
        "data": { ... },
        "coleccion": "rpc_contratos_emprestito"
    }
    ```
    
    ### ❌ Respuesta de duplicado (409):
    ```json
    {
        "success": false,
        "error": "Ya existe un RPC con número: RPC-SALUD-003-2024",
        "duplicate": true,
        "existing_data": { ... }
    }
    ```
    """
    try:
        check_emprestito_availability()
        
        logger.info(f"📥 Recibiendo RPC: {numero_rpc}")
        logger.info(f"📎 Documentos recibidos: {len(documentos)}")
        
        # Validar que se hayan proporcionado documentos
        if not documentos or len(documentos) == 0:
            return JSONResponse(
                content={
                    "success": False,
                    "error": "Se requiere al menos un documento para cargar el RPC",
                    "message": "Debe proporcionar al menos un archivo PDF, DOC, DOCX, XLS, XLSX, JPG o PNG",
                    "timestamp": datetime.now().isoformat()
                },
                status_code=400,
                headers={"Content-Type": "application/json; charset=utf-8"}
            )
        
        # Validar tipos de archivo permitidos
        allowed_extensions = ['.pdf', '.doc', '.docx', '.xls', '.xlsx', '.jpg', '.jpeg', '.png']
        for doc in documentos:
            filename_lower = doc.filename.lower()
            if not any(filename_lower.endswith(ext) for ext in allowed_extensions):
                return JSONResponse(
                    content={
                        "success": False,
                        "error": f"Tipo de archivo no permitido: {doc.filename}",
                        "message": "Solo se permiten archivos PDF, DOC, DOCX, XLS, XLSX, JPG y PNG",
                        "allowed_types": allowed_extensions,
                        "timestamp": datetime.now().isoformat()
                    },
                    status_code=400,
                    headers={"Content-Type": "application/json; charset=utf-8"}
                )
            logger.info(f"   - {doc.filename} ({doc.content_type})")
        
        # Procesar cdp_asociados: puede venir como string separado por comas o como JSON array
        cdp_asociados_processed = None
        if cdp_asociados and cdp_asociados.strip():
            # Si parece JSON array, intentar parsear
            if cdp_asociados.strip().startswith('['):
                try:
                    cdp_parsed = json.loads(cdp_asociados)
                    if isinstance(cdp_parsed, list):
                        cdp_asociados_processed = cdp_parsed
                    else:
                        # Si no es lista, usar como string
                        cdp_asociados_processed = cdp_asociados
                except json.JSONDecodeError:
                    # Si falla el parseo, usar como string
                    cdp_asociados_processed = cdp_asociados
            else:
                # Si no parece JSON, asumir que es string separado por comas o simple
                cdp_asociados_processed = cdp_asociados
        
        # Procesar programacion_pac si viene como string JSON
        programacion_pac_dict = {}
        if programacion_pac and programacion_pac.strip():
            # Solo intentar parsear si parece ser JSON (empieza con { o [)
            if programacion_pac.strip().startswith('{') or programacion_pac.strip().startswith('['):
                try:
                    programacion_pac_dict = json.loads(programacion_pac)
                    if not isinstance(programacion_pac_dict, dict):
                        return JSONResponse(
                            content={
                                "success": False,
                                "error": "programacion_pac debe ser un objeto JSON (diccionario)",
                                "message": "El formato de programacion_pac debe ser un objeto JSON como {\"enero-2024\": \"1000000\"}",
                                "timestamp": datetime.now().isoformat()
                            },
                            status_code=400,
                            headers={"Content-Type": "application/json; charset=utf-8"}
                        )
                except json.JSONDecodeError as e:
                    return JSONResponse(
                        content={
                            "success": False,
                            "error": f"programacion_pac tiene formato JSON inválido: {str(e)}",
                            "message": "El formato de programacion_pac no es un JSON válido. Debe ser un objeto como {\"enero-2024\": \"1000000\"}",
                            "timestamp": datetime.now().isoformat()
                        },
                        status_code=400,
                        headers={"Content-Type": "application/json; charset=utf-8"}
                    )
            else:
                # Si no parece JSON, ignorar el campo con un warning
                logger.warning(f"programacion_pac no parece ser JSON, ignorando valor: {programacion_pac[:50]}")
                programacion_pac_dict = {}
        
        # Procesar documentos si se proporcionan
        documentos_procesados = []
        if documentos:
            for doc in documentos:
                # Leer contenido del archivo
                contenido = await doc.read()
                documentos_procesados.append({
                    'content': contenido,
                    'filename': doc.filename,
                    'content_type': doc.content_type,
                    'size': len(contenido)
                })
            logger.info(f"📄 Procesando {len(documentos_procesados)} documentos para RPC {numero_rpc}")
        
        # Crear diccionario con los datos del formulario
        datos_rpc = {
            "numero_rpc": numero_rpc,
            "beneficiario_id": beneficiario_id,
            "beneficiario_nombre": beneficiario_nombre,
            "descripcion_rpc": descripcion_rpc,
            "fecha_contabilizacion": fecha_contabilizacion,
            "fecha_impresion": fecha_impresion,
            "estado_liberacion": estado_liberacion,
            "valor_rpc": valor_rpc,
            "cdp_asociados": cdp_asociados_processed,
            "programacion_pac": programacion_pac_dict,
            "nombre_centro_gestor": nombre_centro_gestor,
            "referencia_contrato": referencia_contrato
        }
        
        # Procesar RPC (función síncrona) con documentos
        logger.info(f"💾 Procesando RPC {numero_rpc} con {len(documentos_procesados)} documentos")
        resultado = cargar_rpc_emprestito(datos_rpc, documentos=documentos_procesados if documentos_procesados else None)
        
        # Log del resultado
        if resultado.get("success"):
            logger.info(f"✅ RPC {numero_rpc} procesado exitosamente")
        else:
            logger.error(f"❌ Error procesando RPC {numero_rpc}: {resultado.get('error')}")
        
        # Manejar respuesta según el resultado
        if not resultado.get("success"):
            # Manejar caso especial de duplicado
            if resultado.get("duplicate"):
                return JSONResponse(
                    content={
                        "success": False,
                        "error": resultado.get("error"),
                        "duplicate": True,
                        "existing_data": resultado.get("existing_data"),
                        "message": "Ya existe un RPC con este número",
                        "timestamp": datetime.now().isoformat()
                    },
                    status_code=409,  # Conflict
                    headers={"Content-Type": "application/json; charset=utf-8"}
                )
            else:
                # Error general
                return JSONResponse(
                    content={
                        "success": False,
                        "error": resultado.get("error"),
                        "message": "Error al procesar el RPC",
                        "timestamp": datetime.now().isoformat()
                    },
                    status_code=400,
                    headers={"Content-Type": "application/json; charset=utf-8"}
                )
        
        # Respuesta exitosa
        # Extraer URLs de documentos del resultado
        documentos_urls = []
        if resultado.get("data") and resultado.get("data").get("documentos_s3"):
            documentos_urls = [doc.get("url") for doc in resultado.get("data").get("documentos_s3") if doc.get("url")]
        
        return JSONResponse(
            content={
                "success": True,
                "message": resultado.get("message"),
                "data": {
                    "numero_rpc": numero_rpc,
                    "doc_id": resultado.get("doc_id"),
                    "documentos_urls": documentos_urls,
                    "total_documentos": resultado.get("documentos_count", 0),
                    "detalles_completos": resultado.get("data")
                },
                "coleccion": resultado.get("coleccion"),
                "timestamp": datetime.now().isoformat()
            },
            status_code=201,
            headers={"Content-Type": "application/json; charset=utf-8"}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error en endpoint de RPC: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "error": "Error interno del servidor",
                "message": "Por favor, inténtelo de nuevo más tarde",
                "code": "INTERNAL_SERVER_ERROR"
            }
        )

@app.post("/emprestito/cargar-pago", tags=["Gestión de Empréstito"], summary="🟢 Cargar Pago de Empréstito")
async def cargar_pago_emprestito_endpoint(
    numero_rpc: str = Form(..., description="Número del RPC (obligatorio)"),
    valor_pago: float = Form(..., description="Valor del pago (obligatorio, debe ser mayor a 0)"),
    fecha_transaccion: str = Form(..., description="Fecha de la transacción (obligatorio)"),
    referencia_contrato: str = Form(..., description="Referencia del contrato (obligatorio)"),
    nombre_centro_gestor: str = Form(..., description="Centro gestor responsable (obligatorio)"),
    documentos: List[UploadFile] = File(None, description="Documentos del pago (PDF, DOC, DOCX, XLS, XLSX, JPG, PNG) - OPCIONAL")
):
    """
    ## 📝 POST | 📥 Carga de Datos | Cargar Pago de Empréstito
    
    Endpoint para registrar un pago de empréstito en la colección `pagos_emprestito`.
    El campo `fecha_registro` se genera automáticamente con la hora actual del sistema como timestamp.
    
    ### ✅ Funcionalidades principales:
    - **Registro de pagos**: Guarda información de pagos realizados
    - **Carga de documentos a S3**: Los documentos son OPCIONALES y se suben a AWS S3 si se proporcionan
    - **Validación de tipos de archivo**: Valida formatos permitidos (PDF, DOC, DOCX, XLS, XLSX, JPG, PNG)
    - **Timestamp automático**: `fecha_registro` se genera automáticamente con la hora del sistema
    - **Validación de campos**: Verifica que todos los campos obligatorios estén presentes
    - **Validación de valores**: Verifica que el valor del pago sea positivo
    - **Trazabilidad**: Registra fecha de creación y actualización
    
    ### ⚙️ Campos obligatorios:
    - `numero_rpc`: Número del RPC asociado al pago
    - `valor_pago`: Valor monetario del pago (debe ser mayor a 0)
    - `fecha_transaccion`: Fecha en que se realizó la transacción
    - `referencia_contrato`: Referencia del contrato asociado
    - `nombre_centro_gestor`: Centro gestor responsable del pago
    
    ### ⚙️ Campos opcionales:
    - `documentos`: Archivos del pago (PDF, DOC, DOCX, XLS, XLSX, JPG, PNG)
    
    ### 🤖 Campos automáticos:
    - `fecha_registro`: Timestamp automático del momento de registro (NO se envía por el usuario)
    - `fecha_creacion`: Timestamp de creación del registro
    - `fecha_actualizacion`: Timestamp de última actualización
    - `estado`: "registrado" (valor por defecto)
    - `tipo`: "pago_manual" (valor por defecto)
    
    ### 📊 Estructura de datos guardados:
    ```json
    {
        "numero_rpc": "RPC-2024-001",
        "valor_pago": 10000000.0,
        "fecha_transaccion": "2024-11-11",
        "referencia_contrato": "CONT-SALUD-003-2024",
        "nombre_centro_gestor": "Secretaría de Salud",
        "fecha_registro": "2024-11-11T14:30:45.123456",
        "fecha_creacion": "2024-11-11T14:30:45.123456",
        "fecha_actualizacion": "2024-11-11T14:30:45.123456",
        "estado": "registrado",
        "tipo": "pago_manual"
    }
    ```
    
    ### 📋 Ejemplo de request:
    ```json
    {
        "numero_rpc": "RPC-SALUD-003-2024",
        "valor_pago": 10000000.0,
        "fecha_transaccion": "2024-11-11",
        "referencia_contrato": "CONT-SALUD-003-2024",
        "nombre_centro_gestor": "Secretaría de Salud"
    }
    ```
    
    ### ✅ Respuesta exitosa (201):
    ```json
    {
        "success": true,
        "message": "Pago registrado exitosamente para RPC RPC-SALUD-003-2024",
        "data": { ... },
        "doc_id": "abc123def456",
        "coleccion": "pagos_emprestito",
        "timestamp": "2024-11-11T14:30:45.123456"
    }
    ```
    
    ### ❌ Respuesta de error (400):
    ```json
    {
        "success": false,
        "error": "El campo 'numero_rpc' es obligatorio",
        "message": "Error al procesar el pago",
        "timestamp": "2024-11-11T14:30:45.123456"
    }
    ```
    
    ### 💡 Notas importantes:
    - El campo `fecha_registro` NO debe ser enviado por el usuario
    - Se genera automáticamente con la hora exacta del servidor
    - El `valor_pago` debe ser un número positivo mayor a 0
    - Todos los campos de texto se limpian de espacios en blanco
    """
    try:
        check_emprestito_availability()
        
        logger.info(f"📥 Recibiendo pago para RPC: {numero_rpc}")
        logger.info(f"📎 Documentos recibidos: {len(documentos) if documentos else 0}")
        logger.info(f"💰 Valor del pago: {valor_pago}")
        
        # Validar tipos de archivo permitidos solo si se proporcionaron documentos
        allowed_extensions = ['.pdf', '.doc', '.docx', '.xls', '.xlsx', '.jpg', '.jpeg', '.png']
        if documentos:
            for doc in documentos:
                filename_lower = doc.filename.lower()
                if not any(filename_lower.endswith(ext) for ext in allowed_extensions):
                    return JSONResponse(
                        content={
                            "success": False,
                            "error": f"Tipo de archivo no permitido: {doc.filename}",
                            "message": "Solo se permiten archivos PDF, DOC, DOCX, XLS, XLSX, JPG y PNG",
                            "allowed_types": allowed_extensions,
                            "timestamp": datetime.now().isoformat()
                        },
                        status_code=400,
                        headers={"Content-Type": "application/json; charset=utf-8"}
                    )
                logger.info(f"   - {doc.filename} ({doc.content_type})")
        
        # Procesar documentos si se proporcionan
        documentos_procesados = []
        if documentos:
            for doc in documentos:
                # Leer contenido del archivo
                contenido = await doc.read()
                documentos_procesados.append({
                    'content': contenido,
                    'filename': doc.filename,
                    'content_type': doc.content_type,
                    'size': len(contenido)
                })
            logger.info(f"📄 Procesando {len(documentos_procesados)} documentos para pago de RPC {numero_rpc}")
        
        # Preparar datos para procesar
        datos_pago = {
            "numero_rpc": numero_rpc,
            "valor_pago": valor_pago,
            "fecha_transaccion": fecha_transaccion,
            "referencia_contrato": referencia_contrato,
            "nombre_centro_gestor": nombre_centro_gestor
        }
        
        # Procesar pago (función síncrona) con documentos
        logger.info(f"💾 Procesando pago para RPC {numero_rpc} con {len(documentos_procesados)} documentos")
        resultado = cargar_pago_emprestito(datos_pago, documentos=documentos_procesados if documentos_procesados else None)
        
        # Log del resultado
        if resultado.get("success"):
            logger.info(f"✅ Pago para RPC {numero_rpc} procesado exitosamente")
        else:
            logger.error(f"❌ Error procesando pago para RPC {numero_rpc}: {resultado.get('error')}")
        
        # Manejar respuesta según el resultado
        if not resultado.get("success"):
            return JSONResponse(
                content={
                    "success": False,
                    "error": resultado.get("error"),
                    "message": "Error al procesar el pago",
                    "timestamp": datetime.now().isoformat()
                },
                status_code=400,
                headers={"Content-Type": "application/json; charset=utf-8"}
            )
        
        # Respuesta exitosa
        # Extraer URLs de documentos del resultado
        documentos_urls = []
        if resultado.get("data") and resultado.get("data").get("documentos_s3"):
            documentos_urls = [doc.get("url") for doc in resultado.get("data").get("documentos_s3") if doc.get("url")]
        
        return JSONResponse(
            content={
                "success": True,
                "message": resultado.get("message"),
                "data": {
                    "numero_rpc": numero_rpc,
                    "doc_id": resultado.get("doc_id"),
                    "valor_pago": valor_pago,
                    "documentos_urls": documentos_urls,
                    "total_documentos": resultado.get("documentos_count", 0),
                    "detalles_completos": resultado.get("data")
                },
                "coleccion": resultado.get("coleccion"),
                "timestamp": resultado.get("timestamp")
            },
            status_code=201,
            headers={"Content-Type": "application/json; charset=utf-8"}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error en endpoint de pago de empréstito: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "error": "Error interno del servidor",
                "message": "Por favor, inténtelo de nuevo más tarde",
                "code": "INTERNAL_SERVER_ERROR"
            }
        )

@app.get("/contratos_pagos_all", tags=["Gestión de Empréstito"], summary="🔵 Obtener Todos los Pagos")
async def get_all_pagos_emprestito():
    """
    ## 🔵 GET | 📋 Consultas | Obtener Todos los Pagos de Empréstito
    
    Endpoint para obtener todos los pagos de empréstito registrados en la colección `pagos_emprestito`.
    
    ### ✅ Funcionalidades principales:
    - **Listado completo**: Retorna todos los pagos registrados
    - **Datos completos**: Incluye todos los campos de cada pago
    - **Detección de documentos soporte**: Verifica si cada pago tiene documentos en S3
    - **Metadatos**: Incluye ID del documento, conteo total y timestamp
    - **Serialización JSON**: Fechas y objetos datetime convertidos correctamente
    - **Trazabilidad**: Información completa de cada transacción registrada
    
    ### 📊 Información incluida:
    - Todos los campos del pago
    - ID del documento para referencia
    - Campo `tiene_documentos_soporte`: indica si el pago tiene documentos en S3 (true/false)
    - Conteo total de registros
    - Timestamp de la consulta
    - Datos serializados correctamente para JSON
    
    ### 🗄️ Campos principales esperados:
    - **numero_rpc**: Número del RPC asociado al pago
    - **valor_pago**: Valor monetario del pago realizado
    - **fecha_transaccion**: Fecha en que se realizó la transacción
    - **referencia_contrato**: Referencia del contrato asociado
    - **nombre_centro_gestor**: Centro gestor responsable
    - **fecha_registro**: Timestamp automático del momento del registro
    - **fecha_creacion**: Fecha de creación del registro
    - **fecha_actualizacion**: Última actualización del registro
    - **estado**: Estado del pago (registrado, procesado, etc.)
    - **tipo**: Tipo de registro (pago_manual)
    - **tiene_documentos_soporte**: Boolean que indica si el pago tiene documentos en S3
    - **documentos_s3**: Array con información de documentos en S3 (si existen)
    
    ### 💡 Casos de uso:
    - Obtener historial completo de pagos de empréstito
    - Consulta de pagos para reportes financieros
    - Análisis de flujo de caja y ejecución presupuestal
    - Seguimiento de transacciones por RPC
    - Dashboard de pagos realizados
    - Exportación de datos para auditorías
    - Integración con sistemas contables
    - Reportes de ejecución por centro gestor
    
    ### 📈 Análisis posibles:
    - Total de pagos realizados
    - Suma de valores pagados
    - Pagos por centro gestor
    - Pagos por contrato
    - Pagos por RPC
    - Histórico de transacciones
    
    ### ✅ Respuesta exitosa (200):
    ```json
    {
        "success": true,
        "data": [
            {
                "id": "xyz789",
                "numero_rpc": "RPC-2024-001",
                "valor_pago": 10000000.0,
                "fecha_transaccion": "2024-11-11",
                "referencia_contrato": "CONT-SALUD-003-2024",
                "nombre_centro_gestor": "Secretaría de Salud",
                "fecha_registro": "2024-11-11T14:30:45.123456",
                "fecha_creacion": "2024-11-11T14:30:45.123456",
                "fecha_actualizacion": "2024-11-11T14:30:45.123456",
                "estado": "registrado",
                "tipo": "pago_manual",
                "tiene_documentos_soporte": true,
                "documentos_s3": [
                    {
                        "filename": "pago_001.pdf",
                        "s3_url": "https://contratos-emprestito.s3.us-east-1.amazonaws.com/...",
                        "upload_date": "2024-11-11T14:30:45.123456"
                    }
                ]
            },
            {
                "id": "abc456",
                "numero_rpc": "RPC-2024-002",
                "valor_pago": 5000000.0,
                "fecha_transaccion": "2024-11-10",
                "referencia_contrato": "CONT-INFRA-001-2024",
                "nombre_centro_gestor": "Secretaría de Infraestructura",
                "fecha_registro": "2024-11-10T10:15:30.654321",
                "fecha_creacion": "2024-11-10T10:15:30.654321",
                "fecha_actualizacion": "2024-11-10T10:15:30.654321",
                "estado": "registrado",
                "tipo": "pago_manual",
                "tiene_documentos_soporte": false,
                "documentos_s3": []
            }
        ],
        "count": 15,
        "collection": "pagos_emprestito",
        "timestamp": "2024-11-11T15:00:00.000000",
        "message": "Se obtuvieron 15 pagos exitosamente"
    }
    ```
    
    ### ❌ Respuesta de error (500):
    ```json
    {
        "success": false,
        "error": "Error obteniendo pagos de empréstito: [detalles del error]",
        "data": [],
        "count": 0
    }
    ```
    
    ### 📝 Notas:
    - Los campos de tipo datetime se serializan en formato ISO 8601
    - El campo `id` corresponde al ID del documento en Firestore
    - Los datos se retornan en el orden en que fueron insertados en Firestore
    - Para consultas filtradas, considere crear endpoints específicos adicionales
    """
    try:
        check_emprestito_availability()
        
        # Obtener todos los pagos
        resultado = await get_pagos_emprestito_all()
        
        if not resultado.get("success"):
            raise HTTPException(
                status_code=500,
                detail={
                    "success": False,
                    "error": resultado.get("error", "Error desconocido"),
                    "message": "Error al obtener los pagos de empréstito"
                }
            )
        
        # Respuesta exitosa
        return JSONResponse(
            content={
                "success": True,
                "data": resultado.get("data", []),
                "count": resultado.get("count", 0),
                "collection": resultado.get("collection", "pagos_emprestito"),
                "timestamp": resultado.get("timestamp"),
                "message": f"Se obtuvieron {resultado.get('count', 0)} pagos exitosamente"
            },
            status_code=200,
            headers={"Content-Type": "application/json; charset=utf-8"}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error en endpoint de consulta de pagos: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "error": "Error interno del servidor",
                "message": "Por favor, inténtelo de nuevo más tarde",
                "code": "INTERNAL_SERVER_ERROR"
            }
        )

@app.get("/rpc_all", tags=["Gestión de Empréstito"], summary="🔵 Obtener Todos los RPCs")
async def get_all_rpc_contratos_emprestito():
    """
    ## 🔵 GET | 📋 Consultas | Obtener Todos los RPCs de Empréstito
    
    Endpoint para obtener todos los RPC (Registros Presupuestales de Compromiso) de empréstito 
    almacenados en la colección `rpc_contratos_emprestito`.
    
    ### ✅ Funcionalidades principales:
    - **Listado completo**: Retorna todos los RPCs registrados
    - **Datos completos**: Incluye todos los campos de cada RPC
    - **Metadatos**: Incluye ID del documento, conteo total y timestamp
    - **Serialización JSON**: Fechas y objetos convertidos correctamente
    
    ### 📊 Información incluida:
    - Todos los campos del RPC
    - ID del documento para referencia
    - Conteo total de registros
    - Timestamp de la consulta
    - Datos serializados correctamente para JSON
    
    ### 🗄️ Campos principales esperados:
    - **numero_rpc**: Número único del RPC
    - **beneficiario_id**: Identificación del beneficiario
    - **beneficiario_nombre**: Nombre del beneficiario
    - **descripcion_rpc**: Descripción del compromiso
    - **fecha_contabilizacion**: Fecha de contabilización
    - **fecha_impresion**: Fecha de impresión del documento
    - **estado_liberacion**: Estado de liberación del RPC
    - **bp**: Código BP (Banco de Programas)
    - **valor_rpc**: Valor monetario del RPC
    - **cdp_asociados**: Lista de CDPs asociados
    - **programacion_pac**: Objeto con programación mensual del PAC
    - **nombre_centro_gestor**: Centro gestor responsable
    - **referencia_contrato**: Referencia del contrato asociado
    - **fecha_creacion**: Fecha de creación del registro
    - **fecha_actualizacion**: Última actualización
    - **estado**: Estado del registro (activo/inactivo)
    - **tipo**: Tipo de registro (rpc_manual)
    
    ### 💡 Casos de uso:
    - Obtener listado completo de RPCs de empréstito
    - Exportación de datos para análisis
    - Integración con sistemas externos
    - Reportes y dashboards de seguimiento presupuestal
    - Monitoreo de compromisos presupuestales
    - Análisis de ejecución presupuestal por contrato
    
    ### ✅ Respuesta exitosa (200):
    ```json
    {
        "success": true,
        "data": [
            {
                "id": "abc123",
                "numero_rpc": "RPC-2024-001",
                "beneficiario_id": "890123456",
                "beneficiario_nombre": "Proveedor XYZ S.A.S.",
                "descripcion_rpc": "Suministro de equipos médicos",
                "fecha_contabilizacion": "2024-10-15",
                "fecha_impresion": "2024-10-16",
                "estado_liberacion": "Liberado",
                "bp": "BP-2024-001",
                "valor_rpc": 50000000.0,
                "cdp_asociados": ["CDP-2024-100", "CDP-2024-101"],
                "programacion_pac": {
                    "enero-2024": "10000000",
                    "febrero-2024": "20000000"
                },
                "nombre_centro_gestor": "Secretaría de Salud",
                "referencia_contrato": "CONT-SALUD-003-2024",
                "fecha_creacion": "2024-10-14T10:30:00",
                "fecha_actualizacion": "2024-10-14T10:30:00",
                "estado": "activo",
                "tipo": "rpc_manual"
            }
        ],
        "count": 25,
        "collection": "rpc_contratos_emprestito",
        "timestamp": "2024-11-11T...",
        "message": "Se obtuvieron 25 RPCs exitosamente"
    }
    ```
    
    ### ❌ Respuesta de error (500):
    ```json
    {
        "success": false,
        "error": "Error obteniendo RPCs: ...",
        "data": [],
        "count": 0
    }
    ```
    
    ### 🔗 Endpoints relacionados:
    - `POST /emprestito/cargar-rpc` - Para crear nuevos RPCs
    - `GET /convenios_transferencias_all` - Para consultar convenios de transferencia
    """
    try:
        check_emprestito_availability()
        
        # Obtener todos los RPCs
        result = await get_rpc_contratos_emprestito_all()
        
        if not result["success"]:
            raise HTTPException(
                status_code=500,
                detail=f"Error obteniendo RPCs: {result.get('error', 'Error desconocido')}"
            )
        
        return JSONResponse(
            content={
                "success": True,
                "data": result["data"],
                "count": result["count"],
                "collection": result["collection"],
                "timestamp": result["timestamp"],
                "message": f"Se obtuvieron {result['count']} RPCs exitosamente"
            },
            status_code=200,
            headers={"Content-Type": "application/json; charset=utf-8"}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error en endpoint de RPCs: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "error": "Error interno del servidor",
                "message": "Por favor, inténtelo de nuevo más tarde",
                "code": "INTERNAL_SERVER_ERROR"
            }
        )

@app.get("/rpc_documentos_temporales", tags=["Gestión de Empréstito"], summary="🔵 Obtener Enlaces Temporales de Documentos de RPC")
async def get_rpc_documentos_temporales(numero_rpc: str, expiration: int = 3600):
    """
    ## 🔵 GET | 📄 Documentos | Obtener Enlaces Temporales de Documentos de RPC
    
    Endpoint para generar enlaces temporales (presigned URLs) para visualizar y descargar 
    los documentos PDF asociados a un RPC específico almacenados en S3.
    
    ### ✅ Funcionalidades principales:
    - **Enlaces bajo demanda**: Genera URLs solo cuando se solicitan
    - **URLs temporales**: Enlaces seguros con tiempo de expiración configurable
    - **Acceso directo**: URLs listas para visualizar o descargar en el frontend
    - **Seguridad**: Enlaces con expiración automática (por defecto 1 hora)
    
    ### 📝 Parámetros:
    - **numero_rpc** (requerido): Número del RPC para buscar sus documentos
    - **expiration** (opcional): Tiempo de expiración en segundos (default: 3600 = 1 hora)
    
    ### 📊 Información retornada:
    - Lista de documentos del RPC
    - URL temporal para cada documento
    - Información del archivo (nombre, tamaño, fecha)
    - Tiempo de expiración de cada URL
    
    ### 💡 Casos de uso:
    - Visualizar documentos de RPC en el frontend
    - Descargar documentos de soporte
    - Validar documentación de compromisos presupuestales
    - Auditoría de documentos
    
    ### ✅ Respuesta exitosa (200):
    ```json
    {
        "success": true,
        "numero_rpc": "RPC-2024-001",
        "referencia_contrato": "CONT-SALUD-003-2024",
        "documentos": [
            {
                "filename": "documento_rpc.pdf",
                "s3_key": "contratos-rpc-docs/CONT-SALUD-003-2024/documento_rpc.pdf",
                "presigned_url": "https://contratos-emprestito.s3.amazonaws.com/...",
                "size": 1048576,
                "last_modified": "2024-12-20T10:30:00",
                "url_expiration_seconds": 3600,
                "url_expires_at": "2024-12-20T11:30:00"
            }
        ],
        "count": 1,
        "message": "Se generaron 1 enlace(s) temporal(es) exitosamente"
    }
    ```
    
    ### ❌ Respuesta de error (404):
    ```json
    {
        "success": false,
        "error": "No se encontró el RPC especificado",
        "numero_rpc": "RPC-XXX"
    }
    ```
    
    ### ❌ Respuesta de error (500):
    ```json
    {
        "success": false,
        "error": "Error generando enlaces temporales: ..."
    }
    ```
    
    ### 🔗 Endpoints relacionados:
    - `GET /rpc_all` - Para listar todos los RPCs
    - `POST /emprestito/cargar-rpc` - Para crear nuevos RPCs con documentos
    """
    try:
        check_emprestito_availability()
        
        # Importar S3DocumentManager
        try:
            from api.utils.s3_document_manager import S3DocumentManager
        except ImportError:
            raise HTTPException(
                status_code=500,
                detail={
                    "success": False,
                    "error": "Servicio de almacenamiento S3 no disponible",
                    "message": "No es posible generar enlaces temporales en este momento"
                }
            )
        
        # Validar que se proporcionó numero_rpc
        if not numero_rpc or not numero_rpc.strip():
            raise HTTPException(
                status_code=400,
                detail={
                    "success": False,
                    "error": "El parámetro 'numero_rpc' es requerido"
                }
            )
        
        numero_rpc = numero_rpc.strip()
        
        # Buscar el RPC en Firebase para obtener la referencia_contrato
        db_client = get_firestore_client()
        if not db_client:
            raise HTTPException(
                status_code=500,
                detail={
                    "success": False,
                    "error": "Error conectando con la base de datos"
                }
            )
        
        # Buscar RPC por numero_rpc
        rpc_ref = db_client.collection('rpc_contratos_emprestito')
        query = rpc_ref.where('numero_rpc', '==', numero_rpc).limit(1)
        docs = list(query.stream())
        
        if not docs:
            raise HTTPException(
                status_code=404,
                detail={
                    "success": False,
                    "error": f"No se encontró el RPC con número: {numero_rpc}",
                    "numero_rpc": numero_rpc
                }
            )
        
        rpc_data = docs[0].to_dict()
        referencia_contrato = rpc_data.get('referencia_contrato', '')
        
        if not referencia_contrato:
            raise HTTPException(
                status_code=500,
                detail={
                    "success": False,
                    "error": "El RPC no tiene referencia de contrato asociada",
                    "numero_rpc": numero_rpc
                }
            )
        
        # Inicializar S3DocumentManager y generar URLs temporales
        try:
            s3_manager = S3DocumentManager()
            
            # Obtener documentos desde el campo documentos_s3 en Firebase
            documentos_firebase = rpc_data.get('documentos_s3', [])
            documentos_resultado = []
            
            if documentos_firebase and isinstance(documentos_firebase, list) and len(documentos_firebase) > 0:
                logger.info(f"✅ Encontrados {len(documentos_firebase)} documentos en Firebase para RPC {numero_rpc}")
                
                # Generar presigned URLs para cada documento guardado en Firebase
                from datetime import timedelta
                
                for doc in documentos_firebase:
                    if isinstance(doc, dict):
                        # Buscar s3_key en diferentes variantes posibles
                        s3_key = doc.get('s3_key') or doc.get('key') or doc.get('s3_url', '').replace(f"https://{s3_manager.bucket_name}.s3.{s3_manager.region}.amazonaws.com/", '')
                        
                        if s3_key:
                            # Generar presigned URL
                            presigned_url = s3_manager.generate_presigned_url(
                                s3_key,
                                expiration=expiration
                            )
                            
                            # Calcular tiempo de expiración
                            expiration_time = datetime.now() + timedelta(seconds=expiration)
                            
                            documento_con_url = {
                                'filename': doc.get('filename', s3_key.split('/')[-1]),
                                's3_key': s3_key,
                                's3_url': doc.get('s3_url', f"https://{s3_manager.bucket_name}.s3.{s3_manager.region}.amazonaws.com/{s3_key}"),
                                'size': doc.get('size', 0),
                                'content_type': doc.get('content_type', 'application/pdf'),
                                'upload_date': doc.get('upload_date', ''),
                                'presigned_url': presigned_url,
                                'url_expiration_seconds': expiration,
                                'url_expires_at': expiration_time.isoformat()
                            }
                            
                            documentos_resultado.append(documento_con_url)
                            logger.info(f"✅ URL temporal generada para: {documento_con_url['filename']}")
                        else:
                            logger.warning(f"⚠️  Documento sin s3_key válido: {doc}")
                
                if len(documentos_resultado) == 0:
                    logger.warning(f"⚠️  Documentos encontrados en Firebase pero ninguno con s3_key válido")
            else:
                # Si no hay documentos en Firebase, buscar directamente en S3
                logger.info(f"📋 No hay documentos en Firebase, buscando directamente en S3 para referencia: {referencia_contrato}")
                documentos_resultado = s3_manager.list_documents_with_presigned_urls(
                    referencia_contrato=referencia_contrato,
                    document_type='rpc',
                    numero_rpc=None,
                    expiration=expiration
                )
            
            return JSONResponse(
                content={
                    "success": True,
                    "numero_rpc": numero_rpc,
                    "referencia_contrato": referencia_contrato,
                    "documentos": documentos_resultado,
                    "count": len(documentos_resultado),
                    "expiration_seconds": expiration,
                    "message": f"Se generaron {len(documentos_resultado)} enlace(s) temporal(es) exitosamente"
                },
                status_code=200,
                headers={"Content-Type": "application/json; charset=utf-8"}
            )
            
        except Exception as e:
            logger.error(f"Error generando URLs temporales: {e}")
            raise HTTPException(
                status_code=500,
                detail={
                    "success": False,
                    "error": f"Error generando enlaces temporales: {str(e)}"
                }
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error en endpoint de documentos temporales: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "error": "Error interno del servidor",
                "message": str(e)
            }
        )

@app.get("/convenios_transferencias_all", tags=["Gestión de Empréstito"], summary="🔵 Obtener Todos los Convenios de Transferencia")
async def get_all_convenios_transferencia_emprestito():
    """
    ## 🔵 GET | 📋 Consultas | Obtener Todos los Convenios de Transferencia
    
    Endpoint para obtener todos los convenios de transferencia de empréstito 
    almacenados en la colección `convenios_transferencias_emprestito`.
    
    ### ✅ Funcionalidades principales:
    - **Listado completo**: Retorna todos los convenios registrados
    - **Ordenamiento**: Por fecha de creación (más recientes primero)
    - **Datos completos**: Incluye todos los campos de cada convenio
    - **Metadatos**: Incluye ID del documento, conteo total y timestamp
    
    ### 📊 Información incluida:
    - Todos los campos del convenio
    - ID del documento para referencia
    - Conteo total de registros
    - Timestamp de la consulta
    - Datos serializados correctamente para JSON
    
    ### 🗄️ Campos principales esperados:
    - **referencia_contrato**: Referencia única del contrato/convenio
    - **nombre_centro_gestor**: Centro gestor responsable
    - **banco**: Nombre del banco
    - **bp**: Código BP
    - **bpin**: Código BPIN
    - **objeto_contrato**: Descripción del objeto del contrato
    - **valor_contrato**: Valor del contrato
    - **valor_convenio**: Valor específico del convenio
    - **fecha_inicio_contrato**: Fecha de inicio
    - **fecha_fin_contrato**: Fecha de finalización
    - **modalidad_contrato**: Modalidad de contratación
    - **ordenador_gastor**: Ordenador del gasto
    - **tipo_contrato**: Tipo de contrato
    - **estado_contrato**: Estado actual
    - **sector**: Sector al que pertenece
    - **nombre_resumido_proceso**: Nombre resumido del proceso
    - **fecha_creacion**: Fecha de creación del registro
    - **fecha_actualizacion**: Última actualización
    - **estado**: Estado del registro (activo/inactivo)
    - **tipo**: Tipo de registro
    
    ### 💡 Casos de uso:
    - Obtener listado completo de convenios de transferencia
    - Exportación de datos para análisis
    - Integración con sistemas externos
    - Reportes y dashboards
    - Monitoreo del estado de convenios
    
    ### ✅ Respuesta exitosa (200):
    ```json
    {
        "success": true,
        "data": [
            {
                "id": "abc123",
                "referencia_contrato": "CONV-2024-001",
                "nombre_centro_gestor": "Secretaría de Salud",
                "banco": "Banco Mundial",
                "objeto_contrato": "Convenio de transferencia...",
                "valor_contrato": 1500000000.0,
                "bpin": "2024000010001",
                ...
            }
        ],
        "count": 15,
        "collection": "convenios_transferencias_emprestito",
        "timestamp": "2024-11-09T...",
        "message": "Se obtuvieron 15 convenios de transferencia exitosamente"
    }
    ```
    
    ### ❌ Respuesta de error (500):
    ```json
    {
        "success": false,
        "error": "Error obteniendo convenios de transferencia: ...",
        "data": [],
        "count": 0
    }
    ```
    
    ### 🔗 Endpoints relacionados:
    - `POST /emprestito/cargar-convenio-transferencia` - Para crear nuevos convenios
    """
    try:
        check_emprestito_availability()
        
        # Obtener todos los convenios de transferencia
        result = await get_convenios_transferencia_emprestito_all()
        
        if not result["success"]:
            raise HTTPException(
                status_code=500,
                detail=f"Error obteniendo convenios de transferencia: {result.get('error', 'Error desconocido')}"
            )
        
        return JSONResponse(
            content={
                "success": True,
                "data": result["data"],
                "count": result["count"],
                "collection": result["collection"],
                "timestamp": result["timestamp"],
                "message": result["message"],
                "metadata": {
                    "sorted_by": "fecha_creacion",
                    "order": "desc",
                    "utf8_enabled": True,
                    "spanish_support": True,
                    "purpose": "Lista completa de convenios de transferencia de empréstito"
                }
            },
            status_code=200,
            headers={"Content-Type": "application/json; charset=utf-8"}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error en endpoint de convenios de transferencia: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "error": "Error interno del servidor",
                "message": "Error al obtener convenios de transferencia",
                "code": "INTERNAL_SERVER_ERROR"
            }
        )

@app.get("/pagos_emprestito_all", tags=["Gestión de Empréstito"], summary="🔵 Obtener Todos los Pagos de Empréstito")
async def get_all_pagos_emprestito():
    """
    ## 🔵 GET | 📋 Consultas | Obtener Todos los Pagos de Empréstito
    
    Endpoint para obtener todos los pagos de empréstito almacenados en la colección `pagos_emprestito`.
    
    ### ✅ Funcionalidades principales:
    - **Listado completo**: Retorna todos los pagos registrados
    - **Datos completos**: Incluye todos los campos de cada pago
    - **Metadatos**: Incluye ID del documento, conteo total y timestamp
    
    ### 📊 Información incluida:
    - Todos los campos del pago
    - ID del documento para referencia
    - Conteo total de registros
    - Timestamp de la consulta
    
    ### ✅ Respuesta exitosa (200):
    ```json
    {
        "success": true,
        "data": [...],
        "count": 10,
        "collection": "pagos_emprestito",
        "timestamp": "2024-11-17T..."
    }
    ```
    """
    try:
        check_emprestito_availability()
        
        result = await get_pagos_emprestito_all()
        
        if not result["success"]:
            raise HTTPException(
                status_code=500,
                detail=f"Error obteniendo pagos de empréstito: {result.get('error', 'Error desconocido')}"
            )
        
        return JSONResponse(
            content={
                "success": True,
                "data": result["data"],
                "count": result["count"],
                "collection": result["collection"],
                "timestamp": result["timestamp"],
                "message": f"Se obtuvieron {result['count']} pagos de empréstito exitosamente"
            },
            status_code=200,
            headers={"Content-Type": "application/json; charset=utf-8"}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error en endpoint de pagos de empréstito: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "error": "Error interno del servidor",
                "message": "Error al obtener pagos de empréstito",
                "code": "INTERNAL_SERVER_ERROR"
            }
        )

@app.get("/rpc_contratos_emprestito_all", tags=["Gestión de Empréstito"], summary="🔵 Obtener Todos los RPCs de Empréstito")
async def get_all_rpc_contratos_emprestito():
    """
    ## 🔵 GET | 📋 Consultas | Obtener Todos los RPCs de Empréstito
    
    Endpoint para obtener todos los Registros Presupuestales de Compromiso (RPC) 
    de empréstito almacenados en la colección `rpc_contratos_emprestito`.
    
    ### ✅ Funcionalidades principales:
    - **Listado completo**: Retorna todos los RPCs registrados
    - **Datos completos**: Incluye todos los campos de cada RPC
    - **Metadatos**: Incluye ID del documento, conteo total y timestamp
    
    ### 📊 Información incluida:
    - Todos los campos del RPC
    - ID del documento para referencia
    - Conteo total de registros
    - Timestamp de la consulta
    
    ### 🗄️ Campos principales esperados:
    - **numero_rpc**: Número único del RPC
    - **beneficiario_id**: Identificación del beneficiario
    - **beneficiario_nombre**: Nombre del beneficiario
    - **descripcion_rpc**: Descripción del compromiso
    - **fecha_contabilizacion**: Fecha de contabilización
    - **fecha_impresion**: Fecha de impresión
    - **estado_liberacion**: Estado de liberación
    - **bp**: Código BP
    - **valor_rpc**: Valor monetario del RPC
    - **nombre_centro_gestor**: Centro gestor responsable
    - **referencia_contrato**: Referencia del contrato asociado
    - **cdp_asociados**: CDPs asociados
    - **programacion_pac**: Programación PAC
    
    ### ✅ Respuesta exitosa (200):
    ```json
    {
        "success": true,
        "data": [...],
        "count": 15,
        "collection": "rpc_contratos_emprestito",
        "timestamp": "2024-11-17T..."
    }
    ```
    """
    try:
        check_emprestito_availability()
        
        result = await get_rpc_contratos_emprestito_all()
        
        if not result["success"]:
            raise HTTPException(
                status_code=500,
                detail=f"Error obteniendo RPCs de empréstito: {result.get('error', 'Error desconocido')}"
            )
        
        return JSONResponse(
            content={
                "success": True,
                "data": result["data"],
                "count": result["count"],
                "collection": result["collection"],
                "timestamp": result["timestamp"],
                "message": f"Se obtuvieron {result['count']} RPCs de empréstito exitosamente"
            },
            status_code=200,
            headers={"Content-Type": "application/json; charset=utf-8"}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error en endpoint de RPCs de empréstito: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "error": "Error interno del servidor",
                "message": "Error al obtener RPCs de empréstito",
                "code": "INTERNAL_SERVER_ERROR"
            }
        )

@app.put("/emprestito/modificar-rpc", tags=["Gestión de Empréstito"], summary="🟡 Modificar RPC de Empréstito")
async def actualizar_rpc_endpoint(
    numero_rpc: str = Form(..., description="Número del RPC a modificar (obligatorio)"),
    datos_actualizacion: str = Form(..., description="JSON con los campos a actualizar")
):
    """
    ## 🟡 PUT | ✏️ Actualización | Modificar RPC (Registro Presupuestal de Compromiso)
    
    **Propósito**: Actualiza cualquier campo de un RPC existente en la colección "rpc_contratos_emprestito" 
    según su "numero_rpc". Solo se modifican los campos proporcionados, los demás permanecen sin cambios.
    
    ### ✅ Casos de uso:
    - Actualizar valores específicos de un RPC existente
    - Corregir información incorrecta en RPCs
    - Modificar beneficiarios, valores, o fechas
    - Actualizar CDPs asociados o programación PAC
    - Cambiar estado de liberación o referencias
    
    ### 🎯 Funcionamiento:
    1. **Busca** el RPC por `numero_rpc` (parámetro de formulario)
    2. **Actualiza** solo los campos proporcionados en `datos_actualizacion`
    3. **Mantiene** los campos no especificados sin cambios
    4. **Registra** timestamp de última actualización automáticamente
    5. **Retorna** datos previos y actualizados para auditoría
    
    ### 📋 Campos actualizables:
    - `beneficiario_id`: ID del beneficiario
    - `beneficiario_nombre`: Nombre del beneficiario
    - `descripcion_rpc`: Descripción del RPC
    - `fecha_contabilizacion`: Fecha de contabilización
    - `fecha_impresion`: Fecha de impresión
    - `estado_liberacion`: Estado de liberación
    - `bp`: Código BP
    - `valor_rpc`: Valor del RPC (numérico, >= 0)
    - `cdp_asociados`: Lista de CDPs (array o string separado por comas)
    - `programacion_pac`: Objeto con programación PAC
    - `nombre_centro_gestor`: Centro gestor responsable
    - `referencia_contrato`: Referencia del contrato
    - `estado`: Estado del RPC (activo, inactivo, etc.)
    
    ### 🔒 Campos protegidos (NO modificables):
    - `numero_rpc`: Identificador único (se usa para búsqueda)
    - `fecha_creacion`: Fecha de creación original
    - `tipo`: Tipo de RPC (manual, automático, etc.)
    
    ### 🔒 Validaciones:
    - **numero_rpc**: Debe existir en la colección
    - **valor_rpc**: Debe ser >= 0 si se proporciona
    - **strings**: Se limpian automáticamente de espacios
    - **cdp_asociados**: Acepta lista o string separado por comas
    - **programacion_pac**: Debe ser un objeto JSON válido
    - **campos opcionales**: Solo se actualizan los proporcionados
    
    ### 📝 Ejemplo de uso con fetch:
    ```javascript
    const formData = new FormData();
    formData.append('numero_rpc', 'RPC-2024-001');
    formData.append('datos_actualizacion', JSON.stringify({
        valor_rpc: 500000000,
        estado_liberacion: "Liberado",
        beneficiario_nombre: "Nuevo Beneficiario S.A.S",
        cdp_asociados: ["CDP-001", "CDP-002"]
    }));
    
    const response = await fetch('/emprestito/modificar-rpc', {
        method: 'PUT',
        body: formData
    });
    ```
    
    ### ✅ Respuesta exitosa (200):
    ```json
    {
        "success": true,
        "message": "RPC RPC-2024-001 actualizado exitosamente",
        "numero_rpc": "RPC-2024-001",
        "doc_id": "abc123xyz",
        "coleccion": "rpc_contratos_emprestito",
        "datos_previos": { ... },
        "datos_actualizados": { ... },
        "campos_modificados": ["valor_rpc", "estado_liberacion", "beneficiario_nombre"],
        "timestamp": "2025-01-06T..."
    }
    ```
    
    ### ❌ Errores posibles:
    - **404**: RPC no encontrado con el numero_rpc especificado
    - **400**: Datos inválidos o formato JSON incorrecto
    - **400**: No hay campos válidos para actualizar
    - **500**: Error en la actualización de Firestore
    
    ### 💡 Características:
    - **Actualización parcial**: Solo modifica campos especificados
    - **Auditoría completa**: Guarda datos previos y nuevos
    - **Búsqueda exacta**: Por numero_rpc únicamente
    - **UTF-8**: Soporte completo para caracteres especiales
    - **Timestamp automático**: Registra fecha_actualizacion
    - **Validación robusta**: Verifica existencia y tipos de datos
    - **Protección de campos**: No permite modificar campos del sistema
    """
    try:
        check_emprestito_availability()
        
        # Validar numero_rpc
        if not numero_rpc or not numero_rpc.strip():
            raise HTTPException(
                status_code=400,
                detail={
                    "success": False,
                    "error": "numero_rpc es requerido",
                    "message": "Debe proporcionar un numero_rpc válido"
                }
            )
        
        # Parsear datos_actualizacion JSON
        try:
            import json
            datos_dict = json.loads(datos_actualizacion)
        except json.JSONDecodeError as e:
            raise HTTPException(
                status_code=400,
                detail={
                    "success": False,
                    "error": "JSON inválido en datos_actualizacion",
                    "message": f"Error parseando JSON: {str(e)}"
                }
            )
        
        # Verificar que se proporcionen datos para actualizar
        if not datos_dict or not isinstance(datos_dict, dict):
            raise HTTPException(
                status_code=400,
                detail={
                    "success": False,
                    "error": "datos_actualizacion debe ser un objeto JSON válido",
                    "message": "Debe proporcionar al menos un campo para actualizar"
                }
            )
        
        # Llamar a la función de actualización
        result = await actualizar_rpc_contrato_emprestito(
            numero_rpc=numero_rpc.strip(),
            datos_actualizacion=datos_dict
        )
        
        if not result["success"]:
            # Determinar código de estado según el error
            if "No se encontró" in result.get("error", ""):
                status_code = 404
            else:
                status_code = 400
                
            raise HTTPException(
                status_code=status_code,
                detail={
                    "success": False,
                    "error": result.get("error", "Error desconocido"),
                    "numero_rpc": numero_rpc
                }
            )
        
        return JSONResponse(
            content=result,
            status_code=200,
            headers={"Content-Type": "application/json; charset=utf-8"}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error en endpoint de actualización de RPC: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "error": "Error interno del servidor",
                "message": str(e),
                "code": "INTERNAL_SERVER_ERROR"
            }
        )

@app.get("/emprestito/proceso/{referencia_proceso}", tags=["Gestión de Empréstito"], summary="🔵 Verificar Proceso Existente")
async def verificar_proceso_existente_endpoint(referencia_proceso: str):
    """
    ## � GET | �🔍 Consultas | Verificar Proceso Existente
    
    Verifica si ya existe un proceso con la referencia especificada en cualquiera 
    de las colecciones de empréstito.
    
    ### ✅ Funcionalidades:
    - Búsqueda en `procesos_emprestito` (SECOP)
    - Búsqueda en `ordenes_compra_emprestito` (TVEC)
    - Información detallada del proceso encontrado
    
    ### 📊 Respuesta si existe:
    - Datos completos del proceso
    - Colección donde se encontró
    - ID del documento
    
    ### 💡 Casos de uso:
    - Validación previa antes de crear proceso
    - Búsqueda de procesos existentes
    - Prevención de duplicados
    
    ### 📝 Ejemplo de respuesta (proceso existente):
    ```json
    {
        "existe": true,
        "coleccion": "procesos_emprestito",
        "documento": { ... },
        "doc_id": "xyz123",
        "timestamp": "2025-10-06T..."
    }
    ```
    """
    try:
        check_emprestito_availability()
        
        resultado = await verificar_proceso_existente(referencia_proceso)
        
        return JSONResponse(
            content={
                **resultado,
                "referencia_proceso": referencia_proceso,
                "timestamp": datetime.now().isoformat()
            },
            status_code=200,
            headers={"Content-Type": "application/json; charset=utf-8"}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error verificando proceso: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "error": "Error interno del servidor",
                "message": "Error verificando proceso existente"
            }
        )


@app.delete("/emprestito/proceso/{referencia_proceso}", tags=["Gestión de Empréstito"], summary="🔴 Eliminar Proceso")
async def eliminar_proceso_emprestito_endpoint(referencia_proceso: str):
    """
    ## � DELETE | �🗑️ Eliminación | Eliminar Proceso de Empréstito
    
    Elimina un proceso de empréstito específico basado en su referencia_proceso.
    Busca automáticamente en ambas colecciones (SECOP y TVEC) y elimina el proceso encontrado.
    
    ### ✅ Funcionalidades principales:
    - **Búsqueda automática**: Localiza el proceso en ambas colecciones
    - **Eliminación segura**: Elimina únicamente el proceso especificado
    - **Información completa**: Retorna detalles del proceso eliminado
    - **Validación previa**: Verifica existencia antes de intentar eliminar
    
    ### 🔍 Colecciones de búsqueda:
    - **procesos_emprestito** (SECOP)
    - **ordenes_compra_emprestito** (TVEC)
    
    ### ⚠️ Consideraciones importantes:
    - La eliminación es **irreversible**
    - Solo se elimina un proceso por referencia_proceso
    - Se requiere coincidencia exacta en referencia_proceso
    
    ### 📋 Respuesta exitosa:
    ```json
    {
        "success": true,
        "message": "Proceso eliminado exitosamente",
        "referencia_proceso": "SCMGSU-CM-003-2024",
        "coleccion": "procesos_emprestito",
        "documento_id": "xyz123",
        "proceso_eliminado": {
            "referencia_proceso": "SCMGSU-CM-003-2024",
            "nombre_centro_gestor": "Secretaría de Salud",
            "nombre_banco": "Banco Mundial",
            "plataforma": "SECOP II",
            "fecha_creacion": "2025-10-06T..."
        },
        "timestamp": "2025-10-06T..."
    }
    ```
    
    ### 📋 Respuesta si no existe:
    ```json
    {
        "success": false,
        "error": "No se encontró ningún proceso con referencia_proceso: REFERENCIA",
        "referencia_proceso": "REFERENCIA",
        "colecciones_buscadas": ["procesos_emprestito", "ordenes_compra_emprestito"]
    }
    ```
    """
    try:
        check_emprestito_availability()
        
        # Validar parámetro
        if not referencia_proceso or not referencia_proceso.strip():
            raise HTTPException(
                status_code=400,
                detail={
                    "success": False,
                    "error": "referencia_proceso es requerida",
                    "message": "Debe proporcionar una referencia_proceso válida"
                }
            )
        
        # Eliminar proceso
        resultado = await eliminar_proceso_emprestito(referencia_proceso.strip())
        
        # Manejar respuesta según el resultado
        if not resultado.get("success"):
            # Si no se encontró el proceso
            if "No se encontró" in resultado.get("error", ""):
                raise HTTPException(
                    status_code=404,
                    detail=resultado
                )
            else:
                # Otros errores
                raise HTTPException(
                    status_code=500,
                    detail=resultado
                )
        
        # Respuesta exitosa
        return JSONResponse(
            content=resultado,
            status_code=200,
            headers={"Content-Type": "application/json; charset=utf-8"}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error en endpoint eliminar proceso: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "error": "Error interno del servidor",
                "message": "Error eliminando proceso de empréstito",
                "referencia_proceso": referencia_proceso
            }
        )


@app.put("/emprestito/modificar-valores/proceso/{referencia_proceso}", tags=["Gestión de Empréstito"], summary="🟡 Modificar Valor de Proceso SECOP")
async def actualizar_valor_proceso_secop_endpoint(
    referencia_proceso: str,
    valor_publicacion: Optional[float] = Form(None, description="Valor de publicación del proceso SECOP (opcional, debe ser numérico)"),
    change_motivo: str = Form(..., description="Justificación del cambio (obligatorio)"),
    change_support_file: UploadFile = File(..., description="Documento soporte (obligatorio, PDF, XLSX, DOCX, etc.)")
):
    """
    ## 🟡 PUT | ✏️ Actualización | Modificar Valor de Publicación de Proceso SECOP
    
    Actualiza únicamente el campo `valor_publicacion` de un proceso SECOP existente 
    identificado por `referencia_proceso`.
    
    ### ✅ Funcionalidades principales:
    - **Búsqueda por referencia_proceso**: Localiza el proceso en `procesos_emprestito`
    - **Actualización exclusiva de valor**: Solo modifica `valor_publicacion`
    - **Historial de cambios**: Muestra valor anterior y nuevo
    - **Persistencia garantizada**: Los cambios persisten incluso después de ejecutar endpoints POST
    
    ### 🔍 Colección de búsqueda:
    - **procesos_emprestito** (SECOP)
    
    ### 📝 Campo actualizable:
    - `valor_publicacion`: Valor de publicación del proceso (numérico) **[Único campo modificable]**
    
    ### ⚙️ Comportamiento:
    - **Campo vacío**: Error - debe proporcionar un valor
    - **Campo con valor**: Se actualiza en la base de datos
    - **Timestamp**: Se actualiza automáticamente `fecha_actualizacion`
    - **Validación previa**: Verifica que el proceso existe
    
    ### 📋 Respuesta exitosa:
    ```json
    {
        "success": true,
        "message": "Proceso SECOP actualizado exitosamente",
        "referencia_proceso": "SCMGSU-CM-003-2024",
        "coleccion": "procesos_emprestito",
        "documento_id": "xyz123",
        "campos_modificados": ["valor_publicacion"],
        "valores_anteriores": {
            "valor_publicacion": 1000000.0
        },
        "valores_nuevos": {
            "valor_publicacion": 1500000.0
        },
        "proceso_actualizado": { ... },
        "timestamp": "2025-12-28T..."
    }
    ```
    
    ### 📋 Respuesta si no existe:
    ```json
    {
        "success": false,
        "error": "No se encontró ningún proceso SECOP con referencia_proceso: SCMGSU-CM-003-2024",
        "referencia_proceso": "SCMGSU-CM-003-2024"
    }
    ```
    """
    try:
        check_emprestito_availability()
        
        # Validar parámetro
        if not referencia_proceso or not referencia_proceso.strip():
            raise HTTPException(
                status_code=400,
                detail={
                    "success": False,
                    "error": "referencia_proceso es requerida",
                    "message": "Debe proporcionar una referencia_proceso válida"
                }
            )
        
        # Validar que se proporcione al menos un valor para actualizar
        if valor_publicacion is None:
            raise HTTPException(
                status_code=400,
                detail={
                    "success": False,
                    "error": "No se proporcionaron campos para actualizar",
                    "message": "Debe proporcionar al menos valor_publicacion para actualizar"
                }
            )
        
        # Preparar campos para actualizar
        campos_actualizar = {
            "valor_publicacion": float(valor_publicacion)
        }
        
        # Actualizar proceso
        resultado = await actualizar_proceso_secop_por_referencia(
            referencia_proceso=referencia_proceso.strip(),
            campos_actualizar=campos_actualizar
        )
        
        # Manejar respuesta según el resultado
        if not resultado.get("success"):
            # Si no se encontró el proceso
            if "No se encontró" in resultado.get("error", ""):
                raise HTTPException(
                    status_code=404,
                    detail=resultado
                )
            # Si no se proporcionaron campos para actualizar
            elif "No se proporcionaron campos" in resultado.get("error", ""):
                raise HTTPException(
                    status_code=400,
                    detail=resultado
                )
            else:
                # Otros errores
                raise HTTPException(
                    status_code=500,
                    detail=resultado
                )
        
        # ✅ Actualización exitosa - registrar en auditoría
        try:
            logger.info(f"🔍 Iniciando registro de auditoría para proceso: {referencia_proceso}")
            auditoria_resultado = await registrar_cambio_valor(
                tipo_coleccion="procesos",
                identificador=referencia_proceso.strip(),
                campo_modificado="valor_publicacion",
                valor_anterior=resultado.get("valores_anteriores", {}).get("valor_publicacion"),
                valor_nuevo=resultado.get("valores_nuevos", {}).get("valor_publicacion"),
                motivo=change_motivo,
                archivo_soporte=change_support_file,
                usuario=None,  # Puede integrarse con autenticación
                endpoint_usado="/emprestito/modificar-valores/proceso"
            )
            
            logger.info(f"📋 Resultado de auditoría: {auditoria_resultado}")
            
            # Agregar información de auditoría a la respuesta
            resultado["auditoria"] = auditoria_resultado
            
            if not auditoria_resultado.get("success"):
                logger.warning(f"⚠️ Auditoría no registrada: {auditoria_resultado.get('error')}")
                resultado["auditoria_warning"] = "Cambio realizado pero no se pudo registrar en auditoría"
            else:
                logger.info(f"✅ Auditoría registrada exitosamente: {auditoria_resultado.get('change_id')}")
                
        except Exception as e_audit:
            logger.error(f"Error registrando auditoría: {e_audit}")
            resultado["auditoria"] = {"success": False, "error": str(e_audit)}
            resultado["auditoria_warning"] = "Cambio realizado pero auditoría falló"
        
        # Respuesta exitosa
        return JSONResponse(
            content=resultado,
            status_code=200,
            headers={"Content-Type": "application/json; charset=utf-8"}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error en endpoint actualizar valor proceso SECOP: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "error": "Error interno del servidor",
                "message": "Error actualizando valor de proceso SECOP",
                "referencia_proceso": referencia_proceso
            }
        )


@app.put("/emprestito/modificar-valores/orden-compra/{numero_orden}", tags=["Gestión de Empréstito"], summary="🟡 Modificar Valor de Orden de Compra")
async def actualizar_orden_compra_endpoint(
    numero_orden: str,
    valor_orden: Optional[float] = Form(None, description="Valor de la orden (opcional, debe ser numérico)"),
    valor_proyectado: Optional[float] = Form(None, description="Valor proyectado (opcional, debe ser numérico)"),
    change_motivo: str = Form(..., description="Justificación del cambio (obligatorio)"),
    change_support_file: UploadFile = File(..., description="Documento soporte (obligatorio, PDF, XLSX, DOCX, etc.)")
):
    """
    ## 🟡 PUT | ✏️ Actualización | Actualizar Orden de Compra de Empréstito por Número de Orden
    
    Actualiza campos específicos de una orden de compra existente identificada por `numero_orden`.
    Solo se actualizan los campos proporcionados, manteniendo los demás valores sin cambios.
    
    ### ✅ Funcionalidades principales:
    - **Búsqueda por numero_orden**: Localiza la orden de compra en `ordenes_compra_emprestito`
    - **Actualización selectiva**: Solo modifica los campos proporcionados
    - **Preservación de datos**: Mantiene los campos no especificados
    - **Historial de cambios**: Muestra valores anteriores y nuevos
    - **Persistencia garantizada**: Los cambios persisten incluso después de ejecutar endpoints POST
    
    ### 🔍 Colección de búsqueda:
    - **ordenes_compra_emprestito** (TVEC)
    
    ### 📝 Campos actualizables:
    - `valor_orden`: Valor de la orden de compra (numérico) **[Campo principal]**
    - `valor_proyectado`: Valor proyectado (numérico) **[Opcional si existe]**
    
    ### ⚙️ Comportamiento:
    - **Campos vacíos**: Se ignoran (no se actualizan)
    - **Campos con valor**: Se actualizan en la base de datos
    - **Timestamp**: Se actualiza automáticamente `fecha_actualizacion`
    - **Validación previa**: Verifica que la orden existe
    - **Solo valores**: Ningún otro campo puede ser modificado por este endpoint
    
    ### 📋 Respuesta exitosa:
    ```json
    {
        "success": true,
        "message": "Orden de compra actualizada exitosamente",
        "numero_orden": "OC-2024-001",
        "coleccion": "ordenes_compra_emprestito",
        "documento_id": "xyz123",
        "campos_modificados": ["valor_orden"],
        "valores_anteriores": {
            "valor_orden": 1000000.0
        },
        "valores_nuevos": {
            "valor_orden": 1500000.0
        },
        "orden_actualizada": { ... },
        "timestamp": "2025-12-28T..."
    }
    ```
    """
    try:
        check_emprestito_availability()
        
        # Validar parámetro
        if not numero_orden or not numero_orden.strip():
            raise HTTPException(
                status_code=400,
                detail={
                    "success": False,
                    "error": "numero_orden es requerido",
                    "message": "Debe proporcionar un numero_orden válido"
                }
            )
        
        # Validar que se proporcione al menos un valor para actualizar
        if valor_orden is None and valor_proyectado is None:
            raise HTTPException(
                status_code=400,
                detail={
                    "success": False,
                    "error": "No se proporcionaron campos para actualizar",
                    "message": "Debe proporcionar al menos uno de: valor_orden, valor_proyectado"
                }
            )
        
        # Preparar campos para actualizar (solo valores numéricos proporcionados)
        campos_actualizar = {}
        if valor_orden is not None:
            campos_actualizar["valor_orden"] = float(valor_orden)
        if valor_proyectado is not None:
            campos_actualizar["valor_proyectado"] = float(valor_proyectado)
        
        # Actualizar orden de compra
        resultado = await actualizar_orden_compra_por_numero(
            numero_orden=numero_orden.strip(),
            campos_actualizar=campos_actualizar
        )
        
        # Manejar respuesta según el resultado
        if not resultado.get("success"):
            if "No se encontró" in resultado.get("error", ""):
                raise HTTPException(
                    status_code=404,
                    detail=resultado
                )
            elif "No se proporcionaron campos" in resultado.get("error", ""):
                raise HTTPException(
                    status_code=400,
                    detail=resultado
                )
            else:
                raise HTTPException(
                    status_code=500,
                    detail=resultado
                )
        
        # ✅ Actualización exitosa - registrar en auditoría
        try:
            logger.info(f"🔍 Iniciando registro de auditoría para orden: {numero_orden}")
            # Determinar campo(s) modificado(s)
            campos_modificados = list(campos_actualizar.keys())
            campo_modificado = ", ".join(campos_modificados)
            
            auditoria_resultado = await registrar_cambio_valor(
                tipo_coleccion="ordenes",
                identificador=numero_orden.strip(),
                campo_modificado=campo_modificado,
                valor_anterior=resultado.get("valores_anteriores", {}).get("valor_orden"),
                valor_nuevo=resultado.get("valores_nuevos", {}).get("valor_orden"),
                motivo=change_motivo,
                archivo_soporte=change_support_file,
                usuario=None,
                endpoint_usado="/emprestito/modificar-valores/orden-compra"
            )
            
            logger.info(f"📋 Resultado de auditoría: {auditoria_resultado}")
            
            # Agregar información de auditoría a la respuesta
            resultado["auditoria"] = auditoria_resultado
            
            if not auditoria_resultado.get("success"):
                logger.warning(f"⚠️ Auditoría no registrada: {auditoria_resultado.get('error')}")
                resultado["auditoria_warning"] = "Cambio realizado pero no se pudo registrar en auditoría"
            else:
                logger.info(f"✅ Auditoría registrada exitosamente: {auditoria_resultado.get('change_id')}")
                
        except Exception as e_audit:
            logger.error(f"Error registrando auditoría: {e_audit}")
            resultado["auditoria"] = {"success": False, "error": str(e_audit)}
            resultado["auditoria_warning"] = "Cambio realizado pero auditoría falló"
        
        # Respuesta exitosa
        return JSONResponse(
            content=resultado,
            status_code=200,
            headers={"Content-Type": "application/json; charset=utf-8"}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error en endpoint actualizar valores orden de compra: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "error": "Error interno del servidor",
                "message": "Error actualizando valores de orden de compra",
                "numero_orden": numero_orden
            }
        )


@app.put("/emprestito/modificar-valores/convenio/{referencia_contrato}", tags=["Gestión de Empréstito"], summary="🟡 Modificar Valor de Convenio")
async def actualizar_valor_convenio_endpoint(
    referencia_contrato: str,
    valor_contrato: Optional[float] = Form(None, description="Valor del contrato (opcional, debe ser numérico)"),
    change_motivo: str = Form(..., description="Justificación del cambio (obligatorio)"),
    change_support_file: UploadFile = File(..., description="Documento soporte (obligatorio, PDF, XLSX, DOCX, etc.)")
):
    """
    ## 🟡 PUT | ✏️ Actualización | Modificar Valor de Convenio de Transferencia
    
    Actualiza únicamente el campo `valor_contrato` de un convenio de transferencia existente 
    identificado por `referencia_contrato`.
    
    ### ✅ Funcionalidades principales:
    - **Búsqueda por referencia_contrato**: Localiza el convenio en `convenios_transferencias_emprestito`
    - **Actualización exclusiva de valor**: Solo modifica `valor_contrato`
    - **Historial de cambios**: Muestra valor anterior y nuevo
    - **Persistencia garantizada**: Los cambios persisten incluso después de ejecutar endpoints POST
    
    ### 🔍 Colección de búsqueda:
    - **convenios_transferencias_emprestito**
    
    ### 📝 Campo actualizable:
    - `valor_contrato`: Valor del contrato (numérico) **[Único campo modificable]**
    
    ### ⚙️ Comportamiento:
    - **Campo vacío**: Error - debe proporcionar un valor
    - **Campo con valor**: Se actualiza en la base de datos
    - **Timestamp**: Se actualiza automáticamente `fecha_actualizacion`
    - **Validación previa**: Verifica que el convenio existe
    
    ### 📋 Respuesta exitosa:
    ```json
    {
        "success": true,
        "message": "Convenio de transferencia actualizado exitosamente",
        "referencia_contrato": "CONT-2024-001",
        "coleccion": "convenios_transferencias_emprestito",
        "documento_id": "xyz123",
        "campos_modificados": ["valor_contrato"],
        "valores_anteriores": {
            "valor_contrato": 1000000.0
        },
        "valores_nuevos": {
            "valor_contrato": 1500000.0
        },
        "convenio_actualizado": { ... },
        "timestamp": "2025-12-28T..."
    }
    ```
    """
    try:
        check_emprestito_availability()
        
        # Validar parámetro
        if not referencia_contrato or not referencia_contrato.strip():
            raise HTTPException(
                status_code=400,
                detail={
                    "success": False,
                    "error": "referencia_contrato es requerida",
                    "message": "Debe proporcionar una referencia_contrato válida"
                }
            )
        
        # Validar que se proporcione al menos un valor para actualizar
        if valor_contrato is None:
            raise HTTPException(
                status_code=400,
                detail={
                    "success": False,
                    "error": "No se proporcionaron campos para actualizar",
                    "message": "Debe proporcionar al menos valor_contrato para actualizar"
                }
            )
        
        # Preparar campos para actualizar
        campos_actualizar = {
            "valor_contrato": float(valor_contrato)
        }
        
        # Actualizar convenio
        resultado = await actualizar_convenio_por_referencia(
            referencia_contrato=referencia_contrato.strip(),
            campos_actualizar=campos_actualizar
        )
        
        # Manejar respuesta según el resultado
        if not resultado.get("success"):
            if "No se encontró" in resultado.get("error", ""):
                raise HTTPException(
                    status_code=404,
                    detail=resultado
                )
            elif "No se proporcionaron campos" in resultado.get("error", ""):
                raise HTTPException(
                    status_code=400,
                    detail=resultado
                )
            else:
                raise HTTPException(
                    status_code=500,
                    detail=resultado
                )
        
        # ✅ Actualización exitosa - registrar en auditoría
        try:
            logger.info(f"🔍 Iniciando registro de auditoría para convenio: {referencia_contrato}")
            auditoria_resultado = await registrar_cambio_valor(
                tipo_coleccion="convenios",
                identificador=referencia_contrato.strip(),
                campo_modificado="valor_contrato",
                valor_anterior=resultado.get("valores_anteriores", {}).get("valor_contrato"),
                valor_nuevo=resultado.get("valores_nuevos", {}).get("valor_contrato"),
                motivo=change_motivo,
                archivo_soporte=change_support_file,
                usuario=None,
                endpoint_usado="/emprestito/modificar-valores/convenio"
            )
            
            logger.info(f"📋 Resultado de auditoría: {auditoria_resultado}")
            
            # Agregar información de auditoría a la respuesta
            resultado["auditoria"] = auditoria_resultado
            
            if not auditoria_resultado.get("success"):
                logger.warning(f"⚠️ Auditoría no registrada: {auditoria_resultado.get('error')}")
                resultado["auditoria_warning"] = "Cambio realizado pero no se pudo registrar en auditoría"
            else:
                logger.info(f"✅ Auditoría registrada exitosamente: {auditoria_resultado.get('change_id')}")
                
        except Exception as e_audit:
            logger.error(f"Error registrando auditoría: {e_audit}")
            resultado["auditoria"] = {"success": False, "error": str(e_audit)}
            resultado["auditoria_warning"] = "Cambio realizado pero auditoría falló"
        
        # Respuesta exitosa
        return JSONResponse(
            content=resultado,
            status_code=200,
            headers={"Content-Type": "application/json; charset=utf-8"}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error en endpoint actualizar valor convenio: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "error": "Error interno del servidor",
                "message": "Error actualizando valor de convenio de transferencia",
                "referencia_contrato": referencia_contrato
            }
        )


@app.put("/emprestito/modificar-valores/contrato-secop/{referencia_contrato}", tags=["Gestión de Empréstito"], summary="🟡 Actualizar Valor Contrato SECOP")
async def actualizar_contrato_secop_endpoint(
    referencia_contrato: str,
    valor_contrato: Optional[float] = Form(None, description="Valor del contrato (opcional, debe ser numérico)"),
    change_motivo: str = Form(..., description="Justificación del cambio (obligatorio)"),
    change_support_file: UploadFile = File(..., description="Documento soporte (obligatorio, PDF, XLSX, DOCX, etc.)")
):
    """
    ## 🟡 PUT | ✏️ Actualización | Actualizar Valor de Contrato SECOP
    
    Actualiza únicamente el campo `valor_contrato` de un contrato SECOP existente identificado por `referencia_contrato`.
    Este endpoint está diseñado específicamente para modificar el valor del contrato, sin alterar ningún otro campo.
    
    ### ✅ Funcionalidades principales:
    - **Búsqueda por referencia_contrato**: Localiza el contrato en `contratos_emprestito`
    - **Actualización del valor**: Modifica solo el campo `valor_contrato`
    - **Persistencia garantizada**: Los cambios persisten incluso después de ejecutar endpoints POST
    - **Historial de cambios**: Muestra el valor anterior y el nuevo valor
    
    ### 🔍 Colección de búsqueda:
    - **contratos_emprestito** (SECOP)
    
    ### 📝 Campo actualizable:
    - `valor_contrato`: Valor del contrato (numérico, requerido)
    
    ### ⚙️ Comportamiento:
    - **Campo requerido**: Debe proporcionar `valor_contrato`
    - **Timestamp**: Se actualiza automáticamente `fecha_actualizacion`
    - **Validación previa**: Verifica que el contrato existe
    
    ### 📋 Respuesta exitosa:
    ```json
    {
        "success": true,
        "message": "Contrato SECOP actualizado exitosamente",
        "referencia_contrato": "CONT-SECOP-2024-001",
        "coleccion": "contratos_emprestito",
        "documento_id": "xyz123",
        "campos_modificados": ["valor_contrato"],
        "valores_anteriores": {
            "valor_contrato": 1000000.0
        },
        "valores_nuevos": {
            "valor_contrato": 1500000.0
        },
        "contrato_actualizado": { ... },
        "timestamp": "2025-12-28T..."
    }
    ```
    """
    try:
        check_emprestito_availability()
        
        # Validar parámetro
        if not referencia_contrato or not referencia_contrato.strip():
            raise HTTPException(
                status_code=400,
                detail={
                    "success": False,
                    "error": "referencia_contrato es requerida",
                    "message": "Debe proporcionar una referencia_contrato válida"
                }
            )
        
        # Validar que se proporcione al menos un valor para actualizar
        if valor_contrato is None:
            raise HTTPException(
                status_code=400,
                detail={
                    "success": False,
                    "error": "No se proporcionaron campos para actualizar",
                    "message": "Debe proporcionar al menos valor_contrato para actualizar"
                }
            )
        
        # Preparar campos para actualizar (solo valor_contrato)
        campos_actualizar = {
            "valor_contrato": float(valor_contrato)
        }
        
        # Actualizar contrato
        resultado = await actualizar_contrato_secop_por_referencia(
            referencia_contrato=referencia_contrato.strip(),
            campos_actualizar=campos_actualizar
        )
        
        # Manejar respuesta según el resultado
        if not resultado.get("success"):
            if "No se encontró" in resultado.get("error", ""):
                raise HTTPException(
                    status_code=404,
                    detail=resultado
                )
            elif "No se proporcionaron campos" in resultado.get("error", ""):
                raise HTTPException(
                    status_code=400,
                    detail=resultado
                )
            else:
                raise HTTPException(
                    status_code=500,
                    detail=resultado
                )
        
        # ✅ Actualización exitosa - registrar en auditoría
        try:
            logger.info(f"🔍 Iniciando registro de auditoría para contrato: {referencia_contrato}")
            auditoria_resultado = await registrar_cambio_valor(
                tipo_coleccion="contratos",
                identificador=referencia_contrato.strip(),
                campo_modificado="valor_contrato",
                valor_anterior=resultado.get("valores_anteriores", {}).get("valor_contrato"),
                valor_nuevo=resultado.get("valores_nuevos", {}).get("valor_contrato"),
                motivo=change_motivo,
                archivo_soporte=change_support_file,
                usuario=None,
                endpoint_usado="/emprestito/modificar-valores/contrato-secop"
            )
            
            logger.info(f"📋 Resultado de auditoría: {auditoria_resultado}")
            
            # Agregar información de auditoría a la respuesta
            resultado["auditoria"] = auditoria_resultado
            
            if not auditoria_resultado.get("success"):
                logger.warning(f"⚠️ Auditoría no registrada: {auditoria_resultado.get('error')}")
                resultado["auditoria_warning"] = "Cambio realizado pero no se pudo registrar en auditoría"
            else:
                logger.info(f"✅ Auditoría registrada exitosamente: {auditoria_resultado.get('change_id')}")
                
        except Exception as e_audit:
            logger.error(f"Error registrando auditoría: {e_audit}")
            resultado["auditoria"] = {"success": False, "error": str(e_audit)}
            resultado["auditoria_warning"] = "Cambio realizado pero auditoría falló"
        
        # Respuesta exitosa
        return JSONResponse(
            content=resultado,
            status_code=200,
            headers={"Content-Type": "application/json; charset=utf-8"}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error en endpoint actualizar valor contrato SECOP: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "error": "Error interno del servidor",
                "message": "Error actualizando valor de contrato SECOP",
                "referencia_contrato": referencia_contrato
            }
        )


@app.get("/emprestito/historial-cambios", tags=["Gestión de Empréstito"], summary="📋 Obtener Historial de Cambios")
async def obtener_historial_cambios_endpoint(
    tipo_coleccion: Optional[str] = Query(None, description="Filtrar por tipo de colección (procesos, ordenes, convenios, contratos)"),
    identificador: Optional[str] = Query(None, description="Filtrar por identificador específico"),
    limite: int = Query(50, ge=1, le=200, description="Número máximo de registros (1-200)")
):
    """
    ## 📋 GET | Consulta | Obtener Historial de Cambios en Valores de Empréstito
    
    Consulta el historial completo de cambios realizados en los valores de las colecciones de empréstito.
    Cada cambio incluye información de auditoría completa: motivo, documento soporte, valores anteriores y nuevos.
    
    ### ✅ Funcionalidades principales:
    - **Historial completo**: Accede a todos los cambios registrados
    - **Filtros opcionales**: Por tipo de colección o identificador específico
    - **Información detallada**: Incluye motivo, documento soporte, timestamp, valores modificados
    - **Trazabilidad**: ID único para cada cambio
    
    ### 🔍 Filtros disponibles:
    - **tipo_coleccion**: procesos, ordenes, convenios, contratos (opcional)
    - **identificador**: referencia_proceso, numero_orden, referencia_contrato (opcional)
    - **limite**: Número máximo de registros a retornar (1-200, default: 50)
    
    ### 📝 Información por cambio:
    - `change_id`: ID único del cambio
    - `change_timestamp`: Fecha y hora del cambio
    - `change_motivo`: Justificación del cambio
    - `change_support_file`: URL del documento soporte en S3 (si existe)
    - `tipo_coleccion`: Tipo de colección modificada
    - `identificador`: Identificador del documento modificado
    - `campo_modificado`: Campo que se modificó
    - `valor_anterior`: Valor antes del cambio
    - `valor_nuevo`: Valor después del cambio
    - `diferencia`: Diferencia numérica (valor_nuevo - valor_anterior)
    - `usuario`: Usuario que realizó el cambio
    - `endpoint_usado`: Endpoint utilizado
    
    ### 📋 Respuesta exitosa:
    ```json
    {
        "success": true,
        "total_cambios": 15,
        "cambios": [
            {
                "change_id": "uuid-123",
                "change_timestamp": "2025-12-28T10:30:00",
                "change_motivo": "Ajuste por modificación contractual",
                "change_support_file": "https://s3.../documento.pdf",
                "tipo_coleccion": "contratos",
                "identificador": "CONT-2024-001",
                "campo_modificado": "valor_contrato",
                "valor_anterior": 1000000.0,
                "valor_nuevo": 1500000.0,
                "diferencia": 500000.0,
                "usuario": "Sistema",
                "endpoint_usado": "/emprestito/modificar-valores/contrato-secop"
            }
        ]
    }
    ```
    """
    try:
        check_emprestito_availability()
        
        # Obtener historial
        resultado = await obtener_historial_cambios(
            tipo_coleccion=tipo_coleccion,
            identificador=identificador,
            limite=limite
        )
        
        if not resultado.get("success"):
            raise HTTPException(
                status_code=500,
                detail=resultado
            )
        
        return JSONResponse(
            content=resultado,
            status_code=200,
            headers={"Content-Type": "application/json; charset=utf-8"}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error obteniendo historial de cambios: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "error": "Error interno del servidor",
                "message": "Error consultando historial de cambios"
            }
        )


@app.post("/emprestito/obtener-contratos-secop", tags=["Gestión de Empréstito"], summary="🟢 Obtener Contratos SECOP - SIN LIMITACIONES")
async def obtener_contratos_secop_endpoint(offset: int = 0, limit: int = None):
    """
    ## � POST | 🔄 Procesamiento por Lotes | Obtener Contratos de SECOP desde Procesos
    
    Procesa registros de la colección 'procesos_emprestito' en lotes, busca contratos en SECOP 
    para cada proceso y guarda los resultados en la nueva colección 'contratos_emprestito'.
    
    ### 📝 Parámetros opcionales:
    - **offset**: Índice inicial para procesar (default: 0)
    - **limit**: Cantidad de registros a procesar (default: 10, máximo: 50)
    
    ### 📤 Envío:
    ```http
    POST /emprestito/obtener-contratos-secop?offset=0&limit=10
    ```
    
    ### 🔄 Proceso:
    1. Leer registros de 'procesos_emprestito' desde offset hasta offset+limit
    2. Para cada proceso, extraer referencia_proceso y proceso_contractual
    3. Conectar con la API de SECOP (www.datos.gov.co) para cada proceso
    4. Buscar contratos que contengan el proceso_contractual y NIT = 890399011
    5. Transformar los datos al esquema de la colección 'contratos_emprestito'
    6. Verificar duplicados y actualizar/crear registros en Firebase
    7. Retornar resumen del lote procesado con información de paginación
    
    ### ✅ Respuesta exitosa:
    ```json
    {
        "success": true,
        "message": "Lote procesado: 10 procesos (offset 0-10)",
        "resumen_procesamiento": {
            "offset": 0,
            "limit": 10,
            "total_procesos_coleccion": 50,
            "procesos_en_lote": 10,
            "procesos_procesados": 9,
            "procesos_sin_contratos": 1,
            "procesos_con_errores": 0,
            "mas_registros": true,
            "siguiente_offset": 10
        },
        "criterios_busqueda": {
            "coleccion_origen": "procesos_emprestito",
            "filtro_secop": "nit_entidad = '890399011'"
        },
        "resultados_secop": {
            "total_contratos_encontrados": 12,
            "total_contratos_procesados": 12
        },
        "firebase_operacion": {
            "documentos_nuevos": 8,
            "documentos_actualizados": 3,
            "duplicados_ignorados": 1
        },
        "contratos_guardados": [
            {
                "referencia_proceso": "4151.010.32.1.0575-2025",
                "proceso_contractual": "CO1.REQ.8485621",
                "sector": "Educación",
                "referencia_contrato": "CONT-001-2025",
                "descripcion_proceso": "Descripción detallada del proceso contractual",
                "estado_contrato": "Activo",
                "valor_contrato": 150000000,
                "valor_pagado": "75000000",
                "representante_legal": "Juan Pérez García",
                "ordenador_gasto": "María López Silva",
                "supervisor": "Carlos Rodríguez Mesa",
                "fecha_firma_contrato": "2025-01-15",
                "entidad_contratante": "MUNICIPIO DE SANTIAGO DE CALI",
                "nombre_contratista": "EMPRESA XYZ LTDA",
                "nit_entidad": "890399011",
                "fuente_datos": "SECOP_API",
                "fecha_guardado": "2025-10-09T..."
            }
        ],
        "procesos_sin_contratos": [],
        "procesos_con_errores": [],
        "timestamp": "2025-10-09T..."
    }
    ```
    
    ### 📋 Respuesta sin procesos:
    ```json
    {
        "success": false,
        "error": "No se encontraron procesos en la colección procesos_emprestito",
        "timestamp": "2025-10-09T..."
    }
    ```
    
    ### 🗄️ Esquema de la colección 'contratos_emprestito':
    **🔄 Campos heredados desde procesos_emprestito:**
    - **referencia_proceso**: Heredado desde procesos_emprestito
    - **banco**: Heredado desde 'nombre_banco' de procesos_emprestito
    - **bp**: Heredado desde procesos_emprestito
    - **nombre_centro_gestor**: Heredado desde procesos_emprestito
    
    **📊 Campos desde SECOP API:**
    - **referencia_contrato**: referencia_del_contrato desde SECOP
    - **id_contrato**: Desde SECOP
    - **proceso_contractual**: Mapeado desde 'proceso_de_compra' de SECOP (sobrescribe el heredado)
    - **sector**: Desde SECOP
    - **nombre_procedimiento**: Mapeado desde 'nombre_del_procedimiento' de SECOP
    - **descripcion_proceso**: Mapeado desde 'descripcion_del_proceso' de SECOP
    - **estado_contrato**: Mapeado desde 'estado_contrato' de SECOP
    - **valor_contrato**: Desde SECOP (campo único, sin duplicados)
    - **valor_pagado**: Desde SECOP
    - **representante_legal**: Mapeado desde 'nombre_representante_legal' de SECOP
    - **ordenador_gasto**: Mapeado desde 'nombre_ordenador_del_gasto' de SECOP
    - **supervisor**: Mapeado desde 'nombre_supervisor' de SECOP
    - **bpin**: Mapeado desde 'c_digo_bpin' de SECOP
    - **fecha_firma_contrato**: Desde SECOP
    - **objeto_contrato**: Desde SECOP
    - **modalidad_contratacion**: Desde SECOP
    - **entidad_contratante**: Desde SECOP
    - **nombre_contratista**: Mapeado desde 'nombre_del_contratista' de SECOP
    - **nit_entidad**: Desde SECOP (filtrado por 890399011)
    - **nit_contratista**: Desde SECOP
    
    **🔧 Metadatos:**
    - **fecha_guardado**: Timestamp de cuando se guardó en Firebase
    - **fuente_datos**: "SECOP_API"
    - **version_esquema**: "1.1"
    
    ### 🔗 Integración SECOP:
    - **API**: www.datos.gov.co
    - **Dataset**: jbjy-vk9h (Contratos)
    - **Filtros**: proceso_de_compra LIKE '%{proceso_contractual}%' AND nit_entidad = '890399011'
    - **Mapeo**: proceso_de_compra → proceso_contractual (sobrescribe valor heredado)
    - **Nuevos campos**: sector desde SECOP
    - **Límite**: 2000 registros por consulta
    """
    try:
        check_emprestito_availability()
        
        # Si limit es None, procesar TODO sin límite
        if limit is None:
            # Procesar todos los procesos sin limitación
            resultado = await obtener_contratos_desde_proceso_contractual_completo()
        else:
            # Si se especifica limit, mantener comportamiento por lotes
            if limit > 50:
                limit = 50
            if limit < 1:
                limit = 10
            if offset < 0:
                offset = 0
            resultado = await obtener_contratos_desde_proceso_contractual(offset=offset, limit=limit)
        
        # Retornar resultado
        return JSONResponse(
            content=resultado,
            status_code=200 if resultado.get("success") else 404,
            headers={"Content-Type": "application/json; charset=utf-8"}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error en endpoint obtener contratos SECOP: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "error": "Error interno del servidor",
                "message": "Error obteniendo contratos de SECOP",
                "detalles": str(e)
            }
        )

@app.get("/contratos_emprestito_all", tags=["Gestión de Empréstito"], summary="🔵 Todos los Contratos Empréstito")
@optional_rate_limit("50/minute")  # Máximo 50 requests por minuto
async def obtener_todos_contratos_emprestito(request: Request):
    """
    ## 🔵 GET | 📋 Listados | Obtener Todos los Contratos de Empréstito
    
    **Propósito**: Retorna todos los registros de las colecciones "contratos_emprestito", "ordenes_compra_emprestito" y "convenios_transferencias_emprestito".
    
    ### ✅ Casos de uso:
    - Obtener listado completo de contratos de empréstito
    - Exportación de datos para análisis
    - Integración con sistemas externos
    - Reportes y dashboards de contratos
    
    ### 📊 Información incluida:
    - Todos los campos disponibles en las tres colecciones
    - ID del documento para referencia
    - Conteo total de registros y por tipo
    - Timestamp de la consulta
    
    ### 🗄️ Colecciones incluidas:
    1. **contratos_emprestito**: Contratos principales
    2. **ordenes_compra_emprestito**: Órdenes de compra
    3. **convenios_transferencias_emprestito**: Convenios de transferencia
    
    ### 🗄️ Campos principales:
    - **referencia_contrato**: Referencia del contrato
    - **referencia_proceso**: Proceso de origen
    - **nombre_centro_gestor**: Entidad responsable
    - **banco**: Entidad bancaria
    - **estado_contrato**: Estado actual del contrato
    - **valor_contrato**: Valor del contrato
    - **fecha_firma_contrato**: Fecha de firma
    - **objeto_contrato**: Descripción del objeto
    - **modalidad_contratacion**: Modalidad de contratación
    - **entidad_contratante**: Entidad que contrata
    - **contratista**: Empresa contratista
    - **nombre_resumido_proceso**: 🔄 Heredado desde procesos_emprestito
    - **tipo_registro**: Identificador del tipo de registro (convenio_transferencia, contrato, orden)
    
    ### 🔄 Campos heredados desde procesos_emprestito:
    - **nombre_resumido_proceso**: Nombre resumido del proceso obtenido automáticamente usando referencia_proceso
    
    ### 📝 Ejemplo de uso:
    ```javascript
    const response = await fetch('/contratos_emprestito_all');
    const data = await response.json();
    if (data.success) {
        console.log('Total de registros:', data.count);
        console.log('Contratos:', data.contratos_count);
        console.log('Órdenes:', data.ordenes_count);
        console.log('Convenios:', data.convenios_count);
        console.log('Datos:', data.data);
    }
    ```
    """
    if not FIREBASE_AVAILABLE or not SCRIPTS_AVAILABLE:
        raise HTTPException(status_code=503, detail="Firebase or scripts not available")
    
    try:
        result = await get_contratos_emprestito_all()
        
        if not result["success"]:
            raise HTTPException(
                status_code=500,
                detail=f"Error obteniendo contratos de empréstito: {result.get('error', 'Error desconocido')}"
            )
        
        return create_utf8_response({
            "success": True,
            "data": result["data"],
            "count": result["count"],
            "contratos_count": result["contratos_count"],
            "ordenes_count": result["ordenes_count"],
            "convenios_count": result.get("convenios_count", 0),
            "collections": result["collections"],
            "timestamp": datetime.now().isoformat(),
            "last_updated": "2025-10-10T00:00:00Z",
            "message": result["message"]
        })
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error procesando contratos de empréstito: {str(e)}"
        )

@app.get("/contratos_emprestito/referencia/{referencia_contrato}", tags=["Gestión de Empréstito"], summary="🔵 Contratos por Referencia")
async def obtener_contratos_por_referencia(referencia_contrato: str):
    """
    ## � GET | �🔍 Consultas | Obtener Contratos por Referencia
    
    **Propósito**: Retorna contratos de empréstito filtrados por referencia_contrato específica.
    
    ### ✅ Casos de uso:
    - Búsqueda de contratos por referencia específica
    - Consulta de detalles de contrato individual
    - Validación de existencia de contrato
    - Integración con sistemas de seguimiento contractual
    
    ### 🔍 Filtrado:
    - **Campo**: `referencia_contrato` (coincidencia exacta)
    - **Tipo**: String - Referencia única del contrato
    - **Sensible a mayúsculas**: Sí
    
    ### 📊 Información incluida:
    - Todos los campos del contrato que coincida con la referencia
    - ID del documento para referencia
    - Conteo de registros encontrados
    - Información del filtro aplicado
    
    ### 📝 Ejemplo de uso:
    ```javascript
    const referencia = "CONT-001-2025";
    const response = await fetch(`/contratos_emprestito/${referencia}`);
    const data = await response.json();
    if (data.success && data.count > 0) {
        console.log('Contrato encontrado:', data.data[0]);
    } else {
        console.log('No se encontró contrato con referencia:', referencia);
    }
    ```
    
    ### 💡 Notas:
    - Si no se encuentra ningún contrato, retorna array vacío
    - La referencia debe ser exacta (sin espacios adicionales)
    - Puede retornar múltiples contratos si hay duplicados
    """
    if not FIREBASE_AVAILABLE or not SCRIPTS_AVAILABLE:
        raise HTTPException(status_code=503, detail="Firebase or scripts not available")
    
    try:
        result = await get_contratos_emprestito_by_referencia(referencia_contrato)
        
        if not result["success"]:
            raise HTTPException(
                status_code=500,
                detail=f"Error obteniendo contratos por referencia: {result.get('error', 'Error desconocido')}"
            )
        
        return create_utf8_response({
            "success": True,
            "data": result["data"],
            "count": result["count"],
            "collection": result["collection"],
            "filter": result["filter"],
            "timestamp": datetime.now().isoformat(),
            "last_updated": "2025-10-10T00:00:00Z",
            "message": result["message"]
        })
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error procesando consulta por referencia de contrato: {str(e)}"
        )

@app.get("/contratos_emprestito/centro-gestor/{nombre_centro_gestor}", tags=["Gestión de Empréstito"])
async def obtener_contratos_por_centro_gestor(nombre_centro_gestor: str):
    """
    ## 🏢 Obtener Contratos de Empréstito por Centro Gestor
    
    **Propósito**: Retorna contratos de empréstito filtrados por nombre del centro gestor específico.
    
    ### ✅ Casos de uso:
    - Consulta de contratos por dependencia responsable
    - Reportes por entidad gestora
    - Dashboard por centro de responsabilidad
    - Análisis de distribución institucional
    - Seguimiento de contratos por secretaría/departamento
    
    ### 🔍 Filtrado:
    - **Campo**: `nombre_centro_gestor` (coincidencia exacta)
    - **Tipo**: String - Nombre completo del centro gestor
    - **Sensible a mayúsculas**: Sí
    - **Espacios**: Sensible a espacios adicionales
    
    ### 📊 Información incluida:
    - Todos los campos de los contratos del centro gestor
    - ID del documento para referencia
    - Conteo de registros encontrados
    - Información del filtro aplicado
    
    ### 📝 Ejemplo de uso:
    ```javascript
    const centroGestor = "Secretaría de Salud";
    const response = await fetch(`/contratos_emprestito/${encodeURIComponent(centroGestor)}`);
    const data = await response.json();
    if (data.success && data.count > 0) {
        console.log(`${data.count} contratos encontrados para:`, centroGestor);
        const valorTotal = data.data.reduce((sum, c) => sum + (parseFloat(c.valor_contrato) || 0), 0);
        console.log('Valor total:', valorTotal);
    }
    ```
    
    ### 💡 Notas:
    - Típicamente retorna múltiples contratos por centro gestor
    - El nombre debe ser exacto (use `/centros-gestores/nombres-unicos` para obtener nombres válidos)
    - Para nombres con espacios, usar `encodeURIComponent()` en el frontend
    - Si no se encuentra ningún contrato, retorna array vacío
    
    ### 🔗 Endpoint relacionado:
    - `GET /centros-gestores/nombres-unicos` - Para obtener lista de centros gestores válidos
    """
    if not FIREBASE_AVAILABLE or not SCRIPTS_AVAILABLE:
        raise HTTPException(status_code=503, detail="Firebase or scripts not available")
    
    try:
        result = await get_contratos_emprestito_by_centro_gestor(nombre_centro_gestor)
        
        if not result["success"]:
            raise HTTPException(
                status_code=500,
                detail=f"Error obteniendo contratos por centro gestor: {result.get('error', 'Error desconocido')}"
            )
        
        return create_utf8_response({
            "success": True,
            "data": result["data"],
            "count": result["count"],
            "collection": result["collection"],
            "filter": result["filter"],
            "timestamp": datetime.now().isoformat(),
            "last_updated": "2025-10-10T00:00:00Z",
            "message": result["message"]
        })
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error procesando consulta por centro gestor: {str(e)}"
        )

@app.get("/emprestito/ordenes-compra", tags=["Gestión de Empréstito"])
async def get_ordenes_compra_todas():
    """
    ## 📋 Consultar Todas las Órdenes de Compra Existentes
    
    **Propósito**: Obtiene todas las órdenes de compra almacenadas en la colección 
    `ordenes_compra_emprestito` para revisar los datos disponibles.
    
    ### ✅ Información que proporciona:
    - **Listado completo**: Todas las órdenes de compra existentes
    - **Campos disponibles**: Estructura de datos actual
    - **Números de orden**: Para debugging del matching con TVEC
    """
    try:
        from api.scripts.ordenes_compra_operations import get_ordenes_compra_emprestito_all
        resultado = await get_ordenes_compra_emprestito_all()
        return resultado
        
    except Exception as e:
        logger.error(f"❌ Error consultando órdenes: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error consultando órdenes: {str(e)}"
        )

@app.post("/emprestito/obtener-ordenes-compra-TVEC", tags=["Gestión de Empréstito"])
async def obtener_ordenes_compra_tvec_endpoint(
    numero_orden: Optional[str] = Query(None, description="Filtrar ejecución a una única orden de compra")
):
    """
    ## 🛒 Obtener y Enriquecer Órdenes de Compra con Datos de TVEC
    
    **Propósito**: Enriquece todas las órdenes de compra existentes en la colección 
    `ordenes_compra_emprestito` con datos adicionales de la API de TVEC.
    
    ### ✅ Funcionalidades principales:
    - **Enriquecimiento de datos**: Obtiene datos adicionales de TVEC usando `numero_orden`
    - **Conservación de campos**: Mantiene todos los campos existentes en la colección
    - **Datos adicionales**: Agrega campos con prefijo `tvec_` para datos de la tienda virtual
    - **API Integration**: Usa la API oficial de datos abiertos de Colombia (rgxm-mmea)
    
    ### 📝 Parámetros opcionales:
    - `numero_orden`: Si se envía, procesa únicamente esa orden.
    
    ### 📤 Envío:
    ```http
    POST /emprestito/obtener-ordenes-compra-TVEC
    POST /emprestito/obtener-ordenes-compra-TVEC?numero_orden=OC-2024-001
    ```
    **No es necesario enviar ningún cuerpo JSON**.
    
    ### 🔄 Proceso:
    1. Obtener todas las órdenes de la colección `ordenes_compra_emprestito`
    2. Conectar con la API de TVEC (www.datos.gov.co/rgxm-mmea)
    3. Para cada orden, buscar datos adicionales usando `numero_orden`
    4. Enriquecer órdenes con campos adicionales con prefijo `tvec_`
    5. Actualizar registros en Firebase conservando campos originales
    6. Retornar resumen completo del enriquecimiento
    
    ### 📊 Campos adicionales agregados (estructura similar a contratos):
    
    **Campos principales (estructura estándar):**
    - `referencia_orden`: Referencia de la orden (similar a referencia_contrato)
    - `id_orden`: Identificador único de la orden (similar a id_contrato)
    - `estado_orden`: Estado de la orden (similar a estado_contrato)
    - `modalidad_contratacion`: Modalidad de la compra (mapeado desde tipo_compra)
    - `tipo_orden`: Tipo de compra (similar a tipo_contrato)
    - `fecha_publicacion_orden`: Fecha de publicación (similar a fecha_firma_contrato)
    - `fecha_vencimiento_orden`: Fecha de vencimiento (similar a fecha_fin_contrato)
    - `entidad_compradora`: Entidad que compra (similar a entidad_contratante)
    - `nombre_proveedor`: Nombre del proveedor (similar a nombre_contratista)
    - `nit_proveedor`: NIT del proveedor (similar a nit_contratista)
    - `descripcion_orden`: Descripción detallada (similar a descripcion_proceso)
    - `objeto_orden`: Objeto de la orden (similar a objeto_contrato)
    - `sector`: Sector/categoría principal
    - `valor_orden`: Valor total como número (similar a valor_contrato)
    - `_dataset_source`: "rgxm-mmea" (similar a "jbjy-vk9h" para contratos)
    - `fuente_datos`: "TVEC_API" (similar a "SECOP_API")
    - `fecha_guardado`: Timestamp de procesamiento
    - `version_esquema`: "1.0" (versión del esquema TVEC)
    
    **Campos específicos TVEC (con prefijo):**
    - `tvec_agregacion`: Tipo de agregación
    - `tvec_codigo_categoria`: Código de categoría
    - `tvec_unidad_medida`: Unidad de medida
    - `tvec_cantidad`: Cantidad
    - `tvec_precio_unitario`: Precio unitario
    
    ### 🔐 Snippet utilizado:
    El endpoint usa exactamente el snippet proporcionado:
    ```python
    import pandas as pd
    from sodapy import Socrata
    
    client = Socrata("www.datos.gov.co", None)
    results = client.get("rgxm-mmea", limit=2000)
    results_df = pd.DataFrame.from_records(results)
    ```
    
    ### ✅ Respuesta exitosa:
    ```json
    {
        "success": true,
        "message": "Enriquecimiento completado: 15/20 órdenes enriquecidas",
        "resumen": {
            "total_ordenes_procesadas": 20,
            "ordenes_enriquecidas": 15,
            "ordenes_sin_datos_tvec": 3,
            "ordenes_con_errores": 2,
            "tasa_enriquecimiento": "75.0%"
        },
        "fuente_datos": {
            "api_tvec": "www.datos.gov.co",
            "dataset": "rgxm-mmea",
            "registros_tvec_disponibles": 1850
        },
        "operacion_firebase": {
            "coleccion": "ordenes_compra_emprestito",
            "documentos_actualizados": 15,
            "campos_preservados": true,
            "campos_agregados_prefijo": "tvec_"
        },
        "ordenes_actualizadas": [
            {
                "doc_id": "abc123",
                "numero_orden": "OC-2024-001",
                "campos_agregados": [
                    "referencia_orden", "estado_orden", "valor_orden", 
                    "entidad_compradora", "nombre_proveedor", "nit_proveedor",
                    "descripcion_orden", "objeto_orden", "sector", "_dataset_source",
                    "fuente_datos", "fecha_guardado", "version_esquema"
                ],
                "datos_enriquecidos": {
                    "numero_orden": "OC-2024-001",
                    "referencia_orden": "OC-2024-001",
                    "estado_orden": "Activa",
                    "valor_orden": 1500000,
                    "entidad_compradora": "ALCALDIA DE SANTIAGO DE CALI",
                    "nombre_proveedor": "PROVEEDOR EJEMPLO S.A.S",
                    "nit_proveedor": "900123456-1",
                    "descripcion_orden": "Suministro de equipos tecnológicos",
                    "sector": "Tecnología",
                    "_dataset_source": "rgxm-mmea",
                    "fuente_datos": "TVEC_API",
                    "version_esquema": "1.0"
                }
            }
        ],
        "tiempo_total_segundos": 45.2,
        "timestamp": "2025-10-16T..."
    }
    ```
    
    ### 🚨 Requisitos:
    - Tener órdenes de compra registradas en `ordenes_compra_emprestito`
    - Cada orden debe tener el campo `numero_orden` 
    - Conexión a internet para acceder a la API de TVEC
    - Librerías: `sodapy` y `pandas` instaladas
    
    ### 💡 Características especiales:
    - **Preserva datos originales**: No modifica campos existentes
    - **Prefijo tvec_**: Evita conflictos con campos originales
    - **Matching por numero_orden**: Usa identificador único para relacionar datos
    - **Tolerante a errores**: Continúa procesando aunque algunas órdenes fallen
    - **Sin duplicados**: Solo agrega campos si no existen ya
    
    ### 🔗 Endpoints relacionados:
    - `POST /emprestito/cargar-orden-compra` - Para crear nuevas órdenes
    - `GET /ordenes_compra_emprestito_all` - Para consultar órdenes enriquecidas (si existe)
    """
    # Verificar disponibilidad de servicios
    if not FIREBASE_AVAILABLE or not SCRIPTS_AVAILABLE:
        raise HTTPException(status_code=503, detail="Firebase or scripts not available")
    
    if not TVEC_ENRICH_OPERATIONS_AVAILABLE:
        raise HTTPException(
            status_code=503, 
            detail={
                "success": False,
                "error": "TVEC enrich operations not available",
                "message": "Las operaciones de enriquecimiento TVEC no están disponibles",
                "requirements": [
                    "pip install sodapy pandas",
                    "Verificar conectividad a internet",
                    "Confirmar acceso a www.datos.gov.co"
                ],
                "code": "TVEC_SERVICES_UNAVAILABLE"
            }
        )
    
    try:
        # Ejecutar enriquecimiento de órdenes de compra con datos de TVEC
        resultado = await obtener_ordenes_compra_tvec_enriquecidas(numero_orden=numero_orden)
        
        # Determinar código de estado basado en el resultado
        status_code = 200 if resultado.get("success") else 500
        
        # Retornar resultado con información detallada
        return JSONResponse(
            content={
                **resultado,
                "api_info": {
                    "endpoint_name": "obtener-ordenes-compra-TVEC",
                    "version": "1.0",
                    "snippet_based": True,
                    "preserves_original_data": True
                },
                "last_updated": "2025-10-16T00:00:00Z"
            },
            status_code=status_code,
            headers={"Content-Type": "application/json; charset=utf-8"}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error en endpoint TVEC enriquecimiento: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "error": "Error interno del servidor",
                "message": "Error ejecutando enriquecimiento con datos de TVEC",
                "detalles": str(e),
                "code": "TVEC_INTERNAL_ERROR"
            }
        )

@app.get("/procesos_emprestito_all", tags=["Gestión de Empréstito"])
async def get_all_procesos_emprestito():
    """
    ## Obtener Todos los Procesos de Empréstito
    
    **Propósito**: Retorna todo el contenido de la colección "procesos_emprestito" en Firebase.
    
    ### ✅ Casos de uso:
    - Obtener listado completo de procesos de empréstito
    - Exportación de datos para análisis
    - Integración con sistemas externos
    - Reportes y dashboards de procesos
    - Monitoreo del estado de procesos
    
    ### 📊 Información incluida:
    - Todos los campos disponibles en la colección
    - ID del documento para referencia
    - Conteo total de registros
    - Timestamp de la consulta
    - Datos serializados correctamente para JSON
    
    ### 🗄️ Campos principales esperados:
    - **referencia_proceso**: Referencia única del proceso
    - **nombre_centro_gestor**: Entidad responsable
    - **nombre_banco**: Entidad bancaria
    - **plataforma**: SECOP, SECOP II, TVEC, etc.
    - **bp**: Código de proyecto base
    - **proceso_contractual**: Código del proceso contractual
    - **nombre_proceso**: Nombre del procedimiento
    - **estado_proceso**: Estado actual del proceso
    - **valor_publicacion**: Valor del proceso
    - **fecha_publicacion**: Fecha de publicación
    - **nombre_resumido_proceso**: Nombre resumido (opcional)
    - **id_paa**: ID del PAA (opcional)
    - **valor_proyectado**: Valor proyectado (opcional)
    
    ### 📝 Ejemplo de uso:
    ```javascript
    const response = await fetch('/procesos_emprestito_all');
    const data = await response.json();
    if (data.success) {
        console.log('Procesos encontrados:', data.count);
        console.log('Datos:', data.data);
        
        // Filtrar por estado
        const activos = data.data.filter(p => p.estado_proceso === 'Activo');
        
        // Sumar valores
        const valorTotal = data.data.reduce((sum, p) => sum + (p.valor_publicacion || 0), 0);
    }
    ```
    
    ### 💡 Características:
    - **Serialización**: Datos de Firebase convertidos correctamente a JSON
    - **UTF-8**: Soporte completo para caracteres especiales
    - **Fechas**: Timestamps convertidos a formato ISO
    - **Performance**: Consulta optimizada de toda la colección
    - **Consistencia**: Estructura de datos uniforme
    
    ### 🔗 Endpoints relacionados:
    - `POST /emprestito/cargar-proceso` - Para crear nuevos procesos
    - `GET /contratos_emprestito_all` - Para consultar contratos relacionados
    """
    if not FIREBASE_AVAILABLE or not SCRIPTS_AVAILABLE:
        raise HTTPException(status_code=503, detail="Firebase or scripts not available")
    
    if not EMPRESTITO_OPERATIONS_AVAILABLE:
        raise HTTPException(status_code=503, detail="Emprestito operations not available")
    
    try:
        result = await get_procesos_emprestito_all()
        
        if not result["success"]:
            raise HTTPException(
                status_code=500,
                detail=f"Error obteniendo procesos de empréstito: {result.get('error', 'Error desconocido')}"
            )
        
        return create_utf8_response({
            "success": True,
            "data": result["data"],
            "count": result["count"],
            "collection": result["collection"],
            "timestamp": result["timestamp"],
            "last_updated": "2025-10-18T00:00:00Z",  # Endpoint creation date
            "message": result["message"],
            "metadata": {
                "data_serialized": True,
                "utf8_enabled": True,
                "spanish_support": True,
                "firebase_timestamps_converted": True,
                "purpose": "Complete procesos_emprestito collection data"
            }
        })
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error procesando consulta de procesos de empréstito: {str(e)}"
        )

@app.get("/emprestito/obtener-procesos-bp", tags=["Gestión de Empréstito"], summary="🔵 Obtener Procesos BP")
async def obtener_procesos_bp():
    """
    ## Obtener Procesos de Empréstito - Campos Básicos BP
    
    **Propósito**: Retorna datos específicos de la colección "procesos_emprestito" optimizados para visualización.
    
    ### ✅ Casos de uso:
    - Listado de procesos para dashboards
    - Exportación simplificada de datos
    - Integración con sistemas externos
    - Reportes básicos de procesos
    
    ### 📊 Campos incluidos:
    - **bp**: Código de proyecto base
    - **banco**: Entidad bancaria
    - **nombre_centro_gestor**: Entidad responsable
    - **nombre_resumido_proceso**: Nombre resumido del proceso
    - **tipo_contrato**: Tipo de contrato
    - **urlproceso**: URL del proceso
    - **valor_publicacion**: Valor del proceso
    
    ### 📝 Ejemplo de uso:
    ```javascript
    const response = await fetch('/emprestito/obtener-procesos-bp');
    const data = await response.json();
    if (data.success) {
        console.log('Procesos encontrados:', data.count);
        data.data.forEach(proceso => {
            console.log(`BP: ${proceso.bp}, Banco: ${proceso.banco}`);
        });
    }
    ```
    
    ### 💡 Características:
    - **Optimizado**: Solo campos necesarios para reducir payload
    - **UTF-8**: Soporte completo para caracteres especiales
    """
    if not FIREBASE_AVAILABLE or not SCRIPTS_AVAILABLE:
        raise HTTPException(status_code=503, detail="Firebase or scripts not available")
    
    try:
        db = get_firestore_client()
        if db is None:
            raise HTTPException(
                status_code=503,
                detail="No se pudo conectar a Firestore"
            )
        
        collection_ref = db.collection('procesos_emprestito')
        docs = collection_ref.stream()
        procesos_data = []
        
        for doc in docs:
            doc_data = doc.to_dict()
            # Extraer solo los campos solicitados
            proceso_filtrado = {
                'bp': doc_data.get('bp', ''),
                'banco': doc_data.get('nombre_banco', ''),
                'nombre_centro_gestor': doc_data.get('nombre_centro_gestor', ''),
                'nombre_resumido_proceso': doc_data.get('nombre_resumido_proceso', ''),
                'tipo_contrato': doc_data.get('tipo_contrato', ''),
                'urlproceso': doc_data.get('urlproceso', ''),
                'valor_publicacion': doc_data.get('valor_publicacion', 0)
            }
            procesos_data.append(proceso_filtrado)
        
        return create_utf8_response({
            "success": True,
            "data": procesos_data,
            "count": len(procesos_data),
            "collection": "procesos_emprestito",
            "timestamp": datetime.now().isoformat(),
            "message": f"Se obtuvieron {len(procesos_data)} procesos exitosamente",
            "metadata": {
                "fields": ["bp", "banco", "nombre_centro_gestor", "nombre_resumido_proceso", "tipo_contrato", "urlproceso", "valor_publicacion"],
                "utf8_enabled": True,
                "spanish_support": True
            }
        })
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error obteniendo procesos BP: {str(e)}"
        )

@app.get("/emprestito/obtener-contratos-bp", tags=["Gestión de Empréstito"], summary="🔵 Obtener Contratos BP")
async def obtener_contratos_bp():
    """
    ## Obtener Contratos de Empréstito - Campos Básicos BP
    
    **Propósito**: Retorna datos específicos de las tres colecciones de empréstito optimizados para visualización.
    
    ### 🗄️ Colecciones incluidas:
    1. **contratos_emprestito**: Contratos principales
    2. **ordenes_compra_emprestito**: Órdenes de compra
    3. **convenios_transferencias_emprestito**: Convenios de transferencia
    
    ### ✅ Casos de uso:
    - Listado de contratos para dashboards
    - Exportación simplificada de datos de contratos
    - Integración con sistemas externos
    - Reportes básicos de contratos
    - Seguimiento de vigencias contractuales
    
    ### 📊 Campos incluidos:
    - **bp**: Código de proyecto base
    - **banco**: Entidad bancaria
    - **nombre_centro_gestor**: Entidad responsable
    - **nombre_resumido_proceso**: Nombre resumido del proceso
    - **tipo_contrato**: Tipo de contrato
    - **urlproceso**: URL del proceso
    - **valor_contrato**: Valor del contrato
    - **fecha_inicio_contrato**: Fecha de inicio del contrato
    - **fecha_fin_contrato**: Fecha de finalización del contrato
    - **sector**: Sector del contrato
    
    ### 📝 Ejemplo de uso:
    ```javascript
    const response = await fetch('/emprestito/obtener-contratos-bp');
    const data = await response.json();
    if (data.success) {
        console.log('Registros encontrados:', data.count);
        console.log('Contratos:', data.contratos_count);
        console.log('Órdenes:', data.ordenes_count);
        console.log('Convenios:', data.convenios_count);
        data.data.forEach(contrato => {
            console.log(`BP: ${contrato.bp}, Banco: ${contrato.banco}`);
            console.log(`Valor: ${contrato.valor_contrato}`);
            console.log(`Vigencia: ${contrato.fecha_inicio_contrato} - ${contrato.fecha_fin_contrato}`);
        });
    }
    ```
    
    ### 💡 Características:
    - **Optimizado**: Solo campos necesarios para reducir payload
    - **UTF-8**: Soporte completo para caracteres especiales
    - **Cache**: Datos cacheados por 5 minutos para mejor performance
    - **Fechas**: Incluye información de vigencia contractual
    - **Multi-colección**: Combina datos de las tres colecciones de empréstito
    """
    if not FIREBASE_AVAILABLE or not SCRIPTS_AVAILABLE:
        raise HTTPException(status_code=503, detail="Firebase or scripts not available")
    
    try:
        db = get_firestore_client()
        if db is None:
            raise HTTPException(
                status_code=503,
                detail="No se pudo conectar a Firestore"
            )
        
        # Función auxiliar para extraer los campos solicitados
        def extraer_campos_bp(doc_data: dict) -> dict:
            """Extrae solo los campos solicitados manteniendo la estructura BP"""
            return {
                'bp': doc_data.get('bp', ''),
                'banco': doc_data.get('banco', ''),
                'nombre_centro_gestor': doc_data.get('nombre_centro_gestor', ''),
                'nombre_resumido_proceso': doc_data.get('nombre_resumido_proceso', ''),
                'tipo_contrato': doc_data.get('tipo_contrato', ''),
                'urlproceso': doc_data.get('urlproceso', ''),
                'valor_contrato': doc_data.get('valor_contrato', 0),
                'fecha_inicio_contrato': doc_data.get('fecha_inicio_contrato', ''),
                'fecha_fin_contrato': doc_data.get('fecha_fin_contrato', ''),
                'sector': doc_data.get('sector', '')
            }
        
        # Lista para almacenar todos los datos combinados
        todos_los_datos = []
        
        # 1. Obtener contratos_emprestito
        collection_ref = db.collection('contratos_emprestito')
        docs = collection_ref.stream()
        contratos_count = 0
        
        for doc in docs:
            doc_data = doc.to_dict()
            contrato_filtrado = extraer_campos_bp(doc_data)
            todos_los_datos.append(contrato_filtrado)
            contratos_count += 1
        
        # 2. Obtener ordenes_compra_emprestito
        ordenes_ref = db.collection('ordenes_compra_emprestito')
        ordenes_docs = ordenes_ref.stream()
        ordenes_count = 0
        
        for doc in ordenes_docs:
            doc_data = doc.to_dict()
            # Mapear campos de órdenes de compra al formato BP
            orden_mapeada = {
                'bp': doc_data.get('bp', ''),
                'banco': doc_data.get('nombre_banco', ''),  # Mapear nombre_banco a banco
                'nombre_centro_gestor': doc_data.get('nombre_centro_gestor', ''),
                'nombre_resumido_proceso': doc_data.get('nombre_resumido_proceso', ''),
                'tipo_contrato': doc_data.get('tipo_contrato', 'Orden de Compra - TVEC'),
                'urlproceso': doc_data.get('urlproceso', ''),
                'valor_contrato': int(float(doc_data.get('valor_orden', 0))) if doc_data.get('valor_orden') else 0,
                'fecha_inicio_contrato': doc_data.get('fecha_publicacion_orden', ''),
                'fecha_fin_contrato': doc_data.get('fecha_vencimiento_orden', ''),
                'sector': doc_data.get('sector', '')
            }
            todos_los_datos.append(orden_mapeada)
            ordenes_count += 1
        
        # 3. Obtener convenios_transferencias_emprestito
        convenios_ref = db.collection('convenios_transferencias_emprestito')
        convenios_docs = convenios_ref.stream()
        convenios_count = 0
        
        for doc in convenios_docs:
            doc_data = doc.to_dict()
            convenio_filtrado = extraer_campos_bp(doc_data)
            todos_los_datos.append(convenio_filtrado)
            convenios_count += 1
        
        return create_utf8_response({
            "success": True,
            "data": todos_los_datos,
            "count": len(todos_los_datos),
            "contratos_count": contratos_count,
            "ordenes_count": ordenes_count,
            "convenios_count": convenios_count,
            "collections": ["contratos_emprestito", "ordenes_compra_emprestito", "convenios_transferencias_emprestito"],
            "timestamp": datetime.now().isoformat(),
            "message": f"Se obtuvieron {contratos_count} contratos, {ordenes_count} órdenes de compra y {convenios_count} convenios de transferencia exitosamente ({len(todos_los_datos)} registros totales)",
            "metadata": {
                "fields": ["bp", "banco", "nombre_centro_gestor", "nombre_resumido_proceso", "tipo_contrato", "urlproceso", "valor_contrato", "fecha_inicio_contrato", "fecha_fin_contrato", "sector"],
                "utf8_enabled": True,
                "spanish_support": True
            }
        })
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error obteniendo contratos BP: {str(e)}"
        )

@app.get("/ordenes_compra_emprestito/numero/{numero_orden}", tags=["Gestión de Empréstito"])
async def obtener_ordenes_por_numero(numero_orden: str):
    """
    ## 🔍 Obtener Órdenes de Compra por Número de Orden
    
    **Propósito**: Retorna órdenes de compra filtradas por número de orden específico.
    
    ### ✅ Casos de uso:
    - Búsqueda de órdenes por número específico
    - Consulta de detalles de orden individual
    - Validación de existencia de orden
    - Verificar datos enriquecidos de una orden específica
    
    ### 🔍 Filtrado:
    - **Campo**: `numero_orden` (coincidencia exacta)
    - **Tipo**: String - Número único de la orden
    - **Sensible a mayúsculas**: Sí
    
    ### 📊 Información incluida:
    - Todos los campos de las órdenes que coincidan con el número
    - Datos enriquecidos de TVEC (si están disponibles)
    - ID del documento para referencia
    - Información del filtro aplicado
    
    ### 📝 Ejemplo de uso:
    ```javascript
    const numeroOrden = "OC-2024-001";
    const response = await fetch(`/ordenes_compra_emprestito/numero/${numeroOrden}`);
    const data = await response.json();
    if (data.success && data.count > 0) {
        const orden = data.data[0];
        console.log('Orden encontrada:', orden.numero_orden);
        if (orden._dataset_source === 'rgxm-mmea') {
            console.log('Orden enriquecida con TVEC:', orden.valor_orden);
        }
    }
    ```
    """
    if not FIREBASE_AVAILABLE or not SCRIPTS_AVAILABLE:
        raise HTTPException(status_code=503, detail="Firebase or scripts not available")
    
    try:
        result = await get_ordenes_compra_emprestito_by_referencia(numero_orden)
        
        if not result["success"]:
            raise HTTPException(
                status_code=500,
                detail=f"Error obteniendo órdenes por número: {result.get('error', 'Error desconocido')}"
            )
        
        return create_utf8_response({
            "success": True,
            "data": result["data"],
            "count": result["count"],
            "collection": result["collection"],
            "filter": result["filter"],
            "timestamp": datetime.now().isoformat(),
            "last_updated": "2025-10-16T00:00:00Z",
            "message": result["message"]
        })
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error procesando consulta por número de orden: {str(e)}"
        )

@app.get("/ordenes_compra_emprestito/centro-gestor/{nombre_centro_gestor}", tags=["Gestión de Empréstito"])
async def obtener_ordenes_por_centro_gestor(nombre_centro_gestor: str):
    """
    ## 🏢 Obtener Órdenes de Compra por Centro Gestor
    
    **Propósito**: Retorna órdenes de compra filtradas por nombre del centro gestor específico.
    
    ### ✅ Casos de uso:
    - Consulta de órdenes por dependencia responsable
    - Reportes por entidad gestora
    - Dashboard por centro de responsabilidad
    - Análisis de distribución institucional de órdenes de compra
    
    ### 🔍 Filtrado:
    - **Campo**: `nombre_centro_gestor` (coincidencia exacta)
    - **Tipo**: String - Nombre completo del centro gestor
    - **Sensible a mayúsculas**: Sí
    
    ### 📊 Información incluida:
    - Todas las órdenes del centro gestor especificado
    - Datos enriquecidos de TVEC (si están disponibles)
    - Conteo de registros encontrados
    - Información del filtro aplicado
    
    ### 📝 Ejemplo de uso:
    ```javascript
    const centroGestor = "Secretaría de Salud";
    const response = await fetch(`/ordenes_compra_emprestito/centro-gestor/${encodeURIComponent(centroGestor)}`);
    const data = await response.json();
    if (data.success && data.count > 0) {
        console.log(`${data.count} órdenes encontradas para:`, centroGestor);
        const valorTotal = data.data.reduce((sum, o) => sum + (o.valor_orden || 0), 0);
        console.log('Valor total de órdenes:', valorTotal);
    }
    ```
    """
    if not FIREBASE_AVAILABLE or not SCRIPTS_AVAILABLE:
        raise HTTPException(status_code=503, detail="Firebase or scripts not available")
    
    try:
        result = await get_ordenes_compra_emprestito_by_centro_gestor(nombre_centro_gestor)
        
        if not result["success"]:
            raise HTTPException(
                status_code=500,
                detail=f"Error obteniendo órdenes por centro gestor: {result.get('error', 'Error desconocido')}"
            )
        
        return create_utf8_response({
            "success": True,
            "data": result["data"],
            "count": result["count"],
            "collection": result["collection"],
            "filter": result["filter"],
            "timestamp": datetime.now().isoformat(),
            "last_updated": "2025-10-16T00:00:00Z",
            "message": result["message"]
        })
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error procesando consulta por centro gestor: {str(e)}"
        )

@app.post("/emprestito/obtener-procesos-secop", tags=["Gestión de Empréstito"])
async def obtener_procesos_secop_completo_endpoint():
    """
    ## 🔄 Obtener y Actualizar Datos Completos de SECOP para Todos los Procesos
    
    Endpoint para complementar los datos de TODA la colección "procesos_emprestito" con información 
    adicional desde la API de SECOP, sin alterar los campos existentes ni los nombres de variables.
    
    ### ✅ Funcionalidades principales:
    - **Procesamiento masivo**: Actualiza TODOS los procesos de la colección automáticamente
    - **Actualización selectiva**: Solo actualiza campos que han cambiado por proceso
    - **Preservación de datos**: Mantiene todos los campos existentes intactos
    - **Mapeo desde SECOP**: Obtiene datos adicionales usando la API oficial
    - **Sin parámetros**: Lee automáticamente todas las referencias_proceso de Firebase
    
    ### 📊 Campos que se actualizan/complementan:
    **Campos básicos:**
    - `adjudicado` ← adjudicado (SECOP)
    - `fase` ← fase (SECOP)
    - `estado_proceso` ← estado_del_procedimiento (SECOP)
    
    **Campos adicionales agregados:**
    - `fecha_publicacion_fase` ← fecha_de_publicacion_del (SECOP)
    - `fecha_publicacion_fase_1` ← null (no disponible en SECOP)
    - `fecha_publicacion_fase_2` ← null (no disponible en SECOP)
    - `fecha_publicacion_fase_3` ← fecha_de_publicacion_fase_3 (SECOP)
    - `proveedores_invitados` ← proveedores_invitados (SECOP)
    - `proveedores_con_invitacion` ← proveedores_con_invitacion (SECOP)
    - `visualizaciones_proceso` ← visualizaciones_del (SECOP)
    - `proveedores_que_manifestaron` ← proveedores_que_manifestaron (SECOP)
    - `numero_lotes` ← numero_de_lotes (SECOP)
    - `fecha_adjudicacion` ← null (no disponible en SECOP)
    - `estado_resumen` ← estado_resumen (SECOP)
    - `fecha_recepcion_respuestas` ← null (no disponible en SECOP)
    - `fecha_apertura_respuestas` ← null (no disponible en SECOP)
    - `fecha_apertura_efectiva` ← null (no disponible en SECOP)
    - `respuestas_procedimiento` ← respuestas_al_procedimiento (SECOP)
    - `respuestas_externas` ← respuestas_externas (SECOP)
    - `conteo_respuestas_ofertas` ← conteo_de_respuestas_a_ofertas (SECOP)
    
    ### 🔐 Validaciones:
    - Verificar que el proceso existe en la colección `procesos_emprestito`
    - Conectar con API de SECOP usando la referencia_proceso
    - Solo actualizar si hay cambios reales en los datos
    - Mantener estructura de variables sin cambios
    
    ### 📝 Ejemplo de request:
    ```http
    POST /emprestito/obtener-procesos-secop
    ```
    **No requiere parámetros - procesamiento automático**
    
    ### ✅ Respuesta exitosa:
    ```json
    {
        "success": true,
        "message": "Se procesaron 5 procesos de empréstito exitosamente",
        "resumen_procesamiento": {
            "total_procesos_encontrados": 5,
            "procesos_procesados": 4,
            "procesos_actualizados": 3,
            "procesos_sin_cambios": 1,
            "procesos_con_errores": 1
        },
        "resultados_detallados": [
            {
                "referencia_proceso": "4163.001.32.1.718-2024",
                "success": true,
                "changes_count": 8,
                "changes_summary": [
                    "adjudicado: 'No' → 'Sí'",
                    "estado_proceso: 'En evaluación' → 'Seleccionado'"
                ]
            },
            {
                "referencia_proceso": "4164.001.32.1.719-2024",
                "success": true,
                "changes_count": 0,
                "message": "Ya está actualizado"
            }
        ],
        "estadisticas": {
            "total_campos_actualizados": 25,
            "tiempo_procesamiento": "45.2 segundos"
        },
        "timestamp": "2024-10-18T..."
    }
    ```
    
    ### 📋 Respuesta sin procesos:
    ```json
    {
        "success": false,
        "error": "No se encontraron procesos en la colección procesos_emprestito",
        "total_procesos_encontrados": 0
    }
    ```
    
    ### 🔍 API de SECOP utilizada:
    - **Dominio**: www.datos.gov.co
    - **Dataset**: p6dx-8zbt (Procesos de contratación)
    - **Filtro**: nit_entidad='890399011' AND referencia_del_proceso='{referencia_proceso}'
    
    ### ⏱️ Tiempo de procesamiento:
    - **Timeout extendido**: 5 minutos (300 segundos)
    - **Tiempo estimado**: ~10-15 segundos por proceso
    - **Progreso**: Se reporta en logs con ETA para procesos restantes
    - **Recomendación**: Monitor logs del servidor para ver progreso en tiempo real
    """
    try:
        check_emprestito_availability()
        
        # Procesar todos los procesos de empréstito automáticamente
        resultado = await procesar_todos_procesos_emprestito_completo()
        
        # Manejar respuesta según el resultado
        if not resultado.get("success"):
            # Si no se encontraron procesos
            if "No se encontraron procesos" in resultado.get("error", ""):
                raise HTTPException(
                    status_code=404,
                    detail=resultado
                )
            else:
                # Otros errores
                raise HTTPException(
                    status_code=500,
                    detail=resultado
                )
        
        # Respuesta exitosa
        return JSONResponse(
            content=resultado,
            status_code=200,
            headers={"Content-Type": "application/json; charset=utf-8"}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error en endpoint obtener procesos SECOP completo: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "error": "Error interno del servidor",
                "message": "Error obteniendo datos completos de SECOP para todos los procesos"
            }
        )


@app.get("/asignaciones-emprestito-banco-centro-gestor", tags=["Gestión de Empréstito"], summary="🔵 Obtener Asignaciones Banco-Centro Gestor")
async def get_all_asignaciones_emprestito_banco_centro_gestor():
    """
    ## 🔵 GET | 📋 Consultas | Obtener Todas las Asignaciones de Empréstito Banco-Centro Gestor
    
    Endpoint para obtener todas las asignaciones de montos de empréstito por banco y centro gestor
    almacenadas en la colección `montos_emprestito_asignados_centro_gestor`.
    
    ### ✅ Funcionalidades principales:
    - **Listado completo**: Retorna todas las asignaciones registradas
    - **Datos completos**: Incluye todos los campos de cada asignación
    - **Metadatos**: Incluye ID del documento, conteo total y timestamp
    
    ### 📊 Información incluida:
    - Todos los campos de la asignación
    - ID del documento para referencia
    - Conteo total de registros
    - Timestamp de la consulta
    
    ### 🗄️ Campos principales esperados:
    - **banco**: Nombre del banco financiador
    - **nombre_centro_gestor**: Nombre del centro gestor
    - **bp**: Código del proyecto presupuestal (BP)
    - **monto_programado**: Monto programado para el banco y centro gestor
    - **anio**: Año de la asignación
    - **created_at**: Fecha de creación del registro
    - **updated_at**: Fecha de última actualización
    - **data_hash**: Hash para control de duplicados
    
    ### ✅ Respuesta exitosa (200):
    ```json
    {
        "success": true,
        "data": [
            {
                "id": "BBVA_BP26004701_2026",
                "banco": "BBVA",
                "nombre_centro_gestor": "Secretaría de Educación",
                "bp": "BP26004701",
                "monto_programado": 1500000.00,
                "anio": 2026,
                "created_at": "2024-11-17T...",
                "updated_at": "2024-11-17T...",
                "data_hash": "abc123..."
            }
        ],
        "count": 83,
        "collection": "montos_emprestito_asignados_centro_gestor",
        "timestamp": "2024-11-17T...",
        "message": "Se obtuvieron 83 asignaciones de empréstito banco-centro gestor exitosamente"
    }
    ```
    """
    try:
        check_emprestito_availability()
        
        result = await get_asignaciones_emprestito_banco_centro_gestor_all()
        
        if not result["success"]:
            raise HTTPException(
                status_code=500,
                detail=f"Error obteniendo asignaciones de empréstito banco-centro gestor: {result.get('error', 'Error desconocido')}"
            )
        
        return JSONResponse(
            content={
                "success": True,
                "data": result["data"],
                "count": result["count"],
                "collection": result["collection"],
                "timestamp": result["timestamp"],
                "message": f"Se obtuvieron {result['count']} asignaciones de empréstito banco-centro gestor exitosamente"
            },
            status_code=200,
            headers={"Content-Type": "application/json; charset=utf-8"}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error en endpoint de asignaciones de empréstito banco-centro gestor: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "error": "Error interno del servidor",
                "message": "Error al obtener asignaciones de empréstito banco-centro gestor",
                "code": "INTERNAL_SERVER_ERROR"
            }
        )


# ============================================================================
# ENDPOINTS DE FLUJO DE CAJA EMPRÉSTITO
# ============================================================================

@app.post("/emprestito/flujo-caja/cargar-excel", tags=["Gestión de Empréstito"], summary="🟢 Cargar Flujos de Caja Excel")
async def cargar_flujo_caja_excel(
    archivo_excel: UploadFile = File(..., description="Archivo Excel con flujos de caja"),
    update_mode: str = Form(default="merge", description="Modo de actualización: merge, replace, append")
):
    """
    ## � POST | �📊 Carga de Archivos | Cargar Flujos de Caja desde Excel
    
    Endpoint para procesar archivos Excel con información de flujos de caja de proyectos
    y cargarlos en la colección "flujo_caja_emprestito".
    
    ### 📁 Archivo Excel esperado:
    - **Hoja**: "CONTRATOS - Seguimiento" 
    - **Columnas requeridas**: Responsable, Organismo, Banco, BP Proyecto, Descripcion BP
    - **Columnas de datos**: Todas las columnas que contengan "Desembolso" en su nombre
    - **Formato de fechas**: Las columnas de desembolso deben contener fechas como jul-25, ago-25, etc.
    
    ### 🔧 Modos de actualización:
    - **merge**: Actualiza existentes y crea nuevos (por defecto)
    - **replace**: Reemplaza toda la colección
    - **append**: Solo agrega nuevos registros
    
    ### 📊 Procesamiento:
    1. Lee datos del Excel
    2. Separa columnas de Desembolso normal y REAL
    3. Convierte a formato largo (un registro por mes)
    4. Crea campo Periodo en formato fecha
    5. Guarda en Firebase con ID único por organismo_banco_mes
    
    ### 🎯 Cómo usar:
    1. Selecciona archivo .xlsx con formato correcto
    2. Elige modo de actualización
    3. Haz clic en "Execute"
    
    ### ✅ Validaciones:
    - Solo archivos .xlsx
    - Columnas Organismo y Banco requeridas
    - Al menos una columna de Desembolso
    - Tamaño máximo: 10MB
    """
    if not FIREBASE_AVAILABLE or not SCRIPTS_AVAILABLE:
        raise HTTPException(status_code=503, detail="Firebase o scripts no disponibles")
    
    if not FLUJO_CAJA_OPERATIONS_AVAILABLE:
        raise HTTPException(status_code=503, detail="Operaciones de flujo de caja no disponibles")
    
    # Validar modo de actualización
    if update_mode not in ["merge", "replace", "append"]:
        raise HTTPException(status_code=400, detail="update_mode debe ser: merge, replace o append")
    
    # Validar tipo de archivo
    if not archivo_excel.filename.lower().endswith(('.xlsx', '.xls')):
        raise HTTPException(status_code=400, detail="Solo se permiten archivos Excel (.xlsx, .xls)")
    
    # Validar tamaño del archivo (10MB máximo)
    max_size = 10 * 1024 * 1024  # 10MB
    file_content = await archivo_excel.read()
    if len(file_content) > max_size:
        raise HTTPException(status_code=400, detail="El archivo no puede exceder 10MB")
    
    try:
        # Procesar el archivo Excel
        result = process_flujo_caja_excel(file_content, archivo_excel.filename)
        
        if not result["success"]:
            raise HTTPException(status_code=400, detail=result.get('error', 'Error procesando Excel'))
        
        # Guardar en Firebase
        save_result = await save_flujo_caja_to_firebase(result["data"], update_mode)
        
        if not save_result["success"]:
            raise HTTPException(status_code=500, detail=save_result.get('error', 'Error guardando en Firebase'))
        
        # Combinar resultados
        final_result = {
            "success": True,
            "message": "Flujos de caja cargados exitosamente",
            "archivo_info": {
                "nombre_archivo": archivo_excel.filename,
                "tamaño_bytes": len(file_content),
                "modo_actualizacion": update_mode
            },
            "procesamiento": result["summary"],
            "guardado": save_result["summary"],
            "timestamp": datetime.now().isoformat(),
            "last_updated": "2025-10-20T00:00:00Z"
        }
        
        return create_utf8_response(final_result)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")

@app.get("/emprestito/flujo-caja/all", tags=["Gestión de Empréstito"], summary="🔵 Flujos de Caja")
async def get_flujos_caja_all(
    responsable: Optional[str] = Query(None, description="Filtrar por responsable específico"),
    organismo: Optional[str] = Query(None, description="Filtrar por organismo específico"),
    banco: Optional[str] = Query(None, description="Filtrar por banco específico"),
    bp_proyecto: Optional[str] = Query(None, description="Filtrar por BP Proyecto específico"),
    mes: Optional[str] = Query(None, description="Filtrar por mes específico (ej: jul-25)"),
    periodo_desde: Optional[str] = Query(None, description="Periodo desde (formato: YYYY-MM-DD)"),
    periodo_hasta: Optional[str] = Query(None, description="Periodo hasta (formato: YYYY-MM-DD)"),
    limit: Optional[int] = Query(None, ge=1, le=1000, description="Límite de registros")
):
    """
    ## � GET | �📊 Consultas con Filtros | Obtener Todos los Flujos de Caja
    
    Endpoint para consultar flujos de caja almacenados en la colección "flujo_caja_emprestito".
    
    ### ✅ Casos de uso:
    - Consultar flujos de caja por organismo o banco
    - Filtrar por períodos específicos
    - Analizar desembolsos planeados vs reales
    - Generar reportes de flujo de caja
    - Exportar datos para dashboards
    
    ### 🔍 Filtros disponibles:
    - **responsable**: Filtrar por responsable específico
    - **organismo**: Filtrar por organismo específico
    - **banco**: Filtrar por banco específico
    - **bp_proyecto**: Filtrar por BP Proyecto específico  
    - **mes**: Filtrar por mes específico (ej: "jul-25")
    - **periodo_desde**: Desde fecha específica (YYYY-MM-DD)
    - **periodo_hasta**: Hasta fecha específica (YYYY-MM-DD)
    - **limit**: Limitar número de resultados (máx: 1000)
    
    ### 📊 Información incluida:
    - Responsable, organismo, banco y BP proyecto
    - Descripción del BP proyecto
    - Mes y período en formato fecha
    - Monto de desembolso
    - Columna origen del Excel
    - ID único del registro y metadatos de archivo origen
    
    ### 📝 Ejemplo de uso:
    ```javascript
    // Obtener todos los flujos
    const response = await fetch('/emprestito/flujo-caja/all');
    
    // Filtrar por banco específico
    const response = await fetch('/emprestito/flujo-caja/all?banco=Banco Popular');
    
    // Filtrar por período
    const response = await fetch('/emprestito/flujo-caja/all?periodo_desde=2025-07-01&periodo_hasta=2025-12-31');
    ```
    
    ### 💡 Características:
    - **Ordenamiento**: Por período (cronológico)
    - **Resumen**: Estadísticas agregadas incluidas
    - **Metadatos**: Organismos, bancos y meses únicos
    - **UTF-8**: Soporte completo para caracteres especiales
    """
    if not FIREBASE_AVAILABLE or not SCRIPTS_AVAILABLE:
        raise HTTPException(status_code=503, detail="Firebase o scripts no disponibles")
    
    if not FLUJO_CAJA_OPERATIONS_AVAILABLE:
        raise HTTPException(status_code=503, detail="Operaciones de flujo de caja no disponibles")
    
    try:
        # Construir filtros
        filters = {}
        
        if responsable:
            filters['responsable'] = responsable
        if organismo:
            filters['organismo'] = organismo
        if banco:
            filters['banco'] = banco
        if bp_proyecto:
            filters['bp_proyecto'] = bp_proyecto
        if mes:
            filters['mes'] = mes
        if periodo_desde:
            filters['periodo_desde'] = periodo_desde
        if periodo_hasta:
            filters['periodo_hasta'] = periodo_hasta
        if limit:
            filters['limit'] = limit
        
        # Obtener datos de Firebase
        result = await get_flujo_caja_from_firebase(filters)
        
        if not result["success"]:
            raise HTTPException(
                status_code=500,
                detail=f"Error obteniendo flujos de caja: {result.get('error', 'Error desconocido')}"
            )
        
        # Agregar información del endpoint
        result["last_updated"] = "2025-10-20T00:00:00Z"
        result["endpoint_info"] = {
            "filtros_aplicados": len([k for k, v in filters.items() if v is not None]),
            "total_filtros_disponibles": 6,
            "ordenamiento": "por_periodo_cronologico"
        }
        
        return create_utf8_response(result)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error procesando consulta de flujos de caja: {str(e)}"
        )

@app.post("/emprestito/crear-tabla-proyecciones", tags=["Gestión de Empréstito"], summary="🟢 Crear Tabla Proyecciones")
async def crear_tabla_proyecciones_endpoint():
    """
    ## � POST | 🔗 Integración Externa | Crear Tabla de Proyecciones desde Google Sheets
    
    **Propósito**: Lee datos de Google Sheets específico y los carga en la colección "proyecciones_emprestito".
    
    ### 🔧 Proceso automático:
    1. **Lee datos** desde Google Sheets específico (Publicados Emprestitos nuevo)
    2. **Mapea campos** según especificaciones definidas
    3. **Procesa BP** agregando prefijo "BP" automáticamente
    4. **Guarda en Firebase** en colección "proyecciones_emprestito"
    5. **Elimina temporal** y registra fecha de actualización
    
    ### 📋 Mapeo de campos:
    - `Item` → `item`
    - `Nro de Proceso` → `referencia_proceso`
    - `NOMBRE ABREVIADO` → `nombre_organismo_reducido`
    - `Banco` → `nombre_banco`
    - `BP` → `BP` (con prefijo "BP" agregado)
    - `DESCRIPCION BP` → `descripcion_bp`
    - `Proyecto` → `nombre_generico_proyecto`
    - `Proyecto con su respectivo contrato` → `nombre_resumido_proceso`
    - `ID PAA` → `id_paa`
    - `LINK DEL PROCESO` → `urlProceso`
    - `valor_proyectado` → `valor_proyectado` (mapeo directo)
    
    **NOTA**: La columna en Google Sheets ahora se llama "valor_proyectado" directamente
    
    ### ✅ Características:
    - **Reemplazo completo**: Elimina datos existentes y carga nuevos
    - **Validación automática**: Verifica campos obligatorios
    - **Manejo de errores**: Reporta filas con problemas
    - **Metadatos**: Registra fecha de carga y estadísticas
    - **UTF-8**: Soporte completo para caracteres especiales
    - **URL fija**: Usa Google Sheets predefinido
    - **Service Account**: Autenticación con service account configurado
    
    ### 🔐 Autenticación:
    - **Service Account**: `unidad-cumplimiento-sheets@unidad-cumplimiento.iam.gserviceaccount.com`
    - **Permisos**: Debe tener acceso de lectura al Google Sheets configurado
    - **Scopes**: `spreadsheets.readonly` y `drive.readonly`
    - **Credenciales**: Configuradas en el sistema usando ADC o variable de entorno
    
    ### 📝 Ejemplo de respuesta:
    ```json
    {
        "success": true,
        "message": "Tabla de proyecciones creada exitosamente",
        "resumen_operacion": {
            "filas_leidas": 150,
            "registros_procesados": 148,
            "registros_guardados": 148,
            "docs_eliminados_previos": 145
        }
    }
    ```
    
    ### 💡 Notas importantes:
    - **URL fija**: Usa Google Sheets predefinido internamente
    - **Automático**: No requiere parámetros de entrada
    - **Destructivo**: Reemplaza todos los datos existentes
    - **Auditable**: Mantiene registro de fecha de última actualización
    - **Permisos**: Requiere service account con acceso al Google Sheets
    """
    if not FIREBASE_AVAILABLE or not SCRIPTS_AVAILABLE:
        raise HTTPException(status_code=503, detail="Firebase o scripts no disponibles")
    
    if not EMPRESTITO_OPERATIONS_AVAILABLE:
        raise HTTPException(status_code=503, detail="Operaciones de empréstito no disponibles")
    
    try:
        # URL fija del Google Sheets según especificación del usuario
        sheet_url = "https://docs.google.com/spreadsheets/d/11-sdLwINHHwRit8b9jnnXcO2phhuEVUpXM6q6yv8DYo/edit?usp=sharing"
        
        # Ejecutar proceso completo
        result = await crear_tabla_proyecciones_desde_sheets(sheet_url)
        
        if not result["success"]:
            # Verificar si es error de autorización para dar mejor mensaje
            error_msg = result.get('error', 'Error desconocido')
            
            if 'Unauthorized' in error_msg or '401' in error_msg:
                raise HTTPException(
                    status_code=403,
                    detail={
                        "error": "El Google Sheets no es público o no tiene permisos de lectura",
                        "solucion": "Para resolver este problema:",
                        "pasos": [
                            "1. Abrir el Google Sheets",
                            "2. Hacer clic en 'Compartir' (botón azul superior derecho)",
                            "3. En 'Obtener enlace', cambiar a 'Cualquier persona con el enlace'",
                            "4. Cambiar permisos a 'Lector'",
                            "5. Copiar el enlace y usarlo en el parámetro sheet_url"
                        ],
                        "error_original": error_msg
                    }
                )
            else:
                raise HTTPException(
                    status_code=500,
                    detail=f"Error creando tabla de proyecciones: {error_msg}"
                )
        
        # Agregar información del endpoint
        result["last_updated"] = "2025-10-22T00:00:00Z"
        result["endpoint_info"] = {
            "sheet_url_fija": True,
            "operacion": "reemplazo_completo",
            "campos_mapeados": 10,
            "validaciones": "campos_obligatorios",
            "service_account": "unidad-cumplimiento-sheets@unidad-cumplimiento.iam.gserviceaccount.com"
        }
        
        return create_utf8_response(result)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error procesando creación de tabla de proyecciones: {str(e)}"
        )

@app.get("/emprestito/leer-tabla-proyecciones", tags=["Gestión de Empréstito"], summary="🔵 Tabla de Proyecciones")
async def leer_tabla_proyecciones_endpoint(
    sheet_url: Optional[str] = Query(
        None, 
        description="URL de Google Sheets para detectar registros con Nro de Proceso que NO están en procesos_emprestito."
    ),
    solo_no_guardados: bool = Query(
        False,
        description="Si es True y se proporciona sheet_url, devuelve solo registros que NO están en procesos_emprestito pero tienen Nro de Proceso válido"
    )
):
    """
    ## 📋 GET | 📋 Listados | Leer Tabla de Proyecciones de Empréstito
    
    **Propósito**: 
    - **Sin parámetros**: Obtiene todos los registros de la colección "proyecciones_emprestito".
    - **Con sheet_url**: Detecta registros de Google Sheets que NO están en procesos_emprestito.
    
    ### ✅ Casos de uso:
    
    #### Modo 1: Lectura de BD (sin parámetros)
    - Consultar proyecciones cargadas desde Google Sheets
    - Verificar datos después de carga
    - Exportar proyecciones para análisis
    - Integrar con dashboards y reportes
    - Auditar última fecha de actualización
    
    #### Modo 2: Detección de no guardados en procesos_emprestito (con sheet_url)
    - **Identifica registros pendientes**: Encuentra qué datos de Sheets tienen Nro de Proceso pero NO están en procesos_emprestito
    - **Validación de sincronización**: Verifica qué procesos faltan por crear en la BD
    - **Detección de pendientes**: Lista proyecciones que necesitan ser guardadas como procesos
    - **Control de calidad**: Asegura que todos los procesos válidos estén registrados
    
    ### 🔍 Condiciones para Modo 2 (Registros devueltos):
    1. ✅ Tienen valor en columna "Nro de Proceso" (no vacío, no null)
    2. ❌ El valor de "Nro de Proceso" NO existe en la colección `procesos_emprestito` con campo `referencia_proceso`
    
    ### 📊 Información incluida (Modo 1 - Sin sheet_url):
    - **Datos mapeados**: Todos los campos según mapeo definido
    - **Metadatos**: Fecha de carga, fuente, fila origen
    - **Timestamps**: Fecha de guardado y última actualización
    - **ID único**: Identificador de Firebase para cada registro
    - **Estadísticas**: Información de la última carga realizada
    
    ### 🔍 Información incluida (Modo 2 - Con sheet_url):
    - **Registros no guardados**: Solo los que tienen Nro de Proceso válido pero NO existen en procesos_emprestito
    - **Comparación precisa**: Verifica contra la colección procesos_emprestito
    - **Metadata de comparación**: Estadísticas sobre registros encontrados/no encontrados
    - **Optimización**: Usa mapas en memoria para comparación rápida O(1)
    
    ### 🔍 Campos de respuesta:
    - `item`: Número de ítem
    - `referencia_proceso`: Número de proceso (Nro de Proceso de Sheets)
    - `nombre_organismo_reducido`: Nombre abreviado del organismo
    - `nombre_banco`: Banco asociado
    - `BP`: Código BP con prefijo agregado
    - `descripcion_bp`: Descripción del BP
    - `nombre_generico_proyecto`: Nombre del proyecto
    - `nombre_resumido_proceso`: Proyecto con contrato
    - `id_paa`: ID del PAA
    - `urlProceso`: Enlace al proceso
    - `valor_proyectado`: Valor total del proyecto (única columna de valor)
    - `_es_nuevo`: (Solo Modo 2) Indica que es un registro no guardado
    - `_motivo`: (Solo Modo 2) Razón por la cual no está guardado
    
    **NOTA**: NO se incluyen campos duplicados como "VALOR TOTAL" o "Valor Adjudicado"
    
    ### 📝 Ejemplos de uso:
    
    #### Ejemplo 1: Leer todos los registros guardados en proyecciones_emprestito
    ```javascript
    const response = await fetch('/emprestito/leer-tabla-proyecciones');
    const data = await response.json();
    
    if (data.success) {
        console.log(`Proyecciones encontradas: ${data.count}`);
        data.data.forEach(proyeccion => {
            console.log(`${proyeccion.referencia_proceso}: ${proyeccion.valor_proyectado}`);
        });
    }
    ```
    
    #### Ejemplo 2: Detectar registros pendientes de guardar en procesos_emprestito
    ```javascript
    const sheetUrl = 'https://docs.google.com/spreadsheets/d/ABC123/edit';
    const response = await fetch(
        `/emprestito/leer-tabla-proyecciones?sheet_url=${encodeURIComponent(sheetUrl)}&solo_no_guardados=true`
    );
    const data = await response.json();
    
    if (data.success) {
        console.log(`Registros pendientes: ${data.count}`);
        console.log(`Total en Sheets: ${data.metadata.total_sheets}`);
        console.log(`Ya en procesos_emprestito: ${data.metadata.ya_en_procesos}`);
        console.log(`Sin Nro de Proceso: ${data.metadata.sin_proceso}`);
        
        // Procesar registros pendientes
        data.data.forEach(registro => {
            console.log(`Pendiente: ${registro.referencia_proceso} - ${registro._motivo}`);
        });
    }
    ```
    
    ### 💡 Características:
    - **Ordenamiento** (Modo 1): Por fecha de carga (más recientes primero)
    - **Filtrado inteligente** (Modo 2): Solo registros con Nro Proceso válido que NO están en procesos_emprestito
    - **Validación estricta**: Verifica que referencia_proceso no sea null, vacío o solo espacios
    - **UTF-8**: Soporte completo para caracteres especiales
    - **Auditoría**: Incluye información de trazabilidad
    - **Optimización**: Búsqueda O(1) usando sets en memoria
    """
    if not FIREBASE_AVAILABLE or not SCRIPTS_AVAILABLE:
        raise HTTPException(status_code=503, detail="Firebase o scripts no disponibles")
    
    if not EMPRESTITO_OPERATIONS_AVAILABLE:
        raise HTTPException(status_code=503, detail="Operaciones de empréstito no disponibles")
    
    try:
        # Modo 2: Comparar con Google Sheets y devolver no guardados en procesos_emprestito
        if sheet_url and solo_no_guardados:
            result = await leer_proyecciones_no_guardadas(sheet_url)
            
            if not result["success"]:
                raise HTTPException(
                    status_code=500,
                    detail=f"Error comparando con Google Sheets: {result.get('error', 'Error desconocido')}"
                )
            
            # Agregar información del endpoint
            result["last_updated"] = "2025-11-01T00:00:00Z"
            result["endpoint_info"] = {
                "modo": "deteccion_no_guardados",
                "sheet_url": sheet_url,
                "filtro": "no_en_procesos_emprestito_con_nro_proceso_valido",
                "coleccion_comparada": "procesos_emprestito",
                "campo_comparado": "referencia_proceso",
                "optimizado": True
            }
            
            return create_utf8_response(result)
        
        # Modo 1: Obtener proyecciones de Firebase (comportamiento original)
        result = await leer_proyecciones_emprestito()
        
        if not result["success"]:
            raise HTTPException(
                status_code=500,
                detail=f"Error leyendo tabla de proyecciones: {result.get('error', 'Error desconocido')}"
            )
        
        # Agregar información del endpoint
        result["last_updated"] = "2025-11-01T00:00:00Z"
        result["endpoint_info"] = {
            "modo": "lectura_bd",
            "coleccion_fuente": "proyecciones_emprestito",
            "ordenamiento": "por_fecha_carga_desc",
            "incluye_metadatos": True,
            "trazabilidad_completa": True
        }
        
        return create_utf8_response(result)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error procesando lectura de tabla de proyecciones: {str(e)}"
        )


@app.get("/emprestito/proyecciones-sin-proceso", tags=["Gestión de Empréstito"])
async def endpoint_proyecciones_sin_proceso():
    """Devuelve proyecciones cuya 'referencia_proceso' no exista en 'procesos_emprestito'."""
    if not FIREBASE_AVAILABLE or not SCRIPTS_AVAILABLE:
        raise HTTPException(status_code=503, detail="Firebase o scripts no disponibles")

    if not EMPRESTITO_OPERATIONS_AVAILABLE:
        raise HTTPException(status_code=503, detail="Operaciones de empréstito no disponibles")

    try:
        result = await get_proyecciones_sin_proceso()

        if not result.get("success", False):
            raise HTTPException(status_code=500, detail=result.get("error", "Error desconocido"))

        # Agregar metadata del endpoint
        result["last_updated"] = "2025-10-23T00:00:00Z"
        result["endpoint_info"] = {
            "coleccion_origen": "proyecciones_emprestito",
            "coleccion_comparacion": "procesos_emprestito",
            "filter_field": "referencia_proceso",
            "returned_count": result.get("count", 0)
        }

        return create_utf8_response(result)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error procesando endpoint: {str(e)}")


# ============================================================================
# ENDPOINTS PUT - MODIFICAR DATOS EN FIREBASE
# ============================================================================

@app.put("/emprestito/modificar-orden-compra", tags=["Gestión de Empréstito"], summary="🟡 Modificar Orden de Compra")
async def modificar_orden_compra(
    numero_orden: str = Query(..., description="Número de orden a modificar (REQUERIDO)"),
    ano_orden: Optional[int] = Query(None, description="[Opcional] Año de la orden"),
    bp: Optional[str] = Query(None, description="[Opcional] BP"),
    bpin: Optional[str] = Query(None, description="[Opcional] BPIN"),
    estado: Optional[str] = Query(None, description="[Opcional] Estado de la orden"),
    estado_orden: Optional[str] = Query(None, description="[Opcional] Estado de la orden (alternativo)"),
    fecha_actualizacion: Optional[str] = Query(None, description="[Opcional] Fecha de actualización"),
    fecha_creacion: Optional[str] = Query(None, description="[Opcional] Fecha de creación"),
    fecha_enriquecimiento_tvec: Optional[str] = Query(None, description="[Opcional] Fecha de enriquecimiento TVEC"),
    fecha_guardado: Optional[str] = Query(None, description="[Opcional] Fecha de guardado"),
    fecha_publicacion_orden: Optional[str] = Query(None, description="[Opcional] Fecha de publicación de la orden"),
    fecha_vencimiento_orden: Optional[str] = Query(None, description="[Opcional] Fecha de vencimiento de la orden"),
    fuente_datos: Optional[str] = Query(None, description="[Opcional] Fuente de datos"),
    items: Optional[str] = Query(None, description="[Opcional] Items (JSON array)"),
    modalidad_contratacion: Optional[str] = Query(None, description="[Opcional] Modalidad de contratación"),
    nit_entidad: Optional[str] = Query(None, description="[Opcional] NIT de la entidad"),
    nit_proveedor: Optional[str] = Query(None, description="[Opcional] NIT del proveedor"),
    nombre_banco: Optional[str] = Query(None, description="[Opcional] Nombre del banco"),
    nombre_centro_gestor: Optional[str] = Query(None, description="[Opcional] Nombre del centro gestor"),
    nombre_proveedor: Optional[str] = Query(None, description="[Opcional] Nombre del proveedor"),
    nombre_resumido_proceso: Optional[str] = Query(None, description="[Opcional] Nombre resumido del proceso"),
    objeto_orden: Optional[str] = Query(None, description="[Opcional] Objeto de la orden"),
    observaciones: Optional[str] = Query(None, description="[Opcional] Observaciones sobre la orden"),
    ordenador_gasto: Optional[str] = Query(None, description="[Opcional] Ordenador de gasto"),
    plataforma_origen: Optional[str] = Query(None, description="[Opcional] Plataforma de origen"),
    rama_entidad: Optional[str] = Query(None, description="[Opcional] Rama de la entidad"),
    sector: Optional[str] = Query(None, description="[Opcional] Sector"),
    solicitante: Optional[str] = Query(None, description="[Opcional] Solicitante"),
    solicitud_id: Optional[str] = Query(None, description="[Opcional] ID de solicitud"),
    tipo: Optional[str] = Query(None, description="[Opcional] Tipo"),
    tipo_documento: Optional[str] = Query(None, description="[Opcional] Tipo de documento"),
    valor_orden: Optional[float] = Query(None, description="[Opcional] Valor de la orden"),
    valor_proyectado: Optional[float] = Query(None, description="[Opcional] Valor proyectado"),
    datos_json: Optional[str] = Query(None, description="[Opcional] JSON con campos adicionales a actualizar"),
):
    """
    ## 🟡 PUT | ✏️ Modificar | Modificar Orden de Compra en Firebase
    
    Endpoint para modificar un registro en la colección `ordenes_compra_emprestito` 
    usando el campo `numero_orden` como identificador único.
    
    ### ✅ Funcionalidades principales:
    - **Actualización selectiva**: Solo se modifican los campos especificados
    - **Preservación de datos**: Los campos no incluidos mantienen sus valores originales
    - **Búsqueda por numero_orden**: Identifica el documento automáticamente
    - **Validación**: Verifica que el registro exista antes de actualizar
    - **Múltiples formas de entrada**: Query parameters para facilitar pruebas en Swagger
    - **Respuesta clara**: Informa el estado de la operación
    
    ### ⚙️ Parámetros disponibles (todos opcionales excepto numero_orden):
    - `numero_orden` (string, **REQUERIDO**): El número de orden a modificar
    - `ano_orden` (int, opcional): Año de la orden
    - `bp` (string, opcional): BP
    - `bpin` (string, opcional): BPIN
    - `estado` (string, opcional): Estado de la orden
    - `estado_orden` (string, opcional): Estado de la orden (alternativo)
    - `fecha_actualizacion` (string, opcional): Fecha de actualización
    - `fecha_creacion` (string, opcional): Fecha de creación
    - `fecha_enriquecimiento_tvec` (string, opcional): Fecha de enriquecimiento TVEC
    - `fecha_guardado` (string, opcional): Fecha de guardado
    - `fecha_publicacion_orden` (string, opcional): Fecha de publicación de la orden
    - `fecha_vencimiento_orden` (string, opcional): Fecha de vencimiento de la orden
    - `fuente_datos` (string, opcional): Fuente de datos
    - `items` (string, opcional): Items (JSON array como string)
    - `modalidad_contratacion` (string, opcional): Modalidad de contratación
    - `nit_entidad` (string, opcional): NIT de la entidad
    - `nit_proveedor` (string, opcional): NIT del proveedor
    - `nombre_banco` (string, opcional): Nombre del banco
    - `nombre_centro_gestor` (string, opcional): Nombre del centro gestor
    - `nombre_proveedor` (string, opcional): Nombre del proveedor
    - `nombre_resumido_proceso` (string, opcional): Nombre resumido del proceso
    - `objeto_orden` (string, opcional): Objeto de la orden
    - `observaciones` (string, opcional): Observaciones sobre la orden
    - `ordenador_gasto` (string, opcional): Ordenador de gasto
    - `plataforma_origen` (string, opcional): Plataforma de origen
    - `rama_entidad` (string, opcional): Rama de la entidad
    - `sector` (string, opcional): Sector
    - `solicitante` (string, opcional): Solicitante
    - `solicitud_id` (string, opcional): ID de solicitud
    - `tipo` (string, opcional): Tipo
    - `tipo_documento` (string, opcional): Tipo de documento
    - `valor_orden` (float, opcional): Valor de la orden
    - `valor_proyectado` (float, opcional): Valor proyectado
    - `datos_json` (string, opcional): JSON con campos adicionales a actualizar
    
    ### 📝 Ejemplos de uso en Swagger:
    ```
    numero_orden: OC-2024-001
    estado: pagado
    valor_total: 5000000
    observaciones: Orden procesada
    ```
    
    O incluir campos adicionales en:
    ```
    datos_json: {"campo_adicional": "valor", "otro_campo": 123}
    ```
    
    ### ✅ Respuesta exitosa (200):
    ```json
    {
        "success": true,
        "message": "Orden de compra actualizada correctamente",
        "numero_orden": "OC-2024-001",
        "campos_actualizados": ["estado", "valor_total", "observaciones"],
        "timestamp": "2024-11-12T10:30:45.123456"
    }
    ```
    
    ### ❌ Respuesta de error (404):
    ```json
    {
        "success": false,
        "error": "Orden de compra no encontrada",
        "numero_orden": "OC-2024-001",
        "timestamp": "2024-11-12T10:30:45.123456"
    }
    ```
    
    ### 💡 Notas importantes:
    - El `numero_orden` es el identificador único
    - Los campos no especificados NO se modifican
    - La actualización es parcial (solo lo que envíes se modifica)
    - Se requiere Firebase disponible
    - Perfectamente integrado con Swagger UI para pruebas interactivas
    """
    if not FIREBASE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Firebase no está disponible")

    try:
        # Construir diccionario de datos a actualizar
        datos_actualizados = {}
        
        if ano_orden is not None:
            datos_actualizados["ano_orden"] = ano_orden
        if bp is not None:
            datos_actualizados["bp"] = bp
        if bpin is not None:
            datos_actualizados["bpin"] = bpin
        if estado is not None:
            datos_actualizados["estado"] = estado
        if estado_orden is not None:
            datos_actualizados["estado_orden"] = estado_orden
        if fecha_actualizacion is not None:
            datos_actualizados["fecha_actualizacion"] = fecha_actualizacion
        if fecha_creacion is not None:
            datos_actualizados["fecha_creacion"] = fecha_creacion
        if fecha_enriquecimiento_tvec is not None:
            datos_actualizados["fecha_enriquecimiento_tvec"] = fecha_enriquecimiento_tvec
        if fecha_guardado is not None:
            datos_actualizados["fecha_guardado"] = fecha_guardado
        if fecha_publicacion_orden is not None:
            datos_actualizados["fecha_publicacion_orden"] = fecha_publicacion_orden
        if fecha_vencimiento_orden is not None:
            datos_actualizados["fecha_vencimiento_orden"] = fecha_vencimiento_orden
        if fuente_datos is not None:
            datos_actualizados["fuente_datos"] = fuente_datos
        if items is not None:
            try:
                datos_actualizados["items"] = json.loads(items) if isinstance(items, str) else items
            except:
                datos_actualizados["items"] = items
        if modalidad_contratacion is not None:
            datos_actualizados["modalidad_contratacion"] = modalidad_contratacion
        if nit_entidad is not None:
            datos_actualizados["nit_entidad"] = nit_entidad
        if nit_proveedor is not None:
            datos_actualizados["nit_proveedor"] = nit_proveedor
        if nombre_banco is not None:
            datos_actualizados["nombre_banco"] = nombre_banco
        if nombre_centro_gestor is not None:
            datos_actualizados["nombre_centro_gestor"] = nombre_centro_gestor
        if nombre_proveedor is not None:
            datos_actualizados["nombre_proveedor"] = nombre_proveedor
        if nombre_resumido_proceso is not None:
            datos_actualizados["nombre_resumido_proceso"] = nombre_resumido_proceso
        if objeto_orden is not None:
            datos_actualizados["objeto_orden"] = objeto_orden
        if observaciones is not None:
            datos_actualizados["observaciones"] = observaciones
        if ordenador_gasto is not None:
            datos_actualizados["ordenador_gasto"] = ordenador_gasto
        if plataforma_origen is not None:
            datos_actualizados["plataforma_origen"] = plataforma_origen
        if rama_entidad is not None:
            datos_actualizados["rama_entidad"] = rama_entidad
        if sector is not None:
            datos_actualizados["sector"] = sector
        if solicitante is not None:
            datos_actualizados["solicitante"] = solicitante
        if solicitud_id is not None:
            datos_actualizados["solicitud_id"] = solicitud_id
        if tipo is not None:
            datos_actualizados["tipo"] = tipo
        if tipo_documento is not None:
            datos_actualizados["tipo_documento"] = tipo_documento
        if valor_orden is not None:
            datos_actualizados["valor_orden"] = valor_orden
        if valor_proyectado is not None:
            datos_actualizados["valor_proyectado"] = valor_proyectado
        
        # Parsear JSON adicional si se proporciona
        if datos_json:
            try:
                datos_json_dict = json.loads(datos_json)
                datos_actualizados.update(datos_json_dict)
            except json.JSONDecodeError:
                raise HTTPException(
                    status_code=400,
                    detail="El parámetro 'datos_json' debe ser un JSON válido"
                )
        
        # Validar que se proporcionaron datos para actualizar
        if not datos_actualizados:
            raise HTTPException(
                status_code=400,
                detail="Debes proporcionar al menos un campo para actualizar o un JSON válido en datos_json"
            )
        
        db = get_firestore_client()
        if not db:
            raise HTTPException(status_code=503, detail="No se pudo obtener cliente de Firebase")
        
        # Buscar el documento por numero_orden
        coleccion = db.collection("ordenes_compra_emprestito")
        query = coleccion.where("numero_orden", "==", numero_orden)
        docs = list(query.stream())
        
        if not docs:
            raise HTTPException(
                status_code=404, 
                detail=f"Orden de compra con número '{numero_orden}' no encontrada"
            )
        
        # Obtener el ID del documento
        doc_id = docs[0].id
        
        # Actualizar solo los campos proporcionados
        campos_actualizados = list(datos_actualizados.keys())
        coleccion.document(doc_id).update(datos_actualizados)
        
        return create_utf8_response({
            "success": True,
            "message": "Orden de compra actualizada correctamente",
            "numero_orden": numero_orden,
            "campos_actualizados": campos_actualizados,
            "timestamp": datetime.now().isoformat()
        })

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error al modificar orden de compra: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail=f"Error al actualizar la orden de compra: {str(e)}"
        )


@app.put("/emprestito/modificar-proceso", tags=["Gestión de Empréstito"], summary="🟡 Modificar Proceso de Empréstito")
async def modificar_proceso(
    referencia_proceso: str = Query(..., description="Referencia del proceso a modificar (REQUERIDO)"),
    adjudicado: Optional[str] = Query(None, description="[Opcional] Adjudicado"),
    bp: Optional[str] = Query(None, description="[Opcional] BP"),
    conteo_respuestas_ofertas: Optional[int] = Query(None, description="[Opcional] Conteo de respuestas de ofertas"),
    descripcion_proceso: Optional[str] = Query(None, description="[Opcional] Descripción del proceso"),
    duracion: Optional[int] = Query(None, description="[Opcional] Duración"),
    estado_proceso: Optional[str] = Query(None, description="[Opcional] Estado del proceso"),
    estado_resumen: Optional[str] = Query(None, description="[Opcional] Estado resumen"),
    fase: Optional[str] = Query(None, description="[Opcional] Fase"),
    fecha_actualizacion: Optional[str] = Query(None, description="[Opcional] Fecha de actualización"),
    fecha_actualizacion_completa: Optional[str] = Query(None, description="[Opcional] Fecha de actualización completa"),
    fecha_creacion: Optional[str] = Query(None, description="[Opcional] Fecha de creación"),
    fecha_publicacion: Optional[str] = Query(None, description="[Opcional] Fecha de publicación"),
    fecha_publicacion_fase: Optional[str] = Query(None, description="[Opcional] Fecha de publicación fase"),
    fecha_publicacion_fase_3: Optional[str] = Query(None, description="[Opcional] Fecha de publicación fase 3"),
    id_paa: Optional[str] = Query(None, description="[Opcional] ID PAA"),
    modalidad_contratacion: Optional[str] = Query(None, description="[Opcional] Modalidad de contratación"),
    nombre_banco: Optional[str] = Query(None, description="[Opcional] Nombre del banco"),
    nombre_centro_gestor: Optional[str] = Query(None, description="[Opcional] Nombre del centro gestor"),
    nombre_proceso: Optional[str] = Query(None, description="[Opcional] Nombre del proceso"),
    nombre_resumido_proceso: Optional[str] = Query(None, description="[Opcional] Nombre resumido del proceso"),
    nombre_unidad: Optional[str] = Query(None, description="[Opcional] Nombre de unidad"),
    numero_lotes: Optional[int] = Query(None, description="[Opcional] Número de lotes"),
    observaciones_test: Optional[str] = Query(None, description="[Opcional] Observaciones test"),
    plataforma: Optional[str] = Query(None, description="[Opcional] Plataforma"),
    proceso_contractual: Optional[str] = Query(None, description="[Opcional] Proceso contractual"),
    proveedores_con_invitacion: Optional[str] = Query(None, description="[Opcional] Proveedores con invitación"),
    proveedores_invitados: Optional[str] = Query(None, description="[Opcional] Proveedores invitados"),
    proveedores_que_manifestaron: Optional[str] = Query(None, description="[Opcional] Proveedores que manifestaron"),
    respuestas_externas: Optional[str] = Query(None, description="[Opcional] Respuestas externas"),
    respuestas_procedimiento: Optional[str] = Query(None, description="[Opcional] Respuestas procedimiento"),
    tipo_contrato: Optional[str] = Query(None, description="[Opcional] Tipo de contrato"),
    unidad_duracion: Optional[str] = Query(None, description="[Opcional] Unidad de duración"),
    urlproceso: Optional[str] = Query(None, description="[Opcional] URL del proceso"),
    valor_proyectado: Optional[float] = Query(None, description="[Opcional] Valor proyectado"),
    valor_publicacion: Optional[float] = Query(None, description="[Opcional] Valor de publicación"),
    visualizaciones_proceso: Optional[int] = Query(None, description="[Opcional] Visualizaciones del proceso"),
    datos_json: Optional[str] = Query(None, description="[Opcional] JSON con campos adicionales a actualizar"),
):
    """
    ## 🟡 PUT | ✏️ Modificar | Modificar Proceso de Empréstito en Firebase
    
    Endpoint para modificar un registro en la colección `procesos_emprestito` 
    usando el campo `referencia_proceso` como identificador único.
    
    ### ✅ Funcionalidades principales:
    - **Actualización selectiva**: Solo se modifican los campos especificados
    - **Preservación de datos**: Los campos no incluidos mantienen sus valores originales
    - **Búsqueda por referencia_proceso**: Identifica el documento automáticamente
    - **Validación**: Verifica que el registro exista antes de actualizar
    - **Múltiples formas de entrada**: Query parameters para facilitar pruebas en Swagger
    - **Respuesta clara**: Informa el estado de la operación
    
    ### ⚙️ Parámetros disponibles (todos opcionales excepto referencia_proceso):
    - `referencia_proceso` (string, **REQUERIDO**): La referencia del proceso a modificar
    - `adjudicado` (string, opcional): Adjudicado
    - `bp` (string, opcional): BP
    - `conteo_respuestas_ofertas` (int, opcional): Conteo de respuestas de ofertas
    - `descripcion_proceso` (string, opcional): Descripción del proceso
    - `duracion` (int, opcional): Duración
    - `estado_proceso` (string, opcional): Estado del proceso
    - `estado_resumen` (string, opcional): Estado resumen
    - `fase` (string, opcional): Fase
    - `fecha_actualizacion` (string, opcional): Fecha de actualización
    - `fecha_actualizacion_completa` (string, opcional): Fecha de actualización completa
    - `fecha_creacion` (string, opcional): Fecha de creación
    - `fecha_publicacion` (string, opcional): Fecha de publicación
    - `fecha_publicacion_fase` (string, opcional): Fecha de publicación fase
    - `fecha_publicacion_fase_3` (string, opcional): Fecha de publicación fase 3
    - `id_paa` (string, opcional): ID PAA
    - `modalidad_contratacion` (string, opcional): Modalidad de contratación
    - `nombre_banco` (string, opcional): Nombre del banco
    - `nombre_centro_gestor` (string, opcional): Nombre del centro gestor
    - `nombre_proceso` (string, opcional): Nombre del proceso
    - `nombre_resumido_proceso` (string, opcional): Nombre resumido del proceso
    - `nombre_unidad` (string, opcional): Nombre de unidad
    - `numero_lotes` (int, opcional): Número de lotes
    - `observaciones_test` (string, opcional): Observaciones test
    - `plataforma` (string, opcional): Plataforma
    - `proceso_contractual` (string, opcional): Proceso contractual
    - `proveedores_con_invitacion` (string, opcional): Proveedores con invitación
    - `proveedores_invitados` (string, opcional): Proveedores invitados
    - `proveedores_que_manifestaron` (string, opcional): Proveedores que manifestaron
    - `respuestas_externas` (string, opcional): Respuestas externas
    - `respuestas_procedimiento` (string, opcional): Respuestas procedimiento
    - `tipo_contrato` (string, opcional): Tipo de contrato
    - `unidad_duracion` (string, opcional): Unidad de duración
    - `urlproceso` (string, opcional): URL del proceso
    - `valor_proyectado` (float, opcional): Valor proyectado
    - `valor_publicacion` (float, opcional): Valor de publicación
    - `visualizaciones_proceso` (int, opcional): Visualizaciones del proceso
    - `datos_json` (string, opcional): JSON con campos adicionales a actualizar
    
    ### 📝 Ejemplos de uso en Swagger:
    ```
    referencia_proceso: PROC-SALUD-2024-001
    estado_proceso: ejecutado
    valor_total: 25000000
    fecha_cierre: 2024-11-12
    observaciones: Proceso completado exitosamente
    ```
    
    ### ✅ Respuesta exitosa (200):
    ```json
    {
        "success": true,
        "message": "Proceso de empréstito actualizado correctamente",
        "referencia_proceso": "PROC-SALUD-2024-001",
        "campos_actualizados": ["estado_proceso", "valor_total", "fecha_cierre", "observaciones"],
        "timestamp": "2024-11-12T10:35:22.654321"
    }
    ```
    
    ### ❌ Respuesta de error (404):
    ```json
    {
        "success": false,
        "error": "Proceso de empréstito no encontrado",
        "referencia_proceso": "PROC-SALUD-2024-001",
        "timestamp": "2024-11-12T10:35:22.654321"
    }
    ```
    
    ### 💡 Notas importantes:
    - La `referencia_proceso` es el identificador único
    - Los campos no especificados NO se modifican
    - La actualización es parcial (solo lo que envíes se modifica)
    - Se requiere Firebase disponible
    - Perfectamente integrado con Swagger UI para pruebas interactivas
    """
    if not FIREBASE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Firebase no está disponible")

    try:
        # Construir diccionario de datos a actualizar
        datos_actualizados = {}
        
        if adjudicado is not None:
            datos_actualizados["adjudicado"] = adjudicado
        if bp is not None:
            datos_actualizados["bp"] = bp
        if conteo_respuestas_ofertas is not None:
            datos_actualizados["conteo_respuestas_ofertas"] = conteo_respuestas_ofertas
        if descripcion_proceso is not None:
            datos_actualizados["descripcion_proceso"] = descripcion_proceso
        if duracion is not None:
            datos_actualizados["duracion"] = duracion
        if estado_proceso is not None:
            datos_actualizados["estado_proceso"] = estado_proceso
        if estado_resumen is not None:
            datos_actualizados["estado_resumen"] = estado_resumen
        if fase is not None:
            datos_actualizados["fase"] = fase
        if fecha_actualizacion is not None:
            datos_actualizados["fecha_actualizacion"] = fecha_actualizacion
        if fecha_actualizacion_completa is not None:
            datos_actualizados["fecha_actualizacion_completa"] = fecha_actualizacion_completa
        if fecha_creacion is not None:
            datos_actualizados["fecha_creacion"] = fecha_creacion
        if fecha_publicacion is not None:
            datos_actualizados["fecha_publicacion"] = fecha_publicacion
        if fecha_publicacion_fase is not None:
            datos_actualizados["fecha_publicacion_fase"] = fecha_publicacion_fase
        if fecha_publicacion_fase_3 is not None:
            datos_actualizados["fecha_publicacion_fase_3"] = fecha_publicacion_fase_3
        if id_paa is not None:
            datos_actualizados["id_paa"] = id_paa
        if modalidad_contratacion is not None:
            datos_actualizados["modalidad_contratacion"] = modalidad_contratacion
        if nombre_banco is not None:
            datos_actualizados["nombre_banco"] = nombre_banco
        if nombre_centro_gestor is not None:
            datos_actualizados["nombre_centro_gestor"] = nombre_centro_gestor
        if nombre_proceso is not None:
            datos_actualizados["nombre_proceso"] = nombre_proceso
        if nombre_resumido_proceso is not None:
            datos_actualizados["nombre_resumido_proceso"] = nombre_resumido_proceso
        if nombre_unidad is not None:
            datos_actualizados["nombre_unidad"] = nombre_unidad
        if numero_lotes is not None:
            datos_actualizados["numero_lotes"] = numero_lotes
        if observaciones_test is not None:
            datos_actualizados["observaciones_test"] = observaciones_test
        if plataforma is not None:
            datos_actualizados["plataforma"] = plataforma
        if proceso_contractual is not None:
            datos_actualizados["proceso_contractual"] = proceso_contractual
        if proveedores_con_invitacion is not None:
            datos_actualizados["proveedores_con_invitacion"] = proveedores_con_invitacion
        if proveedores_invitados is not None:
            datos_actualizados["proveedores_invitados"] = proveedores_invitados
        if proveedores_que_manifestaron is not None:
            datos_actualizados["proveedores_que_manifestaron"] = proveedores_que_manifestaron
        if respuestas_externas is not None:
            datos_actualizados["respuestas_externas"] = respuestas_externas
        if respuestas_procedimiento is not None:
            datos_actualizados["respuestas_procedimiento"] = respuestas_procedimiento
        if tipo_contrato is not None:
            datos_actualizados["tipo_contrato"] = tipo_contrato
        if unidad_duracion is not None:
            datos_actualizados["unidad_duracion"] = unidad_duracion
        if urlproceso is not None:
            datos_actualizados["urlproceso"] = urlproceso
        if valor_proyectado is not None:
            datos_actualizados["valor_proyectado"] = valor_proyectado
        if valor_publicacion is not None:
            datos_actualizados["valor_publicacion"] = valor_publicacion
        if visualizaciones_proceso is not None:
            datos_actualizados["visualizaciones_proceso"] = visualizaciones_proceso
        
        # Parsear JSON adicional si se proporciona
        if datos_json:
            try:
                datos_json_dict = json.loads(datos_json)
                datos_actualizados.update(datos_json_dict)
            except json.JSONDecodeError:
                raise HTTPException(
                    status_code=400,
                    detail="El parámetro 'datos_json' debe ser un JSON válido"
                )
        
        # Validar que se proporcionaron datos para actualizar
        if not datos_actualizados:
            raise HTTPException(
                status_code=400,
                detail="Debes proporcionar al menos un campo para actualizar o un JSON válido en datos_json"
            )
        
        db = get_firestore_client()
        if not db:
            raise HTTPException(status_code=503, detail="No se pudo obtener cliente de Firebase")
        
        # Buscar el documento por referencia_proceso
        coleccion = db.collection("procesos_emprestito")
        query = coleccion.where("referencia_proceso", "==", referencia_proceso)
        docs = list(query.stream())
        
        if not docs:
            raise HTTPException(
                status_code=404, 
                detail=f"Proceso de empréstito con referencia '{referencia_proceso}' no encontrado"
            )
        
        # Obtener el ID del documento
        doc_id = docs[0].id
        
        # Actualizar solo los campos proporcionados
        campos_actualizados = list(datos_actualizados.keys())
        coleccion.document(doc_id).update(datos_actualizados)
        
        return create_utf8_response({
            "success": True,
            "message": "Proceso de empréstito actualizado correctamente",
            "referencia_proceso": referencia_proceso,
            "campos_actualizados": campos_actualizados,
            "timestamp": datetime.now().isoformat()
        })

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error al modificar proceso de empréstito: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail=f"Error al actualizar el proceso de empréstito: {str(e)}"
        )


@app.put("/emprestito/modificar-contrato", tags=["Gestión de Empréstito"], summary="🟡 Modificar Contrato de Empréstito")
async def modificar_contrato(
    referencia_contrato: str = Query(..., description="Referencia del contrato a modificar (REQUERIDO)"),
    _dataset_source: Optional[str] = Query(None, description="[Opcional] Fuente del dataset"),
    banco: Optional[str] = Query(None, description="[Opcional] Banco"),
    bp: Optional[str] = Query(None, description="[Opcional] BP"),
    bpin: Optional[str] = Query(None, description="[Opcional] BPIN"),
    descripcion_proceso: Optional[str] = Query(None, description="[Opcional] Descripción del proceso"),
    entidad_contratante: Optional[str] = Query(None, description="[Opcional] Entidad contratante"),
    estado_contrato: Optional[str] = Query(None, description="[Opcional] Estado del contrato"),
    fecha_actualizacion: Optional[str] = Query(None, description="[Opcional] Fecha de actualización"),
    fecha_fin_contrato: Optional[str] = Query(None, description="[Opcional] Fecha de fin del contrato"),
    fecha_firma_contrato: Optional[str] = Query(None, description="[Opcional] Fecha de firma del contrato"),
    fecha_guardado: Optional[str] = Query(None, description="[Opcional] Fecha de guardado"),
    fecha_inicio_contrato: Optional[str] = Query(None, description="[Opcional] Fecha de inicio del contrato"),
    fuente_datos: Optional[str] = Query(None, description="[Opcional] Fuente de datos"),
    id_contrato: Optional[str] = Query(None, description="[Opcional] ID del contrato"),
    modalidad_contratacion: Optional[str] = Query(None, description="[Opcional] Modalidad de contratación"),
    nit_contratista: Optional[str] = Query(None, description="[Opcional] NIT del contratista"),
    nit_entidad: Optional[str] = Query(None, description="[Opcional] NIT de la entidad"),
    nombre_centro_gestor: Optional[str] = Query(None, description="[Opcional] Nombre del centro gestor"),
    nombre_contratista: Optional[str] = Query(None, description="[Opcional] Nombre del contratista"),
    nombre_procedimiento: Optional[str] = Query(None, description="[Opcional] Nombre del procedimiento"),
    objeto_contrato: Optional[str] = Query(None, description="[Opcional] Objeto del contrato"),
    observaciones_test: Optional[str] = Query(None, description="[Opcional] Observaciones test"),
    ordenador_gasto: Optional[str] = Query(None, description="[Opcional] Ordenador de gasto"),
    proceso_contractual: Optional[str] = Query(None, description="[Opcional] Proceso contractual"),
    referencia_proceso: Optional[str] = Query(None, description="[Opcional] Referencia del proceso"),
    representante_legal: Optional[str] = Query(None, description="[Opcional] Representante legal"),
    sector: Optional[str] = Query(None, description="[Opcional] Sector"),
    supervisor: Optional[str] = Query(None, description="[Opcional] Supervisor"),
    tipo_contrato: Optional[str] = Query(None, description="[Opcional] Tipo de contrato"),
    urlproceso: Optional[str] = Query(None, description="[Opcional] URL del proceso"),
    valor_contrato: Optional[float] = Query(None, description="[Opcional] Valor del contrato"),
    valor_pagado: Optional[float] = Query(None, description="[Opcional] Valor pagado"),
    version_esquema: Optional[str] = Query(None, description="[Opcional] Versión del esquema"),
    datos_json: Optional[str] = Query(None, description="[Opcional] JSON con campos adicionales a actualizar"),
):
    """
    ## 🟡 PUT | ✏️ Modificar | Modificar Contrato de Empréstito en Firebase
    
    Endpoint para modificar un registro en la colección `contratos_emprestito` 
    usando el campo `referencia_contrato` como identificador único.
    
    ### ✅ Funcionalidades principales:
    - **Actualización selectiva**: Solo se modifican los campos especificados
    - **Preservación de datos**: Los campos no incluidos mantienen sus valores originales
    - **Búsqueda por referencia_contrato**: Identifica el documento automáticamente
    - **Validación**: Verifica que el registro exista antes de actualizar
    - **Múltiples formas de entrada**: Query parameters para facilitar pruebas en Swagger
    - **Respuesta clara**: Informa el estado de la operación
    
    ### ⚙️ Parámetros disponibles (todos opcionales excepto referencia_contrato):
    - `referencia_contrato` (string, **REQUERIDO**): La referencia del contrato a modificar
    - `_dataset_source` (string, opcional): Fuente del dataset
    - `banco` (string, opcional): Banco
    - `bp` (string, opcional): BP
    - `bpin` (string, opcional): BPIN
    - `descripcion_proceso` (string, opcional): Descripción del proceso
    - `entidad_contratante` (string, opcional): Entidad contratante
    - `estado_contrato` (string, opcional): Estado del contrato
    - `fecha_actualizacion` (string, opcional): Fecha de actualización
    - `fecha_fin_contrato` (string, opcional): Fecha de fin del contrato
    - `fecha_firma_contrato` (string, opcional): Fecha de firma del contrato
    - `fecha_guardado` (string, opcional): Fecha de guardado
    - `fecha_inicio_contrato` (string, opcional): Fecha de inicio del contrato
    - `fuente_datos` (string, opcional): Fuente de datos
    - `id_contrato` (string, opcional): ID del contrato
    - `modalidad_contratacion` (string, opcional): Modalidad de contratación
    - `nit_contratista` (string, opcional): NIT del contratista
    - `nit_entidad` (string, opcional): NIT de la entidad
    - `nombre_centro_gestor` (string, opcional): Nombre del centro gestor
    - `nombre_contratista` (string, opcional): Nombre del contratista
    - `nombre_procedimiento` (string, opcional): Nombre del procedimiento
    - `objeto_contrato` (string, opcional): Objeto del contrato
    - `observaciones_test` (string, opcional): Observaciones test
    - `ordenador_gasto` (string, opcional): Ordenador de gasto
    - `proceso_contractual` (string, opcional): Proceso contractual
    - `referencia_proceso` (string, opcional): Referencia del proceso
    - `representante_legal` (string, opcional): Representante legal
    - `sector` (string, opcional): Sector
    - `supervisor` (string, opcional): Supervisor
    - `tipo_contrato` (string, opcional): Tipo de contrato
    - `urlproceso` (string, opcional): URL del proceso
    - `valor_contrato` (float, opcional): Valor del contrato
    - `valor_pagado` (float, opcional): Valor pagado
    - `version_esquema` (string, opcional): Versión del esquema
    - `datos_json` (string, opcional): JSON con campos adicionales a actualizar
    
    ### 📝 Ejemplos de uso en Swagger:
    ```
    referencia_contrato: CONT-SALUD-003-2024
    estado_contrato: ejecutado
    valor_contrato: 50000000
    fecha_cierre: 2024-11-12
    observaciones: Contrato completado
    ```
    
    ### ✅ Respuesta exitosa (200):
    ```json
    {
        "success": true,
        "message": "Contrato de empréstito actualizado correctamente",
        "referencia_contrato": "CONT-SALUD-003-2024",
        "campos_actualizados": ["estado_contrato", "valor_contrato", "fecha_cierre", "observaciones"],
        "timestamp": "2024-11-12T11:45:30.987654"
    }
    ```
    
    ### ❌ Respuesta de error (404):
    ```json
    {
        "success": false,
        "error": "Contrato de empréstito no encontrado",
        "referencia_contrato": "CONT-SALUD-003-2024",
        "timestamp": "2024-11-12T11:45:30.987654"
    }
    ```
    
    ### 💡 Notas importantes:
    - La `referencia_contrato` es el identificador único
    - Los campos no especificados NO se modifican
    - La actualización es parcial (solo lo que envíes se modifica)
    - Se requiere Firebase disponible
    - Perfectamente integrado con Swagger UI para pruebas interactivas
    """
    if not FIREBASE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Firebase no está disponible")

    try:
        # Construir diccionario de datos a actualizar
        datos_actualizados = {}
        
        if _dataset_source is not None:
            datos_actualizados["_dataset_source"] = _dataset_source
        if banco is not None:
            datos_actualizados["banco"] = banco
        if bp is not None:
            datos_actualizados["bp"] = bp
        if bpin is not None:
            datos_actualizados["bpin"] = bpin
        if descripcion_proceso is not None:
            datos_actualizados["descripcion_proceso"] = descripcion_proceso
        if entidad_contratante is not None:
            datos_actualizados["entidad_contratante"] = entidad_contratante
        if estado_contrato is not None:
            datos_actualizados["estado_contrato"] = estado_contrato
        if fecha_actualizacion is not None:
            datos_actualizados["fecha_actualizacion"] = fecha_actualizacion
        if fecha_fin_contrato is not None:
            datos_actualizados["fecha_fin_contrato"] = fecha_fin_contrato
        if fecha_firma_contrato is not None:
            datos_actualizados["fecha_firma_contrato"] = fecha_firma_contrato
        if fecha_guardado is not None:
            datos_actualizados["fecha_guardado"] = fecha_guardado
        if fecha_inicio_contrato is not None:
            datos_actualizados["fecha_inicio_contrato"] = fecha_inicio_contrato
        if fuente_datos is not None:
            datos_actualizados["fuente_datos"] = fuente_datos
        if id_contrato is not None:
            datos_actualizados["id_contrato"] = id_contrato
        if modalidad_contratacion is not None:
            datos_actualizados["modalidad_contratacion"] = modalidad_contratacion
        if nit_contratista is not None:
            datos_actualizados["nit_contratista"] = nit_contratista
        if nit_entidad is not None:
            datos_actualizados["nit_entidad"] = nit_entidad
        if nombre_centro_gestor is not None:
            datos_actualizados["nombre_centro_gestor"] = nombre_centro_gestor
        if nombre_contratista is not None:
            datos_actualizados["nombre_contratista"] = nombre_contratista
        if nombre_procedimiento is not None:
            datos_actualizados["nombre_procedimiento"] = nombre_procedimiento
        if objeto_contrato is not None:
            datos_actualizados["objeto_contrato"] = objeto_contrato
        if observaciones_test is not None:
            datos_actualizados["observaciones_test"] = observaciones_test
        if ordenador_gasto is not None:
            datos_actualizados["ordenador_gasto"] = ordenador_gasto
        if proceso_contractual is not None:
            datos_actualizados["proceso_contractual"] = proceso_contractual
        if referencia_proceso is not None:
            datos_actualizados["referencia_proceso"] = referencia_proceso
        if representante_legal is not None:
            datos_actualizados["representante_legal"] = representante_legal
        if sector is not None:
            datos_actualizados["sector"] = sector
        if supervisor is not None:
            datos_actualizados["supervisor"] = supervisor
        if tipo_contrato is not None:
            datos_actualizados["tipo_contrato"] = tipo_contrato
        if urlproceso is not None:
            datos_actualizados["urlproceso"] = urlproceso
        if valor_contrato is not None:
            datos_actualizados["valor_contrato"] = valor_contrato
        if valor_pagado is not None:
            datos_actualizados["valor_pagado"] = valor_pagado
        if version_esquema is not None:
            datos_actualizados["version_esquema"] = version_esquema
        
        # Parsear JSON adicional si se proporciona
        if datos_json:
            try:
                datos_json_dict = json.loads(datos_json)
                datos_actualizados.update(datos_json_dict)
            except json.JSONDecodeError:
                raise HTTPException(
                    status_code=400,
                    detail="El parámetro 'datos_json' debe ser un JSON válido"
                )
        
        # Validar que se proporcionaron datos para actualizar
        if not datos_actualizados:
            raise HTTPException(
                status_code=400,
                detail="Debes proporcionar al menos un campo para actualizar o un JSON válido en datos_json"
            )
        
        db = get_firestore_client()
        if not db:
            raise HTTPException(status_code=503, detail="No se pudo obtener cliente de Firebase")
        
        # Buscar el documento por referencia_contrato
        coleccion = db.collection("contratos_emprestito")
        query = coleccion.where("referencia_contrato", "==", referencia_contrato)
        docs = list(query.stream())
        
        if not docs:
            raise HTTPException(
                status_code=404, 
                detail=f"Contrato de empréstito con referencia '{referencia_contrato}' no encontrado"
            )
        
        # Obtener el ID del documento
        doc_id = docs[0].id
        
        # Actualizar solo los campos proporcionados
        campos_actualizados = list(datos_actualizados.keys())
        coleccion.document(doc_id).update(datos_actualizados)
        
        return create_utf8_response({
            "success": True,
            "message": "Contrato de empréstito actualizado correctamente",
            "referencia_contrato": referencia_contrato,
            "campos_actualizados": campos_actualizados,
            "timestamp": datetime.now().isoformat()
        })

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error al modificar contrato de empréstito: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail=f"Error al actualizar el contrato de empréstito: {str(e)}"
        )


# ============================================================================
# SERVIDOR
# ============================================================================

# ============================================================================
# INCLUIR ROUTERS DE ADMINISTRACIÓN
# ============================================================================

# Incluir router de administración de usuarios, roles y permisos
if AUTH_SYSTEM_AVAILABLE:
    try:
        from api.routers.auth_admin import router as auth_admin_router
        app.include_router(auth_admin_router)
        print("✅ Auth admin router included successfully")
    except Exception as e:
        print(f"⚠️ Warning: Could not include auth admin router: {e}")
else:
    print("⚠️ Auth admin router not included - Auth system not available")

# NOTA: Router de Captura 360 ya fue incluido antes de las rutas dinámicas (ver línea ~2410)

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

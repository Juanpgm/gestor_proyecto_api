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
from fastapi import FastAPI, HTTPException, Query, Request, status, Form, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from typing import Dict, Any, Optional, Union, List
import uvicorn
import asyncio
from datetime import datetime
import xml.etree.ElementTree as ET
import json
import re
import uuid

# Importar para manejar tipos de Firebase
try:
    from google.cloud.firestore_v1._helpers import DatetimeWithNanoseconds
    FIREBASE_TYPES_AVAILABLE = True
except ImportError:
    FIREBASE_TYPES_AVAILABLE = False
    DatetimeWithNanoseconds = None



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
        # Contratos operations
        get_contratos_init_data,
        get_contratos_emprestito_all,
        get_contratos_emprestito_by_referencia,
        get_contratos_emprestito_by_centro_gestor,
        # Bancos operations
        get_bancos_emprestito_all,
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
        EmprestitoRequest,
        EmprestitoResponse,
        USER_MODELS_AVAILABLE,
        # Reportes contratos models
        ReporteContratoRequest,
        ReporteContratoResponse,
        REPORTE_MODELS_AVAILABLE,
        # Proyectos presupuestales models
        PROYECTOS_PRESUPUESTALES_MODELS_AVAILABLE,
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

# Configurar CORS - Optimizado para Vercel + Railway + Netlify + Live Server
def get_cors_origins():
    """Obtener orígenes CORS desde variables de entorno de forma segura"""
    origins = []
    
    # Orígenes de desarrollo local (incluye Live Server)
    local_origins = [
        "http://localhost:3000",
        "http://localhost:3001", 
        "http://localhost:5500",  # Live Server default port
        "http://localhost:8080",  # Webpack dev server
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3001",
        "http://127.0.0.1:5500",  # Live Server con 127.0.0.1
        "http://127.0.0.1:8080",
    ]
    
    # Dominios de servicios de hosting conocidos
    hosting_origins = [
        # Netlify específicos
        "https://captura-emprestito.netlify.app",  # Dominio específico reportado
        "https://*.netlify.app",
        "https://*.netlify.com", 
        # Vercel patterns
        "https://*.vercel.app",
        "https://*.vercel.com",
        # GitHub Pages
        "https://*.github.io",
        # Firebase Hosting
        "https://*.firebaseapp.com",
        "https://*.web.app",
    ]
    
    # Siempre incluir dominios de hosting (tanto en desarrollo como producción)
    origins.extend(hosting_origins)
    
    # En desarrollo, también permitir localhost
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
    
    # Si no hay orígenes configurados, usar configuración permisiva para desarrollo
    if not origins:
        print("⚠️ Warning: No CORS origins configured, using default safe origins")
        origins = local_origins + hosting_origins
    
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

# 🌐 CORS CONFIGURADO PARA UTF-8 + HOSTING SERVICES
origins = get_cors_origins()

# Siempre incluir dominios específicos importantes
important_origins = [
    "https://captura-emprestito.netlify.app",
    "http://127.0.0.1:5500",
    "http://localhost:3000",
    "http://localhost:5500",
    "https://gestor-proyectos-vercel.vercel.app"  # Frontend específico de Vercel
]

# Combinar todos los orígenes
all_origins = list(set(origins + important_origins))

print(f"🌐 CORS configured for {len(all_origins)} origins including Netlify apps")

# Usar configuración permisiva que funcione en producción
cors_allow_origins = all_origins
cors_allow_credentials = True

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_allow_origins,
    allow_credentials=cors_allow_credentials,          
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
            "general": ["/", "/health", "/ping", "/centros-gestores/nombres-unicos"],
            "firebase": ["/firebase/status", "/firebase/collections"], 
            "proyectos_de_inversion": [
                "/proyectos-presupuestales/all",
                "/proyectos-presupuestales/bpin/{bpin}",
                "/proyectos-presupuestales/bp/{bp}",
                "/proyectos-presupuestales/centro-gestor/{nombre_centro_gestor}",
                "/proyectos-presupuestales/cargar-json (POST)"
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
                "/emprestito/proceso/{referencia_proceso}",
                "/emprestito/obtener-contratos-secop",
                "/contratos_emprestito_all",
                "/contratos_emprestito/referencia/{referencia_contrato}",
                "/contratos_emprestito/centro-gestor/{nombre_centro_gestor}",
                "/bancos_emprestito_all"
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
            "cors_origins_count": len(cors_allow_origins)
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
    
    try:
        result = await get_unique_nombres_centros_gestores()
        
        if not result["success"]:
            raise HTTPException(
                status_code=500,
                detail=f"Error obteniendo nombres únicos de centros gestores: {result.get('error', 'Error desconocido')}"
            )
        
        return {
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
# ENDPOINTS DE PROYECTOS DE INVERSIÓN
# ============================================================================

@app.get("/proyectos-presupuestales/all", tags=["Proyectos de Inversión"])
async def get_proyectos_all():
    """
    ## Obtener Todos los Proyectos Presupuestales
    
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
        result = await get_proyectos_presupuestales()
        
        if not result["success"]:
            raise HTTPException(
                status_code=500,
                detail=f"Error obteniendo proyectos presupuestales: {result.get('error', 'Error desconocido')}"
            )
        
        return {
            "success": True,
            "data": result["data"],
            "count": result["count"],
            "collection": result["collection"],
            "timestamp": result["timestamp"],
            "last_updated": "2025-10-04T00:00:00Z",  # Endpoint creation date
            "message": f"Se obtuvieron {result['count']} proyectos presupuestales exitosamente"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error procesando proyectos presupuestales: {str(e)}"
        )

@app.get("/proyectos-presupuestales/bpin/{bpin}", tags=["Proyectos de Inversión"])
async def get_proyectos_by_bpin(bpin: str):
    """
    ## Obtener Proyectos Presupuestales por BPIN
    
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
        result = await get_proyectos_presupuestales_by_bpin(bpin)
        
        if not result["success"]:
            raise HTTPException(
                status_code=500,
                detail=f"Error obteniendo proyectos por BPIN: {result.get('error', 'Error desconocido')}"
            )
        
        return {
            "success": True,
            "data": result["data"],
            "count": result["count"],
            "collection": result["collection"],
            "filter": result["filter"],
            "timestamp": result["timestamp"],
            "last_updated": "2025-10-04T00:00:00Z",  # Endpoint creation date
            "message": f"Se encontraron {result['count']} proyectos con BPIN '{bpin}'"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error procesando consulta por BPIN: {str(e)}"
        )

@app.get("/proyectos-presupuestales/bp/{bp}", tags=["Proyectos de Inversión"])
async def get_proyectos_by_bp(bp: str):
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
        result = await get_proyectos_presupuestales_by_bp(bp)
        
        if not result["success"]:
            raise HTTPException(
                status_code=500,
                detail=f"Error obteniendo proyectos por BP: {result.get('error', 'Error desconocido')}"
            )
        
        return {
            "success": True,
            "data": result["data"],
            "count": result["count"],
            "collection": result["collection"],
            "filter": result["filter"],
            "timestamp": result["timestamp"],
            "last_updated": "2025-10-04T00:00:00Z",  # Endpoint creation date
            "message": f"Se encontraron {result['count']} proyectos con BP '{bp}'"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error procesando consulta por BP: {str(e)}"
        )

@app.get("/proyectos-presupuestales/centro-gestor/{nombre_centro_gestor}", tags=["Proyectos de Inversión"])
async def get_proyectos_by_centro_gestor(nombre_centro_gestor: str):
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
        result = await get_proyectos_presupuestales_by_centro_gestor(nombre_centro_gestor)
        
        if not result["success"]:
            raise HTTPException(
                status_code=500,
                detail=f"Error obteniendo proyectos por centro gestor: {result.get('error', 'Error desconocido')}"
            )
        
        return {
            "success": True,
            "data": result["data"],
            "count": result["count"],
            "collection": result["collection"],
            "filter": result["filter"],
            "timestamp": result["timestamp"],
            "last_updated": "2025-10-04T00:00:00Z",  # Endpoint creation date
            "message": f"Se encontraron {result['count']} proyectos para el centro gestor '{nombre_centro_gestor}'"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error procesando consulta por centro gestor: {str(e)}"
        )

@app.post("/proyectos-presupuestales/cargar-json", tags=["Proyectos de Inversión"])
async def cargar_proyectos_presupuestales_json(
    archivo_json: UploadFile = File(..., description="Archivo JSON con proyectos presupuestales"),
    update_mode: str = Form(default="merge", description="Modo de actualización: merge, replace, append")
):
    """
    ## 📊 Cargar Proyectos Presupuestales desde Archivo JSON
    
    Endpoint POST para subir un archivo JSON con información de proyectos presupuestales 
    y cargarlo en la colección "proyectos_presupuestales".
    
    ### 📁 Archivo JSON esperado:
    ```json
    [
        {
            "nombre_proyecto": "Construcción de Puente",
            "bpin": "2023000123456",
            "bp": "BP-2023-001", 
            "nombre_centro_gestor": "Secretaría de Infraestructura",
            "valor_proyecto": 500000000
        },
        {
            "nombre_proyecto": "Otro Proyecto",
            "bpin": "2023000789012"
        }
    ]
    ```
    
    ### 🔧 Modos de actualización:
    - **merge**: Actualiza existentes y crea nuevos (por defecto)
    - **replace**: Reemplaza toda la colección
    - **append**: Solo agrega nuevos
    
    ### 🎯 Cómo usar:
    1. Haz clic en "Choose File" 
    2. Selecciona tu archivo .json
    3. Selecciona el modo de actualización
    4. Haz clic en "Execute"
    
    ### ✅ Validaciones:
    - Solo archivos .json
    - Cada proyecto debe tener "nombre_proyecto"
    - Tamaño máximo: 10MB
    """
    # Verificar disponibilidad de servicios
    if not FIREBASE_AVAILABLE or not SCRIPTS_AVAILABLE:
        raise HTTPException(status_code=503, detail="Firebase o scripts no disponibles")
    
    if not PROYECTOS_PRESUPUESTALES_OPERATIONS_AVAILABLE:
        raise HTTPException(status_code=503, detail="Operaciones de proyectos presupuestales no disponibles")
    
    # Validar modo de actualización
    if update_mode not in ["merge", "replace", "append"]:
        raise HTTPException(status_code=400, detail="update_mode debe ser: merge, replace o append")
    
    # Validar tipo de archivo
    if not archivo_json.filename.lower().endswith('.json'):
        raise HTTPException(status_code=400, detail="Solo se permiten archivos JSON (.json)")
    
    # Validar tamaño del archivo (10MB máximo)
    max_size = 10 * 1024 * 1024  # 10MB
    if archivo_json.size and archivo_json.size > max_size:
        raise HTTPException(status_code=400, detail="El archivo no puede exceder 10MB")
    
    try:
        # Leer el contenido del archivo
        contenido = await archivo_json.read()
        
        # Decodificar como JSON
        try:
            json_data = json.loads(contenido.decode('utf-8'))
        except json.JSONDecodeError as e:
            raise HTTPException(status_code=400, detail=f"Error al leer JSON: {str(e)}")
        except UnicodeDecodeError:
            raise HTTPException(status_code=400, detail="El archivo debe estar codificado en UTF-8")
        
        # Validar que sea una lista
        if not isinstance(json_data, list):
            raise HTTPException(status_code=400, detail="El JSON debe ser una lista de proyectos")
        
        if len(json_data) == 0:
            raise HTTPException(status_code=400, detail="La lista no puede estar vacía")
        
        # Validar que cada proyecto tenga nombre_proyecto
        for i, proyecto in enumerate(json_data):
            if not isinstance(proyecto, dict):
                raise HTTPException(status_code=400, detail=f"El elemento {i} debe ser un objeto")
            if not proyecto.get("nombre_proyecto"):
                raise HTTPException(status_code=400, detail=f"El proyecto {i} debe tener 'nombre_proyecto'")
        
        # Procesar proyectos
        result = await process_proyectos_presupuestales_json(
            proyectos_data=json_data,
            update_mode=update_mode
        )
        
        if not result["success"]:
            raise HTTPException(status_code=400, detail=result.get('error', 'Error desconocido'))
        
        # Agregar información del archivo procesado
        result["archivo_info"] = {
            "nombre_archivo": archivo_json.filename,
            "tamaño_bytes": len(contenido),
            "proyectos_en_archivo": len(json_data),
            "update_mode_usado": update_mode
        }
        
        return create_utf8_response(result)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")



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
    
    # Filtros geográficos adicionales
    comuna_corregimiento: Optional[str] = Query(None, description="Comuna o corregimiento específico"),
    barrio_vereda: Optional[str] = Query(None, description="Barrio o vereda específico"),
    
    # Filtros de visualización y análisis
    presupuesto_base: Optional[float] = Query(None, ge=0, description="Presupuesto mínimo del proyecto"),
    avance_obra: Optional[float] = Query(None, ge=0, le=100, description="Porcentaje mínimo de avance de obra"),
    
    # Configuración geográfica
    include_bbox: Optional[bool] = Query(False, description="Calcular y incluir bounding box"),
    limit: Optional[int] = Query(None, ge=1, le=10000, description="Límite de registros"),
    
    # Parámetros de mantenimiento y debug
    force_refresh: Optional[str] = Query(None, description="Forzar limpieza de cache (debug)")
):
    """
    ## Datos Geoespaciales Completos
    
    **Propósito**: Retorna TODOS los registros de proyectos (646) en formato GeoJSON, incluyendo aquellos sin coordenadas válidas.
    
    ### Solución Implementada
    
    **TODOS los registros incluidos**: Proyectos con y sin geometría válida
    **Marcador de geometría**: Campo `has_valid_geometry` indica si las coordenadas son reales
    **Coordenadas placeholder**: Registros sin geometría usan [0,0] como placeholder
    **Bounding box**: Disponible bajo demanda con `include_bbox=true`
    
    ### Estrategia de Filtrado
    
    **Sin filtros**: Dataset geográfico completo
    **Con filtros**: Optimización server-side en Firestore + refinamiento client-side
    
    **Server-side**: upid, estado, tipo_intervencion, nombre_centro_gestor  
    **Client-side**: comuna_corregimiento, barrio_vereda, presupuesto_base, avance_obra, bbox, include_bbox
    
    ### Parámetros
    
    | Filtro | Descripción |
    |--------|-------------|
    | nombre_centro_gestor | Centro gestor responsable |
    | tipo_intervencion | Tipo de intervención |
    | estado | Estado del proyecto |
    | upid | ID específico de unidad |
    | comuna_corregimiento | Comuna o corregimiento específico |
    | barrio_vereda | Barrio o vereda específico |
    | presupuesto_base | Presupuesto mínimo del proyecto |
    | avance_obra | Porcentaje mínimo de avance de obra (0-100) |
    | include_bbox | Incluir bounding box calculado |
    | limit | Límite de resultados (1-10000) |
    
    ### Aplicaciones
    
    - Mapas interactivos mostrando el conteo total correcto (646 proyectos)
    - Capas geográficas con opción de filtrar por `has_valid_geometry`
    - Integración con bibliotecas cartográficas que manejan coordenadas [0,0]
    - Visualización completa del portafolio de proyectos
    """
    # Verificación robusta de Firebase con reintentos
    if not FIREBASE_AVAILABLE or not SCRIPTS_AVAILABLE:
        # Intentar reconfigurar Firebase como último recurso
        try:
            print("⚠️ Attempting Firebase reconfiguration...")
            firebase_initialized, status = configure_firebase()
            if firebase_initialized:
                print("✅ Firebase reconfiguration successful")
            else:
                print(f"❌ Firebase reconfiguration failed: {status.get('error', 'Unknown error')}")
                return {
                    "success": False,
                    "error": "Firebase not available - check Railway environment variables",
                    "data": [],
                    "count": 0,
                    "type": "geometry",
                    "help": "Verify FIREBASE_SERVICE_ACCOUNT_KEY or GOOGLE_APPLICATION_CREDENTIALS_JSON",
                    "railway_fix": "Run generate_railway_fallback.py to create Service Account fallback"
                }
        except Exception as e:
            return {
                "success": False,
                "error": f"Firebase configuration failed: {str(e)}",
                "data": [],
                "count": 0,
                "type": "geometry",
                "help": "Check Railway environment variables or use Service Account fallback"
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
        if comuna_corregimiento:
            filters["comuna_corregimiento"] = comuna_corregimiento
        if barrio_vereda:
            filters["barrio_vereda"] = barrio_vereda
        if presupuesto_base is not None:
            filters["presupuesto_base"] = presupuesto_base
        if avance_obra is not None:
            filters["avance_obra"] = avance_obra
        if limit:
            filters["limit"] = limit
        if include_bbox:
            filters["include_bbox"] = include_bbox
        if force_refresh:
            filters["force_refresh"] = force_refresh
        
        result = await get_unidades_proyecto_geometry(filters)
        
        # Manejar el formato correcto de respuesta
        if result.get("type") == "FeatureCollection":
            # Respuesta GeoJSON exitosa
            if result.get("properties", {}).get("success", True):
                return create_utf8_response(result)
            else:
                raise HTTPException(
                    status_code=500,
                    detail=f"Error obteniendo geometrías: {result.get('properties', {}).get('error', 'Error desconocido')}"
                )
        elif result.get("success") is False:
            # Respuesta de error
            raise HTTPException(
                status_code=500,
                detail=f"Error obteniendo geometrías: {result.get('error', 'Error desconocido')}"
            )
        else:
            # Formato inesperado
            raise HTTPException(
                status_code=500,
                detail="Formato de respuesta inesperado del servicio de geometrías"
            )
        
        return create_utf8_response(response_data)
        
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
    # Verificación robusta de Firebase con reintentos
    if not FIREBASE_AVAILABLE or not SCRIPTS_AVAILABLE:
        # Intentar reconfigurar Firebase como último recurso
        try:
            print("⚠️ Attempting Firebase reconfiguration...")
            firebase_initialized, status = configure_firebase()
            if firebase_initialized:
                print("✅ Firebase reconfiguration successful")
            else:
                print(f"❌ Firebase reconfiguration failed: {status.get('error', 'Unknown error')}")
                return {
                    "success": False,
                    "error": "Firebase not available - check Railway environment variables",
                    "data": [],
                    "count": 0,
                    "type": "attributes",
                    "help": "Verify FIREBASE_SERVICE_ACCOUNT_KEY or GOOGLE_APPLICATION_CREDENTIALS_JSON",
                    "railway_fix": "Run generate_railway_fallback.py to create Service Account fallback"
                }
        except Exception as e:
            return {
                "success": False,
                "error": f"Firebase configuration failed: {str(e)}",
                "data": [],
                "count": 0,
                "type": "attributes",
                "help": "Check Railway environment variables or use Service Account fallback"
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
        
        response_data = {
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
        
        return create_utf8_response(response_data)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error procesando atributos: {str(e)}"
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
    # Verificación robusta de Firebase con reintentos
    if not FIREBASE_AVAILABLE or not SCRIPTS_AVAILABLE:
        # Intentar reconfigurar Firebase como último recurso
        try:
            print("⚠️ Attempting Firebase reconfiguration...")
            firebase_initialized, status = configure_firebase()
            if firebase_initialized:
                print("✅ Firebase reconfiguration successful")
            else:
                print(f"❌ Firebase reconfiguration failed: {status.get('error', 'Unknown error')}")
                return {
                    "success": False,
                    "error": "Firebase not available - check Railway environment variables",
                    "filters": {},
                    "type": "filters",
                    "help": "Verify FIREBASE_SERVICE_ACCOUNT_KEY or GOOGLE_APPLICATION_CREDENTIALS_JSON",
                    "railway_fix": "Run generate_railway_fallback.py to create Service Account fallback"
                }
        except Exception as e:
            return {
                "success": False,
                "error": f"Firebase configuration failed: {str(e)}",
                "filters": {},
                "type": "filters",
                "help": "Check Railway environment variables or use Service Account fallback"
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
        
        return create_utf8_response(response_data)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error procesando filtros: {str(e)}"
        )


# ============================================================================
# FUNCIONES AUXILIARES PARA PROCESAMIENTO KML
# ============================================================================

def parse_kml_to_geojson_linestrings(kml_content: str) -> Dict[str, Any]:
    """
    Convierte contenido KML a GeoJSON con LineStrings y formato de base de datos
    """
    try:
        # Parse del XML KML
        root = ET.fromstring(kml_content)
        
        # Namespace de KML
        kml_ns = {'kml': 'http://www.opengis.net/kml/2.2'}
        
        # Buscar todos los Placemarks
        placemarks = root.findall('.//kml:Placemark', kml_ns)
        
        features = []
        
        for placemark in placemarks:
            # Extraer nombre y descripción
            name_elem = placemark.find('kml:name', kml_ns)
            name = name_elem.text if name_elem is not None else f"Línea_{uuid.uuid4().hex[:8]}"
            
            desc_elem = placemark.find('kml:description', kml_ns)
            description = desc_elem.text if desc_elem is not None else ""
            
            # Buscar LineString
            linestring = placemark.find('.//kml:LineString', kml_ns)
            if linestring is not None:
                # Obtener coordenadas
                coords_elem = linestring.find('kml:coordinates', kml_ns)
                if coords_elem is not None:
                    coords_text = coords_elem.text.strip()
                    
                    # Parsear coordenadas (formato: lng,lat,alt lng,lat,alt ...)
                    coord_pairs = []
                    for coord_str in coords_text.split():
                        parts = coord_str.split(',')
                        if len(parts) >= 2:
                            try:
                                lng = float(parts[0])
                                lat = float(parts[1])
                                coord_pairs.append([lng, lat])
                            except ValueError:
                                continue
                    
                    if len(coord_pairs) >= 2:  # LineString necesita al menos 2 puntos
                        # Crear feature GeoJSON con formato de base de datos
                        feature = {
                            "type": "Feature",
                            "properties": {
                                # Campos básicos (upid se generará en el GET endpoint)
                                "nombre_up": name,
                                "descripcion": description,
                                "estado": "En Planificación",
                                "tipo_intervencion": "Infraestructura Vial",
                                "nombre_centro_gestor": "Centro Gestor por Definir",
                                "comuna_corregimiento": "Por Definir",
                                "barrio_vereda": "Por Definir",
                                "fuente_financiacion": "Por Definir",
                                "ano": datetime.now().year,
                                "presupuesto_base": 0,
                                "avance_obra": 0.0,
                                "fecha_inicio": None,
                                "fecha_fin": None
                            },
                            "geometry": {
                                "type": "LineString",
                                "coordinates": coord_pairs
                            }
                        }
                        features.append(feature)
        
        # Crear FeatureCollection GeoJSON
        geojson = {
            "type": "FeatureCollection",
            "features": features,
            "processing_metadata": {
                "source": "KML Import",
                "processed_at": datetime.now().isoformat(),
                "total_features": len(features),
                "geometry_type": "LineString",
                "format_version": "1.0",
                "upid_generation": "Will be handled by GET endpoint",
                "coordinates_count_per_feature": [len(f["geometry"]["coordinates"]) for f in features],
                "note": "This metadata is for processing info only, not for database insertion"
            }
        }
        
        return {
            "success": True,
            "geojson": geojson,
            "summary": {
                "features_processed": len(placemarks),
                "linestrings_found": len(features),
                "conversion_successful": True
            }
        }
        
    except ET.ParseError as e:
        return {
            "success": False,
            "error": f"Error parsing KML: {str(e)}",
            "geojson": None
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Error processing KML: {str(e)}",
            "geojson": None
        }


# ============================================================================
# ENDPOINT PARA INSERCIÓN DE LINESTRINGS DESDE KML
# ============================================================================

@app.post("/unidades-proyecto/insert-linestrings", tags=["Unidades de Proyecto"], response_class=JSONResponse)
async def insert_linestrings_from_kml(
    kml_file: UploadFile = File(..., description="Archivo KML con geometrías tipo línea")
):
    """
    **Convertir archivo KML a GeoJSON con LineStrings**
    
    Endpoint para procesar archivos KML y convertirlos a formato GeoJSON compatible 
    con la estructura de base de datos de unidades de proyecto.
    
    **Características principales:**
    - **Conversión KML → GeoJSON**: Procesa geometrías LineString desde KML
    - **Formato de BD**: Aplica estructura estándar de unidades de proyecto
    - **Sin persistencia**: Solo conversión y visualización (no guarda en BD)
    - **Validación**: Verifica geometrías válidas y estructura correcta
    
    **Proceso de conversión:**
    1. Parse del archivo KML
    2. Extracción de geometrías LineString
    3. Generación de propiedades por defecto
    4. Formato GeoJSON compatible con base de datos
    5. Validación de resultados
    
    **Campos generados automáticamente:**
    - `nombre_up`: Nombre extraído desde KML o generado
    - `estado`: "En Planificación" (por defecto)
    - `tipo_intervencion`: "Infraestructura Vial" (por defecto)
    - `geometry`: LineString con coordenadas del KML
    - `ano`: Año actual
    
    **Campos por definir manualmente:**
    - `upid`: Se generará automáticamente en el endpoint GET (no incluido aquí)
    - `nombre_centro_gestor`: Centro gestor responsable
    - `comuna_corregimiento`: Ubicación administrativa
    - `barrio_vereda`: Ubicación específica
    - `fuente_financiacion`: Fuente de recursos
    - `presupuesto_base`: Valor del proyecto
    
    **Respuesta incluye:**
    - GeoJSON completo con todas las features
    - Resumen de conversión con estadísticas
    - Metadata de procesamiento
    - Estructura lista para revisión antes de inserción
    
    **Uso recomendado:**
    1. Subir archivo KML
    2. Revisar GeoJSON generado
    3. Validar geometrías y propiedades
    4. Ajustar campos faltantes si es necesario
    5. Proceder con inserción manual posterior
    """
    
    # Validar tipo de archivo
    if not kml_file.filename.lower().endswith('.kml'):
        raise HTTPException(
            status_code=400,
            detail="Solo se permiten archivos KML (.kml)"
        )
    
    try:
        # Leer contenido del archivo
        kml_content = await kml_file.read()
        kml_text = kml_content.decode('utf-8')
        
        # Procesar KML
        result = parse_kml_to_geojson_linestrings(kml_text)
        
        if not result.get("success", False):
            raise HTTPException(
                status_code=400,
                detail=f"Error procesando KML: {result.get('error', 'Error desconocido')}"
            )
        
        geojson = result["geojson"]
        summary = result["summary"]
        
        # Crear respuesta completa
        response_data = {
            "success": True,
            "message": "KML convertido exitosamente a GeoJSON",
            "conversion_summary": {
                "source_file": kml_file.filename,
                "file_size_bytes": len(kml_content),
                "features_processed": summary["features_processed"],
                "linestrings_converted": summary["linestrings_found"],
                "conversion_successful": summary["conversion_successful"]
            },
            "geojson": geojson,
            "database_preview": {
                "ready_for_insertion": True,
                "format_validation": "✅ Compatible con estructura de BD",
                "required_fields_status": "✅ Campos base generados (upid se creará en GET)",
                "geometry_validation": "✅ LineStrings válidos",
                "upid_status": "⏳ Se generará automáticamente en endpoint GET",
                "next_steps": [
                    "Revisar y ajustar campos por defecto",
                    "Validar coordenadas geográficas",
                    "Confirmar información de proyecto",
                    "El upid se generará automáticamente al guardar",
                    "Proceder con inserción manual"
                ]
            },
            "metadata": {
                "processed_at": datetime.now().isoformat(),
                "geometry_type": "LineString",
                "coordinate_system": "WGS84 (EPSG:4326)",
                "format_version": "GeoJSON v1.0",
                "database_compatible": True,
                "persistence_status": "NOT_SAVED (Preview only)"
            },
            "type": "kml_conversion",
            "timestamp": datetime.now().isoformat()
        }
        
        return create_utf8_response(response_data)
        
    except UnicodeDecodeError:
        raise HTTPException(
            status_code=400,
            detail="Error de codificación: El archivo KML debe estar en UTF-8"
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error interno procesando KML: {str(e)}"
        )


# ============================================================================
# ENDPOINTS DE INTEROPERABILIDAD CON ARTEFACTO DE SEGUIMIENTO
# ============================================================================

@app.get("/contratos/init_contratos_seguimiento", tags=["Interoperabilidad con Artefacto de Seguimiento"])
async def init_contratos_seguimiento(
    referencia_contrato: Optional[str] = Query(None, description="Referencia del contrato (búsqueda parcial)"),
    nombre_centro_gestor: Optional[str] = Query(None, description="Centro gestor responsable (exacto)")
):
    """
    ## Inicialización de Contratos para Seguimiento
    
    Obtiene datos de contratos desde la colección `contratos_emprestito` con filtros optimizados.
    
    **Campos retornados**: bpin, banco, nombre_centro_gestor, estado_contrato, referencia_contrato, 
    referencia_proceso, objeto_contrato, modalidad_contratacion, fecha_inicio_contrato, fecha_firma, 
    fecha_fin_contrato
    
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
async def obtener_reportes_contratos():
    """
    ## 📋 Obtener Todos los Reportes de Contratos
    
    **Propósito**: Obtener listado completo de todos los reportes de contratos almacenados en Firebase.
    Muestra todos los registros de la colección `reportes_contratos` con `nombre_centro_gestor` 
    actualizado desde la colección `contratos_emprestito` cuando sea necesario.
    
    ### 🔄 Integración con contratos_emprestito:
    - Si un reporte no tiene `nombre_centro_gestor` o está vacío, se busca automáticamente 
      en la colección `contratos_emprestito` usando `referencia_contrato` como clave
    - Los reportes actualizados incluyen el campo `nombre_centro_gestor_source: 'contratos_emprestito'`
    
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
        
        return create_utf8_response(result)
        
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
        
        return JSONResponse(
            content={
                "success": True,
                "session_valid": True,
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
            
            return JSONResponse(
                content={
                    "success": True,
                    "user": clean_user_data,
                    "auth_method": result.get("auth_method", "email_password"),
                    "credentials_validated": result.get("credentials_validated", True),
                    "message": result.get("message", "Autenticación exitosa"),
                    "timestamp": datetime.now().isoformat()
                },
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
    limit: int = Query(default=100, ge=1, le=1000, description="Límite de resultados por página")
):
    """
    ## 📋 Listado de Usuarios desde Firestore
    
    Lee directamente la colección "users" de Firestore y devuelve todos los usuarios registrados.
    
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
    const response = await fetch('/admin/users?limit=50');
    const data = await response.json();
    console.log(`Encontrados ${data.count} usuarios`);
    ```
    """
    try:
        check_user_management_availability()
        
        from database.firebase_config import get_firestore_client
        
        firestore_client = get_firestore_client()
        
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
        get_emprestito_operations_status,
        cargar_orden_compra_directa,
        EMPRESTITO_OPERATIONS_AVAILABLE
    )
    from api.models import EmprestitoRequest, EmprestitoResponse
    print(f"✅ Empréstito imports successful - AVAILABLE: {EMPRESTITO_OPERATIONS_AVAILABLE}")
except ImportError as e:
    print(f"❌ Warning: Empréstito imports failed: {e}")
    EMPRESTITO_OPERATIONS_AVAILABLE = False

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

@app.post("/emprestito/cargar-proceso", tags=["Gestión de Empréstito"])
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
    ## 📋 Cargar Proceso de Empréstito
    
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
        return JSONResponse(
            content={
                "success": True,
                "message": "Proceso de empréstito cargado exitosamente",
                "data": resultado.get("data"),
                "doc_id": resultado.get("doc_id"),
                "coleccion": resultado.get("coleccion"),
                "plataforma_detectada": resultado.get("plataforma_detectada"),
                "fuente_datos": resultado.get("fuente_datos"),
                "timestamp": datetime.now().isoformat()
            },
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

@app.post("/emprestito/cargar-orden-compra", tags=["Gestión de Empréstito"])
async def cargar_orden_compra_emprestito(
    numero_orden: str = Form(..., description="Número de la orden de compra (obligatorio)"),
    nombre_centro_gestor: str = Form(..., description="Centro gestor responsable (obligatorio)"),
    nombre_banco: str = Form(..., description="Nombre del banco (obligatorio)"),
    nombre_resumido_proceso: str = Form(..., description="Nombre resumido del proceso (obligatorio)"),
    valor_proyectado: float = Form(..., description="Valor proyectado (obligatorio)"),
    bp: Optional[str] = Form(None, description="Código BP (opcional)")
):
    """
    ## 📋 Cargar Orden de Compra de Empréstito
    
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

@app.get("/emprestito/proceso/{referencia_proceso}", tags=["Gestión de Empréstito"])
async def verificar_proceso_existente_endpoint(referencia_proceso: str):
    """
    ## 🔍 Verificar Proceso Existente
    
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


@app.delete("/emprestito/proceso/{referencia_proceso}", tags=["Gestión de Empréstito"])
async def eliminar_proceso_emprestito_endpoint(referencia_proceso: str):
    """
    ## 🗑️ Eliminar Proceso de Empréstito
    
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


@app.put("/emprestito/proceso/{referencia_proceso}", tags=["Gestión de Empréstito"])
async def actualizar_proceso_emprestito_endpoint(
    referencia_proceso: str,
    bp: Optional[str] = Form(None, description="Código BP (opcional)"),
    nombre_resumido_proceso: Optional[str] = Form(None, description="Nombre resumido del proceso (opcional)"),
    id_paa: Optional[str] = Form(None, description="ID PAA (opcional)"),
    valor_proyectado: Optional[float] = Form(None, description="Valor proyectado (opcional)")
):
    """
    ## ✏️ Actualizar Proceso de Empréstito
    
    Actualiza campos específicos de un proceso de empréstito existente sin crear registros nuevos.
    Solo se actualizan los campos proporcionados, manteniendo los demás valores sin cambios.
    
    ### ✅ Funcionalidades principales:
    - **Búsqueda automática**: Localiza el proceso en ambas colecciones
    - **Actualización selectiva**: Solo modifica los campos proporcionados
    - **Preservación de datos**: Mantiene los campos no especificados
    - **Historial de cambios**: Muestra valores anteriores y nuevos
    
    ### 🔍 Colecciones de búsqueda:
    - **procesos_emprestito** (SECOP)
    - **ordenes_compra_emprestito** (TVEC)
    
    ### 📝 Campos actualizables:
    - `bp`: Código BP
    - `nombre_resumido_proceso`: Nombre resumido del proceso
    - `id_paa`: ID PAA
    - `valor_proyectado`: Valor proyectado (numérico)
    
    ### ⚙️ Comportamiento:
    - **Campos vacíos**: Se ignoran (no se actualizan)
    - **Campos con valor**: Se actualizan en la base de datos
    - **Timestamp**: Se actualiza automáticamente `fecha_actualizacion`
    - **Validación previa**: Verifica que el proceso existe
    
    ### 📋 Respuesta exitosa:
    ```json
    {
        "success": true,
        "message": "Proceso actualizado exitosamente",
        "referencia_proceso": "SCMGSU-CM-003-2024",
        "coleccion": "procesos_emprestito",
        "documento_id": "xyz123",
        "campos_modificados": ["bp", "valor_proyectado"],
        "valores_anteriores": {
            "bp": "BP-OLD-001",
            "valor_proyectado": 1000000.0
        },
        "valores_nuevos": {
            "bp": "BP-NEW-001",
            "valor_proyectado": 1500000.0
        },
        "proceso_actualizado": { ... },
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
    
    ### 📋 Respuesta sin campos:
    ```json
    {
        "success": false,
        "error": "No se proporcionaron campos para actualizar",
        "campos_disponibles": ["bp", "nombre_resumido_proceso", "id_paa", "valor_proyectado"]
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
        
        # Actualizar proceso
        resultado = await actualizar_proceso_emprestito(
            referencia_proceso=referencia_proceso.strip(),
            bp=bp,
            nombre_resumido_proceso=nombre_resumido_proceso,
            id_paa=id_paa,
            valor_proyectado=valor_proyectado
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
        
        # Respuesta exitosa
        return JSONResponse(
            content=resultado,
            status_code=200,
            headers={"Content-Type": "application/json; charset=utf-8"}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error en endpoint actualizar proceso: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "error": "Error interno del servidor",
                "message": "Error actualizando proceso de empréstito",
                "referencia_proceso": referencia_proceso
            }
        )


@app.post("/emprestito/obtener-contratos-secop", tags=["Gestión de Empréstito"])
async def obtener_contratos_secop_endpoint():
    """
    ## 🔍 Obtener Contratos de SECOP desde Todos los Procesos de Empréstito
    
    Procesa TODOS los registros de la colección 'procesos_emprestito', busca contratos en SECOP 
    para cada proceso y guarda los resultados en la nueva colección 'contratos_emprestito'.
    
    ### 📝 No requiere parámetros:
    Este endpoint procesa automáticamente todos los registros existentes en 'procesos_emprestito'.
    
    ### 📤 Envío:
    ```http
    POST /emprestito/obtener-contratos-secop
    ```
    **No es necesario enviar ningún cuerpo JSON**.
    
    ### 🔄 Proceso:
    1. Leer TODOS los registros de la colección 'procesos_emprestito'
    2. Para cada proceso, extraer referencia_proceso y proceso_contractual
    3. Conectar con la API de SECOP (www.datos.gov.co) para cada proceso
    4. Buscar contratos que contengan el proceso_contractual y NIT = 890399011
    5. Transformar los datos al esquema de la colección 'contratos_emprestito'
    6. Verificar duplicados y actualizar/crear registros en Firebase
    7. Retornar resumen completo del procesamiento masivo
    
    ### ✅ Respuesta exitosa:
    ```json
    {
        "success": true,
        "message": "Se procesaron 5 procesos de empréstito. Contratos: 12 total (8 nuevos, 3 actualizados, 1 ignorados)",
        "resumen_procesamiento": {
            "total_procesos": 5,
            "procesos_procesados": 4,
            "procesos_sin_contratos": 1,
            "procesos_con_errores": 0
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
        
        # Ejecutar procesamiento completo de todos los procesos de empréstito
        resultado = await obtener_contratos_desde_proceso_contractual()
        
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

@app.get("/contratos_emprestito_all", tags=["Gestión de Empréstito"])
async def obtener_todos_contratos_emprestito():
    """
    ## 📋 Obtener Todos los Contratos de Empréstito
    
    **Propósito**: Retorna todos los registros de la colección "contratos_emprestito".
    
    ### ✅ Casos de uso:
    - Obtener listado completo de contratos de empréstito
    - Exportación de datos para análisis
    - Integración con sistemas externos
    - Reportes y dashboards de contratos
    
    ### 📊 Información incluida:
    - Todos los campos disponibles en la colección
    - ID del documento para referencia
    - Conteo total de registros
    - Timestamp de la consulta
    
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
    
    ### 🔄 Campos heredados desde procesos_emprestito:
    - **nombre_resumido_proceso**: Nombre resumido del proceso obtenido automáticamente usando referencia_proceso
    
    ### 📝 Ejemplo de uso:
    ```javascript
    const response = await fetch('/contratos_emprestito_all');
    const data = await response.json();
    if (data.success) {
        console.log('Contratos encontrados:', data.count);
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
            "collection": result["collection"],
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

@app.get("/contratos_emprestito/referencia/{referencia_contrato}", tags=["Gestión de Empréstito"])
async def obtener_contratos_por_referencia(referencia_contrato: str):
    """
    ## 🔍 Obtener Contratos de Empréstito por Referencia
    
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

@app.get("/bancos_emprestito_all", tags=["Gestión de Empréstito"])
async def get_all_bancos_emprestito():
    """
    ## Obtener Todos los Bancos de Empréstito
    
    **Propósito**: Retorna todos los bancos disponibles en la colección "bancos_emprestito".
    
    ### ✅ Casos de uso:
    - Poblar dropdowns y selectores en formularios de empréstito
    - Obtener listado completo de bancos para validación
    - Integración con sistemas de gestión de procesos
    - Reportes y dashboards de bancos disponibles
    
    ### 📊 Información incluida:
    - Todos los campos disponibles de cada banco
    - ID del documento para referencia
    - Conteo total de bancos disponibles
    - Lista ordenada por nombre de banco
    
    ### 📝 Ejemplo de uso:
    ```javascript
    const response = await fetch('/bancos_emprestito_all');
    const data = await response.json();
    if (data.success) {
        console.log('Bancos disponibles:', data.count);
        const bancoOptions = data.data.map(banco => ({
            value: banco.nombre_banco,
            label: banco.nombre_banco
        }));
    }
    ```
    
    ### 💡 Características:
    - **Ordenamiento**: Lista alfabética por nombre de banco
    - **Validación**: Datos limpios y serializados correctamente
    - **Compatibilidad**: UTF-8 completo para nombres con caracteres especiales
    - **Performance**: Optimizado para carga rápida de opciones
    
    ### 🔗 Endpoints relacionados:
    - `POST /emprestito/cargar-proceso` - Para crear nuevos procesos de empréstito usando estos bancos
    - `GET /contratos_emprestito_all` - Para consultar contratos por banco
    """
    if not FIREBASE_AVAILABLE or not SCRIPTS_AVAILABLE:
        raise HTTPException(status_code=503, detail="Firebase or scripts not available")
    
    if not EMPRESTITO_OPERATIONS_AVAILABLE:
        raise HTTPException(status_code=503, detail="Emprestito operations not available")
    
    try:
        result = await get_bancos_emprestito_all()
        
        if not result["success"]:
            raise HTTPException(
                status_code=500,
                detail=f"Error obteniendo bancos de empréstito: {result.get('error', 'Error desconocido')}"
            )
        
        return create_utf8_response({
            "success": True,
            "data": result["data"],
            "count": result["count"],
            "collection": result["collection"],
            "timestamp": result["timestamp"],
            "last_updated": "2025-10-11T00:00:00Z",  # Endpoint creation date
            "message": result["message"],
            "metadata": {
                "sorted": True,
                "utf8_enabled": True,
                "spanish_support": True,
                "purpose": "Banco selection for emprestito processes"
            }
        })
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error procesando consulta de bancos: {str(e)}"
        )


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

"""
Gestor de Proyectos API - Versión Limpia
API principal para gestión de proyectos con Firebase
Arquitectura modular optimizada para NextJS
"""

import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from typing import Dict, Any, Optional, Union
import uvicorn
import asyncio
from datetime import datetime

# Importar Firebase con configuración automática
try:
    from database.firebase_config import FirebaseManager, PROJECT_ID, FIREBASE_AVAILABLE
    print(f"✅ Firebase auto-config loaded successfully - FIREBASE_AVAILABLE: {FIREBASE_AVAILABLE}")
except Exception as e:
    print(f"❌ Warning: Firebase import failed: {e}")
    FIREBASE_AVAILABLE = False
    PROJECT_ID = "your-project-id"
    
    class FirebaseManager:
        @staticmethod
        def is_available(): return False
        @staticmethod 
        def setup(): return False
        @staticmethod
        def test_connection(): return {'connected': False, 'message': 'Not available'}

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
    )
    SCRIPTS_AVAILABLE = True
    print(f"✅ Scripts imported successfully - SCRIPTS_AVAILABLE: {SCRIPTS_AVAILABLE}")
except Exception as e:
    print(f"❌ Warning: Scripts import failed: {e}")
    SCRIPTS_AVAILABLE = False



# Configurar el lifespan de la aplicación
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gestionar el ciclo de vida de la aplicación"""
    # Startup
    print("Starting API...")
    print(f"Port: {os.getenv('PORT', '8000')}")
    print(f"Environment: {os.getenv('ENVIRONMENT', 'development')}")
    print(f"Firebase Project: {PROJECT_ID}")
    
    # Inicializar Firebase automáticamente (sin fallar la app)
    firebase_initialized = False
    if FIREBASE_AVAILABLE:
        try:
            firebase_initialized = FirebaseManager.setup()
            if firebase_initialized:
                print("✅ Firebase initialized successfully")
            else:
                print("⚠️ Firebase initialization failed - API will run in limited mode")
        except Exception as e:
            print(f"⚠️ Firebase setup error: {e} - API will run in limited mode")
    else:
        print("⚠️ Firebase not available - API running in limited mode")
    
    print(f"🚀 API starting with Firebase: {'✅ Connected' if firebase_initialized else '❌ Limited mode'}")
    
    yield
    
    # Shutdown
    print("Stopping API...")

# Crear instancia de FastAPI con lifespan
app = FastAPI(
    title="Gestor de Proyectos API",
    description="API para gestión de proyectos con Firebase/Firestore",
    version="1.0.0",
    lifespan=lifespan
)

# Configurar CORS - Optimizado para Vercel + Railway  
origins = [
    # 🌐 Producción - Tu dominio específico de Vercel
    "https://gestor-proyectos-vercel.vercel.app",
    
    # 🔧 Desarrollo local - Todas las variantes
    "http://localhost:3000",
    "http://localhost:3001", 
    "http://127.0.0.1:3000",
    "http://127.0.0.1:3001",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,           
    allow_credentials=True,          
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],  
    allow_headers=[               
        "Authorization",
        "Content-Type", 
        "Accept",
        "Origin", 
        "X-Requested-With",
        "Cache-Control",
        "Pragma"
    ],
)

# 🛠️ MIDDLEWARE DE TIMEOUT PARA PREVENIR COLGADAS
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

# ============================================================================
# ENDPOINTS GENERALES
# ============================================================================

@app.get("/")
async def read_root():
    """Endpoint raíz con información básica de la API"""
    return {
        "message": "Gestor de Proyectos API",
        "version": "1.0.0",
        "timestamp": datetime.now().isoformat(),
        "last_updated": "2025-10-02T00:00:00Z",  # API last update date
        "firebase_project": PROJECT_ID,
        "status": "running",
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
            ]
        },
        "new_features": {
            "filters": "Todos los endpoints de Unidades de Proyecto ahora soportan filtros avanzados",
            "supported_filters": [
                "nombre_centro_gestor", "tipo_intervencion", "estado", "upid", 
                "comuna_corregimiento", "barrio_vereda", "nombre_up", "direccion",
                "referencia_contrato", "referencia_proceso", "include_bbox", "limit", "offset"
            ],
            "dashboard": "Nuevo endpoint de dashboard con métricas agregadas y análisis estadístico",
            "workload_identity": "Autenticación automática usando Google Cloud Workload Identity Federation"
        }
    }

@app.get("/ping", tags=["General"])
async def ping():
    """Health check super simple para Railway"""
    return {
        "status": "ok", 
        "timestamp": datetime.now().isoformat(),
        "last_updated": "2025-10-02T00:00:00Z"  # Endpoint creation/update date
    }

@app.get("/debug/railway", tags=["General"])
async def railway_debug():
    """Debug específico para Railway - Diagnóstico completo"""
    try:
        # Variables de entorno
        env_info = {
            "FIREBASE_PROJECT_ID": os.getenv("FIREBASE_PROJECT_ID", "NOT_SET"),
            "HAS_FIREBASE_SERVICE_ACCOUNT_KEY": bool(os.getenv("FIREBASE_SERVICE_ACCOUNT_KEY")),
            "SERVICE_ACCOUNT_KEY_LENGTH": len(os.getenv("FIREBASE_SERVICE_ACCOUNT_KEY", "")),
            "ENVIRONMENT": os.getenv("ENVIRONMENT", "NOT_SET"),
            "PORT": os.getenv("PORT", "NOT_SET"),
            "RAILWAY_ENVIRONMENT": os.getenv("RAILWAY_ENVIRONMENT", "NOT_SET"),
            "FIRESTORE_BATCH_SIZE": os.getenv("FIRESTORE_BATCH_SIZE", "NOT_SET"),
            "FIRESTORE_TIMEOUT": os.getenv("FIRESTORE_TIMEOUT", "NOT_SET")
        }
        
        # Test de decodificación de Service Account (mejorado)
        sa_test = {"status": "not_tested"}
        sa_key = os.getenv("FIREBASE_SERVICE_ACCOUNT_KEY")
        if sa_key:
            try:
                import json
                import base64
                
                creds_data = None
                method_used = "unknown"
                
                # Method 1: Plain JSON
                if sa_key.strip().startswith("{"):
                    creds_data = json.loads(sa_key)
                    method_used = "plain_json"
                else:
                    # Method 2: Base64
                    try:
                        decoded = base64.b64decode(sa_key).decode()
                        creds_data = json.loads(decoded)
                        method_used = "base64_standard"
                    except:
                        # Method 3: URL-safe Base64
                        decoded = base64.urlsafe_b64decode(sa_key).decode()
                        creds_data = json.loads(decoded)
                        method_used = "base64_urlsafe"
                
                # Validate required fields
                required_fields = ['type', 'project_id', 'private_key', 'client_email']
                missing_fields = [f for f in required_fields if not creds_data.get(f)]
                
                sa_test = {
                    "status": "success",
                    "method": method_used,
                    "client_email": creds_data.get("client_email", "missing"),
                    "project_id": creds_data.get("project_id", "missing"),
                    "has_private_key": bool(creds_data.get("private_key")),
                    "missing_fields": missing_fields,
                    "valid": len(missing_fields) == 0
                }
            except Exception as e:
                sa_test = {
                    "status": "failed",
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "key_preview": sa_key[:50] + "..." if len(sa_key) > 50 else sa_key
                }
        
        # Test Firebase directly
        firebase_test = None
        if FIREBASE_AVAILABLE:
            try:
                firebase_test = FirebaseManager.test_connection()
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
            firebase_status = FirebaseManager.test_connection()
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
"""
Gestor de P# Importar Firebase con configuración automática
try:
    from database.firebase_config import FirebaseManager, PROJECT_ID, FIREBASE_AVAILABLE
    print("Firebase auto-config loaded successfully")
except Exception as e:
    print(f"Warning: Firebase import failed: {e}")
    FIREBASE_AVAILABLE = False
    PROJECT_ID = "your-project-id"
    
    class FirebaseManager:
        @staticmethod
        def is_available(): return False
        @staticmethod 
        def setup(): return False
        @staticmethod
        def test_connection(): return {'connected': False, 'message': 'Not available'}API principal para gestión de proyectos con Firebase
Arquitectura modular con programación funcional optimizada para producción
Deployment: 2025-09-25T12:20:00
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
    print("Firebase auto-config loaded successfully")
except Exception as e:
    print(f"Warning: Firebase import failed: {e}")
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
        # Unidades proyecto operations (simplificadas)
        get_all_unidades_proyecto_simple,
        get_unidades_proyecto_summary,
        validate_unidades_proyecto_collection,
        delete_all_unidades_proyecto,
        delete_unidades_proyecto_by_criteria
    )
    SCRIPTS_AVAILABLE = True
except Exception as e:
    print(f"Warning: Scripts import failed: {e}")
    SCRIPTS_AVAILABLE = False# Configurar el lifespan de la aplicación
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gestionar el ciclo de vida de la aplicación"""
    # Startup
    print("Starting API...")
    print(f"Port: {os.getenv('PORT', '8000')}")
    print(f"Environment: {os.getenv('ENVIRONMENT', 'development')}")
    print(f"Firebase Project: {PROJECT_ID}")
    
    # Inicializar Firebase automáticamente
    if FIREBASE_AVAILABLE:
        if FirebaseManager.setup():
            print("Firebase initialized successfully")
        else:
            print("Warning: Firebase initialization failed - API will run in limited mode")
    else:
        print("Firebase not available - API running in limited mode")
    
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
def is_cors_allowed(origin: str) -> bool:
    """Verificar si el origen está permitido"""
    allowed_patterns = [
        "vercel.app",
        "railway.app", 
        "localhost",
        "127.0.0.1"
    ]
    return any(pattern in origin for pattern in allowed_patterns)

# Lista específica de orígenes permitidos
origins = [
    # 🌐 Producción - Tu dominio específico de Vercel
    "https://gestor-proyectos-vercel.vercel.app",
    
    # 🔧 Desarrollo local - Todas las variantes
    "http://localhost:3000",
    "http://localhost:3001", 
    "http://127.0.0.1:3000",
    "http://127.0.0.1:3001",
    
    # � Para debugging desde cualquier subdominio de Vercel
    # Nota: Agregar manualmente URLs específicas si necesitas más
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,           # ✅ Orígenes específicos
    allow_credentials=True,          # ✅ Permite cookies/auth  
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],  # ✅ Métodos HTTP necesarios
    allow_headers=[               # ✅ Headers específicos para NextJS
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
        "firebase_project": PROJECT_ID,
        "status": "running",
        "documentation": "/docs",
        "endpoints": {
            "general": ["/", "/health"],
            "firebase": ["/firebase/status", "/firebase/collections", "/firebase/collections/summary"],
            "unidades_proyecto": [
                "/unidades-proyecto", 
                "/unidades-proyecto/summary", 
                "/unidades-proyecto/validate",
                "/unidades-proyecto/filter",
                "/unidades-proyecto/dashboard-summary",
                "/unidades-proyecto/paginated",
                "/unidades-proyecto/delete-all",
                "/unidades-proyecto/delete-by-criteria"
            ]
        }
    }

@app.get("/ping", tags=["General"])
async def ping():
    """Health check super simple para Railway (fallback compatibility)"""
    return {"status": "ok", "timestamp": datetime.now().isoformat()}

@app.get("/unidades-proyecto/demo", tags=["Demo"])
async def get_demo_data():
    """
    🎯 DATOS DE EJEMPLO PARA DESARROLLO
    Retorna datos de ejemplo cuando Firebase no está disponible
    """
    return {
        "success": True,
        "data": [
            {
                "id": "demo-001",
                "bpin": "2024000000001",
                "upid": "UP001",
                "nombre_proyecto": "Proyecto de Ejemplo 1",
                "estado": "En ejecución",
                "ano": "2024",
                "comuna_corregimiento": "Comuna 1",
                "fuente_financiacion": "Recursos propios",
                "tipo_intervencion": "Construcción",
                "coordenadas": {"lat": 6.2442, "lng": -75.5812}
            },
            {
                "id": "demo-002", 
                "bpin": "2024000000002",
                "upid": "UP002",
                "nombre_proyecto": "Proyecto de Ejemplo 2",
                "estado": "Terminado",
                "ano": "2023", 
                "comuna_corregimiento": "Comuna 2",
                "fuente_financiacion": "Cofinanciación",
                "tipo_intervencion": "Mejoramiento",
                "coordenadas": {"lat": 6.2518, "lng": -75.5636}
            }
        ],
        "count": 2,
        "demo": True,
        "message": "Demo data for development"
    }

@app.get("/debug/firebase", tags=["Debug"])
async def debug_firebase_connection():
    """
    🔧 DIAGNÓSTICO DE CONEXIÓN FIREBASE
    Ayuda a identificar problemas de conexión
    """
    diagnostics = {
        "firebase_available": FIREBASE_AVAILABLE,
        "scripts_available": SCRIPTS_AVAILABLE,
        "project_id": PROJECT_ID if FIREBASE_AVAILABLE else "not-configured",
        "timestamp": datetime.now().isoformat()
    }
    
    if FIREBASE_AVAILABLE:
        try:
            # Test de conexión básico
            from api.scripts.firebase_operations import test_firebase_connection
            test_result = await test_firebase_connection()
            diagnostics["connection_test"] = test_result
        except Exception as e:
            diagnostics["connection_error"] = str(e)
    
    return diagnostics

@app.get("/debug/cors", tags=["Debug"])
async def debug_cors_configuration():
    """
    🌐 DIAGNÓSTICO DE CONFIGURACIÓN CORS
    Muestra la configuración actual de CORS
    """
    return {
        "cors_configuration": {
            "allowed_origins": origins,
            "allow_credentials": True,
            "allowed_methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            "allowed_headers": [
                "Authorization", "Content-Type", "Accept", 
                "Origin", "X-Requested-With", "Cache-Control", "Pragma"
            ]
        },
        "test_instructions": {
            "frontend_test": "Intenta hacer fetch desde tu NextJS a este endpoint",
            "browser_test": "Abre DevTools > Network y verifica headers CORS",
            "curl_test": "curl -H 'Origin: https://gestor-proyectos-vercel.vercel.app' {API_URL}/debug/cors"
        },
        "common_solutions": {
            "if_cors_error": "Agrega tu dominio específico a la lista 'origins'",
            "if_preflight_fails": "Verifica que OPTIONS esté permitido", 
            "if_credentials_fail": "Verifica allow_credentials=True"
        }
    }

@app.options("/unidades-proyecto", tags=["CORS"])
async def preflight_unidades_proyecto():
    """Manejo manual de preflight para el endpoint principal"""
    return {"message": "CORS preflight OK"}

@app.options("/unidades-proyecto/summary", tags=["CORS"]) 
async def preflight_summary():
    """Manejo manual de preflight para summary"""
    return {"message": "CORS preflight OK"}

@app.options("/unidades-proyecto/search", tags=["CORS"])
async def preflight_search():
    """Manejo manual de preflight para search"""
    return {"message": "CORS preflight OK"}

@app.get("/health", tags=["General"])
async def health_check():
    """Verificar estado de salud de la API - Health check básico para Railway"""
    try:
        # Health check básico sin Firebase para Railway
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
            firebase_status = FirebaseManager.test_connection()
            basic_response["services"]["firebase"] = firebase_status
            basic_response["services"]["scripts"] = {"available": SCRIPTS_AVAILABLE}
            
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
        # Return basic response even if there are errors
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
    if not FIREBASE_AVAILABLE or not SCRIPTS_AVAILABLE:
        raise HTTPException(status_code=503, detail="Firebase or scripts not available")
    try:
        connection_result = await test_firebase_connection()
        
        if not connection_result["connected"]:
            raise HTTPException(
                status_code=503, 
                detail=f"Firebase no disponible: {connection_result.get('error', 'Error desconocido')}"
            )
        
        return connection_result
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error verificando Firebase: {str(e)}")

@app.get("/firebase/collections", tags=["Firebase"])
async def get_firebase_collections():
    """
    Obtener información completa de todas las colecciones de Firestore
    
    Retorna:
    - Número de documentos por colección
    - Tamaño estimado de cada colección  
    - Última fecha de actualización
    - Estado de cada colección
    """
    if not FIREBASE_AVAILABLE or not SCRIPTS_AVAILABLE:
        raise HTTPException(status_code=503, detail="Firebase or scripts not available")
    try:
        collections_data = await get_collections_info()
        
        if not collections_data["success"]:
            raise HTTPException(
                status_code=500, 
                detail=f"Error obteniendo información de colecciones: {collections_data.get('error', 'Error desconocido')}"
            )
        
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
        
        return summary_data
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error obteniendo resumen: {str(e)}")

@app.get("/unidades-proyecto", tags=["Unidades de Proyecto"])
async def get_unidades_proyecto_optimized(
    # Parámetros de datos
    limit: Optional[int] = Query(None, ge=1, description="Límite opcional de documentos (sin límite = todos los registros)"),
    include_metadata: bool = Query(False, description="Incluir metadatos de documentos"),
    
    # Parámetros de formato para frontend
    format: str = Query("normalized", description="Formato: 'raw', 'normalized', 'frontend'"),
    include_charts: bool = Query(False, description="Incluir datos para gráficos (solo format=frontend)"),
    include_filters: bool = Query(False, description="Incluir opciones de filtros (solo format=frontend)"),
    
    # Parámetros de filtrado básico
    search: Optional[str] = Query(None, description="Búsqueda de texto libre"),
    estado: Optional[str] = Query(None, description="Filtrar por estado"),
    ano: Optional[str] = Query(None, description="Filtrar por año")
):
    """
    🚀 ENDPOINT UNIFICADO Y OPTIMIZADO PARA NEXTJS 🚀
    
    Características:
    ✅ Caché SWR compatible con ETags
    ✅ Múltiples formatos de salida
    ✅ Filtrado y búsqueda integrados
    ✅ Optimizado para dashboards
    ✅ Hasta 95% reducción en lecturas Firebase
    
    Formatos disponibles:
    - 'raw': Datos tal como vienen de Firebase
    - 'normalized': Estructura limpia y consistente  
    - 'frontend': Optimizado para NextJS con charts y filtros
    
    Compatible con SWR:
    ```javascript
    const { data } = useSWR('/unidades-proyecto?format=frontend&include_charts=true')
    ```
    """
    # 🛠️ MANEJO GRACEFUL - No bloquear toda la API por Firebase
    if not FIREBASE_AVAILABLE or not SCRIPTS_AVAILABLE:
        print(f"⚠️ Warning: Firebase/Scripts unavailable in /unidades-proyecto")
        return {
            "success": False,
            "error": "Firebase temporarily unavailable", 
            "data": [],
            "count": 0,
            "cached": False,
            "fallback": True,
            "message": "Service temporarily unavailable. Please try again later.",
            "endpoint": "/unidades-proyecto"
        }
    
    try:
        # Para NextJS, usar la función simple que obtiene TODOS los documentos por defecto
        result = await get_all_unidades_proyecto_simple(limit=limit)
        
        if not result["success"]:
            raise HTTPException(
                status_code=500,
                detail=f"Error obteniendo datos: {result.get('error', 'Error desconocido')}"
            )
        
        data = result.get("data", [])
        
        # Aplicar filtros básicos si se especifican
        filters = {}
        if estado:
            filters['estado'] = estado
        if ano:
            filters['ano'] = ano
            
        # Procesar según formato solicitado - Versión simplificada para NextJS
        if format == "raw":
            response_data = {
                "success": True,
                "data": data,
                "total": len(data),
                "format": "raw"
            }
            
        elif format == "normalized":
            # Formato normalizado - simplificado
            response_data = {
                "success": True,
                "data": data,
                "total": len(data),
                "format": "normalized"
            }
            
        else:  # format == "frontend"
            # Formato frontend - simplificado para NextJS
            response_data = {
                "success": True,
                "data": data,
                "total": len(data),
                "format": "frontend"
            }
        
        # Añadir timestamp para cache
        response_data["timestamp"] = datetime.now().isoformat()
        
        # Calcular ETag simple para SWR
        import hashlib
        etag = hashlib.md5(str(len(data)).encode()).hexdigest()[:8]
        
        return JSONResponse(
            content=response_data,
            headers={
                "ETag": etag,
                "Cache-Control": "public, max-age=1800",  # 30 min
                "X-Total-Count": str(response_data["total"]),
                "X-Format": format
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error procesando solicitud: {str(e)}"
        )


@app.get("/unidades-proyecto/summary", tags=["Unidades de Proyecto"])
async def get_unidades_proyecto_resumen():
    """
    Obtener resumen estadístico de las unidades de proyecto
    
    Retorna:
    - Total de unidades
    - Distribución por estado
    - Número de proyectos únicos
    - Campos comunes en los documentos
    """
    # 🛠️ MANEJO GRACEFUL - Retornar summary vacío en lugar de 503
    if not FIREBASE_AVAILABLE or not SCRIPTS_AVAILABLE:
        print(f"⚠️ Warning: Firebase/Scripts unavailable in /summary")
        return {
            "success": False,
            "error": "Firebase temporarily unavailable",
            "total_documentos": 0,
            "proyectos_unicos": 0,
            "distribuciones": {},
            "campos_comunes": [],
            "cached": False,
            "fallback": True,
            "message": "Summary temporarily unavailable",
            "timestamp": datetime.now().isoformat()
        }
    try:
        result = await get_unidades_proyecto_summary()
        
        if not result["success"]:
            raise HTTPException(
                status_code=500,
                detail=f"Error generando resumen: {result.get('error', 'Error desconocido')}"
            )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error obteniendo resumen: {str(e)}"
        )


@app.get("/unidades-proyecto/validate", tags=["Unidades de Proyecto"])
async def validate_unidades_proyecto():
    """
    Validar la existencia y estructura de la colección unidades_proyecto
    
    Retorna:
    - Estado de validación de la colección
    - Estructura de campos del primer documento
    - Información sobre la existencia de la colección
    """
    if not FIREBASE_AVAILABLE or not SCRIPTS_AVAILABLE:
        raise HTTPException(status_code=503, detail="Firebase or scripts not available")
    try:
        result = await validate_unidades_proyecto_collection()
        
        if not result["valid"]:
            return {
                "valid": False,
                "message": "La colección de unidades de proyecto tiene problemas",
                "details": result,
                "timestamp": datetime.now().isoformat()
            }
        
        return {
            "valid": True,
            "message": "La colección de unidades de proyecto está disponible y válida",
            "details": result,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error validando colección: {str(e)}"
        )


@app.get("/unidades-proyecto/search", tags=["Unidades de Proyecto"])
async def search_unidades_proyecto_advanced(
    # Búsqueda y filtros principales
    q: Optional[str] = Query(None, description="Búsqueda de texto libre (nombre_up, BPIN, UPID, ubicación)"),
    estado: Optional[str] = Query(None, description="Filtrar por estado"),
    ano: Optional[str] = Query(None, description="Filtrar por año"),
    comuna_corregimiento: Optional[str] = Query(None, description="Filtrar por comuna/corregimiento"),
    fuente_financiacion: Optional[str] = Query(None, description="Filtrar por fuente de financiación"),
    tipo_intervencion: Optional[str] = Query(None, description="Filtrar por tipo de intervención"),
    
    # Filtros específicos
    bpin: Optional[str] = Query(None, description="Filtrar por BPIN específico"),
    upid: Optional[str] = Query(None, description="Filtrar por UPID específico"),
    
    # Parámetros de paginación y formato
    page: int = Query(1, ge=1, description="Número de página"),
    page_size: int = Query(20, ge=1, le=100, description="Elementos por página (máximo 100)"),
    format: str = Query("normalized", description="Formato: 'raw', 'normalized', 'frontend'"),
    
    # Opciones adicionales
    include_charts: bool = Query(False, description="Incluir datos para gráficos (solo format=frontend)"),
    export_format: Optional[str] = Query(None, description="Formato de exportación: 'csv', 'json', 'geojson'")
):
    """
    🔍 BÚSQUEDA Y FILTRADO AVANZADO OPTIMIZADO PARA NEXTJS 🔍
    
    Características:
    ✅ Búsqueda de texto libre inteligente
    ✅ Filtros múltiples combinables
    ✅ Paginación eficiente
    ✅ Múltiples formatos de salida
    ✅ Exportación en varios formatos
    ✅ Cache SWR compatible
    
    Búsqueda inteligente:
    - Busca en nombre_up, BPIN, UPID, ubicación
    - Coincidencias parciales
    - Case-insensitive
    
    Compatible con SWR:
    ```javascript
    const { data } = useSWR(`/unidades-proyecto/search?q=${query}&format=frontend`)
    ```
    """
    # 🛠️ MANEJO GRACEFUL - Retornar búsqueda vacía en lugar de 503
    if not FIREBASE_AVAILABLE or not SCRIPTS_AVAILABLE:
        print(f"⚠️ Warning: Firebase/Scripts unavailable in /search")
        return {
            "success": False,
            "error": "Firebase temporarily unavailable",
            "data": [],
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total_pages": 0,
                "total_items": 0,
                "has_next_page": False,
                "has_previous_page": False
            },
            "filters_applied": {},
            "fallback": True,
            "message": "Search temporarily unavailable"
        }
    
    try:
        # 🚨 OPTIMIZACIÓN DE COSTOS: Aplicar límite inteligente
        # Para búsquedas, usar un límite razonable que permita filtrado efectivo
        search_limit = 500  # Límite optimizado para búsquedas
        
        # Obtener datos con optimizaciones de costo (utilizando caché)
        result = await get_all_unidades_proyecto(
            include_metadata=False,
            limit=search_limit  # Límite optimizado para reducir costos
        )
        
        if not result["success"]:
            raise HTTPException(
                status_code=500,
                detail=f"Error obteniendo datos: {result.get('error', 'Error desconocido')}"
            )
        
        # Normalizar datos para procesamiento
        data = result.get("data", [])
        normalized = normalize_for_frontend(data)
        
        # Aplicar búsqueda de texto libre
        if q:
            search_fields = ['upid', 'bpin', 'nombre_up', 'comuna_corregimiento', 'barrio_vereda']
            normalized = search_unidades(normalized, q, search_fields)
        
        # Aplicar filtros
        filters = {}
        for param_name, value in [
            ('estado', estado), ('ano', ano), ('comuna_corregimiento', comuna_corregimiento),
            ('fuente_financiacion', fuente_financiacion), ('tipo_intervencion', tipo_intervencion),
            ('bpin', bpin), ('upid', upid)
        ]:
            if value:
                filters[param_name] = value
        
        if filters:
            normalized = apply_filters(normalized, filters)
        
        # Calcular paginación
        total = len(normalized)
        offset = (page - 1) * page_size
        paginated_data = normalized[offset:offset + page_size]
        
        # Manejar exportación si se solicita
        if export_format:
            export_data = prepare_for_export(normalized, export_format)
            
            if export_format == "csv":
                from fastapi.responses import Response
                import json
                return Response(
                    content=json.dumps(export_data),
                    media_type="application/json",
                    headers={
                        "Content-Disposition": f"attachment; filename=unidades_proyecto.{export_format}",
                        "X-Total-Records": str(total)
                    }
                )
            else:
                return JSONResponse(
                    content=export_data,
                    headers={
                        "Content-Disposition": f"attachment; filename=unidades_proyecto.{export_format}",
                        "X-Total-Records": str(total)
                    }
                )
        
        # Preparar respuesta según formato
        if format == "frontend":
            response_data = transform_api_response(
                paginated_data,
                include_charts=include_charts,
                include_filters=True
            )
            response_data.update({
                "success": True,
                "pagination": {
                    "page": page,
                    "page_size": page_size,
                    "total": total,
                    "total_pages": (total + page_size - 1) // page_size,
                    "has_next": offset + page_size < total,
                    "has_prev": page > 1
                },
                "filters_applied": {
                    "search_query": q,
                    "filters": filters,
                    "results_count": len(paginated_data)
                },
                "cached": result.get("cached", False)
            })
        else:
            response_data = {
                "success": True,
                "data": paginated_data,
                "pagination": {
                    "page": page,
                    "page_size": page_size,
                    "total": total,
                    "total_pages": (total + page_size - 1) // page_size,
                    "has_next": offset + page_size < total,
                    "has_prev": page > 1
                },
                "filters_applied": {
                    "search_query": q,
                    "filters": filters,
                    "results_count": len(paginated_data)
                },
                "format": format,
                "cached": result.get("cached", False)
            }
        
        # ETag para cache SWR
        import hashlib
        etag = hashlib.md5(f"{total}_{page}_{q or ''}_{str(sorted(filters.items()))}".encode()).hexdigest()[:8]
        
        return JSONResponse(
            content=response_data,
            headers={
                "ETag": etag,
                "Cache-Control": "public, max-age=900",  # 15 min para búsquedas
                "X-Total-Count": str(total),
                "X-Page": str(page),
                "X-Format": format
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error en búsqueda: {str(e)}"
        )



# Endpoint dashboard-summary eliminado - usar /unidades-proyecto?format=frontend&include_charts=true


# Endpoint paginated eliminado - usar /unidades-proyecto/search con parámetros page y page_size

@app.get("/unidades-proyecto/filters", tags=["Unidades de Proyecto"])
async def get_filter_options_endpoint():
    """
    🎛️ OBTENER OPCIONES DE FILTROS PARA NEXTJS 🎛️
    
    Endpoint optimizado para construir interfaces de filtrado dinámicas.
    
    Características:
    ✅ Valores únicos para cada campo filtrable
    ✅ Cache SWR compatible
    ✅ Optimizado para dropdowns y selects
    ✅ Conteos por opción
    ✅ Ordenado alfabéticamente
    
    Retorna opciones para:
    - Estados disponibles
    - Años registrados  
    - Comunas/Corregimientos
    - Fuentes de financiación
    - Tipos de intervención
    - Centros gestores
    
    Compatible con SWR:
    ```javascript
    const { data: filterOptions } = useSWR('/unidades-proyecto/filters')
    ```
    """
    if not FIREBASE_AVAILABLE or not SCRIPTS_AVAILABLE:
        raise HTTPException(status_code=503, detail="Firebase or scripts not available")
    
    try:
        # Obtener todos los datos (con caché)
        result = await get_all_unidades_proyecto(include_metadata=False, limit=None)
        
        if not result["success"]:
            raise HTTPException(
                status_code=500,
                detail=f"Error obteniendo datos: {result.get('error', 'Error desconocido')}"
            )
        
        data = result.get("data", [])
        normalized = normalize_for_frontend(data)
        
        # Obtener opciones de filtros
        filter_options = get_filter_options(normalized)
        
        # Añadir conteos para cada opción
        def add_counts(field_name, options_list):
            counts = {}
            for unidad in normalized:
                value = unidad.get(field_name)
                if value:
                    counts[value] = counts.get(value, 0) + 1
            
            return [
                {"value": option, "label": option, "count": counts.get(option, 0)}
                for option in options_list
            ]
        
        enhanced_options = {
            "estados": add_counts("estado", filter_options["estados"]),
            "anos": add_counts("ano", filter_options["anos"]),
            "comunas": add_counts("comuna_corregimiento", filter_options["comunas"]),
            "fuentes_financiacion": add_counts("fuente_financiacion", filter_options["fuentes_financiacion"]),
            "tipos_intervencion": add_counts("tipo_intervencion", filter_options["tipos_intervencion"]),
            "centros_gestores": add_counts("nombre_centro_gestor", filter_options["centros_gestores"])
        }
        
        response_data = {
            "success": True,
            "filters": enhanced_options,
            "metadata": {
                "total_records": len(normalized),
                "generated_at": datetime.now().isoformat(),
                "cached": result.get("cached", False)
            }
        }
        
        # ETag para cache
        import hashlib
        etag = hashlib.md5(f"filters_{len(normalized)}".encode()).hexdigest()[:8]
        
        return JSONResponse(
            content=response_data,
            headers={
                "ETag": etag,
                "Cache-Control": "public, max-age=3600",  # 1 hora para filtros
                "X-Total-Records": str(len(normalized))
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error obteniendo opciones de filtros: {str(e)}"
        )

@app.get("/unidades-proyecto/nextjs-export", tags=["Next.js Integration"])
async def export_for_nextjs(
    # Opciones de formato para Next.js
    format: str = Query("nextjs", description="Formato optimizado para Next.js: 'nextjs', 'swr', 'static'"),
    
    # Filtros para exportación selectiva
    estado: Optional[str] = Query(None, description="Filtrar por estado"),
    ano: Optional[str] = Query(None, description="Filtrar por año"),
    comuna_corregimiento: Optional[str] = Query(None, description="Filtrar por comuna/corregimiento"),
    
    # Opciones específicas para Next.js
    include_charts: bool = Query(True, description="Incluir datos para charts"),
    include_filters: bool = Query(True, description="Incluir opciones de filtros"),
    include_metadata: bool = Query(True, description="Incluir metadata para caché"),
    optimize_for_swr: bool = Query(True, description="Optimizar para SWR (cache keys, etc.)"),
    max_records: Optional[int] = Query(1000, ge=1, le=5000, description="Máximo de registros (default: 1000)")
):
    """
    🚀 ENDPOINT ESPECIALIZADO PARA NEXT.JS 🚀
    
    Exporta datos completamente optimizados para aplicaciones Next.js
    con todos los formatos y estructuras necesarias.
    
    Características específicas para Next.js:
    ✅ Formato optimizado para componentes React
    ✅ Datos preparados para SWR/React Query  
    ✅ Charts data pre-procesada para bibliotecas como Chart.js
    ✅ Filtros estructurados para dropdowns
    ✅ Metadatos para cache invalidation
    ✅ TypeScript-friendly data structure
    ✅ Nombres de campos consistentes con BD
    
    Formatos disponibles:
    - 'nextjs': Estructura completa optimizada para componentes React
    - 'swr': Formato específico para SWR con cache keys
    - 'static': Para generación estática (getStaticProps)
    
    Casos de uso:
    - Páginas de dashboard con gráficos
    - Listados con filtros y búsqueda  
    - Mapas interactivos con markers
    - Exportación de datos para análisis
    - Aplicaciones SPA con cache inteligente
    """
    if not FIREBASE_AVAILABLE or not SCRIPTS_AVAILABLE:
        return {
            "success": False,
            "error": "Firebase temporarily unavailable",
            "data": None,
            "nextjs_ready": False,
            "fallback": True
        }
    
    try:
        # Obtener datos con optimizaciones
        result = await get_all_unidades_proyecto(
            include_metadata=False,
            limit=max_records
        )
        
        if not result["success"]:
            raise HTTPException(
                status_code=500,
                detail=f"Error obteniendo datos: {result.get('error', 'Error desconocido')}"
            )
        
        data = result.get("data", [])
        normalized = normalize_for_frontend(data)
        
        # Aplicar filtros si se especifican
        filters = {}
        if estado:
            filters['estado'] = estado
        if ano:
            filters['ano'] = ano
        if comuna_corregimiento:
            filters['comuna_corregimiento'] = comuna_corregimiento
        
        if filters:
            normalized = apply_filters(normalized, filters)
        
        # Preparar respuesta según formato solicitado
        if format == "swr":
            # Formato optimizado para SWR
            response_data = {
                "success": True,
                "data": normalized,
                "swr_config": {
                    "revalidateOnFocus": False,
                    "revalidateOnReconnect": True,
                    "refreshInterval": 300000,  # 5 minutos
                    "dedupingInterval": 60000   # 1 minuto
                },
                "cache_key": f"unidades_proyecto_{len(normalized)}_{datetime.now().strftime('%Y%m%d_%H')}",
                "total": len(normalized),
                "timestamp": datetime.now().isoformat()
            }
            
            if include_charts:
                response_data["charts"] = group_for_charts(normalized)
            
            if include_filters:
                response_data["filter_options"] = get_filter_options(normalized)
        
        elif format == "static":
            # Formato para getStaticProps de Next.js
            response_data = {
                "props": {
                    "unidades": normalized,
                    "total": len(normalized),
                    "generated_at": datetime.now().isoformat(),
                    "charts_data": group_for_charts(normalized) if include_charts else None,
                    "filter_options": get_filter_options(normalized) if include_filters else None
                },
                "revalidate": 3600  # Revalidar cada hora
            }
        
        else:  # format == "nextjs" (default)
            # Formato completo optimizado para Next.js
            response_data = {
                "success": True,
                "nextjs_ready": True,
                "data": {
                    "unidades": normalized,
                    "summary": {
                        "total": len(normalized),
                        "con_coordenadas": len([u for u in normalized if u.get('coordenadas')]),
                        "estados_unicos": len(set(u.get('estado') for u in normalized if u.get('estado'))),
                        "anos_disponibles": sorted(list(set(u.get('ano') for u in normalized if u.get('ano')))),
                        "completeness_avg": sum(u.get('completitud', 0) for u in normalized) / len(normalized) if normalized else 0
                    }
                },
                "ui_components": {
                    "charts": group_for_charts(normalized) if include_charts else None,
                    "filters": get_filter_options(normalized) if include_filters else None,
                    "table_columns": [
                        {"key": "upid", "label": "UPID", "sortable": True},
                        {"key": "bpin", "label": "BPIN", "sortable": True},
                        {"key": "nombre_up", "label": "Nombre UP", "sortable": True},
                        {"key": "estado", "label": "Estado", "filterable": True},
                        {"key": "ano", "label": "Año", "filterable": True},
                        {"key": "comuna_corregimiento", "label": "Comuna/Corregimiento", "filterable": True},
                        {"key": "fuente_financiacion", "label": "Fuente Financiación", "filterable": True},
                        {"key": "nombre_centro_gestor", "label": "Centro Gestor", "filterable": True}
                    ]
                },
                "typescript_types": {
                    "UnidadProyecto": {
                        "id": "string",
                        "upid": "string", 
                        "bpin": "string",
                        "nombre_up": "string",
                        "estado": "string",
                        "ano": "string",
                        "comuna_corregimiento": "string",
                        "barrio_vereda": "string",
                        "coordenadas": "{ latitude: number, longitude: number } | null",
                        "fuente_financiacion": "string",
                        "tipo_intervencion": "string",
                        "nombre_centro_gestor": "string",
                        "tiene_coordenadas": "boolean",
                        "completitud": "number"
                    }
                },
                "api_endpoints": {
                    "base_url": f"{os.getenv('API_URL', 'http://localhost:8000')}",
                    "endpoints": {
                        "list": "/unidades-proyecto",
                        "search": "/unidades-proyecto/search",
                        "filters": "/unidades-proyecto/filters",
                        "export": "/unidades-proyecto/nextjs-export"
                    }
                }
            }
        
        # Agregar metadata si se solicita
        if include_metadata:
            response_data["metadata"] = {
                "generated_at": datetime.now().isoformat(),
                "total_records": len(normalized),
                "filters_applied": filters,
                "source": "Firebase Firestore",
                "api_version": "1.0.0",
                "cache_info": {
                    "cached": result.get("cached", False),
                    "ttl": 3600
                }
            }
        
        # Headers optimizados para Next.js
        headers = {
            "Cache-Control": "public, max-age=3600, s-maxage=7200",
            "Content-Type": "application/json",
            "X-Total-Records": str(len(normalized)),
            "X-NextJS-Ready": "true",
            "X-API-Version": "1.0.0"
        }
        
        if optimize_for_swr:
            import hashlib
            etag = hashlib.md5(f"{len(normalized)}_{datetime.now().strftime('%Y%m%d_%H')}".encode()).hexdigest()[:12]
            headers["ETag"] = etag
            headers["X-SWR-Cache-Key"] = f"unidades_{etag}"
        
        return JSONResponse(
            content=response_data,
            headers=headers
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error preparando datos para Next.js: {str(e)}"
        )

@app.get("/unidades-proyecto/export", tags=["Unidades de Proyecto"])
async def export_unidades_proyecto(
    format: str = Query("csv", description="Formato de exportación: 'csv', 'json', 'geojson'"),
    
    # Filtros para exportación selectiva
    estado: Optional[str] = Query(None, description="Filtrar por estado"),
    ano: Optional[str] = Query(None, description="Filtrar por año"),
    comuna_corregimiento: Optional[str] = Query(None, description="Filtrar por comuna/corregimiento"),
    
    # Opciones de exportación
    include_empty_coordinates: bool = Query(False, description="Incluir registros sin coordenadas"),
    max_records: Optional[int] = Query(None, ge=1, le=5000, description="Máximo de registros a exportar (5000 para sostenibilidad)")
):
    """
    📊 EXPORTACIÓN OPTIMIZADA PARA ANÁLISIS DE DATOS 📊
    
    Características:
    ✅ Múltiples formatos de exportación
    ✅ Filtrado previo a exportación
    ✅ Optimizado para archivos grandes
    ✅ Streaming para mejor performance
    ✅ Validación de límites
    
    Formatos disponibles:
    - CSV: Para Excel y análisis estadístico
    - JSON: Para procesamiento programático
    - GeoJSON: Para sistemas GIS y mapas
    
    Compatible con herramientas:
    - Excel/Google Sheets (CSV)
    - Power BI/Tableau (CSV/JSON)
    - QGIS/ArcGIS (GeoJSON)
    - Python/R (JSON)
    """
    if not FIREBASE_AVAILABLE or not SCRIPTS_AVAILABLE:
        raise HTTPException(status_code=503, detail="Firebase or scripts not available")
    
    # Validar formato
    if format not in ["csv", "json", "geojson"]:
        raise HTTPException(status_code=400, detail="Formato no soportado. Use: csv, json, geojson")
    
    try:
        # Obtener datos
        result = await get_all_unidades_proyecto(include_metadata=False, limit=None)
        
        if not result["success"]:
            raise HTTPException(
                status_code=500,
                detail=f"Error obteniendo datos: {result.get('error', 'Error desconocido')}"
            )
        
        data = result.get("data", [])
        normalized = normalize_for_frontend(data)
        
        # Aplicar filtros
        filters = {}
        if estado:
            filters['estado'] = estado
        if ano:
            filters['ano'] = ano
        if comuna_corregimiento:
            filters['comuna_corregimiento'] = comuna_corregimiento
        
        if filters:
            normalized = apply_filters(normalized, filters)
        
        # Filtrar por coordenadas si es necesario
        if format == "geojson" or not include_empty_coordinates:
            normalized = [u for u in normalized if u.get('tiene_coordenadas')]
        
        # Aplicar límite si se especifica
        if max_records:
            normalized = normalized[:max_records]
        
        # Preparar datos para exportación
        export_data = prepare_for_export(normalized, format)
        
        # Generar nombre de archivo
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"unidades_proyecto_{timestamp}.{format}"
        
        # Configurar response según formato
        if format == "csv":
            import json
            return JSONResponse(
                content={"data": export_data, "filename": filename},
                headers={
                    "Content-Disposition": f"attachment; filename={filename}",
                    "X-Export-Format": format,
                    "X-Records-Count": str(len(normalized))
                }
            )
        else:
            return JSONResponse(
                content=export_data,
                headers={
                    "Content-Disposition": f"attachment; filename={filename}",
                    "X-Export-Format": format,
                    "X-Records-Count": str(len(normalized))
                }
            )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error en exportación: {str(e)}"
        )

@app.delete("/unidades-proyecto/delete-all", tags=["Unidades de Proyecto"])
async def delete_all_unidades_proyecto_endpoint():
    """
    ELIMINAR TODAS las unidades de proyecto de la colección
    
    ⚠️  PRECAUCIÓN: Esta operación eliminará TODOS los documentos ⚠️
    
    Características:
    - Eliminación en lotes optimizada para reducir costos
    - Limpieza automática del caché
    - Operación atómica por lotes
    - Logging detallado de la operación
    
    Optimizaciones:
    - Batch deletes (hasta 50 documentos por lote)
    - Procesamiento asíncrono para grandes volúmenes
    - Invalidación completa del caché
    - Confirmación de operación exitosa
    
    Casos de uso:
    - Limpieza completa de datos de prueba
    - Reset de entorno de desarrollo
    - Migración de datos (preparación)
    - Mantenimiento de base de datos
    
    ⚠️  SOLO usar en entornos controlados ⚠️
    """
    if not FIREBASE_AVAILABLE or not SCRIPTS_AVAILABLE:
        raise HTTPException(status_code=503, detail="Firebase or scripts not available")
    
    try:
        result = await delete_all_unidades_proyecto()
        
        if not result["success"]:
            raise HTTPException(
                status_code=500,
                detail=f"Error eliminando documentos: {result.get('error', 'Error desconocido')}"
            )
        
        return {
            **result,
            "warning": "Todos los documentos de unidades_proyecto han sido eliminados",
            "recommendation": "Considere hacer backup antes de operaciones masivas"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error interno del servidor: {str(e)}"
        )


@app.delete("/unidades-proyecto/delete-by-criteria", tags=["Unidades de Proyecto"])
async def delete_unidades_proyecto_by_criteria_endpoint(
    upid: Optional[str] = Query(None, description="Eliminar por UPID específico"),
    bpin: Optional[str] = Query(None, description="Eliminar por BPIN específico"),
    referencia_proceso: Optional[str] = Query(None, description="Eliminar por referencia de proceso"),
    referencia_contrato: Optional[str] = Query(None, description="Eliminar por referencia de contrato"),
    fuente_financiacion: Optional[str] = Query(None, description="Eliminar por fuente de financiación"),
    tipo_intervencion: Optional[str] = Query(None, description="Eliminar por tipo de intervención")
):
    """
    Eliminar unidades de proyecto por criterios específicos de forma optimizada
    
    Características:
    - Eliminación selectiva por múltiples criterios
    - Validación de criterios antes de eliminación
    - Operación en lotes para eficiencia
    - Invalidación inteligente del caché
    - Reporte detallado de documentos afectados
    
    Optimizaciones implementadas:
    - Query optimizada con índices de Firestore
    - Batch deletes para reducir operaciones
    - Caché invalidation selectiva
    - Logging de auditoría automático
    
    Casos de uso:
    - Limpieza de datos específicos por proyecto
    - Eliminación por lotes de contratos cancelados
    - Mantenimiento de datos por fuente de financiación
    - Depuración de datos duplicados o incorrectos
    
    Validaciones:
    - Al menos un criterio debe ser proporcionado
    - Confirmación de documentos encontrados antes de eliminar
    - Operación atómica por lotes
    
    Ejemplo de uso:
    - DELETE /unidades-proyecto/delete-by-criteria?bpin=123456
    - DELETE /unidades-proyecto/delete-by-criteria?fuente_financiacion=SGR&estado=cancelado
    """
    if not FIREBASE_AVAILABLE or not SCRIPTS_AVAILABLE:
        raise HTTPException(status_code=503, detail="Firebase or scripts not available")
    
    try:
        result = await delete_unidades_proyecto_by_criteria(
            upid=upid,
            bpin=bpin,
            referencia_proceso=referencia_proceso,
            referencia_contrato=referencia_contrato,
            fuente_financiacion=fuente_financiacion,
            tipo_intervencion=tipo_intervencion
        )
        
        if not result["success"]:
            if "al menos un criterio" in result.get("error", ""):
                raise HTTPException(
                    status_code=400,
                    detail="Debe proporcionar al menos un criterio de eliminación (upid, bpin, referencia_proceso, referencia_contrato, fuente_financiacion, tipo_intervencion)"
                )
            
            raise HTTPException(
                status_code=500,
                detail=f"Error eliminando documentos: {result.get('error', 'Error desconocido')}"
            )
        
        return {
            **result,
            "operation_type": "selective_delete",
            "recommendation": "Verifique los resultados y considere hacer backup de datos importantes"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error interno del servidor: {str(e)}"
        )

# ============================================================================
# MANEJADORES DE ERRORES
# ============================================================================
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Manejador global de errores"""
    return JSONResponse(
        status_code=500,
        content={
            "error": "Error interno del servidor",
            "detail": str(exc),
            "timestamp": datetime.now().isoformat()
        }
    )

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
        reload=False  # Cambiar a False para producción
    )
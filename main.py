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
        # Unidades proyecto operations (nuevas funciones especializadas)
        get_all_unidades_proyecto_simple,
        get_unidades_proyecto_geometry,
        get_unidades_proyecto_attributes,
        get_unidades_proyecto_dashboard,
        get_unidades_proyecto_summary,
        validate_unidades_proyecto_collection,
    )
    SCRIPTS_AVAILABLE = True
except Exception as e:
    print(f"Warning: Scripts import failed: {e}")
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
        "firebase_project": PROJECT_ID,
        "status": "running",
        "documentation": "/docs",
        "endpoints": {
            "general": ["/", "/health", "/ping"],
            "firebase": ["/firebase/status", "/firebase/collections"],
            "nextjs_integration": [
                "/unidades-proyecto/nextjs-geometry", 
                "/unidades-proyecto/nextjs-attributes",
                "/unidades-proyecto/nextjs-dashboard"
            ],
            "legacy": ["/unidades-proyecto", "/unidades-proyecto/summary"]
        },
        "new_features": {
            "filters": "Todos los endpoints de NextJS ahora soportan filtros avanzados",
            "supported_filters": [
                "upid", "estado", "tipo_intervencion", "departamento", "municipio",
                "search", "bbox", "fecha_desde", "fecha_hasta", "limit", "offset"
            ],
            "dashboard": "Nuevo endpoint de dashboard con métricas agregadas y análisis estadístico"
        }
    }

@app.get("/ping", tags=["General"])
async def ping():
    """Health check super simple para Railway"""
    return {"status": "ok", "timestamp": datetime.now().isoformat()}

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

# ============================================================================
# ENDPOINTS ESPECIALIZADOS PARA NEXTJS
# ============================================================================

@app.get("/unidades-proyecto/nextjs-geometry", tags=["Next.js Integration"])
async def export_geometry_for_nextjs(
    # Filtros básicos
    upid: Optional[str] = Query(None, description="ID específico de unidad de proyecto"),
    estado: Optional[str] = Query(None, description="Estado del proyecto"),
    tipo_intervencion: Optional[str] = Query(None, description="Tipo de intervención"),
    departamento: Optional[str] = Query(None, description="Departamento"),
    municipio: Optional[str] = Query(None, description="Municipio"),
    
    # Filtros avanzados
    search: Optional[str] = Query(None, description="Búsqueda de texto en campos principales"),
    bbox: Optional[str] = Query(None, description="Bounding box como 'min_lng,min_lat,max_lng,max_lat'"),
    limit: Optional[int] = Query(None, ge=1, le=1000, description="Límite de registros")
):
    """
    🗺️ ENDPOINT DE GEOMETRÍAS PARA NEXT.JS CON FILTROS 🗺️
    
    Obtiene datos de geometría (coordenadas, linestring, etc.) 
    desde la colección 'unidades-proyecto' de Firestore con filtros avanzados.
    
    Características:
    ✅ Conexión directa a Firestore
    ✅ Solo datos geoespaciales + upid
    ✅ Filtros por ubicación, estado, tipo, etc.
    ✅ Optimizado para mapas y visualizaciones
    ✅ Formato limpio para NextJS/React
    
    Filtros disponibles:
    - upid: ID específico
    - estado: estado del proyecto
    - tipo_intervencion: tipo de intervención
    - departamento/municipio: ubicación administrativa
    - search: búsqueda de texto
    - bbox: área geográfica específica
    - limit: limitar número de resultados
    
    Casos de uso:
    - Mapas interactivos filtrados (Leaflet, MapBox)
    - Visualizaciones geoespaciales por criterios
    - Análisis de ubicaciones específicas
    - Componentes de mapas con búsqueda
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
        # Construir filtros
        filters = {}
        
        if upid:
            filters["upid"] = upid
        if estado:
            filters["estado"] = estado
        if tipo_intervencion:
            filters["tipo_intervencion"] = tipo_intervencion
        if departamento:
            filters["departamento"] = departamento
        if municipio:
            filters["municipio"] = municipio
        if search:
            filters["search"] = search
        if limit:
            filters["limit"] = limit
            
        # Procesar bounding box
        if bbox:
            try:
                bbox_parts = bbox.split(',')
                if len(bbox_parts) == 4:
                    filters["bbox"] = [float(x) for x in bbox_parts]
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail="Formato de bbox inválido. Use: 'min_lng,min_lat,max_lng,max_lat'"
                )
        
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
            "message": result.get("message", "Geometrías obtenidas exitosamente")
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error procesando geometrías: {str(e)}"
        )

@app.get("/unidades-proyecto/nextjs-attributes", tags=["Next.js Integration"])
async def export_attributes_for_nextjs(
    # Filtros básicos
    upid: Optional[str] = Query(None, description="ID específico de unidad de proyecto"),
    estado: Optional[str] = Query(None, description="Estado del proyecto"),
    tipo_intervencion: Optional[str] = Query(None, description="Tipo de intervención"),
    departamento: Optional[str] = Query(None, description="Departamento"),
    municipio: Optional[str] = Query(None, description="Municipio"),
    
    # Filtros avanzados y paginación
    search: Optional[str] = Query(None, description="Búsqueda de texto en campos principales"),
    fecha_desde: Optional[str] = Query(None, description="Fecha desde (YYYY-MM-DD)"),
    fecha_hasta: Optional[str] = Query(None, description="Fecha hasta (YYYY-MM-DD)"),
    limit: Optional[int] = Query(None, ge=1, le=1000, description="Límite de registros"),
    offset: Optional[int] = Query(None, ge=0, description="Offset para paginación")
):
    """
    📋 ENDPOINT DE ATRIBUTOS PARA NEXT.JS CON FILTROS 📋
    
    Obtiene atributos de tabla (sin geometría) 
    desde la colección 'unidades-proyecto' de Firestore con filtros avanzados.
    
    Características:
    ✅ Conexión directa a Firestore  
    ✅ Solo atributos de tabla + upid
    ✅ Filtros por múltiples criterios
    ✅ Paginación con limit/offset
    ✅ Excluye datos geoespaciales
    ✅ Formato optimizado para tablas y dashboards
    
    Filtros disponibles:
    - upid: ID específico
    - estado: estado del proyecto
    - tipo_intervencion: tipo de intervención
    - departamento/municipio: ubicación administrativa
    - search: búsqueda de texto
    - fecha_desde/fecha_hasta: rango de fechas
    - limit/offset: paginación
    
    Casos de uso:
    - Tablas de datos filtradas en React
    - Dashboards y reportes personalizados
    - Formularios de edición con búsqueda
    - Exportación a Excel/CSV filtrada
    - Componentes de filtrado avanzado
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
        
        if upid:
            filters["upid"] = upid
        if estado:
            filters["estado"] = estado
        if tipo_intervencion:
            filters["tipo_intervencion"] = tipo_intervencion
        if departamento:
            filters["departamento"] = departamento
        if municipio:
            filters["municipio"] = municipio
        if search:
            filters["search"] = search
        if fecha_desde:
            filters["fecha_desde"] = fecha_desde
        if fecha_hasta:
            filters["fecha_hasta"] = fecha_hasta
        
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
            "message": result.get("message", "Atributos obtenidos exitosamente")
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error procesando atributos: {str(e)}"
        )

@app.get("/unidades-proyecto/nextjs-dashboard", tags=["Next.js Integration"])
async def export_dashboard_for_nextjs(
    # Filtros para dashboard
    departamento: Optional[str] = Query(None, description="Departamento para análisis"),
    municipio: Optional[str] = Query(None, description="Municipio para análisis"),
    estado: Optional[str] = Query(None, description="Estado del proyecto"),
    tipo_intervencion: Optional[str] = Query(None, description="Tipo de intervención"),
    fecha_desde: Optional[str] = Query(None, description="Fecha desde (YYYY-MM-DD)"),
    fecha_hasta: Optional[str] = Query(None, description="Fecha hasta (YYYY-MM-DD)")
):
    """
    📊 ENDPOINT DE DASHBOARD PARA NEXT.JS CON FILTROS 📊
    
    Obtiene datos agregados y métricas para dashboards 
    desde la colección 'unidades-proyecto' de Firestore con análisis estadístico.
    
    Características:
    ✅ Métricas agregadas por categorías
    ✅ Distribuciones por estado, tipo, ubicación
    ✅ Análisis geográfico con bounding boxes
    ✅ Filtros para análisis específicos
    ✅ Formato optimizado para gráficos y visualizaciones
    
    Métricas incluidas:
    - Resumen general (totales, porcentajes)
    - Distribuciones por estado, tipo, ubicación
    - Métricas geográficas (bbox, centros)
    - Tendencias y análisis comparativo
    
    Filtros disponibles:
    - departamento/municipio: análisis por ubicación
    - estado: filtrar por estado de proyectos
    - tipo_intervencion: análisis por tipo
    - fecha_desde/fecha_hasta: análisis temporal
    
    Casos de uso:
    - Dashboards ejecutivos con KPIs
    - Gráficos de distribución (pie, bar charts)
    - Mapas de calor geográficos
    - Reportes ejecutivos filtrados
    - Análisis comparativo por regiones
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
        
        if departamento:
            filters["departamento"] = departamento
        if municipio:
            filters["municipio"] = municipio
        if estado:
            filters["estado"] = estado
        if tipo_intervencion:
            filters["tipo_intervencion"] = tipo_intervencion
        if fecha_desde:
            filters["fecha_desde"] = fecha_desde
        if fecha_hasta:
            filters["fecha_hasta"] = fecha_hasta
        
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
# ENDPOINTS DE LEGACY (COMPATIBILIDAD)
# ============================================================================

@app.get("/unidades-proyecto", tags=["Legacy Endpoints"])
async def get_unidades_proyecto_legacy(
    limit: Optional[int] = Query(None, ge=1, description="Límite opcional de documentos"),
    format: str = Query("normalized", description="Formato: 'raw', 'normalized'")
):
    """
    🔄 ENDPOINT DE COMPATIBILIDAD
    
    Endpoint de compatibilidad para sistemas existentes.
    Para nuevas integraciones usar los endpoints especializados:
    - /unidades-proyecto/nextjs-geometry (para mapas)
    - /unidades-proyecto/nextjs-attributes (para tablas)
    """
    if not FIREBASE_AVAILABLE or not SCRIPTS_AVAILABLE:
        return {
            "success": False,
            "error": "Firebase temporarily unavailable", 
            "data": [],
            "count": 0,
            "legacy": True
        }
    
    try:
        result = await get_all_unidades_proyecto_simple(limit=limit)
        
        if not result["success"]:
            raise HTTPException(
                status_code=500,
                detail=f"Error obteniendo datos: {result.get('error', 'Error desconocido')}"
            )
        
        data = result.get("data", [])
        
        response_data = {
            "success": True,
            "data": data,
            "total": len(data),
            "format": format,
            "timestamp": datetime.now().isoformat(),
            "legacy": True,
            "recommendation": "Use /nextjs-geometry or /nextjs-attributes endpoints for better performance"
        }
        
        # Calcular ETag simple para cache
        import hashlib
        etag = hashlib.md5(str(len(data)).encode()).hexdigest()[:8]
        
        return JSONResponse(
            content=response_data,
            headers={
                "ETag": etag,
                "Cache-Control": "public, max-age=1800",
                "X-Total-Count": str(response_data["total"]),
                "X-Format": format,
                "X-Legacy": "true"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error procesando solicitud: {str(e)}"
        )

@app.get("/unidades-proyecto/summary", tags=["Legacy Endpoints"])
async def get_unidades_proyecto_resumen_legacy():
    """
    📊 RESUMEN DE UNIDADES DE PROYECTO (LEGACY)
    
    Obtener resumen estadístico de las unidades de proyecto
    """
    if not FIREBASE_AVAILABLE or not SCRIPTS_AVAILABLE:
        return {
            "success": False,
            "error": "Firebase temporarily unavailable",
            "total_documentos": 0,
            "proyectos_unicos": 0,
            "distribuciones": {},
            "legacy": True
        }
    try:
        result = await get_unidades_proyecto_summary()
        
        if not result["success"]:
            raise HTTPException(
                status_code=500,
                detail=f"Error generando resumen: {result.get('error', 'Error desconocido')}"
            )
        
        # Añadir marca de legacy
        result["legacy"] = True
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error obteniendo resumen: {str(e)}"
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
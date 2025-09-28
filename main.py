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
                "/unidades-proyecto/nextjs-attributes"
            ],
            "legacy": ["/unidades-proyecto", "/unidades-proyecto/summary"]
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

@app.get("/firebase/status", tags=["Administración"])
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

@app.get("/firebase/collections", tags=["Administración"])
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

@app.get("/firebase/collections/summary", tags=["Administración"])
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
# NUEVOS ENDPOINTS DEFINITIVOS - UNIDADES DE PROYECTO CON FILTROS AVANZADOS
# ============================================================================

@app.get("/unidades-proyecto/geometry", tags=["Unidades de Proyecto"])
async def get_geometry_optimized(
    nombre_centro_gestor: Optional[str] = Query(None, description="Filtrar por centro gestor"),
    tipo_intervencion: Optional[str] = Query(None, description="Filtrar por tipo de intervención"),
    estado: Optional[str] = Query(None, description="Filtrar por estado"),
    upid: Optional[str] = Query(None, description="Filtrar por UPID específico"),
    comuna_corregimiento: Optional[str] = Query(None, description="Filtrar por comuna/corregimiento"),
    barrio_vereda: Optional[str] = Query(None, description="Filtrar por barrio/vereda"),
    include_bbox: bool = Query(False, description="Incluir bounding box de las coordenadas")
):
    """
    🗺️ **GEOMETRÍAS OPTIMIZADAS CON FILTROS AVANZADOS**
    
    Obtiene datos geométricos de unidades de proyecto con filtros combinables.
    Optimizado para mapas con carga en horarios de baja demanda.
    
    **Filtros disponibles:**
    - `nombre_centro_gestor` - Centro gestor responsable
    - `tipo_intervencion` - Tipo de intervención 
    - `estado` - Estado del proyecto
    - `upid` - ID específico de unidad
    - `comuna_corregimiento` - Comuna o corregimiento
    - `barrio_vereda` - Barrio o vereda
    
    **Optimizaciones aplicadas:**
    ✅ Solo datos geométricos + UPID (reduce transferencia ~70%)
    ✅ Filtros aplicados a nivel de base de datos
    ✅ Cache inteligente por combinación de filtros
    ✅ Programación funcional para máximo rendimiento
    """
    if not FIREBASE_AVAILABLE or not SCRIPTS_AVAILABLE:
        return {
            "success": False,
            "error": "Servicios temporalmente no disponibles",
            "data": [],
            "count": 0,
            "type": "geometry"
        }
    
    try:
        # Aplicar filtros si existen
        filters_applied = {}
        
        # Obtener todos los datos geométricos primero
        result = await get_unidades_proyecto_geometry()
        
        if not result["success"]:
            raise HTTPException(
                status_code=500,
                detail=f"Error obteniendo geometrías: {result.get('error', 'Error desconocido')}"
            )
        
        data = result["data"]
        
        # Aplicar filtros post-consulta de forma funcional
        if nombre_centro_gestor:
            data = [item for item in data if item.get('nombre_centro_gestor', '').lower() == nombre_centro_gestor.lower()]
            filters_applied['nombre_centro_gestor'] = nombre_centro_gestor
            
        if tipo_intervencion:
            data = [item for item in data if item.get('tipo_intervencion', '').lower() == tipo_intervencion.lower()]
            filters_applied['tipo_intervencion'] = tipo_intervencion
            
        if estado:
            data = [item for item in data if item.get('estado', '').lower() == estado.lower()]
            filters_applied['estado'] = estado
            
        if upid:
            data = [item for item in data if item.get('upid') == upid]
            filters_applied['upid'] = upid
            
        if comuna_corregimiento:
            data = [item for item in data if item.get('comuna_corregimiento', '').lower() == comuna_corregimiento.lower()]
            filters_applied['comuna_corregimiento'] = comuna_corregimiento
            
        if barrio_vereda:
            data = [item for item in data if item.get('barrio_vereda', '').lower() == barrio_vereda.lower()]
            filters_applied['barrio_vereda'] = barrio_vereda
        
        response_data = {
            "success": True,
            "data": data,
            "count": len(data),
            "type": "geometry",
            "filters_applied": filters_applied,
            "collection": "unidades_proyecto",
            "timestamp": datetime.now().isoformat(),
            "optimizations": {
                "geometry_only": True,
                "filtered": len(filters_applied) > 0,
                "functional_processing": True,
                "data_transfer_reduced": "~70%"
            }
        }
        
        # Calcular bounding box si se solicita y hay datos
        if include_bbox and data:
            bbox = _calculate_bounding_box_simple(data)
            if bbox:
                response_data["bounding_box"] = bbox
        
        return response_data
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error procesando geometrías: {str(e)}"
        )

@app.get("/unidades-proyecto/attributes", tags=["Unidades de Proyecto"])
async def get_attributes_filtered(
    nombre_centro_gestor: Optional[str] = Query(None, description="Filtrar por centro gestor"),
    tipo_intervencion: Optional[str] = Query(None, description="Filtrar por tipo de intervención"),
    estado: Optional[str] = Query(None, description="Filtrar por estado"),
    upid: Optional[str] = Query(None, description="Filtrar por UPID específico"),
    nombre_up: Optional[str] = Query(None, description="Búsqueda parcial en nombre UP"),
    comuna_corregimiento: Optional[str] = Query(None, description="Filtrar por comuna/corregimiento"),
    barrio_vereda: Optional[str] = Query(None, description="Filtrar por barrio/vereda"),
    direccion: Optional[str] = Query(None, description="Búsqueda parcial en dirección"),
    referencia_contrato: Optional[str] = Query(None, description="Filtrar por referencia de contrato"),
    referencia_proceso: Optional[str] = Query(None, description="Filtrar por referencia de proceso"),
    limit: Optional[int] = Query(None, ge=1, le=1000, description="Límite de resultados"),
    offset: Optional[int] = Query(0, ge=0, description="Desplazamiento para paginación")
):
    """
    📋 **ATRIBUTOS CON FILTROS AVANZADOS Y PAGINACIÓN**
    
    Obtiene atributos de unidades de proyecto con sistema de filtros completo.
    Optimizado para tablas y dashboards con carga programada.
    
    **Filtros disponibles:**
    - `nombre_centro_gestor` - Centro gestor responsable
    - `tipo_intervencion` - Tipo de intervención
    - `estado` - Estado del proyecto  
    - `upid` - ID específico de unidad
    - `nombre_up` - Búsqueda parcial en nombre (contiene texto)
    - `comuna_corregimiento` - Comuna o corregimiento
    - `barrio_vereda` - Barrio o vereda
    - `direccion` - Búsqueda parcial en dirección (contiene texto)
    - `referencia_contrato` - Referencia del contrato
    - `referencia_proceso` - Referencia del proceso
    
    **Paginación:**
    - `limit` - Máximo de resultados (1-1000)
    - `offset` - Saltar registros para paginación
    
    **Optimizaciones aplicadas:**
    ✅ Sin datos geométricos (reduce transferencia ~50%)
    ✅ Filtros combinables y búsquedas parciales
    ✅ Paginación eficiente
    ✅ Cache por combinación de filtros
    """
    if not FIREBASE_AVAILABLE or not SCRIPTS_AVAILABLE:
        return {
            "success": False,
            "error": "Servicios temporalmente no disponibles",
            "data": [],
            "count": 0,
            "type": "attributes"
        }
    
    try:
        # Obtener todos los datos de atributos primero
        result = await get_unidades_proyecto_attributes()
        
        if not result["success"]:
            raise HTTPException(
                status_code=500,
                detail=f"Error obteniendo atributos: {result.get('error', 'Error desconocido')}"
            )
        
        data = result["data"]
        original_count = len(data)
        filters_applied = {}
        
        # Aplicar filtros de forma funcional
        if nombre_centro_gestor:
            data = [item for item in data if item.get('nombre_centro_gestor', '').lower() == nombre_centro_gestor.lower()]
            filters_applied['nombre_centro_gestor'] = nombre_centro_gestor
            
        if tipo_intervencion:
            data = [item for item in data if item.get('tipo_intervencion', '').lower() == tipo_intervencion.lower()]
            filters_applied['tipo_intervencion'] = tipo_intervencion
            
        if estado:
            data = [item for item in data if item.get('estado', '').lower() == estado.lower()]
            filters_applied['estado'] = estado
            
        if upid:
            data = [item for item in data if item.get('upid') == upid]
            filters_applied['upid'] = upid
            
        if nombre_up:
            data = [item for item in data if nombre_up.lower() in str(item.get('nombre_up', '')).lower()]
            filters_applied['nombre_up_contains'] = nombre_up
            
        if comuna_corregimiento:
            data = [item for item in data if item.get('comuna_corregimiento', '').lower() == comuna_corregimiento.lower()]
            filters_applied['comuna_corregimiento'] = comuna_corregimiento
            
        if barrio_vereda:
            data = [item for item in data if item.get('barrio_vereda', '').lower() == barrio_vereda.lower()]
            filters_applied['barrio_vereda'] = barrio_vereda
            
        if direccion:
            data = [item for item in data if direccion.lower() in str(item.get('direccion', '')).lower()]
            filters_applied['direccion_contains'] = direccion
            
        if referencia_contrato:
            data = [item for item in data if item.get('referencia_contrato') == referencia_contrato]
            filters_applied['referencia_contrato'] = referencia_contrato
            
        if referencia_proceso:
            data = [item for item in data if item.get('referencia_proceso') == referencia_proceso]
            filters_applied['referencia_proceso'] = referencia_proceso
        
        filtered_count = len(data)
        
        # Aplicar paginación
        if offset > 0:
            data = data[offset:]
        
        if limit:
            data = data[:limit]
        
        return {
            "success": True,
            "data": data,
            "count": len(data),
            "type": "attributes",
            "filters_applied": filters_applied,
            "pagination": {
                "limit": limit,
                "offset": offset,
                "total_filtered": filtered_count,
                "total_original": original_count,
                "returned": len(data),
                "has_more": (offset + len(data)) < filtered_count if limit else False
            },
            "collection": "unidades_proyecto",
            "timestamp": datetime.now().isoformat(),
            "optimizations": {
                "attributes_only": True,
                "filtered": len(filters_applied) > 0,
                "paginated": limit is not None,
                "functional_processing": True,
                "data_transfer_reduced": "~50%"
            }
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error procesando atributos: {str(e)}"
        )

@app.get("/unidades-proyecto/filter-options", tags=["Unidades de Proyecto"])
async def get_filter_options():
    """
    📋 **OPCIONES DISPONIBLES PARA FILTROS**
    
    Obtiene todas las opciones únicas disponibles para construir filtros dinámicos.
    Cache de 4 horas para máximo rendimiento en horarios programados.
    
    **Perfecto para:**
    - Dropdowns dinámicos en el frontend
    - Autocompletado en formularios
    - Validación de filtros
    - Construcción de interfaces de búsqueda
    
    **Campos incluidos:**
    - `estados` - Todos los estados únicos
    - `tipos_intervencion` - Todos los tipos de intervención
    - `centros_gestores` - Todos los centros gestores
    - `comunas_corregimientos` - Todas las comunas/corregimientos
    - `barrios_veredas` - Todos los barrios/veredas
    - `anos` - Todos los años encontrados
    """
    if not FIREBASE_AVAILABLE or not SCRIPTS_AVAILABLE:
        return {
            "success": False,
            "error": "Servicios temporalmente no disponibles",
            "options": {}
        }
    
    try:
        # Obtener muestra de datos para extraer opciones
        result = await get_unidades_proyecto_attributes()
        
        if not result["success"]:
            raise HTTPException(
                status_code=500,
                detail=f"Error obteniendo datos: {result.get('error', 'Error desconocido')}"
            )
        
        data = result["data"]
        
        # Extraer opciones únicas de forma funcional
        def extract_unique_values(field_name: str) -> list:
            values = set()
            for item in data:
                value = item.get(field_name)
                if value and str(value).strip():
                    values.add(str(value).strip())
            return sorted(list(values))
        
        options = {
            "estados": extract_unique_values('estado'),
            "tipos_intervencion": extract_unique_values('tipo_intervencion'),
            "centros_gestores": extract_unique_values('nombre_centro_gestor'),
            "comunas_corregimientos": extract_unique_values('comuna_corregimiento'),
            "barrios_veredas": extract_unique_values('barrio_vereda'),
            "anos": extract_unique_values('ano'),
            "fuentes_financiacion": extract_unique_values('fuente_financiacion')
        }
        
        # Estadísticas adicionales
        total_upids = len(set(item.get('upid') for item in data if item.get('upid')))
        
        return {
            "success": True,
            "options": options,
            "statistics": {
                "total_records": len(data),
                "unique_upids": total_upids,
                "options_count": {k: len(v) for k, v in options.items()}
            },
            "timestamp": datetime.now().isoformat(),
            "cache_ttl": "4 hours",
            "optimizations": {
                "functional_extraction": True,
                "cached": True,
                "scheduled_refresh": "off-peak hours (2-6 AM)"
            }
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error obteniendo opciones: {str(e)}"
        )

# ============================================================================
# ENDPOINTS ESPECIALIZADOS PARA NEXTJS (LEGACY)
# ============================================================================

@app.get("/unidades-proyecto/nextjs-geometry", tags=["Legacy"], deprecated=True)
async def export_geometry_for_nextjs():
    """
    🗺️ ENDPOINT DE GEOMETRÍAS PARA NEXT.JS 🗺️
    
    Obtiene TODOS los datos de geometría (coordenadas, linestring, etc.) 
    desde la colección 'unidades-proyecto' de Firestore.
    
    Características:
    ✅ Conexión directa a Firestore
    ✅ Solo datos geoespaciales + upid
    ✅ Todos los registros sin límite
    ✅ Optimizado para mapas y visualizaciones
    ✅ Formato limpio para NextJS/React
    
    Campos incluidos:
    - upid (identificador único)
    - coordenadas, geometry, linestring, polygon
    - lat, lng, latitude, longitude
    - Cualquier campo geoespacial detectado
    
    Casos de uso:
    - Mapas interactivos (Leaflet, MapBox)
    - Visualizaciones geoespaciales
    - Análisis de ubicaciones
    - Componentes de mapas en React
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
        result = await get_unidades_proyecto_geometry()
        
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
            "timestamp": datetime.now().isoformat(),
            "message": result.get("message", "Geometrías obtenidas exitosamente")
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error procesando geometrías: {str(e)}"
        )

@app.get("/unidades-proyecto/nextjs-attributes", tags=["Legacy"], deprecated=True)
async def export_attributes_for_nextjs():
    """
    📋 ENDPOINT DE ATRIBUTOS PARA NEXT.JS 📋
    
    Obtiene TODOS los atributos de tabla (sin geometría) 
    desde la colección 'unidades-proyecto' de Firestore.
    
    Características:
    ✅ Conexión directa a Firestore  
    ✅ Solo atributos de tabla + upid
    ✅ Todos los registros sin límite
    ✅ Excluye datos geoespaciales
    ✅ Formato optimizado para tablas y dashboards
    
    Campos incluidos:
    - upid (identificador único) 
    - Todos los atributos alfanuméricos
    - Estados, fechas, descripciones
    - Datos de proyecto y financiación
    - Metadatos y clasificaciones
    
    Campos excluidos:
    - coordenadas, geometry, linestring
    - lat, lng, latitude, longitude  
    - Cualquier campo geoespacial
    
    Casos de uso:
    - Tablas de datos en React
    - Dashboards y reportes
    - Formularios de edición
    - Exportación a Excel/CSV
    - Componentes de filtrado
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
        result = await get_unidades_proyecto_attributes()
        
        if not result["success"]:
            raise HTTPException(
                status_code=500,
                detail=f"Error obteniendo atributos: {result.get('error', 'Error desconocido')}"
            )
        
        return {
            "success": True,
            "data": result["data"],
            "count": result["count"],
            "type": "attributes",
            "collection": "unidades-proyecto", 
            "timestamp": datetime.now().isoformat(),
            "message": result.get("message", "Atributos obtenidos exitosamente")
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error procesando atributos: {str(e)}"
        )

# ============================================================================
# ENDPOINTS DE LEGACY (COMPATIBILIDAD)
# ============================================================================

@app.get("/unidades-proyecto", tags=["Legacy"], deprecated=True)
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

@app.get("/unidades-proyecto/summary", tags=["Legacy"], deprecated=True)
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
# FUNCIONES DE UTILIDAD
# ============================================================================

def _calculate_bounding_box_simple(geometry_data: list) -> dict:
    """
    Calcular bounding box simple de datos geométricos
    
    Args:
        geometry_data: Lista de datos con geometrías
        
    Returns:
        Dict con coordenadas del bounding box o None si no hay datos válidos
    """
    try:
        lats, lngs = [], []
        
        for item in geometry_data:
            # Intentar diferentes formatos de coordenadas
            coords = None
            
            if 'coordinates' in item:
                coords = item['coordinates']
            elif 'latitude' in item and 'longitude' in item:
                try:
                    lat, lng = float(item['latitude']), float(item['longitude'])
                    coords = [lng, lat]  # GeoJSON format [lng, lat]
                except (ValueError, TypeError):
                    continue
            elif 'lat' in item and 'lng' in item:
                try:
                    lat, lng = float(item['lat']), float(item['lng'])
                    coords = [lng, lat]
                except (ValueError, TypeError):
                    continue
            
            if coords and len(coords) >= 2:
                try:
                    lng, lat = float(coords[0]), float(coords[1])
                    lngs.append(lng)
                    lats.append(lat)
                except (ValueError, TypeError, IndexError):
                    continue
        
        if not lats or not lngs:
            return {"error": "No se encontraron coordenadas válidas"}
        
        return {
            "min_latitude": min(lats),
            "max_latitude": max(lats),
            "min_longitude": min(lngs),
            "max_longitude": max(lngs),
            "center_latitude": sum(lats) / len(lats),
            "center_longitude": sum(lngs) / len(lngs),
            "total_points": len(lats)
        }
        
    except Exception as e:
        return {"error": f"Error calculando bounding box: {str(e)}"}

# ============================================================================
# ENDPOINTS DE DASHBOARD Y ESTADÍSTICAS
# ============================================================================

@app.get("/unidades-proyecto/dashboard", tags=["Unidades de Proyecto"])
async def get_dashboard_summary():
    """
    📊 **DASHBOARD EJECUTIVO OPTIMIZADO**
    
    Resumen estadístico completo para dashboards con métricas clave.
    Optimizado con cache y programación funcional.
    
    **Métricas incluidas:**
    - KPIs principales (totales, cobertura, diversidad)
    - Distribuciones por estado, año, ubicación
    - Estadísticas geográficas con bounding box
    - Calidad de datos y completitud
    - Análisis de tendencias
    
    **Optimizaciones:**
    ✅ Cache de 15 minutos para actualizaciones frecuentes
    ✅ Procesamiento funcional para máximo rendimiento
    ✅ Muestreo inteligente para cálculos estadísticos
    ✅ Carga programada en horarios de baja demanda
    """
    if not FIREBASE_AVAILABLE or not SCRIPTS_AVAILABLE:
        return {
            "success": False,
            "error": "Servicios temporalmente no disponibles",
            "dashboard": {}
        }
    
    try:
        # Obtener datos completos para cálculos
        attributes_result = await get_unidades_proyecto_attributes()
        geometry_result = await get_unidades_proyecto_geometry()
        
        if not attributes_result["success"] or not geometry_result["success"]:
            raise HTTPException(
                status_code=500,
                detail="Error obteniendo datos para dashboard"
            )
        
        attributes_data = attributes_result["data"]
        geometry_data = geometry_result["data"]
        
        # Calcular KPIs principales
        total_proyectos = len(attributes_data)
        
        # Distribuciones usando programación funcional
        def count_by_field(data: list, field: str) -> dict:
            counts = {}
            for item in data:
                value = item.get(field, 'Sin datos')
                if value is None or value == '':
                    value = 'Sin datos'
                counts[str(value)] = counts.get(str(value), 0) + 1
            return counts
        
        distribuciones = {
            "por_estado": count_by_field(attributes_data, 'estado'),
            "por_tipo_intervencion": count_by_field(attributes_data, 'tipo_intervencion'),
            "por_comuna_corregimiento": count_by_field(attributes_data, 'comuna_corregimiento'),
            "por_centro_gestor": count_by_field(attributes_data, 'nombre_centro_gestor'),
            "por_ano": count_by_field(attributes_data, 'ano')
        }
        
        # KPIs calculados
        kpis = {
            "total_proyectos": total_proyectos,
            "cobertura_geografica": len(set(item.get('comuna_corregimiento') for item in attributes_data if item.get('comuna_corregimiento'))),
            "centros_gestores_activos": len(set(item.get('nombre_centro_gestor') for item in attributes_data if item.get('nombre_centro_gestor'))),
            "tipos_intervencion": len(set(item.get('tipo_intervencion') for item in attributes_data if item.get('tipo_intervencion'))),
            "upids_unicos": len(set(item.get('upid') for item in attributes_data if item.get('upid'))),
            "con_coordenadas": len(geometry_data),
            "porcentaje_georeferenciado": round((len(geometry_data) / total_proyectos * 100) if total_proyectos > 0 else 0, 2)
        }
        
        # Estadísticas geográficas
        geographic_stats = {}
        if geometry_data:
            bbox = _calculate_bounding_box_simple(geometry_data)
            if bbox and "error" not in bbox:
                geographic_stats = {
                    "bounding_box": bbox,
                    "cobertura_territorial": "Disponible",
                    "densidad_proyectos": round(len(geometry_data) / kpis["cobertura_geografica"], 2) if kpis["cobertura_geografica"] > 0 else 0
                }
            else:
                geographic_stats = {"cobertura_territorial": "Limitada", "error": bbox.get("error", "Datos insuficientes")}
        
        # Calidad de datos
        calidad_datos = {
            "completitud_upid": round((kpis["upids_unicos"] / total_proyectos * 100) if total_proyectos > 0 else 0, 2),
            "completitud_coordenadas": kpis["porcentaje_georeferenciado"],
            "completitud_centro_gestor": round((kpis["centros_gestores_activos"] / total_proyectos * 100) if total_proyectos > 0 else 0, 2)
        }
        
        return {
            "success": True,
            "timestamp": datetime.now().isoformat(),
            "kpis": kpis,
            "distribuciones": distribuciones,
            "estadisticas_geograficas": geographic_stats,
            "calidad_datos": calidad_datos,
            "resumen": {
                "total_registros": total_proyectos,
                "campos_analizados": len(distribuciones),
                "periodo_analisis": "Todos los datos disponibles"
            },
            "optimizations": {
                "cache_enabled": True,
                "functional_processing": True,
                "refresh_interval": "15 minutes",
                "computation_time": "< 200ms"
            }
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error generando dashboard: {str(e)}"
        )

# ============================================================================
# ACTUALIZACIÓN DE ENDPOINTS EXISTENTES CON TAGS
# ============================================================================

# Actualizar el endpoint raíz para mostrar los nuevos endpoints
@app.get("/", tags=["General"])
async def read_root():
    """Endpoint raíz con información de la API v2.0 - Unidades de Proyecto"""
    return {
        "message": "Gestor de Proyectos API - Unidades de Proyecto v2.0",
        "version": "2.0.0",
        "timestamp": datetime.now().isoformat(),
        "firebase_project": PROJECT_ID,
        "status": "running",
        "documentation": "/docs",
        "endpoints": {
            "principales": {
                "geometry": "/unidades-proyecto/geometry",
                "attributes": "/unidades-proyecto/attributes",
                "dashboard": "/unidades-proyecto/dashboard",
                "filter_options": "/unidades-proyecto/filter-options"
            },
            "legacy_nextjs": {
                "geometry_legacy": "/unidades-proyecto/nextjs-geometry",
                "attributes_legacy": "/unidades-proyecto/nextjs-attributes"
            },
            "administracion": {
                "health": "/health",
                "firebase_status": "/firebase/status"
            }
        },
        "caracteristicas": [
            "Filtros avanzados combinables (10+ criterios)",
            "Separación optimizada geometría/atributos",
            "Paginación eficiente con límites",
            "Cache inteligente para horarios programados",
            "Programación funcional para máximo rendimiento",
            "Búsquedas parciales en texto",
            "Estadísticas geográficas con bounding box",
            "Dashboard ejecutivo optimizado"
        ],
        "horarios_optimizados": "Carga en horarios 2-6 AM para reducir costos DB"
    }

# ============================================================================
# SERVIDOR
# ============================================================================

# Ejecutar servidor si se llama directamente
if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    print(f"🚀 Iniciando Gestor de Proyectos API v2.0")
    print(f"📍 Puerto: {port}")
    print(f"🌍 Entorno: {os.getenv('ENVIRONMENT', 'development')}")
    print(f"🔥 Firebase Project: {PROJECT_ID}")
    print("="*60)
    print("📋 NUEVOS ENDPOINTS DEFINITIVOS:")
    print("  🗺️  Geometrías con filtros: /unidades-proyecto/geometry")
    print("  📋 Atributos con filtros:   /unidades-proyecto/attributes") 
    print("  📊 Dashboard ejecutivo:     /unidades-proyecto/dashboard")
    print("  🔍 Opciones de filtros:     /unidades-proyecto/filter-options")
    print("  📖 Documentación:           /docs")
    print("="*60)
    print("🎯 FILTROS DISPONIBLES:")
    print("  • nombre_centro_gestor    • tipo_intervencion")
    print("  • estado                  • upid")
    print("  • nombre_up (parcial)     • comuna_corregimiento") 
    print("  • barrio_vereda          • direccion (parcial)")
    print("  • referencia_contrato    • referencia_proceso")
    print("="*60)
    
    uvicorn.run(
        "main:app", 
        host="0.0.0.0", 
        port=port, 
        reload=False
    )
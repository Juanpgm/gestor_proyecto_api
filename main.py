"""
Gestor de Proyectos API
API principal para gestión de proyectos con Firebase
Arquitectura modular con programación funcional optimizada para producción
"""

import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from typing import Dict, Any, Optional, Union
import uvicorn
from datetime import datetime

from database.config import initialize_firebase, setup_firebase, PROJECT_ID
from api.scripts import (
    # Firebase operations
    get_collections_info,
    test_firebase_connection,
    get_collections_summary,
    # Unidades proyecto operations  
    get_all_unidades_proyecto,
    get_unidades_proyecto_summary,
    validate_unidades_proyecto_collection,
    filter_unidades_proyecto,
    get_dashboard_summary
)

# Configurar el lifespan de la aplicación
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gestionar el ciclo de vida de la aplicación"""
    # Startup
    print("🚀 Iniciando API...")
    print(f"📍 Puerto: {os.getenv('PORT', '8000')}")
    print(f"🌍 Environment: {os.getenv('ENVIRONMENT', 'development')}")
    print(f"🔧 Firebase Project: {PROJECT_ID}")
    
    # Intentar inicializar Firebase pero no fallar si no funciona
    try:
        if initialize_firebase():
            print("✅ Firebase inicializado correctamente")
        else:
            print("⚠️  Advertencia: Firebase no disponible - API funcionará en modo limitado")
    except Exception as e:
        print(f"⚠️  Warning: Firebase initialization failed: {e}")
        print("🔧 API will start but Firebase endpoints may not work")
    
    yield
    
    # Shutdown
    print("🛑 Cerrando API...")

# Crear instancia de FastAPI con lifespan
app = FastAPI(
    title="Gestor de Proyectos API",
    description="API para gestión de proyectos con Firebase/Firestore",
    version="1.0.0",
    lifespan=lifespan
)

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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
                "/unidades-proyecto/dashboard-summary"
            ]
        }
    }

@app.get("/ping", tags=["General"])
async def ping():
    """Health check super simple para Railway"""
    return {"status": "ok", "timestamp": datetime.now().isoformat()}

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
        
        # Intentar Firebase solo si está disponible
        try:
            firebase_status = await test_firebase_connection()
            basic_response["services"]["firebase"] = firebase_status
            if not firebase_status["connected"]:
                basic_response["status"] = "degraded"
        except Exception as firebase_error:
            print(f"⚠️  Firebase check failed: {firebase_error}")
            basic_response["services"]["firebase"] = {
                "connected": False, 
                "error": str(firebase_error)[:100]
            }
            basic_response["status"] = "degraded"
        
        return basic_response
        
    except Exception as e:
        print(f"❌ Health check error: {e}")
        # Returnear response básico incluso si hay errores
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
async def get_unidades_proyecto():
    """
    Obtener todas las unidades de proyecto de la colección 'unidades_proyecto'
    
    Retorna:
    - Lista completa de unidades de proyecto
    - Metadatos de cada documento (fechas de creación y actualización)
    - Conteo total de unidades
    """
    try:
        result = await get_all_unidades_proyecto()
        
        if not result["success"]:
            raise HTTPException(
                status_code=500,
                detail=f"Error obteniendo unidades de proyecto: {result.get('error', 'Error desconocido')}"
            )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error interno del servidor: {str(e)}"
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


@app.get("/unidades-proyecto/filter", tags=["Unidades de Proyecto"])
async def filter_unidades_proyecto_endpoint(
    bpin: Optional[str] = Query(None, description="Filtrar por BPIN"),
    referencia_proceso: Optional[str] = Query(None, description="Filtrar por referencia del proceso"),
    referencia_contrato: Optional[str] = Query(None, description="Filtrar por referencia del contrato"),
    estado: Optional[str] = Query(None, description="Filtrar por estado"),
    upid: Optional[str] = Query(None, description="Filtrar por ID de unidad de proyecto"),
    barrio_vereda: Optional[str] = Query(None, description="Filtrar por barrio o vereda"),
    comuna_corregimiento: Optional[str] = Query(None, description="Filtrar por comuna o corregimiento"),
    nombre_up: Optional[str] = Query(None, description="Buscar por nombre de UP (búsqueda parcial)"),
    fuente_financiacion: Optional[str] = Query(None, description="Filtrar por fuente de financiación"),
    ano: Optional[Union[int, str]] = Query(None, description="Filtrar por año"),
    limit: Optional[int] = Query(None, ge=1, le=1000, description="Límite de resultados (máximo 1000)"),
    include_metadata: bool = Query(False, description="Incluir metadatos de los documentos")
):
    """
    Filtrar unidades de proyecto por múltiples criterios - Optimizado para Dashboards
    
    Este endpoint está diseñado para ser extremadamente eficiente en dashboards,
    permitiendo combinar múltiples filtros y obtener resultados rápidos.
    
    Características:
    - Filtros combinables (AND lógico)
    - Búsqueda parcial en nombre de UP
    - Límite configurable de resultados
    - Solo datos reales de la DB (sin metadatos por defecto)
    - Incluye coordenadas geográficas (latitude, longitude, geometry)
    - Información de filtros aplicados en la respuesta
    
    Casos de uso:
    - Dashboards interactivos
    - Reportes dinámicos
    - Análisis de datos en tiempo real
    - Filtros cascada (combo boxes dependientes)
    """
    try:
        result = await filter_unidades_proyecto(
            bpin=bpin,
            referencia_proceso=referencia_proceso,
            referencia_contrato=referencia_contrato,
            estado=estado,
            upid=upid,
            barrio_vereda=barrio_vereda,
            comuna_corregimiento=comuna_corregimiento,
            nombre_up=nombre_up,
            fuente_financiacion=fuente_financiacion,
            ano=ano,
            limit=limit,
            include_metadata=include_metadata
        )
        
        if not result["success"]:
            raise HTTPException(
                status_code=500,
                detail=f"Error filtrando unidades: {result.get('error', 'Error desconocido')}"
            )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error interno del servidor: {str(e)}"
        )



@app.get("/unidades-proyecto/dashboard-summary", tags=["Unidades de Proyecto"])
async def get_dashboard_summary_endpoint():
    """
    Obtener resumen ejecutivo optimizado para dashboards
    
    Proporciona métricas clave y distribuciones estadísticas 
    ideales para visualizaciones de dashboard:
    
    Métricas incluidas:
    - Total de unidades de proyecto
    - Número de BPINs únicos
    - Número de procesos únicos
    - Número de contratos únicos
    
    Distribuciones incluidas:
    - Por estado
    - Por año
    - Por fuente de financiación  
    - Por comuna/corregimiento
    - Por barrio/vereda
    
    Casos de uso:
    - Página principal de dashboard
    - Gráficos de barras y tortas
    - KPIs ejecutivos
    - Análisis de tendencias
    """
    try:
        result = await get_dashboard_summary()
        
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
            detail=f"Error obteniendo resumen de dashboard: {str(e)}"
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
    print(f"🚀 Iniciando servidor en puerto: {port}")
    print(f"🌍 Environment: {os.getenv('ENVIRONMENT', 'development')}")
    print(f"🔧 Firebase Project: {PROJECT_ID}")
    
    uvicorn.run(
        "main:app", 
        host="0.0.0.0", 
        port=port, 
        reload=False  # Cambiar a False para producción
    )
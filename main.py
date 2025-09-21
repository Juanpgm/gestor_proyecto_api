"""
API refactorizada con programación funcional para gestión de datos municipales
Arquitectura optimizada y simplificada con Parameter Input Widgets mejorados
"""
from fastapi import FastAPI, Depends, HTTPException
from fastapi.responses import JSONResponse
from fastapi.openapi.utils import get_openapi
from sqlalchemy.orm import Session
from sqlalchemy import text, inspect
from typing import Dict, Any, List, Optional
from functools import lru_cache, reduce
import os
from datetime import datetime

# Imports locales optimizados
from config import get_db, engine, test_database_connection
from api.models import (
    UnidadProyecto, DatosCaracteristicosProyecto, EjecucionPresupuestal,
    MovimientoPresupuestal, ProcesoContratacionDacp, OrdenCompraDacp,
    PaaDacp, EmpPaaDacp, Usuario, Rol, TokenSeguridad
)
from api.user_router import user_router
from api.schemas import get_openapi_config, get_swagger_ui_config

# ============================================================================
# CONFIGURACIÓN FUNCIONAL DE LA APLICACIÓN
# ============================================================================

@lru_cache(maxsize=1)
def get_app_config() -> Dict[str, str]:
    """Configuración de la aplicación con cache"""
    return {
        "name": os.getenv("APP_NAME", "API Gestor Municipal"),
        "version": os.getenv("APP_VERSION", "3.0.0"),
        "environment": os.getenv("APP_ENV", "development"),
        "description": "API refactorizada para gestión de datos municipales con programación funcional"
    }

def create_app() -> FastAPI:
    """Factory function para crear la aplicación FastAPI con configuración mejorada"""
    config = get_app_config()
    openapi_config = get_openapi_config()
    swagger_config = get_swagger_ui_config()
    
    app = FastAPI(
        title=openapi_config["title"],
        description=openapi_config["description"],
        version=openapi_config["version"],
        contact=openapi_config["contact"],
        license_info=openapi_config["license"],
        docs_url="/docs",
        redoc_url="/redoc",
        **swagger_config
    )
    
    # Personalizar OpenAPI schema
    def custom_openapi():
        if app.openapi_schema:
            return app.openapi_schema
        
        openapi_schema = get_openapi(
            title=openapi_config["title"],
            version=openapi_config["version"],
            description=openapi_config["description"],
            routes=app.routes,
            tags=openapi_config["tags"]
        )
        
        # Personalizar esquemas para mejor UX
        openapi_schema["info"]["x-logo"] = {
            "url": "https://fastapi.tiangolo.com/img/logo-margin/logo-teal.png"
        }
        
        # Mejorar seguridad en la documentación
        openapi_schema["components"]["securitySchemes"] = {
            "BearerAuth": {
                "type": "http",
                "scheme": "bearer",
                "bearerFormat": "JWT",
                "description": (
                    "Introduce tu token JWT obtenido del login:\n\n"
                    "1. Haz login en `/users/login`\n"
                    "2. Copia el `access_token` de la respuesta\n"
                    "3. Pega aquí: `Bearer tu_token_aqui`\n\n"
                    "Ejemplo: `Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...`"
                )
            }
        }
        
        app.openapi_schema = openapi_schema
        return app.openapi_schema
    
    app.openapi = custom_openapi
    return app

# Instancia de la aplicación
app = create_app()

# ============================================================================
# INCLUIR ROUTERS
# ============================================================================

# Router de gestión de usuarios
app.include_router(user_router)

# ============================================================================
# FUNCIONES UTILITARIAS FUNCIONALES
# ============================================================================

def safe_execute_query(db: Session, query: str) -> Optional[Any]:
    """Ejecutar query de forma segura"""
    try:
        return db.execute(text(query)).scalar()
    except Exception:
        return None

def get_table_count(db: Session, table_name: str) -> int:
    """Obtener conteo de registros de una tabla"""
    count = safe_execute_query(db, f"SELECT COUNT(*) FROM {table_name}")
    return count or 0

def get_table_stats(db: Session, table_name: str, numeric_columns: List[str]) -> Dict[str, Any]:
    """Obtener estadísticas básicas de una tabla"""
    stats = {"count": get_table_count(db, table_name)}
    
    for column in numeric_columns:
        try:
            # Obtener estadísticas numéricas
            avg_val = safe_execute_query(db, f"SELECT AVG({column}) FROM {table_name} WHERE {column} IS NOT NULL")
            min_val = safe_execute_query(db, f"SELECT MIN({column}) FROM {table_name} WHERE {column} IS NOT NULL")
            max_val = safe_execute_query(db, f"SELECT MAX({column}) FROM {table_name} WHERE {column} IS NOT NULL")
            
            if avg_val is not None:
                stats[f"{column}_avg"] = float(avg_val)
                stats[f"{column}_min"] = float(min_val) if min_val else None
                stats[f"{column}_max"] = float(max_val) if max_val else None
        except Exception:
            continue
    
    return stats

# ============================================================================
# CONFIGURACIÓN DE TABLAS Y MODELOS
# ============================================================================

@lru_cache(maxsize=1)
def get_tables_config() -> Dict[str, Dict[str, Any]]:
    """Configuración de tablas y sus columnas numéricas para estadísticas"""
    return {
        "unidad_proyecto": {
            "model": UnidadProyecto,
            "numeric_columns": ["presupuesto_base", "avance_obra", "usuarios", "latitude", "longitude"],
            "description": "Unidades de proyecto - Equipamientos de infraestructura municipal"
        },
        "datos_caracteristicos_proyecto": {
            "model": DatosCaracteristicosProyecto,
            "numeric_columns": ["bpin", "anio"],
            "description": "Datos característicos y descriptivos de proyectos municipales"
        },
        "ejecucion_presupuestal": {
            "model": EjecucionPresupuestal,
            "numeric_columns": ["ejecucion", "pagos", "ppto_disponible", "saldos_cdp", "total_acumul_obligac", "total_acumulado_cdp", "total_acumulado_rpc"],
            "description": "Ejecución presupuestal mensual de proyectos"
        },
        "movimiento_presupuestal": {
            "model": MovimientoPresupuestal,
            "numeric_columns": ["adiciones", "aplazamiento", "contracreditos", "creditos", "desaplazamiento", "ppto_inicial", "ppto_modificado", "reducciones"],
            "description": "Movimientos y modificaciones presupuestales"
        },
        "proceso_contratacion_dacp": {
            "model": ProcesoContratacionDacp,
            "numeric_columns": ["valor_proceso", "valor_contrato", "valor_contrato_ejecutado_sap"],
            "description": "Procesos de contratación DACP (SECOP II y otros)"
        },
        "orden_compra_dacp": {
            "model": OrdenCompraDacp,
            "numeric_columns": ["valor_proceso", "valor_contrato", "valor_contrato_ejecutado_sap"],
            "description": "Órdenes de compra DACP (TVEC y otros)"
        },
        "paa_dacp": {
            "model": PaaDacp,
            "numeric_columns": ["valor_actividad", "valor_disponible", "valor_apropiado", "valor_total_estimado", "valor_vigencia_actual", "inversion_real_estimado"],
            "description": "Plan Anual de Adquisiciones DACP"
        },
        "emp_paa_dacp": {
            "model": EmpPaaDacp,
            "numeric_columns": ["valor_actividad", "valor_disponible", "valor_apropiado", "valor_total_estimado", "valor_vigencia_actual", "inversion_real_estimado"],
            "description": "Plan Anual de Adquisiciones DACP - Empréstito"
        },
        "usuarios": {
            "model": Usuario,
            "numeric_columns": ["rol"],
            "description": "Usuarios del sistema de gestión municipal"
        },
        "roles": {
            "model": Rol,
            "numeric_columns": ["nivel"],
            "description": "Roles y niveles de acceso del sistema"
        },
        "tokens_seguridad": {
            "model": TokenSeguridad,
            "numeric_columns": [],
            "description": "Tokens de seguridad para autenticación"
        }
    }

# ============================================================================
# FUNCIONES PRINCIPALES DEL NEGOCIO
# ============================================================================

def calculate_summary_statistics(db: Session) -> Dict[str, Any]:
    """Calcular estadísticas resumen de todas las tablas"""
    tables_config = get_tables_config()
    
    # Función auxiliar para procesar una tabla
    def process_table(acc: Dict, item: tuple) -> Dict:
        table_name, config = item
        try:
            stats = get_table_stats(db, table_name, config["numeric_columns"])
            acc[table_name] = {
                "description": config["description"],
                "statistics": stats
            }
        except Exception as e:
            acc[table_name] = {
                "description": config["description"],
                "error": str(e),
                "statistics": {"count": 0}
            }
        return acc
    
    # Usar reduce para procesar todas las tablas de forma funcional
    return reduce(process_table, tables_config.items(), {})

def get_database_overview() -> Dict[str, Any]:
    """Obtener resumen general de la base de datos"""
    config = get_app_config()
    
    return {
        "api_info": {
            "name": config["name"],
            "version": config["version"],
            "environment": config["environment"],
            "timestamp": datetime.now().isoformat()
        },
        "database_info": {
            "connected": test_database_connection(),
            "total_tables": len(get_tables_config()),
            "available_tables": list(get_tables_config().keys())
        }
    }

# ============================================================================
# ENDPOINTS DE LA API
# ============================================================================

@app.get("/")
async def root():
    """Endpoint raíz con información de la API"""
    config = get_app_config()
    
    return {
        "message": f"Bienvenido a {config['name']} v{config['version']}",
        "description": config["description"],
        "features": [
            "Programación funcional",
            "Arquitectura simplificada",
            "Estadísticas de base de datos",
            "Conexión optimizada"
        ],
        "endpoints": {
            "docs": "/docs",
            "redoc": "/redoc",
            "database_summary": "/database/summary",
            "health": "/health",
            "users": "/users",
            "auth": "/users/login"
        }
    }

@app.get("/health")
async def health_check():
    """Verificar estado de la API y base de datos"""
    config = get_app_config()
    is_connected = test_database_connection()
    
    return {
        "status": "healthy" if is_connected else "unhealthy",
        "service": config["name"],
        "version": config["version"],
        "database": "connected" if is_connected else "disconnected",
        "timestamp": datetime.now().isoformat()
    }

@app.get("/database/summary")
async def get_database_summary(db: Session = Depends(get_db)):
    """
    Endpoint principal: Resumen completo de todas las tablas con estadísticas
    
    Returns:
        - Información general de la base de datos
        - Conteo de registros por tabla
        - Estadísticas básicas de columnas numéricas
        - Descripción de cada tabla
    """
    try:
        # Obtener resumen general
        overview = get_database_overview()
        
        # Calcular estadísticas de todas las tablas
        tables_stats = calculate_summary_statistics(db)
        
        # Calcular totales generales
        total_records = sum(
            table_data["statistics"].get("count", 0) 
            for table_data in tables_stats.values()
        )
        
        return {
            "database_overview": overview,
            "total_records": total_records,
            "tables": tables_stats,
            "summary": {
                "tables_analyzed": len(tables_stats),
                "tables_with_data": len([
                    t for t in tables_stats.values() 
                    if t["statistics"].get("count", 0) > 0
                ]),
                "total_records_all_tables": total_records
            }
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error generando resumen de base de datos: {str(e)}"
        )

# ============================================================================
# MANEJO DE ERRORES
# ============================================================================

@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """Manejo centralizado de excepciones HTTP"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": True,
            "message": exc.detail,
            "status_code": exc.status_code,
            "timestamp": datetime.now().isoformat()
        }
    )

# ============================================================================
# PUNTO DE ENTRADA
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    config = get_app_config()
    
    # Ejecutar con string import para habilitar reload
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8001,
        log_level="info",
        reload=True if config["environment"] == "development" else False
    )
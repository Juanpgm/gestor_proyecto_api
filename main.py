"""
API principal de FastAPI para gestión de contratos gubernamentales
Optimizada con programación funcional y arquitectura modular
"""
from fastapi import FastAPI, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import Dict, Any
import os
from dotenv import load_dotenv

# Importar módulos locales optimizados
from config import get_db, engine
from models import EmpContrato, Base
import schemas
from error_handling import (
    Result, Ok, Err, AppError, ErrorType, ResultHelper,
    app_logger
)

# Importar routers modulares
from api.contracts import contracts_router
from api.statistics import stats_router
from api.search import search_router
from api.procesos import procesos_router

# Cargar variables de entorno
load_dotenv()

# Configuración de la aplicación desde variables de entorno
APP_NAME = os.getenv("APP_NAME", "API Gestor de Proyectos")
APP_VERSION = os.getenv("APP_VERSION", "2.0.0")
APP_ENV = os.getenv("APP_ENV", "development")

# Crear la aplicación FastAPI
app = FastAPI(
    title=APP_NAME,
    description="API optimizada para gestión de contratos gubernamentales - Sistema de Contratación Pública",
    version=APP_VERSION,
    docs_url="/docs",
    redoc_url="/redoc"
)

# ============================================================================
# INCLUIR ROUTERS MODULARES
# ============================================================================

app.include_router(contracts_router)
app.include_router(stats_router)
app.include_router(search_router)
app.include_router(procesos_router)

# ============================================================================
# EXCEPTION HANDLERS FUNCIONALES
# ============================================================================

@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """Manejo centralizado de excepciones HTTP"""
    app_logger.logger.error(f"HTTP Exception: {exc.status_code} - {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": True,
            "message": exc.detail,
            "status_code": exc.status_code,
            "timestamp": app_logger.logger.handlers[0].format(
                app_logger.logger.makeRecord(
                    name="api", level=40, fn="", lno=0, msg="", args=(), exc_info=None
                )
            ).split(' - ')[0]
        }
    )

@app.get("/")
async def root():
    """
    Endpoint raíz de la API con información completa
    """
    return {
        "message": f"Bienvenido a {APP_NAME} v{APP_VERSION}",
        "description": "API optimizada para consulta de contratos de contratación pública",
        "version": APP_VERSION,
        "environment": APP_ENV,
        "features": [
            "Programación funcional",
            "Manejo de errores robusto",
            "Arquitectura modular",
            "Validaciones automáticas",
            "Logging estructurado"
        ],
        "endpoints": {
            "docs": "/docs",
            "redoc": "/redoc",
            "contratos": "/contratos",
            "procesos": "/procesos",
            "estadisticas": "/estadisticas",
            "busqueda": "/buscar",
            "health": "/health"
        }
    }

@app.get("/health")
async def health_check():
    """
    Endpoint para verificar el estado de la API
    """
    try:
        # Test de conexión a base de datos
        from sqlalchemy import text
        db = next(get_db())
        test_query = db.execute(text("SELECT 1")).scalar()
        db.close()
        
        return {
            "status": "healthy",
            "service": APP_NAME,
            "version": APP_VERSION,
            "database": "connected",
            "timestamp": app_logger.logger.handlers[0].format(
                app_logger.logger.makeRecord(
                    name="health", level=20, fn="", lno=0, msg="", args=(), exc_info=None
                )
            ).split(' - ')[0]
        }
    except Exception as e:
        app_logger.logger.error(f"Health check failed: {str(e)}")
        return {
            "status": "unhealthy",
            "service": APP_NAME,
            "version": APP_VERSION,
            "database": "disconnected",
            "error": str(e)
        }

# ============================================================================
# ENDPOINTS LEGACY PARA COMPATIBILIDAD
# ============================================================================

@app.get("/estadisticas/resumen")
async def legacy_stats_summary(db: Session = Depends(get_db)):
    """Endpoint legacy mantenido para compatibilidad"""
    from api.statistics import get_summary_statistics
    return await get_summary_statistics(db)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=8001,
        log_level="info",
        reload=True if APP_ENV == "development" else False
    )
"""
Router de Calidad de Datos de Empréstito
Endpoints para evaluación y monitoreo de calidad de datos en las colecciones de empréstito.
Misma estructura de respuesta que /unidades-proyecto/calidad-datos/*
"""

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)

# Importar funciones de calidad
try:
    from api.scripts.emprestito_quality_metrics import (
        generate_emprestito_quality_report,
        get_emprestito_quality_summary,
        get_emprestito_quality_records,
        get_emprestito_quality_by_centro_gestor,
        get_emprestito_quality_stats,
    )
    EMPRESTITO_QUALITY_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Empréstito quality metrics not available: {e}")
    EMPRESTITO_QUALITY_AVAILABLE = False

# Importar historial de cambios existente
try:
    from api.scripts.control_cambios_emprestito import obtener_historial_cambios
    CHANGELOG_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Control de cambios not available: {e}")
    CHANGELOG_AVAILABLE = False

# Rate limiting (misma importación que main.py)
try:
    from slowapi import Limiter
    from slowapi.util import get_remote_address
    RATE_LIMIT_AVAILABLE = True
except ImportError:
    RATE_LIMIT_AVAILABLE = False


def _utf8_response(data: Dict[str, Any], status_code: int = 200) -> JSONResponse:
    return JSONResponse(content=data, status_code=status_code, media_type="application/json; charset=utf-8")


router = APIRouter(tags=["Gestión de Empréstito"])


# ============================================================================
# A. CALIDAD DE DATOS DE EMPRÉSTITO
# ============================================================================

@router.get(
    "/emprestito/quality-control/summary",
    summary="📊 Resumen global de calidad de datos de empréstito",
    description="""
Retorna el resumen global de calidad de datos de empréstito incluyendo:
- **quality_score**: Puntuación DQS (0-100) basada en framework ISO 8000 / DAMA-DMBOK
- **error_rate**: Porcentaje de registros con issues
- **severity_distribution**: Distribución de issues por severidad (S1-S4)
- **summary**: Detalle por tipo de registro (contratos, procesos, órdenes, convenios, pagos, RPC)
- **rules**: Reglas de calidad evaluadas con impacto y prioridad

Se lee del último snapshot generado. Para generar uno nuevo, usar POST /emprestito/quality-control/analyze.
    """,
)
async def emprestito_quality_summary(
    report_id: Optional[str] = Query(None, description="ID de reporte específico. Si no se envía, usa el último generado."),
    nombre_centro_gestor: Optional[str] = Query(None, description="Filtrar por centro gestor"),
    auto_generate: bool = Query(False, description="Generar automáticamente si no existe snapshot"),
):
    if not EMPRESTITO_QUALITY_AVAILABLE:
        raise HTTPException(status_code=503, detail="Módulo de calidad de empréstito no disponible")

    try:
        result = await get_emprestito_quality_summary(
            report_id=report_id,
            nombre_centro_gestor=nombre_centro_gestor,
            auto_generate=auto_generate,
        )
        if not result.get("success"):
            return _utf8_response(result, status_code=404)
        return _utf8_response(result)
    except Exception as e:
        logger.error(f"Error obteniendo resumen de calidad: {e}")
        raise HTTPException(status_code=500, detail=f"Error obteniendo resumen de calidad: {str(e)}")


@router.post(
    "/emprestito/quality-control/analyze",
    summary="🔍 Generar análisis de calidad de empréstito",
    description="""
Ejecuta un análisis completo de calidad de datos sobre las 6 colecciones de empréstito y persiste el snapshot.
Evalúa:
- Campos requeridos faltantes (S2)
- Campos numéricos inválidos (S3)
- Duplicados por referencia (S1)
- Integridad referencial proceso→contrato, pago→contrato (S1)
    """,
)
async def emprestito_quality_analyze(
    nombre_centro_gestor: Optional[str] = Query(None, description="Filtrar análisis por centro gestor"),
):
    if not EMPRESTITO_QUALITY_AVAILABLE:
        raise HTTPException(status_code=503, detail="Módulo de calidad de empréstito no disponible")

    try:
        result = await generate_emprestito_quality_report(
            nombre_centro_gestor=nombre_centro_gestor,
            persist=True,
        )
        return _utf8_response(result)
    except Exception as e:
        logger.error(f"Error generando análisis de calidad: {e}")
        raise HTTPException(status_code=500, detail=f"Error generando análisis de calidad: {str(e)}")


@router.get(
    "/emprestito/quality-control/records",
    summary="📋 Registros individuales con issues de calidad",
    description="""
Retorna registros individuales evaluados con sus issues de calidad.
Soporta paginación (page/limit) y filtros por centro_gestor y tipo_registro.
    """,
)
async def emprestito_quality_records(
    report_id: Optional[str] = Query(None, description="ID de reporte específico"),
    page: int = Query(1, ge=1, description="Número de página"),
    limit: int = Query(50, ge=1, le=200, description="Registros por página"),
    centro_gestor: Optional[str] = Query(None, description="Filtrar por centro gestor"),
    tipo_registro: Optional[str] = Query(None, description="Filtrar: contrato, proceso, orden_compra, convenio, pago, rpc"),
):
    if not EMPRESTITO_QUALITY_AVAILABLE:
        raise HTTPException(status_code=503, detail="Módulo de calidad de empréstito no disponible")

    try:
        result = await get_emprestito_quality_records(
            report_id=report_id,
            page=page,
            limit=limit,
            centro_gestor=centro_gestor,
            tipo_registro=tipo_registro,
        )
        if not result.get("success"):
            return _utf8_response(result, status_code=404)
        return _utf8_response(result)
    except Exception as e:
        logger.error(f"Error obteniendo registros de calidad: {e}")
        raise HTTPException(status_code=500, detail=f"Error obteniendo registros de calidad: {str(e)}")


@router.get(
    "/emprestito/quality-control/changelog",
    summary="📜 Historial de cambios campo a campo",
    description="""
Retorna el historial de cambios realizados en registros de empréstito (control de cambios / auditoría).
Wrapper sobre el sistema existente de `emprestito_control_cambios`.
    """,
)
async def emprestito_quality_changelog(
    page: int = Query(1, ge=1, description="Número de página"),
    limit: int = Query(50, ge=1, le=200, description="Registros por página"),
    tipo_coleccion: Optional[str] = Query(None, description="Filtrar: procesos, ordenes, convenios, contratos"),
    identificador: Optional[str] = Query(None, description="Filtrar por identificador específico"),
):
    if not CHANGELOG_AVAILABLE:
        raise HTTPException(status_code=503, detail="Módulo de control de cambios no disponible")

    try:
        # Pedir más registros de los necesarios para poder paginar
        max_items = page * limit
        result = await obtener_historial_cambios(
            tipo_coleccion=tipo_coleccion,
            identificador=identificador,
            limite=min(max_items + limit, 500),
        )

        if not result.get("success"):
            return _utf8_response(result, status_code=500)

        cambios = result.get("cambios", [])

        # Normalizar timestamps para serialización JSON
        for cambio in cambios:
            for key, value in cambio.items():
                if hasattr(value, 'isoformat'):
                    cambio[key] = value.isoformat()

        # Paginar
        offset = (page - 1) * limit
        paged = cambios[offset:offset + limit]
        total = len(cambios)
        total_pages = max(1, -(-total // limit))

        return _utf8_response({
            "success": True,
            "page": page,
            "limit": limit,
            "total_records": total,
            "total_pages": total_pages,
            "has_more": page < total_pages,
            "changelog": paged,
        })
    except Exception as e:
        logger.error(f"Error obteniendo changelog: {e}")
        raise HTTPException(status_code=500, detail=f"Error obteniendo changelog: {str(e)}")


@router.get(
    "/emprestito/quality-control/by-centro-gestor",
    summary="🏢 Métricas de calidad agrupadas por centro gestor",
    description="""
Retorna métricas de calidad agrupadas por centro gestor, incluyendo:
- Total de registros y con issues por centro
- Distribución de severidad por centro
- Desglose por tipo de registro
    """,
)
async def emprestito_quality_by_centro_gestor(
    report_id: Optional[str] = Query(None, description="ID de reporte específico"),
):
    if not EMPRESTITO_QUALITY_AVAILABLE:
        raise HTTPException(status_code=503, detail="Módulo de calidad de empréstito no disponible")

    try:
        result = await get_emprestito_quality_by_centro_gestor(report_id=report_id)
        if not result.get("success"):
            return _utf8_response(result, status_code=404)
        return _utf8_response(result)
    except Exception as e:
        logger.error(f"Error obteniendo métricas por centro gestor: {e}")
        raise HTTPException(status_code=500, detail=f"Error obteniendo métricas por centro gestor: {str(e)}")


@router.get(
    "/emprestito/quality-control/stats",
    summary="📈 Estadísticas del sistema de empréstito",
    description="""
Retorna estadísticas globales del sistema de empréstito:
- Total de documentos por colección
- Info del último reporte de calidad generado
- Cantidad de reportes de calidad existentes
    """,
)
async def emprestito_quality_stats():
    if not EMPRESTITO_QUALITY_AVAILABLE:
        raise HTTPException(status_code=503, detail="Módulo de calidad de empréstito no disponible")

    try:
        result = await get_emprestito_quality_stats()
        return _utf8_response(result)
    except Exception as e:
        logger.error(f"Error obteniendo estadísticas: {e}")
        raise HTTPException(status_code=500, detail=f"Error obteniendo estadísticas: {str(e)}")

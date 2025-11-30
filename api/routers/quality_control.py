"""
Router de Control de Calidad de Unidades de Proyecto
Endpoints para gestión de registros de calidad en Firebase
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone

from database.firebase_config import get_firestore_client

router = APIRouter(prefix="/unidades-proyecto/quality-control", tags=["Unidades de Proyecto"])

# Nombres de colecciones
QC_COLLECTIONS = {
    "by_centro_gestor": "unidades_proyecto_quality_control_by_centro_gestor",
    "changelog": "unidades_proyecto_quality_control_changelog",
    "metadata": "unidades_proyecto_quality_control_metadata",
    "records": "unidades_proyecto_quality_control_records",
    "summary": "unidades_proyecto_quality_control_summary"
}


def clean_firebase_document(doc: Dict[str, Any]) -> Dict[str, Any]:
    """
    Limpia un documento de Firebase convirtiendo tipos especiales a JSON-serializables
    """
    try:
        from google.cloud.firestore_v1._helpers import DatetimeWithNanoseconds
    except ImportError:
        DatetimeWithNanoseconds = None
    
    cleaned = {}
    for key, value in doc.items():
        if DatetimeWithNanoseconds and isinstance(value, DatetimeWithNanoseconds):
            cleaned[key] = value.isoformat()
        elif isinstance(value, datetime):
            cleaned[key] = value.isoformat()
        elif isinstance(value, dict):
            cleaned[key] = clean_firebase_document(value)
        elif isinstance(value, list):
            cleaned[key] = [clean_firebase_document(item) if isinstance(item, dict) else item for item in value]
        else:
            cleaned[key] = value
    return cleaned


# ========== SUMMARY ENDPOINTS ==========

@router.get("/summary", response_model=dict)
async def get_quality_control_summary():
    """
    Obtener el resumen de control de calidad de unidades de proyecto (último reporte).
    
    Retorna el documento `latest` con el reporte más reciente de calidad,
    incluyendo métricas de comparación con el reporte anterior.
    
    **Colección**: `unidades_proyecto_quality_control_summary`
    
    **Campos principales:**
    - `report_id`: Identificador único del reporte
    - `global_quality_score`: Puntuación global de calidad (0-100)
    - `total_records_validated`: Total de registros validados
    - `total_issues_found`: Total de problemas encontrados
    - `records_with_issues`: Registros con al menos un problema
    - `records_without_issues`: Registros sin problemas
    - `error_rate`: Tasa de error en porcentaje
    - `system_status`: Estado del sistema (CRITICAL, WARNING, OK)
    - `requires_immediate_action`: Indica si requiere acción inmediata
    - `dimension_distribution`: Distribución de problemas por dimensión ISO 19157
    - `severity_distribution`: Distribución por severidad (CRITICAL, HIGH, MEDIUM, LOW)
    - `top_problematic_centros`: Top 10 centros gestores con más problemas
    - `top_quality_centros`: Top 10 centros gestores con mejor calidad
    - `centros_require_attention`: Cantidad de centros que requieren atención
    - `total_centros_gestores`: Total de centros gestores evaluados
    - `recommendations`: Recomendaciones priorizadas
    - `dimensions_evaluated`: Lista de dimensiones ISO 19157 evaluadas
    - `iso_standard`: Estándar ISO utilizado
    - `validation_engine_version`: Versión del motor de validación
    
    **Métricas de comparación (`comparison_with_previous`):**
    - `has_previous`: Indica si existe un reporte anterior para comparar
    - `previous_report_id`: ID del reporte anterior
    - `previous_timestamp`: Fecha del reporte anterior
    - `changes`: Cambios en métricas principales:
        - `quality_score`: Cambio en puntuación de calidad
        - `total_records`: Cambio en registros totales
        - `total_issues`: Cambio en total de problemas
        - `records_with_issues`: Cambio en registros con problemas
        - `error_rate`: Cambio en tasa de error
        - `centros_require_attention`: Cambio en centros que requieren atención
    - `severity_changes`: Cambios por nivel de severidad (CRITICAL, HIGH, MEDIUM, LOW, INFO)
    
    **Estructura de cada métrica de cambio:**
    - `value`: Valor actual
    - `previous`: Valor anterior
    - `change`: Diferencia absoluta (value - previous)
    - `change_percentage`: Cambio porcentual
    - `trend`: Tendencia (`improving`, `stable`, `worsening`)
    """
    try:
        db = get_firestore_client()
        if db is None:
            raise HTTPException(status_code=503, detail="Firestore no disponible")
        
        doc = db.collection(QC_COLLECTIONS["summary"]).document("latest").get()
        
        if not doc.exists:
            raise HTTPException(status_code=404, detail="No se encontró el reporte de calidad")
        
        doc_dict = doc.to_dict()
        doc_dict["id"] = doc.id
        cleaned_doc = clean_firebase_document(doc_dict)
        
        # Extraer resumen de tendencias y comparación
        has_comparison = False
        trends_summary = {}
        overall_trend = "stable"
        trends_count = {"improving": 0, "stable": 0, "worsening": 0}
        
        if "comparison_with_previous" in cleaned_doc:
            comp = cleaned_doc["comparison_with_previous"]
            has_comparison = comp.get("has_previous", False)
            
            if has_comparison and "changes" in comp:
                for key, change_data in comp["changes"].items():
                    if isinstance(change_data, dict):
                        trend = change_data.get("trend", "stable")
                        trends_summary[key] = {
                            "trend": trend,
                            "change": change_data.get("change", 0),
                            "change_percentage": change_data.get("change_percentage", 0)
                        }
                        if trend in trends_count:
                            trends_count[trend] += 1
                
                # Calcular tendencia general
                if any(trends_count.values()):
                    overall_trend = max(trends_count, key=trends_count.get)
        
        return {
            "success": True,
            "data": cleaned_doc,
            "collection": QC_COLLECTIONS["summary"],
            "has_comparison_data": has_comparison,
            "trends_summary": trends_summary if trends_summary else None,
            "overall_trend": overall_trend,
            "trends_count": trends_count if has_comparison else None,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error obteniendo resumen: {str(e)}")


# ========== RECORDS ENDPOINTS ==========

@router.get("/records", response_model=dict)
async def get_quality_control_records(
    upid: Optional[str] = Query(None, description="Filtrar por UPID"),
    nombre_centro_gestor: Optional[str] = Query(None, description="Filtrar por centro gestor"),
    tiene_issues: Optional[bool] = Query(None, description="Filtrar por registros con issues"),
    limit: Optional[int] = Query(None, ge=1, le=1000, description="Límite de resultados")
):
    """
    Obtener registros individuales de control de calidad.
    
    Esta colección contiene registros detallados de cada unidad de proyecto
    con información sobre su estado de validación y control de calidad.
    
    **Colección**: `unidades_proyecto_quality_control_records`
    """
    try:
        db = get_firestore_client()
        if db is None:
            raise HTTPException(status_code=503, detail="Firestore no disponible")
        
        collection_ref = db.collection(QC_COLLECTIONS["records"])
        query = collection_ref
        
        # Aplicar filtros
        if upid:
            query = query.where("upid", "==", upid)
        
        if nombre_centro_gestor:
            query = query.where("nombre_centro_gestor", "==", nombre_centro_gestor)
        
        if tiene_issues is not None:
            query = query.where("tiene_issues", "==", tiene_issues)
        
        if limit:
            query = query.limit(limit)
        
        # Ejecutar consulta
        docs = query.stream()
        
        data = []
        for doc in docs:
            doc_dict = doc.to_dict()
            doc_dict["id"] = doc.id
            data.append(clean_firebase_document(doc_dict))
        
        return {
            "success": True,
            "data": data,
            "count": len(data),
            "collection": QC_COLLECTIONS["records"],
            "filters_applied": {
                "upid": upid,
                "nombre_centro_gestor": nombre_centro_gestor,
                "tiene_issues": tiene_issues,
                "limit": limit
            },
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error obteniendo registros: {str(e)}")


@router.get("/records/{record_id}", response_model=dict)
async def get_quality_control_record_by_id(record_id: str):
    """
    Obtener un registro específico de control de calidad por su ID.
    
    **Colección**: `unidades_proyecto_quality_control_records`
    """
    try:
        db = get_firestore_client()
        if db is None:
            raise HTTPException(status_code=503, detail="Firestore no disponible")
        
        doc = db.collection(QC_COLLECTIONS["records"]).document(record_id).get()
        
        if not doc.exists:
            raise HTTPException(status_code=404, detail="Registro no encontrado")
        
        doc_dict = doc.to_dict()
        doc_dict["id"] = doc.id
        
        return {
            "success": True,
            "data": clean_firebase_document(doc_dict),
            "collection": QC_COLLECTIONS["records"],
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error obteniendo registro: {str(e)}")


# ========== CHANGELOG ENDPOINTS ==========

@router.get("/changelog", response_model=dict)
async def get_quality_control_changelog(
    upid: Optional[str] = Query(None, description="Filtrar por UPID"),
    action: Optional[str] = Query(None, description="Filtrar por tipo de acción"),
    limit: Optional[int] = Query(100, ge=1, le=1000, description="Límite de resultados")
):
    """
    Obtener historial de cambios en el control de calidad.
    
    Esta colección registra todos los cambios realizados en los registros
    de control de calidad, incluyendo quién los hizo y cuándo.
    
    **Colección**: `unidades_proyecto_quality_control_changelog`
    """
    try:
        db = get_firestore_client()
        if db is None:
            raise HTTPException(status_code=503, detail="Firestore no disponible")
        
        collection_ref = db.collection(QC_COLLECTIONS["changelog"])
        query = collection_ref.order_by("timestamp", direction="DESCENDING")
        
        # Aplicar filtros
        if upid:
            query = query.where("upid", "==", upid)
        
        if action:
            query = query.where("action", "==", action)
        
        if limit:
            query = query.limit(limit)
        
        # Ejecutar consulta
        docs = query.stream()
        
        data = []
        for doc in docs:
            doc_dict = doc.to_dict()
            doc_dict["id"] = doc.id
            data.append(clean_firebase_document(doc_dict))
        
        return {
            "success": True,
            "data": data,
            "count": len(data),
            "collection": QC_COLLECTIONS["changelog"],
            "filters_applied": {
                "upid": upid,
                "action": action,
                "limit": limit
            },
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error obteniendo changelog: {str(e)}")


# ========== BY CENTRO GESTOR ENDPOINTS ==========

@router.get("/by-centro-gestor", response_model=dict)
async def get_quality_control_by_centro_gestor(
    nombre_centro_gestor: Optional[str] = Query(None, description="Filtrar por centro gestor específico")
):
    """
    Obtener estadísticas de control de calidad agrupadas por centro gestor.
    
    Esta colección contiene métricas agregadas de calidad por cada centro gestor,
    útil para dashboards y reportes gerenciales.
    
    **Colección**: `unidades_proyecto_quality_control_by_centro_gestor`
    """
    try:
        db = get_firestore_client()
        if db is None:
            raise HTTPException(status_code=503, detail="Firestore no disponible")
        
        collection_ref = db.collection(QC_COLLECTIONS["by_centro_gestor"])
        query = collection_ref
        
        # Aplicar filtro si se especifica
        if nombre_centro_gestor:
            query = query.where("nombre_centro_gestor", "==", nombre_centro_gestor)
        
        # Ejecutar consulta
        docs = query.stream()
        
        data = []
        for doc in docs:
            doc_dict = doc.to_dict()
            doc_dict["id"] = doc.id
            data.append(clean_firebase_document(doc_dict))
        
        return {
            "success": True,
            "data": data,
            "count": len(data),
            "collection": QC_COLLECTIONS["by_centro_gestor"],
            "filters_applied": {
                "nombre_centro_gestor": nombre_centro_gestor
            },
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error obteniendo datos por centro gestor: {str(e)}")


@router.get("/by-centro-gestor/{centro_gestor_id}", response_model=dict)
async def get_quality_control_centro_gestor_by_id(centro_gestor_id: str):
    """
    Obtener estadísticas de un centro gestor específico por su ID.
    
    **Colección**: `unidades_proyecto_quality_control_by_centro_gestor`
    """
    try:
        db = get_firestore_client()
        if db is None:
            raise HTTPException(status_code=503, detail="Firestore no disponible")
        
        doc = db.collection(QC_COLLECTIONS["by_centro_gestor"]).document(centro_gestor_id).get()
        
        if not doc.exists:
            raise HTTPException(status_code=404, detail="Centro gestor no encontrado")
        
        doc_dict = doc.to_dict()
        doc_dict["id"] = doc.id
        
        return {
            "success": True,
            "data": clean_firebase_document(doc_dict),
            "collection": QC_COLLECTIONS["by_centro_gestor"],
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error obteniendo centro gestor: {str(e)}")


# ========== METADATA ENDPOINTS ==========

@router.get("/metadata", response_model=dict)
async def get_quality_control_metadata():
    """
    Obtener metadatos del sistema de control de calidad.
    
    Esta colección contiene información sobre la última actualización,
    configuración del sistema de validación, y estadísticas globales.
    
    **Colección**: `unidades_proyecto_quality_control_metadata`
    """
    try:
        db = get_firestore_client()
        if db is None:
            raise HTTPException(status_code=503, detail="Firestore no disponible")
        
        collection_ref = db.collection(QC_COLLECTIONS["metadata"])
        docs = collection_ref.stream()
        
        data = []
        for doc in docs:
            doc_dict = doc.to_dict()
            doc_dict["id"] = doc.id
            data.append(clean_firebase_document(doc_dict))
        
        return {
            "success": True,
            "data": data,
            "count": len(data),
            "collection": QC_COLLECTIONS["metadata"],
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error obteniendo metadata: {str(e)}")


@router.get("/metadata/{metadata_id}", response_model=dict)
async def get_quality_control_metadata_by_id(metadata_id: str):
    """
    Obtener metadatos específicos por ID.
    
    **Colección**: `unidades_proyecto_quality_control_metadata`
    """
    try:
        db = get_firestore_client()
        if db is None:
            raise HTTPException(status_code=503, detail="Firestore no disponible")
        
        doc = db.collection(QC_COLLECTIONS["metadata"]).document(metadata_id).get()
        
        if not doc.exists:
            raise HTTPException(status_code=404, detail="Metadata no encontrado")
        
        doc_dict = doc.to_dict()
        doc_dict["id"] = doc.id
        
        return {
            "success": True,
            "data": clean_firebase_document(doc_dict),
            "collection": QC_COLLECTIONS["metadata"],
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error obteniendo metadata: {str(e)}")


# ========== ESTADÍSTICAS GENERALES ==========

@router.get("/stats", response_model=dict)
async def get_quality_control_stats():
    """
    Obtener estadísticas generales del sistema de control de calidad.
    
    Retorna conteos de documentos en cada colección y métricas agregadas.
    """
    try:
        db = get_firestore_client()
        if db is None:
            raise HTTPException(status_code=503, detail="Firestore no disponible")
        
        stats = {}
        
        # Contar documentos en cada colección
        for key, collection_name in QC_COLLECTIONS.items():
            docs = list(db.collection(collection_name).stream())
            stats[key] = {
                "collection": collection_name,
                "count": len(docs)
            }
        
        return {
            "success": True,
            "data": stats,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error obteniendo estadísticas: {str(e)}")

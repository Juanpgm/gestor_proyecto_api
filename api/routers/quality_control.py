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
async def get_quality_control_summary(
    nombre_centro_gestor: Optional[str] = Query(None, description="Filtrar por centro gestor"),
    estado: Optional[str] = Query(None, description="Filtrar por estado"),
    limit: Optional[int] = Query(None, ge=1, le=1000, description="Límite de resultados")
):
    """
    Obtener resumen de control de calidad de unidades de proyecto.
    
    Esta colección contiene información resumida sobre el estado del control
    de calidad de las unidades de proyecto.
    
    **Colección**: `unidades_proyecto_quality_control_summary`
    """
    try:
        db = get_firestore_client()
        if db is None:
            raise HTTPException(status_code=503, detail="Firestore no disponible")
        
        collection_ref = db.collection(QC_COLLECTIONS["summary"])
        query = collection_ref
        
        # Aplicar filtros
        if nombre_centro_gestor:
            query = query.where("nombre_centro_gestor", "==", nombre_centro_gestor)
        
        if estado:
            query = query.where("estado", "==", estado)
        
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
            "collection": QC_COLLECTIONS["summary"],
            "filters_applied": {
                "nombre_centro_gestor": nombre_centro_gestor,
                "estado": estado,
                "limit": limit
            },
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
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

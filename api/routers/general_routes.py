# -*- coding: utf-8 -*-
"""
api/routers/general_routes.py — Endpoints generales de la aplicacion.

Rutas expuestas:
    POST   /reportar-bug
    GET    /reportar-bug
    PUT    /reportar-bug/{registro_id}
    DELETE /reportar-bug/{registro_id}

    POST   /solicitar-escalada-privilegios
    GET    /solicitar-escalada-privilegios
    PUT    /solicitar-escalada-privilegios/{registro_id}
    DELETE /solicitar-escalada-privilegios/{registro_id}

    POST   /realizar-recomendacion
    GET    /realizar-recomendacion
    PUT    /realizar-recomendacion/{registro_id}
    DELETE /realizar-recomendacion/{registro_id}

    GET    /centros-gestores/nombres-unicos

    GET    /firebase/status
    GET    /firebase/collections
    GET    /firebase/collections/summary
"""

import logging
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter, Body, HTTPException, Query, Request

from api.core.cache import get_cache_key, get_from_cache, set_in_cache
from api.core.responses import (
    clean_firebase_data,
    create_utf8_response,
    payload_to_dict,
    timestamp_colombia_iso,
)
from api.core.security import optional_rate_limit
from api.models.general_models import (
    ActualizarRecomendacionRequest,
    RealizarRecomendacionRequest,
    ReportarBugRequest,
    SolicitarEscaladaPrivilegiosRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["General"])

# ---------------------------------------------------------------------------
# Firebase / scripts — importación segura
# ---------------------------------------------------------------------------
try:
    from database.firebase_config import (
        FIREBASE_AVAILABLE,
        get_firestore_client,
    )
except Exception:
    FIREBASE_AVAILABLE = False
    get_firestore_client = lambda: None

try:
    from api.scripts import (
        get_collections_info,
        get_collections_summary,
        get_unique_nombres_centros_gestores,
        test_firebase_connection,
    )

    SCRIPTS_AVAILABLE = True
except Exception:
    SCRIPTS_AVAILABLE = False
    get_collections_info = None
    get_collections_summary = None
    get_unique_nombres_centros_gestores = None
    test_firebase_connection = None


# ---------------------------------------------------------------------------
# Utilidades internas de CRUD genérico sobre Firestore
# ---------------------------------------------------------------------------


def _get_collection(collection_name: str):
    if not FIREBASE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Firebase no disponible")
    db = get_firestore_client()
    if db is None:
        raise HTTPException(status_code=503, detail="No se pudo conectar a Firestore")
    return db.collection(collection_name)


def _create_record(collection_name: str, payload: Optional[Any]) -> Dict[str, Any]:
    col = _get_collection(collection_name)
    data = payload_to_dict(payload)
    now = timestamp_colombia_iso()
    data.update({"timestamp": now, "created_at": now, "updated_at": now})
    doc_id = str(uuid.uuid4())
    col.document(doc_id).set(data)
    return {"success": True, "id": doc_id, "collection": collection_name, "data": data}


def _get_records(
    collection_name: str, registro_id: Optional[str], limit: int
) -> Dict[str, Any]:
    col = _get_collection(collection_name)
    if registro_id:
        doc = col.document(registro_id).get()
        if not doc.exists:
            raise HTTPException(
                status_code=404,
                detail=f"Registro no encontrado en {collection_name}: {registro_id}",
            )
        row = clean_firebase_data(doc.to_dict() or {})
        row["id"] = doc.id
        return {
            "success": True,
            "collection": collection_name,
            "count": 1,
            "data": [row],
        }
    docs = col.limit(limit).stream()
    data = []
    for doc in docs:
        row = clean_firebase_data(doc.to_dict() or {})
        row["id"] = doc.id
        data.append(row)
    return {
        "success": True,
        "collection": collection_name,
        "count": len(data),
        "data": data,
        "limit": limit,
    }


def _update_record(
    collection_name: str, registro_id: str, payload: Optional[Any]
) -> Dict[str, Any]:
    col = _get_collection(collection_name)
    doc_ref = col.document(registro_id)
    updates = payload_to_dict(payload)
    if not updates:
        raise HTTPException(
            status_code=400, detail="Debe enviar al menos un campo para actualizar"
        )
    updates["updated_at"] = timestamp_colombia_iso()
    try:
        # update() raises google.api_core.exceptions.NotFound if doc doesn't exist
        # — no pre-check read needed.
        doc_ref.update(updates)
    except Exception as exc:
        exc_name = type(exc).__name__
        if "NotFound" in exc_name or getattr(exc, "code", None) == 404:
            raise HTTPException(
                status_code=404,
                detail=f"Registro no encontrado en {collection_name}: {registro_id}",
            )
        raise
    # Return the merged payload without a second round-trip to Firestore.
    updated = clean_firebase_data({**updates, "id": registro_id})
    return {
        "success": True,
        "collection": collection_name,
        "id": registro_id,
        "data": updated,
    }


def _delete_record(collection_name: str, registro_id: str) -> Dict[str, Any]:
    col = _get_collection(collection_name)
    doc_ref = col.document(registro_id)
    # Delete directly — if the document doesn't exist Firestore silently succeeds,
    # so we verify existence only when we need to surface a 404 to the caller.
    snapshot = doc_ref.get()
    if not snapshot.exists:
        raise HTTPException(
            status_code=404,
            detail=f"Registro no encontrado en {collection_name}: {registro_id}",
        )
    doc_ref.delete()
    return {
        "success": True,
        "collection": collection_name,
        "id": registro_id,
        "deleted_at": timestamp_colombia_iso(),
    }


# ---------------------------------------------------------------------------
# Reportar Bug
# ---------------------------------------------------------------------------


@router.post("/reportar-bug", summary="Reportar Bug")
async def reportar_bug(
    payload: Optional[ReportarBugRequest] = Body(
        None, description="Campos opcionales del reporte de bug"
    )
):
    try:
        return create_utf8_response(_create_record("general_reportes_bug", payload))
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error reportando bug: {exc!s}")


@router.get("/reportar-bug", summary="Consultar Reportes de Bug")
async def get_reportes_bug(
    registro_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
):
    try:
        return create_utf8_response(
            _get_records("general_reportes_bug", registro_id, limit)
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Error consultando reportes: {exc!s}"
        )


@router.put("/reportar-bug/{registro_id}", summary="Actualizar Reporte de Bug")
async def update_reportar_bug(
    registro_id: str,
    payload: Optional[ReportarBugRequest] = Body(None),
):
    try:
        return create_utf8_response(
            _update_record("general_reportes_bug", registro_id, payload)
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Error actualizando reporte: {exc!s}"
        )


@router.delete("/reportar-bug/{registro_id}", summary="Eliminar Reporte de Bug")
async def delete_reportar_bug(registro_id: str):
    try:
        return create_utf8_response(_delete_record("general_reportes_bug", registro_id))
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Error eliminando reporte: {exc!s}"
        )


# ---------------------------------------------------------------------------
# Solicitar Escalada de Privilegios
# ---------------------------------------------------------------------------

_COL_ESCALADA = "general_solicitudes_escalada_privilegios"


@router.post(
    "/solicitar-escalada-privilegios", summary="Solicitar Escalada de Privilegios"
)
async def solicitar_escalada_privilegios(
    payload: Optional[SolicitarEscaladaPrivilegiosRequest] = Body(None),
):
    try:
        return create_utf8_response(_create_record(_COL_ESCALADA, payload))
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Error solicitando escalada: {exc!s}"
        )


@router.get(
    "/solicitar-escalada-privilegios", summary="Consultar Solicitudes de Escalada"
)
async def get_solicitudes_escalada_privilegios(
    registro_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
):
    try:
        return create_utf8_response(_get_records(_COL_ESCALADA, registro_id, limit))
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Error consultando solicitudes: {exc!s}"
        )


@router.put(
    "/solicitar-escalada-privilegios/{registro_id}",
    summary="Actualizar Solicitud de Escalada",
)
async def update_solicitar_escalada_privilegios(
    registro_id: str,
    payload: Optional[SolicitarEscaladaPrivilegiosRequest] = Body(None),
):
    try:
        return create_utf8_response(_update_record(_COL_ESCALADA, registro_id, payload))
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Error actualizando solicitud: {exc!s}"
        )


@router.delete(
    "/solicitar-escalada-privilegios/{registro_id}",
    summary="Eliminar Solicitud de Escalada",
)
async def delete_solicitar_escalada_privilegios(registro_id: str):
    try:
        return create_utf8_response(_delete_record(_COL_ESCALADA, registro_id))
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Error eliminando solicitud: {exc!s}"
        )


# ---------------------------------------------------------------------------
# Realizar Recomendacion
# ---------------------------------------------------------------------------

_COL_RECOMENDACIONES = "general_recomendaciones"


@router.post("/realizar-recomendacion", summary="Realizar Recomendacion")
async def realizar_recomendacion(payload: RealizarRecomendacionRequest = Body(...)):
    try:
        return create_utf8_response(_create_record(_COL_RECOMENDACIONES, payload))
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Error registrando recomendacion: {exc!s}"
        )


@router.get("/realizar-recomendacion", summary="Consultar Recomendaciones")
async def get_recomendaciones(
    registro_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
):
    try:
        return create_utf8_response(
            _get_records(_COL_RECOMENDACIONES, registro_id, limit)
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Error consultando recomendaciones: {exc!s}"
        )


@router.put("/realizar-recomendacion/{registro_id}", summary="Actualizar Recomendacion")
async def update_recomendacion(
    registro_id: str,
    payload: Optional[ActualizarRecomendacionRequest] = Body(None),
):
    try:
        return create_utf8_response(
            _update_record(_COL_RECOMENDACIONES, registro_id, payload)
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Error actualizando recomendacion: {exc!s}"
        )


@router.delete(
    "/realizar-recomendacion/{registro_id}", summary="Eliminar Recomendacion"
)
async def delete_recomendacion(registro_id: str):
    try:
        return create_utf8_response(_delete_record(_COL_RECOMENDACIONES, registro_id))
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Error eliminando recomendacion: {exc!s}"
        )


# ---------------------------------------------------------------------------
# Centros Gestores
# ---------------------------------------------------------------------------


@router.get("/centros-gestores/nombres-unicos")
async def get_all_nombres_centros_gestores_unique():
    """Retorna lista ordenada de nombres unicos de centros gestores."""
    if not FIREBASE_AVAILABLE or not SCRIPTS_AVAILABLE:
        raise HTTPException(status_code=503, detail="Firebase o scripts no disponibles")

    cache_key = get_cache_key("centros_gestores_unique")
    cached, valid = get_from_cache(cache_key, 600)
    if valid:
        return cached

    try:
        result = await get_unique_nombres_centros_gestores()
        if not result.get("success"):
            raise HTTPException(
                status_code=500,
                detail=result.get("error", "Error obteniendo centros gestores"),
            )
        set_in_cache(cache_key, result)
        return result
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error: {exc!s}")


# ---------------------------------------------------------------------------
# Firebase Status / Collections
# ---------------------------------------------------------------------------


@router.get("/firebase/status", tags=["Firebase"])
async def firebase_status():
    """Verificar estado de la conexion con Firebase."""
    cache_key = get_cache_key("firebase_status")
    cached, valid = get_from_cache(cache_key, 30)
    if valid:
        return cached

    if not FIREBASE_AVAILABLE:
        return {
            "connected": False,
            "error": "Firebase SDK not available",
            "status": "unavailable",
        }

    if not SCRIPTS_AVAILABLE or test_firebase_connection is None:
        return {
            "connected": False,
            "error": "Scripts not available",
            "status": "limited",
        }

    try:
        result = await test_firebase_connection()
        set_in_cache(cache_key, result)
        return result
    except Exception as exc:
        return {"connected": False, "error": str(exc), "status": "error"}


@router.get("/firebase/collections", tags=["Firebase"])
@optional_rate_limit("30/minute")
async def get_firebase_collections(request: Request):
    """Informacion completa de todas las colecciones de Firestore."""
    if not FIREBASE_AVAILABLE or not SCRIPTS_AVAILABLE:
        raise HTTPException(status_code=503, detail="Firebase o scripts no disponibles")

    cache_key = get_cache_key("firebase_collections")
    cached, valid = get_from_cache(cache_key, 300)
    if valid:
        return cached

    try:
        data = await get_collections_info(limit_docs_per_collection=10)
        if not data.get("success"):
            raise HTTPException(
                status_code=500,
                detail=data.get("error", "Error obteniendo colecciones"),
            )
        set_in_cache(cache_key, data)
        return data
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/firebase/collections/summary", tags=["Firebase"])
@optional_rate_limit("30/minute")
async def get_firebase_collections_summary(request: Request):
    """Resumen estadistico de las colecciones de Firestore."""
    if not FIREBASE_AVAILABLE or not SCRIPTS_AVAILABLE:
        raise HTTPException(status_code=503, detail="Firebase o scripts no disponibles")

    cache_key = get_cache_key("firebase_collections_summary")
    cached, valid = get_from_cache(cache_key, 300)
    if valid:
        return cached

    try:
        data = await get_collections_summary()
        if not data.get("success"):
            raise HTTPException(
                status_code=500, detail=data.get("error", "Error obteniendo resumen")
            )
        set_in_cache(cache_key, data)
        return data
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

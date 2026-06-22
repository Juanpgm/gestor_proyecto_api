"""
Router REST para el sistema de notificaciones de CaliTrack.

Endpoints:
  GET  /notificaciones                  — obtener notificaciones del usuario
  PATCH /notificaciones/{id}/leer       — marcar como leída
  DELETE /notificaciones/{id}           — eliminar
  GET  /notificaciones/count            — conteo de no leídas
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

_BOGOTA_TZ = timezone(timedelta(hours=-5))

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Notificaciones"])

NOTIFICACIONES_COLLECTION = "notificaciones"
TTL_LEIDAS_DIAS = 7  # Días hasta que expiran las notificaciones leídas


def _get_db():
    try:
        from database.firebase_config import get_firestore_client

        return get_firestore_client()
    except Exception as e:
        logger.warning(f"Firestore no disponible: {e}")
        return None


def _serialize(data: dict) -> dict:
    """Normaliza timestamps de Firestore a string ISO."""
    result = {}
    for k, v in data.items():
        if hasattr(v, "isoformat"):
            result[k] = v.isoformat()
        else:
            result[k] = v
    return result


def _is_expired(notif: dict) -> bool:
    """Retorna True si la notificación está leída y han pasado más de 7 días."""
    if not notif.get("leida"):
        return False
    leida_en = notif.get("leida_en")
    if not leida_en:
        return False
    try:
        ts = datetime.fromisoformat(str(leida_en))
        return datetime.now() - ts > timedelta(days=TTL_LEIDAS_DIAS)
    except Exception:
        return False


# ---------------------------------------------------------------------------
# GET /notificaciones
# ---------------------------------------------------------------------------


@router.get("/notificaciones", summary="Obtener notificaciones del usuario")
async def get_notificaciones(
    request: Request,
    role: str = Query(
        ...,
        description="Rol del usuario: admin_centro_gestor, admin_general, super_admin",
    ),
    centro_gestor: Optional[str] = Query(
        None,
        description="Nombre del centro gestor (requerido para admin_centro_gestor)",
    ),
    solo_no_leidas: bool = Query(
        False, description="Retorna solo notificaciones no leídas"
    ),
    limit: int = Query(50, ge=1, le=200),
):
    """
    Retorna las notificaciones correspondientes al usuario según su rol.

    - `admin_centro_gestor`: solo notificaciones de su centro gestor (solicitudes resueltas).
    - `admin_general` / `super_admin`: notificaciones de nuevas solicitudes.

    Las notificaciones leídas hace más de 7 días se excluyen automáticamente.
    """
    db = _get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="Base de datos no disponible")

    try:
        query = db.collection(NOTIFICACIONES_COLLECTION).where(
            "destinatario_role", "==", role.strip().lower()
        )

        docs = list(query.stream())

        notificaciones = []
        for doc in docs:
            data = _serialize(doc.to_dict() or {})
            data["id"] = doc.id

            # Filtrar por centro gestor para admin_centro_gestor
            if role.strip().lower() == "admin_centro_gestor" and centro_gestor:
                dest_cg = data.get("destinatario_centro_gestor") or ""
                if dest_cg.lower() != centro_gestor.strip().lower():
                    continue

            # Excluir expiradas
            if _is_expired(data):
                continue

            # Filtro opcional no leídas
            if solo_no_leidas and data.get("leida"):
                continue

            notificaciones.append(data)

        # Ordenar más recientes primero
        notificaciones.sort(key=lambda n: n.get("created_at", ""), reverse=True)

        # Limitar
        notificaciones = notificaciones[:limit]

        return JSONResponse(
            content={
                "success": True,
                "data": notificaciones,
                "count": len(notificaciones),
                "unread_count": sum(1 for n in notificaciones if not n.get("leida")),
            },
            status_code=200,
            headers={"Content-Type": "application/json; charset=utf-8"},
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error obteniendo notificaciones: {e}")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


# ---------------------------------------------------------------------------
# GET /notificaciones/count
# ---------------------------------------------------------------------------


@router.get("/notificaciones/count", summary="Contar notificaciones no leídas")
async def count_notificaciones(
    request: Request,
    role: str = Query(..., description="Rol del usuario"),
    centro_gestor: Optional[str] = Query(
        None, description="Centro gestor (para admin_centro_gestor)"
    ),
):
    """Retorna el conteo de notificaciones no leídas del usuario."""
    db = _get_db()
    if db is None:
        return JSONResponse(content={"success": True, "count": 0})

    try:
        query = (
            db.collection(NOTIFICACIONES_COLLECTION)
            .where("destinatario_role", "==", role.strip().lower())
            .where("leida", "==", False)
        )

        docs = list(query.stream())
        count = 0
        for doc in docs:
            data = _serialize(doc.to_dict() or {})
            if role.strip().lower() == "admin_centro_gestor" and centro_gestor:
                dest_cg = data.get("destinatario_centro_gestor") or ""
                if dest_cg.lower() != centro_gestor.strip().lower():
                    continue
            if not _is_expired(data):
                count += 1

        return JSONResponse(
            content={"success": True, "count": count},
            status_code=200,
        )
    except Exception as e:
        logger.error(f"Error contando notificaciones: {e}")
        return JSONResponse(content={"success": True, "count": 0})


# ---------------------------------------------------------------------------
# PATCH /notificaciones/{id}/leer
# ---------------------------------------------------------------------------


@router.patch(
    "/notificaciones/{notif_id}/leer", summary="Marcar notificación como leída"
)
async def marcar_leida(
    request: Request,
    notif_id: str,
):
    """
    Marca una notificación como leída y registra la fecha (para TTL de 7 días).
    """
    db = _get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="Base de datos no disponible")

    try:
        ref = db.collection(NOTIFICACIONES_COLLECTION).document(notif_id)
        doc = ref.get()

        if not doc.exists:
            raise HTTPException(status_code=404, detail="Notificación no encontrada")

        now_iso = datetime.now(tz=_BOGOTA_TZ).isoformat()
        ref.update({"leida": True, "leida_en": now_iso})

        return JSONResponse(
            content={
                "success": True,
                "id": notif_id,
                "leida": True,
                "leida_en": now_iso,
            },
            status_code=200,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error marcando notificación como leída: {e}")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


# ---------------------------------------------------------------------------
# DELETE /notificaciones/{id}
# ---------------------------------------------------------------------------


@router.delete("/notificaciones/{notif_id}", summary="Eliminar notificación")
async def eliminar_notificacion(
    request: Request,
    notif_id: str,
):
    """Elimina una notificación por ID."""
    db = _get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="Base de datos no disponible")

    try:
        ref = db.collection(NOTIFICACIONES_COLLECTION).document(notif_id)
        doc = ref.get()

        if not doc.exists:
            raise HTTPException(status_code=404, detail="Notificación no encontrada")

        ref.delete()

        return JSONResponse(
            content={"success": True, "id": notif_id, "deleted": True},
            status_code=200,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error eliminando notificación: {e}")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


# ---------------------------------------------------------------------------
# PATCH /notificaciones/leer-todas — marcar todas como leídas
# ---------------------------------------------------------------------------


@router.patch(
    "/notificaciones/leer-todas", summary="Marcar todas las notificaciones como leídas"
)
async def marcar_todas_leidas(
    request: Request,
    role: str = Query(..., description="Rol del usuario"),
    centro_gestor: Optional[str] = Query(None),
):
    """Marca todas las notificaciones no leídas del usuario como leídas."""
    db = _get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="Base de datos no disponible")

    try:
        query = (
            db.collection(NOTIFICACIONES_COLLECTION)
            .where("destinatario_role", "==", role.strip().lower())
            .where("leida", "==", False)
        )
        docs = list(query.stream())
        now_iso = datetime.now(tz=_BOGOTA_TZ).isoformat()
        count = 0
        pending = []

        for doc in docs:
            data = doc.to_dict() or {}
            if role.strip().lower() == "admin_centro_gestor" and centro_gestor:
                dest_cg = data.get("destinatario_centro_gestor") or ""
                if dest_cg.lower() != centro_gestor.strip().lower():
                    continue
            pending.append(doc.id)
            count += 1

        # Firestore batch limit is 500 writes
        for i in range(0, len(pending), 500):
            chunk = pending[i : i + 500]
            batch = db.batch()
            for doc_id in chunk:
                ref = db.collection(NOTIFICACIONES_COLLECTION).document(doc_id)
                batch.update(ref, {"leida": True, "leida_en": now_iso})
            batch.commit()

        return JSONResponse(
            content={"success": True, "marcadas": count},
            status_code=200,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error marcando todas como leídas: {e}")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

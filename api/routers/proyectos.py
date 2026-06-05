# -*- coding: utf-8 -*-
"""
api/routers/proyectos.py — Endpoints de Proyectos Presupuestales.

Rutas expuestas:
    GET /proyectos-presupuestales/all
    GET /proyectos-presupuestales/bpin/{bpin}
    GET /proyectos-presupuestales/bp/{bp}
    GET /proyectos-presupuestales/centro-gestor/{nombre_centro_gestor}
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, Request

from api.core.responses import create_utf8_response
from api.core.security import optional_rate_limit

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/proyectos-presupuestales",
    tags=["Proyectos de Inversion"],
)

# ---------------------------------------------------------------------------
# Importaciones seguras
# ---------------------------------------------------------------------------
try:
    from database.firebase_config import FIREBASE_AVAILABLE
except Exception:
    FIREBASE_AVAILABLE = False

try:
    from api.scripts import (
        get_proyectos_presupuestales,
        get_proyectos_presupuestales_by_bpin,
        get_proyectos_presupuestales_by_bp,
        get_proyectos_presupuestales_by_centro_gestor,
        PROYECTOS_PRESUPUESTALES_OPERATIONS_AVAILABLE,
    )
    SCRIPTS_AVAILABLE = bool(PROYECTOS_PRESUPUESTALES_OPERATIONS_AVAILABLE)
except Exception:
    SCRIPTS_AVAILABLE = False
    get_proyectos_presupuestales = None
    get_proyectos_presupuestales_by_bpin = None
    get_proyectos_presupuestales_by_bp = None
    get_proyectos_presupuestales_by_centro_gestor = None


# ---------------------------------------------------------------------------
# Utilidades internas
# ---------------------------------------------------------------------------

def _check_availability():
    if not FIREBASE_AVAILABLE or not SCRIPTS_AVAILABLE:
        raise HTTPException(status_code=503, detail="Firebase o scripts no disponibles")


def _apply_field_filter(data: List[Dict[str, Any]], campos: Optional[str]) -> List[Dict[str, Any]]:
    """Filtra los campos devueltos en cada registro."""
    if not campos:
        return data
    selected = [f.strip() for f in campos.split(",") if f.strip()]
    if not selected:
        return data
    if "id" not in selected:
        selected.append("id")
    return [{f: row.get(f) for f in selected if f in row} for row in data if isinstance(row, dict)]


def _build_pagination(limit: int, offset: int, count: int) -> Dict[str, Any]:
    return {"limit": limit, "offset": offset, "returned": count}


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/all", summary="Todos los Proyectos Presupuestales")
@optional_rate_limit("40/minute")
async def get_proyectos_all(
    request: Request,
    limit: int = Query(200, ge=1, le=5000),
    offset: int = Query(0, ge=0),
    campos: Optional[str] = Query(None, description="Campos separados por coma"),
):
    """Retorna todos los proyectos presupuestales con paginacion y filtrado de campos."""
    _check_availability()
    try:
        result = await get_proyectos_presupuestales(limit=limit, offset=offset if offset > 0 else None)
        if not result["success"]:
            raise HTTPException(status_code=500, detail=result.get("error", "Error desconocido"))

        data = _apply_field_filter(result["data"], campos)
        return {
            "success": True,
            "data": data,
            "count": len(data),
            "collection": result.get("collection"),
            "timestamp": result.get("timestamp"),
            "pagination": _build_pagination(limit, offset, len(data)),
            "message": f"Se obtuvieron {len(data)} proyectos presupuestales",
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error: {exc!s}")


@router.get("/bpin/{bpin}", summary="Proyectos por BPIN")
async def get_proyectos_by_bpin(
    bpin: str,
    limit: int = Query(200, ge=1, le=5000),
    offset: int = Query(0, ge=0),
    campos: Optional[str] = Query(None),
):
    """Retorna proyectos presupuestales filtrados por codigo BPIN especifico."""
    _check_availability()
    try:
        result = await get_proyectos_presupuestales_by_bpin(bpin, limit=limit, offset=offset)
        if not result["success"]:
            raise HTTPException(status_code=500, detail=result.get("error", "Error desconocido"))

        data = _apply_field_filter(result["data"], campos)
        return {
            "success": True,
            "data": data,
            "count": len(data),
            "collection": result.get("collection"),
            "filter": result.get("filter"),
            "timestamp": result.get("timestamp"),
            "pagination": _build_pagination(limit, offset, len(data)),
            "message": f"Se encontraron {len(data)} proyectos con BPIN '{bpin}'",
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error: {exc!s}")


@router.get("/bp/{bp}", summary="Proyectos por BP")
async def get_proyectos_by_bp(
    bp: str,
    limit: int = Query(200, ge=1, le=5000),
    offset: int = Query(0, ge=0),
    campos: Optional[str] = Query(None),
):
    """Retorna proyectos presupuestales filtrados por codigo BP especifico."""
    _check_availability()
    try:
        result = await get_proyectos_presupuestales_by_bp(bp, limit=limit, offset=offset)
        if not result["success"]:
            raise HTTPException(status_code=500, detail=result.get("error", "Error desconocido"))

        data = _apply_field_filter(result["data"], campos)
        return {
            "success": True,
            "data": data,
            "count": len(data),
            "collection": result.get("collection"),
            "filter": result.get("filter"),
            "timestamp": result.get("timestamp"),
            "pagination": _build_pagination(limit, offset, len(data)),
            "message": f"Se encontraron {len(data)} proyectos con BP '{bp}'",
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error: {exc!s}")


@router.get("/centro-gestor/{nombre_centro_gestor}", summary="Proyectos por Centro Gestor")
async def get_proyectos_by_centro_gestor(
    nombre_centro_gestor: str,
    limit: int = Query(200, ge=1, le=5000),
    offset: int = Query(0, ge=0),
    campos: Optional[str] = Query(None),
):
    """Retorna proyectos presupuestales de un centro gestor especifico."""
    _check_availability()
    try:
        result = await get_proyectos_presupuestales_by_centro_gestor(
            nombre_centro_gestor, limit=limit, offset=offset
        )
        if not result["success"]:
            raise HTTPException(status_code=500, detail=result.get("error", "Error desconocido"))

        data = _apply_field_filter(result["data"], campos)
        return {
            "success": True,
            "data": data,
            "count": len(data),
            "collection": result.get("collection"),
            "filter": result.get("filter"),
            "timestamp": result.get("timestamp"),
            "pagination": _build_pagination(limit, offset, len(data)),
            "message": f"Se encontraron {len(data)} proyectos para '{nombre_centro_gestor}'",
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error: {exc!s}")

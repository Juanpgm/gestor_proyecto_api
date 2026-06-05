# -*- coding: utf-8 -*-
"""
api/dependencies.py — Dependencias FastAPI reutilizables.

Uso:
    from api.dependencies import get_db, require_firebase

    @router.get("/data")
    async def endpoint(db=Depends(get_db)):
        ...
"""

import logging

from fastapi import Depends, HTTPException

logger = logging.getLogger(__name__)


def get_db():
    """
    Dependencia que retorna el cliente Firestore activo.

    Raises:
        HTTPException 503 — Firebase no disponible o cliente no inicializado
    """
    try:
        from database.firebase_config import get_firestore_client, FIREBASE_AVAILABLE

        if not FIREBASE_AVAILABLE:
            raise HTTPException(
                status_code=503,
                detail={
                    "success": False,
                    "error": "Firebase no disponible",
                    "code": "FIREBASE_UNAVAILABLE",
                },
            )

        db = get_firestore_client()
        if db is None:
            raise HTTPException(
                status_code=503,
                detail={
                    "success": False,
                    "error": "No se pudo conectar a Firestore",
                    "code": "FIRESTORE_CONNECTION_ERROR",
                },
            )
        return db
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"get_db dependency error: {exc}", exc_info=True)
        raise HTTPException(
            status_code=503,
            detail={
                "success": False,
                "error": f"Error de base de datos: {exc!s}",
                "code": "DB_ERROR",
            },
        )


def require_firebase():
    """
    Dependencia que verifica que Firebase y los scripts estén disponibles.
    Retorna (FIREBASE_AVAILABLE, SCRIPTS_AVAILABLE) como tupla.
    """
    try:
        from database.firebase_config import FIREBASE_AVAILABLE

        try:
            from api.scripts import EMPRESTITO_OPERATIONS_AVAILABLE as _
            SCRIPTS_AVAILABLE = True
        except Exception:
            SCRIPTS_AVAILABLE = False

        if not FIREBASE_AVAILABLE or not SCRIPTS_AVAILABLE:
            raise HTTPException(
                status_code=503,
                detail={
                    "success": False,
                    "error": "Firebase o scripts no disponibles",
                    "code": "DEPENDENCIES_UNAVAILABLE",
                },
            )
        return FIREBASE_AVAILABLE, SCRIPTS_AVAILABLE
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc))

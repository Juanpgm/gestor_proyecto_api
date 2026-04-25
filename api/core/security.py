# -*- coding: utf-8 -*-
"""
api/core/security.py — Seguridad, autenticación y rate-limiting.

Exporta:
    limiter              — instancia de SlowAPI Limiter (None si no disponible)
    SLOWAPI_AVAILABLE    — bool
    optional_rate_limit  — decorador que aplica límite de velocidad si está disponible
    verify_firebase_token — dependencia FastAPI para verificar tokens JWT de Firebase
"""

import asyncio
import logging
import os
from concurrent.futures import ThreadPoolExecutor

from fastapi import HTTPException, Request

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# SlowAPI — Rate limiting opcional
# ---------------------------------------------------------------------------
try:
    from slowapi import Limiter, _rate_limit_exceeded_handler
    from slowapi.util import get_remote_address
    from slowapi.errors import RateLimitExceeded

    SLOWAPI_AVAILABLE = True
    limiter = Limiter(key_func=get_remote_address)
    logger.info("SlowAPI rate-limiter initialized")
except ImportError as exc:
    SLOWAPI_AVAILABLE = False
    limiter = None
    _rate_limit_exceeded_handler = None
    get_remote_address = None
    RateLimitExceeded = None
    logger.warning(f"SlowAPI not available — rate limiting disabled: {exc}")


def optional_rate_limit(limit_string: str):
    """
    Decorador que aplica rate-limiting **solo si SlowAPI está disponible**.
    En caso contrario, devuelve la función sin modificar.

    Uso::

        @optional_rate_limit("30/minute")
        async def mi_endpoint():
            ...
    """
    def decorator(func):
        if SLOWAPI_AVAILABLE and limiter is not None:
            try:
                return limiter.limit(limit_string)(func)
            except Exception as exc:
                logger.warning(f"No se pudo aplicar rate-limit a {func.__name__}: {exc}")
        return func
    return decorator


# ---------------------------------------------------------------------------
# Thread pool dedicado para verificación de tokens Firebase
# ---------------------------------------------------------------------------
_AUTH_EXECUTOR = ThreadPoolExecutor(max_workers=8, thread_name_prefix="route-auth")


async def verify_firebase_token(request: Request) -> dict:
    """
    Dependencia FastAPI que verifica el JWT de Firebase del header ``Authorization``.

    Returns:
        Diccionario con uid, email, email_verified y firestore_data del usuario.

    Raises:
        HTTPException 401 — token ausente, inválido o expirado
        HTTPException 503 — timeout de verificación
        HTTPException 500 — error interno
    """
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail={
                "success": False,
                "error": "Token de autenticacion requerido",
                "code": "MISSING_TOKEN",
            },
        )

    token = auth_header.split(" ", 1)[1]

    try:
        from firebase_admin import auth
        from database.firebase_config import get_firestore_client

        def _verify_sync():
            decoded = auth.verify_id_token(token)
            db = get_firestore_client()
            user_data = {}
            if db is not None:
                doc = db.collection("users").document(decoded["uid"]).get()
                if doc.exists:
                    user_data = doc.to_dict()
            return {
                "uid": decoded["uid"],
                "email": decoded.get("email"),
                "email_verified": decoded.get("email_verified", False),
                "firestore_data": user_data,
            }

        loop = asyncio.get_running_loop()
        try:
            return await asyncio.wait_for(
                loop.run_in_executor(_AUTH_EXECUTOR, _verify_sync),
                timeout=10.0,
            )
        except asyncio.TimeoutError:
            raise HTTPException(
                status_code=503,
                detail={
                    "success": False,
                    "error": "Tiempo de espera agotado verificando autenticacion",
                    "code": "AUTH_TIMEOUT",
                },
            )

    except HTTPException:
        raise
    except Exception as exc:
        # Intentar detectar errores de Firebase Auth
        exc_type = type(exc).__name__
        if "InvalidIdToken" in exc_type:
            raise HTTPException(
                status_code=401,
                detail={"success": False, "error": "Token invalido o expirado", "code": "INVALID_TOKEN"},
            )
        if "ExpiredIdToken" in exc_type:
            raise HTTPException(
                status_code=401,
                detail={"success": False, "error": "Token expirado", "code": "TOKEN_EXPIRED"},
            )
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "error": f"Error verificando autenticacion: {exc!s}",
                "code": "AUTH_VERIFICATION_ERROR",
            },
        )

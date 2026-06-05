# -*- coding: utf-8 -*-
"""
api/core/responses.py — Utilidades de respuesta y serialización.

Uso:
    from api.core.responses import create_utf8_response, clean_firebase_data
"""

import logging
import os
from datetime import datetime
from typing import Any, Dict, Optional
from zoneinfo import ZoneInfo

from fastapi.responses import JSONResponse
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# Importar tipos de Firebase si están disponibles
try:
    from google.cloud.firestore_v1._helpers import DatetimeWithNanoseconds
    _FIREBASE_TYPES_AVAILABLE = True
except ImportError:
    _FIREBASE_TYPES_AVAILABLE = False
    DatetimeWithNanoseconds = None


# ---------------------------------------------------------------------------
# Respuestas JSON con charset UTF-8 explícito
# ---------------------------------------------------------------------------

def create_utf8_response(content: Dict[str, Any], status_code: int = 200) -> JSONResponse:
    """Crea una JSONResponse con Content-Type explícitamente UTF-8."""
    return JSONResponse(
        content=content,
        status_code=status_code,
        headers={"Content-Type": "application/json; charset=utf-8"},
        media_type="application/json",
    )


# ---------------------------------------------------------------------------
# Serialización de datos de Firebase
# ---------------------------------------------------------------------------

def clean_firebase_data(data: Any) -> Any:
    """
    Convierte tipos de Firebase no serializables (DatetimeWithNanoseconds, etc.)
    a tipos nativos de Python aptos para JSON.
    """
    if isinstance(data, dict):
        return {key: clean_firebase_data(value) for key, value in data.items()}
    if isinstance(data, list):
        return [clean_firebase_data(item) for item in data]
    if _FIREBASE_TYPES_AVAILABLE and isinstance(data, DatetimeWithNanoseconds):
        return data.isoformat()
    if isinstance(data, datetime):
        return data.isoformat()
    return data


def handle_utf8_text(text: str) -> str:
    """Garantiza que el texto se mantiene en UTF-8."""
    if isinstance(text, str):
        return text.encode("utf-8").decode("utf-8")
    return str(text)


# ---------------------------------------------------------------------------
# Utilidades de timestamp con zona horaria Colombia
# ---------------------------------------------------------------------------

def timestamp_colombia_iso() -> str:
    """Devuelve un timestamp ISO en hora Colombia (UTC-5)."""
    try:
        tz_colombia = ZoneInfo("America/Bogota")
    except Exception:
        from datetime import timezone, timedelta
        tz_colombia = timezone(timedelta(hours=-5))
    return datetime.now(tz_colombia).isoformat()


# ---------------------------------------------------------------------------
# Serialización de payloads Pydantic
# ---------------------------------------------------------------------------

def payload_to_dict(payload: Optional[BaseModel]) -> Dict[str, Any]:
    """Serializa un modelo Pydantic y elimina campos nulos."""
    if payload is None:
        return {}
    if hasattr(payload, "model_dump"):
        data = payload.model_dump(exclude_unset=True)
    else:
        data = payload.dict(exclude_unset=True)
    return {k: v for k, v in data.items() if v is not None}

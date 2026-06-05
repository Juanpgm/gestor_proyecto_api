# -*- coding: utf-8 -*-
"""
api/core — Infraestructura compartida de la API.

Exporta las utilidades más usadas para importación directa:
    from api.core import get_cache_key, get_from_cache, set_in_cache
    from api.core import create_utf8_response, clean_firebase_data
    from api.core import optional_rate_limit, verify_firebase_token
    from api.core import get_cors_origins
"""

from .cache import get_cache_key, get_from_cache, set_in_cache, async_cache
from .responses import create_utf8_response, clean_firebase_data, handle_utf8_text
from .config import get_cors_origins, get_cors_origin_regex, CORS_ORIGINS
from .security import optional_rate_limit, limiter, SLOWAPI_AVAILABLE

__all__ = [
    # Cache
    "get_cache_key",
    "get_from_cache",
    "set_in_cache",
    "async_cache",
    # Responses
    "create_utf8_response",
    "clean_firebase_data",
    "handle_utf8_text",
    # Config / CORS
    "get_cors_origins",
    "get_cors_origin_regex",
    "CORS_ORIGINS",
    # Security / Rate-limiting
    "optional_rate_limit",
    "limiter",
    "SLOWAPI_AVAILABLE",
]

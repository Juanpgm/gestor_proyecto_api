# -*- coding: utf-8 -*-
"""
api/core/cache.py — Cache en memoria thread-safe con TTL y tamaño acotado.

Uso:
    from api.core.cache import get_cache_key, get_from_cache, set_in_cache, async_cache
"""

import hashlib
import threading
import logging
from collections import OrderedDict
from datetime import datetime
from typing import Any, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Almacenamiento interno
# ---------------------------------------------------------------------------

_CACHE_MAX_SIZE = 1000
_cache_lock = threading.Lock()
_simple_cache: OrderedDict = OrderedDict()   # key -> value
_cache_timestamps: dict = {}                  # key -> datetime


# ---------------------------------------------------------------------------
# API pública
# ---------------------------------------------------------------------------

def get_cache_key(func_name: str, *args, **kwargs) -> str:
    """Genera una clave de caché única y determinista."""
    key_data = f"{func_name}:{args!s}:{sorted(kwargs.items())!s}"
    return hashlib.md5(key_data.encode()).hexdigest()


def get_from_cache(cache_key: str, max_age_seconds: int = 300) -> Tuple[Any, bool]:
    """
    Recupera un valor del caché si existe y no ha expirado.

    Returns:
        (value, True)  — cuando el hit es válido
        (None, False)  — cuando hay miss o el entry expiró
    """
    with _cache_lock:
        if cache_key in _simple_cache:
            cached_time = _cache_timestamps.get(cache_key)
            if cached_time and (datetime.now() - cached_time).total_seconds() < max_age_seconds:
                _simple_cache.move_to_end(cache_key)
                return _simple_cache[cache_key], True
            # Entrada expirada — desalojar
            _simple_cache.pop(cache_key, None)
            _cache_timestamps.pop(cache_key, None)
    return None, False


def set_in_cache(cache_key: str, value: Any) -> None:
    """
    Almacena un valor en el caché.
    Evita desbordamiento de memoria expulsando el entry más antiguo (LRU).
    """
    with _cache_lock:
        while len(_simple_cache) >= _CACHE_MAX_SIZE:
            oldest_key, _ = _simple_cache.popitem(last=False)
            _cache_timestamps.pop(oldest_key, None)
        _simple_cache[cache_key] = value
        _cache_timestamps[cache_key] = datetime.now()


def async_cache(ttl_seconds: int = 300):
    """
    Decorador para cachear funciones async con TTL.

    Uso::

        @async_cache(ttl_seconds=600)
        async def mi_endpoint():
            ...
    """
    def decorator(func):
        import copy
        from functools import wraps

        @wraps(func)
        async def wrapper(*args, **kwargs):
            cache_key = get_cache_key(func.__name__, *args, **kwargs)
            cached_value, is_valid = get_from_cache(cache_key, ttl_seconds)
            if is_valid:
                logger.info(f"Cache hit: {func.__name__}")
                try:
                    return copy.deepcopy(cached_value)
                except Exception:
                    return cached_value

            logger.info(f"Cache miss: {func.__name__}")
            result = await func(*args, **kwargs)
            try:
                set_in_cache(cache_key, result)
            except Exception as exc:
                logger.warning(f"No se pudo cachear {func.__name__}: {exc}")
            return result

        return wrapper
    return decorator

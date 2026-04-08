"""
Sistema de Caché en Memoria para Endpoints de Empréstito
Optimiza la velocidad de carga usando caché con TTL (Time To Live)
"""

import asyncio
import logging
from typing import Dict, Any, Optional, Callable
from datetime import datetime, timedelta
from functools import wraps
import hashlib
import json

logger = logging.getLogger(__name__)

# Configuración del caché
CACHE_TTL_SECONDS = 300  # 5 minutos por defecto
CACHE_ENABLED = True

# Almacenamiento del caché en memoria
_cache_storage: Dict[str, Dict[str, Any]] = {}
_cache_locks: Dict[str, asyncio.Lock] = {}


class CacheEntry:
    """Entrada de caché con timestamp y datos"""
    
    def __init__(self, data: Any, ttl_seconds: int = CACHE_TTL_SECONDS):
        self.data = data
        self.created_at = datetime.now()
        self.expires_at = self.created_at + timedelta(seconds=ttl_seconds)
        self.hits = 0
    
    def is_expired(self) -> bool:
        """Verifica si la entrada ha expirado"""
        return datetime.now() > self.expires_at
    
    def get_age_seconds(self) -> float:
        """Retorna la edad de la entrada en segundos"""
        return (datetime.now() - self.created_at).total_seconds()
    
    def increment_hits(self):
        """Incrementa el contador de accesos"""
        self.hits += 1


def generate_cache_key(func_name: str, **kwargs) -> str:
    """
    Genera una clave única para el caché basada en el nombre de la función y parámetros
    
    Args:
        func_name: Nombre de la función
        **kwargs: Parámetros de la función
    
    Returns:
        Clave hash MD5 como string
    """
    # Crear representación ordenada de los parámetros
    params_str = json.dumps(kwargs, sort_keys=True, default=str)
    cache_input = f"{func_name}:{params_str}"
    
    # Generar hash MD5
    cache_key = hashlib.md5(cache_input.encode()).hexdigest()
    return f"cache_{func_name}_{cache_key}"


async def get_from_cache(cache_key: str) -> Optional[Any]:
    """
    Obtiene un valor del caché si existe y no ha expirado
    
    Args:
        cache_key: Clave del caché
    
    Returns:
        Datos cacheados o None si no existe o ha expirado
    """
    if not CACHE_ENABLED:
        return None
    
    entry = _cache_storage.get(cache_key)
    
    if entry is None:
        return None
    
    if entry.is_expired():
        # Eliminar entrada expirada
        del _cache_storage[cache_key]
        logger.debug(f"♻️ Caché expirado y eliminado: {cache_key}")
        return None
    
    # Incrementar contador de accesos
    entry.increment_hits()
    
    logger.info(f"✅ Cache HIT: {cache_key} (edad: {entry.get_age_seconds():.1f}s, hits: {entry.hits})")
    return entry.data


async def set_to_cache(cache_key: str, data: Any, ttl_seconds: int = CACHE_TTL_SECONDS):
    """
    Almacena un valor en el caché
    
    Args:
        cache_key: Clave del caché
        data: Datos a cachear
        ttl_seconds: Tiempo de vida en segundos
    """
    if not CACHE_ENABLED:
        return
    
    entry = CacheEntry(data, ttl_seconds)
    _cache_storage[cache_key] = entry
    
    logger.info(f"💾 Cache STORE: {cache_key} (TTL: {ttl_seconds}s)")


async def clear_cache(pattern: Optional[str] = None):
    """
    Limpia el caché completamente o por patrón
    
    Args:
        pattern: Patrón opcional para filtrar claves a eliminar
    """
    if pattern:
        # Eliminar solo claves que coincidan con el patrón
        keys_to_delete = [k for k in _cache_storage.keys() if pattern in k]
        for key in keys_to_delete:
            del _cache_storage[key]
        logger.info(f"🧹 Cache limpiado: {len(keys_to_delete)} entradas con patrón '{pattern}'")
    else:
        # Limpiar todo el caché
        count = len(_cache_storage)
        _cache_storage.clear()
        logger.info(f"🧹 Cache limpiado completamente: {count} entradas")


def get_cache_lock(cache_key: str) -> asyncio.Lock:
    """
    Obtiene un lock para evitar condiciones de carrera al actualizar el caché
    
    Args:
        cache_key: Clave del caché
    
    Returns:
        Lock de asyncio
    """
    if cache_key not in _cache_locks:
        _cache_locks[cache_key] = asyncio.Lock()
    return _cache_locks[cache_key]


def with_cache(ttl_seconds: int = CACHE_TTL_SECONDS, key_params: Optional[list] = None):
    """
    Decorador para cachear resultados de funciones async
    
    Args:
        ttl_seconds: Tiempo de vida del caché en segundos
        key_params: Lista de nombres de parámetros a usar para generar la clave
                   Si es None, usa todos los parámetros
    
    Uso:
        @with_cache(ttl_seconds=300, key_params=['centro_gestor'])
        async def get_data(centro_gestor: str, other_param: str):
            # código de la función
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Determinar parámetros a usar para la clave
            if key_params is not None:
                cache_kwargs = {k: v for k, v in kwargs.items() if k in key_params}
            else:
                cache_kwargs = kwargs
            
            # Generar clave de caché
            cache_key = generate_cache_key(func.__name__, **cache_kwargs)
            
            # Intentar obtener del caché
            cached_result = await get_from_cache(cache_key)
            if cached_result is not None:
                return cached_result
            
            # Obtener lock para evitar llamadas paralelas duplicadas
            lock = get_cache_lock(cache_key)
            
            async with lock:
                # Verificar nuevamente por si otra llamada ya actualizó el caché
                cached_result = await get_from_cache(cache_key)
                if cached_result is not None:
                    return cached_result
                
                # Ejecutar función original
                logger.debug(f"❌ Cache MISS: {cache_key} - ejecutando función")
                result = await func(*args, **kwargs)
                
                # Cachear resultado solo si fue exitoso
                if isinstance(result, dict) and result.get("success"):
                    await set_to_cache(cache_key, result, ttl_seconds)
                
                return result
        
        return wrapper
    return decorator


def get_cache_stats() -> Dict[str, Any]:
    """
    Obtiene estadísticas del caché
    
    Returns:
        Diccionario con estadísticas del caché
    """
    total_entries = len(_cache_storage)
    expired_count = sum(1 for entry in _cache_storage.values() if entry.is_expired())
    active_count = total_entries - expired_count
    
    total_hits = sum(entry.hits for entry in _cache_storage.values())
    
    # Calcular tamaños aproximados
    entries_info = []
    for key, entry in _cache_storage.items():
        entries_info.append({
            "key": key[:50] + "..." if len(key) > 50 else key,
            "age_seconds": entry.get_age_seconds(),
            "hits": entry.hits,
            "expired": entry.is_expired()
        })
    
    # Ordenar por hits (más usados primero)
    entries_info.sort(key=lambda x: x["hits"], reverse=True)
    
    return {
        "enabled": CACHE_ENABLED,
        "ttl_seconds": CACHE_TTL_SECONDS,
        "total_entries": total_entries,
        "active_entries": active_count,
        "expired_entries": expired_count,
        "total_hits": total_hits,
        "entries": entries_info[:10],  # Top 10 entradas más usadas
        "timestamp": datetime.now().isoformat()
    }


# Funciones de utilidad para invalidar caché específico

async def invalidate_contratos_cache():
    """Invalida todo el caché relacionado con contratos"""
    await clear_cache("get_contratos")
    logger.info("🔄 Caché de contratos invalidado")


async def invalidate_procesos_cache():
    """Invalida todo el caché relacionado con procesos"""
    await clear_cache("get_procesos")
    logger.info("🔄 Caché de procesos invalidado")


async def invalidate_bancos_cache():
    """Invalida todo el caché relacionado con bancos"""
    await clear_cache("get_bancos")
    logger.info("🔄 Caché de bancos invalidado")


async def invalidate_all_emprestito_cache():
    """Invalida todo el caché de empréstito"""
    await clear_cache()
    logger.info("🔄 Todo el caché de empréstito invalidado")

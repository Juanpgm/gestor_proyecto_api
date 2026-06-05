"""
Funciones Optimizadas para Endpoints GET de Empréstito
Mejoras de rendimiento: caché, paginación, proyección de campos, consultas paralelas
"""

import logging
import asyncio
from typing import Dict, List, Any, Optional
from datetime import datetime
from database.firebase_config import get_firestore_client
from api.scripts.emprestito_cache import with_cache, generate_cache_key, get_from_cache, set_to_cache

logger = logging.getLogger(__name__)

# Importar funciones de serialización existentes
try:
    from api.scripts.emprestito_operations import serialize_datetime_objects, FIRESTORE_AVAILABLE
except ImportError:
    FIRESTORE_AVAILABLE = False
    def serialize_datetime_objects(obj):
        """Fallback si no está disponible"""
        if isinstance(obj, dict):
            return {key: serialize_datetime_objects(value) for key, value in obj.items()}
        elif isinstance(obj, list):
            return [serialize_datetime_objects(item) for item in obj]
        elif isinstance(obj, datetime):
            return obj.isoformat()
        else:
            return obj


def apply_field_projection(data: List[Dict[str, Any]], fields: Optional[List[str]]) -> List[Dict[str, Any]]:
    """
    Aplica proyección de campos para reducir el payload
    
    Args:
        data: Lista de documentos
        fields: Lista de campos a incluir. Si es None, incluye todos
    
    Returns:
        Lista de documentos con solo los campos especificados
    """
    if not fields or not data:
        return data
    
    # Siempre incluir 'id' si existe
    fields_set = set(fields)
    if 'id' not in fields_set:
        fields_set.add('id')
    
    projected_data = []
    for doc in data:
        projected_doc = {k: v for k, v in doc.items() if k in fields_set}
        projected_data.append(projected_doc)
    
    return projected_data


def apply_pagination(data: List[Any], limit: Optional[int], offset: Optional[int]) -> tuple[List[Any], Dict[str, Any]]:
    """
    Aplica paginación a una lista de datos
    
    Args:
        data: Lista de datos a paginar
        limit: Número máximo de elementos a retornar
        offset: Número de elementos a saltar
    
    Returns:
        Tupla con (datos_paginados, metadata_paginacion)
    """
    total = len(data)
    
    # Validar y normalizar parámetros
    offset = max(0, offset or 0)
    limit = min(max(1, limit or total), 1000) if limit else total  # Máximo 1000 por página
    
    # Calcular rango
    start = offset
    end = min(offset + limit, total)
    
    # Obtener slice
    paginated_data = data[start:end]
    
    # Metadata de paginación
    has_more = end < total
    next_offset = end if has_more else None
    
    pagination_meta = {
        "total": total,
        "limit": limit,
        "offset": offset,
        "returned": len(paginated_data),
        "has_more": has_more,
        "next_offset": next_offset,
        "current_page": (offset // limit) + 1 if limit > 0 else 1,
        "total_pages": (total + limit - 1) // limit if limit > 0 else 1
    }
    
    return paginated_data, pagination_meta


@with_cache(ttl_seconds=300)  # Cache de 5 minutos
async def get_procesos_emprestito_optimized(
    limit: Optional[int] = None,
    offset: Optional[int] = None,
    fields: Optional[List[str]] = None,
    centro_gestor: Optional[str] = None
) -> Dict[str, Any]:
    """
    Versión optimizada de get_procesos_emprestito_all con paginación, proyección y caché
    
    Args:
        limit: Número máximo de registros a retornar
        offset: Número de registros a saltar
        fields: Lista de campos a incluir (proyección)
        centro_gestor: Filtrar por centro gestor específico
    
    Returns:
        Diccionario con datos paginados y metadata
    """
    try:
        if not FIRESTORE_AVAILABLE:
            return {"success": False, "error": "Firebase no disponible", "data": [], "count": 0}
        
        db = get_firestore_client()
        if db is None:
            return {"success": False, "error": "No se pudo conectar a Firestore", "data": [], "count": 0}
        
        # Construir query
        collection_ref = db.collection('procesos_emprestito')
        query = collection_ref
        
        # Aplicar filtro server-side si se especifica centro_gestor
        if centro_gestor:
            query = query.where('nombre_centro_gestor', '==', centro_gestor)
        
        # Ejecutar query
        docs = query.stream()
        procesos_data = []
        
        for doc in docs:
            doc_data = doc.to_dict()
            doc_data['id'] = doc.id
            
            # Limpiar datos para serialización JSON
            doc_data_clean = serialize_datetime_objects(doc_data)
            procesos_data.append(doc_data_clean)
        
        # Aplicar proyección de campos
        if fields:
            procesos_data = apply_field_projection(procesos_data, fields)
        
        # Aplicar paginación
        paginated_data, pagination_meta = apply_pagination(procesos_data, limit, offset)
        
        return {
            "success": True,
            "data": paginated_data,
            "count": len(paginated_data),
            "pagination": pagination_meta,
            "collection": "procesos_emprestito",
            "timestamp": datetime.now().isoformat(),
            "cached": False,  # El decorador maneja esto automáticamente
            "message": f"Se obtuvieron {len(paginated_data)} de {pagination_meta['total']} procesos de empréstito"
        }
        
    except Exception as e:
        logger.error(f"Error en get_procesos_emprestito_optimized: {str(e)}")
        return {
            "success": False, 
            "error": f"Error obteniendo procesos: {str(e)}",
            "data": [],
            "count": 0
        }


@with_cache(ttl_seconds=300)  # Cache de 5 minutos
async def get_contratos_emprestito_optimized(
    limit: Optional[int] = None,
    offset: Optional[int] = None,
    fields: Optional[List[str]] = None,
    centro_gestor: Optional[str] = None,
    include_ordenes: bool = True
) -> Dict[str, Any]:
    """
    Versión optimizada de get_contratos_emprestito_all con consultas paralelas
    
    Args:
        limit: Número máximo de registros a retornar
        offset: Número de registros a saltar
        fields: Lista de campos a incluir
        centro_gestor: Filtrar por centro gestor
        include_ordenes: Incluir órdenes de compra en el resultado
    
    Returns:
        Diccionario con datos combinados y paginados
    """
    try:
        if not FIRESTORE_AVAILABLE:
            return {"success": False, "error": "Firebase no disponible", "data": [], "count": 0}
        
        db = get_firestore_client()
        if db is None:
            return {"success": False, "error": "No se pudo conectar a Firestore", "data": [], "count": 0}
        
        # Ejecutar consultas en paralelo
        tasks = [
            _fetch_contratos(db, centro_gestor, fields)
        ]
        
        if include_ordenes:
            tasks.append(_fetch_ordenes_compra(db, centro_gestor, fields))
        
        # Esperar ambas consultas
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Procesar resultados
        contratos_data = []
        ordenes_data = []
        
        if len(results) > 0 and not isinstance(results[0], Exception):
            contratos_data = results[0]
        
        if len(results) > 1 and not isinstance(results[1], Exception):
            ordenes_data = results[1]
        
        # Combinar datos
        combined_data = contratos_data + ordenes_data
        
        # Ordenar por fecha de firma/creación (más recientes primero)
        combined_data.sort(
            key=lambda x: x.get('fecha_firma_contrato') or x.get('fecha_guardado') or '', 
            reverse=True
        )
        
        # Aplicar paginación
        paginated_data, pagination_meta = apply_pagination(combined_data, limit, offset)
        
        return {
            "success": True,
            "data": paginated_data,
            "count": len(paginated_data),
            "pagination": pagination_meta,
            "contratos_count": len(contratos_data),
            "ordenes_count": len(ordenes_data),
            "collections": ["contratos_emprestito"] + (["ordenes_compra_emprestito"] if include_ordenes else []),
            "timestamp": datetime.now().isoformat(),
            "message": f"🚀 OPTIMIZADO: Se obtuvieron {len(contratos_data)} contratos y {len(ordenes_data)} órdenes de compra"
        }
        
    except Exception as e:
        logger.error(f"Error en get_contratos_emprestito_optimized: {str(e)}")
        return {
            "success": False,
            "error": f"Error obteniendo contratos: {str(e)}",
            "data": [],
            "count": 0
        }


async def _fetch_contratos(
    db, 
    centro_gestor: Optional[str] = None,
    fields: Optional[List[str]] = None
) -> List[Dict[str, Any]]:
    """
    Helper async para obtener contratos con filtros opcionales
    """
    try:
        collection_ref = db.collection('contratos_emprestito')
        query = collection_ref
        
        if centro_gestor:
            query = query.where('nombre_centro_gestor', '==', centro_gestor)
        
        docs = query.stream()
        contratos_data = []
        
        for doc in docs:
            doc_data = doc.to_dict()
            doc_data['id'] = doc.id
            doc_data['_source'] = 'contratos_emprestito'
            
            # Serializar
            doc_data_clean = serialize_datetime_objects(doc_data)
            contratos_data.append(doc_data_clean)
        
        # Aplicar proyección de campos
        if fields:
            contratos_data = apply_field_projection(contratos_data, fields)
        
        return contratos_data
        
    except Exception as e:
        logger.error(f"Error fetching contratos: {str(e)}")
        return []


async def _fetch_ordenes_compra(
    db,
    centro_gestor: Optional[str] = None,
    fields: Optional[List[str]] = None
) -> List[Dict[str, Any]]:
    """
    Helper async para obtener órdenes de compra con filtros opcionales
    """
    try:
        collection_ref = db.collection('ordenes_compra_emprestito')
        query = collection_ref
        
        if centro_gestor:
            query = query.where('nombre_centro_gestor', '==', centro_gestor)
        
        docs = query.stream()
        ordenes_data = []
        
        for doc in docs:
            doc_data = doc.to_dict()
            doc_data['id'] = doc.id
            doc_data['_source'] = 'ordenes_compra_emprestito'
            
            # Serializar
            doc_data_clean = serialize_datetime_objects(doc_data)
            ordenes_data.append(doc_data_clean)
        
        # Aplicar proyección de campos
        if fields:
            ordenes_data = apply_field_projection(ordenes_data, fields)
        
        return ordenes_data
        
    except Exception as e:
        logger.error(f"Error fetching ordenes: {str(e)}")
        return []


@with_cache(ttl_seconds=600)  # Cache de 10 minutos (más estable)
async def get_bancos_emprestito_optimized(
    limit: Optional[int] = None,
    offset: Optional[int] = None
) -> Dict[str, Any]:
    """
    Versión optimizada de get_bancos_emprestito_all con paginación y caché
    """
    try:
        if not FIRESTORE_AVAILABLE:
            return {"success": False, "error": "Firebase no disponible", "data": [], "count": 0}
        
        db = get_firestore_client()
        if db is None:
            return {"success": False, "error": "No se pudo conectar a Firestore", "data": [], "count": 0}
        
        collection_ref = db.collection('bancos_emprestito')
        docs = collection_ref.stream()
        bancos_data = []
        
        for doc in docs:
            doc_data = doc.to_dict()
            doc_data['id'] = doc.id
            doc_data_clean = serialize_datetime_objects(doc_data)
            bancos_data.append(doc_data_clean)
        
        # Ordenar por nombre
        bancos_data.sort(key=lambda x: x.get('nombre_banco', '').lower())
        
        # Aplicar paginación
        paginated_data, pagination_meta = apply_pagination(bancos_data, limit, offset)
        
        return {
            "success": True,
            "data": paginated_data,
            "count": len(paginated_data),
            "pagination": pagination_meta,
            "collection": "bancos_emprestito",
            "timestamp": datetime.now().isoformat(),
            "message": f"Se obtuvieron {len(paginated_data)} de {pagination_meta['total']} bancos"
        }
        
    except Exception as e:
        logger.error(f"Error en get_bancos_emprestito_optimized: {str(e)}")
        return {
            "success": False,
            "error": f"Error obteniendo bancos: {str(e)}",
            "data": [],
            "count": 0
        }


# Flag de disponibilidad
EMPRESTITO_OPTIMIZED_AVAILABLE = FIRESTORE_AVAILABLE

"""
Operaciones para obtener órdenes de compra enriquecidas
"""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
from database.firebase_config import get_firestore_client

# Configurar logging
logger = logging.getLogger(__name__)

# Variables de disponibilidad
FIRESTORE_AVAILABLE = True
try:
    from database.firebase_config import get_firestore_client
    get_firestore_client()
except Exception as e:
    FIRESTORE_AVAILABLE = False
    logger.warning(f"Firebase no disponible: {e}")

def serialize_datetime_objects(obj):
    """Serializar objetos datetime para JSON"""
    if isinstance(obj, dict):
        return {key: serialize_datetime_objects(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [serialize_datetime_objects(item) for item in obj]
    elif hasattr(obj, 'timestamp'):  # Firebase Timestamp
        return obj.strftime('%Y-%m-%d %H:%M:%S')
    elif isinstance(obj, datetime):
        return obj.strftime('%Y-%m-%d %H:%M:%S')
    else:
        return obj

async def get_ordenes_compra_emprestito_all() -> Dict[str, Any]:
    """Obtener todos los registros de la colección ordenes_compra_emprestito"""
    try:
        if not FIRESTORE_AVAILABLE:
            return {"success": False, "error": "Firebase no disponible", "data": [], "count": 0}
        
        db = get_firestore_client()
        if db is None:
            return {"success": False, "error": "No se pudo conectar a Firestore", "data": [], "count": 0}
        
        collection_ref = db.collection('ordenes_compra_emprestito')
        docs = collection_ref.stream()
        ordenes_data = []
        
        for doc in docs:
            doc_data = doc.to_dict()
            doc_data['id'] = doc.id  # Agregar ID del documento
            # Limpiar datos de Firebase para serialización JSON
            doc_data_clean = serialize_datetime_objects(doc_data)
            ordenes_data.append(doc_data_clean)
        
        # Ordenar por numero_orden para mejor presentación
        ordenes_data.sort(key=lambda x: x.get('numero_orden', '').lower())
        
        return {
            "success": True,
            "data": ordenes_data,
            "count": len(ordenes_data),
            "collection": "ordenes_compra_emprestito",
            "timestamp": datetime.now().isoformat(),
            "message": f"Se obtuvieron {len(ordenes_data)} órdenes de compra de empréstito exitosamente"
        }
        
    except Exception as e:
        return {
            "success": False, 
            "error": f"Error obteniendo todas las órdenes de compra de empréstito: {str(e)}",
            "data": [],
            "count": 0
        }

async def get_ordenes_compra_emprestito_by_referencia(numero_orden: str) -> Dict[str, Any]:
    """Obtener órdenes de compra de empréstito por número de orden específico"""
    try:
        if not FIRESTORE_AVAILABLE:
            return {"success": False, "error": "Firebase no disponible", "data": [], "count": 0}
        
        db = get_firestore_client()
        if db is None:
            return {"success": False, "error": "No se pudo conectar a Firestore", "data": [], "count": 0}
        
        collection_ref = db.collection('ordenes_compra_emprestito')
        query = collection_ref.where('numero_orden', '==', numero_orden)
        docs = query.stream()
        ordenes_data = []
        
        for doc in docs:
            doc_data = doc.to_dict()
            doc_data['id'] = doc.id
            doc_data_clean = serialize_datetime_objects(doc_data)
            ordenes_data.append(doc_data_clean)
        
        return {
            "success": True,
            "data": ordenes_data,
            "count": len(ordenes_data),
            "collection": "ordenes_compra_emprestito",
            "filter": {"numero_orden": numero_orden},
            "timestamp": datetime.now().isoformat(),
            "message": f"Se encontraron {len(ordenes_data)} órdenes con número '{numero_orden}'"
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": f"Error obteniendo órdenes por número: {str(e)}",
            "data": [],
            "count": 0
        }

async def get_ordenes_compra_emprestito_by_centro_gestor(nombre_centro_gestor: str) -> Dict[str, Any]:
    """Obtener órdenes de compra de empréstito por centro gestor específico"""
    try:
        if not FIRESTORE_AVAILABLE:
            return {"success": False, "error": "Firebase no disponible", "data": [], "count": 0}
        
        db = get_firestore_client()
        if db is None:
            return {"success": False, "error": "No se pudo conectar a Firestore", "data": [], "count": 0}
        
        collection_ref = db.collection('ordenes_compra_emprestito')
        query = collection_ref.where('nombre_centro_gestor', '==', nombre_centro_gestor)
        docs = query.stream()
        ordenes_data = []
        
        for doc in docs:
            doc_data = doc.to_dict()
            doc_data['id'] = doc.id
            doc_data_clean = serialize_datetime_objects(doc_data)
            ordenes_data.append(doc_data_clean)
        
        # Ordenar por numero_orden
        ordenes_data.sort(key=lambda x: x.get('numero_orden', '').lower())
        
        return {
            "success": True,
            "data": ordenes_data,
            "count": len(ordenes_data),
            "collection": "ordenes_compra_emprestito",
            "filter": {"nombre_centro_gestor": nombre_centro_gestor},
            "timestamp": datetime.now().isoformat(),
            "message": f"Se encontraron {len(ordenes_data)} órdenes para el centro gestor '{nombre_centro_gestor}'"
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": f"Error obteniendo órdenes por centro gestor: {str(e)}",
            "data": [],
            "count": 0
        }

# Variables de disponibilidad
ORDENES_COMPRA_OPERATIONS_AVAILABLE = FIRESTORE_AVAILABLE

def get_ordenes_compra_operations_status() -> Dict[str, Any]:
    """Obtener estado de las operaciones de órdenes de compra"""
    return {
        "firestore_available": FIRESTORE_AVAILABLE,
        "operations_available": FIRESTORE_AVAILABLE,
        "supported_collections": ["ordenes_compra_emprestito"],
        "supported_filters": ["numero_orden", "nombre_centro_gestor"]
    }
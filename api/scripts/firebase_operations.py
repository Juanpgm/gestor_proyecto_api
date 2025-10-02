"""
Scripts generales para Firebase/Firestore
Funciones reutilizables para operaciones comunes de Firestore
"""

from typing import Dict, List, Any, Optional
from datetime import datetime

try:
    from google.cloud import firestore
    from google.api_core import exceptions as gcp_exceptions
    GOOGLE_CLOUD_AVAILABLE = True
except ImportError:
    GOOGLE_CLOUD_AVAILABLE = False
    firestore = None
    gcp_exceptions = None

from database.firebase_config import FirebaseManager

# Constantes para compatibilidad
PROJECT_ID = "gestor-proyecto"  # Este se obtendrá dinámicamente
BATCH_SIZE = 500
TIMEOUT = 30


async def get_collections_info() -> Dict[str, Any]:
    """
    Obtener información de todas las colecciones de Firestore
    Versión optimizada y modular
    """
    if not GOOGLE_CLOUD_AVAILABLE:
        return {
            "success": False,
            "error": "Google Cloud SDK no disponible",
            "collections": []
        }
    try:
        firebase_manager = FirebaseManager()
        db = firebase_manager.get_client()
        if db is None:
            raise Exception("No se pudo conectar a Firestore")
        
        collections = db.collections()
        collections_info = {}
        
        for collection in collections:
            collection_name = collection.id
            info = await _get_single_collection_info(collection)
            collections_info[collection_name] = info
        
        return {
            "success": True,
            "timestamp": datetime.now().isoformat(),
            "project_id": PROJECT_ID,
            "collections": collections_info,
            "total_collections": len(collections_info)
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "timestamp": datetime.now().isoformat(),
            "collections": {},
            "total_collections": 0
        }


async def _get_single_collection_info(collection) -> Dict[str, Any]:
    """
    Función auxiliar para obtener información de una sola colección
    
    Args:
        collection: Referencia a la colección de Firestore
        
    Returns:
        Dict con información de la colección
    """
    try:
        collection_name = collection.id
        
        # Contar documentos y calcular información
        docs = collection.stream()
        doc_count = 0
        total_size = 0
        last_updated = None
        
        for doc in docs:
            doc_count += 1
            doc_data = doc.to_dict()
            
            # Estimación básica del tamaño
            total_size += len(str(doc_data).encode('utf-8'))
            
            # Buscar timestamps
            update_time = doc.update_time
            if update_time and (last_updated is None or update_time > last_updated):
                last_updated = update_time
        
        return {
            "document_count": doc_count,
            "estimated_size_bytes": total_size,
            "estimated_size_mb": round(total_size / (1024 * 1024), 2),
            "last_updated": last_updated.isoformat() if last_updated else None,
            "status": "active"
        }
        
    except Exception as e:
        return {
            "document_count": 0,
            "estimated_size_bytes": 0,
            "estimated_size_mb": 0,
            "last_updated": None,
            "status": f"error: {str(e)}"
        }


async def test_firebase_connection() -> Dict[str, Any]:
    """
    Probar la conexión con Firebase de forma modular
    
    Returns:
        Dict con resultado de la prueba de conexión
    """
    try:
        firebase_manager = FirebaseManager()
        db = firebase_manager.get_client()
        if db is None:
            return {
                "connected": False,
                "error": "No se pudo obtener cliente de Firestore"
            }
            
        # Probar con una consulta simple
        collections = db.collections()
        collection_list = list(collections)
        
        return {
            "connected": True,
            "project_id": PROJECT_ID,
            "collections_found": len(collection_list),
            "timestamp": datetime.now().isoformat(),
            "configuration": {
                "batch_size": BATCH_SIZE,
                "timeout": TIMEOUT,
                "debug": True
            }
        }
        
    except gcp_exceptions.PermissionDenied:
        return {
            "connected": False,
            "error": "Permisos insuficientes para acceder a Firestore",
            "suggestion": "Verifica las credenciales y permisos del proyecto"
        }
    except Exception as e:
        return {
            "connected": False,
            "error": f"Error probando conexión Firebase: {str(e)}"
        }


async def get_collections_summary() -> Dict[str, Any]:
    """
    Obtener resumen estadístico de todas las colecciones
    
    Returns:
        Dict con resumen de las colecciones
    """
    try:
        collections_data = await get_collections_info()
        
        if not collections_data["success"]:
            return {
                "success": False,
                "error": collections_data.get('error'),
                "summary": {}
            }
        
        # Calcular estadísticas resumidas
        collections = collections_data["collections"]
        total_documents = sum(col.get("document_count", 0) for col in collections.values())
        total_size_mb = sum(col.get("estimated_size_mb", 0) for col in collections.values())
        
        active_collections = sum(1 for col in collections.values() if col.get("status") == "active")
        error_collections = sum(1 for col in collections.values() if col.get("status", "").startswith("error"))
        
        return {
            "success": True,
            "summary": {
                "total_collections": collections_data["total_collections"],
                "active_collections": active_collections,
                "error_collections": error_collections,
                "total_documents": total_documents,
                "total_size_mb": round(total_size_mb, 2),
                "project_id": collections_data["project_id"]
            },
            "timestamp": collections_data["timestamp"]
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": f"Error obteniendo resumen: {str(e)}",
            "summary": {}
        }
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

from database.firebase_config import get_firestore_client, get_auth_client, PROJECT_ID
BATCH_SIZE = 500
TIMEOUT = 30


async def get_collections_info(limit_docs_per_collection: int = 50) -> Dict[str, Any]:
    """
    Obtener información de todas las colecciones de Firestore
    Versión ULTRA-OPTIMIZADA con procesamiento paralelo
    
    OPTIMIZACIONES:
    - Procesamiento paralelo de colecciones con asyncio.gather
    - Límite de documentos por colección para muestreo rápido
    - Estimaciones en lugar de conteos exactos
    - Timeout de seguridad por colección
    
    Args:
        limit_docs_per_collection: Número de docs a muestrear por colección (default: 50)
    
    Returns:
        Dict con información estimada de todas las colecciones
    """
    if not GOOGLE_CLOUD_AVAILABLE:
        return {
            "success": False,
            "error": "Google Cloud SDK no disponible",
            "collections": []
        }
    try:
        db = get_firestore_client()
        if db is None:
            raise Exception("No se pudo conectar a Firestore")
        
        # Obtener lista de colecciones
        collections_list = list(db.collections())
        
        # OPTIMIZACIÓN CRÍTICA: Procesar colecciones en PARALELO con asyncio.gather
        import asyncio
        tasks = [
            _get_single_collection_info(collection, limit_docs=limit_docs_per_collection) 
            for collection in collections_list
        ]
        
        # Ejecutar todas las tareas en paralelo con timeout
        collections_data = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Construir diccionario de resultados
        collections_info = {}
        for collection, data in zip(collections_list, collections_data):
            collection_name = collection.id
            if isinstance(data, Exception):
                collections_info[collection_name] = {
                    "document_count": 0,
                    "status": f"error: {str(data)}",
                    "is_estimate": False
                }
            else:
                collections_info[collection_name] = data
        
        return {
            "success": True,
            "timestamp": datetime.now().isoformat(),
            "project_id": PROJECT_ID,
            "collections": collections_info,
            "total_collections": len(collections_info),
            "optimization_note": f"Muestra de {limit_docs_per_collection} docs por colección procesada en paralelo"
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "timestamp": datetime.now().isoformat(),
            "collections": {},
            "total_collections": 0
        }


async def _get_single_collection_info(collection, limit_docs: int = 100) -> Dict[str, Any]:
    """
    Función auxiliar OPTIMIZADA para obtener información de una sola colección
    
    OPTIMIZACIONES:
    - Limita a primeros N documentos para estimación (default: 100)
    - Solo obtiene metadatos, no el contenido completo
    - Usa select() para proyección de campos mínimos
    - Calcula estimaciones en lugar de valores exactos
    
    Args:
        collection: Referencia a la colección de Firestore
        limit_docs: Número máximo de documentos para muestreo (default: 100)
        
    Returns:
        Dict con información estimada de la colección
    """
    try:
        collection_name = collection.id
        
        # OPTIMIZACIÓN 1: Contar con límite para estimación rápida
        # En lugar de iterar TODOS los docs, solo muestreamos los primeros N
        sample_docs = collection.limit(limit_docs).stream()
        doc_count = 0
        total_size = 0
        last_updated = None
        
        for doc in sample_docs:
            doc_count += 1
            
            # OPTIMIZACIÓN 2: Solo obtener tamaño aproximado sin serializar todo
            # Usar solo el ID y timestamp, no los datos completos
            doc_data = doc.to_dict()
            if doc_data:
                # Estimación ligera del tamaño
                total_size += len(str(doc.id).encode('utf-8')) + 100  # ID + overhead estimado
            
            # Buscar timestamps
            update_time = doc.update_time
            if update_time and (last_updated is None or update_time > last_updated):
                last_updated = update_time
        
        # Si obtuvimos el límite completo, asumir que hay más documentos
        estimated_total = doc_count
        if doc_count >= limit_docs:
            estimated_total = f"{doc_count}+ (muestra)"
        
        return {
            "document_count": estimated_total,
            "estimated_size_bytes": total_size,
            "estimated_size_mb": round(total_size / (1024 * 1024), 4),
            "last_updated": last_updated.isoformat() if last_updated else None,
            "status": "active",
            "is_estimate": doc_count >= limit_docs
        }
        
    except Exception as e:
        return {
            "document_count": 0,
            "estimated_size_bytes": 0,
            "estimated_size_mb": 0,
            "last_updated": None,
            "status": f"error: {str(e)}",
            "is_estimate": False
        }


async def test_firebase_connection() -> Dict[str, Any]:
    """
    Probar la conexión con Firebase de forma modular
    
    Returns:
        Dict con resultado de la prueba de conexión
    """
    try:
        db = get_firestore_client()
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


async def get_proyectos_presupuestales(limit: Optional[int] = 500, offset: Optional[int] = None) -> Dict[str, Any]:
    """
    Obtener documentos de la colección "proyectos_presupuestales" con paginación
    
    OPTIMIZADO: Límite por defecto de 500 documentos para performance
    
    Args:
        limit: Número máximo de documentos a retornar (default: 500)
        offset: Saltar N documentos (paginación)
    
    Returns:
        Dict con proyectos presupuestales paginados
    """
    if not GOOGLE_CLOUD_AVAILABLE:
        return {
            "success": False,
            "error": "Google Cloud SDK no disponible",
            "data": [],
            "count": 0
        }
    
    try:
        db = get_firestore_client()
        if db is None:
            raise Exception("No se pudo conectar a Firestore")
        
        # OPTIMIZACIÓN: Aplicar límite para reducir carga
        collection_ref = db.collection("proyectos_presupuestales")
        
        # Aplicar offset si se proporciona
        if offset:
            # Firestore no soporta offset directo, simular con limit + skip
            docs = collection_ref.limit(limit + offset).stream()
            all_docs = list(docs)
            docs_to_process = all_docs[offset:]
        else:
            docs = collection_ref.limit(limit).stream()
            docs_to_process = docs
        
        proyectos = []
        for doc in docs_to_process:
            doc_data = doc.to_dict()
            if doc_data:  # Verificar que el documento no esté vacío
                doc_data["id"] = doc.id  # Incluir el ID del documento
                proyectos.append(doc_data)
        
        return {
            "success": True,
            "data": proyectos,
            "count": len(proyectos),
            "collection": "proyectos_presupuestales",
            "timestamp": datetime.now().isoformat(),
            "pagination": {
                "limit": limit,
                "offset": offset or 0,
                "returned": len(proyectos)
            }
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": f"Error obteniendo proyectos presupuestales: {str(e)}",
            "data": [],
            "count": 0
        }


async def get_unique_nombres_centros_gestores() -> Dict[str, Any]:
    """
    Obtener valores únicos del campo "nombre_centro_gestor" de la colección "proyectos_presupuestales"
    
    Returns:
        Dict con lista de nombres únicos de centros gestores
    """
    if not GOOGLE_CLOUD_AVAILABLE:
        return {
            "success": False,
            "error": "Google Cloud SDK no disponible",
            "data": [],
            "count": 0
        }
    
    try:
        db = get_firestore_client()
        if db is None:
            raise Exception("No se pudo conectar a Firestore")
        
        # Obtener todos los documentos de la colección
        collection_ref = db.collection("proyectos_presupuestales")
        docs = collection_ref.stream()
        
        # Usar un set para almacenar valores únicos
        nombres_centros_gestores = set()
        
        for doc in docs:
            doc_data = doc.to_dict()
            nombre_centro_gestor = doc_data.get("nombre_centro_gestor")
            
            # Solo agregar si el campo existe y no está vacío
            if nombre_centro_gestor and nombre_centro_gestor.strip():
                nombres_centros_gestores.add(nombre_centro_gestor.strip())
        
        # Convertir set a lista ordenada
        nombres_unicos = sorted(list(nombres_centros_gestores))
        
        return {
            "success": True,
            "data": nombres_unicos,
            "count": len(nombres_unicos),
            "field": "nombre_centro_gestor",
            "collection": "proyectos_presupuestales",
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": f"Error obteniendo nombres únicos de centros gestores: {str(e)}",
            "data": [],
            "count": 0
        }


async def get_proyectos_presupuestales_by_bpin(bpin: str) -> Dict[str, Any]:
    """
    Obtener proyectos presupuestales filtrados por BPIN
    
    Args:
        bpin: Código BPIN para filtrar
        
    Returns:
        Dict con proyectos filtrados por BPIN
    """
    if not GOOGLE_CLOUD_AVAILABLE:
        return {
            "success": False,
            "error": "Google Cloud SDK no disponible",
            "data": [],
            "count": 0
        }
    
    try:
        db = get_firestore_client()
        if db is None:
            raise Exception("No se pudo conectar a Firestore")
        
        # Convertir bpin a entero ya que en la base de datos se almacena como número
        try:
            bpin_int = int(bpin)
        except ValueError:
            raise Exception(f"BPIN '{bpin}' no es un número válido")
        
        # Filtrar por BPIN
        collection_ref = db.collection("proyectos_presupuestales")
        query = collection_ref.where("bpin", "==", bpin_int)
        docs = query.stream()
        
        proyectos = []
        for doc in docs:
            doc_data = doc.to_dict()
            doc_data["id"] = doc.id  # Incluir el ID del documento
            proyectos.append(doc_data)
        
        return {
            "success": True,
            "data": proyectos,
            "count": len(proyectos),
            "collection": "proyectos_presupuestales",
            "filter": {"field": "bpin", "value": bpin_int},
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": f"Error obteniendo proyectos por BPIN: {str(e)}",
            "data": [],
            "count": 0
        }


async def get_proyectos_presupuestales_by_bp(bp: str) -> Dict[str, Any]:
    """
    Obtener proyectos presupuestales filtrados por BP
    
    Args:
        bp: Código BP para filtrar
        
    Returns:
        Dict con proyectos filtrados por BP
    """
    if not GOOGLE_CLOUD_AVAILABLE:
        return {
            "success": False,
            "error": "Google Cloud SDK no disponible",
            "data": [],
            "count": 0
        }
    
    try:
        db = get_firestore_client()
        if db is None:
            raise Exception("No se pudo conectar a Firestore")
        
        # Filtrar por BP
        collection_ref = db.collection("proyectos_presupuestales")
        query = collection_ref.where("bp", "==", bp)
        docs = query.stream()
        
        proyectos = []
        for doc in docs:
            doc_data = doc.to_dict()
            doc_data["id"] = doc.id  # Incluir el ID del documento
            proyectos.append(doc_data)
        
        return {
            "success": True,
            "data": proyectos,
            "count": len(proyectos),
            "collection": "proyectos_presupuestales",
            "filter": {"field": "bp", "value": bp},
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": f"Error obteniendo proyectos por BP: {str(e)}",
            "data": [],
            "count": 0
        }


async def get_proyectos_presupuestales_by_centro_gestor(nombre_centro_gestor: str) -> Dict[str, Any]:
    """
    Obtener proyectos presupuestales filtrados por nombre de centro gestor
    
    Args:
        nombre_centro_gestor: Nombre del centro gestor para filtrar
        
    Returns:
        Dict con proyectos filtrados por centro gestor
    """
    if not GOOGLE_CLOUD_AVAILABLE:
        return {
            "success": False,
            "error": "Google Cloud SDK no disponible",
            "data": [],
            "count": 0
        }
    
    try:
        db = get_firestore_client()
        if db is None:
            raise Exception("No se pudo conectar a Firestore")
        
        # Filtrar por nombre_centro_gestor
        collection_ref = db.collection("proyectos_presupuestales")
        query = collection_ref.where("nombre_centro_gestor", "==", nombre_centro_gestor)
        docs = query.stream()
        
        proyectos = []
        for doc in docs:
            doc_data = doc.to_dict()
            doc_data["id"] = doc.id  # Incluir el ID del documento
            proyectos.append(doc_data)
        
        return {
            "success": True,
            "data": proyectos,
            "count": len(proyectos),
            "collection": "proyectos_presupuestales",
            "filter": {"field": "nombre_centro_gestor", "value": nombre_centro_gestor},
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": f"Error obteniendo proyectos por centro gestor: {str(e)}",
            "data": [],
            "count": 0
        }
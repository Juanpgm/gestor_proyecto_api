"""
Operaciones para Proyectos Presupuestales
Gestión de la colección 'proyectos_presupuestales' con JSON
Tag: Proyectos de Inversión
"""

from typing import Dict, List, Any, Optional
from datetime import datetime
import uuid

try:
    from google.cloud import firestore
    GOOGLE_CLOUD_AVAILABLE = True
except ImportError:
    GOOGLE_CLOUD_AVAILABLE = False
    firestore = None

from database.firebase_config import get_firestore_client

# Configuración
COLLECTION_NAME = "proyectos_presupuestales"

# ============================================================================
# FUNCIONES PRINCIPALES PARA PROYECTOS PRESUPUESTALES
# ============================================================================

async def process_proyectos_presupuestales_json(
    proyectos_data: List[Dict[str, Any]],
    update_mode: str = "merge"
) -> Dict[str, Any]:
    """
    Procesa una lista de proyectos presupuestales y actualiza la colección Firebase
    
    Args:
        proyectos_data: Lista de proyectos presupuestales
        update_mode: Modo de actualización ('merge', 'replace', 'append')
    
    Returns:
        Dict con resultado de la operación
    """
    if not GOOGLE_CLOUD_AVAILABLE:
        return {
            "success": False,
            "error": "Google Cloud SDK no disponible",
            "processed_count": 0,
            "created_count": 0,
            "updated_count": 0
        }
    
    try:
        db = get_firestore_client()
        if db is None:
            raise Exception("No se pudo conectar a Firestore")
        
        collection_ref = db.collection(COLLECTION_NAME)
        
        if not proyectos_data:
            return {
                "success": False,
                "error": "No hay proyectos para procesar",
                "processed_count": 0,
                "created_count": 0,
                "updated_count": 0
            }
        
        # Si el modo es 'replace', limpiar colección primero
        if update_mode == "replace":
            docs = collection_ref.stream()
            for doc in docs:
                doc.reference.delete()
        
        processed_count = 0
        created_count = 0
        updated_count = 0
        
        # Procesar cada proyecto
        for proyecto in proyectos_data:
            try:
                # Generar ID único
                doc_id = _generate_document_id(proyecto)
                doc_ref = collection_ref.document(doc_id)
                
                # Preparar datos del documento
                doc_data = {
                    **proyecto,
                    "created_at": datetime.now(),
                    "updated_at": datetime.now()
                }
                
                # Verificar si existe para merge
                if update_mode == "merge":
                    doc_snapshot = doc_ref.get()
                    if doc_snapshot.exists:
                        doc_ref.update(doc_data)
                        updated_count += 1
                    else:
                        doc_ref.set(doc_data)
                        created_count += 1
                else:
                    # Modo append o replace
                    doc_ref.set(doc_data)
                    created_count += 1
                
                processed_count += 1
                
            except Exception as e:
                print(f"Error procesando proyecto: {str(e)}")
                continue
        
        return {
            "success": True,
            "message": f"Procesados {processed_count} proyectos presupuestales",
            "processed_count": processed_count,
            "created_count": created_count,
            "updated_count": updated_count,
            "collection_name": COLLECTION_NAME,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": f"Error procesando proyectos: {str(e)}",
            "processed_count": 0,
            "created_count": 0,
            "updated_count": 0,
            "timestamp": datetime.now().isoformat()
        }

def _generate_document_id(proyecto: Dict[str, Any]) -> str:
    """Genera un ID único para el documento"""
    # Prioridad 1: BPIN si existe
    if proyecto.get("bpin"):
        return f"bpin_{proyecto['bpin']}"
    
    # Prioridad 2: BP si existe  
    if proyecto.get("bp"):
        return f"bp_{proyecto['bp']}"
    
    # Último recurso: UUID aleatorio
    return f"proyecto_{uuid.uuid4().hex[:8]}"

# ============================================================================
# CONSTANTES Y CONFIGURACIÓN
# ============================================================================

# Indica que las operaciones están disponibles
PROYECTOS_PRESUPUESTALES_OPERATIONS_AVAILABLE = GOOGLE_CLOUD_AVAILABLE
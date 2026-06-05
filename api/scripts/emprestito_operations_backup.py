"""
Scripts para manejo de Procesos de Empréstito - Versión Limpia
Solo funcionalidades esenciales habilitadas
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

async def get_procesos_emprestito_all() -> Dict[str, Any]:
    """Obtener todos los registros de la colección procesos_emprestito"""
    try:
        if not FIRESTORE_AVAILABLE:
            return {"success": False, "error": "Firebase no disponible", "data": [], "count": 0}
        
        db = get_firestore_client()
        if db is None:
            return {"success": False, "error": "No se pudo conectar a Firestore", "data": [], "count": 0}
        
        collection_ref = db.collection('procesos_emprestito')
        docs = collection_ref.stream()
        procesos_data = []
        
        for doc in docs:
            doc_data = doc.to_dict()
            doc_data['id'] = doc.id  # Agregar ID del documento
            # Limpiar datos de Firebase para serialización JSON
            doc_data_clean = serialize_datetime_objects(doc_data)
            procesos_data.append(doc_data_clean)
        
        return {
            "success": True,
            "data": procesos_data,
            "count": len(procesos_data),
            "collection": "procesos_emprestito",
            "timestamp": datetime.now().isoformat(),
            "message": f"Se obtuvieron {len(procesos_data)} procesos de empréstito exitosamente"
        }
        
    except Exception as e:
        return {
            "success": False, 
            "error": f"Error obteniendo todos los procesos de empréstito: {str(e)}",
            "data": [],
            "count": 0
        }

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

async def actualizar_procesos_emprestito_desde_secop() -> Dict[str, Any]:
    """
    FUNCIÓN TEMPORALMENTE DESHABILITADA
    
    El endpoint PUT /actualizar_procesos_emprestito está deshabilitado por mantenimiento.
    Esta función será reimplementada cuando sea necesario.
    """
    logger.info("⚠️ Función actualizar_procesos_emprestito_desde_secop temporalmente deshabilitada")
    
    return {
        "success": False,
        "message": "⚠️ Función temporalmente deshabilitada",
        "error": "El endpoint PUT /actualizar_procesos_emprestito está deshabilitado por mantenimiento",
        "estadisticas": {
            "total_procesos": 0,
            "procesos_actualizados": 0,
            "procesos_sin_cambios": 0,
            "procesos_no_encontrados_secop": 0,
            "procesos_con_errores": 0,
            "tasa_actualizacion": "0.0%"
        },
        "detalles_actualizaciones": [],
        "procesos_con_errores": [],
        "configuracion": {
            "dataset_secop": "p6dx-8zbt",
            "filtro_aplicado": "nit_entidad = '890399011'",
            "campos_preservados": ["bp", "nombre_banco", "nombre_centro_gestor", "id_paa", "referencia_proceso", "plataforma"],
            "campos_comparados": ["nombre_proceso", "descripcion_proceso", "estado_proceso", "modalidad_contratacion", "etapa"]
        },
        "tiempo_total_segundos": 0,
        "timestamp": datetime.now().isoformat(),
        "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

# Variable de disponibilidad
EMPRESTITO_OPERATIONS_AVAILABLE = FIRESTORE_AVAILABLE

def get_emprestito_operations_status() -> Dict[str, Any]:
    """Obtener estado de las operaciones de empréstito"""
    return {
        "firestore_available": FIRESTORE_AVAILABLE,
        "operations_available": FIRESTORE_AVAILABLE,
        "supported_platforms": ["SECOP", "SECOP II", "SECOP I", "SECOP 2", "SECOP 1", "TVEC"],
        "collections": ["procesos_emprestito", "ordenes_compra_emprestito", "contratos_emprestito"]
    }
"""
Scripts para manejo de Contratos de Empréstito
Función optimizada para el endpoint init_contratos_seguimiento
"""

from typing import Dict, List, Any, Optional
from database.firebase_config import get_firestore_client


def extract_contract_fields(doc_data: Dict[str, Any]) -> Dict[str, Any]:
    """Extraer solo los campos requeridos para el endpoint"""
    registro_origen = doc_data.get('registro_origen', {})
    
    # Normalizar referencia_proceso
    referencia_proceso = registro_origen.get('referencia_proceso', [])
    if isinstance(referencia_proceso, list):
        referencia_proceso_str = ', '.join(referencia_proceso) if referencia_proceso else ''
    else:
        referencia_proceso_str = str(referencia_proceso) if referencia_proceso else ''
    
    return {
        'bpin': doc_data.get('bpin', 0),
        'banco': registro_origen.get('banco', ''),
        'nombre_centro_gestor': doc_data.get('nombre_centro_gestor', ''),
        'estado_contrato': doc_data.get('estado_contrato', ''),
        'referencia_contrato': doc_data.get('referencia_contrato', ''),
        'referencia_proceso': referencia_proceso_str,
        'objeto_contrato': doc_data.get('objeto_contrato', ''),
        'modalidad_contratacion': doc_data.get('modalidad_contratacion', '')
    }


async def get_contratos_init_data(filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Obtener datos de contratos con filtros por referencia_contrato y nombre_centro_gestor"""
    try:
        db = get_firestore_client()
        if db is None:
            return {"success": False, "error": "No se pudo conectar a Firestore", "data": [], "count": 0}
        
        collection_ref = db.collection('contratos_emprestito')
        query = collection_ref
        
        # Aplicar filtro server-side por nombre_centro_gestor (exacto)
        if filters and filters.get('nombre_centro_gestor'):
            query = query.where('nombre_centro_gestor', '==', filters['nombre_centro_gestor'])
        
        # Obtener documentos
        docs = query.stream()
        contratos_data = []
        
        for doc in docs:
            doc_data = doc.to_dict()
            contract_record = extract_contract_fields(doc_data)
            
            # Filtro client-side por referencia_contrato (búsqueda parcial)
            if filters and filters.get('referencia_contrato'):
                search_term = str(filters['referencia_contrato']).lower()
                if search_term not in str(contract_record.get('referencia_contrato', '')).lower():
                    continue
            
            contratos_data.append(contract_record)
        
        return {
            "success": True,
            "data": contratos_data,
            "count": len(contratos_data)
        }
        
    except Exception as e:
        return {
            "success": False, 
            "error": f"Error obteniendo contratos: {str(e)}",
            "data": [],
            "count": 0
        }
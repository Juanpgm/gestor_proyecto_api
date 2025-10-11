"""
Scripts para manejo de Contratos de Empréstito
Función optimizada para el endpoint init_contratos_seguimiento
"""

import re
from typing import Dict, List, Any, Optional
from datetime import datetime
from database.firebase_config import get_firestore_client

# Importar para manejar tipos de Firebase
try:
    from google.cloud.firestore_v1._helpers import DatetimeWithNanoseconds
    FIREBASE_TYPES_AVAILABLE = True
except ImportError:
    FIREBASE_TYPES_AVAILABLE = False
    DatetimeWithNanoseconds = None


def clean_firebase_data(data):
    """
    Limpia datos de Firebase para serialización JSON
    Convierte DatetimeWithNanoseconds y otros tipos no serializables
    """
    if isinstance(data, dict):
        cleaned = {}
        for key, value in data.items():
            cleaned[key] = clean_firebase_data(value)
        return cleaned
    elif isinstance(data, list):
        return [clean_firebase_data(item) for item in data]
    elif FIREBASE_TYPES_AVAILABLE and isinstance(data, DatetimeWithNanoseconds):
        return data.isoformat()
    elif isinstance(data, datetime):
        return data.isoformat()
    else:
        return data


def clean_text_field(text: Any) -> str:
    """Limpiar caracteres especiales de campos de texto manteniendo UTF-8"""
    if not text:
        return ''
    
    # Convertir a string si no lo es
    text_str = str(text)
    
    # Intentar decodificar si está mal codificado
    try:
        # Si el texto viene con encoding incorrecto, intentar corregirlo
        if 'Ã' in text_str:
            # Intentar recodificar desde latin-1 a utf-8
            text_str = text_str.encode('latin-1').decode('utf-8')
    except (UnicodeDecodeError, UnicodeEncodeError):
        # Si hay error en la recodificación, mantener el texto original
        pass
    
    # Eliminar caracteres de control pero mantener caracteres UTF-8 válidos
    text_str = text_str.replace('\n', ' ')  # Saltos de línea
    text_str = text_str.replace('\r', ' ')  # Retorno de carro
    text_str = text_str.replace('\t', ' ')  # Tabulaciones
    text_str = text_str.replace('\v', ' ')  # Tabulación vertical
    text_str = text_str.replace('\f', ' ')  # Form feed
    text_str = text_str.replace('\x0b', ' ')  # Tabulación vertical (hex)
    text_str = text_str.replace('\x0c', ' ')  # Form feed (hex)
    
    # Eliminar espacios múltiples y espacios al inicio/final
    text_str = re.sub(r'\s+', ' ', text_str).strip()
    
    return text_str


def extract_contract_fields(doc_data: Dict[str, Any]) -> Dict[str, Any]:
    """Extraer solo los campos requeridos para el endpoint con texto limpio"""
    registro_origen = doc_data.get('registro_origen', {})
    
    # Normalizar referencia_proceso
    referencia_proceso = registro_origen.get('referencia_proceso', [])
    if isinstance(referencia_proceso, list):
        referencia_proceso_str = ', '.join(referencia_proceso) if referencia_proceso else ''
    else:
        referencia_proceso_str = str(referencia_proceso) if referencia_proceso else ''
    
    # Función auxiliar para obtener campos de fecha con múltiples ubicaciones posibles
    def get_date_field(field_name: str) -> str:
        """Buscar campo de fecha en el documento raíz o en registro_origen"""
        # Primero buscar en el documento raíz
        value = doc_data.get(field_name)
        if value:
            return clean_text_field(value)
        
        # Si no está en raíz, buscar en registro_origen
        value = registro_origen.get(field_name)
        if value:
            return clean_text_field(value)
        
        return ''
    
    return {
        'bpin': doc_data.get('bpin', 0),
        'banco': clean_text_field(registro_origen.get('banco', '')),
        'nombre_centro_gestor': clean_text_field(doc_data.get('nombre_centro_gestor', '')),
        'estado_contrato': clean_text_field(doc_data.get('estado_contrato', '')),
        'referencia_contrato': clean_text_field(doc_data.get('referencia_contrato', '')),
        'referencia_proceso': clean_text_field(referencia_proceso_str),
        'objeto_contrato': clean_text_field(doc_data.get('objeto_contrato', '')),
        'modalidad_contratacion': clean_text_field(doc_data.get('modalidad_contratacion', '')),
        'fecha_inicio_contrato': get_date_field('fecha_inicio_contrato'),
        'fecha_firma': get_date_field('fecha_firma'),
        'fecha_fin_contrato': get_date_field('fecha_fin_contrato')
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


async def get_contratos_emprestito_all() -> Dict[str, Any]:
    """Obtener todos los registros de la colección contratos_emprestito"""
    try:
        db = get_firestore_client()
        if db is None:
            return {"success": False, "error": "No se pudo conectar a Firestore", "data": [], "count": 0}
        
        collection_ref = db.collection('contratos_emprestito')
        docs = collection_ref.stream()
        contratos_data = []
        
        for doc in docs:
            doc_data = doc.to_dict()
            doc_data['id'] = doc.id  # Agregar ID del documento
            # Limpiar datos de Firebase para serialización JSON
            doc_data_clean = clean_firebase_data(doc_data)
            contratos_data.append(doc_data_clean)
        
        return {
            "success": True,
            "data": contratos_data,
            "count": len(contratos_data),
            "collection": "contratos_emprestito",
            "timestamp": datetime.now().isoformat(),
            "message": f"Se obtuvieron {len(contratos_data)} contratos de empréstito exitosamente"
        }
        
    except Exception as e:
        return {
            "success": False, 
            "error": f"Error obteniendo todos los contratos de empréstito: {str(e)}",
            "data": [],
            "count": 0
        }


async def get_contratos_emprestito_by_referencia(referencia_contrato: str) -> Dict[str, Any]:
    """Obtener contratos de empréstito por referencia_contrato"""
    try:
        db = get_firestore_client()
        if db is None:
            return {"success": False, "error": "No se pudo conectar a Firestore", "data": [], "count": 0}
        
        collection_ref = db.collection('contratos_emprestito')
        query = collection_ref.where('referencia_contrato', '==', referencia_contrato)
        docs = query.stream()
        contratos_data = []
        
        for doc in docs:
            doc_data = doc.to_dict()
            doc_data['id'] = doc.id  # Agregar ID del documento
            # Limpiar datos de Firebase para serialización JSON
            doc_data_clean = clean_firebase_data(doc_data)
            contratos_data.append(doc_data_clean)
        
        return {
            "success": True,
            "data": contratos_data,
            "count": len(contratos_data),
            "collection": "contratos_emprestito",
            "filter": {"referencia_contrato": referencia_contrato},
            "timestamp": datetime.now().isoformat(),
            "message": f"Se encontraron {len(contratos_data)} contratos con referencia '{referencia_contrato}'"
        }
        
    except Exception as e:
        return {
            "success": False, 
            "error": f"Error obteniendo contratos por referencia: {str(e)}",
            "data": [],
            "count": 0
        }


async def get_contratos_emprestito_by_centro_gestor(nombre_centro_gestor: str) -> Dict[str, Any]:
    """Obtener contratos de empréstito por nombre_centro_gestor"""
    try:
        db = get_firestore_client()
        if db is None:
            return {"success": False, "error": "No se pudo conectar a Firestore", "data": [], "count": 0}
        
        collection_ref = db.collection('contratos_emprestito')
        query = collection_ref.where('nombre_centro_gestor', '==', nombre_centro_gestor)
        docs = query.stream()
        contratos_data = []
        
        for doc in docs:
            doc_data = doc.to_dict()
            doc_data['id'] = doc.id  # Agregar ID del documento
            # Limpiar datos de Firebase para serialización JSON
            doc_data_clean = clean_firebase_data(doc_data)
            contratos_data.append(doc_data_clean)
        
        return {
            "success": True,
            "data": contratos_data,
            "count": len(contratos_data),
            "collection": "contratos_emprestito",
            "filter": {"nombre_centro_gestor": nombre_centro_gestor},
            "timestamp": datetime.now().isoformat(),
            "message": f"Se encontraron {len(contratos_data)} contratos para el centro gestor '{nombre_centro_gestor}'"
        }
        
    except Exception as e:
        return {
            "success": False, 
            "error": f"Error obteniendo contratos por centro gestor: {str(e)}",
            "data": [],
            "count": 0
        }
"""
Scripts para manejo de Contratos de Empréstito
Función optimizada para el endpoint init_contratos_seguimiento
"""

import re
import asyncio
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


def extract_contract_fields(doc_data: Dict[str, Any], nombre_resumido_proceso: str = '') -> Dict[str, Any]:
    """Extraer solo los campos requeridos para el endpoint con texto limpio"""
    registro_origen = doc_data.get('registro_origen', {})
    
    # Obtener banco - primero del documento raíz, luego de registro_origen
    banco = doc_data.get('banco', '') or registro_origen.get('banco', '')
    
    # Obtener referencia_proceso - primero del documento raíz, luego de registro_origen
    referencia_proceso = doc_data.get('referencia_proceso', '') or registro_origen.get('referencia_proceso', [])
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
        'banco': clean_text_field(banco),
        'nombre_centro_gestor': clean_text_field(doc_data.get('nombre_centro_gestor', '')),
        'estado_contrato': clean_text_field(doc_data.get('estado_contrato', '')),
        'referencia_contrato': clean_text_field(doc_data.get('referencia_contrato', '')),
        'referencia_proceso': clean_text_field(referencia_proceso_str),
        'nombre_resumido_proceso': clean_text_field(nombre_resumido_proceso),
        'objeto_contrato': clean_text_field(doc_data.get('objeto_contrato', '')),
        'modalidad_contratacion': clean_text_field(doc_data.get('modalidad_contratacion', '')),
        'fecha_inicio_contrato': get_date_field('fecha_inicio_contrato'),
        'fecha_firma': get_date_field('fecha_firma'),
        'fecha_fin_contrato': get_date_field('fecha_fin_contrato')
    }


async def get_contratos_init_data(filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Obtener datos combinados de contratos y órdenes de compra con filtros por referencia_contrato y nombre_centro_gestor"""
    try:
        # Obtener datos de contratos
        contratos_result = await get_contratos_emprestito_init_data(filters)
        
        # Obtener datos de órdenes de compra
        ordenes_result = await get_ordenes_compra_init_data(filters)
        
        # Verificar si al menos uno fue exitoso
        if not contratos_result["success"] and not ordenes_result["success"]:
            return {
                "success": False,
                "error": f"Error obteniendo datos: Contratos - {contratos_result.get('error', 'Error desconocido')}, Órdenes - {ordenes_result.get('error', 'Error desconocido')}",
                "data": [],
                "count": 0
            }
        
        # Combinar datos usando programación funcional
        contratos_data = contratos_result["data"] if contratos_result["success"] else []
        ordenes_data = ordenes_result["data"] if ordenes_result["success"] else []
        
        # Función para agregar metadatos de origen
        def add_source_metadata(item: dict, source: str) -> dict:
            """Agregar metadatos de origen a cada item usando programación funcional"""
            return {**item, '_source': source}
        
        # Aplicar metadatos usando programación funcional
        contratos_with_source = [add_source_metadata(item, 'contratos_emprestito') for item in contratos_data]
        ordenes_with_source = [add_source_metadata(item, 'ordenes_compra_emprestito') for item in ordenes_data]
        
        # Combinar datasets
        combined_data = contratos_with_source + ordenes_with_source
        
        # Ordenar por referencia_contrato usando programación funcional
        sorted_data = sorted(combined_data, key=lambda x: str(x.get('referencia_contrato', '')))
        
        return {
            "success": True,
            "data": sorted_data,
            "count": len(sorted_data),
            "sources": {
                "contratos_emprestito": {
                    "count": len(contratos_data),
                    "success": contratos_result["success"]
                },
                "ordenes_compra_emprestito": {
                    "count": len(ordenes_data),
                    "success": ordenes_result["success"]
                }
            },
            "filters_applied": filters or {},
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        return {
            "success": False, 
            "error": f"Error obteniendo datos combinados: {str(e)}",
            "data": [],
            "count": 0
        }


async def get_contratos_emprestito_init_data(filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Obtener datos de contratos con filtros por referencia_contrato y nombre_centro_gestor (función original renombrada)"""
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
            
            # Obtener referencia_proceso para buscar nombre_resumido_proceso
            # Prioridad: campo directo -> registro_origen -> proceso_contractual como fallback
            referencia_proceso = doc_data.get('referencia_proceso', '')
            
            if not referencia_proceso:
                # Intentar desde registro_origen
                registro_origen = doc_data.get('registro_origen', {})
                referencia_proceso = registro_origen.get('referencia_proceso', [])
                if isinstance(referencia_proceso, list):
                    referencia_proceso = referencia_proceso[0] if referencia_proceso else ''
            
            if not referencia_proceso:
                # Como último recurso, intentar con proceso_contractual
                referencia_proceso = doc_data.get('proceso_contractual', '')
            
            # Limpiar y convertir a string
            referencia_proceso_str = str(referencia_proceso).strip() if referencia_proceso else ''
            
            # Obtener nombre_resumido_proceso desde la colección procesos_emprestito
            nombre_resumido_proceso = await get_nombre_resumido_proceso_by_referencia(db, referencia_proceso_str)
            
            contract_record = extract_contract_fields(doc_data, nombre_resumido_proceso)
            
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


async def get_all_procesos_emprestito_map(db) -> Dict[str, str]:
    """Obtener un mapa de referencia_proceso -> nombre_resumido_proceso de una sola vez"""
    try:
        procesos_ref = db.collection('procesos_emprestito')
        docs = procesos_ref.stream()
        
        proceso_map = {}
        for doc in docs:
            doc_data = doc.to_dict()
            referencia = doc_data.get('referencia_proceso', '')
            nombre_resumido = doc_data.get('nombre_resumido_proceso', '')
            
            if referencia and nombre_resumido:
                # Normalizar la referencia
                referencia_clean = str(referencia).strip()
                proceso_map[referencia_clean] = nombre_resumido
        
        return proceso_map
    except Exception as e:
        print(f"Error obteniendo mapa de procesos: {str(e)}")
        return {}

async def get_nombre_resumido_proceso_by_referencia(db, referencia_proceso: str) -> str:
    """Obtener nombre_resumido_proceso desde la colección procesos_emprestito (función legacy para compatibilidad)"""
    try:
        if not referencia_proceso:
            return ""
        
        # Limpiar la referencia (quitar espacios y convertir a string)
        referencia_proceso = str(referencia_proceso).strip()
        
        # Buscar en procesos_emprestito por referencia_proceso
        procesos_ref = db.collection('procesos_emprestito')
        query = procesos_ref.where('referencia_proceso', '==', referencia_proceso)
        docs = list(query.stream())
        
        if docs:
            proceso_data = docs[0].to_dict()
            nombre_resumido = proceso_data.get('nombre_resumido_proceso', '')
            return nombre_resumido
        
        return ""
    except Exception as e:
        print(f"Error obteniendo nombre_resumido_proceso para {referencia_proceso}: {str(e)}")
        return ""


def extract_orden_compra_fields_all(orden_data: dict) -> dict:
    """Extrae y mapea campos de orden de compra usando programación funcional para contratos_emprestito_all"""
    field_mapping = {
        'bpin': lambda x: x.get('bpin', ''),
        'banco': lambda x: x.get('banco', ''),
        'nombre_centro_gestor': lambda x: x.get('nombre_centro_gestor', ''),
        'estado_contrato': lambda x: x.get('estado_orden', ''),
        'referencia_contrato': lambda x: x.get('numero_orden', ''),
        'referencia_proceso': lambda x: x.get('solicitud_id', ''),
        'objeto_contrato': lambda x: x.get('objeto_orden', ''),
        'modalidad_contratacion': lambda x: x.get('modalidad_contratacion', ''),
        'fecha_inicio_contrato': lambda x: x.get('fecha_publicacion_orden', ''),
        'fecha_fin_contrato': lambda x: x.get('fecha_vencimiento_orden', ''),
        'tipo_contrato': lambda x: "Orden de Compra - TVEC",
        'nombre_contratista': lambda x: x.get('nombre_proveedor', ''),
        'valor_contrato': lambda x: x.get('valor_orden', ''),
        'ordenador_gasto': lambda x: x.get('ordenador_gasto', ''),
        'nombre_resumido_proceso': lambda x: x.get('nombre_resumido_proceso', '')
    }
    
    # Aplicar mapeo funcional
    mapped_data = {new_field: mapper(orden_data) for new_field, mapper in field_mapping.items()}
    
    # Agregar ID del documento
    mapped_data['id'] = orden_data.get('id', '')
    
    return mapped_data

async def get_ordenes_compra_all_data(db) -> list:
    """Obtener datos de órdenes de compra mapeados para contratos_emprestito_all (versión legacy)"""
    try:
        collection_ref = db.collection('ordenes_compra_emprestito')
        docs = collection_ref.stream()
        ordenes_data = []
        
        for doc in docs:
            doc_data = doc.to_dict()
            doc_data['id'] = doc.id
            
            # Obtener referencia_proceso (solicitud_id) de la orden
            referencia_proceso = doc_data.get('solicitud_id', '')
            
            # Si referencia_proceso es una lista, tomar el primer elemento
            if isinstance(referencia_proceso, list):
                referencia_proceso = referencia_proceso[0] if referencia_proceso else ''
            
            # Buscar nombre_resumido_proceso en procesos_emprestito
            if referencia_proceso:
                nombre_resumido_proceso = await get_nombre_resumido_proceso_by_referencia(db, referencia_proceso)
                if nombre_resumido_proceso:
                    doc_data['nombre_resumido_proceso'] = nombre_resumido_proceso
            
            # Mapear campos usando programación funcional
            mapped_data = extract_orden_compra_fields_all(doc_data)
            
            # Limpiar datos de Firebase para serialización JSON
            mapped_data_clean = clean_firebase_data(mapped_data)
            ordenes_data.append(mapped_data_clean)
        
        return ordenes_data
        
    except Exception as e:
        print(f"Error obteniendo órdenes de compra: {str(e)}")
        return []

async def get_contratos_emprestito_all_optimized(db, proceso_map: Dict[str, str]) -> list:
    """Obtener contratos de empréstito usando el mapa de procesos precargado"""
    try:
        collection_ref = db.collection('contratos_emprestito')
        docs = collection_ref.stream()
        contratos_data = []
        
        for doc in docs:
            doc_data = doc.to_dict()
            doc_data['id'] = doc.id  # Agregar ID del documento
            
            # Obtener referencia_proceso del contrato
            referencia_proceso = doc_data.get('referencia_proceso', '')
            
            # Si referencia_proceso es una lista, tomar el primer elemento
            if isinstance(referencia_proceso, list):
                referencia_proceso = referencia_proceso[0] if referencia_proceso else ''
            
            # Buscar nombre_resumido_proceso usando el mapa precargado
            if referencia_proceso:
                referencia_clean = str(referencia_proceso).strip()
                nombre_resumido = proceso_map.get(referencia_clean, '')
                if nombre_resumido:
                    doc_data['nombre_resumido_proceso'] = nombre_resumido
            
            # Limpiar datos de Firebase para serialización JSON
            doc_data_clean = clean_firebase_data(doc_data)
            contratos_data.append(doc_data_clean)
        
        return contratos_data
        
    except Exception as e:
        print(f"Error obteniendo contratos: {str(e)}")
        return []

async def get_ordenes_compra_all_data_optimized(db, proceso_map: Dict[str, str]) -> list:
    """Obtener datos de órdenes de compra mapeados usando el mapa de procesos precargado"""
    try:
        collection_ref = db.collection('ordenes_compra_emprestito')
        docs = collection_ref.stream()
        ordenes_data = []
        
        for doc in docs:
            doc_data = doc.to_dict()
            doc_data['id'] = doc.id
            
            # Obtener referencia_proceso (solicitud_id) de la orden
            referencia_proceso = doc_data.get('solicitud_id', '')
            
            # Si referencia_proceso es una lista, tomar el primer elemento
            if isinstance(referencia_proceso, list):
                referencia_proceso = referencia_proceso[0] if referencia_proceso else ''
            
            # Buscar nombre_resumido_proceso usando el mapa precargado
            if referencia_proceso:
                referencia_clean = str(referencia_proceso).strip()
                nombre_resumido = proceso_map.get(referencia_clean, '')
                if nombre_resumido:
                    doc_data['nombre_resumido_proceso'] = nombre_resumido
            
            # Mapear campos usando programación funcional
            mapped_data = extract_orden_compra_fields_all(doc_data)
            
            # Limpiar datos de Firebase para serialización JSON
            mapped_data_clean = clean_firebase_data(mapped_data)
            ordenes_data.append(mapped_data_clean)
        
        return ordenes_data
        
    except Exception as e:
        print(f"Error obteniendo órdenes de compra: {str(e)}")
        return []

async def get_contratos_emprestito_all() -> Dict[str, Any]:
    """Obtener todos los registros de las colecciones contratos_emprestito y ordenes_compra_emprestito con campos unificados - VERSIÓN OPTIMIZADA"""
    try:
        db = get_firestore_client()
        if db is None:
            return {"success": False, "error": "No se pudo conectar a Firestore", "data": [], "count": 0}
        
        # 🚀 OPTIMIZACIÓN 1: Cargar mapa de procesos una sola vez
        print("📊 Cargando mapa de procesos...")
        proceso_map = await get_all_procesos_emprestito_map(db)
        print(f"✅ Mapa de procesos cargado: {len(proceso_map)} procesos")
        
        # 🚀 OPTIMIZACIÓN 2: Usar funciones optimizadas con el mapa precargado
        # Ejecutar ambas consultas en paralelo
        contratos_task = get_contratos_emprestito_all_optimized(db, proceso_map)
        ordenes_task = get_ordenes_compra_all_data_optimized(db, proceso_map)
        
        print("🔄 Ejecutando consultas en paralelo...")
        contratos_data, ordenes_data = await asyncio.gather(contratos_task, ordenes_task)
        
        print(f"✅ Contratos obtenidos: {len(contratos_data)}")
        print(f"✅ Órdenes obtenidas: {len(ordenes_data)}")
        
        # Combinar ambas colecciones
        all_data = contratos_data + ordenes_data
        
        return {
            "success": True,
            "data": all_data,
            "count": len(all_data),
            "contratos_count": len(contratos_data),
            "ordenes_count": len(ordenes_data),
            "collections": ["contratos_emprestito", "ordenes_compra_emprestito"],
            "timestamp": datetime.now().isoformat(),
            "message": f"🚀 OPTIMIZADO: Se obtuvieron {len(contratos_data)} contratos y {len(ordenes_data)} órdenes de compra exitosamente ({len(all_data)} registros totales)"
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


def extract_orden_compra_fields(doc_data: Dict[str, Any], nombre_resumido_proceso: str = '') -> Dict[str, Any]:
    """Extraer y mapear campos de órdenes de compra al formato de contratos con programación funcional"""
    
    # Funciones auxiliares puras
    def safe_get(data: dict, key: str, default='') -> str:
        """Obtener valor de manera segura y limpia"""
        value = data.get(key, default)
        return clean_text_field(str(value)) if value else ''
    
    def safe_get_int(data: dict, key: str, default=0) -> int:
        """Obtener valor entero de manera segura"""
        value = data.get(key, default)
        try:
            return int(value) if value else default
        except (ValueError, TypeError):
            return default
    
    # Si no se pasó nombre_resumido_proceso como parámetro, intentar obtenerlo del documento
    if not nombre_resumido_proceso:
        nombre_resumido_proceso = doc_data.get('nombre_resumido_proceso', '')
    
    # Mapeo de campos usando programación funcional
    field_mappings = {
        'bpin': lambda data: safe_get_int(data, 'bpin'),
        'banco': lambda data: safe_get(data, 'nombre_banco'),
        'nombre_centro_gestor': lambda data: safe_get(data, 'nombre_centro_gestor'),
        'estado_contrato': lambda data: safe_get(data, 'estado_orden'),
        'referencia_contrato': lambda data: safe_get(data, 'numero_orden'),
        'referencia_proceso': lambda data: safe_get(data, 'solicitud_id'),
        'nombre_resumido_proceso': lambda data: clean_text_field(nombre_resumido_proceso),
        'objeto_contrato': lambda data: safe_get(data, 'objeto_orden'),
        'modalidad_contratacion': lambda data: safe_get(data, 'modalidad_contratacion'),
        'fecha_inicio_contrato': lambda data: safe_get(data, 'fecha_publicacion_orden'),
        'fecha_firma': lambda data: '',  # No disponible en órdenes de compra
        'fecha_fin_contrato': lambda data: safe_get(data, 'fecha_vencimiento_orden')
    }
    
    # Aplicar mapeos usando programación funcional
    return {key: mapper(doc_data) for key, mapper in field_mappings.items()}


async def get_ordenes_compra_init_data(filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Obtener datos de órdenes de compra con filtros por referencia_contrato y nombre_centro_gestor"""
    try:
        db = get_firestore_client()
        if db is None:
            return {"success": False, "error": "No se pudo conectar a Firestore", "data": [], "count": 0}
        
        collection_ref = db.collection('ordenes_compra_emprestito')
        query = collection_ref
        
        # Aplicar filtro server-side por nombre_centro_gestor (exacto)
        if filters and filters.get('nombre_centro_gestor'):
            query = query.where('nombre_centro_gestor', '==', filters['nombre_centro_gestor'])
        
        # Obtener documentos
        docs = query.stream()
        ordenes_data = []
        
        for doc in docs:
            doc_data = doc.to_dict()
            
            # Las órdenes de compra ya tienen nombre_resumido_proceso directamente
            nombre_resumido_proceso = doc_data.get('nombre_resumido_proceso', '')
            
            orden_record = extract_orden_compra_fields(doc_data, nombre_resumido_proceso)
            
            # Filtro client-side por referencia_contrato (búsqueda parcial usando numero_orden)
            if filters and filters.get('referencia_contrato'):
                search_term = str(filters['referencia_contrato']).lower()
                if search_term not in str(orden_record.get('referencia_contrato', '')).lower():
                    continue
            
            ordenes_data.append(orden_record)
        
        return {
            "success": True,
            "data": ordenes_data,
            "count": len(ordenes_data)
        }
        
    except Exception as e:
        return {
            "success": False, 
            "error": f"Error obteniendo órdenes de compra: {str(e)}",
            "data": [],
            "count": 0
        }
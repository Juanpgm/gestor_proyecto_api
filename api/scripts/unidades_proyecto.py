"""
Scripts para manejo de Unidades de Proyecto
Funciones puras y modulares para interactuar con la colección unidades_proyecto
"""

from typing import Dict, List, Any, Optional, Union
from datetime import datetime
from google.cloud import firestore
from google.api_core import exceptions as gcp_exceptions

from database.firebase_config import FirebaseManager


async def get_all_unidades_proyecto() -> Dict[str, Any]:
    """
    Obtener todas las unidades de proyecto de Firestore
    
    Returns:
        Dict con la información de todas las unidades de proyecto
    """
    try:
        firebase_manager = FirebaseManager()
        db = firebase_manager.get_firestore_client()
        if db is None:
            return {
                "success": False,
                "error": "No se pudo conectar a Firestore",
                "data": [],
                "count": 0
            }
        
        # Obtener referencia a la colección
        collection_ref = db.collection('unidades_proyecto')
        
        # Obtener todos los documentos
        docs = collection_ref.stream()
        
        unidades = []
        for doc in docs:
            doc_data = doc.to_dict()
            doc_data['id'] = doc.id  # Agregar el ID del documento
            
            # Agregar metadatos del documento
            doc_data['_metadata'] = {
                'create_time': doc.create_time.isoformat() if doc.create_time else None,
                'update_time': doc.update_time.isoformat() if doc.update_time else None
            }
            
            unidades.append(doc_data)
        
        return {
            "success": True,
            "data": unidades,
            "count": len(unidades),
            "timestamp": datetime.now().isoformat(),
            "collection": "unidades_proyecto"
        }
        
    except gcp_exceptions.NotFound:
        return {
            "success": False,
            "error": "Colección 'unidades_proyecto' no encontrada",
            "data": [],
            "count": 0
        }
    except gcp_exceptions.PermissionDenied:
        return {
            "success": False,
            "error": "Permisos insuficientes para acceder a la colección",
            "data": [],
            "count": 0
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Error obteniendo unidades de proyecto: {str(e)}",
            "data": [],
            "count": 0
        }


async def get_unidades_proyecto_summary() -> Dict[str, Any]:
    """
    Obtener resumen estadístico de las unidades de proyecto
    
    Returns:
        Dict con estadísticas de las unidades de proyecto
    """
    try:
        result = await get_all_unidades_proyecto()
        
        if not result["success"]:
            return result
        
        unidades = result["data"]
        
        # Calcular estadísticas
        total = len(unidades)
        
        # Contar por estado si existe el campo
        estados = {}
        proyectos_unicos = set()
        
        for unidad in unidades:
            # Estado
            estado = unidad.get('estado', 'sin_estado')
            estados[estado] = estados.get(estado, 0) + 1
            
            # Proyectos únicos
            proyecto = unidad.get('proyecto_id') or unidad.get('proyecto')
            if proyecto:
                proyectos_unicos.add(proyecto)
        
        return {
            "success": True,
            "summary": {
                "total_unidades": total,
                "proyectos_unicos": len(proyectos_unicos),
                "distribucion_por_estado": estados,
                "campos_comunes": _get_common_fields(unidades) if unidades else []
            },
            "timestamp": datetime.now().isoformat(),
            "collection": "unidades_proyecto"
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": f"Error generando resumen: {str(e)}",
            "summary": {}
        }


def _get_common_fields(unidades: List[Dict]) -> List[str]:
    """
    Función auxiliar para obtener campos comunes en los documentos
    
    Args:
        unidades: Lista de unidades de proyecto
        
    Returns:
        Lista de campos que aparecen en al menos el 80% de los documentos
    """
    if not unidades:
        return []
    
    field_count = {}
    total_docs = len(unidades)
    
    for unidad in unidades:
        # Contar campos de nivel raíz
        for field in unidad.keys():
            if not field.startswith('_'):  # Ignorar metadatos
                field_count[field] = field_count.get(field, 0) + 1
        
        # Contar campos dentro de properties
        properties = unidad.get('properties', {})
        for field in properties.keys():
            property_field = f"properties.{field}"
            field_count[property_field] = field_count.get(property_field, 0) + 1
    
    # Campos que aparecen en al menos 80% de los documentos
    common_fields = [
        field for field, count in field_count.items()
        if count >= (total_docs * 0.8)
    ]
    
    return sorted(common_fields)


async def validate_unidades_proyecto_collection() -> Dict[str, Any]:
    """
    Validar la existencia y estructura de la colección unidades_proyecto
    
    Returns:
        Dict con información de validación
    """
    try:
        firebase_manager = FirebaseManager()
        db = firebase_manager.get_firestore_client()
        if db is None:
            return {
                "valid": False,
                "error": "No se pudo conectar a Firestore"
            }
        
        collection_ref = db.collection('unidades_proyecto')
        
        # Verificar si existe al menos un documento
        docs = collection_ref.limit(1).stream()
        doc_list = list(docs)
        
        if not doc_list:
            return {
                "valid": False,
                "error": "La colección existe pero está vacía",
                "collection_exists": True,
                "document_count": 0
            }
        
        # Obtener estructura del primer documento
        first_doc = doc_list[0]
        sample_structure = list(first_doc.to_dict().keys())
        
        return {
            "valid": True,
            "collection_exists": True,
            "sample_fields": sample_structure,
            "timestamp": datetime.now().isoformat()
        }
        
    except gcp_exceptions.NotFound:
        return {
            "valid": False,
            "error": "Colección 'unidades_proyecto' no encontrada",
            "collection_exists": False
        }
    except Exception as e:
        return {
            "valid": False,
            "error": f"Error validando colección: {str(e)}"
        }


async def filter_unidades_proyecto(
    bpin: Optional[str] = None,
    referencia_proceso: Optional[str] = None,
    referencia_contrato: Optional[str] = None,
    estado: Optional[str] = None,
    upid: Optional[str] = None,
    barrio_vereda: Optional[str] = None,
    comuna_corregimiento: Optional[str] = None,
    nombre_up: Optional[str] = None,
    fuente_financiacion: Optional[str] = None,
    ano: Optional[Union[int, str]] = None,
    tipo_intervencion: Optional[str] = None,
    nombre_centro_gestor: Optional[str] = None,
    limit: Optional[int] = None,
    include_metadata: bool = False
) -> Dict[str, Any]:
    """
    Filtrar unidades de proyecto por múltiples criterios de forma optimizada
    
    Args:
        bpin: Filtro por BPIN
        referencia_proceso: Filtro por referencia del proceso
        referencia_contrato: Filtro por referencia del contrato
        estado: Filtro por estado
        upid: Filtro por ID de unidad de proyecto
        barrio_vereda: Filtro por barrio o vereda
        comuna_corregimiento: Filtro por comuna o corregimiento
        nombre_up: Filtro por nombre de UP (búsqueda parcial)
        fuente_financiacion: Filtro por fuente de financiación
        ano: Filtro por año
        tipo_intervencion: Filtro por tipo de intervención
        nombre_centro_gestor: Filtro por nombre del centro gestor
        limit: Límite de resultados
        include_metadata: Si incluir metadatos de documentos
    
    Returns:
        Dict con los resultados filtrados y estadísticas
    """
    try:
        firebase_manager = FirebaseManager()
        db = firebase_manager.get_firestore_client()
        if db is None:
            return {
                "success": False,
                "error": "No se pudo conectar a Firestore",
                "data": [],
                "count": 0,
                "filters_applied": {}
            }
        
        collection_ref = db.collection('unidades_proyecto')
        query = collection_ref
        
        # Construir filtros aplicados
        filters_applied = {}
        
        # Aplicar filtros de igualdad exacta (los campos están en properties)
        if bpin:
            query = query.where('properties.bpin', '==', bpin)
            filters_applied['bpin'] = bpin
            
        if referencia_proceso:
            query = query.where('properties.referencia_proceso', '==', referencia_proceso)
            filters_applied['referencia_proceso'] = referencia_proceso
            
        if referencia_contrato:
            query = query.where('properties.referencia_contrato', '==', referencia_contrato)
            filters_applied['referencia_contrato'] = referencia_contrato
            
        if estado:
            query = query.where('properties.estado', '==', estado)
            filters_applied['estado'] = estado
            
        if upid:
            query = query.where('properties.upid', '==', upid)
            filters_applied['upid'] = upid
            
        if barrio_vereda:
            query = query.where('properties.barrio_vereda', '==', barrio_vereda)
            filters_applied['barrio_vereda'] = barrio_vereda
            
        if comuna_corregimiento:
            query = query.where('properties.comuna_corregimiento', '==', comuna_corregimiento)
            filters_applied['comuna_corregimiento'] = comuna_corregimiento
            
        if fuente_financiacion:
            query = query.where('properties.fuente_financiacion', '==', fuente_financiacion)
            filters_applied['fuente_financiacion'] = fuente_financiacion
            
        if ano:
            query = query.where('properties.ano', '==', str(ano))  # Los años están como string
            filters_applied['ano'] = str(ano)
            
        if tipo_intervencion:
            query = query.where('properties.tipo_intervencion', '==', tipo_intervencion)
            filters_applied['tipo_intervencion'] = tipo_intervencion
            
        if nombre_centro_gestor:
            query = query.where('properties.nombre_centro_gestor', '==', nombre_centro_gestor)
            filters_applied['nombre_centro_gestor'] = nombre_centro_gestor
        
        # Aplicar límite si se especifica
        if limit and limit > 0:
            query = query.limit(limit)
            filters_applied['limit'] = limit
        
        # Ejecutar consulta
        docs = query.stream()
        
        unidades = []
        for doc in docs:
            doc_data = doc.to_dict()
            doc_data['id'] = doc.id
            
            # Filtro por nombre (búsqueda parcial) - se aplica post-consulta
            if nombre_up:
                properties = doc_data.get('properties', {})
                nombre_campo = properties.get('nombre_up', '') or properties.get('nombre', '')
                if nombre_up.lower() not in str(nombre_campo).lower():
                    continue
                filters_applied['nombre_up'] = f"contains '{nombre_up}'"
            
            # Asegurar que se incluyan los datos de geometría/coordenadas
            geometry = doc_data.get('geometry', {})
            if geometry and geometry.get('coordinates'):
                doc_data['coordinates'] = geometry.get('coordinates')
                doc_data['latitude'] = geometry.get('coordinates', [None, None])[1]
                doc_data['longitude'] = geometry.get('coordinates', [None, None])[0]
            
            if include_metadata:
                doc_data['_metadata'] = {
                    'create_time': doc.create_time.isoformat() if doc.create_time else None,
                    'update_time': doc.update_time.isoformat() if doc.update_time else None
                }
            
            unidades.append(doc_data)
        
        return {
            "success": True,
            "data": unidades,
            "count": len(unidades),
            "filters_applied": filters_applied,
            "timestamp": datetime.now().isoformat(),
            "collection": "unidades_proyecto"
        }
        
    except gcp_exceptions.NotFound:
        return {
            "success": False,
            "error": "Colección 'unidades_proyecto' no encontrada",
            "data": [],
            "count": 0,
            "filters_applied": {}
        }
    except gcp_exceptions.PermissionDenied:
        return {
            "success": False,
            "error": "Permisos insuficientes para acceder a la colección",
            "data": [],
            "count": 0,
            "filters_applied": {}
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Error filtrando unidades de proyecto: {str(e)}",
            "data": [],
            "count": 0,
            "filters_applied": {}
        }



async def get_dashboard_summary() -> Dict[str, Any]:
    """
    Obtener resumen optimizado para dashboards
    
    Returns:
        Dict con métricas clave y distribuciones para dashboards
    """
    try:
        # Obtener todas las unidades para calcular métricas
        result = await get_all_unidades_proyecto()
        
        if not result["success"]:
            return result
        
        unidades = result["data"]
        total = len(unidades)
        
        # Calcular distribuciones para dashboards
        distribuciones = {
            "por_estado": {},
            "por_ano": {},
            "por_fuente_financiacion": {},
            "por_comuna_corregimiento": {},
            "por_barrio_vereda": {}
        }
        
        # Métricas adicionales
        bpins_unicos = set()
        procesos_unicos = set()
        contratos_unicos = set()
        
        for unidad in unidades:
            # Acceder a los datos dentro de properties
            properties = unidad.get('properties', {})
            
            # Distribuciones
            estado = properties.get('estado', 'sin_estado')
            distribuciones["por_estado"][estado] = distribuciones["por_estado"].get(estado, 0) + 1
            
            ano = properties.get('ano')
            if ano:
                distribuciones["por_ano"][str(ano)] = distribuciones["por_ano"].get(str(ano), 0) + 1
            
            fuente = properties.get('fuente_financiacion')
            if fuente:
                distribuciones["por_fuente_financiacion"][fuente] = distribuciones["por_fuente_financiacion"].get(fuente, 0) + 1
            
            comuna = properties.get('comuna_corregimiento')
            if comuna:
                distribuciones["por_comuna_corregimiento"][comuna] = distribuciones["por_comuna_corregimiento"].get(comuna, 0) + 1
            
            barrio = properties.get('barrio_vereda')
            if barrio:
                distribuciones["por_barrio_vereda"][barrio] = distribuciones["por_barrio_vereda"].get(barrio, 0) + 1
            
            # Contadores únicos
            if properties.get('bpin'):
                bpins_unicos.add(properties['bpin'])
            if properties.get('referencia_proceso'):
                procesos_unicos.add(properties['referencia_proceso'])
            if properties.get('referencia_contrato'):
                contratos_unicos.add(properties['referencia_contrato'])
        
        return {
            "success": True,
            "metrics": {
                "total_unidades": total,
                "bpins_unicos": len(bpins_unicos),
                "procesos_unicos": len(procesos_unicos),
                "contratos_unicos": len(contratos_unicos)
            },
            "distribuciones": distribuciones,
            "timestamp": datetime.now().isoformat(),
            "collection": "unidades_proyecto"
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": f"Error generando resumen de dashboard: {str(e)}",
            "metrics": {},
            "distribuciones": {}
        }
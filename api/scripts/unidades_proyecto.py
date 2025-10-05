"""
Scripts simples para manejo de Unidades de Proyecto - VERSIÓN SIMPLIFICADA
Sistema de cache simplificado y optimizado
"""

import os
import time
from typing import Dict, List, Any, Optional, Union
from database.firebase_config import get_firestore_client

# ✅ PROGRAMACIÓN FUNCIONAL: Sin cache global que cause problemas de estado
# ✅ Sin variables mutables globales que persistan datos entre requests
# ✅ Cada request es independiente y sin efectos colaterales

print("� Módulo unidades_proyecto inicializado sin cache (programación funcional)")


def _convert_to_int(value) -> Optional[int]:
    """Convertir valor a entero, manejo seguro"""
    if value is None or value == '' or str(value).strip() in ['null', 'None', 'nan', 'NaN']:
        return None
    try:
        # Si es string, limpiar y convertir
        if isinstance(value, str):
            cleaned = value.strip().replace(',', '').replace('$', '').replace(' ', '')
            if cleaned:
                return int(float(cleaned))  # float primero por si tiene decimales
        else:
            return int(float(value))
    except (ValueError, TypeError):
        return None

def _convert_to_float(value) -> Optional[float]:
    """Convertir valor a float, manejo seguro"""
    if value is None or value == '' or str(value).strip() in ['null', 'None', 'nan', 'NaN']:
        return None
    try:
        # Si es string, limpiar y convertir
        if isinstance(value, str):
            cleaned = value.strip().replace(',', '').replace('%', '').replace(' ', '')
            if cleaned:
                return float(cleaned)
        else:
            return float(value)
    except (ValueError, TypeError):
        return None

def apply_client_side_filters(data: List[Dict[str, Any]], filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """
    Aplicar filtros del lado del cliente a los datos obtenidos de Firestore
    
    Filtros soportados:
    - upid: filtrar por ID específico o lista de IDs
    - estado: filtrar por estado del proyecto
    - tipo_intervencion: filtrar por tipo de intervención
    - departamento: filtrar por departamento
    - municipio: filtrar por municipio
    - comuna_corregimiento: filtrar por comuna o corregimiento específico
    - barrio_vereda: filtrar por barrio o vereda específico
    - fecha_desde / fecha_hasta: filtrar por rango de fechas
    - search: búsqueda de texto en campos principales
    - has_geometry: solo registros con/sin geometría
    - bbox: bounding box geográfico [min_lng, min_lat, max_lng, max_lat]
    """
    if not filters or not data:
        return data
    
    filtered_data = data.copy()
    
    try:
        # Filtro por UPID
        if 'upid' in filters and filters['upid']:
            upid_filter = filters['upid']
            if isinstance(upid_filter, list):
                filtered_data = [item for item in filtered_data 
                               if item.get('upid') in upid_filter or 
                                  item.get('properties', {}).get('upid') in upid_filter]
            else:
                filtered_data = [item for item in filtered_data 
                               if item.get('upid') == upid_filter or 
                                  item.get('properties', {}).get('upid') == upid_filter]
        
        # Filtro por estado
        if 'estado' in filters and filters['estado']:
            estado_value = filters['estado']
            filtered_data = [item for item in filtered_data
                           if item.get('estado') == estado_value or
                              item.get('properties', {}).get('estado') == estado_value]
        
        # Filtro por tipo de intervención
        if 'tipo_intervencion' in filters and filters['tipo_intervencion']:
            tipo_value = filters['tipo_intervencion']
            filtered_data = [item for item in filtered_data
                           if item.get('tipo_intervencion') == tipo_value or
                              item.get('properties', {}).get('tipo_intervencion') == tipo_value]
        
        # Filtro por departamento
        if 'departamento' in filters and filters['departamento']:
            dept_value = filters['departamento']
            filtered_data = [item for item in filtered_data
                           if item.get('departamento') == dept_value or
                              item.get('properties', {}).get('departamento') == dept_value]
        
        # Filtro por municipio
        if 'municipio' in filters and filters['municipio']:
            mun_value = filters['municipio']
            filtered_data = [item for item in filtered_data
                           if item.get('municipio') == mun_value or
                              item.get('properties', {}).get('municipio') == mun_value]
        
        # Filtro por comuna/corregimiento
        if 'comuna_corregimiento' in filters and filters['comuna_corregimiento']:
            comuna_value = filters['comuna_corregimiento']
            filtered_data = [item for item in filtered_data
                           if item.get('comuna_corregimiento') == comuna_value or
                              item.get('properties', {}).get('comuna_corregimiento') == comuna_value]
        
        # Filtro por barrio/vereda
        if 'barrio_vereda' in filters and filters['barrio_vereda']:
            barrio_value = filters['barrio_vereda']
            filtered_data = [item for item in filtered_data
                           if item.get('barrio_vereda') == barrio_value or
                              item.get('properties', {}).get('barrio_vereda') == barrio_value]
        
        # Filtro por presupuesto_base (rango numérico mínimo)
        if 'presupuesto_base' in filters and filters['presupuesto_base']:
            try:
                min_presupuesto = float(filters['presupuesto_base'])
                filtered_data = [item for item in filtered_data
                               if (item.get('presupuesto_base') and float(item['presupuesto_base']) >= min_presupuesto) or
                                  (item.get('properties', {}).get('presupuesto_base') and 
                                   float(item['properties']['presupuesto_base']) >= min_presupuesto)]
            except (ValueError, TypeError):
                pass
        
        # Filtro por avance_obra (porcentaje mínimo)
        if 'avance_obra' in filters and filters['avance_obra']:
            try:
                min_avance = float(filters['avance_obra'])
                filtered_data = [item for item in filtered_data
                               if (item.get('avance_obra') and float(item['avance_obra']) >= min_avance) or
                                  (item.get('properties', {}).get('avance_obra') and 
                                   float(item['properties']['avance_obra']) >= min_avance)]
            except (ValueError, TypeError):
                pass
        
        # Filtro por búsqueda de texto
        if 'search' in filters and filters['search']:
            search_term = str(filters['search']).lower()
            filtered_data = [item for item in filtered_data
                           if search_in_record(item, search_term)]
        
        # Filtro por presencia de geometría
        if 'has_geometry' in filters:
            has_geom = bool(filters['has_geometry'])
            geometry_fields = ['geometry', 'coordinates', 'lat', 'lng', 'latitude', 'longitude', 'coordenadas']
            
            if has_geom:
                filtered_data = [item for item in filtered_data
                               if any(item.get(field) is not None for field in geometry_fields)]
            else:
                filtered_data = [item for item in filtered_data
                               if not any(item.get(field) is not None for field in geometry_fields)]
        
        # Filtro por bounding box geográfico
        if 'bbox' in filters and filters['bbox'] and len(filters['bbox']) == 4:
            min_lng, min_lat, max_lng, max_lat = filters['bbox']
            filtered_data = [item for item in filtered_data
                           if is_point_in_bbox(item, min_lng, min_lat, max_lng, max_lat)]
        
        # Filtros de fecha
        if 'fecha_desde' in filters and filters['fecha_desde']:
            # Implementación básica - buscar campos de fecha comunes
            fecha_desde = str(filters['fecha_desde'])
            filtered_data = [item for item in filtered_data
                           if check_date_filter(item, 'desde', fecha_desde)]
        
        if 'fecha_hasta' in filters and filters['fecha_hasta']:
            fecha_hasta = str(filters['fecha_hasta'])
            filtered_data = [item for item in filtered_data
                           if check_date_filter(item, 'hasta', fecha_hasta)]
        
        return filtered_data
        
    except Exception as e:
        print(f"⚠️ WARNING: Error aplicando filtros: {str(e)}")
        return data  # Devolver datos originales si hay error en filtros


def search_in_record(record: Dict[str, Any], search_term: str) -> bool:
    """Buscar término en campos principales del registro"""
    searchable_fields = [
        'upid', 'nombre', 'descripcion', 'estado', 'tipo_intervencion',
        'departamento', 'municipio', 'comuna_corregimiento', 'barrio_vereda', 'nombre_proyecto'
    ]
    
    # Buscar en campos directos
    for field in searchable_fields:
        if field in record and record[field] and search_term in str(record[field]).lower():
            return True
    
    # Buscar en properties
    properties = record.get('properties', {})
    for field in searchable_fields:
        if field in properties and properties[field] and search_term in str(properties[field]).lower():
            return True
    
    return False


def is_point_in_bbox(record: Dict[str, Any], min_lng: float, min_lat: float, max_lng: float, max_lat: float) -> bool:
    """Verificar si un punto está dentro del bounding box"""
    try:
        # Buscar coordenadas en diferentes campos posibles
        lat = record.get('lat') or record.get('latitude') or record.get('properties', {}).get('lat')
        lng = record.get('lng') or record.get('longitude') or record.get('properties', {}).get('lng')
        
        # También buscar en coordenadas como array [lng, lat]
        if not lat or not lng:
            coords = record.get('coordinates') or record.get('coordenadas')
            if coords and isinstance(coords, list) and len(coords) >= 2:
                lng, lat = coords[0], coords[1]
        
        if lat is not None and lng is not None:
            return (min_lat <= float(lat) <= max_lat and 
                   min_lng <= float(lng) <= max_lng)
        
        return False
    except:
        return False


def check_date_filter(record: Dict[str, Any], filter_type: str, date_value: str) -> bool:
    """Verificar filtros de fecha básicos"""
    try:
        date_fields = ['fecha', 'fecha_creacion', 'fecha_actualizacion', 'created_at', 'updated_at']
        
        for field in date_fields:
            field_value = record.get(field) or record.get('properties', {}).get(field)
            if field_value:
                # Comparación básica de strings - mejorar según formato de fechas
                if filter_type == 'desde':
                    return str(field_value) >= date_value
                elif filter_type == 'hasta':
                    return str(field_value) <= date_value
        
        return True  # Si no hay fechas, incluir el registro
    except:
        return True

async def get_all_unidades_proyecto_simple(limit: Optional[int] = None) -> Dict[str, Any]:
    """
    Función simple para obtener TODOS los documentos de unidades-proyecto
    Sin cache ni optimizaciones complejas, para NextJS
    """
    try:
        print(f"🔍 DEBUG: get_all_unidades_proyecto_simple llamada con limit={limit}")
        
        db = get_firestore_client()
        if db is None:
            return {
                "success": False,
                "error": "No se pudo conectar a Firestore",
                "data": [],
                "count": 0
            }
        
        # Obtener la colección
        collection_ref = db.collection('unidades_proyecto')
        
        # Aplicar límite solo si se especifica explícitamente
        if limit is not None and limit > 0:
            print(f"🔍 DEBUG: Aplicando límite de {limit} documentos")
            query = collection_ref.limit(limit)
        else:
            print(f"🔍 DEBUG: SIN LÍMITE - obteniendo TODOS los documentos")
            query = collection_ref  # Sin límite = todos los documentos
        
        # Ejecutar consulta
        docs = query.stream()
        data = []
        doc_count = 0
        
        for doc in docs:
            doc_data = doc.to_dict()
            # No agregamos ID redundante, upid es suficiente
            data.append(doc_data)
            doc_count += 1
            
            # Log cada 100 documentos para mostrar progreso
            if doc_count % 100 == 0:
                print(f"🔍 DEBUG: Procesados {doc_count} documentos...")
        
        print(f"🔍 DEBUG: TOTAL procesados: {len(data)} documentos")
        
        return {
            "success": True,
            "data": data,
            "count": len(data),
            "message": f"Obtenidos {len(data)} documentos de unidades_proyecto"
        }
        
    except Exception as e:
        print(f"❌ ERROR en get_all_unidades_proyecto_simple: {str(e)}")
        import traceback
        print(f"❌ TRACEBACK: {traceback.format_exc()}")
        
        return {
            "success": False,
            "error": f"Error obteniendo datos: {str(e)}",
            "data": [],
            "count": 0
        }


async def get_unidades_proyecto_geometry(filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Obtener datos de unidades-proyecto para visualización geoespacial
    Especializado para NextJS - Incluye TODOS los registros (646 proyectos)
    
    SOLUCIÓN ÚNICA APLICADA: Incluye todos los registros, tengan o no geometría válida
    - Registros sin geometría usan coordenadas [0,0] como placeholder
    - Campo 'has_valid_geometry' indica si las coordenadas son reales
    - El frontend puede filtrar por 'has_valid_geometry' si necesita solo registros con coordenadas
    
    Filtros soportados:
    - upid: ID específico o lista de IDs
    - estado: estado del proyecto
    - tipo_intervencion: tipo de intervención
    - nombre_centro_gestor: centro gestor específico
    - comuna_corregimiento: comuna o corregimiento específico
    - barrio_vereda: barrio o vereda específico
    - bbox: bounding box [min_lng, min_lat, max_lng, max_lat]
    - search: búsqueda de texto en campos principales
    - limit: límite de registros a retornar
    """
    try:
        # ============================================
        # ESTRATEGIA CACHE-FIRST (12 horas)
        # ✅ PROGRAMACIÓN FUNCIONAL: Sin cache, datos frescos siempre
        
        # Cargar datos desde Firestore
        print("🔄 DEBUG: Cargando datos desde Firestore")
        
        db = get_firestore_client()
        if db is None:
            return {
                "success": False,
                "error": "No se pudo conectar a Firestore",
                "data": [],
                "count": 0
            }
        
        # Consulta simple
        query = db.collection('unidades_proyecto')
        
        # Procesar documentos
        docs = query.stream()
        geometry_data = []
        total_docs_processed = 0
        
        # Campos esenciales
        geo_fields = ['upid', 'coordenadas', 'geometry', 'coordinates', 'lat', 'lng']
        viz_fields = ['comuna_corregimiento', 'barrio_vereda', 'estado', 'tipo_intervencion', 'nombre_centro_gestor', 'presupuesto_base', 'avance_obra']
        
        for doc in docs:
            total_docs_processed += 1
            doc_data = doc.to_dict()
            record = {}
            
            # DEBUG: Mostrar primeros 3 documentos
            if total_docs_processed <= 3:
                print(f"🔍 DEBUG Doc {total_docs_processed}: {doc.id}")
                print(f"   Keys: {list(doc_data.keys())[:10]}")
                if 'properties' in doc_data:
                    props = doc_data.get('properties', {})
                    print(f"   Properties keys: {list(props.keys())[:10]}")
                    print(f"   UPID: {props.get('upid', 'N/A')}")
                    print(f"   Comuna: {props.get('comuna_corregimiento', 'N/A')}")
            
            # Extraer campos geométricos y de visualización
            for field in geo_fields + viz_fields:
                if field in doc_data:
                    record[field] = doc_data[field]
                elif field in doc_data.get('properties', {}):
                    record[field] = doc_data['properties'][field]
            
            # ARREGLO INTELIGENTE: Buscar geometría en más ubicaciones posibles
            upid_value = record.get('upid') or doc_data.get('upid') or doc_data.get('properties', {}).get('upid')
            
            if upid_value:
                # Buscar geometría en múltiples ubicaciones posibles
                geometry_found = False
                geometry_data_obj = {}
                
                # 1. Buscar en diferentes campos de geometría
                geo_sources = [
                    ('geometry', doc_data.get('geometry')),
                    ('coordinates', doc_data.get('coordinates')),
                    ('coordenadas', doc_data.get('coordenadas')),
                    ('location', doc_data.get('location')),
                    ('geom', doc_data.get('geom')),
                    # También en properties
                    ('geometry_props', doc_data.get('properties', {}).get('geometry')),
                    ('coordinates_props', doc_data.get('properties', {}).get('coordinates')),
                    ('coordenadas_props', doc_data.get('properties', {}).get('coordenadas')),
                ]
                
                # 2. Verificar lat/lng por separado
                lat = (doc_data.get('lat') or doc_data.get('latitude') or 
                      doc_data.get('properties', {}).get('lat') or 
                      doc_data.get('properties', {}).get('latitude'))
                lng = (doc_data.get('lng') or doc_data.get('lon') or doc_data.get('longitude') or
                      doc_data.get('properties', {}).get('lng') or 
                      doc_data.get('properties', {}).get('lon') or
                      doc_data.get('properties', {}).get('longitude'))
                
                # 3. Construir objeto de geometría válido
                for geo_name, geo_value in geo_sources:
                    if geo_value and str(geo_value).strip() not in ['null', 'None', '', '[]', '{}']:
                        try:
                            # Si es string, intentar parsear como JSON
                            if isinstance(geo_value, str):
                                import json
                                geo_value = json.loads(geo_value)
                            
                            geometry_data_obj = geo_value
                            geometry_found = True
                            break
                        except:
                            continue
                
                # 4. Si no hay geometría compleja, crear desde lat/lng
                if not geometry_found and lat and lng:
                    try:
                        lat_num = float(lat)
                        lng_num = float(lng)
                        if -90 <= lat_num <= 90 and -180 <= lng_num <= 180:
                            geometry_data_obj = {
                                "type": "Point",
                                "coordinates": [lng_num, lat_num]
                            }
                            geometry_found = True
                    except (ValueError, TypeError):
                        pass
                
                # 5. SOLUCIÓN ÚNICA: Incluir TODOS los registros, tengan o no geometría
                # Crear geometría por defecto si no existe (punto nulo o coordenadas sintéticas)
                if not geometry_found or not geometry_data_obj:
                    # Si no tiene geometría, crear un punto nulo para mantener estructura GeoJSON
                    geometry_data_obj = {
                        "type": "Point",
                        "coordinates": [0, 0]  # Coordenadas nulas, el frontend puede decidir cómo manejarlas
                    }
                
                # Crear registro completo con estructura GeoJSON (TODOS los registros incluidos)
                feature = {
                    "type": "Feature",
                    "geometry": geometry_data_obj,
                    "properties": {
                        "upid": upid_value,
                        "has_valid_geometry": geometry_found,  # Marcar si tiene geometría real
                        # Campos originales  
                        "comuna_corregimiento": record.get('comuna_corregimiento') or doc_data.get('properties', {}).get('comuna_corregimiento'),
                        "barrio_vereda": record.get('barrio_vereda') or doc_data.get('properties', {}).get('barrio_vereda'),
                        "estado": record.get('estado') or doc_data.get('properties', {}).get('estado'),
                        # NUEVOS CAMPOS SOLICITADOS CON CONVERSIÓN DE TIPOS
                        "presupuesto_base": _convert_to_int(record.get('presupuesto_base') or doc_data.get('properties', {}).get('presupuesto_base')),
                        "tipo_intervencion": record.get('tipo_intervencion') or doc_data.get('properties', {}).get('tipo_intervencion'),
                        "avance_obra": _convert_to_float(record.get('avance_obra') or doc_data.get('properties', {}).get('avance_obra')),
                        # Campos adicionales útiles
                        "nombre_centro_gestor": record.get('nombre_centro_gestor') or doc_data.get('properties', {}).get('nombre_centro_gestor'),
                    }
                }
                geometry_data.append(feature)
        
        print(f"🗺️ DEBUG: Procesados {total_docs_processed} docs, incluidos {len(geometry_data)} registros totales (con y sin geometría)")
        
        # Aplicar filtros
        if filters:
            content_filters = {k: v for k, v in filters.items() 
                             if k in ['comuna_corregimiento', 'barrio_vereda', 'estado', 'tipo_intervencion', 'nombre_centro_gestor', 'presupuesto_base', 'avance_obra']}
            if content_filters:
                geometry_data = apply_client_side_filters(geometry_data, content_filters)
                print(f"�️ DEBUG: Filtros aplicados: {len(geometry_data)} registros")
            
            # Aplicar límite
            if 'limit' in filters and filters['limit']:
                try:
                    limit_value = int(filters['limit'])
                    if limit_value > 0:
                        geometry_data = geometry_data[:limit_value]
                except (ValueError, TypeError):
                    pass
        
        # ✅ FUNCIONAL: Sin cache, datos siempre frescos
        
        # Respuesta en formato GeoJSON válido para NextJS
        geojson_response = {
            "type": "FeatureCollection",
            "features": geometry_data,
            "properties": {
                "success": True,
                "count": len(geometry_data),
                "filters_applied": filters or {},
                "functional_approach": True,
                "message": f"Geometrías cargadas desde Firestore (sin cache)"
            }
        }
        
        return geojson_response
        
    except Exception as e:
        print(f"❌ ERROR en get_unidades_proyecto_geometry: {str(e)}")
        import traceback
        print(f"❌ TRACEBACK: {traceback.format_exc()}")
        
        return {
            "success": False,
            "error": f"Error obteniendo geometrías: {str(e)}",
            "data": [],
            "count": 0
        }


async def get_unidades_proyecto_attributes(
    filters: Optional[Dict[str, Any]] = None, 
    limit: Optional[int] = None, 
    offset: Optional[int] = None
) -> Dict[str, Any]:
    """
    Obtener solo los atributos de tabla (sin geometría) de unidades-proyecto
    Especializado para NextJS - Tabla de atributos con filtros avanzados y paginación
    
    Parámetros:
    - filters: dict con filtros a aplicar
    - limit: número máximo de registros a retornar
    - offset: número de registros a saltar (paginación)
    
    Filtros soportados:
    - upid: ID específico o lista de IDs
    - estado: estado del proyecto
    - tipo_intervencion: tipo de intervención
    """
    try:
        # ============================================
        # SISTEMA DE CACHE (4 horas)
        # ============================================
        import hashlib
        import json
        
        # ✅ PROGRAMACIÓN FUNCIONAL: Sin cache, datos frescos siempre
            
        # ============================================
        # LÓGICA PRINCIPAL (si no hay cache)
        # ============================================
        # ============================================
        # DETECCIÓN DE FILTROS
        # ============================================
        has_filters = filters and any(
            key in filters and filters[key] 
            for key in ['upid', 'estado', 'tipo_intervencion', 'nombre_centro_gestor', 
                       'search', 'comuna_corregimiento', 'barrio_vereda', 'nombre_up', 'direccion']
        )
        
        print(f"📋 DEBUG: get_unidades_proyecto_attributes - Filtros detectados: {has_filters}")
        print(f"📋 DEBUG: Sin límites por defecto - Acceso completo a datos")
        
        db = get_firestore_client()
        if db is None:
            return {
                "success": False,
                "error": "No se pudo conectar a Firestore",
                "data": [],
                "count": 0
            }
        
        collection_ref = db.collection('unidades_proyecto')
        
        # ============================================
        # OPTIMIZACIÓN: FILTROS SERVER-SIDE EN FIRESTORE
        # ============================================
        query = collection_ref
        
        # Aplicar filtros server-side para reducir datos descargados
        server_side_filters_applied = []
        
        # Filtro server-side por upid específico (solo si es un valor único)
        if filters and 'upid' in filters and filters['upid'] and not isinstance(filters['upid'], list):
            query = query.where('upid', '==', filters['upid'])
            server_side_filters_applied.append(f"upid={filters['upid']}")
            print(f"📋 DEBUG: ✅ SERVER-SIDE filtro por upid: {filters['upid']}")
        
        # Filtro por estado (server-side)
        if filters and 'estado' in filters and filters['estado']:
            query = query.where('estado', '==', filters['estado'])
            server_side_filters_applied.append(f"estado={filters['estado']}")
            print(f"📋 DEBUG: ✅ SERVER-SIDE filtro por estado: {filters['estado']}")
        
        # Filtro por tipo_intervencion (server-side)
        if filters and 'tipo_intervencion' in filters and filters['tipo_intervencion']:
            query = query.where('tipo_intervencion', '==', filters['tipo_intervencion'])
            server_side_filters_applied.append(f"tipo_intervencion={filters['tipo_intervencion']}")
            print(f"📋 DEBUG: ✅ SERVER-SIDE filtro por tipo_intervencion: {filters['tipo_intervencion']}")
        
        # Filtro por nombre_centro_gestor (server-side)
        if filters and 'nombre_centro_gestor' in filters and filters['nombre_centro_gestor']:
            query = query.where('nombre_centro_gestor', '==', filters['nombre_centro_gestor'])
            server_side_filters_applied.append(f"nombre_centro_gestor={filters['nombre_centro_gestor']}")
            print(f"📋 DEBUG: ✅ SERVER-SIDE filtro por nombre_centro_gestor: {filters['nombre_centro_gestor']}")
        
        print(f"📋 DEBUG: Filtros SERVER-SIDE aplicados: {server_side_filters_applied}")
        
        # Ordenar para paginación consistente
        query = query.order_by('__name__')  # Ordenar por document ID
        
        # Aplicar límite server-side SOLO si se especifica explícitamente
        if limit and limit > 0:
            query = query.limit(limit + (offset or 0))  # Aumentar límite para compensar offset
            server_side_filters_applied.append(f"limit_explícito={limit}")
            print(f"📋 DEBUG: ✅ SERVER-SIDE límite explícito aplicado: {limit}")
        
        # Aplicar offset si se especifica
        if offset and offset > 0:
            # Simular offset saltando documentos
            docs_to_skip = list(query.limit(offset).stream())
            if docs_to_skip:
                last_doc = docs_to_skip[-1]
                query = query.start_after(last_doc)
            print(f"📋 DEBUG: Aplicando offset de {offset} registros")
        
        # Obtener documentos (YA OPTIMIZADOS por Firestore)
        docs = query.stream()
        
        attributes_data = []
        doc_count = 0
        
        # Campos de geometría que queremos EXCLUIR
        geometry_fields = {
            'coordenadas', 'geometry', 'linestring', 'polygon', 'coordinates',
            'lat', 'lng', 'latitude', 'longitude', 'geom', 'shape', 'location'
        }
        
        for doc in docs:
            doc_data = doc.to_dict()
            
            # Crear registro solo con atributos (sin geometría, sin ID redundante)
            attributes_record = {}  # Sin ID redundante
            
            for field, value in doc_data.items():
                # Excluir campos de geometría pero incluir todo lo demás
                if field not in geometry_fields:
                    attributes_record[field] = value
            
            attributes_data.append(attributes_record)
            doc_count += 1
            
            if doc_count % 100 == 0:
                print(f"📋 DEBUG: Procesados {doc_count} registros de atributos...")
        
        total_docs = len(attributes_data)
        print(f"📋 DEBUG: TOTAL atributos después de filtros SERVER-SIDE: {total_docs}")
        
        # ============================================
        # FILTROS CLIENT-SIDE ADICIONALES  
        # ============================================
        client_side_filters_applied = []
        
        if filters:
            # Solo aplicar client-side para filtros que no se pueden hacer server-side
            client_side_filters = {}
            for key, value in filters.items():
                if key in ['search', 'comuna_corregimiento', 'barrio_vereda'] or (key == 'upid' and isinstance(value, list)):
                    client_side_filters[key] = value
            
            if client_side_filters:
                attributes_data = apply_client_side_filters(attributes_data, client_side_filters)
                client_side_filters_applied = list(client_side_filters.keys())
                print(f"📋 DEBUG: 🔄 CLIENT-SIDE filtros aplicados: {client_side_filters_applied}")
                print(f"📋 DEBUG: 🎯 RESULTADO FINAL - Registros después de optimización: {len(attributes_data)} de {total_docs} descargados")
        
        # Aplicar límite después de filtros client-side
        original_count = len(attributes_data)
        if limit and limit > 0:
            attributes_data = attributes_data[:limit]
            print(f"📋 DEBUG: Aplicando límite de {limit} registros")
        
        # Aplicar filtros del lado del cliente para casos especiales
        client_side_filters = {}
        client_side_filters_applied = []
        total_docs = doc_count  # Guardamos el total antes de filtros client-side
        
        if filters:
            # Filtros que requieren procesamiento client-side
            if 'search' in filters and filters['search']:
                client_side_filters['search'] = filters['search']
                client_side_filters_applied.append('search')
            
            if 'comuna_corregimiento' in filters and filters['comuna_corregimiento']:
                client_side_filters['comuna_corregimiento'] = filters['comuna_corregimiento']
                client_side_filters_applied.append('comuna_corregimiento')
                
            if 'barrio_vereda' in filters and filters['barrio_vereda']:
                client_side_filters['barrio_vereda'] = filters['barrio_vereda']
                client_side_filters_applied.append('barrio_vereda')
            
            if 'upid' in filters and isinstance(filters['upid'], list):
                client_side_filters['upid'] = filters['upid']
                client_side_filters_applied.append('upid_multiple')
            
            # Aplicar filtros client-side si los hay
            if client_side_filters:
                attributes_data = apply_client_side_filters(attributes_data, client_side_filters)
                print(f"📋 DEBUG: 🔄 CLIENT-SIDE filtros aplicados: {client_side_filters_applied}")
                print(f"📋 DEBUG: 🎯 RESULTADO FINAL - Registros después de optimización: {len(attributes_data)} de {total_docs} descargados")
        
        # Aplicar límite después de filtros client-side
        original_count = len(attributes_data)
        if limit and limit > 0:
            attributes_data = attributes_data[:limit]
            print(f"📋 DEBUG: Aplicando límite de {limit} registros")
        
        optimization_info = "Con filtros aplicados" if has_filters else "Sin filtros - Datos completos"
        
        result = {
            "success": True,
            "data": attributes_data,
            "count": len(attributes_data),
            "total_before_limit": original_count,
            "type": "attributes",
            "filters_applied": filters or {},
            "optimization": optimization_info,
            "pagination": {
                "limit": limit,
                "offset": offset,
                "has_more": original_count > len(attributes_data) if limit else False
            },
            "message": f"Obtenidos {len(attributes_data)} registros de atributos ({optimization_info})"
        }
        
        # ✅ FUNCIONAL: Sin cache, datos siempre frescos
        
        return result
        
    except Exception as e:
        print(f"❌ ERROR en get_unidades_proyecto_attributes: {str(e)}")
        import traceback
        print(f"❌ TRACEBACK: {traceback.format_exc()}")
        
        return {
            "success": False,
            "error": f"Error obteniendo atributos: {str(e)}",
            "data": [],
            "count": 0
        }


async def get_unidades_proyecto_dashboard(filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Obtener datos para dashboard de unidades de proyecto con métricas agregadas
    Incluye estadísticas, distribuciones y datos filtrados para visualizaciones
    
    Filtros soportados:
    - departamento: filtrar por departamento específico
    - municipio: filtrar por municipio específico
    - estado: filtrar por estado del proyecto
    - tipo_intervencion: filtrar por tipo de intervención
    - fecha_desde / fecha_hasta: rango de fechas
    """
    try:
        # ============================================
        # DETECCIÓN DE FILTROS PARA DASHBOARD
        # ============================================
        has_filters = filters and any(
            key in filters and filters[key] 
            for key in ['estado', 'tipo_intervencion', 'nombre_centro_gestor', 'comuna_corregimiento', 'barrio_vereda']
        )
        
        print(f"📊 DEBUG: get_unidades_proyecto_dashboard - Filtros detectados: {has_filters}")
        print(f"📊 DEBUG: Dashboard con datos completos para análisis preciso")
        
        # Usar filtros originales sin límites automáticos
        dashboard_filters = filters.copy() if filters else {}
        
        # Obtener datos para análisis (ya optimizados por las funciones individuales)
        geometry_result = await get_unidades_proyecto_geometry(dashboard_filters)
        attributes_result = await get_unidades_proyecto_attributes(dashboard_filters)
        
        # Verificar resultados con diferentes formatos
        geometry_success = (geometry_result.get("type") == "FeatureCollection" or 
                          geometry_result.get("success") == True)
        attributes_success = attributes_result.get("success") == True
        
        if not geometry_success or not attributes_success:
            return {
                "success": False,
                "error": "Error obteniendo datos base para dashboard",
                "dashboard": {}
            }
        
        # Extraer datos según el formato de respuesta
        if geometry_result.get("type") == "FeatureCollection":
            geometry_data = geometry_result.get("features", [])
        else:
            geometry_data = geometry_result.get("data", [])
        
        attributes_data = attributes_result.get("data", [])
        
        # USAR ATTRIBUTES COMO FUENTE PRINCIPAL para análisis de negocio
        # Los datos de attributes contienen toda la información de negocio necesaria
        all_records = attributes_data
        total_records = len(all_records)
        
        print(f"📊 DEBUG: Dashboard usando {total_records} registros de attributes para análisis")
        
        # Calcular métricas avanzadas del dashboard
        dashboard_data = {
            "resumen_general": {
                "total_proyectos": total_records,
                "con_geometria": len(geometry_data),
                "con_atributos": len(attributes_data),
                "porcentaje_geo": round((len(geometry_data) / total_records) * 100, 1) if total_records > 0 else 0,
                "cobertura_datos": {
                    "completos": len([r for r in all_records if r.get('upid') and (r.get('coordinates') or r.get('lat'))]),
                    "solo_atributos": len(attributes_data) - len(geometry_data) if len(attributes_data) > len(geometry_data) else 0,
                    "solo_geometria": len(geometry_data) - len(attributes_data) if len(geometry_data) > len(attributes_data) else 0
                }
            },
            "distribuciones": {},
            "metricas_geograficas": {},
            "analisis_calidad": {},
            "kpis_negocio": {},
            "filtros_aplicados": filters or {}
        }
        
        if total_records > 0:
            # Inicializar contadores para análisis
            estados = {}
            tipos_intervencion = {}
            centros_gestores = {}
            comunas_corregimientos = {}
            barrios_veredas = {}
            
            for record in all_records:
                # Buscar en properties si no está en el nivel raíz
                properties = record.get('properties', {})
                
                # Estados
                estado = record.get('estado') or properties.get('estado')
                if estado:
                    estados[estado] = estados.get(estado, 0) + 1
                
                # Tipos de intervención
                tipo = record.get('tipo_intervencion') or properties.get('tipo_intervencion')
                if tipo:
                    tipos_intervencion[tipo] = tipos_intervencion.get(tipo, 0) + 1
                
                # Centros gestores
                centro = record.get('nombre_centro_gestor') or properties.get('nombre_centro_gestor')
                if centro:
                    centros_gestores[centro] = centros_gestores.get(centro, 0) + 1
                
                # Comunas/Corregimientos
                comuna = record.get('comuna_corregimiento') or properties.get('comuna_corregimiento')
                if comuna:
                    comunas_corregimientos[comuna] = comunas_corregimientos.get(comuna, 0) + 1
                
                # Barrios/Veredas
                barrio = record.get('barrio_vereda') or properties.get('barrio_vereda')
                if barrio:
                    barrios_veredas[barrio] = barrios_veredas.get(barrio, 0) + 1
            
            # Calcular porcentajes y rankings
            def calcular_distribucion(datos_dict, label):
                total = sum(datos_dict.values())
                return {
                    "conteos": dict(sorted(datos_dict.items(), key=lambda x: x[1], reverse=True)[:15]),
                    "total_categorias": len(datos_dict),
                    "porcentajes": {k: round((v/total)*100, 1) for k, v in sorted(datos_dict.items(), key=lambda x: x[1], reverse=True)[:10]} if total > 0 else {},
                    "top_3": list(sorted(datos_dict.items(), key=lambda x: x[1], reverse=True)[:3])
                }
            
            dashboard_data["distribuciones"] = {
                "por_estado": calcular_distribucion(estados, "Estados"),
                "por_tipo_intervencion": calcular_distribucion(tipos_intervencion, "Tipos de Intervención"),
                "por_centro_gestor": calcular_distribucion(centros_gestores, "Centros Gestores"),
                "por_comuna_corregimiento": calcular_distribucion(comunas_corregimientos, "Comunas/Corregimientos"),
                "por_barrio_vereda": calcular_distribucion(barrios_veredas, "Barrios/Veredas")
            }
            
            # Métricas geográficas
            if geometry_data:
                latitudes = []
                longitudes = []
                
                for record in geometry_data:
                    lat = record.get('lat') or record.get('latitude')
                    lng = record.get('lng') or record.get('longitude')
                    
                    # También buscar en coordinates array
                    coords = record.get('coordinates') or record.get('coordenadas')
                    if coords and isinstance(coords, list) and len(coords) >= 2:
                        lng, lat = coords[0], coords[1]
                    
                    if lat is not None and lng is not None:
                        try:
                            latitudes.append(float(lat))
                            longitudes.append(float(lng))
                        except:
                            pass
                
                if latitudes and longitudes:
                    # Calcular dispersión geográfica
                    lat_mean = sum(latitudes) / len(latitudes)
                    lng_mean = sum(longitudes) / len(longitudes)
                    lat_range = max(latitudes) - min(latitudes)
                    lng_range = max(longitudes) - min(longitudes)
                    
                    dashboard_data["metricas_geograficas"] = {
                        "cobertura": {
                            "puntos_validos": len(latitudes),
                            "porcentaje_geo": round((len(latitudes) / total_records) * 100, 1)
                        },
                        "bbox": {
                            "min_lat": min(latitudes),
                            "max_lat": max(latitudes),
                            "min_lng": min(longitudes),
                            "max_lng": max(longitudes),
                            "area_grados": round(lat_range * lng_range, 4)
                        },
                        "centro_gravedad": {
                            "lat": round(lat_mean, 6),
                            "lng": round(lng_mean, 6)
                        },
                        "dispersion": {
                            "rango_lat": round(lat_range, 4),
                            "rango_lng": round(lng_range, 4),
                            "concentracion": "Alta" if lat_range < 0.1 and lng_range < 0.1 else "Media" if lat_range < 1 and lng_range < 1 else "Amplia"
                        }
                    }
            
            # Análisis de calidad de datos
            campos_criticos = ['upid', 'estado', 'tipo_intervencion', 'nombre_centro_gestor']
            calidad_datos = {}
            
            for campo in campos_criticos:
                valores_validos = len([r for r in all_records if r.get(campo) or r.get('properties', {}).get(campo)])
                porcentaje_completitud = round((valores_validos / total_records) * 100, 1) if total_records > 0 else 0
                calidad_datos[campo] = {
                    "valores_validos": valores_validos,
                    "valores_faltantes": total_records - valores_validos,
                    "completitud_porcentaje": porcentaje_completitud,
                    "calidad": "Excelente" if porcentaje_completitud >= 95 else "Buena" if porcentaje_completitud >= 80 else "Regular" if porcentaje_completitud >= 60 else "Deficiente"
                }
            
            dashboard_data["analisis_calidad"] = calidad_datos
            
            # KPIs de negocio
            if estados:
                estados_activos = sum(v for k, v in estados.items() if k and 'activ' in k.lower() or 'ejecuc' in k.lower() or 'curso' in k.lower())
                estados_finalizados = sum(v for k, v in estados.items() if k and ('final' in k.lower() or 'complet' in k.lower() or 'termin' in k.lower()))
                
                dashboard_data["kpis_negocio"] = {
                    "proyectos_activos": estados_activos,
                    "proyectos_finalizados": estados_finalizados,
                    "tasa_completitud": round((estados_finalizados / total_records) * 100, 1) if total_records > 0 else 0,
                    "diversidad_tipos": len(tipos_intervencion),
                    "centros_gestores_activos": len(centros_gestores),
                    "cobertura_territorial": {
                        "comunas_corregimientos": len(comunas_corregimientos),
                        "barrios_veredas": len(barrios_veredas)
                    }
                }
        
        return {
            "success": True,
            "dashboard": dashboard_data,
            "data_sources": {
                "geometry_count": len(geometry_data),
                "attributes_count": len(attributes_data),
                "combined_count": total_records
            },
            "message": f"Dashboard generado con {total_records} registros"
        }
        
    except Exception as e:
        print(f"❌ ERROR en get_unidades_proyecto_dashboard: {str(e)}")
        import traceback
        print(f"❌ TRACEBACK: {traceback.format_exc()}")
        
        return {
            "success": False,
            "error": f"Error generando dashboard: {str(e)}",
            "dashboard": {}
        }


async def get_unidades_proyecto_summary() -> Dict[str, Any]:
    """
    Obtener resumen simple de las unidades de proyecto
    """
    try:
        # Obtener una muestra de datos para el resumen
        result = await get_all_unidades_proyecto_simple(limit=100)
        
        if not result.get("success"):
            return {
                "success": False,
                "error": "No se pudieron obtener datos para el resumen",
                "summary": {}
            }
        
        data = result.get("data", [])
        
        if not data:
            return {
                "success": True,
                "summary": {
                    "total": 0,
                    "message": "No hay datos disponibles"
                }
            }
        
        # Calcular estadísticas básicas
        total = len(data)
        
        # Contar registros con diferentes tipos de datos
        with_geometry = sum(1 for item in data if item.get('geometry') or item.get('coordinates'))
        with_properties = sum(1 for item in data if item.get('properties'))
        
        # Extraer algunos campos comunes para análisis
        estados = set()
        tipos = set()
        
        for item in data:
            properties = item.get('properties', {})
            if properties.get('estado'):
                estados.add(properties['estado'])
            if properties.get('tipo_intervencion'):
                tipos.add(properties['tipo_intervencion'])
        
        summary = {
            "total_sample": total,
            "with_geometry": with_geometry,
            "with_properties": with_properties,
            "unique_estados": len(estados),
            "unique_tipos_intervencion": len(tipos),
            "sample_estados": list(estados)[:5],  # Mostrar solo los primeros 5
            "sample_tipos": list(tipos)[:5]
        }
        
        return {
            "success": True,
            "summary": summary,
            "message": f"Resumen basado en {total} registros de muestra"
        }
        
    except Exception as e:
        print(f"❌ ERROR en get_unidades_proyecto_summary: {str(e)}")
        
        return {
            "success": False,
            "error": f"Error generando resumen: {str(e)}",
            "summary": {}
        }


async def validate_unidades_proyecto_collection() -> Dict[str, Any]:
    """
    Validar la existencia y estructura de la colección unidades_proyecto
    """
    try:
        db = get_firestore_client()
        if db is None:
            return {
                "valid": False,
                "error": "No se pudo conectar a Firestore"
            }
        
        collection_ref = db.collection('unidades_proyecto')
        
        # Obtener una muestra pequeña para validar
        docs = list(collection_ref.limit(3).stream())
        
        if not docs:
            return {
                "valid": False,
                "error": "La colección existe pero está vacía",
                "collection_exists": True,
                "document_count": 0
            }
        
        # Analizar estructura
        sample_doc = docs[0].to_dict()
        fields = list(sample_doc.keys())
        
        return {
            "valid": True,
            "collection_exists": True,
            "document_count": len(docs),
            "sample_fields": fields,
            "message": f"Colección válida con {len(docs)} documentos de muestra"
        }
        
    except Exception as e:
        return {
            "valid": False,
            "error": f"Error validando colección: {str(e)}"
        }


# ============================================================================
# CACHE GLOBAL PARA FILTROS (24 horas de duración)
# ============================================================================
# CÓDIGO OBSOLETO REMOVIDO - VARIABLES DE CACHE DUPLICADAS

# ✅ CACHE ELIMINADO - PROGRAMACIÓN FUNCIONAL
# Las funciones de cache causaban persistencia de datos entre requests
# Ahora cada request es independiente y sin efectos colaterales

async def get_filter_options(field: Optional[str] = None, limit: Optional[int] = None) -> Dict[str, Any]:
    """
    ✅ PROGRAMACIÓN FUNCIONAL: Obtener valores únicos para filtros
    Sin cache, datos siempre frescos y consistentes
    """
    try:
        # Campos disponibles
        available_fields = {
            'estados': 'estado',
            'tipos_intervencion': 'tipo_intervencion', 
            'centros_gestores': 'nombre_centro_gestor',
            'comunas': 'comuna_corregimiento',
            'barrios_veredas': 'barrio_vereda',
            'fuentes_financiacion': 'fuente_financiacion',
            'anos': 'ano'
        }
        
        # ✅ FUNCIONAL: Obtener datos frescos siempre
        attributes_result = await get_unidades_proyecto_attributes(filters={}, limit=400)
        
        if not attributes_result.get("success", False):
            return {
                "success": False,
                "error": "No se pudieron obtener datos para generar filtros",
                "filters": {}
            }
        
        # ✅ INMUTABLE: Extraer valores únicos sin mutar datos
        attributes_data = attributes_result.get("data", [])
        field_collectors = {field_key: set() for field_key in available_fields.keys()}
        
        for record in attributes_data:
            properties = record.get('properties', {})
            
            for field_key, field_path in available_fields.items():
                value = properties.get(field_path) or record.get(field_path)
                
                if value and str(value).strip() and str(value).strip().lower() not in ['null', 'none', '']:
                    clean_value = str(value).strip()
                    if clean_value:
                        field_collectors[field_key].add(clean_value)
        
        # ✅ TRANSFORMACIÓN FUNCIONAL: Sin efectos colaterales
        all_filters = {field_key: sorted(list(values_set)) 
                      for field_key, values_set in field_collectors.items()}
        
        # ✅ RESPUESTA PURA: Basada solo en parámetros de entrada
        if field:
            field_mapping = {v: k for k, v in available_fields.items()}
            target_field_key = field_mapping.get(field, field)
            result = {target_field_key: all_filters.get(target_field_key, [])}
            if limit:
                result[target_field_key] = result[target_field_key][:limit]
        else:
            result = all_filters.copy()
            if limit:
                result = {key: values[:limit] for key, values in result.items()}
        
        return {
            "success": True,
            "filters": result,
            "metadata": {
                "total_fields": len(result),
                "field_requested": field,
                "limit_applied": limit,
                "functional_approach": True,
                "fresh_data": True
            }
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": f"Error obteniendo opciones de filtros: {str(e)}",
            "filters": {}
        }
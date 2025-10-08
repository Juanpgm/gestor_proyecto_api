"""
Scripts simples para manejo de Unidades de Proyecto - VERSIÓN SIMPLIFICADA
Sistema de cache simplificado y optimizado
"""

import os
import time
from datetime import datetime
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
            cleaned = value.strip().replace('%', '').replace(' ', '')
            
            # Manejar formato decimal europeo (coma como separador decimal)
            # Si hay una sola coma y está en posición de decimal (ej: "50,75")
            if ',' in cleaned and cleaned.count(',') == 1:
                comma_pos = cleaned.find(',')
                # Si la coma está en los últimos 3 caracteres, probablemente es decimal
                if len(cleaned) - comma_pos <= 3:
                    cleaned = cleaned.replace(',', '.')
                else:
                    # Si no, es separador de miles, remover
                    cleaned = cleaned.replace(',', '')
            else:
                # Múltiples comas = separadores de miles
                cleaned = cleaned.replace(',', '')
            
            if cleaned:
                return float(cleaned)
        else:
            return float(value)
    except (ValueError, TypeError):
        return None

def _convert_bpin_to_positive_int(value) -> Optional[int]:
    """Convertir BPIN a número entero positivo, eliminando prefijo '-'"""
    if value is None or value == '' or str(value).strip() in ['null', 'None', 'nan', 'NaN']:
        return None
    try:
        # Si es string, limpiar y convertir
        if isinstance(value, str):
            cleaned = value.strip()
            # Eliminar prefijo '-' si existe
            if cleaned.startswith('-'):
                cleaned = cleaned[1:]
            # Eliminar otros caracteres no numéricos comunes
            cleaned = cleaned.replace(',', '').replace('$', '').replace(' ', '').replace('.', '')
            if cleaned and cleaned.isdigit():
                return int(cleaned)
        else:
            # Si es numérico, convertir a positivo
            num_value = abs(int(float(value)))
            return num_value if num_value > 0 else None
    except (ValueError, TypeError):
        return None
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
        
        # Filtro por nombre_centro_gestor
        if 'nombre_centro_gestor' in filters and filters['nombre_centro_gestor']:
            centro_value = filters['nombre_centro_gestor']
            filtered_data = [item for item in filtered_data
                           if item.get('nombre_centro_gestor') == centro_value or
                              item.get('properties', {}).get('nombre_centro_gestor') == centro_value]
        
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
                        # BPIN convertido a entero positivo (sin prefijo '-')
                        "bpin": _convert_bpin_to_positive_int(record.get('bpin') or doc_data.get('properties', {}).get('bpin')),
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
        
        # ✅ FILTROS MOVIDOS A CLIENT-SIDE - Los campos están siendo procesados después de la descarga
        # Los filtros server-side de Firestore fallan porque los índices pueden no estar configurados
        # o la estructura de datos no coincide exactamente. Usar client-side es más confiable.
        
        # Solo mantener filtros server-side para campos simples que sabemos que funcionan
        # Por ahora, deshabilitar filtros server-side problemáticos
        
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
                    # Aplicar conversiones de tipos específicas
                    if field == 'presupuesto_base':
                        attributes_record[field] = _convert_to_int(value)
                    elif field == 'avance_obra':
                        attributes_record[field] = _convert_to_float(value)
                    elif field == 'bpin':
                        attributes_record[field] = _convert_bpin_to_positive_int(value)
                    else:
                        attributes_record[field] = value
            
            # También verificar y convertir campos en properties si existen
            if 'properties' in doc_data and isinstance(doc_data['properties'], dict):
                for field, value in doc_data['properties'].items():
                    if field not in geometry_fields and field not in attributes_record:
                        # Aplicar conversiones de tipos específicas
                        if field == 'presupuesto_base':
                            attributes_record[field] = _convert_to_int(value)
                        elif field == 'avance_obra':
                            attributes_record[field] = _convert_to_float(value)
                        elif field == 'bpin':
                            attributes_record[field] = _convert_bpin_to_positive_int(value)
                        else:
                            attributes_record[field] = value
            
            attributes_data.append(attributes_record)
            doc_count += 1
            
            if doc_count % 100 == 0:
                print(f"📋 DEBUG: Procesados {doc_count} registros de atributos...")
        
        total_docs = len(attributes_data)
        print(f"📋 DEBUG: TOTAL atributos después de filtros SERVER-SIDE: {total_docs}")
        
        # ============================================
        # FILTROS CLIENT-SIDE (TODOS LOS FILTROS)
        # ============================================
        total_docs = doc_count
        client_side_filters_applied = []
        
        if filters:
            # ✅ TODOS los filtros se procesan client-side para mayor confiabilidad
            client_side_filters = {}
            
            # Filtros principales que antes fallaban en server-side
            if 'estado' in filters and filters['estado']:
                client_side_filters['estado'] = filters['estado']
                client_side_filters_applied.append('estado')
                
            if 'tipo_intervencion' in filters and filters['tipo_intervencion']:
                client_side_filters['tipo_intervencion'] = filters['tipo_intervencion']
                client_side_filters_applied.append('tipo_intervencion')
                
            if 'nombre_centro_gestor' in filters and filters['nombre_centro_gestor']:
                client_side_filters['nombre_centro_gestor'] = filters['nombre_centro_gestor']
                client_side_filters_applied.append('nombre_centro_gestor')
            
            # Filtros adicionales
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
            
            # Aplicar filtros client-side
            if client_side_filters:
                print(f"📋 DEBUG: 🔄 CLIENT-SIDE filtros aplicados: {client_side_filters_applied}")
                attributes_data = apply_client_side_filters(attributes_data, client_side_filters)
                print(f"📋 DEBUG: 🎯 RESULTADO FINAL - Registros después de filtros: {len(attributes_data)} de {total_docs} descargados")
        
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


async def get_unidades_proyecto_summary() -> Dict[str, Any]:
    """
    Obtener resumen simple de las unidades de proyecto
    """
    try:
        # ============================================
        # 🚀 OBTENCIÓN DE DATOS COMPLETOS PARA ANÁLISIS AVANZADO
        # ============================================
        has_filters = filters and any(
            key in filters and filters[key] 
            for key in ['estado', 'tipo_intervencion', 'nombre_centro_gestor', 'comuna_corregimiento', 'barrio_vereda']
        )
        
        print(f"📊 DEBUG: Dashboard avanzado - Filtros aplicados: {has_filters}")
        print(f"📊 DEBUG: Generando métricas optimizadas para dashboards y gráficos")
        
        # Obtener datos completos sin límites para análisis preciso
        dashboard_filters = filters.copy() if filters else {}
        
        # Obtener todos los datos necesarios
        geometry_result = await get_unidades_proyecto_geometry(dashboard_filters)
        attributes_result = await get_unidades_proyecto_attributes(dashboard_filters, limit=None)
        
        # Verificar resultados
        geometry_success = (geometry_result.get("type") == "FeatureCollection" or geometry_result.get("success") == True)
        attributes_success = attributes_result.get("success") == True
        
        if not geometry_success or not attributes_success:
            return {
                "success": False,
                "error": "Error obteniendo datos base para dashboard avanzado",
                "dashboard": {}
            }
        
        # Extraer datos
        if geometry_result.get("type") == "FeatureCollection":
            geometry_data = geometry_result.get("features", [])
        else:
            geometry_data = geometry_result.get("data", [])
        
        attributes_data = attributes_result.get("data", [])
        all_records = attributes_data
        total_records = len(all_records)
        
        print(f"📊 DEBUG: Procesando {total_records} registros para métricas avanzadas")
        print(f"📊 DEBUG: Total records para metadatos: {total_records}")
        
        # ============================================
        # 💰 ANÁLISIS FINANCIERO AVANZADO
        # ============================================
        presupuestos_validos = []
        avances_validos = []
        años_disponibles = {}
        fuentes_financiacion = {}
        
        # ============================================
        # 📊 CONTADORES Y AGRUPACIONES PARA GRÁFICOS
        # ============================================
        estados = {}
        tipos_intervencion = {}
        centros_gestores = {}
        comunas_corregimientos = {}
        barrios_veredas = {}
        
        # Análisis de calidad por campo
        completitud_campos = {}
        campos_criticos = ['upid', 'estado', 'tipo_intervencion', 'nombre_centro_gestor', 'comuna_corregimiento', 'presupuesto_base', 'avance_obra']
        
        # Métricas geográficas
        latitudes = []
        longitudes = []
        
        # ============================================
        # 🔄 PROCESAMIENTO AVANZADO DE REGISTROS
        # ============================================
        print(f"📊 DEBUG: Iniciando procesamiento de {total_records} registros")
        
        for record in all_records:
            properties = record.get('properties', {})
            
            # 💰 PROCESAMIENTO FINANCIERO
            presupuesto_raw = record.get('presupuesto_base') or properties.get('presupuesto_base')
            if presupuesto_raw is not None:
                presupuesto = _convert_to_int(presupuesto_raw)
                record['presupuesto_base'] = presupuesto
                if presupuesto > 0:
                    presupuestos_validos.append(presupuesto)
            
            avance_raw = record.get('avance_obra') or properties.get('avance_obra')
            if avance_raw is not None:
                avance = _convert_to_float(avance_raw)
                record['avance_obra'] = avance
                if 0 <= avance <= 100:
                    avances_validos.append(avance)
            
            # BPIN
            bpin_raw = record.get('bpin') or properties.get('bpin')
            if bpin_raw is not None:
                record['bpin'] = _convert_bpin_to_positive_int(bpin_raw)
            
            # 📅 ANÁLISIS TEMPORAL
            año = record.get('ano') or properties.get('ano')
            if año:
                try:
                    año_int = int(año)
                    años_disponibles[año_int] = años_disponibles.get(año_int, 0) + 1
                except:
                    pass
            
            # 💳 FUENTES DE FINANCIACIÓN
            fuente = record.get('fuente_financiacion') or properties.get('fuente_financiacion')
            if fuente and str(fuente).strip() and str(fuente).strip().lower() not in ['null', 'none', '', 'por definir']:
                fuentes_financiacion[fuente] = fuentes_financiacion.get(fuente, 0) + 1
            
            # 📊 DISTRIBUCIONES CATEGÓRICAS
            estado = record.get('estado') or properties.get('estado')
            if estado and str(estado).strip():
                estados[estado] = estados.get(estado, 0) + 1
            
            tipo = record.get('tipo_intervencion') or properties.get('tipo_intervencion')
            if tipo and str(tipo).strip():
                tipos_intervencion[tipo] = tipos_intervencion.get(tipo, 0) + 1
            
            centro = record.get('nombre_centro_gestor') or properties.get('nombre_centro_gestor')
            if centro and str(centro).strip():
                centros_gestores[centro] = centros_gestores.get(centro, 0) + 1
            
            comuna = record.get('comuna_corregimiento') or properties.get('comuna_corregimiento')
            if comuna and str(comuna).strip():
                comunas_corregimientos[comuna] = comunas_corregimientos.get(comuna, 0) + 1
            
            barrio = record.get('barrio_vereda') or properties.get('barrio_vereda')
            if barrio and str(barrio).strip():
                barrios_veredas[barrio] = barrios_veredas.get(barrio, 0) + 1
            
            # 🗺️ COORDENADAS GEOGRÁFICAS - ACCESO DIRECTO A GEOMETRY
            lat = None
            lng = None
            
            # 1. PRIORIDAD: Acceder directamente al campo geometry del record
            geometry = record.get('geometry')
            if geometry and isinstance(geometry, dict):
                # Buscar coordinates en geometry
                coords = geometry.get('coordinates')
                if coords and isinstance(coords, list) and len(coords) >= 2:
                    try:
                        lng = float(coords[0])
                        lat = float(coords[1])
                    except (ValueError, TypeError, IndexError):
                        pass
                
                # Si no hay coordinates, buscar lat/lng directos en geometry
                if lat is None or lng is None:
                    lat = lat or geometry.get('lat') or geometry.get('latitude')
                    lng = lng or geometry.get('lng') or geometry.get('longitude') or geometry.get('lon')
            
            # 2. FALLBACK: Buscar en nivel raíz del record
            if lat is None or lng is None:
                lat_sources = [
                    record.get('lat'), record.get('latitude'),
                    properties.get('lat'), properties.get('latitude')
                ]
                
                lng_sources = [
                    record.get('lng'), record.get('longitude'), record.get('lon'),
                    properties.get('lng'), properties.get('longitude'), properties.get('lon')
                ]
                
                # Encontrar la primera coordenada válida
                for lat_val in lat_sources:
                    if lat_val is not None and str(lat_val).strip() not in ['', 'null', 'None']:
                        try:
                            lat = float(lat_val)
                            break
                        except:
                            continue
                
                for lng_val in lng_sources:
                    if lng_val is not None and str(lng_val).strip() not in ['', 'null', 'None']:
                        try:
                            lng = float(lng_val)
                            break
                        except:
                            continue
            
            # 3. FALLBACK: Buscar en arrays de coordenadas alternativos
            if lat is None or lng is None:
                coords_arrays = [
                    record.get('coordinates'), record.get('coordenadas'),
                    properties.get('coordinates'), properties.get('coordenadas')
                ]
                
                for coords in coords_arrays:
                    if coords and isinstance(coords, list) and len(coords) >= 2:
                        try:
                            if lng is None:
                                lng = float(coords[0])
                            if lat is None:
                                lat = float(coords[1])
                            break
                        except:
                            continue
            
            # 4. VALIDAR Y AGREGAR coordenadas válidas para Colombia
            if lat is not None and lng is not None:
                try:
                    lat_float = float(lat)
                    lng_float = float(lng)
                    # Validar coordenadas de Colombia (rangos amplios)
                    if -10 <= lat_float <= 20 and -90 <= lng_float <= -60:
                        latitudes.append(lat_float)
                        longitudes.append(lng_float)
                        # DEBUG para las primeras coordenadas encontradas
                        if len(latitudes) <= 3:
                            print(f"📍 DEBUG: Coordenada {len(latitudes)} - Lat: {lat_float}, Lng: {lng_float}")
                except Exception as e:
                    pass
            
            # 📋 ANÁLISIS DE COMPLETITUD
            for campo in campos_criticos:
                if campo not in completitud_campos:
                    completitud_campos[campo] = 0
                valor = record.get(campo) or properties.get(campo)
                if valor is not None and str(valor).strip() and str(valor).strip().lower() not in ['null', 'none', '']:
                    completitud_campos[campo] += 1
        
        # ============================================
        # 💰 MÉTRICAS FINANCIERAS AVANZADAS
        # ============================================
        metricas_financieras = {}
        if presupuestos_validos:
            presupuestos_ordenados = sorted(presupuestos_validos)
            total_presupuesto = sum(presupuestos_validos)
            
            metricas_financieras = {
                "resumen": {
                    "total_proyectos_con_presupuesto": len(presupuestos_validos),
                    "presupuesto_total": total_presupuesto,
                    "presupuesto_promedio": round(total_presupuesto / len(presupuestos_validos), 2),
                    "presupuesto_mediano": presupuestos_ordenados[len(presupuestos_ordenados) // 2],
                    "presupuesto_minimo": min(presupuestos_validos),
                    "presupuesto_maximo": max(presupuestos_validos)
                },
                "distribucion_rangos": {
                    "menos_100M": len([p for p in presupuestos_validos if p < 100_000_000]),
                    "100M_1B": len([p for p in presupuestos_validos if 100_000_000 <= p < 1_000_000_000]),
                    "1B_10B": len([p for p in presupuestos_validos if 1_000_000_000 <= p < 10_000_000_000]),
                    "mas_10B": len([p for p in presupuestos_validos if p >= 10_000_000_000])
                },
                "percentiles": {
                    "p25": presupuestos_ordenados[len(presupuestos_ordenados) // 4],
                    "p50": presupuestos_ordenados[len(presupuestos_ordenados) // 2],
                    "p75": presupuestos_ordenados[3 * len(presupuestos_ordenados) // 4],
                    "p90": presupuestos_ordenados[9 * len(presupuestos_ordenados) // 10]
                }
            }
        
        # ============================================
        # 📈 MÉTRICAS DE AVANCE Y RENDIMIENTO
        # ============================================
        metricas_avance = {}
        if avances_validos:
            avance_promedio = sum(avances_validos) / len(avances_validos)
            metricas_avance = {
                "resumen": {
                    "proyectos_con_avance": len(avances_validos),
                    "avance_promedio": round(avance_promedio, 1),
                    "avance_mediano": sorted(avances_validos)[len(avances_validos) // 2]
                },
                "distribucion_avance": {
                    "sin_iniciar": len([a for a in avances_validos if a == 0]),
                    "en_progreso": len([a for a in avances_validos if 0 < a < 100]),
                    "completados": len([a for a in avances_validos if a == 100]),
                    "iniciados": len([a for a in avances_validos if a > 0])
                },
                "rangos_avance": {
                    "0_25": len([a for a in avances_validos if 0 <= a < 25]),
                    "25_50": len([a for a in avances_validos if 25 <= a < 50]),
                    "50_75": len([a for a in avances_validos if 50 <= a < 75]),
                    "75_100": len([a for a in avances_validos if 75 <= a <= 100])
                }
            }
        
        # ============================================
        # 📊 DISTRIBUCIONES OPTIMIZADAS PARA GRÁFICOS
        # ============================================
        def crear_distribucion_grafico(datos_dict, max_items=15, incluir_otros=True):
            """Optimizada para gráficos de barras, pie charts, y treemaps"""
            if not datos_dict:
                return {}
            
            total = sum(datos_dict.values())
            items_ordenados = sorted(datos_dict.items(), key=lambda x: x[1], reverse=True)
            
            # Tomar los top items
            top_items = items_ordenados[:max_items]
            otros_count = sum(v for k, v in items_ordenados[max_items:]) if len(items_ordenados) > max_items else 0
            
            # Preparar datos para diferentes tipos de gráficos
            labels = [item[0] for item in top_items]
            valores = [item[1] for item in top_items]
            porcentajes = [round((v/total)*100, 1) for v in valores]
            
            if incluir_otros and otros_count > 0:
                labels.append("Otros")
                valores.append(otros_count)
                porcentajes.append(round((otros_count/total)*100, 1))
            
            return {
                "chart_data": {
                    "labels": labels,
                    "values": valores,
                    "percentages": porcentajes,
                    "total": total
                },
                "pie_chart": [{"name": labels[i], "value": valores[i], "percentage": porcentajes[i]} for i in range(len(labels))],
                "bar_chart": {"categories": labels, "series": [{"name": "Cantidad", "data": valores}]},
                "treemap": [{"name": labels[i], "value": valores[i], "colorValue": porcentajes[i]} for i in range(len(labels))],
                "summary": {
                    "total_categories": len(datos_dict),
                    "top_3": items_ordenados[:3],
                    "diversity_index": len(datos_dict) / total if total > 0 else 0
                }
            }
        
        # ============================================
        # 🏗️ ESTRUCTURA FINAL DEL DASHBOARD
        # ============================================
        dashboard_data = {
            # 📋 RESUMEN EJECUTIVO
            "resumen_ejecutivo": {
                "total_proyectos": total_records,
                "con_geometria": len(latitudes),
                "con_presupuesto": len(presupuestos_validos),
                "presupuesto_total_formateado": f"${sum(presupuestos_validos):,.0f}" if presupuestos_validos else "N/D",
                "avance_promedio": round(sum(avances_validos) / len(avances_validos), 1) if avances_validos else 0,
                "cobertura_territorial": len(comunas_corregimientos),
                "centros_gestores_activos": len(centros_gestores)
            },
            
            # 💰 ANÁLISIS FINANCIERO
            "analisis_financiero": metricas_financieras,
            
            # 📈 MÉTRICAS DE RENDIMIENTO
            "metricas_rendimiento": metricas_avance,
            
            # 📊 DISTRIBUCIONES PARA GRÁFICOS
            "distribuciones_graficos": {
                "estados": crear_distribucion_grafico(estados, 10),
                "tipos_intervencion": crear_distribucion_grafico(tipos_intervencion, 12),
                "centros_gestores": crear_distribucion_grafico(centros_gestores, 15),
                "comunas_corregimientos": crear_distribucion_grafico(comunas_corregimientos, 20),
                "fuentes_financiacion": crear_distribucion_grafico(fuentes_financiacion, 10),
                "años": crear_distribucion_grafico(años_disponibles, 15, False)
            },
            
            # 🗺️ ANÁLISIS GEOGRÁFICO
            "analisis_geografico": {},
            
            # 📊 KPIs Y MÉTRICAS DE NEGOCIO
            "kpis_negocio": {
                "eficiencia_ejecucion": round(len([a for a in avances_validos if a > 50]) / len(avances_validos) * 100, 1) if avances_validos else 0,
                "proyectos_completados": len([a for a in avances_validos if a == 100]),
                "inversion_promedio_por_comuna": round(sum(presupuestos_validos) / len(comunas_corregimientos), 0) if presupuestos_validos and comunas_corregimientos else 0,
                "diversidad_tipos": len(tipos_intervencion),
                "cobertura_geografica": round(len(latitudes) / total_records * 100, 1) if total_records > 0 else 0,
                "densidad_proyectos_territorial": round(total_records / len(comunas_corregimientos), 1) if comunas_corregimientos else 0
            },
            
            # 📋 CALIDAD DE DATOS
            "calidad_datos": {
                campo: {
                    "completitud": round((count / total_records) * 100, 1),
                    "valores_validos": count,
                    "valores_faltantes": total_records - count,
                    "calidad_nivel": "Excelente" if count/total_records >= 0.95 else "Buena" if count/total_records >= 0.80 else "Regular" if count/total_records >= 0.60 else "Deficiente"
                }
                for campo, count in completitud_campos.items()
            },
            
            # 🎯 CONFIGURACIÓN FILTROS
            "filtros_aplicados": filters or {}
        }
        
        # 🗺️ MÉTRICAS GEOGRÁFICAS AVANZADAS
        if latitudes and longitudes:
            lat_mean = sum(latitudes) / len(latitudes)
            lng_mean = sum(longitudes) / len(longitudes)
            
            dashboard_data["analisis_geografico"] = {
                "cobertura": {
                    "puntos_validos": len(latitudes),
                    "cobertura_porcentaje": round((len(latitudes) / total_records) * 100, 1)
                },
                "centro_gravedad": {"lat": round(lat_mean, 6), "lng": round(lng_mean, 6)},
                "bounding_box": {
                    "norte": max(latitudes), "sur": min(latitudes),
                    "este": max(longitudes), "oeste": min(longitudes),
                    "area_km2": round(abs(max(latitudes) - min(latitudes)) * abs(max(longitudes) - min(longitudes)) * 111.32**2, 2)
                },
                "densidad_geografica": round(len(latitudes) / max(1, abs(max(latitudes) - min(latitudes)) * abs(max(longitudes) - min(longitudes))), 2),
                "heatmap_data": [{"lat": lat, "lng": lng, "intensity": 1} for lat, lng in zip(latitudes, longitudes)][:100]  # Limitar para rendimiento
            }
        
        print(f"📊 DEBUG: Procesamiento completado - Coordenadas encontradas: {len(latitudes)}")
        print(f"📊 DEBUG: Registros financieros: {len(presupuestos_validos)}")
        print(f"📊 DEBUG: Registros de rendimiento: {len(avances_validos)}")
        
        return {
            "success": True,
            "dashboard": dashboard_data,
            "message": f"Dashboard avanzado generado con {total_records} registros, {len(latitudes)} coordenadas geográficas y métricas optimizadas"
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
        
        # ✅ FUNCIONAL: Obtener TODOS los datos frescos siempre (sin límite para filtros)
        attributes_result = await get_unidades_proyecto_attributes(filters={}, limit=None)
        
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
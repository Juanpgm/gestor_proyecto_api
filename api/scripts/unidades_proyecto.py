"""
Scripts simples para manejo de Unidades de Proyecto
Solo las funciones que funcionan correctamente con Firebase
Incluye sistema de filtros avanzados para geometry, attributes y dashboard
"""

import os
from typing import Dict, List, Any, Optional, Union
from database.firebase_config import get_firestore_client


def apply_client_side_filters(data: List[Dict[str, Any]], filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """
    Aplicar filtros del lado del cliente a los datos obtenidos de Firestore
    
    Filtros soportados:
    - upid: filtrar por ID específico o lista de IDs
    - estado: filtrar por estado del proyecto
    - tipo_intervencion: filtrar por tipo de intervención
    - departamento: filtrar por departamento
    - municipio: filtrar por municipio
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
        'departamento', 'municipio', 'nombre_proyecto'
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
            doc_data['id'] = doc.id
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
    Obtener solo los datos de geometría (coordenadas, linestring, etc.) de unidades-proyecto
    Especializado para NextJS - Datos geoespaciales con filtros avanzados
    
    Filtros soportados:
    - upid: ID específico o lista de IDs
    - estado: estado del proyecto
    - tipo_intervencion: tipo de intervención
    - departamento: departamento específico
    - municipio: municipio específico
    - bbox: bounding box [min_lng, min_lat, max_lng, max_lat]
    - search: búsqueda de texto en campos principales
    - limit: límite de registros a retornar
    """
    try:
        print(f"🗺️ DEBUG: Obteniendo datos de GEOMETRÍA... filtros={filters}")
        
        db = get_firestore_client()
        if db is None:
            return {
                "success": False,
                "error": "No se pudo conectar a Firestore",
                "data": [],
                "count": 0
            }
        
        collection_ref = db.collection('unidades_proyecto')
        
        # Aplicar filtros server-side básicos si están disponibles
        query = collection_ref
        
        # Filtro por upid específico (server-side si es un solo valor)
        if filters and 'upid' in filters and filters['upid'] and not isinstance(filters['upid'], list):
            query = query.where('upid', '==', filters['upid'])
            print(f"🗺️ DEBUG: Aplicando filtro server-side por upid: {filters['upid']}")
        
        # Obtener documentos
        docs = query.stream()
        
        geometry_data = []
        doc_count = 0
        
        # Campos de geometría que queremos extraer
        geometry_fields = [
            'upid',  # Siempre incluir upid
            'coordenadas', 
            'geometry', 
            'linestring', 
            'polygon', 
            'coordinates',
            'lat', 
            'lng', 
            'latitude', 
            'longitude',
            'geom',
            'shape',
            'location'
        ]
        
        # Campos adicionales útiles para filtros client-side
        additional_fields = [
            'estado', 'tipo_intervencion', 'departamento', 'municipio', 
            'nombre', 'descripcion', 'properties'
        ]
        
        for doc in docs:
            doc_data = doc.to_dict()
            
            # Extraer campos de geometría que existan
            geometry_record = {'id': doc.id}  # Incluir ID del documento
            
            # Incluir campos geométricos
            for field in geometry_fields:
                if field in doc_data:
                    geometry_record[field] = doc_data[field]
                # También buscar en properties
                properties = doc_data.get('properties', {})
                if field in properties:
                    geometry_record[field] = properties[field]
            
            # Incluir campos adicionales para filtros (sin duplicar)
            for field in additional_fields:
                if field in doc_data and field not in geometry_record:
                    geometry_record[field] = doc_data[field]
            
            # Solo agregar si tiene al menos un campo geométrico además del ID
            has_geometry = any(field in geometry_record for field in geometry_fields[1:])  # Excluir 'upid'
            if has_geometry:
                geometry_data.append(geometry_record)
                doc_count += 1
                
                if doc_count % 100 == 0:
                    print(f"🗺️ DEBUG: Procesados {doc_count} registros de geometría...")
        
        print(f"🗺️ DEBUG: TOTAL geometrías antes de filtros client-side: {len(geometry_data)}")
        
        # Aplicar filtros del lado del cliente
        if filters:
            geometry_data = apply_client_side_filters(geometry_data, filters)
            print(f"🗺️ DEBUG: TOTAL geometrías después de filtros: {len(geometry_data)}")
        
        # Aplicar límite si se especifica
        if filters and 'limit' in filters and filters['limit'] and isinstance(filters['limit'], int):
            limit = filters['limit']
            geometry_data = geometry_data[:limit]
            print(f"🗺️ DEBUG: Aplicando límite de {limit} registros")
        
        return {
            "success": True,
            "data": geometry_data,
            "count": len(geometry_data),
            "type": "geometry",
            "filters_applied": filters or {},
            "message": f"Obtenidos {len(geometry_data)} registros de geometría"
        }
        
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
    - departamento: departamento específico
    - municipio: municipio específico
    - search: búsqueda de texto en campos principales
    - fecha_desde / fecha_hasta: rango de fechas
    """
    try:
        print(f"📋 DEBUG: Obteniendo ATRIBUTOS de tabla... filtros={filters}, limit={limit}, offset={offset}")
        
        db = get_firestore_client()
        if db is None:
            return {
                "success": False,
                "error": "No se pudo conectar a Firestore",
                "data": [],
                "count": 0
            }
        
        collection_ref = db.collection('unidades_proyecto')
        
        # Construir query con filtros server-side básicos
        query = collection_ref
        
        # Filtro server-side por upid específico (solo si es un valor único)
        if filters and 'upid' in filters and filters['upid'] and not isinstance(filters['upid'], list):
            query = query.where('upid', '==', filters['upid'])
            print(f"📋 DEBUG: Aplicando filtro server-side por upid: {filters['upid']}")
        
        # Ordenar para paginación consistente
        query = query.order_by('__name__')  # Ordenar por document ID
        
        # Aplicar offset si se especifica
        if offset and offset > 0:
            # Simular offset saltando documentos
            docs_to_skip = list(query.limit(offset).stream())
            if docs_to_skip:
                last_doc = docs_to_skip[-1]
                query = query.start_after(last_doc)
            print(f"📋 DEBUG: Aplicando offset de {offset} registros")
        
        # Obtener documentos (aplicaremos limit después de filtros client-side)
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
            
            # Crear registro solo con atributos (sin geometría)
            attributes_record = {'id': doc.id}  # Incluir ID del documento
            
            for field, value in doc_data.items():
                # Excluir campos de geometría pero incluir todo lo demás
                if field not in geometry_fields:
                    attributes_record[field] = value
            
            attributes_data.append(attributes_record)
            doc_count += 1
            
            if doc_count % 100 == 0:
                print(f"📋 DEBUG: Procesados {doc_count} registros de atributos...")
        
        print(f"📋 DEBUG: TOTAL atributos antes de filtros client-side: {len(attributes_data)}")
        
        # Aplicar filtros del lado del cliente
        if filters:
            attributes_data = apply_client_side_filters(attributes_data, filters)
            print(f"📋 DEBUG: TOTAL atributos después de filtros: {len(attributes_data)}")
        
        # Aplicar límite después de filtros client-side
        original_count = len(attributes_data)
        if limit and limit > 0:
            attributes_data = attributes_data[:limit]
            print(f"📋 DEBUG: Aplicando límite de {limit} registros")
        
        return {
            "success": True,
            "data": attributes_data,
            "count": len(attributes_data),
            "total_before_limit": original_count,
            "type": "attributes",
            "filters_applied": filters or {},
            "pagination": {
                "limit": limit,
                "offset": offset,
                "has_more": original_count > len(attributes_data) if limit else False
            },
            "message": f"Obtenidos {len(attributes_data)} registros de atributos"
        }
        
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
        print(f"📊 DEBUG: Obteniendo datos para DASHBOARD... filtros={filters}")
        
        # Obtener datos completos para análisis
        geometry_result = await get_unidades_proyecto_geometry(filters)
        attributes_result = await get_unidades_proyecto_attributes(filters)
        
        if not geometry_result.get("success") or not attributes_result.get("success"):
            return {
                "success": False,
                "error": "Error obteniendo datos base para dashboard",
                "dashboard": {}
            }
        
        geometry_data = geometry_result.get("data", [])
        attributes_data = attributes_result.get("data", [])
        
        # Combinar datos por ID para análisis completo
        combined_data = {}
        
        # Añadir datos de geometría
        for item in geometry_data:
            item_id = item.get('id') or item.get('upid')
            if item_id:
                combined_data[item_id] = item.copy()
        
        # Añadir/actualizar con datos de atributos
        for item in attributes_data:
            item_id = item.get('id') or item.get('upid')
            if item_id:
                if item_id in combined_data:
                    combined_data[item_id].update(item)
                else:
                    combined_data[item_id] = item
        
        all_records = list(combined_data.values())
        total_records = len(all_records)
        
        # Calcular métricas del dashboard
        dashboard_data = {
            "resumen_general": {
                "total_proyectos": total_records,
                "con_geometria": len(geometry_data),
                "con_atributos": len(attributes_data),
                "porcentaje_geo": round((len(geometry_data) / total_records) * 100, 1) if total_records > 0 else 0
            },
            "distribuciones": {},
            "metricas_geograficas": {},
            "tendencias": {},
            "filtros_aplicados": filters or {}
        }
        
        if total_records > 0:
            # Distribución por estado
            estados = {}
            tipos_intervencion = {}
            departamentos = {}
            municipios = {}
            
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
                
                # Departamentos
                dept = record.get('departamento') or properties.get('departamento')
                if dept:
                    departamentos[dept] = departamentos.get(dept, 0) + 1
                
                # Municipios
                mun = record.get('municipio') or properties.get('municipio')
                if mun:
                    municipios[mun] = municipios.get(mun, 0) + 1
            
            dashboard_data["distribuciones"] = {
                "por_estado": estados,
                "por_tipo_intervencion": tipos_intervencion,
                "por_departamento": departamentos,
                "por_municipio": dict(list(municipios.items())[:10])  # Top 10 municipios
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
                    dashboard_data["metricas_geograficas"] = {
                        "puntos_validos": len(latitudes),
                        "bbox": {
                            "min_lat": min(latitudes),
                            "max_lat": max(latitudes),
                            "min_lng": min(longitudes),
                            "max_lng": max(longitudes)
                        },
                        "centro": {
                            "lat": sum(latitudes) / len(latitudes),
                            "lng": sum(longitudes) / len(longitudes)
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
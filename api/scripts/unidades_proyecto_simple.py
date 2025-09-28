"""
Scripts simples para manejo de Unidades de Proyecto
Solo las funciones que funcionan correctamente con Firebase
"""

import os
from typing import Dict, List, Any, Optional
from database.firebase_config import get_firestore_client

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


async def get_unidades_proyecto_geometry() -> Dict[str, Any]:
    """
    Obtener solo los datos de geometría (coordenadas, linestring, etc.) de unidades-proyecto
    Especializado para NextJS - Datos geoespaciales
    """
    try:
        print(f"🗺️ DEBUG: Obteniendo datos de GEOMETRÍA...")
        
        db = get_firestore_client()
        if db is None:
            return {
                "success": False,
                "error": "No se pudo conectar a Firestore",
                "data": [],
                "count": 0
            }
        
        collection_ref = db.collection('unidades_proyecto')
        docs = collection_ref.stream()
        
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
        
        for doc in docs:
            doc_data = doc.to_dict()
            
            # Extraer solo campos de geometría que existan
            geometry_record = {'id': doc.id}  # Incluir ID del documento
            
            for field in geometry_fields:
                if field in doc_data:
                    geometry_record[field] = doc_data[field]
                # También buscar en properties
                properties = doc_data.get('properties', {})
                if field in properties:
                    geometry_record[field] = properties[field]
            
            # Solo agregar si tiene al menos un campo geométrico además del ID
            if len(geometry_record) > 1:
                geometry_data.append(geometry_record)
                doc_count += 1
                
                if doc_count % 100 == 0:
                    print(f"🗺️ DEBUG: Procesados {doc_count} registros de geometría...")
        
        print(f"🗺️ DEBUG: TOTAL geometrías procesadas: {len(geometry_data)}")
        
        return {
            "success": True,
            "data": geometry_data,
            "count": len(geometry_data),
            "type": "geometry",
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


async def get_unidades_proyecto_attributes() -> Dict[str, Any]:
    """
    Obtener solo los atributos de tabla (sin geometría) de unidades-proyecto
    Especializado para NextJS - Tabla de atributos
    """
    try:
        print(f"📋 DEBUG: Obteniendo ATRIBUTOS de tabla...")
        
        db = get_firestore_client()
        if db is None:
            return {
                "success": False,
                "error": "No se pudo conectar a Firestore",
                "data": [],
                "count": 0
            }
        
        collection_ref = db.collection('unidades_proyecto')
        docs = collection_ref.stream()
        
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
            
            # Agregar todos los registros (no filtrar por upid aquí)
            attributes_data.append(attributes_record)
            doc_count += 1
            
            if doc_count % 100 == 0:
                print(f"📋 DEBUG: Procesados {doc_count} registros de atributos...")
        
        print(f"📋 DEBUG: TOTAL atributos procesados: {len(attributes_data)}")
        
        return {
            "success": True,
            "data": attributes_data,
            "count": len(attributes_data),
            "type": "attributes",
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
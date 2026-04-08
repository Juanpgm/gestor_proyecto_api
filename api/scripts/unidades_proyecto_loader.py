"""
Script para cargar datos GeoJSON a la colección 'unidades_proyecto' en Firebase
Permite importar masivamente unidades de proyecto desde archivos GeoJSON
"""

import json
import uuid
from typing import Dict, Any, List, Optional
from datetime import datetime
from database.firebase_config import get_firestore_client
from api.models.unidades_proyecto_models import (
    UnidadProyectoFirestore,
    UnidadProyectoProperties
)


def process_geometry(geometry: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Procesar y validar geometría GeoJSON para Firebase
    
    Maneja todos los tipos: Point, LineString, Polygon, Multi*, GeometryCollection
    Serializa como JSON string compatible con Firebase
    Valida coordenadas reales vs placeholders [0,0]
    
    Args:
        geometry: Objeto geometría GeoJSON o None
        
    Returns:
        Dict con:
            - geometry_json: String JSON serializado (None si no hay geometría)
            - type: Tipo de geometría (Point, LineString, etc.)
            - has_geometry: bool - True si hay geometría
            - is_valid: bool - True si tiene coordenadas válidas (no [0,0])
    """
    if not geometry or not isinstance(geometry, dict):
        return {
            'geometry_json': None,
            'type': None,
            'has_geometry': False,
            'is_valid': False
        }
    
    geometry_type = geometry.get('type')
    
    # Validar si tiene coordenadas válidas (no placeholder [0,0])
    is_valid = validate_geometry_coordinates(geometry)
    
    # Serializar como JSON string para Firebase
    geometry_json = json.dumps(geometry, ensure_ascii=False)
    
    return {
        'geometry_json': geometry_json,
        'type': geometry_type,
        'has_geometry': True,
        'is_valid': is_valid
    }


def validate_geometry_coordinates(geometry: Dict[str, Any]) -> bool:
    """
    Validar si la geometría tiene coordenadas reales (no placeholders [0,0])
    
    Args:
        geometry: Objeto geometría GeoJSON
        
    Returns:
        bool: True si tiene coordenadas válidas
    """
    if not geometry:
        return False
    
    geometry_type = geometry.get('type')
    
    # GeometryCollection: validar que al menos una geometría sea válida
    if geometry_type == 'GeometryCollection':
        geometries = geometry.get('geometries', [])
        return any(validate_geometry_coordinates(geom) for geom in geometries)
    
    # Obtener coordenadas según el tipo
    coords = geometry.get('coordinates', [])
    if not coords:
        return False
    
    # Point: verificar que no sea [0, 0]
    if geometry_type == 'Point':
        if len(coords) >= 2:
            return not (coords[0] == 0 and coords[1] == 0)
        return False
    
    # MultiPoint: verificar que tenga al menos un punto válido
    if geometry_type == 'MultiPoint':
        return any(not (pt[0] == 0 and pt[1] == 0) for pt in coords if len(pt) >= 2)
    
    # LineString, Polygon, y Multi*: si tienen coordenadas, son válidos
    if geometry_type in ['LineString', 'Polygon', 'MultiLineString', 'MultiPolygon']:
        return True
    
    return False


def generate_upid() -> str:
    """
    Generar un UPID único (DEPRECADO)
    Formato: UP-{timestamp}-{uuid}
    
    NOTA: Esta función está deprecada. Usar generate_upid_with_number() 
    con el consecutivo adecuado desde get_next_upid_number()
    """
    timestamp = datetime.utcnow().strftime('%Y%m%d%H%M%S')
    unique_id = uuid.uuid4().hex[:8]
    return f"UP-{timestamp}-{unique_id}"


def generate_upid_with_number(number: int) -> str:
    """
    Generar un UPID con número consecutivo
    
    Args:
        number: Número consecutivo para el UPID
        
    Returns:
        str: UPID con formato UNP-{número}
    """
    return f"UNP-{number}"


async def get_next_upid_number(db) -> int:
    """
    Obtener el siguiente número de UPID disponible en la colección
    
    Args:
        db: Cliente de Firestore
        
    Returns:
        int: Siguiente número disponible
    """
    collection_ref = db.collection('unidades_proyecto')
    
    # Obtener todos los documentos (solo IDs)
    # No podemos usar order_by sin índice, así que obtenemos todos y procesamos en Python
    docs = collection_ref.select([]).stream()  # select([]) solo trae IDs, no datos
    
    max_number = 0
    
    for doc in docs:
        doc_id = doc.id
        
        # Extraer número del formato UNP-X
        if doc_id.startswith('UNP-'):
            try:
                parts = doc_id.split('-')
                if len(parts) >= 2 and parts[1].isdigit():
                    number = int(parts[1])
                    if number > max_number:
                        max_number = number
            except (ValueError, IndexError):
                continue
    
    # Si no encontramos ningún UNP, empezar desde 1
    # Si encontramos, retornar el siguiente
    return max_number + 1 if max_number > 0 else 1


def validate_geojson_structure(geojson_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validar estructura básica de GeoJSON
    
    Returns:
        Dict con resultado de validación
    """
    try:
        # Validar tipo principal
        if geojson_data.get('type') != 'FeatureCollection':
            return {
                "valid": False,
                "error": "El GeoJSON debe ser de tipo 'FeatureCollection'"
            }
        
        # Validar que tenga features
        features = geojson_data.get('features', [])
        if not isinstance(features, list):
            return {
                "valid": False,
                "error": "El campo 'features' debe ser una lista"
            }
        
        if len(features) == 0:
            return {
                "valid": False,
                "error": "El GeoJSON no contiene ningún feature"
            }
        
        # Validar estructura de features
        for idx, feature in enumerate(features[:5]):  # Validar primeros 5
            if feature.get('type') != 'Feature':
                return {
                    "valid": False,
                    "error": f"Feature en índice {idx} no es de tipo 'Feature'"
                }
            
            if 'properties' not in feature:
                return {
                    "valid": False,
                    "error": f"Feature en índice {idx} no tiene campo 'properties'"
                }
        
        return {
            "valid": True,
            "feature_count": len(features),
            "message": f"GeoJSON válido con {len(features)} features"
        }
        
    except Exception as e:
        return {
            "valid": False,
            "error": f"Error validando GeoJSON: {str(e)}"
        }


def process_geojson_feature(
    feature: Dict[str, Any], 
    override_upid: bool = False,
    upid_number: Optional[int] = None
) -> Dict[str, Any]:
    """
    Procesar un feature individual de GeoJSON para Firebase
    
    Args:
        feature: Feature individual de GeoJSON
        override_upid: Si True, genera nuevo UPID aunque exista en properties
        upid_number: Número consecutivo para generar UPID (formato UNP-X)
        
    Returns:
        Dict con upid y data procesada
    """
    try:
        properties = feature.get('properties', {})
        geometry = feature.get('geometry')
        
        # Obtener o generar UPID
        upid = properties.get('upid')
        
        if not upid or override_upid:
            # Si se proporciona número consecutivo, usar ese formato
            if upid_number is not None:
                upid = generate_upid_with_number(upid_number)
            else:
                # Fallback a formato timestamp (deprecado)
                upid = generate_upid()
        
        # Limpiar UPID (asegurar que sea string válido)
        upid = str(upid).strip()
        
        # Procesar y validar geometría
        geometry_info = process_geometry(geometry)
        
        # Crear documento para Firestore
        firestore_doc = {
            'upid': upid,
            'geometry': geometry_info['geometry_json'],  # JSON string
            'geometry_type': geometry_info['type'],
            'has_geometry': geometry_info['has_geometry'],
            'has_valid_geometry': geometry_info['is_valid'],
            'updated_at': datetime.utcnow().isoformat(),
            'loaded_at': datetime.utcnow().isoformat(),
        }
        
        # Agregar todos los campos de properties
        for key, value in properties.items():
            if key != 'upid':  # upid ya se agregó arriba
                # Limpiar valores None, NaN, null
                if value is not None and str(value).strip().lower() not in ['nan', 'null', 'none', '']:
                    firestore_doc[key] = value
        
        # Agregar tipo_equipamiento automáticamente con valor "Vías"
        firestore_doc['tipo_equipamiento'] = 'Vías'
        
        # Procesar campos numéricos específicos
        if 'presupuesto_base' in firestore_doc:
            try:
                presupuesto = str(firestore_doc['presupuesto_base']).replace(',', '').replace('$', '').strip()
                firestore_doc['presupuesto_base'] = float(presupuesto) if presupuesto else None
            except:
                firestore_doc['presupuesto_base'] = None
        
        if 'avance_obra' in firestore_doc:
            try:
                avance = str(firestore_doc['avance_obra']).replace('%', '').replace(',', '.').strip()
                firestore_doc['avance_obra'] = float(avance) if avance else None
            except:
                firestore_doc['avance_obra'] = None
        
        if 'cantidad' in firestore_doc:
            try:
                cantidad = str(firestore_doc['cantidad']).replace(',', '').strip()
                firestore_doc['cantidad'] = int(float(cantidad)) if cantidad else None
            except:
                firestore_doc['cantidad'] = None
        
        if 'bpin' in firestore_doc:
            try:
                bpin = str(firestore_doc['bpin']).strip()
                # Eliminar prefijo '-' si existe
                if bpin.startswith('-'):
                    bpin = bpin[1:]
                # Limpiar caracteres no numéricos
                import re
                bpin = re.sub(r'[^\d]', '', bpin)
                firestore_doc['bpin'] = bpin if bpin else None
            except:
                firestore_doc['bpin'] = None
        
        return {
            "success": True,
            "upid": upid,
            "data": firestore_doc
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": f"Error procesando feature: {str(e)}"
        }


async def load_geojson_to_firestore(
    geojson_data: Dict[str, Any],
    batch_size: int = 500,
    override_existing: bool = False,
    override_upid: bool = False,
    dry_run: bool = False
) -> Dict[str, Any]:
    """
    Cargar datos de GeoJSON a la colección 'unidades_proyecto' en Firestore
    
    Args:
        geojson_data: Dict con estructura GeoJSON completa
        batch_size: Tamaño de lote para operaciones batch (máx 500)
        override_existing: Si True, sobrescribe documentos existentes
        override_upid: Si True, genera nuevos UPIDs aunque existan
        dry_run: Si True, solo simula la carga sin escribir en Firebase
        
    Returns:
        Dict con resultado de la operación
    """
    try:
        print("🔄 Iniciando carga de GeoJSON a Firestore...")
        
        # Validar estructura de GeoJSON
        validation = validate_geojson_structure(geojson_data)
        if not validation.get('valid'):
            return {
                "success": False,
                "error": validation.get('error'),
                "stats": {}
            }
        
        print(f"✅ {validation.get('message')}")
        
        features = geojson_data.get('features', [])
        total_features = len(features)
        
        # 🔀 UNIFICACIÓN: Agrupar features por nombre_up idéntico
        print("🔀 Unificando features con mismo nombre_up...")
        unified_features = {}
        duplicates_merged = 0
        
        for feature in features:
            # Obtener nombre_up de forma segura
            nombre_up = feature.get('properties', {}).get('nombre_up')
            
            # Manejar None, vacío o whitespace
            if nombre_up and isinstance(nombre_up, str):
                nombre_up = nombre_up.strip()
            
            if not nombre_up:
                # Si no tiene nombre_up válido, usar un identificador único
                nombre_up = f"SIN_NOMBRE_{uuid.uuid4().hex[:8]}"
            
            if nombre_up in unified_features:
                # Ya existe una feature con este nombre_up
                duplicates_merged += 1
                existing_feature = unified_features[nombre_up]
                
                # Combinar geometrías si ambas existen
                existing_geom = existing_feature.get('geometry')
                new_geom = feature.get('geometry')
                
                if existing_geom and new_geom:
                    # Si ambas geometrías existen, convertir a MultiGeometry o combinar
                    existing_type = existing_geom.get('type')
                    new_type = new_geom.get('type')
                    
                    if existing_type == 'GeometryCollection':
                        # Ya es una colección, añadir la nueva geometría
                        existing_geom['geometries'].append(new_geom)
                    elif existing_type == new_type and existing_type in ['Point', 'LineString', 'Polygon']:
                        # Convertir a Multi-tipo
                        multi_type = f"Multi{existing_type}"
                        if existing_type == 'Point':
                            existing_feature['geometry'] = {
                                'type': 'MultiPoint',
                                'coordinates': [existing_geom['coordinates'], new_geom['coordinates']]
                            }
                        elif existing_type == 'LineString':
                            existing_feature['geometry'] = {
                                'type': 'MultiLineString',
                                'coordinates': [existing_geom['coordinates'], new_geom['coordinates']]
                            }
                        elif existing_type == 'Polygon':
                            existing_feature['geometry'] = {
                                'type': 'MultiPolygon',
                                'coordinates': [existing_geom['coordinates'], new_geom['coordinates']]
                            }
                    else:
                        # Crear GeometryCollection
                        existing_feature['geometry'] = {
                            'type': 'GeometryCollection',
                            'geometries': [existing_geom, new_geom]
                        }
                
                # Actualizar propiedades (mantener las existentes, añadir nuevas)
                new_props = feature.get('properties', {})
                existing_props = existing_feature['properties']
                
                for key, value in new_props.items():
                    if key not in existing_props or existing_props[key] is None:
                        existing_props[key] = value
                    elif key in ['presupuesto_base', 'valor_total']:
                        # Sumar presupuestos
                        try:
                            existing_val = float(existing_props.get(key, 0) or 0)
                            new_val = float(value or 0)
                            existing_props[key] = existing_val + new_val
                        except (ValueError, TypeError):
                            pass
                
            else:
                # Primera vez que vemos este nombre_up
                unified_features[nombre_up] = feature
        
        # Convertir de vuelta a lista
        features = list(unified_features.values())
        
        if duplicates_merged > 0:
            print(f"✅ Unificación completada:")
            print(f"   - Features originales: {total_features}")
            print(f"   - Features duplicados unificados: {duplicates_merged}")
            print(f"   - Features resultantes: {len(features)}")
        else:
            print(f"ℹ️  No se encontraron duplicados por nombre_up")
        
        # Actualizar total_features después de la unificación
        total_features = len(features)
        
        if dry_run:
            print(f"🔍 DRY RUN MODE - No se escribirá en Firebase")
        
        # Obtener cliente de Firestore
        db = get_firestore_client()
        if db is None:
            return {
                "success": False,
                "error": "No se pudo conectar a Firestore",
                "stats": {}
            }
        
        collection_ref = db.collection('unidades_proyecto')
        
        # Obtener el siguiente número UPID disponible
        print("🔢 Obteniendo siguiente número UPID...")
        next_upid_number = await get_next_upid_number(db)
        print(f"📊 Siguiente UPID disponible: UNP-{next_upid_number}")
        
        # 🚀 OPTIMIZACIÓN: Obtener todos los UPIDs existentes en UNA SOLA consulta
        print("🔍 Obteniendo UPIDs existentes para UPSERT optimizado...")
        existing_upids = set()
        if not dry_run:
            try:
                # Usar select([]) para obtener solo los IDs sin datos
                docs = collection_ref.select([]).stream()
                existing_upids = {doc.id for doc in docs}
                print(f"📋 Encontrados {len(existing_upids)} UPIDs existentes en Firebase")
            except Exception as e:
                print(f"⚠️  No se pudieron obtener UPIDs existentes: {e}")
                print("   Continuando sin optimización (puede ser más lento)")
        
        # Estadísticas
        stats = {
            "total_features": total_features,
            "processed": 0,
            "created": 0,
            "updated": 0,
            "skipped": 0,
            "errors": 0,
            "error_details": [],
            "upid_range": {
                "start": next_upid_number,
                "end": None
            }
        }
        
        # Procesar en lotes
        batch = db.batch()
        batch_count = 0
        current_upid_number = next_upid_number
        
        for idx, feature in enumerate(features):
            try:
                # Procesar feature con número consecutivo
                result = process_geojson_feature(
                    feature, 
                    override_upid, 
                    upid_number=current_upid_number
                )
                
                if not result.get('success'):
                    stats['errors'] += 1
                    stats['error_details'].append({
                        "index": idx,
                        "error": result.get('error')
                    })
                    continue
                
                upid = result.get('upid')
                data = result.get('data')
                
                # Crear referencia al documento
                doc_ref = collection_ref.document(upid)
                
                # 🚀 Verificar existencia usando el set pre-cargado (mucho más rápido)
                doc_exists = upid in existing_upids if not dry_run else False
                
                if not dry_run:
                    # UPSERT: Usar merge=True para actualizar solo campos que cambiaron
                    # Si el documento existe, actualiza solo los campos nuevos/modificados
                    # Si no existe, lo crea completo
                    batch.set(doc_ref, data, merge=True)
                    
                    if doc_exists:
                        stats['updated'] += 1
                    else:
                        stats['created'] += 1
                else:
                    # En dry run, asumir que son nuevos
                    stats['created'] += 1
                
                stats['processed'] += 1
                batch_count += 1
                
                # Incrementar número UPID solo si es un documento nuevo
                if not doc_exists:
                    current_upid_number += 1
                
                # Ejecutar batch cuando alcance el límite
                if batch_count >= batch_size:
                    if not dry_run:
                        batch.commit()
                        print(f"📦 Batch de {batch_count} documentos guardado")
                    batch = db.batch()
                    batch_count = 0
                
                # Mostrar progreso cada 50 features para dar feedback más frecuente
                if (idx + 1) % 50 == 0:
                    print(f"📊 Progreso: {idx + 1}/{total_features} features procesados")
                
            except Exception as e:
                stats['errors'] += 1
                stats['error_details'].append({
                    "index": idx,
                    "error": str(e)
                })
                print(f"❌ Error en feature {idx}: {str(e)}")
        
        # Ejecutar último batch
        if batch_count > 0 and not dry_run:
            batch.commit()
            print(f"📦 Último batch de {batch_count} documentos guardado")
        
        # Actualizar rango final de UPIDs
        stats['upid_range']['end'] = current_upid_number - 1
        
        success_rate = (stats['processed'] / total_features * 100) if total_features > 0 else 0
        
        print(f"\n✅ Carga completada!")
        print(f"📊 Estadísticas:")
        print(f"   - Total features: {stats['total_features']}")
        print(f"   - Procesados: {stats['processed']} ({success_rate:.1f}%)")
        print(f"   - Creados: {stats['created']}")
        print(f"   - Actualizados: {stats['updated']}")
        print(f"   - Omitidos: {stats['skipped']}")
        print(f"   - Errores: {stats['errors']}")
        print(f"   - Rango UPIDs: UNP-{stats['upid_range']['start']} a UNP-{stats['upid_range']['end']}")
        
        return {
            "success": True,
            "message": f"Carga completada: {stats['processed']}/{total_features} features procesados",
            "stats": stats,
            "dry_run": dry_run
        }
        
    except Exception as e:
        print(f"❌ ERROR CRÍTICO: {str(e)}")
        import traceback
        print(traceback.format_exc())
        
        return {
            "success": False,
            "error": f"Error crítico durante la carga: {str(e)}",
            "stats": stats if 'stats' in locals() else {}
        }


async def delete_all_unidades_proyecto(confirm: bool = False) -> Dict[str, Any]:
    """
    PELIGRO: Eliminar todos los documentos de la colección unidades_proyecto
    
    Args:
        confirm: Debe ser True para ejecutar (seguridad)
        
    Returns:
        Dict con resultado
    """
    if not confirm:
        return {
            "success": False,
            "error": "Debe confirmar la eliminación con confirm=True"
        }
    
    try:
        print("⚠️  ADVERTENCIA: Eliminando TODOS los documentos de unidades_proyecto...")
        
        db = get_firestore_client()
        if db is None:
            return {
                "success": False,
                "error": "No se pudo conectar a Firestore"
            }
        
        collection_ref = db.collection('unidades_proyecto')
        
        # Eliminar en lotes
        batch = db.batch()
        deleted = 0
        batch_count = 0
        
        docs = collection_ref.stream()
        
        for doc in docs:
            batch.delete(doc.reference)
            batch_count += 1
            deleted += 1
            
            if batch_count >= 500:
                batch.commit()
                print(f"🗑️  {deleted} documentos eliminados...")
                batch = db.batch()
                batch_count = 0
        
        # Eliminar último batch
        if batch_count > 0:
            batch.commit()
        
        print(f"✅ Eliminación completada: {deleted} documentos eliminados")
        
        return {
            "success": True,
            "deleted_count": deleted,
            "message": f"{deleted} documentos eliminados"
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": f"Error eliminando documentos: {str(e)}"
        }

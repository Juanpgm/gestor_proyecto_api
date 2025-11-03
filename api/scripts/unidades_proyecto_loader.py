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
        
        # Detectar tipo de geometría y validez
        geometry_type = None
        has_geometry = False
        has_valid_geometry = False
        
        if geometry:
            geometry_type = geometry.get('type')
            has_geometry = True
            
            # Validar si tiene coordenadas reales (no [0,0])
            coords = geometry.get('coordinates', [])
            if coords:
                if geometry_type == 'Point':
                    has_valid_geometry = not (
                        len(coords) >= 2 and 
                        coords[0] == 0 and 
                        coords[1] == 0
                    )
                elif geometry_type in ['LineString', 'MultiLineString', 'Polygon']:
                    has_valid_geometry = True
        
        # Crear documento para Firestore
        # Serializar geometría como JSON string porque Firestore no acepta objetos anidados complejos
        import json
        
        firestore_doc = {
            'upid': upid,  # Agregar UPID tanto como ID del documento como campo
            'geometry': json.dumps(geometry) if geometry else None,
            'geometry_type': geometry_type,
            'has_geometry': has_geometry,
            'has_valid_geometry': has_valid_geometry,
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

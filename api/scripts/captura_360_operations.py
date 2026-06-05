"""
Operaciones para el módulo de Captura Estado 360
Gestión de reconocimiento de unidades de proyecto
"""

import logging
import unicodedata
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
from google.cloud import firestore

from database.firebase_config import get_firestore_client

# Importar S3DocumentManager si está disponible
try:
    from api.utils.s3_document_manager import S3DocumentManager, BOTO3_AVAILABLE
    S3_AVAILABLE = BOTO3_AVAILABLE
except ImportError:
    S3_AVAILABLE = False
    S3DocumentManager = None

# Configurar logger
logger = logging.getLogger(__name__)

# Constantes
COLLECTION_NAME = "unidades_proyecto_reconocimiento_360"

# Mapeo de estados
ESTADO_360_MAPPING = {
    "En alistamiento": "Antes",
    "En ejecución": "Durante",
    "Suspendido": "Durante",
    "Terminado": "Después",
    "Inaugurado": "Después"
}


def mapear_estado_360(estado: str) -> str:
    """
    Mapear estado del proyecto a estado_360
    
    Args:
        estado: Estado del proyecto
        
    Returns:
        Estado 360 correspondiente (Antes/Durante/Después)
    """
    return ESTADO_360_MAPPING.get(estado, "Antes")


def generar_estructura_carpetas_s3(
    nombre_centro_gestor: str,
    upid: str,
    estado_360: str,
    fecha_registro: str
) -> Dict[str, str]:
    """
    Generar estructura de carpetas S3 según estado_360
    
    Estructura: /images/nombre_centro_gestor/upid/(antes|durante|despues)/fecha_registro
    
    Args:
        nombre_centro_gestor: Nombre del centro gestor
        upid: ID de la unidad de proyecto
        estado_360: Estado 360 (Antes/Durante/Después)
        fecha_registro: Fecha de registro
        
    Returns:
        Diccionario con rutas para cada estado
    """
    # Sanitizar nombre del centro gestor
    centro_gestor_safe = "".join(
        c for c in nombre_centro_gestor 
        if c.isalnum() or c in (' ', '-', '_')
    ).strip().replace(' ', '_')
    
    # Sanitizar upid
    upid_safe = "".join(
        c for c in upid 
        if c.isalnum() or c in ('-', '_')
    ).strip()
    
    # Formatear fecha
    fecha_safe = fecha_registro.replace(':', '-').replace(' ', '_')
    
    # Base path
    base_path = f"images/{centro_gestor_safe}/{upid_safe}"
    
    # Generar rutas para cada estado
    paths = {
        "photosBeforeUrl": f"{base_path}/antes/{fecha_safe}",
        "photoWhileUrl": f"{base_path}/durante/{fecha_safe}",
        "photosAfterUrl": f"{base_path}/despues/{fecha_safe}"
    }
    
    return paths


def obtener_ruta_por_estado(
    paths: Dict[str, str],
    estado_360: str
) -> str:
    """
    Obtener la ruta S3 correspondiente según el estado_360
    
    Args:
        paths: Diccionario con todas las rutas generadas
        estado_360: Estado 360 actual (Antes/Durante/Después)
        
    Returns:
        Ruta S3 correspondiente
    """
    estado_mapping = {
        "Antes": "photosBeforeUrl",
        "Durante": "photoWhileUrl",
        "Después": "photosAfterUrl"
    }
    
    key = estado_mapping.get(estado_360, "photosBeforeUrl")
    return paths.get(key, "")


async def subir_fotos_s3(
    photos_urls: List[str],
    nombre_centro_gestor: str,
    upid: str,
    estado_360: str,
    fecha_registro: str
) -> Tuple[List[Dict], List[Dict]]:
    """
    Procesar URLs de fotos y guardarlas en Firebase según el estado_360
    
    Args:
        photos_urls: Lista de URLs de fotos a guardar
        nombre_centro_gestor: Nombre del centro gestor (para referencia)
        upid: ID de la unidad de proyecto (para referencia)
        estado_360: Estado 360 (Antes/Durante/Después)
        fecha_registro: Fecha de registro
        
    Returns:
        Tupla (fotos_exitosas, fotos_fallidas)
    """
    fotos_exitosas = []
    fotos_fallidas = []
    
    if not photos_urls:
        return fotos_exitosas, fotos_fallidas
    
    # Procesar cada URL
    for idx, url in enumerate(photos_urls):
        try:
            if not isinstance(url, str) or not url.strip():
                raise ValueError("URL no válida o vacía")
            
            # Validar que sea una URL válida
            if not url.startswith(('http://', 'https://')):
                raise ValueError(f"URL debe comenzar con http:// o https://: {url}")
            
            fotos_exitosas.append({
                'url': url,
                'orden': idx + 1,
                'estado_360': estado_360,
                'fecha_registro': fecha_registro
            })
            
            logger.info(f"✅ URL de foto procesada: {url} para {estado_360}")
            
        except Exception as e:
            logger.error(f"❌ Error procesando URL de foto {idx + 1}: {e}")
            fotos_fallidas.append({
                'url': photos_urls[idx] if idx < len(photos_urls) else 'unknown',
                'error': str(e)
            })
    
    return fotos_exitosas, fotos_fallidas


async def crear_registro_captura_360(
    upid: str,
    nombre_up: str,
    nombre_up_detalle: str,
    descripcion_intervencion: str,
    solicitud_intervencion: str,
    up_entorno: Dict[str, Any],
    estado_360: str,
    requiere_alcalde: bool,
    entrega_publica: bool,
    tipo_visita: str,
    observaciones: Optional[str],
    registrado_por: Dict[str, str],
    coordinates_gps: Dict[str, Any],
    photos_info: Optional[List[Dict]] = None
) -> Dict[str, Any]:
    """
    Crear o actualizar registro de captura estado 360 en Firestore (UPSERT)
    
    Args:
        upid: ID de la unidad de proyecto
        nombre_up: Nombre de la unidad de proyecto
        nombre_up_detalle: Detalle del nombre
        descripcion_intervencion: Descripción de la intervención
        solicitud_intervencion: Solicitud de intervención
        up_entorno: Información del entorno (dict con nombre_centro_gestor, invocar_centro_gestor, solicitud_centro_gestor)
        estado_360: Estado 360 del proyecto ('Antes', 'Durante', 'Después')
        requiere_alcalde: Boolean indicando si requiere alcalde
        entrega_publica: Boolean indicando si hay entrega pública
        tipo_visita: Tipo de visita ('Verificación' o 'Comunicaciones')
        observaciones: Observaciones adicionales (opcional)
        registrado_por: Información de quién registra (dict con username y email)
        coordinates_gps: Coordenadas GPS (formato GeoJSON)
        photos_info: Información de fotos subidas (opcional)
        
    Returns:
        Diccionario con resultado de la operación
    """
    try:
        # Obtener cliente Firestore
        db = get_firestore_client()
        if db is None:
            return {
                "success": False,
                "error": "No se pudo conectar a Firestore",
                "timestamp": datetime.now().isoformat()
            }
        
        # Generar timestamp
        fecha_registro = datetime.now().isoformat()
        
        # Obtener el primer centro gestor para referencia
        # Si hay múltiples centros, usamos el primero para la carpeta principal
        entornos = up_entorno.get('entornos', [])
        nombre_centro_gestor = entornos[0]['nombre_centro_gestor'] if entornos else ''
        
        # Preparar objeto photosUrl basado en estado_360
        # Ahora guardamos URLs directas (no rutas S3)
        photos_url = {
            "photosBeforeUrl": [],
            "photoWhileUrl": [],
            "photosAfterUrl": []
        }
        
        # Si hay fotos (URLs) subidas, agregarlas a la lista correspondiente según estado_360
        if photos_info and len(photos_info) > 0:
            # Extraer solo las URLs de photos_info
            photo_urls_list = [photo['url'] for photo in photos_info]
            
            if estado_360 == "Antes":
                photos_url["photosBeforeUrl"] = photo_urls_list
            elif estado_360 == "Durante":
                photos_url["photoWhileUrl"] = photo_urls_list
            elif estado_360 == "Después":
                photos_url["photosAfterUrl"] = photo_urls_list
        
        # coordinates_gps debe guardarse como objeto GeoJSON con coordinates como string
        # Esto evita el error de Firestore "invalid nested entity"
        # Formato: {"type": "Point", "coordinates": "[lng, lat]"}
        import json
        coordinates_gps_firestore = {
            "type": coordinates_gps.get("type") if coordinates_gps else None,
            "coordinates": json.dumps(coordinates_gps.get("coordinates")) if coordinates_gps else "[]"
        }
        
        # UPSERT: Buscar documento existente por upid y estado_360
        query = db.collection(COLLECTION_NAME).where("upid", "==", upid).where("estado_360", "==", estado_360).limit(1)
        existing_docs = list(query.stream())
        
        # Preparar documento con nuevos valores
        documento_actualizado = {
            "upid": upid,
            "nombre_up": nombre_up,
            "nombre_up_detalle": nombre_up_detalle,
            "descripcion_intervencion": descripcion_intervencion,
            "solicitud_intervencion": solicitud_intervencion,
            "up_entorno": up_entorno,
            "estado_360": estado_360,
            "fecha_registro": fecha_registro,
            "requiere_alcalde": requiere_alcalde,
            "entrega_publica": entrega_publica,
            "tipo_visita": tipo_visita,
            "registrado_por": registrado_por,
            "coordinates_gps": coordinates_gps_firestore,
            "updated_at": firestore.SERVER_TIMESTAMP
        }
        
        # Agregar observaciones solo si se proporciona
        if observaciones is not None:
            documento_actualizado["observaciones"] = observaciones
        
        # Agregar photosUrl
        documento_actualizado["photosUrl"] = photos_url
        
        if existing_docs:
            # Actualizar documento existente
            doc_ref = existing_docs[0].reference
            existing_data = existing_docs[0].to_dict()
            
            # Merge de photosUrl: mantener URLs existentes y agregar nuevas
            if photos_info and len(photos_info) > 0:
                existing_photos_url = existing_data.get("photosUrl", {})
                
                # Para cada estado, combinar URLs existentes con nuevas
                for key in ["photosBeforeUrl", "photoWhileUrl", "photosAfterUrl"]:
                    existing_urls = existing_photos_url.get(key, [])
                    new_urls = photos_url.get(key, [])
                    
                    # Si hay URLs nuevas como lista, combinarlas
                    if isinstance(new_urls, list) and isinstance(existing_urls, list):
                        documento_actualizado["photosUrl"][key] = existing_urls + new_urls
                    elif isinstance(new_urls, list):
                        documento_actualizado["photosUrl"][key] = new_urls
                    elif isinstance(existing_urls, list):
                        documento_actualizado["photosUrl"][key] = existing_urls
            
            doc_ref.update(documento_actualizado)
            logger.info(f"✅ Registro actualizado en {COLLECTION_NAME}: {doc_ref.id}")
            accion = "actualizado"
        else:
            # Crear nuevo documento
            documento_actualizado["created_at"] = firestore.SERVER_TIMESTAMP
            doc_ref = db.collection(COLLECTION_NAME).document()
            doc_ref.set(documento_actualizado)
            logger.info(f"✅ Registro creado en {COLLECTION_NAME}: {doc_ref.id}")
            accion = "creado"
        
        # Crear copia del documento sin los timestamps de Firestore para retornar
        documento_respuesta = {
            "upid": upid,
            "nombre_up": nombre_up,
            "nombre_up_detalle": nombre_up_detalle,
            "descripcion_intervencion": descripcion_intervencion,
            "solicitud_intervencion": solicitud_intervencion,
            "up_entorno": up_entorno,
            "estado_360": estado_360,
            "fecha_registro": fecha_registro,
            "requiere_alcalde": requiere_alcalde,
            "entrega_publica": entrega_publica,
            "tipo_visita": tipo_visita,
            "registrado_por": registrado_por,
            "coordinates_gps": coordinates_gps_firestore,
            "photosUrl": documento_actualizado["photosUrl"]
        }
        
        if observaciones is not None:
            documento_respuesta["observaciones"] = observaciones
        
        return {
            "success": True,
            "message": f"Registro de captura 360 {accion} exitosamente para UPID {upid}",
            "data": documento_respuesta,
            "document_id": doc_ref.id,
            "estado_360": estado_360,
            "collection": COLLECTION_NAME,
            "timestamp": fecha_registro,
            "action": accion
        }
        
    except Exception as e:
        logger.error(f"❌ Error creando registro captura 360: {e}")
        return {
            "success": False,
            "error": f"Error creando registro: {str(e)}",
            "timestamp": datetime.now().isoformat()
        }


async def obtener_registros_con_filtros(filtros: Dict[str, str]) -> Dict[str, Any]:
    """
    Obtener registros de captura 360 con filtros opcionales
    
    Args:
        filtros: Diccionario con filtros opcionales (upid, nombre_centro_gestor, estado_360, tipo_visita)
        
    Returns:
        Diccionario con los registros encontrados
    """
    try:
        db = get_firestore_client()
        if db is None:
            return {
                "success": False,
                "error": "No se pudo conectar a Firestore",
                "timestamp": datetime.now().isoformat()
            }
        
        # Iniciar query base
        query = db.collection(COLLECTION_NAME)
        
        # Aplicar filtros si existen
        if "upid" in filtros:
            query = query.where("upid", "==", filtros["upid"])
        
        if "estado_360" in filtros:
            query = query.where("estado_360", "==", filtros["estado_360"])
        
        if "tipo_visita" in filtros:
            query = query.where("tipo_visita", "==", filtros["tipo_visita"])
        
        # Para nombre_centro_gestor, necesitamos filtrar en up_entorno.nombre_centro_gestor
        if "nombre_centro_gestor" in filtros:
            query = query.where("up_entorno.nombre_centro_gestor", "==", filtros["nombre_centro_gestor"])
        
        # Ejecutar query
        docs = query.stream()
        
        registros = []
        for doc in docs:
            data = doc.to_dict()
            data['document_id'] = doc.id
            registros.append(data)
        
        return {
            "success": True,
            "data": registros,
            "count": len(registros),
            "filtros_aplicados": filtros,
            "collection": COLLECTION_NAME,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"❌ Error obteniendo registros con filtros: {e}")
        return {
            "success": False,
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }


async def obtener_registros_por_upid(upid: str) -> Dict[str, Any]:
    """
    Obtener todos los registros de captura 360 para un UPID específico
    (Función legacy - usar obtener_registros_con_filtros en su lugar)
    
    Args:
        upid: ID de la unidad de proyecto
        
    Returns:
        Diccionario con los registros encontrados
    """
    return await obtener_registros_con_filtros({"upid": upid})


# Flag de disponibilidad
CAPTURA_360_OPERATIONS_AVAILABLE = True

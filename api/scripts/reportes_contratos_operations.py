"""
Operaciones para reportes de contratos con almacenamiento en AWS S3.
Incluye diagnóstico de carga y normalización de URLs públicas para frontend.
"""

import os
import uuid
import logging
import json
import mimetypes
import unicodedata
from functools import lru_cache
from urllib.parse import urlparse
from datetime import datetime
from typing import Dict, Any, List, Tuple, Optional

# Firebase imports
from database.firebase_config import get_firestore_client

# Intentar importar DatetimeWithNanoseconds, con fallback seguro
try:
    from google.cloud.firestore_v1._helpers import DatetimeWithNanoseconds
    FIREBASE_DATETIME_AVAILABLE = True
except ImportError:
    # Si no se puede importar, crear un tipo placeholder
    DatetimeWithNanoseconds = type('DatetimeWithNanoseconds', (), {})
    FIREBASE_DATETIME_AVAILABLE = False

# S3 imports
try:
    from api.utils.s3_document_manager import S3DocumentManager, BOTO3_AVAILABLE
except Exception:
    S3DocumentManager = None
    BOTO3_AVAILABLE = False

# Configurar logger
logger = logging.getLogger(__name__)

IMAGE_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".bmp", ".gif", ".webp", ".tif", ".tiff", ".heic", ".heif", ".ico"
}

ALLOWED_EXTENSIONS = {
    ".pdf", ".txt", ".csv", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".zip", ".rar", ".7z",
    ".jpg", ".jpeg", ".png", ".bmp", ".gif", ".webp", ".tif", ".tiff", ".heic", ".heif", ".ico"
}


def _sanitize_for_s3(text: str, default: str = "archivo") -> str:
    normalized = unicodedata.normalize("NFKD", str(text or "")).encode("ascii", "ignore").decode("ascii")
    normalized = "".join(ch for ch in normalized if ch.isalnum() or ch in "._-")
    normalized = normalized.strip("._-")
    return normalized or default


def _build_public_url(bucket: str, key: str, region: str) -> str:
    region = (region or "us-east-1").strip()
    if region == "us-east-1":
        return f"https://{bucket}.s3.amazonaws.com/{key}"
    return f"https://{bucket}.s3.{region}.amazonaws.com/{key}"


def _detect_content_type(filename: str, declared_content_type: str = "") -> str:
    if declared_content_type and declared_content_type != "application/octet-stream":
        return declared_content_type
    guessed, _ = mimetypes.guess_type(filename)
    return guessed or "application/octet-stream"


def _bool_from_env(name: str, default: bool = True) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return str(raw).strip().lower() in {"1", "true", "yes", "y", "on"}


def _presigned_enabled() -> bool:
    return _bool_from_env("S3_USE_PRESIGNED_URLS", True)


def _presigned_expiration() -> int:
    try:
        return int(os.getenv("S3_PRESIGNED_URL_EXPIRATION_SECONDS", "3600"))
    except Exception:
        return 3600


def _extract_bucket_key_from_url(url: str) -> Tuple[Optional[str], Optional[str]]:
    if not url:
        return None, None
    try:
        parsed = urlparse(url)
        host = (parsed.netloc or "").lower()
        path = (parsed.path or "").lstrip("/")

        if host.endswith("amazonaws.com"):
            if ".s3." in host:
                bucket = host.split(".s3.")[0]
                return bucket or None, path or None
            if host.startswith("s3.") or host == "s3.amazonaws.com":
                if "/" in path:
                    bucket, key = path.split("/", 1)
                    return bucket or None, key or None
        return None, None
    except Exception:
        return None, None


@lru_cache(maxsize=4)
def _get_s3_client_for_presign(credentials_path: str = ""):
    if not BOTO3_AVAILABLE or S3DocumentManager is None:
        return None
    manager = S3DocumentManager(credentials_path=credentials_path or None)
    return manager.s3_client


def _generate_presigned_url(bucket: str, s3_key: str) -> Optional[str]:
    if not _presigned_enabled() or not bucket or not s3_key:
        return None
    try:
        credentials_path = os.getenv('AWS_CREDENTIALS_FILE_REPORTES_CONTRATOS') or os.getenv('AWS_CREDENTIALS_FILE_UNIDADES_PROYECTO') or ""
        s3_client = _get_s3_client_for_presign(credentials_path)
        if s3_client is None:
            return None
        return s3_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': bucket, 'Key': s3_key},
            ExpiresIn=_presigned_expiration()
        )
    except Exception as e:
        logger.warning(f"No se pudo generar presigned URL para s3://{bucket}/{s3_key}: {e}")
        return None


def _normalize_archivos_for_frontend(doc_data: Dict[str, Any]) -> Dict[str, Any]:
    """Asegura que los reportes siempre expongan URLs públicas listas para frontend."""
    archivos = list(doc_data.get("archivos_evidencia") or [])
    imagenes_urls = []
    documentos_urls = []
    archivos_normalizados = []

    for idx, archivo in enumerate(archivos):
        if not isinstance(archivo, dict):
            continue

        url_publica_directa = (
            archivo.get("url_publica")
            or archivo.get("s3_url")
            or archivo.get("url")
            or archivo.get("download_url")
            or ""
        )
        bucket = archivo.get("bucket")
        s3_key = archivo.get("s3_key")
        if (not bucket or not s3_key) and url_publica_directa:
            parsed_bucket, parsed_key = _extract_bucket_key_from_url(url_publica_directa)
            bucket = bucket or parsed_bucket
            s3_key = s3_key or parsed_key

        presigned_url = _generate_presigned_url(str(bucket or ""), str(s3_key or ""))
        url_publica = presigned_url or url_publica_directa
        content_type = str(archivo.get("content_type") or archivo.get("type") or "")
        extension = str(archivo.get("extension") or "").lower()

        if not extension and archivo.get("name"):
            _, ext = os.path.splitext(str(archivo.get("name")))
            extension = ext.lower()

        is_image = (extension in IMAGE_EXTENSIONS) or content_type.startswith("image/")
        tipo = "imagen" if is_image else "documento"

        archivo_normalizado = {
            "indice": archivo.get("indice", idx + 1),
            "nombre_original": archivo.get("nombre_original") or archivo.get("name") or "archivo",
            "tipo": tipo,
            "extension": extension,
            "content_type": content_type or _detect_content_type(archivo.get("name") or "archivo"),
            "bucket": bucket,
            "s3_key": s3_key,
            "size": archivo.get("size", 0),
            "status": archivo.get("status", "uploaded_successfully"),
            "url_publica_directa": url_publica_directa,
            "url_presigned": presigned_url,
            "url_publica": url_publica,
            "url": url_publica,
        }

        archivos_normalizados.append(archivo_normalizado)
        if url_publica:
            if is_image:
                imagenes_urls.append(url_publica)
            else:
                documentos_urls.append(url_publica)

    doc_data["archivos_evidencia"] = archivos_normalizados
    doc_data["imagenes_urls"] = list(dict.fromkeys(imagenes_urls))
    doc_data["documentos_urls"] = list(dict.fromkeys(documentos_urls))
    doc_data["urls_publicas"] = {
        "imagenes": doc_data["imagenes_urls"],
        "documentos": doc_data["documentos_urls"],
    }
    doc_data["links"] = {
        "imagenes": doc_data["imagenes_urls"],
        "documentos": doc_data["documentos_urls"],
        "all_archivos": archivos_normalizados,
        "visores": {
            "imagenes": doc_data["imagenes_urls"],
            "documentos_inline": [u for u in doc_data["documentos_urls"] if u.lower().endswith(".pdf")],
            "documentos_download": [u for u in doc_data["documentos_urls"] if not u.lower().endswith(".pdf")],
        }
    }
    doc_data["total_imagenes"] = len(doc_data["imagenes_urls"])
    doc_data["total_documentos"] = len(doc_data["documentos_urls"])
    doc_data["total_archivos_evidencia"] = len(archivos_normalizados)
    return doc_data


def upload_files_to_s3(referencia_contrato: str, archivos: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Sube archivos de evidencia a S3 separando imágenes y documentos."""
    if not BOTO3_AVAILABLE or S3DocumentManager is None:
        raise Exception("S3 no disponible: boto3 o S3DocumentManager no importado")

    credentials_path = os.getenv('AWS_CREDENTIALS_FILE_REPORTES_CONTRATOS') or os.getenv('AWS_CREDENTIALS_FILE_UNIDADES_PROYECTO')
    s3_manager = S3DocumentManager(credentials_path=credentials_path)
    s3_client = s3_manager.s3_client

    # Requisito funcional: reportes_contratos debe guardar TODO dentro del bucket contratos-emprestito.
    # Se mantiene separación por carpetas/prefix (fotos vs documentos), no por bucket.
    contratos_bucket = "contratos-emprestito"
    fotos_bucket = contratos_bucket
    docs_bucket = contratos_bucket
    fotos_prefix = os.getenv('S3_PREFIX_REPORTES_CONTRATOS_FOTOS', 'reportes_contratos_fotos').strip('/')
    docs_prefix = os.getenv('S3_PREFIX_REPORTES_CONTRATOS_DOCUMENTOS', 'reportes_contratos_documentos').strip('/')

    # Verificación temprana de buckets para diagnóstico confiable
    s3_client.head_bucket(Bucket=fotos_bucket)
    s3_client.head_bucket(Bucket=docs_bucket)

    now = datetime.now()
    date_part = now.strftime('%Y-%m-%d')
    ts_part = now.strftime('%Y%m%d_%H%M%S')
    safe_ref = _sanitize_for_s3(referencia_contrato, default='sin_referencia')

    archivos_subidos = []
    failed = []
    total_imagenes = 0
    total_documentos = 0

    for idx, archivo in enumerate(archivos):
        nombre_original = str(archivo.get("filename") or f"archivo_{idx + 1}")
        _, ext = os.path.splitext(nombre_original)
        ext_lower = ext.lower()
        content_type = _detect_content_type(nombre_original, archivo.get("content_type", ""))
        is_image = ext_lower in IMAGE_EXTENSIONS or content_type.startswith('image/')

        try:
            target_bucket = fotos_bucket if is_image else docs_bucket
            target_prefix = fotos_prefix if is_image else docs_prefix
            safe_name = _sanitize_for_s3(os.path.splitext(nombre_original)[0], default=f"archivo_{idx + 1}")
            final_ext = ext_lower if ext_lower else (".jpg" if is_image else "")
            object_name = f"{safe_ref}_{ts_part}_{idx + 1:03d}_{safe_name}{final_ext}"
            s3_key = f"{target_prefix}/{safe_ref}/{date_part}/{object_name}"
            file_bytes = archivo.get("content") or b""

            content_disposition = "inline" if (is_image or ext_lower == ".pdf") else f'attachment; filename="{object_name}"'
            s3_client.put_object(
                Bucket=target_bucket,
                Key=s3_key,
                Body=file_bytes,
                ContentType=content_type,
                ContentDisposition=content_disposition,
                Metadata={
                    "referencia_contrato": _sanitize_for_s3(referencia_contrato, "sin_ref")[:120],
                    "tipo": "imagen" if is_image else "documento",
                    "original_filename": _sanitize_for_s3(nombre_original, "archivo")[:150],
                    "upload_date": datetime.now().isoformat(),
                }
            )

            region = os.getenv('AWS_REGION') or s3_manager.region or 'us-east-1'
            public_url_directa = _build_public_url(target_bucket, s3_key, region)
            presigned_url = _generate_presigned_url(target_bucket, s3_key)
            public_url = presigned_url or public_url_directa

            item = {
                "indice": idx + 1,
                "name": nombre_original,
                "nombre_original": nombre_original,
                "size": int(archivo.get("size") or len(file_bytes)),
                "type": content_type,
                "content_type": content_type,
                "tipo": "imagen" if is_image else "documento",
                "extension": ext_lower,
                "bucket": target_bucket,
                "s3_key": s3_key,
                "s3_url": public_url_directa,
                "url_publica_directa": public_url_directa,
                "url_presigned": presigned_url,
                "url_publica": public_url,
                "url": public_url,
                "status": "uploaded_successfully"
            }
            archivos_subidos.append(item)
            if is_image:
                total_imagenes += 1
            else:
                total_documentos += 1

        except Exception as upload_error:
            failed.append({
                "name": nombre_original,
                "error": str(upload_error)
            })

    diagnostico = {
        "storage_provider": "aws_s3",
        "buckets": {
            "fotos": fotos_bucket,
            "documentos": docs_bucket,
        },
        "prefixes": {
            "fotos": fotos_prefix,
            "documentos": docs_prefix,
        },
        "total_recibidos": len(archivos),
        "total_subidos": len(archivos_subidos),
        "total_fallidos": len(failed),
        "total_imagenes": total_imagenes,
        "total_documentos": total_documentos,
        "fallidos": failed,
        "timestamp": datetime.now().isoformat(),
    }

    return archivos_subidos, diagnostico

def convert_firebase_timestamps(doc_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convertir timestamps de Firebase a strings serializables
    """
    converted_data = {}
    for key, value in doc_data.items():
        # Verificar si el valor tiene el método isoformat (datetime-like)
        if hasattr(value, 'isoformat') and callable(getattr(value, 'isoformat')):
            # Convertir a ISO string
            converted_data[key] = value.isoformat()
        elif isinstance(value, datetime):
            # Convertir datetime regular a ISO string
            converted_data[key] = value.isoformat()
        elif isinstance(value, dict):
            # Recursivamente convertir diccionarios anidados
            converted_data[key] = convert_firebase_timestamps(value)
        elif isinstance(value, list):
            # Convertir listas que pueden contener objetos con fechas
            converted_list = []
            for item in value:
                if isinstance(item, dict):
                    converted_list.append(convert_firebase_timestamps(item))
                elif hasattr(item, 'isoformat') and callable(getattr(item, 'isoformat')):
                    converted_list.append(item.isoformat())
                elif isinstance(item, datetime):
                    converted_list.append(item.isoformat())
                else:
                    converted_list.append(item)
            converted_data[key] = converted_list
        else:
            converted_data[key] = value
    return converted_data

def create_drive_folder(referencia_contrato: str, archivos: List[Dict[str, Any]]) -> Tuple[str, List[Dict[str, str]]]:
    """Compatibilidad legacy: usa S3 y retorna URL base + archivos."""
    archivos_subidos, diagnostico = upload_files_to_s3(referencia_contrato, archivos)
    base_url = diagnostico["buckets"]["documentos"] if diagnostico.get("buckets") else ""
    return str(base_url), archivos_subidos

def get_drive_credentials():
    """Compatibilidad legacy: el flujo activo usa S3, no Google Drive."""
    return None

def create_folder_in_drive(service, referencia_contrato: str, parent_folder_id: str = None, shared_drive_id: str = None) -> Tuple[str, str]:
    """Compatibilidad legacy: devuelve placeholders, flujo actual usa S3."""
    safe_ref = _sanitize_for_s3(referencia_contrato, default="sin_referencia")
    return f"legacy_{safe_ref}", ""

def upload_files_to_folder(service, archivos: List[Dict[str, Any]], folder_id: str) -> List[Dict[str, str]]:
    """Compatibilidad legacy: usa pipeline de S3."""
    archivos_subidos, _ = upload_files_to_s3(folder_id or "legacy", archivos)
    return archivos_subidos

def upload_single_file(service, archivo: Dict[str, Any], folder_id: str) -> Dict[str, str]:
    """Compatibilidad legacy: sube un solo archivo usando S3."""
    archivos_subidos, diagnostico = upload_files_to_s3(folder_id or "legacy", [archivo])
    if archivos_subidos:
        return archivos_subidos[0]
    return {
        "name": archivo.get("filename", "archivo"),
        "size": int(archivo.get("size", 0)),
        "type": archivo.get("content_type", "application/octet-stream"),
        "status": "upload_failed",
        "error": json.dumps(diagnostico.get("fallidos", []), ensure_ascii=False)
    }



def validate_uploaded_files(archivos_evidencia: List[Dict[str, Any]]) -> Tuple[bool, str]:
    """
    Validar archivos subidos
    """
    if not archivos_evidencia:
        return False, "Se requiere al menos un archivo de evidencia"
    
    for archivo in archivos_evidencia:
        filename = str(archivo.get('filename') or '')
        _, ext = os.path.splitext(filename)
        ext_lower = ext.lower()
        if ext_lower and ext_lower not in ALLOWED_EXTENSIONS:
            return False, f"Extensión no permitida: {ext_lower}"
        if not filename:
            return False, "Todos los archivos deben tener filename"
        
        if archivo.get('size', 0) > 10 * 1024 * 1024:  # 10MB
            return False, f"Archivo demasiado grande: {archivo.get('filename')}"
    
    return True, "Archivos válidos"

async def create_reporte_contrato(reporte_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Crear reporte de contrato con almacenamiento S3 (fotos y documentos).
    Si nombre_centro_gestor viene vacío, se resuelve automáticamente desde
    las colecciones de empréstito usando referencia_contrato como clave.
    """
    try:
        db = get_firestore_client()
        if db is None:
            raise Exception("No se pudo conectar a Firestore")
        
        # Validar archivos
        is_valid, validation_message = validate_uploaded_files(reporte_data.get('archivos_evidencia', []))
        if not is_valid:
            raise Exception(validation_message)
        
        archivos_subidos, diagnostico_s3 = upload_files_to_s3(
            reporte_data['referencia_contrato'],
            reporte_data['archivos_evidencia']
        )

        if diagnostico_s3.get("total_fallidos", 0) > 0:
            failed_names = [f.get("name", "archivo") for f in diagnostico_s3.get("fallidos", [])]
            raise Exception(f"Error subiendo archivos a S3: {failed_names}")
        
        # Resolver nombre_centro_gestor: usar el enviado, o auto-resolver desde empréstito
        nombre_centro_gestor = (reporte_data.get('nombre_centro_gestor') or '').strip()
        if not nombre_centro_gestor:
            try:
                nombre_centro_gestor_resolved = await get_nombre_centro_gestor_from_emprestito(
                    reporte_data['referencia_contrato']
                )
                if nombre_centro_gestor_resolved:
                    nombre_centro_gestor = nombre_centro_gestor_resolved
                    logger.info(
                        f"✅ nombre_centro_gestor auto-resuelto desde empréstito: "
                        f"'{nombre_centro_gestor}' para referencia '{reporte_data['referencia_contrato']}'"
                    )
            except Exception as resolve_error:
                logger.warning(f"⚠️ No se pudo auto-resolver nombre_centro_gestor: {resolve_error}")
        
        # Datos para Firebase
        doc_data = {
            'referencia_contrato': reporte_data['referencia_contrato'],
            'nombre_centro_gestor': nombre_centro_gestor,
            'observaciones': reporte_data['observaciones'],
            'avance_fisico': reporte_data['avance_fisico'],
            'avance_financiero': reporte_data['avance_financiero'],
            'alertas': reporte_data['alertas'],
            'archivos_evidencia': archivos_subidos,
            'almacenamiento': {
                'provider': 'aws_s3',
                'diagnostico': diagnostico_s3,
            },
            'url_carpeta_drive': None,
            'url_carpeta_s3': {
                'fotos': f"s3://{diagnostico_s3['buckets']['fotos']}/{diagnostico_s3['prefixes']['fotos']}/{_sanitize_for_s3(reporte_data['referencia_contrato'], 'sin_referencia')}/",
                'documentos': f"s3://{diagnostico_s3['buckets']['documentos']}/{diagnostico_s3['prefixes']['documentos']}/{_sanitize_for_s3(reporte_data['referencia_contrato'], 'sin_referencia')}/",
            },
            'imagenes_urls': [a.get('url_publica') for a in archivos_subidos if a.get('tipo') == 'imagen' and a.get('url_publica')],
            'documentos_urls': [a.get('url_publica') for a in archivos_subidos if a.get('tipo') == 'documento' and a.get('url_publica')],
            'fecha_reporte': datetime.now(),
            'estado_reporte': 'activo'
        }
        
        # Guardar en Firebase
        doc_ref = db.collection('reportes_contratos').add(doc_data)
        doc_id = doc_ref[1].id
        
        logger.info(f"✅ Reporte creado: {doc_id}")
        
        return {
            "success": True,
            "message": "Reporte creado exitosamente con archivos en S3",
            "doc_id": doc_id,
            "url_carpeta_drive": None,
            "url_carpeta_s3": doc_data.get("url_carpeta_s3"),
            "diagnostico_s3": diagnostico_s3,
            "imagenes_urls": doc_data.get("imagenes_urls", []),
            "documentos_urls": doc_data.get("documentos_urls", [])
        }
        
    except Exception as e:
        logger.error(f"❌ Error creando reporte: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "doc_id": None
        }

async def get_nombre_centro_gestor_from_emprestito(referencia_contrato: str) -> Optional[str]:
    """
    Obtener nombre_centro_gestor desde las colecciones contratos_emprestito, 
    ordenes_compra_emprestito y convenios_transferencias_emprestito
    usando la referencia_contrato como clave de búsqueda
    """
    try:
        db = get_firestore_client()
        if db is None:
            return None
        
        # Buscar primero en la colección contratos_emprestito
        collection_ref = db.collection('contratos_emprestito')
        query = collection_ref.where('referencia_contrato', '==', referencia_contrato).limit(1)
        docs = list(query.stream())
        
        if docs:
            doc_data = docs[0].to_dict()
            nombre_cg = doc_data.get('nombre_centro_gestor', '')
            if nombre_cg:
                return nombre_cg
        
        # Si no se encuentra en contratos, buscar en ordenes_compra_emprestito (usando numero_orden)
        collection_ref = db.collection('ordenes_compra_emprestito')
        query = collection_ref.where('numero_orden', '==', referencia_contrato).limit(1)
        docs = list(query.stream())
        
        if docs:
            doc_data = docs[0].to_dict()
            nombre_cg = doc_data.get('nombre_centro_gestor', '')
            if nombre_cg:
                return nombre_cg
        
        # Si no se encuentra en ordenes, buscar en convenios_transferencias_emprestito
        collection_ref = db.collection('convenios_transferencias_emprestito')
        query = collection_ref.where('referencia_contrato', '==', referencia_contrato).limit(1)
        docs = list(query.stream())
        
        if docs:
            doc_data = docs[0].to_dict()
            nombre_cg = doc_data.get('nombre_centro_gestor', '')
            if nombre_cg:
                return nombre_cg
        
        return None
        
    except Exception as e:
        logger.warning(f"Error obteniendo nombre_centro_gestor para {referencia_contrato}: {e}")
        return None

async def get_data_from_emprestito(referencia_contrato: str) -> Optional[Dict[str, str]]:
    """
    Obtener nombre_centro_gestor y bp desde las colecciones contratos_emprestito, 
    ordenes_compra_emprestito y convenios_transferencias_emprestito
    usando la referencia_contrato como clave de búsqueda
    
    Returns:
        Dict con 'nombre_centro_gestor' y 'bp' si se encuentran, None si no
    """
    try:
        db = get_firestore_client()
        if db is None:
            return None
        
        # Buscar primero en la colección contratos_emprestito
        collection_ref = db.collection('contratos_emprestito')
        query = collection_ref.where('referencia_contrato', '==', referencia_contrato).limit(1)
        docs = list(query.stream())
        
        if docs:
            doc_data = docs[0].to_dict()
            nombre_cg = doc_data.get('nombre_centro_gestor', '')
            bp = doc_data.get('bp', '')
            if nombre_cg or bp:
                return {
                    'nombre_centro_gestor': nombre_cg,
                    'bp': bp
                }
        
        # Si no se encuentra en contratos, buscar en ordenes_compra_emprestito (usando numero_orden)
        collection_ref = db.collection('ordenes_compra_emprestito')
        query = collection_ref.where('numero_orden', '==', referencia_contrato).limit(1)
        docs = list(query.stream())
        
        if docs:
            doc_data = docs[0].to_dict()
            nombre_cg = doc_data.get('nombre_centro_gestor', '')
            bp = doc_data.get('bp', '')
            if nombre_cg or bp:
                return {
                    'nombre_centro_gestor': nombre_cg,
                    'bp': bp
                }
        
        # Si no se encuentra en ordenes, buscar en convenios_transferencias_emprestito
        collection_ref = db.collection('convenios_transferencias_emprestito')
        query = collection_ref.where('referencia_contrato', '==', referencia_contrato).limit(1)
        docs = list(query.stream())
        
        if docs:
            doc_data = docs[0].to_dict()
            nombre_cg = doc_data.get('nombre_centro_gestor', '')
            bp = doc_data.get('bp', '')
            if nombre_cg or bp:
                return {
                    'nombre_centro_gestor': nombre_cg,
                    'bp': bp
                }
        
        return None
        
    except Exception as e:
        logger.warning(f"Error obteniendo datos de empréstito para {referencia_contrato}: {e}")
        return None

async def get_all_centros_gestores_map() -> Dict[str, Dict[str, str]]:
    """
    Obtener un mapa de referencia_contrato -> {nombre_centro_gestor, bp}
    de las colecciones contratos_emprestito, ordenes_compra_emprestito 
    y convenios_transferencias_emprestito de una sola vez
    """
    try:
        db = get_firestore_client()
        if db is None:
            return {}
        
        # Crear mapa en memoria
        centro_gestor_map = {}
        
        # Obtener todos los contratos de empréstito
        collection_ref = db.collection('contratos_emprestito')
        docs = collection_ref.stream()
        
        for doc in docs:
            doc_data = doc.to_dict()
            ref_contrato = doc_data.get('referencia_contrato')
            nombre_cg = doc_data.get('nombre_centro_gestor', '')
            bp = doc_data.get('bp', '')
            if ref_contrato and (nombre_cg or bp):
                centro_gestor_map[ref_contrato] = {
                    'nombre_centro_gestor': nombre_cg,
                    'bp': bp
                }
        
        # Obtener todas las órdenes de compra
        collection_ref = db.collection('ordenes_compra_emprestito')
        docs = collection_ref.stream()
        
        for doc in docs:
            doc_data = doc.to_dict()
            # Usar numero_orden como referencia_contrato
            ref_contrato = doc_data.get('numero_orden')
            nombre_cg = doc_data.get('nombre_centro_gestor', '')
            bp = doc_data.get('bp', '')
            if ref_contrato and (nombre_cg or bp) and ref_contrato not in centro_gestor_map:
                centro_gestor_map[ref_contrato] = {
                    'nombre_centro_gestor': nombre_cg,
                    'bp': bp
                }
        
        # Obtener todos los convenios de transferencia
        collection_ref = db.collection('convenios_transferencias_emprestito')
        docs = collection_ref.stream()
        
        for doc in docs:
            doc_data = doc.to_dict()
            ref_contrato = doc_data.get('referencia_contrato')
            nombre_cg = doc_data.get('nombre_centro_gestor', '')
            bp = doc_data.get('bp', '')
            if ref_contrato and (nombre_cg or bp) and ref_contrato not in centro_gestor_map:
                centro_gestor_map[ref_contrato] = {
                    'nombre_centro_gestor': nombre_cg,
                    'bp': bp
                }
        
        logger.info(f"✅ Mapa de centros gestores y BP creado con {len(centro_gestor_map)} entradas (contratos + órdenes + convenios)")
        return centro_gestor_map
        
    except Exception as e:
        logger.warning(f"Error creando mapa de centros gestores: {e}")
        return {}

async def get_reportes_contratos(filtros: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Obtener lista de reportes de contratos con nombre_centro_gestor y bp desde colecciones de empréstito
    (contratos_emprestito, ordenes_compra_emprestito, convenios_transferencias_emprestito)
    OPTIMIZADO: Carga todos los centros gestores y bp de una sola vez para evitar N+1 queries
    """
    try:
        db = get_firestore_client()
        if db is None:
            return {
                "success": False,
                "error": "No se pudo conectar a Firestore",
                "data": [],
                "count": 0
            }
        
        # OPTIMIZACIÓN: Cargar mapa de centros gestores UNA SOLA VEZ (incluye contratos, órdenes y convenios)
        centro_gestor_map = await get_all_centros_gestores_map()
        
        collection_ref = db.collection('reportes_contratos')
        
        # Aplicar filtros si existen
        if filtros:
            if 'referencia_contrato' in filtros:
                collection_ref = collection_ref.where('referencia_contrato', '==', filtros['referencia_contrato'])
            if 'estado_reporte' in filtros:
                collection_ref = collection_ref.where('estado_reporte', '==', filtros['estado_reporte'])
        
        # Obtener documentos sin ordenar para evitar errores con campos faltantes
        try:
            docs = collection_ref.order_by('fecha_reporte', direction='DESCENDING').stream()
        except Exception as order_error:
            logger.warning(f"Error ordenando por fecha_reporte, obteniendo sin ordenar: {order_error}")
            # Si falla el order_by, obtener sin ordenar
            docs = collection_ref.stream()
        
        reportes = []
        for doc in docs:
            try:
                doc_data = doc.to_dict()
                if doc_data:  # Verificar que el documento no esté vacío
                    # Convertir timestamps de Firebase a strings serializables
                    converted_data = convert_firebase_timestamps(doc_data)
                    converted_data = _normalize_archivos_for_frontend(converted_data)
                    
                    # OPTIMIZACIÓN: Lookup en memoria en lugar de query a Firebase
                    referencia_contrato = converted_data.get('referencia_contrato')
                    nombre_centro_gestor_actual = converted_data.get('nombre_centro_gestor', '')
                    bp_actual = converted_data.get('bp', '')
                    
                    # Heredar datos de empréstito si es necesario
                    if referencia_contrato:
                        # Buscar en el mapa en memoria (O(1) lookup vs query a Firebase)
                        # El mapa incluye contratos_emprestito, ordenes_compra_emprestito y convenios_transferencias_emprestito
                        emprestito_data = centro_gestor_map.get(referencia_contrato)
                        if emprestito_data:
                            # Heredar nombre_centro_gestor si no existe o está vacío
                            if not nombre_centro_gestor_actual or nombre_centro_gestor_actual.strip() == '':
                                nombre_centro_gestor_emprestito = emprestito_data.get('nombre_centro_gestor', '')
                                if nombre_centro_gestor_emprestito:
                                    converted_data['nombre_centro_gestor'] = nombre_centro_gestor_emprestito
                            
                            # Heredar bp si no existe o está vacío
                            if not bp_actual or bp_actual.strip() == '':
                                bp_emprestito = emprestito_data.get('bp', '')
                                if bp_emprestito:
                                    converted_data['bp'] = bp_emprestito
                    
                    # Construir reporte_data con el orden deseado: id, bp, luego el resto
                    reporte_data = {
                        'id': doc.id,
                        'bp': converted_data.pop('bp', ''),
                        **converted_data
                    }
                    
                    reportes.append(reporte_data)
            except Exception as doc_error:
                logger.warning(f"Error procesando documento {doc.id}: {doc_error}")
                continue
        
        # Ordenar manualmente por fecha_reporte si existe el campo
        try:
            reportes.sort(key=lambda x: x.get('fecha_reporte', ''), reverse=True)
        except Exception as sort_error:
            logger.warning(f"Error ordenando reportes manualmente: {sort_error}")
        
        return {
            "success": True,
            "data": reportes,
            "count": len(reportes),
            "collection": "reportes_contratos",
            "timestamp": datetime.now().isoformat(),
            "message": f"Se obtuvieron {len(reportes)} reportes de contratos exitosamente (con nombre_centro_gestor y bp desde contratos_emprestito cuando necesario)"
        }
        
    except Exception as e:
        logger.error(f"Error obteniendo reportes: {str(e)}")
        return {
            "success": False,
            "error": f"Error obteniendo reportes: {str(e)}",
            "data": [],
            "count": 0
        }

async def get_reporte_contrato_by_id(reporte_id: str) -> Dict[str, Any]:
    """
    Obtener un reporte específico por ID con nombre_centro_gestor y bp desde colecciones de empréstito
    (contratos_emprestito, ordenes_compra_emprestito, convenios_transferencias_emprestito)
    """
    try:
        db = get_firestore_client()
        if db is None:
            return {
                "success": False,
                "error": "No se pudo conectar a Firestore",
                "data": None
            }
        
        doc_ref = db.collection('reportes_contratos').document(reporte_id)
        doc = doc_ref.get()
        
        if not doc.exists:
            return {
                "success": False,
                "error": "Reporte no encontrado",
                "data": None
            }
        
        doc_data = doc.to_dict()
        # Convertir timestamps de Firebase a strings serializables
        converted_data = convert_firebase_timestamps(doc_data)
        converted_data = _normalize_archivos_for_frontend(converted_data)
        
        # Obtener nombre_centro_gestor y bp desde colecciones de empréstito si no existen o están vacíos
        referencia_contrato = converted_data.get('referencia_contrato')
        nombre_centro_gestor_actual = converted_data.get('nombre_centro_gestor', '')
        bp_actual = converted_data.get('bp', '')
        
        if referencia_contrato:
            # Obtener datos de empréstito
            emprestito_data = await get_data_from_emprestito(referencia_contrato)
            if emprestito_data:
                # Heredar nombre_centro_gestor si no existe o está vacío
                if not nombre_centro_gestor_actual or nombre_centro_gestor_actual.strip() == '':
                    nombre_centro_gestor_emprestito = emprestito_data.get('nombre_centro_gestor', '')
                    if nombre_centro_gestor_emprestito:
                        converted_data['nombre_centro_gestor'] = nombre_centro_gestor_emprestito
                        logger.info(f"✅ Actualizado nombre_centro_gestor para reporte {reporte_id}: {nombre_centro_gestor_emprestito}")
                
                # Heredar bp si no existe o está vacío
                if not bp_actual or bp_actual.strip() == '':
                    bp_emprestito = emprestito_data.get('bp', '')
                    if bp_emprestito:
                        converted_data['bp'] = bp_emprestito
                        logger.info(f"✅ Actualizado bp para reporte {reporte_id}: {bp_emprestito}")
        
        # Construir reporte_data con el orden deseado: id, bp, luego el resto
        reporte_data = {
            'id': doc.id,
            'bp': converted_data.pop('bp', ''),
            **converted_data
        }
        
        return {
            "success": True,
            "data": reporte_data,
            "message": "Reporte obtenido exitosamente"
        }
        
    except Exception as e:
        logger.error(f"Error obteniendo reporte por ID: {str(e)}")
        return {
            "success": False,
            "error": f"Error obteniendo reporte: {str(e)}",
            "data": None
        }

async def get_reportes_by_centro_gestor(nombre_centro_gestor: str) -> Dict[str, Any]:
    """
    Obtener reportes filtrados por nombre_centro_gestor 
    (también busca en contratos_emprestito, ordenes_compra_emprestito y convenios_transferencias_emprestito)
    """
    try:
        db = get_firestore_client()
        if db is None:
            return {
                "success": False,
                "error": "No se pudo conectar a Firestore",
                "data": []
            }
        
        # Buscar reportes por nombre_centro_gestor en reportes_contratos
        query = db.collection('reportes_contratos').where('nombre_centro_gestor', '==', nombre_centro_gestor)
        try:
            docs = list(query.order_by('fecha_reporte', direction='DESCENDING').stream())
        except Exception as order_error:
            logger.warning(f"Fallback sin order_by en get_reportes_by_centro_gestor: {order_error}")
            docs = list(query.stream())
        
        reportes = []
        for doc in docs:
            doc_data = doc.to_dict()
            # Convertir timestamps de Firebase a strings serializables
            converted_data = convert_firebase_timestamps(doc_data)
            converted_data = _normalize_archivos_for_frontend(converted_data)
            reporte_data = {
                'id': doc.id,
                **converted_data
            }
            reportes.append(reporte_data)
        
        # Recopilar referencias de contrato de todas las colecciones de empréstito
        referencias_emprestito = set()
        
        try:
            # Obtener referencias desde contratos_emprestito
            emprestito_docs = db.collection('contratos_emprestito')\
                               .where('nombre_centro_gestor', '==', nombre_centro_gestor)\
                               .stream()
            
            for emp_doc in emprestito_docs:
                emp_data = emp_doc.to_dict()
                ref_contrato = emp_data.get('referencia_contrato')
                if ref_contrato:
                    referencias_emprestito.add(ref_contrato)
            
            # Obtener referencias desde ordenes_compra_emprestito
            ordenes_docs = db.collection('ordenes_compra_emprestito')\
                           .where('nombre_centro_gestor', '==', nombre_centro_gestor)\
                           .stream()
            
            for orden_doc in ordenes_docs:
                orden_data = orden_doc.to_dict()
                ref_contrato = orden_data.get('numero_orden')  # En órdenes es numero_orden
                if ref_contrato:
                    referencias_emprestito.add(ref_contrato)
            
            # Obtener referencias desde convenios_transferencias_emprestito
            convenios_docs = db.collection('convenios_transferencias_emprestito')\
                              .where('nombre_centro_gestor', '==', nombre_centro_gestor)\
                              .stream()
            
            for conv_doc in convenios_docs:
                conv_data = conv_doc.to_dict()
                ref_contrato = conv_data.get('referencia_contrato')
                if ref_contrato:
                    referencias_emprestito.add(ref_contrato)
            
            # Buscar reportes con estas referencias que no tengan nombre_centro_gestor establecido
            for referencia in referencias_emprestito:
                ref_docs = db.collection('reportes_contratos')\
                          .where('referencia_contrato', '==', referencia)\
                          .stream()
                
                for ref_doc in ref_docs:
                    ref_doc_data = ref_doc.to_dict()
                    # Solo agregar si no tiene nombre_centro_gestor o está vacío
                    if not ref_doc_data.get('nombre_centro_gestor', '').strip():
                        converted_data = convert_firebase_timestamps(ref_doc_data)
                        converted_data = _normalize_archivos_for_frontend(converted_data)
                        reporte_data = {
                            'id': ref_doc.id,
                            **converted_data,
                            'nombre_centro_gestor': nombre_centro_gestor,
                            'nombre_centro_gestor_source': 'emprestito_collections'
                        }
                        # Verificar que no esté duplicado
                        if not any(r['id'] == reporte_data['id'] for r in reportes):
                            reportes.append(reporte_data)
                            logger.info(f"✅ Agregado reporte desde colecciones de empréstito: {referencia}")
            
        except Exception as emprestito_error:
            logger.warning(f"Error buscando en colecciones de empréstito: {emprestito_error}")
        
        # Ordenar por fecha_reporte
        try:
            reportes.sort(key=lambda x: x.get('fecha_reporte', ''), reverse=True)
        except Exception as sort_error:
            logger.warning(f"Error ordenando reportes: {sort_error}")
        
        return {
            "success": True,
            "data": reportes,
            "count": len(reportes),
            "message": f"Reportes obtenidos para centro gestor: {nombre_centro_gestor} (incluyendo búsqueda en colecciones de empréstito)"
        }
        
    except Exception as e:
        logger.error(f"Error obteniendo reportes por centro gestor: {str(e)}")
        return {
            "success": False,
            "error": f"Error obteniendo reportes: {str(e)}",
            "data": []
        }

async def get_reportes_by_referencia_contrato(referencia_contrato: str) -> Dict[str, Any]:
    """
    Obtener reportes filtrados por referencia_contrato específica con nombre_centro_gestor 
    desde colecciones de empréstito (contratos, órdenes y convenios)
    """
    try:
        db = get_firestore_client()
        if db is None:
            return {
                "success": False,
                "error": "No se pudo conectar a Firestore",
                "data": []
            }
        
        # Buscar reportes por referencia_contrato
        query = db.collection('reportes_contratos').where('referencia_contrato', '==', referencia_contrato)
        try:
            docs = list(query.order_by('fecha_reporte', direction='DESCENDING').stream())
        except Exception as order_error:
            logger.warning(f"Fallback sin order_by en get_reportes_by_referencia_contrato: {order_error}")
            docs = list(query.stream())
        
        reportes = []
        for doc in docs:
            doc_data = doc.to_dict()
            # Convertir timestamps de Firebase a strings serializables
            converted_data = convert_firebase_timestamps(doc_data)
            converted_data = _normalize_archivos_for_frontend(converted_data)
            reporte_data = {
                'id': doc.id,
                **converted_data
            }
            
            # Obtener nombre_centro_gestor desde colecciones de empréstito si no existe o está vacío
            nombre_centro_gestor_actual = reporte_data.get('nombre_centro_gestor', '')
            
            if not nombre_centro_gestor_actual or nombre_centro_gestor_actual.strip() == '':
                nombre_centro_gestor_emprestito = await get_nombre_centro_gestor_from_emprestito(referencia_contrato)
                if nombre_centro_gestor_emprestito:
                    reporte_data['nombre_centro_gestor'] = nombre_centro_gestor_emprestito
                    reporte_data['nombre_centro_gestor_source'] = 'emprestito_collections'
                    logger.info(f"✅ Actualizado nombre_centro_gestor para {referencia_contrato}: {nombre_centro_gestor_emprestito}")
            
            reportes.append(reporte_data)
        
        return {
            "success": True,
            "data": reportes,
            "count": len(reportes),
            "message": f"Reportes obtenidos para contrato: {referencia_contrato} (con nombre_centro_gestor desde colecciones de empréstito cuando necesario)"
        }
        
    except Exception as e:
        logger.error(f"Error obteniendo reportes por referencia contrato: {str(e)}")
        return {
            "success": False,
            "error": f"Error obteniendo reportes: {str(e)}",
            "data": []
        }

def setup_google_drive_service():
    """
    Compatibilidad legacy: validación de disponibilidad de S3
    """
    try:
        return bool(BOTO3_AVAILABLE and S3DocumentManager is not None)
    except Exception:
        return False
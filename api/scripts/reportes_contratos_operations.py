"""
Operaciones para reportes de contratos con integración Google Drive
Versión de producción optimizada
"""

import os
import uuid
import logging
import json
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

# Google Drive imports con manejo de errores
try:
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaIoBaseUpload
    from google.oauth2 import service_account
    import io
    GOOGLE_API_AVAILABLE = True
except ImportError:
    GOOGLE_API_AVAILABLE = False

# Configurar logger
logger = logging.getLogger(__name__)

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
    """
    Crear carpeta y subir archivos al Google Drive Shared Drive (solo operaciones reales)
    """
    if not GOOGLE_API_AVAILABLE:
        raise Exception("Google Drive API no disponible - instalar dependencias")
    
    # Obtener credenciales
    credentials = get_drive_credentials()
    if not credentials:
        raise Exception("Service Account no configurado - verificar variables de entorno")
    
    # Obtener configuración
    shared_drive_id = os.getenv('GOOGLE_DRIVE_SHARED_DRIVE_ID')
    parent_folder_id = os.getenv('GOOGLE_DRIVE_PARENT_FOLDER_ID')  # Opcional
    
    if not shared_drive_id:
        raise Exception("GOOGLE_DRIVE_SHARED_DRIVE_ID no configurado")
    
    service = build('drive', 'v3', credentials=credentials)
    
    # Crear carpeta (usar parent_folder_id si existe, sino crear en raíz del Shared Drive)
    folder_id, folder_url = create_folder_in_drive(
        service, referencia_contrato, parent_folder_id, shared_drive_id
    )
    
    # Subir archivos
    archivos_info = upload_files_to_folder(service, archivos, folder_id)
    
    return folder_url, archivos_info

def get_drive_credentials():
    """Obtener credenciales de Google Drive (funcional)"""
    credentials_path = os.getenv('GOOGLE_DRIVE_SERVICE_ACCOUNT_PATH')
    credentials_json = os.getenv('GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON')
    scopes = ['https://www.googleapis.com/auth/drive']
    
    try:
        if credentials_path and os.path.exists(credentials_path):
            return service_account.Credentials.from_service_account_file(credentials_path, scopes=scopes)
        elif credentials_json:
            return service_account.Credentials.from_service_account_info(
                json.loads(credentials_json), scopes=scopes
            )
    except Exception as e:
        logger.error(f"❌ Error obteniendo credenciales: {e}")
        
    return None

def create_folder_in_drive(service, referencia_contrato: str, parent_folder_id: str = None, shared_drive_id: str = None) -> Tuple[str, str]:
    """Crear carpeta en Google Drive (funcional) - soporta Shared Drive"""
    timestamp = datetime.now().strftime('%d-%m-%Y')
    folder_name = f"{referencia_contrato}_{timestamp}"
    
    # Configurar metadatos de la carpeta
    folder_metadata = {
        'name': folder_name,
        'mimeType': 'application/vnd.google-apps.folder'
    }
    
    # Si hay parent_folder_id, usarlo; sino crear en raíz del Shared Drive usando el ID como parent
    if parent_folder_id:
        folder_metadata['parents'] = [parent_folder_id]
        logger.info(f"📁 Creando carpeta en parent: {parent_folder_id}")
    elif shared_drive_id:
        # Para crear en raíz del Shared Drive, usar el shared_drive_id como parent
        folder_metadata['parents'] = [shared_drive_id]
        logger.info(f"📁 Creando carpeta en Shared Drive: {shared_drive_id}")
    
    # Crear la carpeta
    folder = service.files().create(
        body=folder_metadata,
        fields='id,webViewLink',
        supportsAllDrives=True
    ).execute()
    
    folder_id = folder.get('id')
    folder_url = folder.get('webViewLink', f"https://drive.google.com/drive/folders/{folder_id}")
    
    logger.info(f"✅ Carpeta creada: {folder_name} -> {folder_id}")
    return folder_id, folder_url

def upload_files_to_folder(service, archivos: List[Dict[str, Any]], folder_id: str) -> List[Dict[str, str]]:
    """Subir archivos a carpeta de Google Drive (funcional)"""
    return [upload_single_file(service, archivo, folder_id) for archivo in archivos]

def upload_single_file(service, archivo: Dict[str, Any], folder_id: str) -> Dict[str, str]:
    """Subir un archivo individual (funcional)"""
    try:
        file_metadata = {
            'name': archivo["filename"],
            'parents': [folder_id]
        }
        
        file_content = archivo.get("content")
        if isinstance(file_content, str):
            file_content = file_content.encode('utf-8')
        
        media = MediaIoBaseUpload(
            io.BytesIO(file_content),
            mimetype=archivo["content_type"],
            resumable=False
        )
        
        uploaded_file = service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id,webViewLink,size',
            supportsAllDrives=True
        ).execute()
        
        file_id = uploaded_file.get('id')
        file_url = uploaded_file.get('webViewLink', f"https://drive.google.com/file/d/{file_id}/view")
        uploaded_size = uploaded_file.get('size', len(file_content))
        
        logger.info(f"📄✅ Archivo subido: {archivo['filename']} -> {file_id}")
        
        return {
            "name": archivo["filename"],
            "size": int(uploaded_size),
            "type": archivo["content_type"],
            "drive_id": file_id,
            "url": file_url,
            "download_url": f"https://drive.google.com/uc?id={file_id}",
            "status": "uploaded_successfully"
        }
        
    except Exception as e:
        logger.error(f"❌ Error subiendo {archivo['filename']}: {e}")
        return {
            "name": archivo["filename"],
            "size": archivo.get("size", 0),
            "type": archivo["content_type"],
            "drive_id": f"error_{uuid.uuid4()}",
            "url": "#error",
            "download_url": "#error",
            "status": "upload_failed",
            "error": str(e)
        }



def validate_uploaded_files(archivos_evidencia: List[Dict[str, Any]]) -> Tuple[bool, str]:
    """
    Validar archivos subidos
    """
    if not archivos_evidencia:
        return False, "Se requiere al menos un archivo de evidencia"
    
    allowed_types = [
        'application/pdf',
        'text/plain',
        'text/csv',
        'image/jpeg',
        'image/png',
        'image/gif',
        'application/msword',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'application/vnd.ms-excel',
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    ]
    
    for archivo in archivos_evidencia:
        if archivo.get('content_type') not in allowed_types:
            return False, f"Tipo de archivo no permitido: {archivo.get('content_type')}"
        
        if archivo.get('size', 0) > 10 * 1024 * 1024:  # 10MB
            return False, f"Archivo demasiado grande: {archivo.get('filename')}"
    
    return True, "Archivos válidos"

async def create_reporte_contrato(reporte_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Crear reporte de contrato con integración Google Drive (solo operaciones reales)
    """
    try:
        db = get_firestore_client()
        if db is None:
            raise Exception("No se pudo conectar a Firestore")
        
        # Validar archivos
        is_valid, validation_message = validate_uploaded_files(reporte_data.get('archivos_evidencia', []))
        if not is_valid:
            raise Exception(validation_message)
        
        # Crear carpeta en Google Drive (operación real)
        url_carpeta_drive, archivos_subidos = create_drive_folder(
            reporte_data['referencia_contrato'], 
            reporte_data['archivos_evidencia']
        )
        
        # Verificar que los archivos se subieron correctamente
        failed_uploads = [a for a in archivos_subidos if a.get('status') == 'upload_failed']
        if failed_uploads:
            raise Exception(f"Error subiendo archivos: {[f['name'] for f in failed_uploads]}")
        
        # Datos para Firebase
        doc_data = {
            'referencia_contrato': reporte_data['referencia_contrato'],
            'nombre_centro_gestor': reporte_data.get('nombre_centro_gestor', ''),
            'observaciones': reporte_data['observaciones'],
            'avance_fisico': reporte_data['avance_fisico'],
            'avance_financiero': reporte_data['avance_financiero'],
            'alertas': reporte_data['alertas'],
            'archivos_evidencia': archivos_subidos,
            'url_carpeta_drive': url_carpeta_drive,
            'fecha_reporte': datetime.now(),
            'estado_reporte': 'activo'
        }
        
        # Guardar en Firebase
        doc_ref = db.collection('reportes_contratos').add(doc_data)
        doc_id = doc_ref[1].id
        
        logger.info(f"✅ Reporte creado: {doc_id}")
        
        return {
            "success": True,
            "message": "Reporte creado exitosamente con archivos en Google Drive",
            "doc_id": doc_id,
            "url_carpeta_drive": url_carpeta_drive
        }
        
    except Exception as e:
        logger.error(f"❌ Error creando reporte: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "doc_id": None
        }

async def get_reportes_contratos(filtros: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Obtener lista de reportes de contratos
    """
    try:
        db = get_firestore_client()
        if db is None:
            return {
                "success": False,
                "error": "No se pudo conectar a Firestore",
                "data": []
            }
        
        collection_ref = db.collection('reportes_contratos')
        
        # Aplicar filtros si existen
        if filtros:
            if 'referencia_contrato' in filtros:
                collection_ref = collection_ref.where('referencia_contrato', '==', filtros['referencia_contrato'])
            if 'estado_reporte' in filtros:
                collection_ref = collection_ref.where('estado_reporte', '==', filtros['estado_reporte'])
        
        # Ordenar por fecha
        docs = collection_ref.order_by('fecha_reporte', direction='DESCENDING').stream()
        
        reportes = []
        for doc in docs:
            doc_data = doc.to_dict()
            # Convertir timestamps de Firebase a strings serializables
            converted_data = convert_firebase_timestamps(doc_data)
            reporte_data = {
                'id': doc.id,
                **converted_data
            }
            reportes.append(reporte_data)
        
        return {
            "success": True,
            "data": reportes,
            "count": len(reportes)
        }
        
    except Exception as e:
        logger.error(f"Error obteniendo reportes: {str(e)}")
        return {
            "success": False,
            "error": f"Error obteniendo reportes: {str(e)}",
            "data": []
        }

async def get_reporte_contrato_by_id(reporte_id: str) -> Dict[str, Any]:
    """
    Obtener un reporte específico por ID
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
        reporte_data = {
            'id': doc.id,
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
    """
    try:
        db = get_firestore_client()
        if db is None:
            return {
                "success": False,
                "error": "No se pudo conectar a Firestore",
                "data": []
            }
        
        # Buscar reportes por nombre_centro_gestor
        docs = db.collection('reportes_contratos')\
                .where('nombre_centro_gestor', '==', nombre_centro_gestor)\
                .order_by('fecha_reporte', direction='DESCENDING')\
                .stream()
        
        reportes = []
        for doc in docs:
            doc_data = doc.to_dict()
            # Convertir timestamps de Firebase a strings serializables
            converted_data = convert_firebase_timestamps(doc_data)
            reporte_data = {
                'id': doc.id,
                **converted_data
            }
            reportes.append(reporte_data)
        
        return {
            "success": True,
            "data": reportes,
            "count": len(reportes),
            "message": f"Reportes obtenidos para centro gestor: {nombre_centro_gestor}"
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
    Obtener reportes filtrados por referencia_contrato específica
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
        docs = db.collection('reportes_contratos')\
                .where('referencia_contrato', '==', referencia_contrato)\
                .order_by('fecha_reporte', direction='DESCENDING')\
                .stream()
        
        reportes = []
        for doc in docs:
            doc_data = doc.to_dict()
            # Convertir timestamps de Firebase a strings serializables
            converted_data = convert_firebase_timestamps(doc_data)
            reporte_data = {
                'id': doc.id,
                **converted_data
            }
            reportes.append(reporte_data)
        
        return {
            "success": True,
            "data": reportes,
            "count": len(reportes),
            "message": f"Reportes obtenidos para contrato: {referencia_contrato}"
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
    Configurar servicio de Google Drive
    """
    try:
        credentials_path = os.getenv('GOOGLE_DRIVE_SERVICE_ACCOUNT_PATH')
        credentials_json = os.getenv('GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON')
        return (credentials_path and os.path.exists(credentials_path)) or (credentials_json and GOOGLE_API_AVAILABLE)
    except Exception:
        return False
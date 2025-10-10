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

def create_drive_folder(referencia_contrato: str, archivos: List[Dict[str, Any]]) -> Tuple[str, List[Dict[str, str]]]:
    """
    Crear carpeta en Google Drive usando Shared Drive (solución para Service Account)
    """
    if not GOOGLE_API_AVAILABLE:
        logger.warning("🚨 Google Drive API no disponible - usando simulación")
        return create_simulated_folder(referencia_contrato, archivos)
    
    try:
        # Verificar Service Account (compatible con Railway)
        credentials_path = os.getenv('GOOGLE_DRIVE_SERVICE_ACCOUNT_PATH')
        credentials_json = os.getenv('GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON')
        parent_folder_id = os.getenv('GOOGLE_DRIVE_PARENT_FOLDER_ID')
        
        credentials = None
        
        # Método 1: Archivo JSON (desarrollo local)
        if credentials_path and os.path.exists(credentials_path):
            credentials = service_account.Credentials.from_service_account_file(
                credentials_path,
                scopes=[
                    'https://www.googleapis.com/auth/drive',
                    'https://www.googleapis.com/auth/drive.file'
                ]
            )
            logger.info("🔐 Usando Service Account desde archivo")
            
        # Método 2: JSON como string (Railway/producción)
        elif credentials_json:
            service_account_info = json.loads(credentials_json)
            credentials = service_account.Credentials.from_service_account_info(
                service_account_info,
                scopes=[
                    'https://www.googleapis.com/auth/drive',
                    'https://www.googleapis.com/auth/drive.file'
                ]
            )
            logger.info("🔐 Usando Service Account desde variable de entorno")
        
        else:
            logger.warning("⚠️ Service Account no configurado - usando simulación")
            return create_simulated_folder(referencia_contrato, archivos)
        
        service = build('drive', 'v3', credentials=credentials)
        
        # Configurar carpeta padre y Shared Drive
        parent_folder_id = os.getenv('GOOGLE_DRIVE_PARENT_FOLDER_ID')
        shared_drive_id = os.getenv('GOOGLE_DRIVE_SHARED_DRIVE_ID')
        
        # Verificar acceso a carpeta padre en Shared Drive
        if parent_folder_id and shared_drive_id:
            try:
                parent_folder = service.files().get(
                    fileId=parent_folder_id, 
                    fields='id,name,driveId',
                    supportsAllDrives=True
                ).execute()
                logger.info(f"📁 Carpeta padre en Shared Drive: {parent_folder.get('name')}")
                logger.info(f"🔗 Shared Drive ID: {shared_drive_id}")
            except Exception as e:
                logger.error(f"❌ Error accediendo carpeta padre en Shared Drive: {e}")
                logger.error("🔧 Configuración incorrecta de Shared Drive")
                return create_simulated_folder(referencia_contrato, archivos)
        else:
            logger.error("❌ GOOGLE_DRIVE_PARENT_FOLDER_ID o GOOGLE_DRIVE_SHARED_DRIVE_ID no configurados")
            logger.error("💡 Ejecuta 'python auto_configure_shared_drive.py' para configurar")
            return create_simulated_folder(referencia_contrato, archivos)
        
        # Crear carpeta real con formato dd-mm-aaaa
        timestamp = datetime.now().strftime('%d-%m-%Y')
        folder_name = f"{referencia_contrato}_{timestamp}"
        folder_metadata = {
            'name': folder_name,
            'mimeType': 'application/vnd.google-apps.folder',
            'parents': [parent_folder_id] if parent_folder_id else []
        }
        
        # Crear carpeta en Shared Drive
        folder = service.files().create(
            body=folder_metadata, 
            fields='id,name,webViewLink',
            supportsAllDrives=True
        ).execute()
        folder_id = folder.get('id')
        folder_url = folder.get('webViewLink', f"https://drive.google.com/drive/folders/{folder_id}")
        
        # Configurar permisos para hacer la carpeta accesible (opcional en Shared Drive)
        try:
            permission = {
                'role': 'reader',
                'type': 'anyone'
            }
            service.permissions().create(
                fileId=folder_id, 
                body=permission,
                supportsAllDrives=True
            ).execute()
            logger.info(f"✅ Permisos públicos configurados para carpeta: {folder_id}")
        except Exception as e:
            logger.warning(f"⚠️ No se pudieron configurar permisos públicos (normal en Shared Drive): {e}")
        
        logger.info(f"✅ Carpeta REAL creada y accesible: {folder_url}")
        
        # Subir archivos reales con contenido
        archivos_info = []
        for archivo in archivos:
            try:
                # Metadatos del archivo
                file_metadata = {
                    'name': archivo["filename"],
                    'parents': [folder_id]
                }
                
                # Crear media upload con el contenido real del archivo
                # Crear un objeto de bytes desde el contenido del archivo
                file_content = io.BytesIO(archivo["content"])
                media = MediaIoBaseUpload(
                    file_content,
                    mimetype=archivo["content_type"],
                    resumable=True
                )
                
                # Subir archivo real con contenido a Shared Drive
                uploaded_file = service.files().create(
                    body=file_metadata,
                    media_body=media,
                    fields='id,webViewLink,size',
                    supportsAllDrives=True
                ).execute()
                
                file_id = uploaded_file.get('id')
                # Generar tanto URL de vista como de descarga directa
                file_url = uploaded_file.get('webViewLink', f"https://drive.google.com/file/d/{file_id}/view")
                download_url = f"https://drive.google.com/uc?id={file_id}&export=download"
                uploaded_size = uploaded_file.get('size', archivo["size"])
                
                # Configurar permisos para el archivo
                try:
                    permission = {
                        'role': 'reader',
                        'type': 'anyone'
                    }
                    service.permissions().create(
                        fileId=file_id, 
                        body=permission,
                        supportsAllDrives=True
                    ).execute()
                    logger.info(f"✅ Permisos públicos configurados para archivo: {file_id}")
                except Exception as perm_error:
                    logger.warning(f"⚠️ No se pudieron configurar permisos públicos (normal en Shared Drive): {perm_error}")
                
                archivos_info.append({
                    "name": archivo["filename"],
                    "size": uploaded_size,
                    "type": archivo["content_type"],
                    "drive_id": file_id,
                    "url": file_url,
                    "download_url": download_url,
                    "status": "uploaded_successfully"
                })
                
                logger.info(f"📄✅ Archivo REAL subido: {archivo['filename']} -> {file_id} ({uploaded_size} bytes)")
                
            except Exception as file_error:
                logger.error(f"❌ Error subiendo archivo {archivo['filename']}: {file_error}")
                archivos_info.append({
                    "name": archivo["filename"],
                    "size": archivo["size"],
                    "type": archivo["content_type"],
                    "drive_id": f"error_{uuid.uuid4()}",
                    "url": "#error",
                    "download_url": "#error",
                    "status": "upload_failed"
                })
        
        return folder_url, archivos_info
            
    except Exception as e:
        logger.error(f"❌ Error creando carpeta real: {e}")
        return create_simulated_folder(referencia_contrato, archivos)

def create_simulated_folder(referencia_contrato: str, archivos: List[Dict[str, Any]]) -> Tuple[str, List[Dict[str, str]]]:
    """
    Crear carpeta simulada cuando Google Drive no está disponible
    """
    folder_id = '1' + ''.join([str(uuid.uuid4()).replace('-', '') for _ in range(1)])[:32]
    logger.warning("🚨 Google Drive en modo simulación")
    
    archivos_simulados = []
    for archivo in archivos:
        file_id = '1' + ''.join([str(uuid.uuid4()).replace('-', '') for _ in range(1)])[:32]
        archivos_simulados.append({
            "name": archivo["filename"],
            "size": archivo["size"],
            "type": archivo["content_type"],
            "drive_id": file_id,
            "url": f"https://drive.google.com/file/d/{file_id}/view",
            "download_url": f"https://drive.google.com/uc?id={file_id}&export=download",
            "status": "simulated"
        })
    
    folder_url = f"https://drive.google.com/drive/folders/{folder_id}"
    logger.info(f"📁 Carpeta simulada: {folder_url}")
    
    return folder_url, archivos_simulados

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
    Crear reporte de contrato con integración Google Drive
    """
    try:
        db = get_firestore_client()
        if db is None:
            return {
                "success": False,
                "error": "No se pudo conectar a Firestore",
                "doc_id": None
            }
        
        # Validar archivos
        is_valid, validation_message = validate_uploaded_files(reporte_data.get('archivos_evidencia', []))
        if not is_valid:
            return {"success": False, "error": validation_message, "doc_id": None}
        
        # Crear carpeta en Google Drive
        url_carpeta_drive, archivos_subidos = create_drive_folder(
            reporte_data['referencia_contrato'], 
            reporte_data['archivos_evidencia']
        )
        
        # Datos para Firebase
        doc_data = {
            'referencia_contrato': reporte_data['referencia_contrato'],
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
        
        logger.info(f"Reporte creado: {doc_id}")
        
        return {
            "success": True,
            "message": "Reporte creado exitosamente",
            "doc_id": doc_id,
            "url_carpeta_drive": url_carpeta_drive
        }
        
    except Exception as e:
        logger.error(f"Error creando reporte de contrato: {str(e)}")
        return {
            "success": False,
            "error": f"Error interno: {str(e)}",
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
            reporte_data = {
                'id': doc.id,
                **doc.to_dict()
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
        
        reporte_data = {
            'id': doc.id,
            **doc.to_dict()
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
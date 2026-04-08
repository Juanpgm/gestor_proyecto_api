"""
Módulo para control y auditoría de cambios en valores de empréstito
Registra todos los cambios realizados en campos de valores con documentos soporte
"""

import os
import logging
import uuid
from datetime import datetime
from typing import Dict, Any, Optional, List
from fastapi import UploadFile

# Configurar logger
logger = logging.getLogger(__name__)

# Importar Firebase y S3
try:
    from database.firebase_config import get_firestore_client, FIRESTORE_AVAILABLE
except ImportError:
    try:
        from ..database.firebase_config import get_firestore_client, FIRESTORE_AVAILABLE
    except ImportError:
        FIRESTORE_AVAILABLE = False
        logger.warning("Firebase no disponible para control de cambios")

try:
    from api.utils.s3_document_manager import S3DocumentManager, BOTO3_AVAILABLE
except ImportError:
    BOTO3_AVAILABLE = False
    logger.warning("S3 no disponible para control de cambios")


async def registrar_cambio_valor(
    tipo_coleccion: str,
    identificador: str,
    campo_modificado: str,
    valor_anterior: Any,
    valor_nuevo: Any,
    motivo: str,
    archivo_soporte: Optional[UploadFile] = None,
    usuario: Optional[str] = None,
    endpoint_usado: Optional[str] = None
) -> Dict[str, Any]:
    """
    Registra un cambio de valor en la colección de control de cambios
    
    Args:
        tipo_coleccion: Tipo de colección modificada (procesos, ordenes, convenios, contratos)
        identificador: Identificador del documento (referencia_proceso, numero_orden, referencia_contrato)
        campo_modificado: Campo que fue modificado (valor_publicacion, valor_orden, valor_contrato)
        valor_anterior: Valor antes del cambio
        valor_nuevo: Valor después del cambio
        motivo: Justificación del cambio
        archivo_soporte: Archivo PDF, XLSX, DOCX, etc. como documento soporte (opcional)
        usuario: Usuario que realizó el cambio (opcional)
        endpoint_usado: Endpoint que se utilizó (opcional)
    
    Returns:
        Dict con información del registro creado
    """
    try:
        # Validar que Firebase esté disponible
        if not FIRESTORE_AVAILABLE:
            logger.error("Firebase no está disponible para registrar cambio")
            return {
                "success": False,
                "error": "Firebase no disponible",
                "message": "No se puede registrar el cambio sin Firebase"
            }
        
        # Generar ID único para el cambio
        change_id = str(uuid.uuid4())
        change_timestamp = datetime.now()
        
        # Preparar datos del cambio
        cambio_data = {
            "change_id": change_id,
            "change_timestamp": change_timestamp,
            "change_motivo": motivo,
            "tipo_coleccion": tipo_coleccion,
            "identificador": identificador,
            "campo_modificado": campo_modificado,
            "valor_anterior": valor_anterior,
            "valor_nuevo": valor_nuevo,
            "diferencia": float(valor_nuevo) - float(valor_anterior) if isinstance(valor_anterior, (int, float)) and isinstance(valor_nuevo, (int, float)) else None,
            "usuario": usuario or "Sistema",
            "endpoint_usado": endpoint_usado
        }
        
        # Subir archivo soporte a S3 si se proporciona
        if archivo_soporte and BOTO3_AVAILABLE:
            try:
                s3_result = await _subir_archivo_soporte_s3(
                    archivo=archivo_soporte,
                    tipo_coleccion=tipo_coleccion,
                    identificador=identificador,
                    change_id=change_id
                )
                
                if s3_result.get("success"):
                    cambio_data["change_support_file"] = s3_result.get("url")
                    cambio_data["support_file_name"] = s3_result.get("filename")
                    cambio_data["support_file_size"] = s3_result.get("file_size")
                    cambio_data["support_file_type"] = s3_result.get("file_type")
                    logger.info(f"✅ Archivo soporte subido a S3: {s3_result.get('s3_key')}")
                else:
                    logger.warning(f"⚠️ No se pudo subir archivo soporte: {s3_result.get('error')}")
                    cambio_data["change_support_file"] = None
                    cambio_data["support_file_error"] = s3_result.get("error")
                    
            except Exception as e:
                logger.error(f"Error subiendo archivo soporte: {e}")
                cambio_data["change_support_file"] = None
                cambio_data["support_file_error"] = str(e)
        else:
            cambio_data["change_support_file"] = None
            if archivo_soporte and not BOTO3_AVAILABLE:
                cambio_data["support_file_error"] = "S3 no disponible"
        
        # Guardar en Firebase
        db = get_firestore_client()
        collection_ref = db.collection("emprestito_control_cambios")
        doc_ref = collection_ref.document(change_id)
        doc_ref.set(cambio_data)
        
        logger.info(f"✅ Cambio registrado en control_cambios: {change_id}")
        
        return {
            "success": True,
            "message": "Cambio registrado exitosamente en auditoría",
            "change_id": change_id,
            "change_timestamp": change_timestamp.isoformat(),
            "cambio_registrado": cambio_data
        }
        
    except Exception as e:
        logger.error(f"Error registrando cambio en control_cambios: {e}")
        return {
            "success": False,
            "error": str(e),
            "message": "Error registrando cambio en auditoría"
        }


async def _subir_archivo_soporte_s3(
    archivo: UploadFile,
    tipo_coleccion: str,
    identificador: str,
    change_id: str
) -> Dict[str, Any]:
    """
    Sube archivo de soporte a S3 con estructura organizada
    
    Estructura en S3:
    control-cambios-emprestito/
    ├── {referencia_proceso}/{change_id}_{filename}
    ├── {numero_orden}/{change_id}_{filename}
    └── {referencia_contrato}/{change_id}_{filename}
    
    Args:
        archivo: Archivo subido por el usuario
        tipo_coleccion: Tipo de colección (procesos, ordenes, convenios, contratos)
        identificador: Identificador del documento (referencia_proceso, numero_orden, referencia_contrato)
        change_id: ID único del cambio
    
    Returns:
        Dict con información del archivo subido
    """
    try:
        if not BOTO3_AVAILABLE:
            return {
                "success": False,
                "error": "S3 no disponible",
                "message": "boto3 no está instalado"
            }
        
        # Validar tipo de archivo
        allowed_extensions = ['.pdf', '.xlsx', '.xls', '.docx', '.doc', '.png', '.jpg', '.jpeg']
        file_extension = os.path.splitext(archivo.filename)[1].lower()
        
        if file_extension not in allowed_extensions:
            return {
                "success": False,
                "error": f"Tipo de archivo no permitido: {file_extension}",
                "message": f"Solo se permiten archivos: {', '.join(allowed_extensions)}"
            }
        
        # Leer contenido del archivo
        file_content = await archivo.read()
        file_size = len(file_content)
        
        # Validar tamaño (máximo 10 MB)
        max_size = 10 * 1024 * 1024  # 10 MB
        if file_size > max_size:
            return {
                "success": False,
                "error": f"Archivo muy grande: {file_size / 1024 / 1024:.2f} MB",
                "message": "El archivo no debe superar 10 MB"
            }
        
        # Sanitizar nombre de archivo
        safe_filename = "".join(c for c in archivo.filename if c.isalnum() or c in (' ', '.', '_', '-')).strip()
        safe_identificador = "".join(c for c in identificador if c.isalnum() or c in ('-', '_')).strip()
        
        # Construir clave S3 usando el identificador como carpeta
        s3_key = f"{safe_identificador}/{change_id}_{safe_filename}"
        
        # Nombre del bucket específico para control de cambios
        bucket_name = "control-cambios-emprestito"
        
        # Inicializar S3 manager
        s3_manager = S3DocumentManager()
        
        # Subir archivo al bucket de control de cambios
        s3_manager.s3_client.put_object(
            Bucket=bucket_name,
            Key=s3_key,
            Body=file_content,
            ContentType=archivo.content_type or 'application/octet-stream',
            Metadata={
                'change_id': change_id,
                'tipo_coleccion': tipo_coleccion,
                'identificador': identificador,
                'uploaded_at': datetime.now().isoformat()
            }
        )
        
        # Construir URL del archivo
        url = f"https://{bucket_name}.s3.{s3_manager.region}.amazonaws.com/{s3_key}"
        
        logger.info(f"✅ Archivo subido a S3: {bucket_name}/{s3_key}")
        
        return {
            "success": True,
            "url": url,
            "s3_key": s3_key,
            "filename": safe_filename,
            "file_size": file_size,
            "file_type": file_extension,
            "bucket": s3_manager.bucket_name
        }
        
    except Exception as e:
        logger.error(f"Error subiendo archivo a S3: {e}")
        return {
            "success": False,
            "error": str(e),
            "message": "Error subiendo archivo a S3"
        }


async def obtener_historial_cambios(
    tipo_coleccion: Optional[str] = None,
    identificador: Optional[str] = None,
    limite: int = 50
) -> Dict[str, Any]:
    """
    Obtiene el historial de cambios de la colección de auditoría
    
    Args:
        tipo_coleccion: Filtrar por tipo de colección (opcional)
        identificador: Filtrar por identificador específico (opcional)
        limite: Número máximo de registros a retornar
    
    Returns:
        Dict con lista de cambios registrados
    """
    try:
        if not FIRESTORE_AVAILABLE:
            return {
                "success": False,
                "error": "Firebase no disponible"
            }
        
        db = get_firestore_client()
        query = db.collection("emprestito_control_cambios")
        
        # Aplicar filtros
        if tipo_coleccion:
            query = query.where("tipo_coleccion", "==", tipo_coleccion)
        
        if identificador:
            query = query.where("identificador", "==", identificador)
        
        # Ordenar por timestamp descendente y limitar
        query = query.order_by("change_timestamp", direction="DESCENDING").limit(limite)
        
        # Ejecutar query
        docs = query.stream()
        
        cambios = []
        for doc in docs:
            cambio_data = doc.to_dict()
            cambio_data["document_id"] = doc.id
            cambios.append(cambio_data)
        
        return {
            "success": True,
            "total_cambios": len(cambios),
            "cambios": cambios
        }
        
    except Exception as e:
        logger.error(f"Error obteniendo historial de cambios: {e}")
        return {
            "success": False,
            "error": str(e),
            "message": "Error obteniendo historial de cambios"
        }

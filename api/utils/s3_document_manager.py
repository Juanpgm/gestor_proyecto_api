"""
Módulo para gestión de documentos en AWS S3 para contratos de empréstito
Basado en los patrones existentes de la aplicación
"""

import os
import json
import logging
import io
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path

# Configurar logger
logger = logging.getLogger(__name__)

# Intentar importar boto3
try:
    import boto3
    from botocore.exceptions import ClientError, NoCredentialsError
    BOTO3_AVAILABLE = True
except ImportError:
    BOTO3_AVAILABLE = False
    logger.warning("boto3 no está instalado. Funcionalidad S3 no disponible.")


class S3DocumentManager:
    """
    Gestor de documentos S3 para contratos de empréstito
    
    Estructura en S3:
    contratos-emprestito/
    ├── contratos-rpc-docs/
    │   ├── {numero_rpc}/
    │   │   └── {timestamp}_{filename}
    └── contratos-pagos-docs/
        ├── {numero_rpc}/
        │   └── {timestamp}_{filename}
    """
    
    def __init__(self, credentials_path: str = None):
        """
        Inicializar el gestor de documentos S3
        
        Args:
            credentials_path: Ruta al archivo de credenciales AWS (opcional)
                             Si no se proporciona, busca en múltiples ubicaciones
        """
        if not BOTO3_AVAILABLE:
            raise ImportError("boto3 no está instalado. Instalar con: pip install boto3")
        
        self.credentials = self._load_credentials(credentials_path)
        self.bucket_name = self.credentials.get('bucket_name_emprestito', 'contratos-emprestito')
        self.region = self.credentials.get('aws_region', self.credentials.get('region', 'us-east-1'))
        
        # Inicializar cliente S3
        self.s3_client = boto3.client(
            's3',
            aws_access_key_id=self.credentials.get('aws_access_key_id'),
            aws_secret_access_key=self.credentials.get('aws_secret_access_key'),
            region_name=self.region
        )
        
        logger.info(f"✅ S3DocumentManager inicializado - Bucket: {self.bucket_name}")
    
    def _load_credentials(self, credentials_path: str = None) -> Dict[str, str]:
        """
        Cargar credenciales desde archivo JSON o variables de entorno
        
        Busca credenciales en el siguiente orden:
        1. Archivo especificado en credentials_path
        2. credentials/aws_credentials.json (ubicación actual)
        3. context/aws_credentials.json (ubicación legacy)
        4. Variables de entorno (producción)
        """
        try:
            # Si se especificó una ruta, intentar cargarla
            if credentials_path and os.path.exists(credentials_path):
                with open(credentials_path, 'r') as f:
                    creds = json.load(f)
                    logger.info(f"✅ Credenciales cargadas desde: {credentials_path}")
                    return creds
            
            # Buscar en ubicaciones conocidas
            possible_paths = [
                "credentials/aws_credentials.json",  # Ubicación actual
                "context/aws_credentials.json",       # Legacy
            ]
            
            for path in possible_paths:
                if os.path.exists(path):
                    with open(path, 'r') as f:
                        creds = json.load(f)
                        logger.info(f"✅ Credenciales cargadas desde: {path}")
                        return creds
            
            # Si no se encuentra archivo, usar variables de entorno (producción)
            logger.warning("Archivo de credenciales no encontrado, usando variables de entorno")
            env_creds = {
                'aws_access_key_id': os.getenv('AWS_ACCESS_KEY_ID', ''),
                'aws_secret_access_key': os.getenv('AWS_SECRET_ACCESS_KEY', ''),
                'aws_region': os.getenv('AWS_REGION', 'us-east-1'),
                'region': os.getenv('AWS_REGION', 'us-east-1'),
                'bucket_name_emprestito': os.getenv('S3_BUCKET_EMPRESTITO', 'contratos-emprestito'),
                'bucket_name': os.getenv('S3_BUCKET_NAME', 'unidades-proyecto-documents')
            }
            
            # Verificar que las credenciales están presentes
            if not env_creds['aws_access_key_id'] or not env_creds['aws_secret_access_key']:
                raise ValueError(
                    "No se encontraron credenciales AWS. "
                    "Proporciona un archivo JSON o configura las variables de entorno: "
                    "AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_REGION, S3_BUCKET_EMPRESTITO"
                )
            
            logger.info("✅ Credenciales cargadas desde variables de entorno")
            return env_creds
            
        except Exception as e:
            logger.error(f"Error cargando credenciales: {e}")
            raise
    
    def _generate_s3_key(self, folder: str, referencia_contrato: str, filename: str, numero_rpc: str = None, use_timestamp: bool = False) -> str:
        """
        Generar clave S3 con estructura organizada
        
        RPC: contratos-rpc-docs/{referencia_contrato}/{filename}
        PAGO: contratos-pagos-docs/{referencia_contrato}/{numero_rpc}/{filename}
        
        Args:
            folder: Carpeta base (contratos-rpc-docs o contratos-pagos-docs)
            referencia_contrato: Referencia del contrato (carpeta principal)
            filename: Nombre del archivo original
            numero_rpc: Número de RPC (requerido para pagos - nivel adicional)
            use_timestamp: Si es True, agrega timestamp al nombre (para evitar colisiones durante testing)
        
        Returns:
            Clave S3 completa
        """
        # Sanitizar nombre de archivo
        safe_filename = "".join(c for c in filename if c.isalnum() or c in (' ', '.', '_', '-')).strip()
        safe_referencia = "".join(c for c in referencia_contrato if c.isalnum() or c in ('-', '_')).strip()
        
        # Si use_timestamp es True, agregar timestamp (útil para tests)
        if use_timestamp:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            final_filename = f"{timestamp}_{safe_filename}"
        else:
            final_filename = safe_filename
        
        # Estructura según tipo (2 niveles para RPC, 3 para PAGO)
        if folder == 'contratos-pagos-docs' and numero_rpc:
            # PAGO: 3 niveles - referencia_contrato/numero_rpc/filename
            safe_rpc = "".join(c for c in numero_rpc if c.isalnum() or c in ('-', '_')).strip()
            return f"{folder}/{safe_referencia}/{safe_rpc}/{final_filename}"
        else:
            # RPC: 2 niveles - referencia_contrato/filename
            return f"{folder}/{safe_referencia}/{final_filename}"
    
    def upload_document(
        self,
        file_content: bytes,
        filename: str,
        referencia_contrato: str,
        document_type: str,
        numero_rpc: str = None,
        content_type: str = 'application/pdf',
        metadata: Optional[Dict[str, str]] = None,
        use_timestamp: bool = False
    ) -> Dict[str, Any]:
        """
        Subir un documento a S3
        
        RPC: contratos-rpc-docs/{referencia_contrato}/{filename}
        PAGO: contratos-pagos-docs/{referencia_contrato}/{numero_rpc}/{filename}
        
        Args:
            file_content: Contenido del archivo en bytes
            filename: Nombre del archivo original
            referencia_contrato: Referencia del contrato (carpeta principal)
            document_type: Tipo de documento ('rpc' o 'pago')
            numero_rpc: Número de RPC (REQUERIDO para pagos)
            content_type: Tipo MIME del archivo
            metadata: Metadatos adicionales para el archivo
            use_timestamp: Si es True, agrega timestamp al nombre del archivo
        
        Returns:
            Diccionario con información del archivo subido
        """
        try:
            # Determinar carpeta según tipo de documento
            folder = 'contratos-rpc-docs' if document_type == 'rpc' else 'contratos-pagos-docs'
            
            # Validar que numero_rpc esté presente para pagos
            if document_type == 'pago' and not numero_rpc:
                raise ValueError("numero_rpc es requerido para documentos de tipo 'pago'")
            
            # Generar clave S3
            s3_key = self._generate_s3_key(folder, referencia_contrato, filename, numero_rpc, use_timestamp)
            
            # Preparar metadatos (S3 solo acepta ASCII en metadata)
            def encode_metadata_value(value: str) -> str:
                """Codificar valores a ASCII seguro"""
                try:
                    # Intentar mantener ASCII válido
                    return value.encode('ascii', errors='ignore').decode('ascii')
                except:
                    return value
            
            s3_metadata = {
                'referencia_contrato': encode_metadata_value(referencia_contrato),
                'document_type': document_type,
                'original_filename': encode_metadata_value(filename),
                'upload_date': datetime.now().isoformat()
            }
            
            if metadata:
                # Codificar todos los valores del metadata adicional
                encoded_metadata = {
                    key: encode_metadata_value(str(value)) if value else ''
                    for key, value in metadata.items()
                }
                s3_metadata.update(encoded_metadata)
            
            # Subir archivo a S3
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=s3_key,
                Body=file_content,
                ContentType=content_type,
                Metadata=s3_metadata
            )
            
            # Generar URL del archivo
            file_url = f"https://{self.bucket_name}.s3.{self.region}.amazonaws.com/{s3_key}"
            
            logger.info(f"✅ Documento subido a S3: {s3_key}")
            
            return {
                'success': True,
                'filename': filename,
                's3_key': s3_key,
                's3_url': file_url,
                'bucket': self.bucket_name,
                'size': len(file_content),
                'content_type': content_type,
                'upload_date': datetime.now().isoformat()
            }
            
        except NoCredentialsError:
            logger.error("❌ Credenciales AWS no configuradas")
            return {
                'success': False,
                'error': 'Credenciales AWS no configuradas',
                'filename': filename
            }
        except ClientError as e:
            logger.error(f"❌ Error de cliente S3: {e}")
            return {
                'success': False,
                'error': str(e),
                'filename': filename
            }
        except Exception as e:
            logger.error(f"❌ Error subiendo documento: {e}")
            return {
                'success': False,
                'error': str(e),
                'filename': filename
            }
    
    def upload_multiple_documents(
        self,
        files: List[Dict[str, Any]],
        referencia_contrato: str,
        document_type: str,
        numero_rpc: str = None,
        use_timestamp: bool = False
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Subir múltiples documentos a S3
        
        Args:
            files: Lista de diccionarios con información de archivos
                   Cada dict debe tener: 'content' (bytes), 'filename', 'content_type'
            referencia_contrato: Referencia del contrato (carpeta principal)
            document_type: Tipo de documento ('rpc' o 'pago')
            numero_rpc: Número de RPC (REQUERIDO para pagos)
            use_timestamp: Si es True, agrega timestamp a los nombres de archivo
        
        Returns:
            Tupla con (archivos_exitosos, archivos_fallidos)
        """
        successful_uploads = []
        failed_uploads = []
        
        for file_info in files:
            try:
                result = self.upload_document(
                    file_content=file_info['content'],
                    filename=file_info['filename'],
                    referencia_contrato=referencia_contrato,
                    document_type=document_type,
                    numero_rpc=numero_rpc,
                    content_type=file_info.get('content_type', 'application/pdf'),
                    metadata={
                        'numero_rpc': file_info.get('numero_rpc', numero_rpc or ''),
                        'centro_gestor': file_info.get('centro_gestor', '')
                    },
                    use_timestamp=use_timestamp
                )
                
                if result['success']:
                    successful_uploads.append(result)
                else:
                    failed_uploads.append(result)
                    
            except Exception as e:
                logger.error(f"❌ Error procesando archivo {file_info.get('filename', 'unknown')}: {e}")
                failed_uploads.append({
                    'success': False,
                    'filename': file_info.get('filename', 'unknown'),
                    'error': str(e)
                })
        
        logger.info(f"📊 Subida completa - Exitosos: {len(successful_uploads)}, Fallidos: {len(failed_uploads)}")
        
        return successful_uploads, failed_uploads
    
    def get_document(self, s3_key: str) -> Optional[bytes]:
        """
        Descargar un documento desde S3
        
        Args:
            s3_key: Clave del archivo en S3
        
        Returns:
            Contenido del archivo en bytes o None si hay error
        """
        try:
            response = self.s3_client.get_object(
                Bucket=self.bucket_name,
                Key=s3_key
            )
            return response['Body'].read()
        except Exception as e:
            logger.error(f"❌ Error descargando documento: {e}")
            return None
    
    def list_documents(self, referencia_contrato: str, document_type: str, numero_rpc: str = None) -> List[Dict[str, Any]]:
        """
        Listar documentos de un contrato específico
        
        Args:
            referencia_contrato: Referencia del contrato
            document_type: Tipo de documento ('rpc' o 'pago')
            numero_rpc: Número de RPC (opcional, para filtrar pagos específicos de un RPC)
        
        Returns:
            Lista de documentos encontrados
        """
        try:
            folder = 'contratos-rpc-docs' if document_type == 'rpc' else 'contratos-pagos-docs'
            safe_referencia = "".join(c for c in referencia_contrato if c.isalnum() or c in ('-', '_')).strip()
            
            # Construir prefix según si es pago con numero_rpc específico
            if document_type == 'pago' and numero_rpc:
                safe_rpc = "".join(c for c in numero_rpc if c.isalnum() or c in ('-', '_')).strip()
                prefix = f"{folder}/{safe_referencia}/{safe_rpc}/"
            else:
                prefix = f"{folder}/{safe_referencia}/"
            
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=prefix
            )
            
            documents = []
            if 'Contents' in response:
                for obj in response['Contents']:
                    documents.append({
                        's3_key': obj['Key'],
                        'size': obj['Size'],
                        'last_modified': obj['LastModified'].isoformat(),
                        's3_url': f"https://{self.bucket_name}.s3.{self.region}.amazonaws.com/{obj['Key']}"
                    })
            
            return documents
            
        except Exception as e:
            logger.error(f"❌ Error listando documentos: {e}")
            return []
    
    def delete_document(self, s3_key: str) -> bool:
        """
        Eliminar un documento de S3
        
        Args:
            s3_key: Clave del archivo en S3
        
        Returns:
            True si se eliminó exitosamente, False en caso contrario
        """
        try:
            self.s3_client.delete_object(
                Bucket=self.bucket_name,
                Key=s3_key
            )
            logger.info(f"✅ Documento eliminado: {s3_key}")
            return True
        except Exception as e:
            logger.error(f"❌ Error eliminando documento: {e}")
            return False
    
    def verify_bucket_exists(self) -> bool:
        """
        Verificar si el bucket existe y es accesible
        
        Returns:
            True si el bucket existe y es accesible
        """
        try:
            self.s3_client.head_bucket(Bucket=self.bucket_name)
            logger.info(f"✅ Bucket verificado: {self.bucket_name}")
            return True
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == '404':
                logger.error(f"❌ Bucket no existe: {self.bucket_name}")
            elif error_code == '403':
                logger.error(f"❌ Sin permisos para acceder al bucket: {self.bucket_name}")
            else:
                logger.error(f"❌ Error verificando bucket: {e}")
            return False
        except Exception as e:
            logger.error(f"❌ Error inesperado verificando bucket: {e}")
            return False


def validate_document_file(filename: str, content: bytes, max_size_mb: int = 10) -> Tuple[bool, str]:
    """
    Validar archivo de documento
    
    Args:
        filename: Nombre del archivo
        content: Contenido del archivo
        max_size_mb: Tamaño máximo en MB
    
    Returns:
        Tupla (es_válido, mensaje_error)
    """
    # Validar tamaño
    max_size_bytes = max_size_mb * 1024 * 1024
    if len(content) > max_size_bytes:
        return False, f"Archivo excede el tamaño máximo de {max_size_mb}MB"
    
    # Validar extensión
    allowed_extensions = {'.pdf', '.doc', '.docx', '.xls', '.xlsx', '.jpg', '.jpeg', '.png', '.txt'}
    file_ext = Path(filename).suffix.lower()
    
    if file_ext not in allowed_extensions:
        return False, f"Tipo de archivo no permitido: {file_ext}"
    
    return True, "Archivo válido"

"""
Pydantic Models for Reportes de Contratos
Modelos específicos para el sistema de reportes de seguimiento de contratos
Interoperabilidad con Artefacto de Seguimiento
"""

from pydantic import BaseModel, Field, validator
from typing import Optional, Dict, Any, List
from datetime import datetime

# ============================================================================
# MODELOS PARA REPORTES DE CONTRATOS (Interoperabilidad con Artefacto de Seguimiento)
# ============================================================================

class AlertaReporte(BaseModel):
    """Modelo para alertas en reportes de contratos"""
    descripcion: str = Field(..., description="Descripción de la alerta")
    es_alerta: bool = Field(..., description="Indica si es una alerta activa")
    tipo_alerta: List[str] = Field(..., description="Lista de tipos de alerta")

class ArchivoEvidencia(BaseModel):
    """Modelo para archivos de evidencia en Google Drive"""
    id: str = Field(..., description="ID único del archivo")
    name: str = Field(..., description="Nombre del archivo")
    size: int = Field(..., ge=0, description="Tamaño del archivo en bytes")
    type: str = Field(..., description="Tipo MIME del archivo")
    url: str = Field(..., description="URL del archivo en Google Drive")

class ReporteContratoRequest(BaseModel):
    """Modelo para crear reportes de contratos"""
    alertas: AlertaReporte = Field(..., description="Información de alertas del reporte")
    archivos_evidencia: List[ArchivoEvidencia] = Field(..., description="Lista de archivos de evidencia")
    avance_financiero: int = Field(..., ge=0, le=100, description="Porcentaje de avance financiero (0-100)")
    avance_fisico: int = Field(..., ge=0, le=100, description="Porcentaje de avance físico (0-100)")
    fecha_reporte: str = Field(..., description="Fecha del reporte (ISO format)")
    nombre_centro_gestor: Optional[str] = Field(None, description="Nombre del centro gestor responsable")
    observaciones: str = Field(..., description="Observaciones del reporte")
    referencia_contrato: str = Field(..., min_length=1, description="Referencia del contrato")
    url_carpeta_drive: str = Field(..., description="URL de la carpeta en Google Drive")
    usuario_reporte: str = Field(..., min_length=1, description="Usuario que crea el reporte")
    
    @validator('fecha_reporte')
    def validate_fecha_reporte(cls, v):
        """Validar formato de fecha"""
        if not v or not v.strip():
            raise ValueError('Fecha del reporte es requerida')
        return v.strip()
    
    @validator('referencia_contrato', 'usuario_reporte')
    def validate_required_fields(cls, v):
        """Validar campos obligatorios"""
        if not v or not v.strip():
            raise ValueError('Este campo es obligatorio')
        return v.strip()

class ReporteContratoResponse(BaseModel):
    """Respuesta para operaciones de reportes de contratos"""
    success: bool
    message: str
    doc_id: Optional[str] = None
    reporte_data: Optional[Dict[str, Any]] = None
    drive_folder_created: Optional[bool] = None
    drive_folder_url: Optional[str] = None
    timestamp: datetime
    error: Optional[str] = None
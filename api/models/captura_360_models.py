"""
Modelos Pydantic para Captura de Estado 360
Gestión de reconocimiento de unidades de proyecto
"""

from pydantic import BaseModel, Field, validator
from typing import Optional, Dict, List
from datetime import datetime


class UpEntorno(BaseModel):
    """Modelo para información del entorno del proyecto"""
    nombre_centro_gestor: str = Field(..., description="Nombre del centro gestor")
    invocar_centro_gestor: bool = Field(..., description="Indica si se debe invocar al centro gestor")
    solicitud_centro_gestor: str = Field(..., description="Solicitud específica al centro gestor")


class CoordinatesGPS(BaseModel):
    """Modelo para coordenadas GPS"""
    type: str = Field(..., description="Tipo de geometría (Point, LineString, Polygon, etc.)")
    coordinates: List = Field(..., description="Coordenadas en formato GeoJSON")


class PhotosUrl(BaseModel):
    """Modelo para URLs de fotos organizadas por estado"""
    photosBeforeUrl: Optional[str] = Field(None, description="URL de carpeta con fotos 'Antes'")
    photoWhileUrl: Optional[str] = Field(None, description="URL de carpeta con fotos 'Durante'")
    photosAfterUrl: Optional[str] = Field(None, description="URL de carpeta con fotos 'Después'")


class CapturaEstado360Request(BaseModel):
    """Modelo de solicitud para captura de estado 360"""
    upid: str = Field(..., description="ID único de la unidad de proyecto")
    nombre_up: str = Field(..., description="Nombre de la unidad de proyecto")
    nombre_up_detalle: str = Field(..., description="Detalle del nombre de la unidad de proyecto")
    descripcion_intervencion: str = Field(..., description="Descripción de la intervención")
    solicitud_intervencion: str = Field(..., description="Solicitud de la intervención")
    up_entorno: UpEntorno = Field(..., description="Información del entorno del proyecto")
    estado: str = Field(..., description="Estado actual del proyecto (usado para calcular estado_360)")
    requiere_alcalde: bool = Field(..., description="Indica si requiere participación del alcalde")
    entrega_publica: bool = Field(..., description="Indica si habrá entrega pública")
    observaciones: str = Field(..., description="Observaciones adicionales")
    coordinates_gps: CoordinatesGPS = Field(..., description="Coordenadas GPS del proyecto")
    photos: Optional[List[str]] = Field(None, description="Lista de nombres de archivos de fotos a subir")
    
    @validator('estado')
    def validate_estado(cls, v):
        """Validar que el estado sea uno de los valores permitidos"""
        estados_validos = [
            "En alistamiento", 
            "En ejecución", 
            "Suspendido", 
            "Terminado", 
            "Inaugurado"
        ]
        if v not in estados_validos:
            raise ValueError(f"Estado debe ser uno de: {', '.join(estados_validos)}")
        return v


class CapturaEstado360Response(BaseModel):
    """Modelo de respuesta para captura de estado 360"""
    success: bool = Field(..., description="Indica si la operación fue exitosa")
    message: str = Field(..., description="Mensaje descriptivo del resultado")
    data: Optional[Dict] = Field(None, description="Datos del registro creado")
    document_id: Optional[str] = Field(None, description="ID del documento en Firebase")
    estado_360: Optional[str] = Field(None, description="Estado 360 calculado (Antes/Durante/Después)")
    photos_uploaded: Optional[List[Dict]] = Field(None, description="Lista de fotos subidas exitosamente")
    photos_failed: Optional[List[Dict]] = Field(None, description="Lista de fotos que fallaron al subir")
    timestamp: str = Field(..., description="Timestamp de la operación")


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

CAPTURA_360_MODELS_AVAILABLE = True

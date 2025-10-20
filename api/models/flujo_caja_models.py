"""
Pydantic Models for Flujo de Caja Empréstito
Modelos de datos para validación de flujos de caja
"""

from pydantic import BaseModel, Field, validator
from typing import Optional, Dict, Any, List
from datetime import datetime

# ============================================================================
# MODELOS PARA FLUJO DE CAJA EMPRÉSTITO
# ============================================================================

class FlujoCajaRequest(BaseModel):
    """Modelo para registro individual de flujo de caja"""
    responsable: str = Field(..., description="Nombre del responsable")
    organismo: str = Field(..., description="Nombre del organismo")
    banco: str = Field(..., description="Nombre del banco")
    bp_proyecto: str = Field(..., description="BP del proyecto")
    descripcion_bp: str = Field(..., description="Descripción del BP")
    mes: str = Field(..., description="Mes en formato abreviado (ej: jul-25)")
    periodo: str = Field(..., description="Período en formato ISO (YYYY-MM-DD)")
    desembolso: float = Field(default=0.0, description="Monto de desembolso")
    columna_origen: Optional[str] = Field(None, description="Columna origen del Excel")
    archivo_origen: Optional[str] = Field(None, description="Nombre del archivo origen")

class FlujoCajaResponse(BaseModel):
    """Modelo para respuesta de operaciones de flujo de caja"""
    success: bool
    message: Optional[str] = None
    data: Optional[List[Dict[str, Any]]] = None
    count: Optional[int] = None
    summary: Optional[Dict[str, Any]] = None

class FlujoCajaUploadRequest(BaseModel):
    """Modelo para request de carga de flujo de caja"""
    update_mode: str = Field(default="merge", description="Modo de actualización: merge, replace, append")
    
    @validator('update_mode')
    def validate_update_mode(cls, v):
        if v not in ["merge", "replace", "append"]:
            raise ValueError('update_mode debe ser: merge, replace o append')
        return v

class FlujoCajaFilters(BaseModel):
    """Modelo para filtros de consulta de flujo de caja"""
    responsable: Optional[str] = Field(None, description="Filtrar por responsable específico")
    organismo: Optional[str] = Field(None, description="Filtrar por organismo específico")
    banco: Optional[str] = Field(None, description="Filtrar por banco específico")
    bp_proyecto: Optional[str] = Field(None, description="Filtrar por BP Proyecto específico")
    mes: Optional[str] = Field(None, description="Filtrar por mes específico")
    periodo_desde: Optional[str] = Field(None, description="Período desde (YYYY-MM-DD)")
    periodo_hasta: Optional[str] = Field(None, description="Período hasta (YYYY-MM-DD)")
    limit: Optional[int] = Field(None, ge=1, le=1000, description="Límite de registros")

# Variable de disponibilidad
FLUJO_CAJA_MODELS_AVAILABLE = True
# -*- coding: utf-8 -*-
"""
api/models/general_models.py — Modelos Pydantic para endpoints generales.

Incluye los modelos de:
- Reportar Bug
- Solicitar Escalada de Privilegios
- Realizar Recomendación
"""

from typing import Optional
from pydantic import BaseModel, Field


class ReportarBugRequest(BaseModel):
    reportado_por: Optional[str] = Field(None, description="Usuario que reporta el bug")
    descripcion_bug: Optional[str] = Field(None, description="Descripcion del comportamiento inesperado")
    contexto_adicional_bug: Optional[str] = Field(None, description="Impacto o contexto adicional del bug")


class SolicitarEscaladaPrivilegiosRequest(BaseModel):
    reportado_por: Optional[str] = Field(None, description="Usuario que solicita la escalada")
    rol_solicitado: Optional[str] = Field(None, description="Rol que se requiere")
    motivo_solicitud: Optional[str] = Field(None, description="Motivo de la solicitud")
    justificacion_escalada: Optional[str] = Field(None, description="Justificacion de por que requiere el nuevo rol")


class RealizarRecomendacionRequest(BaseModel):
    reportado_por: str = Field(..., description="Usuario que realiza la recomendacion")
    recomendacion_sugerencia: str = Field(..., description="Recomendacion o sugerencia propuesta")
    beneficio_esperado: str = Field(..., description="Beneficio esperado de la recomendacion")


class ActualizarRecomendacionRequest(BaseModel):
    reportado_por: Optional[str] = Field(None, description="Usuario que realiza la recomendacion")
    recomendacion_sugerencia: Optional[str] = Field(None, description="Recomendacion o sugerencia propuesta")
    beneficio_esperado: Optional[str] = Field(None, description="Beneficio esperado de la recomendacion")

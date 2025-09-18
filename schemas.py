"""
Esquemas Pydantic para la serialización de datos basados en la estructura real de la tabla
"""
from pydantic import BaseModel
from datetime import datetime, date
from decimal import Decimal
from typing import Optional, Dict, Any

class EmpContratoBase(BaseModel):
    """Esquema base para contratos de empleados con los campos reales de la tabla"""
    # Información básica del contrato
    referencia_del_contrato: Optional[str] = None
    proceso_de_compra: Optional[str] = None
    proceso_id: Optional[int] = None
    
    # Información de la entidad
    nombre_entidad: Optional[str] = None
    nit_entidad: Optional[str] = None
    localizacion: Optional[str] = None
    orden: Optional[str] = None
    sector: Optional[str] = None
    rama: Optional[str] = None
    entidad_centralizada: Optional[str] = None
    codigo_entidad: Optional[str] = None
    
    # Estado y categorización del contrato
    estado_contrato: Optional[str] = None
    codigo_de_categoria_principal: Optional[str] = None
    descripcion_del_proceso: Optional[str] = None
    objeto_del_contrato: Optional[str] = None
    tipo_de_contrato: Optional[str] = None
    modalidad_de_contratacion: Optional[str] = None
    justificacion_modalidad: Optional[str] = None
    
    # Fechas del contrato
    fecha_de_firma: Optional[date] = None
    fecha_de_inicio_del_contrato: Optional[date] = None
    fecha_de_fin_del_contrato: Optional[date] = None
    duracion_del_contrato: Optional[str] = None
    fecha_inicio_liquidacion: Optional[date] = None
    fecha_fin_liquidacion: Optional[date] = None
    
    # Información del proveedor
    documento_proveedor: Optional[str] = None
    tipodocproveedor: Optional[str] = None
    proveedor_adjudicado: Optional[str] = None
    es_grupo: Optional[bool] = None
    es_pyme: Optional[bool] = None
    codigo_proveedor: Optional[str] = None
    
    # Representante legal
    nombre_representante_legal: Optional[str] = None
    nacionalidad_representante_legal: Optional[str] = None
    domicilio_representante_legal: Optional[str] = None
    tipo_identificacion_representante_legal: Optional[str] = None
    identificacion_representante_legal: Optional[str] = None
    genero_representante_legal: Optional[str] = None
    
    # Valores monetarios
    valor_del_contrato: Optional[Decimal] = None
    valor_de_pago_adelantado: Optional[Decimal] = None
    valor_facturado: Optional[Decimal] = None
    valor_pendiente_de_pago: Optional[Decimal] = None
    valor_pagado: Optional[Decimal] = None
    valor_amortizado: Optional[Decimal] = None
    valor_pendiente_de_ejecucion: Optional[Decimal] = None
    
    # Fuentes de financiamiento
    presupuesto_general_nacion: Optional[Decimal] = None
    sistema_general_participaciones: Optional[Decimal] = None
    sistema_general_regalias: Optional[Decimal] = None
    recursos_propios_alcaldias: Optional[Decimal] = None
    recursos_de_credito: Optional[Decimal] = None
    recursos_propios: Optional[Decimal] = None
    
    # Información BPIN
    estado_bpin: Optional[str] = None
    anno_bpin: Optional[str] = None
    bpin: Optional[str] = None
    saldo_cdp: Optional[str] = None
    saldo_vigencia: Optional[str] = None
    
    # Condiciones y características especiales
    condiciones_de_entrega: Optional[str] = None
    habilita_pago_adelantado: Optional[bool] = None
    liquidacion: Optional[bool] = None
    obligacion_ambiental: Optional[bool] = None
    obligaciones_postconsumo: Optional[bool] = None
    reversion: Optional[bool] = None
    origen_de_los_recursos: Optional[str] = None
    destino_gasto: Optional[str] = None
    
    # Prórrogas
    el_contrato_puede_ser_prorrogado: Optional[bool] = None
    fecha_notificacion_prorroga: Optional[date] = None
    espostconflicto: Optional[bool] = None
    dias_adicionados: Optional[str] = None
    puntos_del_acuerdo: Optional[str] = None
    pilares_del_acuerdo: Optional[str] = None
    
    # Información bancaria
    nombre_del_banco: Optional[str] = None
    tipo_de_cuenta: Optional[str] = None
    numero_de_cuenta: Optional[str] = None
    
    # Responsables
    nombre_ordenador_del_gasto: Optional[str] = None
    tipo_documento_ordenador_gasto: Optional[str] = None
    numero_documento_ordenador_gasto: Optional[str] = None
    nombre_supervisor: Optional[str] = None
    tipo_documento_supervisor: Optional[str] = None
    numero_documento_supervisor: Optional[str] = None
    nombre_ordenador_de_pago: Optional[str] = None
    tipo_documento_ordenador_pago: Optional[str] = None
    numero_documento_ordenador_pago: Optional[str] = None
    
    # Información adicional
    urlproceso: Optional[Dict[str, Any]] = None
    search_field: Optional[str] = None
    referencia_buscada: Optional[str] = None
    search_type: Optional[str] = None
    total_campos: Optional[int] = None
    
    # Timestamps
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

class EmpContrato(EmpContratoBase):
    """Esquema para respuesta de contratos de empleados"""
    id_contrato: str
    
    class Config:
        from_attributes = True

class EmpContratoCreate(BaseModel):
    """Esquema para crear nuevos contratos - solo campos requeridos y opcionales para creación"""
    # Campos obligatorios para crear un contrato
    referencia_del_contrato: str
    proceso_de_compra: str
    nombre_entidad: str
    nit_entidad: str
    objeto_del_contrato: str
    valor_del_contrato: Decimal
    estado_contrato: str = "En Proceso"
    
    # Campos opcionales más comunes
    proceso_id: Optional[int] = None
    localizacion: Optional[str] = None
    sector: Optional[str] = None
    descripcion_del_proceso: Optional[str] = None
    tipo_de_contrato: Optional[str] = None
    modalidad_de_contratacion: Optional[str] = None
    
    # Fechas opcionales
    fecha_de_firma: Optional[date] = None
    fecha_de_inicio_del_contrato: Optional[date] = None
    fecha_de_fin_del_contrato: Optional[date] = None
    duracion_del_contrato: Optional[str] = None
    
    # Información del proveedor
    documento_proveedor: Optional[str] = None
    proveedor_adjudicado: Optional[str] = None
    es_pyme: Optional[bool] = False
    
    # Valores monetarios opcionales
    valor_de_pago_adelantado: Optional[Decimal] = None
    presupuesto_general_nacion: Optional[Decimal] = None
    recursos_propios: Optional[Decimal] = None

class EmpContratoUpdate(BaseModel):
    """Esquema para actualizar contratos existentes - todos los campos opcionales"""
    # Información básica del contrato
    referencia_del_contrato: Optional[str] = None
    proceso_de_compra: Optional[str] = None
    proceso_id: Optional[int] = None
    
    # Información de la entidad
    nombre_entidad: Optional[str] = None
    nit_entidad: Optional[str] = None
    localizacion: Optional[str] = None
    sector: Optional[str] = None
    
    # Estado y categorización del contrato
    estado_contrato: Optional[str] = None
    descripcion_del_proceso: Optional[str] = None
    objeto_del_contrato: Optional[str] = None
    tipo_de_contrato: Optional[str] = None
    modalidad_de_contratacion: Optional[str] = None
    
    # Fechas del contrato
    fecha_de_firma: Optional[date] = None
    fecha_de_inicio_del_contrato: Optional[date] = None
    fecha_de_fin_del_contrato: Optional[date] = None
    duracion_del_contrato: Optional[str] = None
    fecha_inicio_liquidacion: Optional[date] = None
    fecha_fin_liquidacion: Optional[date] = None
    
    # Información del proveedor
    documento_proveedor: Optional[str] = None
    proveedor_adjudicado: Optional[str] = None
    es_pyme: Optional[bool] = None
    
    # Valores monetarios
    valor_del_contrato: Optional[Decimal] = None
    valor_de_pago_adelantado: Optional[Decimal] = None
    valor_facturado: Optional[Decimal] = None
    valor_pendiente_de_pago: Optional[Decimal] = None
    valor_pagado: Optional[Decimal] = None
    
    # Fuentes de financiamiento
    presupuesto_general_nacion: Optional[Decimal] = None
    recursos_propios: Optional[Decimal] = None
    recursos_de_credito: Optional[Decimal] = None
    
    # Condiciones especiales
    liquidacion: Optional[bool] = None
    habilita_pago_adelantado: Optional[bool] = None

class EmpContratoSummary(BaseModel):
    """Esquema simplificado para listados"""
    id_contrato: str
    referencia_del_contrato: str
    nombre_entidad: str
    proveedor_adjudicado: str
    valor_del_contrato: Decimal
    estado_contrato: str
    fecha_de_inicio_del_contrato: Optional[date] = None
    fecha_de_fin_del_contrato: Optional[date] = None
    tipo_de_contrato: Optional[str] = None
    modalidad_de_contratacion: Optional[str] = None
    
    class Config:
        from_attributes = True


# ============================================================================
# SCHEMAS PARA EMP_PROCESOS
# ============================================================================

class EmpProcesoBase(BaseModel):
    """Esquema base para procesos"""
    referencia_proceso: Optional[str] = None
    banco: Optional[str] = None
    descripcion: Optional[str] = None
    objeto: Optional[str] = None
    valor_total: Optional[Decimal] = None
    valor_plataforma: Optional[Decimal] = None
    modalidad: Optional[str] = None
    referencia_contrato: Optional[str] = None
    planeado: Optional[date] = None
    estado_proceso_secop: Optional[str] = None
    observaciones: Optional[str] = None
    numero_contacto: Optional[str] = None
    url_proceso: Optional[str] = None
    url_estado_real_proceso: Optional[str] = None
    archivo_origen: Optional[str] = None
    fecha_procesamiento: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

class EmpProcesoCreate(BaseModel):
    """Esquema para crear nuevos procesos"""
    referencia_proceso: str
    banco: str
    objeto: str
    valor_total: Decimal
    estado_proceso_secop: str = "En Planeación"
    
    # Campos opcionales
    descripcion: Optional[str] = None
    valor_plataforma: Optional[Decimal] = None
    modalidad: Optional[str] = None
    referencia_contrato: Optional[str] = None
    planeado: Optional[date] = None
    observaciones: Optional[str] = None
    numero_contacto: Optional[str] = None
    url_proceso: Optional[str] = None
    url_estado_real_proceso: Optional[str] = None

class EmpProcesoUpdate(BaseModel):
    """Esquema para actualizar procesos existentes"""
    referencia_proceso: Optional[str] = None
    banco: Optional[str] = None
    descripcion: Optional[str] = None
    objeto: Optional[str] = None
    valor_total: Optional[Decimal] = None
    valor_plataforma: Optional[Decimal] = None
    modalidad: Optional[str] = None
    referencia_contrato: Optional[str] = None
    planeado: Optional[date] = None
    estado_proceso_secop: Optional[str] = None
    observaciones: Optional[str] = None
    numero_contacto: Optional[str] = None
    url_proceso: Optional[str] = None
    url_estado_real_proceso: Optional[str] = None

class EmpProceso(EmpProcesoBase):
    """Esquema completo para respuesta de procesos"""
    id: int
    
    class Config:
        from_attributes = True

class EmpProcesoSummary(BaseModel):
    """Esquema simplificado para listados de procesos"""
    id: int
    referencia_proceso: str
    banco: str
    objeto: str
    valor_total: Decimal
    estado_proceso_secop: str
    referencia_contrato: Optional[str] = None
    planeado: Optional[date] = None
    modalidad: Optional[str] = None
    
    class Config:
        from_attributes = True

class ProcesoContratoIndex(BaseModel):
    """Esquema para el índice de referencia_proceso y referencia_contrato"""
    referencia_proceso: str
    referencia_contrato: Optional[str] = None
    proceso_id: int
    estado_proceso: str
    valor_total: Decimal
    
    class Config:
        from_attributes = True
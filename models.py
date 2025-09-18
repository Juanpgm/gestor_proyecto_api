"""
Modelos de datos para la API basados en la estructura real de la base de datos
"""
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, Numeric, Date, TIMESTAMP
from sqlalchemy.dialects.postgresql import JSONB
from config import Base

class EmpContrato(Base):
    """
    Modelo para la tabla emp_contratos basado en la estructura real de la base de datos
    """
    __tablename__ = "emp_contratos"
    __table_args__ = {'schema': 'public'}
    
    # Clave primaria
    id_contrato = Column(String(50), primary_key=True, index=True)
    
    # Información básica del contrato
    referencia_del_contrato = Column(String(100), nullable=False, unique=True, index=True)
    proceso_de_compra = Column(String(50), nullable=False, index=True)
    proceso_id = Column(Integer, nullable=True, index=True)
    
    # Información de la entidad
    nombre_entidad = Column(String(500), nullable=False, index=True)
    nit_entidad = Column(String(20), nullable=False, index=True)
    departamento = Column(String(100), nullable=True, index=True)
    ciudad = Column(String(100), nullable=True, index=True)
    localizacion = Column(String(200), nullable=True)
    orden = Column(String(50), nullable=True)
    sector = Column(String(200), nullable=True, index=True)
    rama = Column(String(50), nullable=True)
    entidad_centralizada = Column(String(50), nullable=True)
    codigo_entidad = Column(String(20), nullable=True)
    
    # Estado y categorización del contrato
    estado_contrato = Column(String(50), nullable=False, index=True)
    codigo_de_categoria_principal = Column(String(50), nullable=True)
    descripcion_del_proceso = Column(Text, nullable=True)
    objeto_del_contrato = Column(Text, nullable=False)
    tipo_de_contrato = Column(String(100), nullable=True, index=True)
    modalidad_de_contratacion = Column(String(100), nullable=True, index=True)
    justificacion_modalidad = Column(String(200), nullable=True)
    
    # Fechas del contrato
    fecha_de_firma = Column(Date, nullable=True, index=True)
    fecha_de_inicio_del_contrato = Column(Date, nullable=True, index=True)
    fecha_de_fin_del_contrato = Column(Date, nullable=True, index=True)
    duracion_del_contrato = Column(String(50), nullable=True)
    fecha_inicio_liquidacion = Column(Date, nullable=True)
    fecha_fin_liquidacion = Column(Date, nullable=True)
    
    # Información del proveedor
    documento_proveedor = Column(String(20), nullable=True)
    tipodocproveedor = Column(String(50), nullable=True)
    proveedor_adjudicado = Column(String(500), nullable=False, index=True)
    es_grupo = Column(Boolean, nullable=True)
    es_pyme = Column(Boolean, nullable=True)
    codigo_proveedor = Column(String(20), nullable=True)
    
    # Representante legal
    nombre_representante_legal = Column(String(200), nullable=True)
    nacionalidad_representante_legal = Column(String(10), nullable=True)
    domicilio_representante_legal = Column(String(200), nullable=True)
    tipo_identificacion_representante_legal = Column(String(50), nullable=True)
    identificacion_representante_legal = Column(String(50), nullable=True)
    genero_representante_legal = Column(String(20), nullable=True)
    
    # Valores monetarios
    valor_del_contrato = Column(Numeric(15, 2), nullable=False, index=True)
    valor_de_pago_adelantado = Column(Numeric(15, 2), nullable=True, default=0)
    valor_facturado = Column(Numeric(15, 2), nullable=True, default=0)
    valor_pendiente_de_pago = Column(Numeric(15, 2), nullable=True, default=0)
    valor_pagado = Column(Numeric(15, 2), nullable=True, default=0)
    valor_amortizado = Column(Numeric(15, 2), nullable=True, default=0)
    valor_pendiente_de_ejecucion = Column(Numeric(15, 2), nullable=True, default=0)
    
    # Fuentes de financiamiento
    presupuesto_general_nacion = Column(Numeric(15, 2), nullable=True, default=0)
    sistema_general_participaciones = Column(Numeric(15, 2), nullable=True, default=0)
    sistema_general_regalias = Column(Numeric(15, 2), nullable=True, default=0)
    recursos_propios_alcaldias = Column(Numeric(15, 2), nullable=True, default=0)
    recursos_de_credito = Column(Numeric(15, 2), nullable=True, default=0)
    recursos_propios = Column(Numeric(15, 2), nullable=True, default=0)
    
    # Información BPIN
    estado_bpin = Column(String(50), nullable=True)
    anno_bpin = Column(String(10), nullable=True)
    bpin = Column(String(20), nullable=True, index=True)
    saldo_cdp = Column(String(50), nullable=True)
    saldo_vigencia = Column(String(50), nullable=True)
    
    # Condiciones y características especiales
    condiciones_de_entrega = Column(String(100), nullable=True)
    habilita_pago_adelantado = Column(Boolean, nullable=True)
    liquidacion = Column(Boolean, nullable=True)
    obligacion_ambiental = Column(Boolean, nullable=True)
    obligaciones_postconsumo = Column(Boolean, nullable=True)
    reversion = Column(Boolean, nullable=True)
    origen_de_los_recursos = Column(String(50), nullable=True)
    destino_gasto = Column(String(50), nullable=True)
    
    # Prórrogas
    el_contrato_puede_ser_prorrogado = Column(Boolean, nullable=True)
    fecha_notificacion_prorroga = Column(Date, nullable=True)
    espostconflicto = Column(Boolean, nullable=True)
    dias_adicionados = Column(String(20), nullable=True)
    puntos_del_acuerdo = Column(String(100), nullable=True)
    pilares_del_acuerdo = Column(String(100), nullable=True)
    
    # Información bancaria
    nombre_del_banco = Column(String(100), nullable=True)
    tipo_de_cuenta = Column(String(50), nullable=True)
    numero_de_cuenta = Column(String(50), nullable=True)
    
    # Responsables
    nombre_ordenador_del_gasto = Column(String(200), nullable=True)
    tipo_documento_ordenador_gasto = Column(String(50), nullable=True)
    numero_documento_ordenador_gasto = Column(String(50), nullable=True)
    nombre_supervisor = Column(String(200), nullable=True)
    tipo_documento_supervisor = Column(String(50), nullable=True)
    numero_documento_supervisor = Column(String(50), nullable=True)
    nombre_ordenador_de_pago = Column(String(200), nullable=True)
    tipo_documento_ordenador_pago = Column(String(50), nullable=True)
    numero_documento_ordenador_pago = Column(String(50), nullable=True)
    
    # Información adicional
    urlproceso = Column(JSONB, nullable=True)
    search_field = Column(String(50), nullable=True)
    referencia_buscada = Column(String(100), nullable=True)
    search_type = Column(String(50), nullable=True)
    total_campos = Column(Integer, nullable=True)
    
    # Timestamps
    created_at = Column(TIMESTAMP, nullable=False, index=True, server_default='CURRENT_TIMESTAMP')
    updated_at = Column(TIMESTAMP, nullable=True, server_default='CURRENT_TIMESTAMP')
    
    def __repr__(self):
        return f"<EmpContrato(id_contrato='{self.id_contrato}', referencia='{self.referencia_del_contrato}', entidad='{self.nombre_entidad}')>"


class EmpProceso(Base):
    """
    Modelo para la tabla emp_procesos basado en la estructura real de la base de datos
    """
    __tablename__ = "emp_procesos"
    __table_args__ = {'schema': 'public'}
    
    # Clave primaria
    id = Column(Integer, primary_key=True, index=True)
    
    # Información básica del proceso
    referencia_proceso = Column(String(100), nullable=False, unique=True, index=True)
    banco = Column(String(100), nullable=False, index=True)
    descripcion = Column(Text, nullable=True)
    objeto = Column(Text, nullable=False)
    
    # Valores monetarios
    valor_total = Column(Numeric(15, 2), nullable=False, index=True)
    valor_plataforma = Column(Numeric(15, 2), nullable=True)
    
    # Información del proceso
    modalidad = Column(String(100), nullable=True, index=True)
    referencia_contrato = Column(String(100), nullable=True, index=True)
    planeado = Column(Date, nullable=True, index=True)
    estado_proceso_secop = Column(String(100), nullable=False, index=True)
    observaciones = Column(Text, nullable=True)
    
    # Información de contacto y URLs
    numero_contacto = Column(String(20), nullable=True)
    url_proceso = Column(String(500), nullable=True)
    url_estado_real_proceso = Column(String(500), nullable=True)
    
    # Metadatos
    archivo_origen = Column(String(200), nullable=True)
    fecha_procesamiento = Column(TIMESTAMP, nullable=True)
    
    # Timestamps
    created_at = Column(TIMESTAMP, nullable=False, index=True, server_default='CURRENT_TIMESTAMP')
    updated_at = Column(TIMESTAMP, nullable=True, server_default='CURRENT_TIMESTAMP')
    
    def __repr__(self):
        return f"<EmpProceso(id={self.id}, referencia_proceso='{self.referencia_proceso}', estado='{self.estado_proceso_secop}')>"
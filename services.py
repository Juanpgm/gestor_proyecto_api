"""
Servicios y funciones puras para lógica de negocio
Siguiendo principios de programación funcional
"""
from typing import Dict, Any, Optional, List, Union, Callable, TypeVar
from datetime import datetime, date
from decimal import Decimal
from functools import reduce, partial
from sqlalchemy.orm import Session, Query
from sqlalchemy import and_, or_, func
import uuid
import re

from models import EmpContrato
import schemas

# Tipos genéricos para programación funcional
T = TypeVar('T')
R = TypeVar('R')

# ============================================================================
# FUNCIONES PURAS DE VALIDACIÓN
# ============================================================================

def validate_nit(nit: str) -> bool:
    """Valida formato de NIT colombiano"""
    if not nit:
        return False
    # Remover guiones y espacios
    clean_nit = re.sub(r'[-\s]', '', nit)
    # Verificar que solo contenga números y tenga entre 8-11 dígitos
    return bool(re.match(r'^\d{8,11}$', clean_nit))

def validate_contract_reference(reference: str) -> bool:
    """Valida formato de referencia de contrato"""
    if not reference or len(reference.strip()) < 3:
        return False
    # Verificar que no contenga caracteres especiales peligrosos
    return not bool(re.search(r'[<>"\']', reference))

def validate_positive_amount(amount: Optional[Decimal]) -> bool:
    """Valida que un monto sea positivo"""
    return amount is None or (isinstance(amount, (Decimal, int, float)) and amount > 0)

def validate_date_range(start_date: Optional[date], end_date: Optional[date]) -> bool:
    """Valida que fecha de inicio sea anterior a fecha de fin"""
    if not start_date or not end_date:
        return True
    return start_date <= end_date

def validate_contract_data(data: Dict[str, Any]) -> List[str]:
    """Función pura que valida todos los datos de un contrato"""
    errors = []
    
    # Validaciones requeridas
    if not data.get('referencia_del_contrato'):
        errors.append("referencia_del_contrato es requerida")
    elif not validate_contract_reference(data['referencia_del_contrato']):
        errors.append("referencia_del_contrato tiene formato inválido")
    
    if not data.get('nit_entidad'):
        errors.append("nit_entidad es requerido")
    elif not validate_nit(data['nit_entidad']):
        errors.append("nit_entidad tiene formato inválido")
    
    if not data.get('nombre_entidad'):
        errors.append("nombre_entidad es requerido")
    
    if not data.get('objeto_del_contrato'):
        errors.append("objeto_del_contrato es requerido")
    
    # Validaciones de montos
    valor_contrato = data.get('valor_del_contrato')
    if valor_contrato is not None and not validate_positive_amount(valor_contrato):
        errors.append("valor_del_contrato debe ser positivo")
    
    # Validaciones de fechas
    fecha_inicio = data.get('fecha_de_inicio_del_contrato')
    fecha_fin = data.get('fecha_de_fin_del_contrato')
    if not validate_date_range(fecha_inicio, fecha_fin):
        errors.append("fecha_de_inicio_del_contrato debe ser anterior a fecha_de_fin_del_contrato")
    
    return errors

# ============================================================================
# FUNCIONES PURAS DE TRANSFORMACIÓN
# ============================================================================

def normalize_string(text: Optional[str]) -> Optional[str]:
    """Normaliza strings eliminando espacios extra y convirtiendo a título"""
    if not text:
        return text
    return ' '.join(text.strip().split()).title()

def generate_contract_id() -> str:
    """Genera un ID único para contrato"""
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    random_part = str(uuid.uuid4())[:8]
    return f"CT-{timestamp}-{random_part}".upper()

def transform_contract_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """Transforma y normaliza datos de contrato"""
    transformed = data.copy()
    
    # Normalizar strings
    string_fields = ['nombre_entidad', 'proveedor_adjudicado']
    for field in string_fields:
        if transformed.get(field):
            transformed[field] = normalize_string(transformed[field])
    
    # Normalizar NIT
    if transformed.get('nit_entidad'):
        transformed['nit_entidad'] = re.sub(r'[-\s]', '', transformed['nit_entidad'])
    
    # Agregar timestamps
    now = datetime.utcnow()
    if 'created_at' not in transformed:
        transformed['created_at'] = now
    transformed['updated_at'] = now
    
    return transformed

def calculate_contract_metrics(contract_data: Dict[str, Any]) -> Dict[str, Any]:
    """Calcula métricas derivadas del contrato"""
    metrics = {}
    
    valor_contrato = contract_data.get('valor_del_contrato', 0)
    valor_pagado = contract_data.get('valor_pagado', 0)
    valor_facturado = contract_data.get('valor_facturado', 0)
    
    if valor_contrato:
        metrics['porcentaje_ejecutado'] = (valor_facturado / valor_contrato) * 100 if valor_facturado else 0
        metrics['porcentaje_pagado'] = (valor_pagado / valor_contrato) * 100 if valor_pagado else 0
    
    # Calcular duración en días si hay fechas
    fecha_inicio = contract_data.get('fecha_de_inicio_del_contrato')
    fecha_fin = contract_data.get('fecha_de_fin_del_contrato')
    if fecha_inicio and fecha_fin and isinstance(fecha_inicio, date) and isinstance(fecha_fin, date):
        metrics['duracion_dias'] = (fecha_fin - fecha_inicio).days
    
    return metrics

# ============================================================================
# FUNCIONES PURAS DE FILTRADO
# ============================================================================

def build_filter_conditions(filters: Dict[str, Any]) -> List[Any]:
    """Construye condiciones de filtro para SQLAlchemy de forma funcional"""
    conditions = []
    
    filter_map = {
        'estado': lambda val: EmpContrato.estado_contrato.ilike(f"%{val}%"),
        'entidad': lambda val: EmpContrato.nombre_entidad.ilike(f"%{val}%"),
        'nit_entidad': lambda val: EmpContrato.nit_entidad == val,
        'proveedor': lambda val: EmpContrato.proveedor_adjudicado.ilike(f"%{val}%"),
        'tipo_contrato': lambda val: EmpContrato.tipo_de_contrato.ilike(f"%{val}%"),
        'valor_min': lambda val: EmpContrato.valor_del_contrato >= val,
        'valor_max': lambda val: EmpContrato.valor_del_contrato <= val,
        'fecha_desde': lambda val: EmpContrato.fecha_de_inicio_del_contrato >= val,
        'fecha_hasta': lambda val: EmpContrato.fecha_de_fin_del_contrato <= val,
    }
    
    for key, value in filters.items():
        if value is not None and key in filter_map:
            conditions.append(filter_map[key](value))
    
    return conditions

def apply_pagination(query: Query, skip: int = 0, limit: int = 10) -> Query:
    """Aplica paginación de forma funcional"""
    return query.offset(skip).limit(min(limit, 100))

def apply_sorting(query: Query, sort_by: str = 'created_at', order: str = 'desc') -> Query:
    """Aplica ordenamiento de forma funcional"""
    sort_map = {
        'created_at': EmpContrato.created_at,
        'valor_contrato': EmpContrato.valor_del_contrato,
        'fecha_inicio': EmpContrato.fecha_de_inicio_del_contrato,
        'nombre_entidad': EmpContrato.nombre_entidad,
    }
    
    column = sort_map.get(sort_by, EmpContrato.created_at)
    return query.order_by(column.desc() if order == 'desc' else column.asc())

# ============================================================================
# FUNCIONES DE ALTO ORDEN PARA QUERIES
# ============================================================================

def compose_query_modifiers(*modifiers: Callable[[Query], Query]) -> Callable[[Query], Query]:
    """Compone múltiples modificadores de query usando programación funcional"""
    def composed_modifier(query: Query) -> Query:
        return reduce(lambda q, modifier: modifier(q), modifiers, query)
    return composed_modifier

def create_filtered_query(
    db: Session,
    filters: Dict[str, Any],
    skip: int = 0,
    limit: int = 10,
    sort_by: str = 'created_at',
    order: str = 'desc'
) -> Query:
    """Crea query filtrada usando composición funcional"""
    base_query = db.query(EmpContrato)
    
    # Aplicar filtros
    conditions = build_filter_conditions(filters)
    if conditions:
        base_query = base_query.filter(and_(*conditions))
    
    # Componer modificadores
    query_modifier = compose_query_modifiers(
        partial(apply_sorting, sort_by=sort_by, order=order),
        partial(apply_pagination, skip=skip, limit=limit)
    )
    
    return query_modifier(base_query)

# ============================================================================
# SERVICIOS DE NEGOCIO
# ============================================================================

class ContractService:
    """Servicio para operaciones de contratos usando funciones puras"""
    
    @staticmethod
    def create_contract(db: Session, contract_data: schemas.EmpContratoCreate) -> Union[EmpContrato, List[str]]:
        """Crea un nuevo contrato validando datos"""
        # Convertir a diccionario para funciones puras
        data_dict = contract_data.model_dump()
        
        # Validar datos
        validation_errors = validate_contract_data(data_dict)
        if validation_errors:
            return validation_errors
        
        # Transformar datos
        transformed_data = transform_contract_data(data_dict)
        
        # Generar ID único
        transformed_data['id_contrato'] = generate_contract_id()
        
        # Crear modelo
        new_contract = EmpContrato(**transformed_data)
        
        try:
            db.add(new_contract)
            db.commit()
            db.refresh(new_contract)
            return new_contract
        except Exception as e:
            db.rollback()
            return [f"Error al crear contrato: {str(e)}"]
    
    @staticmethod
    def update_contract(
        db: Session, 
        contract_id: str, 
        update_data: schemas.EmpContratoUpdate
    ) -> Union[EmpContrato, List[str]]:
        """Actualiza un contrato existente"""
        # Buscar contrato existente
        existing_contract = db.query(EmpContrato).filter(
            EmpContrato.id_contrato == contract_id
        ).first()
        
        if not existing_contract:
            return ["Contrato no encontrado"]
        
        # Convertir datos de actualización
        update_dict = update_data.model_dump(exclude_unset=True)
        
        if not update_dict:
            return ["No hay datos para actualizar"]
        
        # Validar solo los campos que se van a actualizar
        validation_errors = validate_contract_data(update_dict)
        if validation_errors:
            return validation_errors
        
        # Transformar datos
        transformed_data = transform_contract_data(update_dict)
        
        try:
            # Actualizar campos
            for field, value in transformed_data.items():
                if hasattr(existing_contract, field):
                    setattr(existing_contract, field, value)
            
            db.commit()
            db.refresh(existing_contract)
            return existing_contract
        except Exception as e:
            db.rollback()
            return [f"Error al actualizar contrato: {str(e)}"]
    
    @staticmethod
    def get_contracts_with_filters(
        db: Session,
        filters: Dict[str, Any],
        skip: int = 0,
        limit: int = 10,
        sort_by: str = 'created_at',
        order: str = 'desc'
    ) -> List[EmpContrato]:
        """Obtiene contratos con filtros usando funciones puras"""
        query = create_filtered_query(db, filters, skip, limit, sort_by, order)
        return query.all()
    
    @staticmethod
    def get_contract_statistics(db: Session) -> Dict[str, Any]:
        """Calcula estadísticas usando funciones puras"""
        base_query = db.query(EmpContrato)
        
        stats = {
            'total_contracts': base_query.count(),
            'total_value': base_query.with_entities(
                func.sum(EmpContrato.valor_del_contrato)
            ).scalar() or 0,
            'average_value': base_query.with_entities(
                func.avg(EmpContrato.valor_del_contrato)
            ).scalar() or 0,
            'contracts_by_status': base_query.with_entities(
                EmpContrato.estado_contrato,
                func.count(EmpContrato.id_contrato)
            ).group_by(EmpContrato.estado_contrato).all()
        }
        
        return stats


# ============================================================================
# SERVICIOS PARA EMP_PROCESOS
# ============================================================================

def validate_proceso_data(data: Dict[str, Any]) -> List[str]:
    """Función pura que valida todos los datos de un proceso"""
    errors = []
    
    # Validaciones requeridas
    if not data.get('referencia_proceso'):
        errors.append("referencia_proceso es requerida")
    elif not validate_contract_reference(data['referencia_proceso']):
        errors.append("referencia_proceso tiene formato inválido")
    
    if not data.get('banco'):
        errors.append("banco es requerido")
    
    if not data.get('objeto'):
        errors.append("objeto es requerido")
    
    if not data.get('estado_proceso_secop'):
        errors.append("estado_proceso_secop es requerido")
    
    # Validaciones de montos
    valor_total = data.get('valor_total')
    if valor_total is not None and not validate_positive_amount(valor_total):
        errors.append("valor_total debe ser positivo")
    
    valor_plataforma = data.get('valor_plataforma')
    if valor_plataforma is not None and not validate_positive_amount(valor_plataforma):
        errors.append("valor_plataforma debe ser positivo")
    
    return errors

def generate_proceso_filters(filters: Dict[str, Any]) -> List[Any]:
    """Construye condiciones de filtro para procesos"""
    from models import EmpProceso
    conditions = []
    
    filter_map = {
        'banco': lambda val: EmpProceso.banco.ilike(f"%{val}%"),
        'estado': lambda val: EmpProceso.estado_proceso_secop.ilike(f"%{val}%"),
        'modalidad': lambda val: EmpProceso.modalidad.ilike(f"%{val}%"),
        'referencia_contrato': lambda val: EmpProceso.referencia_contrato == val,
        'referencia_proceso': lambda val: EmpProceso.referencia_proceso.ilike(f"%{val}%"),
        'valor_min': lambda val: EmpProceso.valor_total >= val,
        'valor_max': lambda val: EmpProceso.valor_total <= val,
        'fecha_desde': lambda val: EmpProceso.planeado >= val,
        'fecha_hasta': lambda val: EmpProceso.planeado <= val,
    }
    
    for key, value in filters.items():
        if value is not None and key in filter_map:
            conditions.append(filter_map[key](value))
    
    return conditions

class ProcesoService:
    """Servicio para operaciones de procesos usando funciones puras"""
    
    @staticmethod
    def create_proceso(db: Session, proceso_data: schemas.EmpProcesoCreate) -> Union['EmpProceso', List[str]]:
        """Crea un nuevo proceso validando datos"""
        from models import EmpProceso
        
        # Convertir a diccionario para funciones puras
        data_dict = proceso_data.model_dump()
        
        # Validar datos
        validation_errors = validate_proceso_data(data_dict)
        if validation_errors:
            return validation_errors
        
        # Transformar datos
        transformed_data = transform_contract_data(data_dict)  # Reutilizar función de transformación
        
        # Crear modelo
        new_proceso = EmpProceso(**transformed_data)
        
        try:
            db.add(new_proceso)
            db.commit()
            db.refresh(new_proceso)
            return new_proceso
        except Exception as e:
            db.rollback()
            return [f"Error al crear proceso: {str(e)}"]
    
    @staticmethod
    def update_proceso(
        db: Session, 
        proceso_id: int, 
        update_data: schemas.EmpProcesoUpdate
    ) -> Union['EmpProceso', List[str]]:
        """Actualiza un proceso existente"""
        from models import EmpProceso
        
        # Buscar proceso existente
        existing_proceso = db.query(EmpProceso).filter(
            EmpProceso.id == proceso_id
        ).first()
        
        if not existing_proceso:
            return ["Proceso no encontrado"]
        
        # Convertir datos de actualización
        update_dict = update_data.model_dump(exclude_unset=True)
        
        if not update_dict:
            return ["No hay datos para actualizar"]
        
        # Validar solo los campos que se van a actualizar
        validation_errors = validate_proceso_data(update_dict)
        if validation_errors:
            return validation_errors
        
        # Transformar datos
        transformed_data = transform_contract_data(update_dict)
        
        try:
            # Actualizar campos
            for field, value in transformed_data.items():
                if hasattr(existing_proceso, field):
                    setattr(existing_proceso, field, value)
            
            db.commit()
            db.refresh(existing_proceso)
            return existing_proceso
        except Exception as e:
            db.rollback()
            return [f"Error al actualizar proceso: {str(e)}"]
    
    @staticmethod
    def get_procesos_with_filters(
        db: Session,
        filters: Dict[str, Any],
        skip: int = 0,
        limit: int = 10,
        sort_by: str = 'created_at',
        order: str = 'desc'
    ) -> List['EmpProceso']:
        """Obtiene procesos con filtros usando funciones puras"""
        from models import EmpProceso
        
        base_query = db.query(EmpProceso)
        
        # Aplicar filtros
        conditions = generate_proceso_filters(filters)
        if conditions:
            base_query = base_query.filter(and_(*conditions))
        
        # Aplicar ordenamiento
        sort_map = {
            'created_at': EmpProceso.created_at,
            'valor_total': EmpProceso.valor_total,
            'planeado': EmpProceso.planeado,
            'referencia_proceso': EmpProceso.referencia_proceso,
        }
        
        column = sort_map.get(sort_by, EmpProceso.created_at)
        base_query = base_query.order_by(column.desc() if order == 'desc' else column.asc())
        
        # Aplicar paginación
        return base_query.offset(skip).limit(min(limit, 100)).all()
    
    @staticmethod
    def delete_proceso(db: Session, proceso_id: int) -> Union[bool, List[str]]:
        """Elimina un proceso"""
        from models import EmpProceso
        
        proceso = db.query(EmpProceso).filter(EmpProceso.id == proceso_id).first()
        if not proceso:
            return ["Proceso no encontrado"]
        
        try:
            db.delete(proceso)
            db.commit()
            return True
        except Exception as e:
            db.rollback()
            return [f"Error al eliminar proceso: {str(e)}"]
    
    @staticmethod
    def update_referencia_contrato(
        db: Session, 
        proceso_id: int, 
        referencia_contrato: str
    ) -> Union['EmpProceso', List[str]]:
        """Actualiza solo la referencia_contrato de un proceso"""
        from models import EmpProceso
        
        proceso = db.query(EmpProceso).filter(EmpProceso.id == proceso_id).first()
        if not proceso:
            return ["Proceso no encontrado"]
        
        try:
            proceso.referencia_contrato = referencia_contrato
            proceso.updated_at = datetime.utcnow()
            db.commit()
            db.refresh(proceso)
            return proceso
        except Exception as e:
            db.rollback()
            return [f"Error al actualizar referencia_contrato: {str(e)}"]
    
    @staticmethod
    def get_proceso_contrato_index(db: Session) -> List[Dict[str, Any]]:
        """Obtiene el índice de referencia_proceso y referencia_contrato"""
        from models import EmpProceso
        
        try:
            results = db.query(
                EmpProceso.id,
                EmpProceso.referencia_proceso,
                EmpProceso.referencia_contrato,
                EmpProceso.estado_proceso_secop,
                EmpProceso.valor_total
            ).filter(
                EmpProceso.referencia_contrato.isnot(None)
            ).order_by(EmpProceso.referencia_proceso).all()
            
            return [
                {
                    'proceso_id': r.id,
                    'referencia_proceso': r.referencia_proceso,
                    'referencia_contrato': r.referencia_contrato,
                    'estado_proceso': r.estado_proceso_secop,
                    'valor_total': r.valor_total
                }
                for r in results
            ]
        except Exception as e:
            return []
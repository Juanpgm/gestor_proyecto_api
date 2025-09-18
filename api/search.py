"""
Routers para búsquedas y filtros especializados
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from decimal import Decimal
from datetime import date

from config import get_db
from models import EmpContrato
import schemas
from services import ContractService
from error_handling import app_logger

search_router = APIRouter(prefix="/buscar", tags=["Búsqueda Avanzada"])

@search_router.get("/entidad/{nit}", response_model=List[schemas.EmpContratoSummary])
async def search_by_entity(
    nit: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """Buscar contratos por NIT de entidad"""
    app_logger.log_operation("search_by_entity", nit=nit)
    
    filters = {"nit_entidad": nit}
    contratos = ContractService.get_contracts_with_filters(
        db, filters, skip, limit
    )
    return contratos

@search_router.get("/proveedor/{proveedor}", response_model=List[schemas.EmpContratoSummary])
async def search_by_provider(
    proveedor: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """Buscar contratos por proveedor"""
    app_logger.log_operation("search_by_provider", proveedor=proveedor)
    
    filters = {"proveedor": proveedor}
    contratos = ContractService.get_contracts_with_filters(
        db, filters, skip, limit
    )
    return contratos

@search_router.get("/rango-valor", response_model=List[schemas.EmpContratoSummary])
async def search_by_value_range(
    valor_min: Optional[Decimal] = Query(None, ge=0, description="Valor mínimo"),
    valor_max: Optional[Decimal] = Query(None, ge=0, description="Valor máximo"),
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """Buscar contratos por rango de valor"""
    app_logger.log_operation("search_by_value_range", min=valor_min, max=valor_max)
    
    filters = {}
    if valor_min is not None:
        filters["valor_min"] = valor_min
    if valor_max is not None:
        filters["valor_max"] = valor_max
    
    contratos = ContractService.get_contracts_with_filters(
        db, filters, skip, limit
    )
    return contratos

@search_router.get("/rango-fechas", response_model=List[schemas.EmpContratoSummary])
async def search_by_date_range(
    fecha_desde: Optional[date] = Query(None, description="Fecha desde (YYYY-MM-DD)"),
    fecha_hasta: Optional[date] = Query(None, description="Fecha hasta (YYYY-MM-DD)"),
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """Buscar contratos por rango de fechas"""
    app_logger.log_operation("search_by_date_range", desde=fecha_desde, hasta=fecha_hasta)
    
    filters = {}
    if fecha_desde:
        filters["fecha_desde"] = fecha_desde
    if fecha_hasta:
        filters["fecha_hasta"] = fecha_hasta
    
    contratos = ContractService.get_contracts_with_filters(
        db, filters, skip, limit
    )
    return contratos

@search_router.get("/avanzada", response_model=List[schemas.EmpContratoSummary])
async def advanced_search(
    texto: Optional[str] = Query(None, description="Texto a buscar en objeto del contrato"),
    estado: Optional[str] = Query(None, description="Estado del contrato"),
    tipo_contrato: Optional[str] = Query(None, description="Tipo de contrato"),
    valor_min: Optional[Decimal] = Query(None, ge=0),
    valor_max: Optional[Decimal] = Query(None, ge=0),
    fecha_desde: Optional[date] = Query(None),
    fecha_hasta: Optional[date] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """Búsqueda avanzada con múltiples filtros"""
    app_logger.log_operation("advanced_search", texto=texto)
    
    filters = {
        "estado": estado,
        "tipo_contrato": tipo_contrato,
        "valor_min": valor_min,
        "valor_max": valor_max,
        "fecha_desde": fecha_desde,
        "fecha_hasta": fecha_hasta
    }
    
    # Filtro especial por texto en objeto del contrato
    if texto:
        contratos = db.query(EmpContrato).filter(
            EmpContrato.objeto_del_contrato.ilike(f"%{texto}%")
        )
        
        # Aplicar otros filtros manualmente
        if estado:
            contratos = contratos.filter(EmpContrato.estado_contrato.ilike(f"%{estado}%"))
        if tipo_contrato:
            contratos = contratos.filter(EmpContrato.tipo_de_contrato.ilike(f"%{tipo_contrato}%"))
        if valor_min:
            contratos = contratos.filter(EmpContrato.valor_del_contrato >= valor_min)
        if valor_max:
            contratos = contratos.filter(EmpContrato.valor_del_contrato <= valor_max)
        if fecha_desde:
            contratos = contratos.filter(EmpContrato.fecha_de_inicio_del_contrato >= fecha_desde)
        if fecha_hasta:
            contratos = contratos.filter(EmpContrato.fecha_de_fin_del_contrato <= fecha_hasta)
        
        return contratos.order_by(EmpContrato.created_at.desc()).offset(skip).limit(limit).all()
    
    # Usar servicio normal si no hay búsqueda de texto
    contratos = ContractService.get_contracts_with_filters(
        db, filters, skip, limit
    )
    return contratos
"""
Routers para endpoints de contratos
Separados por responsabilidad funcional
"""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from typing import List, Optional

from config import get_db
from models import EmpContrato
import schemas
from services import ContractService
from error_handling import app_logger

# Router para operaciones CRUD básicas
contracts_router = APIRouter(prefix="/contratos", tags=["Contratos"])

@contracts_router.get("/", response_model=List[schemas.EmpContratoSummary])
async def list_contracts(
    skip: int = Query(0, ge=0, description="Número de registros a saltar"),
    limit: int = Query(10, ge=1, le=100, description="Número máximo de registros"),
    estado: Optional[str] = Query(None, description="Filtrar por estado"),
    entidad: Optional[str] = Query(None, description="Filtrar por entidad"),
    proveedor: Optional[str] = Query(None, description="Filtrar por proveedor"),
    sort_by: str = Query("created_at", description="Campo para ordenar"),
    order: str = Query("desc", description="Orden: asc o desc"),
    db: Session = Depends(get_db)
):
    """Lista contratos con filtros avanzados"""
    app_logger.log_operation("list_contracts", skip=skip, limit=limit)
    
    filters = {
        "estado": estado,
        "entidad": entidad,
        "proveedor": proveedor
    }
    
    contratos = ContractService.get_contracts_with_filters(
        db, filters, skip, limit, sort_by, order
    )
    return contratos

@contracts_router.post("/", response_model=schemas.EmpContrato, status_code=status.HTTP_201_CREATED)
async def create_contract(
    contrato_data: schemas.EmpContratoCreate,
    db: Session = Depends(get_db)
):
    """Crear nuevo contrato"""
    app_logger.log_operation("create_contract", ref=contrato_data.referencia_del_contrato)
    
    result = ContractService.create_contract(db, contrato_data)
    
    if isinstance(result, list):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": "Errores de validación", "errors": result}
        )
    
    return result

@contracts_router.get("/{contrato_id}", response_model=schemas.EmpContrato)
async def get_contract(contrato_id: str, db: Session = Depends(get_db)):
    """Obtener contrato por ID"""
    contrato = db.query(EmpContrato).filter(EmpContrato.id_contrato == contrato_id).first()
    if not contrato:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Contrato {contrato_id} no encontrado"
        )
    return contrato

@contracts_router.put("/{contrato_id}", response_model=schemas.EmpContrato)
async def update_contract(
    contrato_id: str,
    contrato_data: schemas.EmpContratoUpdate,
    db: Session = Depends(get_db)
):
    """Actualizar contrato existente"""
    app_logger.log_operation("update_contract", id=contrato_id)
    
    result = ContractService.update_contract(db, contrato_id, contrato_data)
    
    if isinstance(result, list):
        if "no encontrado" in result[0]:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=result[0]
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": "Errores de validación", "errors": result}
        )
    
    return result

@contracts_router.get("/referencia/{referencia}", response_model=schemas.EmpContrato)
async def get_contract_by_reference(referencia: str, db: Session = Depends(get_db)):
    """Obtener contrato por referencia del contrato"""
    contrato = db.query(EmpContrato).filter(
        EmpContrato.referencia_del_contrato == referencia
    ).first()
    if not contrato:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Contrato con referencia {referencia} no encontrado"
        )
    return contrato

@contracts_router.get("/proceso/{referencia_proceso}", response_model=List[schemas.EmpContratoSummary])
async def get_contracts_by_proceso_reference(referencia_proceso: str, db: Session = Depends(get_db)):
    """Obtener contratos por referencia de proceso"""
    app_logger.log_operation("get_contracts_by_proceso", ref=referencia_proceso)
    
    contratos = db.query(EmpContrato).filter(
        EmpContrato.referencia_buscada == referencia_proceso
    ).all()
    
    if not contratos:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No se encontraron contratos con referencia de proceso {referencia_proceso}"
        )
    return contratos
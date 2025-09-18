"""
Routers para endpoints de procesos
CRUD completo para emp_procesos
"""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from decimal import Decimal
from datetime import date, datetime

from config import get_db
from models import EmpProceso
import schemas
from services import ProcesoService
from error_handling import app_logger

# Router para operaciones CRUD de procesos
procesos_router = APIRouter(prefix="/procesos", tags=["Procesos"])

@procesos_router.get("/", response_model=List[schemas.EmpProcesoSummary])
async def list_procesos(
    skip: int = Query(0, ge=0, description="Número de registros a saltar"),
    limit: int = Query(10, ge=1, le=100, description="Número máximo de registros"),
    banco: Optional[str] = Query(None, description="Filtrar por banco"),
    estado: Optional[str] = Query(None, description="Filtrar por estado"),
    modalidad: Optional[str] = Query(None, description="Filtrar por modalidad"),
    referencia_contrato: Optional[str] = Query(None, description="Filtrar por referencia de contrato"),
    referencia_proceso: Optional[str] = Query(None, description="Filtrar por referencia de proceso"),
    valor_min: Optional[Decimal] = Query(None, ge=0, description="Valor mínimo"),
    valor_max: Optional[Decimal] = Query(None, ge=0, description="Valor máximo"),
    fecha_desde: Optional[date] = Query(None, description="Fecha desde (planeado)"),
    fecha_hasta: Optional[date] = Query(None, description="Fecha hasta (planeado)"),
    sort_by: str = Query("created_at", description="Campo para ordenar"),
    order: str = Query("desc", description="Orden: asc o desc"),
    db: Session = Depends(get_db)
):
    """Lista procesos con filtros avanzados"""
    app_logger.log_operation("list_procesos", skip=skip, limit=limit)
    
    filters = {
        "banco": banco,
        "estado": estado,
        "modalidad": modalidad,
        "referencia_contrato": referencia_contrato,
        "referencia_proceso": referencia_proceso,
        "valor_min": valor_min,
        "valor_max": valor_max,
        "fecha_desde": fecha_desde,
        "fecha_hasta": fecha_hasta
    }
    
    procesos = ProcesoService.get_procesos_with_filters(
        db, filters, skip, limit, sort_by, order
    )
    return procesos

@procesos_router.post("/", response_model=schemas.EmpProceso, status_code=status.HTTP_201_CREATED)
async def create_proceso(
    proceso_data: schemas.EmpProcesoCreate,
    db: Session = Depends(get_db)
):
    """Crear nuevo proceso"""
    app_logger.log_operation("create_proceso", ref=proceso_data.referencia_proceso)
    
    result = ProcesoService.create_proceso(db, proceso_data)
    
    if isinstance(result, list):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": "Errores de validación", "errors": result}
        )
    
    app_logger.logger.info(f"✅ Proceso creado: {result.id}")
    return result

@procesos_router.get("/{proceso_id}", response_model=schemas.EmpProceso)
async def get_proceso(proceso_id: int, db: Session = Depends(get_db)):
    """Obtener proceso por ID"""
    proceso = db.query(EmpProceso).filter(EmpProceso.id == proceso_id).first()
    if not proceso:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Proceso {proceso_id} no encontrado"
        )
    return proceso

@procesos_router.put("/{proceso_id}", response_model=schemas.EmpProceso)
async def update_proceso(
    proceso_id: int,
    proceso_data: schemas.EmpProcesoUpdate,
    db: Session = Depends(get_db)
):
    """Actualizar proceso existente"""
    app_logger.log_operation("update_proceso", id=proceso_id)
    
    result = ProcesoService.update_proceso(db, proceso_id, proceso_data)
    
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
    
    app_logger.logger.info(f"✅ Proceso actualizado: {proceso_id}")
    return result

@procesos_router.delete("/{proceso_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_proceso(proceso_id: int, db: Session = Depends(get_db)):
    """Eliminar proceso"""
    app_logger.log_operation("delete_proceso", id=proceso_id)
    
    result = ProcesoService.delete_proceso(db, proceso_id)
    
    if isinstance(result, list):
        if "no encontrado" in result[0]:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=result[0]
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"message": "Error al eliminar", "errors": result}
        )
    
    app_logger.logger.info(f"✅ Proceso eliminado: {proceso_id}")

@procesos_router.put("/{proceso_id}/referencia-contrato", response_model=schemas.EmpProceso)
async def update_referencia_contrato(
    proceso_id: int,
    referencia_contrato: str = Query(..., description="Nueva referencia de contrato"),
    db: Session = Depends(get_db)
):
    """Actualizar solo la referencia_contrato de un proceso"""
    app_logger.log_operation("update_referencia_contrato", proceso_id=proceso_id, ref=referencia_contrato)
    
    result = ProcesoService.update_referencia_contrato(db, proceso_id, referencia_contrato)
    
    if isinstance(result, list):
        if "no encontrado" in result[0]:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=result[0]
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"message": "Error al actualizar referencia", "errors": result}
        )
    
    app_logger.logger.info(f"✅ Referencia contrato actualizada: {proceso_id} -> {referencia_contrato}")
    return result

@procesos_router.put("/referencia/{referencia_proceso}", response_model=schemas.EmpProceso)
async def update_estado_proceso_secop(
    referencia_proceso: str,
    estado: str = Query(..., description="Nuevo valor para estado_proceso_secop"),
    db: Session = Depends(get_db)
):
    """
    Actualizar únicamente el campo estado_proceso_secop de un proceso
    usando su referencia_proceso como identificador
    """
    app_logger.log_operation("update_estado_proceso_secop", ref=referencia_proceso, estado=estado)
    
    # Buscar el proceso por referencia
    proceso = db.query(EmpProceso).filter(
        EmpProceso.referencia_proceso == referencia_proceso
    ).first()
    
    if not proceso:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Proceso con referencia {referencia_proceso} no encontrado"
        )
    
    # Actualizar únicamente el estado_proceso_secop
    try:
        # Almacenar el valor anterior para logging
        estado_anterior = proceso.estado_proceso_secop
        
        # Actualizar solo el campo estado_proceso_secop
        proceso.estado_proceso_secop = estado
        proceso.updated_at = datetime.utcnow()
        
        db.commit()
        db.refresh(proceso)
        
        app_logger.logger.info(f"✅ Estado actualizado: {referencia_proceso} | {estado_anterior} -> {estado}")
        return proceso
        
    except Exception as e:
        db.rollback()
        app_logger.logger.error(f"❌ Error actualizando estado_proceso_secop: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al actualizar estado_proceso_secop: {str(e)}"
        )

@procesos_router.get("/referencia/{referencia_proceso}", response_model=schemas.EmpProceso)
async def get_proceso_by_reference(referencia_proceso: str, db: Session = Depends(get_db)):
    """Obtener proceso por referencia"""
    proceso = db.query(EmpProceso).filter(
        EmpProceso.referencia_proceso == referencia_proceso
    ).first()
    if not proceso:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Proceso con referencia {referencia_proceso} no encontrado"
        )
    return proceso

@procesos_router.get("/contrato/{referencia_contrato}", response_model=List[schemas.EmpProcesoSummary])
async def get_procesos_by_contrato(
    referencia_contrato: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """Obtener procesos asociados a un contrato específico"""
    app_logger.log_operation("get_procesos_by_contrato", ref=referencia_contrato)
    
    filters = {"referencia_contrato": referencia_contrato}
    procesos = ProcesoService.get_procesos_with_filters(
        db, filters, skip, limit
    )
    return procesos

@procesos_router.get("/banco/{banco_nombre}", response_model=List[schemas.EmpProcesoSummary])
async def get_procesos_by_banco(
    banco_nombre: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """Obtener procesos por banco"""
    app_logger.log_operation("get_procesos_by_banco", banco=banco_nombre)
    
    filters = {"banco": banco_nombre}
    procesos = ProcesoService.get_procesos_with_filters(
        db, filters, skip, limit
    )
    return procesos

# ============================================================================
# ENDPOINT ESPECIAL PARA ÍNDICE
# ============================================================================

@procesos_router.get("/index/proceso-contrato", response_model=List[schemas.ProcesoContratoIndex])
async def get_proceso_contrato_index(db: Session = Depends(get_db)):
    """
    Obtener índice de referencia_proceso y referencia_contrato
    Solo devuelve procesos que tienen referencia_contrato asignada
    """
    app_logger.log_operation("get_proceso_contrato_index")
    
    try:
        index_data = ProcesoService.get_proceso_contrato_index(db)
        
        # Convertir a schema
        result = [
            schemas.ProcesoContratoIndex(
                referencia_proceso=item['referencia_proceso'],
                referencia_contrato=item['referencia_contrato'],
                proceso_id=item['proceso_id'],
                estado_proceso=item['estado_proceso'],
                valor_total=item['valor_total']
            )
            for item in index_data
        ]
        
        app_logger.logger.info(f"✅ Índice generado: {len(result)} registros")
        return result
        
    except Exception as e:
        app_logger.logger.error(f"Error generando índice: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al generar índice: {str(e)}"
        )
"""
Routers para endpoints de estadísticas y reportes
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func

from config import get_db
from models import EmpContrato
from services import ContractService
from error_handling import app_logger

stats_router = APIRouter(prefix="/estadisticas", tags=["Estadísticas"])

@stats_router.get("/avanzadas")
async def get_advanced_statistics(db: Session = Depends(get_db)):
    """Estadísticas avanzadas usando servicios funcionales"""
    app_logger.log_operation("get_advanced_statistics")
    
    try:
        stats = ContractService.get_contract_statistics(db)
        return {
            "estadisticas_generales": {
                "total_contratos": stats['total_contracts'],
                "valor_total": float(stats['total_value']),
                "valor_promedio": float(stats['average_value']),
            },
            "distribucion_por_estado": [
                {"estado": estado, "cantidad": cantidad} 
                for estado, cantidad in stats['contracts_by_status']
            ]
        }
    except Exception as e:
        app_logger.logger.error(f"Error getting advanced statistics: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error al obtener estadísticas: {str(e)}")

@stats_router.get("/resumen")
async def get_summary_statistics(db: Session = Depends(get_db)):
    """Estadísticas resumidas (compatibilidad)"""
    try:
        total_contratos = db.query(EmpContrato).count()
        
        estados = db.query(
            EmpContrato.estado_contrato,
            func.count(EmpContrato.id_contrato).label('cantidad')
        ).group_by(EmpContrato.estado_contrato).all()
        
        valor_total = db.query(
            func.sum(EmpContrato.valor_del_contrato)
        ).scalar() or 0
        
        return {
            "total_contratos": total_contratos,
            "valor_total_contratos": float(valor_total),
            "contratos_por_estado": [{"estado": estado, "cantidad": cantidad} for estado, cantidad in estados]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al obtener estadísticas: {str(e)}")
# -*- coding: utf-8 -*-
"""
Flujo de Caja Operations
Operaciones para gestión de flujos de caja de empréstito
Basado en la lógica de context/flujo.py
"""

import pandas as pd
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List
import os
import tempfile

# Configurar logger
logger = logging.getLogger(__name__)

# Importar Firebase
try:
    from database.firebase_config import get_firestore_client
    FIREBASE_AVAILABLE = True
except ImportError:
    FIREBASE_AVAILABLE = False
    logger.warning("Firebase no disponible para flujo_caja_operations")

def process_flujo_caja_excel(file_content: bytes, filename: str) -> Dict[str, Any]:
    """
    Procesa archivo Excel de flujo de caja basado en la lógica de context/flujo.py
    
    Args:
        file_content: Contenido del archivo Excel en bytes
        filename: Nombre del archivo original
    
    Returns:
        Dict con resultado del procesamiento
    """
    try:
        # Crear archivo temporal para procesamiento
        with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as tmp_file:
            tmp_file.write(file_content)
            tmp_file_path = tmp_file.name
        
        try:
            # Leer el archivo Excel desde la sheet "CONTRATOS - Seguimiento"
            df = pd.read_excel(tmp_file_path, sheet_name="CONTRATOS - Seguimiento")
            
            # Definir las columnas base requeridas
            base_columns = ['Responsable', 'Organismo', 'Banco', 'BP Proyecto', 'Descripcion BP']
            
            # Verificar que existan las columnas base
            missing_columns = [col for col in base_columns if col not in df.columns]
            if missing_columns:
                return {
                    "success": False,
                    "error": f"Faltan columnas requeridas: {', '.join(missing_columns)}",
                    "details": f"El archivo debe contener las columnas: {', '.join(base_columns)}"
                }
            
            # Obtener todas las columnas que contengan "Desembolso" en su nombre
            columnas_desembolso = [col for col in df.columns if 'Desembolso' in col]
            
            # Validar que existan columnas de desembolso
            if not columnas_desembolso:
                return {
                    "success": False,
                    "error": "No se encontraron columnas de Desembolso en el archivo Excel",
                    "details": "El archivo debe contener al menos una columna con 'Desembolso' en el nombre"
                }
            
            # Seleccionar solo las columnas necesarias
            columnas_a_usar = base_columns + columnas_desembolso
            df = df[columnas_a_usar]
            
            # Procesar todas las columnas de desembolso usando melt
            df_melted = df.melt(
                id_vars=base_columns,  # Mantener las columnas base como identificadores
                value_vars=columnas_desembolso,  # Convertir todas las columnas de desembolso
                var_name='Columna_Desembolso',
                value_name='Monto_Desembolso'
            )
            
            # Extraer el mes de la columna de desembolso
            # Buscar patrones de mes en formato jul-25, ago-25, etc.
            df_melted['Mes'] = df_melted['Columna_Desembolso'].str.extract(r'(jul-25|ago-25|sep-25|oct-25|nov-25|dic-25|ene-26|feb-26|mar-26|abr-26|may-26|jun-26)')
            
            # Filtrar solo registros con mes válido y monto no nulo
            df_final = df_melted.dropna(subset=['Mes', 'Monto_Desembolso'])
            df_final = df_final[df_final['Monto_Desembolso'] != 0]  # Opcional: excluir montos en 0
            
            # Renombrar columnas para consistencia
            df_final = df_final.rename(columns={'Monto_Desembolso': 'Desembolso'})
            
            if df_final.empty:
                return {
                    "success": False,
                    "error": "No se encontraron datos válidos de desembolso",
                    "details": "Verificar que las columnas contengan fechas en formato jul-25, ago-25, etc."
                }
            
            # Crear columna Periodo en formato fecha (año-mes) para Looker Studio
            meses_map = {
                'jul-25': '2025-07-01',
                'ago-25': '2025-08-01', 
                'sep-25': '2025-09-01',
                'oct-25': '2025-10-01',
                'nov-25': '2025-11-01',
                'dic-25': '2025-12-01',
                'ene-26': '2026-01-01',
                'feb-26': '2026-02-01',
                'mar-26': '2026-03-01',
                'abr-26': '2026-04-01',
                'may-26': '2026-05-01',
                'jun-26': '2026-06-01'
            }
            
            df_final['Periodo'] = pd.to_datetime(df_final['Mes'].map(meses_map))
            
            # Reordenar columnas para incluir todas las columnas base
            columnas_ordenadas = ['Responsable', 'Organismo', 'Banco', 'BP Proyecto', 'Descripcion BP', 'Mes', 'Periodo', 'Desembolso', 'Columna_Desembolso']
            df_final = df_final[columnas_ordenadas]
            
            # Convertir a lista de diccionarios para Firebase
            records = []
            for _, row in df_final.iterrows():
                record = {
                    'responsable': str(row['Responsable']) if pd.notna(row['Responsable']) else '',
                    'organismo': str(row['Organismo']) if pd.notna(row['Organismo']) else '',
                    'banco': str(row['Banco']) if pd.notna(row['Banco']) else '',
                    'bp_proyecto': str(row['BP Proyecto']) if pd.notna(row['BP Proyecto']) else '',
                    'descripcion_bp': str(row['Descripcion BP']) if pd.notna(row['Descripcion BP']) else '',
                    'mes': str(row['Mes']),
                    'periodo': row['Periodo'].isoformat() if pd.notna(row['Periodo']) else None,
                    'desembolso': float(row['Desembolso']) if pd.notna(row['Desembolso']) else 0.0,
                    'columna_origen': str(row['Columna_Desembolso']),
                    'archivo_origen': filename,
                    'fecha_procesamiento': datetime.now().isoformat(),
                    'id_registro': f"{str(row['BP Proyecto'])}_{str(row['Banco'])}_{str(row['Mes'])}"
                }
                records.append(record)
            
            return {
                "success": True,
                "data": records,
                "summary": {
                    "total_registros": len(records),
                    "responsables_unicos": df_final['Responsable'].nunique(),
                    "organismos_unicos": df_final['Organismo'].nunique(),
                    "bancos_unicos": df_final['Banco'].nunique(),
                    "bp_proyectos_unicos": df_final['BP Proyecto'].nunique(),
                    "meses_procesados": df_final['Mes'].nunique(),
                    "columnas_desembolso_encontradas": len(columnas_desembolso),
                    "archivo_origen": filename,
                    "fecha_procesamiento": datetime.now().isoformat()
                },
                "metadata": {
                    "formato_periodo": "ISO 8601",
                    "campos_numericos": ["desembolso"],
                    "estructura_id": "bp_proyecto_banco_mes",
                    "columnas_base": base_columns,
                    "columnas_desembolso_procesadas": columnas_desembolso
                }
            }
            
        finally:
            # Limpiar archivo temporal
            try:
                os.unlink(tmp_file_path)
            except:
                pass
                
    except Exception as e:
        logger.error(f"Error procesando flujo de caja: {e}")
        return {
            "success": False,
            "error": f"Error procesando archivo Excel: {str(e)}",
            "details": "Verificar que el archivo tenga el formato correcto"
        }

async def save_flujo_caja_to_firebase(records: List[Dict[str, Any]], update_mode: str = "merge") -> Dict[str, Any]:
    """
    Guarda registros de flujo de caja en Firebase
    
    Args:
        records: Lista de registros a guardar
        update_mode: Modo de actualización (merge, replace, append)
    
    Returns:
        Dict con resultado de la operación
    """
    if not FIREBASE_AVAILABLE:
        return {
            "success": False,
            "error": "Firebase no disponible",
            "details": "No se pudo conectar a Firebase"
        }
    
    try:
        db = get_firestore_client()
        collection_name = "flujo_caja_emprestito"
        collection_ref = db.collection(collection_name)
        
        # Determinar estrategia según el modo
        if update_mode == "replace":
            # Eliminar todos los documentos existentes
            docs = collection_ref.limit(1000).stream()
            batch = db.batch()
            count = 0
            for doc in docs:
                batch.delete(doc.reference)
                count += 1
                if count % 500 == 0:  # Commit en lotes de 500
                    batch.commit()
                    batch = db.batch()
            if count % 500 != 0:
                batch.commit()
        
        # Agregar/actualizar nuevos registros
        successful_saves = 0
        failed_saves = 0
        updated_records = 0
        
        batch = db.batch()
        batch_count = 0
        
        for record in records:
            try:
                doc_id = record['id_registro']
                doc_ref = collection_ref.document(doc_id)
                
                if update_mode == "merge":
                    # Verificar si existe para determinar si es actualización
                    existing_doc = doc_ref.get()
                    if existing_doc.exists:
                        updated_records += 1
                    
                    batch.set(doc_ref, record, merge=True)
                elif update_mode == "append":
                    # Solo agregar si no existe
                    existing_doc = doc_ref.get()
                    if not existing_doc.exists:
                        batch.set(doc_ref, record)
                        successful_saves += 1
                    else:
                        # Ya existe, no hacer nada
                        continue
                else:  # replace
                    batch.set(doc_ref, record)
                
                batch_count += 1
                
                # Commit en lotes de 500
                if batch_count >= 500:
                    batch.commit()
                    batch = db.batch()
                    successful_saves += batch_count
                    batch_count = 0
                    
            except Exception as e:
                logger.error(f"Error guardando registro {record.get('id_registro', 'unknown')}: {e}")
                failed_saves += 1
        
        # Commit del último lote
        if batch_count > 0:
            batch.commit()
            successful_saves += batch_count
        
        return {
            "success": True,
            "message": f"Flujos de caja guardados exitosamente en {collection_name}",
            "summary": {
                "registros_procesados": len(records),
                "guardados_exitosamente": successful_saves,
                "actualizados": updated_records if update_mode == "merge" else 0,
                "errores": failed_saves,
                "modo_actualizacion": update_mode,
                "coleccion": collection_name
            },
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error guardando en Firebase: {e}")
        return {
            "success": False,
            "error": f"Error guardando en Firebase: {str(e)}",
            "details": "Error en la operación de base de datos"
        }

async def get_flujo_caja_from_firebase(filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Obtiene registros de flujo de caja desde Firebase
    
    Args:
        filters: Filtros opcionales para la consulta
    
    Returns:
        Dict con los registros encontrados
    """
    if not FIREBASE_AVAILABLE:
        return {
            "success": False,
            "error": "Firebase no disponible",
            "details": "No se pudo conectar a Firebase"
        }
    
    try:
        db = get_firestore_client()
        collection_name = "flujo_caja_emprestito"
        collection_ref = db.collection(collection_name)
        
        # Aplicar filtros si existen
        query = collection_ref
        
        if filters:
            if 'responsable' in filters:
                query = query.where('responsable', '==', filters['responsable'])
            if 'organismo' in filters:
                query = query.where('organismo', '==', filters['organismo'])
            if 'banco' in filters:
                query = query.where('banco', '==', filters['banco'])
            if 'bp_proyecto' in filters:
                query = query.where('bp_proyecto', '==', filters['bp_proyecto'])
            if 'mes' in filters:
                query = query.where('mes', '==', filters['mes'])
            if 'periodo_desde' in filters:
                query = query.where('periodo', '>=', filters['periodo_desde'])
            if 'periodo_hasta' in filters:
                query = query.where('periodo', '<=', filters['periodo_hasta'])
        
        # Agregar ordenamiento
        query = query.order_by('periodo')
        
        # Aplicar límite si se especifica
        if filters and 'limit' in filters:
            query = query.limit(filters['limit'])
        
        # Ejecutar consulta
        docs = query.stream()
        
        records = []
        for doc in docs:
            record = doc.to_dict()
            record['id'] = doc.id
            records.append(record)
        
        # Crear resumen
        if records:
            responsables = set(r.get('responsable', '') for r in records if r.get('responsable'))
            organismos = set(r.get('organismo', '') for r in records if r.get('organismo'))
            bancos = set(r.get('banco', '') for r in records if r.get('banco'))
            bp_proyectos = set(r.get('bp_proyecto', '') for r in records if r.get('bp_proyecto'))
            meses = set(r['mes'] for r in records)
            total_desembolso = sum(r.get('desembolso', 0) for r in records)
        else:
            responsables = set()
            organismos = set()
            bancos = set()
            bp_proyectos = set()
            meses = set()
            total_desembolso = 0
        
        return {
            "success": True,
            "data": records,
            "count": len(records),
            "collection": collection_name,
            "filters_applied": filters or {},
            "summary": {
                "responsables_unicos": len(responsables),
                "organismos_unicos": len(organismos),
                "bancos_unicos": len(bancos),
                "bp_proyectos_unicos": len(bp_proyectos),
                "meses_procesados": len(meses),
                "total_desembolso": total_desembolso
            },
            "metadata": {
                "responsables": sorted(list(responsables)),
                "organismos": sorted(list(organismos)),
                "bancos": sorted(list(bancos)),
                "bp_proyectos": sorted(list(bp_proyectos)),
                "meses": sorted(list(meses))
            },
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error obteniendo datos de Firebase: {e}")
        return {
            "success": False,
            "error": f"Error obteniendo datos: {str(e)}",
            "details": "Error en la consulta a la base de datos"
        }

# Variable de disponibilidad
FLUJO_CAJA_OPERATIONS_AVAILABLE = FIREBASE_AVAILABLE

# Exportar funciones
__all__ = [
    'process_flujo_caja_excel',
    'save_flujo_caja_to_firebase', 
    'get_flujo_caja_from_firebase',
    'FLUJO_CAJA_OPERATIONS_AVAILABLE'
]
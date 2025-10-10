# -*- coding: utf-8 -*-
"""
Operaciones de Empréstito - Version Limpia
Funciones para manejo de datos de empréstito con Firebase y SECOP
"""

import traceback
import json
import re
import os
import time
import asyncio
from typing import Dict, Any, List, Optional, Union
from datetime import datetime
import pandas as pd
from sodapy import Socrata

def serialize_datetime_objects(obj):
    """
    Convierte objetos datetime a strings ISO para serialización JSON
    """
    if isinstance(obj, dict):
        return {key: serialize_datetime_objects(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [serialize_datetime_objects(item) for item in obj]
    elif isinstance(obj, datetime):
        return obj.isoformat()
    else:
        return obj

async def procesar_proceso_individual(db_client, proceso_data, referencia_proceso, proceso_contractual, contratos_ref):
    """
    Procesa un proceso individual de empréstito:
    1. Busca contratos en SECOP
    2. Los transforma y guarda en contratos_emprestito
    3. Retorna resultado del procesamiento
    """
    resultado = {
        "exito": False,
        "contratos_encontrados": 0,
        "documentos_nuevos": 0,
        "documentos_actualizados": 0,
        "contratos_guardados": [],
        "error": None
    }
    
    try:
        logger.info(f"🔍 Buscando contratos en SECOP para proceso: {proceso_contractual}")
        
        # Buscar contratos que contengan el proceso_contractual y el NIT específico
        where_clause = f"proceso_de_compra LIKE '%{proceso_contractual}%' AND nit_entidad = '890399011'"
        
        with Socrata("www.datos.gov.co", None) as client:
            contratos_secop = client.get("jbjy-vk9h", limit=100, where=where_clause)
            
        resultado["contratos_encontrados"] = len(contratos_secop)
        logger.info(f"📊 Encontrados {len(contratos_secop)} contratos en SECOP para {proceso_contractual}")
        
        if not contratos_secop:
            resultado["exito"] = True  # No es error, simplemente no hay contratos
            logger.info(f"ℹ️  No se encontraron contratos para el proceso {proceso_contractual}")
            return resultado
        
        # Procesar cada contrato encontrado
        for j, contrato in enumerate(contratos_secop, 1):
            try:
                logger.info(f"🔄 Procesando contrato {j}/{len(contratos_secop)}: {contrato.get('referencia_del_contrato', 'N/A')}")
                
                # Validar datos mínimos requeridos
                if not contrato.get("referencia_del_contrato") and not contrato.get("id_contrato"):
                    logger.warning(f"⚠️ Contrato sin referencia válida, saltando...")
                    continue
                
                # Transformar contrato usando la lógica existente
                contrato_transformado = transformar_contrato_secop(contrato, proceso_data, referencia_proceso, proceso_contractual)
                
                # Verificar si ya existe este contrato usando campos únicos
                referencia_contrato = contrato_transformado.get("referencia_contrato", "")
                id_contrato = contrato_transformado.get("id_contrato", "")
                
                # Buscar duplicados por referencia_contrato o id_contrato + proceso_contractual
                existing_query = None
                if referencia_contrato:
                    existing_query = contratos_ref.where('referencia_contrato', '==', referencia_contrato).where('proceso_contractual', '==', proceso_contractual)
                elif id_contrato:
                    existing_query = contratos_ref.where('id_contrato', '==', id_contrato).where('proceso_contractual', '==', proceso_contractual)
                
                existing_docs = []
                if existing_query:
                    existing_docs = list(existing_query.limit(1).stream())
                
                if existing_docs:
                    # Actualizar documento existente
                    existing_doc = existing_docs[0]
                    contrato_transformado["fecha_actualizacion"] = datetime.now()
                    existing_doc.reference.update(contrato_transformado)
                    
                    resultado["documentos_actualizados"] += 1
                    logger.info(f"🔄 Contrato actualizado: {referencia_contrato or id_contrato}")
                else:
                    # Crear nuevo documento con UID automático de Firebase (como procesos_emprestito)
                    doc_ref = contratos_ref.add(contrato_transformado)
                    
                    resultado["documentos_nuevos"] += 1
                    logger.info(f"✅ Nuevo contrato guardado: {referencia_contrato or id_contrato}")
                
                # Agregar a resultados (serializado para JSON)
                contrato_serializable = serialize_datetime_objects(contrato_transformado)
                resultado["contratos_guardados"].append(contrato_serializable)
                
            except Exception as e:
                logger.error(f"❌ Error procesando contrato individual: {e}")
                continue
        
        resultado["exito"] = True
        logger.info(f"✅ Proceso individual completado: {resultado['contratos_encontrados']} encontrados, {resultado['documentos_nuevos']} nuevos, {resultado['documentos_actualizados']} actualizados")
        
    except Exception as e:
        resultado["error"] = str(e)
        logger.error(f"💥 Error en procesamiento individual de {referencia_proceso}: {e}")
    
    return resultado

def transformar_contrato_secop(contrato, proceso_data, referencia_proceso, proceso_contractual):
    """
    Transforma un contrato de SECOP al esquema de contratos_emprestito
    """
    # Convertir BPIN desde c_digo_bpin
    bpin_value = None
    if contrato.get("c_digo_bpin"):
        try:
            bpin_str = str(contrato["c_digo_bpin"]).replace(',', '').replace(' ', '').strip()
            if bpin_str and bpin_str != 'null' and bpin_str.lower() != 'none':
                bpin_value = int(float(bpin_str))
                logger.debug(f"✅ BPIN convertido: {contrato['c_digo_bpin']} → {bpin_value}")
        except (ValueError, TypeError) as e:
            logger.warning(f"⚠️ Error convertiendo BPIN '{contrato['c_digo_bpin']}': {e}")
            bpin_value = None
    
    # Convertir valor del contrato a entero
    valor_contrato = 0
    if contrato.get("valor_del_contrato"):
        try:
            valor_str = str(contrato["valor_del_contrato"]).replace(',', '').replace(' ', '').strip()
            if valor_str and valor_str != 'null':
                valor_contrato = int(float(valor_str))
        except (ValueError, TypeError):
            valor_contrato = 0
    
    # Procesar fechas al formato ISO 8601
    def process_date(date_field):
        if not contrato.get(date_field):
            return None
        try:
            fecha_str = str(contrato[date_field]).strip()
            if fecha_str and fecha_str != 'null' and fecha_str.lower() != 'none':
                # Intentar diferentes formatos de fecha
                fecha_formats = [
                    '%Y-%m-%dT%H:%M:%S.%f',  # 2025-08-27T00:00:00.000
                    '%Y-%m-%dT%H:%M:%S',     # 2025-08-27T00:00:00
                    '%Y-%m-%d',              # 2025-08-27
                    '%d/%m/%Y',              # 27/08/2025
                    '%m/%d/%Y',              # 08/27/2025
                    '%Y%m%d',                # 20250827
                ]
                
                for fmt in fecha_formats:
                    try:
                        fecha_parsed = datetime.strptime(fecha_str, fmt)
                        fecha_final = fecha_parsed.strftime('%Y-%m-%d')
                        logger.debug(f"📅 Fecha convertida {date_field}: '{fecha_str}' → '{fecha_final}'")
                        return fecha_final
                    except ValueError:
                        continue
                
                logger.warning(f"⚠️ No se pudo convertir fecha {date_field}: '{fecha_str}'")
            return None
        except (ValueError, TypeError):
            return None
    
    return {
        # Campos heredados del proceso de empréstito
        "referencia_proceso": referencia_proceso,
        "proceso_contractual": proceso_contractual,
        "nombre_centro_gestor": proceso_data.get('nombre_centro_gestor', ''),
        "banco": proceso_data.get('nombre_banco', ''),  # CORREGIDO: heredar desde 'nombre_banco'
        "bp": proceso_data.get('bp', ''),  # AGREGADO: heredar campo bp
        
        # Campos principales del contrato desde SECOP
        "referencia_contrato": contrato.get("referencia_del_contrato", ""),
        "id_contrato": contrato.get("id_contrato", ""),
        # ELIMINADO: "proceso_de_compra" - redundante con "proceso_contractual"
        "nombre_del_procedimiento": contrato.get("nombre_del_procedimiento", ""),
        "descripcion_proceso": contrato.get("descripci_n_del_procedimiento", ""),
        "objeto_contrato": contrato.get("objeto_del_contrato", ""),
        
        # Estado y modalidad
        "estado_del_contrato": contrato.get("estado_del_contrato", ""),
        "modalidad_contratacion": contrato.get("modalidad_de_contratacion", ""),
        "tipo_contrato": contrato.get("tipo_de_contrato", ""),
        
        # Valores monetarios
        # ELIMINADO: "valor_del_contrato" - redundante con "valor_contrato"
        "valor_contrato": valor_contrato,
        
        # Fechas en formato ISO 8601
        "fecha_firma_contrato": process_date("fecha_de_firma_del_contrato"),
        "fecha_firma": process_date("fecha_de_firma_del_contrato"),  # Alias
        "fecha_inicio_contrato": process_date("fecha_de_inicio_del_contrato"),
        "fecha_fin_contrato": process_date("fecha_de_fin_del_contrato"),
        
        # Entidades participantes
        "entidad_contratante": contrato.get("nombre_entidad", ""),
        "nombre_entidad": contrato.get("nombre_entidad", ""),  # Alias
        "contratista": contrato.get("nombre_del_contratista", ""),
        "nombre_del_contratista": contrato.get("nombre_del_contratista", ""),  # Alias
        
        # NITs
        "nit_entidad": contrato.get("nit_entidad", ""),
        "nit_contratista": contrato.get("nit_del_contratista", ""),
        
        # BPIN (código BPIN mapeado correctamente)
        "bpin": bpin_value,
        "codigo_bpin": bpin_value,  # Alias para compatibilidad
        
        # URLs y enlaces
        "urlproceso": contrato.get("urlproceso", ""),
        "link_proceso": contrato.get("urlproceso", ""),  # Alias
        
        # Metadatos de guardado
        "fecha_guardado": datetime.now(),
        "fuente_datos": "SECOP_API",
        "version_esquema": "1.1",
        "_dataset_source": "jbjy-vk9h"
    }

# Configurar logging
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Importar Firebase con manejo de errores
try:
    from database.firebase_config import get_firestore_client
    FIRESTORE_AVAILABLE = True
    logger.info("✅ Firebase configurado correctamente")
except ImportError as e:
    logger.error(f"❌ Error importando Firebase: {e}")
    FIRESTORE_AVAILABLE = False
    
    def get_firestore_client():
        return None


async def obtener_contratos_desde_proceso_contractual() -> Dict[str, Any]:
    """
    Obtener TODOS los registros de procesos_emprestito y buscar contratos en SECOP para cada uno,
    guardando los resultados en la colección contratos_emprestito
    
    OPTIMIZADO para procesamiento completo:
    - Procesa TODOS los procesos de empréstito automáticamente
    - Hereda campos: nombre_centro_gestor, banco (desde nombre_banco), bp
    - Mapea bpin desde c_digo_bpin de SECOP
    - Elimina campos redundantes (valor_del_contrato, proceso_de_compra)
    - Crea colección automáticamente si no existe
    """
    if not FIRESTORE_AVAILABLE:
        return {
            "success": False,
            "error": "Firebase no disponible"
        }
    
    inicio_tiempo = datetime.now()
    logger.info("🚀 Iniciando obtención completa de contratos desde SECOP (procesamiento automático de TODOS los procesos)...")
    
    try:
        db_client = get_firestore_client()
        if not db_client:
            return {
                "success": False,
                "error": "Error obteniendo cliente Firestore"
            }
        
        # 1. Obtener todos los registros de la colección procesos_emprestito
        procesos_ref = db_client.collection('procesos_emprestito')
        procesos_docs = list(procesos_ref.stream())
        
        if not procesos_docs:
            return {
                "success": False,
                "error": "No se encontraron procesos en la colección procesos_emprestito",
                "timestamp": datetime.now().isoformat()
            }
        
        # Variables de control
        total_procesos = len(procesos_docs)
        total_contratos_encontrados = 0
        total_documentos_nuevos = 0
        total_documentos_actualizados = 0
        todos_contratos_guardados = []
        procesos_con_errores = []
        
        # Procesar TODOS los procesos de empréstito
        procesos_a_procesar = procesos_docs
        
        logger.info(f"🔄 Procesamiento completo iniciado: {len(procesos_a_procesar)} procesos totales a procesar")
        
        # Crear la colección si no existe (Firestore la crea automáticamente al agregar el primer documento)
        contratos_ref = db_client.collection('contratos_emprestito')
        logger.info("📁 Referencia a colección 'contratos_emprestito' establecida (se creará automáticamente si no existe)")
        
        # 3. Procesar cada proceso de empréstito
        procesados_exitosos = 0
        
        for i, proceso_doc in enumerate(procesos_a_procesar, 1):
            logger.info(f"\n{'='*60}")
            logger.info(f"🎯 PROCESO {i}/{total_procesos} - PROCESAMIENTO INDIVIDUAL")
            logger.info(f"{'='*60}")
            
            try:
                proceso_data = proceso_doc.to_dict()
                referencia_proceso = proceso_data.get('referencia_proceso', '')
                proceso_contractual = proceso_data.get('proceso_contractual', '')
                
                if not referencia_proceso or not proceso_contractual:
                    logger.warning(f"❌ Proceso incompleto {i}/{total_procesos}: {proceso_doc.id}")
                    procesos_con_errores.append({
                        "id": proceso_doc.id,
                        "referencia_proceso": referencia_proceso or "N/A",
                        "error": "Datos incompletos (falta referencia_proceso o proceso_contractual)"
                    })
                    continue
                
                logger.info(f"📋 Procesando: {referencia_proceso} - {proceso_contractual}")
                logger.info(f"🏦 Centro Gestor: {proceso_data.get('nombre_centro_gestor', 'N/A')}")
                logger.info(f"💳 Banco: {proceso_data.get('nombre_banco', 'N/A')}")  # CORREGIDO: nombre_banco
                logger.info(f"🔢 BP: {proceso_data.get('bp', 'N/A')}")  # AGREGADO: mostrar BP
                
                # Procesar este proceso individual
                resultado_individual = await procesar_proceso_individual(
                    db_client, proceso_data, referencia_proceso, proceso_contractual, contratos_ref
                )
                
                if resultado_individual["exito"]:
                    procesados_exitosos += 1
                    total_documentos_nuevos += resultado_individual["documentos_nuevos"]
                    total_documentos_actualizados += resultado_individual["documentos_actualizados"]
                    total_contratos_encontrados += resultado_individual["contratos_encontrados"]
                    todos_contratos_guardados.extend(resultado_individual["contratos_guardados"])
                    
                    logger.info(f"✅ ÉXITO - Proceso {i}/{total_procesos}: {resultado_individual['contratos_encontrados']} contratos encontrados, {resultado_individual['documentos_nuevos']} nuevos, {resultado_individual['documentos_actualizados']} actualizados")
                else:
                    procesos_con_errores.append({
                        "id": proceso_doc.id,
                        "referencia_proceso": referencia_proceso,
                        "error": resultado_individual["error"]
                    })
                    logger.error(f"❌ ERROR - Proceso {i}/{total_procesos}: {resultado_individual['error']}")
                
                # Log de progreso
                tiempo_transcurrido = (datetime.now() - inicio_tiempo).total_seconds()
                logger.info(f"⏱️  Tiempo transcurrido: {tiempo_transcurrido:.1f}s | Exitosos: {procesados_exitosos}/{i}")
                
            except Exception as e:
                logger.error(f"💥 EXCEPCIÓN en proceso {i}/{total_procesos}: {e}")
                procesos_con_errores.append({
                    "id": proceso_doc.id,
                    "referencia_proceso": referencia_proceso if 'referencia_proceso' in locals() else "DESCONOCIDO",
                    "error": f"Excepción durante procesamiento: {str(e)}"
                })
                continue
        
        # Actualizar estadísticas finales
        procesos_procesados = procesados_exitosos
        total_duplicados_ignorados = 0  # Ya se cuenta en el procesamiento individual
        
        logger.info(f"\n🏁 PROCESAMIENTO COMPLETO FINALIZADO")
        logger.info(f"📊 Estadísticas finales:")
        logger.info(f"   - Total procesos en BD: {total_procesos}")
        logger.info(f"   - Procesados exitosamente: {procesados_exitosos}")
        logger.info(f"   - Procesos con errores: {len(procesos_con_errores)}")
        logger.info(f"   - Contratos encontrados: {total_contratos_encontrados}")
        logger.info(f"   - Documentos nuevos: {total_documentos_nuevos}")
        logger.info(f"   - Documentos actualizados: {total_documentos_actualizados}")
        
        # 4. Preparar respuesta final
        total_procesados = total_documentos_nuevos + total_documentos_actualizados + total_duplicados_ignorados
        
        return {
            "success": True,
            "message": f"✅ PROCESAMIENTO COMPLETO: {procesados_exitosos}/{total_procesos} procesos exitosos. Contratos: {total_procesados} total ({total_documentos_nuevos} nuevos, {total_documentos_actualizados} actualizados)",
            "resumen_procesamiento": {
                "total_procesos_en_bd": total_procesos,
                "procesos_procesados_exitosamente": procesados_exitosos,
                "procesos_con_errores": len(procesos_con_errores),
                "tasa_exito": f"{(procesados_exitosos/total_procesos*100):.1f}%" if total_procesos > 0 else "0%"
            },
            "criterios_busqueda": {
                "coleccion_origen": "procesos_emprestito",
                "filtro_secop": "nit_entidad = '890399011'",
                "procesamiento": "completo_automatico"
            },
            "resultados_secop": {
                "total_contratos_encontrados": total_contratos_encontrados,
                "total_contratos_procesados": total_procesados
            },
            "firebase_operacion": {
                "coleccion_destino": "contratos_emprestito",
                "documentos_nuevos": total_documentos_nuevos,
                "documentos_actualizados": total_documentos_actualizados,
                "duplicados_ignorados": total_duplicados_ignorados
            },
            "contratos_guardados": todos_contratos_guardados,
            "procesos_con_errores": procesos_con_errores,
            "tiempo_total": (datetime.now() - inicio_tiempo).total_seconds(),
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error general en obtener_contratos_desde_proceso_contractual: {e}")
        return {
            "success": False,
            "error": str(e),
            "message": "Error durante el procesamiento iterativo de contratos",
            "timestamp": datetime.now().isoformat()
        }


# Funciones adicionales requeridas por __init__.py
def verificar_proceso_existente(referencia_proceso: str) -> bool:
    """Verificar si un proceso existe en la colección procesos_emprestito"""
    if not FIRESTORE_AVAILABLE:
        return False
    try:
        db_client = get_firestore_client()
        if not db_client:
            return False
        docs = db_client.collection('procesos_emprestito').where('referencia_proceso', '==', referencia_proceso).limit(1).stream()
        return len(list(docs)) > 0
    except Exception:
        return False

def obtener_datos_secop(proceso_contractual: str) -> Dict[str, Any]:
    """Obtener datos de SECOP para un proceso específico"""
    return {"mensaje": "Función no implementada"}

def obtener_datos_tvec(proceso_contractual: str) -> Dict[str, Any]:
    """Obtener datos de TVEC para un proceso específico"""
    return {"mensaje": "Función no implementada"}

def detectar_plataforma(proceso_contractual: str) -> str:
    """Detectar la plataforma (SECOP/TVEC) basada en el proceso contractual"""
    return "SECOP"

def guardar_proceso_emprestito(datos: Dict[str, Any]) -> Dict[str, Any]:
    """Guardar un proceso de empréstito"""
    return {"mensaje": "Función no implementada"}

def guardar_orden_compra_emprestito(datos: Dict[str, Any]) -> Dict[str, Any]:
    """Guardar una orden de compra de empréstito"""
    return {"mensaje": "Función no implementada"}

def procesar_emprestito_completo(datos: Dict[str, Any]) -> Dict[str, Any]:
    """Procesar un empréstito completo"""
    return {"mensaje": "Función no implementada"}

def eliminar_proceso_emprestito(referencia_proceso: str) -> Dict[str, Any]:
    """Eliminar un proceso de empréstito"""
    return {"mensaje": "Función no implementada"}

def actualizar_proceso_emprestito(referencia_proceso: str, datos: Dict[str, Any]) -> Dict[str, Any]:
    """Actualizar un proceso de empréstito"""
    return {"mensaje": "Función no implementada"}

def obtener_codigos_contratos() -> Dict[str, Any]:
    """Obtener códigos de contratos"""
    return {"mensaje": "Función no implementada"}

def buscar_y_poblar_contratos_secop(proceso_contractual: str) -> Dict[str, Any]:
    """Buscar y poblar contratos desde SECOP"""
    return {"mensaje": "Función deprecada - usar obtener_contratos_desde_proceso_contractual"}

# Variable de disponibilidad
EMPRESTITO_OPERATIONS_AVAILABLE = FIRESTORE_AVAILABLE

# Funciones de disponibilidad
def get_emprestito_operations_status() -> Dict[str, Any]:
    """Obtener estado de las operaciones de empréstito"""
    return {
        "firestore_available": FIRESTORE_AVAILABLE,
        "operations_available": FIRESTORE_AVAILABLE,
        "supported_platforms": ["SECOP", "SECOP II", "SECOP I", "SECOP 2", "SECOP 1", "TVEC"],
        "collections": ["procesos_emprestito", "ordenes_compra_emprestito", "contratos_emprestito"]
    }
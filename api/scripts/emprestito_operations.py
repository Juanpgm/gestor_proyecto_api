# -*- coding: utf-8 -*-
"""
Operaciones de Gestión de Empréstito
====================================

Módulo funcional para manejo de procesos de empréstito con integración
a APIs externas (SECOP y TVEC) y validación de duplicados.

Enfoque funcional, simple y eficiente sin alterar el resto del código.
"""

import os
import logging
import json
import asyncio
from typing import Dict, Any, List, Optional, Union
from datetime import datetime
import pandas as pd
from sodapy import Socrata

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Importar Firebase con manejo de errores
try:
    from database.firebase_config import FIREBASE_AVAILABLE
    if FIREBASE_AVAILABLE:
        import firebase_admin
        from firebase_admin import firestore
        from google.cloud.firestore_v1._helpers import DatetimeWithNanoseconds
        FIRESTORE_AVAILABLE = True
        db = None  # Se inicializará cuando sea necesario
    else:
        FIRESTORE_AVAILABLE = False
        db = None
        DatetimeWithNanoseconds = None
except ImportError as e:
    logger.warning(f"Firebase no disponible: {e}")
    FIRESTORE_AVAILABLE = False
    db = None
    DatetimeWithNanoseconds = None


def get_firestore_client():
    """Obtener cliente de Firestore con inicialización lazy"""
    global db
    if db is None and FIRESTORE_AVAILABLE:
        try:
            db = firestore.client()
        except Exception as e:
            logger.error(f"Error inicializando cliente Firestore: {e}")
            return None
    return db


def clean_firebase_data_for_json(data):
    """Limpiar datos de Firebase para serialización JSON"""
    if isinstance(data, dict):
        cleaned = {}
        for key, value in data.items():
            cleaned[key] = clean_firebase_data_for_json(value)
        return cleaned
    elif isinstance(data, list):
        return [clean_firebase_data_for_json(item) for item in data]
    elif DatetimeWithNanoseconds and isinstance(data, DatetimeWithNanoseconds):
        return data.isoformat()
    elif isinstance(data, datetime):
        return data.isoformat()
    else:
        return data


async def verificar_proceso_existente(referencia_proceso: str) -> Dict[str, Any]:
    """
    Verificar si ya existe un proceso con la referencia_proceso dada
    buscando en las colecciones 'procesos_emprestito' y 'ordenes_compra_emprestito'
    """
    if not FIRESTORE_AVAILABLE:
        return {
            "existe": False,
            "coleccion": None,
            "documento": None,
            "error": "Firebase no disponible"
        }
    
    try:
        db_client = get_firestore_client()
        if not db_client:
            return {
                "existe": False,
                "coleccion": None,
                "documento": None,
                "error": "Error obteniendo cliente Firestore"
            }
        
        logger.info(f"Buscando referencia_proceso: {referencia_proceso}")
        
        # Buscar en procesos_emprestito
        procesos_ref = db_client.collection('procesos_emprestito')
        procesos_query = procesos_ref.where('referencia_proceso', '==', referencia_proceso).limit(1)
        procesos_docs = list(procesos_query.get())
        
        logger.info(f"Documentos encontrados en procesos_emprestito: {len(procesos_docs)}")
        
        if procesos_docs:
            doc = procesos_docs[0]
            return {
                "existe": True,
                "coleccion": "procesos_emprestito",
                "documento": clean_firebase_data_for_json(doc.to_dict()),
                "doc_id": doc.id
            }
        
        # Buscar en ordenes_compra_emprestito
        ordenes_ref = db_client.collection('ordenes_compra_emprestito')
        ordenes_query = ordenes_ref.where('referencia_proceso', '==', referencia_proceso).limit(1)
        ordenes_docs = list(ordenes_query.get())
        
        logger.info(f"Documentos encontrados en ordenes_compra_emprestito: {len(ordenes_docs)}")
        
        if ordenes_docs:
            doc = ordenes_docs[0]
            return {
                "existe": True,
                "coleccion": "ordenes_compra_emprestito",
                "documento": clean_firebase_data_for_json(doc.to_dict()),
                "doc_id": doc.id
            }
        
        return {
            "existe": False,
            "coleccion": None,
            "documento": None
        }
        
    except Exception as e:
        logger.error(f"Error verificando proceso existente: {e}")
        return {
            "existe": False,
            "coleccion": None,
            "documento": None,
            "error": str(e)
        }


async def obtener_datos_secop(referencia_proceso: str) -> Dict[str, Any]:
    """
    Obtener datos de un proceso desde la API del SECOP
    Optimizada para obtener solo los campos necesarios
    """
    try:
        # Configuración SECOP
        SECOP_DOMAIN = "www.datos.gov.co"
        DATASET_ID = "p6dx-8zbt"
        NIT_ENTIDAD_CALI = "890399011"
        
        # Cliente no autenticado para datos públicos
        client = Socrata(SECOP_DOMAIN, None, timeout=30)
        
        # Construir filtro para búsqueda específica
        where_clause = f"nit_entidad='{NIT_ENTIDAD_CALI}' AND referencia_del_proceso='{referencia_proceso}'"
        
        # Realizar consulta
        results = client.get(
            DATASET_ID,
            where=where_clause,
            limit=1  # Solo necesitamos un resultado
        )
        
        client.close()
        
        if not results:
            return {
                "success": False,
                "error": f"No se encontró el proceso {referencia_proceso} en SECOP"
            }
        
        # Tomar el primer resultado
        proceso_raw = results[0]
        
        # Log para debugging: ver todos los campos disponibles
        logger.info(f"Campos disponibles en SECOP para {referencia_proceso}: {list(proceso_raw.keys())}")
        logger.info(f"Valor de id_portafolio: '{proceso_raw.get('id_portafolio')}'")
        
        # Buscar el campo proceso_compra en diferentes variantes posibles
        proceso_compra = (
            proceso_raw.get("id_del_portafolio") or  # ✅ Este es el campo correcto según la API
            proceso_raw.get("id_portafolio") or 
            proceso_raw.get("proceso_compra") or 
            proceso_raw.get("id_del_proceso") or  # ✅ También podría ser útil
            proceso_raw.get("id_proceso") or
            proceso_raw.get("numero_proceso") or
            proceso_raw.get("codigo_proceso") or
            ""
        )
        
        logger.info(f"Proceso contractual encontrado: '{proceso_compra}'")
        
        # Mapear campos según especificaciones
        proceso_datos = {
            "referencia_proceso": proceso_raw.get("referencia_del_proceso", referencia_proceso),
            "proceso_contractual": proceso_compra,
            "nombre_proceso": proceso_raw.get("nombre_del_procedimiento", ""),
            "descripcion_proceso": proceso_raw.get("descripci_n_del_procedimiento", ""),
            "fase": proceso_raw.get("fase", ""),
            "fecha_publicacion": proceso_raw.get("fecha_de_publicacion_del", ""),  # ✅ Nombre correcto
            "estado_proceso": proceso_raw.get("estado_del_procedimiento", ""),
            "duracion": proceso_raw.get("duracion", ""),
            "unidad_duracion": proceso_raw.get("unidad_de_duracion", ""),
            "tipo_contrato": proceso_raw.get("tipo_de_contrato", ""),
            "nombre_unidad": proceso_raw.get("nombre_de_la_unidad_de", ""),  # ✅ Nombre correcto
            "modalidad_contratacion": proceso_raw.get("modalidad_de_contratacion", ""),
            "valor_publicacion": proceso_raw.get("precio_base", ""),
            "urlproceso": proceso_raw.get("urlproceso", ""),
            "adjudicado": proceso_raw.get("adjudicado", "")
        }
        
        return {
            "success": True,
            "data": proceso_datos
        }
        
    except Exception as e:
        logger.error(f"Error obteniendo datos de SECOP: {e}")
        return {
            "success": False,
            "error": str(e)
        }


async def obtener_datos_tvec(referencia_proceso: str) -> Dict[str, Any]:
    """
    Obtener datos de una orden desde la API de TVEC
    """
    try:
        # Cliente para API de TVEC
        client = Socrata("www.datos.gov.co", None, timeout=30)
        
        # Buscar por identificador_de_la_orden
        where_clause = f"identificador_de_la_orden='{referencia_proceso}'"
        
        # Realizar consulta en dataset TVEC
        results = client.get(
            "rgxm-mmea",  # Dataset ID de TVEC según documentación
            where=where_clause,
            limit=1
        )
        
        client.close()
        
        if not results:
            return {
                "success": False,
                "error": f"No se encontró la orden {referencia_proceso} en TVEC"
            }
        
        # Tomar el primer resultado
        orden_raw = results[0]
        
        # Mapear campos según especificaciones
        orden_datos = {
            "referencia_proceso": orden_raw.get("identificador_de_la_orden", referencia_proceso),
            "fecha_publicacion": orden_raw.get("fecha", ""),
            "fecha_vence": orden_raw.get("fecha_vence", ""),
            "estado": orden_raw.get("estado", ""),
            "agregacion": orden_raw.get("agregacion", ""),
            "valor_publicacion": orden_raw.get("total", "")
        }
        
        return {
            "success": True,
            "data": orden_datos
        }
        
    except Exception as e:
        logger.error(f"Error obteniendo datos de TVEC: {e}")
        return {
            "success": False,
            "error": str(e)
        }


def detectar_plataforma(plataforma: str) -> str:
    """
    Detectar el tipo de plataforma basado en el valor ingresado
    """
    plataforma_lower = plataforma.lower().strip()
    
    # Detectar SECOP (incluye todas las variantes)
    secop_variants = ['secop', 'secop ii', 'secop i', 'secop 2', 'secop 1']
    
    for variant in secop_variants:
        if variant in plataforma_lower:
            return "SECOP"
    
    # Detectar TVEC
    if 'tvec' in plataforma_lower:
        return "TVEC"
    
    # Por defecto, si no se detecta, asumir SECOP
    return "SECOP"


async def guardar_proceso_emprestito(datos: Dict[str, Any]) -> Dict[str, Any]:
    """
    Guardar proceso en la colección procesos_emprestito
    """
    if not FIRESTORE_AVAILABLE:
        return {
            "success": False,
            "error": "Firebase no disponible"
        }
    
    try:
        db_client = get_firestore_client()
        if not db_client:
            return {
                "success": False,
                "error": "Error obteniendo cliente Firestore"
            }
        
        # Agregar timestamp
        datos['fecha_creacion'] = datetime.now()
        datos['fecha_actualizacion'] = datetime.now()
        
        # Guardar en Firestore
        doc_ref = db_client.collection('procesos_emprestito').add(datos)
        
        return {
            "success": True,
            "doc_id": doc_ref[1].id,
            "message": "Proceso guardado exitosamente en procesos_emprestito"
        }
        
    except Exception as e:
        logger.error(f"Error guardando proceso: {e}")
        return {
            "success": False,
            "error": str(e)
        }


async def guardar_orden_compra_emprestito(datos: Dict[str, Any]) -> Dict[str, Any]:
    """
    Guardar orden de compra en la colección ordenes_compra_emprestito
    """
    if not FIRESTORE_AVAILABLE:
        return {
            "success": False,
            "error": "Firebase no disponible"
        }
    
    try:
        db_client = get_firestore_client()
        if not db_client:
            return {
                "success": False,
                "error": "Error obteniendo cliente Firestore"
            }
        
        # Agregar timestamp
        datos['fecha_creacion'] = datetime.now()
        datos['fecha_actualizacion'] = datetime.now()
        
        # Guardar en Firestore
        doc_ref = db_client.collection('ordenes_compra_emprestito').add(datos)
        
        return {
            "success": True,
            "doc_id": doc_ref[1].id,
            "message": "Orden guardada exitosamente en ordenes_compra_emprestito"
        }
        
    except Exception as e:
        logger.error(f"Error guardando orden: {e}")
        return {
            "success": False,
            "error": str(e)
        }


async def procesar_emprestito_completo(datos_iniciales: Dict[str, Any]) -> Dict[str, Any]:
    """
    Procesar datos de empréstito completo: verificar duplicados, obtener datos de API
    y guardar en la colección correspondiente
    """
    try:
        referencia_proceso = datos_iniciales.get("referencia_proceso", "").strip()
        plataforma = datos_iniciales.get("plataforma", "").strip()
        
        if not referencia_proceso:
            return {
                "success": False,
                "error": "referencia_proceso es requerida"
            }
        
        # 1. Verificar si ya existe el proceso
        verificacion = await verificar_proceso_existente(referencia_proceso)
        
        if verificacion.get("existe"):
            return {
                "success": False,
                "error": f"Ya existe un proceso con referencia {referencia_proceso}",
                "existing_data": {
                    "coleccion": verificacion.get("coleccion"),
                    "doc_id": verificacion.get("doc_id"),
                    "encontrado_en": verificacion.get("coleccion")
                },
                "duplicate": True
            }
        
        # 2. Detectar plataforma y obtener datos
        tipo_plataforma = detectar_plataforma(plataforma)
        
        datos_completos = datos_iniciales.copy()
        
        if tipo_plataforma == "SECOP":
            # Obtener datos de SECOP
            resultado_secop = await obtener_datos_secop(referencia_proceso)
            
            if not resultado_secop.get("success"):
                return {
                    "success": False,
                    "error": f"Error obteniendo datos de SECOP: {resultado_secop.get('error')}",
                    "plataforma_detectada": tipo_plataforma
                }
            
            # Combinar datos iniciales con datos de SECOP
            datos_completos.update(resultado_secop["data"])
            
            # Guardar en procesos_emprestito
            resultado_guardado = await guardar_proceso_emprestito(datos_completos)
            
            return {
                "success": resultado_guardado.get("success"),
                "error": resultado_guardado.get("error"),
                "data": clean_firebase_data_for_json(datos_completos),
                "doc_id": resultado_guardado.get("doc_id"),
                "coleccion": "procesos_emprestito",
                "plataforma_detectada": tipo_plataforma,
                "fuente_datos": "SECOP API"
            }
            
        elif tipo_plataforma == "TVEC":
            # Obtener datos de TVEC
            resultado_tvec = await obtener_datos_tvec(referencia_proceso)
            
            if not resultado_tvec.get("success"):
                return {
                    "success": False,
                    "error": f"Error obteniendo datos de TVEC: {resultado_tvec.get('error')}",
                    "plataforma_detectada": tipo_plataforma
                }
            
            # Combinar datos iniciales con datos de TVEC
            datos_completos.update(resultado_tvec["data"])
            
            # Guardar en ordenes_compra_emprestito
            resultado_guardado = await guardar_orden_compra_emprestito(datos_completos)
            
            return {
                "success": resultado_guardado.get("success"),
                "error": resultado_guardado.get("error"),
                "data": clean_firebase_data_for_json(datos_completos),
                "doc_id": resultado_guardado.get("doc_id"),
                "coleccion": "ordenes_compra_emprestito",
                "plataforma_detectada": tipo_plataforma,
                "fuente_datos": "TVEC API"
            }
        
        else:
            return {
                "success": False,
                "error": f"Plataforma no soportada: {plataforma}",
                "plataforma_detectada": tipo_plataforma
            }
            
    except Exception as e:
        logger.error(f"Error procesando empréstito: {e}")
        return {
            "success": False,
            "error": str(e)
        }


async def eliminar_proceso_emprestito(referencia_proceso: str) -> Dict[str, Any]:
    """
    Eliminar un proceso de empréstito por su referencia_proceso
    
    Args:
        referencia_proceso (str): Referencia del proceso a eliminar
        
    Returns:
        Dict[str, Any]: Resultado de la eliminación
    """
    try:
        if not FIRESTORE_AVAILABLE:
            return {
                "success": False,
                "error": "Firestore no disponible"
            }
        
        if not referencia_proceso or not referencia_proceso.strip():
            return {
                "success": False,
                "error": "referencia_proceso es requerida"
            }
        
        referencia_proceso = referencia_proceso.strip()
        db = get_firestore_client()
        
        # Buscar en ambas colecciones
        proceso_encontrado = None
        coleccion_origen = None
        doc_id = None
        
        # Buscar en procesos_emprestito (SECOP)
        procesos_ref = db.collection('procesos_emprestito')
        query_procesos = procesos_ref.where('referencia_proceso', '==', referencia_proceso).limit(1)
        procesos_docs = query_procesos.get()
        
        if procesos_docs:
            proceso_encontrado = procesos_docs[0].to_dict()
            coleccion_origen = 'procesos_emprestito'
            doc_id = procesos_docs[0].id
        else:
            # Buscar en ordenes_compra_emprestito (TVEC)
            ordenes_ref = db.collection('ordenes_compra_emprestito')
            query_ordenes = ordenes_ref.where('referencia_proceso', '==', referencia_proceso).limit(1)
            ordenes_docs = query_ordenes.get()
            
            if ordenes_docs:
                proceso_encontrado = ordenes_docs[0].to_dict()
                coleccion_origen = 'ordenes_compra_emprestito'
                doc_id = ordenes_docs[0].id
        
        # Si no se encuentra el proceso
        if not proceso_encontrado:
            return {
                "success": False,
                "error": f"No se encontró ningún proceso con referencia_proceso: {referencia_proceso}",
                "referencia_proceso": referencia_proceso,
                "colecciones_buscadas": ["procesos_emprestito", "ordenes_compra_emprestito"]
            }
        
        # Eliminar el documento
        doc_ref = db.collection(coleccion_origen).document(doc_id)
        doc_ref.delete()
        
        logger.info(f"Proceso eliminado exitosamente: {referencia_proceso} de {coleccion_origen}")
        
        # Limpiar datos de Firebase para serialización JSON
        proceso_limpio = clean_firebase_data_for_json(proceso_encontrado)
        
        return {
            "success": True,
            "message": f"Proceso eliminado exitosamente",
            "referencia_proceso": referencia_proceso,
            "coleccion": coleccion_origen,
            "documento_id": doc_id,
            "proceso_eliminado": {
                "referencia_proceso": proceso_limpio.get('referencia_proceso'),
                "nombre_centro_gestor": proceso_limpio.get('nombre_centro_gestor'),
                "nombre_banco": proceso_limpio.get('nombre_banco'),
                "plataforma": proceso_limpio.get('plataforma'),
                "fecha_creacion": proceso_limpio.get('fecha_creacion')
            },
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error eliminando proceso {referencia_proceso}: {e}")
        return {
            "success": False,
            "error": str(e),
            "referencia_proceso": referencia_proceso
        }


# Funciones de disponibilidad
def get_emprestito_operations_status() -> Dict[str, Any]:
    """Obtener estado de las operaciones de empréstito"""
    return {
        "firestore_available": FIRESTORE_AVAILABLE,
        "operations_available": FIRESTORE_AVAILABLE,
        "supported_platforms": ["SECOP", "SECOP II", "SECOP I", "SECOP 2", "SECOP 1", "TVEC"],
        "collections": ["procesos_emprestito", "ordenes_compra_emprestito"]
    }


# Constantes de disponibilidad
EMPRESTITO_OPERATIONS_AVAILABLE = FIRESTORE_AVAILABLE
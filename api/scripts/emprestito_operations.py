"""
Scripts para manejo de Procesos de Empréstito - Versión Limpia
Solo funcionalidades esenciales habilitadas
"""

import logging
import asyncio
from typing import Dict, List, Any, Optional
from datetime import datetime
import pandas as pd
import re
from database.firebase_config import get_firestore_client

# Configurar logging primero
logger = logging.getLogger(__name__)

# Importar utilidad S3 para documentos
try:
    from api.utils.s3_document_manager import S3DocumentManager, validate_document_file
    S3_AVAILABLE = True
    logger.info("✅ S3DocumentManager disponible - funcionalidad de carga de documentos habilitada")
except ImportError as e:
    S3_AVAILABLE = False
    logger.warning(f"⚠️ S3DocumentManager no disponible - funcionalidad de carga de documentos deshabilitada: {e}")

# Variables de disponibilidad
FIRESTORE_AVAILABLE = True
try:
    # Verificar disponibilidad de Firestore
    get_firestore_client()
except Exception as e:
    FIRESTORE_AVAILABLE = False
    logger.warning(f"Firebase no disponible: {e}")

async def get_procesos_emprestito_all() -> Dict[str, Any]:
    """Obtener todos los registros de la colección procesos_emprestito"""
    try:
        # Intentar obtener el cliente de Firestore siempre, sin depender de variable global
        try:
            db = get_firestore_client()
        except Exception as e:
            return {
                "success": False,
                "error": f"No se pudo inicializar Firestore: {str(e)}",
                "data": [],
                "count": 0
            }

        if db is None:
            return {"success": False, "error": "No se pudo conectar a Firestore (cliente es None)", "data": [], "count": 0}

        try:
            collection_ref = db.collection('procesos_emprestito')
            docs = collection_ref.stream()
        except Exception as e:
            return {
                "success": False,
                "error": f"Error accediendo a la colección procesos_emprestito: {str(e)}",
                "data": [],
                "count": 0
            }

        procesos_data = []
        try:
            for doc in docs:
                doc_data = doc.to_dict()
                doc_data['id'] = doc.id  # Agregar ID del documento
                # Limpiar datos de Firebase para serialización JSON
                doc_data_clean = serialize_datetime_objects(doc_data)
                procesos_data.append(doc_data_clean)
        except Exception as e:
            return {
                "success": False,
                "error": f"Error procesando documentos de la colección: {str(e)}",
                "data": [],
                "count": 0
            }

        return {
            "success": True,
            "data": procesos_data,
            "count": len(procesos_data),
            "collection": "procesos_emprestito",
            "timestamp": datetime.now().isoformat(),
            "message": f"Se obtuvieron {len(procesos_data)} procesos de empréstito exitosamente"
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Error inesperado en get_procesos_emprestito_all: {str(e)}",
            "data": [],
            "count": 0
        }

def serialize_datetime_objects(obj):
    """Serializar objetos datetime para JSON"""
    if isinstance(obj, dict):
        return {key: serialize_datetime_objects(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [serialize_datetime_objects(item) for item in obj]
    elif hasattr(obj, 'timestamp'):  # Firebase Timestamp
        return obj.strftime('%Y-%m-%d %H:%M:%S')
    elif isinstance(obj, datetime):
        return obj.strftime('%Y-%m-%d %H:%M:%S')
    else:
        return obj

async def restaurar_procesos_emprestito_usando_post() -> Dict[str, Any]:
    """
    FUNCIÓN PARA RESTAURAR PROCESOS USANDO EL POST /emprestito/cargar-proceso
    
    Esta función toma todos los procesos existentes en la colección procesos_emprestito,
    extrae los campos que necesita el POST /emprestito/cargar-proceso, y los procesa
    usando la función procesar_emprestito_completo para restaurarlos a su formato original.
    
    Campos extraídos para el POST:
    - referencia_proceso (obligatorio)
    - nombre_centro_gestor (obligatorio) 
    - nombre_banco (obligatorio)
    - plataforma (obligatorio)
    - bp (opcional)
    - nombre_resumido_proceso (opcional)
    - id_paa (opcional)
    - valor_proyectado (opcional)
    """
    logger.info("🔄 Iniciando restauración de procesos usando POST /emprestito/cargar-proceso...")
    
    try:
        if not FIRESTORE_AVAILABLE:
            return {"success": False, "error": "Firebase no disponible"}
        
        db = get_firestore_client()
        if db is None:
            return {"success": False, "error": "No se pudo conectar a Firestore"}
        
        # Obtener todos los procesos actuales
        collection_ref = db.collection('procesos_emprestito')
        procesos_docs = list(collection_ref.stream())
        
        if not procesos_docs:
            logger.warning("⚠️ No se encontraron procesos para restaurar")
            return {
                "success": True,
                "message": "No hay procesos para restaurar", 
                "total_procesos": 0,
                "restaurados": 0,
                "errores": []
            }
        
        logger.info(f"📊 Encontrados {len(procesos_docs)} procesos para restaurar usando POST")
        
        total_procesos = len(procesos_docs)
        restaurados = 0
        errores = []
        procesos_restaurados = []
        
        for doc in procesos_docs:
            doc_id = doc.id
            proceso_data = doc.to_dict()
            
            # Validar campos obligatorios del POST
            referencia_proceso = proceso_data.get('referencia_proceso')
            nombre_centro_gestor = proceso_data.get('nombre_centro_gestor')
            nombre_banco = proceso_data.get('nombre_banco')
            plataforma = proceso_data.get('plataforma')
            
            if not referencia_proceso:
                error_msg = f"❌ Proceso {doc_id} no tiene 'referencia_proceso' (obligatorio)"
                logger.warning(error_msg)
                errores.append(error_msg)
                continue
                
            if not nombre_centro_gestor:
                error_msg = f"❌ Proceso {referencia_proceso} no tiene 'nombre_centro_gestor' (obligatorio)"
                logger.warning(error_msg)
                errores.append(error_msg)
                continue
                
            if not nombre_banco:
                error_msg = f"❌ Proceso {referencia_proceso} no tiene 'nombre_banco' (obligatorio)"
                logger.warning(error_msg)
                errores.append(error_msg)
                continue
                
            if not plataforma:
                plataforma = "SECOP II"  # Valor por defecto
                logger.info(f"⚠️ Proceso {referencia_proceso} no tiene 'plataforma', usando default: SECOP II")
            
            try:
                logger.info(f"🔄 Procesando con POST: {referencia_proceso}")
                
                # Preparar datos exactamente como los espera el POST /emprestito/cargar-proceso
                datos_post = {
                    "referencia_proceso": referencia_proceso,
                    "nombre_centro_gestor": nombre_centro_gestor,
                    "nombre_banco": nombre_banco,
                    "plataforma": plataforma,
                    "bp": proceso_data.get("bp"),  # Opcional
                    "nombre_resumido_proceso": proceso_data.get("nombre_resumido_proceso"),  # Opcional
                    "id_paa": proceso_data.get("id_paa"),  # Opcional
                    "valor_proyectado": proceso_data.get("valor_proyectado")  # Opcional
                }
                
                # Limpiar valores None de los campos opcionales (como hace Form en FastAPI)
                datos_post_clean = {k: v for k, v in datos_post.items() if v is not None}
                
                logger.info(f"📝 Datos para POST: {datos_post_clean}")
                
                # Llamar a la función del POST (procesar_emprestito_completo)
                resultado = await procesar_emprestito_completo(datos_post_clean)
                
                if resultado.get("success"):
                    restaurados += 1
                    procesos_restaurados.append({
                        "referencia_proceso": referencia_proceso,
                        "doc_id_original": doc_id,
                        "doc_id_nuevo": resultado.get("doc_id"),
                        "datos_procesados": datos_post_clean
                    })
                    logger.info(f"✅ POST exitoso para proceso {referencia_proceso}")
                else:
                    error_msg = f"❌ Error en POST para proceso {referencia_proceso}: {resultado.get('error')}"
                    logger.error(error_msg)
                    errores.append(error_msg)
                
            except Exception as e:
                error_msg = f"❌ Excepción procesando proceso {referencia_proceso}: {str(e)}"
                logger.error(error_msg)
                errores.append(error_msg)
        
        resultado = {
            "success": True,
            "message": f"Restauración usando POST completada: {restaurados}/{total_procesos} procesos restaurados",
            "total_procesos": total_procesos,
            "restaurados": restaurados,
            "errores": errores,
            "procesos_restaurados": procesos_restaurados,
            "metodo_usado": "POST /emprestito/cargar-proceso",
            "funcion_llamada": "procesar_emprestito_completo",
            "campos_obligatorios": ["referencia_proceso", "nombre_centro_gestor", "nombre_banco", "plataforma"],
            "campos_opcionales": ["bp", "nombre_resumido_proceso", "id_paa", "valor_proyectado"],
            "timestamp": datetime.now().isoformat()
        }
        
        logger.info(f"🏁 {resultado['message']}")
        return resultado
        
    except Exception as e:
        logger.error(f"❌ Error en restauración usando POST: {str(e)}")
        return {
            "success": False,
            "error": f"Error en restauración usando POST: {str(e)}"
        }


async def actualizar_procesos_emprestito_desde_secop() -> Dict[str, Any]:
    """
    FUNCIÓN TEMPORALMENTE DESHABILITADA
    
    El endpoint PUT /actualizar_procesos_emprestito está deshabilitado por mantenimiento.
    Esta función será reimplementada cuando sea necesario.
    """
    logger.info("⚠️ Función actualizar_procesos_emprestito_desde_secop temporalmente deshabilitada")
    
    return {
        "success": False,
        "message": "⚠️ Función temporalmente deshabilitada",
        "error": "El endpoint PUT /actualizar_procesos_emprestito está deshabilitado por mantenimiento",
        "estadisticas": {
            "total_procesos": 0,
            "procesos_actualizados": 0,
            "procesos_sin_cambios": 0,
            "procesos_no_encontrados_secop": 0,
            "procesos_con_errores": 0,
            "tasa_actualizacion": "0.0%"
        },
        "detalles_actualizaciones": [],
        "procesos_con_errores": [],
        "configuracion": {
            "dataset_secop": "p6dx-8zbt",
            "filtro_aplicado": "nit_entidad = '890399011'",
            "campos_preservados": ["bp", "nombre_banco", "nombre_centro_gestor", "id_paa", "referencia_proceso", "plataforma"],
            "campos_comparados": ["nombre_proceso", "descripcion_proceso", "estado_proceso", "modalidad_contratacion", "etapa"]
        },
        "tiempo_total_segundos": 0,
        "timestamp": datetime.now().isoformat(),
        "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

# Variable de disponibilidad
EMPRESTITO_OPERATIONS_AVAILABLE = FIRESTORE_AVAILABLE

def get_emprestito_operations_status() -> Dict[str, Any]:
    """Obtener estado de las operaciones de empréstito"""
    return {
        "firestore_available": FIRESTORE_AVAILABLE,
        "operations_available": FIRESTORE_AVAILABLE,
        "supported_platforms": ["SECOP", "SECOP II", "SECOP I", "SECOP 2", "SECOP 1", "TVEC"],
        "collections": ["procesos_emprestito", "ordenes_compra_emprestito", "contratos_emprestito"]
    }


# ============================================================================
# FUNCIONES STUB (Para compatibilidad con importaciones existentes)
# ============================================================================

async def verificar_proceso_existente(referencia_proceso: str) -> Dict[str, Any]:
    """
    Verifica si ya existe un proceso con la referencia especificada en cualquiera 
    de las colecciones de empréstito.
    """
    try:
        if not FIRESTORE_AVAILABLE:
            return {"existe": False, "error": "Firebase no disponible"}
        
        db = get_firestore_client()
        if db is None:
            return {"existe": False, "error": "No se pudo conectar a Firestore"}
        
        # Buscar en colección procesos_emprestito (SECOP)
        procesos_ref = db.collection('procesos_emprestito')
        procesos_query = procesos_ref.where('referencia_proceso', '==', referencia_proceso).limit(1)
        procesos_docs = list(procesos_query.stream())
        
        if procesos_docs:
            doc = procesos_docs[0]
            return {
                "existe": True,
                "coleccion": "procesos_emprestito",
                "documento": doc.to_dict(),
                "doc_id": doc.id
            }
        
        # Buscar en colección ordenes_compra_emprestito (TVEC)
        ordenes_ref = db.collection('ordenes_compra_emprestito')
        ordenes_query = ordenes_ref.where('referencia_proceso', '==', referencia_proceso).limit(1)
        ordenes_docs = list(ordenes_query.stream())
        
        if ordenes_docs:
            doc = ordenes_docs[0]
            return {
                "existe": True,
                "coleccion": "ordenes_compra_emprestito",
                "documento": doc.to_dict(),
                "doc_id": doc.id
            }
        
        return {"existe": False}
        
    except Exception as e:
        logger.error(f"Error verificando proceso existente: {str(e)}")
        return {"existe": False, "error": str(e)}

async def obtener_datos_secop(referencia_proceso: str, nit_entidad: Optional[str] = None) -> Dict[str, Any]:
    """
    Obtener datos de un proceso desde la API del SECOP
    Optimizada para obtener solo los campos necesarios
    
    Args:
        referencia_proceso: Referencia del proceso a buscar
        nit_entidad: NIT de la entidad (opcional). Si no se proporciona, busca sin filtro de NIT.
    """
    try:
        # Importar Socrata aquí para evitar errores de importación si no está disponible
        from sodapy import Socrata
        
        # Configuración SECOP
        SECOP_DOMAIN = "www.datos.gov.co"
        DATASET_ID = "p6dx-8zbt"
        NIT_ENTIDAD_CALI = "890399011"

        # Cliente no autenticado para datos públicos
        client = Socrata(SECOP_DOMAIN, None, timeout=30)

        # Construir filtro para búsqueda específica
        # Si se proporciona NIT, filtrar por él. Si no, buscar sin filtro de NIT
        if nit_entidad:
            where_clause = f"nit_entidad='{nit_entidad}' AND referencia_del_proceso='{referencia_proceso}'"
            logger.info(f"🔍 Buscando proceso {referencia_proceso} con NIT {nit_entidad}")
        else:
            where_clause = f"referencia_del_proceso='{referencia_proceso}'"
            logger.info(f"🔍 Buscando proceso {referencia_proceso} sin filtro de NIT")

        # Realizar consulta
        results = client.get(
            DATASET_ID,
            where=where_clause,
            limit=1  # Solo necesitamos un resultado
        )

        client.close()

        if not results:
            # Si no se encontró con el NIT proporcionado (o sin NIT), intentar sin restricción
            if nit_entidad:
                logger.warning(f"⚠️ No se encontró el proceso {referencia_proceso} con NIT {nit_entidad}, reintentando sin filtro de NIT...")
                return await obtener_datos_secop(referencia_proceso, nit_entidad=None)
            
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

        # Convertir valor_publicacion a entero
        valor_publicacion = 0
        if proceso_raw.get("precio_base"):
            try:
                valor_str = str(proceso_raw["precio_base"]).replace(',', '').replace(' ', '').strip()
                if valor_str and valor_str != 'null' and valor_str.lower() != 'none':
                    valor_publicacion = int(float(valor_str))
                    logger.debug(f"✅ Valor publicación convertido: '{proceso_raw['precio_base']}' → {valor_publicacion}")
            except (ValueError, TypeError) as e:
                logger.warning(f"⚠️ Error convertiendo valor_publicacion '{proceso_raw['precio_base']}': {e}")
                valor_publicacion = 0

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
            "valor_publicacion": valor_publicacion,
            "urlproceso": proceso_raw.get("urlproceso", ""),
            "adjudicado": proceso_raw.get("adjudicado", "")
        }

        return {
            "success": True,
            "data": proceso_datos
        }

    except ImportError:
        logger.error("sodapy no está instalado. Instala con: pip install sodapy")
        return {
            "success": False,
            "error": "sodapy no está disponible. Instala con: pip install sodapy"
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
        # Importar Socrata aquí para evitar errores de importación si no está disponible
        from sodapy import Socrata
        
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

        # Convertir valor_publicacion a entero
        valor_publicacion = 0
        if orden_raw.get("total"):
            try:
                valor_str = str(orden_raw["total"]).replace(',', '').replace(' ', '').strip()
                if valor_str and valor_str != 'null' and valor_str.lower() != 'none':
                    valor_publicacion = int(float(valor_str))
                    logger.debug(f"✅ Valor publicación TVEC convertido: '{orden_raw['total']}' → {valor_publicacion}")
            except (ValueError, TypeError) as e:
                logger.warning(f"⚠️ Error convertiendo valor_publicacion TVEC '{orden_raw['total']}': {e}")
                valor_publicacion = 0

        # Extraer nombre_banco de agregacion si está disponible
        agregacion = orden_raw.get("agregacion", "")
        nombre_banco = orden_raw.get("nombre_banco", "")
        
        # Si nombre_banco no está disponible, usar agregacion como banco
        # (ya que agregacion puede contener información del banco financiador)
        if not nombre_banco and agregacion:
            nombre_banco = agregacion
        
        # Mapear campos según especificaciones
        orden_datos = {
            "referencia_proceso": orden_raw.get("identificador_de_la_orden", referencia_proceso),
            "fecha_publicacion": orden_raw.get("fecha", ""),
            "fecha_vence": orden_raw.get("fecha_vence", ""),
            "estado": orden_raw.get("estado", ""),
            "agregacion": agregacion,
            "nombre_banco": nombre_banco,  # Agregar nombre_banco al resultado
            "valor_publicacion": valor_publicacion
        }

        return {
            "success": True,
            "data": orden_datos
        }

    except ImportError:
        logger.error("sodapy no está instalado. Instala con: pip install sodapy")
        return {
            "success": False,
            "error": "sodapy no está disponible. Instala con: pip install sodapy"
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

        # Si nombre_banco no está presente pero agregacion sí, usar agregacion como nombre_banco
        if not datos.get("nombre_banco") and datos.get("agregacion"):
            datos["nombre_banco"] = datos.get("agregacion")
            logger.info(f"nombre_banco derivado de agregacion: {datos['nombre_banco']}")
        
        # Si aún no hay nombre_banco, establecer valor por defecto
        if not datos.get("nombre_banco"):
            datos["nombre_banco"] = "No especificado"
            logger.warning("nombre_banco no disponible, usando valor por defecto")

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
            # Obtener datos de SECOP - Intentar primero con NIT de Cali, luego sin restricción
            NIT_ENTIDAD_CALI = "890399011"
            resultado_secop = await obtener_datos_secop(referencia_proceso, nit_entidad=NIT_ENTIDAD_CALI)

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
                "data": serialize_datetime_objects(datos_completos),
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
                "data": serialize_datetime_objects(datos_completos),
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



async def obtener_centros_gestores_validos() -> List[str]:
    """
    Obtiene la lista de centros gestores válidos desde el endpoint correspondiente.
    """
    try:
        # Lista hardcodeada basada en los datos proporcionados por el usuario
        centros_gestores = [
            "UNIDAD DE PROYECTOS ESPECIALES - UPE",
            "DIRECCION GENERAL DE CREDITO PUBLICO Y TESORO NACIONAL",
            "PROGRAMA NACIONAL DE CIENCIA, TECNOLOGIA E INNOVACION",
            "DIRECCION GENERAL DE ORDENAMIENTO Y DESARROLLO TERRITORIAL",
            "DIRECCION GENERAL DE DESARROLLO EMPRESARIAL",
            "PROGRAMA NACIONAL DE EMPRENDIMIENTO Y INNOVACION",
            "PROGRAMA NACIONAL COLOMBIA CIENTIFICA",
            "PROGRAMA NACIONAL DE FOMENTO A LA INVESTIGACION",
            "PROGRAMA NACIONAL DE FINANCIAMIENTO DE LA INFRAESTRUCTURA",
            "DIRECCION GENERAL DE COMPETITIVIDAD Y DESARROLLO PRODUCTIVO",
            "PROGRAM NACIONAL DE APOYO DIRECTO AL EMPLEO Y ECOSISTEMA",
            "PROGRAMA NACIONAL DE INNOVACION EMPRESARIAL",
            "PROGRAMA NACIONAL DE DESARROLLO DE PROVEEDORES",
            "PROGRAMA DE FORTALECIMIENTO DE LA GESTIÓN PÚBLICA TERRITORIAL",
            "PROGRAMA NACIONAL DE TRANSFORMACIÓN PRODUCTIVA",
            "PROGRAMA NACIONAL DE SERVICIOS DE DESARROLLO EMPRESARIAL",
            "PROGRAMA NACIONAL DE DESARROLLO DE CONGLOMERADOS PRODUCTIVOS",
            "PROGRAMA NACIONAL DE DESARROLLO DE INSTRUMENTOS DE CREDITO",
            "DIRECCIONGENERAL DE DESARROLLO RURAL",
            "PROGRAMA NACIONAL DE DESARROLLO RURAL CON EQUIDAD - PNDRE",
            "PROGRAMA NACIONAL DE ASISTENCIA TECNICA AGROPECUARIA - PNATA",
            "PROGRAMA NACIONAL DE ECONOMIA CAMPESINA, FAMILIAR Y COMUNITARIA",
            "PROGRAMA NACIONAL DE CONSTRUCCION DE PAZ Y CONVIVENCIA",
            "PROGRAMA NACIONAL DE RECONCILIACION Y CONVIVENCIA",
            "PROGRAMA NACIONAL DE SUSTITUCION DE CULTIVOS ILICITOS - PNSCI",
            "PROGRAMA NACIONAL DE ATENCION A VICTIMAS DEL CONFLICTO ARMADO",
            "PROGRAM NACIONAL DE CIENCIA TECNOLOGIA E INNOVACION AGROPECUARIA"
        ]
        
        return centros_gestores
        
    except Exception as e:
        logger.error(f"Error obteniendo centros gestores válidos: {str(e)}")
        return []

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
        "error": None,
        "sin_contratos": False
    }

    try:
        from sodapy import Socrata
        
        logger.info(f"🔍 Buscando contratos en SECOP para proceso: {proceso_contractual}")

        # Buscar contratos que contengan el proceso_contractual
        # Primero intentar con NIT específico de Cali
        NIT_ENTIDAD_CALI = "890399011"
        where_clause = f"proceso_de_compra LIKE '%{proceso_contractual}%' AND nit_entidad = '{NIT_ENTIDAD_CALI}'"

        with Socrata("www.datos.gov.co", None) as client:
            contratos_secop = client.get("jbjy-vk9h", limit=100, where=where_clause)
        
        # Si no se encuentran contratos con el NIT de Cali, buscar sin restricción de NIT
        if not contratos_secop:
            logger.warning(f"⚠️ No se encontraron contratos para {proceso_contractual} con NIT {NIT_ENTIDAD_CALI}, buscando sin restricción de NIT...")
            where_clause = f"proceso_de_compra LIKE '%{proceso_contractual}%'"
            with Socrata("www.datos.gov.co", None) as client:
                contratos_secop = client.get("jbjy-vk9h", limit=100, where=where_clause)

        # Filtrar contratos excluyendo estados "Borrador" y "Cancelado"
        estados_excluidos = ["Borrador", "Cancelado"]
        contratos_secop_filtrados = [
            c for c in contratos_secop 
            if c.get("estado_contrato", "").strip() not in estados_excluidos
        ]
        
        contratos_excluidos = len(contratos_secop) - len(contratos_secop_filtrados)
        if contratos_excluidos > 0:
            logger.info(f"🚫 Excluidos {contratos_excluidos} contratos con estado 'Borrador' o 'Cancelado'")
        
        resultado["contratos_encontrados"] = len(contratos_secop_filtrados)
        logger.info(f"📊 Encontrados {len(contratos_secop_filtrados)} contratos válidos en SECOP para {proceso_contractual} (total original: {len(contratos_secop)})")

        if not contratos_secop_filtrados:
            resultado["exito"] = True  # No es error, simplemente no hay contratos
            resultado["sin_contratos"] = True  # Flag para distinguir de errores técnicos
            logger.info(f"ℹ️  No se encontraron contratos válidos para el proceso {proceso_contractual}")
            return resultado

        # Procesar cada contrato encontrado
        for j, contrato in enumerate(contratos_secop_filtrados, 1):
            try:
                logger.info(f"🔄 Procesando contrato {j}/{len(contratos_secop_filtrados)}: {contrato.get('referencia_del_contrato', 'N/A')}")

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
                    # Actualizar documento existente - Solo campos que han cambiado
                    existing_doc = existing_docs[0]
                    existing_data = existing_doc.to_dict()
                    
                    # Crear objeto de actualización solo con campos que han cambiado
                    campos_actualizacion = {}
                    
                    # Comparar cada campo y solo actualizar si hay cambios
                    for key, new_value in contrato_transformado.items():
                        if key == "fecha_guardado":  # No comparar fecha_guardado
                            continue
                        
                        existing_value = existing_data.get(key)
                        
                        # Actualizar solo si el valor es diferente o el campo no existe
                        if existing_value != new_value:
                            campos_actualizacion[key] = new_value
                    
                    # Solo actualizar si hay cambios reales
                    if campos_actualizacion:
                        campos_actualizacion["fecha_actualizacion"] = datetime.now()
                        existing_doc.reference.update(campos_actualizacion)
                        resultado["documentos_actualizados"] += 1
                        logger.info(f"🔄 Contrato actualizado ({len(campos_actualizacion)} campos): {referencia_contrato or id_contrato}")
                    else:
                        logger.info(f"📋 Contrato sin cambios: {referencia_contrato or id_contrato}")
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
    except ImportError:
        resultado["error"] = "sodapy no está disponible. Instala con: pip install sodapy"
        logger.error(f"💥 Error: sodapy no está disponible")
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
        "nombre_centro_gestor": proceso_data.get('nombre_centro_gestor', ''),
        "banco": proceso_data.get('nombre_banco', ''),  # CORREGIDO: heredar desde 'nombre_banco'
        "bp": proceso_data.get('bp', ''),  # AGREGADO: heredar campo bp

        # Campos principales del contrato desde SECOP
        "referencia_contrato": contrato.get("referencia_del_contrato", ""),
        "id_contrato": contrato.get("id_contrato", ""),
        "proceso_contractual": contrato.get("proceso_de_compra", ""),  # Cambio: proceso_de_compra -> proceso_contractual (sobrescribe el heredado)
        "sector": contrato.get("sector", ""),  # Nuevo campo: sector desde SECOP
        "nombre_procedimiento": contrato.get("nombre_del_procedimiento", ""),
        "descripcion_proceso": contrato.get("descripcion_del_proceso", ""),  # Unificado: descripcion_del_proceso -> descripcion_proceso
        "objeto_contrato": contrato.get("objeto_del_contrato", ""),

        # Estado y modalidad
        "estado_contrato": contrato.get("estado_contrato", ""),  # Corregido: estado_contrato en SECOP
        "modalidad_contratacion": contrato.get("modalidad_de_contratacion", ""),
        "tipo_contrato": contrato.get("tipo_de_contrato", ""),

        # Valores monetarios
        # ELIMINADO: "valor_del_contrato" - redundante con "valor_contrato"
        "valor_contrato": valor_contrato,
        "valor_pagado": contrato.get("valor_pagado", ""),

        # Personal y responsables
        "representante_legal": contrato.get("nombre_representante_legal", ""),  # Limpio: nombre_representante_legal -> representante_legal
        "ordenador_gasto": contrato.get("nombre_ordenador_del_gasto", ""),  # Limpio: nombre_ordenador_del_gasto -> ordenador_gasto
        "supervisor": contrato.get("nombre_supervisor", ""),  # Limpio: nombre_supervisor -> supervisor

        # Fechas en formato ISO 8601
        "fecha_firma_contrato": process_date("fecha_de_firma_del_contrato"),
        "fecha_inicio_contrato": process_date("fecha_de_inicio_del_contrato"),
        "fecha_fin_contrato": process_date("fecha_de_fin_del_contrato"),

        # Entidades participantes
        "entidad_contratante": contrato.get("nombre_entidad", ""),
        "nombre_contratista": contrato.get("nombre_del_contratista", ""),

        # NITs
        "nit_entidad": contrato.get("nit_entidad", ""),
        "nit_contratista": contrato.get("nit_del_contratista", ""),

        # BPIN (código BPIN mapeado correctamente)
        "bpin": bpin_value,

        # URLs y enlaces
        "urlproceso": contrato.get("urlproceso", ""),

        # Metadatos de guardado
        "fecha_guardado": datetime.now(),
        "fuente_datos": "SECOP_API",
        "version_esquema": "1.1",
        "_dataset_source": "jbjy-vk9h"
    }

async def get_bancos_emprestito_all() -> Dict[str, Any]:
    """Obtener todos los registros de la colección bancos_emprestito"""
    try:
        if not FIRESTORE_AVAILABLE:
            return {"success": False, "error": "Firebase no disponible", "data": [], "count": 0}
        
        db = get_firestore_client()
        if db is None:
            return {"success": False, "error": "No se pudo conectar a Firestore", "data": [], "count": 0}
        
        collection_ref = db.collection('bancos_emprestito')
        docs = collection_ref.stream()
        bancos_data = []
        
        for doc in docs:
            doc_data = doc.to_dict()
            doc_data['id'] = doc.id  # Agregar ID del documento
            # Limpiar datos de Firebase para serialización JSON
            doc_data_clean = serialize_datetime_objects(doc_data)
            bancos_data.append(doc_data_clean)
        
        # Ordenar por nombre_banco para mejor presentación
        bancos_data.sort(key=lambda x: x.get('nombre_banco', '').lower())
        
        return {
            "success": True,
            "data": bancos_data,
            "count": len(bancos_data),
            "collection": "bancos_emprestito",
            "timestamp": datetime.now().isoformat(),
            "message": f"Se obtuvieron {len(bancos_data)} bancos de empréstito exitosamente"
        }
        
    except Exception as e:
        return {
            "success": False, 
            "error": f"Error obteniendo todos los bancos de empréstito: {str(e)}",
            "data": [],
            "count": 0
        }

async def get_convenios_transferencia_emprestito_all() -> Dict[str, Any]:
    """Obtener todos los registros de la colección convenios_transferencias_emprestito"""
    try:
        if not FIRESTORE_AVAILABLE:
            return {"success": False, "error": "Firebase no disponible", "data": [], "count": 0}
        
        db = get_firestore_client()
        if db is None:
            return {"success": False, "error": "No se pudo conectar a Firestore", "data": [], "count": 0}
        
        collection_ref = db.collection('convenios_transferencias_emprestito')
        docs = collection_ref.stream()
        convenios_data = []
        
        for doc in docs:
            doc_data = doc.to_dict()
            doc_data['id'] = doc.id  # Agregar ID del documento
            # Limpiar datos de Firebase para serialización JSON
            doc_data_clean = serialize_datetime_objects(doc_data)
            convenios_data.append(doc_data_clean)
        
        # Ordenar por fecha de creación (más recientes primero)
        convenios_data.sort(key=lambda x: x.get('fecha_creacion', ''), reverse=True)
        
        return {
            "success": True,
            "data": convenios_data,
            "count": len(convenios_data),
            "collection": "convenios_transferencias_emprestito",
            "timestamp": datetime.now().isoformat(),
            "message": f"Se obtuvieron {len(convenios_data)} convenios de transferencia exitosamente"
        }
        
    except Exception as e:
        return {
            "success": False, 
            "error": f"Error obteniendo todos los convenios de transferencia: {str(e)}",
            "data": [],
            "count": 0
        }

async def eliminar_proceso_emprestito(*args, **kwargs):
    """Función stub - No implementada temporalmente"""
    return {"success": False, "error": "Función no implementada temporalmente"}

async def actualizar_proceso_emprestito(*args, **kwargs):
    """Función stub - No implementada temporalmente"""
    return {"success": False, "error": "Función no implementada temporalmente"}

async def actualizar_proceso_secop_por_referencia(referencia_proceso: str, campos_actualizar: Dict[str, Any]) -> Dict[str, Any]:
    """
    Actualizar un proceso SECOP existente en procesos_emprestito por referencia_proceso
    Permite actualizar SOLO valor_publicacion
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

        # Buscar proceso por referencia_proceso
        procesos_ref = db_client.collection('procesos_emprestito')
        query_resultado = procesos_ref.where('referencia_proceso', '==', referencia_proceso).get()

        if len(query_resultado) == 0:
            return {
                "success": False,
                "error": f"No se encontró ningún proceso SECOP con referencia_proceso: {referencia_proceso}",
                "referencia_proceso": referencia_proceso
            }

        # Obtener el documento
        doc = query_resultado[0]
        doc_data = doc.to_dict()

        # SOLO permitir actualizar valor_publicacion
        campos_permitidos = ["valor_publicacion"]
        
        # Preparar datos para actualizar
        datos_actualizacion = {}
        campos_actualizados = []
        valores_anteriores = {}
        valores_nuevos = {}
        
        for campo, valor in campos_actualizar.items():
            if campo not in campos_permitidos:
                continue  # Ignorar campos no permitidos
                
            if valor is not None:
                # Guardar valor anterior para el historial
                valores_anteriores[campo] = doc_data.get(campo)
                
                # El campo valor_publicacion es numérico
                datos_actualizacion[campo] = float(valor)
                valores_nuevos[campo] = datos_actualizacion[campo]
                campos_actualizados.append(campo)

        # Si no hay campos para actualizar
        if not datos_actualizacion:
            return {
                "success": False,
                "error": "No se proporcionaron campos para actualizar",
                "campos_disponibles": ["valor_publicacion"]
            }

        # Agregar timestamp de actualización
        datos_actualizacion["fecha_actualizacion"] = datetime.now()

        # Actualizar documento
        doc.reference.update(datos_actualizacion)

        # Obtener documento actualizado
        doc_actualizado = doc.reference.get()
        datos_completos = doc_actualizado.to_dict()

        logger.info(f"Proceso SECOP actualizado exitosamente: {referencia_proceso}, campos: {campos_actualizados}")

        return {
            "success": True,
            "message": "Proceso SECOP actualizado exitosamente",
            "referencia_proceso": referencia_proceso,
            "coleccion": "procesos_emprestito",
            "documento_id": doc.id,
            "campos_modificados": campos_actualizados,
            "valores_anteriores": valores_anteriores,
            "valores_nuevos": valores_nuevos,
            "proceso_actualizado": serialize_datetime_objects(datos_completos),
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Error actualizando proceso SECOP: {e}")
        return {
            "success": False,
            "error": str(e)
        }

async def obtener_codigos_contratos(*args, **kwargs):
    """Función stub - No implementada temporalmente"""
    return {"success": False, "error": "Función no implementada temporalmente"}

async def buscar_y_poblar_contratos_secop(*args, **kwargs):
    """Función stub - No implementada temporalmente"""
    return {"success": False, "error": "Función no implementada temporalmente"}

async def obtener_contratos_desde_proceso_contractual(offset: int = 0, limit: int = 10) -> Dict[str, Any]:
    """
    Obtener registros de procesos_emprestito en lotes y buscar contratos en SECOP para cada uno,
    guardando los resultados en la colección contratos_emprestito

    OPTIMIZADO para procesamiento por lotes:
    - Procesa lotes de procesos de empréstito (por defecto 10, máximo 50)
    - Parámetros: offset (inicio) y limit (cantidad)
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
    logger.info(f"🚀 Iniciando obtención de contratos desde SECOP (procesamiento por lotes: offset={offset}, limit={limit})...")

    try:
        db_client = get_firestore_client()
        if not db_client:
            return {
                "success": False,
                "error": "Error obteniendo cliente Firestore"
            }

        # 1. Obtener todos los registros de la colección procesos_emprestito
        procesos_ref = db_client.collection('procesos_emprestito')
        todos_procesos_docs = list(procesos_ref.stream())
        
        total_procesos_coleccion = len(todos_procesos_docs)

        if not todos_procesos_docs:
            return {
                "success": False,
                "error": "No se encontraron procesos en la colección procesos_emprestito",
                "timestamp": datetime.now().isoformat()
            }
        
        # Aplicar offset y limit
        fin = min(offset + limit, total_procesos_coleccion)
        procesos_docs = todos_procesos_docs[offset:fin]
        procesos_en_lote = len(procesos_docs)
        
        if procesos_en_lote == 0:
            return {
                "success": True,
                "message": f"No hay más procesos para procesar (offset {offset} excede total {total_procesos_coleccion})",
                "resumen_procesamiento": {
                    "offset": offset,
                    "limit": limit,
                    "total_procesos_coleccion": total_procesos_coleccion,
                    "procesos_en_lote": 0,
                    "mas_registros": False
                },
                "timestamp": datetime.now().isoformat()
            }

        # Variables de control
        total_contratos_encontrados = 0
        total_documentos_nuevos = 0
        total_documentos_actualizados = 0
        todos_contratos_guardados = []
        procesos_con_errores_tecnicos = []
        procesos_sin_contratos = []

        # Procesar el lote de procesos
        procesos_a_procesar = procesos_docs

        logger.info(f"🔄 Procesamiento por lotes iniciado: {procesos_en_lote} procesos en este lote (offset {offset}-{fin} de {total_procesos_coleccion} total)")

        # Crear la colección si no existe (Firestore la crea automáticamente al agregar el primer documento)
        contratos_ref = db_client.collection('contratos_emprestito')
        logger.info("📁 Referencia a colección 'contratos_emprestito' establecida (se creará automáticamente si no existe)")

        # 3. Procesar cada proceso de empréstito
        procesados_exitosos = 0

        for i, proceso_doc in enumerate(procesos_a_procesar, 1):
            logger.info(f"\n{'='*60}")
            logger.info(f"🎯 PROCESO {i}/{procesos_en_lote} (Global: {offset + i}/{total_procesos_coleccion}) - PROCESAMIENTO INDIVIDUAL")
            logger.info(f"{'='*60}")

            try:
                proceso_data = proceso_doc.to_dict()
                referencia_proceso = proceso_data.get('referencia_proceso', '')
                proceso_contractual = proceso_data.get('proceso_contractual', '')

                if not referencia_proceso or not proceso_contractual:
                    logger.warning(f"❌ Proceso incompleto {i}/{total_procesos}: {proceso_doc.id}")
                    procesos_con_errores_tecnicos.append({
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

                    if resultado_individual.get("sin_contratos", False):
                        # Proceso exitoso pero sin contratos encontrados en SECOP
                        procesos_sin_contratos.append({
                            "id": proceso_doc.id,
                            "referencia_proceso": referencia_proceso,
                            "proceso_contractual": proceso_contractual,
                            "motivo": "No se encontraron contratos en SECOP para este proceso"
                        })
                        logger.info(f"ℹ️  SIN CONTRATOS - Proceso {i}/{procesos_en_lote}: {proceso_contractual}")
                    else:
                        logger.info(f"✅ ÉXITO - Proceso {i}/{procesos_en_lote}: {resultado_individual['contratos_encontrados']} contratos encontrados, {resultado_individual['documentos_nuevos']} nuevos, {resultado_individual['documentos_actualizados']} actualizados")
                else:
                    # Error técnico real
                    procesos_con_errores_tecnicos.append({
                        "id": proceso_doc.id,
                        "referencia_proceso": referencia_proceso,
                        "error": resultado_individual["error"]
                    })
                    logger.error(f"❌ ERROR TÉCNICO - Proceso {i}/{procesos_en_lote}: {resultado_individual['error']}")

                # Log de progreso
                tiempo_transcurrido = (datetime.now() - inicio_tiempo).total_seconds()
                logger.info(f"⏱️  Tiempo transcurrido: {tiempo_transcurrido:.1f}s | Exitosos: {procesados_exitosos}/{i}")

            except Exception as e:
                logger.error(f"💥 EXCEPCIÓN en proceso {i}/{procesos_en_lote}: {e}")
                procesos_con_errores_tecnicos.append({
                    "id": proceso_doc.id,
                    "referencia_proceso": referencia_proceso if 'referencia_proceso' in locals() else "DESCONOCIDO",
                    "error": f"Excepción durante procesamiento: {str(e)}"
                })
                continue

        # Actualizar estadísticas finales
        procesos_procesados = procesados_exitosos
        total_duplicados_ignorados = 0
        mas_registros = fin < total_procesos_coleccion
        siguiente_offset = fin if mas_registros else None

        logger.info(f"\n🏁 LOTE PROCESADO")
        logger.info(f"📊 Estadísticas del lote:")
        logger.info(f"   - Lote: offset {offset}, limit {limit}")
        logger.info(f"   - Procesos en lote: {procesos_en_lote}")
        logger.info(f"   - Total en colección: {total_procesos_coleccion}")
        logger.info(f"   - Procesados exitosamente: {procesados_exitosos}")
        logger.info(f"   - Procesos sin contratos en SECOP: {len(procesos_sin_contratos)}")
        logger.info(f"   - Errores técnicos: {len(procesos_con_errores_tecnicos)}")
        logger.info(f"   - Contratos encontrados: {total_contratos_encontrados}")
        logger.info(f"   - Documentos nuevos: {total_documentos_nuevos}")
        logger.info(f"   - Documentos actualizados: {total_documentos_actualizados}")
        logger.info(f"   - Más registros: {'Sí' if mas_registros else 'No'}")
        if siguiente_offset:
            logger.info(f"   - Siguiente offset: {siguiente_offset}")

        # 4. Preparar respuesta final
        total_procesados = total_documentos_nuevos + total_documentos_actualizados + total_duplicados_ignorados

        return {
            "success": True,
            "message": f"✅ LOTE PROCESADO: {procesados_exitosos}/{procesos_en_lote} procesos. Contratos: {total_procesados} total ({total_documentos_nuevos} nuevos, {total_documentos_actualizados} actualizados)",
            "resumen_procesamiento": {
                "offset": offset,
                "limit": limit,
                "total_procesos_coleccion": total_procesos_coleccion,
                "procesos_en_lote": procesos_en_lote,
                "procesos_procesados_exitosamente": procesados_exitosos,
                "procesos_sin_contratos_en_secop": len(procesos_sin_contratos),
                "procesos_con_errores_tecnicos": len(procesos_con_errores_tecnicos),
                "tasa_exito": f"{(procesados_exitosos/procesos_en_lote*100):.1f}%" if procesos_en_lote > 0 else "0%",
                "mas_registros": mas_registros,
                "siguiente_offset": siguiente_offset
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
            "procesos_sin_contratos_en_secop": procesos_sin_contratos,
            "procesos_con_errores_tecnicos": procesos_con_errores_tecnicos,
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


async def obtener_contratos_desde_proceso_contractual_completo() -> Dict[str, Any]:
    """
    Obtener y procesar TODOS los registros de procesos_emprestito de manera iterativa,
    sin límite de 50 registros. Itera sobre todos los datos automáticamente.

    OPTIMIZADO para procesamiento completo:
    - Itera automáticamente sobre todos los procesos sin límite
    - Procesa en lotes internos con paralelización (hasta 3 procesos simultáneamente)
    - Retorna resumen completo al finalizar
    - Hereda campos: nombre_centro_gestor, banco (desde nombre_banco), bp
    - Mapea bpin desde c_digo_bpin de SECOP
    """
    if not FIRESTORE_AVAILABLE:
        return {
            "success": False,
            "error": "Firebase no disponible"
        }

    inicio_tiempo = datetime.now()
    logger.info(f"🚀 Iniciando obtención COMPLETA de contratos desde SECOP (sin límite de registros)...")

    try:
        db_client = get_firestore_client()
        if not db_client:
            return {
                "success": False,
                "error": "Error obteniendo cliente Firestore"
            }

        # 1. Obtener todos los registros de la colección procesos_emprestito
        procesos_ref = db_client.collection('procesos_emprestito')
        todos_procesos_docs = list(procesos_ref.stream())
        
        total_procesos_coleccion = len(todos_procesos_docs)

        if not todos_procesos_docs:
            return {
                "success": False,
                "error": "No se encontraron procesos en la colección procesos_emprestito",
                "timestamp": datetime.now().isoformat()
            }
        
        logger.info(f"📊 Total de procesos a procesar: {total_procesos_coleccion}")

        # Variables de control - acumuladores globales
        total_contratos_encontrados = 0
        total_documentos_nuevos = 0
        total_documentos_actualizados = 0
        todos_contratos_guardados = []
        procesos_con_errores_tecnicos = []
        procesos_sin_contratos = []
        procesados_exitosos = 0
        total_lotes = 0

        # Crear la colección si no existe
        contratos_ref = db_client.collection('contratos_emprestito')
        logger.info("📁 Referencia a colección 'contratos_emprestito' establecida")

        # 2. Procesar todos los procesos con paralelización
        TAMAÑO_LOTE_INTERNO = 10  # Reducido para mejor responsividad
        MAX_PARALELO = 3  # Máximo 3 procesos en paralelo para no saturar SECOP
        
        for lote_num in range(0, total_procesos_coleccion, TAMAÑO_LOTE_INTERNO):
            total_lotes += 1
            fin_lote = min(lote_num + TAMAÑO_LOTE_INTERNO, total_procesos_coleccion)
            procesos_en_lote_actual = fin_lote - lote_num
            
            logger.info(f"\n{'='*60}")
            logger.info(f"🔄 LOTE #{total_lotes}: Registros {lote_num + 1} a {fin_lote} de {total_procesos_coleccion}")
            logger.info(f"{'='*60}")

            # Obtener procesos para este lote
            procesos_lote = todos_procesos_docs[lote_num:fin_lote]

            # Preparar tareas asincrónicas para paralelización
            tareas = []
            indices = []
            
            for i, proceso_doc in enumerate(procesos_lote, 1):
                try:
                    proceso_data = proceso_doc.to_dict()
                    referencia_proceso = proceso_data.get('referencia_proceso', '')
                    proceso_contractual = proceso_data.get('proceso_contractual', '')

                    if not referencia_proceso or not proceso_contractual:
                        logger.warning(f"❌ Proceso incompleto {i}/{procesos_en_lote_actual}")
                        procesos_con_errores_tecnicos.append({
                            "id": proceso_doc.id,
                            "referencia_proceso": referencia_proceso or "N/A",
                            "error": "Datos incompletos"
                        })
                        continue

                    # Agregar a la lista de tareas
                    tareas.append(procesar_proceso_individual(
                        db_client, proceso_data, referencia_proceso, proceso_contractual, contratos_ref
                    ))
                    indices.append((i, referencia_proceso, proceso_contractual, proceso_doc.id))
                    
                except Exception as e:
                    logger.error(f"💥 Error preparando proceso {i}: {e}")
                    procesos_con_errores_tecnicos.append({
                        "id": proceso_doc.id,
                        "referencia_proceso": "DESCONOCIDO",
                        "error": f"Error: {str(e)}"
                    })
                    continue
            
            # Procesar tareas en paralelo en grupos de MAX_PARALELO
            for grupo_idx in range(0, len(tareas), MAX_PARALELO):
                grupo_tareas = tareas[grupo_idx:min(grupo_idx + MAX_PARALELO, len(tareas))]
                grupo_indices = indices[grupo_idx:min(grupo_idx + MAX_PARALELO, len(indices))]
                
                # Ejecutar tareas en paralelo
                resultados_grupo = await asyncio.gather(*grupo_tareas, return_exceptions=True)
                
                # Procesar resultados
                for resultado_individual, (i, referencia_proceso, proceso_contractual, doc_id) in zip(resultados_grupo, grupo_indices):
                    if isinstance(resultado_individual, Exception):
                        logger.error(f"❌ Excepción en {referencia_proceso}: {resultado_individual}")
                        procesos_con_errores_tecnicos.append({
                            "id": doc_id,
                            "referencia_proceso": referencia_proceso,
                            "error": str(resultado_individual)
                        })
                        continue
                    
                    if resultado_individual.get("exito"):
                        procesados_exitosos += 1
                        total_documentos_nuevos += resultado_individual["documentos_nuevos"]
                        total_documentos_actualizados += resultado_individual["documentos_actualizados"]
                        total_contratos_encontrados += resultado_individual["contratos_encontrados"]
                        todos_contratos_guardados.extend(resultado_individual["contratos_guardados"])

                        if resultado_individual.get("sin_contratos", False):
                            procesos_sin_contratos.append({
                                "id": doc_id,
                                "referencia_proceso": referencia_proceso,
                                "proceso_contractual": proceso_contractual,
                                "motivo": "No encontrados en SECOP"
                            })
                        
                        logger.info(f"  ✅ [{i}] {referencia_proceso}: {resultado_individual['contratos_encontrados']} contratos")
                    else:
                        procesos_con_errores_tecnicos.append({
                            "id": doc_id,
                            "referencia_proceso": referencia_proceso,
                            "error": resultado_individual.get("error", "Error desconocido")
                        })
                        logger.error(f"  ❌ [{i}] {referencia_proceso}: {resultado_individual.get('error')}")

            # Log de progreso
            tiempo_transcurrido = (datetime.now() - inicio_tiempo).total_seconds()
            logger.info(f"⏱️  Progreso: {tiempo_transcurrido:.1f}s | {procesados_exitosos} exitosos")

        # Calcular estadísticas finales
        total_duplicados_ignorados = 0
        total_procesados = total_documentos_nuevos + total_documentos_actualizados + total_duplicados_ignorados

        logger.info(f"\n{'='*60}")
        logger.info(f"🏁 PROCESAMIENTO COMPLETO FINALIZADO")
        logger.info(f"{'='*60}")

        # Preparar respuesta final
        return {
            "success": True,
            "message": f"✅ COMPLETADO: {procesados_exitosos}/{total_procesos_coleccion} procesos. Contratos: {total_procesados} total",
            "resumen_procesamiento": {
                "total_procesos_coleccion": total_procesos_coleccion,
                "procesos_procesados_exitosamente": procesados_exitosos,
                "procesos_sin_contratos_en_secop": len(procesos_sin_contratos),
                "procesos_con_errores_tecnicos": len(procesos_con_errores_tecnicos),
                "tasa_exito": f"{(procesados_exitosos/total_procesos_coleccion*100):.1f}%" if total_procesos_coleccion > 0 else "0%",
                "lotes_procesados": total_lotes,
                "procesamiento_paralelo": f"hasta {MAX_PARALELO} simultáneamente"
            },
            "criterios_busqueda": {
                "coleccion_origen": "procesos_emprestito",
                "filtro_secop": "nit_entidad = '890399011'",
                "procesamiento": "completo_iterativo_paralelo"
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
            "procesos_sin_contratos_en_secop": procesos_sin_contratos,
            "procesos_con_errores_tecnicos": procesos_con_errores_tecnicos,
            "tiempo_total": (datetime.now() - inicio_tiempo).total_seconds(),
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Error general en obtener_contratos_desde_proceso_contractual_completo: {e}")
        return {
            "success": False,
            "error": str(e),
            "message": "Error durante el procesamiento completo",
            "timestamp": datetime.now().isoformat()
        }


async def cargar_orden_compra_directa(datos_orden: Dict[str, Any]) -> Dict[str, Any]:
    """
    Cargar orden de compra directamente en la colección ordenes_compra_emprestito
    sin procesamiento adicional de APIs externas
    """
    if not FIRESTORE_AVAILABLE:
        return {
            "success": False,
            "error": "Firebase no disponible"
        }

    try:
        # Validar campos obligatorios
        campos_obligatorios = [
            "numero_orden", 
            "nombre_centro_gestor", 
            "nombre_banco", 
            "nombre_resumido_proceso", 
            "valor_proyectado"
        ]
        
        for campo in campos_obligatorios:
            if not datos_orden.get(campo):
                return {
                    "success": False,
                    "error": f"El campo '{campo}' es obligatorio"
                }

        # Verificar si ya existe una orden con el mismo número
        numero_orden = datos_orden.get("numero_orden", "").strip()
        
        db_client = get_firestore_client()
        if not db_client:
            return {
                "success": False,
                "error": "Error obteniendo cliente Firestore"
            }

        # Buscar duplicados por numero_orden
        ordenes_ref = db_client.collection('ordenes_compra_emprestito')
        query_resultado = ordenes_ref.where('numero_orden', '==', numero_orden).get()

        if len(query_resultado) > 0:
            return {
                "success": False,
                "error": f"Ya existe una orden de compra con número: {numero_orden}",
                "duplicate": True,
                "existing_data": {
                    "doc_id": query_resultado[0].id,
                    "numero_orden": numero_orden
                }
            }

        # Preparar datos para guardar
        datos_completos = {
            "numero_orden": numero_orden,
            "nombre_centro_gestor": datos_orden.get("nombre_centro_gestor", "").strip(),
            "nombre_banco": datos_orden.get("nombre_banco", "").strip(),
            "nombre_resumido_proceso": datos_orden.get("nombre_resumido_proceso", "").strip(),
            "valor_proyectado": float(datos_orden.get("valor_proyectado", 0)),
            "bp": datos_orden.get("bp", "").strip() if datos_orden.get("bp") else None,
            "fecha_creacion": datetime.now(),
            "fecha_actualizacion": datetime.now(),
            "estado": "activo",
            "tipo": "orden_compra_manual"
        }

        # Guardar en Firestore
        doc_ref = db_client.collection('ordenes_compra_emprestito').add(datos_completos)
        doc_id = doc_ref[1].id

        logger.info(f"Orden de compra creada exitosamente: {doc_id}")

        return {
            "success": True,
            "doc_id": doc_id,
            "data": serialize_datetime_objects(datos_completos),
            "message": f"Orden de compra {numero_orden} guardada exitosamente",
            "coleccion": "ordenes_compra_emprestito"
        }

    except Exception as e:
        logger.error(f"Error cargando orden de compra: {e}")
        return {
            "success": False,
            "error": str(e)
        }

async def cargar_convenio_transferencia(datos_convenio: Dict[str, Any]) -> Dict[str, Any]:
    """
    Cargar convenio de transferencia directamente en la colección convenios_transferencias_emprestito
    sin procesamiento adicional de APIs externas
    """
    if not FIRESTORE_AVAILABLE:
        return {
            "success": False,
            "error": "Firebase no disponible"
        }

    try:
        # Validar campos obligatorios
        campos_obligatorios = [
            "referencia_contrato",
            "nombre_centro_gestor",
            "banco",
            "objeto_contrato",
            "valor_contrato",
            "nombre_resumido_proceso"
        ]
        
        for campo in campos_obligatorios:
            if not datos_convenio.get(campo):
                return {
                    "success": False,
                    "error": f"El campo '{campo}' es obligatorio"
                }

        # Verificar si ya existe un convenio con la misma referencia
        referencia_contrato = datos_convenio.get("referencia_contrato", "").strip()
        
        db_client = get_firestore_client()
        if not db_client:
            return {
                "success": False,
                "error": "Error obteniendo cliente Firestore"
            }

        # Buscar duplicados por referencia_contrato
        convenios_ref = db_client.collection('convenios_transferencias_emprestito')
        query_resultado = convenios_ref.where('referencia_contrato', '==', referencia_contrato).get()

        if len(query_resultado) > 0:
            return {
                "success": False,
                "error": f"Ya existe un convenio de transferencia con referencia: {referencia_contrato}",
                "duplicate": True,
                "existing_data": {
                    "doc_id": query_resultado[0].id,
                    "referencia_contrato": referencia_contrato
                }
            }

        # Preparar datos para guardar
        datos_completos = {
            "referencia_contrato": referencia_contrato,
            "nombre_centro_gestor": datos_convenio.get("nombre_centro_gestor", "").strip(),
            "bp": datos_convenio.get("bp", "").strip() if datos_convenio.get("bp") else None,
            "bpin": datos_convenio.get("bpin", "").strip() if datos_convenio.get("bpin") else None,
            "objeto_contrato": datos_convenio.get("objeto_contrato", "").strip(),
            "valor_contrato": float(datos_convenio.get("valor_contrato", 0)),
            "valor_convenio": float(datos_convenio.get("valor_convenio", 0)) if datos_convenio.get("valor_convenio") else None,
            "urlproceso": datos_convenio.get("urlproceso", "").strip() if datos_convenio.get("urlproceso") else None,
            "banco": datos_convenio.get("banco", "").strip(),
            "fecha_inicio_contrato": datos_convenio.get("fecha_inicio_contrato", "").strip() if datos_convenio.get("fecha_inicio_contrato") else None,
            "fecha_fin_contrato": datos_convenio.get("fecha_fin_contrato", "").strip() if datos_convenio.get("fecha_fin_contrato") else None,
            "modalidad_contrato": datos_convenio.get("modalidad_contrato", "").strip() if datos_convenio.get("modalidad_contrato") else None,
            "ordenador_gastor": datos_convenio.get("ordenador_gastor", "").strip() if datos_convenio.get("ordenador_gastor") else None,
            "tipo_contrato": datos_convenio.get("tipo_contrato", "").strip() if datos_convenio.get("tipo_contrato") else None,
            "estado_contrato": datos_convenio.get("estado_contrato", "").strip() if datos_convenio.get("estado_contrato") else None,
            "sector": datos_convenio.get("sector", "").strip() if datos_convenio.get("sector") else None,
            "nombre_resumido_proceso": datos_convenio.get("nombre_resumido_proceso", "").strip() if datos_convenio.get("nombre_resumido_proceso") else None,
            "fecha_creacion": datetime.now(),
            "fecha_actualizacion": datetime.now(),
            "estado": "activo",
            "tipo": "convenio_transferencia_manual"
        }

        # Guardar en Firestore
        doc_ref = db_client.collection('convenios_transferencias_emprestito').add(datos_completos)
        doc_id = doc_ref[1].id

        logger.info(f"Convenio de transferencia creado exitosamente: {doc_id}")

        return {
            "success": True,
            "doc_id": doc_id,
            "data": serialize_datetime_objects(datos_completos),
            "message": f"Convenio de transferencia {referencia_contrato} guardado exitosamente",
            "coleccion": "convenios_transferencias_emprestito"
        }

    except Exception as e:
        logger.error(f"Error cargando convenio de transferencia: {e}")
        return {
            "success": False,
            "error": str(e)
        }

async def modificar_convenio_transferencia(doc_id: str, campos_actualizar: Dict[str, Any]) -> Dict[str, Any]:
    """
    Modificar un convenio de transferencia existente en la colección convenios_transferencias_emprestito
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

        # Verificar que el documento existe
        doc_ref = db_client.collection('convenios_transferencias_emprestito').document(doc_id)
        doc = doc_ref.get()

        if not doc.exists:
            return {
                "success": False,
                "error": f"No se encontró el convenio de transferencia con ID: {doc_id}"
            }

        # Preparar datos para actualizar
        datos_actualizacion = {}
        campos_actualizados = []
        
        for campo, valor in campos_actualizar.items():
            if valor is not None:
                # Limpiar strings si es necesario
                if isinstance(valor, str):
                    datos_actualizacion[campo] = valor.strip()
                else:
                    datos_actualizacion[campo] = valor
                campos_actualizados.append(campo)

        # Agregar timestamp de actualización
        datos_actualizacion["fecha_actualizacion"] = datetime.now()

        # Actualizar documento
        doc_ref.update(datos_actualizacion)

        # Obtener documento actualizado
        doc_actualizado = doc_ref.get()
        datos_completos = doc_actualizado.to_dict()

        logger.info(f"Convenio de transferencia actualizado exitosamente: {doc_id}, campos: {campos_actualizados}")

        return {
            "success": True,
            "doc_id": doc_id,
            "campos_actualizados": campos_actualizados,
            "data": serialize_datetime_objects(datos_completos),
            "message": f"Convenio de transferencia actualizado exitosamente",
            "coleccion": "convenios_transferencias_emprestito"
        }

    except Exception as e:
        logger.error(f"Error modificando convenio de transferencia: {e}")
        return {
            "success": False,
            "error": str(e)
        }

def cargar_rpc_emprestito(datos_rpc: Dict[str, Any], documentos: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    """
    Cargar RPC (Registro Presupuestal de Compromiso) directamente en la colección rpc_contratos_emprestito
    con soporte para carga de documentos a S3
    
    Args:
        datos_rpc: Diccionario con los datos del RPC
        documentos: Lista OBLIGATORIA de documentos a subir (cada uno con 'content', 'filename', 'content_type')
    """
    if not FIRESTORE_AVAILABLE:
        return {
            "success": False,
            "error": "Firebase no disponible"
        }

    try:
        # Validar que se hayan proporcionado documentos
        if not documentos or len(documentos) == 0:
            return {
                "success": False,
                "error": "Se requiere al menos un documento para cargar el RPC",
                "message": "Debe proporcionar al menos un archivo PDF, DOC, DOCX, XLS, XLSX, JPG o PNG"
            }
        
        logger.info(f"📥 Validando {len(documentos)} documentos para RPC")
        
        # Validar campos obligatorios
        campos_obligatorios = [
            "numero_rpc",
            "beneficiario_id",
            "beneficiario_nombre",
            "descripcion_rpc",
            "fecha_contabilizacion",
            "fecha_impresion",
            "estado_liberacion",
            "valor_rpc",
            "nombre_centro_gestor",
            "referencia_contrato"
        ]
        
        for campo in campos_obligatorios:
            if not datos_rpc.get(campo):
                return {
                    "success": False,
                    "error": f"El campo '{campo}' es obligatorio"
                }

        # Verificar si ya existe un RPC con el mismo número
        numero_rpc = datos_rpc.get("numero_rpc", "").strip()
        
        db_client = get_firestore_client()
        if not db_client:
            return {
                "success": False,
                "error": "Error obteniendo cliente Firestore"
            }

        # Buscar duplicados por numero_rpc
        rpc_ref = db_client.collection('rpc_contratos_emprestito')
        query_resultado = rpc_ref.where('numero_rpc', '==', numero_rpc).get()

        if len(query_resultado) > 0:
            return {
                "success": False,
                "error": f"Ya existe un RPC con número: {numero_rpc}",
                "duplicate": True,
                "existing_data": {
                    "doc_id": query_resultado[0].id,
                    "numero_rpc": numero_rpc
                }
            }

        # Procesar documentos (OBLIGATORIOS)
        documentos_info = []
        if not S3_AVAILABLE:
            return {
                "success": False,
                "error": "Servicio de almacenamiento S3 no disponible",
                "message": "No es posible subir documentos en este momento"
            }
        
        try:
            s3_manager = S3DocumentManager()
            
            # Preparar archivos para subida
            referencia_contrato = datos_rpc.get('referencia_contrato', '').strip()
            files_to_upload = []
            for doc in documentos:
                # Validar documento
                is_valid, error_msg = validate_document_file(doc['filename'], doc['content'])
                if not is_valid:
                    logger.warning(f"Documento inválido: {error_msg}")
                    return {
                        "success": False,
                        "error": f"Documento inválido: {error_msg}",
                        "filename": doc['filename']
                    }
                
                files_to_upload.append({
                    'content': doc['content'],
                    'filename': doc['filename'],
                    'content_type': doc.get('content_type', 'application/pdf'),
                    'numero_rpc': numero_rpc,
                    'centro_gestor': datos_rpc.get('nombre_centro_gestor', '')
                })
            
            # Subir documentos a S3 (usa referencia_contrato como carpeta)
            if files_to_upload:
                successful, failed = s3_manager.upload_multiple_documents(
                    files=files_to_upload,
                    referencia_contrato=referencia_contrato,
                    document_type='rpc',
                    use_timestamp=False  # Sin timestamp para permitir sobreescritura
                )
                
                documentos_info = successful
                
                if failed:
                    logger.error(f"Algunos documentos fallaron al subir: {len(failed)}")
                    return {
                        "success": False,
                        "error": f"Error subiendo {len(failed)} documento(s)",
                        "failed_files": [f.get('filename') for f in failed]
                    }
                
                logger.info(f"✅ Subidos {len(successful)} documentos para RPC {numero_rpc}")
            else:
                return {
                    "success": False,
                    "error": "No se pudo validar ningún documento para subir"
                }
                
        except Exception as e:
            logger.error(f"Error subiendo documentos a S3: {e}")
            return {
                "success": False,
                "error": f"Error subiendo documentos a S3: {str(e)}"
            }

        # Preparar datos para guardar
        # Procesar cdp_asociados: puede venir como lista o string separado por comas
        cdp_asociados_list = []
        if datos_rpc.get("cdp_asociados"):
            cdp_value = datos_rpc.get("cdp_asociados")
            if isinstance(cdp_value, list):
                # Si ya es una lista, limpiar cada elemento
                cdp_asociados_list = [str(cdp).strip() for cdp in cdp_value if cdp]
            elif isinstance(cdp_value, str):
                # Si es string, dividir por comas y limpiar
                cdp_asociados_list = [cdp.strip() for cdp in cdp_value.split(",") if cdp.strip()]
        
        datos_completos = {
            "numero_rpc": numero_rpc,
            "beneficiario_id": datos_rpc.get("beneficiario_id", "").strip(),
            "beneficiario_nombre": datos_rpc.get("beneficiario_nombre", "").strip(),
            "descripcion_rpc": datos_rpc.get("descripcion_rpc", "").strip(),
            "fecha_contabilizacion": datos_rpc.get("fecha_contabilizacion", "").strip(),
            "fecha_impresion": datos_rpc.get("fecha_impresion", "").strip(),
            "estado_liberacion": datos_rpc.get("estado_liberacion", "").strip(),
            "bp": "",  # BP se hereda al consultar desde contratos_emprestito, convenios o ordenes
            "valor_rpc": float(datos_rpc.get("valor_rpc", 0)),
            "cdp_asociados": cdp_asociados_list if cdp_asociados_list else [],
            "programacion_pac": datos_rpc.get("programacion_pac", {}) if isinstance(datos_rpc.get("programacion_pac"), dict) else {},
            "nombre_centro_gestor": datos_rpc.get("nombre_centro_gestor", "").strip(),
            "referencia_contrato": datos_rpc.get("referencia_contrato", "").strip(),
            "documentos_s3": documentos_info if documentos_info else [],
            "fecha_creacion": datetime.now(),
            "fecha_actualizacion": datetime.now(),
            "estado": "activo",
            "tipo": "rpc_manual"
        }

        # Guardar en Firestore
        doc_ref = db_client.collection('rpc_contratos_emprestito').add(datos_completos)
        doc_id = doc_ref[1].id

        logger.info(f"RPC creado exitosamente: {doc_id}")

        return {
            "success": True,
            "doc_id": doc_id,
            "data": serialize_datetime_objects(datos_completos),
            "message": f"RPC {numero_rpc} guardado exitosamente" + (f" con {len(documentos_info)} documentos" if documentos_info else ""),
            "coleccion": "rpc_contratos_emprestito",
            "documentos_count": len(documentos_info)
        }

    except Exception as e:
        logger.error(f"Error cargando RPC: {e}")
        return {
            "success": False,
            "error": str(e)
        }

def cargar_pago_emprestito(datos_pago: Dict[str, Any], documentos: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    """
    Cargar pago de empréstito directamente en la colección pagos_emprestito
    con fecha_registro automática según la hora del sistema y soporte para documentos S3
    
    Args:
        datos_pago: Diccionario con los datos del pago
        documentos: Lista OPCIONAL de documentos a subir (cada uno con 'content', 'filename', 'content_type')
    """
    if not FIRESTORE_AVAILABLE:
        return {
            "success": False,
            "error": "Firebase no disponible"
        }

    try:
        # Validar campos obligatorios
        campos_obligatorios = [
            "numero_rpc",
            "valor_pago",
            "fecha_transaccion",
            "referencia_contrato",
            "nombre_centro_gestor"
        ]
        
        for campo in campos_obligatorios:
            if not datos_pago.get(campo):
                return {
                    "success": False,
                    "error": f"El campo '{campo}' es obligatorio"
                }

        # Validar que valor_pago sea positivo
        try:
            valor_pago = float(datos_pago.get("valor_pago", 0))
            if valor_pago <= 0:
                return {
                    "success": False,
                    "error": "El valor del pago debe ser mayor a 0"
                }
        except (ValueError, TypeError):
            return {
                "success": False,
                "error": "El valor del pago debe ser un número válido"
            }

        db_client = get_firestore_client()
        if not db_client:
            return {
                "success": False,
                "error": "Error obteniendo cliente Firestore"
            }

        # Procesar documentos solo si se proporcionaron
        documentos_info = []
        numero_rpc = datos_pago.get("numero_rpc", "").strip()
        
        if documentos and len(documentos) > 0:
            logger.info(f"📥 Validando {len(documentos)} documentos para pago")
            
            if not S3_AVAILABLE:
                return {
                    "success": False,
                    "error": "Servicio de almacenamiento S3 no disponible",
                    "message": "No es posible subir documentos en este momento"
                }
            
            try:
                s3_manager = S3DocumentManager()
                
                # Preparar archivos para subida
                referencia_contrato = datos_pago.get('referencia_contrato', '').strip()
                files_to_upload = []
                for doc in documentos:
                    # Validar documento
                    is_valid, error_msg = validate_document_file(doc['filename'], doc['content'])
                    if not is_valid:
                        logger.warning(f"Documento inválido: {error_msg}")
                        return {
                            "success": False,
                            "error": f"Documento inválido: {error_msg}",
                            "filename": doc['filename']
                        }
                    
                    files_to_upload.append({
                        'content': doc['content'],
                        'filename': doc['filename'],
                        'content_type': doc.get('content_type', 'application/pdf'),
                        'numero_rpc': numero_rpc,
                        'centro_gestor': datos_pago.get('nombre_centro_gestor', '')
                    })
                
                # Subir documentos a S3 (usa referencia_contrato/numero_rpc como carpeta)
                if files_to_upload:
                    successful, failed = s3_manager.upload_multiple_documents(
                        files=files_to_upload,
                        referencia_contrato=referencia_contrato,
                        document_type='pago',
                        numero_rpc=numero_rpc,  # Nivel adicional para pagos
                        use_timestamp=False  # Sin timestamp para permitir sobreescritura
                    )
                    
                    documentos_info = successful
                    
                    if failed:
                        logger.error(f"Algunos documentos fallaron al subir: {len(failed)}")
                        return {
                            "success": False,
                            "error": f"Error subiendo {len(failed)} documento(s)",
                            "failed_files": [f.get('filename') for f in failed]
                        }
                    
                    logger.info(f"✅ Subidos {len(successful)} documentos para pago de RPC {numero_rpc}")
                else:
                    return {
                        "success": False,
                        "error": "No se pudo validar ningún documento para subir"
                    }
                    
            except Exception as e:
                logger.error(f"Error subiendo documentos a S3: {e}")
                return {
                    "success": False,
                    "error": f"Error subiendo documentos a S3: {str(e)}"
                }
        else:
            logger.info(f"📝 Registro de pago sin documentos para RPC {numero_rpc}")

        # Preparar datos para guardar
        # fecha_registro se genera automáticamente con la hora del sistema
        datos_completos = {
            "numero_rpc": numero_rpc,
            "valor_pago": valor_pago,
            "fecha_transaccion": datos_pago.get("fecha_transaccion", "").strip(),
            "referencia_contrato": datos_pago.get("referencia_contrato", "").strip(),
            "nombre_centro_gestor": datos_pago.get("nombre_centro_gestor", "").strip(),
            "documentos_s3": documentos_info if documentos_info else [],
            "fecha_registro": datetime.now(),  # Timestamp automático del sistema
            "fecha_creacion": datetime.now(),
            "fecha_actualizacion": datetime.now(),
            "estado": "registrado",
            "tipo": "pago_manual"
        }

        # Guardar en Firestore
        doc_ref = db_client.collection('pagos_emprestito').add(datos_completos)
        doc_id = doc_ref[1].id

        logger.info(f"Pago de empréstito creado exitosamente: {doc_id}")

        return {
            "success": True,
            "doc_id": doc_id,
            "data": serialize_datetime_objects(datos_completos),
            "message": f"Pago registrado exitosamente para RPC {numero_rpc}" + (f" con {len(documentos_info)} documentos" if documentos_info else ""),
            "coleccion": "pagos_emprestito",
            "timestamp": datetime.now().isoformat(),
            "documentos_count": len(documentos_info)
        }

    except Exception as e:
        logger.error(f"Error cargando pago de empréstito: {e}")
        return {
            "success": False,
            "error": str(e)
        }

async def get_pagos_emprestito_all() -> Dict[str, Any]:
    """
    Obtener todos los pagos de empréstito desde la colección pagos_emprestito
    e incluir información sobre si tienen documentos soporte en S3.
    
    El campo 'bp' se hereda de las colecciones: 
    - 'contratos_emprestito' (prioridad 1)
    - 'convenios_transferencias_emprestito' (prioridad 2)
    - 'ordenes_compra_emprestito' (prioridad 3)
    
    OPTIMIZACIÓN: Se cargan todas las colecciones en memoria para evitar múltiples
    consultas a Firestore y prevenir timeouts.
    """
    if not FIRESTORE_AVAILABLE:
        return {
            "success": False,
            "error": "Firebase no disponible",
            "data": [],
            "count": 0
        }

    try:
        db_client = get_firestore_client()
        if not db_client:
            return {
                "success": False,
                "error": "Error obteniendo cliente Firestore",
                "data": [],
                "count": 0
            }

        logger.info("Iniciando carga de pagos con herencia de BP desde múltiples colecciones")

        # PASO 1: Cargar TODAS las colecciones en memoria (optimización para evitar timeouts)
        logger.info("Cargando contratos_emprestito...")
        contratos_map = {}  # {referencia_contrato: bp}
        try:
            for doc in db_client.collection('contratos_emprestito').stream():
                data = doc.to_dict()
                ref = data.get('referencia_contrato', '').strip()
                bp = data.get('bp', '').strip()
                if ref and bp:
                    contratos_map[ref] = bp
            logger.info(f"✓ Cargados {len(contratos_map)} contratos con BP")
        except Exception as e:
            logger.error(f"Error cargando contratos_emprestito: {e}")

        logger.info("Cargando convenios_transferencias_emprestito...")
        convenios_map = {}  # {referencia_contrato: bp}
        try:
            for doc in db_client.collection('convenios_transferencias_emprestito').stream():
                data = doc.to_dict()
                ref = data.get('referencia_contrato', '').strip()
                bp = data.get('bp', '').strip()
                if ref and bp:
                    convenios_map[ref] = bp
            logger.info(f"✓ Cargados {len(convenios_map)} convenios con BP")
        except Exception as e:
            logger.error(f"Error cargando convenios_transferencias_emprestito: {e}")

        logger.info("Cargando ordenes_compra_emprestito...")
        ordenes_map = {}  # {nombre_centro_gestor: bp}
        try:
            for doc in db_client.collection('ordenes_compra_emprestito').stream():
                data = doc.to_dict()
                centro = data.get('nombre_centro_gestor', '').strip()
                bp = data.get('bp', '').strip()
                if centro and bp:
                    ordenes_map[centro] = bp
            logger.info(f"✓ Cargadas {len(ordenes_map)} órdenes con BP")
        except Exception as e:
            logger.error(f"Error cargando ordenes_compra_emprestito: {e}")

        # PASO 2: Obtener y procesar pagos
        logger.info("Procesando pagos...")
        pagos_ref = db_client.collection('pagos_emprestito')
        docs = pagos_ref.stream()

        pagos_list = []
        bp_stats = {'contratos': 0, 'convenios': 0, 'ordenes': 0, 'sin_bp': 0}
        
        for doc in docs:
            pago_data = doc.to_dict()
            pago_data['id'] = doc.id
            
            # Heredar BP
            bp_heredado = ''
            referencia_contrato = pago_data.get('referencia_contrato', '').strip()
            nombre_centro_gestor = pago_data.get('nombre_centro_gestor', '').strip()
            
            # PRIORIDAD 1: Buscar en contratos_map
            if referencia_contrato and referencia_contrato in contratos_map:
                bp_heredado = contratos_map[referencia_contrato]
                bp_stats['contratos'] += 1
            
            # PRIORIDAD 2: Buscar en convenios_map
            elif referencia_contrato and referencia_contrato in convenios_map:
                bp_heredado = convenios_map[referencia_contrato]
                bp_stats['convenios'] += 1
            
            # PRIORIDAD 3: Buscar en ordenes_map
            elif nombre_centro_gestor and nombre_centro_gestor in ordenes_map:
                bp_heredado = ordenes_map[nombre_centro_gestor]
                bp_stats['ordenes'] += 1
            
            else:
                bp_stats['sin_bp'] += 1
            
            # Asignar bp heredado
            pago_data['bp'] = bp_heredado
            
            # Detectar si tiene documentos soporte revisando la variable documentos_s3
            documentos_s3 = pago_data.get('documentos_s3', [])
            tiene_documentos_soporte = False
            
            if documentos_s3 and isinstance(documentos_s3, list) and len(documentos_s3) > 0:
                # Verificar que al menos un documento tenga URL válida
                tiene_documentos_soporte = any(
                    doc.get('s3_url') or doc.get('url') 
                    for doc in documentos_s3 
                    if isinstance(doc, dict)
                )
            
            # Agregar campo tiene_documentos_soporte
            pago_data['tiene_documentos_soporte'] = tiene_documentos_soporte
            
            # Serializar objetos datetime
            pago_data = serialize_datetime_objects(pago_data)
            
            pagos_list.append(pago_data)

        logger.info(f"✓ Procesados {len(pagos_list)} pagos | BP desde contratos: {bp_stats['contratos']}, convenios: {bp_stats['convenios']}, órdenes: {bp_stats['ordenes']}, sin BP: {bp_stats['sin_bp']}")

        return {
            "success": True,
            "data": pagos_list,
            "count": len(pagos_list),
            "collection": "pagos_emprestito",
            "timestamp": datetime.now().isoformat(),
            "bp_inheritance_stats": bp_stats
        }

    except Exception as e:
        logger.error(f"Error obteniendo pagos de empréstito: {e}")
        return {
            "success": False,
            "error": str(e),
            "data": [],
            "count": 0
        }

async def get_rpc_contratos_emprestito_all() -> Dict[str, Any]:
    """
    Obtener todos los RPCs (Registros Presupuestales de Compromiso) de empréstito
    desde la colección rpc_contratos_emprestito.
    
    El campo 'bp' se hereda de las colecciones: 
    - 'contratos_emprestito' (prioridad 1)
    - 'convenios_transferencias_emprestito' (prioridad 2)
    - 'ordenes_compra_emprestito' (prioridad 3)
    
    El valor de 'bp' NO se lee desde rpc_contratos_emprestito, solo se hereda.
    
    OPTIMIZACIÓN: Se cargan todas las colecciones en memoria para evitar múltiples
    consultas a Firestore y prevenir timeouts.
    """
    if not FIRESTORE_AVAILABLE:
        return {
            "success": False,
            "error": "Firebase no disponible",
            "data": [],
            "count": 0
        }

    try:
        db_client = get_firestore_client()
        if not db_client:
            return {
                "success": False,
                "error": "Error obteniendo cliente Firestore",
                "data": [],
                "count": 0
            }

        logger.info("Iniciando carga de RPCs con herencia de BP desde múltiples colecciones")

        # PASO 1: Cargar TODAS las colecciones en memoria (optimización para evitar timeouts)
        logger.info("Cargando contratos_emprestito...")
        contratos_map = {}  # {referencia_contrato: bp}
        try:
            for doc in db_client.collection('contratos_emprestito').stream():
                data = doc.to_dict()
                ref = data.get('referencia_contrato', '').strip()
                bp = data.get('bp', '').strip()
                if ref and bp:
                    contratos_map[ref] = bp
            logger.info(f"✓ Cargados {len(contratos_map)} contratos con BP")
        except Exception as e:
            logger.error(f"Error cargando contratos_emprestito: {e}")

        logger.info("Cargando convenios_transferencias_emprestito...")
        convenios_map = {}  # {referencia_contrato: bp}
        try:
            for doc in db_client.collection('convenios_transferencias_emprestito').stream():
                data = doc.to_dict()
                ref = data.get('referencia_contrato', '').strip()
                bp = data.get('bp', '').strip()
                if ref and bp:
                    convenios_map[ref] = bp
            logger.info(f"✓ Cargados {len(convenios_map)} convenios con BP")
        except Exception as e:
            logger.error(f"Error cargando convenios_transferencias_emprestito: {e}")

        logger.info("Cargando ordenes_compra_emprestito...")
        ordenes_map = {}  # {nombre_centro_gestor: bp}
        try:
            for doc in db_client.collection('ordenes_compra_emprestito').stream():
                data = doc.to_dict()
                centro = data.get('nombre_centro_gestor', '').strip()
                bp = data.get('bp', '').strip()
                if centro and bp:
                    ordenes_map[centro] = bp
            logger.info(f"✓ Cargadas {len(ordenes_map)} órdenes con BP")
        except Exception as e:
            logger.error(f"Error cargando ordenes_compra_emprestito: {e}")

        # PASO 2: Obtener y procesar RPCs
        logger.info("Procesando RPCs...")
        rpc_ref = db_client.collection('rpc_contratos_emprestito')
        docs = rpc_ref.stream()

        rpc_list = []
        bp_stats = {'contratos': 0, 'convenios': 0, 'ordenes': 0, 'sin_bp': 0}
        
        for doc in docs:
            rpc_data = doc.to_dict()
            rpc_data['id'] = doc.id
            
            bp_heredado = ''
            referencia_contrato = rpc_data.get('referencia_contrato', '').strip()
            nombre_centro_gestor = rpc_data.get('nombre_centro_gestor', '').strip()
            
            # PRIORIDAD 1: Buscar en contratos_map
            if referencia_contrato and referencia_contrato in contratos_map:
                bp_heredado = contratos_map[referencia_contrato]
                bp_stats['contratos'] += 1
            
            # PRIORIDAD 2: Buscar en convenios_map
            elif referencia_contrato and referencia_contrato in convenios_map:
                bp_heredado = convenios_map[referencia_contrato]
                bp_stats['convenios'] += 1
            
            # PRIORIDAD 3: Buscar en ordenes_map
            elif nombre_centro_gestor and nombre_centro_gestor in ordenes_map:
                bp_heredado = ordenes_map[nombre_centro_gestor]
                bp_stats['ordenes'] += 1
            
            else:
                bp_stats['sin_bp'] += 1
            
            # Asignar bp heredado
            rpc_data['bp'] = bp_heredado
            
            # Serializar objetos datetime
            rpc_data = serialize_datetime_objects(rpc_data)
            
            rpc_list.append(rpc_data)

        logger.info(f"✓ Procesados {len(rpc_list)} RPCs | BP desde contratos: {bp_stats['contratos']}, convenios: {bp_stats['convenios']}, órdenes: {bp_stats['ordenes']}, sin BP: {bp_stats['sin_bp']}")

        return {
            "success": True,
            "data": rpc_list,
            "count": len(rpc_list),
            "collection": "rpc_contratos_emprestito",
            "timestamp": datetime.now().isoformat(),
            "bp_inheritance_stats": bp_stats
        }

    except Exception as e:
        logger.error(f"Error obteniendo RPCs de empréstito: {e}")
        return {
            "success": False,
            "error": str(e),
            "data": [],
            "count": 0
        }


async def actualizar_rpc_contrato_emprestito(numero_rpc: str, datos_actualizacion: Dict[str, Any]) -> Dict[str, Any]:
    """
    Actualiza un RPC existente en la colección rpc_contratos_emprestito por numero_rpc
    Solo actualiza los campos proporcionados, manteniendo los demás sin cambios
    
    Args:
        numero_rpc (str): Número del RPC a actualizar
        datos_actualizacion (dict): Datos a actualizar (solo los campos proporcionados serán modificados)
    
    Returns:
        Dict con el resultado de la operación
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

        # Validar que numero_rpc sea válido
        if not numero_rpc or not numero_rpc.strip():
            return {
                "success": False,
                "error": "El numero_rpc es requerido"
            }

        # Buscar RPC por numero_rpc
        rpc_ref = db_client.collection('rpc_contratos_emprestito')
        query_resultado = rpc_ref.where('numero_rpc', '==', numero_rpc.strip()).get()

        if len(query_resultado) == 0:
            return {
                "success": False,
                "error": f"No se encontró ningún RPC con numero_rpc: {numero_rpc}",
                "numero_rpc": numero_rpc
            }

        # Obtener el documento
        doc = query_resultado[0]
        doc_data = doc.to_dict()
        doc_ref = rpc_ref.document(doc.id)

        # Campos que pueden actualizarse (excluir campos de sistema)
        campos_protegidos = ["fecha_creacion", "tipo"]
        
        # Preparar datos para actualizar
        datos_finales = {}
        campos_actualizados = []

        for campo, valor in datos_actualizacion.items():
            # No actualizar campos protegidos
            if campo in campos_protegidos:
                logger.warning(f"Campo protegido '{campo}' no será actualizado")
                continue
                
            # Procesar según el tipo de campo
            if campo == "valor_rpc":
                # Asegurar que sea numérico y mayor o igual a 0
                try:
                    valor_numerico = float(valor)
                    if valor_numerico < 0:
                        logger.warning(f"Valor negativo no permitido para valor_rpc: {valor}")
                        continue
                    datos_finales[campo] = valor_numerico
                    campos_actualizados.append(campo)
                except (ValueError, TypeError):
                    logger.warning(f"Valor inválido para valor_rpc: {valor}")
                    continue
                    
            elif campo == "cdp_asociados":
                # Procesar lista de CDPs
                if isinstance(valor, list):
                    datos_finales[campo] = [str(cdp).strip() for cdp in valor if cdp]
                elif isinstance(valor, str):
                    datos_finales[campo] = [cdp.strip() for cdp in valor.split(",") if cdp.strip()]
                else:
                    datos_finales[campo] = []
                campos_actualizados.append(campo)
                
            elif campo == "programacion_pac":
                # Validar que sea diccionario
                if isinstance(valor, dict):
                    datos_finales[campo] = valor
                    campos_actualizados.append(campo)
                else:
                    logger.warning(f"programacion_pac debe ser un diccionario")
                    continue
                    
            elif isinstance(valor, str):
                # Limpiar strings
                valor_limpio = valor.strip()
                if valor_limpio:  # Solo actualizar si no está vacío
                    datos_finales[campo] = valor_limpio
                    campos_actualizados.append(campo)
            else:
                # Otros tipos de datos
                datos_finales[campo] = valor
                campos_actualizados.append(campo)

        # Verificar que haya al menos un campo para actualizar
        if not datos_finales:
            return {
                "success": False,
                "error": "No hay campos válidos para actualizar"
            }

        # Agregar fecha de actualización
        datos_finales["fecha_actualizacion"] = datetime.now()

        # Actualizar el documento
        doc_ref.update(datos_finales)

        logger.info(f"✅ RPC actualizado: {numero_rpc} - Campos modificados: {campos_actualizados}")

        # Obtener datos actualizados
        doc_actualizado = doc_ref.get()
        datos_actualizados_completos = serialize_datetime_objects(doc_actualizado.to_dict())
        datos_actualizados_completos['id'] = doc_actualizado.id

        return {
            "success": True,
            "message": f"RPC {numero_rpc} actualizado exitosamente",
            "numero_rpc": numero_rpc,
            "doc_id": doc.id,
            "coleccion": "rpc_contratos_emprestito",
            "datos_previos": serialize_datetime_objects(doc_data),
            "datos_actualizados": datos_actualizados_completos,
            "campos_modificados": campos_actualizados,
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"❌ Error actualizando RPC: {str(e)}")
        return {
            "success": False,
            "error": f"Error actualizando RPC: {str(e)}"
        }


async def get_asignaciones_emprestito_banco_centro_gestor_all() -> Dict[str, Any]:
    """
    Obtener todas las asignaciones de empréstito banco-centro gestor
    desde la colección montos_emprestito_asignados_centro_gestor
    """
    if not FIRESTORE_AVAILABLE:
        return {
            "success": False,
            "error": "Firebase no disponible",
            "data": [],
            "count": 0
        }

    try:
        db_client = get_firestore_client()
        if not db_client:
            return {
                "success": False,
                "error": "Error obteniendo cliente Firestore",
                "data": [],
                "count": 0
            }

        # Obtener todos los documentos de la colección
        asignaciones_ref = db_client.collection('montos_emprestito_asignados_centro_gestor')
        docs = asignaciones_ref.stream()

        # Procesar documentos
        asignaciones_list = []
        for doc in docs:
            asignacion_data = doc.to_dict()
            asignacion_data['id'] = doc.id
            
            # Serializar objetos datetime
            asignacion_data = serialize_datetime_objects(asignacion_data)
            
            asignaciones_list.append(asignacion_data)

        logger.info(f"Se obtuvieron {len(asignaciones_list)} asignaciones de empréstito banco-centro gestor")

        return {
            "success": True,
            "data": asignaciones_list,
            "count": len(asignaciones_list),
            "collection": "montos_emprestito_asignados_centro_gestor",
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Error obteniendo asignaciones de empréstito banco-centro gestor: {e}")
        return {
            "success": False,
            "error": str(e),
            "data": [],
            "count": 0
        }

async def obtener_datos_secop_completos(referencia_proceso: str, nit_entidad: Optional[str] = None) -> Dict[str, Any]:
    """
    Obtener datos completos de un proceso desde la API del SECOP
    Incluye todos los campos adicionales solicitados para complementar procesos_emprestito
    
    Args:
        referencia_proceso: Referencia del proceso a buscar
        nit_entidad: NIT de la entidad (opcional). Si no se proporciona, busca sin filtro de NIT.
    """
    try:
        # Importar Socrata aquí para evitar errores de importación si no está disponible
        from sodapy import Socrata
        
        # Configuración SECOP
        SECOP_DOMAIN = "www.datos.gov.co"
        DATASET_ID = "p6dx-8zbt"
        NIT_ENTIDAD_CALI = "890399011"

        # Cliente no autenticado para datos públicos
        client = Socrata(SECOP_DOMAIN, None, timeout=30)

        # Construir filtro para búsqueda específica
        # Si se proporciona NIT, filtrar por él. Si no, buscar sin filtro de NIT
        if nit_entidad:
            where_clause = f"nit_entidad='{nit_entidad}' AND referencia_del_proceso='{referencia_proceso}'"
            logger.info(f"🔍 Buscando proceso {referencia_proceso} con NIT {nit_entidad}")
        else:
            where_clause = f"referencia_del_proceso='{referencia_proceso}'"
            logger.info(f"🔍 Buscando proceso {referencia_proceso} sin filtro de NIT")

        # Realizar consulta
        results = client.get(
            DATASET_ID,
            where=where_clause,
            limit=1  # Solo necesitamos un resultado
        )

        client.close()

        if not results:
            # Si no se encontró con el NIT proporcionado (o sin NIT), intentar sin restricción
            if nit_entidad:
                logger.warning(f"⚠️ No se encontró el proceso {referencia_proceso} con NIT {nit_entidad}, reintentando sin filtro de NIT...")
                return await obtener_datos_secop_completos(referencia_proceso, nit_entidad=None)
            
            return {
                "success": False,
                "error": f"No se encontró el proceso {referencia_proceso} en SECOP"
            }

        # Tomar el primer resultado
        proceso_raw = results[0]

        # Log para debugging: ver todos los campos disponibles
        logger.info(f"Obteniendo datos completos SECOP para {referencia_proceso}")

        # Mapear campos completos según especificaciones
        # Mantener nombres de variables en Firebase sin cambiar, pero mapear desde SECOP
        
        # Determinar estado del proceso de manera inteligente
        # Prioridad: estado_resumen > adjudicado > estado_del_procedimiento
        adjudicado_raw = proceso_raw.get("adjudicado", "")
        estado_resumen_raw = proceso_raw.get("estado_resumen", "")
        estado_procedimiento_raw = proceso_raw.get("estado_del_procedimiento", "")
        
        # Lógica para determinar el estado correcto
        estado_proceso_final = estado_procedimiento_raw  # Default
        if estado_resumen_raw and estado_resumen_raw.strip():
            # Si hay estado_resumen, usarlo como estado principal
            estado_proceso_final = estado_resumen_raw
        elif adjudicado_raw and adjudicado_raw.lower() in ["sí", "si", "yes", "true"]:
            # Si está marcado como adjudicado, el estado debe ser Adjudicado
            estado_proceso_final = "Adjudicado"
        
        proceso_datos_completos = {
            # Campos básicos existentes
            "adjudicado": adjudicado_raw,
            "fase": proceso_raw.get("fase", ""),
            "estado_proceso": estado_proceso_final,  # Estado determinado inteligentemente
            
            # Campos adicionales solicitados con mapeo exacto
            "fecha_publicacion_fase": proceso_raw.get("fecha_de_publicacion_del", ""),
            "fecha_publicacion_fase_1": None,  # No disponible en SECOP
            "fecha_publicacion_fase_2": None,  # No disponible en SECOP
            "fecha_publicacion_fase_3": proceso_raw.get("fecha_de_publicacion_fase_3", ""),
            
            "proveedores_invitados": proceso_raw.get("proveedores_invitados", 0),
            "proveedores_con_invitacion": proceso_raw.get("proveedores_con_invitacion", 0),
            "visualizaciones_proceso": proceso_raw.get("visualizaciones_del", 0),
            "proveedores_que_manifestaron": proceso_raw.get("proveedores_que_manifestaron", 0),
            "numero_lotes": proceso_raw.get("numero_de_lotes", 0),
            "fecha_adjudicacion": None,  # No disponible directamente en SECOP
            "estado_resumen": proceso_raw.get("estado_resumen", ""),
            "fecha_recepcion_respuestas": None,  # No disponible en SECOP
            "fecha_apertura_respuestas": None,  # No disponible en SECOP
            "fecha_apertura_efectiva": None,  # No disponible en SECOP
            "respuestas_procedimiento": proceso_raw.get("respuestas_al_procedimiento", 0),
            "respuestas_externas": proceso_raw.get("respuestas_externas", 0),
            "conteo_respuestas_ofertas": proceso_raw.get("conteo_de_respuestas_a_ofertas", 0),
        }

        # Convertir valores numéricos
        campos_numericos = [
            "proveedores_invitados", "proveedores_con_invitacion", "visualizaciones_proceso",
            "proveedores_que_manifestaron", "numero_lotes", "respuestas_procedimiento",
            "respuestas_externas", "conteo_respuestas_ofertas"
        ]
        
        for campo in campos_numericos:
            try:
                valor = proceso_datos_completos.get(campo, 0)
                if valor is not None and str(valor).strip() != "":
                    proceso_datos_completos[campo] = int(float(str(valor)))
                else:
                    proceso_datos_completos[campo] = 0
            except (ValueError, TypeError):
                logger.warning(f"⚠️ Error convertiendo campo numérico {campo}: {proceso_datos_completos.get(campo)}")
                proceso_datos_completos[campo] = 0

        return {
            "success": True,
            "data": proceso_datos_completos
        }

    except ImportError:
        logger.error("sodapy no está instalado. Instala con: pip install sodapy")
        return {
            "success": False,
            "error": "sodapy no está disponible. Instala con: pip install sodapy"
        }
    except Exception as e:
        logger.error(f"Error obteniendo datos completos de SECOP: {e}")
        return {
            "success": False,
            "error": str(e)
        }

async def actualizar_proceso_emprestito_completo(referencia_proceso: str) -> Dict[str, Any]:
    """
    Actualizar un proceso de empréstito existente con datos completos de SECOP
    sin afectar campos existentes, solo complementando con nuevos datos
    """
    try:
        if not FIRESTORE_AVAILABLE:
            return {"success": False, "error": "Firebase no disponible"}
        
        db = get_firestore_client()
        if db is None:
            return {"success": False, "error": "No se pudo conectar a Firestore"}
        
        # 1. Verificar que el proceso existe en procesos_emprestito
        collection_ref = db.collection('procesos_emprestito')
        query = collection_ref.where('referencia_proceso', '==', referencia_proceso).limit(1)
        docs = list(query.stream())
        
        if not docs:
            return {
                "success": False,
                "error": f"No se encontró el proceso {referencia_proceso} en la colección procesos_emprestito"
            }
        
        doc = docs[0]
        doc_data = doc.to_dict()
        
        # 2. Obtener datos completos de SECOP
        # Primero intentar con el NIT de Cali, luego sin restricción si no se encuentra
        NIT_ENTIDAD_CALI = "890399011"
        resultado_secop = await obtener_datos_secop_completos(referencia_proceso, nit_entidad=NIT_ENTIDAD_CALI)
        
        if not resultado_secop.get("success"):
            return {
                "success": False,
                "error": f"Error obteniendo datos de SECOP: {resultado_secop.get('error')}"
            }
        
        datos_secop = resultado_secop["data"]
        
        # 3. Preparar datos para actualización (solo los campos nuevos)
        datos_actualizacion = {}
        campos_cambios = []
        
        for campo, valor_nuevo in datos_secop.items():
            valor_actual = doc_data.get(campo)
            
            # Solo actualizar si el campo no existe o ha cambiado
            if valor_actual != valor_nuevo:
                datos_actualizacion[campo] = valor_nuevo
                campos_cambios.append(f"{campo}: '{valor_actual}' → '{valor_nuevo}'")
        
        # 4. Si no hay cambios, no actualizar
        if not datos_actualizacion:
            return {
                "success": True,
                "message": f"Proceso {referencia_proceso} ya está actualizado, no se requieren cambios",
                "changes_count": 0,
                "doc_id": doc.id
            }
        
        # 5. Agregar timestamp de actualización
        datos_actualizacion["fecha_actualizacion_completa"] = datetime.now()
        
        # 6. Actualizar el documento
        doc.reference.update(datos_actualizacion)
        
        logger.info(f"✅ Proceso {referencia_proceso} actualizado con {len(datos_actualizacion)} campos")
        
        return {
            "success": True,
            "message": f"Proceso {referencia_proceso} actualizado exitosamente",
            "doc_id": doc.id,
            "changes_count": len(datos_actualizacion),
            "changes_summary": campos_cambios[:10],  # Mostrar máximo 10 cambios
            "datos_actualizados": serialize_datetime_objects(datos_actualizacion)
        }
        
    except Exception as e:
        logger.error(f"Error actualizando proceso completo: {e}")
        return {
            "success": False,
            "error": str(e)
        }

async def procesar_todos_procesos_emprestito_completo() -> Dict[str, Any]:
    """
    Procesar TODOS los procesos de empréstito de la colección para actualizarlos
    con datos completos de SECOP sin requerir parámetros de entrada
    """
    try:
        import time
        start_time = time.time()
        
        if not FIRESTORE_AVAILABLE:
            return {"success": False, "error": "Firebase no disponible"}
        
        db = get_firestore_client()
        if db is None:
            return {"success": False, "error": "No se pudo conectar a Firestore"}
        
        # 1. Obtener todos los procesos de la colección procesos_emprestito
        logger.info("🔍 Obteniendo todos los procesos de empréstito para actualización completa...")
        collection_ref = db.collection('procesos_emprestito')
        docs = list(collection_ref.stream())
        
        if not docs:
            return {
                "success": False,
                "error": "No se encontraron procesos en la colección procesos_emprestito",
                "total_procesos_encontrados": 0
            }
        
        logger.info(f"📊 Encontrados {len(docs)} procesos para actualizar con datos completos de SECOP")
        
        # 2. Inicializar contadores y resultados
        total_procesos = len(docs)
        procesos_procesados = 0
        procesos_actualizados = 0
        procesos_sin_cambios = 0
        procesos_con_errores = 0
        total_campos_actualizados = 0
        
        resultados_detallados = []
        errores_detallados = []
        
        # 3. Procesar cada proceso individualmente
        for i, doc in enumerate(docs, 1):
            doc_data = doc.to_dict()
            referencia_proceso = doc_data.get('referencia_proceso')
            
            if not referencia_proceso:
                error_msg = f"Proceso {doc.id} no tiene 'referencia_proceso'"
                logger.warning(f"⚠️ {error_msg}")
                errores_detallados.append(error_msg)
                procesos_con_errores += 1
                continue
            
            try:
                # Calcular tiempo estimado restante
                if i > 1:
                    tiempo_transcurrido = time.time() - start_time
                    tiempo_promedio_por_proceso = tiempo_transcurrido / (i - 1)
                    procesos_restantes = total_procesos - i + 1
                    tiempo_estimado_restante = tiempo_promedio_por_proceso * procesos_restantes
                    logger.info(f"🔄 Procesando {i}/{total_procesos}: {referencia_proceso} (ETA: {tiempo_estimado_restante:.1f}s)")
                else:
                    logger.info(f"🔄 Procesando {i}/{total_procesos}: {referencia_proceso}")
                
                # Actualizar proceso individual con datos completos
                resultado_individual = await actualizar_proceso_emprestito_completo(referencia_proceso)
                
                procesos_procesados += 1
                
                if resultado_individual.get("success"):
                    changes_count = resultado_individual.get("changes_count", 0)
                    
                    if changes_count > 0:
                        procesos_actualizados += 1
                        total_campos_actualizados += changes_count
                        logger.info(f"✅ {referencia_proceso}: {changes_count} campos actualizados")
                    else:
                        procesos_sin_cambios += 1
                        logger.info(f"ℹ️ {referencia_proceso}: sin cambios necesarios")
                    
                    # Agregar resultado detallado
                    resultado_detalle = {
                        "referencia_proceso": referencia_proceso,
                        "success": True,
                        "changes_count": changes_count,
                        "changes_summary": resultado_individual.get("changes_summary", [])[:3]  # Máximo 3 cambios
                    }
                    
                    if changes_count == 0:
                        resultado_detalle["message"] = "Ya está actualizado"
                    
                    resultados_detallados.append(resultado_detalle)
                    
                else:
                    procesos_con_errores += 1
                    error_msg = f"{referencia_proceso}: {resultado_individual.get('error', 'Error desconocido')}"
                    logger.error(f"❌ {error_msg}")
                    errores_detallados.append(error_msg)
                    
                    resultados_detallados.append({
                        "referencia_proceso": referencia_proceso,
                        "success": False,
                        "error": resultado_individual.get("error", "Error desconocido")
                    })
                
            except Exception as e:
                procesos_con_errores += 1
                error_msg = f"{referencia_proceso}: Excepción - {str(e)}"
                logger.error(f"❌ {error_msg}")
                errores_detallados.append(error_msg)
                
                resultados_detallados.append({
                    "referencia_proceso": referencia_proceso,
                    "success": False,
                    "error": str(e)
                })
        
        # 4. Calcular tiempo de procesamiento
        end_time = time.time()
        tiempo_procesamiento = round(end_time - start_time, 2)
        
        # 5. Preparar respuesta final
        mensaje_resumen = f"Se procesaron {procesos_procesados} procesos de empréstito exitosamente"
        if procesos_con_errores > 0:
            mensaje_resumen += f" ({procesos_con_errores} con errores)"
        
        resultado_final = {
            "success": True,
            "message": mensaje_resumen,
            "resumen_procesamiento": {
                "total_procesos_encontrados": total_procesos,
                "procesos_procesados": procesos_procesados,
                "procesos_actualizados": procesos_actualizados,
                "procesos_sin_cambios": procesos_sin_cambios,
                "procesos_con_errores": procesos_con_errores
            },
            "resultados_detallados": resultados_detallados,
            "estadisticas": {
                "total_campos_actualizados": total_campos_actualizados,
                "tiempo_procesamiento": f"{tiempo_procesamiento} segundos"
            },
            "timestamp": datetime.now().isoformat()
        }
        
        # 6. Agregar errores si los hay
        if errores_detallados:
            resultado_final["errores"] = errores_detallados[:10]  # Máximo 10 errores
        
        logger.info(f"""
✅ Procesamiento completo finalizado:
   📊 Total procesos: {total_procesos}
   ✅ Procesados: {procesos_procesados}
   🔄 Actualizados: {procesos_actualizados}
   ℹ️ Sin cambios: {procesos_sin_cambios}
   ❌ Con errores: {procesos_con_errores}
   📈 Campos actualizados: {total_campos_actualizados}
   ⏱️ Tiempo: {tiempo_procesamiento}s
        """)
        
        return resultado_final
        
    except Exception as e:
        logger.error(f"Error procesando todos los procesos de empréstito: {e}")
        return {
            "success": False,
            "error": str(e)
        }

# ============================================================================
# FUNCIONES PARA PROYECCIONES DE EMPRÉSTITO DESDE GOOGLE SHEETS
# ============================================================================

async def leer_google_sheets_proyecciones(sheet_url: str) -> Dict[str, Any]:
    """
    Lee datos de Google Sheets usando autenticación con service account
    
    Args:
        sheet_url: URL del Google Sheet
        
    Returns:
        Dict con success, data (DataFrame) y mensaje
    """
    try:
        import gspread
        from google.oauth2.service_account import Credentials
        
        # Extraer el ID del spreadsheet de la URL (múltiples formatos soportados)
        sheet_id = None
        
        # Formato 1: URL completa con /spreadsheets/d/
        sheet_id_match = re.search(r'/spreadsheets/d/([a-zA-Z0-9-_]+)', sheet_url)
        if sheet_id_match:
            sheet_id = sheet_id_match.group(1)
        else:
            # Formato 2: URL corta docs.google.com/spreadsheets/u/0/d/
            sheet_id_match = re.search(r'/spreadsheets/u/\d+/d/([a-zA-Z0-9-_]+)', sheet_url)
            if sheet_id_match:
                sheet_id = sheet_id_match.group(1)
            else:
                # Formato 3: Solo el ID (si viene sin URL completa)
                if re.match(r'^[a-zA-Z0-9-_]+$', sheet_url.strip()):
                    sheet_id = sheet_url.strip()
        
        if not sheet_id:
            logger.error(f"❌ No se pudo extraer ID de la URL: {sheet_url}")
            return {
                "success": False,
                "error": f"No se pudo extraer el ID del Google Sheet de la URL proporcionada. URL recibida: {sheet_url}"
            }
        
        logger.info(f"📊 Accediendo a Google Sheets ID: {sheet_id}")
        
        # Obtener credenciales de Firebase para Google Sheets
        import firebase_admin
        from firebase_admin import credentials
        import os
        import json
        import base64
        
        # ESTRATEGIA DE CREDENCIALES (prioridad en orden):
        # 1. Archivo local service account (desarrollo)
        # 2. Variable de entorno FIREBASE_SERVICE_ACCOUNT_KEY (producción)
        # 3. Application Default Credentials (último recurso)
        
        gc = None
        service_account_file = "credentials/unidad-cumplimiento-drive.json"
        service_account_email = "unidad-cumplimiento-drive@unidad-cumplimiento.iam.gserviceaccount.com"
        scopes = [
            'https://www.googleapis.com/auth/spreadsheets.readonly',
            'https://www.googleapis.com/auth/drive.readonly'
        ]
        
        try:
            # OPCIÓN 1: Intentar archivo local (desarrollo)
            import os
            if os.path.exists(service_account_file):
                from google.oauth2.service_account import Credentials
                
                sheets_credentials = Credentials.from_service_account_file(
                    service_account_file, 
                    scopes=scopes
                )
                logger.info(f"🔑 Usando service account desde archivo: {service_account_email}")
                gc = gspread.authorize(sheets_credentials)
                logger.info("✅ Cliente gspread autorizado con archivo local")
            else:
                raise FileNotFoundError("Archivo de service account no encontrado en desarrollo")
                
        except Exception as file_error:
            logger.warning(f"⚠️ Service account desde archivo no disponible: {str(file_error)}")
            
            try:
                # OPCIÓN 2: Variable de entorno (producción - Railway, etc)
                firebase_key = os.getenv("FIREBASE_SERVICE_ACCOUNT_KEY")
                if firebase_key:
                    # Decodificar las credenciales
                    service_account_info = json.loads(base64.b64decode(firebase_key).decode('utf-8'))
                    service_account_email = service_account_info.get('client_email', service_account_email)
                    
                    logger.info(f"🔑 Usando service account desde env: {service_account_email}")
                    
                    # Crear credenciales con los scopes necesarios
                    from google.oauth2.service_account import Credentials
                    sheets_credentials = Credentials.from_service_account_info(
                        service_account_info, 
                        scopes=scopes
                    )
                    
                    gc = gspread.authorize(sheets_credentials)
                    logger.info("✅ Cliente gspread autorizado con variable de entorno")
                else:
                    raise ValueError("FIREBASE_SERVICE_ACCOUNT_KEY no encontrada en variables de entorno")
                    
            except Exception as env_error:
                logger.warning(f"⚠️ Credenciales desde variable de entorno no disponibles: {str(env_error)}")
                
                try:
                    # OPCIÓN 3: Application Default Credentials (último recurso)
                    from google.auth import default
                    
                    sheets_credentials, project_id = default(scopes=scopes)
                    logger.info(f"🔑 Usando Application Default Credentials para Google Sheets")
                    logger.info(f"🆔 Proyecto detectado: {project_id}")
                    
                    gc = gspread.authorize(sheets_credentials)
                    logger.info("✅ Cliente gspread autorizado con ADC")
                    
                except Exception as adc_error:
                    logger.error(f"❌ Todas las opciones de credenciales fallaron")
                    logger.error(f"   - Archivo local: {str(file_error)}")
                    logger.error(f"   - Variable entorno: {str(env_error)}")
                    logger.error(f"   - ADC: {str(adc_error)}")
                    return {
                        "success": False,
                        "error": f"Error obteniendo credenciales para Google Sheets: {str(adc_error)}"
                    }
        
        if gc is None:
            return {
                "success": False,
                "error": "No se pudo crear cliente de Google Sheets con ninguna credencial disponible"
            }
        
        try:
            # Abrir el spreadsheet por ID
            spreadsheet = gc.open_by_key(sheet_id)
            logger.info(f"📋 Spreadsheet abierto: '{spreadsheet.title}'")
            
            # Obtener la worksheet "publicados_emprestito"
            try:
                worksheet = spreadsheet.worksheet("publicados_emprestito")
                logger.info(f"📄 Accediendo a worksheet: 'publicados_emprestito'")
            except gspread.exceptions.WorksheetNotFound:
                # Si no existe, usar la primera worksheet
                worksheet = spreadsheet.get_worksheet(0)
                logger.info(f"📄 Worksheet 'publicados_emprestito' no encontrada, usando: '{worksheet.title}'")
            
            # Obtener todos los valores como lista de listas
            all_values = worksheet.get_all_values()
            
            if not all_values:
                return {
                    "success": False,
                    "error": "El worksheet está vacío"
                }
            
            # IMPORTANTE: Los headers reales están en la fila 2 (índice 1), no en la fila 1
            # La fila 1 (índice 0) contiene columnas vacías o metadatos
            # Detectar automáticamente qué fila tiene las cabeceras reales
            header_row_index = 0
            
            # Buscar la fila que contiene las cabeceras reales (tiene más valores no vacíos)
            for idx, row in enumerate(all_values[:5]):  # Revisar primeras 5 filas
                non_empty_count = sum(1 for cell in row if cell and str(cell).strip())
                if non_empty_count > 5:  # Si tiene más de 5 columnas con contenido, es probable que sea la fila de headers
                    # Verificar si contiene palabras clave de headers esperados
                    row_text = ' '.join(str(cell).lower() for cell in row)
                    if 'item' in row_text or 'proceso' in row_text or 'banco' in row_text:
                        header_row_index = idx
                        logger.info(f"📍 Detectada fila de headers en índice {idx}")
                        break
            
            # Si no detectamos headers en fila 0, usar la fila detectada
            if header_row_index > 0:
                headers = all_values[header_row_index]
                data_start_index = header_row_index + 1
            else:
                headers = all_values[0]
                data_start_index = 1
            
            logger.info(f"📋 Headers detectados en fila {header_row_index}: {headers[:5]}...")
            
            # El contenido comienza desde la columna B (índice 1) según especificación
            # Filtrar headers y datos para empezar desde columna B
            headers_desde_b = headers[1:] if len(headers) > 1 else headers
            datos_desde_b = [fila[1:] if len(fila) > 1 else fila for fila in all_values[data_start_index:]]
            
            # Renombrar headers vacíos para evitar columnas duplicadas con nombre ''
            # Esto previene el error "The truth value of a Series is ambiguous"
            headers_unicos = []
            contador_vacios = 0
            for i, header in enumerate(headers_desde_b):
                if not header or header.strip() == '':
                    # Asignar nombre único a columnas vacías
                    headers_unicos.append(f'_columna_vacia_{contador_vacios}')
                    contador_vacios += 1
                else:
                    headers_unicos.append(header)
            
            # Crear DataFrame con pandas
            df = pd.DataFrame(datos_desde_b, columns=headers_unicos)
            
            # Eliminar columnas vacías (las que tienen nombres como '_columna_vacia_X')
            # Solo si están completamente vacías
            columnas_a_eliminar = []
            for col in df.columns:
                if col.startswith('_columna_vacia_'):
                    # Verificar si la columna está completamente vacía
                    if df[col].isna().all() or (df[col] == '').all():
                        columnas_a_eliminar.append(col)
            
            if columnas_a_eliminar:
                df = df.drop(columns=columnas_a_eliminar)
                logger.info(f"🗑️ Eliminadas {len(columnas_a_eliminar)} columnas vacías sin nombre")
            
            # Limpiar DataFrame eliminando filas completamente vacías
            df = df.dropna(how='all')
            
            logger.info(f"✅ Google Sheets leído exitosamente: {len(df)} filas, {len(df.columns)} columnas")
            logger.info(f"📋 Columnas encontradas (desde columna B): {list(df.columns)}")
            
            return {
                "success": True,
                "data": df,
                "message": f"Se leyeron {len(df)} filas del Google Sheet (worksheet: {worksheet.title})",
                "columns": list(df.columns),
                "rows_count": len(df),
                "worksheet_name": worksheet.title,
                "spreadsheet_title": spreadsheet.title,
                "service_account_email": service_account_email,
                "autenticacion": "service_account"
            }
            
        except gspread.exceptions.SpreadsheetNotFound:
            return {
                "success": False,
                "error": f"No se encontró el Google Sheets con ID: {sheet_id}. Verifica que el service account {service_account_email} tenga acceso al documento."
            }
        except gspread.exceptions.APIError as api_error:
            error_message = str(api_error)
            if "[400]" in error_message and "not supported for this document" in error_message:
                return {
                    "success": False,
                    "error": f"El documento de Google Sheets no es accesible. Esto puede deberse a: 1) Restricciones de Google Workspace, 2) El service account no tiene permisos, 3) El documento no es un Google Sheets válido. Service account: {service_account_email}"
                }
            else:
                return {
                    "success": False,
                    "error": f"Error de API de Google Sheets: {str(api_error)}. Verifica permisos del service account {service_account_email}."
                }
        
    except ImportError as e:
        logger.error(f"❌ Error importando gspread: {str(e)}")
        return {
            "success": False,
            "error": "gspread no está disponible. Instala con: pip install gspread"
        }
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        logger.error(f"❌ Error leyendo Google Sheets: {str(e)}")
        logger.error(f"❌ Traceback completo: {error_details}")
        return {
            "success": False,
            "error": f"Error leyendo Google Sheets: {str(e)} | Detalles: {type(e).__name__}"
        }

async def procesar_datos_proyecciones(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Procesa y mapea los datos del DataFrame según las especificaciones del usuario
    
    Mapeo de campos:
    - Item: item
    - Nro de Proceso: referencia_proceso  
    - NOMBRE ABREVIADO: nombre_organismo_reducido
    - Banco: nombre_banco
    - BP: BP (con prefijo "BP" agregado)
    - DESCRIPCION BP: descripcion_bp
    - Proyecto: nombre_generico_proyecto
    - Proyecto con su respectivo contrato: nombre_resumido_proceso
    - ID PAA: id_paa
    - LINK DEL PROCESO: urlProceso
    - valor_proyectado: valor_proyectado (mapeo directo)
    
    NOTA: La columna en Google Sheets ahora se llama "valor_proyectado" directamente
    """
    try:
        logger.info("🔄 Procesando datos de proyecciones...")
        
        # Mapeo de columnas original -> campo destino
        # IMPORTANTE: Orden de prioridad para valor_proyectado
        mapeo_campos = {
            "Item": "item",
            "Nro de Proceso": "referencia_proceso",
            "NOMBRE ABREVIADO": "nombre_organismo_reducido", 
            "Banco": "nombre_banco",
            "BP": "BP",
            "DESCRIPCION BP": "descripcion_bp",
            "Proyecto": "nombre_generico_proyecto",
            "Proyecto con su respectivo contrato": "nombre_resumido_proceso",
            "ID PAA": "id_paa",
            "LINK DEL PROCESO": "urlProceso"
        }
        
        # Variantes de columnas para valor_proyectado (orden de prioridad)
        # NOTA: En Google Sheets el campo se llama "VALOR TOTAL"
        columnas_valor_proyectado = [
            "VALOR TOTAL",           # Nombre real en Google Sheets (PRIORIDAD 1)
            "valor_proyectado",      # Nombre ideal
            "VALOR \n TOTAL",        # Con espacios y salto de línea
            "VALOR\n TOTAL",         # Legacy con salto de línea sin espacio inicial
            "VALOR \nTOTAL",         # Variante sin espacio después del salto
            "VALOR\nTOTAL",          # Sin espacios
            "VALOR  TOTAL",          # Con doble espacio
        ]
        
        # Verificar qué columnas están disponibles
        columnas_disponibles = list(df.columns)
        logger.info(f"📋 Columnas disponibles en el DataFrame: {columnas_disponibles}")
        
        # Crear lista de registros procesados
        registros_procesados = []
        filas_con_errores = []
        
        for index, fila in df.iterrows():
            try:
                # Crear registro mapeado
                registro = {}
                
                # Mapear cada campo según la especificación
                for col_original, campo_destino in mapeo_campos.items():
                    # Si el campo destino ya fue asignado con un valor válido, no sobrescribir
                    if campo_destino in registro:
                        valor_existente = str(registro[campo_destino]).strip()
                        if valor_existente and valor_existente != "":
                            # Para otros campos, no sobrescribir si ya tiene valor
                            continue
                    
                    # Buscar la columna en el DataFrame (puede haber variaciones)
                    valor = None
                    
                    # Búsqueda exacta primero
                    if col_original in columnas_disponibles:
                        valor = fila[col_original]
                    else:
                        # Búsqueda flexible para manejar variaciones y saltos de línea
                        col_original_clean = col_original.replace('\n', '').replace('\r', '').lower().strip()
                        
                        for col_df in columnas_disponibles:
                            col_df_clean = col_df.replace('\n', '').replace('\r', '').lower().strip()
                            
                            # Busqueda exacta de versión limpia
                            if col_original_clean == col_df_clean:
                                valor = fila[col_df]
                                break
                            # Búsqueda parcial
                            elif col_original_clean in col_df_clean or col_df_clean in col_original_clean:
                                valor = fila[col_df]
                                break
                    
                    # Procesar el valor - convertir a escalar si es necesario
                    if valor is None:
                        registro[campo_destino] = ""
                    elif pd.isna(valor):
                        registro[campo_destino] = ""
                    else:
                        # Convertir a escalar si es un Series (para manejar columnas duplicadas)
                        if isinstance(valor, pd.Series):
                            valor = valor.iloc[0] if len(valor) > 0 else None
                        
                        if valor is None or pd.isna(valor):
                            registro[campo_destino] = ""
                        else:
                            valor_str = str(valor).strip()
                            
                            # Procesamiento especial para BP - agregar prefijo
                            if campo_destino == "BP" and valor_str:
                                if not valor_str.upper().startswith("BP"):
                                    registro[campo_destino] = f"BP{valor_str}"
                                else:
                                    registro[campo_destino] = valor_str
                            else:
                                registro[campo_destino] = valor_str
                
                # Procesar valor_proyectado por separado (con orden de prioridad)
                valor_proyectado_encontrado = False
                columna_usada = None
                
                for col_valor in columnas_valor_proyectado:
                    if valor_proyectado_encontrado:
                        break
                    
                    # Búsqueda exacta primero
                    valor = None
                    if col_valor in columnas_disponibles:
                        valor = fila[col_valor]
                        columna_usada = col_valor
                    else:
                        # Búsqueda flexible con normalización agresiva
                        # Normalizar: quitar \n, \r, \t, espacios múltiples, y convertir a minúsculas
                        col_valor_clean = re.sub(r'\s+', ' ', col_valor.replace('\n', ' ').replace('\r', ' ').replace('\t', ' ')).lower().strip()
                        
                        for col_df in columnas_disponibles:
                            col_df_clean = re.sub(r'\s+', ' ', col_df.replace('\n', ' ').replace('\r', ' ').replace('\t', ' ')).lower().strip()
                            
                            # Busqueda exacta de versión normalizada
                            if col_valor_clean == col_df_clean:
                                valor = fila[col_df]
                                columna_usada = col_df
                                logger.debug(f"🔍 Fila {index + 1}: Encontrada columna normalizada '{col_df}' (buscando '{col_valor}')")
                                break
                            # Búsqueda parcial si contiene "valor" y "total"
                            elif 'valor' in col_df_clean and 'total' in col_df_clean:
                                valor = fila[col_df]
                                columna_usada = col_df
                                logger.debug(f"🔍 Fila {index + 1}: Encontrada columna por palabras clave '{col_df}' (buscando '{col_valor}')")
                                break
                    
                    # Si encontramos un valor válido, procesarlo
                    if valor is not None:
                        # Convertir a escalar si es un Series
                        if isinstance(valor, pd.Series):
                            valor = valor.iloc[0] if len(valor) > 0 else None
                        
                        if valor is not None and not pd.isna(valor):
                            valor_str = str(valor).strip()
                            if valor_str and valor_str != '':
                                try:
                                    # Limpiar formato de número (quitar $, espacios, comas, puntos como separadores de miles)
                                    valor_limpio = valor_str.replace('$', '').replace(',', '').replace(' ', '').strip()
                                    
                                    # Remover puntos que actúan como separadores de miles (formato colombiano)
                                    # Solo si hay más de un punto o si el punto no está en los últimos 3 caracteres
                                    if '.' in valor_limpio:
                                        puntos = valor_limpio.count('.')
                                        if puntos > 1 or (puntos == 1 and len(valor_limpio.split('.')[-1]) != 2):
                                            # Es separador de miles, no decimal
                                            valor_limpio = valor_limpio.replace('.', '')
                                    
                                    if valor_limpio and valor_limpio != '':
                                        registro["valor_proyectado"] = float(valor_limpio)
                                        valor_proyectado_encontrado = True
                                        col_display = columna_usada.replace('\n', '\\n').replace('\r', '\\r') if columna_usada else col_valor
                                        logger.info(f"✅ Fila {index + 1}: valor_proyectado = {registro['valor_proyectado']:,.0f} desde columna '{col_display}'")
                                except (ValueError, TypeError) as e:
                                    logger.warning(f"⚠️ No se pudo convertir valor '{valor_str}' a número en fila {index + 1}: {str(e)}")
                
                # Si no se encontró valor_proyectado, asignar 0
                if "valor_proyectado" not in registro:
                    registro["valor_proyectado"] = 0
                    logger.warning(f"⚠️ Fila {index + 1}: valor_proyectado no encontrado en ninguna variante de columna, asignado 0")
                
                # Agregar metadatos
                registro["fecha_carga"] = datetime.now().isoformat()
                registro["fuente"] = "google_sheets"
                registro["fila_origen"] = index + 1  # +1 porque pandas usa índice 0
                
                # Validar campos obligatorios mínimos (usar item en lugar de referencia_proceso)
                item_value = str(registro.get("item", "")).strip()
                if not item_value or item_value == "":
                    filas_con_errores.append({
                        "fila": index + 1,
                        "error": "item vacío o faltante",
                        "datos": registro
                    })
                    continue
                
                # Validar que al menos tenga un proyecto o descripción
                proyecto_generico = str(registro.get("nombre_generico_proyecto", "")).strip()
                proyecto_resumido = str(registro.get("nombre_resumido_proceso", "")).strip()
                if not proyecto_generico and not proyecto_resumido:
                    filas_con_errores.append({
                        "fila": index + 1,
                        "error": "sin proyecto o descripción válida",
                        "datos": registro
                    })
                    continue
                
                registros_procesados.append(registro)
                
            except Exception as e:
                logger.error(f"❌ Error procesando fila {index + 1}: {str(e)}")
                filas_con_errores.append({
                    "fila": index + 1,
                    "error": str(e),
                    "datos": {}
                })
        
        logger.info(f"✅ Procesamiento completado: {len(registros_procesados)} registros válidos, {len(filas_con_errores)} con errores")
        
        # Mapeo completo para documentación
        mapeo_completo = mapeo_campos.copy()
        mapeo_completo["valor_proyectado (prioridad 1)"] = "valor_proyectado"
        mapeo_completo["VALOR\\n TOTAL (prioridad 2)"] = "valor_proyectado"
        mapeo_completo["VALOR TOTAL (prioridad 3)"] = "valor_proyectado"
        
        return {
            "success": True,
            "data": registros_procesados,
            "message": f"Se procesaron {len(registros_procesados)} registros exitosamente",
            "registros_validos": len(registros_procesados),
            "filas_con_errores": len(filas_con_errores),
            "errores_detalle": filas_con_errores,
            "mapeo_aplicado": mapeo_completo
        }
        
    except Exception as e:
        logger.error(f"❌ Error procesando datos de proyecciones: {str(e)}")
        return {
            "success": False,
            "error": f"Error procesando datos: {str(e)}"
        }

async def guardar_proyecciones_emprestito(registros: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Guarda los registros de proyecciones en la colección proyecciones_emprestito
    """
    try:
        if not FIRESTORE_AVAILABLE:
            return {
                "success": False,
                "error": "Firebase no disponible"
            }
        
        db = get_firestore_client()
        if db is None:
            return {
                "success": False,
                "error": "No se pudo conectar a Firestore"
            }
        
        # Limpiar la colección existente (reemplazar datos completos)
        logger.info("🗑️ Limpiando colección proyecciones_emprestito existente...")
        collection_ref = db.collection('proyecciones_emprestito')
        
        # Eliminar documentos existentes
        docs = collection_ref.stream()
        batch = db.batch()
        docs_eliminados = 0
        
        for doc in docs:
            batch.delete(doc.reference)
            docs_eliminados += 1
            
            # Ejecutar batch cada 500 documentos para evitar límites
            if docs_eliminados % 500 == 0:
                batch.commit()
                batch = db.batch()
        
        # Ejecutar batch final si hay documentos pendientes
        if docs_eliminados % 500 != 0:
            batch.commit()
        
        logger.info(f"🗑️ Eliminados {docs_eliminados} documentos existentes")
        
        # Guardar nuevos registros
        logger.info(f"💾 Guardando {len(registros)} nuevos registros...")
        documentos_guardados = 0
        
        # Usar batch para operaciones eficientes
        batch = db.batch()
        
        for i, registro in enumerate(registros):
            # Agregar timestamp de guardado
            registro_con_timestamp = registro.copy()
            registro_con_timestamp["fecha_guardado"] = datetime.now()
            registro_con_timestamp["ultima_actualizacion"] = datetime.now()
            
            # Crear documento con ID automático
            doc_ref = collection_ref.document()
            batch.set(doc_ref, registro_con_timestamp)
            documentos_guardados += 1
            
            # Ejecutar batch cada 500 documentos
            if documentos_guardados % 500 == 0:
                batch.commit()
                batch = db.batch()
                logger.info(f"💾 Guardados {documentos_guardados}/{len(registros)} registros...")
        
        # Ejecutar batch final
        if documentos_guardados % 500 != 0:
            batch.commit()
        
        # Guardar metadatos de la carga
        metadatos_carga = {
            "fecha_ultima_carga": datetime.now(),
            "registros_cargados": documentos_guardados,
            "fuente": "google_sheets",
            "docs_eliminados_previos": docs_eliminados,
            "operacion": "reemplazo_completo"
        }
        
        # Guardar metadatos en documento especial - DESHABILITADO
        # db.collection('proyecciones_emprestito_meta').document('ultima_carga').set(metadatos_carga)
        
        logger.info(f"✅ Guardado completado: {documentos_guardados} registros en proyecciones_emprestito")
        
        return {
            "success": True,
            "message": f"Se guardaron {documentos_guardados} registros exitosamente",
            "registros_guardados": documentos_guardados,
            "docs_eliminados_previos": docs_eliminados,
            "coleccion": "proyecciones_emprestito",
            "operacion": "reemplazo_completo",
            "metadatos_guardados": True
        }
        
    except Exception as e:
        logger.error(f"❌ Error guardando proyecciones: {str(e)}")
        return {
            "success": False,
            "error": f"Error guardando proyecciones: {str(e)}"
        }

async def leer_proyecciones_emprestito() -> Dict[str, Any]:
    """
    Lee todos los registros de la colección proyecciones_emprestito
    """
    try:
        if not FIRESTORE_AVAILABLE:
            return {
                "success": False,
                "error": "Firebase no disponible",
                "data": [],
                "count": 0
            }
        
        db = get_firestore_client()
        if db is None:
            return {
                "success": False,
                "error": "No se pudo conectar a Firestore",
                "data": [],
                "count": 0
            }
        
        # Leer todos los documentos de la colección
        collection_ref = db.collection('proyecciones_emprestito')
        docs = collection_ref.stream()
        
        proyecciones_data = []
        for doc in docs:
            doc_data = doc.to_dict()
            doc_data['id'] = doc.id  # Agregar ID del documento
            # Limpiar datos de Firebase para serialización JSON
            doc_data_clean = serialize_datetime_objects(doc_data)
            proyecciones_data.append(doc_data_clean)
        
        # Leer metadatos de la última carga - DESHABILITADO
        metadatos = None
        # try:
        #     meta_doc = db.collection('proyecciones_emprestito_meta').document('ultima_carga').get()
        #     if meta_doc.exists:
        #         metadatos = serialize_datetime_objects(meta_doc.to_dict())
        # except Exception as e:
        #     logger.warning(f"⚠️ No se pudieron leer metadatos: {str(e)}")
        
        # Ordenar por fecha de carga (más recientes primero)
        proyecciones_data.sort(key=lambda x: x.get('fecha_carga', ''), reverse=True)

        return {
            "success": True,
            "data": proyecciones_data,
            "count": len(proyecciones_data),
            "collection": "proyecciones_emprestito",
            "metadatos_carga": metadatos,
            "timestamp": datetime.now().isoformat(),
            "message": f"Se obtuvieron {len(proyecciones_data)} proyecciones de empréstito exitosamente"
        }
        
    except Exception as e:
        logger.error(f"❌ Error leyendo proyecciones: {str(e)}")
        return {
            "success": False,
            "error": f"Error leyendo proyecciones: {str(e)}",
            "data": [],
            "count": 0
        }


# FUNCIONES HELPER PARA OPTIMIZACIÓN DE CONSULTAS

async def get_referencias_from_collection(db, collection_name: str, field_name: str) -> set:
    """
    Helper optimizado para obtener referencias de una colección en Firebase.
    Reutilizable para múltiples colecciones y campos.
    
    Args:
        db: Cliente de Firestore
        collection_name: Nombre de la colección
        field_name: Campo del que extraer las referencias
    
    Returns:
        Set de referencias únicas (strings)
    """
    try:
        collection_ref = db.collection(collection_name)
        docs = collection_ref.stream()
        referencias = set()
        
        for doc in docs:
            doc_data = doc.to_dict()
            ref = doc_data.get(field_name, '')
            
            if ref:
                # Manejar listas y strings
                if isinstance(ref, list):
                    for r in ref:
                        if r:
                            referencias.add(str(r).strip())
                else:
                    referencias.add(str(ref).strip())
        
        return referencias
        
    except Exception as e:
        logger.error(f"❌ Error obteniendo referencias de {collection_name}.{field_name}: {str(e)}")
        return set()


async def leer_proyecciones_no_guardadas(sheet_url: str) -> Dict[str, Any]:
    """
    Lee datos de Google Sheets y devuelve solo los registros que:
    1. Tienen un número de proceso válido (no vacío en campo "Nro de Proceso")
    2. Ese número de proceso NO existe en la colección procesos_emprestito
    
    Esta función NO guarda nada en Firebase, solo lee y compara.
    Optimizada con consultas paralelas y mapas en memoria.
    """
    try:
        if not FIRESTORE_AVAILABLE:
            return {"success": False, "error": "Firebase no disponible", "data": [], "count": 0}
        
        db = get_firestore_client()
        if db is None:
            return {"success": False, "error": "No se pudo conectar a Firestore", "data": [], "count": 0}
        
        logger.info("🚀 Iniciando lectura de proyecciones no guardadas desde Google Sheets...")
        
        # PASO 1: Leer datos de Google Sheets (sin guardar)
        resultado_lectura = await leer_google_sheets_proyecciones(sheet_url)
        if not resultado_lectura["success"]:
            return resultado_lectura
        
        df_temporal = resultado_lectura["data"]
        logger.info(f"📊 Datos leídos de Sheets: {len(df_temporal)} filas")
        
        # PASO 2: Procesar y mapear datos (sin guardar)
        resultado_procesamiento = await procesar_datos_proyecciones(df_temporal)
        if not resultado_procesamiento["success"]:
            return resultado_procesamiento
        
        registros_sheets = resultado_procesamiento["data"]
        logger.info(f"✅ Datos procesados de Sheets: {len(registros_sheets)} registros")
        
        # LOG: Verificar que los primeros registros tengan valor_proyectado
        if len(registros_sheets) > 0:
            muestra = registros_sheets[0]
            logger.info(f"📋 Muestra de registro procesado:")
            logger.info(f"   - referencia_proceso: {muestra.get('referencia_proceso', 'N/A')}")
            logger.info(f"   - valor_proyectado: {muestra.get('valor_proyectado', 'NO_ENCONTRADO')}")
            logger.info(f"   - nombre_banco: {muestra.get('nombre_banco', 'N/A')}")
            logger.info(f"   - Campos disponibles: {list(muestra.keys())}")
        
        # PASO 3: Obtener SOLO referencias de procesos_emprestito (única colección relevante)
        logger.info("🔄 Cargando referencias de procesos_emprestito...")
        referencias_procesos = await get_referencias_from_collection(db, 'procesos_emprestito', 'referencia_proceso')
        
        logger.info(f"✅ Referencias cargadas:")
        logger.info(f"   - Procesos en BD: {len(referencias_procesos)}")
        
        # PASO 4: Filtrar PRIMERO solo registros con Nro de Proceso válido
        registros_con_proceso_valido = []
        count_sin_proceso = 0
        
        logger.info("🔍 Filtrando registros con Nro de Proceso válido...")
        
        for registro in registros_sheets:
            referencia_proceso = registro.get('referencia_proceso', '')
            
            # Convertir a string y limpiar espacios
            if referencia_proceso is None:
                count_sin_proceso += 1
                continue
            
            referencia_str = str(referencia_proceso).strip()
            
            # Lista de valores que se consideran inválidos
            valores_invalidos = ['', '0', '0.0', 'null', 'none', 'n/a', 'na', 'nan', 'undefined']
            
            # Verificar que NO sea vacío o un valor inválido
            if not referencia_str or referencia_str.lower() in valores_invalidos:
                count_sin_proceso += 1
                logger.debug(f"❌ Rechazado: '{referencia_proceso}' (valor inválido)")
                continue
            
            # Verificar que no sea solo un número cero
            try:
                if float(referencia_str) == 0:
                    count_sin_proceso += 1
                    logger.debug(f"❌ Rechazado: '{referencia_proceso}' (es cero numérico)")
                    continue
            except (ValueError, TypeError):
                # No es un número, está bien
                pass
            
            # Tiene un número de proceso válido
            logger.debug(f"✅ Válido: '{referencia_str}'")
            registros_con_proceso_valido.append(registro)
        
        logger.info(f"📊 Filtro inicial:")
        logger.info(f"   - Total en Sheets: {len(registros_sheets)}")
        logger.info(f"   - Con Nro Proceso válido: {len(registros_con_proceso_valido)}")
        logger.info(f"   - Sin Nro Proceso o inválido: {count_sin_proceso}")
        
        # PASO 5: Comparar SOLO los registros con proceso válido contra procesos_emprestito
        registros_no_guardados = []
        count_ya_en_procesos = 0
        
        logger.info("🔄 Comparando registros válidos con procesos_emprestito...")
        
        for registro in registros_con_proceso_valido:
            referencia_proceso = str(registro.get('referencia_proceso', '')).strip()
            
            # Verificar si YA existe en procesos_emprestito (búsqueda O(1) en set)
            existe_en_procesos = referencia_proceso in referencias_procesos
            
            if existe_en_procesos:
                # Ya está guardado en procesos_emprestito - no incluir
                count_ya_en_procesos += 1
                logger.debug(f"✓ En BD: '{referencia_proceso}'")
            else:
                # NO está en procesos_emprestito - INCLUIR
                registro['_es_nuevo'] = True
                registro['_motivo'] = 'No existe en procesos_emprestito'
                
                # LOG: Verificar que valor_proyectado esté presente
                valor_proy = registro.get('valor_proyectado', 'NO_ENCONTRADO')
                logger.info(f"⚠️ NO en BD: '{referencia_proceso}' | valor_proyectado: {valor_proy}")
                
                registros_no_guardados.append(registro)
        
        logger.info(f"📊 Resultados de la comparación:")
        logger.info(f"   - Registros válidos analizados: {len(registros_con_proceso_valido)}")
        logger.info(f"   - NO en procesos_emprestito: {len(registros_no_guardados)}")
        logger.info(f"   - Ya en procesos_emprestito: {count_ya_en_procesos}")
        
        # Limpiar DataFrame temporal
        del df_temporal
        
        return {
            "success": True,
            "data": registros_no_guardados,
            "count": len(registros_no_guardados),
            "metadata": {
                "total_sheets": len(registros_sheets),
                "con_proceso_valido": len(registros_con_proceso_valido),
                "sin_proceso_o_invalido": count_sin_proceso,
                "no_en_procesos_emprestito": len(registros_no_guardados),
                "ya_en_procesos_emprestito": count_ya_en_procesos,
                "referencias_bd": {
                    "procesos_emprestito": len(referencias_procesos)
                }
            },
            "timestamp": datetime.now().isoformat(),
            "message": f"De {len(registros_sheets)} registros en Sheets, {len(registros_con_proceso_valido)} tienen Nro de Proceso válido. De estos, {len(registros_no_guardados)} NO están en procesos_emprestito."
        }
        
    except Exception as e:
        logger.error(f"❌ Error leyendo proyecciones no guardadas: {str(e)}")
        return {
            "success": False,
            "error": f"Error leyendo proyecciones no guardadas: {str(e)}",
            "data": [],
            "count": 0
        }


async def get_proyecciones_sin_proceso() -> Dict[str, Any]:
    """
    Compara los valores de 'referencia_proceso' en 'proyecciones_emprestito' con
    la colección 'procesos_emprestito' y devuelve las proyecciones cuyo
    'referencia_proceso' no aparece en procesos_emprestito.
    """
    try:
        if not FIRESTORE_AVAILABLE:
            return {"success": False, "error": "Firebase no disponible", "data": [], "count": 0}

        db = get_firestore_client()
        if db is None:
            return {"success": False, "error": "No se pudo conectar a Firestore", "data": [], "count": 0}

        # Obtener todos los procesos existentes y construir un set de referencias
        procesos_ref = db.collection('procesos_emprestito')
        procesos_docs = list(procesos_ref.stream())
        referencias_procesos = set()
        for doc in procesos_docs:
            d = doc.to_dict()
            ref = d.get('referencia_proceso')
            if ref:
                referencias_procesos.add(str(ref).strip())

        # Obtener todas las proyecciones
        proyecciones_ref = db.collection('proyecciones_emprestito')
        proyecciones_docs = list(proyecciones_ref.stream())

        # PASO 1: Filtrar PRIMERO solo registros con referencia_proceso VÁLIDA (no nulo, no vacío, no cero)
        proyecciones_con_referencia_valida = []
        valores_invalidos = ['', '0', '0.0', 'null', 'none', 'n/a', 'na', 'nan', 'undefined']
        
        for doc in proyecciones_docs:
            pdata = doc.to_dict()
            refp = pdata.get('referencia_proceso')
            
            # Verificar que no sea None
            if refp is None:
                continue
            
            # Convertir a string y limpiar
            refp_str = str(refp).strip()
            
            # Verificar que NO sea vacío o valor inválido
            if not refp_str or refp_str.lower() in valores_invalidos:
                continue
            
            # Verificar que no sea cero numérico
            try:
                if float(refp_str) == 0:
                    continue
            except (ValueError, TypeError):
                pass
            
            # Tiene referencia válida, guardar con su string limpio
            pdata['id'] = doc.id
            pdata['_referencia_limpia'] = refp_str
            proyecciones_con_referencia_valida.append(pdata)
        
        # PASO 2: De las que tienen referencia válida, filtrar las que NO están en procesos_emprestito
        proyecciones_sin_proceso = []
        for pdata in proyecciones_con_referencia_valida:
            refp_str = pdata['_referencia_limpia']
            
            # Si NO está en procesos_emprestito, incluir
            if refp_str not in referencias_procesos:
                # Limpiar campo temporal antes de devolver
                del pdata['_referencia_limpia']
                pdata_clean = serialize_datetime_objects(pdata)
                proyecciones_sin_proceso.append(pdata_clean)

        return {
            "success": True,
            "data": proyecciones_sin_proceso,
            "count": len(proyecciones_sin_proceso),
            "collection_source": "proyecciones_emprestito",
            "collection_compare": "procesos_emprestito",
            "timestamp": datetime.now().isoformat(),
            "message": f"Se encontraron {len(proyecciones_sin_proceso)} proyecciones sin proceso asociado"
        }

    except Exception as e:
        logger.error(f"❌ Error comparando colecciones: {str(e)}")
        return {"success": False, "error": f"Error comparando colecciones: {str(e)}", "data": [], "count": 0}

async def crear_tabla_proyecciones_desde_sheets(sheet_url: str) -> Dict[str, Any]:
    """
    Función principal que orquesta todo el proceso:
    1. Lee datos de Google Sheets
    2. Procesa y mapea los datos
    3. Guarda en Firebase
    4. Limpia recursos temporales
    """
    try:
        logger.info("🚀 Iniciando creación de tabla de proyecciones desde Google Sheets...")
        
        # Paso 1: Leer Google Sheets
        resultado_lectura = await leer_google_sheets_proyecciones(sheet_url)
        if not resultado_lectura["success"]:
            return resultado_lectura
        
        df_temporal = resultado_lectura["data"]
        logger.info(f"📊 DataFrame temporal creado: {len(df_temporal)} filas")
        
        # Paso 2: Procesar y mapear datos
        resultado_procesamiento = await procesar_datos_proyecciones(df_temporal)
        if not resultado_procesamiento["success"]:
            return resultado_procesamiento
        
        registros_procesados = resultado_procesamiento["data"]
        logger.info(f"✅ Datos procesados: {len(registros_procesados)} registros válidos")
        
        # Paso 3: Guardar en Firebase
        resultado_guardado = await guardar_proyecciones_emprestito(registros_procesados)
        if not resultado_guardado["success"]:
            return resultado_guardado
        
        # Paso 4: Limpiar DataFrame temporal (Python se encarga automáticamente)
        del df_temporal
        logger.info("🗑️ DataFrame temporal eliminado")
        
        # Preparar respuesta final
        return {
            "success": True,
            "message": "Tabla de proyecciones creada exitosamente desde Google Sheets",
            "resumen_operacion": {
                "sheet_url": sheet_url,
                "filas_leidas": resultado_lectura["rows_count"],
                "registros_procesados": len(registros_procesados),
                "registros_guardados": resultado_guardado["registros_guardados"],
                "docs_eliminados_previos": resultado_guardado["docs_eliminados_previos"]
            },
            "detalle_procesamiento": {
                "filas_con_errores": resultado_procesamiento["filas_con_errores"],
                "errores_detalle": resultado_procesamiento["errores_detalle"][:5],  # Máximo 5 errores
                "mapeo_aplicado": resultado_procesamiento["mapeo_aplicado"]
            },
            "coleccion_destino": "proyecciones_emprestito",
            "operacion": "reemplazo_completo",
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"❌ Error en creación de tabla de proyecciones: {str(e)}")
        return {
            "success": False,
            "error": f"Error en creación de tabla de proyecciones: {str(e)}"
        }


async def actualizar_proyeccion_emprestito(referencia_proceso: str, datos_actualizacion: Dict[str, Any]) -> Dict[str, Any]:
    """
    Actualiza un registro específico en la colección proyecciones_emprestito según su referencia_proceso
    
    Args:
        referencia_proceso (str): Referencia del proceso a actualizar
        datos_actualizacion (dict): Datos a actualizar
    
    Returns:
        Dict con el resultado de la operación
    """
    try:
        if not FIRESTORE_AVAILABLE:
            return {
                "success": False,
                "error": "Firebase no disponible"
            }
        
        db = get_firestore_client()
        if db is None:
            return {
                "success": False,
                "error": "No se pudo conectar a Firestore"
            }
        
        # Buscar el documento por referencia_proceso
        collection_ref = db.collection('proyecciones_emprestito')
        query = collection_ref.where('referencia_proceso', '==', referencia_proceso)
        docs = list(query.stream())
        
        if not docs:
            return {
                "success": False,
                "error": f"No se encontró ningún registro con referencia_proceso: {referencia_proceso}",
                "count": 0
            }
        
        if len(docs) > 1:
            logger.warning(f"⚠️ Se encontraron {len(docs)} registros con la misma referencia_proceso: {referencia_proceso}")
        
        # Tomar el primer documento encontrado
        doc = docs[0]
        doc_ref = doc.reference
        datos_actuales = doc.to_dict()
        
        # Preparar datos de actualización
        datos_finales = datos_actualizacion.copy()
        datos_finales["ultima_actualizacion"] = datetime.now()
        datos_finales["referencia_proceso"] = referencia_proceso  # Mantener la referencia
        
        # Actualizar el documento
        doc_ref.update(datos_finales)
        
        logger.info(f"✅ Proyección actualizada para referencia_proceso: {referencia_proceso}")
        
        # Obtener datos actualizados para respuesta
        doc_actualizado = doc_ref.get()
        datos_actualizados = serialize_datetime_objects(doc_actualizado.to_dict())
        datos_actualizados['id'] = doc_actualizado.id
        
        return {
            "success": True,
            "message": f"Proyección actualizada exitosamente para referencia_proceso: {referencia_proceso}",
            "referencia_proceso": referencia_proceso,
            "doc_id": doc_actualizado.id,
            "datos_previos": serialize_datetime_objects(datos_actuales),
            "datos_actualizados": datos_actualizados,
            "campos_modificados": list(datos_actualizacion.keys()),
            "timestamp": datetime.now().isoformat(),
            "coleccion": "proyecciones_emprestito"
        }
        
    except Exception as e:
        logger.error(f"❌ Error actualizando proyección: {str(e)}")
        return {
            "success": False,
            "error": f"Error actualizando proyección: {str(e)}"
        }


async def actualizar_orden_compra_por_numero(numero_orden: str, campos_actualizar: Dict[str, Any]) -> Dict[str, Any]:
    """
    Actualizar una orden de compra existente en ordenes_compra_emprestito por numero_orden
    Permite actualizar SOLO valor_orden y valor_proyectado (opcional si existe)
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

        # Buscar orden de compra por numero_orden
        ordenes_ref = db_client.collection('ordenes_compra_emprestito')
        query_resultado = ordenes_ref.where('numero_orden', '==', numero_orden).get()

        if len(query_resultado) == 0:
            return {
                "success": False,
                "error": f"No se encontró ninguna orden de compra con numero_orden: {numero_orden}",
                "numero_orden": numero_orden
            }

        # Obtener el documento
        doc = query_resultado[0]
        doc_data = doc.to_dict()

        # SOLO permitir actualizar campos de valores
        campos_permitidos = ["valor_orden", "valor_proyectado"]
        
        # Preparar datos para actualizar
        datos_actualizacion = {}
        campos_actualizados = []
        valores_anteriores = {}
        valores_nuevos = {}
        
        for campo, valor in campos_actualizar.items():
            if campo not in campos_permitidos:
                continue  # Ignorar campos no permitidos
                
            if valor is not None:
                # Guardar valor anterior para el historial
                valores_anteriores[campo] = doc_data.get(campo)
                
                # Los campos de valores son numéricos
                datos_actualizacion[campo] = float(valor)
                valores_nuevos[campo] = datos_actualizacion[campo]
                campos_actualizados.append(campo)

        # Si no hay campos para actualizar
        if not datos_actualizacion:
            return {
                "success": False,
                "error": "No se proporcionaron campos para actualizar",
                "campos_disponibles": ["valor_orden", "valor_proyectado"]
            }

        # Agregar timestamp de actualización
        datos_actualizacion["fecha_actualizacion"] = datetime.now()

        # Actualizar documento
        doc.reference.update(datos_actualizacion)

        # Obtener documento actualizado
        doc_actualizado = doc.reference.get()
        datos_completos = doc_actualizado.to_dict()

        logger.info(f"Orden de compra actualizada exitosamente: {numero_orden}, campos: {campos_actualizados}")

        return {
            "success": True,
            "message": "Orden de compra actualizada exitosamente",
            "numero_orden": numero_orden,
            "coleccion": "ordenes_compra_emprestito",
            "documento_id": doc.id,
            "campos_modificados": campos_actualizados,
            "valores_anteriores": valores_anteriores,
            "valores_nuevos": valores_nuevos,
            "orden_actualizada": serialize_datetime_objects(datos_completos),
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Error actualizando orden de compra: {e}")
        return {
            "success": False,
            "error": str(e)
        }


async def eliminar_orden_compra_por_numero(numero_orden: str) -> Dict[str, Any]:
    """
    Eliminar una orden de compra existente en la colección ordenes_compra_emprestito
    usando numero_orden como identificador de búsqueda.
    """
    if not FIRESTORE_AVAILABLE:
        return {
            "success": False,
            "error": "Firebase no disponible"
        }

    try:
        numero_orden_limpio = (numero_orden or "").strip()
        if not numero_orden_limpio:
            return {
                "success": False,
                "error": "El parámetro 'numero_orden' es obligatorio"
            }

        db_client = get_firestore_client()
        if not db_client:
            return {
                "success": False,
                "error": "Error obteniendo cliente Firestore"
            }

        ordenes_ref = db_client.collection('ordenes_compra_emprestito')
        query_resultado = ordenes_ref.where('numero_orden', '==', numero_orden_limpio).get()

        if len(query_resultado) == 0:
            return {
                "success": False,
                "error": f"No se encontró ninguna orden de compra con numero_orden: {numero_orden_limpio}",
                "not_found": True,
                "numero_orden": numero_orden_limpio
            }

        doc = query_resultado[0]
        datos_previos = serialize_datetime_objects(doc.to_dict())
        doc.reference.delete()

        logger.info(f"Orden de compra eliminada exitosamente por numero_orden: {numero_orden_limpio}")

        return {
            "success": True,
            "message": f"Orden de compra {numero_orden_limpio} eliminada exitosamente",
            "numero_orden": numero_orden_limpio,
            "doc_id": doc.id,
            "deleted_data": datos_previos,
            "coleccion": "ordenes_compra_emprestito"
        }

    except Exception as e:
        logger.error(f"Error eliminando orden de compra por numero_orden: {e}")
        return {
            "success": False,
            "error": str(e)
        }


async def eliminar_convenio_transferencia_por_referencia(referencia_contrato: str) -> Dict[str, Any]:
    """
    Eliminar un convenio de transferencia existente en la colección
    convenios_transferencias_emprestito usando referencia_contrato como identificador.
    """
    if not FIRESTORE_AVAILABLE:
        return {
            "success": False,
            "error": "Firebase no disponible"
        }

    try:
        referencia_limpia = (referencia_contrato or "").strip()
        if not referencia_limpia:
            return {
                "success": False,
                "error": "El parámetro 'referencia_contrato' es obligatorio"
            }

        db_client = get_firestore_client()
        if not db_client:
            return {
                "success": False,
                "error": "Error obteniendo cliente Firestore"
            }

        convenios_ref = db_client.collection('convenios_transferencias_emprestito')
        query_resultado = convenios_ref.where('referencia_contrato', '==', referencia_limpia).get()

        if len(query_resultado) == 0:
            return {
                "success": False,
                "error": f"No se encontró ningún convenio con referencia_contrato: {referencia_limpia}",
                "not_found": True,
                "referencia_contrato": referencia_limpia
            }

        doc = query_resultado[0]
        datos_previos = serialize_datetime_objects(doc.to_dict())
        doc.reference.delete()

        logger.info(f"Convenio eliminado exitosamente por referencia_contrato: {referencia_limpia}")

        return {
            "success": True,
            "message": f"Convenio {referencia_limpia} eliminado exitosamente",
            "referencia_contrato": referencia_limpia,
            "doc_id": doc.id,
            "deleted_data": datos_previos,
            "coleccion": "convenios_transferencias_emprestito"
        }

    except Exception as e:
        logger.error(f"Error eliminando convenio por referencia_contrato: {e}")
        return {
            "success": False,
            "error": str(e)
        }

async def actualizar_convenio_por_referencia(referencia_contrato: str, campos_actualizar: Dict[str, Any]) -> Dict[str, Any]:
    """
    Actualizar un convenio de transferencia existente en convenios_transferencias_emprestito por referencia_contrato
    Permite actualizar SOLO valor_contrato
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

        # Buscar convenio por referencia_contrato
        convenios_ref = db_client.collection('convenios_transferencias_emprestito')
        query_resultado = convenios_ref.where('referencia_contrato', '==', referencia_contrato).get()

        if len(query_resultado) == 0:
            return {
                "success": False,
                "error": f"No se encontró ningún convenio de transferencia con referencia_contrato: {referencia_contrato}",
                "referencia_contrato": referencia_contrato
            }

        # Obtener el documento
        doc = query_resultado[0]
        doc_data = doc.to_dict()

        # SOLO permitir actualizar valor_contrato
        campos_permitidos = ["valor_contrato"]
        
        # Preparar datos para actualizar
        datos_actualizacion = {}
        campos_actualizados = []
        valores_anteriores = {}
        valores_nuevos = {}
        
        for campo, valor in campos_actualizar.items():
            if campo not in campos_permitidos:
                continue  # Ignorar campos no permitidos
                
            if valor is not None:
                # Guardar valor anterior para el historial
                valores_anteriores[campo] = doc_data.get(campo)
                
                # El campo valor_contrato es numérico
                datos_actualizacion[campo] = float(valor)
                valores_nuevos[campo] = datos_actualizacion[campo]
                campos_actualizados.append(campo)

        # Si no hay campos para actualizar
        if not datos_actualizacion:
            return {
                "success": False,
                "error": "No se proporcionaron campos para actualizar",
                "campos_disponibles": ["valor_contrato"]
            }

        # Agregar timestamp de actualización
        datos_actualizacion["fecha_actualizacion"] = datetime.now()

        # Actualizar documento
        doc.reference.update(datos_actualizacion)

        # Obtener documento actualizado
        doc_actualizado = doc.reference.get()
        datos_completos = doc_actualizado.to_dict()

        logger.info(f"Convenio de transferencia actualizado exitosamente: {referencia_contrato}, campos: {campos_actualizados}")

        return {
            "success": True,
            "message": "Convenio de transferencia actualizado exitosamente",
            "referencia_contrato": referencia_contrato,
            "coleccion": "convenios_transferencias_emprestito",
            "documento_id": doc.id,
            "campos_modificados": campos_actualizados,
            "valores_anteriores": valores_anteriores,
            "valores_nuevos": valores_nuevos,
            "convenio_actualizado": serialize_datetime_objects(datos_completos),
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Error actualizando convenio de transferencia: {e}")
        return {
            "success": False,
            "error": str(e)
        }

async def actualizar_contrato_secop_por_referencia(referencia_contrato: str, campos_actualizar: Dict[str, Any]) -> Dict[str, Any]:
    """
    Actualizar un contrato SECOP existente en contratos_emprestito por referencia_contrato
    Permite actualizar SOLO valor_contrato
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

        # Buscar contrato por referencia_contrato
        contratos_ref = db_client.collection('contratos_emprestito')
        query_resultado = contratos_ref.where('referencia_contrato', '==', referencia_contrato).get()

        if len(query_resultado) == 0:
            return {
                "success": False,
                "error": f"No se encontró ningún contrato SECOP con referencia_contrato: {referencia_contrato}",
                "referencia_contrato": referencia_contrato
            }

        # Obtener el documento
        doc = query_resultado[0]
        doc_data = doc.to_dict()

        # SOLO permitir actualizar valor_contrato
        campos_permitidos = ["valor_contrato"]
        
        # Preparar datos para actualizar
        datos_actualizacion = {}
        campos_actualizados = []
        valores_anteriores = {}
        valores_nuevos = {}
        
        for campo, valor in campos_actualizar.items():
            if campo not in campos_permitidos:
                continue  # Ignorar campos no permitidos
                
            if valor is not None:
                # Guardar valor anterior para el historial
                valores_anteriores[campo] = doc_data.get(campo)
                
                # El campo valor_contrato es numérico
                datos_actualizacion[campo] = float(valor)
                valores_nuevos[campo] = datos_actualizacion[campo]
                campos_actualizados.append(campo)

        # Si no hay campos para actualizar
        if not datos_actualizacion:
            return {
                "success": False,
                "error": "No se proporcionaron campos para actualizar",
                "campos_disponibles": ["valor_contrato"]
            }

        # Agregar timestamp de actualización
        datos_actualizacion["fecha_actualizacion"] = datetime.now()

        # Actualizar documento
        doc.reference.update(datos_actualizacion)

        # Obtener documento actualizado
        doc_actualizado = doc.reference.get()
        datos_completos = doc_actualizado.to_dict()

        logger.info(f"Contrato SECOP actualizado exitosamente: {referencia_contrato}, campos: {campos_actualizados}")

        return {
            "success": True,
            "message": "Contrato SECOP actualizado exitosamente",
            "referencia_contrato": referencia_contrato,
            "coleccion": "contratos_emprestito",
            "documento_id": doc.id,
            "campos_modificados": campos_actualizados,
            "valores_anteriores": valores_anteriores,
            "valores_nuevos": valores_nuevos,
            "contrato_actualizado": serialize_datetime_objects(datos_completos),
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Error actualizando contrato SECOP: {e}")
        return {
            "success": False,
            "error": str(e)
        }


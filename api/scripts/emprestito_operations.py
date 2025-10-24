"""
Scripts para manejo de Procesos de Empréstito - Versión Limpia
Solo funcionalidades esenciales habilitadas
"""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
import pandas as pd
import re
from database.firebase_config import get_firestore_client

# Configurar logging
logger = logging.getLogger(__name__)

# Variables de disponibilidad
FIRESTORE_AVAILABLE = True
try:
    from database.firebase_config import get_firestore_client
    get_firestore_client()
except Exception as e:
    FIRESTORE_AVAILABLE = False
    logger.warning(f"Firebase no disponible: {e}")

async def get_procesos_emprestito_all() -> Dict[str, Any]:
    """Obtener todos los registros de la colección procesos_emprestito"""
    try:
        if not FIRESTORE_AVAILABLE:
            return {"success": False, "error": "Firebase no disponible", "data": [], "count": 0}
        
        db = get_firestore_client()
        if db is None:
            return {"success": False, "error": "No se pudo conectar a Firestore", "data": [], "count": 0}
        
        collection_ref = db.collection('procesos_emprestito')
        docs = collection_ref.stream()
        procesos_data = []
        
        for doc in docs:
            doc_data = doc.to_dict()
            doc_data['id'] = doc.id  # Agregar ID del documento
            # Limpiar datos de Firebase para serialización JSON
            doc_data_clean = serialize_datetime_objects(doc_data)
            procesos_data.append(doc_data_clean)
        
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
            "error": f"Error obteniendo todos los procesos de empréstito: {str(e)}",
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

async def obtener_datos_secop(referencia_proceso: str) -> Dict[str, Any]:
    """
    Obtener datos de un proceso desde la API del SECOP
    Optimizada para obtener solo los campos necesarios
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

        # Mapear campos según especificaciones
        orden_datos = {
            "referencia_proceso": orden_raw.get("identificador_de_la_orden", referencia_proceso),
            "fecha_publicacion": orden_raw.get("fecha", ""),
            "fecha_vence": orden_raw.get("fecha_vence", ""),
            "estado": orden_raw.get("estado", ""),
            "agregacion": orden_raw.get("agregacion", ""),
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

        # Buscar contratos que contengan el proceso_contractual y el NIT específico
        where_clause = f"proceso_de_compra LIKE '%{proceso_contractual}%' AND nit_entidad = '890399011'"

        with Socrata("www.datos.gov.co", None) as client:
            contratos_secop = client.get("jbjy-vk9h", limit=100, where=where_clause)

        resultado["contratos_encontrados"] = len(contratos_secop)
        logger.info(f"📊 Encontrados {len(contratos_secop)} contratos en SECOP para {proceso_contractual}")

        if not contratos_secop:
            resultado["exito"] = True  # No es error, simplemente no hay contratos
            resultado["sin_contratos"] = True  # Flag para distinguir de errores técnicos
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

async def eliminar_proceso_emprestito(*args, **kwargs):
    """Función stub - No implementada temporalmente"""
    return {"success": False, "error": "Función no implementada temporalmente"}

async def actualizar_proceso_emprestito(*args, **kwargs):
    """Función stub - No implementada temporalmente"""
    return {"success": False, "error": "Función no implementada temporalmente"}

async def obtener_codigos_contratos(*args, **kwargs):
    """Función stub - No implementada temporalmente"""
    return {"success": False, "error": "Función no implementada temporalmente"}

async def buscar_y_poblar_contratos_secop(*args, **kwargs):
    """Función stub - No implementada temporalmente"""
    return {"success": False, "error": "Función no implementada temporalmente"}

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
        procesos_con_errores_tecnicos = []
        procesos_sin_contratos = []

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
                        logger.info(f"ℹ️  SIN CONTRATOS - Proceso {i}/{total_procesos}: {proceso_contractual}")
                    else:
                        logger.info(f"✅ ÉXITO - Proceso {i}/{total_procesos}: {resultado_individual['contratos_encontrados']} contratos encontrados, {resultado_individual['documentos_nuevos']} nuevos, {resultado_individual['documentos_actualizados']} actualizados")
                else:
                    # Error técnico real
                    procesos_con_errores_tecnicos.append({
                        "id": proceso_doc.id,
                        "referencia_proceso": referencia_proceso,
                        "error": resultado_individual["error"]
                    })
                    logger.error(f"❌ ERROR TÉCNICO - Proceso {i}/{total_procesos}: {resultado_individual['error']}")

                # Log de progreso
                tiempo_transcurrido = (datetime.now() - inicio_tiempo).total_seconds()
                logger.info(f"⏱️  Tiempo transcurrido: {tiempo_transcurrido:.1f}s | Exitosos: {procesados_exitosos}/{i}")

            except Exception as e:
                logger.error(f"💥 EXCEPCIÓN en proceso {i}/{total_procesos}: {e}")
                procesos_con_errores_tecnicos.append({
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
        logger.info(f"   - Procesos sin contratos en SECOP: {len(procesos_sin_contratos)}")
        logger.info(f"   - Errores técnicos: {len(procesos_con_errores_tecnicos)}")
        logger.info(f"   - Contratos encontrados: {total_contratos_encontrados}")
        logger.info(f"   - Documentos nuevos: {total_documentos_nuevos}")
        logger.info(f"   - Documentos actualizados: {total_documentos_actualizados}")

        # 4. Preparar respuesta final
        total_procesados = total_documentos_nuevos + total_documentos_actualizados + total_duplicados_ignorados

        return {
            "success": True,
            "message": f"✅ PROCESAMIENTO COMPLETO: {procesados_exitosos}/{total_procesos} procesos procesados. Contratos: {total_procesados} total ({total_documentos_nuevos} nuevos, {total_documentos_actualizados} actualizados)",
            "resumen_procesamiento": {
                "total_procesos_en_bd": total_procesos,
                "procesos_procesados_exitosamente": procesados_exitosos,
                "procesos_sin_contratos_en_secop": len(procesos_sin_contratos),
                "procesos_con_errores_tecnicos": len(procesos_con_errores_tecnicos),
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

async def obtener_datos_secop_completos(referencia_proceso: str) -> Dict[str, Any]:
    """
    Obtener datos completos de un proceso desde la API del SECOP
    Incluye todos los campos adicionales solicitados para complementar procesos_emprestito
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
        logger.info(f"Obteniendo datos completos SECOP para {referencia_proceso}")

        # Mapear campos completos según especificaciones
        # Mantener nombres de variables en Firebase sin cambiar, pero mapear desde SECOP
        proceso_datos_completos = {
            # Campos básicos existentes
            "adjudicado": proceso_raw.get("adjudicado", ""),
            "fase": proceso_raw.get("fase", ""),
            "estado_proceso": proceso_raw.get("estado_del_procedimiento", ""),
            
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
        resultado_secop = await obtener_datos_secop_completos(referencia_proceso)
        
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
        
        # Extraer el ID del spreadsheet de la URL
        sheet_id_match = re.search(r'/spreadsheets/d/([a-zA-Z0-9-_]+)', sheet_url)
        if not sheet_id_match:
            return {
                "success": False,
                "error": "No se pudo extraer el ID del Google Sheet de la URL proporcionada"
            }
        
        sheet_id = sheet_id_match.group(1)
        logger.info(f"📊 Accediendo a Google Sheets ID: {sheet_id}")
        
        # Obtener credenciales de Firebase para Google Sheets
        import firebase_admin
        from firebase_admin import credentials
        import os
        import json
        import base64
        
        try:
            # Opción 1: Intentar usar el service account específico del archivo de credenciales
            service_account_file = "credentials/unidad-cumplimiento-drive.json"
            service_account_email = "unidad-cumplimiento-drive@unidad-cumplimiento.iam.gserviceaccount.com"
            
            try:
                # Verificar si el archivo de credenciales existe
                import os
                if os.path.exists(service_account_file):
                    from google.oauth2.service_account import Credentials
                    
                    # Scopes necesarios para Google Sheets
                    scopes = [
                        'https://www.googleapis.com/auth/spreadsheets.readonly',
                        'https://www.googleapis.com/auth/drive.readonly'
                    ]
                    
                    sheets_credentials = Credentials.from_service_account_file(
                        service_account_file, 
                        scopes=scopes
                    )
                    logger.info(f"🔑 Usando service account desde archivo: {service_account_email}")
                    
                    # Crear cliente gspread
                    gc = gspread.authorize(sheets_credentials)
                    logger.info("✅ Cliente gspread autorizado exitosamente")
                else:
                    # Fallback a ADC
                    raise FileNotFoundError("Archivo de service account no encontrado")
                
            except Exception as service_account_error:
                logger.warning(f"⚠️ Service account desde archivo no disponible: {str(service_account_error)}")
                
                # Opción 2: Intentar usar las credenciales por defecto de Google Cloud
                from google.auth import default
                
                # Obtener credenciales por defecto con scopes específicos
                scopes = [
                    'https://www.googleapis.com/auth/spreadsheets.readonly',
                    'https://www.googleapis.com/auth/drive.readonly'
                ]
                
                sheets_credentials, project_id = default(scopes=scopes)
                logger.info(f"🔑 Usando Application Default Credentials para Google Sheets")
                logger.info(f"🆔 Proyecto detectado: {project_id}")
                
                # Crear cliente gspread
                gc = gspread.authorize(sheets_credentials)
                logger.info("✅ Cliente gspread autorizado exitosamente")
                
            except Exception as default_error:
                logger.warning(f"⚠️ ADC no disponible: {str(default_error)}")
                
                # Opción 2: Usar credenciales de Firebase desde variable de entorno
                firebase_key = os.getenv("FIREBASE_SERVICE_ACCOUNT_KEY")
                if not firebase_key:
                    raise Exception("FIREBASE_SERVICE_ACCOUNT_KEY no encontrada en variables de entorno")
                
                # Decodificar las credenciales
                service_account_info = json.loads(base64.b64decode(firebase_key).decode('utf-8'))
                service_account_email = service_account_info.get('client_email', service_account_email)
                
                logger.info(f"🔑 Usando service account desde env: {service_account_email}")
                
                # Crear credenciales específicas para Google Sheets API
                scopes = [
                    'https://www.googleapis.com/auth/spreadsheets.readonly',
                    'https://www.googleapis.com/auth/drive.readonly'
                ]
                
                # Crear credenciales con los scopes necesarios
                sheets_credentials = Credentials.from_service_account_info(
                    service_account_info, 
                    scopes=scopes
                )
                
                # Crear cliente gspread
                gc = gspread.authorize(sheets_credentials)
            
        except Exception as cred_error:
            logger.error(f"❌ Error obteniendo credenciales: {str(cred_error)}")
            return {
                "success": False,
                "error": f"Error obteniendo credenciales para Google Sheets: {str(cred_error)}"
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
            
            # Los headers están en la fila 1 (índice 0)
            headers = all_values[0]
            
            # El contenido comienza desde la columna B (índice 1) según especificación
            # Filtrar headers y datos para empezar desde columna B
            headers_desde_b = headers[1:] if len(headers) > 1 else headers
            datos_desde_b = [fila[1:] if len(fila) > 1 else fila for fila in all_values[1:]]
            
            # Crear DataFrame con pandas
            df = pd.DataFrame(datos_desde_b, columns=headers_desde_b)
            
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
    - Proyecto: nombre_generico_proyecto
    - Proyecto con su respectivo contrato: nombre_resumido_proceso
    - ID PAA: id_paa
    - LINK DEL PROCESO: urlProceso
    - VALOR TOTAL: valor_proyectado
    """
    try:
        logger.info("🔄 Procesando datos de proyecciones...")
        
        # Mapeo de columnas original -> campo destino
        mapeo_campos = {
            "Item": "item",
            "Nro de Proceso": "referencia_proceso",
            "NOMBRE ABREVIADO": "nombre_organismo_reducido", 
            "Banco": "nombre_banco",
            "BP": "BP",
            "DESCRIPCION BP": "descripcion_bp",  # Campo adicional que aparece en la especificación
            "Proyecto": "nombre_generico_proyecto",
            "Proyecto con su respectivo contrato": "nombre_resumido_proceso",
            "ID PAA": "id_paa",
            "LINK DEL PROCESO": "urlProceso",
            "VALOR\n TOTAL": "valor_proyectado",  # Puede tener salto de línea
            "VALOR TOTAL": "valor_proyectado"  # Versión sin salto de línea
        }
        
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
                    # Buscar la columna en el DataFrame (puede haber variaciones)
                    valor = None
                    
                    for col_df in columnas_disponibles:
                        if col_original.lower().strip() in col_df.lower().strip():
                            valor = fila[col_df]
                            break
                    
                    # Si no se encontró, intentar búsqueda exacta
                    if valor is None and col_original in columnas_disponibles:
                        valor = fila[col_original]
                    
                    # Procesar el valor
                    if pd.isna(valor) or valor is None:
                        registro[campo_destino] = "" if campo_destino != "valor_proyectado" else 0
                    else:
                        valor_str = str(valor).strip()
                        
                        # Procesamiento especial para BP - agregar prefijo
                        if campo_destino == "BP" and valor_str:
                            if not valor_str.upper().startswith("BP"):
                                registro[campo_destino] = f"BP{valor_str}"
                            else:
                                registro[campo_destino] = valor_str
                        # Procesamiento especial para valor_proyectado
                        elif campo_destino == "valor_proyectado":
                            try:
                                # Limpiar formato de número (comas, espacios, etc.)
                                valor_limpio = re.sub(r'[^\d.-]', '', valor_str)
                                if valor_limpio:
                                    registro[campo_destino] = float(valor_limpio)
                                else:
                                    registro[campo_destino] = 0
                            except (ValueError, TypeError):
                                registro[campo_destino] = 0
                        else:
                            registro[campo_destino] = valor_str
                
                # Agregar metadatos
                registro["fecha_carga"] = datetime.now().isoformat()
                registro["fuente"] = "google_sheets"
                registro["fila_origen"] = index + 1  # +1 porque pandas usa índice 0
                
                # Validar campos obligatorios mínimos
                if not registro.get("referencia_proceso") or registro["referencia_proceso"] == "":
                    filas_con_errores.append({
                        "fila": index + 1,
                        "error": "referencia_proceso vacío o faltante",
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
        
        return {
            "success": True,
            "data": registros_procesados,
            "message": f"Se procesaron {len(registros_procesados)} registros exitosamente",
            "registros_validos": len(registros_procesados),
            "filas_con_errores": len(filas_con_errores),
            "errores_detalle": filas_con_errores,
            "mapeo_aplicado": mapeo_campos
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

        # Obtener todas las proyecciones y filtrar
        proyecciones_ref = db.collection('proyecciones_emprestito')
        proyecciones_docs = list(proyecciones_ref.stream())

        proyecciones_sin_proceso = []
        for doc in proyecciones_docs:
            pdata = doc.to_dict()
            refp = pdata.get('referencia_proceso')
            refp_str = str(refp).strip() if refp is not None else None
            if not refp_str or refp_str not in referencias_procesos:
                pdata['id'] = doc.id
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


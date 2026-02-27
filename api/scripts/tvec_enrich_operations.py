"""
Operaciones para enriquecer datos de órdenes de compra de empréstito con datos de TVEC
"""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
import pandas as pd
from sodapy import Socrata
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

SODAPY_AVAILABLE = True
try:
    import pandas as pd
    from sodapy import Socrata
except ImportError as e:
    SODAPY_AVAILABLE = False
    logger.warning(f"Sodapy o pandas no disponible: {e}")

# Variables de disponibilidad
TVEC_ENRICH_OPERATIONS_AVAILABLE = FIRESTORE_AVAILABLE and SODAPY_AVAILABLE

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


async def obtener_ordenes_compra_tvec_enriquecidas(numero_orden: Optional[str] = None) -> Dict[str, Any]:
    """
    Obtiene órdenes de compra de la colección 'ordenes_compra_emprestito',
    las enriquece con datos de la API de TVEC, y actualiza los registros con la información adicional.

    Si se proporciona `numero_orden`, solo procesa esa orden específica.
    
    El proceso:
    1. Obtiene todas las órdenes de compra existentes
    2. Busca específicamente en TVEC los números de orden que tenemos
    3. Obtiene datos de BPIN desde proyectos_presupuestales usando BP
    4. Enriquece cada orden con datos TVEC y BPIN (campos limitados)
    5. Actualiza los documentos en Firebase preservando datos originales
    
    Returns:
        Dict con resultado del enriquecimiento, estadísticas y órdenes actualizadas
    """
    try:
        tiempo_inicio = datetime.now()
        logger.info("🚀 Iniciando enriquecimiento de órdenes de compra con datos de TVEC...")
        
        # Obtener cliente de Firestore
        try:
            db_client = get_firestore_client()
        except Exception as e:
            logger.error(f"Error obteniendo cliente Firestore: {e}")
            return {
                "success": False,
                "error": "Error obteniendo cliente Firestore",
                "data": [],
                "count": 0
            }
        
        # 1. Obtener órdenes de compra existentes (todas o filtradas por numero_orden)
        ordenes_ref = db_client.collection('ordenes_compra_emprestito')
        numero_orden_filter = str(numero_orden).strip() if numero_orden is not None else None

        if numero_orden_filter:
            ordenes_docs = list(
                ordenes_ref.where('numero_orden', '==', numero_orden_filter).stream()
            )
        else:
            ordenes_docs = list(ordenes_ref.stream())
        
        if not ordenes_docs:
            return {
                "success": True,
                "message": "No se encontraron órdenes de compra para enriquecer",
                "data": [],
                "count": 0,
                "filters": {
                    "numero_orden": numero_orden_filter
                },
                "timestamp": datetime.now().isoformat()
            }
        
        if numero_orden_filter:
            logger.info(f"📊 Encontradas {len(ordenes_docs)} órdenes para numero_orden={numero_orden_filter}")
        else:
            logger.info(f"📊 Encontradas {len(ordenes_docs)} órdenes de compra para enriquecer")
        
        # 2. Extraer números de orden de Firebase para búsqueda específica
        numeros_orden_firebase = []
        for orden_doc in ordenes_docs:
            orden_data = orden_doc.to_dict()
            numero_orden = orden_data.get('numero_orden')
            if numero_orden:
                numeros_orden_firebase.append(str(numero_orden))
        
        logger.info(f"🔍 Números de orden a buscar en TVEC: {numeros_orden_firebase}")

        # 3. Obtener SOLO los registros de TVEC que coincidan con nuestros números
        logger.info("🔍 Buscando registros específicos en TVEC...")
        tvec_dict = {}
        registros_tvec_encontrados = 0
        
        # Usar la API de TVEC con filtros específicos
        try:
            logger.info("🔍 Ejecutando snippet TVEC exacto del usuario...")
            # Implementación exacta del snippet proporcionado
            client = Socrata("www.datos.gov.co", None)
            
            # Buscar cada número de orden específicamente
            for numero_orden in numeros_orden_firebase:
                try:
                    # Buscar en el campo identificador_de_la_orden
                    results = client.get("rgxm-mmea", 
                                       where=f"identificador_de_la_orden='{numero_orden}'",
                                       limit=10)
                    
                    if results:
                        for registro in results:
                            tvec_dict[numero_orden] = registro
                            registros_tvec_encontrados += 1
                        logger.info(f"✅ Encontrado {len(results)} registros para orden: {numero_orden}")
                    else:
                        logger.info(f"❌ No encontrado en TVEC: {numero_orden}")
                        
                except Exception as e:
                    logger.warning(f"⚠️ Error buscando orden {numero_orden}: {str(e)}")
                    continue
            
            client.close()
            
        except Exception as e:
            logger.error(f"❌ Error conectando a TVEC: {str(e)}")
            return {
                "success": False,
                "error": f"Error obteniendo datos de TVEC: {str(e)}",
                "data": [],
                "count": 0
            }

        logger.info(f"📋 Registros TVEC encontrados para nuestras órdenes: {registros_tvec_encontrados}")

        # 4. Obtener datos de BPIN desde proyectos_presupuestales usando BP
        logger.info("🔍 Obteniendo datos de BPIN desde proyectos_presupuestales...")
        bpin_dict = {}
        bps_unicos = list(set([str(orden_doc.to_dict().get('bp', '')) for orden_doc in ordenes_docs if orden_doc.to_dict().get('bp')]))
        
        logger.info(f"📋 BPs únicos a buscar: {bps_unicos}")
        
        try:
            for bp in bps_unicos:
                if bp and bp.strip():
                    # Consultar proyectos_presupuestales por BP
                    proyectos_ref = db_client.collection('proyectos_presupuestales')
                    proyectos_query = proyectos_ref.where('bp', '==', bp).limit(10)
                    proyectos_docs = list(proyectos_query.stream())
                    
                    if proyectos_docs:
                        for proyecto_doc in proyectos_docs:
                            proyecto_data = proyecto_doc.to_dict()
                            bpin = proyecto_data.get('bpin')
                            if bpin:
                                bpin_dict[bp] = {
                                    'bpin': bpin,
                                    'nombre_proyecto': proyecto_data.get('nombre_proyecto', ''),
                                    'estado_proyecto': proyecto_data.get('estado', ''),
                                    'doc_id': proyecto_doc.id
                                }
                                logger.info(f"✅ BPIN encontrado para BP {bp}: {bpin}")
                                break  # Tomar el primer resultado válido
                    else:
                        logger.info(f"❌ No se encontró BPIN para BP: {bp}")
                        
        except Exception as e:
            logger.warning(f"⚠️ Error obteniendo datos de BPIN: {str(e)}")
        
        logger.info(f"📋 Datos de BPIN indexados: {len(bpin_dict)} BPs")

        # 5. Procesar cada orden de compra
        total_ordenes = len(ordenes_docs)
        ordenes_enriquecidas = 0
        ordenes_sin_datos_tvec = 0
        ordenes_actualizadas = []
        errores = []

        for i, orden_doc in enumerate(ordenes_docs, 1):
            try:
                orden_data = orden_doc.to_dict()
                numero_orden = orden_data.get('numero_orden')

                if not numero_orden:
                    logger.warning(f"⚠️ Orden {i}/{total_ordenes} sin numero_orden: {orden_doc.id}")
                    errores.append({
                        "doc_id": orden_doc.id,
                        "error": "Orden sin numero_orden"
                    })
                    continue

                logger.info(f"🔄 Procesando orden {i}/{total_ordenes}: {numero_orden}")

                # Buscar datos adicionales en TVEC (usando número como string)
                datos_tvec = tvec_dict.get(str(numero_orden))
                
                # Buscar datos de BPIN usando BP
                bp_orden = orden_data.get('bp')
                datos_bpin = bpin_dict.get(str(bp_orden)) if bp_orden else None

                if not datos_tvec:
                    logger.info(f"ℹ️ No se encontraron datos adicionales en TVEC para: {numero_orden}")
                    ordenes_sin_datos_tvec += 1
                    continue

                # 6. Enriquecer datos existentes (conservar campos originales)
                datos_enriquecidos = orden_data.copy()  # Mantener datos originales

                # Campos con estructura similar a contratos de empréstito (usando campos reales de TVEC)
                campos_estructura_contrato = {
                    # Identificación y referencias (usando campos reales del API TVEC)
                    "solicitud_id": datos_tvec.get("solicitud"),  # Campo real: solicitud
                    
                    # Estado y modalidad (campos reales)
                    "estado_orden": datos_tvec.get("estado"),  # Campo real: estado
                    "modalidad_contratacion": datos_tvec.get("agregacion"),  # Campo real: agregacion
                    
                    # Fechas en formato estándar (campos reales)
                    "fecha_publicacion_orden": datos_tvec.get("fecha"),  # Campo real: fecha
                    "fecha_vencimiento_orden": datos_tvec.get("fecha_vence"),  # Campo real: fecha_vence
                    "ano_orden": datos_tvec.get("a_o"),  # Campo real: a_o (año)
                    
                    # Proveedores (usando campos reales del API)
                    "nombre_proveedor": datos_tvec.get("proveedor"),  # Campo real: proveedor
                    "nit_proveedor": datos_tvec.get("nit_proveedor"),  # Campo real: nit_proveedor
                    "nit_entidad": datos_tvec.get("nit_entidad"),  # Campo real: nit_entidad
                    
                    # Responsables y solicitantes (campos reales)
                    "solicitante": datos_tvec.get("solicitante"),  # Campo real: solicitante
                    "ordenador_gasto": datos_tvec.get("solicitante"),  # Mapeo a solicitante
                    
                    # Descripción y objeto (campos reales)
                    "objeto_orden": datos_tvec.get("items"),  # Campo real: items
                    "items": datos_tvec.get("items"),  # Campo real: items
                    
                    # Categorización y sector (campos reales)
                    "sector": datos_tvec.get("sector_de_la_entidad"),  # Campo real: sector_de_la_entidad
                    "rama_entidad": datos_tvec.get("rama_de_la_entidad"),  # Campo real: rama_de_la_entidad
                    
                    # Valores monetarios (campo real)
                    "valor_orden": datos_tvec.get("total"),  # Campo real: total
                    
                    # Metadatos de origen
                    "_dataset_source": "rgxm-mmea",  # Similar a jbjy-vk9h para contratos
                    "fuente_datos": "TVEC_API",  # Similar a SECOP_API
                    "plataforma_origen": "TVEC",  # Identificador de plataforma
                    "tipo_documento": "ORDEN_COMPRA_TVEC"
                }
                
                # Campos adicionales TVEC específicos (campos mínimos necesarios)
                campos_adicionales_tvec = {
                    # Solo mantener campos esenciales, eliminando los especificados
                }
                
                # Campos de BPIN desde proyectos_presupuestales (usando BP) - solo BPIN
                campos_bpin = {}
                if datos_bpin:
                    campos_bpin = {
                        "bpin": datos_bpin.get("bpin")  # Solo el BPIN, eliminando otros campos especificados
                    }
                    logger.info(f"✅ BPIN agregado para orden {numero_orden}: {datos_bpin.get('bpin')}")
                else:
                    logger.info(f"ℹ️ No se encontró BPIN para orden {numero_orden} con BP: {bp_orden}")
                
                # Combinar todos los campos
                campos_adicionales = {**campos_estructura_contrato, **campos_adicionales_tvec, **campos_bpin}
                
                # Solo agregar campos que no sean None y que no existan ya
                for campo, valor in campos_adicionales.items():
                    if valor is not None and campo not in datos_enriquecidos:
                        datos_enriquecidos[campo] = valor
                
                # Actualizar metadatos (estructura similar a contratos)
                datos_enriquecidos["fecha_enriquecimiento_tvec"] = datetime.now()
                datos_enriquecidos["fecha_guardado"] = datetime.now()  # Similar a contratos
                datos_enriquecidos["fecha_actualizacion"] = datetime.now()
                
                # 5. Actualizar en Firebase
                orden_doc.reference.update(datos_enriquecidos)
                
                ordenes_enriquecidas += 1
                
                # Agregar a la lista de órdenes actualizadas para la respuesta
                campos_agregados = list(campos_adicionales.keys())
                ordenes_actualizadas.append({
                    "doc_id": orden_doc.id,
                    "numero_orden": numero_orden,
                    "datos_enriquecidos": serialize_datetime_objects(datos_enriquecidos),
                    "campos_agregados": campos_agregados
                })
                
                logger.info(f"✅ Orden {numero_orden} enriquecida y actualizada en Firebase")
                
            except Exception as e:
                logger.error(f"Error procesando orden {numero_orden}: {e}")
                errores.append({
                    "doc_id": orden_doc.id,
                    "numero_orden": numero_orden,
                    "error": str(e)
                })
        
        tiempo_total = (datetime.now() - tiempo_inicio).total_seconds()
        
        return {
            "success": True,
            "message": f"Enriquecimiento completado: {ordenes_enriquecidas}/{total_ordenes} órdenes enriquecidas",
            "filters": {
                "numero_orden": numero_orden_filter
            },
            "resumen": {
                "total_ordenes_procesadas": total_ordenes,
                "ordenes_enriquecidas": ordenes_enriquecidas,
                "ordenes_sin_datos_tvec": ordenes_sin_datos_tvec,
                "ordenes_con_errores": len(errores),
                "tasa_enriquecimiento": f"{(ordenes_enriquecidas/total_ordenes*100):.1f}%" if total_ordenes > 0 else "0%"
            },
            "fuente_datos": {
                "api_tvec": "www.datos.gov.co",
                "dataset": "rgxm-mmea",
                "registros_tvec_disponibles": len(tvec_dict)
            },
            "fuente_bpin": {
                "coleccion_firebase": "proyectos_presupuestales",
                "bps_consultados": len(bps_unicos),
                "bpins_encontrados": len(bpin_dict),
                "matching_field": "bp"
            },
            "operacion_firebase": {
                "coleccion": "ordenes_compra_emprestito",
                "documentos_actualizados": ordenes_enriquecidas,
                "campos_preservados": True,
                "campos_agregados_prefijo": "tvec_",
                "campos_bpin_agregados": True
            },
            "ordenes_actualizadas": ordenes_actualizadas,
            "errores": errores,
            "tiempo_total_segundos": tiempo_total,
            "timestamp": datetime.now().isoformat(),
            "api_info": {
                "endpoint_name": "obtener-ordenes-compra-TVEC",
                "version": "1.0",
                "snippet_based": True,
                "preserves_original_data": True
            },
            "last_updated": datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).isoformat() + "Z"
        }
        
    except Exception as e:
        logger.error(f"Error general en enriquecimiento TVEC: {e}")
        return {
            "success": False,
            "error": str(e),
            "message": "Error durante el enriquecimiento con datos de TVEC",
            "timestamp": datetime.now().isoformat()
        }


def get_tvec_enrich_status() -> Dict[str, Any]:
    """Obtener estado de las operaciones de enriquecimiento TVEC"""
    return {
        "firestore_available": FIRESTORE_AVAILABLE,
        "sodapy_available": SODAPY_AVAILABLE,
        "operations_available": TVEC_ENRICH_OPERATIONS_AVAILABLE,
        "api_endpoint": "www.datos.gov.co",
        "dataset": "rgxm-mmea",
        "timestamp": datetime.now().isoformat()
    }
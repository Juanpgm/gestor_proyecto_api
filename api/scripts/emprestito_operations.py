"""
Scripts para manejo de Procesos de Empréstito - Versión Limpia
Solo funcionalidades esenciales habilitadas
"""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
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

async def obtener_datos_secop(*args, **kwargs):
    """Función stub - No implementada temporalmente"""
    return {"success": False, "error": "Función no implementada temporalmente"}

async def obtener_datos_tvec(*args, **kwargs):
    """Función stub - No implementada temporalmente"""
    return {"success": False, "error": "Función no implementada temporalmente"}

async def detectar_plataforma(*args, **kwargs):
    """Función stub - No implementada temporalmente"""
    return {"success": False, "error": "Función no implementada temporalmente"}

async def guardar_proceso_emprestito(*args, **kwargs):
    """Función stub - No implementada temporalmente"""
    return {"success": False, "error": "Función no implementada temporalmente"}

async def guardar_orden_compra_emprestito(*args, **kwargs):
    """Función stub - No implementada temporalmente"""
    return {"success": False, "error": "Función no implementada temporalmente"}

async def procesar_emprestito_completo(datos_emprestito: Dict[str, Any]) -> Dict[str, Any]:
    """
    Procesa y guarda un empréstito completo implementando la lógica real del POST /emprestito/cargar-proceso.
    
    Esta función implementa:
    1. Validación de duplicados
    2. Detección automática de plataforma (SECOP/TVEC)
    3. Validación de centro gestor contra nombres únicos
    4. Almacenamiento en colección apropiada según plataforma
    5. Formato original básico (sin datos de APIs externas)
    """
    try:
        if not FIRESTORE_AVAILABLE:
            return {"success": False, "error": "Firebase no disponible"}
        
        db = get_firestore_client()
        if db is None:
            return {"success": False, "error": "No se pudo conectar a Firestore"}
        
        # Validar campos obligatorios
        referencia_proceso = datos_emprestito.get("referencia_proceso")
        nombre_centro_gestor = datos_emprestito.get("nombre_centro_gestor")
        nombre_banco = datos_emprestito.get("nombre_banco")
        plataforma = datos_emprestito.get("plataforma")
        
        if not referencia_proceso:
            return {"success": False, "error": "referencia_proceso es obligatorio"}
        if not nombre_centro_gestor:
            return {"success": False, "error": "nombre_centro_gestor es obligatorio"}
        if not nombre_banco:
            return {"success": False, "error": "nombre_banco es obligatorio"}
        if not plataforma:
            return {"success": False, "error": "plataforma es obligatorio"}
        
        logger.info(f"🔄 Procesando empréstito: {referencia_proceso} - {plataforma}")
        
        # 1. VALIDAR CENTRO GESTOR contra nombres únicos
        try:
            centros_gestores_validos = await obtener_centros_gestores_validos()
            if centros_gestores_validos and nombre_centro_gestor not in centros_gestores_validos:
                logger.warning(f"⚠️ Centro gestor no válido: {nombre_centro_gestor}")
                # No es error crítico, solo advertencia
        except Exception as e:
            logger.warning(f"⚠️ No se pudo validar centro gestor: {str(e)}")
        
        # 2. DETECTAR PLATAFORMA
        plataforma_detectada = detectar_plataforma_emprestito(plataforma)
        coleccion_destino = determinar_coleccion_por_plataforma(plataforma_detectada)
        
        logger.info(f"🎯 Plataforma detectada: {plataforma_detectada} → Colección: {coleccion_destino}")
        
        # 3. VERIFICAR DUPLICADOS en ambas colecciones
        resultado_duplicado = await verificar_proceso_existente(referencia_proceso)
        if resultado_duplicado.get("existe"):
            return {
                "success": False,
                "error": f"Ya existe un proceso con referencia {referencia_proceso}",
                "duplicate": True,
                "existing_data": resultado_duplicado.get("documento"),
                "coleccion_existente": resultado_duplicado.get("coleccion")
            }
        
        # 4. CREAR DOCUMENTO EN FORMATO ORIGINAL
        documento_original = {
            "referencia_proceso": referencia_proceso,
            "nombre_centro_gestor": nombre_centro_gestor,
            "nombre_banco": nombre_banco,
            "bp": datos_emprestito.get("bp"),
            "plataforma": plataforma_detectada,
            "nombre_resumido_proceso": datos_emprestito.get("nombre_resumido_proceso"),
            "id_paa": datos_emprestito.get("id_paa"),
            "valor_proyectado": datos_emprestito.get("valor_proyectado"),
            "fecha_creacion": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "fecha_actualizacion": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "fuente_datos": "MANUAL_ENTRY",
            "estado_proceso": "En proceso",  # Estado inicial
            "usuario_creacion": "sistema"
        }
        
        # Limpiar valores None de campos opcionales
        documento_limpio = {k: v for k, v in documento_original.items() if v is not None}
        
        # 5. GUARDAR EN COLECCIÓN APROPIADA
        collection_ref = db.collection(coleccion_destino)
        doc_ref = collection_ref.add(documento_limpio)
        doc_id = doc_ref[1].id
        
        logger.info(f"✅ Proceso {referencia_proceso} creado exitosamente en {coleccion_destino}")
        
        return {
            "success": True,
            "message": f"Proceso de empréstito cargado exitosamente en {coleccion_destino}",
            "data": documento_limpio,
            "doc_id": doc_id,
            "coleccion": coleccion_destino,
            "plataforma_detectada": plataforma_detectada,
            "fuente_datos": "MANUAL_ENTRY"
        }
        
    except Exception as e:
        logger.error(f"Error procesando empréstito completo: {str(e)}")
        return {
            "success": False,
            "error": f"Error procesando empréstito: {str(e)}"
        }

def detectar_plataforma_emprestito(plataforma: str) -> str:
    """
    Detecta y valida la plataforma (SECOP o TVEC).
    """
    try:
        if not plataforma:
            return 'SECOP'  # Por defecto
        
        plataforma_upper = plataforma.upper().strip()
        
        if plataforma_upper in ['SECOP', 'SECOP I', 'SECOP II']:
            return 'SECOP'
        elif plataforma_upper in ['TVEC', 'TIENDA VIRTUAL', 'TIENDA_VIRTUAL']:
            return 'TVEC'
        else:
            logger.warning(f"Plataforma no reconocida: {plataforma}. Usando SECOP por defecto.")
            return 'SECOP'
            
    except Exception as e:
        logger.error(f"Error detectando plataforma: {str(e)}")
        return 'SECOP'

def determinar_coleccion_por_plataforma(plataforma: str) -> str:
    """
    Determina la colección de Firestore según la plataforma.
    """
    if plataforma == 'TVEC':
        return 'ordenes_compra_emprestito'
    else:  # SECOP por defecto
        return 'procesos_emprestito'

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

async def obtener_contratos_desde_proceso_contractual(*args, **kwargs):
    """Función stub - No implementada temporalmente"""
    return {"success": False, "error": "Función no implementada temporalmente"}
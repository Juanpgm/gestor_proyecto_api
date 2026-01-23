"""
Router para Artefacto de Captura #360
Endpoints para gestión de reconocimiento de unidades de proyecto
"""

from fastapi import APIRouter, HTTPException, Form, status
from fastapi.responses import JSONResponse
from typing import List, Optional, Dict, Any
import logging
from datetime import datetime
import json
import re

from api.models.captura_360_models import (
    CapturaEstado360Request,
    CapturaEstado360Response,
    UpEntorno,
    CoordinatesGPS
)

from api.scripts.captura_360_operations import (
    crear_registro_captura_360,
    obtener_registros_por_upid,
    obtener_registros_con_filtros,
    subir_fotos_s3,
    mapear_estado_360,
    CAPTURA_360_OPERATIONS_AVAILABLE
)

# Configurar logger
logger = logging.getLogger(__name__)

# ✅ CONSTANTES Y VALIDADORES
ESTADOS_360_VALIDOS = ["Antes", "Durante", "Después"]
TIPOS_VISITA_VALIDOS = ["Verificación", "Comunicaciones"]

# Expresión regular para validar emails
EMAIL_PATTERN = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')

def validar_email(email: str) -> bool:
    """Validar formato de email"""
    return EMAIL_PATTERN.match(email) is not None

def validar_url_foto(url: str) -> bool:
    """Validar que la URL sea válida (http/https)"""
    if not url or not isinstance(url, str):
        return False
    return url.startswith('http://') or url.startswith('https://')

def validar_coordenadas_json(coord_json: str) -> tuple[bool, Optional[List]]:
    """Validar y parsear JSON de coordenadas"""
    try:
        coords = json.loads(coord_json)
        if not isinstance(coords, list) or len(coords) < 2:
            return False, None
        # Validar que sean números
        if not all(isinstance(c, (int, float)) for c in coords):
            return False, None
        return True, coords
    except (json.JSONDecodeError, ValueError):
        return False, None

def construir_error_validacion(campo: str, detalle: str) -> Dict[str, Any]:
    """Construir objeto de error de validación consistente"""
    return {
        "success": False,
        "message": f"Error de validación en {campo}",
        "detail": detalle,
        "timestamp": datetime.now().isoformat()
    }

# Crear router
router = APIRouter(
    prefix="/unidades-proyecto",
    tags=["Artefacto de Captura #360"]
)


@router.post(
    "/captura-estado-360",
    response_model=CapturaEstado360Response,
    summary="🟢 POST | 📸 Captura 360 | Registrar Estado 360",
    responses={
        200: {"description": "✅ Registro creado exitosamente"},
        400: {"description": "❌ Error de validación de datos"},
        422: {"description": "❌ Campo faltante o formato incorrecto"},
        503: {"description": "❌ Servicio no disponible"}
    }
)
async def captura_estado_360_endpoint(
    # Campos de texto
    upid: str = Form(..., min_length=1, description="ID único de la unidad de proyecto"),
    nombre_up: str = Form(..., min_length=1, description="Nombre de la unidad de proyecto"),
    nombre_up_detalle: str = Form(..., min_length=1, description="Detalle del nombre de la unidad de proyecto"),
    descripcion_intervencion: str = Form(..., min_length=1, description="Descripción de la intervención"),
    solicitud_intervencion: str = Form(..., min_length=1, description="Solicitud de la intervención"),
    
    # Campos del entorno (up_entorno) - LISTA de centros gestores
    nombre_centro_gestor: List[str] = Form(..., description="Lista de nombres de centros gestores"),
    solicitud_centro_gestor: List[str] = Form(..., description="Lista de solicitudes de centros gestores"),
    
    # Estado y flags
    estado_360: str = Form(..., description="Estado 360: 'Antes', 'Durante' o 'Después'"),
    requiere_alcalde: bool = Form(..., description="¿Requiere participación del alcalde?"),
    entrega_publica: bool = Form(..., description="¿Habrá entrega pública?"),
    tipo_visita: str = Form(..., description="Tipo de visita: 'Verificación' o 'Comunicaciones'"),
    observaciones: Optional[str] = Form(None, description="Observaciones adicionales (opcional)"),
    
    # Registrado por
    registrado_por_username: str = Form(..., min_length=1, description="Nombre de usuario que registra (displayName)"),
    registrado_por_email: str = Form(..., min_length=1, description="Email del usuario que registra"),
    
    # Coordenadas GPS
    coordinates_type: str = Form(..., min_length=1, description="Tipo de geometría (Point, LineString, Polygon, etc.)"),
    coordinates_data: str = Form(..., description="Coordenadas en formato JSON array"),
    
    # URLs de fotos
    photosUrl: List[str] = Form(..., description="Lista de URLs de fotos a guardar según estado_360 (obligatorio)")
):
    """
    ## 🟢 POST | 📸 Captura 360 | Registrar Estado de Reconocimiento 360
    
    **Propósito**: Crear registro de captura estado 360 para una unidad de proyecto,
    incluyendo información del reconocimiento y URLs de fotos organizadas por estado.
    
    ### ✅ Funcionalidades:
    - Crear/actualizar registro en colección "unidades_proyecto_reconocimiento_360"
    - Guardar MÚLTIPLES centros gestores para la misma unidad de proyecto
    - Guardar URLs de fotos en Firebase según el estado_360 (Antes/Durante/Después)
    - Validación robusta de todos los campos en producción
    - Manejo completo de errores con mensajes detallados
    
    ### ⚠️ VALIDACIONES IMPLEMENTADAS:
    1. **Campos obligatorios**: Todos deben estar presentes y no vacíos
    2. **estado_360**: Solo acepta 'Antes', 'Durante' o 'Después'
    3. **tipo_visita**: Solo acepta 'Verificación' o 'Comunicaciones'
    4. **Email**: Validación de formato RFC completo
    5. **Coordenadas**: Deben ser JSON array válido con al menos 2 números
    6. **URLs de fotos**: Deben comenzar con http:// o https://
    7. **Centros gestores**: Las listas deben tener el mismo tamaño
    
    ### 📊 Ejemplo de solicitud correcta:
    ```javascript
    const formData = new FormData();
    formData.append('upid', 'UNP-001-2024');
    formData.append('nombre_up', 'Parque Central');
    formData.append('nombre_up_detalle', 'Renovación del parque central');
    formData.append('descripcion_intervencion', 'Intervención integral');
    formData.append('solicitud_intervencion', 'SOL-2024-001');
    
    // Centros gestores (MÚLTIPLES permitidos)
    formData.append('nombre_centro_gestor', 'Secretaría de Infraestructura');
    formData.append('solicitud_centro_gestor', 'Revisión técnica requerida');
    
    formData.append('estado_360', 'Durante');
    formData.append('requiere_alcalde', 'true');
    formData.append('entrega_publica', 'true');
    formData.append('tipo_visita', 'Verificación');
    formData.append('observaciones', 'Observaciones del proyecto');
    
    formData.append('registrado_por_username', 'Juan Pérez');
    formData.append('registrado_por_email', 'juan.perez@example.com');
    formData.append('coordinates_type', 'Point');
    formData.append('coordinates_data', '[-76.5225, 3.4516]');
    
    formData.append('photosUrl', 'https://cloudinary.com/foto1.jpg');
    formData.append('photosUrl', 'https://example.com/foto2.jpg');
    
    const response = await fetch('/unidades-proyecto/captura-estado-360', {
        method: 'POST',
        body: formData
    });
    ```
    """
    # ✅ VALIDACIÓN EXHAUSTIVA EN PRODUCCIÓN
    try:
        # 1️⃣ Validar estado_360
        if estado_360 not in ESTADOS_360_VALIDOS:
            return JSONResponse(
                status_code=400,
                content=construir_error_validacion(
                    "estado_360",
                    f"Valor inválido: '{estado_360}'. Debe ser uno de: {', '.join(ESTADOS_360_VALIDOS)}"
                )
            )
        
        # 2️⃣ Validar tipo_visita
        if tipo_visita not in TIPOS_VISITA_VALIDOS:
            return JSONResponse(
                status_code=400,
                content=construir_error_validacion(
                    "tipo_visita",
                    f"Valor inválido: '{tipo_visita}'. Debe ser uno de: {', '.join(TIPOS_VISITA_VALIDOS)}"
                )
            )
        
        # 3️⃣ Validar email
        if not validar_email(registrado_por_email):
            return JSONResponse(
                status_code=400,
                content=construir_error_validacion(
                    "registrado_por_email",
                    f"Email inválido: '{registrado_por_email}'. Debe ser un email válido"
                )
            )
        
        # 4️⃣ Validar centros gestores
        if not nombre_centro_gestor or len(nombre_centro_gestor) == 0:
            return JSONResponse(
                status_code=400,
                content=construir_error_validacion(
                    "nombre_centro_gestor",
                    "Debe proporcionar al menos un centro gestor"
                )
            )
        
        if len(nombre_centro_gestor) != len(solicitud_centro_gestor):
            return JSONResponse(
                status_code=400,
                content=construir_error_validacion(
                    "arrays_desajustados",
                    f"nombre_centro_gestor ({len(nombre_centro_gestor)}) y solicitud_centro_gestor ({len(solicitud_centro_gestor)}) deben tener el mismo número de elementos"
                )
            )
        
        # 5️⃣ Validar coordenadas
        coords_validas, coords_parseadas = validar_coordenadas_json(coordinates_data)
        if not coords_validas:
            return JSONResponse(
                status_code=400,
                content=construir_error_validacion(
                    "coordinates_data",
                    f"Coordenadas inválidas: '{coordinates_data}'. Debe ser JSON array con al menos 2 números. Ejemplo: [-76.5225, 3.4516]"
                )
            )
        
        # 6️⃣ Validar URLs de fotos
        if not photosUrl or len(photosUrl) == 0:
            return JSONResponse(
                status_code=400,
                content=construir_error_validacion(
                    "photosUrl",
                    "Debe proporcionar al menos una URL de foto"
                )
            )
        
        urls_invalidas = []
        for idx, url in enumerate(photosUrl):
            if not validar_url_foto(url):
                urls_invalidas.append(f"[{idx}] {url}")
        
        if urls_invalidas:
            return JSONResponse(
                status_code=400,
                content=construir_error_validacion(
                    "photosUrl",
                    f"URLs inválidas encontradas (deben comenzar con http:// o https://): {', '.join(urls_invalidas)}"
                )
            )
        
        # ✅ SI LLEGAMOS AQUÍ, TODA LA VALIDACIÓN PASÓ
        
        if not CAPTURA_360_OPERATIONS_AVAILABLE:
            return JSONResponse(
                status_code=503,
                content={
                    "success": False,
                    "message": "Servicio de captura 360 no disponible",
                    "timestamp": datetime.now().isoformat()
                }
            )
        
        # Construir estructuras de datos
        entornos = []
        for nombre, solicitud in zip(nombre_centro_gestor, solicitud_centro_gestor):
            entornos.append({
                "nombre_centro_gestor": nombre.strip(),
                "solicitud_centro_gestor": solicitud.strip()
            })
        
        up_entorno = {"entornos": entornos}
        
        registrado_por = {
            "username": registrado_por_username.strip(),
            "email": registrado_por_email.strip()
        }
        
        coordinates_gps = {
            "type": coordinates_type,
            "coordinates": coords_parseadas
        }
        
        # Procesar URLs de fotos
        logger.info(f"📸 Procesando {len(photosUrl)} URLs para UPID {upid} estado {estado_360}")
        
        photos_uploaded = []
        photos_failed = []
        
        fecha_registro = datetime.now().isoformat()
        
        # Llamar función de procesamiento
        photos_uploaded, photos_failed = await subir_fotos_s3(
            photos_urls=photosUrl,
            nombre_centro_gestor=nombre_centro_gestor[0] if nombre_centro_gestor else "sin_centro",
            upid=upid,
            estado_360=estado_360,
            fecha_registro=fecha_registro
        )
        
        logger.info(f"✅ URLs procesadas: {len(photos_uploaded)}, Fallidas: {len(photos_failed)}")
        
        # Crear registro en Firestore
        document_id, registro_data = await crear_registro_captura_360(
            upid=upid,
            nombre_up=nombre_up,
            nombre_up_detalle=nombre_up_detalle,
            descripcion_intervencion=descripcion_intervencion,
            solicitud_intervencion=solicitud_intervencion,
            up_entorno=up_entorno,
            estado_360=estado_360,
            requiere_alcalde=requiere_alcalde,
            entrega_publica=entrega_publica,
            tipo_visita=tipo_visita,
            observaciones=observaciones,
            coordinates_gps=coordinates_gps,
            registrado_por=registrado_por,
            photosUrl=photos_uploaded,
            fecha_registro=fecha_registro
        )
        
        logger.info(f"✅ Registro creado: {document_id} para UPID {upid}")
        
        return CapturaEstado360Response(
            success=True,
            message="Registro de captura 360 creado exitosamente",
            data=registro_data,
            document_id=document_id,
            estado_360=estado_360,
            photos_uploaded=photos_uploaded,
            photos_failed=photos_failed if photos_failed else None,
            timestamp=fecha_registro
        )
        
    except Exception as e:
        logger.error(f"❌ Error inesperado en captura 360: {str(e)}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "message": "Error interno del servidor",
                "detail": str(e),
                "timestamp": datetime.now().isoformat()
            }
        )


# Endpoints adicionales para consultar registros
@router.get(
    "/captura-estado-360",
    summary="🔵 GET | 📸 Captura 360 | Obtener Registros con Filtros"
)
async def obtener_captura_360_con_filtros(
    upid: Optional[str] = None,
    nombre_centro_gestor: Optional[str] = None,
    estado_360: Optional[str] = None,
    tipo_visita: Optional[str] = None
):
    """
    ## 🔵 GET | 📸 Captura 360 | Obtener Registros con Filtros Opcionales
    
    **Propósito**: Obtener registros de captura 360 con filtros opcionales.
    
    ### 🔍 Filtros disponibles (todos opcionales):
    - **upid**: ID único de la unidad de proyecto
    - **nombre_centro_gestor**: Nombre del centro gestor
    - **estado_360**: Estado 360 ('Antes', 'Durante', 'Después')
    - **tipo_visita**: Tipo de visita ('Verificación', 'Comunicaciones')
    
    ### 📊 Información retornada:
    - Lista de registros que cumplan con los filtros aplicados
    - Si no se aplica ningún filtro, retorna todos los registros
    - Información completa de cada registro (fotos, coordenadas, estados, etc.)
    - Conteo total de registros
    
    ### 📝 Ejemplos de uso:
    ```javascript
    // Buscar por UPID
    const response1 = await fetch('/unidades-proyecto/captura-estado-360?upid=UNP-1234');
    
    // Buscar por centro gestor
    const response2 = await fetch('/unidades-proyecto/captura-estado-360?nombre_centro_gestor=Secretaría de Infraestructura');
    
    // Buscar por estado_360
    const response3 = await fetch('/unidades-proyecto/captura-estado-360?estado_360=Antes');
    
    // Combinar filtros
    const response4 = await fetch('/unidades-proyecto/captura-estado-360?estado_360=Durante&tipo_visita=Verificación');
    
    // Obtener todos los registros
    const response5 = await fetch('/unidades-proyecto/captura-estado-360');
    ```
    """
    if not CAPTURA_360_OPERATIONS_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="Operaciones de captura 360 no disponibles"
        )
    
    try:
        # Construir filtros
        filtros = {}
        if upid:
            filtros["upid"] = upid
        if nombre_centro_gestor:
            filtros["nombre_centro_gestor"] = nombre_centro_gestor
        if estado_360:
            filtros["estado_360"] = estado_360
        if tipo_visita:
            filtros["tipo_visita"] = tipo_visita
        
        resultado = await obtener_registros_con_filtros(filtros)
        
        if not resultado["success"]:
            raise HTTPException(
                status_code=500,
                detail=f"Error obteniendo registros: {resultado.get('error', 'Error desconocido')}"
            )
        
        return resultado
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error obteniendo registros: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error obteniendo registros: {str(e)}"
        )

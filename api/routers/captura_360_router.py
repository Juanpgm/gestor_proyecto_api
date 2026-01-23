"""
Router para Artefacto de Captura #360
Endpoints para gestión de reconocimiento de unidades de proyecto
"""

from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from typing import List, Optional
import logging
from datetime import datetime

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

# Crear router
router = APIRouter(
    prefix="/unidades-proyecto",
    tags=["Artefacto de Captura #360"]
)


@router.post(
    "/captura-estado-360",
    response_model=CapturaEstado360Response,
    summary="🟢 POST | 📸 Captura 360 | Registrar Estado 360"
)
async def captura_estado_360_endpoint(
    # Campos de texto
    upid: str = Form(..., description="ID único de la unidad de proyecto"),
    nombre_up: str = Form(..., description="Nombre de la unidad de proyecto"),
    nombre_up_detalle: str = Form(..., description="Detalle del nombre de la unidad de proyecto"),
    descripcion_intervencion: str = Form(..., description="Descripción de la intervención"),
    solicitud_intervencion: str = Form(..., description="Solicitud de la intervención"),
    
    # Campos del entorno (up_entorno) - LISTA de centros gestores
    nombre_centro_gestor: List[str] = Form(..., description="Lista de nombres de centros gestores"),
    solicitud_centro_gestor: List[str] = Form(..., description="Lista de solicitudes de centros gestores"),
    
    # Estado y flags
    estado_360: str = Form(..., description="Estado 360: 'Antes', 'Durante' o 'Después'"),
    requiere_alcalde: bool = Form(..., description="¿Requiere participación del alcalde?"),
    entrega_publica: bool = Form(..., description="¿Habrá entrega pública?"),
    tipo_visita: str = Form(..., description="Tipo de visita: 'Verificación' o 'Comunicaciones'"),
    observaciones: Optional[str] = Form(None, description="Observaciones adicionales (opcional)"),
    
    # Registrado por (como string JSON)
    registrado_por_username: str = Form(..., description="Nombre de usuario que registra (displayName)"),
    registrado_por_email: str = Form(..., description="Email del usuario que registra"),
    
    # Coordenadas GPS (como string JSON)
    coordinates_type: str = Form(..., description="Tipo de geometría (Point, LineString, Polygon, etc.)"),
    coordinates_data: str = Form(..., description="Coordenadas en formato JSON array"),
    
    # Archivos de fotos (obligatorio)
    photosUrl: List[UploadFile] = File(..., description="Fotos a subir (obligatorio)")
):
    """
    ## 🟢 POST | 📸 Captura 360 | Registrar Estado de Reconocimiento 360
    
    **Propósito**: Crear registro de captura estado 360 para una unidad de proyecto,
    incluyendo información del reconocimiento y fotos organizadas por estado.
    
    ### ✅ Funcionalidades:
    - Crear/actualizar registro en colección "unidades_proyecto_reconocimiento_360"
    - Guardar MÚLTIPLES centros gestores para la misma unidad de proyecto
    - Calcular automáticamente estado_360 basado en el estado del proyecto:
      - "En alistamiento" → "Antes"
      - "En ejecución" o "Suspendido" → "Durante"
      - "Terminado" o "Inaugurado" → "Después"
    - Subir fotos a S3 en bucket "360-photos-cali" con estructura organizada:
      - `/images/nombre_centro_gestor/upid/antes/fecha_registro`
      - `/images/nombre_centro_gestor/upid/durante/fecha_registro`
      - `/images/nombre_centro_gestor/upid/despues/fecha_registro`
    - Generar URLs de carpetas para cada estado (Antes/Durante/Después)
    
    ### 📊 Campos requeridos:
    - **upid**: ID único de la unidad de proyecto
    - **nombre_up**: Nombre del proyecto
    - **nombre_up_detalle**: Detalle del nombre
    - **descripcion_intervencion**: Descripción de la intervención
    - **solicitud_intervencion**: Solicitud de intervención
    - **nombre_centro_gestor**: LISTA de centros gestores responsables
    - **solicitud_centro_gestor**: LISTA de solicitudes específicas (debe coincidir en cantidad con nombre_centro_gestor)
    - **estado_360**: Estado 360 del proyecto ('Antes', 'Durante' o 'Después')
    - **requiere_alcalde**: Boolean (True/False)
    - **entrega_publica**: Boolean (True/False)
    - **tipo_visita**: Tipo de visita ('Verificación' o 'Comunicaciones')
    - **observaciones**: Observaciones adicionales (opcional)
    - **registrado_por_username**: Nombre de usuario que registra (displayName)
    - **registrado_por_email**: Email del usuario que registra
    - **coordinates_type**: Tipo de geometría (Point, LineString, etc.)
    - **coordinates_data**: JSON array con coordenadas
    - **photosUrl**: Archivos de fotos (obligatorio)
    
    ### 📝 Ejemplo de uso con JavaScript/fetch (MÚLTIPLES CENTROS):
    ```javascript
    const formData = new FormData();
    formData.append('upid', 'UNP-1234');
    formData.append('nombre_up', 'Parque Central');
    formData.append('nombre_up_detalle', 'Renovación completa');
    formData.append('descripcion_intervencion', 'Mejoramiento integral');
    formData.append('solicitud_intervencion', 'Solicitud 2024-001');
    
    // ✅ AGREGAR MÚLTIPLES CENTROS GESTORES
    formData.append('nombre_centro_gestor', 'Secretaría de Infraestructura');
    formData.append('nombre_centro_gestor', 'Secretaría de Ambiente');
    formData.append('solicitud_centro_gestor', 'Requiere revisión técnica');
    formData.append('solicitud_centro_gestor', 'Revisión ambiental necesaria');
    
    formData.append('estado_360', 'Durante');
    formData.append('requiere_alcalde', 'true');
    formData.append('entrega_publica', 'true');
    formData.append('tipo_visita', 'Verificación');
    formData.append('observaciones', 'Proyecto prioritario');
    formData.append('registrado_por_username', 'Juan Pérez');
    formData.append('registrado_por_email', 'juan.perez@example.com');
    formData.append('coordinates_type', 'Point');
    formData.append('coordinates_data', '[-76.5225, 3.4516]');
    
    // Agregar fotos
    for (const file of photoFiles) {
        formData.append('photosUrl', file);
    }
    
    const response = await fetch('/unidades-proyecto/captura-estado-360', {
        method: 'POST',
        body: formData
    });
    ```
    
    ### 🗂️ Estructura en S3 (bucket: 360-photos-cali):
    ```
    images/
    ├── secretaria_de_infraestructura/
    │   └── unp-1234/
    │       ├── antes/
    │       │   └── 2024-11-26_10-30-00/
    │       │       ├── foto1.jpg
    │       │       └── foto2.jpg
    │       └── durante/
    │           └── 2024-11-26_14-30-00/
    │               └── foto3.jpg
    └── secretaria_de_ambiente/
        └── unp-1234/
            ├── antes/
            │   └── 2024-11-26_10-30-00/
            │       └── foto4.jpg
            └── durante/
                └── 2024-11-26_14-30-00/
                    └── foto5.jpg
    ```
    
    ### ⚠️ IMPORTANTE:
    - La cantidad de elementos en `nombre_centro_gestor` debe ser igual a la cantidad en `solicitud_centro_gestor`
    - Se crean carpetas separadas en S3 para cada centro gestor
    - Cada centro tendrá sus propias fotos organizadas por estado
    """
    if not CAPTURA_360_OPERATIONS_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="Operaciones de captura 360 no disponibles"
        )
    
    try:
        # Validar estado_360
        estados_360_validos = ["Antes", "Durante", "Después"]
        
        if estado_360 not in estados_360_validos:
            raise HTTPException(
                status_code=400,
                detail=f"estado_360 inválido. Debe ser uno de: {', '.join(estados_360_validos)}"
            )
        
        # Validar tipo_visita
        tipos_visita_validos = ["Verificación", "Comunicaciones"]
        
        if tipo_visita not in tipos_visita_validos:
            raise HTTPException(
                status_code=400,
                detail=f"tipo_visita inválido. Debe ser uno de: {', '.join(tipos_visita_validos)}"
            )
        
        # Construir objeto up_entorno como LISTA de centros gestores
        if len(nombre_centro_gestor) != len(solicitud_centro_gestor):
            raise HTTPException(
                status_code=400,
                detail=f"Los arrays nombre_centro_gestor y solicitud_centro_gestor deben tener la misma cantidad de elementos. Recibido: {len(nombre_centro_gestor)} vs {len(solicitud_centro_gestor)}"
            )
        
        entornos = []
        for nombre, solicitud in zip(nombre_centro_gestor, solicitud_centro_gestor):
            entornos.append({
                "nombre_centro_gestor": nombre,
                "solicitud_centro_gestor": solicitud
            })
        
        up_entorno = {
            "entornos": entornos
        }
        
        # Construir objeto registrado_por
        registrado_por = {
            "username": registrado_por_username,
            "email": registrado_por_email
        }
        
        # Parsear coordenadas
        import json
        try:
            coordinates_array = json.loads(coordinates_data)
        except json.JSONDecodeError:
            raise HTTPException(
                status_code=400,
                detail="coordinates_data debe ser un JSON array válido"
            )
        
        coordinates_gps = {
            "type": coordinates_type,
            "coordinates": coordinates_array
        }
        
        # Procesar fotos (obligatorias)
        photos_uploaded = []
        photos_failed = []
        
        logger.info(f"📸 Procesando {len(photosUrl)} fotos para UPID {upid}")
        
        if len(photosUrl) > 0:
            
            # Preparar archivos para subir
            files_content = []
            for photo in photosUrl:
                content = await photo.read()
                files_content.append({
                    'content': content,
                    'filename': photo.filename,
                    'content_type': photo.content_type or 'image/jpeg'
                })
            
            # Subir fotos a S3
            fecha_registro = datetime.now().isoformat()
            photos_uploaded, photos_failed = await subir_fotos_s3(
                files_content=files_content,
                nombre_centro_gestor=nombre_centro_gestor,
                upid=upid,
                estado_360=estado_360,
                fecha_registro=fecha_registro
            )
            
            logger.info(f"✅ Fotos subidas: {len(photos_uploaded)}, Fallidas: {len(photos_failed)}")
        
        # Crear/actualizar registro en Firestore (UPSERT)
        resultado = await crear_registro_captura_360(
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
            registrado_por=registrado_por,
            coordinates_gps=coordinates_gps,
            photos_info=photos_uploaded if photos_uploaded else None
        )
        
        if not resultado["success"]:
            raise HTTPException(
                status_code=500,
                detail=f"Error creando registro: {resultado.get('error', 'Error desconocido')}"
            )
        
        # Preparar respuesta
        response = CapturaEstado360Response(
            success=True,
            message=resultado["message"],
            data=resultado.get("data"),
            document_id=resultado.get("document_id"),
            estado_360=resultado.get("estado_360"),
            photos_uploaded=photos_uploaded if photos_uploaded else None,
            photos_failed=photos_failed if photos_failed else None,
            timestamp=resultado["timestamp"]
        )
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error en endpoint captura-estado-360: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error procesando captura 360: {str(e)}"
        )


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

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
    
    # Campos del entorno (up_entorno)
    nombre_centro_gestor: str = Form(..., description="Nombre del centro gestor"),
    invocar_centro_gestor: bool = Form(..., description="¿Invocar al centro gestor?"),
    solicitud_centro_gestor: str = Form(..., description="Solicitud al centro gestor"),
    
    # Estado y flags
    estado_360: str = Form(..., description="Estado 360: 'Antes', 'Durante' o 'Después'"),
    requiere_alcalde: bool = Form(..., description="¿Requiere participación del alcalde?"),
    entrega_publica: bool = Form(..., description="¿Habrá entrega pública?"),
    tipo_visita: str = Form(..., description="Tipo de visita: 'Verificación' o 'Comunicaciones'"),
    observaciones: Optional[str] = Form(None, description="Observaciones adicionales (opcional)"),
    
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
    - **nombre_centro_gestor**: Centro gestor responsable
    - **invocar_centro_gestor**: Boolean (True/False)
    - **solicitud_centro_gestor**: Solicitud específica
    - **estado_360**: Estado 360 del proyecto ('Antes', 'Durante' o 'Después')
    - **requiere_alcalde**: Boolean (True/False)
    - **entrega_publica**: Boolean (True/False)
    - **tipo_visita**: Tipo de visita ('Verificación' o 'Comunicaciones')
    - **observaciones**: Observaciones adicionales (opcional)
    - **coordinates_type**: Tipo de geometría (Point, LineString, etc.)
    - **coordinates_data**: JSON array con coordenadas
    - **photosUrl**: Archivos de fotos (obligatorio)
    
    ### 📝 Ejemplo de uso con JavaScript/fetch:
    ```javascript
    const formData = new FormData();
    formData.append('upid', 'UNP-1234');
    formData.append('nombre_up', 'Parque Central');
    formData.append('nombre_up_detalle', 'Renovación completa');
    formData.append('descripcion_intervencion', 'Mejoramiento integral');
    formData.append('solicitud_intervencion', 'Solicitud 2024-001');
    formData.append('nombre_centro_gestor', 'Secretaría de Infraestructura');
    formData.append('invocar_centro_gestor', 'true');
    formData.append('solicitud_centro_gestor', 'Requiere revisión técnica');
    formData.append('estado_360', 'Durante');
    formData.append('requiere_alcalde', 'true');
    formData.append('entrega_publica', 'true');
    formData.append('tipo_visita', 'Verificación');
    formData.append('observaciones', 'Proyecto prioritario');
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
    └── Secretaria_de_Infraestructura/
        └── UNP-1234/
            ├── antes/
            │   └── 2024-11-26_10-30-00/
            │       ├── foto1.jpg
            │       └── foto2.jpg
            ├── durante/
            │   └── 2024-11-26_14-30-00/
            │       └── foto3.jpg
            └── despues/
                └── 2024-12-15_16-00-00/
                    └── foto4.jpg
    ```
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
        
        # Construir objeto up_entorno
        up_entorno = {
            "nombre_centro_gestor": nombre_centro_gestor,
            "invocar_centro_gestor": invocar_centro_gestor,
            "solicitud_centro_gestor": solicitud_centro_gestor
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
    "/captura-estado-360/{upid}",
    summary="🔵 GET | 📸 Captura 360 | Obtener Registros por UPID"
)
async def obtener_captura_360_por_upid(upid: str):
    """
    ## 🔵 GET | 📸 Captura 360 | Obtener Registros de un UPID
    
    **Propósito**: Obtener todos los registros de captura 360 para una unidad de proyecto específica.
    
    ### 📊 Información retornada:
    - Lista de todos los registros asociados al UPID
    - Información completa de cada registro (fotos, coordenadas, estados, etc.)
    - Conteo total de registros
    
    ### 📝 Ejemplo de uso:
    ```javascript
    const upid = 'UNP-1234';
    const response = await fetch(`/unidades-proyecto/captura-estado-360/${upid}`);
    const data = await response.json();
    if (data.success) {
        console.log(`Encontrados ${data.count} registros para ${upid}`);
        data.data.forEach(registro => {
            console.log('Estado 360:', registro.estado_360);
            console.log('Fecha:', registro.fecha_registro);
        });
    }
    ```
    """
    if not CAPTURA_360_OPERATIONS_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="Operaciones de captura 360 no disponibles"
        )
    
    try:
        resultado = await obtener_registros_por_upid(upid)
        
        if not resultado["success"]:
            raise HTTPException(
                status_code=500,
                detail=f"Error obteniendo registros: {resultado.get('error', 'Error desconocido')}"
            )
        
        return resultado
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error obteniendo registros por UPID: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error obteniendo registros: {str(e)}"
        )

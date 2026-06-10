# -*- coding: utf-8 -*-
"""
api/routers/interoperabilidad.py — Endpoints de Interoperabilidad con Artefacto de Seguimiento.

Rutas expuestas:
    POST   /reportes_contratos/
    GET    /reportes_contratos/
    GET    /reportes_contratos/centro_gestor/{nombre_centro_gestor}
    GET    /reportes_contratos/referencia/{referencia_contrato}
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import (
    APIRouter,
    Body,
    File,
    Form,
    HTTPException,
    Path,
    Query,
    Request,
    UploadFile,
)
from fastapi.responses import JSONResponse

from api.core.responses import clean_firebase_data, create_utf8_response

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Interoperabilidad con Artefacto de Seguimiento"])

# ---------------------------------------------------------------------------
# Scripts — importacion segura
# ---------------------------------------------------------------------------
try:
    from api.scripts import (
        create_reporte_contrato,
        get_reportes_contratos,
        get_reporte_contrato_by_id,
        get_reportes_by_centro_gestor,
        get_reportes_by_referencia_contrato,
        delete_reporte_contrato,
        REPORTES_CONTRATOS_AVAILABLE,
    )
except Exception:
    REPORTES_CONTRATOS_AVAILABLE = False
    create_reporte_contrato = None
    get_reportes_contratos = None
    get_reporte_contrato_by_id = None
    get_reportes_by_centro_gestor = None
    get_reportes_by_referencia_contrato = None
    delete_reporte_contrato = None

try:
    from database.firebase_config import FIREBASE_AVAILABLE
except ImportError:
    try:
        from ..database.firebase_config import FIREBASE_AVAILABLE
    except ImportError:
        FIREBASE_AVAILABLE = False

SCRIPTS_AVAILABLE = REPORTES_CONTRATOS_AVAILABLE

try:
    from api.models import ReporteContratoRequest, ReporteContratoResponse
except Exception:
    from pydantic import BaseModel

    class ReporteContratoRequest(BaseModel):
        pass

    class ReporteContratoResponse(BaseModel):
        pass


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/reportes_contratos/", tags=["Interoperabilidad con Artefacto de Seguimiento"]
)
async def crear_reporte_contrato(
    # Información básica del reporte
    referencia_contrato: str = Form(
        ..., min_length=1, description="Referencia del contrato"
    ),
    observaciones: str = Form(..., description="Observaciones del reporte"),
    # Centro gestor responsable (opcional - se auto-resuelve desde empréstito si no se envía)
    nombre_centro_gestor: str = Form(
        default="",
        description="Nombre del centro gestor responsable. Si no se envía, se resuelve automáticamente desde las colecciones de empréstito.",
    ),
    # Avances del proyecto (soporte para decimales)
    avance_fisico: float = Form(
        ...,
        ge=0,
        le=100,
        description="Porcentaje de avance físico (0-100, decimales permitidos)",
    ),
    avance_financiero: float = Form(
        ...,
        ge=0,
        le=100,
        description="Porcentaje de avance financiero (0-100, decimales permitidos)",
    ),
    # Información de alertas
    alertas_descripcion: str = Form(..., description="Descripción de la alerta"),
    alertas_es_alerta: bool = Form(..., description="Indica si es una alerta activa"),
    alertas_tipo_alerta: str = Form(
        default="", description="Tipos de alerta separados por coma"
    ),
    # Archivos de evidencia (carga real de archivos)
    archivos_evidencia: List[UploadFile] = File(
        ...,
        description="Archivos de evidencia (PDF, DOC, DOCX, XLS, XLSX, TXT, CSV, JPG, PNG, GIF)",
    ),
):
    """
    ##  Crear Reporte de Contrato con Evidencias y Upload de Archivos

    **Propósito**: Endpoint unificado para crear reportes de seguimiento de contratos
    con carga de archivos y estructura de carpetas organizada.

    ### [OK] IMPORTANTE - AWS S3:
    - **Estado actual**: PRODUCCIÓN - Subida real de archivos funcionando
    - **Configuración**: AWS S3 con buckets separados por tipo
    - **Archivos**: Imágenes y documentos quedan con URL pública lista para frontend

    ### [OK] Características principales:
    - **Carga de archivos**: Upload directo de archivos de evidencia
    - **Estructura automática**: Carpetas organizadas por contrato y fecha
    - **Firebase**: Almacenamiento en colección `reportes_contratos`
    - **Timestamp automático**: Fecha de reporte generada automáticamente
    - **Decimales**: Soporte para avances con decimales (ej: 75.5)

    ###  Parámetros (Form Data):
    - **referencia_contrato**: Referencia del contrato (obligatorio)
    - **observaciones**: Descripción detallada del avance (obligatorio)
    - **avance_fisico**: Porcentaje de avance físico 0-100 con decimales (obligatorio)
    - **avance_financiero**: Porcentaje de avance financiero 0-100 con decimales (obligatorio)
    - **alertas_descripcion**: Descripción de la alerta (obligatorio)
    - **alertas_es_alerta**: Booleano si es alerta activa (obligatorio)
    - **alertas_tipo_alerta**: Tipos de alerta separados por coma (opcional)
    - **archivos_evidencia**: Archivos de evidencia para subir (obligatorio, múltiples archivos)

        ###  Estructura de almacenamiento en S3:
    ```
         reportes_contratos_fotos/{referencia_contrato}/{YYYY-MM-DD}/...
         reportes_contratos_documentos/{referencia_contrato}/{YYYY-MM-DD}/...
    ```

    ###  Validaciones aplicadas:
    - **Archivos**: Tipos permitidos (PDF, DOC, DOCX, XLS, XLSX, JPG, PNG, GIF)
    - **Tamaño**: Máximo 10MB por archivo
    - **Cantidad**: Al menos 1 archivo requerido
    - **Avances**: Rango 0-100 con decimales (ej: 75.5)
    - **Nombres**: Caracteres especiales manejados automáticamente

    ###  Proceso automático:
    1. Validar archivos subidos
    2. Clasificar archivos por extensión (imagen/documento)
    3. Subir a S3 en bucket/prefix correspondiente
    5. Guardar metadata en Firebase con timestamp actual
    6. Retornar URLs y confirmación

    ###  Ejemplo de uso con HTML Form:
    ```html
    <form method="POST" enctype="multipart/form-data">
        <input name="referencia_contrato" value="CONTRATO-2025-001" required>
        <textarea name="observaciones" required>Avance del proyecto...</textarea>
        <input name="avance_fisico" type="number" step="0.1" min="0" max="100" required>
        <input name="avance_financiero" type="number" step="0.1" min="0" max="100" required>
        <textarea name="alertas_descripcion" required>Descripción de alerta...</textarea>
        <input name="alertas_es_alerta" type="checkbox">
        <input name="alertas_tipo_alerta" value="logistica,cronograma">
        <input name="archivos_evidencia" type="file" multiple accept=".pdf,.doc,.docx,.xls,.xlsx,.jpg,.png,.gif" required>
        <button type="submit">Crear Reporte</button>
    </form>
    ```
    """
    # Verificar disponibilidad de servicios
    if not FIREBASE_AVAILABLE or not SCRIPTS_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="Servicios no disponibles: Firebase o scripts requeridos",
        )

    if not REPORTES_CONTRATOS_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="Operaciones de reportes de contratos no disponibles",
        )

    try:
        # Validar archivos subidos
        if not archivos_evidencia:
            raise HTTPException(
                status_code=400, detail="Se requiere al menos un archivo de evidencia"
            )

        # Validar cada archivo subido
        archivos_validados = []
        tipos_permitidos = {
            "application/pdf": ".pdf",
            "application/msword": ".doc",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
            "application/vnd.ms-excel": ".xls",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
            "text/plain": ".txt",
            "text/csv": ".csv",
            "image/jpeg": ".jpg",
            "image/png": ".png",
            "image/gif": ".gif",
        }

        max_size = 10 * 1024 * 1024  # 10MB

        # Extensiones permitidas (para validar por nombre cuando content_type es genérico)
        extensiones_permitidas = {
            ".pdf",
            ".doc",
            ".docx",
            ".xls",
            ".xlsx",
            ".txt",
            ".csv",
            ".jpg",
            ".jpeg",
            ".png",
            ".gif",
        }

        # Mapeo de extensión a content_type correcto (fallback cuando el browser envía octet-stream)
        extension_to_content_type = {
            ".pdf": "application/pdf",
            ".doc": "application/msword",
            ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ".xls": "application/vnd.ms-excel",
            ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ".txt": "text/plain",
            ".csv": "text/csv",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".gif": "image/gif",
        }

        for archivo in archivos_evidencia:
            # Validar tamaño
            if archivo.size and archivo.size > max_size:
                raise HTTPException(
                    status_code=400,
                    detail=f"Archivo {archivo.filename} excede el tamaño máximo de 10MB",
                )

            # Obtener extensión del archivo
            import os as _os

            _, ext = _os.path.splitext(archivo.filename or "")
            ext_lower = ext.lower()

            # Validar tipo de archivo: primero por content_type, luego por extensión
            content_type_final = archivo.content_type
            if archivo.content_type not in tipos_permitidos:
                # Fallback: validar por extensión del nombre del archivo
                if ext_lower in extensiones_permitidas:
                    content_type_final = extension_to_content_type.get(
                        ext_lower, archivo.content_type
                    )
                else:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Tipo de archivo no permitido: {archivo.content_type} (extensión: {ext_lower}) para {archivo.filename}",
                    )

            # Leer contenido del archivo
            contenido = await archivo.read()
            await archivo.seek(0)  # Reset para lectura posterior si es necesario

            archivo_info = {
                "filename": archivo.filename,
                "content_type": content_type_final,
                "size": archivo.size or len(contenido),
                "content": contenido,
            }
            archivos_validados.append(archivo_info)

        # Construir datos optimizados para Firebase
        reporte_dict = {
            "referencia_contrato": referencia_contrato.strip(),
            "nombre_centro_gestor": nombre_centro_gestor.strip(),
            "observaciones": observaciones.strip(),
            "avance_fisico": float(avance_fisico),
            "avance_financiero": float(avance_financiero),
            "alertas": {
                "descripcion": alertas_descripcion.strip(),
                "es_alerta": alertas_es_alerta,
                "tipos": (
                    [
                        tipo.strip()
                        for tipo in alertas_tipo_alerta.split(",")
                        if tipo.strip()
                    ]
                    if alertas_tipo_alerta
                    else []
                ),
            },
            "archivos_evidencia": archivos_validados,
        }

        # Crear el reporte usando la función del script
        result = await create_reporte_contrato(reporte_dict)

        if not result["success"]:
            raise HTTPException(
                status_code=400,
                detail=f"Error creando reporte: {result.get('error', 'Error desconocido')}",
            )

        # Respuesta optimizada sin redundancias
        response_data = {
            "success": True,
            "message": result["message"],
            "doc_id": result["doc_id"],
            "url_carpeta_drive": result.get("url_carpeta_drive"),
            "url_carpeta_s3": result.get("url_carpeta_s3"),
            "diagnostico_s3": result.get("diagnostico_s3"),
            "imagenes_urls": result.get("imagenes_urls", []),
            "documentos_urls": result.get("documentos_urls", []),
            "archivos_count": len(archivos_validados),
        }

        return create_utf8_response(response_data)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error en endpoint crear_reporte_contrato: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Error interno del servidor: {str(e)}"
        )


@router.get(
    "/reportes_contratos/", tags=["Interoperabilidad con Artefacto de Seguimiento"]
)
async def obtener_reportes_contratos(request: Request):
    """
    ##  Obtener Todos los Reportes de Contratos

    **Propósito**: Obtener listado completo de todos los reportes de contratos almacenados en Firebase.
    Muestra todos los registros de la colección `reportes_contratos` con `nombre_centro_gestor` y `bp`
    actualizados desde las colecciones de empréstito cuando sea necesario.

    ###  Integración con colecciones de empréstito:
    - Si un reporte no tiene `nombre_centro_gestor` o está vacío, se busca automáticamente
      en las colecciones `contratos_emprestito`, `ordenes_compra_emprestito` y
      `convenios_transferencias_emprestito` usando `referencia_contrato` como clave
    - Si un reporte no tiene `bp` o está vacío, se hereda automáticamente desde las mismas colecciones

    ###  Ordenamiento:
    Los resultados se ordenan por `fecha_reporte` descendente (más recientes primero).

    ###  Casos de uso:
    - Obtener listado completo para dashboard de seguimiento
    - Vista general de todos los reportes generados con datos completos
    - Administración y auditoría de reportes con información del centro gestor
    """
    # Verificar disponibilidad de servicios
    if (
        not FIREBASE_AVAILABLE
        or not SCRIPTS_AVAILABLE
        or not REPORTES_CONTRATOS_AVAILABLE
    ):
        return {
            "success": False,
            "error": "Servicios no disponibles",
            "data": [],
            "count": 0,
        }

    try:
        # Obtener todos los reportes (sin filtros)
        result = await get_reportes_contratos(None)

        if not result["success"]:
            raise HTTPException(
                status_code=500,
                detail=f"Error obteniendo reportes: {result.get('error', 'Error desconocido')}",
            )

        # Forzar respuesta sin compresión para evitar conflictos
        response = JSONResponse(
            content=result,
            status_code=200,
            headers={
                "Content-Type": "application/json; charset=utf-8",
                "Content-Encoding": "identity",  # Sin compresión
                "Cache-Control": "no-transform",  # Prevenir transformaciones proxy
            },
        )
        return response

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error procesando consulta de reportes: {str(e)}"
        )


@router.get(
    "/reportes_contratos/centro_gestor/{nombre_centro_gestor}",
    tags=["Interoperabilidad con Artefacto de Seguimiento"],
)
async def obtener_reportes_por_centro_gestor(nombre_centro_gestor: str):
    """
    ##  Obtener Reportes por Centro Gestor

    **Propósito**: Obtener reportes filtrados por nombre del centro gestor.
    Los resultados se ordenan por fecha de reporte descendente.

    ###  Parámetros:
    - **nombre_centro_gestor**: Nombre del centro gestor para filtrar reportes

    ###  Ordenamiento:
    Los resultados se ordenan por `fecha_reporte` descendente (más recientes primero).

    ###  Casos de uso:
    - Consultar reportes específicos de un centro gestor
    - Dashboard por centro de responsabilidad
    - Seguimiento por área organizacional
    """
    # Verificar disponibilidad de servicios
    if (
        not FIREBASE_AVAILABLE
        or not SCRIPTS_AVAILABLE
        or not REPORTES_CONTRATOS_AVAILABLE
    ):
        return {
            "success": False,
            "error": "Servicios no disponibles",
            "data": [],
            "count": 0,
        }

    try:
        result = await get_reportes_by_centro_gestor(nombre_centro_gestor)

        if not result["success"]:
            raise HTTPException(
                status_code=500,
                detail=f"Error obteniendo reportes: {result.get('error', 'Error desconocido')}",
            )

        return create_utf8_response(result)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error obteniendo reportes por centro gestor: {str(e)}",
        )


@router.get(
    "/reportes_contratos/referencia/{referencia_contrato}",
    tags=["Interoperabilidad con Artefacto de Seguimiento"],
)
async def obtener_reportes_por_referencia_contrato(referencia_contrato: str):
    """
    ##  Obtener Reportes por Referencia de Contrato

    **Propósito**: Obtener reportes específicos de un contrato usando su referencia.
    Los resultados se ordenan por fecha de reporte descendente.

    ###  Parámetros:
    - **referencia_contrato**: Referencia específica del contrato

    ###  Ordenamiento:
    Los resultados se ordenan por `fecha_reporte` descendente (más recientes primero).

    ###  Casos de uso:
    - Historial completo de reportes de un contrato específico
    - Seguimiento detallado por contrato
    - Auditoría de reportes por referencia
    """
    # Verificar disponibilidad de servicios
    if (
        not FIREBASE_AVAILABLE
        or not SCRIPTS_AVAILABLE
        or not REPORTES_CONTRATOS_AVAILABLE
    ):
        return {
            "success": False,
            "error": "Servicios no disponibles",
            "data": [],
            "count": 0,
        }

    try:
        result = await get_reportes_by_referencia_contrato(referencia_contrato)

        if not result["success"]:
            raise HTTPException(
                status_code=500,
                detail=f"Error obteniendo reportes: {result.get('error', 'Error desconocido')}",
            )

        return create_utf8_response(result)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error obteniendo reportes por referencia: {str(e)}",
        )


@router.delete(
    "/reportes_contratos/{reporte_id}",
    tags=["Interoperabilidad con Artefacto de Seguimiento"],
)
async def eliminar_reporte_contrato(
    reporte_id: str = Path(..., description="ID del reporte a eliminar")
):
    """
    ##  Eliminar Reporte de Contrato

    **Propósito**: Eliminar un reporte de contrato de empréstito por su ID.
    Solo permitido para roles con permiso `write:reportes_contratos` (super_admin / admin_general).
    """
    if (
        not FIREBASE_AVAILABLE
        or not SCRIPTS_AVAILABLE
        or not REPORTES_CONTRATOS_AVAILABLE
        or delete_reporte_contrato is None
    ):
        raise HTTPException(status_code=503, detail="Servicios no disponibles")

    try:
        result = await delete_reporte_contrato(reporte_id)
        if not result["success"]:
            raise HTTPException(
                status_code=404, detail=result.get("error", "Error eliminando reporte")
            )
        return JSONResponse(content=result, status_code=200)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error eliminando reporte: {str(e)}"
        )


# ============================================================================
# ENDPOINTS DE ADMINISTRACIÓN Y CONTROL DE ACCESOS
# ============================================================================

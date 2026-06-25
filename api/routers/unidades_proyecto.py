# -*- coding: utf-8 -*-
"""
api/routers/unidades_proyecto.py — Endpoints de Unidades de Proyecto e Intervenciones.

Dominios:
  - Unidades de proyecto (geometry, attributes, dashboard, filtros)
  - Calidad de datos
  - Intervenciones y exportacion XLSX
  - Avances
  - Solicitudes de cambio (UP + intervenciones)
  - Carga S3 (documentos)
  - Registro avance UP
  - Sincronizacion links SECOP
"""

import asyncio
import json
import logging
import os
import re
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, cast
from urllib.parse import urlparse
from functools import lru_cache

from fastapi import (
    APIRouter,
    Body,
    Depends,
    File,
    Form,
    HTTPException,
    Path,
    Query,
    Request,
    UploadFile,
)
from pydantic import BaseModel, Field
from fastapi.responses import JSONResponse, StreamingResponse

from api.core.cache import (
    get_cache_key,
    get_from_cache,
    set_in_cache,
    clear_cache_by_prefix,
)
from api.core.responses import clean_firebase_data, create_utf8_response
from api.core.security import optional_rate_limit
from auth_system.decorators import require_unidades, enforce_unidades_access
from auth_system.centros_catalog import canonicalize_centro
from auth_system.centro_scoping import scope_records_by_centro

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Unidades de Proyecto"])

# ---------------------------------------------------------------------------
# Rutas a basemaps (corregido: viven en back/basemaps, no en back/api/routers/basemaps)
# ---------------------------------------------------------------------------
_THIS_FILE = os.path.abspath(__file__)
_BACK_DIR = os.path.abspath(os.path.join(os.path.dirname(_THIS_FILE), "..", ".."))
BASEMAPS_DIR = os.path.join(_BACK_DIR, "basemaps")
PROYECTOS_ESTRATEGICOS_DIR = os.path.join(BASEMAPS_DIR, "proyectos_estrategicos")

# ---------------------------------------------------------------------------
# Firebase — importación segura
# ---------------------------------------------------------------------------
try:
    from database.firebase_config import (
        FIREBASE_AVAILABLE,
        get_firestore_client,
        PROJECT_ID,
    )
except Exception:
    FIREBASE_AVAILABLE = False
    PROJECT_ID = os.getenv("FIREBASE_PROJECT_ID", "NOT_CONFIGURED")
    get_firestore_client = lambda: None

# ---------------------------------------------------------------------------
# Scripts — importación segura
# ---------------------------------------------------------------------------
try:
    from api.scripts import (
        get_unidades_proyecto_geometry,
        get_unidades_proyecto_attributes,
        get_filter_options,
        validate_unidades_proyecto_collection,
        generate_unidades_proyecto_quality_report,
        get_unidades_proyecto_quality_summary,
        get_unidades_proyecto_quality_records_paginated,
        get_unidades_proyecto_quality_issues_paginated,
        get_unidades_proyecto_quality_missing_centros_paginated,
        get_unidades_proyecto_quality_history,
        get_unidades_proyecto_quality_centros_paginated,
        EMPRESTITO_OPERATIONS_AVAILABLE,
    )

    SCRIPTS_AVAILABLE = True
except Exception:
    SCRIPTS_AVAILABLE = False
    EMPRESTITO_OPERATIONS_AVAILABLE = False
    get_unidades_proyecto_geometry = None
    get_unidades_proyecto_attributes = None
    get_filter_options = None
    validate_unidades_proyecto_collection = None
    generate_unidades_proyecto_quality_report = None
    get_unidades_proyecto_quality_summary = None
    get_unidades_proyecto_quality_records_paginated = None
    get_unidades_proyecto_quality_issues_paginated = None
    get_unidades_proyecto_quality_missing_centros_paginated = None
    get_unidades_proyecto_quality_history = None
    get_unidades_proyecto_quality_centros_paginated = None

# ---------------------------------------------------------------------------
# S3 helpers — importación segura
# ---------------------------------------------------------------------------
try:
    from api.utils.s3_document_manager import S3DocumentManager, BOTO3_AVAILABLE

    S3_AVAILABLE = True
except Exception:
    S3_AVAILABLE = False
    BOTO3_AVAILABLE = False

# ---------------------------------------------------------------------------
# Shapely (geometría)
# ---------------------------------------------------------------------------
try:
    from shapely.geometry import shape as shapely_shape, Point as ShapelyPoint

    SHAPELY_AVAILABLE = True
except Exception:
    SHAPELY_AVAILABLE = False
    shapely_shape = None
    ShapelyPoint = None

# ---------------------------------------------------------------------------
# Tipos Firebase y helpers de casting
# ---------------------------------------------------------------------------
try:
    from google.api_core.datetime_helpers import DatetimeWithNanoseconds

    FIREBASE_TYPES_AVAILABLE = True
except ImportError:
    FIREBASE_TYPES_AVAILABLE = False
    DatetimeWithNanoseconds = None

FIREBASE_DATETIME_TYPES: Tuple[type, ...] = (
    (DatetimeWithNanoseconds,)
    if FIREBASE_TYPES_AVAILABLE and DatetimeWithNanoseconds is not None
    else ()
)


def _as_firestore_doc_snapshot(value: Any) -> Any:
    """Type-cast helper para documentos de Firestore."""
    return value


def _bool_from_env(name: str, default: bool = True) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return str(raw).strip().lower() in {"1", "true", "yes", "y", "on"}


def _s3_presigned_enabled() -> bool:
    return _bool_from_env("S3_USE_PRESIGNED_URLS", True)


def _s3_presigned_expiration() -> int:
    try:
        return int(os.getenv("S3_PRESIGNED_URL_EXPIRATION_SECONDS", "3600"))
    except Exception:
        return 3600


def _extract_s3_bucket_key_from_url(url: str) -> Tuple[Optional[str], Optional[str]]:
    if not url:
        return None, None
    try:
        parsed = urlparse(url)
        host = (parsed.netloc or "").lower()
        path = (parsed.path or "").lstrip("/")
        if host.endswith("amazonaws.com"):
            if ".s3." in host:
                bucket = host.split(".s3.")[0]
                return bucket or None, path or None
            if host.startswith("s3.") or host == "s3.amazonaws.com":
                if "/" in path:
                    bucket, key = path.split("/", 1)
                    return bucket or None, key or None
        return None, None
    except Exception:
        return None, None


def _collect_avance_s3_objects(doc_data: dict, default_bucket: str) -> set:
    """Extract (bucket, key) pairs from an avance document covering new and legacy schemas."""
    object_pairs: set = set()

    def _register(url: str = "", bucket: str = "", key: str = "") -> None:
        resolved_bucket = (bucket or "").strip()
        resolved_key = (key or "").strip()
        if (not resolved_bucket or not resolved_key) and url:
            parsed_bucket, parsed_key = _extract_s3_bucket_key_from_url(url)
            resolved_bucket = resolved_bucket or (parsed_bucket or "")
            resolved_key = resolved_key or (parsed_key or "")
        if resolved_key:
            object_pairs.add((resolved_bucket or default_bucket, resolved_key))

    for soporte in doc_data.get("soportes") or []:
        if not isinstance(soporte, dict):
            continue
        _register(
            url=str(soporte.get("url_directa") or soporte.get("url") or ""),
            bucket=str(soporte.get("bucket") or ""),
            key=str(soporte.get("s3_key") or ""),
        )
    for url in doc_data.get("imagenes_urls") or []:
        _register(url=str(url))
    for url in doc_data.get("documentos_urls") or []:
        _register(url=str(url))
    for url in doc_data.get("registro_fotografico_urls") or []:
        _register(url=str(url))
    for url in doc_data.get("documentos_soporte_urls") or []:
        _register(url=str(url))

    return object_pairs


def _delete_s3_objects_batch(s3_client, object_pairs: set) -> tuple:
    """Batch-delete S3 objects grouped by bucket. Returns (deleted_list, failed_list)."""
    deleted: List[Dict] = []
    failed: List[Dict] = []
    bucket_to_keys: Dict[str, List[str]] = {}
    for bucket_name, key_name in object_pairs:
        bucket_to_keys.setdefault(bucket_name, []).append(key_name)

    for bucket_name, keys in bucket_to_keys.items():
        for i in range(0, len(keys), 1000):
            chunk = keys[i : i + 1000]
            try:
                response = s3_client.delete_objects(
                    Bucket=bucket_name,
                    Delete={"Objects": [{"Key": k} for k in chunk], "Quiet": False},
                )
                for d in response.get("Deleted", []):
                    deleted.append({"bucket": bucket_name, "key": d.get("Key")})
                for e in response.get("Errors", []):
                    failed.append(
                        {
                            "bucket": bucket_name,
                            "key": e.get("Key"),
                            "code": e.get("Code"),
                            "message": e.get("Message"),
                        }
                    )
            except Exception as exc:
                for k in chunk:
                    failed.append(
                        {
                            "bucket": bucket_name,
                            "key": k,
                            "code": "DeleteException",
                            "message": str(exc),
                        }
                    )

    return deleted, failed


@lru_cache(maxsize=6)
def _get_s3_client_for_presign_cached(credentials_path: str = ""):
    try:
        if not BOTO3_AVAILABLE:
            return None
        manager = S3DocumentManager(credentials_path=credentials_path or None)
        return manager.s3_client
    except Exception:
        return None


def _generate_presigned_s3_url(
    bucket: str, key: str, credentials_path: str = ""
) -> Optional[str]:
    if not _s3_presigned_enabled() or not bucket or not key:
        return None
    try:
        s3_client = _get_s3_client_for_presign_cached(credentials_path or "")
        if s3_client is None:
            return None
        return s3_client.generate_presigned_url(
            "get_object",
            Params={"Bucket": bucket, "Key": key},
            ExpiresIn=_s3_presigned_expiration(),
        )
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get(
    "/unidades-proyecto",
    tags=["Unidades de Proyecto"],
    summary=" Consultar Unidades de Proyecto",
    dependencies=[Depends(require_unidades("read"))],
)
@optional_rate_limit("60/minute")
async def consultar_unidades_proyecto(
    request: Request,
    # Filtros básicos
    upid: Optional[str] = Query(
        None, description="ID específico de unidad (ej: UNP-1000)"
    ),
    nombre_centro_gestor: Optional[str] = Query(
        None, description="Centro gestor responsable"
    ),
    tipo_intervencion: Optional[str] = Query(None, description="Tipo de intervención"),
    estado: Optional[str] = Query(None, description="Estado del proyecto"),
    clase_up: Optional[str] = Query(None, description="Clase de la unidad de proyecto"),
    tipo_equipamiento: Optional[str] = Query(None, description="Tipo de equipamiento"),
    comuna_corregimiento: Optional[str] = Query(
        None, description="Comuna o corregimiento"
    ),
    barrio_vereda: Optional[str] = Query(None, description="Barrio o vereda"),
    frente_activo: Optional[str] = Query(None, description="Frente activo"),
    fuente_financiacion: Optional[str] = Query(
        None, description="Fuente de financiación"
    ),
    proyectos_estrategicos: Optional[str] = Query(
        None, description="Filtrar por proyecto estratégico (busca dentro de la lista)"
    ),
    ano: Optional[int] = Query(None, description="Año de ejecución"),
    # Paginación
    limit: Optional[int] = Query(
        None, ge=1, le=10000, description="Límite de registros"
    ),
    offset: Optional[int] = Query(None, ge=0, description="Offset para paginación"),
):
    """
    ##  Consultar Unidades de Proyecto

    **Propósito**: Acceso directo a la colección `unidades_proyecto` en Firebase.

    ### Respuesta

    Retorna documentos de la colección con todos sus campos:

    ```json
    {
      "success": true,
      "data": [
        {
          "upid": "UNP-1000",
          "nombre_up": "Nombre del proyecto",
          "estado": "En ejecución",
          "tipo_equipamiento": "Vías",
          "clase_up": "Construcción",
          "nombre_centro_gestor": "DAGRD",
          "comuna_corregimiento": "Comuna 1",
          "barrio_vereda": "El Centro",
          "ano": 2024,
          ...
        }
      ],
      "count": 150,
      "collection": "unidades_proyecto"
    }
    ```

    ### Filtros Disponibles

    - `upid` - Filtrar por ID específico
    - `nombre_centro_gestor` - Filtrar por centro gestor
    - `estado` - Filtrar por estado del proyecto
    - `tipo_intervencion` - Filtrar por tipo de intervención
    - `clase_up` - Filtrar por clase de unidad
    - `tipo_equipamiento` - Filtrar por tipo de equipamiento
    - `comuna_corregimiento` - Filtrar por ubicación
    - `barrio_vereda` - Filtrar por barrio
    - `frente_activo` - Filtrar por frente activo
    - `fuente_financiacion` - Filtrar por fuente de financiación
    - `ano` - Filtrar por año

    ### Paginación

    Use `limit` y `offset`:
    ```bash
    # Primera página (50 resultados)
    GET /unidades-proyecto?limit=50&offset=0

    # Segunda página
    GET /unidades-proyecto?limit=50&offset=50
    ```

    ### Ejemplos

    ```bash
    # Todos los proyectos (limitado a 1000)
    GET /unidades-proyecto

    # Proyectos por centro gestor
    GET /unidades-proyecto?nombre_centro_gestor=DAGRD

    # Proyectos en ejecución
    GET /unidades-proyecto?estado=En ejecución

    # Proyectos por tipo de equipamiento
    GET /unidades-proyecto?tipo_equipamiento=Vías&limit=100

    # Unidad específica por ID
    GET /unidades-proyecto?upid=UNP-1000

    ```

    ### Optimizaciones de Rendimiento

    -  **Streaming eficiente** de documentos Firestore
    -  **Procesamiento batch** optimizado
    -  **Compresión automática** de respuestas
    -  **Queries con índices** Firestore
    -  **Retry automático** en caso de errores transitorios

    **Índices Firestore recomendados:**
    ```
    Collection: unidades_proyecto
    Fields: nombre_centro_gestor, estado, ano (Ascending)
    ```
    """
    import time
    import asyncio

    start_time = time.time()

    if not FIREBASE_AVAILABLE:
        raise HTTPException(
            status_code=503, detail="Firebase no disponible - verifica las credenciales"
        )

    # --- Authorization scoping (F2): forzar centro_gestor del usuario si aplica ---
    current_user = getattr(request.state, "current_user", None)
    if current_user is not None:
        nombre_centro_gestor = enforce_unidades_access(
            current_user, "read:unidades", nombre_centro_gestor
        )

    # Canonicalizar el centro ANTES de tocar Firestore: el query es match exacto
    # (==), así que una forma corta/sin tilde no canónica devolvería 0 resultados
    # en silencio. Cubre también el path sin auth (current_user None).
    if nombre_centro_gestor:
        nombre_centro_gestor = (
            canonicalize_centro(nombre_centro_gestor) or nombre_centro_gestor
        )

    try:
        from database.firebase_config import get_firestore_client
        import google.cloud.firestore

        logger.info(f" Consulta unidades_proyecto iniciada")

        # Obtener cliente Firestore
        db = get_firestore_client()
        if db is None:
            raise HTTPException(
                status_code=503, detail="No se pudo conectar a Firestore"
            )

        logger.info(f"[OK] Cliente Firestore obtenido")

        # Construir query optimizada
        logger.info(f" Construyendo query para unidades_proyecto...")
        query = db.collection("unidades_proyecto")

        # Aplicar filtros
        filters_applied = 0
        active_filters = {}

        if upid:
            query = query.where("upid", "==", upid)
            filters_applied += 1
            active_filters["upid"] = upid
        if nombre_centro_gestor:
            query = query.where("nombre_centro_gestor", "==", nombre_centro_gestor)
            filters_applied += 1
            active_filters["nombre_centro_gestor"] = nombre_centro_gestor
        if estado:
            query = query.where("estado", "==", estado)
            filters_applied += 1
            active_filters["estado"] = estado
        if tipo_intervencion:
            query = query.where("tipo_intervencion", "==", tipo_intervencion)
            filters_applied += 1
            active_filters["tipo_intervencion"] = tipo_intervencion
        if clase_up:
            query = query.where("clase_up", "==", clase_up)
            filters_applied += 1
            active_filters["clase_up"] = clase_up
        if tipo_equipamiento:
            query = query.where("tipo_equipamiento", "==", tipo_equipamiento)
            filters_applied += 1
            active_filters["tipo_equipamiento"] = tipo_equipamiento
        if comuna_corregimiento:
            query = query.where("comuna_corregimiento", "==", comuna_corregimiento)
            filters_applied += 1
            active_filters["comuna_corregimiento"] = comuna_corregimiento
        if barrio_vereda:
            query = query.where("barrio_vereda", "==", barrio_vereda)
            filters_applied += 1
            active_filters["barrio_vereda"] = barrio_vereda
        if frente_activo:
            query = query.where("frente_activo", "==", frente_activo)
            filters_applied += 1
            active_filters["frente_activo"] = frente_activo
        if fuente_financiacion:
            query = query.where("fuente_financiacion", "==", fuente_financiacion)
            filters_applied += 1
            active_filters["fuente_financiacion"] = fuente_financiacion
        if proyectos_estrategicos:
            query = query.where(
                "proyectos_estrategicos", "array_contains", proyectos_estrategicos
            )
            filters_applied += 1
            active_filters["proyectos_estrategicos"] = proyectos_estrategicos
        if ano:
            query = query.where("ano", "==", ano)
            filters_applied += 1
            active_filters["ano"] = ano

        logger.info(f" Filtros aplicados: {filters_applied}")

        # Aplicar límite (max 10000, default 100 para velocidad)
        query_limit = min(limit or 100, 10000)
        query = query.limit(query_limit)

        # Aplicar offset si existe
        if offset:
            query = query.offset(offset)

        logger.info(f" Ejecutando query (limit={query_limit}, offset={offset or 0})...")

        # Ejecutar query
        docs = query.stream()

        # Procesar resultados de forma eficiente
        data = []
        doc_count = 0

        for doc in docs:
            doc_count += 1
            doc_dict = doc.to_dict()

            # Optimización: Convertir timestamps solo si existen
            if FIREBASE_TYPES_AVAILABLE:
                for key, value in doc_dict.items():
                    if isinstance(value, FIREBASE_DATETIME_TYPES):
                        doc_dict[key] = value.isoformat()

            # Normalizar proyectos_estrategicos: string legacy → lista
            pe = doc_dict.get("proyectos_estrategicos")
            if isinstance(pe, str):
                doc_dict["proyectos_estrategicos"] = (
                    [v.strip() for v in pe.split(",") if v.strip()] if pe else []
                )
            elif not isinstance(pe, list):
                doc_dict["proyectos_estrategicos"] = []

            data.append(doc_dict)

            # Log progreso cada 50 docs
            if doc_count % 50 == 0:
                logger.info(f" Procesados {doc_count} documentos...")

        logger.info(f"[OK] Query completada: {doc_count} documentos obtenidos")

        # Defense-in-depth: post-filtro normalizado por centro (red de seguridad
        # ante datos residuales no canónicos en Firestore). No-op para usuarios
        # globales (nombre_centro_gestor None).
        if nombre_centro_gestor:
            data = scope_records_by_centro(
                data, nombre_centro_gestor, log_label="unidades_proyecto"
            )

        # Calcular tiempo de procesamiento
        elapsed_time = time.time() - start_time

        # Respuesta optimizada
        response_data = {
            "success": True,
            "data": data,
            "count": len(data),
            "collection": "unidades_proyecto",
            "filters": {
                "applied": filters_applied,
                "active": active_filters,
                "limit": query_limit,
                "offset": offset or 0,
            },
            "performance": {
                "query_time_seconds": round(elapsed_time, 3),
                "docs_per_second": (
                    round(len(data) / elapsed_time, 2) if elapsed_time > 0 else 0
                ),
            },
            "timestamp": datetime.now().isoformat(),
        }

        logger.info(
            f" Respuesta generada en {elapsed_time:.3f}s - {len(data)} documentos"
        )

        return create_utf8_response(response_data)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[ERROR] Error consultando unidades_proyecto: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Error consultando colección: {str(e)}"
        )


# ============================================================================
# ENDPOINT DE DASHBOARD (UNIDADES DE PROYECTO)
# ============================================================================


@router.get(
    "/unidades-proyecto/dashboard",
    tags=["Unidades de Proyecto"],
    summary=" Dashboard Avanzado de Unidades de Proyecto",
    dependencies=[Depends(require_unidades("read"))],
)
@optional_rate_limit("30/minute")
async def get_unidades_proyecto_dashboard_endpoint(
    request: Request,
    estado: Optional[str] = Query(None, description="Filtrar por estado"),
    tipo_intervencion: Optional[str] = Query(
        None, description="Filtrar por tipo de intervención"
    ),
    nombre_centro_gestor: Optional[str] = Query(
        None, description="Filtrar por centro gestor"
    ),
    comuna_corregimiento: Optional[str] = Query(
        None, description="Filtrar por comuna o corregimiento"
    ),
    barrio_vereda: Optional[str] = Query(
        None, description="Filtrar por barrio o vereda"
    ),
):
    """
    ##  Dashboard Avanzado

    Genera métricas, KPIs y distribuciones para dashboards y gráficos.
    Incluye el KPI de **Frentes de Obra Activos** calculado dinámicamente.
    """
    if not FIREBASE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Firebase not available")

    current_user = getattr(request.state, "current_user", None)
    if current_user is not None:
        nombre_centro_gestor = enforce_unidades_access(
            current_user, "read:unidades", nombre_centro_gestor
        )

    # F20: cache por filtros con TTL de 5 min.
    cache_key = get_cache_key(
        "unidades_proyecto_dashboard",
        estado=estado or "",
        tipo_intervencion=tipo_intervencion or "",
        nombre_centro_gestor=nombre_centro_gestor or "__ALL__",
        comuna_corregimiento=comuna_corregimiento or "",
        barrio_vereda=barrio_vereda or "",
    )
    cached_value, hit = get_from_cache(cache_key, max_age_seconds=300)
    if hit:
        return create_utf8_response(cached_value)

    try:
        from api.scripts import get_unidades_proyecto_dashboard

        filters = {}
        if estado:
            filters["estado"] = estado
        if tipo_intervencion:
            filters["tipo_intervencion"] = tipo_intervencion
        if nombre_centro_gestor:
            filters["nombre_centro_gestor"] = nombre_centro_gestor
        if comuna_corregimiento:
            filters["comuna_corregimiento"] = comuna_corregimiento
        if barrio_vereda:
            filters["barrio_vereda"] = barrio_vereda

        result = await get_unidades_proyecto_dashboard(filters or None)
        set_in_cache(cache_key, result)
        return create_utf8_response(result)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[ERROR] Error en dashboard de unidades_proyecto: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Error generando dashboard: {str(e)}"
        )


# ============================================================================
# ENDPOINT DE CALIDAD DE DATOS (UNIDADES DE PROYECTO)
# ============================================================================


@router.get(
    "/unidades-proyecto/calidad-datos",
    tags=["Unidades de Proyecto"],
    summary=" Métricas de Calidad de Datos (ISO/DAMA)",
    dependencies=[Depends(require_unidades("read"))],
)
@optional_rate_limit("30/minute")
async def get_unidades_proyecto_calidad_datos(
    request: Request,
    report_id: Optional[str] = Query(
        None,
        description="ID del snapshot de calidad a consultar. Si no se envía, usa el último",
    ),
    nombre_centro_gestor: Optional[str] = Query(
        None, description="Filtrar clasificación por centro gestor"
    ),
    history_limit: int = Query(
        10, ge=1, le=200, description="Cantidad máxima de snapshots en historial"
    ),
    auto_generate: bool = Query(
        True, description="Si no hay snapshot, genera uno automáticamente"
    ),
):
    """
    ##  Resumen de Calidad de Datos (Snapshot)

    Consulta el resumen de calidad persistido en Firestore para `unidades_proyecto`
    e `intervenciones_unidades_proyecto` usando snapshots controlados.

    Flujo recomendado:
    1. `POST /unidades-proyecto/calidad-datos/analizar` para generar snapshot extensivo.
    2. `GET /unidades-proyecto/calidad-datos` para ver resumen ISO/DAMA.
    3. `GET /unidades-proyecto/calidad-datos/registros` para detalle uno a uno paginado.
    4. `GET /unidades-proyecto/calidad-datos/historial` para auditoría de snapshots.
    """
    if not FIREBASE_AVAILABLE:
        raise HTTPException(
            status_code=503, detail="Firebase no disponible - verifica las credenciales"
        )

    current_user = getattr(request.state, "current_user", None) or {}
    nombre_centro_gestor = enforce_unidades_access(
        current_user, "read:unidades", nombre_centro_gestor
    )

    try:
        result = await get_unidades_proyecto_quality_summary(
            report_id=report_id,
            history_limit=history_limit,
            auto_generate=auto_generate,
            nombre_centro_gestor=nombre_centro_gestor,
        )
        return create_utf8_response(result)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"[ERROR] Error en métricas de calidad de unidades_proyecto: {str(e)}"
        )
        raise HTTPException(
            status_code=500, detail=f"Error generando métricas de calidad: {str(e)}"
        )


@router.post(
    "/unidades-proyecto/calidad-datos/analizar",
    tags=["Unidades de Proyecto"],
    summary=" Ejecutar Análisis Extensivo de Calidad (Snapshot)",
    dependencies=[Depends(require_unidades("write"))],
)
@optional_rate_limit("10/minute")
async def post_unidades_proyecto_calidad_datos_analizar(
    request: Request,
    nombre_centro_gestor: Optional[str] = Query(
        None,
        description="Filtrar análisis por centro gestor antes de persistir snapshot",
    ),
):
    """Genera y persiste un snapshot completo en colecciones quality para consulta controlada."""
    if not FIREBASE_AVAILABLE:
        raise HTTPException(
            status_code=503, detail="Firebase no disponible - verifica las credenciales"
        )

    try:
        result = await generate_unidades_proyecto_quality_report(
            nombre_centro_gestor=nombre_centro_gestor,
            persist=True,
        )
        return create_utf8_response(result)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[ERROR] Error generando snapshot de calidad: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Error generando snapshot de calidad: {str(e)}"
        )


@router.get(
    "/unidades-proyecto/calidad-datos/registros",
    tags=["Unidades de Proyecto"],
    summary=" Diagnóstico por Registro (Paginado)",
    dependencies=[Depends(require_unidades("read"))],
)
@optional_rate_limit("30/minute")
async def get_unidades_proyecto_calidad_datos_registros(
    request: Request,
    report_id: Optional[str] = Query(
        None, description="ID del snapshot de calidad. Si no se envía, usa el último"
    ),
    page_size: int = Query(
        50, ge=1, le=200, description="Cantidad de registros por página"
    ),
    page_token: Optional[int] = Query(
        None, ge=0, description="Cursor numérico devuelto por la página anterior"
    ),
    record_type: Optional[str] = Query(
        None, description="Filtrar por tipo: unidad o intervencion"
    ),
    has_issues: Optional[bool] = Query(None, description="Filtrar si tiene hallazgos"),
    nombre_centro_gestor: Optional[str] = Query(
        None, description="Filtrar por centro gestor"
    ),
):
    """Devuelve evaluación uno a uno por unidad/intervención con enfoque en presupuesto_base, fechas y geometry."""
    if not FIREBASE_AVAILABLE:
        raise HTTPException(
            status_code=503, detail="Firebase no disponible - verifica las credenciales"
        )

    if record_type is not None and record_type.lower() not in {
        "unidad",
        "intervencion",
    }:
        raise HTTPException(
            status_code=400, detail="record_type debe ser 'unidad' o 'intervencion'"
        )

    current_user = getattr(request.state, "current_user", None) or {}
    nombre_centro_gestor = enforce_unidades_access(
        current_user, "read:unidades", nombre_centro_gestor
    )

    try:
        result = await get_unidades_proyecto_quality_records_paginated(
            report_id=report_id,
            page_size=page_size,
            page_token=page_token,
            record_type=record_type,
            has_issues=has_issues,
            nombre_centro_gestor=nombre_centro_gestor,
        )
        return create_utf8_response(result)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[ERROR] Error consultando detalle de calidad paginado: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error consultando detalle de calidad paginado: {str(e)}",
        )


@router.get(
    "/unidades-proyecto/calidad-datos/issues",
    tags=["Unidades de Proyecto"],
    summary=" Issues Individuales de Calidad (Paginado)",
    dependencies=[Depends(require_unidades("read"))],
)
@optional_rate_limit("30/minute")
async def get_unidades_proyecto_calidad_datos_issues(
    request: Request,
    report_id: Optional[str] = Query(
        None, description="ID del snapshot de calidad. Si no se envía, usa el último"
    ),
    page_size: int = Query(
        100, ge=1, le=200, description="Cantidad de issues por página"
    ),
    page_token: Optional[int] = Query(
        None, ge=0, description="Offset devuelto por la página anterior"
    ),
    record_type: Optional[str] = Query(
        None, description="Filtrar por tipo: unidad o intervencion"
    ),
    severity: Optional[str] = Query(
        None, description="Filtrar por severidad: S1, S2, S3, S4"
    ),
    field: Optional[str] = Query(
        None,
        description="Filtrar por campo: presupuesto_base, fecha_inicio, fecha_fin, geometry, upid, etc.",
    ),
    nombre_centro_gestor: Optional[str] = Query(
        None, description="Filtrar por centro gestor"
    ),
):
    """Devuelve cada issue del snapshot como registro individual para trazabilidad y auditoría."""
    if not FIREBASE_AVAILABLE:
        raise HTTPException(
            status_code=503, detail="Firebase no disponible - verifica las credenciales"
        )

    if record_type is not None and record_type.lower() not in {
        "unidad",
        "intervencion",
    }:
        raise HTTPException(
            status_code=400, detail="record_type debe ser 'unidad' o 'intervencion'"
        )

    if severity is not None and severity not in {"S1", "S2", "S3", "S4"}:
        raise HTTPException(status_code=400, detail="severity debe ser S1, S2, S3 o S4")

    current_user = getattr(request.state, "current_user", None) or {}
    nombre_centro_gestor = enforce_unidades_access(
        current_user, "read:unidades", nombre_centro_gestor
    )

    try:
        result = await get_unidades_proyecto_quality_issues_paginated(
            report_id=report_id,
            page_size=page_size,
            page_token=page_token,
            record_type=record_type,
            severity=severity,
            field=field,
            nombre_centro_gestor=nombre_centro_gestor,
        )
        return create_utf8_response(result)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[ERROR] Error consultando issues de calidad: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Error consultando issues de calidad: {str(e)}"
        )


@router.get(
    "/unidades-proyecto/calidad-datos/historial",
    tags=["Unidades de Proyecto"],
    summary=" Historial de Snapshots de Calidad",
    dependencies=[Depends(require_unidades("read"))],
)
@optional_rate_limit("30/minute")
async def get_unidades_proyecto_calidad_datos_historial(
    request: Request,
    limit: int = Query(
        20, ge=1, le=200, description="Cantidad de snapshots a retornar"
    ),
):
    """Retorna historial de análisis de calidad persistidos en colecciones quality."""
    if not FIREBASE_AVAILABLE:
        raise HTTPException(
            status_code=503, detail="Firebase no disponible - verifica las credenciales"
        )

    # F2: este reporte agrega datos de todos los centros gestores.
    _require_global_unidades_access(request)

    try:
        result = await get_unidades_proyecto_quality_history(limit=limit)
        return create_utf8_response(result)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[ERROR] Error consultando historial de calidad: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Error consultando historial de calidad: {str(e)}"
        )


@router.get(
    "/unidades-proyecto/calidad-datos/centros-gestores",
    tags=["Unidades de Proyecto"],
    summary=" Diagnóstico Agrupado por Centro Gestor (Paginado)",
    dependencies=[Depends(require_unidades("read"))],
)
@optional_rate_limit("30/minute")
async def get_unidades_proyecto_calidad_datos_centros_gestores(
    request: Request,
    report_id: Optional[str] = Query(
        None, description="ID del snapshot de calidad. Si no se envía, usa el último"
    ),
    page_size: int = Query(
        25, ge=1, le=200, description="Cantidad de centros gestores por página"
    ),
    page_token: Optional[int] = Query(
        None, ge=0, description="Offset de paginación devuelto por la página anterior"
    ),
    only_with_issues: bool = Query(
        False, description="Si true, retorna solo centros con hallazgos"
    ),
    sort_by: str = Query(
        "issue_rate", description="Orden: issue_rate, with_issues, total_records, name"
    ),
):
    """Retorna métricas agregadas por nombre_centro_gestor con foco en campos críticos y severidades."""
    if not FIREBASE_AVAILABLE:
        raise HTTPException(
            status_code=503, detail="Firebase no disponible - verifica las credenciales"
        )

    # F2: este reporte agrega datos de todos los centros gestores.
    _require_global_unidades_access(request)

    if sort_by not in {"issue_rate", "with_issues", "total_records", "name"}:
        raise HTTPException(
            status_code=400,
            detail="sort_by debe ser: issue_rate, with_issues, total_records, name",
        )

    try:
        result = await get_unidades_proyecto_quality_centros_paginated(
            report_id=report_id,
            page_size=page_size,
            page_token=page_token,
            only_with_issues=only_with_issues,
            sort_by=sort_by,
        )
        return create_utf8_response(result)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"[ERROR] Error consultando calidad agrupada por centro gestor: {str(e)}"
        )
        raise HTTPException(
            status_code=500,
            detail=f"Error consultando calidad agrupada por centro gestor: {str(e)}",
        )


@router.get(
    "/unidades-proyecto/calidad-datos/centros-gestores/faltantes",
    tags=["Unidades de Proyecto"],
    summary=" Candidatos de Corrección: nombre_centro_gestor Faltante",
    dependencies=[Depends(require_unidades("read"))],
)
@optional_rate_limit("30/minute")
async def get_unidades_proyecto_calidad_datos_centros_gestores_faltantes(
    request: Request,
    report_id: Optional[str] = Query(
        None, description="ID del snapshot de calidad. Si no se envía, usa el último"
    ),
    page_size: int = Query(
        100, ge=1, le=200, description="Cantidad de candidatos por página"
    ),
    page_token: Optional[int] = Query(
        None, ge=0, description="Offset devuelto por la página anterior"
    ),
    record_type: Optional[str] = Query(
        None, description="Filtrar por tipo: unidad o intervencion"
    ),
):
    """Lista documentos con `nombre_centro_gestor_source = not_found` para limpieza de datos."""
    if not FIREBASE_AVAILABLE:
        raise HTTPException(
            status_code=503, detail="Firebase no disponible - verifica las credenciales"
        )

    # F2: este reporte agrega datos de todos los centros gestores.
    _require_global_unidades_access(request)

    if record_type is not None and record_type.lower() not in {
        "unidad",
        "intervencion",
    }:
        raise HTTPException(
            status_code=400, detail="record_type debe ser 'unidad' o 'intervencion'"
        )

    try:
        result = await get_unidades_proyecto_quality_missing_centros_paginated(
            report_id=report_id,
            page_size=page_size,
            page_token=page_token,
            record_type=record_type,
        )
        return create_utf8_response(result)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"[ERROR] Error consultando candidatos faltantes de centro gestor: {str(e)}"
        )
        raise HTTPException(
            status_code=500,
            detail=f"Error consultando candidatos faltantes de centro gestor: {str(e)}",
        )


# ============================================================================
# ENDPOINT PARA ARTEFACTO DE CAPTURA #360
# ============================================================================


@router.get(
    "/unidades-proyecto/init-360",
    tags=["Artefacto de Captura #360"],
    summary=" GET |  Listados | Datos Iniciales para Captura #360",
    dependencies=[Depends(require_unidades("read"))],
)
@optional_rate_limit("60/minute")
async def get_unidades_proyecto_init_360(
    request: Request,
    nombre_centro_gestor: Optional[str] = Query(
        None, description="Filtrar por centro gestor"
    ),
    limit: int = Query(
        500, ge=1, le=5000, description="Máximo de registros a devolver"
    ),
    offset: int = Query(0, ge=0, description="Offset de paginación"),
):
    """
    ##  GET |  Listados | Obtener Datos Iniciales para Artefacto de Captura #360

    **Propósito**: Retorna registros de la colección "unidades_proyecto" filtrados según
    criterios específicos para el artefacto de captura #360.

    ### [OK] Campos retornados:
    - upid
    - nombre_up
    - nombre_up_detalle
    - tipo_equipamiento
    - tipo_intervencion
    - estado
    - avance_obra
    - presupuesto_base
    - geometry (datos geoespaciales del registro)
    - direccion

    ###  Exclusiones aplicadas:

    **Por clase_up**:
    - "Interventoría"
    - "Estudios y diseños"
    - "Subsidios"

    **Por tipo_equipamiento**:
    - "Fuentes y monumentos"
    - "Parques y zonas verdes"
    - "Vivienda mejoramiento"
    - "Vivienda nueva"
    - "Adquisición predios"

    **Por tipo_intervencion**:
    - "Estudios y diseños"
    - "Transferencia directa"

    ###  Información incluida en la respuesta:
    - Lista de registros que cumplen los criterios
    - Conteo total de registros retornados
    - Timestamp de la consulta
    - Criterios de exclusión aplicados

    ###  Ejemplo de uso:
    ```javascript
    const response = await fetch('/unidades-proyecto/init-360');
    const data = await response.json();
    if (data.success) {
        console.log('Registros encontrados:', data.count);
        console.log('Datos:', data.data);
    }
    ```
    """
    if not FIREBASE_AVAILABLE or not SCRIPTS_AVAILABLE:
        raise HTTPException(status_code=503, detail="Firebase or scripts not available")

    # F2: aplicar scoping por centro gestor según el rol del usuario.
    current_user = getattr(request.state, "current_user", None)
    if current_user is not None:
        nombre_centro_gestor = enforce_unidades_access(
            current_user, "read:unidades", nombre_centro_gestor
        )

    # F20: cache por (centro_gestor, limit, offset) con TTL de 5 min.
    cache_key = get_cache_key(
        "init_360",
        nombre_centro_gestor=nombre_centro_gestor or "__ALL__",
        limit=limit,
        offset=offset,
    )
    cached_value, hit = get_from_cache(cache_key, max_age_seconds=300)
    if hit:
        return create_utf8_response(cached_value)

    try:
        # Conectar a Firestore
        db = get_firestore_client()
        if db is None:
            raise HTTPException(
                status_code=503, detail="No se pudo conectar a Firestore"
            )

        # Definir criterios de exclusión
        exclusion_clase_up = ["Interventoría", "Estudios y diseños", "Subsidios"]
        exclusion_tipo_equipamiento = [
            "Fuentes y monumentos",
            "Parques y zonas verdes",
            "Vivienda mejoramiento",
            "Vivienda nueva",
            "Adquisición predios",
        ]
        exclusion_tipo_intervencion = ["Estudios y diseños", "Transferencia directa"]

        # Campos a retornar
        campos_requeridos = [
            "upid",
            "nombre_up",
            "nombre_up_detalle",
            "tipo_equipamiento",
            "tipo_intervencion",
            "estado",
            "avance_obra",
            "presupuesto_base",
            "geometry",
            "direccion",
        ]

        # Consultar colección con filtro opcional por centro gestor (F2 + F20).
        query = db.collection("unidades_proyecto")
        if nombre_centro_gestor:
            query = query.where("nombre_centro_gestor", "==", nombre_centro_gestor)
        docs = query.stream()

        # Procesar documentos
        registros_filtrados = []

        for doc in docs:
            doc_data = doc.to_dict()

            # Extraer campos, buscando en el nivel raíz y en properties
            def get_field_value(field_name):
                """Obtener valor del campo desde el documento o properties"""
                if field_name in doc_data:
                    return doc_data[field_name]
                elif "properties" in doc_data and field_name in doc_data["properties"]:
                    return doc_data["properties"][field_name]
                return None

            # Obtener valores para filtrado
            clase_up = get_field_value("clase_up")
            tipo_equipamiento = get_field_value("tipo_equipamiento")
            tipo_intervencion = get_field_value("tipo_intervencion")

            # Aplicar filtros de exclusión
            # Excluir si clase_up está en la lista de exclusión
            if clase_up and clase_up in exclusion_clase_up:
                continue

            # Excluir si tipo_equipamiento está en la lista de exclusión
            if tipo_equipamiento and tipo_equipamiento in exclusion_tipo_equipamiento:
                continue

            # Excluir si tipo_intervencion está en la lista de exclusión
            if tipo_intervencion and tipo_intervencion in exclusion_tipo_intervencion:
                continue

            # Si pasa todos los filtros, extraer campos requeridos
            registro = {}
            for campo in campos_requeridos:
                valor = get_field_value(campo)
                registro[campo] = valor

            registros_filtrados.append(registro)

        # F20: paginación tras el filtrado lógico.
        total_count = len(registros_filtrados)
        paginated = registros_filtrados[offset : offset + limit]

        # Preparar respuesta
        response_data = {
            "success": True,
            "data": paginated,
            "count": len(paginated),
            "total": total_count,
            "pagination": {
                "limit": limit,
                "offset": offset,
                "returned": len(paginated),
                "total": total_count,
                "has_more": offset + len(paginated) < total_count,
            },
            "collection": "unidades_proyecto",
            "timestamp": datetime.now().isoformat(),
            "last_updated": "2025-11-26T00:00:00Z",
            "message": f"Se obtuvieron {len(paginated)} de {total_count} registros que cumplen los criterios del artefacto #360",
            "filters_applied": {
                "excluded_clase_up": exclusion_clase_up,
                "excluded_tipo_equipamiento": exclusion_tipo_equipamiento,
                "excluded_tipo_intervencion": exclusion_tipo_intervencion,
                "nombre_centro_gestor": nombre_centro_gestor,
            },
            "fields_returned": campos_requeridos,
        }

        # F20: cachear resultado (5 min)
        set_in_cache(cache_key, response_data)

        return create_utf8_response(response_data)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error procesando consulta init-360: {str(e)}"
        )


@router.get(
    "/intervenciones",
    tags=["Unidades de Proyecto"],
    summary=" GET | Filtrar Intervenciones",
    dependencies=[Depends(require_unidades("read"))],
)
@optional_rate_limit("60/minute")
async def get_intervenciones_filtradas_endpoint(
    request: Request,
    avance_obra: Optional[float] = Query(None, description="Avance de obra"),
    bpin: Optional[int] = Query(None, description="BPIN"),
    cantidad: Optional[int] = Query(None, description="Cantidad"),
    clase_up: Optional[str] = Query(None, description="Clase UP"),
    estado: Optional[str] = Query(None, description="Estado de la intervención"),
    fecha_fin: Optional[str] = Query(None, description="Fecha fin (string)"),
    fecha_inicio: Optional[str] = Query(None, description="Fecha inicio (string)"),
    fuente_financiacion: Optional[str] = Query(
        None, description="Fuente de financiacion"
    ),
    identificador: Optional[str] = Query(None, description="Identificador"),
    intervencion_id: Optional[str] = Query(None, description="ID de la intervencion"),
    nombre_centro_gestor: Optional[str] = Query(
        None, description="Nombre centro gestor"
    ),
    presupuesto_base: Optional[float] = Query(None, description="Presupuesto base"),
    referencia_contrato: Optional[str] = Query(None, description="Referencia contrato"),
    referencia_proceso: Optional[str] = Query(None, description="Referencia proceso"),
    tipo_intervencion: Optional[str] = Query(None, description="Tipo de intervencion"),
    unidad: Optional[str] = Query(None, description="Unidad"),
    upid: Optional[str] = Query(None, description="UPID"),
    url_proceso: Optional[str] = Query(None, description="URL proceso"),
    limit: int = Query(
        1000,
        ge=1,
        le=10000,
        description="Número máximo de registros a retornar (1-10000, default 1000)",
    ),
    offset: int = Query(
        0, ge=0, description="Número de registros a omitir para paginación"
    ),
):
    """
    ##  GET | Filtrar Intervenciones

    **Propósito**: Filtrar intervenciones desde la colección
    `intervenciones_unidades_proyecto` y retornar solo las unidades que cumplen.

    ### Filtros Disponibles

    - **estado**: "En ejecución", "Terminado", "En alistamiento", etc.
    - **tipo_intervencion**: Tipo de obra o intervención
    - **ano**: Año específico (ej: 2024)
    - **frente_activo**: "Frente activo", "Inactivo", "No aplica"

    ### Estructura de Respuesta

    Respuesta plana con lista de intervenciones.

    ### Ejemplo de Uso

    ```javascript
    // Obtener todas las intervenciones en ejecución de 2024
    const response = await fetch('/intervenciones?estado=En ejecución&ano=2024');
    const data = await response.json();

    console.log(data.count); // Total de intervenciones encontradas
    console.log(data.data.length); // Total de registros
    ```

    ### Casos de Uso

    - Ver todas las intervenciones activas
    - Filtrar por año para análisis temporal
    - Buscar frentes activos específicos
    - Combinar múltiples filtros para búsquedas precisas
    """
    if not FIREBASE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Firebase not available")

    current_user = getattr(request.state, "current_user", None)
    if current_user is not None:
        nombre_centro_gestor = enforce_unidades_access(
            current_user, "read:unidades", nombre_centro_gestor
        )

    try:
        db = get_firestore_client()
        if db is None:
            raise HTTPException(
                status_code=503, detail="No se pudo conectar a Firestore"
            )

        # Pre-cargar tipo_equipamiento desde unidades_proyecto (no existe en intervenciones)
        # Se cachea 5 min para evitar un stream completo en cada consulta de intervenciones.
        _lookup_cache_key = get_cache_key(
            "intervenciones_unidades_lookup",
            nombre_centro_gestor=nombre_centro_gestor or "__ALL__",
        )
        cached_lookup, lookup_hit = get_from_cache(
            _lookup_cache_key, max_age_seconds=300
        )
        if lookup_hit:
            unidades_props_lookup = cached_lookup
        else:
            unidades_props_lookup = {}
            for udoc in (
                db.collection("unidades_proyecto")
                .select(
                    [
                        "upid",
                        "clase_up",
                        "clase_obra",
                        "tipo_equipamiento",
                        "properties",
                    ]
                )
                .stream()
            ):
                ud = udoc.to_dict()
                props = (
                    ud.get("properties", {})
                    if isinstance(ud.get("properties"), dict)
                    else {}
                )
                u_upid = ud.get("upid") or props.get("upid")
                if u_upid:
                    unidades_props_lookup[u_upid] = {
                        "clase_up": ud.get("clase_up")
                        or ud.get("clase_obra")
                        or props.get("clase_up")
                        or props.get("clase_obra"),
                        "tipo_equipamiento": ud.get("tipo_equipamiento")
                        or props.get("tipo_equipamiento"),
                    }
            set_in_cache(_lookup_cache_key, unidades_props_lookup)

        query = db.collection("intervenciones_unidades_proyecto")
        if avance_obra is not None:
            query = query.where("avance_obra", "==", avance_obra)
        if bpin is not None:
            query = query.where("bpin", "==", bpin)
        if cantidad is not None:
            query = query.where("cantidad", "==", cantidad)
        if clase_up:
            query = query.where("clase_up", "==", clase_up)
        if fecha_fin:
            query = query.where("fecha_fin", "==", fecha_fin)
        if fecha_inicio:
            query = query.where("fecha_inicio", "==", fecha_inicio)
        if fuente_financiacion:
            query = query.where("fuente_financiacion", "==", fuente_financiacion)
        if identificador:
            query = query.where("identificador", "==", identificador)
        if intervencion_id:
            query = query.where("intervencion_id", "==", intervencion_id)
        if nombre_centro_gestor:
            query = query.where("nombre_centro_gestor", "==", nombre_centro_gestor)
        if presupuesto_base is not None:
            query = query.where("presupuesto_base", "==", presupuesto_base)
        if referencia_contrato:
            query = query.where("referencia_contrato", "==", referencia_contrato)
        if referencia_proceso:
            query = query.where("referencia_proceso", "==", referencia_proceso)
        if tipo_intervencion:
            query = query.where("tipo_intervencion", "==", tipo_intervencion)
        if unidad:
            query = query.where("unidad", "==", unidad)
        if upid:
            query = query.where("upid", "==", upid)
        if url_proceso:
            query = query.where("url_proceso", "==", url_proceso)

        fields = [
            "avance_obra",
            "bpin",
            "cantidad",
            "clase_up",
            "estado",
            "fecha_fin",
            "fecha_inicio",
            "fuente_financiacion",
            "identificador",
            "intervencion_id",
            "nombre_centro_gestor",
            "presupuesto_base",
            "referencia_contrato",
            "referencia_proceso",
            "tipo_equipamiento",
            "tipo_intervencion",
            "unidad",
            "upid",
            "url_proceso",
        ]

        query = query.select(fields)
        if offset > 0:
            query = query.offset(offset)
        query = query.limit(limit)
        docs = query.stream()

        filters_payload = {
            "avance_obra": avance_obra,
            "bpin": bpin,
            "cantidad": cantidad,
            "clase_up": clase_up,
            "estado": estado,
            "fecha_fin": fecha_fin,
            "fecha_inicio": fecha_inicio,
            "fuente_financiacion": fuente_financiacion,
            "identificador": identificador,
            "intervencion_id": intervencion_id,
            "nombre_centro_gestor": nombre_centro_gestor,
            "presupuesto_base": presupuesto_base,
            "referencia_contrato": referencia_contrato,
            "referencia_proceso": referencia_proceso,
            "tipo_intervencion": tipo_intervencion,
            "unidad": unidad,
            "upid": upid,
            "url_proceso": url_proceso,
        }

        should_convert = FIREBASE_TYPES_AVAILABLE
        datetime_type = FIREBASE_DATETIME_TYPES

        def normalize_value(value):
            if should_convert and isinstance(value, datetime_type):
                return value.isoformat()
            if isinstance(value, dict):
                for inner_key, inner_value in value.items():
                    value[inner_key] = normalize_value(inner_value)
                return value
            if isinstance(value, list):
                return [normalize_value(item) for item in value]
            return value

        def coerce_float_value(value):
            if value is None or value == "":
                return None
            try:
                if isinstance(value, str):
                    cleaned = value.strip().replace("%", "").replace(" ", "")
                    if "," in cleaned and cleaned.count(",") == 1:
                        comma_pos = cleaned.find(",")
                        if len(cleaned) - comma_pos <= 3:
                            cleaned = cleaned.replace(",", ".")
                        else:
                            cleaned = cleaned.replace(",", "")
                    else:
                        cleaned = cleaned.replace(",", "")
                    return float(cleaned) if cleaned else None
                return float(value)
            except (ValueError, TypeError):
                return None

        data = []
        for doc in docs:
            doc_data = doc.to_dict()
            if should_convert:
                doc_data = normalize_value(doc_data)

            record = {field: doc_data.get(field) for field in fields}
            record["intervencion_id"] = record.get("intervencion_id") or doc.id
            record["avance_obra"] = coerce_float_value(record.get("avance_obra"))

            # Calcular estado dinámicamente desde avance_obra
            from api.scripts.unidades_proyecto import (
                _calcular_estado,
                _clasificar_frente_activo,
            )

            record["estado"] = _calcular_estado(record)

            # Calcular frente_activo dinámicamente usando datos de la unidad padre
            record_upid = record.get("upid")
            parent_props = unidades_props_lookup.get(record_upid, {})
            unidad_props = {
                "clase_up": parent_props.get("clase_up") or record.get("clase_up"),
                "tipo_equipamiento": parent_props.get("tipo_equipamiento")
                or record.get("tipo_equipamiento"),
            }
            record["frente_activo"] = _clasificar_frente_activo(record, unidad_props)

            # Filtro client-side por estado (calculado dinámicamente)
            if estado and record["estado"] != estado:
                continue

            data.append(record)

        return create_utf8_response(
            {
                "success": True,
                "data": data,
                "count": len(data),
                "filters": filters_payload,
                "pagination": {
                    "limit": limit,
                    "offset": offset,
                    "returned": len(data),
                },
            }
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error filtrando intervenciones: {str(e)}"
        )


@router.get(
    "/unidades-proyecto/intervenciones/export-xlsx",
    tags=["Unidades de Proyecto"],
    summary=" Exportar Intervenciones a XLSX",
    dependencies=[Depends(require_unidades("read"))],
)
async def exportar_intervenciones_xlsx(
    request: Request,
    avance_obra: Optional[float] = Query(None, description="Avance de obra"),
    bpin: Optional[int] = Query(None, description="BPIN"),
    cantidad: Optional[int] = Query(None, description="Cantidad"),
    clase_up: Optional[str] = Query(None, description="Clase UP"),
    estado: Optional[str] = Query(None, description="Estado de la intervención"),
    fecha_fin: Optional[str] = Query(None, description="Fecha fin (string)"),
    fecha_inicio: Optional[str] = Query(None, description="Fecha inicio (string)"),
    fuente_financiacion: Optional[str] = Query(
        None, description="Fuente de financiacion"
    ),
    identificador: Optional[str] = Query(None, description="Identificador"),
    intervencion_id: Optional[str] = Query(None, description="ID de la intervencion"),
    nombre_centro_gestor: Optional[str] = Query(
        None, description="Nombre centro gestor"
    ),
    presupuesto_base: Optional[float] = Query(None, description="Presupuesto base"),
    referencia_contrato: Optional[str] = Query(None, description="Referencia contrato"),
    referencia_proceso: Optional[str] = Query(None, description="Referencia proceso"),
    tipo_intervencion: Optional[str] = Query(None, description="Tipo de intervencion"),
    unidad: Optional[str] = Query(None, description="Unidad"),
    upid: Optional[str] = Query(None, description="UPID"),
    url_proceso: Optional[str] = Query(None, description="URL proceso"),
):
    """
    Exporta `intervenciones_unidades_proyecto` a XLSX excluyendo campos definidos
    y agregando `comuna_corregimiento` y `barrio_vereda` desde `unidades_proyecto` por `upid`.
    """
    if not FIREBASE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Firebase not available")

    current_user = getattr(request.state, "current_user", None)
    if current_user is not None:
        nombre_centro_gestor = enforce_unidades_access(
            current_user, "read:unidades", nombre_centro_gestor
        )

    excluded_fields = {
        "referencia_proceso",
        "referencia_contrato",
        "url_proceso",
        "identificador",
        "cantidad",
        "unidad",
        "bpin",
        "avance_obra",
    }

    try:
        from io import BytesIO
        import pandas as pd

        db = get_firestore_client()
        if db is None:
            raise HTTPException(
                status_code=503, detail="No se pudo conectar a Firestore"
            )

        upid_location_map = {}
        for unidad_doc in await asyncio.to_thread(
            lambda: list(db.collection("unidades_proyecto").stream())
        ):
            unidad_data = unidad_doc.to_dict() or {}
            props = (
                unidad_data.get("properties", {})
                if isinstance(unidad_data.get("properties"), dict)
                else {}
            )

            upid_value = unidad_data.get("upid") or props.get("upid")
            if not upid_value:
                continue

            comuna = unidad_data.get("comuna_corregimiento")
            if comuna is None:
                comuna = props.get("comuna_corregimiento")

            barrio = unidad_data.get("barrio_vereda")
            if barrio is None:
                barrio = props.get("barrio_vereda")

            upid_location_map[str(upid_value)] = {
                "comuna_corregimiento": comuna,
                "barrio_vereda": barrio,
            }

        def normalize_for_excel(value):
            if isinstance(value, FIREBASE_DATETIME_TYPES):
                return value.isoformat()
            if isinstance(value, datetime):
                return value.isoformat()
            if isinstance(value, dict):
                return {k: normalize_for_excel(v) for k, v in value.items()}
            if isinstance(value, list):
                return [normalize_for_excel(v) for v in value]
            return value

        interv_query = db.collection("intervenciones_unidades_proyecto")
        if avance_obra is not None:
            interv_query = interv_query.where("avance_obra", "==", avance_obra)
        if bpin is not None:
            interv_query = interv_query.where("bpin", "==", bpin)
        if cantidad is not None:
            interv_query = interv_query.where("cantidad", "==", cantidad)
        if clase_up:
            interv_query = interv_query.where("clase_up", "==", clase_up)
        if estado:
            interv_query = interv_query.where("estado", "==", estado)
        if fecha_fin:
            interv_query = interv_query.where("fecha_fin", "==", fecha_fin)
        if fecha_inicio:
            interv_query = interv_query.where("fecha_inicio", "==", fecha_inicio)
        if fuente_financiacion:
            interv_query = interv_query.where(
                "fuente_financiacion", "==", fuente_financiacion
            )
        if identificador:
            interv_query = interv_query.where("identificador", "==", identificador)
        if intervencion_id:
            interv_query = interv_query.where("intervencion_id", "==", intervencion_id)
        if nombre_centro_gestor:
            interv_query = interv_query.where(
                "nombre_centro_gestor", "==", nombre_centro_gestor
            )
        if presupuesto_base is not None:
            interv_query = interv_query.where(
                "presupuesto_base", "==", presupuesto_base
            )
        if referencia_contrato:
            interv_query = interv_query.where(
                "referencia_contrato", "==", referencia_contrato
            )
        if referencia_proceso:
            interv_query = interv_query.where(
                "referencia_proceso", "==", referencia_proceso
            )
        if tipo_intervencion:
            interv_query = interv_query.where(
                "tipo_intervencion", "==", tipo_intervencion
            )
        if unidad:
            interv_query = interv_query.where("unidad", "==", unidad)
        if upid:
            interv_query = interv_query.where("upid", "==", upid)
        if url_proceso:
            interv_query = interv_query.where("url_proceso", "==", url_proceso)

        export_rows = []
        for interv_doc in await asyncio.to_thread(lambda: list(interv_query.stream())):
            interv_data = interv_doc.to_dict() or {}
            normalized_data = {
                k: normalize_for_excel(v) for k, v in interv_data.items()
            }

            row = {
                key: value
                for key, value in normalized_data.items()
                if key not in excluded_fields
            }

            upid_value = str(interv_data.get("upid") or "")
            location = upid_location_map.get(upid_value, {})
            row["comuna_corregimiento"] = location.get("comuna_corregimiento")
            row["barrio_vereda"] = location.get("barrio_vereda")

            export_rows.append(row)

        def _rows_to_xlsx(rows):
            df = pd.DataFrame(rows)
            buf = BytesIO()
            with pd.ExcelWriter(buf, engine="openpyxl") as writer:
                df.to_excel(writer, index=False, sheet_name="intervenciones")
            buf.seek(0)
            return buf

        output = await asyncio.to_thread(_rows_to_xlsx, export_rows)

        filename = f"intervenciones_unidades_proyecto_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        return StreamingResponse(
            output,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error exportando XLSX de intervenciones: {str(e)}"
        )


@router.get(
    "/avances_unidades_proyecto",
    tags=["Unidades de Proyecto"],
    dependencies=[Depends(require_unidades("read"))],
    summary=" GET | Leer avances de Unidades de Proyecto",
    response_description="Lista de avances con enlaces normalizados para imágenes y documentos",
    responses={
        200: {
            "description": "Consulta exitosa de avances con estructura lista para frontend",
            "content": {
                "application/json": {
                    "example": {
                        "data": [
                            {
                                "id": "f4f0f2dd-10ef-42df-9b4f-b9ad2554d110",
                                "intervencion_id": "INT-001",
                                "avance_obra": 67.5,
                                "observaciones": "Avance de estructura y acabados.",
                                "registrado_por": "usuario@empresa.com",
                                "soportes": [
                                    {
                                        "indice": 1,
                                        "tipo": "imagen",
                                        "nombre_original": "foto_frente.jpg",
                                        "extension": ".jpg",
                                        "content_type": "image/jpeg",
                                        "s3_key": "unidades_proyecto_photos/registro_avance/INT-001/2026-03-07/INT-001_20260307_143000_001.jpg",
                                        "url": "https://unidades-proyecto-documents.s3.amazonaws.com/unidades_proyecto_photos/registro_avance/INT-001/2026-03-07/INT-001_20260307_143000_001.jpg",
                                        "uploaded_at": "2026-03-07T14:30:00-05:00",
                                    },
                                    {
                                        "indice": 2,
                                        "tipo": "documento",
                                        "nombre_original": "informe_tecnico.pdf",
                                        "extension": ".pdf",
                                        "content_type": "application/pdf",
                                        "s3_key": "unidades_proyecto_documentos/registro_avance/INT-001/2026-03-07/INT-001_20260307_143000_001_informe_tecnico.pdf",
                                        "url": "https://unidades-proyecto-documents.s3.amazonaws.com/unidades_proyecto_documentos/registro_avance/INT-001/2026-03-07/INT-001_20260307_143000_001_informe_tecnico.pdf",
                                        "uploaded_at": "2026-03-07T14:30:00-05:00",
                                    },
                                ],
                                "imagenes_urls": [
                                    "https://unidades-proyecto-documents.s3.amazonaws.com/unidades_proyecto_photos/registro_avance/INT-001/2026-03-07/INT-001_20260307_143000_001.jpg"
                                ],
                                "documentos_urls": [
                                    "https://unidades-proyecto-documents.s3.amazonaws.com/unidades_proyecto_documentos/registro_avance/INT-001/2026-03-07/INT-001_20260307_143000_001_informe_tecnico.pdf"
                                ],
                                "links": {
                                    "imagenes": [
                                        "https://unidades-proyecto-documents.s3.amazonaws.com/unidades_proyecto_photos/registro_avance/INT-001/2026-03-07/INT-001_20260307_143000_001.jpg"
                                    ],
                                    "documentos": [
                                        "https://unidades-proyecto-documents.s3.amazonaws.com/unidades_proyecto_documentos/registro_avance/INT-001/2026-03-07/INT-001_20260307_143000_001_informe_tecnico.pdf"
                                    ],
                                    "all_soportes": [
                                        {
                                            "indice": 1,
                                            "tipo": "imagen",
                                            "url": "https://unidades-proyecto-documents.s3.amazonaws.com/unidades_proyecto_photos/registro_avance/INT-001/2026-03-07/INT-001_20260307_143000_001.jpg",
                                        },
                                        {
                                            "indice": 2,
                                            "tipo": "documento",
                                            "url": "https://unidades-proyecto-documents.s3.amazonaws.com/unidades_proyecto_documentos/registro_avance/INT-001/2026-03-07/INT-001_20260307_143000_001_informe_tecnico.pdf",
                                        },
                                    ],
                                    "visores": {
                                        "imagenes": [
                                            "https://unidades-proyecto-documents.s3.amazonaws.com/unidades_proyecto_photos/registro_avance/INT-001/2026-03-07/INT-001_20260307_143000_001.jpg"
                                        ],
                                        "documentos_inline": [
                                            "https://unidades-proyecto-documents.s3.amazonaws.com/unidades_proyecto_documentos/registro_avance/INT-001/2026-03-07/INT-001_20260307_143000_001_informe_tecnico.pdf"
                                        ],
                                        "documentos_download": [],
                                    },
                                },
                                "registro_fotografico_urls": [
                                    "https://unidades-proyecto-documents.s3.amazonaws.com/unidades_proyecto_photos/registro_avance/INT-001/2026-03-07/INT-001_20260307_143000_001.jpg"
                                ],
                                "documentos_soporte_urls": [
                                    "https://unidades-proyecto-documents.s3.amazonaws.com/unidades_proyecto_documentos/registro_avance/INT-001/2026-03-07/INT-001_20260307_143000_001_informe_tecnico.pdf"
                                ],
                                "total_imagenes": 1,
                                "total_documentos": 1,
                                "total_soportes": 2,
                                "created_at": "2026-03-07T14:30:00-05:00",
                                "updated_at": "2026-03-07T14:30:00-05:00",
                            }
                        ],
                        "count": 1,
                        "filters": {"doc_id": None, "intervencion_id": "INT-001"},
                    }
                }
            },
        },
        404: {"description": "No existe avance con el doc_id solicitado"},
        503: {"description": "Firestore/Firebase no disponible"},
    },
)
@optional_rate_limit("60/minute")
async def get_avances_unidades_proyecto(
    request: Request,
    intervencion_id: Optional[str] = Query(
        None, description="Filtrar por intervencion_id"
    ),
    doc_id: Optional[str] = Query(
        None, description="ID exacto del documento en Firestore"
    ),
):
    """
    Lee avances de unidades de proyecto y normaliza enlaces para frontend.

    Compatibilidad de salida:
    - Nuevo esquema: `soportes`, `imagenes_urls`, `documentos_urls`, `links`.
    - Esquema legado: `registro_fotografico_urls`, `documentos_soporte_urls`.

    La respuesta siempre incluye ambos formatos para evitar rompimientos en clientes.
    """
    if not FIREBASE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Firebase not available")

    # F2: aplicar scoping por centro gestor. Si el usuario tiene acceso
    # restringido, se devuelve sólo los avances cuyo doc tenga el centro forzado.
    current_user = getattr(request.state, "current_user", None)
    forced_centro = None
    if current_user is not None:
        forced_centro = enforce_unidades_access(current_user, "read:unidades", None)

    try:
        db = get_firestore_client()
        if db is None:
            raise HTTPException(
                status_code=503, detail="No se pudo conectar a Firestore"
            )

        collection_ref = db.collection("avances_unidades_proyecto")
        presign_credentials_path = os.getenv(
            "AWS_CREDENTIALS_FILE_UNIDADES_PROYECTO", "credentials/aws_credentials.json"
        )
        presign_cache: Dict[Tuple[str, str], str] = {}

        should_convert = FIREBASE_TYPES_AVAILABLE
        datetime_type = FIREBASE_DATETIME_TYPES

        def normalize_value(value):
            if should_convert and isinstance(value, datetime_type):
                return value.isoformat()
            if isinstance(value, dict):
                for inner_key, inner_value in value.items():
                    value[inner_key] = normalize_value(inner_value)
                return value
            if isinstance(value, list):
                return [normalize_value(item) for item in value]
            return value

        def _content_type_from_url(url: str) -> str:
            url_lower = (url or "").lower()
            if url_lower.endswith(
                (
                    ".jpg",
                    ".jpeg",
                    ".png",
                    ".bmp",
                    ".gif",
                    ".webp",
                    ".tif",
                    ".tiff",
                    ".heic",
                    ".heif",
                    ".ico",
                )
            ):
                return "image/jpeg"
            if url_lower.endswith(".pdf"):
                return "application/pdf"
            if url_lower.endswith(".xlsx"):
                return (
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            if url_lower.endswith(".xls"):
                return "application/vnd.ms-excel"
            if url_lower.endswith(".docx"):
                return "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            if url_lower.endswith(".doc"):
                return "application/msword"
            if url_lower.endswith(".csv"):
                return "text/csv"
            if url_lower.endswith(".txt"):
                return "text/plain"
            return "application/octet-stream"

        def _get_presigned_or_direct(
            url: str = "", bucket: str = "", key: str = ""
        ) -> str:
            resolved_bucket = bucket
            resolved_key = key
            if (not resolved_bucket or not resolved_key) and url:
                parsed_bucket, parsed_key = _extract_s3_bucket_key_from_url(url)
                resolved_bucket = resolved_bucket or (parsed_bucket or "")
                resolved_key = resolved_key or (parsed_key or "")

            if not resolved_bucket or not resolved_key:
                return url

            cache_key = (resolved_bucket, resolved_key)
            if cache_key in presign_cache:
                return presign_cache[cache_key]

            signed = _generate_presigned_s3_url(
                resolved_bucket, resolved_key, presign_credentials_path
            )
            final_url = signed or url
            if final_url:
                presign_cache[cache_key] = final_url
            return final_url

        def _normalize_avance_links(
            doc_data: Dict[str, Any], doc_firestore_id: str
        ) -> Dict[str, Any]:
            """Normaliza links para frontend desde esquema nuevo y legado."""
            soportes = doc_data.get("soportes") or []
            imagenes_urls = list(doc_data.get("imagenes_urls") or [])
            documentos_urls = list(doc_data.get("documentos_urls") or [])

            # Compatibilidad con payload legado
            legacy_img_urls = list(doc_data.get("registro_fotografico_urls") or [])
            legacy_doc_urls = list(doc_data.get("documentos_soporte_urls") or [])

            if not imagenes_urls and legacy_img_urls:
                imagenes_urls = legacy_img_urls
            if not documentos_urls and legacy_doc_urls:
                documentos_urls = legacy_doc_urls

            # Si no existen listas separadas, reconstruir desde soportes
            if (not imagenes_urls and not documentos_urls) and soportes:
                for soporte in soportes:
                    if not isinstance(soporte, dict):
                        continue
                    soporte_tipo = str(soporte.get("tipo") or "").lower()
                    soporte_url = soporte.get("url")
                    if not soporte_url:
                        continue
                    if soporte_tipo == "imagen":
                        imagenes_urls.append(soporte_url)
                    elif soporte_tipo == "documento":
                        documentos_urls.append(soporte_url)

            # Si no existe soportes, reconstruirlo con enlaces disponibles
            if not soportes:
                soportes = []
                for idx, url in enumerate(imagenes_urls):
                    soportes.append(
                        {
                            "indice": idx + 1,
                            "tipo": "imagen",
                            "url": url,
                            "content_type": _content_type_from_url(url),
                        }
                    )
                for idx, url in enumerate(documentos_urls):
                    soportes.append(
                        {
                            "indice": len(soportes) + 1,
                            "tipo": "documento",
                            "url": url,
                            "content_type": _content_type_from_url(url),
                        }
                    )

            # Dedupe preservando orden
            def _dedupe(values: List[str]) -> List[str]:
                seen = set()
                out = []
                for value in values:
                    if not value or value in seen:
                        continue
                    seen.add(value)
                    out.append(value)
                return out

            imagenes_urls = _dedupe(imagenes_urls)
            documentos_urls = _dedupe(documentos_urls)

            # Firmar URLs de soportes (nuevo esquema) y retener la directa para diagnóstico
            signed_soportes = []
            for idx, soporte in enumerate(soportes):
                if not isinstance(soporte, dict):
                    continue
                soporte_copy = dict(soporte)
                direct_url = str(
                    soporte_copy.get("url_directa") or soporte_copy.get("url") or ""
                )
                bucket = str(soporte_copy.get("bucket") or "")
                s3_key = str(soporte_copy.get("s3_key") or "")
                signed_url = _get_presigned_or_direct(direct_url, bucket, s3_key)
                if direct_url and "url_directa" not in soporte_copy:
                    soporte_copy["url_directa"] = direct_url
                soporte_copy["url"] = signed_url or direct_url
                soporte_copy["url_presigned"] = (
                    signed_url if signed_url and signed_url != direct_url else None
                )
                soporte_copy["indice"] = soporte_copy.get("indice", idx + 1)
                signed_soportes.append(soporte_copy)

            if signed_soportes:
                soportes = signed_soportes

            # Firmar listas planas (legacy y nuevo)
            imagenes_urls = [_get_presigned_or_direct(url) for url in imagenes_urls]
            documentos_urls = [_get_presigned_or_direct(url) for url in documentos_urls]

            doc_data["soportes"] = soportes
            doc_data["imagenes_urls"] = imagenes_urls
            doc_data["documentos_urls"] = documentos_urls

            # Compatibilidad hacia clientes antiguos
            doc_data["registro_fotografico_urls"] = imagenes_urls
            doc_data["documentos_soporte_urls"] = documentos_urls

            # Estructura explícita para frontend
            doc_data["links"] = {
                "imagenes": imagenes_urls,
                "documentos": documentos_urls,
                "all_soportes": soportes,
                "visores": {
                    "imagenes": imagenes_urls,
                    "documentos_inline": [
                        url
                        for url in documentos_urls
                        if str(url).lower().endswith(".pdf")
                    ],
                    "documentos_download": [
                        url
                        for url in documentos_urls
                        if not str(url).lower().endswith(".pdf")
                    ],
                },
            }

            doc_data["total_imagenes"] = len(imagenes_urls)
            doc_data["total_documentos"] = len(documentos_urls)
            doc_data["total_soportes"] = len(soportes)
            doc_data["id"] = doc_firestore_id
            return doc_data

        if doc_id:
            doc = _as_firestore_doc_snapshot(collection_ref.document(doc_id).get())
            if not doc.exists:
                raise HTTPException(
                    status_code=404, detail=f"No existe avance con id: {doc_id}"
                )

            doc_data = doc.to_dict() or {}
            if should_convert:
                doc_data = normalize_value(doc_data)
            doc_data = _normalize_avance_links(doc_data, doc.id)

            if (
                forced_centro is not None
                and str(doc_data.get("nombre_centro_gestor") or "") != forced_centro
            ):
                raise HTTPException(
                    status_code=403,
                    detail="No tiene acceso a avances de este centro gestor",
                )

            return create_utf8_response(
                {
                    "data": [doc_data],
                    "count": 1,
                    "filters": {"doc_id": doc_id, "intervencion_id": intervencion_id},
                }
            )

        query = collection_ref
        if intervencion_id:
            query = query.where("intervencion_id", "==", intervencion_id)
        docs = query.stream()

        data = []
        for doc in docs:
            doc_data = doc.to_dict() or {}
            if should_convert:
                doc_data = normalize_value(doc_data)
            doc_data = _normalize_avance_links(doc_data, doc.id)
            if (
                forced_centro is not None
                and str(doc_data.get("nombre_centro_gestor") or "") != forced_centro
            ):
                continue
            data.append(doc_data)

        return create_utf8_response(
            {
                "data": data,
                "count": len(data),
                "filters": {"doc_id": doc_id, "intervencion_id": intervencion_id},
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error leyendo avances de unidades de proyecto: {str(e)}",
        )


@router.delete(
    "/avances_unidades_proyecto",
    tags=["Unidades de Proyecto"],
    summary=" DELETE | Eliminar avance UP y soportes S3",
    dependencies=[Depends(require_unidades("delete"))],
)
@optional_rate_limit("30/minute")
async def eliminar_avance_unidades_proyecto(
    request: Request,
    id: str = Query(
        ..., min_length=1, description="ID del avance en Firestore (obligatorio)"
    ),
):
    """
    Elimina un avance de `avances_unidades_proyecto` y todos sus archivos asociados en S3.

    - Requiere `id` del documento.
    - Soporta esquema nuevo (`soportes[].bucket/s3_key`) y legado (URLs directas).
    - Solo elimina el documento en Firestore si la eliminación en S3 fue exitosa.
    """
    if not FIREBASE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Firebase not available")

    current_user = getattr(request.state, "current_user", None)
    if current_user is None:
        raise HTTPException(status_code=401, detail="No autenticado")

    try:
        db = get_firestore_client()
        if db is None:
            raise HTTPException(
                status_code=503, detail="No se pudo conectar a Firestore"
            )

        doc_ref = db.collection("avances_unidades_proyecto").document(id)
        doc = _as_firestore_doc_snapshot(doc_ref.get())
        if not doc.exists:
            raise HTTPException(
                status_code=404, detail=f"No existe avance con id: {id}"
            )

        doc_data = doc.to_dict() or {}

        # F2: validar centro_gestor del avance
        enforce_unidades_access(
            current_user,
            "delete:unidades",
            doc_data.get("nombre_centro_gestor"),
        )

        # Inicializar S3 para borrado
        try:
            from api.utils.s3_document_manager import S3DocumentManager, BOTO3_AVAILABLE

            if not BOTO3_AVAILABLE:
                raise HTTPException(
                    status_code=500, detail="boto3 no disponible para eliminación en S3"
                )

            credentials_path = os.getenv(
                "AWS_CREDENTIALS_FILE_UNIDADES_PROYECTO",
                "credentials/aws_credentials.json",
            )
            default_bucket = os.getenv(
                "S3_BUCKET_UNIDADES_PROYECTO", "unidades-proyecto-documents"
            )

            s3_manager = S3DocumentManager(credentials_path=credentials_path)
            s3_client = s3_manager.s3_client
        except HTTPException:
            raise
        except Exception as s3_init_error:
            raise HTTPException(
                status_code=500,
                detail=f"No se pudo inicializar cliente S3 para eliminar avance: {str(s3_init_error)}",
            )

        # Recolectar objetos S3 asociados al avance
        object_pairs = set()  # (bucket, key)

        def _register_object(url: str = "", bucket: str = "", key: str = ""):
            resolved_bucket = (bucket or "").strip()
            resolved_key = (key or "").strip()
            if (not resolved_bucket or not resolved_key) and url:
                parsed_bucket, parsed_key = _extract_s3_bucket_key_from_url(url)
                resolved_bucket = resolved_bucket or (parsed_bucket or "")
                resolved_key = resolved_key or (parsed_key or "")
            if resolved_key:
                object_pairs.add((resolved_bucket or default_bucket, resolved_key))

        # Esquema nuevo: soportes con bucket/s3_key/url
        for soporte in doc_data.get("soportes") or []:
            if not isinstance(soporte, dict):
                continue
            _register_object(
                url=str(soporte.get("url_directa") or soporte.get("url") or ""),
                bucket=str(soporte.get("bucket") or ""),
                key=str(soporte.get("s3_key") or ""),
            )

        # Campos planos actuales
        for url in doc_data.get("imagenes_urls") or []:
            _register_object(url=str(url))
        for url in doc_data.get("documentos_urls") or []:
            _register_object(url=str(url))

        # Compatibilidad legacy
        for url in doc_data.get("registro_fotografico_urls") or []:
            _register_object(url=str(url))
        for url in doc_data.get("documentos_soporte_urls") or []:
            _register_object(url=str(url))

        # Eliminar objetos en S3 (si existen)
        s3_deleted = []
        s3_failed = []

        # Agrupar por bucket para usar delete_objects en lote
        bucket_to_keys: Dict[str, List[str]] = {}
        for bucket_name, key_name in object_pairs:
            bucket_to_keys.setdefault(bucket_name, []).append(key_name)

        for bucket_name, keys in bucket_to_keys.items():
            # S3 permite máx 1000 claves por lote
            for i in range(0, len(keys), 1000):
                chunk = keys[i : i + 1000]
                try:
                    response = s3_client.delete_objects(
                        Bucket=bucket_name,
                        Delete={
                            "Objects": [{"Key": key} for key in chunk],
                            "Quiet": False,
                        },
                    )
                    for deleted in response.get("Deleted", []):
                        s3_deleted.append(
                            {"bucket": bucket_name, "key": deleted.get("Key")}
                        )
                    for error in response.get("Errors", []):
                        s3_failed.append(
                            {
                                "bucket": bucket_name,
                                "key": error.get("Key"),
                                "code": error.get("Code"),
                                "message": error.get("Message"),
                            }
                        )
                except Exception as delete_error:
                    for key in chunk:
                        s3_failed.append(
                            {
                                "bucket": bucket_name,
                                "key": key,
                                "code": "DeleteException",
                                "message": str(delete_error),
                            }
                        )

        if s3_failed:
            raise HTTPException(
                status_code=500,
                detail={
                    "message": "No se pudo completar la eliminación en S3. El documento NO fue eliminado en Firestore.",
                    "id": id,
                    "s3_deleted": len(s3_deleted),
                    "s3_failed": len(s3_failed),
                    "errors": s3_failed[:20],
                },
            )

        # Eliminar documento en Firestore solo si S3 quedó limpio
        doc_ref.delete()

        return create_utf8_response(
            {
                "success": True,
                "message": "Avance eliminado correctamente junto con sus archivos S3",
                "id": id,
                "deleted_firestore": True,
                "s3_total_detected": len(object_pairs),
                "s3_deleted": len(s3_deleted),
                "s3_failed": 0,
                "deleted_files": s3_deleted,
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error eliminando avance y soportes: {str(e)}"
        )


@router.get(
    "/solicitudes_cambios_unidades_proyecto",
    tags=["Unidades de Proyecto"],
    summary=" GET | Consultar Solicitudes de Cambios de Unidades de Proyecto",
    dependencies=[Depends(require_unidades("read"))],
)
@optional_rate_limit("60/minute")
async def consultar_solicitudes_cambios_unidades_proyecto(
    request: Request,
    doc_id: Optional[str] = Query(None, description="ID del documento en Firestore"),
    upid: Optional[str] = Query(None, description="Filtrar por UPID"),
    limit: Optional[int] = Query(
        None, ge=1, le=10000, description="Límite de registros"
    ),
    offset: Optional[int] = Query(None, ge=0, description="Offset para paginación"),
):
    if not FIREBASE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Firebase not available")

    current_user = getattr(request.state, "current_user", None) or {}
    effective_centro = enforce_unidades_access(current_user, "read:unidades", None)

    try:
        db = get_firestore_client()
        if db is None:
            raise HTTPException(
                status_code=503, detail="No se pudo conectar a Firestore"
            )

        collection_ref = db.collection("solicitudes_cambios_unidades_proyecto")

        should_convert = FIREBASE_TYPES_AVAILABLE
        datetime_type = FIREBASE_DATETIME_TYPES

        def normalize_value(value):
            if should_convert and isinstance(value, datetime_type):
                return value.isoformat()
            if isinstance(value, dict):
                for inner_key, inner_value in value.items():
                    value[inner_key] = normalize_value(inner_value)
                return value
            if isinstance(value, list):
                return [normalize_value(item) for item in value]
            return value

        if doc_id:
            doc = _as_firestore_doc_snapshot(collection_ref.document(doc_id).get())
            if not doc.exists:
                raise HTTPException(
                    status_code=404, detail=f"No existe solicitud con id: {doc_id}"
                )

            doc_data = doc.to_dict() or {}
            if should_convert:
                doc_data = normalize_value(doc_data)
            doc_data["id"] = doc.id

            if (
                effective_centro
                and doc_data.get("nombre_centro_gestor") != effective_centro
            ):
                raise HTTPException(
                    status_code=403,
                    detail="No autorizado para acceder a esta solicitud",
                )

            return create_utf8_response(
                {
                    "success": True,
                    "data": [doc_data],
                    "count": 1,
                    "collection": "solicitudes_cambios_unidades_proyecto",
                    "filters": {
                        "doc_id": doc_id,
                        "upid": upid,
                        "limit": limit,
                        "offset": offset,
                    },
                }
            )

        query = collection_ref
        if upid:
            query = query.where("upid", "==", upid)

        order_applied = False
        try:
            import google.cloud.firestore

            query = query.order_by(
                "created_at", direction=google.cloud.firestore.Query.DESCENDING
            )
            order_applied = True
        except Exception:
            order_applied = False

        query_limit = min(limit or 100, 10000)
        query = query.limit(query_limit)

        if offset:
            query = query.offset(offset)

        try:
            docs = query.stream()
        except Exception as e:
            error_text = str(e).lower()
            if order_applied and (
                "failed_precondition" in error_text or "index" in error_text
            ):
                fallback_query = collection_ref
                if upid:
                    fallback_query = fallback_query.where("upid", "==", upid)
                fallback_query = fallback_query.limit(query_limit)
                if offset:
                    fallback_query = fallback_query.offset(offset)
                docs = fallback_query.stream()
                order_applied = False
            else:
                raise

        data = []
        for doc in docs:
            doc_data = doc.to_dict() or {}
            if should_convert:
                doc_data = normalize_value(doc_data)
            doc_data["id"] = doc.id
            if (
                effective_centro
                and doc_data.get("nombre_centro_gestor") != effective_centro
            ):
                continue
            data.append(doc_data)

        return create_utf8_response(
            {
                "success": True,
                "data": data,
                "count": len(data),
                "collection": "solicitudes_cambios_unidades_proyecto",
                "filters": {
                    "doc_id": doc_id,
                    "upid": upid,
                    "limit": query_limit,
                    "offset": offset or 0,
                    "ordered_by": "created_at_desc" if order_applied else None,
                },
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error consultando solicitudes de cambios de unidades de proyecto: {str(e)}",
        )


@router.get(
    "/solicitudes_cambios_intervenciones",
    tags=["Unidades de Proyecto"],
    summary=" GET | Consultar Solicitudes de Cambios de Intervenciones",
    dependencies=[Depends(require_unidades("read"))],
)
@optional_rate_limit("60/minute")
async def consultar_solicitudes_cambios_intervenciones(
    request: Request,
    doc_id: Optional[str] = Query(None, description="ID del documento en Firestore"),
    intervencion_id: Optional[str] = Query(
        None, description="Filtrar por ID de intervención"
    ),
    upid: Optional[str] = Query(None, description="Filtrar por UPID"),
    limit: Optional[int] = Query(
        None, ge=1, le=10000, description="Límite de registros"
    ),
    offset: Optional[int] = Query(None, ge=0, description="Offset para paginación"),
):
    if not FIREBASE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Firebase not available")

    current_user = getattr(request.state, "current_user", None) or {}
    effective_centro = enforce_unidades_access(current_user, "read:unidades", None)

    try:
        db = get_firestore_client()
        if db is None:
            raise HTTPException(
                status_code=503, detail="No se pudo conectar a Firestore"
            )

        collection_ref = db.collection("solicitudes_cambios_intervenciones")

        should_convert = FIREBASE_TYPES_AVAILABLE
        datetime_type = FIREBASE_DATETIME_TYPES

        def normalize_value(value):
            if should_convert and isinstance(value, datetime_type):
                return value.isoformat()
            if isinstance(value, dict):
                for inner_key, inner_value in value.items():
                    value[inner_key] = normalize_value(inner_value)
                return value
            if isinstance(value, list):
                return [normalize_value(item) for item in value]
            return value

        if doc_id:
            doc = _as_firestore_doc_snapshot(collection_ref.document(doc_id).get())
            if not doc.exists:
                raise HTTPException(
                    status_code=404, detail=f"No existe solicitud con id: {doc_id}"
                )

            doc_data = doc.to_dict() or {}
            if should_convert:
                doc_data = normalize_value(doc_data)
            doc_data["id"] = doc.id

            if (
                effective_centro
                and doc_data.get("nombre_centro_gestor") != effective_centro
            ):
                raise HTTPException(
                    status_code=403,
                    detail="No autorizado para acceder a esta solicitud",
                )

            return create_utf8_response(
                {
                    "success": True,
                    "data": [doc_data],
                    "count": 1,
                    "collection": "solicitudes_cambios_intervenciones",
                    "filters": {
                        "doc_id": doc_id,
                        "intervencion_id": intervencion_id,
                        "upid": upid,
                        "limit": limit,
                        "offset": offset,
                    },
                }
            )

        query = collection_ref
        if intervencion_id:
            query = query.where("intervencion_id", "==", intervencion_id)
        if upid:
            query = query.where("upid", "==", upid)

        order_applied = False
        try:
            import google.cloud.firestore

            query = query.order_by(
                "created_at", direction=google.cloud.firestore.Query.DESCENDING
            )
            order_applied = True
        except Exception:
            order_applied = False

        query_limit = min(limit or 100, 10000)
        query = query.limit(query_limit)

        if offset:
            query = query.offset(offset)

        try:
            docs = query.stream()
        except Exception as e:
            error_text = str(e).lower()
            if order_applied and (
                "failed_precondition" in error_text or "index" in error_text
            ):
                fallback_query = collection_ref
                if intervencion_id:
                    fallback_query = fallback_query.where(
                        "intervencion_id", "==", intervencion_id
                    )
                if upid:
                    fallback_query = fallback_query.where("upid", "==", upid)
                fallback_query = fallback_query.limit(query_limit)
                if offset:
                    fallback_query = fallback_query.offset(offset)
                docs = fallback_query.stream()
                order_applied = False
            else:
                raise

        data = []
        for doc in docs:
            doc_data = doc.to_dict() or {}
            if should_convert:
                doc_data = normalize_value(doc_data)
            doc_data["id"] = doc.id
            if (
                effective_centro
                and doc_data.get("nombre_centro_gestor") != effective_centro
            ):
                continue
            data.append(doc_data)

        return create_utf8_response(
            {
                "success": True,
                "data": data,
                "count": len(data),
                "collection": "solicitudes_cambios_intervenciones",
                "filters": {
                    "doc_id": doc_id,
                    "intervencion_id": intervencion_id,
                    "upid": upid,
                    "limit": query_limit,
                    "offset": offset or 0,
                    "ordered_by": "created_at_desc" if order_applied else None,
                },
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error consultando solicitudes de cambios de intervenciones: {str(e)}",
        )


class SolicitudCambioUnidadProyectoRequest(BaseModel):
    upid: str = Field(..., description="UPID de la unidad a modificar (ej: UNP-1)")
    aprobado: bool = Field(..., description="Indicador de aprobación de la solicitud")
    nombre_up: Optional[str] = Field(
        None, description="Nombre de la unidad de proyecto"
    )
    nombre_up_detalle: Optional[str] = Field(
        None, description="Detalle del nombre de la unidad"
    )
    tipo_equipamiento: Optional[str] = Field(None, description="Tipo de equipamiento")
    clase_up: Optional[str] = Field(None, description="Clase UP")
    direccion: Optional[str] = Field(None, description="Dirección")
    geometry: Optional[Dict[str, Any]] = Field(
        None,
        description="Geometría GeoJSON Point enviada desde el frontend. Si se envía, recalcula automáticamente comuna_corregimiento, barrio_vereda y proyectos_estrategicos",
    )

    class Config:
        extra = "allow"
        json_schema_extra = {
            "example": {
                "upid": "UNP-1",
                "aprobado": True,
                "nombre_up": "Nombre unidad",
                "nombre_up_detalle": "Detalle unidad",
                "tipo_equipamiento": "Parque",
                "clase_up": "Espacio Publico",
                "direccion": "Calle 1 # 2-3",
                "geometry": {"additionalProp1": {}},
                "additionalProp1": {},
            }
        }


@router.post(
    "/solicitudes_cambios_unidad_proyecto",
    tags=["Unidades de Proyecto"],
    summary=" POST | Solicitud de cambios en Unidad de Proyecto",
    dependencies=[Depends(require_unidades("write"))],
)
@optional_rate_limit("30/minute")
async def crear_solicitud_cambio_unidad_proyecto(
    request: Request,
    payload: SolicitudCambioUnidadProyectoRequest = Body(
        ...,
        description="Datos de solicitud. Usa la misma estructura de /modificar/unidad_proyecto",
    ),
):
    if not FIREBASE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Firebase not available")

    try:
        db = get_firestore_client()
        if db is None:
            raise HTTPException(
                status_code=503, detail="No se pudo conectar a Firestore"
            )

        body = (
            payload.model_dump(exclude_unset=True)
            if hasattr(payload, "model_dump")
            else payload.dict(exclude_unset=True)
        )
        upid_value = str(body.get("upid", "")).strip()
        if not upid_value:
            raise HTTPException(
                status_code=400, detail="Debe enviar upid para registrar la solicitud"
            )

        if "aprobado" not in body or not isinstance(body.get("aprobado"), bool):
            raise HTTPException(
                status_code=400, detail="Debe enviar 'aprobado' como booleano"
            )

        changes = {
            key: value for key, value in body.items() if key not in {"upid", "aprobado"}
        }

        # Recalcular campos geograficos cuando se envia geometry.
        geometry_val = changes.get("geometry")
        if (
            isinstance(geometry_val, dict)
            and geometry_val.get("type")
            and geometry_val.get("coordinates")
        ):
            _validate_crs_coords(_normalizar_geometry(geometry_val))
            comuna = _buscar_en_geojson(
                os.path.join(BASEMAPS_DIR, "comunas_corregimientos.geojson"),
                "comuna_corregimiento",
                geometry_val,
            )
            barrio = _buscar_en_geojson(
                os.path.join(BASEMAPS_DIR, "barrios_veredas.geojson"),
                "barrio_vereda",
                geometry_val,
            )
            proyectos = _buscar_proyectos_estrategicos(geometry_val)
            if comuna:
                changes["comuna_corregimiento"] = comuna
            if barrio:
                changes["barrio_vereda"] = barrio
            changes["proyectos_estrategicos"] = proyectos

        now_iso = datetime.now().isoformat()
        solicitud_payload = {
            "upid": upid_value,
            "aprobado": body.get("aprobado"),
            **changes,
            "created_at": now_iso,
            "updated_at": now_iso,
        }
        solicitud_payload = {
            key: value for key, value in solicitud_payload.items() if value is not None
        }

        doc_id = str(uuid.uuid4())
        db.collection("solicitudes_cambios_unidades_proyecto").document(doc_id).set(
            solicitud_payload
        )

        # Notificar a admin_general y super_admin
        try:
            from api.services.notifications_service import notificar_nueva_solicitud

            _cu = getattr(request.state, "current_user", None) or {}
            _actor_email = _cu.get("email") or getattr(request.state, "user_email", None) or ""
            _actor_nombre = _cu.get("fullname") or _cu.get("display_name") or _actor_email or "Usuario"
            _actor_roles = _cu.get("roles") or []
            _actor_role_val = _actor_roles[0] if _actor_roles else "admin_centro_gestor"
            _actor_cg = (
                _cu.get("nombre_centro_gestor")
                or _cu.get("centro_gestor_assigned")
                or _cu.get("centro_gestor")
            )
            notificar_nueva_solicitud(
                actor_nombre=_actor_nombre,
                actor_email=_actor_email,
                actor_role=_actor_role_val,
                actor_centro_gestor=_actor_cg,
                modulo="unidades_proyecto",
                tipo_registro="unidad_proyecto",
                referencia_id=upid_value,
            )
        except Exception as notif_err:
            import logging

            logging.getLogger(__name__).warning(
                f"Notificación UP no enviada: {notif_err}"
            )

        return create_utf8_response(
            {
                "id": doc_id,
                "collection": "solicitudes_cambios_unidades_proyecto",
                "data": solicitud_payload,
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error registrando solicitud de cambio de unidad de proyecto: {str(e)}",
        )


@router.post(
    "/solicitudes_cambios_intervencion",
    tags=["Unidades de Proyecto"],
    summary=" POST | Solicitud de cambios en Intervención",
    dependencies=[Depends(require_unidades("write"))],
)
@optional_rate_limit("30/minute")
async def crear_solicitud_cambio_intervencion(
    request: Request,
    bpin: Optional[int] = Body(None, description="BPIN"),
    cantidad: Optional[int] = Body(None, description="Cantidad"),
    clase_up: Optional[str] = Body(None, description="Clase UP"),
    fecha_fin: Optional[str] = Body(None, description="Fecha fin (string)"),
    fecha_inicio: Optional[str] = Body(None, description="Fecha inicio (string)"),
    fuente_financiacion: Optional[str] = Body(
        None, description="Fuente de financiación"
    ),
    identificador: Optional[str] = Body(None, description="Identificador"),
    intervencion_id: Optional[str] = Body(None, description="ID de la intervención"),
    nombre_centro_gestor: Optional[str] = Body(
        None, description="Nombre centro gestor"
    ),
    presupuesto_base: Optional[float] = Body(None, description="Presupuesto base"),
    referencia_contrato: Optional[str] = Body(None, description="Referencia contrato"),
    referencia_proceso: Optional[str] = Body(None, description="Referencia proceso"),
    tipo_intervencion: Optional[str] = Body(None, description="Tipo de intervención"),
    unidad: Optional[str] = Body(None, description="Unidad"),
    upid: Optional[str] = Body(None, description="UPID"),
    url_proceso: Optional[str] = Body(None, description="URL proceso"),
):
    if not FIREBASE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Firebase not available")

    try:
        db = get_firestore_client()
        if db is None:
            raise HTTPException(
                status_code=503, detail="No se pudo conectar a Firestore"
            )

        now_iso = datetime.now().isoformat()
        solicitud_payload = {
            "bpin": bpin,
            "cantidad": cantidad,
            "clase_up": clase_up,
            "fecha_fin": fecha_fin,
            "fecha_inicio": fecha_inicio,
            "fuente_financiacion": fuente_financiacion,
            "identificador": identificador,
            "intervencion_id": intervencion_id,
            "nombre_centro_gestor": nombre_centro_gestor,
            "presupuesto_base": presupuesto_base,
            "referencia_contrato": referencia_contrato,
            "referencia_proceso": referencia_proceso,
            "tipo_intervencion": tipo_intervencion,
            "unidad": unidad,
            "upid": upid,
            "url_proceso": url_proceso,
            "created_at": now_iso,
            "updated_at": now_iso,
        }
        solicitud_payload = {
            key: value for key, value in solicitud_payload.items() if value is not None
        }

        doc_id = str(uuid.uuid4())
        db.collection("solicitudes_cambios_intervenciones").document(doc_id).set(
            solicitud_payload
        )

        # Notificar a admin_general y super_admin
        try:
            from api.services.notifications_service import notificar_nueva_solicitud

            _cu = getattr(request.state, "current_user", None) or {}
            _actor_email = _cu.get("email") or getattr(request.state, "user_email", None) or ""
            _actor_nombre = _cu.get("fullname") or _cu.get("display_name") or _actor_email or "Usuario"
            _actor_roles = _cu.get("roles") or []
            _actor_role_val = _actor_roles[0] if _actor_roles else "admin_centro_gestor"
            _actor_cg = (
                _cu.get("nombre_centro_gestor")
                or _cu.get("centro_gestor_assigned")
                or _cu.get("centro_gestor")
                or nombre_centro_gestor
            )
            notificar_nueva_solicitud(
                actor_nombre=_actor_nombre,
                actor_email=_actor_email,
                actor_role=_actor_role_val,
                actor_centro_gestor=_actor_cg,
                modulo="intervenciones",
                tipo_registro="intervencion",
                referencia_id=intervencion_id or upid,
            )
        except Exception as notif_err:
            import logging

            logging.getLogger(__name__).warning(
                f"Notificación intervencion no enviada: {notif_err}"
            )

        return create_utf8_response(
            {
                "id": doc_id,
                "collection": "solicitudes_cambios_intervenciones",
                "data": solicitud_payload,
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error registrando solicitud de cambio de intervención: {str(e)}",
        )


def _normalizar_geometry(geometry_dict: dict) -> dict:
    """Normaliza un dict de geometría GeoJSON: si coordinates es string, lo parsea a lista."""
    coords = geometry_dict.get("coordinates")
    if isinstance(coords, str):
        try:
            geometry_dict = dict(geometry_dict)
            geometry_dict["coordinates"] = json.loads(coords)
        except (json.JSONDecodeError, ValueError):
            pass
    return geometry_dict


# Bounding box aproximado para Cali, Colombia (EPSG:4326)
# lon ∈ [-77.0, -76.0], lat ∈ [3.0, 4.0]
_CALI_BBOX = {"lon_min": -77.0, "lon_max": -76.0, "lat_min": 3.0, "lat_max": 4.0}


def _require_global_unidades_access(request: Request) -> None:
    """F2: gate para endpoints de diagnóstico agregado.

    Si el usuario sólo tiene permisos ``:own_centro`` / ``:basic``, no debe
    ver datos agregados de todos los centros gestores. Lanza HTTPException(403).
    """
    current_user = getattr(request.state, "current_user", None)
    if current_user is None:
        return  # auth deshabilitada (tests) – respetar comportamiento previo
    forced = enforce_unidades_access(current_user, "read:unidades", None)
    if forced is not None:
        raise HTTPException(
            status_code=403,
            detail=(
                "Este reporte agrega información de múltiples centros gestores "
                "y requiere acceso global a unidades."
            ),
        )


def _validate_crs_coords(geometry_dict: dict) -> None:
    """Valida que las coordenadas estén en EPSG:4326 dentro del bounding box de Cali.

    Recorre recursivamente la estructura `coordinates` (admite Point, LineString,
    Polygon, MultiPolygon, etc.) y verifica que cada par [lon, lat] esté dentro
    del rango razonable. Lanza HTTPException(400) si detecta valores fuera de
    rango o si la geometría carece de los campos básicos.
    """
    if not isinstance(geometry_dict, dict):
        raise HTTPException(status_code=400, detail="Geometría inválida")
    coords = geometry_dict.get("coordinates")
    if coords is None:
        raise HTTPException(status_code=400, detail="Geometría sin 'coordinates'")

    def _check_pair(pair):
        if (
            not isinstance(pair, (list, tuple))
            or len(pair) < 2
            or not isinstance(pair[0], (int, float))
            or not isinstance(pair[1], (int, float))
        ):
            raise HTTPException(
                status_code=400,
                detail="Coordenadas deben ser pares numéricos [lon, lat]",
            )
        lon, lat = float(pair[0]), float(pair[1])
        if not (-180.0 <= lon <= 180.0 and -90.0 <= lat <= 90.0):
            raise HTTPException(
                status_code=400,
                detail=f"Coordenadas fuera de EPSG:4326 (lon={lon}, lat={lat})",
            )
        if not (
            _CALI_BBOX["lon_min"] <= lon <= _CALI_BBOX["lon_max"]
            and _CALI_BBOX["lat_min"] <= lat <= _CALI_BBOX["lat_max"]
        ):
            raise HTTPException(
                status_code=400,
                detail=(
                    "Coordenadas fuera del bounding box de Cali "
                    f"(lon={lon}, lat={lat}). Esperado EPSG:4326 dentro de Cali."
                ),
            )

    def _walk(node):
        # nodo es lista: si los dos primeros son numéricos, es un par; si no, recursivo
        if (
            isinstance(node, (list, tuple))
            and len(node) >= 2
            and isinstance(node[0], (int, float))
            and isinstance(node[1], (int, float))
        ):
            _check_pair(node)
            return
        if isinstance(node, (list, tuple)):
            for item in node:
                _walk(item)

    _walk(coords)


@lru_cache(maxsize=32)
def _load_geojson_cached(geojson_path: str) -> dict:
    """Carga y cachea en memoria un archivo GeoJSON desde disco.
    Se invoca como máximo una vez por ruta (lru_cache con maxsize=32).
    Reduce los ~100 MB de I/O por request en creación/modificación de UP."""
    with open(geojson_path, "r", encoding="utf-8") as f:
        return json.load(f)


@lru_cache(maxsize=4)
def _list_estrategicos_filenames(estrategicos_dir: str) -> tuple:
    """Retorna una tupla ordenada de nombres .geojson en el directorio (cacheada).
    Evita llamar os.listdir en cada request de modificación/creación."""
    if not os.path.isdir(estrategicos_dir):
        return ()
    return tuple(
        sorted(
            f for f in os.listdir(estrategicos_dir) if f.lower().endswith(".geojson")
        )
    )


def _invalidate_unidades_cache() -> None:
    """Invalida entradas del cache de servidor relacionadas con unidades_proyecto.
    Se llama tras cualquier mutación (crear, modificar, eliminar UP o intervención)."""
    clear_cache_by_prefix("unidades_proyecto")
    clear_cache_by_prefix("init_360")
    clear_cache_by_prefix("intervenciones_unidades_lookup")


def _buscar_en_geojson(
    geojson_path: str, property_name: str, point_coords_or_geometry=None
) -> Optional[str]:
    """Cruza una geometría GeoJSON con una capa y retorna la propiedad del polígono que la contiene.
    Acepta [lon, lat] (legacy) o un dict GeoJSON geometry de cualquier tipo.
    Para geometrías no-Point usa el centroide para determinar contención.
    Usa _load_geojson_cached para evitar recargar el archivo en cada request."""
    try:
        geojson_data = _load_geojson_cached(geojson_path)
        if isinstance(point_coords_or_geometry, dict) and point_coords_or_geometry.get(
            "type"
        ):
            geom = shapely_shape(_normalizar_geometry(point_coords_or_geometry))
            test_point = geom.centroid if geom.geom_type != "Point" else geom
        elif isinstance(point_coords_or_geometry, (list, tuple)):
            test_point = ShapelyPoint(
                point_coords_or_geometry[0], point_coords_or_geometry[1]
            )
        else:
            return None
        for feature in geojson_data.get("features", []):
            polygon = shapely_shape(feature["geometry"])
            if polygon.contains(test_point):
                return feature.get("properties", {}).get(property_name)
    except Exception as e:
        logger.warning(
            f"Error cruzando geometría con {geojson_path}: {type(e).__name__}"
        )
    return None


def _buscar_proyectos_estrategicos(geometry_input) -> list:
    """Intersecta una geometría GeoJSON con todos los GeoJSON en basemaps/proyectos_estrategicos/
    y retorna lista de Name coincidentes.
    Acepta [lon, lat] (legacy) o un dict GeoJSON geometry de cualquier tipo (Point, Polygon, LineString, etc.).
    Usa _load_geojson_cached y _list_estrategicos_filenames para minimizar I/O de disco.
    """
    nombres = []
    estrategicos_dir = PROYECTOS_ESTRATEGICOS_DIR
    filenames = _list_estrategicos_filenames(estrategicos_dir)
    if not filenames:
        logger.warning(
            "proyectos_estrategicos: directorio vacío o no encontrado en %s",
            estrategicos_dir,
        )
        return []
    try:
        if isinstance(geometry_input, dict) and geometry_input.get("type"):
            geom = shapely_shape(_normalizar_geometry(geometry_input))
        elif isinstance(geometry_input, (list, tuple)):
            geom = ShapelyPoint(geometry_input[0], geometry_input[1])
        else:
            return []
        for filename in filenames:
            filepath = os.path.join(estrategicos_dir, filename)
            try:
                geojson_data = _load_geojson_cached(filepath)
                for feature in geojson_data.get("features", []):
                    polygon = shapely_shape(feature["geometry"])
                    if polygon.intersects(geom):
                        name = feature.get("properties", {}).get("Name")
                        if name and name not in nombres:
                            nombres.append(name)
            except Exception as e:
                logger.warning(f"Error procesando {filename}: {type(e).__name__}")
    except Exception as e:
        logger.warning(f"Error en _buscar_proyectos_estrategicos: {type(e).__name__}")
    return nombres


@router.post(
    "/crear_unidad_proyecto",
    tags=["Unidades de Proyecto"],
    dependencies=[Depends(require_unidades("write"))],
    summary=" POST | Crear Unidad de Proyecto",
    description=(
        "Crea una nueva Unidad de Proyecto. Variables auto-calculadas:\n\n"
        "- **upid**: se genera automáticamente (último UNP-### + 1)\n"
        "- **comuna_corregimiento**: se detecta cruzando geometry con basemaps/comunas_corregimientos.geojson\n"
        "- **barrio_vereda**: se detecta cruzando geometry con basemaps/barrios_veredas.geojson\n"
        "- **proyectos_estrategicos**: lista de nombres obtenida por intersección con basemaps/proyectos_estrategicos/*.geojson\n"
    ),
)
@optional_rate_limit("30/minute")
async def crear_unidad_proyecto(
    request: Request,
    nombre_up: Optional[str] = Body(
        None,
        description="Nombre de la unidad de proyecto",
        example="Parque Lineal Río Cali",
    ),
    nombre_up_detalle: Optional[str] = Body(
        None,
        description="Detalle del nombre de la unidad",
        example="Tramo 3 - Sector Norte",
    ),
    tipo_equipamiento: Optional[str] = Body(
        None, description="Tipo de equipamiento", example="Parque"
    ),
    direccion: Optional[str] = Body(
        None, description="Dirección", example="Calle 25 Norte #6N-45"
    ),
    geometry: Optional[Dict[str, Any]] = Body(
        None,
        description="Geometría GeoJSON tipo Point con coordenadas [longitud, latitud]",
        example={"type": "Point", "coordinates": [0.0, 0.0]},
    ),
    nombre_centro_gestor: Optional[str] = Body(
        None,
        description=(
            "Centro gestor responsable. Si el usuario no es global se "
            "fuerza al centro_gestor_assigned del usuario actual."
        ),
        example="DAGMA",
    ),
):
    if not FIREBASE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Firebase not available")

    # --- Authorization scoping (F2/F3) ---
    current_user = getattr(request.state, "current_user", None)
    if current_user is None:
        raise HTTPException(status_code=401, detail="No autenticado")
    effective_centro = enforce_unidades_access(
        current_user, "write:unidades", nombre_centro_gestor
    )
    # Si el usuario solo tiene own_centro o no envió valor, forzamos su centro.
    if not effective_centro:
        effective_centro = current_user.get(
            "centro_gestor_assigned"
        ) or current_user.get("nombre_centro_gestor")

    try:
        db = get_firestore_client()
        if db is None:
            raise HTTPException(
                status_code=503, detail="No se pudo conectar a Firestore"
            )

        # --- Auto-generar UPID (último UNP-### de unidades_proyecto + 1) ---
        def extract_upid_number(upid_value: Any) -> Optional[int]:
            if upid_value is None:
                return None
            match = re.match(r"^UNP-(\d+)$", str(upid_value).strip(), re.IGNORECASE)
            if not match:
                return None
            return int(match.group(1))

        max_upid_number = 0
        collections_to_scan = ["unidades_proyecto"]

        for collection_name in collections_to_scan:
            docs = db.collection(collection_name).select(["upid"]).stream()
            for doc in docs:
                doc_data = doc.to_dict() or {}
                upid_number = extract_upid_number(doc_data.get("upid"))
                if upid_number is not None:
                    max_upid_number = max(max_upid_number, upid_number)

        new_upid = f"UNP-{max_upid_number + 1}"

        # --- Auto-detectar comuna_corregimiento y barrio_vereda desde geometry ---
        comuna_corregimiento = None
        barrio_vereda = None
        proyectos_estrategicos = []

        if geometry and geometry.get("type") and geometry.get("coordinates"):
            _validate_crs_coords(_normalizar_geometry(geometry))
            comuna_corregimiento = _buscar_en_geojson(
                os.path.join(BASEMAPS_DIR, "comunas_corregimientos.geojson"),
                "comuna_corregimiento",
                geometry,
            )
            barrio_vereda = _buscar_en_geojson(
                os.path.join(BASEMAPS_DIR, "barrios_veredas.geojson"),
                "barrio_vereda",
                geometry,
            )
            proyectos_estrategicos = _buscar_proyectos_estrategicos(geometry)

        now_iso = datetime.now().isoformat()

        unidad_payload = {
            "nombre_up": nombre_up,
            "nombre_up_detalle": nombre_up_detalle,
            "tipo_equipamiento": tipo_equipamiento,
            "comuna_corregimiento": comuna_corregimiento,
            "barrio_vereda": barrio_vereda,
            "direccion": direccion,
            "geometry": geometry,
            "nombre_centro_gestor": effective_centro,
        }
        unidad_payload = {
            key: value for key, value in unidad_payload.items() if value is not None
        }
        unidad_payload["upid"] = new_upid
        unidad_payload["proyectos_estrategicos"] = proyectos_estrategicos
        unidad_payload["created_at"] = now_iso
        unidad_payload["updated_at"] = now_iso
        unidad_payload["created_by"] = current_user.get("uid")

        db.collection("unidades_proyecto").document(new_upid).set(unidad_payload)

        # --- Audit (F6) ---
        try:
            db.collection("cambios_implementados_unidades_proyecto").add(
                {
                    "upid": new_upid,
                    "accion": "crear",
                    "uid": current_user.get("uid"),
                    "email": current_user.get("email"),
                    "nombre_centro_gestor": effective_centro,
                    "payload": unidad_payload,
                    "timestamp": now_iso,
                }
            )
        except Exception as audit_err:
            logger.warning(
                "crear_unidad_proyecto: fallo registrando auditoría: %s",
                audit_err,
            )

        _invalidate_unidades_cache()
        return create_utf8_response(
            {"id": new_upid, "collection": "unidades_proyecto", "data": unidad_payload}
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error creando unidad de proyecto: {str(e)}"
        )


@router.post(
    "/crear_intervencion",
    tags=["Unidades de Proyecto"],
    summary=" POST | Crear Intervención",
    dependencies=[Depends(require_unidades("write"))],
)
@optional_rate_limit("30/minute")
async def crear_intervencion(
    request: Request,
    upid: str = Body(..., description="UPID válido existente en unidades_proyecto"),
    bpin: Optional[int] = Body(None, description="BPIN"),
    cantidad: Optional[int] = Body(None, description="Cantidad"),
    clase_up: Optional[str] = Body(None, description="Clase UP"),
    fecha_fin: Optional[str] = Body(None, description="Fecha fin (string)"),
    fecha_inicio: Optional[str] = Body(None, description="Fecha inicio (string)"),
    fuente_financiacion: Optional[str] = Body(
        None, description="Fuente de financiación"
    ),
    identificador: Optional[str] = Body(None, description="Identificador"),
    nombre_centro_gestor: Optional[str] = Body(
        None, description="Nombre centro gestor"
    ),
    presupuesto_base: Optional[float] = Body(None, description="Presupuesto base"),
    referencia_contrato: Optional[str] = Body(None, description="Referencia contrato"),
    referencia_proceso: Optional[str] = Body(None, description="Referencia proceso"),
    tipo_intervencion: Optional[str] = Body(None, description="Tipo de intervención"),
    unidad: Optional[str] = Body(None, description="Unidad"),
    url_proceso: Optional[str] = Body(None, description="URL proceso"),
    descripcion_intervencion: Optional[str] = Body(
        None, description="Descripción de la intervención"
    ),
):
    if not FIREBASE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Firebase not available")

    current_user = getattr(request.state, "current_user", None)
    if current_user is None:
        raise HTTPException(status_code=401, detail="No autenticado")

    effective_centro = enforce_unidades_access(
        current_user, "write:unidades", nombre_centro_gestor
    )
    if effective_centro and not nombre_centro_gestor:
        nombre_centro_gestor = effective_centro

    try:
        db = get_firestore_client()
        if db is None:
            raise HTTPException(
                status_code=503, detail="No se pudo conectar a Firestore"
            )

        upid_value = str(upid).strip()
        if not upid_value:
            raise HTTPException(
                status_code=400,
                detail="El campo upid es obligatorio para crear una intervención",
            )

        upid_docs = list(
            db.collection("unidades_proyecto")
            .where("upid", "==", upid_value)
            .limit(1)
            .stream()
        )
        if not upid_docs:
            raise HTTPException(
                status_code=400,
                detail=f"El upid {upid_value} no existe en unidades_proyecto",
            )

        def extract_intervencion_number(
            intervencion_value: Any, upid_base: str
        ) -> Optional[int]:
            if intervencion_value is None:
                return None
            pattern = rf"^{re.escape(upid_base)}-INT-(\d+)$"
            match = re.match(pattern, str(intervencion_value).strip(), re.IGNORECASE)
            if not match:
                return None
            return int(match.group(1))

        max_intervencion_number = 0
        collections_to_scan = [
            "intervenciones_unidades_proyecto",
            "unidades_proyecto_intervenciones",
        ]

        for collection_name in collections_to_scan:
            docs = (
                db.collection(collection_name).where("upid", "==", upid_value).stream()
            )
            for doc in docs:
                doc_data = doc.to_dict() or {}
                intervencion_number = extract_intervencion_number(
                    doc_data.get("intervencion_id"), upid_value
                )
                if intervencion_number is None:
                    intervencion_number = extract_intervencion_number(
                        doc.id, upid_value
                    )
                if intervencion_number is not None:
                    max_intervencion_number = max(
                        max_intervencion_number, intervencion_number
                    )

        new_intervencion_id = f"{upid_value}-INT-{max_intervencion_number + 1}"
        now_iso = datetime.now().isoformat()

        intervencion_payload = {
            "bpin": bpin,
            "cantidad": cantidad,
            "clase_up": clase_up,
            "fecha_fin": fecha_fin,
            "fecha_inicio": fecha_inicio,
            "fuente_financiacion": fuente_financiacion,
            "identificador": identificador,
            "nombre_centro_gestor": nombre_centro_gestor,
            "presupuesto_base": presupuesto_base,
            "referencia_contrato": referencia_contrato,
            "referencia_proceso": referencia_proceso,
            "tipo_intervencion": tipo_intervencion,
            "unidad": unidad,
            "url_proceso": url_proceso,
            "descripcion_intervencion": descripcion_intervencion,
        }
        intervencion_payload = {
            key: value
            for key, value in intervencion_payload.items()
            if value is not None
        }
        intervencion_payload["upid"] = upid_value
        intervencion_payload["intervencion_id"] = new_intervencion_id
        intervencion_payload["created_at"] = now_iso
        intervencion_payload["updated_at"] = now_iso
        intervencion_payload["created_by"] = current_user.get("uid")

        doc_id = str(uuid.uuid4())
        db.collection("intervenciones_unidades_proyecto").document(doc_id).set(
            intervencion_payload
        )

        # Audit (F6)
        try:
            db.collection("cambios_implementados_intervenciones").add(
                {
                    "intervencion_id": new_intervencion_id,
                    "doc_id": doc_id,
                    "upid": upid_value,
                    "accion": "crear",
                    "uid": current_user.get("uid"),
                    "email": current_user.get("email"),
                    "nombre_centro_gestor": intervencion_payload.get(
                        "nombre_centro_gestor"
                    ),
                    "payload_nuevo": intervencion_payload,
                    "timestamp": now_iso,
                }
            )
        except Exception as audit_err:
            logger.warning(
                "crear_intervencion: fallo registrando auditoría: %s", audit_err
            )

        _invalidate_unidades_cache()
        return create_utf8_response(
            {
                "id": doc_id,
                "collection": "intervenciones_unidades_proyecto",
                "data": intervencion_payload,
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error creando intervención: {str(e)}"
        )


class ModificarUnidadProyectoRequest(BaseModel):
    upid: str = Field(..., description="UPID de la unidad a modificar (ej: UNP-1)")
    aprobado: bool = Field(
        ...,
        description="Si es true aplica cambios; si es false solo registra auditoría",
    )
    nombre_up: Optional[str] = Field(
        None, description="Nombre de la unidad de proyecto"
    )
    nombre_up_detalle: Optional[str] = Field(
        None, description="Detalle del nombre de la unidad"
    )
    tipo_equipamiento: Optional[str] = Field(None, description="Tipo de equipamiento")
    clase_up: Optional[str] = Field(None, description="Clase UP")
    direccion: Optional[str] = Field(None, description="Dirección")
    geometry: Optional[Dict[str, Any]] = Field(
        None,
        description="Geometría GeoJSON Point enviada desde el frontend. Si se envía, recalcula automáticamente comuna_corregimiento, barrio_vereda y proyectos_estrategicos",
    )

    class Config:
        extra = "allow"
        json_schema_extra = {
            "example": {
                "upid": "UNP-1",
                "aprobado": True,
                "nombre_up": "Nombre unidad",
                "geometry": {"type": "Point", "coordinates": [0.0, 0.0]},
            }
        }


class ModificarIntervencionRequest(BaseModel):
    intervencion_id: str = Field(..., description="ID de intervención a modificar")
    aprobado: bool = Field(
        ...,
        description="Si es true aplica cambios; si es false solo registra auditoría",
    )
    upid: Optional[str] = Field(None, description="UPID asociado")
    bpin: Optional[int] = Field(None, description="BPIN")
    cantidad: Optional[int] = Field(None, description="Cantidad")
    clase_up: Optional[str] = Field(None, description="Clase UP")
    fecha_fin: Optional[str] = Field(None, description="Fecha fin")
    fecha_inicio: Optional[str] = Field(None, description="Fecha inicio")
    fuente_financiacion: Optional[str] = Field(
        None, description="Fuente de financiación"
    )
    identificador: Optional[str] = Field(None, description="Identificador")
    nombre_centro_gestor: Optional[str] = Field(
        None, description="Nombre del centro gestor"
    )
    presupuesto_base: Optional[float] = Field(None, description="Presupuesto base")
    referencia_contrato: Optional[str] = Field(None, description="Referencia contrato")
    referencia_proceso: Optional[str] = Field(None, description="Referencia proceso")
    tipo_intervencion: Optional[str] = Field(None, description="Tipo de intervención")
    unidad: Optional[str] = Field(None, description="Unidad")
    url_proceso: Optional[str] = Field(None, description="URL del proceso")
    descripcion_intervencion: Optional[str] = Field(
        None, description="Descripción de la intervención"
    )
    extra_data: Optional[Dict[str, Any]] = Field(
        None,
        description="Campos adicionales válidos de la colección intervenciones_unidades_proyecto",
    )

    class Config:
        extra = "allow"
        json_schema_extra = {
            "example": {
                "intervencion_id": "UP-001-INT-1",
                "aprobado": False,
                "descripcion_intervencion": "Ajuste de alcance",
                "cantidad": 12,
                "extra_data": {"observaciones": "Pendiente aprobación técnica"},
            }
        }


@router.put(
    "/modificar/unidad_proyecto",
    tags=["Unidades de Proyecto"],
    summary=" PUT | Modificar Unidad de Proyecto",
    dependencies=[Depends(require_unidades("write"))],
)
@optional_rate_limit("30/minute")
async def modificar_unidad_proyecto(
    request: Request,
    payload: ModificarUnidadProyectoRequest = Body(
        ...,
        description="Datos a modificar. Incluye upid, aprobado y cualquier campo adicional a actualizar",
    ),
):
    if not FIREBASE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Firebase not available")

    current_user = getattr(request.state, "current_user", None)
    if current_user is None:
        raise HTTPException(status_code=401, detail="No autenticado")

    try:
        db = get_firestore_client()
        if db is None:
            raise HTTPException(
                status_code=503, detail="No se pudo conectar a Firestore"
            )

        body = (
            payload.model_dump(exclude_unset=True)
            if hasattr(payload, "model_dump")
            else payload.dict(exclude_unset=True)
        )
        upid_value = str(body.get("upid", "")).strip()
        if not upid_value:
            raise HTTPException(
                status_code=400,
                detail="Debe enviar upid para modificar la unidad de proyecto",
            )

        if "aprobado" not in body or not isinstance(body.get("aprobado"), bool):
            raise HTTPException(
                status_code=400, detail="Debe enviar 'aprobado' como booleano"
            )
        aprobado = body.get("aprobado")

        doc_ref = db.collection("unidades_proyecto").document(upid_value)
        doc_snap = _as_firestore_doc_snapshot(doc_ref.get())
        if not doc_snap.exists:
            raise HTTPException(
                status_code=404,
                detail=f"No existe unidad_proyecto con upid: {upid_value}",
            )

        # F2: validar centro_gestor del doc existente
        previous_doc_data = doc_snap.to_dict() or {}
        enforce_unidades_access(
            current_user,
            "write:unidades",
            previous_doc_data.get("nombre_centro_gestor"),
        )

        changes = {
            key: value for key, value in body.items() if key not in {"upid", "aprobado"}
        }

        # --- Auto-detectar comuna, barrio y proyectos desde geometry ---
        geometry_val = changes.get("geometry")
        if (
            geometry_val
            and geometry_val.get("type")
            and geometry_val.get("coordinates")
        ):
            _validate_crs_coords(_normalizar_geometry(geometry_val))
            comuna = _buscar_en_geojson(
                os.path.join(BASEMAPS_DIR, "comunas_corregimientos.geojson"),
                "comuna_corregimiento",
                geometry_val,
            )
            barrio = _buscar_en_geojson(
                os.path.join(BASEMAPS_DIR, "barrios_veredas.geojson"),
                "barrio_vereda",
                geometry_val,
            )
            proyectos = _buscar_proyectos_estrategicos(geometry_val)
            if comuna:
                changes["comuna_corregimiento"] = comuna
            if barrio:
                changes["barrio_vereda"] = barrio
            changes["proyectos_estrategicos"] = proyectos

        if not changes:
            raise HTTPException(
                status_code=400, detail="No se enviaron campos a modificar"
            )

        previous_data = doc_snap.to_dict() or {}

        changes_to_apply = dict(changes)
        if aprobado:
            now_iso = datetime.now().isoformat()
            changes_to_apply["updated_at"] = now_iso
            doc_ref.update(changes_to_apply)

        updated_data = dict(previous_data)
        if aprobado:
            updated_data.update(changes_to_apply)

        db.collection("cambios_implementados_unidades_proyecto").add(
            {
                "timestamp": datetime.now().isoformat(),
                "collection_origen": "unidades_proyecto",
                "documento_origen_id": upid_value,
                "upid": upid_value,
                "aprobado": aprobado,
                "ejecutado": aprobado,
                "accion": "modificar",
                "uid": current_user.get("uid"),
                "email": current_user.get("email"),
                "datos_anteriores": previous_data,
                "datos_solicitados": changes,
                "datos_resultantes": updated_data,
            }
        )

        _invalidate_unidades_cache()
        return create_utf8_response(
            {
                "id": upid_value,
                "collection": "unidades_proyecto",
                "upid": upid_value,
                "aprobado": aprobado,
                "ejecutado": aprobado,
                "data": updated_data,
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error modificando unidad de proyecto: {str(e)}"
        )


@router.put(
    "/modificar/intervencion",
    tags=["Unidades de Proyecto"],
    summary=" PUT | Modificar Intervención",
    dependencies=[Depends(require_unidades("write"))],
)
@optional_rate_limit("30/minute")
async def modificar_intervencion(
    request: Request,
    payload: ModificarIntervencionRequest = Body(
        ...,
        description="Datos a modificar. Incluye intervencion_id, aprobado y cualquier campo adicional a actualizar",
    ),
):
    if not FIREBASE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Firebase not available")

    current_user = getattr(request.state, "current_user", None)
    if current_user is None:
        raise HTTPException(status_code=401, detail="No autenticado")

    try:
        db = get_firestore_client()
        if db is None:
            raise HTTPException(
                status_code=503, detail="No se pudo conectar a Firestore"
            )

        body = (
            payload.model_dump(exclude_unset=True)
            if hasattr(payload, "model_dump")
            else payload.dict(exclude_unset=True)
        )
        intervencion_id_value = str(body.get("intervencion_id", "")).strip()
        if not intervencion_id_value:
            raise HTTPException(
                status_code=400,
                detail="Debe enviar intervencion_id para modificar la intervención",
            )

        if "aprobado" not in body or not isinstance(body.get("aprobado"), bool):
            raise HTTPException(
                status_code=400, detail="Debe enviar 'aprobado' como booleano"
            )
        aprobado = body.get("aprobado")

        docs = list(
            db.collection("intervenciones_unidades_proyecto")
            .where("intervencion_id", "==", intervencion_id_value)
            .limit(1)
            .stream()
        )
        if not docs:
            raise HTTPException(
                status_code=404,
                detail=f"No existe intervención con intervencion_id: {intervencion_id_value}",
            )

        # F2: validar centro_gestor del doc existente
        doc = docs[0]
        previous_data = doc.to_dict() or {}
        enforce_unidades_access(
            current_user,
            "write:unidades",
            previous_data.get("nombre_centro_gestor"),
        )

        extra_data = body.get("extra_data") or {}
        if not isinstance(extra_data, dict):
            raise HTTPException(
                status_code=400, detail="'extra_data' debe ser un objeto JSON"
            )

        changes = {
            key: value
            for key, value in body.items()
            if key not in {"intervencion_id", "aprobado", "extra_data"}
        }
        changes.update(extra_data)
        # avance_obra y estado son campos computados: nunca se editan manualmente
        changes.pop("avance_obra", None)
        changes.pop("estado", None)
        if not changes:
            raise HTTPException(
                status_code=400, detail="No se enviaron campos a modificar"
            )

        changes_to_apply = dict(changes)
        if aprobado:
            now_iso = datetime.now().isoformat()
            changes_to_apply["updated_at"] = now_iso
            doc.reference.update(changes_to_apply)

        updated_data = dict(previous_data)
        if aprobado:
            updated_data.update(changes_to_apply)

        db.collection("cambios_implementados_intervenciones").add(
            {
                "timestamp": datetime.now().isoformat(),
                "collection_origen": "intervenciones_unidades_proyecto",
                "documento_origen_id": doc.id,
                "intervencion_id": intervencion_id_value,
                "aprobado": aprobado,
                "ejecutado": aprobado,
                "accion": "modificar",
                "uid": current_user.get("uid"),
                "email": current_user.get("email"),
                "datos_anteriores": previous_data,
                "datos_solicitados": changes,
                "datos_resultantes": updated_data,
            }
        )

        _invalidate_unidades_cache()
        return create_utf8_response(
            {
                "id": doc.id,
                "collection": "intervenciones_unidades_proyecto",
                "intervencion_id": intervencion_id_value,
                "aprobado": aprobado,
                "ejecutado": aprobado,
                "data": updated_data,
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error modificando intervención: {str(e)}"
        )


@router.delete(
    "/eliminar_unidad_proyecto",
    tags=["Unidades de Proyecto"],
    summary=" DELETE | Eliminar Unidad de Proyecto",
    dependencies=[Depends(require_unidades("delete"))],
)
@optional_rate_limit("30/minute")
async def eliminar_unidad_proyecto(
    request: Request,
    upid: str = Query(..., description="UPID de la unidad de proyecto a eliminar"),
):
    if not FIREBASE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Firebase not available")

    current_user = getattr(request.state, "current_user", None)
    if current_user is None:
        raise HTTPException(status_code=401, detail="No autenticado")

    try:
        db = get_firestore_client()
        if db is None:
            raise HTTPException(
                status_code=503, detail="No se pudo conectar a Firestore"
            )

        docs = list(
            db.collection("unidades_proyecto").where("upid", "==", upid).stream()
        )
        if not docs:
            raise HTTPException(
                status_code=404, detail=f"No existe unidad_proyecto con upid: {upid}"
            )

        # Validar centro_gestor del recurso antes de eliminar (F2)
        for doc in docs:
            data = doc.to_dict() or {}
            enforce_unidades_access(
                current_user,
                "delete:unidades",
                data.get("nombre_centro_gestor"),
            )

        # Initialize S3 client for cascade cleanup
        try:
            from api.utils.s3_document_manager import S3DocumentManager as _S3Mgr, BOTO3_AVAILABLE as _B3

            if not _B3:
                raise HTTPException(status_code=500, detail="boto3 no disponible para eliminar archivos S3 asociados")
            _creds_path = os.getenv("AWS_CREDENTIALS_FILE_UNIDADES_PROYECTO", "credentials/aws_credentials.json")
            _s3_client = _S3Mgr(credentials_path=_creds_path).s3_client
            _default_bucket = os.getenv("S3_BUCKET_UNIDADES_PROYECTO", "unidades-proyecto-documents")
        except HTTPException:
            raise
        except Exception as s3_err:
            raise HTTPException(status_code=500, detail=f"No se pudo inicializar S3 para eliminación en cascada: {s3_err}")

        # Collect all avances (and their S3 objects) across all interventions of this UP
        all_s3_pairs: set = set()
        avance_docs_to_delete = []
        intervencion_docs_to_delete = []

        intervencion_docs = list(
            db.collection("intervenciones_unidades_proyecto")
            .where("upid", "==", upid)
            .stream()
        )
        intervencion_docs_to_delete = intervencion_docs

        for intervencion_doc in intervencion_docs:
            int_data = intervencion_doc.to_dict() or {}
            int_id = int_data.get("intervencion_id") or intervencion_doc.id
            avances = list(
                db.collection("avances_unidades_proyecto")
                .where("intervencion_id", "==", int_id)
                .stream()
            )
            for avance_doc in avances:
                avance_docs_to_delete.append(avance_doc)
                all_s3_pairs.update(_collect_avance_s3_objects(avance_doc.to_dict() or {}, _default_bucket))

        # Delete S3 objects (fail fast if any error)
        if all_s3_pairs:
            s3_deleted, s3_failed = _delete_s3_objects_batch(_s3_client, all_s3_pairs)
            if s3_failed:
                raise HTTPException(
                    status_code=500,
                    detail={
                        "message": "No se pudo completar la eliminación en S3. La unidad de proyecto NO fue eliminada.",
                        "upid": upid,
                        "s3_deleted": len(s3_deleted),
                        "s3_failed": len(s3_failed),
                        "errors": s3_failed[:20],
                    },
                )

        # Delete Firestore cascade: avances → intervenciones → unidad
        for avance_doc in avance_docs_to_delete:
            avance_doc.reference.delete()
        for intervencion_doc in intervencion_docs_to_delete:
            intervencion_doc.reference.delete()

        deleted_count = 0
        now_iso = datetime.now().isoformat()
        for doc in docs:
            data = doc.to_dict() or {}
            doc.reference.delete()
            deleted_count += 1
            # Audit (F6)
            try:
                db.collection("cambios_implementados_unidades_proyecto").add(
                    {
                        "upid": upid,
                        "accion": "eliminar",
                        "uid": current_user.get("uid"),
                        "email": current_user.get("email"),
                        "nombre_centro_gestor": data.get("nombre_centro_gestor"),
                        "payload_previo": data,
                        "timestamp": now_iso,
                    }
                )
            except Exception as audit_err:
                logger.warning(
                    "eliminar_unidad_proyecto: fallo registrando auditoría: %s",
                    audit_err,
                )

        _invalidate_unidades_cache()
        return create_utf8_response(
            {
                "deleted": True,
                "collection": "unidades_proyecto",
                "upid": upid,
                "deleted_count": deleted_count,
                "intervenciones_deleted": len(intervencion_docs_to_delete),
                "avances_deleted": len(avance_docs_to_delete),
                "s3_files_deleted": len(all_s3_pairs),
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error eliminando unidad de proyecto: {str(e)}"
        )


@router.delete(
    "/eliminar_intervencion",
    tags=["Unidades de Proyecto"],
    summary=" DELETE | Eliminar Intervención",
    dependencies=[Depends(require_unidades("delete"))],
)
@optional_rate_limit("30/minute")
async def eliminar_intervencion(
    request: Request,
    intervencion_id: str = Query(..., description="ID de la intervención a eliminar"),
):
    if not FIREBASE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Firebase not available")

    current_user = getattr(request.state, "current_user", None)
    if current_user is None:
        raise HTTPException(status_code=401, detail="No autenticado")

    try:
        db = get_firestore_client()
        if db is None:
            raise HTTPException(
                status_code=503, detail="No se pudo conectar a Firestore"
            )

        docs = list(
            db.collection("intervenciones_unidades_proyecto")
            .where("intervencion_id", "==", intervencion_id)
            .stream()
        )
        if not docs:
            raise HTTPException(
                status_code=404,
                detail=f"No existe intervención con intervencion_id: {intervencion_id}",
            )

        # Validar centro_gestor (F2)
        for doc in docs:
            data = doc.to_dict() or {}
            enforce_unidades_access(
                current_user,
                "delete:unidades",
                data.get("nombre_centro_gestor"),
            )

        # Initialize S3 client for cascade cleanup
        try:
            from api.utils.s3_document_manager import S3DocumentManager as _S3Mgr, BOTO3_AVAILABLE as _B3

            if not _B3:
                raise HTTPException(status_code=500, detail="boto3 no disponible para eliminar archivos S3 asociados")
            _creds_path = os.getenv("AWS_CREDENTIALS_FILE_UNIDADES_PROYECTO", "credentials/aws_credentials.json")
            _s3_client = _S3Mgr(credentials_path=_creds_path).s3_client
            _default_bucket = os.getenv("S3_BUCKET_UNIDADES_PROYECTO", "unidades-proyecto-documents")
        except HTTPException:
            raise
        except Exception as s3_err:
            raise HTTPException(status_code=500, detail=f"No se pudo inicializar S3 para eliminación en cascada: {s3_err}")

        # Collect S3 objects from all avances of this intervention
        all_s3_pairs: set = set()
        avance_docs_to_delete = list(
            db.collection("avances_unidades_proyecto")
            .where("intervencion_id", "==", intervencion_id)
            .stream()
        )
        for avance_doc in avance_docs_to_delete:
            all_s3_pairs.update(_collect_avance_s3_objects(avance_doc.to_dict() or {}, _default_bucket))

        # Delete S3 objects first (fail fast)
        if all_s3_pairs:
            s3_deleted, s3_failed = _delete_s3_objects_batch(_s3_client, all_s3_pairs)
            if s3_failed:
                raise HTTPException(
                    status_code=500,
                    detail={
                        "message": "No se pudo completar la eliminación en S3. La intervención NO fue eliminada.",
                        "intervencion_id": intervencion_id,
                        "s3_deleted": len(s3_deleted),
                        "s3_failed": len(s3_failed),
                        "errors": s3_failed[:20],
                    },
                )

        # Delete avances in Firestore, then intervention
        for avance_doc in avance_docs_to_delete:
            avance_doc.reference.delete()

        deleted_count = 0
        now_iso = datetime.now().isoformat()
        for doc in docs:
            data = doc.to_dict() or {}
            doc.reference.delete()
            deleted_count += 1
            # Audit (F6)
            try:
                db.collection("cambios_implementados_intervenciones").add(
                    {
                        "intervencion_id": intervencion_id,
                        "accion": "eliminar",
                        "uid": current_user.get("uid"),
                        "email": current_user.get("email"),
                        "nombre_centro_gestor": data.get("nombre_centro_gestor"),
                        "payload_previo": data,
                        "timestamp": now_iso,
                    }
                )
            except Exception as audit_err:
                logger.warning(
                    "eliminar_intervencion: fallo registrando auditoría: %s",
                    audit_err,
                )

        _invalidate_unidades_cache()
        return create_utf8_response(
            {
                "deleted": True,
                "collection": "intervenciones_unidades_proyecto",
                "intervencion_id": intervencion_id,
                "deleted_count": deleted_count,
                "avances_deleted": len(avance_docs_to_delete),
                "s3_files_deleted": len(all_s3_pairs),
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error eliminando intervención: {str(e)}"
        )


@router.post(
    "/registrar_avance_up",
    tags=["Unidades de Proyecto"],
    summary=" POST | Registrar Avance UP",
    dependencies=[Depends(require_unidades("write"))],
)
@optional_rate_limit("30/minute")
async def registrar_avance_up(
    request: Request,
    avance_obra: float = Form(..., description="Avance de obra (admite decimales)"),
    observaciones: str = Form(..., description="Observaciones del avance"),
    intervencion_id: str = Form(..., min_length=1, description="ID de la intervención"),
    soportes: Optional[List[UploadFile]] = File(
        None,
        description=(
            "Archivos de soporte (opcional, se pueden enviar varios mezclados). "
            "Imágenes (.jpg, .jpeg, .png, .bmp, .gif, .webp, .tiff, .heic…) → se comprimen para web y se "
            "guardan en 'unidades_proyecto_photos'. "
            "Documentos (PDF, XLSX, DOCX, CSV…) → se guardan en 'unidades_proyecto_documentos'."
        ),
    ),
):
    """
    ##  POST | Registrar avance de unidad de proyecto

    - Campo unificado `soportes`: acepta imágenes y documentos mezclados, sin límite de cantidad
    - **Imágenes**: detectadas por extensión → compresión JPEG progresiva optimizada para web →
      carpeta `unidades_proyecto_photos/registro_avance/{intervencion_id}/{fecha}/`
    - **Documentos**: cualquier otra extensión → carpeta `unidades_proyecto_documentos/registro_avance/{intervencion_id}/{fecha}/`
    - Genera URLs directas listas para `<img src>`, visor de PDF o descarga en el frontend
    - `registrado_por` se extrae automáticamente del token de sesión
    - Timestamps en hora Colombia (UTC−5)
    """
    if not FIREBASE_AVAILABLE or not SCRIPTS_AVAILABLE:
        raise HTTPException(status_code=503, detail="Firebase or scripts not available")

    try:
        import io
        import unicodedata
        import mimetypes
        from PIL import Image, UnidentifiedImageError
        from api.utils.s3_document_manager import S3DocumentManager, BOTO3_AVAILABLE

        if not BOTO3_AVAILABLE:
            raise HTTPException(
                status_code=500, detail="boto3 no disponible para subida a S3"
            )

        # ── Timezone Colombia (UTC-5, sin DST) ───────────────────────────────
        try:
            from zoneinfo import ZoneInfo

            _co_tz = ZoneInfo("America/Bogota")
        except ImportError:
            from datetime import timezone as _tz, timedelta as _td

            _co_tz = _tz(_td(hours=-5))

        def now_colombia() -> datetime:
            return datetime.now(_co_tz)

        # ── Usuario autenticado ───────────────────────────────────────────────
        registrado_por: str = (
            getattr(request.state, "user_email", None) or "desconocido"
        )

        # ── Extensiones reconocidas como imagen ──────────────────────────────
        _IMAGE_EXTS = {
            ".jpg",
            ".jpeg",
            ".jfif",
            ".pjpeg",
            ".pjp",
            ".png",
            ".bmp",
            ".gif",
            ".webp",
            ".tiff",
            ".tif",
            ".heic",
            ".heif",
            ".ico",
        }

        # ── Content-types para documentos ────────────────────────────────────
        _DOC_CONTENT_TYPES = {
            ".pdf": "application/pdf",
            ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ".xls": "application/vnd.ms-excel",
            ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ".doc": "application/msword",
            ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            ".ppt": "application/vnd.ms-powerpoint",
            ".csv": "text/csv",
            ".txt": "text/plain",
            ".zip": "application/zip",
            ".rar": "application/x-rar-compressed",
            ".7z": "application/x-7z-compressed",
        }

        # ── Prefijos S3 fijos ────────────────────────────────────────────────
        photos_prefix = "unidades_proyecto_photos"
        docs_prefix = "unidades_proyecto_documentos"

        # ── Inicialización S3 ─────────────────────────────────────────────────
        credentials_path = os.getenv(
            "AWS_CREDENTIALS_FILE_UNIDADES_PROYECTO", "credentials/aws_credentials.json"
        )
        bucket = os.getenv("S3_BUCKET_UNIDADES_PROYECTO", "unidades-proyecto-documents")

        try:
            s3_manager = S3DocumentManager(credentials_path=credentials_path)
            s3_manager.bucket_name = bucket
            s3_client = s3_manager.s3_client

            try:
                s3_client.head_bucket(Bucket=bucket)
            except Exception:
                fallback_bucket = s3_manager.credentials.get(
                    "bucket_name", "unidades-proyecto-documents"
                )
                if fallback_bucket and fallback_bucket != bucket:
                    try:
                        s3_client.head_bucket(Bucket=fallback_bucket)
                        bucket = fallback_bucket
                        s3_manager.bucket_name = fallback_bucket
                    except Exception as fallback_error:
                        raise HTTPException(
                            status_code=500,
                            detail=(
                                f"Bucket S3 inválido ({bucket}) y fallback ({fallback_bucket}) "
                                f"no accesible: {str(fallback_error)}"
                            ),
                        )
                else:
                    raise HTTPException(
                        status_code=500,
                        detail=f"Bucket S3 inválido/no accesible: {bucket}",
                    )
        except HTTPException:
            raise
        except Exception as s3_setup_error:
            raise HTTPException(
                status_code=500,
                detail=f"No se pudo inicializar S3 para registrar_avance_up: {str(s3_setup_error)}",
            )

        # ── Helpers ───────────────────────────────────────────────────────────
        def to_ascii_s3_metadata(value: Any, default: str = "") -> str:
            """Convierte valor a ASCII puro apto para metadatos S3 (máx. 200 chars)."""
            text = str(value) if value is not None else default
            text = (
                unicodedata.normalize("NFKD", text)
                .encode("ascii", "ignore")
                .decode("ascii")
            )
            text = "".join(ch for ch in text if 32 <= ord(ch) <= 126).strip()
            return text[:200] if text else default

        def safe_s3_name(name: str) -> str:
            """Normaliza nombre a caracteres ASCII alfanuméricos + '._-' para S3."""
            name = (
                unicodedata.normalize("NFKD", name)
                .encode("ascii", "ignore")
                .decode("ascii")
            )
            name = "".join(ch for ch in name if ch.isalnum() or ch in "._-")
            return name.strip("._-") or "archivo"

        # ── Timestamps fijos para este registro ──────────────────────────────
        now = now_colombia()
        date_str = now.strftime("%Y-%m-%d")  # 2026-03-07  (carpeta por fecha)
        ts_safe = now.strftime(
            "%Y%m%d_%H%M%S"
        )  # 20260307_143000 (en el nombre del archivo)
        ts_human = now.strftime(
            "%d/%m/%Y %H:%M:%S"
        )  # 07/03/2026 14:30:00 (metadatos S3)
        now_iso = now.isoformat()  # 2026-03-07T14:30:00-05:00 (Firestore)
        presigned_expiration = _s3_presigned_expiration()

        # ── Procesamiento de archivos (optimizado y concurrente) ──────────────
        soportes_registros: list = []
        imagenes_urls: list = []
        documentos_urls: list = []
        fallidos: list = []

        photos_folder = f"{photos_prefix}/registro_avance/{intervencion_id}/{date_str}/"
        docs_folder = f"{docs_prefix}/registro_avance/{intervencion_id}/{date_str}/"

        soporte_items: List[Dict[str, Any]] = []
        img_counter = 0
        doc_counter = 0

        for idx, archivo in enumerate(soportes or []):
            original_name = archivo.filename or f"soporte_{idx + 1}"
            _, ext = os.path.splitext(original_name)
            ext_lower = ext.lower()
            is_image = ext_lower in _IMAGE_EXTS

            try:
                file_bytes = await archivo.read()
                if not file_bytes:
                    raise ValueError("El archivo está vacío (0 bytes)")

                if is_image:
                    img_counter += 1
                    img_seq = img_counter
                    doc_seq = None
                else:
                    doc_counter += 1
                    doc_seq = doc_counter
                    img_seq = None

                soporte_items.append(
                    {
                        "indice": idx + 1,
                        "original_name": original_name,
                        "ext_lower": ext_lower,
                        "is_image": is_image,
                        "file_bytes": file_bytes,
                        "img_seq": img_seq,
                        "doc_seq": doc_seq,
                    }
                )
            except Exception as read_err:
                fallidos.append(
                    {
                        "indice": idx + 1,
                        "filename": original_name,
                        "error": str(read_err),
                    }
                )

        def _process_and_upload_soporte(item: Dict[str, Any]) -> Dict[str, Any]:
            original_name = item["original_name"]
            ext_lower = item["ext_lower"]
            is_image = item["is_image"]
            file_bytes = item["file_bytes"]
            indice = item["indice"]

            if is_image:
                try:
                    image = Image.open(io.BytesIO(file_bytes))
                except UnidentifiedImageError:
                    raise ValueError(
                        f"No se reconoce como imagen válida: {original_name}"
                    )

                if image.mode != "RGB":
                    image = image.convert("RGB")

                image.thumbnail((1280, 1280), Image.Resampling.LANCZOS)

                buf = io.BytesIO()
                image.save(
                    buf,
                    format="JPEG",
                    quality=72,
                    optimize=True,
                    progressive=True,
                    subsampling=2,
                )
                upload_bytes = buf.getvalue()
                content_type = "image/jpeg"
                s3_filename = f"{intervencion_id}_{ts_safe}_{item['img_seq']:03d}.jpg"
                s3_key = f"{photos_folder}{s3_filename}"
                content_disposition = "inline"
                soporte_tipo = "imagen"
            else:
                content_type = _DOC_CONTENT_TYPES.get(
                    ext_lower,
                    mimetypes.guess_type(original_name)[0]
                    or "application/octet-stream",
                )
                upload_bytes = file_bytes
                base_name = safe_s3_name(os.path.splitext(original_name)[0])
                s3_filename = f"{intervencion_id}_{ts_safe}_{item['doc_seq']:03d}_{base_name}{ext_lower}"
                s3_key = f"{docs_folder}{s3_filename}"
                content_disposition = (
                    "inline"
                    if ext_lower == ".pdf"
                    else f'attachment; filename="{s3_filename}"'
                )
                soporte_tipo = "documento"

            s3_client.put_object(
                Bucket=bucket,
                Key=s3_key,
                Body=upload_bytes,
                ContentType=content_type,
                ContentDisposition=content_disposition,
                Metadata={
                    "intervencion-id": to_ascii_s3_metadata(
                        intervencion_id, "sin_intervencion"
                    ),
                    "registrado-por": to_ascii_s3_metadata(
                        registrado_por, "desconocido"
                    ),
                    "timestamp": to_ascii_s3_metadata(ts_human, ""),
                    "original-filename": to_ascii_s3_metadata(
                        original_name, "sin_nombre"
                    ),
                    "tipo": soporte_tipo,
                },
            )

            url_directa = f"https://{bucket}.s3.amazonaws.com/{s3_key}"
            url_presigned = None
            if _s3_presigned_enabled():
                try:
                    url_presigned = s3_client.generate_presigned_url(
                        "get_object",
                        Params={"Bucket": bucket, "Key": s3_key},
                        ExpiresIn=presigned_expiration,
                    )
                except Exception:
                    url_presigned = None
            final_url = url_presigned or url_directa
            return {
                "indice": indice,
                "tipo": soporte_tipo,
                "nombre_original": original_name,
                "extension": ext_lower,
                "content_type": content_type,
                "bucket": bucket,
                "s3_key": s3_key,
                "url_directa": url_directa,
                "url_presigned": url_presigned,
                "url": final_url,
                "uploaded_at": now_iso,
            }

        max_parallel_uploads = int(
            os.getenv("REGISTRAR_AVANCE_UP_UPLOAD_CONCURRENCY", "4")
        )
        upload_semaphore = asyncio.Semaphore(max(1, max_parallel_uploads))

        async def _run_upload(item: Dict[str, Any]) -> Dict[str, Any]:
            async with upload_semaphore:
                return await asyncio.to_thread(_process_and_upload_soporte, item)

        upload_tasks = [_run_upload(item) for item in soporte_items]
        upload_results = await asyncio.gather(*upload_tasks, return_exceptions=True)

        for item, result in zip(soporte_items, upload_results):
            if isinstance(result, Exception):
                fallidos.append(
                    {
                        "indice": item["indice"],
                        "filename": item["original_name"],
                        "error": str(result),
                    }
                )
                continue

            soportes_registros.append(result)
            if result["tipo"] == "imagen":
                imagenes_urls.append(result["url"])
            else:
                documentos_urls.append(result["url"])

        soportes_registros.sort(key=lambda x: x.get("indice", 0))

        # ── Firestore ─────────────────────────────────────────────────────────
        db = get_firestore_client()
        if db is None:
            raise HTTPException(
                status_code=503, detail="No se pudo conectar a Firestore"
            )

        doc_id = str(uuid.uuid4())

        avance_payload = {
            "id": doc_id,
            "avance_obra": avance_obra,
            "observaciones": observaciones,
            "intervencion_id": intervencion_id,
            "registrado_por": registrado_por,
            # Índice completo: cada archivo con su url, tipo, s3_key, content_type, etc.
            "soportes": soportes_registros,
            # Listas planas de URLs para consultas/filtros rápidos en Firestore
            "imagenes_urls": imagenes_urls,
            "documentos_urls": documentos_urls,
            # Contadores
            "total_soportes": len(soportes or []),
            "total_imagenes": len(imagenes_urls),
            "total_documentos": len(documentos_urls),
            "total_fallidos": len(fallidos),
            "fallidos": fallidos,
            # Timestamps en hora Colombia
            "created_at": now_iso,
            "updated_at": now_iso,
        }

        db.collection("avances_unidades_proyecto").document(doc_id).set(avance_payload)

        # Actualizar caché de avance_obra en la intervención correspondiente
        interv_docs = list(
            db.collection("intervenciones_unidades_proyecto")
            .where("intervencion_id", "==", intervencion_id)
            .limit(1)
            .stream()
        )
        if interv_docs:
            interv_docs[0].reference.update(
                {"avance_obra": avance_obra, "updated_at": now_iso}
            )

        return create_utf8_response(
            {
                "id": doc_id,
                "intervencion_id": intervencion_id,
                "avance_obra": avance_obra,
                "observaciones": observaciones,
                "registrado_por": registrado_por,
                "soportes": soportes_registros,
                "imagenes_urls": imagenes_urls,
                "documentos_urls": documentos_urls,
                "total_soportes": len(soportes or []),
                "total_imagenes": len(imagenes_urls),
                "total_documentos": len(documentos_urls),
                "total_fallidos": len(fallidos),
                "fallidos": fallidos,
                "timestamp": now_iso,
            }
        )

    except HTTPException:
        raise
    except ImportError as import_error:
        raise HTTPException(
            status_code=500,
            detail=f"Dependencia faltante para subida de archivos: {str(import_error)}",
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error registrando avance UP: {str(e)}"
        )


# ============================================================================
# ENDPOINT: SINCRONIZACIÓN INCREMENTAL DE LINKS SECOP PARA INTERVENCIONES
# ============================================================================


@router.post(
    "/intervenciones/sincronizar-links-secop",
    tags=["Unidades de Proyecto"],
    summary=" POST | Sincronizar Links SECOP de Intervenciones (incremental)",
    dependencies=[Depends(require_unidades("write"))],
)
@optional_rate_limit("5/minute")
async def sincronizar_links_secop_intervenciones(request: Request):
    """
    ##  POST | Sincronizar Links SECOP de Intervenciones (carga incremental)

    Lee `referencia_proceso` y `referencia_contrato` de cada documento en
    `intervenciones_unidades_proyecto`, consulta en **paralelo** las APIs de SECOP
    (procesos: `p6dx-8zbt` y contratos: `jbjy-vk9h`) para obtener los links públicos
    de cada referencia y guarda los resultados en la colección
    `intervenciones_unidades_proyecto_links`.

    ###  Carga incremental:
    Solo procesa documentos que:
    - **No** existen todavía en `intervenciones_unidades_proyecto_links`, **o**
    - Han cambiado su `referencia_proceso` o `referencia_contrato` respecto al
      registro ya guardado.

    Los documentos sin cambios se omiten para optimizar el tiempo de respuesta.

    ###  Estructura guardada en `intervenciones_unidades_proyecto_links`:
    Incluye **todos** los campos originales de `intervenciones_unidades_proyecto`
    más los campos adicionales de links SECOP:
    ```json
    {
        "upid": "UNP-1",
        "intervencion_id": "INT-001",
        "avance_obra": 50.0,
        "bpin": 12345,
        "cantidad": 10,
        "clase_up": "...",
        "estado": "En ejecución",
        "fecha_fin": "...",
        "fecha_inicio": "...",
        "fuente_financiacion": "...",
        "identificador": "...",
        "nombre_centro_gestor": "...",
        "presupuesto_base": 1000000,
        "tipo_intervencion": "...",
        "unidad": "...",
        "url_proceso": "...",
        "referencia_proceso": "CO1.PCCNTR.123456",
        "link_proceso": "https://www.secop.gov.co/...",
        "referencia_contrato": "CO1.BDOS.123456",
        "link_contrato": "https://www.secop.gov.co/...",
        "fecha_sincronizacion": "2026-03-18T10:00:00"
    }
    ```

    ###  Respuesta:
    ```json
    {
        "success": true,
        "procesados": 5,
        "omitidos_sin_cambios": 20,
        "omitidos_sin_referencias": 3,
        "nuevos": 3,
        "actualizados": 2,
        "errores": 0,
        "detalles_errores": [],
        "timestamp": "2026-03-18T10:00:00"
    }
    ```
    """
    if not FIREBASE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Firebase not available")

    try:
        from sodapy import Socrata
    except ImportError:
        raise HTTPException(
            status_code=500,
            detail="sodapy no está disponible. Instala con: pip install sodapy",
        )

    db = get_firestore_client()
    if db is None:
        raise HTTPException(status_code=503, detail="No se pudo conectar a Firestore")

    import time as _time

    SECOP_DOMAIN = "www.datos.gov.co"
    DATASET_PROCESOS = "p6dx-8zbt"
    DATASET_CONTRATOS = "jbjy-vk9h"
    MAX_PARALELO = (
        10  # Consultas simultáneas a SECOP (aumentado con app_token autenticado)
    )
    PAUSA_ENTRE_LOTES = 0.2  # Segundos de espera entre lotes (reducido con app_token)
    TIMEOUT_INTERNO = (
        540.0  # 9 minutos — detenerse antes del timeout del middleware (600s)
    )
    _inicio_total = _time.monotonic()

    # ── 1. Cargar estado actual de la colección de links ─────────────────────
    links_col = db.collection("intervenciones_unidades_proyecto_links")
    links_existentes: Dict[str, Dict[str, Any]] = {}
    for doc in await asyncio.to_thread(lambda: list(links_col.stream())):
        data = doc.to_dict() or {}
        intervencion_id_key = data.get("intervencion_id") or doc.id
        links_existentes[intervencion_id_key] = {
            "doc_id": doc.id,
            "referencia_proceso": data.get("referencia_proceso", ""),
            "referencia_contrato": data.get("referencia_contrato", ""),
            "link_proceso": data.get("link_proceso", ""),
            "link_contrato": data.get("link_contrato", ""),
        }

    # ── 2. Cargar intervenciones ──────────────────────────────────────────────
    intervenciones_docs = await asyncio.to_thread(
        lambda: list(db.collection("intervenciones_unidades_proyecto").stream())
    )

    # ── 3. Filtrar cuáles necesitan procesarse (lógica incremental) ──────────
    a_procesar = []
    omitidos_sin_cambios = 0
    omitidos_sin_referencias = 0

    # Valores que no son referencias SECOP válidas
    _REFS_INVALIDAS = {
        "",
        "n/a",
        "na",
        "sin referencia",
        "sin proceso",
        "sin contrato",
        "null",
        "none",
        "nan",
        "-",
        "--",
        "0",
        "pendiente",
        "no aplica",
        "no tiene",
        "sin asignar",
        "por definir",
        "sin dato",
        "sin datos",
    }

    def _es_referencia_valida(valor) -> str:
        """Retorna la referencia limpia si es válida, o cadena vacía si no."""
        if valor is None:
            return ""
        # Si es lista, tomar el primer elemento no vacío
        if isinstance(valor, list):
            for v in valor:
                resultado = _es_referencia_valida(v)
                if resultado:
                    return resultado
            return ""
        # Convertir a string y limpiar
        texto = str(valor).strip()
        if texto.lower() in _REFS_INVALIDAS:
            return ""
        # Si contiene comas → múltiples valores concatenados → inválido
        if "," in texto:
            return ""
        # Debe tener al menos 3 caracteres para ser una referencia real
        if len(texto) < 3:
            return ""
        return texto

    for doc in intervenciones_docs:
        data = doc.to_dict() or {}
        intervencion_id = data.get("intervencion_id") or doc.id
        upid = data.get("upid", "")
        ref_proceso = _es_referencia_valida(data.get("referencia_proceso"))
        ref_contrato = _es_referencia_valida(data.get("referencia_contrato"))
        url_proceso_original = str(data.get("url_proceso", "") or "").strip()

        # Sin ninguna referencia y sin url_proceso → no hay nada que buscar
        if not ref_proceso and not ref_contrato and not url_proceso_original:
            omitidos_sin_referencias += 1
            continue

        existente = links_existentes.get(intervencion_id)
        if existente:
            # Solo procesar si alguna referencia cambió
            if (
                existente["referencia_proceso"] == ref_proceso
                and existente["referencia_contrato"] == ref_contrato
            ):
                omitidos_sin_cambios += 1
                continue

        # Determinar qué links se pueden reutilizar (referencia no cambió y ya tiene link)
        link_proceso_cache = ""
        link_contrato_cache = ""
        if existente:
            if (
                existente["referencia_proceso"] == ref_proceso
                and existente["link_proceso"]
            ):
                link_proceso_cache = existente["link_proceso"]
            if (
                existente["referencia_contrato"] == ref_contrato
                and existente["link_contrato"]
            ):
                link_contrato_cache = existente["link_contrato"]

        # Guardar TODOS los campos originales del documento
        campos_originales = {}
        for key, value in data.items():
            campos_originales[key] = value

        a_procesar.append(
            {
                "doc_id": doc.id,
                "intervencion_id": intervencion_id,
                "upid": upid,
                "referencia_proceso": ref_proceso,
                "referencia_contrato": ref_contrato,
                "url_proceso_original": url_proceso_original,
                "link_doc_id": existente["doc_id"] if existente else None,
                "link_proceso_cache": link_proceso_cache,
                "link_contrato_cache": link_contrato_cache,
                "campos_originales": campos_originales,
            }
        )

    # ── 4. Consultar SECOP por lotes con paralelismo controlado ──────────────
    nuevos = 0
    actualizados = 0
    errores = 0
    detalles_errores = []

    def _extraer_url(campo_urlproceso) -> str:
        """Extrae URL del campo urlproceso que puede ser dict {'url': '...'} o string."""
        if isinstance(campo_urlproceso, dict):
            return campo_urlproceso.get("url", "") or ""
        if isinstance(campo_urlproceso, str):
            return campo_urlproceso
        return ""

    def _buscar_en_dataset_sync(dataset: str, campo_where: str, referencia: str) -> str:
        """Consulta urlproceso en un dataset SECOP específico."""
        try:
            client = Socrata(
                SECOP_DOMAIN, os.environ.get("SOCRATA_APP_TOKEN"), timeout=30
            )
            results = client.get(
                dataset,
                where=f"{campo_where}='{referencia}'",
                limit=1,
            )
            client.close()
            if results:
                url = _extraer_url(results[0].get("urlproceso"))
                if url:
                    return url
        except Exception as exc:
            logger.warning(
                f"[ERROR] Error consultando SECOP {dataset}/{campo_where}='{referencia}': {exc}"
            )
        return ""

    def _get_link_proceso_sync(referencia: str) -> str:
        """Busca link de proceso en ambos datasets SECOP para maximizar resultados."""
        if not referencia:
            return ""
        # 1) Intento principal: buscar en dataset de procesos
        logger.info(f" SECOP Procesos: buscando referencia_del_proceso='{referencia}'")
        url = _buscar_en_dataset_sync(
            DATASET_PROCESOS, "referencia_del_proceso", referencia
        )
        if url:
            logger.info(
                f"[OK] SECOP Procesos: {referencia} → {url[:80]}{'...' if len(url) > 80 else ''}"
            )
            return url
        # 2) Fallback: buscar la misma referencia en dataset de contratos
        logger.info(
            f" SECOP Fallback: buscando referencia_del_contrato='{referencia}' en contratos"
        )
        url = _buscar_en_dataset_sync(
            DATASET_CONTRATOS, "referencia_del_contrato", referencia
        )
        if url:
            logger.info(
                f"[OK] SECOP Fallback Contratos: {referencia} → {url[:80]}{'...' if len(url) > 80 else ''}"
            )
            return url
        logger.info(
            f"[WARNING] SECOP Procesos: {referencia} → sin resultados en ambos datasets"
        )
        return ""

    def _get_link_contrato_sync(referencia: str) -> str:
        """Busca link de contrato en ambos datasets SECOP para maximizar resultados."""
        if not referencia:
            return ""
        # 1) Intento principal: buscar en dataset de contratos
        logger.info(
            f" SECOP Contratos: buscando referencia_del_contrato='{referencia}'"
        )
        url = _buscar_en_dataset_sync(
            DATASET_CONTRATOS, "referencia_del_contrato", referencia
        )
        if url:
            logger.info(
                f"[OK] SECOP Contratos: {referencia} → {url[:80]}{'...' if len(url) > 80 else ''}"
            )
            return url
        # 2) Fallback: buscar la misma referencia en dataset de procesos
        logger.info(
            f" SECOP Fallback: buscando referencia_del_proceso='{referencia}' en procesos"
        )
        url = _buscar_en_dataset_sync(
            DATASET_PROCESOS, "referencia_del_proceso", referencia
        )
        if url:
            logger.info(
                f"[OK] SECOP Fallback Procesos: {referencia} → {url[:80]}{'...' if len(url) > 80 else ''}"
            )
            return url
        logger.info(
            f"[WARNING] SECOP Contratos: {referencia} → sin resultados en ambos datasets"
        )
        return ""

    llamadas_secop_ahorradas = 0

    async def _procesar_item(item: dict) -> dict:
        """Consulta proceso y contrato en paralelo, reutilizando links ya resueltos."""
        nonlocal llamadas_secop_ahorradas
        tareas = []
        campos = []  # Para saber qué posición corresponde a qué campo

        # Solo consultar SECOP si no hay link cacheado
        if item["link_proceso_cache"]:
            link_proceso = item["link_proceso_cache"]
            llamadas_secop_ahorradas += 1
        else:
            tareas.append(
                asyncio.to_thread(_get_link_proceso_sync, item["referencia_proceso"])
            )
            campos.append("proceso")
            link_proceso = None

        if item["link_contrato_cache"]:
            link_contrato = item["link_contrato_cache"]
            llamadas_secop_ahorradas += 1
        else:
            tareas.append(
                asyncio.to_thread(_get_link_contrato_sync, item["referencia_contrato"])
            )
            campos.append("contrato")
            link_contrato = None

        if tareas:
            resultados = await asyncio.gather(*tareas)
            for campo, valor in zip(campos, resultados):
                if campo == "proceso":
                    link_proceso = valor
                else:
                    link_contrato = valor

        # Fallback: usar url_proceso del documento original si SECOP no devolvió link
        if not link_proceso and item.get("url_proceso_original"):
            url_orig = item["url_proceso_original"]
            if url_orig.startswith("http"):
                link_proceso = url_orig
                logger.info(
                    f" Fallback url_proceso original: {item['intervencion_id']} → {url_orig[:80]}"
                )

        return {**item, "link_proceso": link_proceso, "link_contrato": link_contrato}

    # Procesar en lotes de MAX_PARALELO para no saturar SECOP
    completado = True
    pendientes = len(a_procesar)
    lotes_procesados = 0
    motivo_corte = None

    try:
        for lote_inicio in range(0, len(a_procesar), MAX_PARALELO):
            # ── Verificar si queda tiempo suficiente antes de iniciar otro lote ──
            elapsed = _time.monotonic() - _inicio_total
            if elapsed >= TIMEOUT_INTERNO:
                completado = False
                pendientes = len(a_procesar) - lote_inicio
                motivo_corte = f"Tiempo límite interno alcanzado ({elapsed:.1f}s/{TIMEOUT_INTERNO}s)"
                logger.warning(
                    f"⏱ {motivo_corte}. Guardados hasta ahora: {nuevos} nuevos, {actualizados} actualizados."
                )
                break

            lote = a_procesar[lote_inicio : lote_inicio + MAX_PARALELO]

            resultados_lote = await asyncio.gather(
                *[_procesar_item(item) for item in lote],
                return_exceptions=True,
            )

            for item, resultado in zip(lote, resultados_lote):
                if isinstance(resultado, Exception):
                    errores += 1
                    detalles_errores.append(
                        {
                            "intervencion_id": item["intervencion_id"],
                            "error": str(resultado),
                        }
                    )
                    logger.error(
                        f"[ERROR] Error sincronizando links SECOP para {item['intervencion_id']}: {resultado}"
                    )
                    continue

                try:
                    # Partir de TODOS los campos originales del documento
                    payload = dict(resultado.get("campos_originales", {}))
                    # Sobreescribir/agregar los campos de links y sincronización
                    payload["upid"] = resultado["upid"]
                    payload["intervencion_id"] = resultado["intervencion_id"]
                    payload["referencia_proceso"] = resultado["referencia_proceso"]
                    payload["link_proceso"] = resultado["link_proceso"]
                    payload["referencia_contrato"] = resultado["referencia_contrato"]
                    payload["link_contrato"] = resultado["link_contrato"]
                    payload["fecha_sincronizacion"] = datetime.now().isoformat()

                    if resultado["link_doc_id"]:
                        links_col.document(resultado["link_doc_id"]).set(payload)
                        actualizados += 1
                    else:
                        links_col.document(resultado["intervencion_id"]).set(payload)
                        nuevos += 1
                except Exception as exc:
                    errores += 1
                    detalles_errores.append(
                        {
                            "intervencion_id": resultado["intervencion_id"],
                            "error": str(exc),
                        }
                    )
                    logger.error(
                        f"[ERROR] Error guardando link para {resultado['intervencion_id']}: {exc}"
                    )

            lotes_procesados += 1
            pendientes = len(a_procesar) - (lote_inicio + len(lote))

            # Pausa entre lotes para respetar rate limits de SECOP sin app_token
            if lote_inicio + MAX_PARALELO < len(a_procesar):
                await asyncio.sleep(PAUSA_ENTRE_LOTES)

    except Exception as exc_global:
        completado = False
        motivo_corte = f"Error inesperado: {str(exc_global)[:200]}"
        logger.error(f"[ERROR] Error global en sincronización SECOP: {exc_global}")

    # ── SIEMPRE devolver métricas, completado o no ───────────────────────────
    elapsed_total = round(_time.monotonic() - _inicio_total, 2)
    procesados_efectivos = nuevos + actualizados + errores

    return create_utf8_response(
        {
            "success": completado and errores == 0,
            "completado": completado,
            "motivo_corte": motivo_corte,
            "total_a_procesar": len(a_procesar),
            "procesados": procesados_efectivos,
            "pendientes": pendientes if not completado else 0,
            "omitidos_sin_cambios": omitidos_sin_cambios,
            "omitidos_sin_referencias": omitidos_sin_referencias,
            "nuevos": nuevos,
            "actualizados": actualizados,
            "errores": errores,
            "llamadas_secop_ahorradas": llamadas_secop_ahorradas,
            "lotes_procesados": lotes_procesados,
            "tiempo_ejecucion_seg": elapsed_total,
            "detalles_errores": detalles_errores[:50],
            "timestamp": datetime.now().isoformat(),
            "nota": (
                "Ejecución parcial — vuelva a llamar para continuar con los pendientes (carga incremental)."
                if not completado
                else "Sincronización completa."
            ),
        }
    )


# ============================================================================
# ENDPOINT: LEER LINKS SECOP DE INTERVENCIONES
# ============================================================================


@router.get(
    "/intervenciones/links-secop",
    tags=["Unidades de Proyecto"],
    summary=" GET | Leer Links SECOP de Intervenciones",
    dependencies=[Depends(require_unidades("read"))],
)
@optional_rate_limit("30/minute")
async def leer_links_secop_intervenciones(
    request: Request,
    nombre_centro_gestor: Optional[str] = Query(
        None, description="Filtrar por nombre del centro gestor"
    ),
    referencia_proceso: Optional[str] = Query(
        None, description="Filtrar por referencia de proceso"
    ),
    referencia_contrato: Optional[str] = Query(
        None, description="Filtrar por referencia de contrato"
    ),
):
    """
    ##  GET | Leer Links SECOP de Intervenciones

    Consulta los datos almacenados en `intervenciones_unidades_proyecto_links`.
    Retorna todos los registros o filtra opcionalmente por:
    - `nombre_centro_gestor`
    - `referencia_proceso`
    - `referencia_contrato`

    Los filtros son opcionales y se pueden combinar.
    """
    if not FIREBASE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Firebase not available")

    # F2: aplicar scoping por centro gestor según el rol del usuario.
    current_user = getattr(request.state, "current_user", None)
    if current_user is not None:
        nombre_centro_gestor = enforce_unidades_access(
            current_user, "read:unidades", nombre_centro_gestor
        )

    db = get_firestore_client()
    if db is None:
        raise HTTPException(status_code=503, detail="No se pudo conectar a Firestore")

    try:
        query = db.collection("intervenciones_unidades_proyecto_links")

        if nombre_centro_gestor:
            query = query.where("nombre_centro_gestor", "==", nombre_centro_gestor)
        if referencia_proceso:
            query = query.where("referencia_proceso", "==", referencia_proceso)
        if referencia_contrato:
            query = query.where("referencia_contrato", "==", referencia_contrato)

        docs = query.stream()
        data = []
        con_link_proceso = 0
        sin_link_proceso = 0
        con_link_contrato = 0
        sin_link_contrato = 0

        for doc in docs:
            record = doc.to_dict() or {}
            record["doc_id"] = doc.id

            lp = record.get("link_proceso") or ""
            lc = record.get("link_contrato") or ""
            if isinstance(lp, dict):
                lp = lp.get("url", "")
            if isinstance(lc, dict):
                lc = lc.get("url", "")
            lp = str(lp).strip()
            lc = str(lc).strip()
            if lp:
                con_link_proceso += 1
            else:
                sin_link_proceso += 1
            if lc:
                con_link_contrato += 1
            else:
                sin_link_contrato += 1

            data.append(clean_firebase_data(record))

        # Ordenar de mayor a menor por upid
        data.sort(key=lambda r: r.get("upid") or "", reverse=True)

        return create_utf8_response(
            {
                "success": True,
                "data": data,
                "count": len(data),
                "metricas_links": {
                    "con_link_proceso": con_link_proceso,
                    "sin_link_proceso": sin_link_proceso,
                    "con_link_contrato": con_link_contrato,
                    "sin_link_contrato": sin_link_contrato,
                },
                "filtros_aplicados": {
                    "nombre_centro_gestor": nombre_centro_gestor,
                    "referencia_proceso": referencia_proceso,
                    "referencia_contrato": referencia_contrato,
                },
            }
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error consultando intervenciones_unidades_proyecto_links: {str(e)}",
        )


# ============================================================================
# ENDPOINT: GEOMETRY — GeoJSON FeatureCollection
# ============================================================================


@router.get(
    "/unidades-proyecto/geometry",
    tags=["Unidades de Proyecto"],
    summary="GET | Geometrías GeoJSON de Unidades de Proyecto",
    dependencies=[Depends(require_unidades("read"))],
)
@optional_rate_limit("60/minute")
async def get_geometry_unidades_proyecto(
    request: Request,
    upid: Optional[str] = Query(None, description="Filtrar por UPID específico"),
    nombre_centro_gestor: Optional[str] = Query(
        None, description="Filtrar por centro gestor"
    ),
    estado: Optional[str] = Query(None, description="Filtrar por estado"),
    tipo_intervencion: Optional[str] = Query(
        None, description="Filtrar por tipo de intervención"
    ),
    clase_up: Optional[str] = Query(None, description="Filtrar por clase UP"),
    frente_activo: Optional[str] = Query(None, description="Filtrar por frente activo"),
    limit: Optional[int] = Query(None, description="Limitar número de features"),
):
    """
    ## GET | Geometrías GeoJSON de Unidades de Proyecto

    Retorna un GeoJSON FeatureCollection con las geometrías de las unidades de proyecto.
    Soporta filtros opcionales incluyendo `frente_activo`.
    """
    if not SCRIPTS_AVAILABLE or get_unidades_proyecto_geometry is None:
        raise HTTPException(
            status_code=503, detail="Scripts de unidades proyecto no disponibles"
        )

    current_user = getattr(request.state, "current_user", None) or {}
    nombre_centro_gestor = enforce_unidades_access(
        current_user, "read:unidades", nombre_centro_gestor
    )

    filters: Dict[str, Any] = {}
    if upid:
        filters["upid"] = upid
    if nombre_centro_gestor:
        filters["nombre_centro_gestor"] = nombre_centro_gestor
    if estado:
        filters["estado"] = estado
    if tipo_intervencion:
        filters["tipo_intervencion"] = tipo_intervencion
    if clase_up:
        filters["clase_up"] = clase_up
    if frente_activo:
        filters["frente_activo"] = frente_activo

    try:
        result = await get_unidades_proyecto_geometry(filters=filters or None)

        features = result.get("features", [])
        if limit and limit > 0:
            features = features[:limit]

        return create_utf8_response(
            {
                "type": "FeatureCollection",
                "features": features,
                "total_features": len(features),
                "filtros_aplicados": filters,
            }
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error obteniendo geometrías: {str(e)}"
        )


# ============================================================================
# ENDPOINT: ATTRIBUTES — Tabla de atributos
# ============================================================================


@router.get(
    "/unidades-proyecto/attributes",
    tags=["Unidades de Proyecto"],
    summary="GET | Atributos tabulares de Unidades de Proyecto",
    dependencies=[Depends(require_unidades("read"))],
)
@optional_rate_limit("60/minute")
async def get_attributes_unidades_proyecto(
    request: Request,
    upid: Optional[str] = Query(None, description="Filtrar por UPID específico"),
    nombre_centro_gestor: Optional[str] = Query(
        None, description="Filtrar por centro gestor"
    ),
    estado: Optional[str] = Query(None, description="Filtrar por estado"),
    tipo_intervencion: Optional[str] = Query(
        None, description="Filtrar por tipo de intervención"
    ),
    clase_up: Optional[str] = Query(None, description="Filtrar por clase UP"),
    frente_activo: Optional[str] = Query(None, description="Filtrar por frente activo"),
    limit: Optional[int] = Query(None, description="Limitar número de registros"),
    offset: Optional[int] = Query(None, description="Número de registros a omitir"),
):
    """
    ## GET | Atributos tabulares de Unidades de Proyecto

    Retorna los atributos tabulares de las unidades de proyecto.
    Soporta filtros opcionales incluyendo `frente_activo`.
    """
    if not SCRIPTS_AVAILABLE or get_unidades_proyecto_attributes is None:
        raise HTTPException(
            status_code=503, detail="Scripts de unidades proyecto no disponibles"
        )

    current_user = getattr(request.state, "current_user", None) or {}
    nombre_centro_gestor = enforce_unidades_access(
        current_user, "read:unidades", nombre_centro_gestor
    )

    filters: Dict[str, Any] = {}
    if upid:
        filters["upid"] = upid
    if nombre_centro_gestor:
        filters["nombre_centro_gestor"] = nombre_centro_gestor
    if estado:
        filters["estado"] = estado
    if tipo_intervencion:
        filters["tipo_intervencion"] = tipo_intervencion
    if clase_up:
        filters["clase_up"] = clase_up
    if frente_activo:
        filters["frente_activo"] = frente_activo

    try:
        result = await get_unidades_proyecto_attributes(
            filters=filters or None,
            limit=limit,
            offset=offset,
        )

        data = result.get("data", [])
        return create_utf8_response(
            {
                "success": True,
                "data": data,
                "count": len(data),
                "filtros_aplicados": filters,
            }
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error obteniendo atributos: {str(e)}"
        )


# ============================================================================
# ENDPOINT: FILTERS — Opciones de filtros dinámicos
# ============================================================================

_FILTERABLE_FIELDS = [
    "estado",
    "tipo_intervencion",
    "clase_up",
    "nombre_centro_gestor",
    "frente_activo",
    "comuna_corregimiento",
    "barrio_vereda",
]


@router.get(
    "/unidades-proyecto/filters",
    tags=["Unidades de Proyecto"],
    summary="GET | Opciones de filtros disponibles",
    dependencies=[Depends(require_unidades("read"))],
)
@optional_rate_limit("60/minute")
async def get_filters_unidades_proyecto(
    request: Request,
    field: Optional[str] = Query(
        None,
        description="Campo específico para obtener valores únicos",
        enum=_FILTERABLE_FIELDS,
    ),
    limit: Optional[int] = Query(None, description="Limitar valores únicos por campo"),
):
    """
    ## GET | Opciones de filtros disponibles para Unidades de Proyecto

    Retorna los valores únicos disponibles para usar como filtros.
    Si se especifica `field`, retorna solo los valores de ese campo.
    Siempre incluye `frentes_activos` en el resultado completo.
    """
    if not SCRIPTS_AVAILABLE or get_filter_options is None:
        raise HTTPException(
            status_code=503, detail="Scripts de unidades proyecto no disponibles"
        )

    try:
        result = await get_filter_options(field=field, limit=limit)

        filters = result.get("filters", result.get("data", {}))

        # Garantizar que frente_activo esté presente en el resultado completo
        if (
            field is None
            and "frentes_activos" not in filters
            and "frente_activo" not in filters
        ):
            filters["frentes_activos"] = []

        return create_utf8_response(
            {
                "success": True,
                "filters": filters,
                "field_requested": field,
            }
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error obteniendo opciones de filtros: {str(e)}"
        )


# ============================================================================
# IMPORTACIÓN GEOESPACIAL — Unidades de Proyecto e Intervenciones
# Los archivos se parsean en el frontend (GeoJSON nativo); el backend solo
# valida el mapping y, si se confirma, crea los registros en Firestore.
# ============================================================================

# Nota: los shapefiles truncan los nombres de columna a 10 caracteres (límite DBF),
# por eso se incluyen las formas truncadas (p.ej. "PRESUPUEST", "AVANCE_OBR").
_UP_FIELD_ALIASES: Dict[str, List[str]] = {
    "nombre_up": ["NOMBRE", "NOM", "NAME", "NOMBRE_UP", "NOM_UP", "PROYECTO"],
    "nombre_up_detalle": ["DETALLE", "DESCRIPCION", "DESCRIPCIÓN", "DESC", "NOM_DET", "NOMBRE_UP_"],
    "tipo_equipamiento": ["TIPO_EQ", "EQUIPAMIENTO", "TIPO_EQUIPAMIENTO", "TIPO_EQUIP"],
    "clase_up": ["CLASE", "CLASE_UP", "CLASE_OBRA"],
    "tipo_intervencion": ["TIPO_INT", "TIPO_INTERV", "TIPO_INTERVENCION", "T_INTERV", "TIPO_INTER"],
    "estado": ["ESTADO", "STATUS", "ESTADO_UP"],
    "presupuesto_base": ["PRESUPUESTO", "PRESUP", "VALOR", "COSTO", "PRESUPUESTO_BASE", "PRESUPUEST"],
    "avance_obra": ["AVANCE", "AVANCE_OBRA", "PROGRESO", "PORCENTAJE", "AVANCE_OBR"],
    "fuente_financiacion": ["FUENTE", "FUENTE_FIN", "FINANCIACION", "FUENTE_FINANCIACION"],
    "nombre_centro_gestor": ["CENTRO", "CENTRO_GESTOR", "SECRETARIA", "SECRETARÍA", "CG", "NOMBRE_CEN"],
    "direccion": ["DIRECCION", "DIRECCIÓN", "ADDRESS", "DIR"],
    "bpin": ["BPIN", "B_PIN"],
    "identificador": ["IDENTIFICADOR", "IDENTIFICA", "COD", "CODIGO", "CÓDIGO", "IDENT", "ID"],
    "ano": ["AÑO", "ANO", "YEAR", "VIGENCIA", "ANIO"],
    "fecha_inicio": ["FECHA_INI", "FECHA_INICIO", "F_INICIO", "INICIO", "FECHA_INIC"],
    "fecha_fin": ["FECHA_FIN", "F_FIN", "FIN", "FECHA_CIERRE"],
    "referencia_contrato": ["CONTRATO", "REF_CONTRATO", "REFERENCIA_CONTRATO"],
    "referencia_proceso": ["PROCESO", "REF_PROCESO", "REFERENCIA_PROCESO"],
    "url_proceso": ["URL", "URL_PROCESO", "LINK", "ENLACE", "SECOP", "URL_PROCES"],
    "descripcion_intervencion": ["DESCRIPCION_INT", "DESC_INT", "DESCRIPCIO", "DESCRIPCION"],
    "cantidad": ["CANTIDAD", "CANT", "QUANTITY"],
    "unidad": ["UNIDAD", "UNIT", "UM"],
}

_INTERVENCION_EXTRA_ALIASES: Dict[str, List[str]] = {
    "upid": ["UPID", "UP_ID", "ID_UP", "UNIDAD_ID", "COD_UP"],
}


def _auto_suggest_mapping(columns: List[str]) -> Dict[str, str]:
    """Sugiere automáticamente el mapping columna_origen → campo_destino."""
    all_aliases = {**_UP_FIELD_ALIASES, **_INTERVENCION_EXTRA_ALIASES}
    mapping: Dict[str, str] = {}
    upper_cols = {c.upper(): c for c in columns}
    for target_field, aliases in all_aliases.items():
        for alias in aliases:
            if alias.upper() in upper_cols:
                original_col = upper_cols[alias.upper()]
                if original_col not in mapping:
                    mapping[original_col] = target_field
                break
        # También intentar coincidencia exacta case-insensitive con el nombre del campo
        if target_field.upper() in upper_cols:
            original_col = upper_cols[target_field.upper()]
            if original_col not in mapping:
                mapping[original_col] = target_field
    return mapping


def _apply_mapping_to_properties(
    props: Dict[str, Any],
    column_mapping: Dict[str, str],
) -> Dict[str, Any]:
    """Aplica el column_mapping a las propiedades de un feature.

    Descarta valores ausentes: None y strings vacíos/espacios (frecuentes en
    shapefiles/DBF, que rellenan celdas sin dato con cadena vacía).
    """
    mapped: Dict[str, Any] = {}
    for src_col, target_field in column_mapping.items():
        if src_col not in props:
            continue
        val = props[src_col]
        if val is None:
            continue
        if isinstance(val, str) and val.strip() == "":
            continue
        mapped[target_field] = val
    return mapped


class ImportarFeatureItem(BaseModel):
    geometry: Optional[Dict[str, Any]] = None
    properties: Dict[str, Any] = {}


class ImportarGeoRequest(BaseModel):
    entity_type: str = Field(
        ..., description="'unidad_proyecto' o 'intervencion'"
    )
    column_mapping: Dict[str, str] = Field(
        default_factory=dict,
        description="Mapa columna_origen → campo_destino",
    )
    features: List[ImportarFeatureItem] = Field(
        ..., description="Lista de features GeoJSON parseados en el frontend"
    )
    nombre_centro_gestor_global: Optional[str] = Field(
        None, description="Centro gestor que se aplica a todos los features si no tienen el campo mapeado"
    )

    class Config:
        extra = "allow"


def _validate_up_feature(mapped: Dict[str, Any], idx: int) -> List[str]:
    errors: List[str] = []
    if not mapped.get("nombre_up") and not mapped.get("nombre_up_detalle"):
        errors.append(f"Feature {idx + 1}: Se requiere al menos nombre_up o nombre_up_detalle")
    presupuesto = mapped.get("presupuesto_base")
    if presupuesto is not None:
        try:
            v = float(presupuesto)
            if v < 0:
                errors.append(f"Feature {idx + 1}: presupuesto_base no puede ser negativo")
        except (ValueError, TypeError):
            errors.append(f"Feature {idx + 1}: presupuesto_base debe ser un número")
    avance = mapped.get("avance_obra")
    if avance is not None:
        try:
            v = float(avance)
            if not (0 <= v <= 100):
                errors.append(f"Feature {idx + 1}: avance_obra debe estar entre 0 y 100")
        except (ValueError, TypeError):
            errors.append(f"Feature {idx + 1}: avance_obra debe ser un número")
    return errors


def _validate_intervencion_feature(mapped: Dict[str, Any], idx: int) -> List[str]:
    errors: List[str] = []
    if not mapped.get("upid"):
        errors.append(f"Feature {idx + 1}: upid es obligatorio para Intervenciones")
    return errors + _validate_up_feature(mapped, idx)


def _validate_combinado_feature(mapped: Dict[str, Any], idx: int) -> List[str]:
    """Valida una fila de una carga combinada (UP + Intervención en la misma tabla).

    El ``upid`` es OPCIONAL: si viene, agrupa las intervenciones de una misma UP
    (y se preserva la UP si ya existe en la DB); si no viene, la fila es una UP nueva
    (1 UP + 1 intervención). La exigencia de ``nombre_up`` para UP nuevas se evalúa a
    nivel de grupo en ``/ejecutar``, por eso aquí no se pide.
    """
    errors: List[str] = []
    presupuesto = mapped.get("presupuesto_base")
    if presupuesto is not None:
        try:
            if float(presupuesto) < 0:
                errors.append(f"Feature {idx + 1}: presupuesto_base no puede ser negativo")
        except (ValueError, TypeError):
            errors.append(f"Feature {idx + 1}: presupuesto_base debe ser un número")
    avance = mapped.get("avance_obra")
    if avance is not None:
        try:
            if not (0 <= float(avance) <= 100):
                errors.append(f"Feature {idx + 1}: avance_obra debe estar entre 0 y 100")
        except (ValueError, TypeError):
            errors.append(f"Feature {idx + 1}: avance_obra debe ser un número")
    return errors


def _up_payload_fields(mapped: Dict[str, Any]) -> Dict[str, Any]:
    """Campos propios de una Unidad de Proyecto a partir de las propiedades mapeadas.

    No incluye geometry / comuna / barrio / upid / timestamps: esos los agrega quien
    arma el documento final. Descarta valores None.
    """
    return {
        k: v
        for k, v in {
            "nombre_up": mapped.get("nombre_up"),
            "nombre_up_detalle": mapped.get("nombre_up_detalle"),
            "tipo_equipamiento": mapped.get("tipo_equipamiento"),
            "clase_up": mapped.get("clase_up"),
            "tipo_intervencion": mapped.get("tipo_intervencion"),
            "estado": mapped.get("estado"),
            "presupuesto_base": float(mapped["presupuesto_base"]) if mapped.get("presupuesto_base") is not None else None,
            "avance_obra": float(mapped["avance_obra"]) if mapped.get("avance_obra") is not None else None,
            "fuente_financiacion": mapped.get("fuente_financiacion"),
            "nombre_centro_gestor": mapped.get("nombre_centro_gestor"),
            "direccion": mapped.get("direccion"),
            "bpin": mapped.get("bpin"),
            "identificador": mapped.get("identificador"),
            "ano": str(mapped["ano"]) if mapped.get("ano") is not None else None,
            "fecha_inicio": mapped.get("fecha_inicio"),
            "fecha_fin": mapped.get("fecha_fin"),
            "referencia_contrato": mapped.get("referencia_contrato"),
            "referencia_proceso": mapped.get("referencia_proceso"),
            "url_proceso": mapped.get("url_proceso"),
            "descripcion_intervencion": mapped.get("descripcion_intervencion"),
            "cantidad": int(mapped["cantidad"]) if mapped.get("cantidad") is not None else None,
            "unidad": mapped.get("unidad"),
        }.items()
        if v is not None
    }


def _intervencion_payload_fields(mapped: Dict[str, Any]) -> Dict[str, Any]:
    """Campos propios de una Intervención a partir de las propiedades mapeadas.

    No incluye upid / intervencion_id / timestamps. Descarta valores None.
    """
    return {
        k: v
        for k, v in {
            "bpin": int(mapped["bpin"]) if mapped.get("bpin") is not None else None,
            "cantidad": int(mapped["cantidad"]) if mapped.get("cantidad") is not None else None,
            "clase_up": mapped.get("clase_up"),
            "fecha_fin": mapped.get("fecha_fin"),
            "fecha_inicio": mapped.get("fecha_inicio"),
            "fuente_financiacion": mapped.get("fuente_financiacion"),
            "identificador": mapped.get("identificador"),
            "nombre_centro_gestor": mapped.get("nombre_centro_gestor"),
            "presupuesto_base": float(mapped["presupuesto_base"]) if mapped.get("presupuesto_base") is not None else None,
            "referencia_contrato": mapped.get("referencia_contrato"),
            "referencia_proceso": mapped.get("referencia_proceso"),
            "tipo_intervencion": mapped.get("tipo_intervencion"),
            "unidad": mapped.get("unidad"),
            "url_proceso": mapped.get("url_proceso"),
            "descripcion_intervencion": mapped.get("descripcion_intervencion"),
        }.items()
        if v is not None
    }


def _group_indices_by_upid(mapped_rows: List[Dict[str, Any]]) -> List[Tuple[str, List[int]]]:
    """Agrupa los índices de filas por su ``upid`` mapeado, preservando el orden de aparición.

    Devuelve una lista de tuplas ``(file_upid, [indices])``. Es la base del modo
    combinado: cada grupo se convierte en 1 UP + N intervenciones.

    Las filas SIN ``upid`` (vacío) NO se agrupan entre sí: cada una es su propia UP
    nueva (caso típico de archivos shapefile que no traen upid). Salen como grupos
    individuales con clave "".
    """
    groups: Dict[str, int] = {}  # upid no vacío → posición en result
    result: List[Tuple[str, List[int]]] = []
    for idx, mapped in enumerate(mapped_rows):
        key = str(mapped.get("upid", "")).strip()
        if not key:
            result.append(("", [idx]))
            continue
        if key in groups:
            result[groups[key]][1].append(idx)
        else:
            groups[key] = len(result)
            result.append((key, [idx]))
    return result


@router.post(
    "/unidades-proyecto/importar/sugerir-mapping",
    tags=["Unidades de Proyecto"],
    summary="POST | Sugerir mapping de columnas para importación geoespacial",
    dependencies=[Depends(require_unidades("read"))],
)
@optional_rate_limit("60/minute")
async def importar_sugerir_mapping(
    request: Request,
    columns: List[str] = Body(..., description="Lista de columnas del archivo cargado"),
):
    """
    Recibe la lista de columnas del archivo y devuelve un mapping sugerido.
    No accede a Firestore.
    """
    suggestion = _auto_suggest_mapping(columns)
    return create_utf8_response({
        "success": True,
        "suggested_mapping": suggestion,
        "up_target_fields": list(_UP_FIELD_ALIASES.keys()),
        "intervencion_extra_fields": list(_INTERVENCION_EXTRA_ALIASES.keys()),
    })


@router.post(
    "/unidades-proyecto/importar/validar",
    tags=["Unidades de Proyecto"],
    summary="POST | Validar features geoespaciales sin escribir en Firestore",
    dependencies=[Depends(require_unidades("write"))],
)
@optional_rate_limit("20/minute")
async def importar_up_validar(
    request: Request,
    body: ImportarGeoRequest,
):
    """
    Valida los features parseados del archivo geoespacial aplicando el column_mapping.
    No realiza ninguna escritura en Firestore.
    Devuelve errores por feature y un preview de los primeros 10.
    """
    current_user = getattr(request.state, "current_user", None)
    if current_user is None:
        raise HTTPException(status_code=401, detail="No autenticado")

    if body.entity_type not in ("unidad_proyecto", "intervencion", "combinado"):
        raise HTTPException(status_code=400, detail="entity_type debe ser 'unidad_proyecto', 'intervencion' o 'combinado'")

    errors_by_feature: List[Dict[str, Any]] = []
    preview_rows: List[Dict[str, Any]] = []
    valid_count = 0
    mapped_rows: List[Dict[str, Any]] = []

    for idx, feat in enumerate(body.features):
        mapped = _apply_mapping_to_properties(feat.properties, body.column_mapping)

        # Aplicar centro gestor global si no viene en el feature
        if not mapped.get("nombre_centro_gestor") and body.nombre_centro_gestor_global:
            mapped["nombre_centro_gestor"] = body.nombre_centro_gestor_global

        mapped_rows.append(mapped)

        if body.entity_type == "unidad_proyecto":
            feat_errors = _validate_up_feature(mapped, idx)
        elif body.entity_type == "intervencion":
            feat_errors = _validate_intervencion_feature(mapped, idx)
        else:  # combinado
            feat_errors = _validate_combinado_feature(mapped, idx)

        if feat_errors:
            errors_by_feature.append({"feature_index": idx, "errors": feat_errors})
        else:
            valid_count += 1

        if idx < 10:
            preview_rows.append({
                "feature_index": idx,
                "mapped_fields": mapped,
                "has_geometry": feat.geometry is not None,
                "geometry_type": feat.geometry.get("type") if feat.geometry else None,
                "errors": feat_errors,
            })

    response: Dict[str, Any] = {
        "success": True,
        "entity_type": body.entity_type,
        "total_features": len(body.features),
        "valid_count": valid_count,
        "error_count": len(errors_by_feature),
        "errors": errors_by_feature,
        "preview": preview_rows,
    }

    # En modo combinado, informar cuántas UP y cuántas intervenciones resultarían.
    # Cada grupo (upid no vacío, o fila individual sin upid) es una UP; cada fila, una intervención.
    if body.entity_type == "combinado":
        groups = _group_indices_by_upid(mapped_rows)
        response["combinado_summary"] = {
            "unique_ups": len(groups),
            "total_intervenciones": sum(len(idxs) for _, idxs in groups),
        }

    return create_utf8_response(response)


@router.post(
    "/unidades-proyecto/importar/ejecutar",
    tags=["Unidades de Proyecto"],
    summary="POST | Importar features geoespaciales a Firestore",
    dependencies=[Depends(require_unidades("write"))],
)
@optional_rate_limit("5/minute")
async def importar_up_ejecutar(
    request: Request,
    body: ImportarGeoRequest,
):
    """
    Importa features geoespaciales ya validados a Firestore.
    Reutiliza la misma lógica de auto-generación de IDs, detección de
    comuna/barrio/proyectos estratégicos que los endpoints de creación individuales.
    """
    if not FIREBASE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Firebase not available")

    current_user = getattr(request.state, "current_user", None)
    if current_user is None:
        raise HTTPException(status_code=401, detail="No autenticado")

    if body.entity_type not in ("unidad_proyecto", "intervencion", "combinado"):
        raise HTTPException(status_code=400, detail="entity_type debe ser 'unidad_proyecto', 'intervencion' o 'combinado'")

    db = get_firestore_client()
    if db is None:
        raise HTTPException(status_code=503, detail="No se pudo conectar a Firestore")

    created_ids: List[str] = []
    errors_by_feature: List[Dict[str, Any]] = []
    now_iso = datetime.now().isoformat()

    # Pre-cargar el max upid actual una sola vez (para batch eficiente)
    def _get_max_upid() -> int:
        max_n = 0
        for doc in db.collection("unidades_proyecto").select(["upid"]).stream():
            data = doc.to_dict() or {}
            m = re.match(r"^UNP-(\d+)$", str(data.get("upid", "")).strip(), re.IGNORECASE)
            if m:
                max_n = max(max_n, int(m.group(1)))
        return max_n

    # Las UP se autogeneran en modo 'unidad_proyecto' y 'combinado' (UP nuevas)
    upid_counter = (
        _get_max_upid()
        if body.entity_type in ("unidad_proyecto", "combinado")
        else 0
    )

    # Cache de max intervencion por upid para batch eficiente
    intervencion_counters: Dict[str, int] = {}

    def _get_max_intervencion(upid_val: str) -> int:
        if upid_val in intervencion_counters:
            return intervencion_counters[upid_val]
        max_n = 0
        for coll in ["intervenciones_unidades_proyecto", "unidades_proyecto_intervenciones"]:
            for doc in db.collection(coll).where("upid", "==", upid_val).stream():
                data = doc.to_dict() or {}
                iid = data.get("intervencion_id", doc.id)
                m = re.match(rf"^{re.escape(upid_val)}-INT-(\d+)$", str(iid), re.IGNORECASE)
                if m:
                    max_n = max(max_n, int(m.group(1)))
        intervencion_counters[upid_val] = max_n
        return max_n

    def _enrich_geometry(geometry: Optional[Dict[str, Any]], idx: int):
        """Deriva comuna/corregimiento, barrio/vereda y proyectos estratégicos de una geometría."""
        comarca_corr = None
        barrio_vrd = None
        proy_estrat: List[str] = []
        if geometry and geometry.get("type") and geometry.get("coordinates"):
            try:
                _validate_crs_coords(_normalizar_geometry(geometry))
                comarca_corr = _buscar_en_geojson(
                    os.path.join(BASEMAPS_DIR, "comunas_corregimientos.geojson"),
                    "comuna_corregimiento",
                    geometry,
                )
                barrio_vrd = _buscar_en_geojson(
                    os.path.join(BASEMAPS_DIR, "barrios_veredas.geojson"),
                    "barrio_vereda",
                    geometry,
                )
                proy_estrat = _buscar_proyectos_estrategicos(geometry)
            except Exception as geo_err:
                logger.warning("importar: error geo feature %d: %s", idx, geo_err)
        return comarca_corr, barrio_vrd, proy_estrat

    def _audit_import(upid_for_audit: Optional[str], payload: Dict[str, Any], entity: str, idx: int):
        try:
            db.collection("cambios_implementados_unidades_proyecto").add({
                "upid": upid_for_audit,
                "accion": "importar",
                "entity_type": entity,
                "uid": current_user.get("uid"),
                "email": current_user.get("email"),
                "payload": payload,
                "timestamp": now_iso,
            })
        except Exception as audit_err:
            logger.warning("importar: fallo auditoría feature %d: %s", idx, audit_err)

    # ── Modo combinado: una tabla con UP + intervenciones, separadas por 'upid' ──
    if body.entity_type == "combinado":
        created_up_ids: List[str] = []
        created_int_ids: List[str] = []

        # 1) Mapear todas las filas (+ centro gestor global + RBAC)
        mapped_rows: List[Dict[str, Any]] = []
        for idx, feat in enumerate(body.features):
            mapped = _apply_mapping_to_properties(feat.properties, body.column_mapping)
            if not mapped.get("nombre_centro_gestor") and body.nombre_centro_gestor_global:
                mapped["nombre_centro_gestor"] = body.nombre_centro_gestor_global
            effective_centro = enforce_unidades_access(
                current_user, "write:unidades", mapped.get("nombre_centro_gestor")
            )
            if effective_centro:
                mapped["nombre_centro_gestor"] = effective_centro
            mapped_rows.append(mapped)

        # 2) Agrupar por el upid del archivo, preservando orden.
        #    Filas sin upid → cada una es una UP nueva (1 UP + 1 intervención).
        for file_upid, indices in _group_indices_by_upid(mapped_rows):
            # Validación per-fila del grupo
            group_errors = False
            for idx in indices:
                ferr = _validate_combinado_feature(mapped_rows[idx], idx)
                if ferr:
                    errors_by_feature.append({"feature_index": idx, "errors": ferr})
                    group_errors = True
            if group_errors:
                continue

            try:
                # ¿La UP ya existe en Firestore? Solo si el archivo trae upid.
                # Si existe → se preserva y solo se cuelgan intervenciones.
                existing = (
                    list(
                        db.collection("unidades_proyecto").where("upid", "==", file_upid).limit(1).stream()
                    )
                    if file_upid
                    else []
                )

                if existing:
                    target_upid = file_upid
                else:
                    # UP nueva: necesita nombre. Se toma la primera fila del grupo que lo traiga.
                    rep_idx = next(
                        (i for i in indices if mapped_rows[i].get("nombre_up") or mapped_rows[i].get("nombre_up_detalle")),
                        None,
                    )
                    if rep_idx is None:
                        for idx in indices:
                            errors_by_feature.append({
                                "feature_index": idx,
                                "errors": [f"Feature {idx + 1}: la UP nueva (upid {file_upid}) requiere nombre_up o nombre_up_detalle"],
                            })
                        continue

                    up_mapped = mapped_rows[rep_idx]
                    geometry = body.features[rep_idx].geometry
                    comarca_corr, barrio_vrd, proy_estrat = _enrich_geometry(geometry, rep_idx)

                    upid_counter += 1
                    target_upid = f"UNP-{upid_counter}"

                    up_payload = _up_payload_fields(up_mapped)
                    if comarca_corr is not None:
                        up_payload["comuna_corregimiento"] = comarca_corr
                    if barrio_vrd is not None:
                        up_payload["barrio_vereda"] = barrio_vrd
                    if geometry is not None:
                        up_payload["geometry"] = geometry
                    up_payload["upid"] = target_upid
                    up_payload["proyectos_estrategicos"] = proy_estrat
                    up_payload["created_at"] = now_iso
                    up_payload["updated_at"] = now_iso
                    up_payload["created_by"] = current_user.get("uid")
                    up_payload["importado"] = True

                    db.collection("unidades_proyecto").document(target_upid).set(up_payload)
                    created_up_ids.append(target_upid)
                    created_ids.append(target_upid)
                    _audit_import(target_upid, up_payload, "unidad_proyecto", rep_idx)

                # Crear una intervención por cada fila del grupo
                for idx in indices:
                    int_mapped = mapped_rows[idx]
                    new_int_num = _get_max_intervencion(target_upid) + 1
                    int_id = f"{target_upid}-INT-{new_int_num}"
                    intervencion_counters[target_upid] = new_int_num

                    int_payload = _intervencion_payload_fields(int_mapped)
                    int_payload["upid"] = target_upid
                    int_payload["intervencion_id"] = int_id
                    int_payload["created_at"] = now_iso
                    int_payload["updated_at"] = now_iso
                    int_payload["created_by"] = current_user.get("uid")
                    int_payload["importado"] = True

                    db.collection("intervenciones_unidades_proyecto").document(int_id).set(int_payload)
                    created_int_ids.append(int_id)
                    created_ids.append(int_id)
                    _audit_import(target_upid, int_payload, "intervencion", idx)

            except Exception as grp_err:
                logger.error("importar combinado: error en grupo upid %s: %s", file_upid, grp_err)
                for idx in indices:
                    errors_by_feature.append({
                        "feature_index": idx,
                        "errors": [f"Error procesando grupo upid {file_upid}: {str(grp_err)}"],
                    })

        _invalidate_unidades_cache()

        return create_utf8_response({
            "success": True,
            "entity_type": "combinado",
            "created_count": len(created_ids),
            "created_up_count": len(created_up_ids),
            "created_intervencion_count": len(created_int_ids),
            "error_count": len(errors_by_feature),
            "created_ids": created_ids,
            "created_up_ids": created_up_ids,
            "created_intervencion_ids": created_int_ids,
            "errors": errors_by_feature,
        })

    for idx, feat in enumerate(body.features):
        try:
            mapped = _apply_mapping_to_properties(feat.properties, body.column_mapping)

            if not mapped.get("nombre_centro_gestor") and body.nombre_centro_gestor_global:
                mapped["nombre_centro_gestor"] = body.nombre_centro_gestor_global

            # Forzar centro gestor según permisos del usuario
            effective_centro = enforce_unidades_access(
                current_user, "write:unidades", mapped.get("nombre_centro_gestor")
            )
            if effective_centro:
                mapped["nombre_centro_gestor"] = effective_centro

            if body.entity_type == "unidad_proyecto":
                feat_errors = _validate_up_feature(mapped, idx)
            else:
                feat_errors = _validate_intervencion_feature(mapped, idx)

            if feat_errors:
                errors_by_feature.append({"feature_index": idx, "errors": feat_errors})
                continue

            geometry = feat.geometry
            comarca_corr, barrio_vrd, proy_estrat = _enrich_geometry(geometry, idx)

            if body.entity_type == "unidad_proyecto":
                upid_counter += 1
                new_id = f"UNP-{upid_counter}"
                payload: Dict[str, Any] = _up_payload_fields(mapped)
                if comarca_corr is not None:
                    payload["comuna_corregimiento"] = comarca_corr
                if barrio_vrd is not None:
                    payload["barrio_vereda"] = barrio_vrd
                if geometry is not None:
                    payload["geometry"] = geometry
                payload["upid"] = new_id
                payload["proyectos_estrategicos"] = proy_estrat
                payload["created_at"] = now_iso
                payload["updated_at"] = now_iso
                payload["created_by"] = current_user.get("uid")
                payload["importado"] = True

                db.collection("unidades_proyecto").document(new_id).set(payload)

            else:  # intervencion
                upid_val = str(mapped.get("upid", "")).strip()
                upid_docs = list(
                    db.collection("unidades_proyecto").where("upid", "==", upid_val).limit(1).stream()
                )
                if not upid_docs:
                    errors_by_feature.append({
                        "feature_index": idx,
                        "errors": [f"Feature {idx + 1}: upid {upid_val} no existe en unidades_proyecto"],
                    })
                    continue

                max_int = _get_max_intervencion(upid_val)
                new_int_num = max_int + 1
                new_id = f"{upid_val}-INT-{new_int_num}"
                intervencion_counters[upid_val] = new_int_num

                payload = _intervencion_payload_fields(mapped)
                payload["upid"] = upid_val
                payload["intervencion_id"] = new_id
                payload["created_at"] = now_iso
                payload["updated_at"] = now_iso
                payload["created_by"] = current_user.get("uid")
                payload["importado"] = True

                db.collection("intervenciones_unidades_proyecto").document(new_id).set(payload)

            _audit_import(
                new_id if body.entity_type == "unidad_proyecto" else mapped.get("upid"),
                payload,
                body.entity_type,
                idx,
            )

            created_ids.append(new_id)

        except Exception as feat_err:
            logger.error("importar: error procesando feature %d: %s", idx, feat_err)
            errors_by_feature.append({
                "feature_index": idx,
                "errors": [f"Error procesando feature {idx + 1}: {str(feat_err)}"],
            })

    _invalidate_unidades_cache()

    return create_utf8_response({
        "success": True,
        "entity_type": body.entity_type,
        "created_count": len(created_ids),
        "error_count": len(errors_by_feature),
        "created_ids": created_ids,
        "errors": errors_by_feature,
    })

# -*- coding: utf-8 -*-
"""
Modularization script for back/main.py.
Extracts endpoint sections into separate router files.
Run from the back/ directory.
"""

import os
import re

MAIN_PY = os.path.join(os.path.dirname(__file__), "..", "main.py")

with open(MAIN_PY, "r", encoding="utf-8") as f:
    lines = f.readlines()

total_lines = len(lines)
print(f"main.py has {total_lines} lines")


def extract_lines(start_1based: int, end_1based: int) -> str:
    """Extract lines (1-based, inclusive) from main.py."""
    return "".join(lines[start_1based - 1 : end_1based])


def replace_app_decorators(code: str) -> str:
    """Replace @app.METHOD with @router.METHOD."""
    return re.sub(
        r"@app\.(get|post|put|delete|patch|options|head)", r"@router.\1", code
    )


# ============================================================
# 1. AUTH ROUTES (lines 7277-8391)
# ============================================================
# Includes check_user_management_availability + all auth/admin endpoints
# Ends JUST before empréstito section (line 8392)

AUTH_HEADER = '''\
# -*- coding: utf-8 -*-
"""
api/routers/auth_routes.py — Endpoints de autenticacion y gestion de usuarios.

Rutas expuestas:
    POST   /auth/validate-session
    POST   /auth/login
    GET    /auth/register/health-check
    POST   /auth/register
    POST   /auth/change-password
    GET    /auth/config
    GET    /auth/workload-identity/status
    POST   /auth/google
    DELETE /auth/user/{uid}
    GET    /admin/users
"""

import logging
import os
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, cast

from fastapi import APIRouter, Form, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse

from api.core.responses import clean_firebase_data, create_utf8_response
from api.core.security import verify_firebase_token

logger = logging.getLogger(__name__)

router = APIRouter()

# ---------------------------------------------------------------------------
# Availability flags — importación segura
# ---------------------------------------------------------------------------
try:
    from database.firebase_config import FIREBASE_AVAILABLE, get_firestore_client, PROJECT_ID
except Exception:
    FIREBASE_AVAILABLE = False
    PROJECT_ID = os.getenv("FIREBASE_PROJECT_ID", "NOT_CONFIGURED")
    get_firestore_client = lambda: None

try:
    from api.scripts import (
        USER_MANAGEMENT_AVAILABLE,
        AUTH_OPERATIONS_AVAILABLE,
        validate_user_session,
        authenticate_email_password,
        create_user_account,
        update_user_password,
        delete_user_account,
        list_users,
    )
except Exception:
    USER_MANAGEMENT_AVAILABLE = False
    AUTH_OPERATIONS_AVAILABLE = False
    validate_user_session = None
    authenticate_email_password = None
    create_user_account = None
    update_user_password = None
    delete_user_account = None
    list_users = None

try:
    from api.models import (
        UserRegistrationRequest,
        UserLoginRequest,
    )
    USER_MODELS_AVAILABLE = True
except Exception:
    USER_MODELS_AVAILABLE = False
    from pydantic import BaseModel

    class UserRegistrationRequest(BaseModel):
        email: str
        password: str
        name: str
        cellphone: str
        nombre_centro_gestor: str

    class UserLoginRequest(BaseModel):
        email: str
        password: str

try:
    from api.scripts import SCRIPTS_AVAILABLE as _SCRIPTS_AVAILABLE
    SCRIPTS_AVAILABLE = _SCRIPTS_AVAILABLE
except Exception:
    SCRIPTS_AVAILABLE = False


def startup_print(message: str) -> None:
    if not os.getenv("RAILWAY_ENVIRONMENT") and not os.getenv("PRODUCTION"):
        print(message)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

'''

auth_body = extract_lines(7277, 8391)
auth_body = replace_app_decorators(auth_body)
auth_content = AUTH_HEADER + auth_body

auth_path = os.path.join(
    os.path.dirname(__file__), "..", "api", "routers", "auth_routes.py"
)
with open(auth_path, "w", encoding="utf-8") as f:
    f.write(auth_content)
print(f"Created auth_routes.py ({len(auth_content.splitlines())} lines)")


# ============================================================
# 2. UNIDADES DE PROYECTO (lines 2596-6828)
# ============================================================
# All UP, intervenciones, avances, solicitudes_cambios, S3 uploads

UP_HEADER = '''\
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

import json
import logging
import os
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, cast
from urllib.parse import urlparse
from functools import lru_cache

from fastapi import APIRouter, Body, File, Form, HTTPException, Path, Query, Request, UploadFile
from fastapi.responses import JSONResponse, StreamingResponse

from api.core.cache import get_cache_key, get_from_cache, set_in_cache
from api.core.responses import clean_firebase_data, create_utf8_response
from api.core.security import optional_rate_limit

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Unidades de Proyecto"])

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


@lru_cache(maxsize=6)
def _get_s3_client_for_presign_cached(credentials_path: str = ""):
    try:
        if not BOTO3_AVAILABLE:
            return None
        manager = S3DocumentManager(credentials_path=credentials_path or None)
        return manager.s3_client
    except Exception:
        return None


def _generate_presigned_s3_url(bucket: str, key: str, credentials_path: str = "") -> Optional[str]:
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

'''

up_body = extract_lines(2596, 6828)
up_body = replace_app_decorators(up_body)
up_content = UP_HEADER + up_body

up_path = os.path.join(
    os.path.dirname(__file__), "..", "api", "routers", "unidades_proyecto.py"
)
with open(up_path, "w", encoding="utf-8") as f:
    f.write(up_content)
print(f"Created unidades_proyecto.py ({len(up_content.splitlines())} lines)")


# ============================================================
# 3. INTEROPERABILIDAD (lines 6829-7276)
# ============================================================

INTEROP_HEADER = '''\
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
from typing import Any, Dict, Optional

from fastapi import APIRouter, Body, HTTPException, Query, Request
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
        REPORTES_CONTRATOS_AVAILABLE,
    )
except Exception:
    REPORTES_CONTRATOS_AVAILABLE = False
    create_reporte_contrato = None
    get_reportes_contratos = None
    get_reporte_contrato_by_id = None
    get_reportes_by_centro_gestor = None
    get_reportes_by_referencia_contrato = None

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

'''

interop_body = extract_lines(6829, 7276)
interop_body = replace_app_decorators(interop_body)
interop_content = INTEROP_HEADER + interop_body

interop_path = os.path.join(
    os.path.dirname(__file__), "..", "api", "routers", "interoperabilidad.py"
)
with open(interop_path, "w", encoding="utf-8") as f:
    f.write(interop_content)
print(f"Created interoperabilidad.py ({len(interop_content.splitlines())} lines)")


# ============================================================
# 4. EMPRESTITO (lines 8392-15875)
# ============================================================
# Last line with empréstito endpoint is 15700 (last @app.put)
# We need to find where the include_router section starts
# Safe to extract up to line 15875 (before the SERVIDOR comment at ~15960)

EMPRESTITO_HEADER = '''\
# -*- coding: utf-8 -*-
"""
api/routers/emprestito.py — Endpoints principales de Gestion de Emprestito.

Cubre: contratos, procesos, ordenes de compra, convenios, pagos, RPC,
solicitudes de cambio, reportes, flujo de caja, proyecciones, SECOP.
"""

import json
import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, File, Form, HTTPException, Path, Query, Request, UploadFile
from fastapi.responses import JSONResponse

from api.core.responses import clean_firebase_data, create_utf8_response
from api.core.security import optional_rate_limit

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Gestión de Empréstito"])

# ---------------------------------------------------------------------------
# Disponibilidad de operaciones
# ---------------------------------------------------------------------------
try:
    from database.firebase_config import FIREBASE_AVAILABLE, get_firestore_client
except Exception:
    FIREBASE_AVAILABLE = False
    get_firestore_client = lambda: None

try:
    from api.scripts import (
        procesar_emprestito_completo,
        verificar_proceso_existente,
        eliminar_proceso_emprestito,
        actualizar_proceso_emprestito,
        obtener_codigos_contratos,
        buscar_y_poblar_contratos_secop,
        obtener_contratos_desde_proceso_contractual,
        obtener_contratos_desde_proceso_contractual_completo,
        get_emprestito_operations_status,
        cargar_orden_compra_directa,
        cargar_convenio_transferencia,
        modificar_convenio_transferencia,
        actualizar_orden_compra_por_numero,
        eliminar_orden_compra_por_numero,
        eliminar_convenio_transferencia_por_referencia,
        actualizar_convenio_por_referencia,
        actualizar_contrato_secop_por_referencia,
        actualizar_proceso_secop_por_referencia,
        cargar_rpc_emprestito,
        cargar_pago_emprestito,
        get_pagos_emprestito_all,
        get_rpc_contratos_emprestito_all,
        actualizar_rpc_contrato_emprestito,
        get_asignaciones_emprestito_banco_centro_gestor_all,
        get_convenios_transferencia_emprestito_all,
        obtener_ordenes_compra_tvec_enriquecidas,
        get_tvec_enrich_status,
        get_ordenes_compra_emprestito_all,
        get_ordenes_compra_emprestito_by_referencia,
        get_ordenes_compra_emprestito_by_centro_gestor,
        registrar_cambio_valor,
        obtener_historial_cambios,
        EMPRESTITO_OPERATIONS_AVAILABLE,
        TVEC_ENRICH_OPERATIONS_AVAILABLE,
        ORDENES_COMPRA_OPERATIONS_AVAILABLE,
        obtener_datos_secop_completos,
        actualizar_proceso_emprestito_completo,
        procesar_todos_procesos_emprestito_completo,
        crear_tabla_proyecciones_desde_sheets,
        leer_proyecciones_emprestito,
        leer_proyecciones_no_guardadas,
        get_proyecciones_sin_proceso,
        actualizar_proyeccion_emprestito,
        get_procesos_emprestito_all,
        get_contratos_emprestito_all,
        get_contratos_emprestito_by_referencia,
        get_contratos_emprestito_by_centro_gestor,
        process_flujo_caja_excel,
        save_flujo_caja_to_firebase,
        get_flujo_caja_from_firebase,
        FLUJO_CAJA_OPERATIONS_AVAILABLE,
    )
except Exception as _e:
    logger.warning(f"Emprestito scripts not fully available: {_e}")
    EMPRESTITO_OPERATIONS_AVAILABLE = False
    TVEC_ENRICH_OPERATIONS_AVAILABLE = False
    ORDENES_COMPRA_OPERATIONS_AVAILABLE = False
    FLUJO_CAJA_OPERATIONS_AVAILABLE = False

try:
    from api.models import (
        EmprestitoRequest,
        EmprestitoResponse,
        PagoEmprestitoRequest,
        PagoEmprestitoResponse,
        ProyeccionEmprestitoUpdateRequest,
        ProyeccionEmprestitoUpdateResponse,
        ProyeccionEmprestitoRegistroRequest,
        ProyeccionEmprestitoRegistroResponse,
        RPCUpdateRequest,
        RPCUpdateResponse,
        FlujoCajaRequest,
        FlujoCajaResponse,
        FlujoCajaUploadRequest,
        FlujoCajaFilters,
    )
except Exception:
    from pydantic import BaseModel

    class EmprestitoRequest(BaseModel):
        referencia_proceso: str = ""

    class EmprestitoResponse(BaseModel):
        success: bool = True

    class PagoEmprestitoRequest(BaseModel):
        pass

    class PagoEmprestitoResponse(BaseModel):
        pass

    class ProyeccionEmprestitoUpdateRequest(BaseModel):
        pass

    class ProyeccionEmprestitoUpdateResponse(BaseModel):
        pass

    class ProyeccionEmprestitoRegistroRequest(BaseModel):
        pass

    class ProyeccionEmprestitoRegistroResponse(BaseModel):
        pass

    class RPCUpdateRequest(BaseModel):
        pass

    class RPCUpdateResponse(BaseModel):
        pass

    class FlujoCajaRequest(BaseModel):
        pass

    class FlujoCajaResponse(BaseModel):
        pass

    class FlujoCajaUploadRequest(BaseModel):
        pass

    class FlujoCajaFilters(BaseModel):
        pass


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

'''

# Find end of emprestito section (before include_router calls)
# Look for the SERVIDOR comment / include_router section
emprestito_end = 15966  # last line of emprestito section (before SERVIDOR comment)

emprestito_body = extract_lines(8392, emprestito_end)
emprestito_body = replace_app_decorators(emprestito_body)
emprestito_content = EMPRESTITO_HEADER + emprestito_body

emprestito_path = os.path.join(
    os.path.dirname(__file__), "..", "api", "routers", "emprestito.py"
)
with open(emprestito_path, "w", encoding="utf-8") as f:
    f.write(emprestito_content)
print(f"Created emprestito.py ({len(emprestito_content.splitlines())} lines)")


# ============================================================
# 5. VERIFY SYNTAX
# ============================================================
import py_compile

for fpath in [auth_path, up_path, interop_path, emprestito_path]:
    try:
        py_compile.compile(fpath, doraise=True)
        print(f"[OK] Syntax OK: {os.path.basename(fpath)}")
    except py_compile.PyCompileError as e:
        print(f"[ERROR] Syntax error in {os.path.basename(fpath)}: {e}")

print("\nDone! Router files created.")

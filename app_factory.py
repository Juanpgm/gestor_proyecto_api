# -*- coding: utf-8 -*-
"""
app_factory.py — Fabrica de la aplicacion FastAPI.

Separa la creacion de la app (middlewares, routers, exception handlers)
del punto de entrada (main.py), facilitando tests y despliegues.

Uso::

    from app_factory import create_app
    app = create_app()
"""

import asyncio
import logging
import os
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from api.core.config import CORS_ORIGINS, CORS_ORIGIN_REGEX
from api.core.security import (
    SLOWAPI_AVAILABLE,
    RateLimitExceeded,
    _rate_limit_exceeded_handler,
    limiter,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Thread pool compartido — token verification + health checks
# ---------------------------------------------------------------------------
_ROUTE_AUTH_EXECUTOR = ThreadPoolExecutor(
    max_workers=8, thread_name_prefix="route-auth"
)

# ---------------------------------------------------------------------------
# Importaciones de routers existentes
# ---------------------------------------------------------------------------
try:
    from api.routers.auth_admin import router as auth_admin_router

    _AUTH_ADMIN_AVAILABLE = True
except Exception as exc:
    logger.warning(f"auth_admin router not available: {exc}")
    _AUTH_ADMIN_AVAILABLE = False

try:
    from api.routers.emprestito_quality_router import (
        router as emprestito_quality_router,
    )

    _EMPRESTITO_QUALITY_AVAILABLE = True
except Exception as exc:
    logger.warning(f"emprestito_quality router not available: {exc}")
    _EMPRESTITO_QUALITY_AVAILABLE = False

try:
    from api.routers.captura_360_router import router as captura_360_router

    _CAPTURA_360_AVAILABLE = True
except Exception as exc:
    logger.warning(f"captura_360 router not available: {exc}")
    _CAPTURA_360_AVAILABLE = False

# Nuevos routers modulares
try:
    from api.routers.core_routes import router as core_router

    _CORE_ROUTES_AVAILABLE = True
except Exception as exc:
    logger.warning(f"core_routes router not available: {exc}")
    _CORE_ROUTES_AVAILABLE = False

try:
    from api.routers.general_routes import router as general_router

    _GENERAL_ROUTES_AVAILABLE = True
except Exception as exc:
    logger.warning(f"general_routes router not available: {exc}")
    _GENERAL_ROUTES_AVAILABLE = False

try:
    from api.routers.proyectos import router as proyectos_router

    _PROYECTOS_AVAILABLE = True
except Exception as exc:
    logger.warning(f"proyectos router not available: {exc}")
    _PROYECTOS_AVAILABLE = False

# Nuevos routers extraídos de main.py
try:
    from api.routers.auth_routes import router as auth_routes_router

    _AUTH_ROUTES_AVAILABLE = True
except Exception as exc:
    logger.warning(f"auth_routes router not available: {exc}")
    _AUTH_ROUTES_AVAILABLE = False

try:
    from api.routers.unidades_proyecto import router as unidades_proyecto_router

    _UNIDADES_PROYECTO_AVAILABLE = True
except Exception as exc:
    logger.warning(f"unidades_proyecto router not available: {exc}")
    _UNIDADES_PROYECTO_AVAILABLE = False

try:
    from api.routers.interoperabilidad import router as interoperabilidad_router

    _INTEROPERABILIDAD_AVAILABLE = True
except Exception as exc:
    logger.warning(f"interoperabilidad router not available: {exc}")
    _INTEROPERABILIDAD_AVAILABLE = False

try:
    from api.routers.emprestito import router as emprestito_router

    _EMPRESTITO_AVAILABLE = True
except Exception as exc:
    logger.warning(f"emprestito router not available: {exc}")
    _EMPRESTITO_AVAILABLE = False


# ---------------------------------------------------------------------------
# Lifespan (startup / shutdown)
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gestionar ciclo de vida: inicializar Firebase al arrancar, cerrar executor al parar."""
    logger.info(
        f"API starting — port={os.getenv('PORT', '8000')} env={os.getenv('ENVIRONMENT', 'development')}"
    )

    try:
        from database.firebase_config import (
            FIREBASE_AVAILABLE,
            configure_firebase,
        )

        if FIREBASE_AVAILABLE:
            initialized, status = configure_firebase()
            if initialized:
                logger.info("Firebase initialized successfully")
            else:
                error_msg = status.get("error", "Unknown error")
                logger.error(f"Firebase init failed: {error_msg}")
                if os.getenv("RAILWAY_ENVIRONMENT") or os.getenv("PRODUCTION"):
                    raise RuntimeError(f"Firebase required in production: {error_msg}")
        else:
            logger.warning("Firebase not available — limited mode")
    except RuntimeError:
        raise
    except ImportError as exc:
        logger.error(f"Firebase SDK import failed: {exc}")
        if os.getenv("RAILWAY_ENVIRONMENT") or os.getenv("PRODUCTION"):
            raise RuntimeError(f"Firebase SDK required in production: {exc}") from exc
    except Exception as exc:
        logger.error(f"Firebase setup error: {exc}", exc_info=True)
        if os.getenv("RAILWAY_ENVIRONMENT") or os.getenv("PRODUCTION"):
            raise RuntimeError(f"Firebase required in production: {exc}") from exc

    yield

    logger.info("API shutting down — cleaning up thread pools")
    _ROUTE_AUTH_EXECUTOR.shutdown(wait=False)


# ---------------------------------------------------------------------------
# Exception handlers
# ---------------------------------------------------------------------------


async def global_exception_handler(request: Request, exc: Exception):
    """Captura excepciones no manejadas y devuelve JSON estructurado."""
    logger.error(
        f"Unhandled exception on {request.method} {request.url.path}: {exc}",
        exc_info=True,
    )
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": "Error interno del servidor",
            "message": "Ha ocurrido un error inesperado. Contacte al administrador.",
            "code": "INTERNAL_SERVER_ERROR",
            "timestamp": datetime.now().isoformat(),
        },
    )


# ---------------------------------------------------------------------------
# Middlewares
# ---------------------------------------------------------------------------


async def _utf8_middleware(request: Request, call_next):
    response = await call_next(request)
    if response.headers.get("content-type", "").startswith("application/json"):
        response.headers["content-type"] = "application/json; charset=utf-8"
    return response


MAX_REQUEST_BODY_SIZE = 50 * 1024 * 1024  # 50 MB


async def _body_size_limit(request: Request, call_next):
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > MAX_REQUEST_BODY_SIZE:
        return JSONResponse(
            status_code=413,
            content={
                "success": False,
                "error": "Request body too large",
                "message": f"Tamano maximo permitido: {MAX_REQUEST_BODY_SIZE // (1024 * 1024)} MB",
                "code": "PAYLOAD_TOO_LARGE",
            },
        )
    return await call_next(request)


import time as _time


async def _performance_middleware(request: Request, call_next):
    start = _time.time()
    response = await call_next(request)
    elapsed = _time.time() - start
    response.headers["X-Process-Time"] = f"{elapsed:.3f}"
    response.headers["X-Content-Type-Options"] = "nosniff"

    # Cache hint para endpoints de lectura estables
    _cacheable_paths = [
        "/centros-gestores/",
        "/firebase/collections",
        "/proyectos-presupuestales/",
        "/unidades-proyecto/filters",
    ]
    if request.method == "GET" and response.status_code == 200:
        if any(p in request.url.path for p in _cacheable_paths):
            response.headers["Cache-Control"] = "public, max-age=300"
    return response


async def _timeout_middleware(request: Request, call_next):
    """Timeout por endpoint — evita colgadas indefinidas."""
    path = request.url.path
    if path == "/emprestito/obtener-procesos-secop":
        timeout = 300.0
    elif path in ("/emprestito/obtener-contratos-secop",):
        timeout = 120.0
    elif path == "/unidades-proyecto/calidad-datos/analizar":
        timeout = 600.0
    elif "/intervenciones/sincronizar" in path:
        timeout = 600.0
    elif "/calidad-datos/" in path:
        timeout = 120.0
    else:
        timeout = 30.0

    try:
        return await asyncio.wait_for(call_next(request), timeout=timeout)
    except asyncio.TimeoutError:
        return JSONResponse(
            status_code=504,
            content={
                "error": "Request timeout",
                "message": f"La peticion tardó mas de {timeout}s",
                "endpoint": path,
                "timestamp": datetime.now().isoformat(),
            },
        )
    except Exception:
        return JSONResponse(
            status_code=500,
            content={
                "error": "Internal server error",
                "timestamp": datetime.now().isoformat(),
            },
        )


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def create_app() -> FastAPI:
    """
    Crea y configura la instancia FastAPI completa.

    - Middlewares: UTF-8, body-size, performance, timeout, CORS, GZip, Auth
    - Exception handlers: global, rate-limit
    - Routers: core, general, proyectos, auth_routes, unidades_proyecto,
                interoperabilidad, emprestito, auth_admin, emprestito_quality, captura_360
    - Static files: /static (si existe)

    Returns:
        app — FastAPI instance lista para servir
    """
    app = FastAPI(
        title="Gestor de Proyectos API",
        description="API para gestion de proyectos con Firebase/Firestore — UTF-8 completo",
        version="2.0.0",
        lifespan=lifespan,
        swagger_ui_parameters={
            "defaultModelsExpandDepth": 1,
            "displayRequestDuration": True,
            "filter": True,
            "tryItOutEnabled": True,
        },
    )

    # -- Rate limit --
    if SLOWAPI_AVAILABLE and limiter is not None and RateLimitExceeded is not None:
        app.state.limiter = limiter
        app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
        logger.info("Rate limiting enabled")

    # -- Global exception handler --
    app.add_exception_handler(Exception, global_exception_handler)

    # -- Middlewares (order matters — outermost first) --
    app.middleware("http")(_timeout_middleware)
    app.middleware("http")(_performance_middleware)
    app.middleware("http")(_body_size_limit)
    app.middleware("http")(_utf8_middleware)

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=CORS_ORIGINS,
        allow_origin_regex=CORS_ORIGIN_REGEX,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "HEAD", "PATCH"],
        allow_headers=[
            "Authorization",
            "Content-Type",
            "Accept",
            "Accept-Charset",
            "Accept-Encoding",
            "Accept-Language",
            "Origin",
            "X-Requested-With",
            "Cache-Control",
            "Pragma",
            "X-CSRF-Token",
        ],
        expose_headers=["Content-Type", "Authorization"],
        max_age=600,
    )
    logger.info(f"CORS configured — {len(CORS_ORIGINS)} origins")

    # GZip
    app.add_middleware(GZipMiddleware, minimum_size=1000)

    # Auth middleware
    try:
        from auth_system.middleware import AuthorizationMiddleware, AuditLogMiddleware

        public_paths = [
            "/",
            "/docs",
            "/openapi.json",
            "/redoc",
            "/ping",
            "/health",
            "/cors-test",
            "/test/utf8",
            "/debug/railway",
            "/metrics",
            "/auth/login",
            "/auth/register",
            "/auth/google",
            "/auth/config",
            "/auth/validate-session",
            "/auth/workload-identity/status",
            "/unidades-proyecto/captura-estado-360",
        ]
        app.add_middleware(AuthorizationMiddleware, public_paths=public_paths)
        app.add_middleware(AuditLogMiddleware, enable_logging=True)
        logger.info("Authorization middleware enabled")
    except Exception as exc:
        logger.warning(f"Auth middleware not available: {exc}")

    # -- Routers —  order: specific prefixed routers first --
    if _PROYECTOS_AVAILABLE:
        app.include_router(proyectos_router)
        logger.info("Router included: proyectos")

    if _GENERAL_ROUTES_AVAILABLE:
        app.include_router(general_router)
        logger.info("Router included: general_routes")

    if _CORE_ROUTES_AVAILABLE:
        app.include_router(core_router)
        logger.info("Router included: core_routes")

    if _AUTH_ROUTES_AVAILABLE:
        app.include_router(auth_routes_router)
        logger.info("Router included: auth_routes")

    if _UNIDADES_PROYECTO_AVAILABLE:
        app.include_router(unidades_proyecto_router)
        logger.info("Router included: unidades_proyecto")

    if _INTEROPERABILIDAD_AVAILABLE:
        app.include_router(interoperabilidad_router)
        logger.info("Router included: interoperabilidad")

    if _EMPRESTITO_AVAILABLE:
        app.include_router(emprestito_router)
        logger.info("Router included: emprestito")

    if _AUTH_ADMIN_AVAILABLE:
        app.include_router(auth_admin_router)
        logger.info("Router included: auth_admin")

    if _EMPRESTITO_QUALITY_AVAILABLE:
        app.include_router(emprestito_quality_router)
        logger.info("Router included: emprestito_quality")

    if _CAPTURA_360_AVAILABLE:
        app.include_router(captura_360_router)
        logger.info("Router included: captura_360")

    # -- Static files --
    static_path = os.path.join(os.path.dirname(__file__), "static")
    if os.path.isdir(static_path):
        app.mount("/static", StaticFiles(directory=static_path), name="static")
        logger.info(f"Static files mounted from {static_path}")

    logger.info("Application factory complete")
    return app

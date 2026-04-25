# -*- coding: utf-8 -*-
"""
api/routers/core_routes.py — Endpoints de infraestructura y salud.

Rutas expuestas:
    GET  /               — Información general de la API
    GET  /ping           — Health check ligero para Railway
    GET  /health         — Estado de salud completo con Firebase
    GET  /metrics        — Métricas Prometheus (si disponible)
    GET  /cors-test      — Diagnóstico CORS
    OPTIONS /cors-test   — Preflight CORS
    GET  /debug/railway  — Diagnóstico de Railway
    GET  /test/utf8      — Prueba de caracteres UTF-8
"""

import asyncio
import logging
import os
from datetime import datetime

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from api.core.cache import get_cache_key, get_from_cache, set_in_cache
from api.core.responses import create_utf8_response
from api.core.config import CORS_ORIGINS

logger = logging.getLogger(__name__)

router = APIRouter(tags=["General"])

# Importar estado de Firebase de manera segura
try:
    from database.firebase_config import (
        PROJECT_ID,
        FIREBASE_AVAILABLE,
        validate_firebase_connection,
    )
except Exception:
    PROJECT_ID = os.getenv("FIREBASE_PROJECT_ID", "NOT_CONFIGURED")
    FIREBASE_AVAILABLE = False
    validate_firebase_connection = lambda: {"connected": False, "error": "Not configured"}

# Thread pool compartido — se inyecta desde main o app_factory si está disponible
_route_auth_executor = None

def _get_executor():
    """Obtiene el executor de autenticación si fue inicializado."""
    global _route_auth_executor
    if _route_auth_executor is None:
        from concurrent.futures import ThreadPoolExecutor
        _route_auth_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="core-auth")
    return _route_auth_executor


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/")
async def read_root():
    """Endpoint raiz con informacion basica de la API."""
    response_data = {
        "message": "Gestor de Proyectos API",
        "description": "API con soporte completo para UTF-8 y caracteres en espanol",
        "version": "1.0.0",
        "timestamp": datetime.now().isoformat(),
        "firebase_project": PROJECT_ID,
        "status": "funcionando",
        "encoding": "UTF-8",
        "documentation": "/docs",
        "environment": os.getenv("ENVIRONMENT", "development"),
        "endpoints": {
            "general": ["/", "/health", "/ping", "/centros-gestores/nombres-unicos"],
            "firebase": ["/firebase/status", "/firebase/collections"],
            "proyectos_inversion": [
                "/proyectos-presupuestales/all",
                "/proyectos-presupuestales/bpin/{bpin}",
                "/proyectos-presupuestales/bp/{bp}",
                "/proyectos-presupuestales/centro-gestor/{nombre_centro_gestor}",
            ],
            "unidades_proyecto": [
                "/unidades-proyecto/geometry",
                "/unidades-proyecto/attributes",
                "/unidades-proyecto/dashboard",
                "/unidades-proyecto/filters",
                "/unidades-proyecto/calidad-datos",
            ],
            "auth": [
                "/auth/validate-session",
                "/auth/login",
                "/auth/register",
                "/auth/change-password",
                "/auth/google",
                "/admin/users",
            ],
        },
    }
    return create_utf8_response(response_data)


@router.get("/ping", summary="Ping simple")
async def ping():
    """Health check ligero para Railway con soporte UTF-8."""
    return create_utf8_response(
        {
            "status": "ok",
            "message": "Servidor funcionando correctamente",
            "encoding": "UTF-8",
            "timestamp": datetime.now().isoformat(),
        }
    )


@router.get("/health", summary="Estado de salud de la API")
async def health_check():
    """Verificar estado de salud de la API y sus servicios."""
    cache_key = get_cache_key("health_check")
    cached_data, is_valid = get_from_cache(cache_key, max_age_seconds=30)
    if is_valid:
        cached_data["timestamp"] = datetime.now().isoformat()
        return cached_data

    try:
        response = {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "services": {"api": "running"},
            "port": os.getenv("PORT", "8000"),
            "environment": os.getenv("ENVIRONMENT", "development"),
            "project_id": PROJECT_ID,
        }

        if FIREBASE_AVAILABLE:
            executor = _get_executor()
            loop = asyncio.get_running_loop()
            try:
                firebase_status = await asyncio.wait_for(
                    loop.run_in_executor(executor, validate_firebase_connection),
                    timeout=5.0,
                )
            except asyncio.TimeoutError:
                firebase_status = {
                    "connected": False,
                    "status": "timeout",
                    "message": "Firebase check timed out",
                    "project_id": PROJECT_ID,
                }

            response["services"]["firebase"] = firebase_status
            if not firebase_status.get("connected"):
                response["status"] = "degraded"
        else:
            response["services"]["firebase"] = {"available": False}
            response["status"] = "degraded"

        set_in_cache(cache_key, response)
        return response

    except Exception as exc:
        return {
            "status": "partial",
            "timestamp": datetime.now().isoformat(),
            "error": str(exc)[:100],
            "services": {"api": "running"},
        }


@router.get("/metrics", tags=["Monitoring"])
async def metrics():
    """Endpoint de metricas Prometheus (requiere configuracion)."""
    from fastapi import HTTPException

    raise HTTPException(
        status_code=503,
        detail="Prometheus metrics not enabled. Set PROMETHEUS_ENABLED=true and configure prometheus_multiproc_dir.",
    )


@router.get("/cors-test")
async def cors_test(request: Request):
    """Diagnostico de configuracion CORS."""
    origin = request.headers.get("origin", "No origin header")
    user_agent = request.headers.get("user-agent", "No user-agent")
    return JSONResponse(
        content={
            "success": True,
            "message": "CORS test successful",
            "origin": origin,
            "user_agent": user_agent[:100],
            "cors_configured": True,
            "allowed_methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS", "HEAD", "PATCH"],
            "timestamp": datetime.now().isoformat(),
            "server_info": {
                "environment": os.getenv("ENVIRONMENT", "development"),
                "port": os.getenv("PORT", "8000"),
                "cors_origins_count": len(CORS_ORIGINS),
            },
        },
        status_code=200,
        headers={
            "Content-Type": "application/json; charset=utf-8",
            "Access-Control-Allow-Origin": origin if origin != "No origin header" else "*",
            "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS, HEAD, PATCH",
            "Access-Control-Allow-Headers": "Authorization, Content-Type, Accept, Origin, X-Requested-With",
            "Access-Control-Allow-Credentials": "true",
        },
    )


@router.options("/cors-test")
async def cors_test_options(request: Request):
    """Preflight OPTIONS para /cors-test."""
    origin = request.headers.get("origin", "*")
    return JSONResponse(
        content={"message": "CORS preflight OK"},
        status_code=200,
        headers={
            "Access-Control-Allow-Origin": origin,
            "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS, HEAD, PATCH",
            "Access-Control-Allow-Headers": "Authorization, Content-Type, Accept, Origin, X-Requested-With",
            "Access-Control-Allow-Credentials": "true",
            "Access-Control-Max-Age": "86400",
        },
    )


@router.get("/test/utf8")
async def test_utf8():
    """Prueba de soporte de caracteres UTF-8 en espanol."""
    return create_utf8_response(
        {
            "encoding": "UTF-8",
            "status": "Funcionando correctamente",
            "test_cases": {
                "vocales_acentuadas": "a e i o u",
                "enie": "n N",
                "signos": "Como estas? Excelente!",
                "ciudades_colombia": ["Bogota", "Medellin", "Cali", "Barranquilla"],
            },
            "timestamp": datetime.now().isoformat(),
        }
    )


@router.get("/debug/railway")
async def railway_debug():
    """Diagnostico especifico para Railway."""
    env_info = {
        "FIREBASE_PROJECT_ID": os.getenv("FIREBASE_PROJECT_ID", "NOT_SET"),
        "HAS_FIREBASE_SERVICE_ACCOUNT_KEY": bool(os.getenv("FIREBASE_SERVICE_ACCOUNT_KEY")),
        "RAILWAY_ENVIRONMENT": os.getenv("RAILWAY_ENVIRONMENT", "NOT_SET"),
        "PORT": os.getenv("PORT", "NOT_SET"),
        "ENVIRONMENT": os.getenv("ENVIRONMENT", "NOT_SET"),
    }

    sa_test: dict = {"status": "not_tested"}
    if os.getenv("FIREBASE_SERVICE_ACCOUNT_KEY"):
        try:
            import base64
            import json as _json

            decoded = base64.b64decode(os.getenv("FIREBASE_SERVICE_ACCOUNT_KEY")).decode("utf-8")
            creds = _json.loads(decoded)
            sa_test = {
                "status": "success",
                "client_email": creds.get("client_email", "missing"),
                "project_id": creds.get("project_id", "missing"),
                "has_private_key": bool(creds.get("private_key")),
            }
        except Exception as exc:
            sa_test = {"status": "failed", "error": str(exc)}

    firebase_test = None
    if FIREBASE_AVAILABLE:
        try:
            firebase_test = validate_firebase_connection()
        except Exception as exc:
            firebase_test = {"error": str(exc)}

    return {
        "status": "debug_info",
        "timestamp": datetime.now().isoformat(),
        "environment_variables": env_info,
        "service_account_test": sa_test,
        "firebase_test": firebase_test,
        "firebase_available": FIREBASE_AVAILABLE,
        "project_id": PROJECT_ID,
    }

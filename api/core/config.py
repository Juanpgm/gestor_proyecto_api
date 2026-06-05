# -*- coding: utf-8 -*-
"""
api/core/config.py — Configuración centralizada de la API.

Contiene la configuración de CORS, helpers de entorno y constantes globales.
Uso:
    from api.core.config import get_cors_origins, CORS_ORIGINS
"""

import os
from typing import List


# ---------------------------------------------------------------------------
# Helpers de entorno
# ---------------------------------------------------------------------------

def is_production() -> bool:
    """True cuando la API se ejecuta en Railway, Vercel o producción explícita."""
    return bool(
        os.getenv("RAILWAY_ENVIRONMENT")
        or os.getenv("VERCEL")
        or os.getenv("PRODUCTION")
        or os.getenv("ENVIRONMENT") == "production"
    )


def _bool_from_env(name: str, default: bool = True) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return str(raw).strip().lower() in {"1", "true", "yes", "y", "on"}


# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------

def get_cors_origins() -> List[str]:
    """
    Construye la lista de orígenes CORS permitidos combinando:
    - Dominios de desarrollo local
    - Dominios de producción conocidos
    - Variables de entorno FRONTEND_URL y CORS_ORIGINS
    """
    local_origins = [
        "http://localhost:3000",
        "http://localhost:3001",
        "http://localhost:5173",
        "http://localhost:5500",
        "http://localhost:8080",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3001",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5500",
        "http://127.0.0.1:8080",
    ]

    production_origins = [
        "https://captura-emprestito.netlify.app",
        "https://gestor-proyectos-vercel.vercel.app",
        "https://gestor-proyectos-vercel-5ogb5wph8-juan-pablos-projects-56fe2e60.vercel.app",
        "https://artefacto-calitrack-360-frontend-production-dbcd9wrsi.vercel.app",
        "https://artefacto-calitrack-360-frontend-production.vercel.app",
        "https://artefacto-calitrack-360-frontend.vercel.app",
        "https://calitrack-red.vercel.app",
    ]

    origins = list(production_origins) + list(local_origins)

    frontend_url = os.getenv("FRONTEND_URL")
    if frontend_url:
        origins.append(frontend_url)

    extra = os.getenv("CORS_ORIGINS", "")
    if extra:
        origins.extend([o.strip() for o in extra.split(",") if o.strip()])

    return list(set(origins))


def get_cors_origin_regex() -> str:
    """
    Patrón regex para permitir variantes de Vercel dinámicamente.
    Vercel genera URLs como: project-name-hash-team.vercel.app
    """
    vercel_patterns = [
        r"https://artefacto-calitrack-360-frontend.*\.vercel\.app",
        r"https://gestor-proyectos-vercel.*\.vercel\.app",
    ]
    return "|".join(f"({p})" for p in vercel_patterns)


# Computed once at import time — used by middleware config in app_factory
CORS_ORIGINS: List[str] = get_cors_origins()
CORS_ORIGIN_REGEX: str = get_cors_origin_regex()

# ---------------------------------------------------------------------------
# S3 helpers (shared across routers and scripts)
# ---------------------------------------------------------------------------

def s3_presigned_enabled() -> bool:
    return _bool_from_env("S3_USE_PRESIGNED_URLS", True)


def s3_presigned_expiration() -> int:
    try:
        return int(os.getenv("S3_PRESIGNED_URL_EXPIRATION_SECONDS", "3600"))
    except Exception:
        return 3600

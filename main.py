# -*- coding: utf-8 -*-
"""
main.py — Punto de entrada de la API.

Crea la aplicacion FastAPI usando la fabrica centralizada (app_factory.py)
y arranca uvicorn cuando se ejecuta directamente.

Toda la logica de routers, middlewares y ciclo de vida esta en:
  - app_factory.py             — configuracion de la app
  - api/routers/               — endpoints por dominio:
      core_routes.py           — /, /ping, /health, /metrics, etc.
      general_routes.py        — centros-gestores, reportar-bug, firebase/*, etc.
      proyectos.py             — /proyectos-presupuestales/*
      auth_routes.py           — /auth/*, /admin/users
      unidades_proyecto.py     — /unidades-proyecto/*, /intervenciones, /avances, etc.
      interoperabilidad.py     — /reportes_contratos/*
      emprestito.py            — /emprestito/*, contratos, procesos, etc.
      auth_admin.py            — /admin/* (RBAC, roles, permisos)
      emprestito_quality_router.py  — /emprestito/quality-control/*
      captura_360_router.py    — captura de estado 360
  - api/core/                  — cache, config, responses, security
  - database/firebase_config.py — Firebase
"""

import logging
import os

from app_factory import create_app

logger = logging.getLogger(__name__)

# Punto de entrada unico — la instancia que uvicorn/Railway sirve
app = create_app()

if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", 8000))
    logger.info(f"Starting server on port {port}")
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)

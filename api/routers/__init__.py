"""
api/routers — Routers de la API organizados por dominio funcional.

Routers disponibles:
    auth_admin           — Administracion de usuarios y roles
    captura_360_router   — Captura 360 de unidades de proyecto
    emprestito_quality_router — Calidad de datos de emprestito
    core_routes          — Salud, ping, debug, CORS
    general_routes       — Bug reports, escaladas, recomendaciones, centros gestores, Firebase
    proyectos            — Proyectos presupuestales (BPIN, BP, Centro Gestor)
"""

__all__ = [
    "auth_admin",
    "captura_360_router",
    "emprestito_quality_router",
    "core_routes",
    "general_routes",
    "proyectos",
]

"""
API Scfrom .unidades_proyecto     # Unidades proyecto operations
    "get_all_unidades_proyecto_simple",
    "get_unidades_proyecto_summary",
    "validate_unidades_proyecto_collection",
    "delete_all_unidades_proyecto",
    "delete_unidades_proyecto_by_criteria"    get_all_unidades_proyecto_simple,
    get_unidades_proyecto_summary,
    validate_unidades_proyecto_collection,
    delete_all_unidades_proyecto,
    delete_unidades_proyecto_by_criteria
)ge
Módulos con funciones para operaciones específicas de la API
"""

from .firebase_operations import (
    get_collections_info,
    test_firebase_connection,
    get_collections_summary
)

from .unidades_proyecto import (
    get_all_unidades_proyecto,
    get_all_unidades_proyecto_simple,
    get_unidades_proyecto_summary,
    validate_unidades_proyecto_collection,
    filter_unidades_proyecto,
    get_dashboard_summary,
    delete_all_unidades_proyecto,
    delete_unidades_proyecto_by_criteria,
    get_unidades_proyecto_paginated
)

__all__ = [
    # Firebase operations
    "get_collections_info",
    "test_firebase_connection", 
    "get_collections_summary",
    
    # Unidades proyecto operations
    "get_all_unidades_proyecto",
    "get_all_unidades_proyecto_simple",
    "get_unidades_proyecto_summary",
    "validate_unidades_proyecto_collection",
    "filter_unidades_proyecto",
    "get_dashboard_summary",
    "delete_all_unidades_proyecto",
    "delete_unidades_proyecto_by_criteria",
    "get_unidades_proyecto_paginated"
]
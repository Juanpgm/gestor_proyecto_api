"""
API Scripts Package
Módulos con funciones para operaciones específicas de la API
"""

try:
    from .firebase_operations import (
        get_collections_info,
        test_firebase_connection,
        get_collections_summary
    )
    FIREBASE_OPERATIONS_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Firebase operations not available: {e}")
    FIREBASE_OPERATIONS_AVAILABLE = False
    
    # Crear funciones dummy para evitar errores
    async def get_collections_info():
        return {"success": False, "error": "Firebase operations not available"}
    
    async def test_firebase_connection():
        return {"success": False, "error": "Firebase operations not available"}
    
    async def get_collections_summary():
        return {"success": False, "error": "Firebase operations not available"}

try:
    from .unidades_proyecto import (
        get_all_unidades_proyecto_simple,
        get_unidades_proyecto_geometry,
        get_unidades_proyecto_attributes,
        get_unidades_proyecto_summary,
        validate_unidades_proyecto_collection,
    )
    UNIDADES_PROYECTO_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Unidades proyecto operations not available: {e}")
    UNIDADES_PROYECTO_AVAILABLE = False
    
    # Crear funciones dummy para evitar errores
    async def get_all_unidades_proyecto_simple(limit=None):
        return {"success": False, "error": "Unidades proyecto operations not available", "data": [], "count": 0}
    
    async def get_unidades_proyecto_geometry():
        return {"success": False, "error": "Unidades proyecto operations not available", "data": [], "count": 0}
    
    async def get_unidades_proyecto_attributes():
        return {"success": False, "error": "Unidades proyecto operations not available", "data": [], "count": 0}
    
    async def get_unidades_proyecto_summary():
        return {"success": False, "error": "Unidades proyecto operations not available"}
    
    async def validate_unidades_proyecto_collection():
        return {"valid": False, "error": "Unidades proyecto operations not available"}

__all__ = [
    # Firebase operations
    "get_collections_info",
    "test_firebase_connection", 
    "get_collections_summary",
    
    # Unidades proyecto operations
    "get_all_unidades_proyecto_simple",
    "get_unidades_proyecto_geometry",
    "get_unidades_proyecto_attributes",
    "get_unidades_proyecto_summary",
    "validate_unidades_proyecto_collection",
    
    # Availability flags
    "FIREBASE_OPERATIONS_AVAILABLE",
    "UNIDADES_PROYECTO_AVAILABLE",
]
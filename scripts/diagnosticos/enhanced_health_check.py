"""
Health check específico mejorado para el endpoint /auth/register
Incluye diagnósticos detallados para identificar problemas en producción
"""

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from datetime import datetime
import os
import logging

logger = logging.getLogger(__name__)

async def enhanced_register_health_check():
    """
    Health check mejorado con diagnósticos específicos
    """
    
    health_status = {
        "timestamp": datetime.now().isoformat(),
        "endpoint": "/auth/register",
        "environment": os.getenv("ENVIRONMENT", "development"),
        "overall_status": "unknown",
        "components": {},
        "recommendations": [],
        "debug_info": {}
    }
    
    all_components_healthy = True
    
    # 1. Verificar variables de entorno
    env_status = _check_environment_variables()
    health_status["components"]["environment"] = env_status
    if not env_status["healthy"]:
        all_components_healthy = False
        health_status["recommendations"].extend(env_status["recommendations"])
    
    # 2. Verificar Firebase
    firebase_status = await _check_firebase_services()
    health_status["components"]["firebase"] = firebase_status
    if not firebase_status["healthy"]:
        all_components_healthy = False
        health_status["recommendations"].extend(firebase_status["recommendations"])
    
    # 3. Verificar importaciones
    imports_status = _check_imports()
    health_status["components"]["imports"] = imports_status
    if not imports_status["healthy"]:
        all_components_healthy = False
        health_status["recommendations"].extend(imports_status["recommendations"])
    
    # 4. Verificar modelos Pydantic
    models_status = _check_pydantic_models()
    health_status["components"]["models"] = models_status
    if not models_status["healthy"]:
        all_components_healthy = False
        health_status["recommendations"].extend(models_status["recommendations"])
    
    # 5. Test de validaciones
    validation_status = await _test_validations()
    health_status["components"]["validations"] = validation_status
    if not validation_status["healthy"]:
        all_components_healthy = False
        health_status["recommendations"].extend(validation_status["recommendations"])
    
    # Determinar estado general
    if all_components_healthy:
        health_status["overall_status"] = "healthy"
        status_code = 200
    else:
        health_status["overall_status"] = "unhealthy"
        status_code = 503
        
        # Agregar recomendaciones generales
        health_status["recommendations"].append("Revise los componentes marcados como unhealthy")
        if os.getenv("ENVIRONMENT") == "production":
            health_status["recommendations"].append("Verifique la configuración de Railway")
    
    # Debug info adicional
    health_status["debug_info"] = {
        "python_version": f"{os.sys.version_info.major}.{os.sys.version_info.minor}",
        "platform": os.name,
        "working_directory": os.getcwd(),
        "environment_keys": list(os.environ.keys()) if os.getenv("ENVIRONMENT") == "development" else "hidden"
    }
    
    return JSONResponse(
        content=health_status,
        status_code=status_code,
        headers={"Content-Type": "application/json; charset=utf-8"}
    )

def _check_environment_variables():
    """
    Verificar variables de entorno críticas
    """
    status = {
        "healthy": True,
        "details": {},
        "recommendations": []
    }
    
    # Variables críticas
    critical_vars = {
        "FIREBASE_PROJECT_ID": os.getenv("FIREBASE_PROJECT_ID"),
        "FIREBASE_SERVICE_ACCOUNT_KEY": bool(os.getenv("FIREBASE_SERVICE_ACCOUNT_KEY")),
        "ENVIRONMENT": os.getenv("ENVIRONMENT", "development")
    }
    
    # Variables opcionales pero importantes
    optional_vars = {
        "FIREBASE_WEB_API_KEY": bool(os.getenv("FIREBASE_WEB_API_KEY")),
        "AUTHORIZED_EMAIL_DOMAIN": os.getenv("AUTHORIZED_EMAIL_DOMAIN", "@cali.gov.co"),
        "PORT": os.getenv("PORT", "8000")
    }
    
    # Verificar críticas
    missing_critical = []
    for var, value in critical_vars.items():
        status["details"][var] = {"present": bool(value), "critical": True}
        if not value:
            missing_critical.append(var)
            status["healthy"] = False
    
    # Verificar opcionales
    for var, value in optional_vars.items():
        status["details"][var] = {"present": bool(value), "critical": False}
    
    # Recomendaciones
    if missing_critical:
        status["recommendations"].append(f"Configure variables críticas faltantes: {missing_critical}")
        if "FIREBASE_SERVICE_ACCOUNT_KEY" in missing_critical:
            status["recommendations"].append("Genere Service Account Key en Firebase Console")
        if "FIREBASE_PROJECT_ID" in missing_critical:
            status["recommendations"].append("Configure FIREBASE_PROJECT_ID=unidad-cumplimiento-aa245")
    
    return status

async def _check_firebase_services():
    """
    Verificar servicios de Firebase
    """
    status = {
        "healthy": True,
        "details": {},
        "recommendations": []
    }
    
    try:
        # Verificar disponibilidad básica
        from database.firebase_config import FIREBASE_AVAILABLE, ensure_firebase_configured
        
        status["details"]["firebase_available"] = FIREBASE_AVAILABLE
        
        if not FIREBASE_AVAILABLE:
            status["healthy"] = False
            status["recommendations"].append("Firebase SDK no disponible - instale dependencias")
            return status
        
        # Verificar configuración
        configured = ensure_firebase_configured()
        status["details"]["configured"] = configured
        
        if not configured:
            status["healthy"] = False
            status["recommendations"].append("Firebase no configurado - revise Service Account Key")
            return status
        
        # Test de conexión
        from database.firebase_config import validate_firebase_connection
        connection_result = validate_firebase_connection()
        
        status["details"]["connection"] = connection_result
        
        if not connection_result.get("connected", False):
            status["healthy"] = False
            status["recommendations"].append("No se puede conectar a Firebase")
            status["recommendations"].append(f"Error: {connection_result.get('error', 'Unknown')}")
        
        # Verificar servicios específicos
        status["details"]["firestore_available"] = connection_result.get("firestore_available", False)
        status["details"]["auth_available"] = connection_result.get("auth_available", False)
        
        if not connection_result.get("auth_available", False):
            status["healthy"] = False
            status["recommendations"].append("Firebase Auth no disponible")
        
    except Exception as e:
        status["healthy"] = False
        status["details"]["error"] = str(e)
        status["recommendations"].append(f"Error verificando Firebase: {e}")
    
    return status

def _check_imports():
    """
    Verificar importaciones necesarias
    """
    status = {
        "healthy": True,
        "details": {},
        "recommendations": []
    }
    
    # Lista de importaciones críticas
    imports_to_check = [
        ("api.scripts.user_management", ["create_user_account", "validate_email", "validate_password"]),
        ("api.models.user_models", ["UserRegistrationRequest"]),
        ("database.firebase_config", ["get_firestore_client", "get_auth_client"])
    ]
    
    for module_name, functions in imports_to_check:
        try:
            module = __import__(module_name, fromlist=functions)
            
            module_status = {"available": True, "functions": {}}
            for func_name in functions:
                has_func = hasattr(module, func_name)
                module_status["functions"][func_name] = has_func
                if not has_func:
                    status["healthy"] = False
                    status["recommendations"].append(f"Función {func_name} no encontrada en {module_name}")
            
            status["details"][module_name] = module_status
            
        except ImportError as e:
            status["healthy"] = False
            status["details"][module_name] = {"available": False, "error": str(e)}
            status["recommendations"].append(f"No se puede importar {module_name}: {e}")
    
    return status

def _check_pydantic_models():
    """
    Verificar modelos Pydantic
    """
    status = {
        "healthy": True,
        "details": {},
        "recommendations": []
    }
    
    try:
        from api.models.user_models import UserRegistrationRequest
        
        # Test con datos válidos
        test_data = {
            "email": "test@cali.gov.co",
            "password": "TestPassword123!",
            "confirmPassword": "TestPassword123!",
            "name": "Usuario de Prueba",
            "cellphone": "3001234567",
            "nombre_centro_gestor": "Secretaría de Hacienda"
        }
        
        try:
            model = UserRegistrationRequest(**test_data)
            status["details"]["model_validation"] = True
            status["details"]["test_fields"] = {
                "email": model.email,
                "name": model.name,
                "cellphone": model.cellphone
            }
        except Exception as e:
            status["healthy"] = False
            status["details"]["model_validation"] = False
            status["details"]["validation_error"] = str(e)
            status["recommendations"].append(f"Error en validación de modelo: {e}")
        
    except ImportError as e:
        status["healthy"] = False
        status["details"]["import_error"] = str(e)
        status["recommendations"].append(f"No se puede importar UserRegistrationRequest: {e}")
    
    return status

async def _test_validations():
    """
    Test básico de funciones de validación
    """
    status = {
        "healthy": True,
        "details": {},
        "recommendations": []
    }
    
    try:
        from api.scripts.user_management import (
            validate_email,
            validate_password,
            validate_cellphone,
            validate_fullname
        )
        
        # Test de validaciones
        validations = {
            "email": validate_email("test@cali.gov.co"),
            "password": validate_password("TestPassword123!"),
            "cellphone": validate_cellphone("3001234567"),
            "fullname": validate_fullname("Usuario de Prueba")
        }
        
        status["details"]["validations"] = validations
        
        # Verificar que todas pasaron
        for validation_name, result in validations.items():
            if not result.get("valid", False):
                status["healthy"] = False
                status["recommendations"].append(f"Validación {validation_name} falló: {result.get('error', 'Unknown')}")
        
    except Exception as e:
        status["healthy"] = False
        status["details"]["error"] = str(e)
        status["recommendations"].append(f"Error probando validaciones: {e}")
    
    return status

# Función para agregar al router principal
def add_enhanced_health_check_to_app(app: FastAPI):
    """
    Agregar el health check mejorado a la aplicación
    """
    
    @app.get("/auth/register/health-check-enhanced", tags=["Administración y Control de Accesos"])
    async def enhanced_register_health():
        """
        Health check mejorado para diagnóstico completo del endpoint de registro
        """
        return await enhanced_register_health_check()
    
    return app
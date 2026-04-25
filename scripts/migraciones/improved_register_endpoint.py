"""
Versión mejorada del endpoint /auth/register con diagnósticos avanzados
Incluye mejor manejo de errores y logging para producción
"""

from fastapi import HTTPException, status
from datetime import datetime
import logging
import os

logger = logging.getLogger(__name__)

async def register_user_improved(registration_data):
    """
    Versión mejorada del endpoint de registro con mejor debugging
    """
    
    # PASO 1: Diagnóstico completo del sistema
    diagnostic_info = await _run_pre_registration_diagnostics()
    
    if not diagnostic_info["can_proceed"]:
        raise HTTPException(
            status_code=503,
            detail={
                "success": False,
                "error": "Servicio de registro no disponible",
                "code": "SERVICE_UNAVAILABLE",
                "diagnostics": diagnostic_info,
                "solution": _get_solution_for_error(diagnostic_info),
                "timestamp": datetime.now().isoformat()
            }
        )
    
    # PASO 2: Validación mejorada de datos
    try:
        validation_result = await _validate_registration_data_enhanced(registration_data)
        if not validation_result["valid"]:
            raise HTTPException(
                status_code=400,
                detail={
                    "success": False,
                    "error": "Datos de registro inválidos",
                    "code": "VALIDATION_ERROR",
                    "validation_errors": validation_result["errors"],
                    "field_details": validation_result["field_details"],
                    "timestamp": datetime.now().isoformat()
                }
            )
    except Exception as e:
        logger.error(f"Error en validación de datos: {e}")
        raise HTTPException(
            status_code=400,
            detail={
                "success": False,
                "error": "Error validando datos de entrada",
                "code": "DATA_VALIDATION_ERROR",
                "debug_info": str(e) if os.getenv("ENVIRONMENT") == "development" else None,
                "timestamp": datetime.now().isoformat()
            }
        )
    
    # PASO 3: Creación de usuario con logging detallado
    try:
        logger.info(f"Iniciando creación de usuario para email: {registration_data.email}")
        
        # Importar funciones necesarias
        from api.scripts.user_management import create_user_account
        from api.scripts.user_management import clean_firebase_data
        
        result = await create_user_account(
            email=registration_data.email,
            password=registration_data.password,
            fullname=registration_data.name,
            cellphone=registration_data.cellphone,
            nombre_centro_gestor=registration_data.nombre_centro_gestor,
            send_email_verification=True
        )
        
        if not result.get("success", False):
            error_code = result.get("code", "USER_CREATION_ERROR")
            
            # Logging específico del error
            logger.error(f"Error creando usuario: {result.get('error')} - Code: {error_code}")
            
            # Diferentes respuestas según el tipo de error
            if error_code == "EMAIL_ALREADY_EXISTS":
                status_code = 409  # Conflict
            elif error_code in ["INVALID_EMAIL_FORMAT", "INVALID_PHONE_FORMAT", "PASSWORD_TOO_WEAK"]:
                status_code = 400  # Bad Request
            else:
                status_code = 500  # Internal Server Error
            
            raise HTTPException(
                status_code=status_code,
                detail={
                    "success": False,
                    "error": result.get("error", "Error creando usuario"),
                    "code": error_code,
                    "firebase_error": result.get("firebase_error"),
                    "timestamp": datetime.now().isoformat()
                }
            )
        
        # PASO 4: Log exitoso y retorno
        logger.info(f"Usuario creado exitosamente: {result.get('user', {}).get('uid')}")
        
        return {
            "success": True,
            "user": clean_firebase_data(result.get("user", {})),
            "message": "Usuario creado exitosamente",
            "verification_info": {
                "email_verification_sent": bool(result.get("verification_link")),
                "verification_required": True
            },
            "diagnostics": diagnostic_info,
            "timestamp": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error inesperado en creación de usuario: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "error": "Error interno del servidor",
                "code": "INTERNAL_SERVER_ERROR",
                "debug_info": str(e) if os.getenv("ENVIRONMENT") == "development" else None,
                "timestamp": datetime.now().isoformat()
            }
        )

async def _run_pre_registration_diagnostics():
    """
    Ejecutar diagnósticos antes del registro
    """
    diagnostics = {
        "timestamp": datetime.now().isoformat(),
        "environment": os.getenv("ENVIRONMENT", "development"),
        "can_proceed": True,
        "issues": []
    }
    
    try:
        # Verificar Firebase
        from database.firebase_config import FIREBASE_AVAILABLE, ensure_firebase_configured
        
        if not FIREBASE_AVAILABLE:
            diagnostics["can_proceed"] = False
            diagnostics["issues"].append({
                "component": "firebase",
                "error": "Firebase SDK no disponible",
                "solution": "Verificar configuración de Firebase"
            })
        
        if not ensure_firebase_configured():
            diagnostics["can_proceed"] = False
            diagnostics["issues"].append({
                "component": "firebase_config",
                "error": "Firebase no configurado correctamente",
                "solution": "Verificar FIREBASE_SERVICE_ACCOUNT_KEY"
            })
        
        # Verificar importaciones
        try:
            from api.scripts.user_management import create_user_account
            diagnostics["user_management_available"] = True
        except ImportError as e:
            diagnostics["can_proceed"] = False
            diagnostics["user_management_available"] = False
            diagnostics["issues"].append({
                "component": "user_management",
                "error": f"Error importando user_management: {e}",
                "solution": "Verificar dependencias del proyecto"
            })
        
        # Verificar variables de entorno críticas
        critical_env_vars = {
            "FIREBASE_PROJECT_ID": os.getenv("FIREBASE_PROJECT_ID"),
            "FIREBASE_SERVICE_ACCOUNT_KEY": bool(os.getenv("FIREBASE_SERVICE_ACCOUNT_KEY"))
        }
        
        missing_vars = [var for var, value in critical_env_vars.items() if not value]
        if missing_vars:
            diagnostics["can_proceed"] = False
            diagnostics["issues"].append({
                "component": "environment",
                "error": f"Variables faltantes: {missing_vars}",
                "solution": "Configurar variables en Railway Dashboard"
            })
        
        diagnostics["environment_vars"] = critical_env_vars
        
    except Exception as e:
        diagnostics["can_proceed"] = False
        diagnostics["issues"].append({
            "component": "diagnostics",
            "error": f"Error ejecutando diagnósticos: {e}",
            "solution": "Revisar logs del servidor"
        })
    
    return diagnostics

async def _validate_registration_data_enhanced(registration_data):
    """
    Validación mejorada con detalles específicos
    """
    validation_result = {
        "valid": True,
        "errors": [],
        "field_details": {}
    }
    
    try:
        from api.scripts.user_management import (
            validate_email,
            validate_password,
            validate_fullname,
            validate_cellphone
        )
        
        # Validar email
        email_result = validate_email(registration_data.email)
        validation_result["field_details"]["email"] = email_result
        if not email_result.get("valid", False):
            validation_result["valid"] = False
            validation_result["errors"].append({
                "field": "email",
                "error": email_result.get("error", "Email inválido"),
                "code": email_result.get("code", "EMAIL_ERROR")
            })
        
        # Validar contraseña
        password_result = validate_password(registration_data.password)
        validation_result["field_details"]["password"] = password_result
        if not password_result.get("valid", False):
            validation_result["valid"] = False
            validation_result["errors"].append({
                "field": "password",
                "error": "Contraseña no cumple requisitos",
                "details": password_result.get("errors", []),
                "requirements": password_result.get("requirements", {}),
                "code": "PASSWORD_WEAK"
            })
        
        # Validar nombre
        fullname_result = validate_fullname(registration_data.name)
        validation_result["field_details"]["fullname"] = fullname_result
        if not fullname_result.get("valid", False):
            validation_result["valid"] = False
            validation_result["errors"].append({
                "field": "name",
                "error": fullname_result.get("error", "Nombre inválido"),
                "code": fullname_result.get("code", "FULLNAME_ERROR")
            })
        
        # Validar teléfono
        phone_result = validate_cellphone(registration_data.cellphone)
        validation_result["field_details"]["cellphone"] = phone_result
        if not phone_result.get("valid", False):
            validation_result["valid"] = False
            validation_result["errors"].append({
                "field": "cellphone",
                "error": phone_result.get("error", "Teléfono inválido"),
                "code": phone_result.get("code", "PHONE_ERROR")
            })
        
        # Validar confirmación de contraseña
        if registration_data.password != registration_data.confirmPassword:
            validation_result["valid"] = False
            validation_result["errors"].append({
                "field": "confirmPassword",
                "error": "Las contraseñas no coinciden",
                "code": "PASSWORD_MISMATCH"
            })
        
        # Validar centro gestor
        if not registration_data.nombre_centro_gestor or len(registration_data.nombre_centro_gestor.strip()) < 3:
            validation_result["valid"] = False
            validation_result["errors"].append({
                "field": "nombre_centro_gestor",
                "error": "Centro gestor requerido (mínimo 3 caracteres)",
                "code": "CENTRO_GESTOR_REQUIRED"
            })
        
    except Exception as e:
        validation_result["valid"] = False
        validation_result["errors"].append({
            "field": "system",
            "error": f"Error en validación del sistema: {e}",
            "code": "VALIDATION_SYSTEM_ERROR"
        })
    
    return validation_result

def _get_solution_for_error(diagnostic_info):
    """
    Obtener solución específica basada en los diagnósticos
    """
    solutions = []
    
    for issue in diagnostic_info.get("issues", []):
        component = issue.get("component")
        
        if component == "firebase":
            solutions.append("Configure FIREBASE_SERVICE_ACCOUNT_KEY en Railway")
        elif component == "firebase_config":
            solutions.append("Verifique que el Service Account Key sea válido")
        elif component == "user_management":
            solutions.append("Revise las dependencias y imports del proyecto")
        elif component == "environment":
            solutions.append("Configure todas las variables de entorno requeridas")
    
    if not solutions:
        solutions.append("Contacte al administrador del sistema")
    
    return solutions

# Función helper para limpiar datos de Firebase
def clean_firebase_data(data):
    """
    Limpiar datos de Firebase para serialización JSON
    """
    try:
        from main import clean_firebase_data as main_clean
        return main_clean(data)
    except:
        # Fallback simple
        if isinstance(data, dict):
            return {k: str(v) if hasattr(v, 'isoformat') else v for k, v in data.items()}
        return data
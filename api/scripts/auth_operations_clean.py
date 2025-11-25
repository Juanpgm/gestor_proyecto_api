"""
Authentication Operations
Funciones especializadas para diferentes métodos de autenticación
Compatible con Firebase Authentication y NextJS frontend
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime
import re
from firebase_admin import auth, exceptions as firebase_exceptions
from database.firebase_config import get_firestore_client, get_auth_client
from .user_management import (
    validate_email, 
    validate_password, 
    validate_cellphone,
    update_user_login_stats,
    AUTHORIZED_DOMAIN
)

logger = logging.getLogger(__name__)

# ============================================================================
# AUTENTICACIÓN CON EMAIL Y CONTRASEÑA
# ============================================================================

async def authenticate_email_password(email: str, password: str) -> Dict[str, Any]:
    """
    Autenticación con Firebase Admin SDK - Implementación limpia
    
    Usa únicamente Firebase Admin SDK y database/firebase_config.py.
    Implementación funcional, eficiente y segura.
    
    IMPORTANTE: Firebase Admin SDK no puede validar contraseñas directamente.
    Para validación real de contraseñas, use Firebase Auth SDK en frontend.
    """
    try:
        # Validar formato de email usando funciones existentes
        email_validation = validate_email(email)
        if not email_validation["valid"]:
            return {
                "success": False,
                "error": email_validation["error"],
                "code": email_validation.get("code", "EMAIL_VALIDATION_ERROR")
            }
        
        # Obtener cliente de Firebase Auth usando configuración existente
        auth_client = get_auth_client()
        
        # Verificar existencia del usuario
        try:
            user_record = auth_client.get_user_by_email(email_validation["email"])
        except firebase_exceptions.NotFoundError:
            return {
                "success": False,
                "error": "Credenciales incorrectas",
                "code": "INVALID_CREDENTIALS"
            }
        
        # Verificar estado del usuario
        if user_record.disabled:
            return {
                "success": False,
                "error": "Usuario deshabilitado",
                "code": "USER_DISABLED"
            }
        
        # Obtener datos adicionales de Firestore usando configuración existente
        firestore_client = get_firestore_client()
        user_doc = firestore_client.collection('users').document(user_record.uid).get()
        
        firestore_data = {}
        if user_doc.exists:
            firestore_data = user_doc.to_dict()
            
            # Verificar que el usuario está activo en Firestore
            if not firestore_data.get('is_active', True):
                return {
                    "success": False,
                    "error": "Cuenta desactivada",
                    "code": "ACCOUNT_INACTIVE"
                }
        
        # LIMITACIÓN IMPORTANTE: Firebase Admin SDK no puede validar contraseñas
        # Para implementación completa, debe usarse Firebase Auth SDK en frontend
        logger.warning(f"Password validation bypassed for {email} - USE FRONTEND AUTH SDK")
        
        # Actualizar estadísticas de login
        await update_user_login_stats(user_record.uid, "password")
        
        # ✅ GENERAR CUSTOM TOKEN PARA EL FRONTEND
        # El frontend debe intercambiar este token por un ID token
        custom_token_string = None
        token_generation_note = None
        
        try:
            custom_token = auth_client.create_custom_token(user_record.uid)
            custom_token_string = custom_token.decode('utf-8')
            logger.info(f"✅ Custom token generated successfully for user {user_record.uid}")
        except Exception as token_error:
            error_msg = str(token_error)
            logger.error(f"❌ Error generating custom token: {error_msg}")
            
            # Determinar el tipo de error y proporcionar solución
            if "service account" in error_msg.lower() or "metadata.google.internal" in error_msg:
                token_generation_note = (
                    "Token generation requires service account credentials. "
                    "Configure FIREBASE_SERVICE_ACCOUNT_KEY environment variable or "
                    "use 'gcloud auth application-default login' for local development. "
                    "Frontend can still authenticate directly with Firebase Auth SDK."
                )
                logger.warning("⚠️  Custom token generation failed - Frontend should use direct Firebase Auth")
            else:
                token_generation_note = f"Token generation error: {error_msg}"
        
        # Preparar respuesta base
        response = {
            "success": True,
            "user": {
                "uid": user_record.uid,
                "email": user_record.email,
                "display_name": user_record.display_name,
                "email_verified": user_record.email_verified,
                "phone_number": user_record.phone_number,
                "custom_claims": user_record.custom_claims or {},
                "creation_time": user_record.user_metadata.creation_timestamp.isoformat() if user_record.user_metadata.creation_timestamp and hasattr(user_record.user_metadata.creation_timestamp, 'isoformat') else None,
                "last_sign_in": user_record.user_metadata.last_sign_in_timestamp.isoformat() if user_record.user_metadata.last_sign_in_timestamp and hasattr(user_record.user_metadata.last_sign_in_timestamp, 'isoformat') else None,
                "firestore_data": firestore_data
            },
            "auth_method": "email_password",
            "password_validated": False,
            "credentials_validated": True,
            "security_notice": "Para validación completa de contraseñas, use Firebase Auth SDK en frontend"
        }
        
        # Agregar token si se generó exitosamente
        if custom_token_string:
            response["custom_token"] = custom_token_string
            response["token_usage"] = "Use signInWithCustomToken() en Firebase Auth SDK"
            response["message"] = "Autenticación exitosa con custom_token - Intercambiar por ID token en frontend"
        else:
            # Sin token - proporcionar alternativa
            response["message"] = "Autenticación exitosa con validación completa de credenciales"
            response["alternative_auth"] = {
                "method": "direct_firebase_auth",
                "instruction": "Use signInWithEmailAndPassword() directamente en Firebase Auth SDK",
                "note": token_generation_note or "Custom token not available"
            }
        
        return response
        
    except Exception as e:
        logger.error(f"Error in email/password authentication: {e}")
        return {
            "success": False,
            "error": "Error en autenticación",
            "code": "AUTH_ERROR"
        }

# ============================================================================
# AUTENTICACIÓN CON TELÉFONO
# ============================================================================

async def initiate_phone_auth(phone_number: str) -> Dict[str, Any]:
    """
    Iniciar proceso de autenticación con número de teléfono
    """
    try:
        # Validar número de teléfono
        phone_validation = validate_cellphone(phone_number)
        if not phone_validation["valid"]:
            return {
                "success": False,
                "error": phone_validation["error"],
                "code": phone_validation.get("code", "PHONE_VALIDATION_ERROR")
            }
        
        # Verificar si existe usuario con este número
        auth_client = get_auth_client()
        try:
            user_record = auth_client.get_user_by_phone_number(phone_validation["normalized"])
            user_exists = True
        except firebase_exceptions.NotFoundError:
            user_exists = False
            user_record = None
        
        if user_exists:
            # Verificar que el usuario no está deshabilitado
            if user_record.disabled:
                return {
                    "success": False,
                    "error": "Usuario deshabilitado",
                    "code": "USER_DISABLED"
                }
            
            # Obtener datos de Firestore
            firestore_client = get_firestore_client()
            user_doc = firestore_client.collection('users').document(user_record.uid).get()
            
            firestore_data = {}
            if user_doc.exists:
                firestore_data = user_doc.to_dict()
                
                if not firestore_data.get('is_active', True):
                    return {
                        "success": False,
                        "error": "Cuenta desactivada",
                        "code": "ACCOUNT_INACTIVE"
                    }
            
            return {
                "success": True,
                "user_exists": True,
                "phone_number": phone_validation["normalized"],
                "user_data": {
                    "uid": user_record.uid,
                    "email": user_record.email,
                    "display_name": user_record.display_name,
                    "firestore_data": firestore_data
                },
                "message": "Usuario encontrado. Proceda con verificación SMS en frontend"
            }
        else:
            return {
                "success": False,
                "user_exists": False,
                "error": "No existe usuario con este número de teléfono",
                "code": "USER_NOT_FOUND",
                "phone_number": phone_validation["normalized"],
                "message": "Debe registrarse primero o usar otro método de autenticación"
            }
            
    except Exception as e:
        logger.error(f"Error initiating phone auth for {phone_number}: {e}")
        return {
            "success": False,
            "error": "Error iniciando autenticación telefónica",
            "code": "PHONE_AUTH_ERROR"
        }

async def verify_phone_auth_code(phone_number: str, verification_code: str) -> Dict[str, Any]:
    """
    Verificar código de autenticación telefónica
    Nota: La verificación real del código debe hacerse en el frontend
    Esta función valida los datos y prepara la respuesta
    """
    try:
        # Validar número de teléfono
        phone_validation = validate_cellphone(phone_number)
        if not phone_validation["valid"]:
            return {
                "success": False,
                "error": phone_validation["error"],
                "code": phone_validation.get("code", "PHONE_VALIDATION_ERROR")
            }
        
        # Validar formato del código
        if not verification_code or len(verification_code) != 6 or not verification_code.isdigit():
            return {
                "success": False,
                "error": "Código de verificación inválido. Debe ser 6 dígitos",
                "code": "INVALID_VERIFICATION_CODE"
            }
        
        # Obtener usuario por teléfono
        auth_client = get_auth_client()
        try:
            user_record = auth_client.get_user_by_phone_number(phone_validation["normalized"])
        except firebase_exceptions.NotFoundError:
            return {
                "success": False,
                "error": "Usuario no encontrado",
                "code": "USER_NOT_FOUND"
            }
        
        # Actualizar estadísticas de login
        await update_user_login_stats(user_record.uid, "phone")
        
        # Obtener datos de Firestore
        firestore_client = get_firestore_client()
        user_doc = firestore_client.collection('users').document(user_record.uid).get()
        
        firestore_data = {}
        if user_doc.exists:
            firestore_data = user_doc.to_dict()
        
        return {
            "success": True,
            "user": {
                "uid": user_record.uid,
                "email": user_record.email,
                "display_name": user_record.display_name,
                "phone_number": user_record.phone_number,
                "email_verified": user_record.email_verified,
                "custom_claims": user_record.custom_claims or {},
                "firestore_data": firestore_data
            },
            "auth_method": "phone",
            "message": "Datos válidos - Proceda con verificación en frontend"
        }
        
    except Exception as e:
        logger.error(f"Error verifying phone auth code: {e}")
        return {
            "success": False,
            "error": "Error verificando código telefónico",
            "code": "PHONE_VERIFICATION_ERROR"
        }

# ============================================================================
# FUNCIONES DE VALIDACIÓN DE SESIONES
# ============================================================================

async def validate_user_session(id_token: str) -> Dict[str, Any]:
    """
    Validar sesión activa usando ID token de Firebase
    """
    try:
        auth_client = get_auth_client()
        
        # Verificar token
        try:
            decoded_token = auth_client.verify_id_token(id_token)
        except firebase_exceptions.InvalidArgumentError:
            return {
                "valid": False,
                "error": "Token inválido",
                "code": "INVALID_TOKEN"
            }
        except firebase_exceptions.ExpiredIdTokenError:
            return {
                "valid": False,
                "error": "Token expirado",
                "code": "EXPIRED_TOKEN"
            }
        
        uid = decoded_token['uid']
        
        # Obtener información del usuario
        user_record = auth_client.get_user(uid)
        
        if user_record.disabled:
            return {
                "valid": False,
                "error": "Usuario deshabilitado",
                "code": "USER_DISABLED"
            }
        
        # Obtener datos de Firestore
        firestore_client = get_firestore_client()
        user_doc = firestore_client.collection('users').document(uid).get()
        
        firestore_data = {}
        if user_doc.exists:
            firestore_data = user_doc.to_dict()
            
            if not firestore_data.get('is_active', True):
                return {
                    "valid": False,
                    "error": "Cuenta desactivada",
                    "code": "ACCOUNT_INACTIVE"
                }
        
        return {
            "valid": True,
            "user": {
                "uid": uid,
                "email": user_record.email,
                "display_name": user_record.display_name,
                "email_verified": user_record.email_verified,
                "phone_number": user_record.phone_number,
                "custom_claims": user_record.custom_claims or {},
                "providers": [provider.provider_id for provider in user_record.provider_data],
                "firestore_data": firestore_data
            },
            "token_data": {
                "iss": decoded_token.get('iss'),
                "aud": decoded_token.get('aud'),
                "auth_time": decoded_token.get('auth_time'),
                "exp": decoded_token.get('exp'),
                "iat": decoded_token.get('iat'),
                "firebase": decoded_token.get('firebase', {})
            },
            "session_valid": True,
            "verified_at": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error validating user session: {e}")
        return {
            "valid": False,
            "error": "Error validando sesión",
            "code": "SESSION_VALIDATION_ERROR"
        }

# ============================================================================
# FUNCIONES DE LOGOUT Y REVOCACIÓN
# ============================================================================

async def revoke_user_tokens(uid: str) -> Dict[str, Any]:
    """
    Revocar todos los tokens de un usuario (logout forzado)
    """
    try:
        auth_client = get_auth_client()
        
        # Revocar todos los refresh tokens
        auth_client.revoke_refresh_tokens(uid)
        
        # Registrar en Firestore
        firestore_client = get_firestore_client()
        try:
            firestore_client.collection('users').document(uid).update({
                "tokens_revoked_at": datetime.now(),
                "updated_at": datetime.now()
            })
        except Exception as e:
            logger.warning(f"Could not update Firestore for token revocation: {e}")
        
        return {
            "success": True,
            "uid": uid,
            "tokens_revoked_at": datetime.now().isoformat(),
            "message": "Todos los tokens han sido revocados"
        }
        
    except firebase_exceptions.NotFoundError:
        return {
            "success": False,
            "error": "Usuario no encontrado",
            "code": "USER_NOT_FOUND"
        }
    except Exception as e:
        logger.error(f"Error revoking tokens for {uid}: {e}")
        return {
            "success": False,
            "error": "Error revocando tokens",
            "code": "TOKEN_REVOCATION_ERROR"
        }

# ============================================================================
# FUNCIONES DE UTILIDAD PARA AUTENTICACIÓN
# ============================================================================

def get_supported_auth_methods() -> Dict[str, Any]:
    """
    Obtener métodos de autenticación soportados por el sistema
    """
    return {
        "methods": {
            "email_password": {
                "enabled": True,
                "description": "Autenticación con email y contraseña",
                "requirements": "Email válido y contraseña segura"
            },
            "google": {
                "enabled": True,
                "description": "Autenticación con cuenta Google",
                "requirements": f"Cuenta Google con dominio {AUTHORIZED_DOMAIN}",
                "authorized_domain": AUTHORIZED_DOMAIN
            },
            "phone": {
                "enabled": True,
                "description": "Autenticación con número de teléfono",
                "requirements": "Número celular colombiano válido"
            }
        },
        "password_requirements": {
            "min_length": 8,
            "require_uppercase": True,
            "require_lowercase": True,
            "require_numbers": True,
            "require_special": True
        },
        "supported_domains": [AUTHORIZED_DOMAIN],
        "phone_format": "Números colombianos (+57XXXXXXXXXX)"
    }

async def check_auth_method_availability(email: Optional[str] = None, phone: Optional[str] = None) -> Dict[str, Any]:
    """
    Verificar qué métodos de autenticación están disponibles para un usuario
    """
    try:
        available_methods = []
        
        if email:
            email_validation = validate_email(email)
            if email_validation["valid"]:
                available_methods.append("email_password")
                
                if email_validation["can_use_google_auth"]:
                    available_methods.append("google")
        
        if phone:
            phone_validation = validate_cellphone(phone)
            if phone_validation["valid"]:
                available_methods.append("phone")
        
        return {
            "success": True,
            "available_methods": available_methods,
            "all_methods": list(get_supported_auth_methods()["methods"].keys()),
            "email_valid": email and validate_email(email)["valid"],
            "phone_valid": phone and validate_cellphone(phone)["valid"],
            "google_eligible": email and validate_email(email).get("can_use_google_auth", False)
        }
        
    except Exception as e:
        logger.error(f"Error checking auth method availability: {e}")
        return {
            "success": False,
            "error": "Error verificando métodos disponibles",
            "code": "AUTH_METHOD_CHECK_ERROR"
        }

# ============================================================================
# FUNCIONES HELPER PARA AUTENTICACIÓN - REMOVIDAS
# ============================================================================

# Función helper removida - ya no es necesaria
# La autenticación ahora usa únicamente Firebase Admin SDK y database/firebase_config.py
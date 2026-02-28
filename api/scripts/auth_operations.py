"""
Authentication Operations
Funciones especializadas para diferentes métodos de autenticación
Compatible con Firebase Authentication y NextJS frontend
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime
import re
import os
import aiohttp
import json
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
DEFAULT_SESSION_ROLE = "publico"


def _normalize_roles(raw_roles: Any) -> list[str]:
    if raw_roles is None:
        return []
    if isinstance(raw_roles, str):
        role = raw_roles.strip().lower()
        return [role] if role else []
    if isinstance(raw_roles, (list, tuple, set)):
        normalized_roles: list[str] = []
        for role in raw_roles:
            role_text = str(role).strip().lower()
            if role_text:
                normalized_roles.append(role_text)
        return normalized_roles
    role_text = str(raw_roles).strip().lower()
    return [role_text] if role_text else []


def _resolve_roles(firestore_data: Dict[str, Any], custom_claims: Dict[str, Any]) -> tuple[list[str], str]:
    roles = _normalize_roles(firestore_data.get("roles"))
    role_source = "firestore"

    if not roles:
        claim_role = str(custom_claims.get("role", "")).strip().lower()
        if claim_role:
            roles = [claim_role]
            role_source = "custom_claims"

    if not roles:
        roles = [DEFAULT_SESSION_ROLE]
        role_source = "default"

    return roles, role_source


def _build_user_payload(user_record, firestore_data: Dict[str, Any]) -> Dict[str, Any]:
    custom_claims = user_record.custom_claims or {}
    roles, role_source = _resolve_roles(firestore_data, custom_claims)

    hydrated_firestore_data = dict(firestore_data or {})
    hydrated_firestore_data["roles"] = roles
    hydrated_firestore_data["primary_role"] = roles[0]

    fullname = hydrated_firestore_data.get("fullname") or user_record.display_name
    centro_gestor = hydrated_firestore_data.get("nombre_centro_gestor")
    cellphone = hydrated_firestore_data.get("cellphone") or user_record.phone_number

    profile_complete = bool(fullname and centro_gestor and cellphone)

    return {
        "uid": user_record.uid,
        "email": user_record.email,
        "display_name": user_record.display_name,
        "fullname": fullname,
        "nombre_centro_gestor": centro_gestor,
        "cellphone": cellphone,
        "email_verified": user_record.email_verified,
        "phone_number": user_record.phone_number,
        "custom_claims": custom_claims,
        "providers": [provider.provider_id for provider in user_record.provider_data],
        "firestore_data": hydrated_firestore_data,
        "roles": roles,
        "primary_role": roles[0],
        "roles_source": role_source,
        "profile_complete": profile_complete
    }

# ============================================================================
# CONFIGURACIÓN DE FIREBASE REST API
# ============================================================================

def get_firebase_web_api_key() -> Optional[str]:
    """
    Obtener la clave Web API de Firebase para autenticación REST.
    Se puede configurar como variable de entorno FIREBASE_WEB_API_KEY.
    """
    return os.getenv("FIREBASE_WEB_API_KEY")

async def validate_password_with_firebase_rest(email: str, password: str) -> Dict[str, Any]:
    """
    Validar contraseña usando Firebase Authentication REST API.
    
    Esta función realiza autenticación real con Firebase Auth REST API.
    Requiere FIREBASE_WEB_API_KEY configurada como variable de entorno.
    
    Returns:
        Dict con success=True si las credenciales son válidas, 
        success=False si son inválidas o hay error.
    """
    web_api_key = get_firebase_web_api_key()
    
    if not web_api_key:
        return {
            "success": False,
            "error": "Firebase Web API Key no configurada",
            "code": "MISSING_WEB_API_KEY",
            "requires_frontend_auth": True
        }
    
    try:
        # URL del endpoint de autenticación de Firebase
        auth_url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={web_api_key}"
        
        # Datos de autenticación
        auth_data = {
            "email": email,
            "password": password,
            "returnSecureToken": True
        }
        
        # Realizar petición HTTP a Firebase Auth REST API
        async with aiohttp.ClientSession() as session:
            async with session.post(auth_url, json=auth_data) as response:
                response_data = await response.json()
                
                if response.status == 200:
                    # Autenticación exitosa
                    return {
                        "success": True,
                        "firebase_user_id": response_data.get("localId"),
                        "id_token": response_data.get("idToken"),
                        "refresh_token": response_data.get("refreshToken"),
                        "email_verified": response_data.get("registered", False),
                        "message": "Credenciales válidas"
                    }
                else:
                    # Autenticación fallida
                    error_message = response_data.get("error", {}).get("message", "Unknown error")
                    
                    # Mapear errores comunes de Firebase
                    if "INVALID_PASSWORD" in error_message:
                        return {
                            "success": False,
                            "error": "Contraseña incorrecta",
                            "code": "INVALID_PASSWORD"
                        }
                    elif "EMAIL_NOT_FOUND" in error_message:
                        return {
                            "success": False,
                            "error": "Usuario no encontrado",
                            "code": "USER_NOT_FOUND"
                        }
                    elif "USER_DISABLED" in error_message:
                        return {
                            "success": False,
                            "error": "Usuario deshabilitado",
                            "code": "USER_DISABLED"
                        }
                    elif "TOO_MANY_ATTEMPTS_TRY_LATER" in error_message:
                        return {
                            "success": False,
                            "error": "Demasiados intentos, intente más tarde",
                            "code": "TOO_MANY_ATTEMPTS"
                        }
                    elif "INVALID_LOGIN_CREDENTIALS" in error_message:
                        return {
                            "success": False,
                            "error": "Credenciales incorrectas",
                            "code": "INVALID_CREDENTIALS"
                        }
                    else:
                        return {
                            "success": False,
                            "error": f"Error de autenticación: {error_message}",
                            "code": "AUTH_ERROR"
                        }
                        
    except aiohttp.ClientError as e:
        logger.error(f"Error de red en autenticación Firebase REST: {e}")
        return {
            "success": False,
            "error": "Error de conexión con Firebase",
            "code": "NETWORK_ERROR"
        }
    except Exception as e:
        logger.error(f"Error inesperado en autenticación Firebase REST: {e}")
        return {
            "success": False,
            "error": "Error interno de autenticación",
            "code": "INTERNAL_ERROR"
        }

# ============================================================================
# AUTENTICACIÓN CON EMAIL Y CONTRASEÑA
# ============================================================================

async def authenticate_email_password(email: str, password: str) -> Dict[str, Any]:
    """
    Autenticación con validación real de contraseña usando Firebase REST API.
    
    Valida credenciales usando Firebase Auth REST API y obtiene información
    completa del usuario desde Firebase Admin SDK.
    
    Requiere FIREBASE_WEB_API_KEY configurada como variable de entorno.
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
        
        # Validar formato de contraseña básico
        if not password or len(password) < 6:
            return {
                "success": False,
                "error": "Contraseña debe tener al menos 6 caracteres",
                "code": "PASSWORD_TOO_SHORT"
            }
        
        # PASO 1: VALIDACIÓN REAL DE CONTRASEÑA usando Firebase REST API
        password_validation = await validate_password_with_firebase_rest(
            email_validation["email"], 
            password
        )
        
        # Si la validación de contraseña falla, rechazar inmediatamente
        if not password_validation.get("success"):
            if password_validation.get("requires_frontend_auth"):
                # Falta configuración de Web API Key
                return {
                    "success": False,
                    "error": "Autenticación de backend no disponible. Configure FIREBASE_WEB_API_KEY o use autenticación de frontend.",
                    "code": "BACKEND_AUTH_UNAVAILABLE",
                    "frontend_auth_required": True,
                    "setup_instructions": {
                        "environment_variable": "FIREBASE_WEB_API_KEY",
                        "description": "Obtenga la Web API Key desde Firebase Console > Project Settings > General > Web API Key"
                    }
                }
            else:
                # Credenciales incorrectas o error de autenticación
                return password_validation
        
        # PASO 2: Si la contraseña es válida, obtener datos completos del usuario
        # Obtener cliente de Firebase Auth usando configuración existente
        auth_client = get_auth_client()
        
        # Verificar existencia del usuario en Admin SDK
        try:
            user_record = auth_client.get_user_by_email(email_validation["email"])
        except firebase_exceptions.NotFoundError:
            # Este caso es raro ya que la validación REST ya confirmó que existe
            return {
                "success": False,
                "error": "Usuario no encontrado en el sistema",
                "code": "USER_NOT_FOUND"
            }
        
        # Verificar estado del usuario
        if user_record.disabled:
            return {
                "success": False,
                "error": "Usuario deshabilitado",
                "code": "USER_DISABLED"
            }
        
        # Obtener datos adicionales de Firestore
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
        
        # PASO 3: Actualizar estadísticas de login exitoso
        await update_user_login_stats(user_record.uid, "password")
        
        # PASO 4: Retornar información completa del usuario autenticado
        user_payload = _build_user_payload(user_record, firestore_data)

        logger.info(
            "auth.login.hydration uid=%s firestore_doc=%s roles=%s source=%s profile_complete=%s",
            user_record.uid,
            bool(user_doc.exists),
            user_payload.get("roles", []),
            user_payload.get("roles_source"),
            user_payload.get("profile_complete")
        )

        return {
            "success": True,
            "user": {
                **user_payload,
                "creation_time": user_record.user_metadata.creation_timestamp.isoformat() if user_record.user_metadata.creation_timestamp and hasattr(user_record.user_metadata.creation_timestamp, 'isoformat') else None,
                "last_sign_in": user_record.user_metadata.last_sign_in_timestamp.isoformat() if user_record.user_metadata.last_sign_in_timestamp and hasattr(user_record.user_metadata.last_sign_in_timestamp, 'isoformat') else None
            },
            "auth_method": "email_password",
            "credentials_validated": True,
            "password_validated": True,
            "firebase_tokens": {
                "id_token": password_validation.get("id_token"),
                "refresh_token": password_validation.get("refresh_token")
            },
            "message": "Autenticación exitosa con validación completa de credenciales",
            "authenticated_at": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error in email/password authentication: {e}")
        return {
            "success": False,
            "error": "Error interno en autenticación",
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

        user_payload = _build_user_payload(user_record, firestore_data)

        if not user_doc.exists:
            try:
                firestore_client.collection('users').document(uid).set({
                    "uid": uid,
                    "email": user_record.email,
                    "fullname": user_payload.get("fullname"),
                    "cellphone": user_payload.get("cellphone"),
                    "nombre_centro_gestor": user_payload.get("nombre_centro_gestor"),
                    "roles": user_payload.get("roles", [DEFAULT_SESSION_ROLE]),
                    "created_at": datetime.now(),
                    "updated_at": datetime.now(),
                    "email_verified": user_record.email_verified,
                    "is_active": True,
                    "auth_providers": [provider.provider_id for provider in user_record.provider_data]
                }, merge=True)
            except Exception as persist_error:
                logger.warning(f"auth.validate_session could not persist default profile for uid={uid}: {persist_error}")
        else:
            try:
                existing_roles = firestore_data.get("roles")
                normalized_existing = _normalize_roles(existing_roles)
                if normalized_existing != user_payload.get("roles", []):
                    firestore_client.collection('users').document(uid).update({
                        "roles": user_payload.get("roles", [DEFAULT_SESSION_ROLE]),
                        "updated_at": datetime.now()
                    })
            except Exception as sync_error:
                logger.warning(f"auth.validate_session could not sync roles for uid={uid}: {sync_error}")

        logger.info(
            "auth.validate_session.hydration uid=%s firestore_doc=%s roles=%s source=%s profile_complete=%s",
            uid,
            bool(user_doc.exists),
            user_payload.get("roles", []),
            user_payload.get("roles_source"),
            user_payload.get("profile_complete")
        )
        
        return {
            "valid": True,
            "user": user_payload,
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
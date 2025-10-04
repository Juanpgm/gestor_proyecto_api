# -*- coding: utf-8 -*-
"""
User Management Backend Functions
Sistema completo de gestión de usuarios con Firebase Authentication
Funciones administrativas para registro, validación, recuperación y administración
Soporte completo para UTF-8 y caracteres especiales en español: ñáéíóúü
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import secrets
import string
import re
from firebase_admin import auth, exceptions as firebase_exceptions
from database.firebase_config import get_firestore_client, get_auth_client

logger = logging.getLogger(__name__)

# ============================================================================
# CONSTANTES Y CONFIGURACIÓN
# ============================================================================

# Niveles de acceso predeterminados
USER_ROLES = {
    "admin": "Administrador del sistema",
    "gestor": "Gestor de proyectos",
    "viewer": "Solo lectura",
    "editor": "Editor de contenido"
}

# Dominio autorizado para autenticación Google
AUTHORIZED_DOMAIN = "@cali.gov.co"

# Configuración de contraseñas
PASSWORD_MIN_LENGTH = 8
PASSWORD_REQUIREMENTS = {
    "min_length": 8,
    "require_uppercase": True,
    "require_lowercase": True,
    "require_numbers": True,
    "require_special": True
}

# ============================================================================
# FUNCIONES DE VALIDACIÓN
# ============================================================================

def validate_fullname(fullname: str) -> Dict[str, Any]:
    """
    Validar nombre completo con soporte para caracteres especiales en español
    """
    try:
        if not fullname or len(fullname.strip()) < 2:
            return {
                "valid": False,
                "error": "El nombre completo es requerido (mínimo 2 caracteres)",
                "code": "FULLNAME_TOO_SHORT"
            }
        
        # Normalizar espacios
        normalized_name = ' '.join(fullname.strip().split())
        
        # Patrón que permite caracteres españoles
        # Incluye: a-z, A-Z, áéíóúüñ, espacios, apostrofes, guiones
        spanish_name_pattern = r'^[a-zA-ZáéíóúüñÁÉÍÓÚÜÑ\s\'\-\.]+$'
        
        if not re.match(spanish_name_pattern, normalized_name):
            return {
                "valid": False,
                "error": "El nombre contiene caracteres no válidos. Solo se permiten letras, espacios, apostrofes y guiones",
                "code": "INVALID_FULLNAME_CHARACTERS"
            }
        
        # Verificar que tenga al menos dos palabras (nombre y apellido)
        words = normalized_name.split()
        if len(words) < 2:
            return {
                "valid": False,
                "error": "Debe incluir al menos nombre y apellido",
                "code": "INCOMPLETE_FULLNAME"
            }
        
        return {
            "valid": True,
            "normalized": normalized_name,
            "word_count": len(words),
            "contains_spanish_chars": bool(re.search(r'[áéíóúüñÁÉÍÓÚÜÑ]', normalized_name))
        }
        
    except Exception as e:
        logger.error(f"Error validating fullname {fullname}: {e}")
        return {
            "valid": False,
            "error": "Error validando nombre completo",
            "code": "FULLNAME_VALIDATION_ERROR"
        }

def validate_email(email: str) -> Dict[str, Any]:
    """
    Validar formato de email y dominio autorizado para Google Auth
    """
    try:
        # Validación básica de formato
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, email):
            return {
                "valid": False,
                "error": "Formato de email inválido",
                "code": "INVALID_EMAIL_FORMAT"
            }
        
        # Validar dominio para autenticación Google
        is_google_domain = email.lower().endswith(AUTHORIZED_DOMAIN)
        
        return {
            "valid": True,
            "email": email.lower(),
            "is_google_domain": is_google_domain,
            "can_use_google_auth": is_google_domain
        }
        
    except Exception as e:
        logger.error(f"Error validating email {email}: {e}")
        return {
            "valid": False,
            "error": "Error validando email",
            "code": "EMAIL_VALIDATION_ERROR"
        }

def validate_password(password: str) -> Dict[str, Any]:
    """
    Validar fortaleza de contraseña según requisitos de seguridad
    """
    try:
        errors = []
        
        if len(password) < PASSWORD_REQUIREMENTS["min_length"]:
            errors.append(f"Mínimo {PASSWORD_REQUIREMENTS['min_length']} caracteres")
        
        if PASSWORD_REQUIREMENTS["require_uppercase"] and not re.search(r'[A-Z]', password):
            errors.append("Debe contener al menos una mayúscula")
        
        if PASSWORD_REQUIREMENTS["require_lowercase"] and not re.search(r'[a-z]', password):
            errors.append("Debe contener al menos una minúscula")
        
        if PASSWORD_REQUIREMENTS["require_numbers"] and not re.search(r'\d', password):
            errors.append("Debe contener al menos un número")
        
        if PASSWORD_REQUIREMENTS["require_special"] and not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            errors.append("Debe contener al menos un carácter especial")
        
        if errors:
            return {
                "valid": False,
                "errors": errors,
                "requirements": PASSWORD_REQUIREMENTS
            }
        
        return {"valid": True}
        
    except Exception as e:
        logger.error(f"Error validating password: {e}")
        return {
            "valid": False,
            "errors": ["Error validando contraseña"],
            "code": "PASSWORD_VALIDATION_ERROR"
        }

def validate_cellphone(cellphone: str) -> Dict[str, Any]:
    """
    Validar formato de número celular colombiano
    """
    try:
        # Limpiar número (remover espacios, guiones, etc.)
        clean_phone = re.sub(r'[^\d+]', '', str(cellphone))
        
        # Patrones válidos para Colombia
        patterns = [
            r'^\+57[39]\d{9}$',  # +57 + 3/9 + 9 dígitos
            r'^57[39]\d{9}$',    # 57 + 3/9 + 9 dígitos
            r'^[39]\d{9}$',      # 3/9 + 9 dígitos
            r'^\d{10}$'          # 10 dígitos exactos
        ]
        
        is_valid = any(re.match(pattern, clean_phone) for pattern in patterns)
        
        if not is_valid:
            return {
                "valid": False,
                "error": "Formato de celular inválido. Debe ser un número colombiano válido",
                "code": "INVALID_PHONE_FORMAT"
            }
        
        # Normalizar a formato internacional
        if clean_phone.startswith('+57'):
            normalized = clean_phone
        elif clean_phone.startswith('57'):
            normalized = '+' + clean_phone
        elif clean_phone.startswith(('3', '9')) and len(clean_phone) == 10:
            normalized = '+57' + clean_phone
        elif len(clean_phone) == 10:
            normalized = '+57' + clean_phone
        else:
            normalized = '+57' + clean_phone
        
        return {
            "valid": True,
            "original": cellphone,
            "normalized": normalized,
            "clean": clean_phone
        }
        
    except Exception as e:
        logger.error(f"Error validating cellphone {cellphone}: {e}")
        return {
            "valid": False,
            "error": "Error validando número celular",
            "code": "PHONE_VALIDATION_ERROR"
        }



# ============================================================================
# FUNCIONES DE GESTIÓN DE USUARIOS
# ============================================================================

async def check_user_session(uid: str) -> Dict[str, Any]:
    """
    Verificar si un usuario tiene una sesión activa válida
    """
    try:
        auth_client = get_auth_client()
        
        # Obtener información del usuario
        user_record = auth_client.get_user(uid)
        
        # Verificar si el usuario está habilitado
        if user_record.disabled:
            return {
                "valid": False,
                "error": "Usuario deshabilitado",
                "code": "USER_DISABLED"
            }
        
        # Verificar si el email está verificado (opcional)
        email_verified = user_record.email_verified if user_record.email else True
        
        # Obtener datos adicionales del usuario desde Firestore
        firestore_client = get_firestore_client()
        user_doc = firestore_client.collection('users').document(uid).get()
        
        user_data = {}
        if user_doc.exists:
            user_data = user_doc.to_dict()
        
        return {
            "valid": True,
            "uid": uid,
            "email": user_record.email,
            "email_verified": email_verified,
            "phone_number": user_record.phone_number,
            "display_name": user_record.display_name,
            "creation_time": user_record.user_metadata.creation_timestamp.isoformat() if user_record.user_metadata.creation_timestamp and hasattr(user_record.user_metadata.creation_timestamp, 'isoformat') else None,
            "last_sign_in": user_record.user_metadata.last_sign_in_timestamp.isoformat() if user_record.user_metadata.last_sign_in_timestamp and hasattr(user_record.user_metadata.last_sign_in_timestamp, 'isoformat') else None,
            "custom_claims": user_record.custom_claims or {},
            "firestore_data": user_data,
            "providers": [provider.provider_id for provider in user_record.provider_data]
        }
        
    except firebase_exceptions.NotFoundError:
        return {
            "valid": False,
            "error": "Usuario no encontrado",
            "code": "USER_NOT_FOUND"
        }
    except Exception as e:
        logger.error(f"Error checking user session for {uid}: {e}")
        return {
            "valid": False,
            "error": "Error verificando sesión",
            "code": "SESSION_CHECK_ERROR"
        }

async def create_user_account(
    email: str,
    password: str,
    fullname: str,
    cellphone: str,
    nombre_centro_gestor: str,
    send_email_verification: bool = True
) -> Dict[str, Any]:
    """
    Crear nueva cuenta de usuario con validaciones completas.
    El rol por defecto será 'viewer' y puede ser modificado posteriormente por un administrador.
    """
    try:
        # Validaciones con soporte UTF-8
        email_validation = validate_email(email)
        if not email_validation["valid"]:
            return email_validation
        
        fullname_validation = validate_fullname(fullname)
        if not fullname_validation["valid"]:
            return fullname_validation
        
        password_validation = validate_password(password)
        if not password_validation["valid"]:
            return password_validation
        
        phone_validation = validate_cellphone(cellphone)
        if not phone_validation["valid"]:
            return phone_validation
        
        # Crear usuario en Firebase Auth
        auth_client = get_auth_client()
        
        try:
            user_record = auth_client.create_user(
                email=email_validation["email"],
                password=password,
                display_name=fullname_validation["normalized"],
                phone_number=phone_validation["normalized"],
                email_verified=False,
                disabled=False
            )
            
            # Establecer custom claims básicos
            custom_claims = {
                "role": "viewer",  # rol por defecto
                "centro_gestor": nombre_centro_gestor,
                "created_at": datetime.now().isoformat()
            }
            
            auth_client.set_custom_user_claims(user_record.uid, custom_claims)
            
            # Guardar datos adicionales en Firestore
            firestore_client = get_firestore_client()
            user_data = {
                "uid": user_record.uid,
                "email": email_validation["email"],
                "fullname": fullname_validation["normalized"],
                "cellphone": phone_validation["normalized"],
                "nombre_centro_gestor": nombre_centro_gestor,
                "created_at": datetime.now(),
                "updated_at": datetime.now(),
                "email_verified": False,
                "is_active": True,
                "can_use_google_auth": email_validation["can_use_google_auth"],
                "auth_providers": ["password"],
                "last_login": None,
                "login_count": 0
            }
            
            firestore_client.collection('users').document(user_record.uid).set(user_data)
            
            # Generar enlace de verificación de email si se solicita
            verification_link = None
            if send_email_verification:
                try:
                    verification_link = auth_client.generate_email_verification_link(
                        email_validation["email"]
                    )
                except Exception as e:
                    logger.warning(f"Could not generate email verification link: {e}")
            
            return {
                "success": True,
                "user": {
                    "uid": user_record.uid,
                    "email": user_record.email,
                    "fullname": fullname_validation["normalized"],
                    "centro_gestor": nombre_centro_gestor,
                    "phone_number": user_record.phone_number,
                    "email_verified": False,
                    "created_at": user_record.user_metadata.creation_timestamp.isoformat() if user_record.user_metadata.creation_timestamp and hasattr(user_record.user_metadata.creation_timestamp, 'isoformat') else datetime.now().isoformat(),
                    "has_spanish_chars": fullname_validation["contains_spanish_chars"]
                },
                "verification_link": verification_link,
                "message": "Usuario creado exitosamente"
            }
            
        except firebase_exceptions.AlreadyExistsError:
            return {
                "success": False,
                "error": "Ya existe un usuario con este email",
                "code": "EMAIL_ALREADY_EXISTS"
            }
        except Exception as e:
            logger.error(f"Error creating user account: {e}")
            return {
                "success": False,
                "error": "Error creando cuenta de usuario",
                "code": "USER_CREATION_ERROR"
            }
            
    except Exception as e:
        logger.error(f"Error in create_user_account: {e}")
        return {
            "success": False,
            "error": "Error interno del servidor",
            "code": "INTERNAL_ERROR"
        }

async def update_user_password(uid: str, new_password: str) -> Dict[str, Any]:
    """
    Actualizar contraseña de usuario existente
    """
    try:
        # Validar nueva contraseña
        password_validation = validate_password(new_password)
        if not password_validation["valid"]:
            return {
                "success": False,
                "error": "Contraseña no cumple con los requisitos",
                "validation_errors": password_validation["errors"],
                "requirements": password_validation["requirements"]
            }
        
        auth_client = get_auth_client()
        
        # Actualizar contraseña en Firebase Auth
        auth_client.update_user(uid, password=new_password)
        
        # Actualizar timestamp en Firestore
        firestore_client = get_firestore_client()
        firestore_client.collection('users').document(uid).update({
            "password_updated_at": datetime.now(),
            "updated_at": datetime.now()
        })
        
        return {
            "success": True,
            "message": "Contraseña actualizada exitosamente",
            "updated_at": datetime.now().isoformat()
        }
        
    except firebase_exceptions.NotFoundError:
        return {
            "success": False,
            "error": "Usuario no encontrado",
            "code": "USER_NOT_FOUND"
        }
    except Exception as e:
        logger.error(f"Error updating password for {uid}: {e}")
        return {
            "success": False,
            "error": "Error actualizando contraseña",
            "code": "PASSWORD_UPDATE_ERROR"
        }

async def delete_user_account(uid: str, soft_delete: bool = True) -> Dict[str, Any]:
    """
    Eliminar cuenta de usuario (soft delete por defecto)
    """
    try:
        auth_client = get_auth_client()
        firestore_client = get_firestore_client()
        
        if soft_delete:
            # Soft delete: deshabilitar usuario y marcar como eliminado
            auth_client.update_user(uid, disabled=True)
            
            firestore_client.collection('users').document(uid).update({
                "is_active": False,
                "deleted_at": datetime.now(),
                "updated_at": datetime.now()
            })
            
            return {
                "success": True,
                "message": "Usuario deshabilitado exitosamente",
                "deleted_at": datetime.now().isoformat(),
                "soft_delete": True
            }
        else:
            # Hard delete: eliminar completamente
            auth_client.delete_user(uid)
            firestore_client.collection('users').document(uid).delete()
            
            return {
                "success": True,
                "message": "Usuario eliminado permanentemente",
                "deleted_at": datetime.now().isoformat(),
                "soft_delete": False
            }
            
    except firebase_exceptions.NotFoundError:
        return {
            "success": False,
            "error": "Usuario no encontrado",
            "code": "USER_NOT_FOUND"
        }
    except Exception as e:
        logger.error(f"Error deleting user {uid}: {e}")
        return {
            "success": False,
            "error": "Error eliminando usuario",
            "code": "USER_DELETE_ERROR"
        }

async def generate_password_reset_link(email: str) -> Dict[str, Any]:
    """
    Generar enlace de recuperación de contraseña
    """
    try:
        # Validar email
        email_validation = validate_email(email)
        if not email_validation["valid"]:
            return email_validation
        
        auth_client = get_auth_client()
        
        # Generar enlace de reseteo
        reset_link = auth_client.generate_password_reset_link(email_validation["email"])
        
        # Registrar solicitud en Firestore
        firestore_client = get_firestore_client()
        try:
            user_record = auth_client.get_user_by_email(email_validation["email"])
            firestore_client.collection('users').document(user_record.uid).update({
                "password_reset_requested_at": datetime.now(),
                "updated_at": datetime.now()
            })
        except:
            pass  # Usuario podría no existir en Firestore
        
        return {
            "success": True,
            "reset_link": reset_link,
            "email": email_validation["email"],
            "message": "Enlace de recuperación generado exitosamente"
        }
        
    except firebase_exceptions.NotFoundError:
        return {
            "success": False,
            "error": "No existe usuario con este email",
            "code": "USER_NOT_FOUND"
        }
    except Exception as e:
        logger.error(f"Error generating password reset link for {email}: {e}")
        return {
            "success": False,
            "error": "Error generando enlace de recuperación",
            "code": "PASSWORD_RESET_ERROR"
        }

async def verify_custom_token(custom_token: str) -> Dict[str, Any]:
    """
    Verificar token personalizado de Firebase
    """
    try:
        auth_client = get_auth_client()
        
        # Verificar token
        decoded_token = auth_client.verify_id_token(custom_token)
        uid = decoded_token['uid']
        
        # Obtener información completa del usuario
        user_session = await check_user_session(uid)
        
        if not user_session["valid"]:
            return user_session
        
        return {
            "valid": True,
            "token_data": decoded_token,
            "user_data": user_session,
            "verified_at": datetime.now().isoformat()
        }
        
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
    except Exception as e:
        logger.error(f"Error verifying custom token: {e}")
        return {
            "valid": False,
            "error": "Error verificando token",
            "code": "TOKEN_VERIFICATION_ERROR"
        }

# ============================================================================
# FUNCIONES ADMINISTRATIVAS
# ============================================================================

async def list_users(
    limit: int = 100,
    page_token: Optional[str] = None,
    filter_by_role: Optional[str] = None,
    filter_by_centro_gestor: Optional[str] = None,
    include_disabled: bool = False
) -> Dict[str, Any]:
    """
    Listar usuarios con filtros administrativos
    """
    try:
        auth_client = get_auth_client()
        firestore_client = get_firestore_client()
        
        # Obtener usuarios de Firebase Auth
        page = auth_client.list_users(max_results=limit, page_token=page_token)
        
        users_list = []
        for user in page.users:
            # Filtrar usuarios deshabilitados si no se incluyen
            if not include_disabled and user.disabled:
                continue
            
            # Obtener datos adicionales de Firestore
            user_doc = firestore_client.collection('users').document(user.uid).get()
            firestore_data = user_doc.to_dict() if user_doc.exists else {}
            
            # Aplicar filtros
            user_role = user.custom_claims.get('role') if user.custom_claims else 'unknown'
            if filter_by_role and user_role != filter_by_role:
                continue
            
            if filter_by_centro_gestor and firestore_data.get('nombre_centro_gestor') != filter_by_centro_gestor:
                continue
            
            user_info = {
                "uid": user.uid,
                "email": user.email,
                "display_name": user.display_name,
                "phone_number": user.phone_number,
                "email_verified": user.email_verified,
                "disabled": user.disabled,
                "creation_time": user.user_metadata.creation_timestamp.isoformat() if user.user_metadata.creation_timestamp and hasattr(user.user_metadata.creation_timestamp, 'isoformat') else None,
                "last_sign_in": user.user_metadata.last_sign_in_timestamp.isoformat() if user.user_metadata.last_sign_in_timestamp and hasattr(user.user_metadata.last_sign_in_timestamp, 'isoformat') else None,
                "custom_claims": user.custom_claims or {},
                "providers": [provider.provider_id for provider in user.provider_data],
                "firestore_data": firestore_data
            }
            
            users_list.append(user_info)
        
        return {
            "success": True,
            "users": users_list,
            "count": len(users_list),
            "has_next_page": page.has_next_page,
            "next_page_token": page.next_page_token,
            "filters_applied": {
                "role": filter_by_role,
                "centro_gestor": filter_by_centro_gestor,
                "include_disabled": include_disabled
            }
        }
        
    except Exception as e:
        logger.error(f"Error listing users: {e}")
        return {
            "success": False,
            "error": "Error obteniendo lista de usuarios",
            "code": "USER_LIST_ERROR"
        }

async def get_user_statistics() -> Dict[str, Any]:
    """
    Obtener estadísticas de usuarios del sistema
    """
    try:
        firestore_client = get_firestore_client()
        
        # Obtener todos los usuarios de Firestore
        users_ref = firestore_client.collection('users')
        users_query = users_ref.get()
        
        total_users = 0
        active_users = 0
        users_by_role = {}
        users_by_centro = {}
        email_verified_count = 0
        google_auth_enabled = 0
        
        for user_doc in users_query:
            if user_doc.exists:
                user_data = user_doc.to_dict()
                total_users += 1
                
                # Contar usuarios activos
                if user_data.get('is_active', True):
                    active_users += 1
                
                # Contar por rol (usar custom claims en lugar de user_range)
                role = 'unknown'  # Por defecto
                users_by_role[role] = users_by_role.get(role, 0) + 1
                
                # Contar por centro gestor
                centro = user_data.get('nombre_centro_gestor', 'unknown')
                users_by_centro[centro] = users_by_centro.get(centro, 0) + 1
                
                # Contar emails verificados
                if user_data.get('email_verified', False):
                    email_verified_count += 1
                
                # Contar usuarios con Google Auth habilitado
                if user_data.get('can_use_google_auth', False):
                    google_auth_enabled += 1
        
        return {
            "success": True,
            "statistics": {
                "total_users": total_users,
                "active_users": active_users,
                "inactive_users": total_users - active_users,
                "email_verified_count": email_verified_count,
                "google_auth_enabled": google_auth_enabled,
                "users_by_role": users_by_role,
                "users_by_centro_gestor": users_by_centro,
                "verification_rate": round((email_verified_count / total_users * 100), 2) if total_users > 0 else 0,
                "google_auth_rate": round((google_auth_enabled / total_users * 100), 2) if total_users > 0 else 0
            },
            "generated_at": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting user statistics: {e}")
        return {
            "success": False,
            "error": "Error obteniendo estadísticas de usuarios",
            "code": "STATISTICS_ERROR"
        }

# ============================================================================
# FUNCIONES DE UTILIDAD
# ============================================================================

def generate_secure_password(length: int = 12) -> str:
    """
    Generar contraseña segura automáticamente
    """
    try:
        # Asegurar que la contraseña cumple todos los requisitos
        uppercase = string.ascii_uppercase
        lowercase = string.ascii_lowercase
        digits = string.digits
        special_chars = "!@#$%^&*(),.?\":{}|<>"
        
        # Garantizar al menos un carácter de cada tipo
        password = [
            secrets.choice(uppercase),
            secrets.choice(lowercase),
            secrets.choice(digits),
            secrets.choice(special_chars)
        ]
        
        # Completar longitud con caracteres aleatorios
        all_chars = uppercase + lowercase + digits + special_chars
        for _ in range(length - 4):
            password.append(secrets.choice(all_chars))
        
        # Mezclar caracteres
        secrets.SystemRandom().shuffle(password)
        
        return ''.join(password)
        
    except Exception as e:
        logger.error(f"Error generating secure password: {e}")
        return None

async def update_user_login_stats(uid: str, provider: str) -> Dict[str, Any]:
    """
    Actualizar estadísticas de login del usuario
    """
    try:
        firestore_client = get_firestore_client()
        
        # Actualizar estadísticas
        user_ref = firestore_client.collection('users').document(uid)
        user_doc = user_ref.get()
        
        if user_doc.exists:
            current_data = user_doc.to_dict()
            login_count = current_data.get('login_count', 0) + 1
            
            # Actualizar providers si es nuevo
            auth_providers = current_data.get('auth_providers', [])
            if provider not in auth_providers:
                auth_providers.append(provider)
            
            user_ref.update({
                "last_login": datetime.now(),
                "login_count": login_count,
                "auth_providers": auth_providers,
                "updated_at": datetime.now()
            })
            
            return {
                "success": True,
                "login_count": login_count,
                "last_login": datetime.now().isoformat()
            }
        else:
            return {
                "success": False,
                "error": "Usuario no encontrado en Firestore",
                "code": "USER_NOT_FOUND_FIRESTORE"
            }
            
    except Exception as e:
        logger.error(f"Error updating login stats for {uid}: {e}")
        return {
            "success": False,
            "error": "Error actualizando estadísticas de login",
            "code": "LOGIN_STATS_ERROR"
        }

"""
Google OAuth2 Integration - DEPRECATED
==================================

⚠️  ESTE ARCHIVO ESTÁ OBSOLETO ⚠️

Este módulo implementa autenticación Google usando OAuth2 tradicional que requiere
configuración manual de Client ID y Client Secret. Ha sido reemplazado por:

👉 workload_identity_auth.py 

🔧 MIGRACIÓN:
- Elimine las variables GOOGLE_OAUTH_CLIENT_ID y GOOGLE_OAUTH_CLIENT_SECRET
- Reemplace calls a estas funciones con authenticate_with_workload_identity()
- No requiere configuración manual - funciona automáticamente en Google Cloud
- Mayor seguridad sin credenciales expuestas

🗑️  PROGRAMADO PARA ELIMINACIÓN EN PRÓXIMA VERSIÓN

Mantenido temporalmente solo para compatibilidad legacy.
Migre sus implementaciones lo antes posible.
"""

import logging
from typing import Dict, Any, Optional
import os
import json
from datetime import datetime
import httpx
from google.oauth2 import id_token
from google.auth.transport import requests
from firebase_admin import auth, exceptions as firebase_exceptions
from database.firebase_config import get_firestore_client, get_auth_client
from .user_management import validate_email, AUTHORIZED_DOMAIN

logger = logging.getLogger(__name__)

# ============================================================================
# CONFIGURACIÓN GOOGLE OAUTH2
# ============================================================================

class GoogleOAuthConfig:
    """Configuración para Google OAuth2"""
    
    def __init__(self):
        # Estas credenciales las obtienes de Google Cloud Console
        self.client_id = os.getenv('GOOGLE_OAUTH_CLIENT_ID')
        self.client_secret = os.getenv('GOOGLE_OAUTH_CLIENT_SECRET')
        self.redirect_uri = os.getenv('GOOGLE_OAUTH_REDIRECT_URI', 'http://localhost:8000/auth/google/callback')
        
        # URLs de Google OAuth2
        self.auth_url = "https://accounts.google.com/o/oauth2/v2/auth"
        self.token_url = "https://oauth2.googleapis.com/token"
        self.userinfo_url = "https://www.googleapis.com/oauth2/v2/userinfo"
        
        # Scopes necesarios
        self.scopes = [
            "openid",
            "email", 
            "profile"
        ]
    
    def is_configured(self) -> bool:
        """Verificar si OAuth2 está configurado"""
        return bool(self.client_id and self.client_secret)
    
    def get_auth_url(self, state: Optional[str] = None) -> str:
        """Generar URL de autorización Google"""
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "scope": " ".join(self.scopes),
            "response_type": "code",
            "access_type": "offline",
            "prompt": "consent",
            "hd": AUTHORIZED_DOMAIN.replace("@", "")  # Domain restriction
        }
        
        if state:
            params["state"] = state
        
        query_string = "&".join([f"{k}={v}" for k, v in params.items()])
        return f"{self.auth_url}?{query_string}"

# Instancia global de configuración
google_config = GoogleOAuthConfig()

# ============================================================================
# FUNCIONES DE AUTENTICACIÓN GOOGLE
# ============================================================================

async def get_google_auth_url(state: Optional[str] = None) -> Dict[str, Any]:
    """
    Generar URL de autorización para Google OAuth2
    """
    try:
        if not google_config.is_configured():
            return {
                "success": False,
                "error": "Google OAuth2 no está configurado",
                "code": "OAUTH_NOT_CONFIGURED",
                "setup_required": True,
                "instructions": "Configure GOOGLE_OAUTH_CLIENT_ID y GOOGLE_OAUTH_CLIENT_SECRET"
            }
        
        auth_url = google_config.get_auth_url(state)
        
        return {
            "success": True,
            "auth_url": auth_url,
            "state": state,
            "message": "Redirija el usuario a esta URL para autenticación Google"
        }
        
    except Exception as e:
        logger.error(f"Error generating Google auth URL: {e}")
        return {
            "success": False,
            "error": "Error generando URL de autenticación",
            "code": "AUTH_URL_ERROR"
        }

async def verify_google_id_token(id_token_string: str) -> Dict[str, Any]:
    """
    Verificar ID token de Google directamente
    """
    try:
        if not google_config.is_configured():
            return {
                "success": False,
                "error": "Google OAuth2 no está configurado",
                "code": "OAUTH_NOT_CONFIGURED"
            }
        
        # Verificar el token con Google
        try:
            # Usar Google's library para verificar el token
            idinfo = id_token.verify_oauth2_token(
                id_token_string, 
                requests.Request(), 
                google_config.client_id
            )
            
            # Verificar el issuer
            if idinfo['iss'] not in ['accounts.google.com', 'https://accounts.google.com']:
                return {
                    "success": False,
                    "error": "Token issuer inválido",
                    "code": "INVALID_ISSUER"
                }
            
            # Verificar dominio si está restringido
            email = idinfo.get('email', '')
            if not email.endswith(AUTHORIZED_DOMAIN):
                return {
                    "success": False,
                    "error": f"Solo se permite autenticación para cuentas {AUTHORIZED_DOMAIN}",
                    "code": "UNAUTHORIZED_DOMAIN"
                }
            
            return {
                "success": True,
                "user_info": {
                    "google_uid": idinfo['sub'],
                    "email": idinfo['email'],
                    "name": idinfo.get('name', ''),
                    "given_name": idinfo.get('given_name', ''),
                    "family_name": idinfo.get('family_name', ''),
                    "picture": idinfo.get('picture', ''),
                    "email_verified": idinfo.get('email_verified', False),
                    "locale": idinfo.get('locale', ''),
                    "hd": idinfo.get('hd', '')  # Hosted domain
                },
                "token_valid": True
            }
            
        except ValueError as e:
            return {
                "success": False,
                "error": "Token de Google inválido",
                "code": "INVALID_GOOGLE_TOKEN",
                "details": str(e)
            }
            
    except Exception as e:
        logger.error(f"Error verifying Google ID token: {e}")
        return {
            "success": False,
            "error": "Error verificando token de Google",
            "code": "GOOGLE_TOKEN_ERROR"
        }

async def handle_google_oauth_callback(code: str, state: Optional[str] = None) -> Dict[str, Any]:
    """
    Manejar callback de Google OAuth2 y obtener tokens
    """
    try:
        if not google_config.is_configured():
            return {
                "success": False,
                "error": "Google OAuth2 no está configurado",
                "code": "OAUTH_NOT_CONFIGURED"
            }
        
        # Intercambiar código por tokens
        async with httpx.AsyncClient() as client:
            token_data = {
                "client_id": google_config.client_id,
                "client_secret": google_config.client_secret,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": google_config.redirect_uri
            }
            
            response = await client.post(google_config.token_url, data=token_data)
            
            if response.status_code != 200:
                return {
                    "success": False,
                    "error": "Error obteniendo tokens de Google",
                    "code": "TOKEN_EXCHANGE_ERROR",
                    "details": response.text
                }
            
            tokens = response.json()
            
            # Verificar el ID token
            id_token_result = await verify_google_id_token(tokens.get('id_token', ''))
            
            if not id_token_result["success"]:
                return id_token_result
            
            return {
                "success": True,
                "tokens": {
                    "access_token": tokens.get('access_token'),
                    "id_token": tokens.get('id_token'),
                    "refresh_token": tokens.get('refresh_token'),
                    "token_type": tokens.get('token_type', 'Bearer'),
                    "expires_in": tokens.get('expires_in')
                },
                "user_info": id_token_result["user_info"],
                "state": state
            }
            
    except Exception as e:
        logger.error(f"Error handling Google OAuth callback: {e}")
        return {
            "success": False,
            "error": "Error procesando callback de Google",
            "code": "OAUTH_CALLBACK_ERROR"
        }

async def authenticate_with_google_token(id_token_string: str) -> Dict[str, Any]:
    """
    Autenticar usuario usando ID token de Google y sincronizar con Firebase
    """
    try:
        # Verificar token de Google
        token_result = await verify_google_id_token(id_token_string)
        if not token_result["success"]:
            return token_result
        
        user_info = token_result["user_info"]
        email = user_info["email"]
        google_uid = user_info["google_uid"]
        
        # Buscar o crear usuario en Firebase
        auth_client = get_auth_client()
        firestore_client = get_firestore_client()
        
        try:
            # Buscar usuario existente por email
            user_record = auth_client.get_user_by_email(email)
            user_exists = True
        except firebase_exceptions.NotFoundError:
            user_exists = False
            user_record = None
        
        if user_exists:
            # Usuario existente - actualizar información
            user_doc = firestore_client.collection('users').document(user_record.uid).get()
            
            if user_doc.exists:
                firestore_data = user_doc.to_dict()
                
                # Verificar que la cuenta está activa
                if not firestore_data.get('is_active', True):
                    return {
                        "success": False,
                        "error": "Cuenta desactivada",
                        "code": "ACCOUNT_INACTIVE"
                    }
                
                # Actualizar datos de Google
                update_data = {
                    "google_uid": google_uid,
                    "google_photo_url": user_info.get("picture"),
                    "updated_at": datetime.now(),
                    "email_verified": True,
                    "last_google_login": datetime.now()
                }
                
                # Agregar Google como proveedor
                auth_providers = firestore_data.get('auth_providers', [])
                if 'google.com' not in auth_providers:
                    auth_providers.append('google.com')
                    update_data['auth_providers'] = auth_providers
                
                # Actualizar estadísticas de login
                update_data['login_count'] = firestore_data.get('login_count', 0) + 1
                update_data['last_login'] = datetime.now()
                
                firestore_client.collection('users').document(user_record.uid).update(update_data)
                
                return {
                    "success": True,
                    "user_exists": True,
                    "user": {
                        "uid": user_record.uid,
                        "email": user_record.email,
                        "display_name": user_info.get("name") or user_record.display_name,
                        "email_verified": True,
                        "google_uid": google_uid,
                        "photo_url": user_info.get("picture"),
                        "custom_claims": user_record.custom_claims or {},
                        "firestore_data": {**firestore_data, **update_data}
                    },
                    "auth_method": "google",
                    "message": "Autenticación Google exitosa"
                }
            else:
                return {
                    "success": False,
                    "error": "Usuario existe en Auth pero no en Firestore",
                    "code": "FIRESTORE_SYNC_ERROR"
                }
        else:
            # Usuario nuevo - crear cuenta con Google
            try:
                # Crear usuario en Firebase Auth
                new_user = auth_client.create_user(
                    email=email,
                    display_name=user_info.get("name"),
                    email_verified=True,
                    photo_url=user_info.get("picture"),
                    disabled=False
                )
                
                # Establecer custom claims
                custom_claims = {
                    "role": "viewer",  # rol por defecto
                    "created_with": "google",
                    "created_at": datetime.now().isoformat(),
                    "google_uid": google_uid
                }
                
                auth_client.set_custom_user_claims(new_user.uid, custom_claims)
                
                # Crear documento en Firestore
                user_data = {
                    "uid": new_user.uid,
                    "email": email,
                    "fullname": user_info.get("name", ""),
                    "google_uid": google_uid,
                    "google_photo_url": user_info.get("picture"),
                    "created_at": datetime.now(),
                    "updated_at": datetime.now(),
                    "email_verified": True,
                    "is_active": True,
                    "can_use_google_auth": True,
                    "auth_providers": ["google.com"],
                    "login_count": 1,
                    "last_login": datetime.now(),
                    "last_google_login": datetime.now(),
                    "created_with": "google"
                }
                
                firestore_client.collection('users').document(new_user.uid).set(user_data)
                
                return {
                    "success": True,
                    "user_exists": False,
                    "user_created": True,
                    "user": {
                        "uid": new_user.uid,
                        "email": new_user.email,
                        "display_name": user_info.get("name"),
                        "email_verified": True,
                        "google_uid": google_uid,
                        "photo_url": user_info.get("picture"),
                        "custom_claims": custom_claims,
                        "firestore_data": user_data
                    },
                    "auth_method": "google",
                    "message": "Usuario creado y autenticado con Google exitosamente"
                }
                
            except firebase_exceptions.AlreadyExistsError:
                return {
                    "success": False,
                    "error": "Error de sincronización: usuario ya existe",
                    "code": "USER_SYNC_ERROR"
                }
            except Exception as e:
                logger.error(f"Error creating Google user: {e}")
                return {
                    "success": False,
                    "error": "Error creando usuario con Google",
                    "code": "USER_CREATION_ERROR"
                }
    
    except Exception as e:
        logger.error(f"Error in Google token authentication: {e}")
        return {
            "success": False,
            "error": "Error en autenticación Google",
            "code": "GOOGLE_AUTH_ERROR"
        }

# ============================================================================
# FUNCIONES DE UTILIDAD
# ============================================================================

def get_google_oauth_status() -> Dict[str, Any]:
    """
    Obtener estado de configuración de Google OAuth2
    """
    return {
        "configured": google_config.is_configured(),
        "client_id_set": bool(google_config.client_id),
        "client_secret_set": bool(google_config.client_secret),
        "redirect_uri": google_config.redirect_uri,
        "authorized_domain": AUTHORIZED_DOMAIN,
        "required_env_vars": [
            "GOOGLE_OAUTH_CLIENT_ID",
            "GOOGLE_OAUTH_CLIENT_SECRET",
            "GOOGLE_OAUTH_REDIRECT_URI (opcional)"
        ]
    }

async def generate_google_signin_config() -> Dict[str, Any]:
    """
    Generar configuración para Google Sign-In JavaScript
    """
    try:
        if not google_config.is_configured():
            return {
                "success": False,
                "error": "Google OAuth2 no está configurado",
                "setup_required": True
            }
        
        return {
            "success": True,
            "config": {
                "client_id": google_config.client_id,
                "hosted_domain": AUTHORIZED_DOMAIN.replace("@", ""),
                "scope": " ".join(google_config.scopes),
                "callback_url": f"{google_config.redirect_uri}",
                "ux_mode": "popup"  # o "redirect"
            },
            "html_snippet": f"""
<!-- Google Sign-In JavaScript API -->
<script src="https://accounts.google.com/gsi/client" async defer></script>

<script>
window.onload = function() {{
    google.accounts.id.initialize({{
        client_id: '{google_config.client_id}',
        callback: handleCredentialResponse,
        hosted_domain: '{AUTHORIZED_DOMAIN.replace("@", "")}'
    }});
    
    google.accounts.id.renderButton(
        document.getElementById('google-signin-button'),
        {{ theme: 'outline', size: 'large' }}
    );
}};

function handleCredentialResponse(response) {{
    // Enviar el ID token al backend
    fetch('/auth/google/token', {{
        method: 'POST',
        headers: {{
            'Content-Type': 'application/json',
        }},
        body: JSON.stringify({{
            id_token: response.credential
        }})
    }})
    .then(response => response.json())
    .then(data => {{
        if (data.success) {{
            console.log('Login exitoso:', data);
            // Manejar login exitoso
        }} else {{
            console.error('Error en login:', data);
        }}
    }});
}}
</script>

<div id="google-signin-button"></div>
""",
            "instructions": [
                "1. Incluya el HTML snippet en su página",
                "2. El botón se renderizará automáticamente",
                "3. Los tokens se enviarán a /auth/google/token",
                "4. Maneje la respuesta según sea necesario"
            ]
        }
        
    except Exception as e:
        logger.error(f"Error generating Google Sign-In config: {e}")
        return {
            "success": False,
            "error": "Error generando configuración",
            "code": "CONFIG_ERROR"
        }
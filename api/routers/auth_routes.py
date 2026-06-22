# -*- coding: utf-8 -*-
"""
api/routers/auth_routes.py — Endpoints de autenticacion y gestion de usuarios.

Rutas expuestas:
    POST   /auth/validate-session
    POST   /auth/login
    GET    /auth/register/health-check
    POST   /auth/register
    POST   /auth/change-password
    GET    /auth/config
    GET    /auth/workload-identity/status
    POST   /auth/google
    DELETE /auth/user/{uid}
    GET    /admin/users
"""

import logging
import os
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, cast

from fastapi import APIRouter, Form, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse

from api.core.responses import clean_firebase_data, create_utf8_response
from api.core.security import verify_firebase_token, optional_rate_limit

logger = logging.getLogger(__name__)

router = APIRouter()

# ---------------------------------------------------------------------------
# Availability flags — importación segura
# ---------------------------------------------------------------------------
try:
    from database.firebase_config import (
        FIREBASE_AVAILABLE,
        get_firestore_client,
        PROJECT_ID,
    )
except Exception:
    FIREBASE_AVAILABLE = False
    PROJECT_ID = os.getenv("FIREBASE_PROJECT_ID", "NOT_CONFIGURED")
    get_firestore_client = lambda: None

try:
    from api.scripts import (
        USER_MANAGEMENT_AVAILABLE,
        AUTH_OPERATIONS_AVAILABLE,
        validate_user_session,
        authenticate_email_password,
        create_user_account,
        update_user_password,
        delete_user_account,
        list_users,
    )
except Exception:
    USER_MANAGEMENT_AVAILABLE = False
    AUTH_OPERATIONS_AVAILABLE = False
    validate_user_session = None
    authenticate_email_password = None
    create_user_account = None
    update_user_password = None
    delete_user_account = None
    list_users = None

try:
    from api.models import (
        UserRegistrationRequest,
        UserLoginRequest,
    )

    USER_MODELS_AVAILABLE = True
except Exception:
    USER_MODELS_AVAILABLE = False
    from pydantic import BaseModel

    class UserRegistrationRequest(BaseModel):
        email: str
        password: str
        name: str
        cellphone: str
        nombre_centro_gestor: str

    class UserLoginRequest(BaseModel):
        email: str
        password: str


try:
    from api.scripts import SCRIPTS_AVAILABLE as _SCRIPTS_AVAILABLE

    SCRIPTS_AVAILABLE = _SCRIPTS_AVAILABLE
except Exception:
    SCRIPTS_AVAILABLE = False


def startup_print(message: str) -> None:
    if not os.getenv("RAILWAY_ENVIRONMENT") and not os.getenv("PRODUCTION"):
        print(message)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def check_user_management_availability():
    """[OK] FUNCIONAL: Verificación simple sin lógica redundante"""
    if not (FIREBASE_AVAILABLE and USER_MANAGEMENT_AVAILABLE):
        raise HTTPException(
            status_code=503,
            detail={
                "error": "Servicios no disponibles",
                "code": "SERVICES_UNAVAILABLE",
            },
        )


@router.post("/auth/validate-session", tags=["Administración y Control de Accesos"])
async def validate_session(request: Request):
    """
    ##  Validación de Sesión Activa para Next.js

    Valida si un token de ID de Firebase es válido y obtiene información completa del usuario.
    Optimizado para integración con Next.js y Firebase Auth SDK del frontend.

    ### [OK] Casos de uso:
    - Middleware de autenticación en Next.js
    - Verificación de permisos antes de acciones sensibles
    - Obtener datos actualizados del usuario
    - Validar sesiones activas desde el frontend

    ###  Proceso:
    1. Verifica token de Firebase desde Authorization header o body
    2. Valida estado del usuario (activo/deshabilitado)
    3. Obtiene datos completos de perfil desde Firestore
    4. Verifica permisos y roles

    ###  Ejemplo de uso desde Next.js:
    ```javascript
    // En tu frontend NextJS
    import { getAuth } from 'firebase/auth';

    const auth = getAuth();
    const user = auth.currentUser;
    if (user) {
        const idToken = await user.getIdToken();
        const response = await fetch('/auth/validate-session', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${idToken}`
            },
            body: JSON.stringify({ id_token: idToken })
        });
        const data = await response.json();
        if (data.success) {
            console.log('Usuario autenticado:', data.user);
        }
    }
    ```
    """
    try:
        check_user_management_availability()
        request_id = request.headers.get("x-request-id") or str(uuid.uuid4())

        # Obtener token del header Authorization o del body
        id_token = None

        # Primero intentar obtener del header Authorization
        auth_header = request.headers.get("authorization") or request.headers.get(
            "Authorization"
        )
        if auth_header and auth_header.startswith("Bearer "):
            id_token = auth_header.split(" ")[1]

        # Si no está en el header, intentar obtener del body
        if not id_token:
            try:
                body = await request.json()
                id_token = body.get("id_token")
            except (ValueError, TypeError, RuntimeError):
                # Si no se puede parsear el JSON, intentar obtener como form data
                try:
                    form = await request.form()
                    id_token = form.get("id_token")
                except (ValueError, TypeError, RuntimeError):
                    pass

        if not id_token:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "Token requerido",
                    "message": "Proporcione el token en el header Authorization o en el body como id_token",
                    "code": "TOKEN_REQUIRED",
                },
            )

        result = await validate_user_session(id_token)

        if not result["valid"]:
            raise HTTPException(
                status_code=401,
                detail={
                    "error": result["error"],
                    "code": result.get("code", "SESSION_INVALID"),
                },
            )

        # Limpiar datos de Firebase antes de serializar
        clean_user_data = clean_firebase_data(result.get("user", {}))
        clean_token_data = clean_firebase_data(result.get("token_data", {}))

        logger.info(
            "auth.validate_session.response request_id=%s uid=%s roles=%s source=%s profile_complete=%s firestore_doc=%s",
            request_id,
            clean_user_data.get("uid"),
            clean_user_data.get("roles", []),
            clean_user_data.get("roles_source"),
            clean_user_data.get("profile_complete"),
            bool(clean_user_data.get("firestore_data")),
        )

        return JSONResponse(
            content={
                "success": True,
                "session_valid": True,
                "request_id": request_id,
                "user": clean_user_data,
                "token_info": clean_token_data,
                "verified_at": result.get("verified_at"),
                "message": "Sesión válida",
            },
            status_code=200,
            headers={"Content-Type": "application/json; charset=utf-8"},
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "error": "Error interno del servidor",
                "message": "Ocurrió un error inesperado durante la validación de sesión",
                "code": "INTERNAL_SERVER_ERROR",
            },
        )


@router.post("/auth/login", tags=["Administración y Control de Accesos"])
@optional_rate_limit("10/minute")
async def login_user(request: Request, login_data: UserLoginRequest):
    """
    ##  Autenticación de Usuario con Email y Contraseña

    Valida credenciales de usuario usando Firebase Authentication.
    Requiere email y contraseña válidos para permitir el acceso.

    ### Validaciones realizadas:
    - Formato de email válido
    - Contraseña correcta mediante Firebase Auth REST API
    - Usuario activo y no deshabilitado
    - Estado de cuenta en Firestore

    ### Respuesta exitosa:
    - Información completa del usuario
    - Tokens de Firebase para sesión
    - Datos adicionales de Firestore

    ### Errores comunes:
    - 401: Credenciales incorrectas
    - 403: Usuario deshabilitado o cuenta inactiva
    - 400: Formato de email inválido
    """
    try:
        check_user_management_availability()

        # Autenticación con validación real de credenciales
        result = await authenticate_email_password(
            login_data.email, login_data.password
        )

        # Verificar si la autenticación fue exitosa
        if result.get("success"):
            clean_user_data = clean_firebase_data(result.get("user", {}))

            # [OK] PREPARAR RESPUESTA CON CUSTOM TOKEN
            response_data = {
                "success": True,
                "user": clean_user_data,
                "auth_method": result.get("auth_method", "email_password"),
                "credentials_validated": result.get("credentials_validated", True),
                "message": result.get("message", "Autenticación exitosa"),
                "timestamp": datetime.now().isoformat(),
            }

            # [OK] AGREGAR CUSTOM TOKEN SI ESTÁ DISPONIBLE
            if "custom_token" in result and result["custom_token"]:
                response_data["custom_token"] = result["custom_token"]
                response_data["token_usage"] = result.get(
                    "token_usage", "Use signInWithCustomToken() en Firebase Auth SDK"
                )

            # Agregar información de autenticación alternativa si está disponible
            if "alternative_auth" in result:
                response_data["alternative_auth"] = result["alternative_auth"]

            #  LOG TEMPORAL PARA DEBUGGING
            import logging

            logger = logging.getLogger(__name__)
            logger.info(f" LOGIN RESPONSE KEYS: {list(response_data.keys())}")
            logger.info(
                f"[WARNING]  custom_token present: {'custom_token' in response_data}"
            )
            if "custom_token" in response_data:
                logger.info(
                    f"[OK] Token preview: {response_data['custom_token'][:50]}..."
                )
            else:
                logger.warning(
                    f"[WARNING]  No custom_token - Alternative auth available: {'alternative_auth' in response_data}"
                )

            return JSONResponse(
                content=response_data,
                status_code=200,
                headers={"Content-Type": "application/json; charset=utf-8"},
            )
        else:
            # Autenticación fallida - mapear errores apropiados
            error_code = result.get("code", "AUTH_ERROR")

            # Mapear códigos de error a respuestas HTTP apropiadas
            if error_code in ["INVALID_CREDENTIALS", "USER_NOT_FOUND"]:
                raise HTTPException(
                    status_code=401,
                    detail={
                        "success": False,
                        "error": result["error"],
                        "code": error_code,
                    },
                )
            elif error_code in ["USER_DISABLED", "ACCOUNT_INACTIVE"]:
                raise HTTPException(
                    status_code=403,
                    detail={
                        "success": False,
                        "error": result["error"],
                        "code": error_code,
                    },
                )
            elif error_code in ["EMAIL_VALIDATION_ERROR", "INVALID_EMAIL_FORMAT"]:
                raise HTTPException(
                    status_code=400,
                    detail={
                        "success": False,
                        "error": result["error"],
                        "code": error_code,
                    },
                )
            else:
                # Cualquier otro error
                raise HTTPException(
                    status_code=500,
                    detail={
                        "success": False,
                        "error": result["error"],
                        "code": error_code,
                    },
                )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in login endpoint: {e}")
        return JSONResponse(
            content={
                "error": "Internal server error",
                "message": "An unexpected error occurred",
                "fallback": True,
                "timestamp": datetime.now().isoformat(),
            },
            status_code=500,
        )


@router.get("/auth/register/health-check", tags=["Administración y Control de Accesos"])
async def register_health_check():
    """
    ##  Health Check para Registro de Usuario

    Verifica que todos los servicios necesarios para el registro estén disponibles.
    Útil para diagnosticar problemas en producción.
    """
    try:
        health_status = {
            "timestamp": datetime.now().isoformat(),
            "environment": os.getenv("ENVIRONMENT", "development"),
            "services": {},
        }

        # Verificar Firebase
        try:
            check_user_management_availability()
            health_status["services"]["user_management"] = {
                "status": "available",
                "error": None,
            }
        except HTTPException as e:
            health_status["services"]["user_management"] = {
                "status": "unavailable",
                "error": str(e.detail),
            }

        # Verificar importaciones
        health_status["services"]["imports"] = {
            "firebase_available": FIREBASE_AVAILABLE,
            "scripts_available": SCRIPTS_AVAILABLE,
            "user_management_available": USER_MANAGEMENT_AVAILABLE,
            "auth_operations_available": AUTH_OPERATIONS_AVAILABLE,
            "user_models_available": USER_MODELS_AVAILABLE,
        }

        # Verificar configuración
        environment = os.getenv("ENVIRONMENT", "development")
        has_service_account = bool(os.getenv("FIREBASE_SERVICE_ACCOUNT_KEY"))

        health_status["configuration"] = {
            "project_id": PROJECT_ID,
            "environment": environment,
            "has_firebase_service_account": has_service_account,
            "firebase_available": FIREBASE_AVAILABLE,
            "auth_method": (
                "Service Account Key"
                if has_service_account
                else "Workload Identity Federation"
            ),
            "authorized_domain": os.getenv("AUTHORIZED_EMAIL_DOMAIN", "@cali.gov.co"),
            "deployment_ready": FIREBASE_AVAILABLE,  # Lo importante es que Firebase esté disponible
        }

        # Determinar estado general - soportar estructuras mixtas en 'services'
        def is_service_available(svc):
            """Evaluar si un servicio (o estructura) se considera disponible.

            - Si es dict y contiene 'status', se considera disponible cuando status == 'available'.
            - Si es dict con flags booleanos, se considera disponible cuando todos los flags booleanos son True.
            - Si es booleano, se usa su valor.
            - En cualquier otro caso se considera no disponible.
            """
            if isinstance(svc, dict):
                # Si tiene la clave 'status' respetarla
                if "status" in svc:
                    return svc.get("status") == "available"
                # Si es un diccionario de flags booleanas, todos deben ser True
                bool_flags = [v for v in svc.values() if isinstance(v, bool)]
                if bool_flags:
                    return all(bool_flags)
                # Fallback: consider available si el dict no está vacío
                return bool(svc)

            # Si es booleano, usar su valor
            if isinstance(svc, bool):
                return svc

            # Cualquier otro tipo se considera no disponible
            return False

        # Normalizar 'imports' a un campo 'status' legible para diagnósticos si procede
        imports_status = health_status["services"].get("imports")
        if isinstance(imports_status, dict) and "status" not in imports_status:
            health_status["services"]["imports"]["status"] = (
                "available" if is_service_available(imports_status) else "unavailable"
            )

        all_services_available = all(
            is_service_available(service)
            for service in health_status["services"].values()
        )

        status_code = 200 if all_services_available else 503
        health_status["overall_status"] = (
            "healthy" if all_services_available else "unhealthy"
        )

        return JSONResponse(
            content=health_status,
            status_code=status_code,
            headers={"Content-Type": "application/json; charset=utf-8"},
        )

    except Exception as e:
        return JSONResponse(
            content={
                "overall_status": "error",
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            },
            status_code=500,
            headers={"Content-Type": "application/json; charset=utf-8"},
        )


@router.post(
    "/auth/register",
    tags=["Administración y Control de Accesos"],
    status_code=status.HTTP_201_CREATED,
)
@optional_rate_limit("5/minute")
async def register_user(request: Request, registration_data: UserRegistrationRequest):
    """
    [OK] **REGISTRO DE USUARIO - VERSIÓN FUNCIONAL SIMPLIFICADA**

    **Fail Fast**: Si no hay Service Account configurado, falla inmediatamente
    **Sin Cache**: Cada request es independiente
    **Funcional**: Sin efectos colaterales entre registros
    """

    #  FAIL FAST: Verificar Service Account inmediatamente
    if not FIREBASE_AVAILABLE:
        environment = os.getenv("ENVIRONMENT", "development")
        if environment == "production":
            error_msg = "Firebase Service Account no configurado en producción"
            solution = "Configure FIREBASE_SERVICE_ACCOUNT_KEY en Railway"
        else:
            error_msg = (
                "Firebase no disponible en desarrollo (requiere WIF o Service Account)"
            )
            solution = (
                "Configure Workload Identity Federation o FIREBASE_SERVICE_ACCOUNT_KEY"
            )

        raise HTTPException(
            status_code=503,
            detail={
                "success": False,
                "error": error_msg,
                "code": "FIREBASE_UNAVAILABLE",
                "solution": solution,
                "environment": environment,
            },
        )

    try:
        # [OK] PROGRAMACIÓN FUNCIONAL: Una sola responsabilidad
        result = await create_user_account(
            email=registration_data.email,
            password=registration_data.password,
            fullname=registration_data.name,
            cellphone=registration_data.cellphone,
            nombre_centro_gestor=registration_data.nombre_centro_gestor,
            send_email_verification=True,
        )

        # [OK] FAIL FAST: Si hay error, fallar inmediatamente
        if not result.get("success", False):
            raise HTTPException(
                status_code=400,
                detail={
                    "success": False,
                    "error": result.get("error", "Error creando usuario"),
                    "code": result.get("code", "USER_CREATION_ERROR"),
                },
            )

        # [OK] FUNCIONAL: Transformar datos sin mutación
        return {
            "success": True,
            "user": clean_firebase_data(result.get("user", {})),
            "message": "Usuario creado exitosamente",
            "timestamp": datetime.now().isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        # [OK] SIMPLE: Error handling directo
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "error": "Error interno del servidor",
                "code": "INTERNAL_SERVER_ERROR",
                "debug": str(e) if os.getenv("ENVIRONMENT") == "development" else None,
            },
        )


# ---------------------------------------------------------------------------
# Forgot-password — genera enlace Firebase + envía correo HTML personalizado
# ---------------------------------------------------------------------------

try:
    from api.scripts import generate_password_reset_link

    _FORGOT_AVAILABLE = True
except Exception:
    generate_password_reset_link = None  # type: ignore[assignment]
    _FORGOT_AVAILABLE = False

try:
    from api.utils.email_service import (
        send_password_reset_email,
        EMAIL_SERVICE_AVAILABLE,
    )
except Exception:
    send_password_reset_email = None  # type: ignore[assignment]
    EMAIL_SERVICE_AVAILABLE = False


@router.post("/auth/forgot-password", tags=["Administración y Control de Accesos"])
@optional_rate_limit("5/minute")
async def forgot_password(request: Request):
    """
    ## Recuperación de Contraseña con Correo HTML Personalizado

    Genera un enlace de recuperación a través de Firebase Admin SDK y envía
    un correo HTML con botón, nombre del usuario y consejos de seguridad.

    ### Body JSON:
    ```json
    { "email": "usuario@ejemplo.com" }
    ```

    ### Respuesta exitosa:
    ```json
    {
      "success": true,
      "message": "Correo de recuperación enviado exitosamente",
      "email_sent": true
    }
    ```

    > Nota: por seguridad, la respuesta es siempre exitosa aunque el email
    > no exista en el sistema (evita enumeración de usuarios).
    """
    try:
        body = await request.json()
        email = (body.get("email") or "").strip().lower()
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "Body JSON inválido", "code": "INVALID_BODY"},
        )

    if not email:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "El campo 'email' es obligatorio",
                "code": "EMAIL_REQUIRED",
            },
        )

    # Respuesta genérica que no revela si el usuario existe
    generic_ok = {
        "success": True,
        "message": "Si existe una cuenta con ese correo, recibirás las instrucciones en breve.",
        "email_sent": False,
    }

    if not _FORGOT_AVAILABLE or generate_password_reset_link is None:
        logger.warning("generate_password_reset_link not available")
        return JSONResponse(content=generic_ok)

    # Generar enlace de reseteo con Firebase Admin SDK
    result = await generate_password_reset_link(email)
    if not result.get("success"):
        # No revelar que el usuario no existe — devolver respuesta genérica igualmente
        logger.info(
            f"forgot-password: link generation failed for {email}: {result.get('code')}"
        )
        return JSONResponse(content=generic_ok)

    reset_link = result["reset_link"]

    # Obtener nombre del usuario desde Firebase
    display_name = ""
    try:
        auth_client = None
        from database.firebase_config import get_auth_client as _get_auth

        auth_client = _get_auth()
        user_record = auth_client.get_user_by_email(email)
        display_name = user_record.display_name or ""
        # Si Firebase no tiene display_name, intentar desde Firestore
        if not display_name:
            db = get_firestore_client()
            doc = db.collection("users").document(user_record.uid).get()
            if doc.exists:
                data = doc.to_dict() or {}
                display_name = data.get("fullname") or data.get("name") or ""
    except Exception as exc:
        logger.debug(f"Could not fetch display_name for {email}: {exc}")

    # Enviar correo HTML personalizado
    email_sent = False
    if EMAIL_SERVICE_AVAILABLE and send_password_reset_email is not None:
        email_result = send_password_reset_email(
            to_email=email,
            reset_link=reset_link,
            display_name=display_name,
        )
        email_sent = email_result.get("success", False)
        if not email_sent:
            logger.warning(
                f"Custom email failed for {email}: {email_result.get('code')}. "
                "Falling back — user must use the reset link directly."
            )
    else:
        logger.info(
            "SMTP not configured. Reset link generated but not emailed. "
            f"Reset link for {email}: (see server logs if needed)"
        )

    return JSONResponse(
        content={
            "success": True,
            "message": "Si existe una cuenta con ese correo, recibirás las instrucciones en breve.",
            "email_sent": email_sent,
        }
    )


@router.post("/auth/change-password", tags=["Administración y Control de Accesos"])
@optional_rate_limit("5/minute")
async def change_password(
    request: Request,
    uid: str = Form(..., description="ID del usuario"),
    new_password: str = Form(..., description="Nueva contraseña"),
):
    """
    ##  Cambio de Contraseña

    Actualiza contraseñas de usuarios con validaciones de seguridad completas.
    **Requiere autenticación con token de Firebase.**

    ###  Autenticación requerida:
    - Header: `Authorization: Bearer <firebase_id_token>`

    ### [OK] Casos de uso:
    - Reset de contraseña por administrador
    - Cambio forzado por políticas de seguridad
    - Actualización por compromiso de cuenta

    ###  Validaciones:
    - Verificación de existencia del usuario
    - Validación de fortaleza de contraseña (8+ caracteres, mayúsculas, minúsculas, números, símbolos)
    - Actualización en Firebase Auth
    - Registro de timestamp en Firestore
    - Contador de cambios de contraseña

    ###  Seguridad:
    - Solo administradores pueden cambiar contraseñas
    - Histórico de cambios para auditoría
    - Notificación automática al usuario

    ###  Ejemplo de uso:
    ```javascript
    const passwordData = {
      uid: "Zx9mK2pQ8RhV3nL7jM4uX1qW6tY0sA5e",
      new_password: "NuevaPassword123!"
    };
    const response = await fetch('/auth/change-password', {
      method: 'POST',
      headers: {
        'Authorization': 'Bearer ' + idToken,
        'Content-Type': 'application/x-www-form-urlencoded'
      },
      body: new URLSearchParams(passwordData)
    });
    ```
    """
    try:
        #  VERIFICAR AUTENTICACIÓN FIREBASE
        current_user = await verify_firebase_token(request)
        check_user_management_availability()

        result = await update_user_password(uid, new_password)

        if not result.get("success", False):
            error_code = result.get("code", "PASSWORD_UPDATE_ERROR")
            error_message = result.get("error", "Error actualizando contraseña")

            if error_code == "USER_NOT_FOUND":
                raise HTTPException(
                    status_code=404,
                    detail={
                        "success": False,
                        "error": error_message,
                        "code": error_code,
                    },
                )
            else:
                raise HTTPException(
                    status_code=400,
                    detail={
                        "success": False,
                        "error": error_message,
                        "code": error_code,
                    },
                )

        return JSONResponse(
            content={
                "success": True,
                "message": result.get("message", "Contraseña actualizada exitosamente"),
                "updated_at": result.get("updated_at"),
                "timestamp": datetime.now().isoformat(),
            },
            status_code=200,
            headers={"Content-Type": "application/json; charset=utf-8"},
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "error": "Error interno del servidor",
                "message": "Ocurrió un error inesperado durante el cambio de contraseña",
                "code": "INTERNAL_SERVER_ERROR",
            },
        )


@router.get("/auth/config", tags=["Integración con el Frontend (NextJS)"])
async def get_firebase_config():
    """
    ##  Configuración Básica de Firebase para Frontend

    **ENDPOINT PÚBLICO** - Acceso directo desde frontend.

    Proporciona configuración mínima necesaria para Firebase Auth en frontend.

    ###  Seguridad:
    - Información pública solamente
    - Datos mínimos necesarios para SDK
    - Sin exposición de endpoints internos
    - Sin detalles de configuración sensibles

    ###  Información incluida:
    - Project ID de Firebase (público)
    - Auth Domain de Firebase (público)

    ###  Uso:
    - Inicialización de Firebase SDK en frontend
    - Configuración de autenticación client-side
    """
    # Solo información esencial para Firebase SDK
    return {"projectId": PROJECT_ID, "authDomain": f"{PROJECT_ID}.firebaseapp.com"}


# ENDPOINT REMOVIDO: /auth/integration-guide
# Razón: Documentación estática mejor manejada externamente
# Fecha: 2025-10-04
# La documentación de integración está disponible en README.md


@router.get(
    "/auth/workload-identity/status", tags=["Administración y Control de Accesos"]
)
async def get_workload_identity_status():
    """
    ##  Estado de Autenticación con Google Cloud

    **ENDPOINT DE DIAGNÓSTICO** - Verifica el estado de autenticación con Google Cloud.

    ###  Información incluida:
    - Estado de Service Account Key o Workload Identity
    - Validez de credenciales con Google Cloud
    - Configuración de Firebase
    - Nivel de seguridad actual

    ###  Útil para:
    - Verificar configuración después de deployment en Railway
    - Diagnóstico de problemas de autenticación
    - Auditoría de seguridad
    - Monitoreo del sistema

    ### [WARNING] Nota:
    Este endpoint es principalmente para diagnóstico. En producción,
    considera eliminar o restringir acceso por seguridad.
    """
    try:
        from api.scripts.workload_identity_auth import get_workload_identity_status

        status = get_workload_identity_status()

        return {
            "success": True,
            "workload_identity_status": status,
            "system_ready": status.get("workload_identity", {}).get(
                "initialized", False
            ),
            "security_level": status.get("security_level", "unknown"),
            "timestamp": datetime.now().isoformat(),
            "message": "Estado de Workload Identity obtenido exitosamente",
        }

    except Exception as e:
        return {
            "success": False,
            "error": "Error obteniendo estado de Workload Identity",
            "details": str(e),
            "fallback_available": True,
            "message": "Sistema puede funcionar en modo compatible",
        }


@router.post("/auth/google", tags=["Administración y Control de Accesos"])
async def google_auth_unified(
    google_token: str = Form(..., description="ID Token de Google Sign-In")
):
    """
    ##  Autenticación Google - ENDPOINT ÚNICO

    **EL ÚNICO ENDPOINT** que necesitas para autenticación Google completa.

    ###  **Funcionalidad Completa:**
    - [OK] Verifica token automáticamente con Workload Identity
    - [OK] Crea usuarios nuevos automáticamente
    - [OK] Actualiza usuarios existentes
    - [OK] Valida dominio @cali.gov.co
    - [OK] Retorna información completa del usuario
    - [OK] Máxima seguridad sin configuración manual

    ###  **Uso desde Frontend:**
    ```javascript
    // Después de Google Sign-In
    function handleGoogleAuth(response) {
        fetch('/auth/google', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ google_token: response.credential })
        })
        .then(res => res.json())
        .then(data => {
            if (data.success) {
                console.log('[OK] Autenticado:', data.user);
                // Tu lógica aquí
            }
        });
    }
    ```

    ###  **Compatible con:**
    - React, Vue, Angular, NextJS
    - Aplicaciones móviles
    - Progressive Web Apps
    - Cualquier framework que haga HTTP requests

    ###  **Seguridad:**
    - Workload Identity Federation
    - Sin credenciales en código
    - Verificación automática con Google
    - Auditoría completa de accesos
    """
    try:
        from api.scripts.workload_identity_auth import (
            authenticate_with_workload_identity,
        )

        result = await authenticate_with_workload_identity(google_token)

        if not result["success"]:
            error_code = result.get("code", "GOOGLE_AUTH_ERROR")

            # Mapear errores específicos a códigos HTTP apropiados
            if error_code == "UNAUTHORIZED_DOMAIN":
                raise HTTPException(
                    status_code=403,
                    detail={
                        "error": "Dominio no autorizado",
                        "message": "Solo se permite autenticación con cuentas @cali.gov.co",
                        "code": "UNAUTHORIZED_DOMAIN",
                    },
                )
            elif error_code in ["INVALID_TOKEN", "TOKEN_VERIFICATION_ERROR"]:
                raise HTTPException(
                    status_code=401,
                    detail={
                        "error": "Token inválido",
                        "message": "El token de Google no es válido o ha expirado",
                        "code": "INVALID_TOKEN",
                    },
                )
            elif error_code == "WORKLOAD_IDENTITY_ERROR":
                raise HTTPException(
                    status_code=503,
                    detail={
                        "error": "Servicio no disponible",
                        "message": "Sistema de autenticación temporalmente no disponible",
                        "code": "SERVICE_UNAVAILABLE",
                    },
                )
            else:
                raise HTTPException(
                    status_code=400,
                    detail={
                        "error": "Error de autenticación",
                        "message": result.get("error", "Error desconocido"),
                        "code": error_code,
                    },
                )

        # Limpiar datos de Firebase antes de serializar
        clean_user_data = clean_firebase_data(result["user"])

        return {
            "success": True,
            "user": clean_user_data,
            "auth_method": "workload_identity_google",
            "security_level": "high",
            "user_created": result.get("user_created", False),
            "message": result["message"],
            "timestamp": datetime.now().isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        startup_print(f"Unexpected error in Google auth: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Error interno del servidor",
                "message": "Por favor, inténtelo de nuevo más tarde",
                "code": "INTERNAL_ERROR",
            },
        )


# ============================================================================
# ENDPOINTS DE ELIMINACIÓN DE USUARIOS
# ============================================================================


@router.delete("/auth/user/{uid}", tags=["Administración y Control de Accesos"])
async def delete_user(
    uid: str,
    request: Request,
    soft_delete: Optional[bool] = Query(
        default=None, description="Eliminación lógica (true) o física (false)"
    ),
):
    """
    ##  Eliminación de Usuario

    Elimina cuentas con opciones flexibles de soft delete (recomendado) o hard delete.
    **Requiere autenticación con token de Firebase.**

    ###  Autenticación requerida:
    - Header: `Authorization: Bearer <firebase_id_token>`

    ### [OK] Casos de uso:
    - Desvinculación de empleados (soft delete)
    - Limpieza de cuentas de prueba (hard delete)
    - Cumplimiento de políticas de retención de datos

    ###  Tipos de eliminación:
    - **Soft delete (predeterminado)**: Deshabilita usuario, mantiene datos para auditoría
    - **Hard delete**: Elimina completamente de Firebase Auth y Firestore

    ###  Protecciones:
    - No permite eliminar el último administrador del sistema
    - Validación de permisos para hard delete
    - Registro de auditoría de eliminaciones

    ###  Ejemplos de uso:
    ```javascript
    // Eliminación lógica (recomendada)
    const response = await fetch('/auth/user/Zx9mK2pQ8RhV3nL7jM4uX1qW6tY0sA5e?soft_delete=true', {
      method: 'DELETE',
      headers: {
        'Authorization': 'Bearer ' + idToken
      }
    });

    // Eliminación física (permanente)
    const response = await fetch('/auth/user/Zx9mK2pQ8RhV3nL7jM4uX1qW6tY0sA5e?soft_delete=false', {
      method: 'DELETE',
      headers: {
        'Authorization': 'Bearer ' + idToken
      }
    });
    ```
    """
    try:
        #  VERIFICAR AUTENTICACIÓN FIREBASE
        current_user = await verify_firebase_token(request)

        from auth_system.permissions import get_user_permissions
        from database.firebase_config import get_firestore_client

        firestore_client = get_firestore_client()
        if firestore_client is None:
            raise HTTPException(
                status_code=503,
                detail={
                    "success": False,
                    "error": "No se pudo conectar a Firestore",
                    "code": "FIRESTORE_UNAVAILABLE",
                },
            )

        #  VERIFICAR PERMISO DE GESTIÓN DE USUARIOS (evita IDOR: cualquier
        #  usuario autenticado podía eliminar cualquier cuenta).
        current_permissions = get_user_permissions(
            current_user["uid"], firestore_client
        )
        if "*" not in current_permissions and "manage:users" not in current_permissions:
            raise HTTPException(
                status_code=403,
                detail={
                    "success": False,
                    "error": "Permiso denegado",
                    "code": "INSUFFICIENT_PERMISSIONS",
                },
            )

        check_user_management_availability()

        result = await delete_user_account(
            uid, soft_delete if soft_delete is not None else True
        )

        if not result.get("success", False):
            error_code = result.get("code", "USER_DELETE_ERROR")
            error_message = result.get("error", "Error eliminando usuario")

            if error_code == "USER_NOT_FOUND":
                raise HTTPException(
                    status_code=404,
                    detail={
                        "success": False,
                        "error": error_message,
                        "code": error_code,
                    },
                )
            else:
                raise HTTPException(
                    status_code=400,
                    detail={
                        "success": False,
                        "error": error_message,
                        "code": error_code,
                    },
                )

        return JSONResponse(
            content={
                "success": True,
                "message": result.get("message", "Usuario eliminado exitosamente"),
                "deleted_at": result.get("deleted_at"),
                "soft_delete": result.get("soft_delete", True),
                "timestamp": datetime.now().isoformat(),
            },
            status_code=200,
            headers={"Content-Type": "application/json; charset=utf-8"},
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "error": "Error interno del servidor",
                "message": "Ocurrió un error inesperado durante la eliminación",
                "code": "INTERNAL_SERVER_ERROR",
            },
        )


# ============================================================================
# ENDPOINTS ADMINISTRATIVOS DE USUARIOS
# ============================================================================


@router.get("/admin/users", tags=["Administración y Control de Accesos"])
async def list_system_users(
    request: Request,
    limit: int = Query(
        default=100, ge=1, le=1000, description="Límite de resultados por página"
    ),
):
    """
    ##  Listado de Usuarios desde Firestore

    Lee directamente la colección "users" de Firestore y devuelve todos los usuarios registrados.
    **Requiere autenticación con token de Firebase.**

    ###  Autenticación requerida:
    - Header: `Authorization: Bearer <firebase_id_token>`

    ###  Información incluida:
    - UID del usuario
    - Email y nombre completo
    - Teléfono y centro gestor
    - Fechas de creación y actualización
    - Estado de activación y verificación
    - Proveedores de autenticación
    - Estadísticas de login

    ###  Ejemplo de uso:
    ```javascript
    const response = await fetch('/admin/users?limit=50', {
      headers: {
        'Authorization': 'Bearer ' + idToken,
        'Content-Type': 'application/json'
      }
    });
    const data = await response.json();
    console.log(`Encontrados ${data.count} usuarios`);
    ```
    """
    try:
        #  VERIFICAR AUTENTICACIÓN FIREBASE
        current_user = await verify_firebase_token(request)

        from auth_system.permissions import get_user_permissions
        from database.firebase_config import get_firestore_client

        firestore_client = get_firestore_client()
        if firestore_client is None:
            raise HTTPException(
                status_code=503,
                detail={
                    "success": False,
                    "error": "No se pudo conectar a Firestore",
                    "code": "FIRESTORE_UNAVAILABLE",
                },
            )

        current_permissions = get_user_permissions(
            current_user["uid"], firestore_client
        )
        if "*" not in current_permissions and "manage:users" not in current_permissions:
            raise HTTPException(
                status_code=403,
                detail={
                    "success": False,
                    "error": "Permiso denegado",
                    "code": "INSUFFICIENT_PERMISSIONS",
                },
            )

        check_user_management_availability()

        # Consultar la colección "users" directamente
        users_ref = firestore_client.collection("users")
        query = users_ref.limit(limit)
        docs = cast(List[FirestoreDocSnapshot], query.get())

        users_list = []
        for doc in docs:
            if doc.exists:
                user_data = doc.to_dict()

                user_info = {
                    "uid": doc.id,
                    "email": user_data.get("email"),
                    "fullname": user_data.get("fullname"),
                    "cellphone": user_data.get("cellphone"),
                    "nombre_centro_gestor": user_data.get("nombre_centro_gestor"),
                    "created_at": user_data.get("created_at"),
                    "updated_at": user_data.get("updated_at"),
                    "is_active": user_data.get("is_active", True),
                    "email_verified": user_data.get("email_verified", False),
                    "can_use_google_auth": user_data.get("can_use_google_auth", False),
                    "auth_providers": user_data.get("auth_providers", []),
                    "last_login": user_data.get("last_login"),
                    "login_count": user_data.get("login_count", 0),
                }

                # Limpiar datos de Firebase antes de agregar a la lista
                user_info = clean_firebase_data(user_info)
                users_list.append(user_info)

        return JSONResponse(
            content={
                "success": True,
                "users": users_list,
                "count": len(users_list),
                "collection": "users",
                "timestamp": datetime.now().isoformat(),
                "message": f"Se obtuvieron {len(users_list)} usuarios de la colección 'users'",
            },
            status_code=200,
            headers={"Content-Type": "application/json; charset=utf-8"},
        )

    except HTTPException:
        # Re-lanzar HTTPException (como las de autenticación) sin modificar
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "error": str(e),
                "message": "Error leyendo la colección 'users' de Firestore",
                "code": "FIRESTORE_READ_ERROR",
            },
        )


# ============================================================================
# ENDPOINTS DE GESTIÓN DE EMPRÉSTITO
# ============================================================================

# Verificar disponibilidad de operaciones de empréstito
try:
    from api.scripts import (
        procesar_emprestito_completo,
        verificar_proceso_existente,
        eliminar_proceso_emprestito,
        actualizar_proceso_emprestito,
        obtener_codigos_contratos,
        buscar_y_poblar_contratos_secop,
        obtener_contratos_desde_proceso_contractual,
        obtener_contratos_desde_proceso_contractual_completo,
        get_emprestito_operations_status,
        cargar_orden_compra_directa,
        cargar_convenio_transferencia,
        modificar_convenio_transferencia,
        actualizar_orden_compra_por_numero,
        eliminar_orden_compra_por_numero,
        eliminar_convenio_transferencia_por_referencia,
        actualizar_convenio_por_referencia,
        actualizar_contrato_secop_por_referencia,
        actualizar_proceso_secop_por_referencia,
        cargar_rpc_emprestito,
        cargar_pago_emprestito,
        get_pagos_emprestito_all,
        get_rpc_contratos_emprestito_all,
        actualizar_rpc_contrato_emprestito,
        get_asignaciones_emprestito_banco_centro_gestor_all,
        get_convenios_transferencia_emprestito_all,
        obtener_ordenes_compra_tvec_enriquecidas,
        get_tvec_enrich_status,
        get_ordenes_compra_emprestito_all,
        get_ordenes_compra_emprestito_by_referencia,
        get_ordenes_compra_emprestito_by_centro_gestor,
        # Control de cambios para auditoría
        registrar_cambio_valor,
        obtener_historial_cambios,
        EMPRESTITO_OPERATIONS_AVAILABLE,
        TVEC_ENRICH_OPERATIONS_AVAILABLE,
        ORDENES_COMPRA_OPERATIONS_AVAILABLE,
    )
    from api.models import (
        EmprestitoRequest,
        EmprestitoResponse,
        PagoEmprestitoRequest,
        PagoEmprestitoResponse,
    )

    logger.info(
        f"Empréstito imports successful - AVAILABLE: {EMPRESTITO_OPERATIONS_AVAILABLE}"
    )
    logger.info(
        f"TVEC enrich imports successful - AVAILABLE: {TVEC_ENRICH_OPERATIONS_AVAILABLE}"
    )
except ImportError as e:
    logger.error(f"Warning: Empréstito or TVEC imports failed: {e}")
    EMPRESTITO_OPERATIONS_AVAILABLE = False
    TVEC_ENRICH_OPERATIONS_AVAILABLE = False


def check_emprestito_availability():
    """Verificar disponibilidad de operaciones de empréstito"""
    if not EMPRESTITO_OPERATIONS_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "Servicios de empréstito no disponibles",
                "message": "Firebase o dependencias no configuradas correctamente",
                "code": "EMPRESTITO_SERVICES_UNAVAILABLE",
            },
        )

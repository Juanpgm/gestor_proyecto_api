"""
Decoradores para Control de Acceso
Decoradores y dependencias de FastAPI para proteger endpoints
"""

import os
from functools import wraps
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import List, Optional, Tuple
from .permissions import (
    get_user_permissions,
    validate_permission,
    has_role as check_has_role,
)
from .constants import FIREBASE_COLLECTIONS

import logging

logger = logging.getLogger(__name__)


def _centro_scoping_disabled() -> bool:
    """Kill-switch de operaciones para el rollout del scoping por centro_gestor.

    Si ``CENTRO_SCOPING_DISABLED`` está en {1,true,yes,on}, el scoping ``:own_centro``
    no se fuerza (los endpoints se comportan como globales). Pensado como break-glass
    si la normalización de datos deja usuarios sin ver su propio centro.
    """
    return os.getenv("CENTRO_SCOPING_DISABLED", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }

# Security scheme para Bearer token
security = HTTPBearer()


async def get_current_user(
    request: Request, credentials: HTTPAuthorizationCredentials = Depends(security)
) -> dict:
    """
    Dependency para obtener el usuario actual desde el token de Firebase

    Args:
        request: Request de FastAPI
        credentials: Credenciales del header Authorization

    Returns:
        Diccionario con datos del usuario autenticado

    Raises:
        HTTPException: Si el token es inválido o el usuario no existe
    """
    try:
        # Importar Firebase Auth
        from firebase_admin import auth
        from database.firebase_config import get_firestore_client

        # Reutilizar el UID ya decodificado por AuthorizationMiddleware (evita
        # una segunda llamada a verify_id_token que cuesta ~100-150 ms extra).
        user_uid = getattr(request.state, "user_uid", None)
        if not user_uid:
            # Fallback: ruta no pasó por el middleware (p.ej. pruebas directas).
            # Se ejecuta en un executor para no bloquear el event loop de asyncio.
            import asyncio

            token = credentials.credentials
            loop = asyncio.get_event_loop()
            decoded_token = await loop.run_in_executor(
                None, auth.verify_id_token, token
            )
            user_uid = decoded_token["uid"]

        # Obtener datos completos del usuario desde Firestore
        db = get_firestore_client()
        user_doc = db.collection(FIREBASE_COLLECTIONS["users"]).document(user_uid).get()

        if not user_doc.exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Usuario no encontrado en la base de datos",
            )

        user_data = user_doc.to_dict()
        if not user_data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Documento de usuario inválido o vacío",
            )
        user_data["uid"] = user_uid

        # Verificar que el usuario esté activo
        if not user_data.get("is_active", True):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Usuario inactivo"
            )

        # Agregar permisos al objeto de usuario.
        # Pasamos user_data ya cargado para evitar que get_user_permissions
        # haga una segunda lectura del mismo documento.
        user_data["permissions"] = get_user_permissions(
            user_uid, db, user_data=user_data
        )

        return user_data

    except auth.InvalidIdTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido o expirado",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except Exception as e:
        if isinstance(e, HTTPException):
            raise
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error verificando autenticación: {str(e)}",
        )


def require_permission(permission: str):
    """
    Decorador para requerir un permiso específico

    Args:
        permission: Permiso requerido (ej: "write:proyectos")

    Usage:
        @app.post("/proyectos")
        @require_permission("write:proyectos")
        async def create_proyecto(current_user: dict = Depends(get_current_user)):
            pass
    """

    def decorator(func):
        @wraps(func)
        async def wrapper(
            *args, current_user: dict = Depends(get_current_user), **kwargs
        ):
            user_permissions = current_user.get("permissions", [])

            if not validate_permission(user_permissions, permission):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Permiso denegado: Se requiere el permiso '{permission}'",
                )

            return await func(*args, current_user=current_user, **kwargs)

        return wrapper

    return decorator


def require_role(roles: List[str]):
    """
    Decorador para requerir uno o más roles específicos

    Args:
        roles: Lista de roles permitidos

    Usage:
        @app.delete("/admin/purge")
        @require_role(["super_admin"])
        async def purge_data(current_user: dict = Depends(get_current_user)):
            pass
    """

    def decorator(func):
        @wraps(func)
        async def wrapper(
            *args, current_user: dict = Depends(get_current_user), **kwargs
        ):
            raw_roles = current_user.get("roles", [])
            if isinstance(raw_roles, str):
                user_roles = [raw_roles.strip()]
            elif isinstance(raw_roles, (list, tuple, set)):
                user_roles = [str(r).strip() for r in raw_roles]
            else:
                user_roles = []

            has_required_role = any(role in user_roles for role in roles)

            if not has_required_role:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Acceso denegado: Se requiere uno de los roles: {', '.join(roles)}",
                )

            return await func(*args, current_user=current_user, **kwargs)

        return wrapper

    return decorator


def optional_auth():
    """
    Dependency que permite autenticación opcional
    Retorna None si no hay token, o el usuario si hay token válido

    Usage:
        @app.get("/public-or-private")
        async def endpoint(current_user: Optional[dict] = Depends(optional_auth)):
            if current_user:
                return {"message": "Authenticated"}
            return {"message": "Public access"}
    """

    async def _optional_auth(request: Request) -> Optional[dict]:
        try:
            auth_header = request.headers.get("Authorization")
            if not auth_header or not auth_header.startswith("Bearer "):
                return None

            token = auth_header.split(" ")[1]

            from firebase_admin import auth
            from database.firebase_config import get_firestore_client

            decoded_token = auth.verify_id_token(token)
            user_uid = decoded_token["uid"]

            db = get_firestore_client()
            user_doc = (
                db.collection(FIREBASE_COLLECTIONS["users"]).document(user_uid).get()
            )

            if not user_doc.exists:
                return None

            user_data = user_doc.to_dict()
            user_data["uid"] = user_uid
            user_data["permissions"] = get_user_permissions(user_uid, db)

            return user_data

        except Exception:
            return None

    return Depends(_optional_auth)


# ---------------------------------------------------------------------------
# Helpers de autorización para endpoints (uso directo dentro del handler)
# ---------------------------------------------------------------------------
async def get_user_with_permissions(request: Request) -> dict:
    """Obtiene el usuario y sus permisos a partir de ``request.state.user_uid``
    (que ya colocó el ``AuthorizationMiddleware``). Evita re-verificar el token.

    Lanza HTTPException(401) si no hay usuario autenticado.
    Lanza HTTPException(404) si el documento del usuario no existe.
    """
    user_uid = (
        getattr(request.state, "user_uid", None) if hasattr(request, "state") else None
    )
    if not user_uid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No autenticado",
        )
    try:
        from database.firebase_config import get_firestore_client

        db = get_firestore_client()
        user_doc = db.collection(FIREBASE_COLLECTIONS["users"]).document(user_uid).get()
        if not user_doc.exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Usuario no encontrado",
            )
        user_data = user_doc.to_dict() or {}
        user_data["uid"] = user_uid
        user_data["permissions"] = get_user_permissions(user_uid, db)
        return user_data
    except HTTPException:
        raise
    except Exception as e:
        logger.error("get_user_with_permissions failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error obteniendo usuario",
        )


def _user_centro_gestor(user_data: dict) -> Optional[str]:
    """Devuelve el centro_gestor del usuario, aceptando ambas convenciones."""
    cg = (
        user_data.get("centro_gestor_assigned")
        or user_data.get("nombre_centro_gestor")
        or user_data.get("centro_gestor")
    )
    if isinstance(cg, str):
        cg = cg.strip()
    return cg or None


def _has_permission(perms: List[str], required: str) -> Tuple[bool, bool]:
    """Evalúa un permiso ``action:resource``. Devuelve ``(has_any, only_own_centro)``.

    ``has_any``: tiene alguna variante del permiso (global, own_centro, basic, public).
    ``only_own_centro``: tiene exclusivamente la versión ``:own_centro``
    (debe forzarse el filtro por su centro).
    """
    if not perms:
        return (False, False)
    if "*" in perms:
        return (True, False)
    action = required.split(":")[0]
    if f"{action}:*" in perms or required in perms:
        # ¿También tiene :own_centro? Si solo tiene own_centro, ya entró por otro check
        return (True, False)
    if f"{required}:own_centro" in perms:
        return (True, True)
    if f"{required}:basic" in perms or f"{required}:public" in perms:
        return (True, False)
    return (False, False)


def enforce_resource_access(
    user_data: dict,
    permission_required: str,
    requested_centro: Optional[str] = None,
) -> Optional[str]:
    """Valida acceso a un recurso y aplica scoping por centro_gestor (genérico).

    - Verifica que el usuario tenga ``permission_required`` (en cualquiera de sus
      variantes: global, ``:own_centro``, ``:basic``, ``:public``).
    - Si su único permiso es ``:own_centro`` / ``:basic``, fuerza/valida que
      ``requested_centro`` coincida con su centro_gestor.

    Devuelve el ``centro_gestor`` efectivo que debe usarse para filtrar (o
    ``None`` si el usuario es global y no filtró).
    Lanza HTTPException(403) si no tiene permisos.

    ``permission_required`` tiene la forma ``action:resource`` (ej. ``read:unidades``,
    ``read:contratos``, ``read:emprestito``).
    """
    perms = user_data.get("permissions", []) or []
    has_any, only_own = _has_permission(perms, permission_required)
    if not has_any:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Permiso denegado: se requiere '{permission_required}'",
        )

    user_cg = _user_centro_gestor(user_data)
    requested_cg = (requested_centro or "").strip() or None

    # Break-glass: no forzar scoping durante el rollout si ops lo desactiva.
    if only_own and _centro_scoping_disabled():
        only_own = False

    if only_own:
        if not user_cg:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Usuario sin centro_gestor asignado",
            )
        if requested_cg and requested_cg != user_cg:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No puede acceder a un centro_gestor distinto al asignado",
            )
        return user_cg

    return requested_cg


# Alias de compatibilidad (firma idéntica). El recurso lo lleva permission_required.
enforce_unidades_access = enforce_resource_access


def require_resource(resource: str, action: str):
    """Factory de ``Depends`` para validar permisos sobre ``resource``.

    ``resource``: ``unidades``, ``proyectos``, ``contratos``, ``emprestito``, ...
    ``action``: ``read``, ``write``, ``delete``, ...

    Carga el usuario, valida que tenga la familia del permiso (global, own_centro,
    basic o public) y guarda el usuario en ``request.state.current_user`` para que
    el handler pueda aplicar scoping con ``enforce_resource_access``.
    """
    permission_required = f"{action}:{resource}"

    async def _dep(request: Request) -> dict:
        user = await get_user_with_permissions(request)
        perms = user.get("permissions", []) or []
        has_any, _ = _has_permission(perms, permission_required)
        if not has_any:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permiso denegado: se requiere '{permission_required}'",
            )
        try:
            request.state.current_user = user
        except Exception:
            pass
        return user

    return _dep


def require_unidades(action: str):
    """Compatibilidad: equivale a ``require_resource('unidades', action)``."""
    return require_resource("unidades", action)

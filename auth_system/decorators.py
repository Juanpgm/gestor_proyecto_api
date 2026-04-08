"""
Decoradores para Control de Acceso
Decoradores y dependencias de FastAPI para proteger endpoints
"""

from functools import wraps
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import List, Optional
from .permissions import get_user_permissions, validate_permission, has_role as check_has_role
from .constants import FIREBASE_COLLECTIONS

# Security scheme para Bearer token
security = HTTPBearer()


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security)
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
        
        # Verificar token de Firebase
        token = credentials.credentials
        decoded_token = auth.verify_id_token(token)
        user_uid = decoded_token['uid']
        
        # Obtener datos completos del usuario desde Firestore
        db = get_firestore_client()
        user_doc = db.collection(FIREBASE_COLLECTIONS["users"]).document(user_uid).get()
        
        if not user_doc.exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Usuario no encontrado en la base de datos"
            )
        
        user_data = user_doc.to_dict()
        user_data['uid'] = user_uid
        
        # Verificar que el usuario esté activo
        if not user_data.get('is_active', True):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Usuario inactivo"
            )
        
        # Agregar permisos al objeto de usuario
        user_data['permissions'] = get_user_permissions(user_uid, db)
        
        return user_data
        
    except auth.InvalidIdTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido o expirado",
            headers={"WWW-Authenticate": "Bearer"}
        )
    except Exception as e:
        if isinstance(e, HTTPException):
            raise
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error verificando autenticación: {str(e)}"
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
        async def wrapper(*args, current_user: dict = Depends(get_current_user), **kwargs):
            user_permissions = current_user.get('permissions', [])
            
            if not validate_permission(user_permissions, permission):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Permiso denegado: Se requiere el permiso '{permission}'"
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
        async def wrapper(*args, current_user: dict = Depends(get_current_user), **kwargs):
            user_roles = current_user.get('roles', [])
            
            has_required_role = any(role in user_roles for role in roles)
            
            if not has_required_role:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Acceso denegado: Se requiere uno de los roles: {', '.join(roles)}"
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
            user_uid = decoded_token['uid']
            
            db = get_firestore_client()
            user_doc = db.collection(FIREBASE_COLLECTIONS["users"]).document(user_uid).get()
            
            if not user_doc.exists:
                return None
            
            user_data = user_doc.to_dict()
            user_data['uid'] = user_uid
            user_data['permissions'] = get_user_permissions(user_uid, db)
            
            return user_data
            
        except Exception:
            return None
    
    return Depends(_optional_auth)

"""
Sistema de Permisos y Validación
Funciones para gestión y verificación de permisos de usuarios
"""

from typing import List, Dict, Optional
from datetime import datetime, timezone
from .constants import ROLES, ROLE_HIERARCHY, FIREBASE_COLLECTIONS


def get_user_permissions(user_uid: str, db_client=None) -> List[str]:
    """
    Obtiene todos los permisos de un usuario basándose en sus roles
    
    Args:
        user_uid: UID del usuario en Firebase
        db_client: Cliente de Firestore (opcional, se obtiene si no se proporciona)
    
    Returns:
        Lista de permisos del usuario
    """
    if db_client is None:
        from database.firebase_config import get_firestore_client
        db_client = get_firestore_client()
    
    try:
        # Obtener documento del usuario
        user_doc = db_client.collection(FIREBASE_COLLECTIONS["users"]).document(user_uid).get()
        
        if not user_doc.exists:
            return []
        
        user_data = user_doc.to_dict()
        user_roles = user_data.get('roles', [])
        
        # Recolectar permisos de todos los roles
        all_permissions = set()
        
        for role in user_roles:
            if role in ROLES:
                role_permissions = ROLES[role]["permissions"]
                all_permissions.update(role_permissions)
        
        # Agregar permisos temporales válidos
        temp_permissions = user_data.get('temporary_permissions', [])
        now = datetime.now(timezone.utc)
        
        for temp_perm in temp_permissions:
            expires_at = temp_perm.get('expires_at')
            if expires_at and isinstance(expires_at, datetime):
                if expires_at > now:
                    all_permissions.add(temp_perm['permission'])
        
        return list(all_permissions)
        
    except Exception as e:
        print(f"Error obteniendo permisos del usuario {user_uid}: {e}")
        return []


def validate_permission(user_permissions: List[str], required_permission: str) -> bool:
    """
    Valida si el usuario tiene el permiso requerido
    
    Args:
        user_permissions: Lista de permisos del usuario
        required_permission: Permiso requerido
    
    Returns:
        True si el usuario tiene el permiso, False en caso contrario
    """
    # Super admin tiene todos los permisos
    if "*" in user_permissions:
        return True
    
    # Verificar permiso exacto
    if required_permission in user_permissions:
        return True
    
    # Verificar wildcards (ej: "read:*" cubre "read:proyectos")
    parts = required_permission.split(':')
    if len(parts) >= 2:
        action = parts[0]
        wildcard_permission = f"{action}:*"
        if wildcard_permission in user_permissions:
            return True
    
    return False


def has_permission(user_uid: str, permission: str, db_client=None) -> bool:
    """
    Verifica si un usuario tiene un permiso específico
    
    Args:
        user_uid: UID del usuario
        permission: Permiso a verificar
        db_client: Cliente de Firestore (opcional)
    
    Returns:
        True si tiene el permiso, False en caso contrario
    """
    user_permissions = get_user_permissions(user_uid, db_client)
    return validate_permission(user_permissions, permission)


def has_role(user_uid: str, role: str, db_client=None) -> bool:
    """
    Verifica si un usuario tiene un rol específico
    
    Args:
        user_uid: UID del usuario
        role: Rol a verificar
        db_client: Cliente de Firestore (opcional)
    
    Returns:
        True si tiene el rol, False en caso contrario
    """
    if db_client is None:
        from database.firebase_config import get_firestore_client
        db_client = get_firestore_client()
    
    try:
        user_doc = db_client.collection(FIREBASE_COLLECTIONS["users"]).document(user_uid).get()
        
        if not user_doc.exists:
            return False
        
        user_data = user_doc.to_dict()
        user_roles = user_data.get('roles', [])
        
        return role in user_roles
        
    except Exception as e:
        print(f"Error verificando rol del usuario {user_uid}: {e}")
        return False


def check_scope_access(user_data: Dict, resource_centro_gestor: str, permission: str) -> bool:
    """
    Verifica acceso basado en scope del permiso
    
    Args:
        user_data: Datos del usuario
        resource_centro_gestor: Centro gestor del recurso
        permission: Permiso que incluye scope
    
    Returns:
        True si tiene acceso, False en caso contrario
    """
    # Si el permiso no tiene scope, permitir acceso
    if ':own_centro' not in permission:
        return True
    
    # Verificar que el centro gestor del recurso coincida con el del usuario
    user_centro_gestor = user_data.get('centro_gestor_assigned')
    
    if not user_centro_gestor:
        return False
    
    return user_centro_gestor == resource_centro_gestor


def get_user_role_level(user_uid: str, db_client=None) -> int:
    """
    Obtiene el nivel jerárquico más alto del usuario
    
    Args:
        user_uid: UID del usuario
        db_client: Cliente de Firestore (opcional)
    
    Returns:
        Nivel jerárquico (0 = máximo, 6 = mínimo)
    """
    if db_client is None:
        from database.firebase_config import get_firestore_client
        db_client = get_firestore_client()
    
    try:
        user_doc = db_client.collection(FIREBASE_COLLECTIONS["users"]).document(user_uid).get()
        
        if not user_doc.exists:
            return 999  # Sin rol
        
        user_data = user_doc.to_dict()
        user_roles = user_data.get('roles', [])
        
        if not user_roles:
            return 999
        
        # Obtener el nivel más bajo (más privilegios)
        min_level = 999
        for role in user_roles:
            if role in ROLE_HIERARCHY:
                level = ROLE_HIERARCHY[role]
                if level < min_level:
                    min_level = level
        
        return min_level
        
    except Exception as e:
        print(f"Error obteniendo nivel de rol del usuario {user_uid}: {e}")
        return 999

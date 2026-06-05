"""
Utilidades para el Sistema de Autenticación
Funciones auxiliares comunes
"""

from typing import Dict, Any
from datetime import datetime


def sanitize_user_data(user_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Sanitiza datos del usuario removiendo información sensible
    
    Args:
        user_data: Diccionario con datos del usuario
    
    Returns:
        Diccionario sanitizado
    """
    sensitive_fields = ['password', 'password_hash', 'temporary_permissions']
    
    sanitized = {k: v for k, v in user_data.items() if k not in sensitive_fields}
    
    # Convertir timestamps de Firebase a ISO format
    for key, value in sanitized.items():
        if isinstance(value, datetime):
            sanitized[key] = value.isoformat()
    
    return sanitized


def format_audit_log(log_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Formatea un log de auditoría para presentación
    
    Args:
        log_data: Datos del log
    
    Returns:
        Log formateado
    """
    formatted = log_data.copy()
    
    # Convertir timestamp
    if 'timestamp' in formatted and isinstance(formatted['timestamp'], datetime):
        formatted['timestamp'] = formatted['timestamp'].isoformat()
    
    return formatted


def validate_role_assignment(user_uid: str, target_uid: str, roles: list) -> bool:
    """
    Valida que la asignación de roles sea segura
    
    Args:
        user_uid: UID del usuario que asigna
        target_uid: UID del usuario objetivo
        roles: Roles a asignar
    
    Returns:
        True si es válida, False en caso contrario
    """
    # Prevenir auto-asignación de super_admin
    if user_uid == target_uid and "super_admin" in roles:
        return False
    
    return True


def calculate_permission_diff(old_permissions: list, new_permissions: list) -> Dict[str, list]:
    """
    Calcula la diferencia entre dos listas de permisos
    
    Args:
        old_permissions: Permisos anteriores
        new_permissions: Permisos nuevos
    
    Returns:
        Diccionario con permisos agregados y removidos
    """
    old_set = set(old_permissions)
    new_set = set(new_permissions)
    
    return {
        "added": list(new_set - old_set),
        "removed": list(old_set - new_set),
        "unchanged": list(old_set & new_set)
    }

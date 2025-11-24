"""
Router de Administración de Usuarios, Roles y Permisos
Endpoints para gestión completa del sistema de autorización
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional, List
from datetime import datetime, timezone

from auth_system.decorators import require_permission, require_role, get_current_user
from auth_system.models import (
    AssignRolesRequest, 
    GrantTemporaryPermissionRequest,
    UserResponse,
    RoleDetails,
    StandardAuthResponse
)
from auth_system.constants import ROLES, FIREBASE_COLLECTIONS, DEFAULT_USER_ROLE
from auth_system.utils import validate_role_assignment, sanitize_user_data
from database.firebase_config import get_firestore_client

router = APIRouter(prefix="/auth/admin", tags=["Administración y Control de Accesos"])


# ========== GESTIÓN DE USUARIOS ==========

@router.get("/users", response_model=dict)
async def list_users(
    current_user: dict = Depends(get_current_user),
    limit: Optional[int] = Query(100, ge=1, le=500),
    offset: Optional[int] = Query(0, ge=0)
):
    """
    Listar todos los usuarios del sistema.
    Solo accesible por super_admin.
    
    Requiere permiso: manage:users
    """
    # Verificar permiso
    if "manage:users" not in current_user.get('permissions', []):
        raise HTTPException(status_code=403, detail="Permiso denegado")
    
    try:
        db = get_firestore_client()
        
        # Obtener usuarios con paginación
        query = db.collection(FIREBASE_COLLECTIONS["users"]).limit(limit).offset(offset)
        users_ref = query.stream()
        
        users = []
        for user_doc in users_ref:
            user_data = user_doc.to_dict()
            user_data['uid'] = user_doc.id
            
            # Sanitizar datos sensibles
            sanitized = sanitize_user_data(user_data)
            users.append(sanitized)
        
        # Contar total de usuarios
        total_count = len(list(db.collection(FIREBASE_COLLECTIONS["users"]).stream()))
        
        return {
            "success": True,
            "data": users,
            "count": len(users),
            "total": total_count,
            "limit": limit,
            "offset": offset
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error obteniendo usuarios: {str(e)}")


@router.get("/users/{uid}", response_model=dict)
async def get_user_details(
    uid: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Obtener detalles de un usuario específico.
    Solo accesible por super_admin.
    
    Requiere permiso: manage:users
    """
    if "manage:users" not in current_user.get('permissions', []):
        raise HTTPException(status_code=403, detail="Permiso denegado")
    
    try:
        db = get_firestore_client()
        user_doc = db.collection(FIREBASE_COLLECTIONS["users"]).document(uid).get()
        
        if not user_doc.exists:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")
        
        user_data = user_doc.to_dict()
        user_data['uid'] = uid
        
        # Sanitizar datos
        sanitized = sanitize_user_data(user_data)
        
        return {
            "success": True,
            "data": sanitized
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error obteniendo usuario: {str(e)}")


@router.post("/users/{uid}/roles", response_model=dict)
async def assign_roles_to_user(
    uid: str,
    request: AssignRolesRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Asignar roles a un usuario.
    Solo accesible por super_admin.
    
    Requiere permiso: manage:users
    """
    if "manage:users" not in current_user.get('permissions', []):
        raise HTTPException(status_code=403, detail="Permiso denegado")
    
    # Validar asignación de roles
    if not validate_role_assignment(current_user['uid'], uid, request.roles):
        raise HTTPException(
            status_code=403,
            detail="No puedes asignarte el rol super_admin a ti mismo"
        )
    
    try:
        db = get_firestore_client()
        user_ref = db.collection(FIREBASE_COLLECTIONS["users"]).document(uid)
        user_doc = user_ref.get()
        
        if not user_doc.exists:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")
        
        # Validar que los roles existen
        for role in request.roles:
            if role not in ROLES:
                raise HTTPException(status_code=400, detail=f"El rol '{role}' no existe")
        
        # Obtener roles anteriores
        old_roles = user_doc.to_dict().get('roles', [])
        
        # Actualizar roles
        user_ref.update({
            'roles': request.roles,
            'updated_at': datetime.now(timezone.utc),
            'updated_by': current_user['uid']
        })
        
        # Registrar en audit_logs
        db.collection(FIREBASE_COLLECTIONS["audit_logs"]).add({
            'timestamp': datetime.now(timezone.utc),
            'action': 'assign_roles',
            'user_uid': current_user['uid'],
            'user_email': current_user.get('email'),
            'target_user_uid': uid,
            'old_roles': old_roles,
            'new_roles': request.roles,
            'reason': request.reason
        })
        
        return {
            "success": True,
            "message": f"Roles asignados exitosamente a {uid}",
            "roles": request.roles,
            "previous_roles": old_roles
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error asignando roles: {str(e)}")


@router.post("/users/{uid}/temporary-permissions", response_model=dict)
async def grant_temporary_permission(
    uid: str,
    request: GrantTemporaryPermissionRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Otorgar permiso temporal a un usuario.
    Solo accesible por super_admin.
    
    Requiere permiso: manage:users
    """
    if "manage:users" not in current_user.get('permissions', []):
        raise HTTPException(status_code=403, detail="Permiso denegado")
    
    try:
        db = get_firestore_client()
        user_ref = db.collection(FIREBASE_COLLECTIONS["users"]).document(uid)
        user_doc = user_ref.get()
        
        if not user_doc.exists:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")
        
        user_data = user_doc.to_dict()
        temp_perms = user_data.get('temporary_permissions', [])
        
        # Agregar nuevo permiso temporal
        temp_perms.append({
            'permission': request.permission,
            'expires_at': request.expires_at,
            'granted_by': current_user['uid'],
            'granted_at': datetime.now(timezone.utc),
            'reason': request.reason
        })
        
        user_ref.update({
            'temporary_permissions': temp_perms,
            'updated_at': datetime.now(timezone.utc)
        })
        
        # Registrar en audit_logs
        db.collection(FIREBASE_COLLECTIONS["audit_logs"]).add({
            'timestamp': datetime.now(timezone.utc),
            'action': 'grant_temporary_permission',
            'user_uid': current_user['uid'],
            'target_user_uid': uid,
            'permission': request.permission,
            'expires_at': request.expires_at,
            'reason': request.reason
        })
        
        return {
            "success": True,
            "message": "Permiso temporal otorgado",
            "permission": request.permission,
            "expires_at": request.expires_at.isoformat()
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error otorgando permiso: {str(e)}")


@router.delete("/users/{uid}/temporary-permissions/{permission}", response_model=dict)
async def revoke_temporary_permission(
    uid: str,
    permission: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Revocar un permiso temporal de un usuario.
    Solo accesible por super_admin.
    
    Requiere permiso: manage:users
    """
    if "manage:users" not in current_user.get('permissions', []):
        raise HTTPException(status_code=403, detail="Permiso denegado")
    
    try:
        db = get_firestore_client()
        user_ref = db.collection(FIREBASE_COLLECTIONS["users"]).document(uid)
        user_doc = user_ref.get()
        
        if not user_doc.exists:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")
        
        user_data = user_doc.to_dict()
        temp_perms = user_data.get('temporary_permissions', [])
        
        # Filtrar el permiso a revocar
        updated_perms = [p for p in temp_perms if p['permission'] != permission]
        
        if len(updated_perms) == len(temp_perms):
            raise HTTPException(status_code=404, detail="Permiso temporal no encontrado")
        
        user_ref.update({
            'temporary_permissions': updated_perms,
            'updated_at': datetime.now(timezone.utc)
        })
        
        return {
            "success": True,
            "message": f"Permiso temporal '{permission}' revocado"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error revocando permiso: {str(e)}")


# ========== GESTIÓN DE ROLES ==========

@router.get("/roles", response_model=dict)
async def list_roles(
    current_user: dict = Depends(get_current_user)
):
    """
    Listar todos los roles disponibles.
    Accesible por admin_general y super_admin.
    
    Requiere permiso: manage:roles
    """
    if "manage:roles" not in current_user.get('permissions', []):
        raise HTTPException(status_code=403, detail="Permiso denegado")
    
    try:
        roles_list = []
        for role_id, role_data in ROLES.items():
            roles_list.append({
                "role_id": role_id,
                "name": role_data["name"],
                "level": role_data["level"],
                "description": role_data["description"],
                "permissions_count": len(role_data["permissions"])
            })
        
        # Ordenar por nivel
        roles_list.sort(key=lambda x: x["level"])
        
        return {
            "success": True,
            "data": roles_list,
            "count": len(roles_list)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error obteniendo roles: {str(e)}")


@router.get("/roles/{role_id}", response_model=dict)
async def get_role_details(
    role_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Obtener detalles de un rol específico.
    Accesible por admin_general y super_admin.
    
    Requiere permiso: manage:roles
    """
    if "manage:roles" not in current_user.get('permissions', []):
        raise HTTPException(status_code=403, detail="Permiso denegado")
    
    if role_id not in ROLES:
        raise HTTPException(status_code=404, detail="Rol no encontrado")
    
    role_data = ROLES[role_id]
    
    return {
        "success": True,
        "data": {
            "role_id": role_id,
            "name": role_data["name"],
            "level": role_data["level"],
            "description": role_data["description"],
            "permissions": role_data["permissions"]
        }
    }


# ========== AUDITORÍA ==========

@router.get("/audit-logs", response_model=dict)
async def get_audit_logs(
    current_user: dict = Depends(get_current_user),
    limit: int = Query(100, ge=1, le=500),
    user_uid: Optional[str] = None,
    action: Optional[str] = None
):
    """
    Obtener logs de auditoría.
    Accesible por admin_general y super_admin.
    
    Requiere permiso: view:audit_logs
    """
    if "view:audit_logs" not in current_user.get('permissions', []):
        raise HTTPException(status_code=403, detail="Permiso denegado")
    
    try:
        db = get_firestore_client()
        query = db.collection(FIREBASE_COLLECTIONS["audit_logs"]).order_by(
            'timestamp', direction='DESCENDING'
        ).limit(limit)
        
        # Aplicar filtros opcionales
        if user_uid:
            query = query.where('user_uid', '==', user_uid)
        if action:
            query = query.where('action', '==', action)
        
        logs = []
        for log_doc in query.stream():
            log_data = log_doc.to_dict()
            log_data['log_id'] = log_doc.id
            
            # Convertir timestamp
            if 'timestamp' in log_data and hasattr(log_data['timestamp'], 'isoformat'):
                log_data['timestamp'] = log_data['timestamp'].isoformat()
            
            logs.append(log_data)
        
        return {
            "success": True,
            "data": logs,
            "count": len(logs),
            "limit": limit
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error obteniendo logs: {str(e)}")


# ========== INFORMACIÓN DEL SISTEMA ==========

@router.get("/system/stats", response_model=dict)
async def get_system_stats(
    current_user: dict = Depends(get_current_user)
):
    """
    Obtener estadísticas del sistema de autorización.
    Accesible por super_admin.
    
    Requiere permiso: manage:users
    """
    if "manage:users" not in current_user.get('permissions', []):
        raise HTTPException(status_code=403, detail="Permiso denegado")
    
    try:
        db = get_firestore_client()
        
        # Contar usuarios
        users_count = len(list(db.collection(FIREBASE_COLLECTIONS["users"]).stream()))
        
        # Contar por rol
        users_by_role = {}
        for user_doc in db.collection(FIREBASE_COLLECTIONS["users"]).stream():
            user_data = user_doc.to_dict()
            roles = user_data.get('roles', [])
            for role in roles:
                users_by_role[role] = users_by_role.get(role, 0) + 1
        
        # Contar logs de auditoría
        logs_count = len(list(db.collection(FIREBASE_COLLECTIONS["audit_logs"]).stream()))
        
        return {
            "success": True,
            "data": {
                "total_users": users_count,
                "total_roles": len(ROLES),
                "users_by_role": users_by_role,
                "total_audit_logs": logs_count,
                "default_role": DEFAULT_USER_ROLE
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error obteniendo estadísticas: {str(e)}")

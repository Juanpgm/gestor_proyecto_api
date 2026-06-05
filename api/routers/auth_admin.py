"""
Router de Administración de Usuarios, Roles y Permisos
Endpoints para gestión completa del sistema de autorización
"""

import asyncio
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional, List
from datetime import datetime, timezone

from auth_system.decorators import require_permission, require_role, get_current_user
from auth_system.permissions import get_user_permissions
from auth_system.models import (
    AssignRolesRequest,
    GrantTemporaryPermissionRequest,
    UserResponse,
    RoleDetails,
    StandardAuthResponse,
    UpdateUserRequest,
)
from auth_system.constants import ROLES, FIREBASE_COLLECTIONS, DEFAULT_USER_ROLE
from auth_system.utils import validate_role_assignment, sanitize_user_data
from database.firebase_config import get_firestore_client

router = APIRouter(prefix="/auth/admin", tags=["Administración y Control de Accesos"])


def _has_any_permission(current_user: dict, permissions: List[str]) -> bool:
    user_permissions = current_user.get("permissions", [])
    if not isinstance(user_permissions, list):
        return False
    if "*" in user_permissions:
        return True
    return any(permission in user_permissions for permission in permissions)


def _get_db_or_raise():
    db = get_firestore_client()
    if db is None:
        raise HTTPException(status_code=503, detail="No se pudo conectar a Firestore")
    return db


def _normalize_roles(raw_roles) -> List[str]:
    if raw_roles is None:
        return []
    if isinstance(raw_roles, str):
        role = raw_roles.strip()
        return [role] if role else []
    if isinstance(raw_roles, (list, tuple, set)):
        normalized_roles: List[str] = []
        for role in raw_roles:
            role_str = str(role).strip()
            if role_str:
                normalized_roles.append(role_str)
        return normalized_roles
    role = str(raw_roles).strip()
    return [role] if role else []


def _build_user_roles_payload(user_uid: str, user_data: dict, db) -> dict:
    user_roles = _normalize_roles(user_data.get("roles", []))
    user_permissions = get_user_permissions(user_uid, db)
    role_details = []
    for role_id in user_roles:
        if role_id in ROLES:
            role_details.append(
                {
                    "role_id": role_id,
                    "name": ROLES[role_id]["name"],
                    "level": ROLES[role_id]["level"],
                    "description": ROLES[role_id]["description"],
                    "permissions": ROLES[role_id]["permissions"],
                }
            )

    role_details.sort(key=lambda x: x["level"])

    return {
        "uid": user_uid,
        "roles": user_roles,
        "roles_count": len(user_roles),
        "permissions": user_permissions,
        "permissions_count": len(user_permissions),
        "role_details": role_details,
    }


def _extract_single_role(role: str) -> str:
    normalized_roles = _normalize_roles(role)
    if len(normalized_roles) == 0:
        raise HTTPException(status_code=400, detail="Debe proporcionar un rol")
    return normalized_roles[0]


# ========== GESTIÓN DE USUARIOS ==========


@router.get("/users", response_model=dict)
async def list_users(
    current_user: dict = Depends(get_current_user),
    limit: Optional[int] = Query(100, ge=1, le=500),
    offset: Optional[int] = Query(0, ge=0),
):
    """
    Listar todos los usuarios del sistema.
    Solo accesible por super_admin.

    Requiere permiso: manage:users
    """
    # Verificar permiso
    if not _has_any_permission(current_user, ["manage:users"]):
        raise HTTPException(status_code=403, detail="Permiso denegado")

    try:
        db = _get_db_or_raise()

        # Obtener usuarios con paginación
        query = db.collection(FIREBASE_COLLECTIONS["users"]).limit(limit).offset(offset)
        users_ref = query.stream()

        users = []
        for user_doc in users_ref:
            user_data = user_doc.to_dict()
            user_data["uid"] = user_doc.id

            # Sanitizar datos sensibles
            sanitized = sanitize_user_data(user_data)
            users.append(sanitized)

        # Contar total de usuarios (aggregation query to avoid loading all docs)
        try:
            count_query = db.collection(FIREBASE_COLLECTIONS["users"]).count()
            count_result = count_query.get()
            total_count = count_result[0][0].value if count_result else 0
        except Exception:
            # Fallback: use offset + current page size as estimate
            total_count = offset + len(users)

        return {
            "success": True,
            "data": users,
            "count": len(users),
            "total": total_count,
            "limit": limit,
            "offset": offset,
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error obteniendo usuarios: {str(e)}"
        )


@router.get("/users/super-admins", response_model=dict)
async def list_super_admin_users(
    current_user: dict = Depends(get_current_user),
    limit: Optional[int] = Query(100, ge=1, le=500),
    offset: Optional[int] = Query(0, ge=0),
):
    """
    Listar todos los usuarios con rol super_admin.
    Requiere permisos de gestión o lectura de usuarios.
    """
    if not _has_any_permission(current_user, ["manage:users", "view:users"]):
        raise HTTPException(status_code=403, detail="Permiso denegado")

    try:
        db = _get_db_or_raise()
        users_collection = db.collection(FIREBASE_COLLECTIONS["users"])
        query = users_collection.where("roles", "array_contains", "super_admin")
        users_ref = query.stream()

        all_super_admins = []
        for user_doc in users_ref:
            user_data = user_doc.to_dict() or {}
            user_data["uid"] = user_doc.id

            sanitized = sanitize_user_data(user_data)
            all_super_admins.append(sanitized)

        # Aplicar paginación manual
        total_count = len(all_super_admins)
        paginated_users = all_super_admins[offset : offset + limit]

        return {
            "success": True,
            "data": paginated_users,
            "count": len(paginated_users),
            "total": total_count,
            "limit": limit,
            "offset": offset,
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error obteniendo super admins: {str(e)}"
        )


@router.get("/users/{uid}", response_model=dict)
async def get_user_details(uid: str, current_user: dict = Depends(get_current_user)):
    """
    Obtener detalles de un usuario específico.
    Solo accesible por super_admin.

    Requiere permiso: manage:users
    """
    if not _has_any_permission(current_user, ["manage:users"]):
        raise HTTPException(status_code=403, detail="Permiso denegado")

    try:
        db = get_firestore_client()
        user_doc = db.collection(FIREBASE_COLLECTIONS["users"]).document(uid).get()

        if not user_doc.exists:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")

        user_data = user_doc.to_dict()
        user_data["uid"] = uid

        # Sanitizar datos
        sanitized = sanitize_user_data(user_data)

        return {"success": True, "data": sanitized}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error obteniendo usuario: {str(e)}"
        )


@router.put("/users/{uid}", response_model=dict)
async def update_user_info(
    uid: str, request: UpdateUserRequest, current_user: dict = Depends(get_current_user)
):
    """
    Actualizar información de un usuario existente.
    Permite llenar variables vacías o modificar existentes.
    Solo accesible por super_admin.

    Requiere permiso: manage:users

    Campos actualizables:
    - full_name: Nombre completo del usuario
    - phone_number: Número de teléfono
    - centro_gestor_assigned: Centro gestor asignado
    - email_verified: Estado de verificación de email
    - phone_verified: Estado de verificación de teléfono
    - is_active: Estado activo del usuario
    """
    if not _has_any_permission(current_user, ["manage:users"]):
        raise HTTPException(status_code=403, detail="Permiso denegado")

    try:
        db = get_firestore_client()
        user_ref = db.collection(FIREBASE_COLLECTIONS["users"]).document(uid)
        user_doc = user_ref.get()

        if not user_doc.exists:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")

        # Obtener datos actuales
        current_data = user_doc.to_dict()

        # Preparar campos a actualizar (solo los que se enviaron)
        update_fields = {}
        changes_log = {}

        if request.full_name is not None:
            update_fields["full_name"] = request.full_name
            changes_log["full_name"] = {
                "old": current_data.get("full_name"),
                "new": request.full_name,
            }

        if request.phone_number is not None:
            update_fields["phone_number"] = request.phone_number
            changes_log["phone_number"] = {
                "old": current_data.get("phone_number"),
                "new": request.phone_number,
            }

        if request.centro_gestor_assigned is not None:
            update_fields["centro_gestor_assigned"] = request.centro_gestor_assigned
            changes_log["centro_gestor_assigned"] = {
                "old": current_data.get("centro_gestor_assigned"),
                "new": request.centro_gestor_assigned,
            }

        if request.email_verified is not None:
            update_fields["email_verified"] = request.email_verified
            changes_log["email_verified"] = {
                "old": current_data.get("email_verified"),
                "new": request.email_verified,
            }

        if request.phone_verified is not None:
            update_fields["phone_verified"] = request.phone_verified
            changes_log["phone_verified"] = {
                "old": current_data.get("phone_verified"),
                "new": request.phone_verified,
            }

        if request.is_active is not None:
            update_fields["is_active"] = request.is_active
            changes_log["is_active"] = {
                "old": current_data.get("is_active"),
                "new": request.is_active,
            }

        # Verificar que haya campos para actualizar
        if not update_fields:
            raise HTTPException(
                status_code=400, detail="No se proporcionaron campos para actualizar"
            )

        # Agregar metadata de actualización
        update_fields["updated_at"] = datetime.now(timezone.utc)
        update_fields["updated_by"] = current_user.get("uid")

        # Actualizar en Firestore
        user_ref.update(update_fields)

        # Registrar en audit_logs
        db.collection(FIREBASE_COLLECTIONS["audit_logs"]).add(
            {
                "timestamp": datetime.now(timezone.utc),
                "action": "update_user_info",
                "user_uid": current_user.get("uid"),
                "user_email": current_user.get("email"),
                "target_user_uid": uid,
                "target_user_email": current_data.get("email"),
                "changes": changes_log,
            }
        )

        # Obtener datos actualizados
        updated_doc = user_ref.get()
        updated_data = updated_doc.to_dict()
        updated_data["uid"] = uid

        return {
            "success": True,
            "message": f"Usuario {uid} actualizado exitosamente",
            "data": sanitize_user_data(updated_data),
            "changes": changes_log,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error actualizando usuario: {str(e)}"
        )


@router.post("/users/{uid}/roles", response_model=dict)
async def assign_roles_to_user(
    uid: str,
    request: AssignRolesRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    Asignar roles a un usuario.
    Solo accesible por super_admin.

    Requiere permiso: manage:users
    """
    if not _has_any_permission(current_user, ["manage:users"]):
        raise HTTPException(status_code=403, detail="Permiso denegado")

    single_role = _extract_single_role(request.role)

    # Validar asignación de roles
    if not validate_role_assignment(current_user.get("uid", ""), uid, [single_role]):
        raise HTTPException(
            status_code=403, detail="No puedes asignarte el rol super_admin a ti mismo"
        )

    try:
        db = get_firestore_client()
        user_ref = db.collection(FIREBASE_COLLECTIONS["users"]).document(uid)
        user_doc = user_ref.get()

        if not user_doc.exists:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")

        # Validar que el rol existe
        if single_role not in ROLES:
            raise HTTPException(
                status_code=400, detail=f"El rol '{single_role}' no existe"
            )

        # Obtener roles anteriores
        old_roles = _normalize_roles(user_doc.to_dict().get("roles", []))

        # Actualizar roles (siempre lista para consistencia)
        user_ref.update(
            {
                "roles": [single_role],
                "updated_at": datetime.now(timezone.utc),
                "updated_by": current_user.get("uid"),
            }
        )

        # Sincronizar custom claims en Firebase Auth (best-effort)
        try:
            from firebase_admin import auth as fb_auth

            existing_claims = {}
            try:
                existing_claims = fb_auth.get_user(uid).custom_claims or {}
            except Exception:
                existing_claims = {}
            existing_claims.update({"role": single_role, "roles": [single_role]})
            fb_auth.set_custom_user_claims(uid, existing_claims)
        except Exception:
            pass

        # Registrar en audit_logs
        db.collection(FIREBASE_COLLECTIONS["audit_logs"]).add(
            {
                "timestamp": datetime.now(timezone.utc),
                "action": "assign_roles",
                "user_uid": current_user.get("uid"),
                "user_email": current_user.get("email"),
                "target_user_uid": uid,
                "old_roles": old_roles,
                "new_roles": [single_role],
                "reason": request.reason,
            }
        )

        return {
            "success": True,
            "message": f"Roles asignados exitosamente a {uid}",
            "role": single_role,
            "previous_roles": old_roles,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error asignando roles: {str(e)}")


@router.put("/change_users_rol/{uid}", response_model=dict)
async def change_users_role_by_uid(
    uid: str,
    request: AssignRolesRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    Cambiar la variable `roles` en la colección `users` de Firebase usando `uid`.

    Requiere permiso: manage:users
    """
    if not _has_any_permission(current_user, ["manage:users"]):
        raise HTTPException(status_code=403, detail="Permiso denegado")

    single_role = _extract_single_role(request.role)

    if not validate_role_assignment(current_user.get("uid", ""), uid, [single_role]):
        raise HTTPException(
            status_code=403, detail="No puedes asignarte el rol super_admin a ti mismo"
        )

    try:
        db = _get_db_or_raise()
        user_ref = db.collection(FIREBASE_COLLECTIONS["users"]).document(uid)
        user_doc = user_ref.get()

        if not user_doc.exists:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")

        if single_role not in ROLES:
            raise HTTPException(
                status_code=400, detail=f"El rol '{single_role}' no existe"
            )

        old_roles = _normalize_roles(user_doc.to_dict().get("roles", []))

        user_ref.update(
            {
                "roles": [single_role],
                "updated_at": datetime.now(timezone.utc),
                "updated_by": current_user.get("uid"),
            }
        )

        # Sincronizar custom claims en Firebase Auth (best-effort)
        try:
            from firebase_admin import auth as fb_auth

            existing_claims = {}
            try:
                existing_claims = fb_auth.get_user(uid).custom_claims or {}
            except Exception:
                existing_claims = {}
            existing_claims.update({"role": single_role, "roles": [single_role]})
            fb_auth.set_custom_user_claims(uid, existing_claims)
        except Exception:
            pass

        db.collection(FIREBASE_COLLECTIONS["audit_logs"]).add(
            {
                "timestamp": datetime.now(timezone.utc),
                "action": "change_users_rol",
                "user_uid": current_user.get("uid"),
                "user_email": current_user.get("email"),
                "target_user_uid": uid,
                "old_roles": old_roles,
                "new_roles": [single_role],
                "reason": request.reason,
            }
        )

        return {
            "success": True,
            "message": f"Roles actualizados exitosamente para {uid}",
            "uid": uid,
            "collection": FIREBASE_COLLECTIONS["users"],
            "role": single_role,
            "previous_roles": old_roles,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error actualizando roles del usuario: {str(e)}"
        )


@router.put("/users/{uid}/centro-gestor", response_model=dict)
async def update_user_centro_gestor(
    uid: str, request: dict, current_user: dict = Depends(get_current_user)
):
    """
    Actualizar el centro gestor asignado a un usuario.
    Requiere permiso: manage:users

    Body:
        { "centro_gestor_assigned": "<nombre>", "reason": "<opcional>" }
    """
    if not _has_any_permission(current_user, ["manage:users"]):
        raise HTTPException(status_code=403, detail="Permiso denegado")

    centro = (request or {}).get("centro_gestor_assigned")
    if centro is not None:
        centro = str(centro).strip()
    if not centro:
        raise HTTPException(
            status_code=400, detail="centro_gestor_assigned es requerido"
        )

    try:
        db = get_firestore_client()
        user_ref = db.collection(FIREBASE_COLLECTIONS["users"]).document(uid)
        user_doc = user_ref.get()
        if not user_doc.exists:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")

        old_data = user_doc.to_dict() or {}
        old_centro = old_data.get("centro_gestor_assigned") or old_data.get(
            "nombre_centro_gestor"
        )

        user_ref.update(
            {
                "centro_gestor_assigned": centro,
                "nombre_centro_gestor": centro,  # compatibilidad con consumidores antiguos
                "updated_at": datetime.now(timezone.utc),
                "updated_by": current_user.get("uid"),
            }
        )

        # Sincronizar custom claims (best-effort)
        try:
            from firebase_admin import auth as fb_auth

            existing_claims = {}
            try:
                existing_claims = fb_auth.get_user(uid).custom_claims or {}
            except Exception:
                existing_claims = {}
            existing_claims["centro_gestor"] = centro
            fb_auth.set_custom_user_claims(uid, existing_claims)
        except Exception:
            pass

        db.collection(FIREBASE_COLLECTIONS["audit_logs"]).add(
            {
                "timestamp": datetime.now(timezone.utc),
                "action": "update_centro_gestor",
                "user_uid": current_user.get("uid"),
                "user_email": current_user.get("email"),
                "target_user_uid": uid,
                "old_centro_gestor": old_centro,
                "new_centro_gestor": centro,
                "reason": (request or {}).get("reason"),
            }
        )

        updated = user_ref.get().to_dict() or {}
        updated["uid"] = uid
        return {
            "success": True,
            "message": "Centro gestor actualizado exitosamente",
            "user": sanitize_user_data(updated),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error actualizando centro gestor: {str(e)}"
        )


@router.post("/users/{uid}/temporary-permissions", response_model=dict)
async def grant_temporary_permission(
    uid: str,
    request: GrantTemporaryPermissionRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    Otorgar permiso temporal a un usuario.
    Solo accesible por super_admin.

    Requiere permiso: manage:users
    """
    if not _has_any_permission(current_user, ["manage:users"]):
        raise HTTPException(status_code=403, detail="Permiso denegado")

    try:
        db = get_firestore_client()
        user_ref = db.collection(FIREBASE_COLLECTIONS["users"]).document(uid)
        user_doc = user_ref.get()

        if not user_doc.exists:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")

        user_data = user_doc.to_dict()
        temp_perms = user_data.get("temporary_permissions", [])

        # Agregar nuevo permiso temporal
        temp_perms.append(
            {
                "permission": request.permission,
                "expires_at": request.expires_at,
                "granted_by": current_user.get("uid"),
                "granted_at": datetime.now(timezone.utc),
                "reason": request.reason,
            }
        )

        user_ref.update(
            {
                "temporary_permissions": temp_perms,
                "updated_at": datetime.now(timezone.utc),
            }
        )

        # Registrar en audit_logs
        db.collection(FIREBASE_COLLECTIONS["audit_logs"]).add(
            {
                "timestamp": datetime.now(timezone.utc),
                "action": "grant_temporary_permission",
                "user_uid": current_user.get("uid"),
                "target_user_uid": uid,
                "permission": request.permission,
                "expires_at": request.expires_at,
                "reason": request.reason,
            }
        )

        return {
            "success": True,
            "message": "Permiso temporal otorgado",
            "permission": request.permission,
            "expires_at": request.expires_at.isoformat(),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error otorgando permiso: {str(e)}"
        )


@router.delete("/users/{uid}/temporary-permissions/{permission}", response_model=dict)
async def revoke_temporary_permission(
    uid: str, permission: str, current_user: dict = Depends(get_current_user)
):
    """
    Revocar un permiso temporal de un usuario.
    Solo accesible por super_admin.

    Requiere permiso: manage:users
    """
    if not _has_any_permission(current_user, ["manage:users"]):
        raise HTTPException(status_code=403, detail="Permiso denegado")

    try:
        db = get_firestore_client()
        user_ref = db.collection(FIREBASE_COLLECTIONS["users"]).document(uid)
        user_doc = user_ref.get()

        if not user_doc.exists:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")

        user_data = user_doc.to_dict()
        temp_perms = user_data.get("temporary_permissions", [])

        # Filtrar el permiso a revocar
        updated_perms = [p for p in temp_perms if p.get("permission") != permission]

        if len(updated_perms) == len(temp_perms):
            raise HTTPException(
                status_code=404, detail="Permiso temporal no encontrado"
            )

        user_ref.update(
            {
                "temporary_permissions": updated_perms,
                "updated_at": datetime.now(timezone.utc),
            }
        )

        return {"success": True, "message": f"Permiso temporal '{permission}' revocado"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error revocando permiso: {str(e)}"
        )


# ========== GESTIÓN DE ROLES ==========


@router.get("/roles", response_model=dict)
async def list_roles(
    uid: Optional[str] = Query(
        None,
        description="UID del usuario a consultar. Si no se envía, retorna roles/permisos de todos los usuarios",
    ),
    include_usage: bool = Query(
        False,
        description="Incluir conteo de usuarios por rol (requiere scan completo de Firestore, lento)",
    ),
    current_user: dict = Depends(get_current_user),
):
    """
    Listar todos los roles disponibles.
    Accesible por admin_general y super_admin.

    Requiere permiso: manage:roles
    """
    if not _has_any_permission(current_user, ["manage:roles", "view:roles"]):
        raise HTTPException(status_code=403, detail="Permiso denegado")

    try:
        db = _get_db_or_raise()
        users_collection_name = FIREBASE_COLLECTIONS["users"]
        loop = asyncio.get_event_loop()

        # Build catalog from in-memory ROLES constant (no Firestore needed)
        def _build_catalog(usage: dict) -> list:
            catalog = []
            for role_id, role_data in ROLES.items():
                catalog.append(
                    {
                        "role_id": role_id,
                        "name": role_data["name"],
                        "level": role_data["level"],
                        "description": role_data["description"],
                        "permissions": role_data["permissions"],
                        "permissions_count": len(role_data["permissions"]),
                        "assigned_users": usage.get(role_id, 0),
                    }
                )
            catalog.sort(key=lambda x: x["level"])
            return catalog

        # --- Single user path (fast: one doc fetch) ---
        if uid:
            target_uid = current_user.get("uid") if uid == "me" else uid
            user_doc = await loop.run_in_executor(
                None,
                lambda: db.collection(users_collection_name).document(target_uid).get(),
            )
            if not user_doc.exists:
                raise HTTPException(status_code=404, detail="Usuario no encontrado")
            user_payload = _build_user_roles_payload(
                target_uid, user_doc.to_dict() or {}, db
            )
            roles_list = _build_catalog({})
            return {
                "success": True,
                "data": user_payload,
                "count": 1,
                "scope": "single_user",
                "requested_uid": target_uid,
                "connected_uid": current_user.get("uid"),
                "roles_catalog": roles_list,
            }

        # --- Catalog-only path (fast: no Firestore scan) ---
        if not include_usage:
            roles_list = _build_catalog({})
            return {
                "success": True,
                "data": roles_list,
                "count": len(roles_list),
                "scope": "catalog_only",
                "connected_uid": current_user.get("uid"),
                "roles_catalog": roles_list,
            }

        # --- Full scan path (slow, only when include_usage=True) ---
        def _scan_users():
            docs = list(db.collection(users_collection_name).stream())
            usage = {role_id: 0 for role_id in ROLES.keys()}
            unknown = {}
            payloads = []
            for doc in docs:
                data = doc.to_dict() or {}
                for role in _normalize_roles(data.get("roles", [])):
                    role_str = str(role)
                    if role_str in usage:
                        usage[role_str] += 1
                    else:
                        unknown[role_str] = unknown.get(role_str, 0) + 1
                payloads.append(_build_user_roles_payload(doc.id, data, db))
            return docs, usage, unknown, payloads

        users_docs, roles_usage, unknown_roles, users_roles_permissions = (
            await loop.run_in_executor(None, _scan_users)
        )
        roles_list = _build_catalog(roles_usage)

        return {
            "success": True,
            "data": users_roles_permissions,
            "count": len(users_roles_permissions),
            "scope": "all_users",
            "connected_uid": current_user.get("uid"),
            "roles_catalog": roles_list,
            "verification": {
                "users_collection": users_collection_name,
                "users_scanned": len(users_docs),
                "roles_detected_in_users": len(
                    [r for r, c in roles_usage.items() if c > 0]
                ),
                "unknown_roles_in_users": unknown_roles,
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error obteniendo roles: {str(e)}")


@router.get("/roles/{role_id}", response_model=dict)
async def get_role_details(
    role_id: str,
    uid: Optional[str] = Query(
        None,
        description="UID del usuario a validar para este rol. Si no se envía, retorna usuarios asignados al rol con sus permisos",
    ),
    current_user: dict = Depends(get_current_user),
):
    """
    Obtener detalles de un rol específico.
    Accesible por admin_general y super_admin.

    Requiere permiso: manage:roles
    """
    if not _has_any_permission(current_user, ["manage:roles", "view:roles"]):
        raise HTTPException(status_code=403, detail="Permiso denegado")

    if role_id not in ROLES:
        raise HTTPException(status_code=404, detail="Rol no encontrado")

    try:
        db = _get_db_or_raise()
        users_docs = list(db.collection(FIREBASE_COLLECTIONS["users"]).stream())
        users_with_role = []

        for user_doc in users_docs:
            user_data = user_doc.to_dict() or {}
            user_roles = _normalize_roles(user_data.get("roles", []))
            if role_id in user_roles:
                users_with_role.append(
                    _build_user_roles_payload(user_doc.id, user_data, db)
                )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error verificando rol en users: {str(e)}"
        )

    role_data = ROLES[role_id]
    role_details_data = {
        "role_id": role_id,
        "name": role_data["name"],
        "level": role_data["level"],
        "description": role_data["description"],
        "permissions": role_data["permissions"],
        "permissions_count": len(role_data["permissions"]),
        "assigned_users": len(users_with_role),
        "users_collection": FIREBASE_COLLECTIONS["users"],
    }

    if uid:
        target_uid = current_user.get("uid") if uid == "me" else uid
        target_doc = (
            db.collection(FIREBASE_COLLECTIONS["users"]).document(target_uid).get()
        )
        if not target_doc.exists:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")

        target_data = target_doc.to_dict() or {}
        target_roles = _normalize_roles(target_data.get("roles", []))

        return {
            "success": True,
            "data": role_details_data,
            "scope": "single_user",
            "requested_uid": target_uid,
            "connected_uid": current_user.get("uid"),
            "user_has_role": role_id in target_roles,
            "user_permissions": get_user_permissions(target_uid, db),
            "user_roles": target_roles,
        }

    return {
        "success": True,
        "data": role_details_data,
        "scope": "all_assigned_users",
        "connected_uid": current_user.get("uid"),
        "assigned_users_details": users_with_role,
        "count": len(users_with_role),
    }


# ========== AUDITORÍA ==========


@router.get("/audit-logs", response_model=dict)
async def get_audit_logs(
    current_user: dict = Depends(get_current_user),
    limit: int = Query(100, ge=1, le=500),
    user_uid: Optional[str] = None,
    action: Optional[str] = None,
):
    """
    Obtener logs de auditoría.
    Accesible por admin_general y super_admin.

    Requiere permiso: view:audit_logs
    """
    if not _has_any_permission(current_user, ["view:audit_logs"]):
        raise HTTPException(status_code=403, detail="Permiso denegado")

    try:
        db = _get_db_or_raise()
        query = db.collection(FIREBASE_COLLECTIONS["audit_logs"])

        # Aplicar filtros opcionales
        if user_uid:
            query = query.where("user_uid", "==", user_uid)
        if action:
            query = query.where("action", "==", action)

        query = query.order_by("timestamp", direction="DESCENDING").limit(limit)

        logs = []
        for log_doc in query.stream():
            log_data = log_doc.to_dict()
            log_data["log_id"] = log_doc.id

            # Convertir timestamp
            if "timestamp" in log_data and hasattr(log_data["timestamp"], "isoformat"):
                log_data["timestamp"] = log_data["timestamp"].isoformat()

            if "granted_at" in log_data and hasattr(
                log_data["granted_at"], "isoformat"
            ):
                log_data["granted_at"] = log_data["granted_at"].isoformat()

            if "expires_at" in log_data and hasattr(
                log_data["expires_at"], "isoformat"
            ):
                log_data["expires_at"] = log_data["expires_at"].isoformat()

            logs.append(log_data)

        return {"success": True, "data": logs, "count": len(logs), "limit": limit}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error obteniendo logs: {str(e)}")


# ========== INFORMACIÓN DEL SISTEMA ==========


@router.get("/system/stats", response_model=dict)
async def get_system_stats(
    current_user: dict = Depends(get_current_user),
    include_users: bool = Query(
        False, description="Incluir datos de la colección users en la respuesta"
    ),
    users_limit: int = Query(
        50, ge=1, le=500, description="Límite de usuarios cuando include_users=true"
    ),
    users_offset: int = Query(
        0, ge=0, description="Offset de usuarios cuando include_users=true"
    ),
):
    """
    Obtener estadísticas del sistema de autorización.
    Accesible por super_admin.

    Requiere permiso: manage:users
    """
    if not _has_any_permission(current_user, ["manage:users"]):
        raise HTTPException(status_code=403, detail="Permiso denegado")

    try:
        db = _get_db_or_raise()
        loop = asyncio.get_event_loop()

        # Count total users using aggregation (fast, no full scan)
        async def _get_total_users() -> int:
            try:
                result = await loop.run_in_executor(
                    None,
                    lambda: db.collection(FIREBASE_COLLECTIONS["users"]).count().get(),
                )
                return result[0][0].value if result else 0
            except Exception:
                return 0

        # Count audit logs using aggregation (fast)
        async def _get_total_logs() -> int:
            try:
                result = await loop.run_in_executor(
                    None,
                    lambda: db.collection(FIREBASE_COLLECTIONS["audit_logs"])
                    .count()
                    .get(),
                )
                return result[0][0].value if result else 0
            except Exception:
                return 0

        # Scan all users for role breakdown (slow, run in executor)
        def _scan_users_for_roles(with_data: bool):
            docs = list(db.collection(FIREBASE_COLLECTIONS["users"]).stream())
            by_role = {}
            without_roles = 0
            unknown = {}
            user_data_list = []
            for doc in docs:
                data = doc.to_dict() or {}
                data["uid"] = doc.id
                if with_data:
                    user_data_list.append(sanitize_user_data(data))
                roles = _normalize_roles(data.get("roles", []))
                if not roles:
                    without_roles += 1
                    continue
                for role in roles:
                    role_str = str(role)
                    if role_str in ROLES:
                        by_role[role_str] = by_role.get(role_str, 0) + 1
                    else:
                        unknown[role_str] = unknown.get(role_str, 0) + 1
            return len(docs), by_role, without_roles, unknown, user_data_list

        # Run aggregation queries in parallel, role scan in executor
        total_users_task = asyncio.ensure_future(_get_total_users())
        total_logs_task = asyncio.ensure_future(_get_total_logs())
        role_scan_task = loop.run_in_executor(
            None, _scan_users_for_roles, include_users
        )

        total_users, total_logs, role_scan = await asyncio.gather(
            total_users_task, total_logs_task, role_scan_task
        )
        (
            scanned_count,
            users_by_role,
            users_without_roles,
            unknown_roles,
            users_data_for_response,
        ) = role_scan

        # Use aggregation count as canonical total (more accurate than scan count)
        users_count = total_users if total_users > 0 else scanned_count

        response_data = {
            "total_users": users_count,
            "total_roles": len(ROLES),
            "users_by_role": users_by_role,
            "users_without_roles": users_without_roles,
            "unknown_roles_in_users": unknown_roles,
            "total_audit_logs": total_logs,
            "default_role": DEFAULT_USER_ROLE,
        }

        if include_users:
            paginated_users = users_data_for_response[
                users_offset : users_offset + users_limit
            ]
            response_data["users_collection"] = {
                "collection": FIREBASE_COLLECTIONS["users"],
                "total": users_count,
                "count": len(paginated_users),
                "limit": users_limit,
                "offset": users_offset,
                "data": paginated_users,
            }

        return {"success": True, "data": response_data}
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error obteniendo estadísticas: {str(e)}"
        )

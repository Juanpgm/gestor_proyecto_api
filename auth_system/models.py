"""
Modelos Pydantic para el Sistema de Autenticación y Autorización
"""

from pydantic import BaseModel, Field, field_validator, model_validator
from typing import List, Optional
from datetime import datetime, timezone


class AssignRolesRequest(BaseModel):
    """Request para asignar roles a un usuario"""
    role: Optional[str] = Field(None, description="Rol único activo a asignar")
    roles: Optional[List[str]] = Field(None, description="Compatibilidad legacy: lista con un solo rol")
    reason: Optional[str] = Field(None, description="Razón para el cambio de roles")

    @model_validator(mode='after')
    def normalize_role_payload(self):
        if self.role is not None and self.role.strip():
            self.role = self.role.strip()
            return self

        if self.roles is not None:
            normalized_roles = [str(role).strip() for role in self.roles if str(role).strip()]
            if len(normalized_roles) == 0:
                raise ValueError("Debe proporcionar un rol")
            if len(normalized_roles) > 1:
                raise ValueError("Solo se permite un rol activo por usuario")
            self.role = normalized_roles[0]
            return self

        raise ValueError("Debe proporcionar un rol")
    
    @field_validator('role')
    @classmethod
    def validate_role(cls, v):
        if v is None:
            return v
        role = v.strip() if isinstance(v, str) else ""
        if not role:
            raise ValueError("Debe proporcionar un rol")
        return role


class GrantTemporaryPermissionRequest(BaseModel):
    """Request para otorgar permiso temporal a un usuario"""
    permission: str = Field(..., description="Permiso a otorgar temporalmente")
    expires_at: datetime = Field(..., description="Fecha de expiración del permiso")
    reason: Optional[str] = Field(None, description="Razón para otorgar el permiso temporal")
    
    @field_validator('expires_at')
    @classmethod
    def validate_expiration(cls, v):
        if v <= datetime.now(timezone.utc):
            raise ValueError("La fecha de expiración debe ser futura")
        return v


class UserResponse(BaseModel):
    """Respuesta con información del usuario"""
    uid: str
    email: str
    full_name: str
    roles: List[str]
    permissions: List[str]
    centro_gestor_assigned: Optional[str] = None
    email_verified: bool
    phone_verified: bool
    is_active: bool
    created_at: str
    last_login_at: Optional[str] = None


class RoleDetails(BaseModel):
    """Detalles de un rol"""
    role_id: str
    name: str
    level: int
    description: str
    permissions: List[str]


class AuditLogEntry(BaseModel):
    """Entrada de log de auditoría"""
    log_id: Optional[str] = None
    timestamp: datetime
    action: str
    user_uid: str
    target_user_uid: Optional[str] = None
    endpoint: Optional[str] = None
    method: Optional[str] = None
    status_code: Optional[int] = None
    details: Optional[dict] = None


class StandardAuthResponse(BaseModel):
    """Respuesta estándar para operaciones de autenticación"""
    success: bool
    message: Optional[str] = None
    data: Optional[dict] = None


class UpdateUserRequest(BaseModel):
    """Request para actualizar información de un usuario"""
    full_name: Optional[str] = Field(None, description="Nombre completo del usuario")
    phone_number: Optional[str] = Field(None, description="Número de teléfono")
    centro_gestor_assigned: Optional[str] = Field(None, description="Centro gestor asignado")
    email_verified: Optional[bool] = Field(None, description="Estado de verificación de email")
    phone_verified: Optional[bool] = Field(None, description="Estado de verificación de teléfono")
    is_active: Optional[bool] = Field(None, description="Estado activo del usuario")
    
    @field_validator('full_name')
    @classmethod
    def validate_full_name(cls, v):
        if v is not None and len(v.strip()) < 3:
            raise ValueError("El nombre completo debe tener al menos 3 caracteres")
        return v.strip() if v else v
    
    @field_validator('phone_number')
    @classmethod
    def validate_phone_number(cls, v):
        if v is not None and len(v.strip()) < 7:
            raise ValueError("El número de teléfono debe tener al menos 7 caracteres")
        return v.strip() if v else v

"""
Pydantic Models for User Management and Authentication
Modelos de datos para validación de requests y responses
"""

from pydantic import BaseModel, EmailStr, Field, validator
from typing import Optional, Dict, Any, List
from datetime import datetime
import re

# ============================================================================
# MODELOS PARA GESTIÓN DE USUARIOS
# ============================================================================

class UserRegistrationRequest(BaseModel):
    """Registro de usuario nuevo"""
    email: EmailStr
    password: str
    fullname: str
    cellphone: str
    nombre_centro_gestor: str
    
    @validator('cellphone')
    def validate_cellphone(cls, v):
        # Básica validación de formato colombiano
        clean_phone = re.sub(r'[^\d+]', '', str(v))
        if not clean_phone or len(clean_phone) < 10:
            raise ValueError('Número de celular inválido')
        return v

class UserLoginRequest(BaseModel):
    """Login con email y contraseña"""
    email: EmailStr
    password: str

class PasswordUpdateRequest(BaseModel):
    """Cambio de contraseña"""
    uid: str
    new_password: str

class PasswordResetRequest(BaseModel):
    """Modelo para solicitud de reseteo de contraseña"""
    email: EmailStr = Field(..., description="Email del usuario")

class GoogleAuthRequest(BaseModel):
    """Autenticación con Google"""
    email: EmailStr
    google_uid: str
    display_name: Optional[str] = None
    photo_url: Optional[str] = None

class PhoneAuthInitRequest(BaseModel):
    """Modelo para iniciar autenticación por teléfono"""
    phone_number: str = Field(..., description="Número de teléfono")

class PhoneAuthVerifyRequest(BaseModel):
    """Modelo para verificar código de autenticación por teléfono"""
    phone_number: str = Field(..., description="Número de teléfono")
    verification_code: str = Field(..., min_length=6, max_length=6, description="Código de verificación")
    
    @validator('verification_code')
    def validate_verification_code(cls, v):
        if not v.isdigit():
            raise ValueError('El código debe contener solo números')
        return v

class SessionValidationRequest(BaseModel):
    """Validación de sesión"""
    id_token: str

class TokenRevocationRequest(BaseModel):
    """Modelo para revocación de tokens"""
    uid: str = Field(..., description="UID del usuario")

class UserDeletionRequest(BaseModel):
    """Modelo para eliminación de usuario"""
    uid: str = Field(..., description="UID del usuario")
    soft_delete: Optional[bool] = Field(default=None, description="Eliminación lógica (true) o física (false)")

# ============================================================================
# MODELOS PARA RESPUESTAS
# ============================================================================

class UserResponse(BaseModel):
    """Modelo para respuesta de datos de usuario"""
    uid: str = Field(description="ID único del usuario")
    email: Optional[str] = Field(description="Email del usuario")
    display_name: Optional[str] = Field(description="Nombre para mostrar")
    fullname: Optional[str] = Field(description="Nombre completo")
    phone_number: Optional[str] = Field(description="Número de teléfono")
    email_verified: bool = Field(description="Estado de verificación del email")
    nombre_centro_gestor: Optional[str] = Field(description="Centro gestor")
    is_active: bool = Field(description="Usuario activo")
    created_at: Optional[datetime] = Field(description="Fecha de creación")
    last_login: Optional[datetime] = Field(description="Último inicio de sesión")
    login_count: int = Field(description="Número de inicios de sesión")
    auth_providers: List[str] = Field(description="Proveedores de autenticación")
    can_use_google_auth: bool = Field(description="Puede usar Google Auth")

class AuthMethodsResponse(BaseModel):
    """Modelo para respuesta de métodos de autenticación disponibles"""
    methods: Dict[str, Dict[str, Any]]
    password_requirements: Dict[str, Any]
    supported_domains: List[str]
    phone_format: str

class UserStatisticsResponse(BaseModel):
    """Modelo para respuesta de estadísticas de usuarios"""
    total_users: int
    active_users: int
    inactive_users: int
    email_verified_count: int
    google_auth_enabled: int
    users_by_role: Dict[str, int]
    users_by_centro_gestor: Dict[str, int]
    verification_rate: float
    google_auth_rate: float
    generated_at: datetime

class StandardResponse(BaseModel):
    """Modelo estándar para respuestas de la API"""
    success: bool
    message: str
    timestamp: datetime
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    code: Optional[str] = None

class ValidationErrorResponse(BaseModel):
    """Modelo para respuestas de error de validación"""
    success: bool = False
    error: str
    code: str
    details: Optional[Dict[str, Any]] = None
    requirements: Optional[Dict[str, Any]] = None

# ============================================================================
# MODELOS PARA FILTROS Y CONSULTAS
# ============================================================================

class UserListFilters(BaseModel):
    """Modelo para filtros de listado de usuarios"""
    limit: Optional[int] = Field(
        100, 
        ge=1, 
        le=1000, 
        description="Límite de resultados por página"
    )
    page_token: Optional[str] = Field(
        None, 
        description="Token para obtener siguiente página (obtenido de respuesta anterior)"
    )
    filter_by_role: Optional[str] = Field(
        None, 
        description="Filtrar por rol específico"
    )
    filter_by_centro_gestor: Optional[str] = Field(
        None, 
        description="Filtrar por centro gestor específico"
    )
    include_disabled: Optional[bool] = Field(
        False, 
        description="Incluir usuarios deshabilitados en los resultados"
    )

# ============================================================================
# MODELOS PARA VALIDACIONES ESPECÍFICAS
# ============================================================================

class EmailValidationRequest(BaseModel):
    """Modelo para validación de email"""
    email: EmailStr = Field(..., description="Email a validar")

class PasswordValidationRequest(BaseModel):
    """Modelo para validación de contraseña"""
    password: str = Field(..., description="Contraseña a validar")

class PhoneValidationRequest(BaseModel):
    """Modelo para validación de teléfono"""
    phone_number: str = Field(..., description="Número de teléfono a validar")



# ============================================================================
# MODELOS PARA CONFIGURACIÓN
# ============================================================================

class SystemConfigResponse(BaseModel):
    """Modelo para respuesta de configuración del sistema"""
    user_roles: Dict[str, str]
    authorized_domain: str
    password_requirements: Dict[str, Any]
    auth_methods_enabled: Dict[str, bool]
    phone_format_supported: str
    email_verification_enabled: bool
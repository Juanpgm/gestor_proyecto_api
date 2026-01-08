"""
Pydantic Models for User Management and Authentication
Modelos de datos para validación de requests y responses
"""

from pydantic import BaseModel, EmailStr, Field, field_validator, ConfigDict
from typing import Optional, Dict, Any, List, Union
from datetime import datetime
import re

# ============================================================================
# MODELOS PARA GESTIÓN DE USUARIOS
# ============================================================================

class UserRegistrationRequest(BaseModel):
    """✅ FUNCIONAL: Registro de usuario simplificado"""
    model_config = ConfigDict(populate_by_name=True)  # Permite tanto camelCase como snake_case
    
    email: EmailStr
    password: str
    confirmPassword: str = Field(alias="confirmPassword")  # Soporte explícito para camelCase
    name: str
    cellphone: str
    nombre_centro_gestor: str
    
    @field_validator('confirmPassword')
    @classmethod
    def passwords_match(cls, v, info):
        if 'password' in info.data and v != info.data['password']:
            raise ValueError('Las contraseñas no coinciden')
        return v
    
    @field_validator('cellphone')
    @classmethod
    def validate_cellphone(cls, v):
        # ✅ FUNCIONAL: Validación simplificada
        if not v or len(str(v).strip()) < 10:
            raise ValueError('Número de celular requerido')
        return str(v).strip()

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
    email: EmailStr

# ============================================================================
# MODELOS PARA GESTIÓN DE EMPRÉSTITO
# ============================================================================

class EmprestitoRequest(BaseModel):
    """Modelo base para registro de empréstito"""
    referencia_proceso: str = Field(..., min_length=1, description="Referencia del proceso (obligatorio)")
    nombre_centro_gestor: str = Field(..., min_length=1, description="Centro gestor responsable (obligatorio)")
    nombre_banco: str = Field(..., min_length=1, description="Nombre del banco (obligatorio)")
    bp: str = Field(..., min_length=1, description="Código BP (obligatorio)")
    plataforma: str = Field(..., min_length=1, description="Plataforma (SECOP, TVEC) (obligatorio)")
    nombre_resumido_proceso: Optional[str] = Field(None, description="Nombre resumido del proceso (opcional)")
    id_paa: Optional[str] = Field(None, description="ID PAA (opcional)")
    valor_proyectado: Optional[float] = Field(None, ge=0, description="Valor proyectado (opcional)")
    
    @field_validator('plataforma')
    @classmethod
    def validate_plataforma(cls, v):
        """Validar que la plataforma sea válida"""
        if not v or not v.strip():
            raise ValueError('Plataforma es requerida')
        return v.strip()
    
    @field_validator('referencia_proceso', 'nombre_centro_gestor', 'nombre_banco', 'bp')
    @classmethod
    def validate_required_fields(cls, v):
        """Validar campos obligatorios"""
        if not v or not v.strip():
            raise ValueError('Este campo es obligatorio')
        return v.strip()

class EmprestitoResponse(BaseModel):
    """Respuesta para operaciones de empréstito"""
    success: bool
    message: Optional[str] = None
    data: Optional[Dict[str, Any]] = None
    doc_id: Optional[str] = None
    coleccion: Optional[str] = None
    plataforma_detectada: Optional[str] = None
    fuente_datos: Optional[str] = None
    duplicate: Optional[bool] = False
    existing_data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

class ProyeccionEmprestitoUpdateRequest(BaseModel):
    """Modelo para actualización de proyecciones de empréstito"""
    item: Optional[int] = Field(None, description="Número de ítem")
    nombre_organismo_reducido: Optional[str] = Field(None, description="Nombre abreviado del organismo")
    nombre_banco: Optional[str] = Field(None, description="Banco asociado")
    BP: Optional[str] = Field(None, description="Código BP")
    nombre_generico_proyecto: Optional[str] = Field(None, description="Nombre del proyecto")
    nombre_resumido_proceso: Optional[str] = Field(None, description="Proyecto con contrato")
    id_paa: Optional[str] = Field(None, description="ID del PAA")
    urlProceso: Optional[str] = Field(None, description="Enlace al proceso")
    valor_proyectado: Optional[float] = Field(None, ge=0, description="Valor total del proyecto")
    
    @field_validator('valor_proyectado')
    @classmethod
    def validate_valor_proyectado(cls, v):
        """Validar que el valor proyectado sea positivo si se proporciona"""
        if v is not None and v < 0:
            raise ValueError('El valor proyectado debe ser mayor o igual a 0')
        return v
    
    @field_validator('*', mode='before')
    @classmethod
    def strip_strings(cls, v):
        """Limpiar strings de espacios en blanco si se proporcionan"""
        if isinstance(v, str):
            return v.strip() if v.strip() else None
        return v

class ProyeccionEmprestitoUpdateResponse(BaseModel):
    """Respuesta para actualización de proyecciones de empréstito"""
    success: bool
    message: Optional[str] = None
    referencia_proceso: Optional[str] = None
    doc_id: Optional[str] = None
    datos_previos: Optional[Dict[str, Any]] = None
    datos_actualizados: Optional[Dict[str, Any]] = None
    campos_modificados: Optional[List[str]] = None
    timestamp: Optional[str] = None
    coleccion: Optional[str] = None
    error: Optional[str] = None

class ProyeccionEmprestitoRegistroRequest(BaseModel):
    """Modelo para registrar nueva proyección de empréstito"""
    referencia_proceso: str = Field(..., description="Referencia única del proceso")
    nombre_centro_gestor: str = Field(..., description="Nombre del centro gestor")
    estado_proyeccion: Optional[str] = Field(None, description="Estado de la proyección")
    nombre_banco: str = Field(..., description="Nombre del banco")
    bp: str = Field(..., description="Código BP", alias="BP")
    proyecto_generico: str = Field(..., description="Proyecto genérico")
    nombre_resumido_proceso: Optional[str] = Field(None, description="Nombre resumido del proceso")
    id_paa: Optional[str] = Field(None, description="ID del PAA")
    valor_proyectado: Optional[float] = Field(None, ge=0, description="Valor proyectado")
    urlProceso: Optional[str] = Field(None, description="URL del proceso")
    
    model_config = ConfigDict(populate_by_name=True)
    
    @field_validator('valor_proyectado')
    @classmethod
    def validate_valor_proyectado(cls, v):
        """Validar que el valor proyectado sea positivo si se proporciona"""
        if v is not None and v < 0:
            raise ValueError('El valor proyectado debe ser mayor o igual a 0')
        return v
    
    @field_validator('*', mode='before')
    @classmethod
    def strip_strings(cls, v):
        """Limpiar strings de espacios en blanco"""
        if isinstance(v, str):
            return v.strip() if v.strip() else None
        return v

class ProyeccionEmprestitoRegistroResponse(BaseModel):
    """Respuesta para registro de nueva proyección de empréstito"""
    success: bool
    message: Optional[str] = None
    referencia_proceso: Optional[str] = None
    doc_id: Optional[str] = None
    datos_registrados: Optional[Dict[str, Any]] = None
    timestamp: Optional[str] = None
    coleccion: Optional[str] = None
    error: Optional[str] = None

class PagoEmprestitoRequest(BaseModel):
    """Modelo para registro de pago de empréstito"""
    numero_rpc: str = Field(..., min_length=1, description="Número del RPC (obligatorio)")
    valor_pago: float = Field(..., gt=0, description="Valor del pago (obligatorio, debe ser mayor a 0)")
    fecha_transaccion: str = Field(..., min_length=1, description="Fecha de la transacción (obligatorio)")
    referencia_contrato: str = Field(..., min_length=1, description="Referencia del contrato (obligatorio)")
    nombre_centro_gestor: str = Field(..., min_length=1, description="Centro gestor responsable (obligatorio)")
    
    @field_validator('numero_rpc', 'referencia_contrato', 'nombre_centro_gestor', 'fecha_transaccion')
    @classmethod
    def validate_required_fields(cls, v):
        """Validar campos obligatorios"""
        if not v or not v.strip():
            raise ValueError('Este campo es obligatorio')
        return v.strip()
    
    @field_validator('valor_pago')
    @classmethod
    def validate_valor_pago(cls, v):
        """Validar que el valor del pago sea positivo"""
        if v <= 0:
            raise ValueError('El valor del pago debe ser mayor a 0')
        return v

class PagoEmprestitoResponse(BaseModel):
    """Respuesta para registro de pago de empréstito"""
    success: bool
    message: Optional[str] = None
    doc_id: Optional[str] = None
    data: Optional[Dict[str, Any]] = None
    coleccion: Optional[str] = None
    timestamp: Optional[str] = None
    error: Optional[str] = None

class RPCUpdateRequest(BaseModel):
    """Modelo para actualización de RPC (Registro Presupuestal de Compromiso)"""
    beneficiario_id: Optional[str] = Field(None, description="ID del beneficiario")
    beneficiario_nombre: Optional[str] = Field(None, description="Nombre del beneficiario")
    descripcion_rpc: Optional[str] = Field(None, description="Descripción del RPC")
    fecha_contabilizacion: Optional[str] = Field(None, description="Fecha de contabilización")
    fecha_impresion: Optional[str] = Field(None, description="Fecha de impresión")
    estado_liberacion: Optional[str] = Field(None, description="Estado de liberación")
    bp: Optional[str] = Field(None, description="Código BP")
    valor_rpc: Optional[float] = Field(None, ge=0, description="Valor del RPC")
    cdp_asociados: Optional[Union[List[str], str]] = Field(None, description="CDPs asociados (lista o string separado por comas)")
    programacion_pac: Optional[Dict[str, Any]] = Field(None, description="Programación PAC")
    nombre_centro_gestor: Optional[str] = Field(None, description="Nombre del centro gestor")
    referencia_contrato: Optional[str] = Field(None, description="Referencia del contrato")
    estado: Optional[str] = Field(None, description="Estado del RPC")
    
    @field_validator('valor_rpc')
    @classmethod
    def validate_valor_rpc(cls, v):
        """Validar que el valor del RPC sea positivo si se proporciona"""
        if v is not None and v < 0:
            raise ValueError('El valor del RPC debe ser mayor o igual a 0')
        return v
    
    @field_validator('*', mode='before')
    @classmethod
    def strip_strings(cls, v):
        """Limpiar strings de espacios en blanco si se proporcionan"""
        if isinstance(v, str):
            return v.strip() if v.strip() else None
        return v

class RPCUpdateResponse(BaseModel):
    """Respuesta para actualización de RPC"""
    success: bool
    message: Optional[str] = None
    numero_rpc: Optional[str] = None
    doc_id: Optional[str] = None
    coleccion: Optional[str] = None
    datos_previos: Optional[Dict[str, Any]] = None
    datos_actualizados: Optional[Dict[str, Any]] = None
    campos_modificados: Optional[List[str]] = None
    timestamp: Optional[str] = None
    error: Optional[str] = None

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
    
    @field_validator('verification_code')
    @classmethod
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
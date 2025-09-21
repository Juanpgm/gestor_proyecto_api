"""
Esquemas Pydantic v2 para validación de datos de usuario
Gestión de Datos de Usuario - Programación Funcional
Compatible con Pydantic 2.11.9 - Documentación mejorada
"""
from pydantic import BaseModel, EmailStr, field_validator, model_validator, Field
from typing import Optional, Literal, Dict, List, Any
from datetime import datetime
import re


# ============================================================================
# ESQUEMAS BASE PARA USUARIOS
# ============================================================================

class UsuarioBase(BaseModel):
    """
    Esquema base para gestión de usuarios del sistema municipal
    Contiene los campos fundamentales para identificación y contacto
    """
    nombre_completo: str = Field(
        ..., 
        min_length=5, 
        max_length=150, 
        title="Nombre Completo",
        description="Nombres y apellidos del usuario"
    )
    email: Optional[EmailStr] = Field(
        None,
        title="Email", 
        description="Correo electrónico"
    )
    telefono: Optional[str] = Field(
        None, 
        max_length=20,
        title="Teléfono",
        description="Número telefónico"
    )
    username: Optional[str] = Field(
        None, 
        min_length=3, 
        max_length=50,
        title="Usuario",
        description="Nombre de usuario único"
    )
    # documento_identidad: Optional[str] = Field(
    #     None, 
    #     max_length=20,
    #     title="Documento",
    #     description="Cédula o documento de identidad"
    # )
    es_activo: bool = Field(
        default=True,
        title="Activo", 
        description="Usuario tiene acceso al sistema"
    )
    
    @field_validator('telefono')
    @classmethod
    def validate_telefono(cls, v):
        """Validar formato de teléfono"""
        if v and not re.match(r'^\+?[\d\s\-\(\)]{8,15}$', v):
            raise ValueError('Formato de teléfono inválido')
        return v
    
    @field_validator('username')
    @classmethod
    def validate_username(cls, v):
        """Validar username"""
        if v and not re.match(r'^[a-zA-Z0-9_]{3,50}$', v):
            raise ValueError('Username debe contener solo letras, números y guiones bajos')
        return v


class UsuarioCreate(UsuarioBase):
    """
    Esquema para registro de nuevos usuarios en el sistema
    Incluye validaciones de seguridad para contraseñas y autenticación
    """
    password: str = Field(
        ..., 
        min_length=8,
        title="Contraseña", 
        description="Contraseña con mínimo 8 caracteres, al menos una letra y un número"
    )
    confirm_password: str = Field(
        ...,
        title="Confirmar Contraseña",
        description="Repetir la misma contraseña"
    )
    autenticacion_tipo: Literal['local', 'google', 'telefono'] = Field(
        default='local',
        title="Tipo de Autenticación", 
        description="local = usuario/contraseña, google = OAuth, telefono = SMS"
    )
    rol: int = Field(
        default=1, 
        ge=1, 
        le=5,
        title="Nivel de Rol",
        description="1=Básico, 2=Avanzado, 3=Moderador, 4=Admin, 5=Super Admin"
    )
    
    @field_validator('password')
    @classmethod
    def validate_password(cls, v):
        """Validar fortaleza de contraseña"""
        if len(v) < 8:
            raise ValueError('La contraseña debe tener al menos 8 caracteres')
        if not re.search(r'[A-Za-z]', v):
            raise ValueError('La contraseña debe contener al menos una letra')
        if not re.search(r'\d', v):
            raise ValueError('La contraseña debe contener al menos un número')
        return v
    
    def model_post_init(self, __context):
        """Validar que las contraseñas coincidan después de la inicialización"""
        if self.password != self.confirm_password:
            raise ValueError('Las contraseñas no coinciden')


class LoginCredentials(BaseModel):
    """
    Esquema para autenticación de usuarios existentes
    Soporta múltiples métodos de identificación (email, username, teléfono)
    """
    identifier: str = Field(
        ...,
        title="Usuario", 
        description="Email, nombre de usuario, o teléfono"
    )
    password: str = Field(
        ...,
        title="Contraseña",
        description="Tu contraseña"
    )
    autenticacion_tipo: Literal['email', 'username', 'telefono'] = Field(
        default='email',
        title="Tipo",
        description="email = correo, username = usuario, telefono = teléfono"
    )
    
    @model_validator(mode='after')
    def validate_identifier_format(self):
        """Validar formato del identificador según el tipo de autenticación"""
        identifier = self.identifier
        auth_type = self.autenticacion_tipo
        
        if auth_type == 'email' and not re.match(r'^[^@]+@[^@]+\.[^@]+$', identifier):
            raise ValueError('Formato de email inválido')
        elif auth_type == 'telefono' and not re.match(r'^\+?[\d\s\-\(\)]{8,15}$', identifier):
            raise ValueError('Formato de teléfono inválido')
        elif auth_type == 'username' and not re.match(r'^[a-zA-Z0-9_]{3,50}$', identifier):
            raise ValueError('Formato de username inválido')
        
        return self


class TokenResponse(BaseModel):
    """Esquema para respuesta de token"""
    access_token: str = Field(..., description="Token de acceso JWT")
    refresh_token: Optional[str] = Field(None, description="Token de actualización JWT")
    token_type: str = Field(default="bearer", description="Tipo de token")
    expires_in: int = Field(..., description="Tiempo de expiración en segundos")
    user_id: str = Field(..., description="ID del usuario (UUID)")
    username: str = Field(..., description="Nombre de usuario")


class UsuarioResponse(BaseModel):
    """Esquema para respuesta de usuario"""
    id: str
    username: str
    nombre_completo: str
    email: Optional[str] = None
    telefono: Optional[str] = None
    # documento_identidad: Optional[str] = None
    es_activo: bool
    rol: int
    autenticacion_tipo: str
    fecha_creacion: datetime
    ultimo_login: Optional[datetime] = None
    
    class Config:
        from_attributes = True


# ============================================================================
# ESQUEMAS PARA RECUPERACIÓN DE CONTRASEÑA
# ============================================================================

class PasswordResetRequest(BaseModel):
    """Esquema para solicitar reseteo de contraseña"""
    email: EmailStr = Field(..., title="Email", description="Tu dirección de correo")


class PasswordReset(BaseModel):
    """Esquema para resetear contraseña"""
    token: str = Field(..., title="Token", description="Código de verificación recibido")
    new_password: str = Field(..., min_length=8, title="Nueva Contraseña", description="Mínimo 8 caracteres")
    confirm_password: str = Field(..., title="Confirmar", description="Repetir nueva contraseña")
    
    @field_validator('new_password')
    @classmethod
    def validate_new_password(cls, v):
        """Validar nueva contraseña"""
        if len(v) < 8:
            raise ValueError('La contraseña debe tener al menos 8 caracteres')
        if not re.search(r'[A-Za-z]', v):
            raise ValueError('La contraseña debe contener al menos una letra')
        if not re.search(r'\d', v):
            raise ValueError('La contraseña debe contener al menos un número')
        return v
    
    def model_post_init(self, __context):
        """Validar que las contraseñas coincidan"""
        if self.new_password != self.confirm_password:
            raise ValueError('Las contraseñas no coinciden')


class PasswordChange(BaseModel):
    """Esquema para cambiar contraseña"""
    current_password: str = Field(..., title="Contraseña Actual", description="Tu contraseña actual")
    new_password: str = Field(..., min_length=8, title="Nueva Contraseña", description="Mínimo 8 caracteres")
    confirm_password: str = Field(..., title="Confirmar", description="Repetir nueva contraseña")
    
    @field_validator('new_password')
    @classmethod
    def validate_new_password(cls, v):
        """Validar nueva contraseña"""
        if len(v) < 8:
            raise ValueError('La contraseña debe tener al menos 8 caracteres')
        if not re.search(r'[A-Za-z]', v):
            raise ValueError('La contraseña debe contener al menos una letra')
        if not re.search(r'\d', v):
            raise ValueError('La contraseña debe contener al menos un número')
        return v
    
    def model_post_init(self, __context):
        """Validar que las contraseñas coincidan"""
        if self.new_password != self.confirm_password:
            raise ValueError('Las contraseñas no coinciden')


# ============================================================================
# ESQUEMAS PARA VERIFICACIÓN Y CÓDIGOS
# ============================================================================

class VerificationCode(BaseModel):
    """Esquema para código de verificación"""
    code: str = Field(..., min_length=6, max_length=6, title="Código", description="Código de 6 dígitos")
    identifier: str = Field(..., title="Email/Teléfono", description="Email o teléfono a verificar")
    
    @field_validator('code')
    @classmethod
    def validate_code(cls, v):
        """Validar código de verificación"""
        if not v.isdigit():
            raise ValueError('El código debe contener solo números')
        return v


class EmailVerification(BaseModel):
    """Esquema para verificación de email"""
    token: str = Field(..., description="Token de verificación de email")


# ============================================================================
# ESQUEMAS PARA GOOGLE OAUTH
# ============================================================================

class GoogleAuthRequest(BaseModel):
    """Esquema para autenticación con Google"""
    google_token: str = Field(..., title="Token de Google", description="Token OAuth de Google")


class PhoneAuthRequest(BaseModel):
    """Esquema para solicitar código de verificación por teléfono"""
    telefono: str = Field(..., title="Teléfono", description="Número de teléfono con código país (+57...)")
    
    @field_validator('telefono')
    @classmethod
    def validate_telefono(cls, v):
        """Validar formato de teléfono"""
        if not re.match(r'^\+?[\d\s\-\(\)]{8,15}$', v):
            raise ValueError('Formato de teléfono inválido')
        return v


class PhoneVerificationRequest(BaseModel):
    """Esquema para verificar código telefónico"""
    telefono: str = Field(..., title="Teléfono", description="Número de teléfono")
    codigo: str = Field(..., min_length=6, max_length=6, title="Código SMS", description="Código de 6 dígitos")
    password: Optional[str] = Field(None, title="Contraseña", description="Solo para nuevos usuarios")
    
    @field_validator('codigo')
    @classmethod
    def validate_codigo(cls, v):
        """Validar código"""
        if not v.isdigit():
            raise ValueError('El código debe contener solo números')
        return v


class GoogleUserInfo(BaseModel):
    """Esquema para información de usuario de Google"""
    google_id: str = Field(..., description="ID de Google")
    email: str = Field(..., description="Email de Google")
    nombres: str = Field(..., description="Nombres de Google")
    apellidos: str = Field(..., description="Apellidos de Google")
    picture: Optional[str] = Field(None, description="URL de imagen de perfil")


# ============================================================================
# ESQUEMAS PARA SESIONES Y AUDITORÍA
# ============================================================================

class SessionInfo(BaseModel):
    """Esquema para información de sesión"""
    session_id: str = Field(..., description="ID de sesión")
    user_id: int = Field(..., description="ID del usuario")
    ip_address: str = Field(..., description="Dirección IP")
    user_agent: str = Field(..., description="User Agent del navegador")
    login_time: datetime = Field(..., description="Fecha y hora de login")
    last_activity: datetime = Field(..., description="Última actividad")
    is_active: bool = Field(default=True, description="Sesión activa")


class AuditLog(BaseModel):
    """Esquema para logs de auditoría"""
    user_id: int = Field(..., description="ID del usuario")
    action: str = Field(..., description="Acción realizada")
    ip_address: str = Field(..., description="Dirección IP")
    user_agent: str = Field(..., description="User Agent")
    timestamp: datetime = Field(..., description="Fecha y hora de la acción")
    details: Optional[str] = Field(None, description="Detalles adicionales")


# ============================================================================
# ESQUEMAS PARA ACTUALIZACIÓN DE PERFIL
# ============================================================================

class UsuarioUpdate(BaseModel):
    """Esquema para actualizar usuario"""
    nombre_completo: Optional[str] = Field(None, min_length=5, max_length=150, title="Nombre Completo", description="Nombre completo del usuario")
    email: Optional[EmailStr] = Field(None, title="Email", description="Nuevo correo electrónico")
    telefono: Optional[str] = Field(None, max_length=20, title="Teléfono", description="Nuevo número de teléfono")
    # documento_identidad: Optional[str] = Field(None, max_length=20, title="Documento", description="Número de documento")  # REMOVIDO: no existe en DB
    
    @field_validator('telefono')
    @classmethod
    def validate_telefono(cls, v):
        """Validar formato de teléfono"""
        if v and not re.match(r'^\+?[\d\s\-\(\)]{8,15}$', v):
            raise ValueError('Formato de teléfono inválido')
        return v


# ============================================================================
# ESQUEMAS PARA RESPUESTAS ESTÁNDAR
# ============================================================================

class StandardResponse(BaseModel):
    """Esquema para respuestas estándar"""
    success: bool = Field(..., description="Indicador de éxito")
    message: str = Field(..., description="Mensaje descriptivo")
    data: Optional[dict] = Field(None, description="Datos adicionales")


class MessageResponse(BaseModel):
    """Esquema para respuestas simples con mensaje"""
    message: str = Field(..., description="Mensaje descriptivo")
    success: bool = Field(default=True, description="Indicador de éxito")


class PaginationParams(BaseModel):
    """Esquema para parámetros de paginación"""
    page: int = Field(default=1, ge=1, title="Página", description="Número de página (desde 1)")
    per_page: int = Field(default=10, ge=1, le=100, title="Por Página", description="Elementos por página (máx 100)")
    
    
class UserListResponse(BaseModel):
    """Esquema para lista de usuarios"""
    users: list[UsuarioResponse] = Field(..., description="Lista de usuarios")
    total: int = Field(..., description="Total de usuarios")
    page: int = Field(..., description="Página actual")
    per_page: int = Field(..., description="Usuarios por página")
    pages: int = Field(..., description="Total de páginas")


# ============================================================================
# FUNCIONES DE CONFIGURACIÓN PARA OPENAPI
# ============================================================================

def get_openapi_config() -> Dict[str, Any]:
    """Configuración OpenAPI para la documentación de la API"""
    return {
        "title": "API Gestor Municipal - Sistema de Gestión de Proyectos",
        "description": """
        ## API Municipal de Gestión de Proyectos
        
        **Sistema integral para la gestión de datos municipales con arquitectura funcional**
        
        ### Características principales:
        - **Autenticación JWT** - Sistema seguro de tokens
        - **Múltiples tipos de auth** - Local, Google OAuth, SMS
        - **Control de roles** - 5 niveles de acceso
        - **Gestión de proyectos** - Infraestructura municipal
        - **Datos presupuestales** - Ejecución y movimientos
        - **Contratos públicos** - DACP y SECOP
        
        ### Niveles de Rol:
        1. **Usuario básico** - Lectura básica
        2. **Supervisor** - Supervisión de proyectos  
        3. **Jefe** - Gestión departamental
        4. **Director** - Dirección de secretaría
        5. **Admin** - Administración completa
        
        ### Cómo usar la API:
        1. **Registrarse** en `/users/register` o usar demo en `/users/demo/register`
        2. **Hacer login** en `/users/login` o usar demo en `/users/demo/login`
        3. **Copiar token** de la respuesta (campo `access_token`)
        4. **Autorizar** usando el botón Authorize con formato: `Bearer tu_token_aqui`
        5. **Probar endpoints** - Ya tienes acceso completo
        
        ### Enlaces útiles:
        - [Documentación Interactiva](https://api.municipio.gov.co/docs)
        - [ReDoc](https://api.municipio.gov.co/redoc)
        - [Estado de la API](https://api.municipio.gov.co/health)
        """,
        "version": "3.0.0",
        "contact": {
            "name": "Municipio - Equipo de Desarrollo",
            "email": "desarrollo@municipio.gov.co",
            "url": "https://municipio.gov.co"
        },
        "license": {
            "name": "Municipio License",
            "url": "https://municipio.gov.co/licencia"
        },
        "tags": [
            {
                "name": "Sistema",
                "description": "Información general y estado de la API"
            },
            {
                "name": "Gestión de Usuarios", 
                "description": "Registro, autenticación y gestión de usuarios"
            },
            {
                "name": "Autenticación",
                "description": "Login, logout y gestión de tokens"
            },
            {
                "name": "Verificación",
                "description": "Verificación de email y teléfono"
            },
            {
                "name": "Recuperación", 
                "description": "Recuperación y cambio de contraseñas"
            },
            {
                "name": "Testing & Demos",
                "description": "Endpoints de prueba con datos predefinidos"
            },
            {
                "name": "Base de Datos",
                "description": "Consultas y estadísticas de datos municipales"
            },
            {
                "name": "Proyectos",
                "description": "Gestión de proyectos de infraestructura"
            },
            {
                "name": "Presupuesto",
                "description": "Ejecución y movimientos presupuestales"
            },
            {
                "name": "Contratos",
                "description": "Gestión de contratación pública"
            }
        ]
    }


def get_swagger_ui_config() -> Dict[str, Any]:
    """Configuración Swagger UI personalizada"""
    return {
        "swagger_ui_parameters": {
            "deepLinking": True,
            "displayRequestDuration": True,
            "defaultModelsExpandDepth": 1,
            "defaultModelExpandDepth": 1,
            "docExpansion": "list",
            "filter": True,
            "showRequestHeaders": True,
            "syntaxHighlight.activate": True,
            "syntaxHighlight.theme": "agate",
            "tryItOutEnabled": True,
            "validatorUrl": None,
            "withCredentials": True
        }
    }


# ============================================================================
# ESQUEMAS PARA TESTING Y DEMOS
# ============================================================================

class UsuarioCreateDemo(UsuarioBase):
    """
    Esquema demo para testing rápido - Datos predefinidos
    
    Facilita el testing al incluir valores por defecto válidos.
    Perfecto para pruebas rápidas sin completar formularios.
    """
    nombre_completo: str = Field(
        default="Juan Carlos Pérez García",
        title="Nombre Completo",
        description="Nombre completo del usuario - Predefinido para demo"
    )
    email: EmailStr = Field(
        default="juan.perez@ejemplo.com",
        title="Email",
        description="Correo electrónico - Predefinido para demo"
    )
    telefono: str = Field(
        default="+57 300 123 4567",
        title="Teléfono", 
        description="Número telefónico - Predefinido para demo"
    )
    username: str = Field(
        default="juan_perez123",
        title="Username",
        description="Nombre de usuario - Predefinido para demo"
    )
    # documento_identidad: str = Field(
    #     default="12345678",
    #     title="Documento",
    #     description="Cédula - Predefinido para demo"
    # )  # REMOVIDO: no existe en DB
    password: str = Field(
        default="Demo123456",
        title="Contraseña",
        description="Contraseña segura - Predefinido para demo"
    )
    confirm_password: str = Field(
        default="Demo123456",
        title="Confirmar Contraseña",
        description="Repetir contraseña - Predefinido para demo"
    )
    autenticacion_tipo: Literal['local', 'google', 'telefono'] = Field(
        default='local',
        title="Tipo de Autenticación",
        description="Tipo de autenticación - Predefinido para demo"
    )
    rol: int = Field(
        default=1,
        ge=1,
        le=5,
        title="Nivel de Rol",
        description="Nivel de acceso (1-5) - Predefinido para demo"
    )


class LoginCredentialsDemo(BaseModel):
    """
    Esquema demo para login rápido - Credenciales predefinidas
    
    Facilita el testing de autenticación con datos válidos automáticos.
    """
    identifier: str = Field(
        default="juan.perez@ejemplo.com",
        title="Email/Username",
        description="Email o username - Predefinido para demo"
    )
    password: str = Field(
        default="Demo123456",
        title="Contraseña",
        description="Contraseña - Predefinido para demo"
    )
    autenticacion_tipo: Literal['email', 'username', 'telefono'] = Field(
        default='email',
        title="Tipo",
        description="Tipo de identificador - Predefinido para demo"
    )


class TestDataSets(BaseModel):
    """
    Conjuntos de datos estructurados para testing comprehensivo
    
    Proporciona ejemplos para diferentes escenarios de prueba.
    """
    usuario_completo: UsuarioCreateDemo = Field(
        default_factory=UsuarioCreateDemo,
        description="Datos completos para registro de usuario"
    )
    
    credenciales_login: LoginCredentialsDemo = Field(
        default_factory=LoginCredentialsDemo,
        description="Credenciales para login de prueba"
    )
    
    roles_disponibles: Dict[int, str] = Field(
        default={
            1: "Usuario básico - Acceso de lectura",
            2: "Supervisor - Supervisión de proyectos", 
            3: "Jefe - Gestión departamental",
            4: "Director - Dirección de secretaría",
            5: "Admin - Administración completa"
        },
        description="Descripción de roles disponibles"
    )
    
    tipos_autenticacion: List[str] = Field(
        default=["local", "google", "telefono"],
        description="Tipos de autenticación soportados"
    )
    
    ejemplos_validacion: Dict[str, List[str]] = Field(
        default={
            "emails_validos": [
                "usuario@ejemplo.com",
                "test.email+tag@domain.co", 
                "admin@municipio.gov.co"
            ],
            "telefonos_validos": [
                "+57 300 123 4567",
                "+57 310 987 6543",
                "+573201234567"
            ],
            "passwords_validas": [
                "SecurePass123",
                "MyPassword456!",
                "Demo123456"
            ]
        },
        description="Ejemplos de datos válidos para testing"
    )
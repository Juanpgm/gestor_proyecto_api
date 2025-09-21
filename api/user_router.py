"""
Router de Gestión de Datos de Usuario
Endpoints para autenticación, registro y gestión de usuarios
Arquitectura Funcional con Documentación Mejorada
"""
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from datetime import datetime
from functools import lru_cache

from config import get_db
from api.models import Usuario, TokenSeguridad
from api.schemas import (
    UsuarioCreate, UsuarioUpdate, UsuarioResponse, LoginCredentials, 
    TokenResponse, GoogleAuthRequest, PhoneAuthRequest, PhoneVerificationRequest,
    PasswordResetRequest, PasswordReset, PasswordChange,
    VerificationCode, StandardResponse, MessageResponse, SessionInfo, 
    UserListResponse, PaginationParams,
    # Esquemas de demo para testing
    UsuarioCreateDemo, LoginCredentialsDemo, TestDataSets
)
from api.auth_service import (
    create_user, authenticate_user, find_user_by_identifier, verify_token,
    generate_tokens_for_user, create_security_token, verify_security_token,
    verify_google_token, find_or_create_google_user, update_user_password,
    generate_phone_code, check_user_permissions
)

# ============================================================================
# FUNCIONES UTILITARIAS PARA DOCUMENTACIÓN FUNCIONAL
# ============================================================================

@lru_cache(maxsize=1)
def get_router_tags() -> List[Dict[str, str]]:
    """Función pura para obtener tags organizados del router"""
    return [
        {
            "name": "Autenticación",
            "description": "Endpoints para login, logout y gestión de tokens de acceso"
        },
        {
            "name": "Registro de Usuarios", 
            "description": "Endpoints para crear nuevas cuentas de usuario"
        },
        {
            "name": "Gestión de Perfil",
            "description": "Endpoints para actualizar información personal del usuario"
        },
        {
            "name": "Recuperación de Contraseña",
            "description": "Endpoints para restablecer contraseñas olvidadas"
        },
        {
            "name": "Administración",
            "description": "Endpoints administrativos para gestión de usuarios"
        }
    ]

def get_endpoint_summary(action: str, resource: str) -> str:
    """Función pura para generar resúmenes de endpoints"""
    action_map = {
        'create': f'Crear nuevo {resource}',
        'login': f'Iniciar sesión de {resource}',
        'get': f'Obtener información de {resource}',
        'update': f'Actualizar datos de {resource}',
        'delete': f'Eliminar {resource}',
        'list': f'Listar {resource}s',
        'reset': f'Restablecer {resource}',
        'verify': f'Verificar {resource}'
    }
    return action_map.get(action, f'{action} {resource}')

def get_response_description(status_code: int) -> str:
    """Función pura para descripciones de respuestas HTTP"""
    descriptions = {
        200: "Operación exitosa - datos retornados correctamente",
        201: "Recurso creado exitosamente",
        400: "Solicitud inválida - revisa los datos enviados", 
        401: "No autorizado - token de acceso requerido o inválido",
        403: "Acceso denegado - permisos insuficientes",
        404: "Recurso no encontrado",
        409: "Conflicto - el recurso ya existe",
        422: "Error de validación - datos no cumplen los requisitos",
        500: "Error interno del servidor"
    }
    return descriptions.get(status_code, f"Respuesta HTTP {status_code}")

# ============================================================================
# CONFIGURACIÓN DEL ROUTER
# ============================================================================

user_router = APIRouter(
    prefix="/users",
    tags=["Gestión de Usuarios"],
    responses={
        404: {"description": "Usuario no encontrado"},
        401: {"description": "No autorizado - token requerido"},
        403: {"description": "Acceso denegado - permisos insuficientes"},
        422: {"description": "Error de validación - datos incorrectos"}
    }
)

# Security scheme
security = HTTPBearer()

# ============================================================================
# FUNCIONES AUXILIARES Y DEPENDENCIAS
# ============================================================================

def usuario_to_response(user: Usuario) -> UsuarioResponse:
    """Convertir modelo Usuario a schema UsuarioResponse"""
    return UsuarioResponse(
        id=user.id,
        username=user.username,
        nombre_completo=user.nombre_completo,
        email=user.email,
        telefono=user.telefono,
        # documento_identidad=user.documento_identidad,
        es_activo=user.estado,
        rol=user.rol,
        autenticacion_tipo=user.autenticacion_tipo,
        fecha_creacion=user.creado_en,
        ultimo_login=user.ultimo_login
    )

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> Usuario:
    """
    Dependencia para obtener usuario actual autenticado
    """
    token = credentials.credentials
    payload = verify_token(token, "access")
    
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido o expirado",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    user_id = payload.get("sub")
    user = db.query(Usuario).filter(Usuario.id == user_id).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario no encontrado"
        )
    
    if not user.estado:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Cuenta desactivada"
        )
    
    return user

def get_admin_user(current_user: Usuario = Depends(get_current_user)) -> Usuario:
    """
    Dependencia para verificar permisos de administrador
    """
    if not check_user_permissions(current_user, 5):  # Rol Admin = 5
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permisos insuficientes. Requiere rol de administrador"
        )
    return current_user

def get_manager_user(current_user: Usuario = Depends(get_current_user)) -> Usuario:
    """
    Dependencia para verificar permisos de jefe o superior
    """
    if not check_user_permissions(current_user, 3):  # Jefe = 3
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permisos insuficientes. Requiere rol de jefe o superior"
        )
    return current_user

# ============================================================================
# ENDPOINTS DE REGISTRO
# ============================================================================

@user_router.post("/register", response_model=UsuarioResponse, status_code=status.HTTP_201_CREATED, tags=["Registro"])
async def register_user(user_data: UsuarioCreate, db: Session = Depends(get_db)):
    """
    Registrar nuevo usuario en el sistema
    
    - **username**: Nombre de usuario único (3-50 caracteres, solo letras, números y _)
    - **nombre_completo**: Nombre completo del usuario
    - **email**: Correo electrónico (opcional si se proporciona teléfono)
    - **telefono**: Número de teléfono colombiano (opcional si se proporciona email)
    - **password**: Contraseña segura (mín 8 caracteres, mayúscula, minúscula, número)
    - **rol**: Nivel de acceso (1=Básico, 2=Supervisor, 3=Jefe, 4=Director, 5=Admin)
    """
    try:
        new_user = create_user(db, user_data)
        
        # TEMPORAL: Comentado para permitir registro sin verificación de email
        # if new_user.email and user_data.autenticacion_tipo == 'local':
        #     verification_token = create_security_token(
        #         db, new_user.id, "verificacion_email", 48
        #     )
        # TODO: Enviar email de verificación
        # print(f"Token de verificación email: {verification_token}")
        
        # TEMPORAL: Auto-verificar usuarios para pruebas
        new_user.verificado = True
        db.commit()

        return UsuarioResponse(
            id=new_user.id,
            username=new_user.username,
            nombre_completo=new_user.nombre_completo,
            email=new_user.email,
            telefono=new_user.telefono,
            # documento_identidad=new_user.documento_identidad,
            es_activo=new_user.estado,
            rol=new_user.rol,
            autenticacion_tipo=new_user.autenticacion_tipo,
            fecha_creacion=new_user.creado_en,
            ultimo_login=new_user.ultimo_login
        )
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno del servidor"
        )

@user_router.post("/verify-email", response_model=MessageResponse, tags=["Verificación"])
async def verify_email(
    token: str,
    db: Session = Depends(get_db)
):
    """
    Verificar email con token enviado por correo
    """
    user_id = verify_security_token(db, token, "verificacion_email")
    
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token inválido o expirado"
        )
    
    user = db.query(Usuario).filter(Usuario.id == user_id).first()
    if user:
        user.verificado = True
        db.commit()
    
    return MessageResponse(message="Email verificado exitosamente")

# ============================================================================
# ENDPOINTS DE AUTENTICACIÓN
# ============================================================================

@user_router.post("/login", response_model=TokenResponse, tags=["Autenticación"])
async def login(
    credentials: LoginCredentials,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Iniciar sesión con username/email/teléfono y contraseña
    
    - **identifier**: Username, email o número de teléfono
    - **password**: Contraseña del usuario
    - **remember_me**: Mantener sesión activa por más tiempo
    """
    try:
        user = authenticate_user(db, credentials)
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Credenciales incorrectas"
            )
        
        # TEMPORAL: Comentado para permitir login sin verificación de email
        # if not user.verificado:
        #     raise HTTPException(
        #         status_code=status.HTTP_401_UNAUTHORIZED,
        #         detail="Cuenta no verificada. Revise su email"
        #     )
        
        # Generar tokens
        tokens = generate_tokens_for_user(user)
        
        # TODO: Registrar sesión en tabla de sesiones
        client_ip = request.client.host
        user_agent = request.headers.get("user-agent", "")
        print(f"Login exitoso: {user.username} desde {client_ip}")
        
        return TokenResponse(
            **tokens,
            user_id=user.id,
            username=user.username
        )
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@user_router.post("/login/google", response_model=TokenResponse, tags=["Autenticación"])
async def login_google(
    google_auth: GoogleAuthRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Iniciar sesión con Google OAuth
    
    - **google_token**: Token de Google OAuth obtenido del frontend
    """
    google_info = verify_google_token(google_auth.google_token)
    
    if not google_info:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de Google inválido"
        )
    
    try:
        user = find_or_create_google_user(db, google_info)
        tokens = generate_tokens_for_user(user)
        
        # TODO: Registrar sesión
        client_ip = request.client.host
        print(f"Login Google exitoso: {user.username} desde {client_ip}")
        
        return TokenResponse(
            **tokens,
            user_id=user.id,
            username=user.username
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error en autenticación con Google"
        )

@user_router.post("/login/phone/request", response_model=TokenResponse, tags=["Verificación"])
async def request_phone_login(
    phone_request: PhoneAuthRequest,
    db: Session = Depends(get_db)
):
    """
    Solicitar código de verificación por SMS para login
    
    - **telefono**: Número de teléfono colombiano
    """
    user = find_user_by_identifier(db, phone_request.telefono)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No existe cuenta con ese número de teléfono"
        )
    
    if user.autenticacion_tipo != 'telefono':
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Esta cuenta no está configurada para autenticación por teléfono"
        )
    
    # Generar código y crear token
    code = generate_phone_code()
    token = create_security_token(db, user.id, "verificacion_telefono", duration_hours=0.17)  # 10 minutos
    
    # TODO: Enviar SMS con código
    print(f"Código SMS para {phone_request.telefono}: {code}")
    
    return TokenResponse(
        message="Código de verificación enviado por SMS",
        expires_in=10 * 60  # 10 minutos
    )

@user_router.post("/login/phone/verify", response_model=TokenResponse)
async def verify_phone_login(
    verification: PhoneVerificationRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Verificar código SMS y completar login por teléfono
    
    - **telefono**: Número de teléfono
    - **codigo**: Código de 6 dígitos enviado por SMS
    """
    user = find_user_by_identifier(db, verification.telefono)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado"
        )
    
    # TODO: Verificar código SMS contra token almacenado
    # Por ahora simulamos verificación exitosa si código es válido
    if len(verification.codigo) != 6 or not verification.codigo.isdigit():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Código inválido"
        )
    
    # Actualizar último login
    user.ultimo_login = datetime.utcnow()
    db.commit()
    
    tokens = generate_tokens_for_user(user)
    
    client_ip = request.client.host
    print(f"Login SMS exitoso: {user.username} desde {client_ip}")
    
    return TokenResponse(
        **tokens,
        user_id=user.id,
        username=user.username
    )

@user_router.post("/refresh", response_model=dict)
async def refresh_token(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    """
    Renovar token de acceso usando refresh token
    """
    refresh_token = credentials.credentials
    payload = verify_token(refresh_token, "refresh")
    
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token inválido o expirado"
        )
    
    user_id = payload.get("sub")
    user = db.query(Usuario).filter(Usuario.id == user_id).first()
    
    if not user or not user.es_activo:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario no válido"
        )
    
    tokens = generate_tokens_for_user(user)
    return tokens

@user_router.post("/logout", response_model=MessageResponse)
async def logout(current_user: Usuario = Depends(get_current_user)):
    """
    Cerrar sesión (invalidar tokens)
    """
    # TODO: Invalidar tokens en blacklist o base de datos
    # TODO: Cerrar sesión en tabla de sesiones activas
    
    print(f"Logout: {current_user.username}")
    
    return MessageResponse(message="Sesión cerrada exitosamente")

# ============================================================================
# ENDPOINTS DE RECUPERACIÓN DE CONTRASEÑA
# ============================================================================

@user_router.post("/password/reset-request", response_model=TokenResponse, tags=["Recuperación"])
async def request_password_reset(
    reset_request: PasswordResetRequest,
    db: Session = Depends(get_db)
):
    """
    Solicitar reset de contraseña
    
    - **identifier**: Email o username del usuario
    """
    user = find_user_by_identifier(db, reset_request.identifier)
    
    if not user:
        # Por seguridad, siempre retornar éxito
        return TokenResponse(message="Si el usuario existe, se enviará email de recuperación")
    
    if not user.email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Usuario sin email configurado"
        )
    
    # Crear token de reset
    reset_token = create_security_token(db, user.id, "reset_password", 24)
    
    # TODO: Enviar email con enlace de reset
    print(f"Token reset password para {user.email}: {reset_token}")
    
    return TokenResponse(
        message="Email de recuperación enviado",
        expires_in=24 * 60 * 60  # 24 horas
    )

@user_router.post("/password/reset-confirm", response_model=MessageResponse)
async def confirm_password_reset(
    reset_confirm: PasswordReset,
    db: Session = Depends(get_db)
):
    """
    Confirmar reset de contraseña con token
    
    - **token**: Token recibido por email
    - **new_password**: Nueva contraseña
    - **confirm_password**: Confirmación de nueva contraseña
    """
    user_id = verify_security_token(db, reset_confirm.token, "reset_password")
    
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token inválido o expirado"
        )
    
    if not update_user_password(db, user_id, reset_confirm.new_password):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al actualizar contraseña"
        )
    
    return MessageResponse(message="Contraseña actualizada exitosamente")

@user_router.post("/password/change", response_model=MessageResponse)
async def change_password(
    password_change: PasswordChange,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Cambiar contraseña (usuario autenticado)
    
    - **current_password**: Contraseña actual
    - **new_password**: Nueva contraseña
    - **confirm_password**: Confirmación de nueva contraseña
    """
    from api.auth_service import verify_password
    
    if not current_user.password_hash:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Usuario sin contraseña configurada"
        )
    
    if not verify_password(password_change.current_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Contraseña actual incorrecta"
        )
    
    if not update_user_password(db, current_user.id, password_change.new_password):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al actualizar contraseña"
        )
    
    return MessageResponse(message="Contraseña cambiada exitosamente")

# ============================================================================
# ENDPOINTS DE GESTIÓN DE USUARIO
# ============================================================================

@user_router.get("/me", response_model=UsuarioResponse)
async def get_current_user_info(current_user: Usuario = Depends(get_current_user)):
    """
    Obtener información del usuario actual
    """
    return UsuarioResponse(
        id=current_user.id,
        username=current_user.username,
        nombre_completo=current_user.nombre_completo,
        email=current_user.email,
        telefono=current_user.telefono,
        # documento_identidad=current_user.documento_identidad,
        es_activo=current_user.estado,
        rol=current_user.rol,
        autenticacion_tipo=current_user.autenticacion_tipo,
        fecha_creacion=current_user.creado_en,
        ultimo_login=current_user.ultimo_login
    )

@user_router.put("/me", response_model=UsuarioResponse)
async def update_current_user(
    user_update: UsuarioUpdate,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Actualizar información del usuario actual
    """
    try:
        # Actualizar campos permitidos
        for field, value in user_update.dict(exclude_unset=True).items():
            if hasattr(current_user, field):
                setattr(current_user, field, value)
        
        current_user.actualizado_en = datetime.utcnow()
        db.commit()
        db.refresh(current_user)
        
        return usuario_to_response(current_user)
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Error al actualizar usuario"
        )

@user_router.delete("/me", response_model=MessageResponse)
async def delete_current_user(
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Eliminar cuenta del usuario actual
    """
    # Desactivar en lugar de eliminar completamente
    current_user.estado = False
    current_user.actualizado_en = datetime.utcnow()
    db.commit()
    
    return MessageResponse(message="Cuenta desactivada exitosamente")

# ============================================================================
# ENDPOINTS DE ADMINISTRACIÓN (Solo Admins)
# ============================================================================

@user_router.get("/", response_model=UserListResponse)
async def list_users(
    pagination: PaginationParams = Depends(),
    admin_user: Usuario = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """
    Listar todos los usuarios (Solo administradores)
    """
    # Calcular offset
    offset = (pagination.page - 1) * pagination.per_page
    
    total = db.query(Usuario).count()
    users = db.query(Usuario).offset(offset).limit(pagination.per_page).all()
    
    pages = (total + pagination.per_page - 1) // pagination.per_page
    
    return UserListResponse(
        users=[usuario_to_response(user) for user in users],
        total=total,
        page=pagination.page,
        per_page=pagination.per_page,
        pages=pages
    )

@user_router.get("/{user_id}", response_model=UsuarioResponse)
async def get_user(
    user_id: str,
    admin_user: Usuario = Depends(get_manager_user),
    db: Session = Depends(get_db)
):
    """
    Obtener usuario por ID (Jefes y superiores)
    """
    user = db.query(Usuario).filter(Usuario.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado"
        )
    
    return usuario_to_response(user)

@user_router.put("/{user_id}", response_model=UsuarioResponse)
async def update_user(
    user_id: str,
    user_update: UsuarioUpdate,
    admin_user: Usuario = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """
    Actualizar usuario por ID (Solo administradores)
    """
    user = db.query(Usuario).filter(Usuario.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado"
        )
    
    try:
        for field, value in user_update.dict(exclude_unset=True).items():
            if hasattr(user, field):
                setattr(user, field, value)
        
        user.actualizado_en = datetime.utcnow()
        db.commit()
        db.refresh(user)
        
        return usuario_to_response(user)
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Error al actualizar usuario"
        )

@user_router.delete("/{user_id}", response_model=MessageResponse)
async def delete_user(
    user_id: str,
    admin_user: Usuario = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """
    Eliminar usuario por ID (Solo administradores)
    """
    user = db.query(Usuario).filter(Usuario.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado"
        )
    
    # Desactivar en lugar de eliminar
    user.estado = False
    user.actualizado_en = datetime.utcnow()
    db.commit()
    
    return MessageResponse(message=f"Usuario {user.username} desactivado exitosamente")


# ============================================================================
# ENDPOINTS DE TESTING Y DEMOS (Para facilitar pruebas)
# ============================================================================

@user_router.post("/demo/register", response_model=UsuarioResponse, tags=["Testing & Demos"])
async def demo_register_user(
    user_data: UsuarioCreateDemo,
    db: Session = Depends(get_db)
):
    """
    **ENDPOINT DE DEMO**: Registro con datos predefinidos
    
    Facilita el testing al proporcionar datos de ejemplo automáticamente.
    Perfecto para pruebas rápidas sin necesidad de completar formularios.
    
    **Datos incluidos automáticamente:**
    - Nombre: Juan Carlos Pérez García
    - Email: juan.perez@ejemplo.com  
    - Teléfono: +57 300 123 4567
    - Username: juan_perez123
    - Documento: 12345678
    - Password: Demo123456 (8+ caracteres)
    
    **¿Cómo usar?**
    1. Haz click en "Try it out"
    2. Los campos se llenan automáticamente
    3. Modifica lo que necesites o deja los valores por defecto
    4. Ejecuta para crear usuario demo
    """
    try:
        # Convertir demo data a formato estándar
        standard_data = UsuarioCreate(**user_data.dict())
        new_user = create_user(db, standard_data)
        
        # Simular verificación automática para demo
        new_user.verificado = True
        db.commit()
        
        return usuario_to_response(new_user)
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Demo Error: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error en registro demo"
        )


@user_router.post("/demo/login", response_model=TokenResponse, tags=["Testing & Demos"])
async def demo_login(
    credentials: LoginCredentialsDemo,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    **ENDPOINT DE DEMO**: Login con credenciales predefinidas
    
    Facilita el testing de autenticación con datos de ejemplo automáticos.
    
    **Credenciales por defecto:**
    - Email: juan.perez@ejemplo.com
    - Password: Demo123456 (8+ caracteres)
    - Tipo: email
    
    **¿Cómo usar?**
    1. Primero crear usuario con `/demo/register`
    2. Usar este endpoint con credenciales predefinidas
    3. Copiar el access_token de la respuesta
    4. Usar "Authorize" con: `Bearer tu_token`
    
    **Flujo completo de testing:**
    1. Demo Register → 2. Demo Login → 3. Authorize → 4. Test endpoints
    """
    try:
        # Convertir demo credentials a formato estándar
        standard_credentials = LoginCredentials(**credentials.dict())
        user = authenticate_user(db, standard_credentials)
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Credenciales demo incorrectas. ¿Creaste el usuario demo primero?"
            )
        
        # Generar tokens
        tokens = generate_tokens_for_user(user)
        
        client_ip = request.client.host
        print(f"Demo Login exitoso: {user.username} desde {client_ip}")
        
        return TokenResponse(
            **tokens,
            user_id=user.id,
            username=user.username
        )
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Demo Error: {str(e)}"
        )


@user_router.get("/demo/test-data", response_model=TestDataSets, tags=["Testing & Demos"])
async def get_demo_test_data():
    """
    **DATOS DE PRUEBA**: Conjuntos de datos para diferentes escenarios
    
    Proporciona ejemplos de datos estructurados para facilitar el testing
    manual y automatizado de todos los endpoints.
    
    **Incluye:**
    - Datos de usuario completo para registro
    - Credenciales para login
    - Ejemplos de diferentes roles y tipos de autenticación
    - Datos para testing de validaciones
    
    **¿Cómo usar?**
    1. Consulta este endpoint para ver ejemplos
    2. Copia los datos que necesites
    3. Úsalos en otros endpoints para testing
    4. Modifica según tus casos de prueba
    """
    return TestDataSets()


@user_router.get("/demo/validation-examples", response_model=Dict[str, Any], tags=["Testing & Demos"])
async def get_validation_examples():
    """
    **EJEMPLOS DE VALIDACIÓN**: Casos de éxito y error para testing
    
    Proporciona ejemplos específicos para probar todas las validaciones
    implementadas en los esquemas.
    
    **Incluye:**
    - Datos válidos que pasan todas las validaciones
    - Datos inválidos para probar manejo de errores
    - Casos edge para testing exhaustivo
    """
    return {
        "valid_examples": {
            "email_formats": [
                "usuario@ejemplo.com",
                "test.email+tag@domain.co",
                "admin@municipio.gov.co"
            ],
            "phone_formats": [
                "+57 300 123 4567",
                "+57 310 987 6543",
                "+573201234567"
            ],
            "passwords": [
                "SecurePass123",
                "MyPassword456!",
                "Demo123456"
            ],
            "usernames": [
                "usuario_123",
                "admin_municipal",
                "test_user"
            ]
        },
        "invalid_examples": {
            "email_formats": [
                "email_sin_arroba.com",
                "sin_dominio@",
                "@sin_usuario.com"
            ],
            "phone_formats": [
                "123456789",  # Sin código país
                "+1 234 567 8900",  # País incorrecto
                "abc def ghij"  # Letras
            ],
            "passwords": [
                "123456",  # Muy corta
                "password",  # Sin números
                "PASSWORD123"  # Sin minúsculas
            ],
            "usernames": [
                "ab",  # Muy corto
                "usuario con espacios",  # Espacios
                "user@special"  # Caracteres especiales
            ]
        },
        "edge_cases": {
            "empty_fields": {
                "email": "",
                "telefono": None,
                "username": ""
            },
            "max_length": {
                "nombre_completo": "A" * 151,  # Excede límite
                "password": "B" * 129  # Excede límite
            },
            "special_characters": {
                "nombre_acentos": "José María Ñuñez",
                "telefono_caracteres": "+57-300-123-4567"
            }
        }
    }


# ============================================================================
# ENDPOINTS DE SESIONES Y AUDITORÍA
# ============================================================================

@user_router.get("/me/sessions", response_model=List[SessionInfo])
async def get_my_sessions(current_user: Usuario = Depends(get_current_user)):
    """
    Obtener sesiones activas del usuario actual
    """
    # TODO: Implementar cuando se cree tabla de sesiones
    return []

@user_router.delete("/me/sessions/{session_id}", response_model=MessageResponse)
async def terminate_session(
    session_id: str,
    current_user: Usuario = Depends(get_current_user)
):
    """
    Terminar sesión específica
    """
    # TODO: Implementar cuando se cree tabla de sesiones
    return MessageResponse(message="Sesión terminada exitosamente")

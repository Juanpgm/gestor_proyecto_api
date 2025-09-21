"""
Servicios de autenticación y seguridad
Gestión de Datos de Usuario
"""
import hashlib
import secrets
import jwt
from datetime import datetime, timedelta
from typing import Optional, Union, Dict, Any, Tuple
from functools import lru_cache, wraps
from sqlalchemy.orm import Session
from sqlalchemy import or_
import bcrypt
import re

from api.models import Usuario, TokenSeguridad, Rol
from api.schemas import UsuarioCreate, LoginCredentials
from config import get_database_config

# ============================================================================
# CONFIGURACIÓN DE SEGURIDAD
# ============================================================================

@lru_cache(maxsize=1)
def get_security_config() -> Dict[str, Any]:
    """Configuración de seguridad con cache"""
    config = get_database_config()
    return {
        "secret_key": config.get("JWT_SECRET_KEY", "your-secret-key-here-change-in-production"),
        "algorithm": "HS256",
        "access_token_expire_minutes": 30,
        "refresh_token_expire_days": 7,
        "password_reset_expire_hours": 24,
        "phone_verification_expire_minutes": 10,
        "max_login_attempts": 5,
        "lockout_duration_minutes": 15
    }

# ============================================================================
# FUNCIONES DE HASH Y VERIFICACIÓN
# ============================================================================

def hash_password(password: str) -> str:
    """
    Hash de contraseña usando bcrypt
    Función pura que retorna hash seguro
    """
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

def verify_password(password: str, hashed: str) -> bool:
    """
    Verificar contraseña contra hash
    Función pura que retorna True si coincide
    """
    try:
        return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))
    except Exception:
        return False

def generate_secure_token(length: int = 32) -> str:
    """
    Generar token seguro aleatorio
    Función pura que retorna token hexadecimal
    """
    return secrets.token_hex(length)

def generate_phone_code() -> str:
    """
    Generar código de verificación telefónico
    Función pura que retorna código de 6 dígitos
    """
    return f"{secrets.randbelow(900000) + 100000}"

# ============================================================================
# FUNCIONES JWT
# ============================================================================

def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """
    Crear token JWT de acceso
    Función pura que retorna token JWT
    """
    config = get_security_config()
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=config["access_token_expire_minutes"])
    
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, config["secret_key"], algorithm=config["algorithm"])

def create_refresh_token(data: Dict[str, Any]) -> str:
    """
    Crear token JWT de refresh
    Función pura que retorna refresh token
    """
    config = get_security_config()
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=config["refresh_token_expire_days"])
    to_encode.update({"exp": expire, "type": "refresh"})
    
    return jwt.encode(to_encode, config["secret_key"], algorithm=config["algorithm"])

def verify_token(token: str, token_type: str = "access") -> Optional[Dict[str, Any]]:
    """
    Verificar y decodificar token JWT
    Función pura que retorna payload o None
    """
    try:
        config = get_security_config()
        payload = jwt.decode(token, config["secret_key"], algorithms=[config["algorithm"]])
        
        if payload.get("type") != token_type:
            return None
            
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.JWTError:
        return None

# ============================================================================
# FUNCIONES DE VALIDACIÓN
# ============================================================================

def validate_identifier(identifier: str) -> Tuple[str, str]:
    """
    Validar identificador y determinar tipo (email, phone, username)
    Función pura que retorna (tipo, identificador_limpio)
    """
    identifier = identifier.strip().lower()
    
    # Verificar si es email
    email_pattern = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
    if email_pattern.match(identifier):
        return ("email", identifier)
    
    # Verificar si es teléfono
    phone_pattern = re.compile(r'^(\+57|57)?[0-9]{10}$')
    clean_phone = identifier.replace(' ', '').replace('-', '').replace('(', '').replace(')', '')
    if phone_pattern.match(clean_phone):
        # Normalizar formato de teléfono
        if clean_phone.startswith('+57'):
            return ("telefono", clean_phone)
        elif clean_phone.startswith('57'):
            return ("telefono", f"+{clean_phone}")
        else:
            return ("telefono", f"+57{clean_phone}")
    
    # Debe ser username
    username_pattern = re.compile(r'^[a-zA-Z0-9_]{3,50}$')
    if username_pattern.match(identifier):
        return ("username", identifier)
    
    raise ValueError("Identificador inválido: debe ser email, teléfono o username válido")

def is_password_strong(password: str) -> Tuple[bool, list]:
    """
    Validar fortaleza de contraseña
    Función pura que retorna (es_fuerte, lista_errores)
    """
    errors = []
    
    if len(password) < 8:
        errors.append("Debe tener al menos 8 caracteres")
    
    if not re.search(r'[A-Z]', password):
        errors.append("Debe contener al menos una mayúscula")
    
    if not re.search(r'[a-z]', password):
        errors.append("Debe contener al menos una minúscula")
    
    if not re.search(r'[0-9]', password):
        errors.append("Debe contener al menos un número")
    
    if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        errors.append("Se recomienda al menos un carácter especial")
    
    return len(errors) == 0, errors

# ============================================================================
# FUNCIONES DE BASE DE DATOS PARA USUARIOS
# ============================================================================

def find_user_by_identifier(db: Session, identifier: str) -> Optional[Usuario]:
    """
    Buscar usuario por email, teléfono o username
    Función que retorna Usuario o None
    """
    try:
        id_type, clean_identifier = validate_identifier(identifier)
        
        if id_type == "email":
            return db.query(Usuario).filter(Usuario.email == clean_identifier).first()
        elif id_type == "telefono":
            # Buscar por formato normalizado primero
            user = db.query(Usuario).filter(Usuario.telefono == clean_identifier).first()
            if user:
                return user
            
            # Si no se encuentra, probar formatos alternativos
            # Generar variaciones del teléfono para búsqueda flexible
            phone_variations = []
            
            # Si el identificador normalizado tiene +57, probar sin él
            if clean_identifier.startswith('+57'):
                # +573195359999 -> 3195359999
                phone_variations.append(clean_identifier[3:])
                # +573195359999 -> 573195359999  
                phone_variations.append(clean_identifier[1:])
            elif clean_identifier.startswith('57'):
                # 573195359999 -> +573195359999
                phone_variations.append(f'+{clean_identifier}')
                # 573195359999 -> 3195359999
                phone_variations.append(clean_identifier[2:])
            else:
                # 3195359999 -> +573195359999
                phone_variations.append(f'+57{clean_identifier}')
                # 3195359999 -> 573195359999
                phone_variations.append(f'57{clean_identifier}')
            
            # Buscar con cada variación
            for variation in phone_variations:
                user = db.query(Usuario).filter(Usuario.telefono == variation).first()
                if user:
                    return user
            
            return None
        elif id_type == "username":
            return db.query(Usuario).filter(Usuario.username == clean_identifier).first()
    except ValueError:
        return None
    
    return None

def check_user_exists(db: Session, username: str = None, email: str = None, telefono: str = None) -> bool:
    """
    Verificar si usuario ya existe
    Función pura que retorna bool
    """
    query = db.query(Usuario)
    conditions = []
    
    if username:
        conditions.append(Usuario.username == username.lower())
    if email:
        conditions.append(Usuario.email == email.lower())
    if telefono:
        # Normalizar formato de teléfono
        try:
            _, clean_phone = validate_identifier(telefono)
            conditions.append(Usuario.telefono == clean_phone)
        except ValueError:
            pass
    
    if conditions:
        return query.filter(or_(*conditions)).first() is not None
    
    return False

def create_user(db: Session, user_data: UsuarioCreate) -> Usuario:
    """
    Crear nuevo usuario en la base de datos
    Función que retorna Usuario creado
    """
    # Verificar que no existe usuario duplicado
    if check_user_exists(db, user_data.username, user_data.email, user_data.telefono):
        raise ValueError("Ya existe un usuario con ese username, email o teléfono")
    
    # Normalizar datos
    username = user_data.username.lower()
    email = user_data.email.lower() if user_data.email else None
    
    # Normalizar teléfono si existe
    telefono = None
    if user_data.telefono:
        try:
            _, telefono = validate_identifier(user_data.telefono)
        except ValueError:
            raise ValueError("Formato de teléfono inválido")
    
    # Hash de contraseña
    password_hash = hash_password(user_data.password)
    
    # Usar nombre completo directamente
    nombre_completo = user_data.nombre_completo
    
    # Crear usuario
    new_user = Usuario(
        username=username,
        nombre_completo=nombre_completo,
        email=email,
        telefono=telefono,
        # documento_identidad=getattr(user_data, 'documento_identidad', None),
        nombre_centro_gestor=getattr(user_data, 'nombre_centro_gestor', None),
        foto_url=getattr(user_data, 'foto_url', None),
        password_hash=password_hash,
        autenticacion_tipo=user_data.autenticacion_tipo,
        rol=user_data.rol,
        verificado=False  # Requiere verificación
    )
    
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    return new_user

def authenticate_user(db: Session, credentials: LoginCredentials) -> Optional[Usuario]:
    """
    Autenticar usuario con credenciales
    Función que retorna Usuario autenticado o None
    """
    user = find_user_by_identifier(db, credentials.identifier)
    
    if not user:
        return None
    
    if not user.estado:
        raise ValueError("Cuenta desactivada")
    
    if user.autenticacion_tipo != 'local':
        raise ValueError(f"Usuario configurado para autenticación {user.autenticacion_tipo}")
    
    if not user.password_hash:
        raise ValueError("Usuario sin contraseña configurada")
    
    if not verify_password(credentials.password, user.password_hash):
        return None
    
    # Actualizar último login
    user.ultimo_login = datetime.utcnow()
    db.commit()
    
    return user

def update_user_password(db: Session, user_id: str, new_password: str) -> bool:
    """
    Actualizar contraseña de usuario
    Función que retorna True si exitoso
    """
    user = db.query(Usuario).filter(Usuario.id == user_id).first()
    if not user:
        return False
    
    user.password_hash = hash_password(new_password)
    db.commit()
    
    return True

# ============================================================================
# FUNCIONES DE TOKENS DE SEGURIDAD
# ============================================================================

def create_security_token(db: Session, user_id: str, token_type: str, duration_hours: int = 24) -> str:
    """
    Crear token de seguridad (reset password, verificación, etc.)
    Función que retorna token string
    """
    # Invalidar tokens anteriores del mismo tipo
    db.query(TokenSeguridad).filter(
        TokenSeguridad.usuario_id == user_id,
        TokenSeguridad.tipo == token_type,
        TokenSeguridad.usado == False
    ).update({"usado": True})
    
    # Crear nuevo token
    token_string = generate_secure_token()
    hashed_token = hashlib.sha256(token_string.encode()).hexdigest()
    
    expiration = datetime.utcnow() + timedelta(hours=duration_hours)
    
    security_token = TokenSeguridad(
        usuario_id=user_id,
        token=hashed_token,
        tipo=token_type,
        expiracion=expiration
    )
    
    db.add(security_token)
    db.commit()
    
    return token_string

def verify_security_token(db: Session, token_string: str, token_type: str) -> Optional[str]:
    """
    Verificar token de seguridad y retornar user_id
    Función que retorna user_id o None
    """
    hashed_token = hashlib.sha256(token_string.encode()).hexdigest()
    
    token = db.query(TokenSeguridad).filter(
        TokenSeguridad.token == hashed_token,
        TokenSeguridad.tipo == token_type,
        TokenSeguridad.usado == False,
        TokenSeguridad.expiracion > datetime.utcnow()
    ).first()
    
    if token:
        # Marcar como usado
        token.usado = True
        db.commit()
        return token.usuario_id
    
    return None

# ============================================================================
# FUNCIONES DE AUTENTICACIÓN GOOGLE
# ============================================================================

def verify_google_token(google_token: str) -> Optional[Dict[str, Any]]:
    """
    Verificar token de Google OAuth
    Función que retorna info del usuario o None
    
    NOTA: Esta es una función stub. En producción, usar google-auth library
    """
    # TODO: Implementar verificación real con Google OAuth
    # from google.oauth2 import id_token
    # from google.auth.transport import requests
    
    # try:
    #     idinfo = id_token.verify_oauth2_token(google_token, requests.Request(), GOOGLE_CLIENT_ID)
    #     return {
    #         'google_id': idinfo['sub'],
    #         'email': idinfo['email'],
    #         'name': idinfo['name'],
    #         'picture': idinfo.get('picture')
    #     }
    # except ValueError:
    #     return None
    
    # Por ahora retorna None para indicar que necesita implementación
    return None

def find_or_create_google_user(db: Session, google_info: Dict[str, Any]) -> Usuario:
    """
    Buscar o crear usuario con información de Google
    Función que retorna Usuario
    """
    # Buscar usuario existente por Google ID
    user = db.query(Usuario).filter(Usuario.google_id == google_info['google_id']).first()
    
    if user:
        # Actualizar último login
        user.ultimo_login = datetime.utcnow()
        db.commit()
        return user
    
    # Buscar por email
    user = db.query(Usuario).filter(Usuario.email == google_info['email']).first()
    
    if user:
        # Vincular cuenta de Google
        user.google_id = google_info['google_id']
        user.autenticacion_tipo = 'google'
        user.verificado = True
        user.ultimo_login = datetime.utcnow()
        db.commit()
        return user
    
    # Crear nuevo usuario
    username = google_info['email'].split('@')[0]
    # Asegurar username único
    base_username = username
    counter = 1
    while check_user_exists(db, username=username):
        username = f"{base_username}{counter}"
        counter += 1
    
    new_user = Usuario(
        username=username,
        nombre_completo=google_info['name'],
        email=google_info['email'],
        google_id=google_info['google_id'],
        foto_url=google_info.get('picture'),
        autenticacion_tipo='google',
        verificado=True,
        rol=1  # Usuario básico por defecto
    )
    
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    return new_user

# ============================================================================
# FUNCIONES AUXILIARES
# ============================================================================

def generate_tokens_for_user(user: Usuario) -> Dict[str, Any]:
    """
    Generar tokens JWT para usuario autenticado
    Función pura que retorna diccionario con tokens
    """
    config = get_security_config()
    
    token_data = {
        "sub": user.id,
        "username": user.username,
        "rol": user.rol
    }
    
    access_token = create_access_token(token_data)
    refresh_token = create_refresh_token({"sub": user.id})
    
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": config["access_token_expire_minutes"] * 60
    }

def check_user_permissions(user: Usuario, required_role: int) -> bool:
    """
    Verificar permisos de usuario
    Función pura que retorna bool
    """
    return user.es_activo and user.es_verificado and user.rol >= required_role
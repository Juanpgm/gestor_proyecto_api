"""
Configuración de la base de datos refactorizada con programación funcional
Conexión optimizada para PostgreSQL con soporte múltiples entornos
"""
import os
from typing import Iterator, Optional
from functools import lru_cache
from dotenv import load_dotenv
from sqlalchemy import create_engine, Engine, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session

# Importar la base y modelos de api/models.py
from api.models import Base

# ============================================================================
# CONFIGURACIÓN FUNCIONAL DE ENTORNO
# ============================================================================

@lru_cache(maxsize=1)
def get_environment() -> str:
    """Obtener entorno actual con cache"""
    return os.getenv("ENVIRONMENT", "local")

def load_environment_config() -> None:
    """Cargar configuración según el entorno"""
    env = get_environment()
    
    if env == "railway":
        load_dotenv(".env.railway")
    elif env == "local":
        load_dotenv(".env.local")
    else:
        load_dotenv()

# ============================================================================
# CONFIGURACIÓN FUNCIONAL DE BASE DE DATOS
# ============================================================================

@lru_cache(maxsize=1)
def get_database_config() -> dict:
    """Obtener configuración de base de datos con cache"""
    load_environment_config()
    
    return {
        "host": os.getenv("DB_HOST", "localhost"),
        "port": os.getenv("DB_PORT", "5432"),
        "name": os.getenv("DB_NAME", "dev"),
        "user": os.getenv("DB_USER", "postgres"),
        "password": os.getenv("DB_PASSWORD", "root"),
        "schema": os.getenv("DB_SCHEMA", "public"),
        "railway_url": os.getenv("DATABASE_URL"),
        "connection_timeout": int(os.getenv("CONNECTION_TIMEOUT", "30")),
        "pool_size": int(os.getenv("POOL_SIZE", "5")),
        "max_overflow": int(os.getenv("MAX_OVERFLOW", "10")),
        # Configuración JWT y Seguridad
        "JWT_SECRET_KEY": os.getenv("JWT_SECRET_KEY", "your-secret-key-here-change-in-production"),
        "JWT_ALGORITHM": os.getenv("JWT_ALGORITHM", "HS256"),
        "JWT_ACCESS_TOKEN_EXPIRE_MINUTES": int(os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "1440")),
        # Configuración Google OAuth
        "GOOGLE_CLIENT_ID": os.getenv("GOOGLE_CLIENT_ID"),
        "GOOGLE_CLIENT_SECRET": os.getenv("GOOGLE_CLIENT_SECRET"),
        # Configuración SMTP
        "SMTP_SERVER": os.getenv("SMTP_SERVER", "smtp.gmail.com"),
        "SMTP_PORT": int(os.getenv("SMTP_PORT", "587")),
        "SMTP_USER": os.getenv("SMTP_USER"),
        "SMTP_PASSWORD": os.getenv("SMTP_PASSWORD")
    }

def build_database_url() -> str:
    """Construir URL de base de datos según el entorno"""
    config = get_database_config()
    env = get_environment()
    
    if env == "railway" and config["railway_url"]:
        print(f"Conectando a Railway: {config['railway_url'][:50]}...")
        return config["railway_url"]
    else:
        url = f"postgresql://{config['user']}:{config['password']}@{config['host']}:{config['port']}/{config['name']}"
        print(f"Conectando a BD local: {url}")
        return url

@lru_cache(maxsize=1)
def create_database_engine() -> Engine:
    """Crear motor de base de datos con cache"""
    config = get_database_config()
    database_url = build_database_url()
    
    print(f"Entorno actual: {get_environment().upper()}")
    
    return create_engine(
        database_url,
        pool_size=config["pool_size"],
        max_overflow=config["max_overflow"],
        pool_timeout=config["connection_timeout"],
        pool_recycle=3600,
        echo=False
    )

# ============================================================================
# INSTANCIAS GLOBALES
# ============================================================================

# Motor de base de datos
engine = create_database_engine()

# Configuración de la sesión
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# ============================================================================
# DEPENDENCIAS FUNCIONALES
# ============================================================================

def get_db() -> Iterator[Session]:
    """
    Dependencia funcional para obtener sesión de base de datos
    Usa context manager para garantizar cierre de conexión
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_db_session() -> Session:
    """
    Función helper para obtener sesión directa (para uso interno)
    """
    return SessionLocal()

def test_database_connection() -> bool:
    """
    Probar conexión a la base de datos
    Returns: True si conexión exitosa, False en caso contrario
    """
    try:
        with engine.connect() as connection:
            result = connection.execute(text("SELECT 1")).scalar()
            return result == 1
    except Exception as e:
        print(f"Error conectando a la base de datos: {e}")
        return False

# ============================================================================
# CONFIGURACIÓN ADICIONAL
# ============================================================================

def get_database_url() -> str:
    """Obtener URL de base de datos para uso externo"""
    return build_database_url()

# Mantener compatibilidad con imports existentes
DATABASE_URL = build_database_url()
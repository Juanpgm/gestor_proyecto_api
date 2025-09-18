"""
Configuración de la base de datos y variables de entorno
Soporte para múltiples entornos: local y Railway
"""
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Determinar el entorno y cargar el archivo .env correspondiente
ENV = os.getenv("ENVIRONMENT", "local")

if ENV == "railway":
    load_dotenv(".env.railway")
elif ENV == "local":
    load_dotenv(".env.local")
else:
    # Fallback al .env original
    load_dotenv()

# Variables de configuración de la base de datos
# Configuración para Railway (usa DATABASE_URL directamente)
DATABASE_URL_RAILWAY = os.getenv("DATABASE_URL")

# Configuración para local (construye URL a partir de componentes)
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "dev")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "root")
DB_SCHEMA = os.getenv("DB_SCHEMA", "public")

# Configuración de conexión
CONNECTION_TIMEOUT = int(os.getenv("CONNECTION_TIMEOUT", "30"))
POOL_SIZE = int(os.getenv("POOL_SIZE", "5"))
MAX_OVERFLOW = int(os.getenv("MAX_OVERFLOW", "10"))

# Determinar la URL de conexión según el entorno
if ENV == "railway":
    # En Railway, DATABASE_URL viene como variable de entorno
    DATABASE_URL_RAILWAY = os.getenv("DATABASE_URL")
    if DATABASE_URL_RAILWAY:
        DATABASE_URL = DATABASE_URL_RAILWAY
        print(f"🚀 Conectando a Railway: {DATABASE_URL_RAILWAY[:50]}...")
    else:
        print("❌ DATABASE_URL no encontrada en variables de entorno de Railway")
        raise ValueError("DATABASE_URL requerida para entorno Railway")
else:
    # URL de conexión a PostgreSQL local
    DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    print(f"🏠 Conectando a BD local: {DATABASE_URL}")

print(f"🌍 Entorno actual: {ENV.upper()}")

# Configuración del motor de SQLAlchemy
engine = create_engine(
    DATABASE_URL,
    pool_size=POOL_SIZE,
    max_overflow=MAX_OVERFLOW,
    pool_timeout=CONNECTION_TIMEOUT,
    pool_recycle=3600,  # Reciclar conexiones cada hora
    echo=False  # Cambiar a True para ver las consultas SQL en desarrollo
)

# Configuración de la sesión
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base para los modelos
Base = declarative_base()

def get_db():
    """
    Dependencia para obtener una sesión de base de datos
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
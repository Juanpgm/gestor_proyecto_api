#!/bin/bash
# Script de despliegue RAILWAY para Unix/Linux/macOS
# deploy_railway.sh

set -e

PORT=${1:-8000}
HOST=${2:-0.0.0.0}
TEST=${3:-false}

echo "🚀 === DESPLIEGUE RAILWAY - API Gestor de Proyectos ==="
echo ""

# Configurar variables de entorno para Railway
export ENVIRONMENT="railway"
echo "🌍 Entorno configurado: RAILWAY"

# Verificar que existe el archivo .env.railway
if [ ! -f ".env.railway" ]; then
    echo "❌ Error: No se encontró el archivo .env.railway"
    echo "   Asegúrate de que existe y tiene la configuración correcta"
    exit 1
fi

# Verificar que existe el entorno virtual
if [ ! -f "env/bin/activate" ]; then
    echo "❌ Error: No se encontró el entorno virtual en 'env'"
    echo "   Ejecuta: python -m venv env"
    exit 1
fi

echo "🔧 Activando entorno virtual..."
source env/bin/activate
echo "✅ Entorno virtual activado"

echo "📦 Instalando dependencias..."
pip install -r requirements.txt
echo "✅ Dependencias instaladas"

if [ "$TEST" = "true" ]; then
    echo "🧪 Modo de prueba: verificando configuración..."
    
    # Test de conexión a Railway
    echo "🔗 Verificando conexión a Railway..."
    python -c "
from config import DATABASE_URL, ENV
print(f'Entorno: {ENV}')
print(f'DATABASE_URL configurada: {DATABASE_URL[:50] if DATABASE_URL else \"No configurada\"}...')

from sqlalchemy import create_engine, text
engine = create_engine(DATABASE_URL)
with engine.connect() as conn:
    result = conn.execute(text('SELECT 1')).scalar()
    print('✅ Conexión a Railway exitosa')
"
    echo "✅ Configuración Railway verificada"
    echo "🎯 Test completado. Usa el script sin el tercer parámetro 'true' para iniciar el servidor"
    exit 0
fi

# Configurar parámetros de uvicorn para producción
UVICORN_ARGS="main:app --host $HOST --port $PORT --workers 1 --log-level info"

echo ""
echo "🚀 Iniciando servidor para Railway..."
echo "📍 Host: $HOST"
echo "🔌 Puerto: $PORT"
echo "🌐 Modo: Producción"
echo ""
echo "Presiona Ctrl+C para detener el servidor"
echo ""

uvicorn $UVICORN_ARGS
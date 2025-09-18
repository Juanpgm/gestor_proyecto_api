#!/bin/bash
# Script de despliegue LOCAL para Unix/Linux/macOS
# deploy_local.sh

set -e

PORT=${1:-8001}
RELOAD=${2:-false}
DEBUG=${3:-false}

echo "🏠 === DESPLIEGUE LOCAL - API Gestor de Proyectos ==="
echo ""

# Configurar variables de entorno
export ENVIRONMENT="local"
echo "🌍 Entorno configurado: LOCAL"

# Verificar que existe el archivo .env.local
if [ ! -f ".env.local" ]; then
    echo "❌ Error: No se encontró el archivo .env.local"
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

# Configurar parámetros de uvicorn
UVICORN_ARGS="main:app --host 127.0.0.1 --port $PORT"

if [ "$RELOAD" = "true" ]; then
    UVICORN_ARGS="$UVICORN_ARGS --reload"
    echo "🔄 Modo reload activado"
fi

if [ "$DEBUG" = "true" ]; then
    UVICORN_ARGS="$UVICORN_ARGS --log-level debug"
    echo "🐛 Modo debug activado"
fi

echo ""
echo "🚀 Iniciando servidor local..."
echo "📍 URL: http://127.0.0.1:$PORT"
echo "📚 Docs: http://127.0.0.1:$PORT/docs"
echo "🔧 Health: http://127.0.0.1:$PORT/health"
echo ""
echo "Presiona Ctrl+C para detener el servidor"
echo ""

uvicorn $UVICORN_ARGS
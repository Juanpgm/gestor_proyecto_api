#!/bin/bash
# Script de inicio para Railway que maneja correctamente la variable PORT

# Usar PORT de Railway o 8000 por defecto
export ACTUAL_PORT=${PORT:-8000}

echo "🚀 Iniciando API en puerto: $ACTUAL_PORT"

# Ejecutar uvicorn con el puerto correcto
exec uvicorn main:app --host 0.0.0.0 --port "$ACTUAL_PORT" --workers 1
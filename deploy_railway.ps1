#!/usr/bin/env powershell
# Script de despliegue RAILWAY para Windows PowerShell
# deploy_railway.ps1

param(
    [string]$Port = "8000",
    [string]$ServerHost = "0.0.0.0",
    [switch]$Test = $false
)

Write-Host "🚀 === DESPLIEGUE RAILWAY - API Gestor de Proyectos ===" -ForegroundColor Blue
Write-Host ""

# Configurar variables de entorno para Railway
$env:ENVIRONMENT = "railway"
Write-Host "🌍 Entorno configurado: RAILWAY" -ForegroundColor Yellow

# Verificar que existe el archivo .env.railway
if (-not (Test-Path ".env.railway")) {
    Write-Host "❌ Error: No se encontró el archivo .env.railway" -ForegroundColor Red
    Write-Host "   Asegúrate de que existe y tiene la configuración correcta" -ForegroundColor Red
    exit 1
}

# Verificar que existe el entorno virtual
if (-not (Test-Path "env\Scripts\activate.ps1")) {
    Write-Host "❌ Error: No se encontró el entorno virtual en 'env'" -ForegroundColor Red
    Write-Host "   Ejecuta: python -m venv env" -ForegroundColor Red
    exit 1
}

Write-Host "🔧 Activando entorno virtual..." -ForegroundColor Cyan
try {
    & .\env\Scripts\Activate.ps1
    Write-Host "✅ Entorno virtual activado" -ForegroundColor Green
}
catch {
    Write-Host "❌ Error activando entorno virtual: $_" -ForegroundColor Red
    exit 1
}

Write-Host "📦 Instalando dependencias..." -ForegroundColor Cyan
try {
    pip install -r requirements.txt
    Write-Host "✅ Dependencias instaladas" -ForegroundColor Green
}
catch {
    Write-Host "❌ Error instalando dependencias: $_" -ForegroundColor Red
    exit 1
}

if ($Test) {
    Write-Host "🧪 Modo de prueba: verificando configuración..." -ForegroundColor Yellow
    
    # Test de conexión a Railway
    Write-Host "🔗 Verificando conexión a Railway..." -ForegroundColor Cyan
    try {
        python -c "
from config import DATABASE_URL, ENV
print(f'Entorno: {ENV}')
print(f'DATABASE_URL configurada: {DATABASE_URL[:50] if DATABASE_URL else 'No configurada'}...')

from sqlalchemy import create_engine, text
engine = create_engine(DATABASE_URL)
with engine.connect() as conn:
    result = conn.execute(text('SELECT 1')).scalar()
    print('✅ Conexión a Railway exitosa')
"
        Write-Host "✅ Configuración Railway verificada" -ForegroundColor Green
    }
    catch {
        Write-Host "❌ Error en configuración Railway: $_" -ForegroundColor Red
        Write-Host "   Verifica el DATABASE_URL en .env.railway" -ForegroundColor Red
        exit 1
    }
    
    Write-Host "🎯 Test completado. Usa el script sin -Test para iniciar el servidor" -ForegroundColor Green
    exit 0
}

# Configurar parámetros de uvicorn para producción
$uvicornArgs = @(
    "main:app",
    "--host", $ServerHost,
    "--port", $Port,
    "--workers", "1",
    "--log-level", "info"
)

Write-Host ""
Write-Host "🚀 Iniciando servidor para Railway..." -ForegroundColor Green
Write-Host "📍 Host: $ServerHost" -ForegroundColor Cyan
Write-Host "🔌 Puerto: $Port" -ForegroundColor Cyan
Write-Host "🌐 Modo: Producción" -ForegroundColor Cyan
Write-Host ""
Write-Host "Presiona Ctrl+C para detener el servidor" -ForegroundColor Gray
Write-Host ""

try {
    uvicorn @uvicornArgs
}
catch {
    Write-Host "❌ Error ejecutando uvicorn: $_" -ForegroundColor Red
    exit 1
}
#!/usr/bin/env powershell
# Script de despliegue LOCAL para Windows PowerShell
# deploy_local.ps1

param(
    [string]$Port = "8001",
    [switch]$Reload = $false,
    [switch]$Debug = $false
)

Write-Host "🏠 === DESPLIEGUE LOCAL - API Gestor de Proyectos ===" -ForegroundColor Green
Write-Host ""

# Configurar variables de entorno
$env:ENVIRONMENT = "local"
Write-Host "🌍 Entorno configurado: LOCAL" -ForegroundColor Yellow

# Verificar que existe el archivo .env.local
if (-not (Test-Path ".env.local")) {
    Write-Host "❌ Error: No se encontró el archivo .env.local" -ForegroundColor Red
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

# Configurar parámetros de uvicorn
$uvicornArgs = @(
    "main:app",
    "--host", "127.0.0.1",
    "--port", $Port
)

if ($Reload) {
    $uvicornArgs += "--reload"
    Write-Host "🔄 Modo reload activado" -ForegroundColor Yellow
}

if ($Debug) {
    $uvicornArgs += "--log-level", "debug"
    Write-Host "🐛 Modo debug activado" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "🚀 Iniciando servidor local..." -ForegroundColor Green
Write-Host "📍 URL: http://127.0.0.1:$Port" -ForegroundColor Cyan
Write-Host "📚 Docs: http://127.0.0.1:$Port/docs" -ForegroundColor Cyan
Write-Host "🔧 Health: http://127.0.0.1:$Port/health" -ForegroundColor Cyan
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
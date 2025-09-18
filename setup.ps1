#!/usr/bin/env powershell
# Script de inicialización rápida del proyecto
# setup.ps1

param(
    [switch]$Local = $false,
    [switch]$Railway = $false,
    [switch]$Help = $false
)

if ($Help) {
    Write-Host "🚀 Setup Script - API Gestor de Proyectos" -ForegroundColor Green
    Write-Host ""
    Write-Host "Uso:" -ForegroundColor Yellow
    Write-Host "  .\setup.ps1 -Local      # Configurar para desarrollo local" -ForegroundColor White
    Write-Host "  .\setup.ps1 -Railway    # Configurar para Railway" -ForegroundColor White
    Write-Host "  .\setup.ps1 -Help       # Mostrar esta ayuda" -ForegroundColor White
    Write-Host ""
    exit 0
}

Write-Host "🛠️  === CONFIGURACIÓN INICIAL - API Gestor de Proyectos ===" -ForegroundColor Green
Write-Host ""

# Verificar si Python está instalado
try {
    $pythonVersion = python --version 2>&1
    Write-Host "✅ Python detectado: $pythonVersion" -ForegroundColor Green
}
catch {
    Write-Host "❌ Error: Python no está instalado o no está en PATH" -ForegroundColor Red
    Write-Host "   Instala Python desde https://python.org" -ForegroundColor Red
    exit 1
}

# Crear entorno virtual si no existe
if (-not (Test-Path "env")) {
    Write-Host "📦 Creando entorno virtual..." -ForegroundColor Cyan
    python -m venv env
    Write-Host "✅ Entorno virtual creado" -ForegroundColor Green
}
else {
    Write-Host "✅ Entorno virtual ya existe" -ForegroundColor Green
}

# Activar entorno virtual
Write-Host "🔧 Activando entorno virtual..." -ForegroundColor Cyan
try {
    & .\env\Scripts\Activate.ps1
    Write-Host "✅ Entorno virtual activado" -ForegroundColor Green
}
catch {
    Write-Host "❌ Error activando entorno virtual: $_" -ForegroundColor Red
    exit 1
}

# Instalar dependencias
Write-Host "📚 Instalando dependencias..." -ForegroundColor Cyan
try {
    pip install --upgrade pip
    pip install -r requirements.txt
    Write-Host "✅ Dependencias instaladas" -ForegroundColor Green
}
catch {
    Write-Host "❌ Error instalando dependencias: $_" -ForegroundColor Red
    exit 1
}

# Crear directorio de logs si no existe
if (-not (Test-Path "logs")) {
    New-Item -ItemType Directory -Path "logs"
    Write-Host "✅ Directorio de logs creado" -ForegroundColor Green
}

Write-Host ""
Write-Host "🎉 ¡Configuración completada!" -ForegroundColor Green
Write-Host ""

if ($Local) {
    Write-Host "🏠 Configuración LOCAL seleccionada" -ForegroundColor Yellow
    Write-Host "📋 Pasos siguientes:" -ForegroundColor Cyan
    Write-Host "   1. Asegúrate de que PostgreSQL esté ejecutándose" -ForegroundColor White
    Write-Host "   2. Verifica la configuración en .env.local" -ForegroundColor White
    Write-Host "   3. Ejecuta: .\deploy_local.ps1" -ForegroundColor White
    Write-Host ""
    Write-Host "🔗 URLs:" -ForegroundColor Cyan
    Write-Host "   API: http://127.0.0.1:8001" -ForegroundColor White
    Write-Host "   Docs: http://127.0.0.1:8001/docs" -ForegroundColor White
}
elseif ($Railway) {
    Write-Host "🚂 Configuración RAILWAY seleccionada" -ForegroundColor Yellow
    Write-Host "📋 Pasos siguientes:" -ForegroundColor Cyan
    Write-Host "   1. Configura DATABASE_URL en .env.railway" -ForegroundColor White
    Write-Host "   2. Ejecuta test: .\deploy_railway.ps1 -Test" -ForegroundColor White
    Write-Host "   3. Si el test pasa: .\deploy_railway.ps1" -ForegroundColor White
    Write-Host ""
    Write-Host "📚 Documentación completa en: DEPLOYMENT.md" -ForegroundColor Cyan
}
else {
    Write-Host "🎯 Opciones disponibles:" -ForegroundColor Yellow
    Write-Host "   .\setup.ps1 -Local      # Para desarrollo local" -ForegroundColor White
    Write-Host "   .\setup.ps1 -Railway    # Para Railway" -ForegroundColor White
    Write-Host ""
    Write-Host "📚 Lee DEPLOYMENT.md para más información" -ForegroundColor Cyan
}

Write-Host ""
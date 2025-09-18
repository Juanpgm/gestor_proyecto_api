#!/usr/bin/env powershell
# Script para probar Railway localmente con DATABASE_URL
# test_railway_local.ps1

param(
    [string]$DatabaseUrl = "",
    [switch]$Init = $false
)

if ($DatabaseUrl -eq "") {
    Write-Host "❌ Error: Se requiere DATABASE_URL" -ForegroundColor Red
    Write-Host ""
    Write-Host "Uso:" -ForegroundColor Yellow
    Write-Host "  .\test_railway_local.ps1 -DatabaseUrl 'postgresql://user:pass@host:port/db'" -ForegroundColor White
    Write-Host "  .\test_railway_local.ps1 -DatabaseUrl 'postgresql://...' -Init  # También inicializar BD" -ForegroundColor White
    Write-Host ""
    Write-Host "💡 Obtén tu DATABASE_URL desde el dashboard de Railway" -ForegroundColor Cyan
    exit 1
}

Write-Host "🧪 === PRUEBA LOCAL DE RAILWAY ===" -ForegroundColor Blue
Write-Host ""

# Configurar variables de entorno como lo haría Railway
$env:ENVIRONMENT = "railway"
$env:DATABASE_URL = $DatabaseUrl
$env:PORT = "8000"

Write-Host "🔧 Variables configuradas:" -ForegroundColor Cyan
Write-Host "  ENVIRONMENT = railway" -ForegroundColor White
Write-Host "  DATABASE_URL = $($DatabaseUrl.Substring(0, [Math]::Min(50, $DatabaseUrl.Length)))..." -ForegroundColor White
Write-Host "  PORT = 8000" -ForegroundColor White
Write-Host ""

if ($Init) {
    Write-Host "🗃️  Inicializando base de datos..." -ForegroundColor Cyan
    .\init_database.ps1 -Railway
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✅ Base de datos inicializada" -ForegroundColor Green
    } else {
        Write-Host "❌ Error inicializando base de datos" -ForegroundColor Red
        exit 1
    }
    Write-Host ""
}

Write-Host "🚀 Iniciando servidor Railway (simulado)..." -ForegroundColor Green
Write-Host "📍 URL: http://localhost:8000" -ForegroundColor Cyan
Write-Host "📚 Docs: http://localhost:8000/docs" -ForegroundColor Cyan
Write-Host "🔧 Health: http://localhost:8000/health" -ForegroundColor Cyan
Write-Host ""
Write-Host "Presiona Ctrl+C para detener" -ForegroundColor Gray
Write-Host ""

# Activar entorno virtual
if (Test-Path "env\Scripts\activate.ps1") {
    & .\env\Scripts\Activate.ps1
}

# Ejecutar con configuración Railway
try {
    uvicorn main:app --host 0.0.0.0 --port 8000 --log-level info
} catch {
    Write-Host "❌ Error ejecutando servidor: $_" -ForegroundColor Red
    exit 1
}
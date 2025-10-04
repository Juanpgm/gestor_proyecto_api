# 🚄 CONFIGURACIÓN DE PRODUCCIÓN PARA RAILWAY
# Este script te ayuda a configurar las variables necesarias en Railway Dashboard

Write-Host "🚄 CONFIGURACIÓN DE RAILWAY PARA PRODUCCIÓN" -ForegroundColor Green
Write-Host "=============================================" -ForegroundColor Yellow
Write-Host ""

# Leer las credenciales WIF existentes
$WIF_CREDENTIALS_PATH = "railway-wif-credentials-fixed.json"
if (Test-Path $WIF_CREDENTIALS_PATH) {
    $WIF_JSON = Get-Content $WIF_CREDENTIALS_PATH -Raw | ConvertFrom-Json | ConvertTo-Json -Compress
    Write-Host "✅ Credenciales WIF encontradas" -ForegroundColor Green
} else {
    Write-Host "❌ No se encontró el archivo de credenciales WIF" -ForegroundColor Red
    Write-Host "📁 Buscando archivo alternativo..." -ForegroundColor Yellow
    
    if (Test-Path "railway-wif-credentials.json") {
        $WIF_JSON = Get-Content "railway-wif-credentials.json" -Raw | ConvertFrom-Json | ConvertTo-Json -Compress
        Write-Host "✅ Usando credenciales WIF alternativas" -ForegroundColor Green
    } else {
        Write-Host "❌ No se encontraron credenciales WIF" -ForegroundColor Red
        exit 1
    }
}

Write-Host ""
Write-Host "📋 PASO 1: Ve a tu Dashboard de Railway" -ForegroundColor Cyan
Write-Host "   🌐 https://railway.app/dashboard" -ForegroundColor White
Write-Host ""

Write-Host "📋 PASO 2: Selecciona tu proyecto y ve a 'Variables'" -ForegroundColor Cyan
Write-Host ""

Write-Host "📋 PASO 3: Agrega estas variables EXACTAMENTE como aparecen:" -ForegroundColor Cyan
Write-Host "=========================================================" -ForegroundColor Yellow

Write-Host ""
Write-Host "🔧 VARIABLES BÁSICAS:" -ForegroundColor Magenta
Write-Host "ENVIRONMENT=production" -ForegroundColor White
Write-Host "FIREBASE_PROJECT_ID=unidad-cumplimiento-aa245" -ForegroundColor White
Write-Host "GOOGLE_CLOUD_PROJECT=unidad-cumplimiento-aa245" -ForegroundColor White

Write-Host ""
Write-Host "⚙️ VARIABLES DE CONFIGURACIÓN:" -ForegroundColor Magenta
Write-Host "FIRESTORE_BATCH_SIZE=500" -ForegroundColor White
Write-Host "FIRESTORE_TIMEOUT=30" -ForegroundColor White
Write-Host "LOG_LEVEL=INFO" -ForegroundColor White

Write-Host ""
Write-Host "🔑 CREDENCIAL WIF (LA MÁS IMPORTANTE):" -ForegroundColor Red
Write-Host "Variable: GOOGLE_APPLICATION_CREDENTIALS_JSON" -ForegroundColor Yellow
Write-Host "Valor:" -ForegroundColor Yellow
Write-Host $WIF_JSON -ForegroundColor Green

Write-Host ""
Write-Host "🌐 VARIABLES OPCIONALES (si tienes frontend):" -ForegroundColor Magenta
Write-Host "FRONTEND_URL=https://tu-frontend.vercel.app" -ForegroundColor Gray
Write-Host "CORS_ORIGINS=https://tu-dominio1.com,https://tu-dominio2.com" -ForegroundColor Gray

Write-Host ""
Write-Host "=========================================================" -ForegroundColor Yellow
Write-Host ""

Write-Host "⚠️  IMPORTANTE - PASOS EN RAILWAY:" -ForegroundColor Red
Write-Host "1. 🔑 Copia la variable GOOGLE_APPLICATION_CREDENTIALS_JSON COMPLETA" -ForegroundColor White
Write-Host "2. 📝 En Railway, pega todo el JSON en una sola línea" -ForegroundColor White
Write-Host "3. ✅ No agregues comillas extras, Railway las maneja automáticamente" -ForegroundColor White
Write-Host "4. 🚀 Despliega tu aplicación después de agregar las variables" -ForegroundColor White

Write-Host ""
Write-Host "🔍 VERIFICACIÓN:" -ForegroundColor Cyan
Write-Host "Una vez desplegado, verifica en:" -ForegroundColor White
Write-Host "https://tu-app.railway.app/auth/workload-identity/status" -ForegroundColor Green

Write-Host ""
Write-Host "📞 TROUBLESHOOTING:" -ForegroundColor Yellow
Write-Host "Si WIF falla, Railway automáticamente usará Service Account como fallback" -ForegroundColor White
Write-Host "Para generar Service Account Key de emergencia, ejecuta:" -ForegroundColor White
Write-Host ".\generate_service_account_fallback.ps1" -ForegroundColor Gray

Write-Host ""
Write-Host "✅ ¡Configuración lista para copiar a Railway!" -ForegroundColor Green
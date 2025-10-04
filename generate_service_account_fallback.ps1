# 🆘 SCRIPT DE FALLBACK - SERVICE ACCOUNT KEY
# Usa este script solo si Workload Identity Federation no funciona en Railway

Write-Host "🆘 GENERANDO SERVICE ACCOUNT KEY DE EMERGENCIA" -ForegroundColor Red
Write-Host "===============================================" -ForegroundColor Yellow
Write-Host ""
Write-Host "⚠️  ADVERTENCIA: Este método es menos seguro que WIF" -ForegroundColor Yellow
Write-Host "🔐 Solo úsalo si WIF absolutamente no funciona" -ForegroundColor Yellow
Write-Host ""

$PROJECT_ID = "unidad-cumplimiento-aa245"
$SERVICE_ACCOUNT = "railway-firebase@unidad-cumplimiento-aa245.iam.gserviceaccount.com"
$KEY_FILE = "railway-service-account-key.json"

Write-Host "📊 Proyecto: $PROJECT_ID" -ForegroundColor Cyan
Write-Host "👤 Service Account: $SERVICE_ACCOUNT" -ForegroundColor Cyan
Write-Host ""

# Verificar si gcloud está configurado
try {
    $currentProject = gcloud config get-value project 2>$null
    if ($currentProject -ne $PROJECT_ID) {
        Write-Host "🔧 Configurando proyecto en gcloud..." -ForegroundColor Blue
        gcloud config set project $PROJECT_ID
    }
    Write-Host "✅ gcloud configurado correctamente" -ForegroundColor Green
} catch {
    Write-Host "❌ Error: gcloud no está configurado" -ForegroundColor Red
    Write-Host "🔧 Ejecuta: gcloud auth login" -ForegroundColor Yellow
    exit 1
}

Write-Host ""
Write-Host "🔑 Generando Service Account Key..." -ForegroundColor Blue

try {
    # Generar la clave del service account
    gcloud iam service-accounts keys create $KEY_FILE `
        --iam-account=$SERVICE_ACCOUNT `
        --project=$PROJECT_ID
    
    if (Test-Path $KEY_FILE) {
        Write-Host "✅ Service Account Key generada: $KEY_FILE" -ForegroundColor Green
        
        # Convertir a Base64
        Write-Host "🔄 Convirtiendo a Base64..." -ForegroundColor Blue
        $keyContent = Get-Content $KEY_FILE -Raw
        $keyBase64 = [Convert]::ToBase64String([System.Text.Encoding]::UTF8.GetBytes($keyContent))
        
        Write-Host "✅ Conversión completada" -ForegroundColor Green
        Write-Host ""
        
        Write-Host "📋 CONFIGURACIÓN PARA RAILWAY (MÉTODO FALLBACK):" -ForegroundColor Red
        Write-Host "=================================================" -ForegroundColor Yellow
        Write-Host ""
        
        Write-Host "🔧 VARIABLES BÁSICAS:" -ForegroundColor Magenta
        Write-Host "ENVIRONMENT=production" -ForegroundColor White
        Write-Host "FIREBASE_PROJECT_ID=unidad-cumplimiento-aa245" -ForegroundColor White
        Write-Host "GOOGLE_CLOUD_PROJECT=unidad-cumplimiento-aa245" -ForegroundColor White
        
        Write-Host ""
        Write-Host "🔑 SERVICE ACCOUNT KEY (FALLBACK):" -ForegroundColor Red
        Write-Host "Variable: FIREBASE_SERVICE_ACCOUNT_KEY" -ForegroundColor Yellow
        Write-Host "Valor:" -ForegroundColor Yellow
        Write-Host $keyBase64 -ForegroundColor Green
        
        Write-Host ""
        Write-Host "⚙️ VARIABLES DE CONFIGURACIÓN:" -ForegroundColor Magenta
        Write-Host "FIRESTORE_BATCH_SIZE=500" -ForegroundColor White
        Write-Host "FIRESTORE_TIMEOUT=30" -ForegroundColor White
        Write-Host "LOG_LEVEL=INFO" -ForegroundColor White
        
        Write-Host ""
        Write-Host "=================================================" -ForegroundColor Yellow
        Write-Host ""
        
        Write-Host "⚠️  IMPORTANTE:" -ForegroundColor Red
        Write-Host "1. 🗑️  NO configures GOOGLE_APPLICATION_CREDENTIALS_JSON si usas este método" -ForegroundColor White
        Write-Host "2. 🔐 Usa FIREBASE_SERVICE_ACCOUNT_KEY en su lugar" -ForegroundColor White
        Write-Host "3. 🗂️  El archivo $KEY_FILE contiene información sensible - guárdalo seguro" -ForegroundColor White
        Write-Host "4. 🔄 Considera volver a intentar WIF más tarde" -ForegroundColor White
        
        # Guardar en archivo de texto para fácil copia
        $fallbackConfig = @"
# CONFIGURACIÓN FALLBACK PARA RAILWAY
ENVIRONMENT=production
FIREBASE_PROJECT_ID=unidad-cumplimiento-aa245
GOOGLE_CLOUD_PROJECT=unidad-cumplimiento-aa245
FIRESTORE_BATCH_SIZE=500
FIRESTORE_TIMEOUT=30
LOG_LEVEL=INFO
FIREBASE_SERVICE_ACCOUNT_KEY=$keyBase64
"@
        
        $fallbackConfig | Out-File -FilePath "railway-fallback-config.txt" -Encoding UTF8
        Write-Host ""
        Write-Host "💾 Configuración guardada en: railway-fallback-config.txt" -ForegroundColor Green
        
    } else {
        Write-Host "❌ Error: No se pudo generar la clave" -ForegroundColor Red
    }
    
} catch {
    Write-Host "❌ Error generando Service Account Key: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host ""
    Write-Host "🔧 Posibles soluciones:" -ForegroundColor Yellow
    Write-Host "1. Verifica que tengas permisos de administrador en el proyecto" -ForegroundColor White
    Write-Host "2. Ejecuta: gcloud auth login" -ForegroundColor White
    Write-Host "3. Verifica que el service account existe:" -ForegroundColor White
    Write-Host "   gcloud iam service-accounts describe $SERVICE_ACCOUNT --project=$PROJECT_ID" -ForegroundColor Gray
}

Write-Host ""
Write-Host "🔄 PARA VOLVER A WIF:" -ForegroundColor Cyan
Write-Host "Una vez que WIF funcione, elimina FIREBASE_SERVICE_ACCOUNT_KEY" -ForegroundColor White
Write-Host "y agrega GOOGLE_APPLICATION_CREDENTIALS_JSON nuevamente" -ForegroundColor White
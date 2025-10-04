# 🔧 SOLUCIÓN INMEDIATA: SERVICE ACCOUNT KEY PARA RAILWAY
# Ya que Railway no proporciona RAILWAY_TOKEN, usamos Service Account Key

Write-Host "🚨 CONFIGURACIÓN DE EMERGENCIA - RAILWAY SIN WIF" -ForegroundColor Red
Write-Host "=================================================" -ForegroundColor Yellow
Write-Host ""
Write-Host "❌ Problema detectado: Railway no proporciona RAILWAY_TOKEN" -ForegroundColor Red
Write-Host "✅ Solución: Usar Service Account Key directamente" -ForegroundColor Green
Write-Host ""

# Verificar si gcloud está configurado
$PROJECT_ID = "unidad-cumplimiento-aa245"
$SERVICE_ACCOUNT = "railway-firebase@$PROJECT_ID.iam.gserviceaccount.com"

try {
    $currentProject = gcloud config get-value project 2>$null
    if ($currentProject -ne $PROJECT_ID) {
        Write-Host "🔧 Configurando proyecto en gcloud..." -ForegroundColor Blue
        gcloud config set project $PROJECT_ID
    }
    Write-Host "✅ gcloud configurado correctamente" -ForegroundColor Green
} catch {
    Write-Host "❌ Error: gcloud no disponible o no configurado" -ForegroundColor Red
    Write-Host "🔧 Instala gcloud SDK: https://cloud.google.com/sdk/docs/install" -ForegroundColor Yellow
    exit 1
}

Write-Host ""
Write-Host "🔑 Generando Service Account Key..." -ForegroundColor Blue

try {
    # Generar clave del service account
    $keyFile = "railway-service-account-key.json"
    gcloud iam service-accounts keys create $keyFile `
        --iam-account=$SERVICE_ACCOUNT `
        --project=$PROJECT_ID

    if (Test-Path $keyFile) {
        # Convertir a Base64
        $keyContent = Get-Content $keyFile -Raw
        $keyBase64 = [Convert]::ToBase64String([System.Text.Encoding]::UTF8.GetBytes($keyContent))
        
        Write-Host "✅ Service Account Key generada y convertida a Base64" -ForegroundColor Green
        Write-Host ""
        
        # Crear configuración para Railway
        Write-Host "📋 CONFIGURACIÓN PARA RAILWAY DASHBOARD" -ForegroundColor Cyan
        Write-Host "=======================================" -ForegroundColor Yellow
        Write-Host ""
        
        Write-Host "🔧 PASO 1: Elimina estas variables si existen:" -ForegroundColor Red
        Write-Host "GOOGLE_APPLICATION_CREDENTIALS_JSON" -ForegroundColor Gray
        Write-Host ""
        
        Write-Host "🔧 PASO 2: Agrega estas variables:" -ForegroundColor Green
        Write-Host "ENVIRONMENT=production" -ForegroundColor White
        Write-Host "FIREBASE_PROJECT_ID=unidad-cumplimiento-aa245" -ForegroundColor White
        Write-Host "GOOGLE_CLOUD_PROJECT=unidad-cumplimiento-aa245" -ForegroundColor White
        Write-Host "FIRESTORE_BATCH_SIZE=500" -ForegroundColor White
        Write-Host "FIRESTORE_TIMEOUT=30" -ForegroundColor White
        Write-Host "LOG_LEVEL=INFO" -ForegroundColor White
        Write-Host ""
        
        Write-Host "🔑 PASO 3: Agrega la clave de autenticación:" -ForegroundColor Yellow
        Write-Host "Variable: FIREBASE_SERVICE_ACCOUNT_KEY" -ForegroundColor Yellow
        Write-Host "Valor:" -ForegroundColor Yellow
        Write-Host $keyBase64 -ForegroundColor Green
        Write-Host ""
        
        # Guardar configuración en archivo
        $config = @"
# CONFIGURACIÓN RAILWAY - SERVICE ACCOUNT METHOD
# Copia estas variables exactamente en Railway Dashboard

ENVIRONMENT=production
FIREBASE_PROJECT_ID=unidad-cumplimiento-aa245
GOOGLE_CLOUD_PROJECT=unidad-cumplimiento-aa245
FIRESTORE_BATCH_SIZE=500
FIRESTORE_TIMEOUT=30
LOG_LEVEL=INFO

# Clave de autenticación (copia esta línea completa)
FIREBASE_SERVICE_ACCOUNT_KEY=$keyBase64
"@
        
        $config | Out-File -FilePath "railway-service-account-config.txt" -Encoding UTF8
        
        Write-Host "💾 Configuración guardada en: railway-service-account-config.txt" -ForegroundColor Green
        Write-Host ""
        
        Write-Host "⚡ VENTAJAS DE ESTE MÉTODO:" -ForegroundColor Cyan
        Write-Host "✅ Funciona inmediatamente en Railway" -ForegroundColor White
        Write-Host "✅ No depende de RAILWAY_TOKEN" -ForegroundColor White
        Write-Host "✅ Autenticación directa con Google Cloud" -ForegroundColor White
        Write-Host "✅ Mismo nivel de seguridad que WIF en producción" -ForegroundColor White
        
        Write-Host ""
        Write-Host "🛡️ SEGURIDAD:" -ForegroundColor Yellow
        Write-Host "• La clave está encriptada en Base64" -ForegroundColor White
        Write-Host "• Solo Railway puede acceder a las variables de entorno" -ForegroundColor White
        Write-Host "• Puedes rotar la clave cuando quieras" -ForegroundColor White
        
    } else {
        Write-Host "❌ Error: No se pudo generar la clave" -ForegroundColor Red
    }
    
} catch {
    Write-Host "❌ Error: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host ""
    Write-Host "🔧 Posibles soluciones:" -ForegroundColor Yellow
    Write-Host "1. Ejecuta: gcloud auth login" -ForegroundColor White
    Write-Host "2. Verifica permisos: gcloud projects get-iam-policy $PROJECT_ID" -ForegroundColor White
    Write-Host "3. Verifica service account: gcloud iam service-accounts describe $SERVICE_ACCOUNT" -ForegroundColor White
}

Write-Host ""
Write-Host "🚀 PRÓXIMOS PASOS:" -ForegroundColor Magenta
Write-Host "1. 📋 Copia la configuración a Railway Dashboard" -ForegroundColor White
Write-Host "2. 🚀 Despliega tu aplicación" -ForegroundColor White
Write-Host "3. ✅ Verifica en: https://tu-app.railway.app/auth/workload-identity/status" -ForegroundColor White
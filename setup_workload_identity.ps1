# 🔐 Script de PowerShell para configurar Workload Identity Federation para Railway

$PROJECT_ID = "unidad-cumplimiento-aa245"
$POOL_ID = "railway-pool"
$PROVIDER_ID = "railway-provider"
$SERVICE_ACCOUNT_NAME = "railway-service"

Write-Host "🚀 Configurando Workload Identity Federation para Railway..." -ForegroundColor Green
Write-Host "Proyecto: $PROJECT_ID" -ForegroundColor Yellow

# Obtener el número del proyecto
$PROJECT_NUMBER = gcloud projects describe $PROJECT_ID --format="value(projectNumber)"
Write-Host "📊 Número del proyecto: $PROJECT_NUMBER" -ForegroundColor Cyan

# 1. Habilitar APIs necesarias
Write-Host "📡 Habilitando APIs necesarias..." -ForegroundColor Blue
gcloud services enable iamcredentials.googleapis.com --project=$PROJECT_ID
gcloud services enable sts.googleapis.com --project=$PROJECT_ID
gcloud services enable firebase.googleapis.com --project=$PROJECT_ID

# 2. Crear Workload Identity Pool
Write-Host "🏊 Creando Workload Identity Pool..." -ForegroundColor Blue
gcloud iam workload-identity-pools create $POOL_ID `
    --project=$PROJECT_ID `
    --location=global `
    --display-name="Railway Workload Identity Pool" `
    --description="Pool para autenticación de Railway con Firebase"

# 3. Crear Provider OIDC para Railway
Write-Host "🔗 Creando Provider OIDC para Railway..." -ForegroundColor Blue
gcloud iam workload-identity-pools providers create-oidc $PROVIDER_ID `
    --project=$PROJECT_ID `
    --location=global `
    --workload-identity-pool=$POOL_ID `
    --issuer-uri="https://railway.app" `
    --attribute-mapping="google.subject=assertion.sub,attribute.project_id=assertion.project_id" `
    --attribute-condition="assertion.aud=='railway'"

# 4. Crear Service Account
Write-Host "👤 Creando Service Account..." -ForegroundColor Blue
gcloud iam service-accounts create $SERVICE_ACCOUNT_NAME `
    --project=$PROJECT_ID `
    --description="Service Account para Railway deployment con Firebase" `
    --display-name="Railway Firebase Service Account"

# 5. Asignar permisos Firebase
Write-Host "🔐 Asignando permisos Firebase..." -ForegroundColor Blue
gcloud projects add-iam-policy-binding $PROJECT_ID `
    --member="serviceAccount:${SERVICE_ACCOUNT_NAME}@${PROJECT_ID}.iam.gserviceaccount.com" `
    --role="roles/firebase.admin"

gcloud projects add-iam-policy-binding $PROJECT_ID `
    --member="serviceAccount:${SERVICE_ACCOUNT_NAME}@${PROJECT_ID}.iam.gserviceaccount.com" `
    --role="roles/datastore.user"

# 6. Permitir que Railway use el Service Account
Write-Host "🚂 Configurando permisos para Railway..." -ForegroundColor Blue
Write-Host "⚠️  IMPORTANTE: Necesitas obtener tu Railway Project ID de https://railway.app/dashboard" -ForegroundColor Yellow
Write-Host "📝 Formato del Railway Project ID: algo como 'a1b2c3d4-e5f6-7890-ab12-cd34ef567890'" -ForegroundColor Yellow
$RAILWAY_PROJECT_ID = Read-Host "🔤 Ingresa tu Railway Project ID"

gcloud iam service-accounts add-iam-policy-binding `
    "${SERVICE_ACCOUNT_NAME}@${PROJECT_ID}.iam.gserviceaccount.com" `
    --project=$PROJECT_ID `
    --role="roles/iam.workloadIdentityUser" `
    --member="principalSet://iam.googleapis.com/projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${POOL_ID}/attribute.project_id/${RAILWAY_PROJECT_ID}"

# 7. Generar archivo de credenciales
Write-Host "📄 Generando archivo de credenciales..." -ForegroundColor Blue
$PROVIDER_PATH = "projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${POOL_ID}/providers/${PROVIDER_ID}"

gcloud iam workload-identity-pools create-cred-config `
    $PROVIDER_PATH `
    --service-account="${SERVICE_ACCOUNT_NAME}@${PROJECT_ID}.iam.gserviceaccount.com" `
    --output-file=railway-workload-identity.json

Write-Host ""
Write-Host "✅ ¡Configuración completada!" -ForegroundColor Green
Write-Host ""
Write-Host "📋 Variables para Railway Dashboard:" -ForegroundColor Cyan
Write-Host "GOOGLE_CLOUD_PROJECT=$PROJECT_ID" -ForegroundColor White
Write-Host "FIREBASE_PROJECT_ID=$PROJECT_ID" -ForegroundColor White
Write-Host "FIRESTORE_BATCH_SIZE=500" -ForegroundColor White
Write-Host "FIRESTORE_TIMEOUT=30" -ForegroundColor White
Write-Host ""
Write-Host "📄 El archivo 'railway-workload-identity.json' ha sido generado." -ForegroundColor Yellow
Write-Host "🔐 Copia TODO el contenido de este archivo como variable:" -ForegroundColor Yellow
Write-Host "    GOOGLE_APPLICATION_CREDENTIALS_JSON=<contenido-completo-del-archivo>" -ForegroundColor White
Write-Host ""
Write-Host "📖 Para ver el contenido del archivo:" -ForegroundColor Yellow
Write-Host "    Get-Content railway-workload-identity.json" -ForegroundColor White
Write-Host ""
Write-Host "🚀 Una vez configuradas las variables en Railway, tu API debería conectar automáticamente con Firebase." -ForegroundColor Green
# 🧪 ALTERNATIVA EXPERIMENTAL: GITHUB OIDC PARA RAILWAY
# Esta opción usa GitHub como proveedor OIDC en lugar de Railway

Write-Host "🧪 CONFIGURACIÓN GITHUB OIDC - EXPERIMENTAL" -ForegroundColor Magenta
Write-Host "=============================================" -ForegroundColor Yellow
Write-Host ""
Write-Host "⚠️ ADVERTENCIA: Método experimental, úsalo solo si tienes experiencia" -ForegroundColor Yellow
Write-Host ""

$PROJECT_ID = "unidad-cumplimiento-aa245"
$PROJECT_NUMBER = "226627821040"  # Tu número de proyecto
$POOL_ID = "github-railway-pool"
$PROVIDER_ID = "github-provider"
$SERVICE_ACCOUNT = "railway-firebase@$PROJECT_ID.iam.gserviceaccount.com"

Write-Host "📊 Configuración:" -ForegroundColor Cyan
Write-Host "Proyecto: $PROJECT_ID" -ForegroundColor White
Write-Host "Repo GitHub: Juanpgm/gestor_proyecto_api" -ForegroundColor White
Write-Host ""

Write-Host "🔧 PASO 1: Crear Workload Identity Pool para GitHub" -ForegroundColor Blue
Write-Host "Ejecuta estos comandos en tu terminal:" -ForegroundColor White
Write-Host ""

$commands = @"
# 1. Crear pool para GitHub
gcloud iam workload-identity-pools create $POOL_ID \
    --project=$PROJECT_ID \
    --location=global \
    --display-name="GitHub Railway Pool" \
    --description="Pool para GitHub Actions con Railway"

# 2. Crear provider OIDC para GitHub
gcloud iam workload-identity-pools providers create-oidc $PROVIDER_ID \
    --project=$PROJECT_ID \
    --location=global \
    --workload-identity-pool=$POOL_ID \
    --issuer-uri="https://token.actions.githubusercontent.com" \
    --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository,attribute.actor=assertion.actor" \
    --attribute-condition="assertion.repository=='Juanpgm/gestor_proyecto_api'"

# 3. Permitir que GitHub use el service account
gcloud iam service-accounts add-iam-policy-binding \
    $SERVICE_ACCOUNT \
    --project=$PROJECT_ID \
    --role="roles/iam.workloadIdentityUser" \
    --member="principalSet://iam.googleapis.com/projects/$PROJECT_NUMBER/locations/global/workloadIdentityPools/$POOL_ID/attribute.repository/Juanpgm/gestor_proyecto_api"

# 4. Generar credenciales para GitHub
gcloud iam workload-identity-pools create-cred-config \
    projects/$PROJECT_NUMBER/locations/global/workloadIdentityPools/$POOL_ID/providers/$PROVIDER_ID \
    --service-account=$SERVICE_ACCOUNT \
    --output-file=github-wif-credentials.json
"@

Write-Host $commands -ForegroundColor Gray
Write-Host ""

Write-Host "🔧 PASO 2: Configurar Railway con credenciales GitHub" -ForegroundColor Blue
Write-Host ""

# Generar credenciales GitHub WIF (simuladas, el usuario debe ejecutar gcloud)
$githubWifCredentials = @{
    "universe_domain" = "googleapis.com"
    "type" = "external_account"
    "audience" = "//iam.googleapis.com/projects/$PROJECT_NUMBER/locations/global/workloadIdentityPools/$POOL_ID/providers/$PROVIDER_ID"
    "subject_token_type" = "urn:ietf:params:oauth:token-type:jwt"
    "token_url" = "https://sts.googleapis.com/v1/token"
    "credential_source" = @{
        "url" = "https://token.actions.githubusercontent.com"
        "headers" = @{
            "Authorization" = "Bearer `$GITHUB_TOKEN"
            "Accept" = "application/json"
        }
    }
    "service_account_impersonation_url" = "https://iamcredentials.googleapis.com/v1/projects/-/serviceAccounts/$SERVICE_ACCOUNT`:generateAccessToken"
}

$githubWifJson = $githubWifCredentials | ConvertTo-Json -Compress -Depth 10

Write-Host "Variables para Railway:" -ForegroundColor Yellow
Write-Host "ENVIRONMENT=production" -ForegroundColor White
Write-Host "FIREBASE_PROJECT_ID=$PROJECT_ID" -ForegroundColor White
Write-Host "GOOGLE_CLOUD_PROJECT=$PROJECT_ID" -ForegroundColor White
Write-Host "GITHUB_TOKEN=tu_github_token_aqui" -ForegroundColor White
Write-Host "GOOGLE_APPLICATION_CREDENTIALS_JSON=$githubWifJson" -ForegroundColor White
Write-Host ""

Write-Host "⚠️ LIMITACIONES:" -ForegroundColor Red
Write-Host "• Necesitas un GITHUB_TOKEN válido en Railway" -ForegroundColor White
Write-Host "• Más complejo de mantener" -ForegroundColor White
Write-Host "• No es la práctica estándar" -ForegroundColor White
Write-Host ""

Write-Host "✅ RECOMENDACIÓN: Usa Service Account Key instead" -ForegroundColor Green
Write-Host "Ejecuta: .\fix_railway_no_token.ps1" -ForegroundColor Green
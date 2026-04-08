# Configurar secrets sin Git
# Este script usa gh CLI directamente

$ErrorActionPreference = "Continue"

Write-Host "🔐 Configurando secrets en GitHub..." -ForegroundColor Cyan

function Get-DefaultApiUrl {
    if ($env:API_BASE_URL -and $env:API_BASE_URL.Trim() -ne "") {
        return $env:API_BASE_URL.Trim().TrimEnd('/')
    }

    $defaultUrlFile = Join-Path $PSScriptRoot "config\api_base_url.txt"
    if (Test-Path $defaultUrlFile) {
        $fileUrl = (Get-Content $defaultUrlFile -Raw).Trim().TrimEnd('/')
        if ($fileUrl -ne "") {
            return $fileUrl
        }
    }

    return "https://tu-api.railway.app"
}

# Valores
$API_URL = Get-DefaultApiUrl
$FIREBASE_UID = "0WGJbRl09nVjf5jN9iO7O9dW5p52"

Write-Host "🌐 API_BASE_URL por defecto: $API_URL" -ForegroundColor DarkCyan

# Obtener owner y repo del token
Write-Host "`n📋 Obteniendo información del repositorio..." -ForegroundColor Yellow

$authStatus = gh auth status 2>&1 | Out-String
if ($authStatus -match "Logged in to github.com account (\w+)") {
    $owner = $matches[1]
    Write-Host "✅ Owner: $owner" -ForegroundColor Green
}
else {
    Write-Host "❌ No se pudo obtener el owner" -ForegroundColor Red
    $owner = Read-Host "Ingresa tu usuario de GitHub"
}

$repo = Read-Host "Ingresa el nombre del repositorio (ej: gestor_proyecto_api)"

# Configurar secrets usando stdin
Write-Host "`n🔐 Configurando API_BASE_URL..." -ForegroundColor Cyan
$API_URL | gh secret set API_BASE_URL --repo="$owner/$repo"
if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ API_BASE_URL configurado" -ForegroundColor Green
}
else {
    Write-Host "❌ Error configurando API_BASE_URL" -ForegroundColor Red
}

Write-Host "`n🔐 Configurando FIREBASE_AUTOMATION_UID..." -ForegroundColor Cyan
$FIREBASE_UID | gh secret set FIREBASE_AUTOMATION_UID --repo="$owner/$repo"
if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ FIREBASE_AUTOMATION_UID configurado" -ForegroundColor Green
}
else {
    Write-Host "❌ Error configurando FIREBASE_AUTOMATION_UID" -ForegroundColor Red
}

# Listar secrets
Write-Host "`n📋 Secrets configurados:" -ForegroundColor Cyan
gh secret list --repo="$owner/$repo"

Write-Host "`n✅ Configuración completada!" -ForegroundColor Green
Write-Host "`n💡 Próximos pasos:" -ForegroundColor Yellow
Write-Host "1. El workflow se ejecutará automáticamente en los horarios configurados"
Write-Host "2. O ejecutalo manualmente:"
Write-Host "   gh workflow run emprestito-automation.yml --repo=$owner/$repo"
Write-Host "`n3. Ver el progreso:"
Write-Host "   gh run list --repo=$owner/$repo"

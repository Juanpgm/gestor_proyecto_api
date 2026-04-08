param(
    [string]$WorkflowFile = "deploy.yml"
)

$ErrorActionPreference = "Stop"

function Write-Info($message) { Write-Host "ℹ️  $message" -ForegroundColor Cyan }
function Write-Ok($message) { Write-Host "✅ $message" -ForegroundColor Green }
function Write-WarnMsg($message) { Write-Host "⚠️  $message" -ForegroundColor Yellow }
function Write-Err($message) { Write-Host "❌ $message" -ForegroundColor Red }

try {
    $repoRoot = $PSScriptRoot
    $urlFile = Join-Path $repoRoot "config\api_base_url.txt"

    if (-not (Test-Path $urlFile)) {
        throw "No existe el archivo de URL base: $urlFile"
    }

    $apiBaseUrl = (Get-Content $urlFile -Raw).Trim().TrimEnd('/')
    if ([string]::IsNullOrWhiteSpace($apiBaseUrl)) {
        throw "El archivo config/api_base_url.txt está vacío"
    }

    if ($apiBaseUrl -notmatch '^https?://') {
        throw "La URL en config/api_base_url.txt debe iniciar con http:// o https://"
    }

    if ($apiBaseUrl -match 'tu-api\.railway\.app') {
        throw "config/api_base_url.txt aún tiene el placeholder. Reemplázalo con tu dominio real de Railway y vuelve a ejecutar."
    }

    Write-Info "Verificando autenticación de GitHub CLI..."
    gh auth status | Out-Null
    Write-Ok "GitHub CLI autenticado"

    Write-Info "Detectando repositorio GitHub desde remoto origin..."
    $originUrl = git config --get remote.origin.url
    if (-not $originUrl) {
        throw "No se encontró remote.origin.url"
    }

    $repoSlug = ""
    if ($originUrl -match 'github\.com[:/](.+?)(\.git)?$') {
        $repoSlug = $matches[1]
    }

    if ([string]::IsNullOrWhiteSpace($repoSlug)) {
        throw "No se pudo detectar owner/repo desde origin: $originUrl"
    }

    Write-Info "Actualizando secret API_BASE_URL en $repoSlug..."
    $apiBaseUrl | gh secret set API_BASE_URL --repo $repoSlug
    if ($LASTEXITCODE -ne 0) {
        throw "Fallo al actualizar secret API_BASE_URL"
    }
    Write-Ok "Secret API_BASE_URL actualizado: $apiBaseUrl"

    Write-Info "Disparando workflow '$WorkflowFile'..."
    gh workflow run $WorkflowFile --repo $repoSlug
    if ($LASTEXITCODE -ne 0) {
        throw "No se pudo ejecutar workflow $WorkflowFile"
    }
    Write-Ok "Workflow disparado correctamente"

    Write-Info "Últimos runs del workflow:"
    gh run list --workflow $WorkflowFile --repo $repoSlug --limit 5

    Write-Host ""
    Write-Ok "Proceso completado"
    Write-Host "Siguiente comando útil para monitorear en vivo:" -ForegroundColor DarkCyan
    Write-Host "gh run watch --repo $repoSlug" -ForegroundColor Gray
}
catch {
    Write-Err $_.Exception.Message
    exit 1
}

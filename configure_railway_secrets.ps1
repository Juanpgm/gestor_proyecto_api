param(
    [string]$Repo = ""
)

$ErrorActionPreference = "Stop"

function Write-Info($msg) { Write-Host "ℹ️  $msg" -ForegroundColor Cyan }
function Write-Ok($msg) { Write-Host "✅ $msg" -ForegroundColor Green }
function Write-WarnMsg($msg) { Write-Host "⚠️  $msg" -ForegroundColor Yellow }
function Write-Err($msg) { Write-Host "❌ $msg" -ForegroundColor Red }

try {
    Write-Info "Verificando GitHub CLI..."
    gh auth status | Out-Null

    if ([string]::IsNullOrWhiteSpace($Repo)) {
        $originUrl = git config --get remote.origin.url
        if (-not $originUrl) { throw "No se encontró remote.origin.url" }

        if ($originUrl -match 'github\.com[:/](.+?)(\.git)?$') {
            $Repo = $matches[1]
        }

        if ([string]::IsNullOrWhiteSpace($Repo)) {
            throw "No se pudo inferir owner/repo desde origin: $originUrl"
        }
    }

    Write-Info "Repositorio objetivo: $Repo"

    Write-Host ""
    Write-Host "Pega tu RAILWAY_TOKEN (se ocultará al escribir):" -ForegroundColor Yellow
    $secureToken = Read-Host -AsSecureString "RAILWAY_TOKEN"
    $tokenBstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureToken)
    $token = [Runtime.InteropServices.Marshal]::PtrToStringAuto($tokenBstr)
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($tokenBstr)

    if ([string]::IsNullOrWhiteSpace($token)) {
        throw "RAILWAY_TOKEN vacío"
    }

    Write-Info "Configurando secret RAILWAY_TOKEN..."
    $token | gh secret set RAILWAY_TOKEN --repo $Repo
    if ($LASTEXITCODE -ne 0) { throw "No se pudo configurar RAILWAY_TOKEN" }
    Write-Ok "RAILWAY_TOKEN configurado"

    Write-Host ""
    $serviceId = Read-Host "RAILWAY_SERVICE_ID (opcional, Enter para omitir)"
    if (-not [string]::IsNullOrWhiteSpace($serviceId)) {
        Write-Info "Configurando secret RAILWAY_SERVICE_ID..."
        $serviceId.Trim() | gh secret set RAILWAY_SERVICE_ID --repo $Repo
        if ($LASTEXITCODE -ne 0) { throw "No se pudo configurar RAILWAY_SERVICE_ID" }
        Write-Ok "RAILWAY_SERVICE_ID configurado"
    }
    else {
        Write-WarnMsg "RAILWAY_SERVICE_ID omitido. El deploy por action fallará hasta configurarlo."
    }

    Write-Info "Secrets actuales:"
    gh secret list --repo $Repo

    Write-Host ""
    Write-Ok "Configuración finalizada"
    Write-Host "Siguiente paso recomendado:" -ForegroundColor DarkCyan
    Write-Host "gh workflow run deploy.yml --repo $Repo" -ForegroundColor Gray
}
catch {
    Write-Err $_.Exception.Message
    exit 1
}

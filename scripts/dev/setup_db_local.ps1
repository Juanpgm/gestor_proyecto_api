<#
.SYNOPSIS
  Bring up the local PostgreSQL+PostGIS database, apply migrations and run the
  v3 test suite. Local only — never touches Firestore writes or production.

.NOTES
  Run from the back/ directory:  powershell scripts/dev/setup_db_local.ps1
#>

$ErrorActionPreference = "Stop"

# Resolve back/ regardless of where the script is invoked from.
$BackDir = Resolve-Path (Join-Path $PSScriptRoot "..\..")
Set-Location $BackDir

$env:DATABASE_URL = "postgresql+asyncpg://calitrack:calitrack@localhost:5433/calitrack_dev"

Write-Host "==> Starting PostGIS container..." -ForegroundColor Cyan
docker compose -f docker-compose.dev.yml up -d | Out-Null

Write-Host "==> Waiting for the database to become healthy..." -ForegroundColor Cyan
$healthy = $false
for ($i = 0; $i -lt 30; $i++) {
    $status = docker inspect --format '{{.State.Health.Status}}' calitrack_pg_dev 2>$null
    if ($status -eq "healthy") { $healthy = $true; break }
    Start-Sleep -Seconds 2
}
if (-not $healthy) { throw "Database did not become healthy in time." }
Write-Host "    healthy." -ForegroundColor Green

Write-Host "==> Applying migrations (alembic upgrade head)..." -ForegroundColor Cyan
python -m alembic upgrade head

Write-Host "==> Running unit + integration tests..." -ForegroundColor Cyan
python -m pytest -m "unit or integration" --no-cov

Write-Host "==> Done. DB at $($env:DATABASE_URL)" -ForegroundColor Green
Write-Host "    Stop with: docker compose -f docker-compose.dev.yml down"

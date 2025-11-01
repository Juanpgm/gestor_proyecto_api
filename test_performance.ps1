# Script para probar el rendimiento del endpoint optimizado
Write-Host "=== PRUEBA DE RENDIMIENTO ENDPOINT OPTIMIZADO ===" -ForegroundColor Green
Write-Host ""

$tiempos = @()

for ($i = 1; $i -le 3; $i++) {
    Write-Host "Ejecutando prueba $i..." -ForegroundColor Yellow
    
    $tiempo = Measure-Command { 
        curl -X GET "http://localhost:8001/contratos_emprestito_all" -o $null -s 2>$null
    }
    
    $milisegundos = [math]::Round($tiempo.TotalMilliseconds, 1)
    $tiempos += $milisegundos
    
    Write-Host "  Tiempo: $milisegundos ms" -ForegroundColor Cyan
    
    if ($i -lt 3) {
        Start-Sleep -Seconds 2
    }
}

Write-Host ""
Write-Host "=== RESULTADOS ===" -ForegroundColor Green
Write-Host "Prueba 1: $($tiempos[0]) ms"
Write-Host "Prueba 2: $($tiempos[1]) ms" 
Write-Host "Prueba 3: $($tiempos[2]) ms"

$promedio = ($tiempos | Measure-Object -Average).Average
$promedio = [math]::Round($promedio, 1)

Write-Host ""
Write-Host "Tiempo promedio: $promedio ms" -ForegroundColor Magenta

# Comparación con el tiempo original
$tiempoOriginal = 16492.5
$mejora = [math]::Round((($tiempoOriginal - $promedio) / $tiempoOriginal) * 100, 1)
$factor = [math]::Round($tiempoOriginal / $promedio, 1)

Write-Host ""
Write-Host "=== COMPARACIÓN CON VERSIÓN ORIGINAL ===" -ForegroundColor Green
Write-Host "Tiempo original: $tiempoOriginal ms"
Write-Host "Tiempo optimizado: $promedio ms"
Write-Host "Mejora: $mejora% más rápido"
Write-Host "Factor de mejora: ${factor}x más rápido" -ForegroundColor Green
#!/usr/bin/env powershell
# Script simple para inicializar Railway con DATABASE_URL como variable de entorno
# railway_init.ps1

Write-Host "🚂 === INICIALIZACIÓN RAILWAY ===" -ForegroundColor Blue
Write-Host ""

# Verificar que DATABASE_URL esté disponible
if (-not $env:DATABASE_URL) {
    Write-Host "❌ ERROR: Variable DATABASE_URL no encontrada" -ForegroundColor Red
    Write-Host ""
    Write-Host "💡 Soluciones:" -ForegroundColor Yellow
    Write-Host "   1. En Railway: La variable se inyecta automáticamente" -ForegroundColor White
    Write-Host "   2. Para pruebas locales:" -ForegroundColor White
    Write-Host "      `$env:DATABASE_URL = 'postgresql://user:pass@host:port/db'" -ForegroundColor Gray
    Write-Host "      .\railway_init.ps1" -ForegroundColor Gray
    Write-Host ""
    exit 1
}

# Configurar entorno
$env:ENVIRONMENT = "railway"

Write-Host "✅ DATABASE_URL detectada: $($env:DATABASE_URL.Substring(0, [Math]::Min(50, $env:DATABASE_URL.Length)))..." -ForegroundColor Green
Write-Host ""

# Activar entorno virtual si existe
if (Test-Path "env\Scripts\activate.ps1") {
    Write-Host "🔧 Activando entorno virtual..." -ForegroundColor Cyan
    & .\env\Scripts\Activate.ps1
}

# Ejecutar inicialización
Write-Host "🗃️  Creando tablas..." -ForegroundColor Cyan

python -c "
import sys
import os

# Verificar que DATABASE_URL esté disponible
database_url = os.getenv('DATABASE_URL')
if not database_url:
    print('❌ DATABASE_URL no disponible')
    sys.exit(1)

print(f'🔗 Conectando a: {database_url[:50]}...')

try:
    from config import engine, Base
    from models import EmpContrato, EmpProceso
    from sqlalchemy import text
    
    print('📋 Modelos detectados:')
    print('  - EmpContrato (tabla: emp_contratos)')
    print('  - EmpProceso (tabla: emp_procesos)')
    print()
    
    # Verificar conexión
    with engine.connect() as conn:
        version = conn.execute(text('SELECT version()')).scalar()
        print(f'✅ Conectado a: {version[:60]}...')
    
    # Crear tablas
    print('🏗️  Creando estructura...')
    Base.metadata.create_all(bind=engine)
    
    # Verificar tablas creadas
    with engine.connect() as conn:
        result = conn.execute(text('''
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = \\'public\\' 
            AND table_name IN (\\'emp_contratos\\', \\'emp_procesos\\')
            ORDER BY table_name
        '''))
        
        tables = [row[0] for row in result]
        print()
        print('📊 Tablas creadas:')
        for table in tables:
            print(f'  ✅ {table}')
        
        if len(tables) == 2:
            print()
            print('🎉 ¡Base de datos Railway inicializada correctamente!')
        else:
            print(f'⚠️  Solo se crearon {len(tables)} de 2 tablas')
            
except Exception as e:
    print(f'❌ Error: {str(e)}')
    sys.exit(1)
"

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "🚂 ¡Railway listo!" -ForegroundColor Blue
    Write-Host "🔗 Las tablas están inicializadas y vacías" -ForegroundColor Cyan
    Write-Host "🚀 Puedes desplegar tu aplicación" -ForegroundColor Green
} else {
    Write-Host ""
    Write-Host "❌ Error durante la inicialización" -ForegroundColor Red
}
#!/usr/bin/env powershell
# Script para inicializar la base de datos en Railway
# init_database.ps1

param(
    [switch]$Local = $false,
    [switch]$Railway = $false,
    [switch]$Force = $false,
    [string]$DatabaseUrl = ""
)

if (-not $Local -and -not $Railway) {
    Write-Host "❌ Error: Especifica el entorno con -Local o -Railway" -ForegroundColor Red
    Write-Host "Uso:" -ForegroundColor Yellow
    Write-Host "  .\init_database.ps1 -Local     # Inicializar BD local" -ForegroundColor White
    Write-Host "  .\init_database.ps1 -Railway   # Inicializar BD Railway (usa variable de entorno)" -ForegroundColor White
    Write-Host "  .\init_database.ps1 -Railway -DatabaseUrl 'postgresql://...'  # Con URL específica" -ForegroundColor White
    Write-Host "  .\init_database.ps1 -Railway -Force  # Forzar recreación" -ForegroundColor White
    exit 1
}

if ($Railway) {
    Write-Host "🚂 === INICIALIZACIÓN BD RAILWAY === " -ForegroundColor Blue
    $env:ENVIRONMENT = "railway"
    $envFile = ".env.railway"
    
    # Si se proporciona DatabaseUrl, configurarlo como variable de entorno
    if ($DatabaseUrl -ne "") {
        $env:DATABASE_URL = $DatabaseUrl
        Write-Host "🔗 Usando DATABASE_URL proporcionada" -ForegroundColor Yellow
    } else {
        Write-Host "🔗 Usando DATABASE_URL de variable de entorno" -ForegroundColor Yellow
    }
}
else {
    Write-Host "🏠 === INICIALIZACIÓN BD LOCAL === " -ForegroundColor Green
    $env:ENVIRONMENT = "local"
    $envFile = ".env.local"
}

Write-Host ""

# Verificar archivo de configuración
if (-not (Test-Path $envFile)) {
    Write-Host "❌ Error: No se encontró $envFile" -ForegroundColor Red
    exit 1
}

# Verificar entorno virtual
if (-not (Test-Path "env\Scripts\activate.ps1")) {
    Write-Host "❌ Error: No se encontró el entorno virtual en 'env'" -ForegroundColor Red
    Write-Host "   Ejecuta: python -m venv env" -ForegroundColor Red
    exit 1
}

Write-Host "🔧 Activando entorno virtual..." -ForegroundColor Cyan
try {
    & .\env\Scripts\Activate.ps1
    Write-Host "✅ Entorno virtual activado" -ForegroundColor Green
}
catch {
    Write-Host "❌ Error activando entorno virtual: $_" -ForegroundColor Red
    exit 1
}

Write-Host "📦 Verificando dependencias..." -ForegroundColor Cyan
try {
    pip install -r requirements.txt -q
    Write-Host "✅ Dependencias verificadas" -ForegroundColor Green
}
catch {
    Write-Host "❌ Error con dependencias: $_" -ForegroundColor Red
    exit 1
}

Write-Host "🔗 Verificando conexión a la base de datos..." -ForegroundColor Cyan
try {
    python -c "
import sys
try:
    from config import DATABASE_URL, ENV, engine
    from sqlalchemy import text
    
    print(f'Entorno: {ENV}')
    print(f'Conectando a: {DATABASE_URL[:50]}...')
    
    # Test de conexión
    with engine.connect() as conn:
        result = conn.execute(text('SELECT version()')).scalar()
        print('✅ Conexión exitosa')
        print(f'PostgreSQL: {result[:50]}...')
        
except Exception as e:
    print(f'❌ Error de conexión: {str(e)}')
    sys.exit(1)
"
    
    if ($LASTEXITCODE -ne 0) {
        Write-Host "❌ Error de conexión a la base de datos" -ForegroundColor Red
        exit 1
    }
    
    Write-Host "✅ Conexión a BD verificada" -ForegroundColor Green
}
catch {
    Write-Host "❌ Error verificando conexión: $_" -ForegroundColor Red
    exit 1
}

if ($Force) {
    Write-Host "⚠️  Modo FORCE activado - Se eliminarán las tablas existentes" -ForegroundColor Yellow
    Write-Host "¿Estás seguro? (S/N): " -NoNewline -ForegroundColor Red
    $confirm = Read-Host
    if ($confirm -ne "S" -and $confirm -ne "s") {
        Write-Host "❌ Operación cancelada" -ForegroundColor Yellow
        exit 0
    }
}

Write-Host "🗃️  Inicializando estructura de base de datos..." -ForegroundColor Cyan

try {
    python -c "
import sys
from config import engine, Base
from models import EmpContrato, EmpProceso
from sqlalchemy import text

print('📋 Modelos detectados:')
print(f'  - EmpContrato (tabla: emp_contratos)')
print(f'  - EmpProceso (tabla: emp_procesos)')
print()

try:
    if '$Force' == 'True':
        print('🗑️  Eliminando tablas existentes...')
        Base.metadata.drop_all(bind=engine)
        print('✅ Tablas eliminadas')
    
    print('🏗️  Creando tablas...')
    Base.metadata.create_all(bind=engine)
    print('✅ Tablas creadas exitosamente')
    
    # Verificar tablas creadas
    with engine.connect() as conn:
        query = '''
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = \\'public\\' 
            AND table_name IN (\\'emp_contratos\\', \\'emp_procesos\\')
            ORDER BY table_name;
        '''
        tables_result = conn.execute(text(query))
        
        tables = [row[0] for row in tables_result]
        print()
        print('📊 Tablas verificadas:')
        for table in tables:
            print(f'  ✅ {table}')
        
        if len(tables) == 2:
            print()
            print('🎉 ¡Base de datos inicializada correctamente!')
        else:
            print(f'⚠️  Solo se crearon {len(tables)} de 2 tablas esperadas')
            
except Exception as e:
    print(f'❌ Error inicializando BD: {str(e)}')
    sys.exit(1)
"
    
    if ($LASTEXITCODE -ne 0) {
        Write-Host "❌ Error durante la inicialización" -ForegroundColor Red
        exit 1
    }
    
}
catch {
    Write-Host "❌ Error ejecutando inicialización: $_" -ForegroundColor Red
    exit 1
}

Write-Host ""
if ($Railway) {
    Write-Host "🚂 ¡Base de datos Railway inicializada!" -ForegroundColor Blue
    Write-Host "🔗 Puedes verificar en tu dashboard de Railway" -ForegroundColor Cyan
}
else {
    Write-Host "🏠 ¡Base de datos local inicializada!" -ForegroundColor Green
    Write-Host "🔗 Las tablas están listas en tu PostgreSQL local" -ForegroundColor Cyan
}

Write-Host ""
Write-Host "📋 Próximos pasos:" -ForegroundColor Yellow
Write-Host "  1. Las tablas están vacías y listas para usar" -ForegroundColor White
Write-Host "  2. Puedes iniciar la API con los scripts de despliegue" -ForegroundColor White
if ($Railway) {
    Write-Host "  3. Ejecuta: .\deploy_railway.ps1" -ForegroundColor White
}
else {
    Write-Host "  3. Ejecuta: .\deploy_local.ps1" -ForegroundColor White
}
Write-Host ""
#!/usr/bin/env powershell
# Script para verificar y diagnosticar la conexión a Railway
# check_railway.ps1

Write-Host "🔍 === DIAGNÓSTICO DE CONEXIÓN RAILWAY ===" -ForegroundColor Blue
Write-Host ""

# Configurar entorno
$env:ENVIRONMENT = "railway"

# Verificar archivo .env.railway
if (-not (Test-Path ".env.railway")) {
    Write-Host "❌ Error: No se encontró .env.railway" -ForegroundColor Red
    exit 1
}

# Activar entorno virtual
if (Test-Path "env\Scripts\activate.ps1") {
    try {
        & .\env\Scripts\Activate.ps1
        Write-Host "✅ Entorno virtual activado" -ForegroundColor Green
    } catch {
        Write-Host "❌ Error activando entorno virtual" -ForegroundColor Red
        exit 1
    }
} else {
    Write-Host "❌ No se encontró entorno virtual" -ForegroundColor Red
    exit 1
}

Write-Host "🔗 Analizando configuración de Railway..." -ForegroundColor Cyan

python -c "
import os
from dotenv import load_dotenv
import re

# Cargar configuración Railway
load_dotenv('.env.railway')

database_url = os.getenv('DATABASE_URL')
print(f'DATABASE_URL encontrada: {database_url is not None}')

if database_url:
    # Analizar componentes de la URL
    pattern = r'postgresql://([^:]+):([^@]+)@([^:]+):(\d+)/(.+)'
    match = re.match(pattern, database_url)
    
    if match:
        user, password, host, port, db = match.groups()
        print(f'Usuario: {user}')
        print(f'Host: {host}')
        print(f'Puerto: {port}')
        print(f'Base de datos: {db}')
        print(f'Contraseña: {password[:5]}...{password[-5:]}')
        print()
    else:
        print('❌ Formato de DATABASE_URL no válido')
        exit(1)
else:
    print('❌ DATABASE_URL no encontrada')
    exit(1)
"

Write-Host ""
Write-Host "🌐 Probando conectividad de red..." -ForegroundColor Cyan

# Probar conectividad básica
try {
    $railwayHost = python -c "
import re
import os
from dotenv import load_dotenv
load_dotenv('.env.railway')
url = os.getenv('DATABASE_URL')
match = re.search(r'@([^:]+):', url)
if match:
    print(match.group(1))
"
    
    Write-Host "🔍 Probando ping a $railwayHost..." -ForegroundColor Yellow
    $pingResult = Test-Connection -ComputerName $railwayHost -Count 2 -Quiet
    
    if ($pingResult) {
        Write-Host "✅ Host $railwayHost es accesible" -ForegroundColor Green
    } else {
        Write-Host "⚠️  Host $railwayHost no responde a ping (puede ser normal)" -ForegroundColor Yellow
    }
} catch {
    Write-Host "⚠️  No se pudo verificar conectividad de red" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "🔗 Intentando conexión a Railway..." -ForegroundColor Cyan

python -c "
import sys
from config import DATABASE_URL, ENV, engine
from sqlalchemy import create_engine, text
import psycopg2
from urllib.parse import urlparse

print(f'Entorno configurado: {ENV}')
print(f'URL: {DATABASE_URL[:50]}...')
print()

# Parsear URL para obtener componentes
parsed = urlparse(DATABASE_URL)
print(f'Esquema: {parsed.scheme}')
print(f'Host: {parsed.hostname}')
print(f'Puerto: {parsed.port}')
print(f'Usuario: {parsed.username}')
print(f'Base de datos: {parsed.path[1:]}')
print()

try:
    # Intentar conexión directa con psycopg2
    print('🔌 Intentando conexión directa con psycopg2...')
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    cursor.execute('SELECT version();')
    version = cursor.fetchone()[0]
    print(f'✅ Conexión directa exitosa!')
    print(f'PostgreSQL: {version[:80]}...')
    cursor.close()
    conn.close()
    
    # Ahora probar con SQLAlchemy
    print()
    print('🔌 Intentando conexión con SQLAlchemy...')
    with engine.connect() as sqlalchemy_conn:
        result = sqlalchemy_conn.execute(text('SELECT current_database();')).scalar()
        print(f'✅ SQLAlchemy conectado a BD: {result}')
        
        # Verificar esquema public
        tables_result = sqlalchemy_conn.execute(text('''
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = \\'public\\'
            ORDER BY table_name;
        '''))
        
        existing_tables = [row[0] for row in tables_result]
        print(f'📊 Tablas existentes en public: {len(existing_tables)}')
        for table in existing_tables:
            print(f'  - {table}')
    
    print()
    print('🎉 ¡Conexión a Railway exitosa!')
    
except psycopg2.Error as e:
    print(f'❌ Error de psycopg2: {e}')
    print('💡 Posibles causas:')
    print('   - La base de datos Railway está pausada o inactiva')
    print('   - Las credenciales han cambiado')
    print('   - El firewall bloquea la conexión')
    print('   - El servicio Railway está en mantenimiento')
    sys.exit(1)
    
except Exception as e:
    print(f'❌ Error general: {e}')
    sys.exit(1)
"

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "✅ Diagnóstico completado - Railway está accesible" -ForegroundColor Green
    Write-Host "🎯 Puedes proceder con la inicialización de la BD" -ForegroundColor Cyan
} else {
    Write-Host ""
    Write-Host "❌ Problemas detectados con Railway" -ForegroundColor Red
    Write-Host ""
    Write-Host "🔧 Pasos para solucionar:" -ForegroundColor Yellow
    Write-Host "   1. Verifica que tu proyecto Railway esté activo" -ForegroundColor White
    Write-Host "   2. Confirma que la base de datos no esté pausada" -ForegroundColor White
    Write-Host "   3. Actualiza DATABASE_URL desde el dashboard Railway" -ForegroundColor White
    Write-Host "   4. Verifica tu conexión a internet" -ForegroundColor White
}
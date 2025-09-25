#!/usr/bin/env python3
"""
Diagnóstico para problemas de Railway deployment
Simula el entorno de Railway localmente
"""

import os
import sys
import subprocess
from datetime import datetime

def print_header(title):
    print(f"\n{'='*60}")
    print(f"🔍 {title}")
    print(f"{'='*60}")

def print_success(msg):
    print(f"✅ {msg}")

def print_warning(msg):
    print(f"⚠️  {msg}")

def print_error(msg):
    print(f"❌ {msg}")

def print_info(msg):
    print(f"ℹ️  {msg}")

def check_python_version():
    print_header("VERSIÓN DE PYTHON")
    print(f"Python: {sys.version}")
    print(f"Ejecutable: {sys.executable}")
    
    version = sys.version_info
    if version.major == 3 and version.minor >= 8:
        print_success(f"Python {version.major}.{version.minor}.{version.micro} es compatible")
        return True
    else:
        print_error(f"Python {version.major}.{version.minor}.{version.micro} podría no ser compatible")
        return False

def check_requirements():
    print_header("DEPENDENCIAS")
    
    try:
        with open('requirements.txt', 'r') as f:
            requirements = f.read().strip().split('\n')
        
        print_info(f"Encontradas {len(requirements)} dependencias en requirements.txt")
        
        missing = []
        for req in requirements:
            if req.strip() and not req.startswith('#'):
                package = req.split('==')[0].split('>=')[0].split('<=')[0].strip()
                try:
                    __import__(package.replace('-', '_'))
                    print_success(f"{package}")
                except ImportError:
                    missing.append(package)
                    print_error(f"{package} - FALTANTE")
        
        if missing:
            print_warning(f"Dependencias faltantes: {', '.join(missing)}")
            return False
        else:
            print_success("Todas las dependencias están instaladas")
            return True
            
    except FileNotFoundError:
        print_error("requirements.txt no encontrado")
        return False

def check_imports():
    print_header("IMPORTACIONES CRÍTICAS")
    
    # Test FastAPI
    try:
        import fastapi
        print_success(f"FastAPI {fastapi.__version__}")
    except ImportError:
        print_error("FastAPI no disponible")
        return False
    
    # Test uvicorn
    try:
        import uvicorn
        print_success(f"Uvicorn disponible")
    except ImportError:
        print_error("Uvicorn no disponible")
        return False
    
    # Test Firebase (opcional)
    try:
        import firebase_admin
        print_success("Firebase Admin SDK disponible")
    except ImportError:
        print_warning("Firebase Admin SDK no disponible (se ejecutará en modo limitado)")
    
    return True

def test_app_startup():
    print_header("PRUEBA DE STARTUP DE LA APLICACIÓN")
    
    # Configurar variables de entorno como Railway
    os.environ['PORT'] = '8000'
    os.environ['ENVIRONMENT'] = 'production'
    
    print_info("Simulando entorno de Railway...")
    print_info(f"PORT={os.environ.get('PORT')}")
    print_info(f"ENVIRONMENT={os.environ.get('ENVIRONMENT')}")
    
    try:
        # Intentar importar main
        print_info("Importando main.py...")
        from main import app
        print_success("main.py importado correctamente")
        
        # Verificar que app existe
        if app:
            print_success("FastAPI app creada correctamente")
            return True
        else:
            print_error("FastAPI app es None")
            return False
            
    except Exception as e:
        print_error(f"Error importando main.py: {e}")
        return False

def simulate_railway_start():
    print_header("SIMULACIÓN DE STARTUP DE RAILWAY")
    
    # El comando que Railway ejecuta
    cmd = ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
    
    print_info(f"Comando Railway: {' '.join(cmd)}")
    print_info("Iniciando servidor (presiona Ctrl+C para detener)...")
    
    try:
        # Ejecutar por 10 segundos para ver si arranca
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        
        import time
        time.sleep(5)  # Esperar 5 segundos
        
        if process.poll() is None:
            print_success("Servidor iniciado correctamente (ejecutándose)")
            process.terminate()
            process.wait()
            return True
        else:
            stdout, stderr = process.communicate()
            print_error("Servidor falló al iniciar")
            print(f"STDOUT: {stdout}")
            print(f"STDERR: {stderr}")
            return False
            
    except Exception as e:
        print_error(f"Error ejecutando servidor: {e}")
        return False

def main():
    print("🚂 DIAGNÓSTICO DE RAILWAY DEPLOYMENT")
    print(f"Timestamp: {datetime.now().isoformat()}")
    
    results = {
        'python': check_python_version(),
        'requirements': check_requirements(),
        'imports': check_imports(),
        'startup': test_app_startup(),
        'server': simulate_railway_start()
    }
    
    print_header("RESUMEN")
    
    success_count = sum(results.values())
    total_count = len(results)
    
    for test, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{test.upper()}: {status}")
    
    print(f"\nRESULTADO: {success_count}/{total_count} pruebas pasaron")
    
    if success_count == total_count:
        print_success("🎉 Todo funciona! El problema podría ser específico de Railway")
        print_info("Revisa los logs de Railway Dashboard para más detalles")
    else:
        print_error("🚨 Problemas detectados que pueden causar fallas en Railway")
        print_info("Soluciona estos problemas antes de hacer redeploy")

if __name__ == "__main__":
    main()
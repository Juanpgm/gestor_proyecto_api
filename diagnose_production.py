#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🔍 DIAGNÓSTICO COMPLETO DE PRODUCCIÓN
Script para verificar el estado de la API tanto en local como en Railway
"""

import requests
import os
import json
from datetime import datetime

def test_endpoint(url, description, method="GET", data=None, timeout=10):
    """Probar un endpoint y retornar resultado"""
    try:
        print(f"\n🧪 Probando: {description}")
        print(f"📍 URL: {url}")
        
        if method == "GET":
            response = requests.get(url, timeout=timeout)
        elif method == "POST":
            headers = {"Content-Type": "application/json"}
            response = requests.post(url, json=data, headers=headers, timeout=timeout)
        
        print(f"📊 Status: {response.status_code}")
        
        if response.status_code == 200:
            try:
                result = response.json()
                print(f"✅ Éxito: {json.dumps(result, indent=2)[:200]}...")
                return {"success": True, "status": response.status_code, "data": result}
            except:
                print(f"✅ Éxito: {response.text[:200]}...")
                return {"success": True, "status": response.status_code, "text": response.text}
        else:
            print(f"❌ Error: {response.text}")
            return {"success": False, "status": response.status_code, "error": response.text}
            
    except requests.exceptions.ConnectTimeout:
        print(f"⏰ Timeout: La conexión tardó más de {timeout} segundos")
        return {"success": False, "error": "Timeout"}
    except requests.exceptions.ConnectionError:
        print(f"🔌 Error de conexión: No se pudo conectar al servidor")
        return {"success": False, "error": "Connection Error"}
    except Exception as e:
        print(f"💥 Error inesperado: {str(e)}")
        return {"success": False, "error": str(e)}

def main():
    print("🚀 DIAGNÓSTICO COMPLETO DE LA API")
    print("=" * 50)
    print(f"⏰ Timestamp: {datetime.now().isoformat()}")
    print()
    
    # URLs a probar
    local_base = "http://localhost:8000"
    production_base = "https://gestorproyectoapi-production.up.railway.app"
    
    # Lista de endpoints críticos
    endpoints = [
        {"path": "/", "description": "Root endpoint"},
        {"path": "/ping", "description": "Simple ping"},
        {"path": "/health", "description": "Health check"},
        {"path": "/auth/register/health-check", "description": "Auth health check"},
        {"path": "/cors-test", "description": "CORS test"},
    ]
    
    # Test de registro (solo local por seguridad)
    registration_test = {
        "name": "Test User Diagnostic",
        "email": "test.diagnostic@cali.gov.co",
        "password": "TestPass123!",
        "confirmPassword": "TestPass123!",
        "cellphone": "+57 315 123 4567",
        "nombre_centro_gestor": "Secretaría de Pruebas"
    }
    
    results = {"local": {}, "production": {}}
    
    # ========================================
    # PRUEBAS EN LOCAL
    # ========================================
    print("🏠 PROBANDO API LOCAL")
    print("-" * 30)
    
    for endpoint in endpoints:
        url = f"{local_base}{endpoint['path']}"
        result = test_endpoint(url, f"LOCAL - {endpoint['description']}")
        results["local"][endpoint["path"]] = result
    
    # Test de registro en local
    print(f"\n🧪 Probando: LOCAL - User Registration")
    url = f"{local_base}/auth/register"
    result = test_endpoint(url, "LOCAL - User Registration", "POST", registration_test, 15)
    results["local"]["/auth/register"] = result
    
    # ========================================
    # PRUEBAS EN PRODUCCIÓN
    # ========================================
    print("\n\n☁️  PROBANDO API EN PRODUCCIÓN (RAILWAY)")
    print("-" * 40)
    
    for endpoint in endpoints:
        url = f"{production_base}{endpoint['path']}"
        result = test_endpoint(url, f"PRODUCTION - {endpoint['description']}")
        results["production"][endpoint["path"]] = result
    
    # ========================================
    # RESUMEN DE RESULTADOS
    # ========================================
    print("\n\n📊 RESUMEN DE RESULTADOS")
    print("=" * 50)
    
    local_success = sum(1 for r in results["local"].values() if r.get("success", False))
    local_total = len(results["local"])
    
    production_success = sum(1 for r in results["production"].values() if r.get("success", False))
    production_total = len(results["production"])
    
    print(f"🏠 LOCAL: {local_success}/{local_total} tests exitosos")
    print(f"☁️  PRODUCTION: {production_success}/{production_total} tests exitosos")
    
    # ========================================
    # ANÁLISIS Y RECOMENDACIONES
    # ========================================
    print("\n📋 ANÁLISIS Y RECOMENDACIONES")
    print("-" * 35)
    
    if production_success == 0:
        print("🚨 PROBLEMA CRÍTICO: La aplicación no responde en producción")
        print("💡 Posibles causas:")
        print("   - La aplicación no está desplegada en Railway")
        print("   - La URL de producción es incorrecta")
        print("   - El servicio está caído o reiniciándose")
        print("   - Problema con las variables de entorno en Railway")
        print()
        print("🔧 ACCIONES RECOMENDADAS:")
        print("   1. Verificar el estado del deployment en Railway Dashboard")
        print("   2. Revisar logs de Railway para errores")
        print("   3. Verificar variables de entorno (FIREBASE_SERVICE_ACCOUNT_KEY)")
        print("   4. Re-deployar la aplicación desde GitHub")
        
    elif production_success < production_total:
        print("⚠️  PROBLEMA PARCIAL: Algunos endpoints fallan en producción")
        print("🔧 Revisar configuración específica de endpoints que fallan")
        
    else:
        print("✅ TODO FUNCIONANDO: La API responde correctamente")
    
    if local_success < local_total:
        print("⚠️  PROBLEMA LOCAL: Algunos endpoints fallan en desarrollo")
        print("🔧 Verificar configuración local y Firebase WIF")
    
    # ========================================
    # INFORMACIÓN TÉCNICA
    # ========================================
    print("\n🔧 INFORMACIÓN TÉCNICA")
    print("-" * 25)
    print(f"LOCAL_BASE: {local_base}")
    print(f"PRODUCTION_BASE: {production_base}")
    print(f"FIREBASE_PROJECT_ID: {os.getenv('FIREBASE_PROJECT_ID', 'NO_SET')}")
    print(f"ENVIRONMENT: {os.getenv('ENVIRONMENT', 'NO_SET')}")
    print(f"HAS_SERVICE_ACCOUNT: {bool(os.getenv('FIREBASE_SERVICE_ACCOUNT_KEY'))}")
    
    # Guardar resultados en archivo
    output_file = "diagnostic_results.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False, default=str)
    print(f"\n💾 Resultados guardados en: {output_file}")

if __name__ == "__main__":
    main()
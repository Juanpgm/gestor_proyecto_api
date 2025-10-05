#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de configuración automática para Railway
Configura todas las variables de entorno necesarias y convierte Service Account Keys
"""

import os
import json
import base64
import sys

def convert_service_account_to_base64(json_file_path):
    """Convertir archivo JSON de Service Account a Base64"""
    try:
        # Leer el archivo JSON
        with open(json_file_path, 'r', encoding='utf-8') as f:
            service_account_data = json.load(f)
        
        # Convertir a string JSON
        json_string = json.dumps(service_account_data, separators=(',', ':'))
        
        # Codificar en Base64
        base64_encoded = base64.b64encode(json_string.encode('utf-8')).decode('utf-8')
        
        print("✅ Service Account Key convertida exitosamente!")
        print("\n🔐 FIREBASE_SERVICE_ACCOUNT_KEY (copia esta línea completa):")
        print(f"FIREBASE_SERVICE_ACCOUNT_KEY={base64_encoded}")
        
        print(f"\n📊 Información del Service Account:")
        print(f"   Project ID: {service_account_data.get('project_id', 'N/A')}")
        print(f"   Client Email: {service_account_data.get('client_email', 'N/A')}")
        print(f"   Private Key ID: {service_account_data.get('private_key_id', 'N/A')[:20]}...")
        
        print(f"\n📝 Longitud del Base64: {len(base64_encoded)} caracteres")
        
        return base64_encoded
        
    except FileNotFoundError:
        print(f"❌ Error: No se encontró el archivo {json_file_path}")
        print("💡 Asegúrate de que la ruta sea correcta")
        return None
    except json.JSONDecodeError:
        print(f"❌ Error: El archivo {json_file_path} no es un JSON válido")
        return None
    except Exception as e:
        print(f"❌ Error inesperado: {e}")
        return None

def setup_railway_environment():
    """Configurar variables de entorno para Railway"""
    
    print("🚀 CONFIGURACIÓN AUTOMÁTICA PARA RAILWAY")
    print("=" * 50)
    
    # Variables requeridas
    required_vars = {
        "FIREBASE_PROJECT_ID": "unidad-cumplimiento-aa245",
        "ENVIRONMENT": "production",
        "PORT": "8000",
        "AUTHORIZED_EMAIL_DOMAIN": "@cali.gov.co"
    }
    
    print("\n📋 Variables básicas:")
    for var, value in required_vars.items():
        print(f"   {var}={value}")
    
    # Service Account Key
    print(f"\n🔐 FIREBASE_SERVICE_ACCOUNT_KEY:")
    print("   ⚠️  REQUERIDA - Debes obtenerla de Firebase Console")
    print("   📝 Pasos:")
    print("      1. Ve a Firebase Console > Configuración del proyecto")
    print("      2. Pestaña 'Cuentas de servicio'")
    print("      3. 'Generar nueva clave privada'")
    print("      4. Usa este mismo script para convertir:")
    print("         python setup_environment.py --convert archivo.json")
    
    print(f"\n🌐 CONFIGURACIÓN EN RAILWAY:")
    print("   1. Ve a Railway Dashboard")
    print("   2. Selecciona tu proyecto")
    print("   3. Variables → Add Variable")
    print("   4. Agrega cada variable una por una:")
    print("")
    
    for var, value in required_vars.items():
        print(f"      Nombre: {var}")
        print(f"      Valor:  {value}")
        print("")
    
    print(f"      Nombre: FIREBASE_SERVICE_ACCOUNT_KEY")
    print(f"      Valor:  <tu_base64_service_account_key_aquí>")
    print("")
    
    print("✅ Después de configurar, usa el health check para verificar:")
    print("   GET /auth/register/health-check")
    
    return True

def verify_local_environment():
    """Verificar configuración local"""
    print("🔍 VERIFICACIÓN DE CONFIGURACIÓN LOCAL")
    print("=" * 40)
    
    checks = {
        "FIREBASE_PROJECT_ID": os.getenv("FIREBASE_PROJECT_ID"),
        "FIREBASE_SERVICE_ACCOUNT_KEY": os.getenv("FIREBASE_SERVICE_ACCOUNT_KEY"),
        "AUTHORIZED_EMAIL_DOMAIN": os.getenv("AUTHORIZED_EMAIL_DOMAIN", "@cali.gov.co")
    }
    
    all_good = True
    
    for var, value in checks.items():
        if value:
            if var == "FIREBASE_SERVICE_ACCOUNT_KEY":
                # Solo mostrar los primeros caracteres
                display_value = f"{value[:20]}..." if len(value) > 20 else value
                print(f"   ✅ {var}: {display_value}")
            else:
                print(f"   ✅ {var}: {value}")
        else:
            print(f"   ❌ {var}: NO CONFIGURADA")
            all_good = False
    
    if all_good:
        print(f"\n🎉 ¡Configuración completa!")
    else:
        print(f"\n⚠️  Faltan variables. Revisa el archivo .env")
    
    return all_good

def show_usage():
    """Mostrar ayuda de uso"""
    print("📝 USO DEL SCRIPT:")
    print("   python setup_environment.py                    # Mostrar guía de configuración")
    print("   python setup_environment.py --verify           # Verificar configuración local")
    print("   python setup_environment.py --convert file.json # Convertir Service Account a Base64")
    print("")
    print("💡 EJEMPLOS:")
    print("   python setup_environment.py --convert unidad-cumplimiento-aa245-firebase-adminsdk-xyz.json")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        if sys.argv[1] == "--verify":
            verify_local_environment()
        elif sys.argv[1] == "--convert":
            if len(sys.argv) != 3:
                print("❌ Error: Debes especificar el archivo JSON")
                print("📝 Uso: python setup_environment.py --convert archivo.json")
                sys.exit(1)
            convert_service_account_to_base64(sys.argv[2])
        elif sys.argv[1] == "--help":
            show_usage()
        else:
            print(f"❌ Opción desconocida: {sys.argv[1]}")
            show_usage()
            sys.exit(1)
    else:
        setup_railway_environment()
        print(f"\n💡 Opciones adicionales:")
        print(f"   python setup_environment.py --verify   # Verificar configuración local")
        print(f"   python setup_environment.py --convert archivo.json # Convertir Service Account")
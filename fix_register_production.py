#!/usr/bin/env python3
"""
Script de solución para problemas de producción en /auth/register
Guía paso a paso para configurar Railway correctamente
"""

import json
import base64
from datetime import datetime

def generate_railway_environment_template():
    """Generar template de variables de entorno para Railway"""
    
    template = {
        "CRITICAL_VARIABLES": {
            "FIREBASE_PROJECT_ID": {
                "value": "unidad-cumplimiento-aa245",
                "description": "ID del proyecto Firebase",
                "required": True,
                "source": "Firebase Console > Project Settings > General"
            },
            "FIREBASE_SERVICE_ACCOUNT_KEY": {
                "value": "BASE64_ENCODED_SERVICE_ACCOUNT_JSON",
                "description": "Service Account Key en formato base64",
                "required": True,
                "source": "Firebase Console > Project Settings > Service Accounts > Generate new private key"
            },
            "ENVIRONMENT": {
                "value": "production",
                "description": "Entorno de ejecución",
                "required": True
            },
            "PORT": {
                "value": "8000",
                "description": "Puerto para Railway",
                "required": True
            }
        },
        "OPTIONAL_VARIABLES": {
            "FIREBASE_WEB_API_KEY": {
                "value": "YOUR_WEB_API_KEY",
                "description": "Web API Key para autenticación REST",
                "required": False,
                "source": "Firebase Console > Project Settings > General > Web API Key"
            },
            "AUTHORIZED_EMAIL_DOMAIN": {
                "value": "@cali.gov.co",
                "description": "Dominio autorizado para Google Auth",
                "required": False
            },
            "CORS_ORIGINS": {
                "value": "https://captura-emprestito.netlify.app",
                "description": "Orígenes CORS permitidos",
                "required": False
            }
        }
    }
    
    return template

def generate_service_account_instructions():
    """Generar instrucciones para crear Service Account Key"""
    
    instructions = """
🔑 INSTRUCCIONES PARA CREAR FIREBASE SERVICE ACCOUNT KEY

Paso 1: Ir a Firebase Console
• Abra https://console.firebase.google.com/
• Seleccione el proyecto 'unidad-cumplimiento-aa245'

Paso 2: Generar Service Account Key
• Vaya a Project Settings (⚙️) > Service accounts
• Haga clic en "Generate new private key"
• Descargue el archivo JSON

Paso 3: Convertir a Base64
• Abra el archivo JSON descargado
• Copie todo el contenido
• Use el script de conversión incluido abajo

Paso 4: Configurar en Railway
• Vaya a Railway Dashboard
• Seleccione su proyecto
• Vaya a Variables tab
• Agregue FIREBASE_SERVICE_ACCOUNT_KEY con el valor base64
"""
    
    return instructions

def create_base64_converter():
    """Crear script para convertir Service Account JSON a base64"""
    
    converter_script = '''
import json
import base64

def convert_service_account_to_base64():
    """
    Convertir Service Account JSON a base64 para Railway
    """
    print("🔧 CONVERTIDOR SERVICE ACCOUNT A BASE64")
    print("=" * 50)
    
    # Solicitar contenido del archivo JSON
    print("Pegue el contenido completo del archivo service account JSON:")
    print("(Pegue y presione Enter dos veces cuando termine)")
    
    lines = []
    while True:
        try:
            line = input()
            if not line:
                break
            lines.append(line)
        except EOFError:
            break
    
    json_content = "\\n".join(lines)
    
    try:
        # Validar que es JSON válido
        json_data = json.loads(json_content)
        
        # Verificar campos requeridos
        required_fields = ['type', 'project_id', 'private_key_id', 'private_key', 'client_email']
        missing_fields = [field for field in required_fields if field not in json_data]
        
        if missing_fields:
            print(f"❌ Error: Campos faltantes: {missing_fields}")
            return
        
        # Convertir a base64
        base64_encoded = base64.b64encode(json_content.encode('utf-8')).decode('utf-8')
        
        print("\\n✅ CONVERSIÓN EXITOSA")
        print("=" * 50)
        print("📋 Información del Service Account:")
        print(f"  • Project ID: {json_data.get('project_id')}")
        print(f"  • Client Email: {json_data.get('client_email')}")
        print(f"  • Type: {json_data.get('type')}")
        
        print("\\n🔑 VALOR PARA RAILWAY (copie esto):")
        print("-" * 50)
        print(base64_encoded)
        print("-" * 50)
        
        print("\\n📝 INSTRUCCIONES:")
        print("1. Copie el valor base64 de arriba")
        print("2. Vaya a Railway Dashboard > Variables")
        print("3. Agregue variable: FIREBASE_SERVICE_ACCOUNT_KEY")
        print("4. Pegue el valor base64")
        print("5. Guarde y redeploy")
        
    except json.JSONDecodeError as e:
        print(f"❌ Error: JSON inválido - {e}")
    except Exception as e:
        print(f"❌ Error inesperado: {e}")

if __name__ == "__main__":
    convert_service_account_to_base64()
'''
    
    return converter_script

def generate_testing_script():
    """Generar script para probar el endpoint en producción"""
    
    test_script = '''
import requests
import json

def test_register_endpoint_production():
    """
    Probar endpoint de registro en producción
    """
    # URL de producción (ajustar según su deployment)
    BASE_URL = "https://your-railway-app.railway.app"  # Cambiar por su URL
    
    # Test health check primero
    print("🔍 PROBANDO HEALTH CHECK...")
    try:
        response = requests.get(f"{BASE_URL}/auth/register/health-check")
        print(f"Status: {response.status_code}")
        print(f"Response: {response.json()}")
    except Exception as e:
        print(f"❌ Error en health check: {e}")
        return
    
    # Test de registro
    print("\\n👤 PROBANDO REGISTRO...")
    test_data = {
        "email": "usuario.test@cali.gov.co",
        "password": "TestPassword123!",
        "confirmPassword": "TestPassword123!",
        "name": "Usuario de Prueba",
        "cellphone": "3001234567",
        "nombre_centro_gestor": "Secretaría de Hacienda"
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}/auth/register",
            json=test_data,
            headers={"Content-Type": "application/json"}
        )
        
        print(f"Status: {response.status_code}")
        print(f"Response: {response.json()}")
        
        if response.status_code == 201:
            print("✅ REGISTRO EXITOSO")
        else:
            print("❌ REGISTRO FALLÓ")
            
    except Exception as e:
        print(f"❌ Error en registro: {e}")

if __name__ == "__main__":
    test_register_endpoint_production()
'''
    
    return test_script

def main():
    """Generar guía completa de solución"""
    
    print("🛠️ GUÍA DE SOLUCIÓN PARA /auth/register EN PRODUCCIÓN")
    print("=" * 70)
    print(f"⏰ Generado: {datetime.now().isoformat()}")
    
    # 1. Variables de entorno
    print("\n📋 1. VARIABLES DE ENTORNO PARA RAILWAY")
    print("-" * 50)
    template = generate_railway_environment_template()
    print(json.dumps(template, indent=2, ensure_ascii=False))
    
    # 2. Instrucciones Service Account
    print("\n🔑 2. CONFIGURAR FIREBASE SERVICE ACCOUNT")
    print("-" * 50)
    print(generate_service_account_instructions())
    
    # 3. Crear archivos helper
    print("\n💾 3. CREANDO ARCHIVOS HELPER...")
    
    # Crear convertidor
    with open("convert_service_account.py", "w", encoding="utf-8") as f:
        f.write(create_base64_converter())
    print("  ✅ Creado: convert_service_account.py")
    
    # Crear tester
    with open("test_production_register.py", "w", encoding="utf-8") as f:
        f.write(generate_testing_script())
    print("  ✅ Creado: test_production_register.py")
    
    # 4. Resumen de pasos
    print("\n🎯 4. PASOS PARA SOLUCIONAR")
    print("-" * 50)
    steps = [
        "1. Crear Service Account Key en Firebase Console",
        "2. Ejecutar: python convert_service_account.py",
        "3. Copiar valor base64 generado",
        "4. Configurar variables en Railway Dashboard:",
        "   • FIREBASE_PROJECT_ID=unidad-cumplimiento-aa245",
        "   • FIREBASE_SERVICE_ACCOUNT_KEY=[valor_base64]",
        "   • ENVIRONMENT=production",
        "   • PORT=8000",
        "5. Redeploy la aplicación en Railway",
        "6. Ejecutar: python test_production_register.py",
        "7. Verificar que el endpoint responde 201"
    ]
    
    for step in steps:
        print(f"  {step}")
    
    print("\n🔗 5. ENDPOINTS PARA VERIFICAR")
    print("-" * 50)
    endpoints = [
        "GET /health - Estado general",
        "GET /firebase/status - Estado de Firebase",
        "GET /auth/register/health-check - Estado de registro",
        "POST /auth/register - Endpoint principal"
    ]
    
    for endpoint in endpoints:
        print(f"  • {endpoint}")
    
    print("\n💡 6. TROUBLESHOOTING COMÚN")
    print("-" * 50)
    issues = [
        "❌ 503 Service Unavailable → Verificar FIREBASE_SERVICE_ACCOUNT_KEY",
        "❌ 400 Bad Request → Verificar formato de datos enviados",
        "❌ 500 Internal Error → Verificar logs de Railway",
        "❌ CORS Error → Verificar CORS_ORIGINS variable",
        "✅ 201 Created → Todo funcionando correctamente"
    ]
    
    for issue in issues:
        print(f"  {issue}")

if __name__ == "__main__":
    main()
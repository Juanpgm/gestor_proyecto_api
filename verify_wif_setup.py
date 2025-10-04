# Script para verificar y reparar la configuración de Workload Identity Federation
import os
import json
import requests
import subprocess
from typing import Dict, Any, Optional

def check_railway_environment() -> Dict[str, Any]:
    """Verifica el entorno de Railway"""
    print("🔍 Verificando entorno de Railway...")
    
    railway_vars = {
        'RAILWAY_ENVIRONMENT': os.getenv('RAILWAY_ENVIRONMENT'),
        'RAILWAY_PROJECT_ID': os.getenv('RAILWAY_PROJECT_ID'), 
        'RAILWAY_SERVICE_ID': os.getenv('RAILWAY_SERVICE_ID'),
        'RAILWAY_TOKEN': bool(os.getenv('RAILWAY_TOKEN'))  # No mostrar el token real
    }
    
    is_railway = any(railway_vars.values())
    
    print(f"¿Ejecutándose en Railway?: {'✅ Sí' if is_railway else '❌ No'}")
    for key, value in railway_vars.items():
        status = "✅" if value else "❌"
        print(f"{status} {key}: {value}")
    
    return {
        'is_railway': is_railway,
        'variables': railway_vars
    }

def test_railway_oidc_endpoint() -> Dict[str, Any]:
    """Prueba el endpoint OIDC de Railway"""
    print("\n🌐 Probando endpoint OIDC de Railway...")
    
    railway_token = os.getenv('RAILWAY_TOKEN')
    if not railway_token:
        return {
            'success': False,
            'error': 'RAILWAY_TOKEN no disponible'
        }
    
    try:
        headers = {'Authorization': f'Bearer {railway_token}'}
        response = requests.get(
            'https://railway.app/.well-known/oidc_subject_token',
            headers=headers,
            timeout=10
        )
        
        success = response.status_code == 200
        print(f"Status Code: {response.status_code}")
        
        if success:
            print("✅ Endpoint OIDC funcionando correctamente")
        else:
            print(f"❌ Error en endpoint OIDC: {response.text[:200]}")
        
        return {
            'success': success,
            'status_code': response.status_code,
            'response': response.text[:500] if not success else 'OK'
        }
        
    except Exception as e:
        print(f"❌ Error conectando a endpoint OIDC: {e}")
        return {
            'success': False,
            'error': str(e)
        }

def check_gcloud_config() -> Dict[str, Any]:
    """Verifica la configuración de gcloud"""
    print("\n⚙️ Verificando configuración de gcloud...")
    
    try:
        # Verificar proyecto activo
        result = subprocess.run(
            ['gcloud', 'config', 'get-value', 'project'],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        project = result.stdout.strip()
        print(f"Proyecto activo: {project}")
        
        # Verificar account activo
        result = subprocess.run(
            ['gcloud', 'config', 'get-value', 'account'],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        account = result.stdout.strip()
        print(f"Cuenta activa: {account}")
        
        return {
            'available': True,
            'project': project,
            'account': account
        }
        
    except Exception as e:
        print(f"❌ gcloud no disponible: {e}")
        return {
            'available': False,
            'error': str(e)
        }

def verify_workload_identity_pool() -> Dict[str, Any]:
    """Verifica la configuración del Workload Identity Pool"""
    print("\n🏊 Verificando Workload Identity Pool...")
    
    try:
        cmd = [
            'gcloud', 'iam', 'workload-identity-pools', 'describe', 'railway-pool',
            '--project=unidad-cumplimiento-aa245',
            '--location=global',
            '--format=json'
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0:
            pool_info = json.loads(result.stdout)
            print("✅ Workload Identity Pool encontrado")
            print(f"Nombre: {pool_info.get('displayName', 'N/A')}")
            print(f"Estado: {pool_info.get('state', 'N/A')}")
            return {'exists': True, 'info': pool_info}
        else:
            print(f"❌ Error verificando pool: {result.stderr}")
            return {'exists': False, 'error': result.stderr}
            
    except Exception as e:
        print(f"❌ Error ejecutando gcloud: {e}")
        return {'exists': False, 'error': str(e)}

def verify_service_account() -> Dict[str, Any]:
    """Verifica el service account"""
    print("\n👤 Verificando Service Account...")
    
    service_account = "railway-firebase@unidad-cumplimiento-aa245.iam.gserviceaccount.com"
    
    try:
        cmd = [
            'gcloud', 'iam', 'service-accounts', 'describe',
            service_account,
            '--project=unidad-cumplimiento-aa245',
            '--format=json'
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0:
            sa_info = json.loads(result.stdout)
            print("✅ Service Account encontrado")
            print(f"Email: {sa_info.get('email', 'N/A')}")
            print(f"Habilitado: {not sa_info.get('disabled', False)}")
            return {'exists': True, 'info': sa_info}
        else:
            print(f"❌ Error verificando service account: {result.stderr}")
            return {'exists': False, 'error': result.stderr}
            
    except Exception as e:
        print(f"❌ Error ejecutando gcloud: {e}")
        return {'exists': False, 'error': str(e)}

def generate_fixed_wif_credentials() -> str:
    """Genera las credenciales WIF corregidas"""
    print("\n🔧 Generando credenciales WIF corregidas...")
    
    wif_credentials = {
        "universe_domain": "googleapis.com",
        "type": "external_account",
        "audience": "//iam.googleapis.com/projects/226627821040/locations/global/workloadIdentityPools/railway-pool/providers/railway-provider",
        "subject_token_type": "urn:ietf:params:oauth:token-type:jwt",
        "token_url": "https://sts.googleapis.com/v1/token",
        "credential_source": {
            "url": "https://railway.app/.well-known/oidc_subject_token",
            "headers": {
                "Authorization": "Bearer $RAILWAY_TOKEN"
            }
        },
        "service_account_impersonation_url": "https://iamcredentials.googleapis.com/v1/projects/-/serviceAccounts/railway-firebase@unidad-cumplimiento-aa245.iam.gserviceaccount.com:generateAccessToken"
    }
    
    credentials_json = json.dumps(wif_credentials, separators=(',', ':'))
    print("✅ Credenciales WIF generadas")
    
    return credentials_json

def main():
    """Función principal de diagnóstico"""
    print("🚀 DIAGNÓSTICO DE WORKLOAD IDENTITY FEDERATION")
    print("=" * 50)
    
    # 1. Verificar entorno de Railway
    railway_check = check_railway_environment()
    
    # 2. Probar endpoint OIDC
    oidc_check = test_railway_oidc_endpoint()
    
    # 3. Verificar gcloud
    gcloud_check = check_gcloud_config()
    
    # 4. Verificar Workload Identity Pool
    if gcloud_check.get('available'):
        pool_check = verify_workload_identity_pool()
        sa_check = verify_service_account()
    else:
        pool_check = {'exists': False, 'error': 'gcloud no disponible'}
        sa_check = {'exists': False, 'error': 'gcloud no disponible'}
    
    # 5. Generar credenciales corregidas
    fixed_credentials = generate_fixed_wif_credentials()
    
    # Resumen final
    print("\n📋 RESUMEN DE CONFIGURACIÓN")
    print("=" * 30)
    print(f"Railway Environment: {'✅' if railway_check['is_railway'] else '❌'}")
    print(f"Railway OIDC: {'✅' if oidc_check.get('success') else '❌'}")
    print(f"Workload Identity Pool: {'✅' if pool_check.get('exists') else '❌'}")
    print(f"Service Account: {'✅' if sa_check.get('exists') else '❌'}")
    
    # Recomendaciones
    print("\n💡 RECOMENDACIONES:")
    
    if not railway_check['is_railway']:
        print("• Ejecuta esto en Railway para obtener todas las variables de entorno")
    
    if not oidc_check.get('success'):
        print("• El endpoint OIDC de Railway no funciona. Considera usar Service Account Key como fallback")
        print("• Verifica que RAILWAY_TOKEN esté disponible en el entorno")
    
    if not pool_check.get('exists'):
        print("• El Workload Identity Pool no existe o no es accesible")
        print("• Ejecuta el script de setup de WIF para crearlo")
    
    print(f"\n🔑 CREDENCIALES WIF PARA RAILWAY:")
    print("Copia esta línea completa en Railway Dashboard como GOOGLE_APPLICATION_CREDENTIALS_JSON:")
    print("-" * 80)
    print(fixed_credentials)
    print("-" * 80)

if __name__ == "__main__":
    main()
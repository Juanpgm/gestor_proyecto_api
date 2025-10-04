#!/usr/bin/env python3
"""
Generador de Service Account Key para Railway Fallback
Crear una clave de Service Account cuando WIF no funciona en Railway
"""

import os
import json
import base64
import subprocess
import sys
from typing import Dict, Any

def check_gcloud_available() -> bool:
    """Verificar si gcloud está disponible"""
    try:
        result = subprocess.run(['gcloud', '--version'], capture_output=True, text=True)
        return result.returncode == 0
    except FileNotFoundError:
        return False

def get_current_project() -> str:
    """Obtener el proyecto actual de gcloud"""
    try:
        result = subprocess.run(['gcloud', 'config', 'get-value', 'project'], 
                              capture_output=True, text=True)
        if result.returncode == 0:
            return result.stdout.strip()
    except:
        pass
    return "unidad-cumplimiento-aa245"  # Fallback

def create_service_account_key(project_id: str, service_account_email: str) -> Dict[str, Any]:
    """Crear una clave de Service Account"""
    try:
        # Crear clave temporal
        key_file = f"railway-sa-key-{project_id}.json"
        
        cmd = [
            'gcloud', 'iam', 'service-accounts', 'keys', 'create', key_file,
            '--iam-account', service_account_email,
            '--project', project_id
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            return {
                "success": False,
                "error": f"Failed to create service account key: {result.stderr}"
            }
        
        # Leer la clave creada
        with open(key_file, 'r') as f:
            key_data = json.load(f)
        
        # Codificar en base64
        key_json = json.dumps(key_data)
        encoded_key = base64.b64encode(key_json.encode()).decode()
        
        # Limpiar archivo temporal
        os.remove(key_file)
        
        return {
            "success": True,
            "key_data": key_data,
            "encoded_key": encoded_key,
            "service_account": service_account_email
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": f"Error creating service account key: {e}"
        }

def main():
    print("🔑 RAILWAY SERVICE ACCOUNT FALLBACK GENERATOR")
    print("=" * 50)
    
    # Verificar gcloud
    if not check_gcloud_available():
        print("❌ gcloud CLI not found. Please install Google Cloud SDK.")
        print("📖 Visit: https://cloud.google.com/sdk/docs/install")
        return
    
    # Obtener configuración
    project_id = get_current_project()
    service_account_email = f"railway-firebase@{project_id}.iam.gserviceaccount.com"
    
    print(f"📊 Project ID: {project_id}")
    print(f"🔐 Service Account: {service_account_email}")
    
    # Verificar que el service account existe
    print(f"\n🔍 Checking if service account exists...")
    check_cmd = [
        'gcloud', 'iam', 'service-accounts', 'describe', service_account_email,
        '--project', project_id
    ]
    
    result = subprocess.run(check_cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"❌ Service account {service_account_email} not found.")
        print(f"💡 Create it first with:")
        print(f"   gcloud iam service-accounts create railway-firebase --project {project_id}")
        print(f"   gcloud projects add-iam-policy-binding {project_id} --member='serviceAccount:{service_account_email}' --role='roles/firebase.admin'")
        return
    
    print("✅ Service account found")
    
    # Crear clave
    print(f"\n🔑 Creating service account key...")
    result = create_service_account_key(project_id, service_account_email)
    
    if not result["success"]:
        print(f"❌ Failed to create key: {result['error']}")
        return
    
    print("✅ Service account key created successfully")
    
    # Mostrar configuración para Railway
    print(f"\n📋 RAILWAY CONFIGURATION")
    print("=" * 50)
    print(f"Add this environment variable in Railway Dashboard:")
    print(f"")
    print(f"Variable Name: FIREBASE_SERVICE_ACCOUNT_KEY")
    print(f"Variable Value:")
    print(f"{result['encoded_key']}")
    print(f"")
    print(f"🔄 Also remove or comment out GOOGLE_APPLICATION_CREDENTIALS_JSON")
    print(f"   (to prevent WIF from trying and failing)")
    
    # Guardar en archivo local
    with open(".env.railway", "w") as f:
        f.write(f"# Railway Service Account Fallback Configuration\n")
        f.write(f"FIREBASE_PROJECT_ID={project_id}\n")
        f.write(f"FIREBASE_SERVICE_ACCOUNT_KEY={result['encoded_key']}\n")
        f.write(f"ENVIRONMENT=production\n")
        f.write(f"# GOOGLE_APPLICATION_CREDENTIALS_JSON=  # Commented out to use Service Account\n")
    
    print(f"\n💾 Configuration saved to .env.railway")
    print(f"🚀 Copy the environment variables to Railway Dashboard")
    print(f"✅ Your API should now work without WIF dependencies!")
    
    # Crear script de limpieza
    with open("cleanup_service_account_key.py", "w") as f:
        f.write(f'''#!/usr/bin/env python3
"""
Cleanup script for Railway service account key
Run this to remove the service account key when no longer needed
"""

import subprocess
import sys

def cleanup_key():
    """Remove the service account key"""
    project_id = "{project_id}"
    service_account_email = "{service_account_email}"
    
    # List and delete keys
    cmd = [
        'gcloud', 'iam', 'service-accounts', 'keys', 'list',
        '--iam-account', service_account_email,
        '--project', project_id,
        '--format', 'value(name)'
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            keys = result.stdout.strip().split('\\n')
            for key in keys:
                if key:
                    print(f"🗑️ Deleting key: {{key}}")
                    delete_cmd = [
                        'gcloud', 'iam', 'service-accounts', 'keys', 'delete', key,
                        '--iam-account', service_account_email,
                        '--project', project_id,
                        '--quiet'
                    ]
                    subprocess.run(delete_cmd)
        
        print("✅ Service account keys cleaned up")
        
    except Exception as e:
        print(f"❌ Error during cleanup: {{e}}")

if __name__ == "__main__":
    cleanup_key()
''')
    
    print(f"🧹 Cleanup script created: cleanup_service_account_key.py")

if __name__ == "__main__":
    main()
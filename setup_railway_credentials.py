"""
Script para generar credenciales de Firebase para Railway
Automatiza la creación del Service Account y la configuración
"""

import subprocess
import json
import base64
import os
from pathlib import Path

def run_gcloud_command(command):
    """Ejecutar comando gcloud y retornar resultado"""
    try:
        # En Windows, usar PowerShell para ejecutar gcloud
        result = subprocess.run(
            ["powershell", "-Command", command],
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"❌ Error ejecutando: {command}")
        print(f"   {e.stderr}")
        return None

def check_gcloud_auth():
    """Verificar que gcloud esté autenticado"""
    result = run_gcloud_command("gcloud auth list")
    if not result or "ACTIVE" not in result:
        print("❌ gcloud no está autenticado")
        print("💡 Ejecuta: gcloud auth login")
        return False
    
    # Extraer cuenta activa
    lines = result.split('\n')
    for line in lines:
        if '*' in line and '@' in line:
            account = line.split()[-1]
            print(f"✅ gcloud autenticado como: {account}")
            return True
    
    print("❌ No se encontró cuenta activa")
    return False

def get_project_number(project_id):
    """Obtener el número del proyecto"""
    result = run_gcloud_command(f"gcloud projects describe {project_id}")
    if result:
        # Buscar projectNumber en la salida
        for line in result.split('\n'):
            if 'projectNumber:' in line:
                project_number = line.split(':')[1].strip().replace("'", "")
                print(f"✅ Project number: {project_number}")
                return project_number
    print("❌ No se pudo obtener el número del proyecto")
    return None

def create_railway_service_account(project_id):
    """Crear Service Account para Railway"""
    sa_name = "railway-firebase-sa"
    sa_email = f"{sa_name}@{project_id}.iam.gserviceaccount.com"
    
    print(f"🔧 Creando Service Account: {sa_name}")
    
    # Crear service account
    result = run_gcloud_command(
        f"gcloud iam service-accounts create {sa_name} "
        f"--project={project_id} "
        f'--display-name="Railway Firebase Service Account"'
    )
    
    if result is None:
        print("⚠️ Service account ya existe o error al crear")
    else:
        print("✅ Service account creado")
    
    # Dar permisos de Firebase
    roles = [
        "roles/firebase.admin",
        "roles/datastore.user",
        "roles/firestore.serviceAgent"
    ]
    
    for role in roles:
        print(f"🔑 Asignando rol: {role}")
        run_gcloud_command(
            f"gcloud projects add-iam-policy-binding {project_id} "
            f"--member=serviceAccount:{sa_email} "
            f"--role={role}"
        )
    
    return sa_email

def generate_service_account_key(project_id, sa_email):
    """Generar y codificar clave del service account"""
    key_file = "railway-service-account.json"
    
    print(f"🔑 Generando clave para: {sa_email}")
    
    # Generar clave
    result = run_gcloud_command(
        f"gcloud iam service-accounts keys create {key_file} "
        f"--iam-account={sa_email} "
        f"--project={project_id}"
    )
    
    if not os.path.exists(key_file):
        print(f"❌ No se pudo generar la clave: {key_file}")
        return None, None
    
    # Leer y codificar en base64
    with open(key_file, 'r') as f:
        key_data = json.load(f)
    
    # Codificar en base64
    key_json = json.dumps(key_data, separators=(',', ':'))  # Compact JSON
    key_b64 = base64.b64encode(key_json.encode()).decode()
    
    print(f"✅ Clave generada y codificada en base64")
    
    # Limpiar archivo temporal
    os.remove(key_file)
    print(f"🗑️ Archivo temporal eliminado")
    
    return key_data, key_b64

def generate_railway_env_vars(project_id, key_data, key_b64):
    """Generar variables de entorno para Railway"""
    
    env_vars = {
        "FIREBASE_PROJECT_ID": project_id,
        "GOOGLE_CLOUD_PROJECT": project_id,
        "FIREBASE_SERVICE_ACCOUNT_KEY": key_b64,
        "ENVIRONMENT": "railway"
    }
    
    print(f"\n{'='*60}")
    print("🚄 VARIABLES DE ENTORNO PARA RAILWAY")
    print(f"{'='*60}")
    
    for key, value in env_vars.items():
        if key == "FIREBASE_SERVICE_ACCOUNT_KEY":
            print(f"{key}={value[:50]}...  # ({len(value)} chars total)")
        else:
            print(f"{key}={value}")
    
    # Guardar en archivo
    env_file = ".env.railway"
    with open(env_file, 'w') as f:
        for key, value in env_vars.items():
            f.write(f"{key}={value}\n")
    
    print(f"\n💾 Variables guardadas en: {env_file}")
    print(f"📋 Copia estas variables a tu configuración de Railway")
    
    return env_vars

def test_credentials(project_id, key_data):
    """Probar las credenciales generadas"""
    print(f"\n🧪 Probando credenciales...")
    
    # Crear archivo temporal para probar
    test_file = "test-credentials.json"
    with open(test_file, 'w') as f:
        json.dump(key_data, f)
    
    # Configurar variable de entorno temporal
    os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = test_file
    
    try:
        # Intentar inicializar Firebase
        import firebase_admin
        from firebase_admin import credentials, firestore
        
        # Limpiar apps existentes
        try:
            firebase_admin.delete_app(firebase_admin.get_app())
        except:
            pass
        
        # Inicializar con las credenciales nuevas
        cred = credentials.Certificate(test_file)
        app = firebase_admin.initialize_app(cred, {
            'projectId': project_id
        })
        
        # Probar Firestore
        db = firestore.client()
        test_ref = db.collection('_test')
        
        print("✅ Credenciales válidas!")
        print("✅ Firebase inicializado correctamente")
        print("✅ Firestore accessible")
        
        # Limpiar
        firebase_admin.delete_app(app)
        
    except Exception as e:
        print(f"❌ Error probando credenciales: {e}")
    finally:
        # Limpiar archivo temporal y variable
        if os.path.exists(test_file):
            os.remove(test_file)
        if 'GOOGLE_APPLICATION_CREDENTIALS' in os.environ:
            del os.environ['GOOGLE_APPLICATION_CREDENTIALS']

def main():
    """Función principal"""
    print("🚄 GENERADOR DE CREDENCIALES PARA RAILWAY")
    print("="*50)
    
    # Verificar gcloud
    if not check_gcloud_auth():
        return
    
    # Obtener project ID
    project_id = "your-project-id"  # Tu proyecto
    print(f"🎯 Proyecto: {project_id}")
    
    # Obtener project number
    project_number = get_project_number(project_id)
    if not project_number:
        print("❌ No se pudo obtener el número del proyecto")
        return
    
    # Crear service account
    sa_email = create_railway_service_account(project_id)
    
    # Generar clave
    key_data, key_b64 = generate_service_account_key(project_id, sa_email)
    if not key_data:
        return
    
    # Generar variables de entorno
    env_vars = generate_railway_env_vars(project_id, key_data, key_b64)
    
    # Probar credenciales
    test_credentials(project_id, key_data)
    
    print(f"\n{'='*60}")
    print("🎯 PRÓXIMOS PASOS:")
    print("="*60)
    print("1. 📋 Copia las variables de entorno a Railway:")
    print("   https://railway.app/project/[tu-proyecto]/settings")
    print("2. 🚀 Despliega tu aplicación")
    print("3. ✅ Verifica que la conexión funcione")
    print(f"\n💡 Las credenciales se guardaron en: .env.railway")

if __name__ == "__main__":
    main()

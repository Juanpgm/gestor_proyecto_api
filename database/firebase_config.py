"""
Firebase Auto-Configuration - Functional Programming Approach
Detects environment automatically and configures Firebase for both local and Railway deployment
Integrates with Google Workload Iden    print(f"🔧 Creating credentials for {env} environment")
    
    # Prioridad 1: Service account desde variables de entorno PRIMERO
    service_creds = create_service_account_credentials()
    if service_creds:
        try:
            creds = credentials.Certificate(service_creds)
            print("✅ Using service account from environment variables")
            return creds
        except Exception as e:
            print(f"⚠️ Service account env failed: {e}")
    
    # Prioridad 2: Application Default Credentials
    try:
        creds = credentials.ApplicationDefault()
        print("✅ Using Application Default Credentials")
        return creds
    except Exception as e:
        print(f"⚠️ ADC not available: {e}")o-setup
Eliminates all duplicated and obsolete logic
"""

import os
import sys
from typing import Optional, Dict, Any, Tuple
from functools import partial
import json
from pathlib import Path

# === ENVIRONMENT DETECTION ===

def detect_environment() -> str:
    """Detect current environment automatically"""
    if os.getenv('RAILWAY_ENVIRONMENT'):
        return 'railway'
    elif os.getenv('VERCEL'):
        return 'vercel'
    elif os.getenv('HEROKU_APP_NAME'):
        return 'heroku'
    elif os.getenv('GAE_ENV'):
        return 'gcp'
    else:
        return 'local'

def get_project_config(project_key: str = 'default') -> Dict[str, str]:
    """Get project configuration - SIMPLIFIED for production"""
    
    def get_project_id() -> str:
        # Prioridad 1: Variables de entorno
        env_vars = ['FIREBASE_PROJECT_ID', 'GOOGLE_CLOUD_PROJECT', 'GCP_PROJECT']
        for env_var in env_vars:
            project = os.getenv(env_var)
            if project and project != 'your-project-id':
                print(f"✅ Project ID from {env_var}: {project}")
                return project
        
        # Prioridad 2: gcloud si está disponible (solo local)
        try:
            import subprocess
            result = subprocess.run(
                ['gcloud', 'config', 'get-value', 'project'],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                project = result.stdout.strip()
                if project and project != '(unset)':
                    print(f"✅ Project from gcloud: {project}")
                    return project
        except:
            pass
        
        # Prioridad 3: Service account file
        sa_file = 'firebase-service-account.json'
        if os.path.exists(sa_file):
            try:
                with open(sa_file, 'r') as f:
                    data = json.load(f)
                    project = data.get('project_id')
                    if project:
                        print(f"✅ Project from service account: {project}")
                        return project
            except:
                pass
        
        # Default fallback
        return 'unidad-cumplimiento-aa245'
    
    return {
        'project_id': get_project_id(),
        'project_key': project_key,
        'environment': detect_environment(),
        'batch_size': int(os.getenv('FIRESTORE_BATCH_SIZE', '500')),
        'timeout': int(os.getenv('FIRESTORE_TIMEOUT', '30'))
    }

# === AUTO-SETUP INTEGRATION ===

def check_adc_authentication() -> tuple[bool, str]:
    """Check if Application Default Credentials are configured"""
    try:
        # Test ADC directly with firebase-admin
        from firebase_admin import credentials
        creds = credentials.ApplicationDefault()
        return True, "ADC available"
    except Exception as e:
        try:
            # Fallback: check gcloud
            import subprocess
            result = subprocess.run(
                ['gcloud', 'config', 'get-value', 'project'],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0 and result.stdout.strip():
                return True, result.stdout.strip()
        except:
            pass
        return False, f"ADC not available: {e}"

def auto_setup_firebase_if_needed() -> bool:
    """Check if Firebase can use ADC (Application Default Credentials)"""
    try:
        # Test ADC directly
        adc_available, message = check_adc_authentication()
        if adc_available:
            print(f"✅ Application Default Credentials available: {message}")
            return True
        
        # Check for service account file
        if os.path.exists('firebase-service-account.json'):
            print("✅ Service account file found")
            return True
        
        # Check environment variables
        if os.getenv('FIREBASE_SERVICE_ACCOUNT_KEY'):
            print("✅ Service account key in environment")
            return True
        
        print(f"⚠️ No Firebase credentials found: {message}")
        return False
                
    except Exception as e:
        print(f"⚠️ Firebase configuration check error: {e}")
        return False

# === FUNCTIONAL FIREBASE SETUP ===

def create_service_account_credentials() -> Optional[Dict[str, Any]]:
    """Create service account credentials - SIMPLIFIED"""
    
    # Método 1: JSON codificado en base64 (para producción)
    for env_var in ['FIREBASE_SERVICE_ACCOUNT_KEY', 'GOOGLE_APPLICATION_CREDENTIALS_JSON']:
        encoded_key = os.getenv(env_var)
        if encoded_key:
            try:
                import base64
                if encoded_key.strip().startswith('{'):
                    # JSON plano
                    return json.loads(encoded_key)
                else:
                    # Base64 encoded
                    decoded = base64.b64decode(encoded_key).decode('utf-8')
                    return json.loads(decoded)
            except Exception as e:
                print(f"⚠️ Error decoding {env_var}: {e}")
    
    # Método 2: Variables individuales
    required_vars = {
        'project_id': 'FIREBASE_PROJECT_ID',
        'private_key_id': 'FIREBASE_PRIVATE_KEY_ID',
        'private_key': 'FIREBASE_PRIVATE_KEY',
        'client_email': 'FIREBASE_CLIENT_EMAIL',
        'client_id': 'FIREBASE_CLIENT_ID'
    }
    
    env_values = {}
    for key, env_var in required_vars.items():
        env_values[key] = os.getenv(env_var)
    
    if all(env_values.values()):
        return {
            "type": "service_account",
            "project_id": env_values['project_id'],
            "private_key_id": env_values['private_key_id'],
            "private_key": env_values['private_key'].replace('\\n', '\n'),
            "client_email": env_values['client_email'],
            "client_id": env_values['client_id'],
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            "client_x509_cert_url": f"https://www.googleapis.com/robot/v1/metadata/x509/{env_values['client_email']}"
        }
    
    return None

def create_application_default_credentials():
    """Create Application Default Credentials (for local development)"""
    try:
        import firebase_admin
        from firebase_admin import credentials
        return credentials.ApplicationDefault()
    except Exception as e:
        print(f"ADC Error: {e}")
        return None

def create_credentials_for_environment(env: str, project_key: str = 'default'):
    """Create appropriate credentials - SIMPLIFIED"""
    from firebase_admin import credentials
    
    print(f"� Creating credentials for {env} environment")
    
    # Prioridad 1: Application Default Credentials (funciona en todos los entornos)
    try:
        creds = credentials.ApplicationDefault()
        print("✅ Using Application Default Credentials")
        return creds
    except Exception as e:
        print(f"⚠️ ADC not available: {e}")
    
    # Prioridad 2: Service account desde variables de entorno
    service_creds = create_service_account_credentials()
    if service_creds:
        try:
            creds = credentials.Certificate(service_creds)
            print("✅ Using service account from environment")
            return creds
        except Exception as e:
            print(f"⚠️ Service account env failed: {e}")
    
    # Prioridad 3: Service account desde archivo
    sa_file = 'firebase-service-account.json'
    if os.path.exists(sa_file):
        try:
            creds = credentials.Certificate(sa_file)
            print(f"✅ Using service account file: {sa_file}")
            return creds
        except Exception as e:
            print(f"⚠️ Service account file failed: {e}")
    
    print("❌ No valid credentials found")
    print("💡 Please set FIREBASE_SERVICE_ACCOUNT_KEY environment variable")
    print("💡 Or run: gcloud auth application-default login")
    return None

# === FIREBASE INITIALIZATION ===

def initialize_firebase_app(project_key: str = 'default'):
    """Initialize Firebase app - SIMPLIFIED"""
    try:
        import firebase_admin
        
        # Check if app already exists
        try:
            return firebase_admin.get_app()
        except ValueError:
            pass  # App doesn't exist, create it
        
        config = get_project_config(project_key)
        
        # Test ADC first directly
        from firebase_admin import credentials
        try:
            creds = credentials.ApplicationDefault()
            print("✅ Using Application Default Credentials")
        except Exception as adc_error:
            print(f"⚠️ ADC failed: {adc_error}")
            creds = create_credentials_for_environment(config['environment'], project_key)
            if not creds:
                print("❌ No credentials found. Please run:")
                print("   gcloud auth application-default login")
                return None
        
        # Initialize with project config
        app = firebase_admin.initialize_app(creds, {
            'projectId': config['project_id']
        })
        
        print(f"✅ Firebase initialized - {config['environment']} - {config['project_id']}")
        return app
        
    except ImportError:
        print("❌ Firebase Admin SDK not installed: pip install firebase-admin")
        return None
    except Exception as e:
        print(f"❌ Firebase initialization failed: {e}")
        return None

def get_firestore_client(project_key: str = 'default'):
    """Get Firestore client - SIMPLIFIED"""
    app = initialize_firebase_app(project_key)
    if not app:
        return None
    
    try:
        from firebase_admin import firestore
        return firestore.client(app)
    except Exception as e:
        print(f"❌ Firestore client error: {e}")
        return None

# === HEALTH CHECKS ===

def test_firebase_connection(project_key: str = 'default') -> Tuple[bool, str]:
    """Test Firebase connection - returns (success, message)"""
    try:
        client = get_firestore_client(project_key)
        if not client:
            return False, f"No Firestore client available for {project_key}"
        
        # Simple test - create collection reference
        test_ref = client.collection('_health_check')
        if test_ref:
            return True, f"Firebase connection successful for {project_key}"
        
        return False, f"Could not create collection reference for {project_key}"
        
    except Exception as e:
        return False, f"Connection test failed for {project_key}: {str(e)[:100]}"

# === PUBLIC API ===

class FirebaseManager:
    """Simplified Firebase manager"""
    
    @staticmethod
    def is_available() -> bool:
        """Check if Firebase is available"""
        try:
            import firebase_admin
            from firebase_admin import credentials, firestore
            return True
        except ImportError:
            return False
        except Exception:
            return False
    
    @staticmethod
    def get_client(project_key: str = 'default'):
        """Get Firestore client"""
        return get_firestore_client(project_key)
    
    @staticmethod
    def get_firestore_client(project_key: str = 'default'):
        """Alias for get_client()"""
        return get_firestore_client(project_key)
    
    @staticmethod
    def test_connection(project_key: str = 'default') -> Dict[str, Any]:
        """Test connection and return status"""
        success, message = test_firebase_connection(project_key)
        config = get_project_config(project_key)
        
        return {
            'available': FirebaseManager.is_available(),
            'connected': success,
            'message': message,
            'environment': config['environment'],
            'project_id': config['project_id'],
            'project_key': project_key
        }
    
    @staticmethod
    def setup(project_key: str = 'default') -> bool:
        """Setup Firebase completely"""
        if not FirebaseManager.is_available():
            print("❌ Firebase SDK not available")
            return False
        
        app = initialize_firebase_app(project_key)
        if not app:
            return False
        
        success, message = test_firebase_connection(project_key)
        if not success:
            print(f"❌ Connection test failed: {message}")
            return False
        
        config = get_project_config(project_key)
        print(f"✅ Firebase setup complete - {config['environment']}")
        return True

# === BACKWARDS COMPATIBILITY ===

# Export functions for existing code
initialize_firebase = FirebaseManager.setup
test_connection = lambda: test_firebase_connection()[0]
setup_firebase = FirebaseManager.setup

# Export constants
PROJECT_ID = get_project_config()['project_id']
FIREBASE_AVAILABLE = FirebaseManager.is_available()

# Convenience functions (simplified)
def get_default_client():
    """Get default Firestore client"""
    return get_firestore_client('default')

if __name__ == "__main__":
    print("🚂 Firebase Multi-Project Auto-Configuration")
    print("=" * 60)
    
    # Test all project connections
    all_statuses = FirebaseManager.test_all_connections()
    
    print("\n📊 PROJECT STATUS SUMMARY:")
    print("-" * 60)
    
    connected_count = 0
    for project_key, status in all_statuses.items():
        icon = "✅" if status['connected'] else "❌"
        print(f"{icon} {project_key.upper()}: {status['project_id']}")
        print(f"   Environment: {status['environment']}")
        print(f"   Connected: {status['connected']}")
        print(f"   Message: {status['message']}")
        print()
        
        if status['connected']:
            connected_count += 1
    
    print(f"🎯 SUMMARY: {connected_count}/{len(all_statuses)} projects connected")
    
    if connected_count > 0:
        print("✅ Ready for multi-project production!")
        
        # Show available clients
        clients = get_project_clients()
        if clients:
            print(f"\n🔗 Available Firestore clients: {list(clients.keys())}")
            
            # Special mention for unidad-cumplimiento
            if 'unidad-cumplimiento' in clients:
                uc_client = get_unidad_cumplimiento_client()
                if uc_client:
                    print("🎯 unidad-cumplimiento-aa245 client ready!")
    else:
        print("❌ Setup required for all projects")
        print("\n💡 Configuration options:")
        print("   🔑 Workload Identity Federation (recommended): gcloud auth application-default login")
        print("   📝 Environment variables: Set project-specific vars")
        print("   📁 Service account files: Create project-specific JSON files")
        
    print("\n� MULTI-PROJECT USAGE:")
    print("   FirebaseManager.get_client('default')              # Default project")
    print("   FirebaseManager.get_client('unidad-cumplimiento')  # unidad-cumplimiento-aa245")
    print("   get_unidad_cumplimiento_client()                   # Convenience function")
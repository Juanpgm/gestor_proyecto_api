"""
Firebase Auto-Configuration - Functional Programming Approach
Detects environment automatically and configures Firebase for both local and Railway deployment
Integrates with Google Workload Identity Federation auto-setup
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
    """Get project configuration with automatic detection and multi-project support"""
    
    # Auto-detect project ID from multiple sources with multi-project support
    def get_project_id(project_key: str = 'default') -> str:
        # Multi-project environment variable mapping
        project_env_vars = {
            'default': ['FIREBASE_PROJECT_ID', 'GOOGLE_CLOUD_PROJECT'],
            'secondary': ['FIREBASE_PROJECT_ID_2', 'GOOGLE_CLOUD_PROJECT_2'],
            'unidad-cumplimiento': ['FIREBASE_PROJECT_ID_UNIDAD', 'GOOGLE_CLOUD_PROJECT_UNIDAD']
        }
        
        # Priority 1: Environment variables (project-specific)
        env_vars = project_env_vars.get(project_key, project_env_vars['default'])
        for env_var in env_vars:
            env_project = os.getenv(env_var)
            if env_project and env_project != 'your-project-id':
                print(f"✅ Project ID from {env_var}: {env_project}")
                return env_project
        
        # Priority 2: gcloud default project (for default project only)
        if project_key == 'default':
            try:
                import subprocess
                # Try different gcloud paths (Windows prioritizes .cmd)
                gcloud_paths = [
                    'gcloud.cmd',  # Windows batch file - works!
                    'gcloud',
                    'C:\\Users\\juanp\\AppData\\Local\\cloud-code\\installer\\google-cloud-sdk\\bin\\gcloud.cmd',
                    os.path.expanduser('~\\AppData\\Local\\Google\\Cloud SDK\\google-cloud-sdk\\bin\\gcloud.cmd')
                ]
                
                for gcloud_path in gcloud_paths:
                    try:
                        result = subprocess.run(
                            [gcloud_path, 'config', 'get-value', 'project'],
                            capture_output=True,
                            text=True,
                            check=True,
                            timeout=10
                        )
                        gcloud_project = result.stdout.strip()
                        if gcloud_project and gcloud_project != 'None':
                            print(f"✅ gcloud project detected: {gcloud_project}")
                            return gcloud_project
                    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
                        continue
            except Exception as e:
                print(f"⚠️ gcloud detection error: {e}")
                pass
        
        # Priority 3: Service account file (project-specific)
        service_account_files = {
            'default': 'firebase-service-account.json',
            'secondary': 'firebase-service-account-2.json',  
            'unidad-cumplimiento': 'firebase-service-account-unidad.json'
        }
        
        sa_file = service_account_files.get(project_key, service_account_files['default'])
        if os.path.exists(sa_file):
            try:
                with open(sa_file, 'r') as f:
                    sa_data = json.load(f)
                    project_id = sa_data.get('project_id', 'unknown-project')
                    print(f"✅ Project ID from {sa_file}: {project_id}")
                    return project_id
            except Exception as e:
                print(f"⚠️ Error reading {sa_file}: {e}")
                pass
        
        # Priority 4: Hardcoded project mappings
        hardcoded_projects = {
            'default': 'your-project-id',
            'secondary': 'unidad-cumplimiento-aa245',
            'unidad-cumplimiento': 'unidad-cumplimiento-aa245'
        }
        
        return hardcoded_projects.get(project_key, 'your-project-id')
    
    return {
        'project_id': get_project_id(project_key),
        'project_key': project_key,
        'environment': detect_environment(),
        'batch_size': int(os.getenv('FIRESTORE_BATCH_SIZE', '500')),
        'timeout': int(os.getenv('FIRESTORE_TIMEOUT', '30'))
    }

# === AUTO-SETUP INTEGRATION ===

def check_adc_authentication() -> tuple[bool, str]:
    """Check if Application Default Credentials are configured"""
    try:
        import subprocess
        
        # Check if gcloud is configured
        result = subprocess.run(
            ['gcloud', 'config', 'get-value', 'project'],
            capture_output=True,
            text=True,
            check=True,
            timeout=10
        )
        
        project_id = result.stdout.strip()
        if project_id and project_id != 'None':
            return True, project_id
        else:
            return False, "No default project configured"
            
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        return False, "gcloud not configured or not available"

def auto_setup_firebase_if_needed() -> bool:
    """Check if Firebase can use ADC (Application Default Credentials)"""
    try:
        # Priority 1: Check ADC first (most secure and automatic)
        adc_available, project_or_message = check_adc_authentication()
        if adc_available:
            print(f"✅ Using Application Default Credentials for project: {project_or_message}")
            return True
        
        # Priority 2: Check for service account file
        if os.path.exists('firebase-service-account.json'):
            print("✅ Using service account file: firebase-service-account.json")
            return True
        
        # Priority 3: Check environment variables
        if all(os.getenv(var) for var in ['FIREBASE_PROJECT_ID', 'FIREBASE_CLIENT_EMAIL']):
            print("✅ Using environment variables for Firebase authentication")
            return True
        
        # No authentication method available
        print("⚠️ Firebase not configured. Recommended setup:")
        print("   🚀 EASIEST: gcloud auth application-default login")
        print("   📋 Alternative: Set environment variables")
        print("   📁 Alternative: Create firebase-service-account.json file")
        return False
                
    except Exception as e:
        print(f"⚠️ Firebase configuration check error: {e}")
        return False

# === FUNCTIONAL FIREBASE SETUP ===

def create_service_account_credentials(project_key: str = 'default') -> Optional[Dict[str, Any]]:
    """Create service account credentials from multiple sources with multi-project support"""
    
    # Multi-project environment variable mapping
    env_var_mappings = {
        'default': {
            'encoded_key': ['FIREBASE_SERVICE_ACCOUNT_KEY', 'GOOGLE_APPLICATION_CREDENTIALS_JSON'],
            'project_id': 'FIREBASE_PROJECT_ID',
            'private_key_id': 'FIREBASE_PRIVATE_KEY_ID',
            'private_key': 'FIREBASE_PRIVATE_KEY',
            'client_email': 'FIREBASE_CLIENT_EMAIL',
            'client_id': 'FIREBASE_CLIENT_ID'
        },
        'secondary': {
            'encoded_key': ['FIREBASE_SERVICE_ACCOUNT_KEY_2', 'GOOGLE_APPLICATION_CREDENTIALS_JSON_2'],
            'project_id': 'FIREBASE_PROJECT_ID_2',
            'private_key_id': 'FIREBASE_PRIVATE_KEY_ID_2',
            'private_key': 'FIREBASE_PRIVATE_KEY_2',
            'client_email': 'FIREBASE_CLIENT_EMAIL_2',
            'client_id': 'FIREBASE_CLIENT_ID_2'
        },
        'unidad-cumplimiento': {
            'encoded_key': ['FIREBASE_SERVICE_ACCOUNT_KEY_UNIDAD', 'GOOGLE_APPLICATION_CREDENTIALS_JSON_UNIDAD'],
            'project_id': 'FIREBASE_PROJECT_ID_UNIDAD',
            'private_key_id': 'FIREBASE_PRIVATE_KEY_ID_UNIDAD',
            'private_key': 'FIREBASE_PRIVATE_KEY_UNIDAD',
            'client_email': 'FIREBASE_CLIENT_EMAIL_UNIDAD',
            'client_id': 'FIREBASE_CLIENT_ID_UNIDAD'
        }
    }
    
    # Get environment variable mapping for this project
    env_vars = env_var_mappings.get(project_key, env_var_mappings['default'])
    
    # Method 0: Base64 encoded JSON (MOST SECURE for deployment)
    for encoded_key_var in env_vars['encoded_key']:
        encoded_key = os.getenv(encoded_key_var)
        if encoded_key:
            try:
                import base64
                # Handle both base64 encoded and plain JSON
                if encoded_key.strip().startswith('{'):
                    # Plain JSON string
                    creds = json.loads(encoded_key)
                    print(f"✅ Using plain JSON from {encoded_key_var} for {project_key}")
                    return creds
                else:
                    # Base64 encoded JSON
                    decoded = base64.b64decode(encoded_key).decode('utf-8')
                    creds = json.loads(decoded)
                    print(f"✅ Using base64 JSON from {encoded_key_var} for {project_key}")
                    return creds
            except Exception as e:
                print(f"⚠️ Failed to decode service account key from {encoded_key_var}: {e}")
    
    # Method 1: Individual environment variables
    required_vars = ['project_id', 'private_key_id', 'private_key', 'client_email', 'client_id']
    env_values = {}
    
    for var in required_vars:
        env_var_name = env_vars[var]
        env_values[var] = os.getenv(env_var_name)
    
    if all(env_values.values()):
        print(f"✅ Using individual env vars for {project_key}")
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
    
    # Method 2: Service account file (project-specific)
    service_account_files = {
        'default': ['firebase-service-account.json', 'service-account.json'],
        'secondary': ['firebase-service-account-2.json', 'service-account-2.json'],  
        'unidad-cumplimiento': ['firebase-service-account-unidad.json', 'service-account-unidad.json']
    }
    
    # Add GOOGLE_APPLICATION_CREDENTIALS if available
    gac_file = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
    if gac_file:
        service_account_files[project_key] = service_account_files.get(project_key, []) + [gac_file]
    
    possible_files = service_account_files.get(project_key, service_account_files['default'])
    
    for file_path in possible_files:
        if file_path and os.path.exists(file_path):
            try:
                with open(file_path, 'r') as f:
                    creds = json.load(f)
                    print(f"✅ Using service account file {file_path} for {project_key}")
                    return creds
            except Exception as e:
                print(f"⚠️ Error reading {file_path}: {e}")
                continue
    
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
    """Create appropriate credentials with production priority and multi-project support"""
    from firebase_admin import credentials
    
    print(f"🔍 DEBUG: Environment detected: {env}, Project: {project_key}")
    
    # Priority 1: Production environments - Service Account from env vars (most secure for deployment)
    if env in ['railway', 'vercel', 'heroku', 'gcp']:
        print(f"🚀 PRODUCTION mode for {env} - Project: {project_key}")
        
        # Try service account credentials for this specific project
        service_creds = create_service_account_credentials(project_key)
        if service_creds:
            try:
                cert_creds = credentials.Certificate(service_creds)
                print(f"✅ Using service account credentials for {project_key}")
                return cert_creds
            except Exception as env_error:
                print(f"❌ Service account failed for {project_key}: {env_error}")
    
    # Priority 2: Local development - Try Application Default Credentials (only for default project)
    else:
        print(f"🏠 LOCAL development mode - Project: {project_key}")
        
        # For local development, prioritize Workload Identity Federation (ADC)
        # ADC can work for any project if gcloud is configured with the right project
        try:
            adc_creds = credentials.ApplicationDefault()
            print(f"✅ Using Application Default Credentials (ADC) - Workload Identity Federation for {project_key}")
            return adc_creds
        except Exception as adc_error:
            print(f"⚠️ ADC not available for {project_key}: {adc_error}")
        
        # For secondary projects in local development, try service account
        service_creds = create_service_account_credentials(project_key)
        if service_creds:
            try:
                cert_creds = credentials.Certificate(service_creds)
                print(f"✅ Using service account file for {project_key} in local development")
                return cert_creds
            except Exception as file_error:
                print(f"❌ Service account failed for {project_key}: {file_error}")
    
    # Priority 3: Fallback - Try service account file (both environments)
    service_account_files = {
        'default': 'firebase-service-account.json',
        'secondary': 'firebase-service-account-2.json',  
        'unidad-cumplimiento': 'firebase-service-account-unidad.json'
    }
    
    sa_file = service_account_files.get(project_key, service_account_files['default'])
    if os.path.exists(sa_file):
        print(f"📁 Found service account file: {sa_file}")
        try:
            file_creds = credentials.Certificate(sa_file)
            print(f"✅ Using service account file {sa_file}")
            return file_creds
        except Exception as file_error:
            print(f"❌ Service account file failed: {file_error}")
    else:
        print(f"📁 No service account file found: {sa_file}")
    
    # No valid credentials found
    print(f"❌ No valid credentials found for {project_key}")
    print(f"🔍 DEBUG: Environment variables checked for {project_key}:")
    
    # Show debug info based on project key
    env_var_mappings = {
        'default': ['FIREBASE_PROJECT_ID', 'FIREBASE_SERVICE_ACCOUNT_KEY', 'FIREBASE_CLIENT_EMAIL'],
        'secondary': ['FIREBASE_PROJECT_ID_2', 'FIREBASE_SERVICE_ACCOUNT_KEY_2', 'FIREBASE_CLIENT_EMAIL_2'],
        'unidad-cumplimiento': ['FIREBASE_PROJECT_ID_UNIDAD', 'FIREBASE_SERVICE_ACCOUNT_KEY_UNIDAD', 'FIREBASE_CLIENT_EMAIL_UNIDAD']
    }
    
    env_vars = env_var_mappings.get(project_key, env_var_mappings['default'])
    for var in env_vars:
        has_var = bool(os.getenv(var))
        print(f"   {var}: {'✅' if has_var else '❌'}")
    
    return None

# === FIREBASE INITIALIZATION ===

def initialize_firebase_app(project_key: str = 'default'):
    """Initialize Firebase app with functional approach, auto-setup and multi-project support"""
    try:
        import firebase_admin
        
        # Generate app name for multi-project support
        app_name = f"firebase-app-{project_key}" if project_key != 'default' else firebase_admin._DEFAULT_APP_NAME
        
        # Try to get existing app
        try:
            return firebase_admin.get_app(app_name)
        except ValueError:
            pass
        
        # Check Firebase configuration
        if not auto_setup_firebase_if_needed():
            print(f"⚠️ Firebase not configured for {project_key}, trying with available credentials...")
        
        config = get_project_config(project_key)
        creds = create_credentials_for_environment(config['environment'], project_key)
        
        if not creds:
            print(f"❌ No valid credentials found for {project_key}. Please configure Firebase:")
            print("   1. Set environment variables OR")
            print("   2. Create project-specific service account file OR") 
            print("   3. Run: gcloud auth application-default login (for default project)")
            return None
        
        # Initialize app with project-specific name
        if app_name == firebase_admin._DEFAULT_APP_NAME:
            app = firebase_admin.initialize_app(creds, {
                'projectId': config['project_id']
            })
        else:
            app = firebase_admin.initialize_app(creds, {
                'projectId': config['project_id']
            }, name=app_name)
        
        print(f"✅ Firebase initialized - {config['environment']} environment - Project: {project_key} ({config['project_id']})")
        return app
        
    except ImportError:
        print("⚠️ Firebase Admin SDK not available. Install with:")
        print("   pip install firebase-admin")
        return None
    except Exception as e:
        print(f"❌ Firebase initialization failed for {project_key}: {e}")
        print("💡 Please configure Firebase authentication")
        return None

def get_firestore_client(project_key: str = 'default'):
    """Get Firestore client with caching and multi-project support"""
    app = initialize_firebase_app(project_key)
    if not app:
        return None
    
    try:
        from firebase_admin import firestore
        return firestore.client(app)
    except Exception as e:
        print(f"❌ Firestore client error for {project_key}: {e}")
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
    """Functional Firebase manager with lazy initialization and multi-project support"""
    
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
        """Get Firestore client for specific project"""
        return get_firestore_client(project_key)
    
    @staticmethod
    def get_firestore_client(project_key: str = 'default'):
        """Alias for get_client() for backwards compatibility"""
        return get_firestore_client(project_key)
    
    @staticmethod
    def test_connection(project_key: str = 'default') -> Dict[str, Any]:
        """Test connection and return status for specific project"""
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
    def test_all_connections() -> Dict[str, Dict[str, Any]]:
        """Test connections for all configured projects"""
        results = {}
        
        # Test all known project configurations
        project_keys = ['default', 'secondary', 'unidad-cumplimiento']
        
        for project_key in project_keys:
            try:
                config = get_project_config(project_key)
                # Only test if project_id is not the fallback value
                if config['project_id'] != 'your-project-id':
                    results[project_key] = FirebaseManager.test_connection(project_key)
                else:
                    results[project_key] = {
                        'available': FirebaseManager.is_available(),
                        'connected': False,
                        'message': f'No configuration found for {project_key}',
                        'environment': config['environment'],
                        'project_id': config['project_id'],
                        'project_key': project_key
                    }
            except Exception as e:
                results[project_key] = {
                    'available': FirebaseManager.is_available(),
                    'connected': False,
                    'message': f'Error testing {project_key}: {str(e)}',
                    'environment': 'unknown',
                    'project_id': 'unknown',
                    'project_key': project_key
                }
        
        return results
    
    @staticmethod
    def setup(project_key: str = 'default') -> bool:
        """Setup Firebase completely for specific project"""
        if not FirebaseManager.is_available():
            print("❌ Firebase SDK not available")
            return False
        
        app = initialize_firebase_app(project_key)
        if not app:
            print(f"❌ Firebase initialization failed for {project_key}")
            return False
        
        success, message = test_firebase_connection(project_key)
        if not success:
            print(f"❌ Connection test failed for {project_key}: {message}")
            return False
        
        config = get_project_config(project_key)
        print(f"✅ Firebase setup complete for {project_key} - {config['environment']}")
        return True
    
    @staticmethod
    def setup_all() -> Dict[str, bool]:
        """Setup all configured Firebase projects"""
        results = {}
        project_keys = ['default', 'secondary', 'unidad-cumplimiento']
        
        for project_key in project_keys:
            try:
                config = get_project_config(project_key)
                # Only setup if project_id is not the fallback value
                if config['project_id'] != 'your-project-id':
                    results[project_key] = FirebaseManager.setup(project_key)
                else:
                    results[project_key] = False
                    print(f"⚠️ Skipping {project_key} - no configuration found")
            except Exception as e:
                results[project_key] = False
                print(f"❌ Error setting up {project_key}: {e}")
        
        return results

# === BACKWARDS COMPATIBILITY ===

# Export functions for existing code
initialize_firebase = FirebaseManager.setup
test_connection = lambda: test_firebase_connection()[0]
setup_firebase = FirebaseManager.setup

# Export constants
PROJECT_ID = get_project_config()['project_id']
FIREBASE_AVAILABLE = FirebaseManager.is_available()

# Multi-project convenience functions
def get_project_clients() -> Dict[str, Any]:
    """Get all available Firestore clients"""
    clients = {}
    project_keys = ['default', 'secondary', 'unidad-cumplimiento']
    
    for project_key in project_keys:
        try:
            config = get_project_config(project_key)
            if config['project_id'] != 'your-project-id':
                client = get_firestore_client(project_key)
                if client:
                    clients[project_key] = {
                        'client': client,
                        'project_id': config['project_id'],
                        'environment': config['environment']
                    }
        except Exception as e:
            print(f"⚠️ Could not get client for {project_key}: {e}")
    
    return clients

def get_unidad_cumplimiento_client():
    """Convenience function to get the unidad-cumplimiento client specifically"""
    return get_firestore_client('unidad-cumplimiento')

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
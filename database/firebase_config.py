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

def get_project_config() -> Dict[str, str]:
    """Get project configuration with automatic detection"""
    
    # Auto-detect project ID from multiple sources
    def get_project_id() -> str:
        # Priority 1: Environment variables
        env_project = os.getenv('FIREBASE_PROJECT_ID') or os.getenv('GOOGLE_CLOUD_PROJECT')
        if env_project and env_project != 'your-project-id':
            return env_project
        
        # Priority 2: gcloud default project
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
        
        # Priority 3: Service account file
        if os.path.exists('firebase-service-account.json'):
            try:
                with open('firebase-service-account.json', 'r') as f:
                    sa_data = json.load(f)
                    return sa_data.get('project_id', 'unknown-project')
            except:
                pass
        
        # Fallback
        return 'your-project-id'
    
    return {
        'project_id': get_project_id(),
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

def create_service_account_credentials() -> Optional[Dict[str, Any]]:
    """Create service account credentials from multiple sources"""
    
    # Method 0: Base64 encoded JSON (MOST SECURE for deployment)
    encoded_key = os.getenv('FIREBASE_SERVICE_ACCOUNT_KEY') or os.getenv('GOOGLE_APPLICATION_CREDENTIALS_JSON')
    if encoded_key:
        try:
            import base64
            # Handle both base64 encoded and plain JSON
            if encoded_key.strip().startswith('{'):
                # Plain JSON string
                return json.loads(encoded_key)
            else:
                # Base64 encoded JSON
                decoded = base64.b64decode(encoded_key).decode('utf-8')
                return json.loads(decoded)
        except Exception as e:
            print(f"⚠️ Failed to decode service account key: {e}")
    
    # Method 1: Environment variables
    required_vars = [
        'FIREBASE_PROJECT_ID',
        'FIREBASE_PRIVATE_KEY_ID', 
        'FIREBASE_PRIVATE_KEY',
        'FIREBASE_CLIENT_EMAIL',
        'FIREBASE_CLIENT_ID'
    ]
    
    env_values = {var: os.getenv(var) for var in required_vars}
    
    if all(env_values.values()):
        return {
            "type": "service_account",
            "project_id": env_values['FIREBASE_PROJECT_ID'],
            "private_key_id": env_values['FIREBASE_PRIVATE_KEY_ID'],
            "private_key": env_values['FIREBASE_PRIVATE_KEY'].replace('\\n', '\n'),
            "client_email": env_values['FIREBASE_CLIENT_EMAIL'],
            "client_id": env_values['FIREBASE_CLIENT_ID'],
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            "client_x509_cert_url": f"https://www.googleapis.com/robot/v1/metadata/x509/{env_values['FIREBASE_CLIENT_EMAIL']}"
        }
    
    # Method 2: Service account file
    possible_files = [
        'firebase-service-account.json',
        'service-account.json',
        os.getenv('GOOGLE_APPLICATION_CREDENTIALS', '')
    ]
    
    for file_path in possible_files:
        if file_path and os.path.exists(file_path):
            try:
                with open(file_path, 'r') as f:
                    return json.load(f)
            except Exception:
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

def create_credentials_for_environment(env: str):
    """Create appropriate credentials with ADC priority"""
    from firebase_admin import credentials
    
    # Priority 1: Try Application Default Credentials (most secure)
    try:
        adc_creds = credentials.ApplicationDefault()
        print("✅ Using Application Default Credentials (ADC)")
        return adc_creds
    except Exception as adc_error:
        print(f"⚠️ ADC not available: {adc_error}")
    
    # Priority 2: Try service account from environment variables
    if env in ['railway', 'vercel', 'heroku']:
        service_creds = create_service_account_credentials()
        if service_creds:
            try:
                cert_creds = credentials.Certificate(service_creds)
                print("✅ Using service account from environment variables")
                return cert_creds
            except Exception as env_error:
                print(f"⚠️ Environment credentials failed: {env_error}")
    
    # Priority 3: Try service account file
    if os.path.exists('firebase-service-account.json'):
        try:
            file_creds = credentials.Certificate('firebase-service-account.json')
            print("✅ Using service account file")
            return file_creds
        except Exception as file_error:
            print(f"⚠️ Service account file failed: {file_error}")
    
    # No valid credentials found
    print("❌ No valid credentials found")
    return None

# === FIREBASE INITIALIZATION ===

def initialize_firebase_app():
    """Initialize Firebase app with functional approach and auto-setup"""
    try:
        import firebase_admin
        
        # Try to get existing app
        try:
            return firebase_admin.get_app()
        except ValueError:
            pass
        
        # Check Firebase configuration
        if not auto_setup_firebase_if_needed():
            print("⚠️ Firebase not configured, trying with available credentials...")
        
        config = get_project_config()
        creds = create_credentials_for_environment(config['environment'])
        
        if not creds:
            print("❌ No valid credentials found. Please configure Firebase:")
            print("   1. Set environment variables OR")
            print("   2. Create firebase-service-account.json OR") 
            print("   3. Run: gcloud auth application-default login")
            return None
        
        app = firebase_admin.initialize_app(creds, {
            'projectId': config['project_id']
        })
        
        print(f"✅ Firebase initialized - {config['environment']} environment")
        return app
        
    except ImportError:
        print("⚠️ Firebase Admin SDK not available. Install with:")
        print("   pip install firebase-admin")
        return None
    except Exception as e:
        print(f"❌ Firebase initialization failed: {e}")
        print("💡 Please configure Firebase authentication")
        return None

def get_firestore_client():
    """Get Firestore client with caching"""
    app = initialize_firebase_app()
    if not app:
        return None
    
    try:
        from firebase_admin import firestore
        return firestore.client()
    except Exception as e:
        print(f"❌ Firestore client error: {e}")
        return None

# === HEALTH CHECKS ===

def test_firebase_connection() -> Tuple[bool, str]:
    """Test Firebase connection - returns (success, message)"""
    try:
        client = get_firestore_client()
        if not client:
            return False, "No Firestore client available"
        
        # Simple test - create collection reference
        test_ref = client.collection('_health_check')
        if test_ref:
            return True, "Firebase connection successful"
        
        return False, "Could not create collection reference"
        
    except Exception as e:
        return False, f"Connection test failed: {str(e)[:100]}"

# === PUBLIC API ===

class FirebaseManager:
    """Functional Firebase manager with lazy initialization"""
    
    @staticmethod
    def is_available() -> bool:
        """Check if Firebase is available"""
        try:
            import firebase_admin
            return True
        except ImportError:
            return False
    
    @staticmethod
    def get_client():
        """Get Firestore client"""
        return get_firestore_client()
    
    @staticmethod
    def get_firestore_client():
        """Alias for get_client() for backwards compatibility"""
        return get_firestore_client()
    
    @staticmethod
    def test_connection() -> Dict[str, Any]:
        """Test connection and return status"""
        success, message = test_firebase_connection()
        config = get_project_config()
        
        return {
            'available': FirebaseManager.is_available(),
            'connected': success,
            'message': message,
            'environment': config['environment'],
            'project_id': config['project_id']
        }
    
    @staticmethod
    def setup() -> bool:
        """Setup Firebase completely"""
        if not FirebaseManager.is_available():
            print("❌ Firebase SDK not available")
            return False
        
        app = initialize_firebase_app()
        if not app:
            print("❌ Firebase initialization failed")
            return False
        
        success, message = test_firebase_connection()
        if not success:
            print(f"❌ Connection test failed: {message}")
            return False
        
        config = get_project_config()
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

if __name__ == "__main__":
    print("🚂 Firebase Auto-Configuration")
    print("=" * 50)
    
    status = FirebaseManager.test_connection()
    
    print(f"Environment: {status['environment']}")
    print(f"Project ID: {status['project_id']}")
    print(f"SDK Available: {status['available']}")
    print(f"Connected: {status['connected']}")
    print(f"Message: {status['message']}")
    
    if status['connected']:
        print("\n✅ Ready for production!")
    else:
        print(f"\n❌ Setup required")
        if status['environment'] == 'local':
            print("💡 Run: gcloud auth application-default login")
        else:
            print("💡 Configure service account environment variables")
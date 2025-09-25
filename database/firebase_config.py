"""
Firebase Auto-Configuration - Functional Programming Approach
Detects environment automatically and configures Firebase for both local and Railway deployment
Eliminates all duplicated and obsolete logic
"""

import os
from typing import Optional, Dict, Any, Tuple
from functools import lru_cache, partial
import json

# === ENVIRONMENT DETECTION ===

@lru_cache(maxsize=1)
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

@lru_cache(maxsize=1)
def get_project_config() -> Dict[str, str]:
    """Get project configuration based on environment"""
    return {
        'project_id': os.getenv('FIREBASE_PROJECT_ID', os.getenv('GOOGLE_CLOUD_PROJECT', 'your-project-id')),
        'environment': detect_environment(),
        'batch_size': int(os.getenv('FIRESTORE_BATCH_SIZE', '500')),
        'timeout': int(os.getenv('FIRESTORE_TIMEOUT', '30'))
    }

# === FUNCTIONAL FIREBASE SETUP ===

def create_service_account_credentials() -> Optional[Dict[str, Any]]:
    """Create service account credentials from environment variables"""
    # Check if all required env vars are present
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
    """Create appropriate credentials based on environment"""
    if env == 'railway':
        # Try service account first, fallback to ADC
        service_creds = create_service_account_credentials()
        if service_creds:
            try:
                from firebase_admin import credentials
                return credentials.Certificate(service_creds)
            except Exception:
                pass
        return create_application_default_credentials()
    else:
        # Local development - use ADC
        return create_application_default_credentials()

# === FIREBASE INITIALIZATION ===

@lru_cache(maxsize=1) 
def initialize_firebase_app():
    """Initialize Firebase app with functional approach"""
    try:
        import firebase_admin
        
        # Try to get existing app
        try:
            return firebase_admin.get_app()
        except ValueError:
            pass
        
        config = get_project_config()
        creds = create_credentials_for_environment(config['environment'])
        
        if not creds:
            raise Exception("No valid credentials found")
        
        app = firebase_admin.initialize_app(creds, {
            'projectId': config['project_id']
        })
        
        print(f"✅ Firebase initialized - {config['environment']} environment")
        return app
        
    except ImportError:
        print("⚠️ Firebase Admin SDK not available")
        return None
    except Exception as e:
        print(f"❌ Firebase initialization failed: {e}")
        return None

@lru_cache(maxsize=1)
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
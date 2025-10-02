"""
Firebase Configuration - Workload Identity Federation Priority
"""
import os
import firebase_admin
from firebase_admin import credentials, firestore
import json
import base64

PROJECT_ID = os.getenv("FIREBASE_PROJECT_ID", "unidad-cumplimiento-aa245")

def initialize_firebase():
    try:
        return firebase_admin.get_app()
    except ValueError:
        pass
    
    print(f"🚀 Initializing Firebase: {PROJECT_ID}")
    
    # PRIORITY 1: Workload Identity Federation (ADC)
    try:
        cred = credentials.ApplicationDefault()
        app = firebase_admin.initialize_app(cred, {"projectId": PROJECT_ID})
        print("✅ Using Application Default Credentials (Workload Identity)")
        return app
    except Exception as e:
        print(f"⚠️ ADC failed: {e}")
        
        # FALLBACK: Service Account
        sa_key = os.getenv("FIREBASE_SERVICE_ACCOUNT_KEY")
        if sa_key:
            try:
                if sa_key.startswith("{"):
                    creds_data = json.loads(sa_key)
                else:
                    creds_data = json.loads(base64.b64decode(sa_key).decode())
                
                cred = credentials.Certificate(creds_data)
                app = firebase_admin.initialize_app(cred, {"projectId": PROJECT_ID})
                print("✅ Using Service Account (fallback)")
                return app
            except Exception as sa_e:
                print(f"❌ Service Account failed: {sa_e}")
        
        print("💡 Run: gcloud auth application-default login")
        raise

def get_firestore_client():
    initialize_firebase()
    return firestore.client()

def get_default_client():
    return get_firestore_client()

# Constantes para compatibilidad
FIREBASE_AVAILABLE = True

try:
    import firebase_admin
    from firebase_admin import credentials, firestore
    FIREBASE_AVAILABLE = True
except ImportError:
    FIREBASE_AVAILABLE = False

class FirebaseManager:
    @staticmethod
    def get_client():
        return get_firestore_client()
    
    @staticmethod  
    def test_connection():
        try:
            client = get_firestore_client()
            test_ref = client.collection("_test")
            return {"connected": True, "message": f"Connected to {PROJECT_ID}"}
        except Exception as e:
            return {"connected": False, "message": str(e)}
    
    @staticmethod
    def is_available():
        return FIREBASE_AVAILABLE
    
    @staticmethod
    def setup():
        """Setup Firebase and return success status"""
        try:
            status = FirebaseManager.test_connection()
            return status.get('connected', False)
        except Exception:
            return False

if __name__ == "__main__":
    status = FirebaseManager.test_connection()
    print(f"Status: {status}")


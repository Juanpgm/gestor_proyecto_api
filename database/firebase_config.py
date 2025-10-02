"""
Firebase Configuration - Workload Identity Federation Priority
"""
import os
import firebase_admin
from firebase_admin import credentials, firestore
import json
import base64

PROJECT_ID = os.getenv("FIREBASE_PROJECT_ID", "unidad-cumplimiento-aa245")

def is_railway_environment():
    """Detect if we're running in Railway"""
    railway_indicators = [
        os.getenv("RAILWAY_ENVIRONMENT"),
        os.getenv("RAILWAY_PROJECT_ID"),
        os.getenv("RAILWAY_SERVICE_ID"),
        os.getenv("NIXPACKS_METADATA")  # Railway uses Nixpacks
    ]
    return any(railway_indicators)

def initialize_firebase():
    try:
        return firebase_admin.get_app()
    except ValueError:
        pass
    
    is_railway = is_railway_environment()
    print(f"🚀 Initializing Firebase: {PROJECT_ID}")
    print(f"🌍 Railway environment: {'YES' if is_railway else 'NO'}")
    
    # RAILWAY PRIORITY: Service Account only
    if is_railway:
        print("🚂 RAILWAY DETECTED - Using Service Account authentication")
        return initialize_firebase_with_service_account()
    
    # LOCAL PRIORITY: Workload Identity Federation (ADC) first
    print("🏠 LOCAL ENVIRONMENT - Trying Workload Identity Federation")
    try:
        cred = credentials.ApplicationDefault()
        app = firebase_admin.initialize_app(cred, {"projectId": PROJECT_ID})
        print("✅ Using Application Default Credentials (Workload Identity)")
        return app
    except Exception as e:
        print(f"⚠️ ADC failed: {e}")
        print("🔄 Fallback to Service Account...")
        return initialize_firebase_with_service_account()

def initialize_firebase_with_service_account():
    """Initialize Firebase with Service Account - optimized for Railway"""
    sa_key = os.getenv("FIREBASE_SERVICE_ACCOUNT_KEY")
    
    if not sa_key:
        print("❌ FIREBASE_SERVICE_ACCOUNT_KEY not found")
        print("💡 Set this environment variable in Railway dashboard")
        raise Exception("No Service Account Key available")
    
    print(f"🔑 Service Account Key found (length: {len(sa_key)})")
    
    try:
        # Try different parsing methods
        creds_data = None
        
        # Method 1: Plain JSON
        if sa_key.strip().startswith("{"):
            print("📝 Parsing as plain JSON")
            creds_data = json.loads(sa_key)
            
        # Method 2: Base64 encoded
        else:
            print("🔓 Decoding from Base64")
            try:
                decoded = base64.b64decode(sa_key).decode('utf-8')
                creds_data = json.loads(decoded)
            except Exception as b64_error:
                print(f"❌ Base64 decode failed: {b64_error}")
                # Method 3: Maybe it's URL-safe base64
                try:
                    decoded = base64.urlsafe_b64decode(sa_key).decode('utf-8')
                    creds_data = json.loads(decoded)
                    print("✅ Decoded with URL-safe Base64")
                except Exception as url_b64_error:
                    print(f"❌ URL-safe Base64 also failed: {url_b64_error}")
                    raise
        
        if not creds_data:
            raise Exception("Could not parse Service Account credentials")
        
        # Validate required fields
        required_fields = ['type', 'project_id', 'private_key', 'client_email']
        missing_fields = [field for field in required_fields if not creds_data.get(field)]
        
        if missing_fields:
            print(f"❌ Missing required fields: {missing_fields}")
            raise Exception(f"Invalid Service Account: missing {missing_fields}")
        
        print(f"✅ Service Account email: {creds_data.get('client_email')}")
        print(f"✅ Project ID in SA: {creds_data.get('project_id')}")
        
        # Initialize Firebase
        cred = credentials.Certificate(creds_data)
        app = firebase_admin.initialize_app(cred, {
            'projectId': creds_data.get('project_id', PROJECT_ID)
        })
        
        print("🎉 Firebase initialized successfully with Service Account")
        return app
        
    except json.JSONDecodeError as json_error:
        print(f"❌ JSON parsing failed: {json_error}")
        print("💡 Check that FIREBASE_SERVICE_ACCOUNT_KEY contains valid JSON")
        raise
    except Exception as e:
        print(f"❌ Service Account initialization failed: {e}")
        print(f"❌ Error type: {type(e).__name__}")
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
            # Get Firestore client
            client = get_firestore_client()
            if not client:
                return {"connected": False, "message": "Could not get Firestore client"}
            
            # Test 1: Create collection reference (basic test)
            test_ref = client.collection("_connection_test")
            if not test_ref:
                return {"connected": False, "message": "Could not create collection reference"}
            
            # Test 2: Try to read an actual collection (more thorough)
            try:
                collections = list(client.collections())
                collection_count = len(collections)
                
                return {
                    "connected": True, 
                    "message": f"Connected to {PROJECT_ID}",
                    "collections_found": collection_count,
                    "environment": "railway" if is_railway_environment() else "local"
                }
            except Exception as collection_error:
                # If we can't list collections, try a simpler test
                print(f"⚠️ Collection listing failed: {collection_error}")
                return {
                    "connected": True, 
                    "message": f"Basic connection to {PROJECT_ID} (limited access)",
                    "warning": str(collection_error)
                }
                
        except Exception as e:
            return {
                "connected": False, 
                "message": str(e),
                "error_type": type(e).__name__,
                "environment": "railway" if is_railway_environment() else "local"
            }
    
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


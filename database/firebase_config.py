"""
Firebase Configuration - Clean and Simple
Environment-aware authentication: Railway (Service Account) vs Local (ADC)
"""
import os
import firebase_admin
from firebase_admin import credentials, firestore
import json
import base64
import binascii
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

PROJECT_ID = os.getenv("FIREBASE_PROJECT_ID", "unidad-cumplimiento-aa245")

def is_railway_environment():
    """Detect if we're running in Railway"""
    return os.getenv("RAILWAY_ENVIRONMENT") is not None

def initialize_firebase():
    """Initialize Firebase based on environment"""
    try:
        return firebase_admin.get_app()
    except ValueError:
        pass
    
    logger.info(f"🚀 Initializing Firebase: {PROJECT_ID}")
    
    if is_railway_environment():
        logger.info("🚂 Railway environment - using Service Account")
        return initialize_with_service_account()
    else:
        logger.info("💻 Local environment - using Application Default Credentials")
        return initialize_with_adc()

def initialize_with_service_account():
    """Initialize Firebase with Service Account (Railway)"""
    sa_key = os.getenv("FIREBASE_SERVICE_ACCOUNT_KEY")
    
    if not sa_key:
        raise Exception("FIREBASE_SERVICE_ACCOUNT_KEY environment variable not set")
    
    try:
        # Clean the Base64 string (remove whitespace, newlines)
        sa_key_clean = sa_key.strip().replace('\n', '').replace('\r', '').replace(' ', '')
        logger.info(f"🔑 Service Account Key length: {len(sa_key_clean)} characters")
        
        # Add padding if necessary
        missing_padding = len(sa_key_clean) % 4
        if missing_padding:
            sa_key_clean += '=' * (4 - missing_padding)
            logger.info(f"🔧 Added {4 - missing_padding} padding characters")
        
        # Decode Base64 service account
        decoded_key = base64.b64decode(sa_key_clean).decode('utf-8')
        creds_data = json.loads(decoded_key)
        
        logger.info(f"✅ Service Account: {creds_data.get('client_email')}")
        
        # Initialize Firebase
        cred = credentials.Certificate(creds_data)
        app = firebase_admin.initialize_app(cred, {'projectId': PROJECT_ID})
        
        logger.info("🎉 Firebase initialized with Service Account")
        return app
        
    except binascii.Error as e:
        logger.error(f"❌ Base64 decode error: {e}")
        logger.error(f"Key preview: {sa_key[:50]}...")
        raise Exception(f"Invalid Base64 format: {e}")
    except json.JSONDecodeError as e:
        logger.error(f"❌ JSON decode error: {e}")
        raise Exception(f"Invalid JSON in Service Account: {e}")
    except Exception as e:
        logger.error(f"❌ Service Account initialization failed: {e}")
        raise

def initialize_with_adc():
    """Initialize Firebase with Application Default Credentials (Local)"""
    try:
        cred = credentials.ApplicationDefault()
        app = firebase_admin.initialize_app(cred, {'projectId': PROJECT_ID})
        
        logger.info("✅ Firebase initialized with Application Default Credentials")
        return app
        
    except Exception as e:
        logger.error(f"❌ ADC initialization failed: {e}")
        # Fallback to Service Account if available
        if os.getenv("FIREBASE_SERVICE_ACCOUNT_KEY"):
            logger.info("🔄 Falling back to Service Account...")
            return initialize_with_service_account()
        else:
            raise

def get_firestore_client():
    """Get Firestore client"""
    initialize_firebase()
    return firestore.client()

# Backward compatibility
def get_default_client():
    return get_firestore_client()

class FirebaseManager:
    @staticmethod
    def get_client():
        return get_firestore_client()
    
    @staticmethod  
    def test_connection():
        """Test Firebase connection"""
        try:
            client = get_firestore_client()
            
            # Test basic connectivity
            collections = list(client.collections())
            
            return {
                "connected": True, 
                "message": f"Connected to {PROJECT_ID}",
                "collections_found": len(collections),
                "environment": "railway" if is_railway_environment() else "local"
            }
                
        except Exception as e:
            return {
                "connected": False, 
                "message": str(e),
                "environment": "railway" if is_railway_environment() else "local"
            }
    
    @staticmethod
    def is_available():
        return True
    
    @staticmethod
    def setup():
        """Setup Firebase and return success status"""
        try:
            status = FirebaseManager.test_connection()
            return status.get('connected', False)
        except Exception:
            return False

# For backward compatibility
FIREBASE_AVAILABLE = True

if __name__ == "__main__":
    status = FirebaseManager.test_connection()
    print(f"Status: {status}")
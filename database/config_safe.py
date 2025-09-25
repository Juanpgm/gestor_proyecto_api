"""
Simple Firebase Configuration for Railway Deployment
Handles imports safely without crashing on missing modules
"""

import os
from typing import Optional
from pathlib import Path

# Safe environment loading
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent.parent / '.env'
    load_dotenv(env_path)
except ImportError:
    print("Warning: python-dotenv not installed, using system environment variables")

# Configuration from environment variables
PROJECT_ID = os.getenv('FIREBASE_PROJECT_ID', os.getenv('GOOGLE_CLOUD_PROJECT', 'dev-test-e778d'))
BATCH_SIZE = int(os.getenv('FIRESTORE_BATCH_SIZE', '500'))
TIMEOUT = int(os.getenv('FIRESTORE_TIMEOUT', '30'))

# Global variables for Firebase components
_firebase_app = None
_firestore_client = None

# Safe Firebase imports
try:
    import firebase_admin
    from firebase_admin import credentials, firestore
    FIREBASE_AVAILABLE = True
    print("Firebase admin SDK loaded successfully")
except ImportError as e:
    FIREBASE_AVAILABLE = False
    firebase_admin = None
    credentials = None
    firestore = None
    print(f"Warning: Firebase admin SDK not available: {e}")


def initialize_firebase():
    """Initialize Firebase safely"""
    if not FIREBASE_AVAILABLE:
        print("Warning: Firebase not available - running in limited mode")
        return False
        
    global _firebase_app
    
    if _firebase_app:
        return True
    
    try:
        # Try to get existing app
        _firebase_app = firebase_admin.get_app()
        return True
    except ValueError:
        # App doesn't exist, create it
        pass
    
    try:
        # Use Application Default Credentials
        cred = credentials.ApplicationDefault()
        _firebase_app = firebase_admin.initialize_app(cred, {'projectId': PROJECT_ID})
        print(f"Firebase initialized successfully: {PROJECT_ID}")
        return True
    except Exception as e:
        print(f"Error initializing Firebase: {e}")
        print("Run: gcloud auth application-default login")
        return False


def get_firestore_client():
    """Get Firestore client safely"""
    if not FIREBASE_AVAILABLE:
        return None
        
    global _firestore_client
    
    if not _firestore_client:
        if initialize_firebase():
            _firestore_client = firestore.client()
    
    return _firestore_client


def test_firebase_connection():
    """Test Firebase connection safely"""
    if not FIREBASE_AVAILABLE:
        return False
        
    try:
        client = get_firestore_client()
        if not client:
            return False
        
        # Simple test - try to create a reference
        test_ref = client.collection('_test_connection')
        if test_ref:
            return True
        return False
        
    except Exception as e:
        print(f"Error testing Firebase connection: {e}")
        return False


def setup_firebase():
    """Setup Firebase completely"""
    try:
        print("Setting up Firebase...")
        print(f"Project: {PROJECT_ID}")
        
        if not FIREBASE_AVAILABLE:
            print("Firebase modules not available - API will run in limited mode")
            return False
            
        if not initialize_firebase():
            return False
            
        if not test_firebase_connection():
            print("Firebase connection test failed")
            return False
            
        print("Firebase setup completed successfully")
        return True
        
    except Exception as e:
        print(f"Error in Firebase setup: {e}")
        return False


if __name__ == "__main__":
    print("Firebase Configuration Test")
    print("=" * 50)
    
    success = setup_firebase()
    if success:
        print("Configuration completed successfully")
    else:
        print("Configuration failed - check logs above")
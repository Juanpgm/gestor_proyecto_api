# Temporary Fix for Railway Authentication Issues
# Run this script to test Railway environment and fix auth issues

import os
import json
import requests

def diagnose_railway_auth():
    """Diagnose Railway authentication issues"""
    print("🔍 Diagnosing Railway Authentication...")
    
    # Check environment variables
    railway_token = os.getenv("RAILWAY_TOKEN")
    railway_project_id = os.getenv("RAILWAY_PROJECT_ID")
    railway_environment = os.getenv("RAILWAY_ENVIRONMENT")
    
    print(f"RAILWAY_TOKEN exists: {'Yes' if railway_token else 'No'}")
    print(f"RAILWAY_PROJECT_ID: {railway_project_id or 'Not set'}")
    print(f"RAILWAY_ENVIRONMENT: {railway_environment or 'Not set'}")
    
    if railway_token:
        # Test Railway OIDC endpoint
        try:
            headers = {"Authorization": f"Bearer {railway_token}"}
            response = requests.get("https://railway.app/.well-known/oidc_subject_token", 
                                  headers=headers, timeout=10)
            print(f"OIDC Endpoint Status: {response.status_code}")
            if response.status_code == 200:
                print("✅ Railway OIDC token endpoint is working")
            else:
                print(f"❌ Railway OIDC endpoint error: {response.text[:200]}")
        except Exception as e:
            print(f"❌ Railway OIDC endpoint error: {e}")
    
    # Check if we have Firebase service account as fallback
    firebase_key = os.getenv("FIREBASE_SERVICE_ACCOUNT_KEY")
    print(f"Firebase Service Account Key exists: {'Yes' if firebase_key else 'No'}")
    
    return railway_token is not None

def create_fallback_env():
    """Create a fallback environment configuration"""
    print("\n🔧 Creating fallback configuration...")
    
    # Create a local .env file for testing
    env_content = """# Fallback configuration for local testing
ENVIRONMENT=development
FIREBASE_PROJECT_ID=unidad-cumplimiento-aa245
FIRESTORE_BATCH_SIZE=500
FIRESTORE_TIMEOUT=30
LOG_LEVEL=INFO

# Add your Firebase service account key here if WIF fails
# FIREBASE_SERVICE_ACCOUNT_KEY=your_base64_encoded_service_account_key_here
"""
    
    with open('.env.local', 'w') as f:
        f.write(env_content)
    
    print("✅ Created .env.local file for local testing")
    print("📝 Add your Firebase service account key to .env.local if needed")

if __name__ == "__main__":
    has_railway_token = diagnose_railway_auth()
    if not has_railway_token:
        create_fallback_env()
        print("\n⚠️ No Railway token found. This is normal for local development.")
        print("📖 For production deployment, ensure Workload Identity is properly configured.")
# -*- coding: utf-8 -*-
"""
Firebase Configuration - Functional Programming Approach
Optimized for User Authentication and Database Management
Clean, efficient, and production-ready configuration
Soporte completo para UTF-8 y caracteres especiales en español
"""
import os
import json
import base64
import logging
from typing import Dict, Any, Optional, Tuple
from functools import lru_cache

import firebase_admin
from firebase_admin import credentials, firestore, auth
import google.auth.transport.requests

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constants - Configuración flexible para WIF y desarrollo
def get_project_id() -> str:
    """Get Firebase Project ID with flexible configuration"""
    # 1. Desde variable de entorno (WIF en Railway)
    project_id = os.getenv("FIREBASE_PROJECT_ID")
    if project_id:
        return project_id
    
    # 2. Desde Google Cloud metadata (si está disponible)
    try:
        import google.auth
        _, project = google.auth.default()
        if project:
            logger.info(f"📊 Project ID detected from ADC: {project}")
            return project
    except Exception:
        pass
    
    # 3. Fallback para desarrollo local (solo si no es producción)
    if not is_production():
        fallback_id = "unidad-cumplimiento-aa245"  # Solo para desarrollo
        logger.warning(f"⚠️ Using development fallback project: {fallback_id}")
        return fallback_id
    
    # 4. Error en producción sin configuración
    raise RuntimeError(
        "FIREBASE_PROJECT_ID environment variable is required in production. "
        "Configure it in Railway Dashboard or use Workload Identity Federation."
    )

PROJECT_ID = get_project_id()
USERS_COLLECTION = "users"
AUTH_SETTINGS_DOC = "auth_settings"

# Pure functions for environment detection
def is_production() -> bool:
    """Check if running in production environment"""
    return bool(os.getenv("RAILWAY_ENVIRONMENT") or os.getenv("VERCEL") or os.getenv("PRODUCTION"))

def is_workload_identity_available() -> bool:
    """Check if Workload Identity Federation is configured"""
    return bool(os.getenv("GOOGLE_APPLICATION_CREDENTIALS_JSON") or 
                os.getenv("GOOGLE_APPLICATION_CREDENTIALS"))

def get_service_account_key() -> Optional[str]:
    """Get service account key from environment"""
    return os.getenv("FIREBASE_SERVICE_ACCOUNT_KEY")

# Pure functions for credential processing
def decode_service_account(encoded_key: str) -> Dict[str, Any]:
    """Decode base64 service account key"""
    try:
        # Clean and pad base64 string
        clean_key = encoded_key.strip().replace('\n', '').replace('\r', '').replace(' ', '')
        padding_needed = len(clean_key) % 4
        if padding_needed:
            clean_key += '=' * (4 - padding_needed)
        
        # Decode and parse JSON
        decoded = base64.b64decode(clean_key).decode('utf-8')
        return json.loads(decoded)
    except Exception as e:
        raise ValueError(f"Invalid service account key: {e}")

# Core Firebase initialization functions
@lru_cache(maxsize=1)
def initialize_firebase_app() -> firebase_admin.App:
    """Initialize Firebase app with appropriate credentials and robust Railway fallback"""
    try:
        return firebase_admin.get_app()
    except ValueError:
        pass
    
    logger.info(f"🚀 Initializing Firebase: {PROJECT_ID}")
    
    # ESTRATEGIA DE FALLBACK ROBUSTO: WIF > Service Account Key > ADC
    # Cambio: Service Account como fallback preferido para Railway
    
    # 1. Intentar Workload Identity Federation (pero con manejo robusto de errores)
    if is_workload_identity_available():
        try:
            logger.info("🔐 Attempting Workload Identity Federation...")
            return _init_with_workload_identity()
        except Exception as e:
            error_msg = str(e)
            logger.warning(f"⚠️ Workload Identity failed: {error_msg}")
            
            # Detección específica de errores de Railway WIF
            if "RefreshError" in error_msg or "Identity Pool" in error_msg:
                logger.error("🚨 Railway WIF Token Issue Detected!")
                logger.error("💡 Railway OIDC endpoint is not working properly")
                logger.info("🔄 Attempting Service Account fallback immediately...")
            else:
                logger.info("🔄 Falling back to next authentication method...")
    
    # 2. Service Account Key (fallback confiable para Railway)
    if get_service_account_key():
        try:
            logger.info("� Using Service Account Key (Railway fallback)...")
            return _init_with_service_account()
        except Exception as e:
            logger.error(f"❌ Service Account Key failed: {e}")
            logger.info("🔄 Trying Application Default Credentials as last resort...")
    
    # 3. Application Default Credentials (último recurso para desarrollo local)
    if _adc_available():
        try:
            logger.info("� Attempting Application Default Credentials...")
            return _init_with_adc()
        except Exception as e:
            logger.warning(f"⚠️ ADC failed: {e}")
            raise RuntimeError(f"All authentication methods failed. Last error: {e}")
    
    # 4. No hay métodos de autenticación disponibles
    error_message = (
        "No authentication method available. For Railway deployment:\n"
        "1. Set FIREBASE_SERVICE_ACCOUNT_KEY (recommended for Railway)\n"
        "2. Or fix GOOGLE_APPLICATION_CREDENTIALS_JSON (WIF)\n"
        "3. For local development: run 'gcloud auth application-default login'"
    )
    logger.error(f"❌ {error_message}")
    raise RuntimeError(error_message)

def _init_with_service_account() -> firebase_admin.App:
    """Initialize with service account credentials"""
    service_key = get_service_account_key()
    if not service_key:
        raise RuntimeError("FIREBASE_SERVICE_ACCOUNT_KEY required in production")
    
    creds_data = decode_service_account(service_key)
    logger.info(f"✅ Service Account: {creds_data.get('client_email')}")
    
    cred = credentials.Certificate(creds_data)
    app = firebase_admin.initialize_app(cred, {'projectId': PROJECT_ID})
    logger.info("✅ Firebase initialized with Service Account")
    return app

def _init_with_workload_identity() -> firebase_admin.App:
    """Initialize with Workload Identity Federation with robust error handling"""
    wif_creds_json = os.getenv("GOOGLE_APPLICATION_CREDENTIALS_JSON")
    if wif_creds_json:
        try:
            import tempfile
            import json
            
            # Create temporary credentials file for WIF
            creds_data = json.loads(wif_creds_json)
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
                json.dump(creds_data, f)
                temp_creds_file = f.name
            
            # Set the environment variable for ADC to use
            os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = temp_creds_file
            logger.info("✅ Workload Identity credentials configured")
            
            # Try to initialize with WIF credentials
            cred = credentials.ApplicationDefault()
            
            # Test if credentials work by trying to refresh them
            if not cred.valid:
                try:
                    cred.refresh(google.auth.transport.requests.Request())
                except Exception as refresh_error:
                    logger.error(f"❌ WIF token refresh failed: {refresh_error}")
                    # If refresh fails, raise an exception to trigger fallback
                    raise RuntimeError(f"WIF authentication failed: {refresh_error}")
            
            app = firebase_admin.initialize_app(cred, {'projectId': PROJECT_ID})
            logger.info("✅ Firebase initialized with Workload Identity Federation")
            return app
            
        except Exception as wif_error:
            logger.error(f"❌ Workload Identity initialization failed: {wif_error}")
            logger.info("🔄 Attempting Service Account fallback...")
            # Clear the temp file if it was created
            try:
                if 'temp_creds_file' in locals():
                    os.unlink(temp_creds_file)
                if 'GOOGLE_APPLICATION_CREDENTIALS' in os.environ:
                    del os.environ['GOOGLE_APPLICATION_CREDENTIALS']
            except:
                pass
            # Raise error to trigger fallback
            raise RuntimeError(f"WIF failed, attempting fallback: {wif_error}")
    
    # If no WIF credentials, try Application Default Credentials
    try:
        cred = credentials.ApplicationDefault()
        app = firebase_admin.initialize_app(cred, {'projectId': PROJECT_ID})
        logger.info("✅ Firebase initialized with Application Default Credentials")
        return app
    except Exception as adc_error:
        logger.error(f"❌ Application Default Credentials failed: {adc_error}")
        raise RuntimeError(f"Both WIF and ADC failed: {adc_error}")

def _adc_available() -> bool:
    """Check if Application Default Credentials are available"""
    try:
        import google.auth
        google.auth.default()
        return True
    except Exception:
        return False

def _init_with_adc() -> firebase_admin.App:
    """Initialize with Application Default Credentials"""
    cred = credentials.ApplicationDefault()
    app = firebase_admin.initialize_app(cred, {'projectId': PROJECT_ID})
    logger.info("✅ Firebase initialized with Application Default Credentials")
    return app

# Client factory functions
@lru_cache(maxsize=1)
def get_firestore_client():
    """Get Firestore client instance"""
    if not ensure_firebase_configured():
        raise RuntimeError("Firebase not configured")
    return firestore.client()

@lru_cache(maxsize=1)
def get_auth_client():
    """Get Firebase Auth client instance"""
    if not ensure_firebase_configured():
        raise RuntimeError("Firebase not configured")
    return auth

# Database initialization functions
def setup_auth_collections() -> bool:
    """Initialize authentication-related collections and documents"""
    try:
        # Solo inicializar colecciones cuando sea realmente necesario
        # La colección 'users' se creará automáticamente cuando se agregue el primer usuario
        logger.info("✅ Auth collections ready (lazy initialization)")
        return True
    except Exception as e:
        logger.error(f"❌ Failed to setup auth collections: {e}")
        return False

# Estas funciones se eliminaron para evitar crear colecciones innecesarias
# La colección 'users' se creará automáticamente cuando se cree el primer usuario
# Los settings de autenticación están embebidos en el código por mayor eficiencia

# Validation functions
def validate_firebase_connection() -> Dict[str, Any]:
    """Validate Firebase connection and services"""
    try:
        db = get_firestore_client()
        auth_client = get_auth_client()
        
        # Test Firestore
        collections = list(db.collections())
        
        # Test Auth
        try:
            auth_client.list_users(max_results=1)
            auth_available = True
        except Exception:
            auth_available = False
        
        return {
            "connected": True,
            "project_id": PROJECT_ID,
            "environment": "production" if is_production() else "development",
            "firestore_available": True,
            "auth_available": auth_available,
            "collections_count": len(collections),
            "users_collection_exists": USERS_COLLECTION in [c.id for c in collections]
        }
    except Exception as e:
        return {
            "connected": False,
            "error": str(e),
            "project_id": PROJECT_ID,
            "environment": "production" if is_production() else "development"
        }

# Main configuration function
def configure_firebase() -> Tuple[bool, Dict[str, Any]]:
    """Configure Firebase with all necessary components"""
    try:
        # Initialize Firebase
        success = ensure_firebase_configured()
        
        if success:
            # Setup auth collections in background (non-blocking)
            try:
                setup_auth_collections()
            except Exception as e:
                logger.warning(f"⚠️ Auth collections setup failed: {e}")
            
            return True, {"configured": True, "project_id": PROJECT_ID}
        else:
            return False, {"error": "Firebase initialization failed"}
    except Exception as e:
        logger.error(f"❌ Firebase configuration failed: {e}")
        return False, {"error": str(e)}

# Simplified API for backward compatibility
FIREBASE_AVAILABLE = True

# Lazy initialization - configure when needed
def ensure_firebase_configured():
    """Ensure Firebase is configured, configure if not already done"""
    try:
        # Try to get existing app
        firebase_admin.get_app()
        return True
    except ValueError:
        # App doesn't exist, initialize it
        try:
            initialize_firebase_app()
            return True
        except Exception as e:
            logger.error(f"❌ Firebase initialization failed: {e}")
            return False

# Para uso directo del script solamente
if __name__ == "__main__":
    print("🔧 Testing Firebase configuration...")
    success, status = configure_firebase()
    if success:
        print(f"✅ Configuration: {status}")
        # Ejecutar pruebas de validación solo en modo directo
        validation_success, validation_status = validate_firebase_connection()
        if validation_success:
            print(f"✅ Validation: {validation_status}")
        else:
            print(f"❌ Validation: {validation_status}")
    else:
        print(f"❌ Configuration: {status}")
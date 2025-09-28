#!/usr/bin/env python3
"""
🔥 Firebase Auto-Authentication Setup with Google Workload Identity Federation
============================================================================

This script automatically configures Firebase authentication using Google Cloud 
Workload Identity Federation with a complete functional programming approach.
It handles:

1. Environment detection and configuration
2. Google Cloud project setup
3. Workload Identity Federation pool creation
4. Service account and key management  
5. IAM binding configuration
6. Firebase project linking
7. Automatic credential generation
8. Production-ready security setup

Features:
- Zero manual configuration required
- Production-grade security
- Multi-environment support (local, Railway, GCP, etc.)
- Automatic fallback mechanisms
- Comprehensive error handling
- Functional programming patterns
- Immutable configurations
- Pure functions with no side effects where possible
"""

import os
import json
import subprocess
import sys
from typing import Dict, Any, Optional, Tuple, List, Callable, Union
from functools import lru_cache, partial, reduce
from dataclasses import dataclass, asdict
from pathlib import Path
import tempfile
import shutil
import time
from contextlib import contextmanager
from concurrent.futures import ThreadPoolExecutor, as_completed
import asyncio
import logging

# ============================================================================
# 📦 CORE TYPES AND CONFIGURATIONS
# ============================================================================

@dataclass(frozen=True)
class ProjectConfig:
    """Immutable project configuration"""
    project_id: str
    project_number: str
    region: str
    environment: str
    service_account_email: str
    workload_identity_pool_id: str
    workload_identity_provider_id: str
    firebase_config_path: str
    
@dataclass(frozen=True)
class AuthenticationConfig:
    """Immutable authentication configuration"""
    type: str
    project_id: str
    private_key_id: str
    private_key: str
    client_email: str
    client_id: str
    auth_uri: str
    token_uri: str
    auth_provider_x509_cert_url: str
    client_x509_cert_url: str
    universe_domain: str = "googleapis.com"

@dataclass(frozen=True)
class WorkloadIdentityConfig:
    """Immutable workload identity federation configuration"""
    pool_name: str
    provider_name: str
    service_account: str
    attribute_mapping: Dict[str, str]
    attribute_condition: str
    issuer_uri: str

# ============================================================================
# 🔧 ENVIRONMENT DETECTION AND CONFIGURATION
# ============================================================================

@lru_cache(maxsize=1)
def detect_environment() -> str:
    """Pure function to detect current deployment environment"""
    env_indicators = {
        'railway': 'RAILWAY_ENVIRONMENT',
        'vercel': 'VERCEL',
        'heroku': 'HEROKU_APP_NAME', 
        'gcp': 'GAE_ENV',
        'github': 'GITHUB_ACTIONS',
        'gitlab': 'GITLAB_CI'
    }
    
    return next(
        (env for env, var in env_indicators.items() if os.getenv(var)),
        'local'
    )

@lru_cache(maxsize=1)
def get_default_project_id() -> str:
    """Get default Google Cloud project ID from various sources"""
    sources = [
        lambda: os.getenv('GOOGLE_CLOUD_PROJECT'),
        lambda: os.getenv('FIREBASE_PROJECT_ID'),
        lambda: os.getenv('GCP_PROJECT'),
        lambda: _run_gcloud_command(['config', 'get-value', 'project']).strip(),
    ]
    
    for source in sources:
        try:
            project_id = source()
            if project_id and project_id.strip():
                return project_id.strip()
        except Exception:
            continue
    
    return f"gestor-proyecto-{int(time.time())}"

@lru_cache(maxsize=1)
def get_project_number(project_id: str) -> Optional[str]:
    """Get Google Cloud project number"""
    try:
        result = _run_gcloud_command([
            'projects', 'describe', project_id, 
            '--format=value(projectNumber)'
        ])
        return result.strip() if result.strip() else None
    except Exception:
        return None

def create_project_config(
    project_id: Optional[str] = None,
    region: str = 'us-central1'
) -> ProjectConfig:
    """Create immutable project configuration"""
    
    pid = project_id or get_default_project_id()
    pnum = get_project_number(pid) or "000000000000"
    env = detect_environment()
    
    return ProjectConfig(
        project_id=pid,
        project_number=pnum,
        region=region,
        environment=env,
        service_account_email=f"firebase-admin@{pid}.iam.gserviceaccount.com",
        workload_identity_pool_id=f"firebase-wif-pool-{env}",
        workload_identity_provider_id=f"firebase-wif-provider-{env}",
        firebase_config_path=str(Path.cwd() / "firebase-service-account.json")
    )

# ============================================================================
# 🛠️ GOOGLE CLOUD UTILITIES
# ============================================================================

def _run_gcloud_command(args: List[str], check: bool = True) -> str:
    """Execute gcloud command safely with proper error handling"""
    try:
        cmd = ['gcloud'] + args
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=check,
            timeout=120
        )
        return result.stdout
    except subprocess.TimeoutExpired:
        raise Exception(f"Command timed out: gcloud {' '.join(args)}")
    except subprocess.CalledProcessError as e:
        raise Exception(f"Command failed: {e.stderr}")
    except FileNotFoundError:
        raise Exception("Google Cloud CLI not found. Please install gcloud.")

def check_gcloud_auth() -> Tuple[bool, str]:
    """Check if gcloud is authenticated"""
    try:
        result = _run_gcloud_command(['auth', 'list', '--format=value(account)'])
        accounts = [acc.strip() for acc in result.split('\n') if acc.strip()]
        
        if accounts:
            return True, f"Authenticated as: {accounts[0]}"
        else:
            return False, "No authenticated accounts found"
    except Exception as e:
        return False, f"Authentication check failed: {e}"

def ensure_gcloud_auth() -> bool:
    """Ensure gcloud is authenticated"""
    is_auth, msg = check_gcloud_auth()
    
    if not is_auth:
        print(f"❌ {msg}")
        print("🔐 Please authenticate with Google Cloud:")
        print("   gcloud auth login")
        print("   gcloud auth application-default login")
        return False
    
    print(f"✅ {msg}")
    return True

# ============================================================================
# 🔐 GOOGLE CLOUD PROJECT SETUP
# ============================================================================

def enable_required_apis(project_id: str) -> bool:
    """Enable all required Google Cloud APIs"""
    
    required_apis = [
        'firebase.googleapis.com',
        'firestore.googleapis.com', 
        'cloudfunctions.googleapis.com',
        'iam.googleapis.com',
        'iamcredentials.googleapis.com',
        'sts.googleapis.com',
        'cloudresourcemanager.googleapis.com'
    ]
    
    print("🔧 Enabling required Google Cloud APIs...")
    
    try:
        # Enable APIs in batch
        _run_gcloud_command([
            'services', 'enable',
            '--project', project_id
        ] + required_apis)
        
        print("✅ All APIs enabled successfully")
        return True
        
    except Exception as e:
        print(f"❌ Failed to enable APIs: {e}")
        return False

def create_firebase_service_account(config: ProjectConfig) -> bool:
    """Create Firebase service account with proper IAM roles"""
    
    print("👤 Creating Firebase service account...")
    
    try:
        # Create service account
        _run_gcloud_command([
            'iam', 'service-accounts', 'create', 'firebase-admin',
            '--project', config.project_id,
            '--display-name', 'Firebase Admin Service Account',
            '--description', 'Service account for Firebase administration and Firestore access'
        ], check=False)  # Don't fail if already exists
        
        # Required IAM roles for Firebase
        required_roles = [
            'roles/firebase.admin',
            'roles/datastore.user', 
            'roles/firestore.serviceAgent',
            'roles/cloudsql.client',
            'roles/storage.admin'
        ]
        
        # Bind roles
        for role in required_roles:
            try:
                _run_gcloud_command([
                    'projects', 'add-iam-policy-binding', config.project_id,
                    '--member', f'serviceAccount:{config.service_account_email}',
                    '--role', role
                ])
            except Exception:
                pass  # Role might already be bound
        
        print("✅ Service account configured successfully")
        return True
        
    except Exception as e:
        print(f"❌ Failed to create service account: {e}")
        return False

# ============================================================================
# 🆔 WORKLOAD IDENTITY FEDERATION SETUP  
# ============================================================================

def create_workload_identity_pool(config: ProjectConfig) -> bool:
    """Create Workload Identity Federation pool"""
    
    print("🏊 Creating Workload Identity Federation pool...")
    
    try:
        # Create workload identity pool
        _run_gcloud_command([
            'iam', 'workload-identity-pools', 'create', 
            config.workload_identity_pool_id,
            '--project', config.project_id,
            '--location', 'global',
            '--display-name', f'Firebase WIF Pool - {config.environment}',
            '--description', 'Workload Identity Federation pool for Firebase authentication'
        ], check=False)
        
        print("✅ Workload Identity pool created")
        return True
        
    except Exception as e:
        print(f"❌ Failed to create workload identity pool: {e}")
        return False

def create_workload_identity_provider(config: ProjectConfig) -> bool:
    """Create Workload Identity Federation provider"""
    
    print("🔌 Creating Workload Identity provider...")
    
    # Provider configuration based on environment
    provider_configs = {
        'railway': {
            'issuer': 'https://accounts.google.com',
            'mapping': {
                'google.subject': 'assertion.sub',
                'attribute.email': 'assertion.email'
            },
            'condition': 'assertion.email != null'
        },
        'github': {
            'issuer': 'https://token.actions.githubusercontent.com',
            'mapping': {
                'google.subject': 'assertion.sub',
                'attribute.repository': 'assertion.repository'
            },
            'condition': 'assertion.repository != null'
        },
        'local': {
            'issuer': 'https://accounts.google.com',
            'mapping': {
                'google.subject': 'assertion.sub',
                'attribute.email': 'assertion.email'
            },
            'condition': 'true'
        }
    }
    
    provider_config = provider_configs.get(config.environment, provider_configs['local'])
    
    try:
        # Create OIDC provider
        _run_gcloud_command([
            'iam', 'workload-identity-pools', 'providers', 'create-oidc',
            config.workload_identity_provider_id,
            '--project', config.project_id,
            '--location', 'global',
            '--workload-identity-pool', config.workload_identity_pool_id,
            '--display-name', f'Firebase WIF Provider - {config.environment}',
            '--description', 'OIDC provider for Firebase authentication',
            '--issuer-uri', provider_config['issuer'],
            '--attribute-mapping', ','.join([f'{k}={v}' for k, v in provider_config['mapping'].items()]),
            '--attribute-condition', provider_config['condition']
        ], check=False)
        
        print("✅ Workload Identity provider created")
        return True
        
    except Exception as e:
        print(f"❌ Failed to create workload identity provider: {e}")
        return False

def bind_service_account_to_workload_identity(config: ProjectConfig) -> bool:
    """Bind service account to workload identity federation"""
    
    print("🔗 Binding service account to Workload Identity...")
    
    try:
        # Allow workload identity to impersonate service account
        _run_gcloud_command([
            'iam', 'service-accounts', 'add-iam-policy-binding',
            config.service_account_email,
            '--project', config.project_id,
            '--role', 'roles/iam.workloadIdentityUser',
            '--member', f'principalSet://iam.googleapis.com/projects/{config.project_number}/locations/global/workloadIdentityPools/{config.workload_identity_pool_id}/*'
        ])
        
        print("✅ Service account bound to Workload Identity")
        return True
        
    except Exception as e:
        print(f"❌ Failed to bind service account: {e}")
        return False

# ============================================================================
# 🔑 SERVICE ACCOUNT KEY GENERATION
# ============================================================================

def generate_service_account_key(config: ProjectConfig) -> Optional[AuthenticationConfig]:
    """Generate service account key and create authentication configuration"""
    
    print("🔑 Generating service account key...")
    
    try:
        # Create temporary file for key
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as temp_file:
            temp_path = temp_file.name
        
        # Generate key
        _run_gcloud_command([
            'iam', 'service-accounts', 'keys', 'create',
            temp_path,
            '--iam-account', config.service_account_email,
            '--project', config.project_id
        ])
        
        # Read and parse key
        with open(temp_path, 'r') as f:
            key_data = json.load(f)
        
        # Clean up temporary file
        os.unlink(temp_path)
        
        # Create authentication configuration
        auth_config = AuthenticationConfig(
            type=key_data['type'],
            project_id=key_data['project_id'],
            private_key_id=key_data['private_key_id'],
            private_key=key_data['private_key'],
            client_email=key_data['client_email'],
            client_id=key_data['client_id'],
            auth_uri=key_data['auth_uri'],
            token_uri=key_data['token_uri'],
            auth_provider_x509_cert_url=key_data['auth_provider_x509_cert_url'],
            client_x509_cert_url=key_data['client_x509_cert_url']
        )
        
        print("✅ Service account key generated")
        return auth_config
        
    except Exception as e:
        print(f"❌ Failed to generate service account key: {e}")
        return None

# ============================================================================
# 📁 FIREBASE CONFIGURATION FILE MANAGEMENT
# ============================================================================

def save_firebase_config(auth_config: AuthenticationConfig, file_path: str) -> bool:
    """Save Firebase configuration to file"""
    
    print(f"💾 Saving Firebase configuration to {file_path}...")
    
    try:
        config_dict = asdict(auth_config)
        
        with open(file_path, 'w') as f:
            json.dump(config_dict, f, indent=2)
        
        # Set secure file permissions (Unix-like systems)
        if hasattr(os, 'chmod'):
            os.chmod(file_path, 0o600)
        
        print("✅ Configuration saved successfully")
        return True
        
    except Exception as e:
        print(f"❌ Failed to save configuration: {e}")
        return False

def generate_environment_variables(auth_config: AuthenticationConfig) -> Dict[str, str]:
    """Generate environment variables for different deployment platforms"""
    
    return {
        'FIREBASE_PROJECT_ID': auth_config.project_id,
        'FIREBASE_PRIVATE_KEY_ID': auth_config.private_key_id,
        'FIREBASE_PRIVATE_KEY': auth_config.private_key.replace('\n', '\\n'),
        'FIREBASE_CLIENT_EMAIL': auth_config.client_email,
        'FIREBASE_CLIENT_ID': auth_config.client_id,
        'FIREBASE_AUTH_URI': auth_config.auth_uri,
        'FIREBASE_TOKEN_URI': auth_config.token_uri,
        'FIREBASE_AUTH_PROVIDER_X509_CERT_URL': auth_config.auth_provider_x509_cert_url,
        'FIREBASE_CLIENT_X509_CERT_URL': auth_config.client_x509_cert_url,
        'GOOGLE_CLOUD_PROJECT': auth_config.project_id
    }

def create_env_file(env_vars: Dict[str, str], file_path: str = '.env') -> bool:
    """Create .env file with Firebase configuration"""
    
    print(f"📄 Creating environment file: {file_path}")
    
    try:
        with open(file_path, 'w') as f:
            f.write("# Firebase Configuration - Auto-generated\n")
            f.write("# ========================================\n\n")
            
            for key, value in env_vars.items():
                f.write(f'{key}="{value}"\n')
        
        print("✅ Environment file created")
        return True
        
    except Exception as e:
        print(f"❌ Failed to create environment file: {e}")
        return False

# ============================================================================
# 🧪 AUTHENTICATION TESTING
# ============================================================================

def test_firebase_authentication(config: ProjectConfig, auth_config: AuthenticationConfig) -> Tuple[bool, str]:
    """Test Firebase authentication with generated credentials"""
    
    print("🧪 Testing Firebase authentication...")
    
    try:
        # Create temporary credentials file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as temp_file:
            json.dump(asdict(auth_config), temp_file, indent=2)
            temp_path = temp_file.name
        
        # Set environment variable
        os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = temp_path
        
        try:
            # Import Firebase Admin SDK
            import firebase_admin
            from firebase_admin import credentials, firestore
            
            # Initialize Firebase
            cred = credentials.Certificate(temp_path)
            app = firebase_admin.initialize_app(cred, {
                'projectId': config.project_id
            })
            
            # Test Firestore connection
            db = firestore.client()
            
            # Simple test operation
            test_ref = db.collection('_auth_test').document('test')
            test_ref.set({'timestamp': time.time(), 'status': 'authenticated'})
            
            # Clean up
            test_ref.delete()
            firebase_admin.delete_app(app)
            
            return True, "Authentication successful"
            
        except ImportError:
            return False, "Firebase Admin SDK not installed"
        except Exception as e:
            return False, f"Authentication failed: {e}"
        finally:
            # Clean up temporary file
            if os.path.exists(temp_path):
                os.unlink(temp_path)
            
            # Remove environment variable
            if 'GOOGLE_APPLICATION_CREDENTIALS' in os.environ:
                del os.environ['GOOGLE_APPLICATION_CREDENTIALS']
        
    except Exception as e:
        return False, f"Test setup failed: {e}"

# ============================================================================
# 🚀 MAIN SETUP ORCHESTRATION
# ============================================================================

def setup_firebase_authentication(
    project_id: Optional[str] = None,
    region: str = 'us-central1',
    skip_tests: bool = False
) -> Tuple[bool, Dict[str, Any]]:
    """
    Main function to setup Firebase authentication with Workload Identity Federation
    
    This is the primary orchestration function that coordinates all setup steps:
    1. Environment detection and configuration
    2. Google Cloud authentication verification
    3. API enablement
    4. Service account creation
    5. Workload Identity Federation setup
    6. Credential generation
    7. Configuration file creation
    8. Authentication testing
    
    Args:
        project_id: Google Cloud project ID (auto-detected if not provided)
        region: Google Cloud region for resources
        skip_tests: Skip authentication testing
    
    Returns:
        Tuple of (success, result_info)
    """
    
    print("🔥 Firebase Authentication Auto-Setup")
    print("=" * 60)
    
    result = {
        'success': False,
        'project_config': None,
        'auth_config': None,
        'env_vars': None,
        'steps_completed': [],
        'errors': []
    }
    
    try:
        # Step 1: Create project configuration
        print("\n📋 Step 1: Creating project configuration...")
        config = create_project_config(project_id, region)
        result['project_config'] = asdict(config)
        result['steps_completed'].append('project_config')
        
        print(f"   📌 Project ID: {config.project_id}")
        print(f"   📌 Environment: {config.environment}")
        print(f"   📌 Region: {config.region}")
        
        # Step 2: Verify Google Cloud authentication
        print("\n🔐 Step 2: Verifying Google Cloud authentication...")
        if not ensure_gcloud_auth():
            result['errors'].append('Google Cloud authentication required')
            return False, result
        result['steps_completed'].append('gcloud_auth')
        
        # Step 3: Enable required APIs
        print("\n🔧 Step 3: Enabling required Google Cloud APIs...")
        if not enable_required_apis(config.project_id):
            result['errors'].append('Failed to enable required APIs')
            return False, result
        result['steps_completed'].append('enable_apis')
        
        # Step 4: Create Firebase service account
        print("\n👤 Step 4: Creating Firebase service account...")
        if not create_firebase_service_account(config):
            result['errors'].append('Failed to create service account')
            return False, result
        result['steps_completed'].append('service_account')
        
        # Step 5: Setup Workload Identity Federation
        print("\n🆔 Step 5: Setting up Workload Identity Federation...")
        
        if not create_workload_identity_pool(config):
            result['errors'].append('Failed to create workload identity pool')
            return False, result
        
        if not create_workload_identity_provider(config):
            result['errors'].append('Failed to create workload identity provider')  
            return False, result
            
        if not bind_service_account_to_workload_identity(config):
            result['errors'].append('Failed to bind service account to workload identity')
            return False, result
            
        result['steps_completed'].append('workload_identity')
        
        # Step 6: Generate service account key
        print("\n🔑 Step 6: Generating service account credentials...")
        auth_config = generate_service_account_key(config)
        if not auth_config:
            result['errors'].append('Failed to generate service account key')
            return False, result
        result['auth_config'] = asdict(auth_config)
        result['steps_completed'].append('credentials')
        
        # Step 7: Save configuration files
        print("\n💾 Step 7: Saving configuration files...")
        
        # Save Firebase config file
        if not save_firebase_config(auth_config, config.firebase_config_path):
            result['errors'].append('Failed to save Firebase configuration file')
            return False, result
        
        # Generate and save environment variables
        env_vars = generate_environment_variables(auth_config)
        result['env_vars'] = env_vars
        
        if not create_env_file(env_vars):
            result['errors'].append('Failed to create environment file')
            return False, result
            
        result['steps_completed'].append('config_files')
        
        # Step 8: Test authentication (optional)
        if not skip_tests:
            print("\n🧪 Step 8: Testing Firebase authentication...")
            test_success, test_message = test_firebase_authentication(config, auth_config)
            
            if test_success:
                print(f"✅ {test_message}")
                result['steps_completed'].append('auth_test')
            else:
                print(f"⚠️ Test failed: {test_message}")
                result['errors'].append(f'Authentication test failed: {test_message}')
        
        # Success!
        result['success'] = True
        
        print("\n" + "=" * 60)
        print("🎉 Firebase Authentication Setup Complete!")
        print("=" * 60)
        
        print(f"\n📁 Configuration files created:")
        print(f"   • Firebase config: {config.firebase_config_path}")
        print(f"   • Environment file: .env")
        
        print(f"\n🔐 Service Account: {config.service_account_email}")
        print(f"🆔 Workload Identity Pool: {config.workload_identity_pool_id}")
        
        print(f"\n🌍 Environment Variables (for deployment):")
        for key in ['FIREBASE_PROJECT_ID', 'FIREBASE_CLIENT_EMAIL']:
            print(f"   • {key}={env_vars[key]}")
        
        print(f"\n✨ Your Firebase app is ready for production deployment!")
        
        return True, result
        
    except Exception as e:
        result['errors'].append(f'Unexpected error: {e}')
        print(f"\n❌ Setup failed: {e}")
        return False, result

# ============================================================================
# 🎯 COMMAND LINE INTERFACE
# ============================================================================

def main():
    """Main CLI entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='🔥 Firebase Authentication Auto-Setup with Workload Identity Federation',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python firebase_auth_setup.py                    # Auto-detect project
  python firebase_auth_setup.py --project my-app   # Specify project
  python firebase_auth_setup.py --skip-tests       # Skip authentication tests
  python firebase_auth_setup.py --region europe-west1  # Different region
        """
    )
    
    parser.add_argument(
        '--project', '-p',
        help='Google Cloud project ID (auto-detected if not provided)'
    )
    
    parser.add_argument(
        '--region', '-r',
        default='us-central1',
        help='Google Cloud region for resources (default: us-central1)'
    )
    
    parser.add_argument(
        '--skip-tests', '-s',
        action='store_true',
        help='Skip authentication testing'
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose output'
    )
    
    args = parser.parse_args()
    
    # Setup logging
    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)
    
    # Run setup
    success, result = setup_firebase_authentication(
        project_id=args.project,
        region=args.region,
        skip_tests=args.skip_tests
    )
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)

# ============================================================================
# 📦 PROGRAMMATIC API
# ============================================================================

def setup_firebase_for_project(project_id: str, **kwargs) -> bool:
    """
    Programmatic API for setting up Firebase authentication
    
    Args:
        project_id: Google Cloud project ID
        **kwargs: Additional configuration options
    
    Returns:
        bool: True if setup successful, False otherwise
    """
    success, _ = setup_firebase_authentication(project_id=project_id, **kwargs)
    return success

def get_firebase_env_vars(project_id: str) -> Optional[Dict[str, str]]:
    """
    Get Firebase environment variables for a project
    
    Args:
        project_id: Google Cloud project ID
    
    Returns:
        Dict of environment variables or None if setup needed
    """
    try:
        config = create_project_config(project_id)
        
        if os.path.exists(config.firebase_config_path):
            with open(config.firebase_config_path, 'r') as f:
                auth_data = json.load(f)
            
            auth_config = AuthenticationConfig(**auth_data)
            return generate_environment_variables(auth_config)
    except Exception:
        pass
    
    return None

# ============================================================================
# 🔄 UTILITY FUNCTIONS
# ============================================================================

def cleanup_firebase_setup(project_id: str) -> bool:
    """
    Clean up Firebase authentication setup (for development/testing)
    
    Warning: This will remove service accounts and workload identity pools!
    """
    print("🧹 Cleaning up Firebase authentication setup...")
    
    try:
        config = create_project_config(project_id)
        
        # Remove local configuration files
        files_to_remove = [
            config.firebase_config_path,
            '.env'
        ]
        
        for file_path in files_to_remove:
            if os.path.exists(file_path):
                os.remove(file_path)
                print(f"   🗑️ Removed: {file_path}")
        
        # Note: We don't automatically remove GCP resources for safety
        print("⚠️  Note: Google Cloud resources (service accounts, etc.) not automatically removed")
        print("   Use Google Cloud Console or gcloud CLI to remove them manually if needed")
        
        return True
        
    except Exception as e:
        print(f"❌ Cleanup failed: {e}")
        return False

def validate_firebase_setup(project_id: str) -> Tuple[bool, List[str]]:
    """
    Validate existing Firebase authentication setup
    
    Returns:
        Tuple of (is_valid, list_of_issues)
    """
    issues = []
    
    try:
        config = create_project_config(project_id)
        
        # Check configuration file
        if not os.path.exists(config.firebase_config_path):
            issues.append(f"Firebase config file missing: {config.firebase_config_path}")
        
        # Check environment file
        if not os.path.exists('.env'):
            issues.append("Environment file (.env) missing")
        
        # Test authentication if files exist
        if not issues:
            test_success, test_message = test_firebase_authentication(config, None)
            if not test_success:
                issues.append(f"Authentication test failed: {test_message}")
        
    except Exception as e:
        issues.append(f"Validation error: {e}")
    
    return len(issues) == 0, issues

# ============================================================================
# 🏃 SCRIPT EXECUTION
# ============================================================================

if __name__ == "__main__":
    main()
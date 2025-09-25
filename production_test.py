#!/usr/bin/env python3
"""
Railway Production Endpoint Tester
Tests all endpoints and diagnoses production issues
"""

import requests
import json
from datetime import datetime

def test_endpoint_detailed(url, endpoint, description):
    """Test an endpoint with detailed analysis"""
    full_url = url + endpoint
    
    print(f"\n{'='*60}")
    print(f"🔍 Testing: {description}")
    print(f"📍 Endpoint: {endpoint}")
    print(f"🌐 Full URL: {full_url}")
    print('='*60)
    
    try:
        response = requests.get(full_url, timeout=30)
        
        print(f"📊 Status Code: {response.status_code}")
        print(f"🕐 Response Time: ~{response.elapsed.total_seconds():.2f}s")
        print(f"📄 Content-Type: {response.headers.get('content-type', 'unknown')}")
        
        if response.status_code == 200:
            print("✅ SUCCESS")
            
            try:
                data = response.json()
                print("📋 JSON Response Analysis:")
                
                # Analyze response structure
                if isinstance(data, dict):
                    for key, value in data.items():
                        if key == 'services' and isinstance(value, dict):
                            print(f"  🔧 Services Status:")
                            for service, status in value.items():
                                if isinstance(status, dict):
                                    connected = status.get('connected', status.get('available', 'unknown'))
                                    message = status.get('message', status.get('error', ''))
                                    print(f"    - {service}: {connected} ({message})")
                                else:
                                    print(f"    - {service}: {status}")
                        elif key in ['status', 'timestamp', 'message', 'version']:
                            print(f"  📄 {key}: {value}")
                        else:
                            print(f"  🔧 {key}: {str(value)[:100]}...")
                
                # Check for specific issues
                if 'firebase' in str(data).lower():
                    if 'not available' in str(data).lower() or 'sdk not available' in str(data).lower():
                        print("🚨 ISSUE DETECTED: Firebase SDK not available in production")
                        print("💡 This may be a dependency installation issue")
                
                return True, data
                
            except json.JSONDecodeError:
                print("📄 Non-JSON Response:")
                print(response.text[:500])
                return True, response.text
                
        elif response.status_code == 503:
            print("⚠️ SERVICE UNAVAILABLE (503)")
            print("💡 Possible causes:")
            print("  - Application is starting up")
            print("  - Internal service error")
            print("  - Dependency not working")
            
            try:
                error_data = response.json()
                print(f"📄 Error Response: {error_data}")
            except:
                print(f"📄 Raw Response: {response.text[:200]}")
                
            return False, response.text
            
        elif response.status_code == 502:
            print("⚠️ BAD GATEWAY (502)")
            print("💡 App is running but not responding correctly")
            
        else:
            print(f"⚠️ HTTP {response.status_code}")
            print(f"📄 Response: {response.text[:200]}")
            
        return False, response.text
        
    except requests.exceptions.Timeout:
        print("⏰ TIMEOUT - Server took too long to respond")
        return False, "timeout"
    except requests.exceptions.ConnectionError:
        print("🔌 CONNECTION ERROR - Cannot reach server")
        return False, "connection_error"
    except Exception as e:
        print(f"❌ UNEXPECTED ERROR: {e}")
        return False, str(e)

def test_firebase_specific_endpoints(url):
    """Test Firebase-specific functionality"""
    print(f"\n{'='*60}")
    print("🔥 FIREBASE-SPECIFIC ENDPOINT TESTING")
    print('='*60)
    
    firebase_endpoints = [
        ("/api/proyectos", "Projects endpoint (requires Firebase)"),
        ("/api/unidades", "Units endpoint (requires Firebase)"), 
        ("/api/auth/status", "Auth status (may require Firebase)")
    ]
    
    for endpoint, description in firebase_endpoints:
        success, response = test_endpoint_detailed(url, endpoint, description)
        
        if not success and "404" in str(response):
            print("📍 Endpoint not found - this is normal if not implemented yet")

def diagnose_production_issues(health_data):
    """Diagnose specific production issues from health check"""
    print(f"\n{'='*60}")
    print("🔍 PRODUCTION ISSUE DIAGNOSIS")
    print('='*60)
    
    issues_found = []
    
    if isinstance(health_data, dict):
        # Check Firebase status
        services = health_data.get('services', {})
        firebase_info = services.get('firebase', {})
        
        if not firebase_info.get('available', True):
            issues_found.append("Firebase SDK not installed")
            print("🚨 CRITICAL: Firebase SDK not available")
            print("💡 Solutions:")
            print("  1. Check requirements.txt includes firebase-admin")
            print("  2. Verify Railway build logs for installation errors")
            print("  3. Check Python version compatibility")
            
        elif not firebase_info.get('connected', True):
            issues_found.append("Firebase authentication failed")
            print("🚨 CRITICAL: Firebase authentication failed")
            print("💡 Solutions:")
            print("  1. Verify all environment variables are set correctly")
            print("  2. Check service account permissions")
            print("  3. Verify private key format (newlines as \\n)")
        
        # Check overall status
        overall_status = health_data.get('status', 'unknown')
        if overall_status == 'degraded':
            issues_found.append("API running in degraded mode")
            print("⚠️ WARNING: API running in degraded mode")
            
    return issues_found

def main():
    url = "https://gestorproyectoapi-production.up.railway.app"
    
    print("🚂 RAILWAY PRODUCTION ENDPOINT COMPREHENSIVE TESTING")
    print(f"🕐 Started: {datetime.now().isoformat()}")
    
    # Test core endpoints
    core_endpoints = [
        ("/ping", "Basic ping health check"),
        ("/health", "Detailed health check with services"),
        ("/", "Root API endpoint"),
        ("/docs", "FastAPI documentation"),
    ]
    
    all_results = {}
    
    for endpoint, description in core_endpoints:
        success, response = test_endpoint_detailed(url, endpoint, description)
        all_results[endpoint] = {'success': success, 'response': response}
    
    # Analyze health check for issues
    if '/health' in all_results and all_results['/health']['success']:
        health_data = all_results['/health']['response']
        issues = diagnose_production_issues(health_data)
    
    # Test Firebase endpoints
    test_firebase_specific_endpoints(url)
    
    # Final summary
    print(f"\n{'='*60}")
    print("📊 TESTING SUMMARY")
    print('='*60)
    
    success_count = sum(1 for result in all_results.values() if result['success'])
    total_count = len(all_results)
    
    print(f"✅ Successful endpoints: {success_count}/{total_count}")
    
    if success_count == total_count:
        print("🎉 All core endpoints working!")
        print("💡 If Firebase issues detected, check environment variables")
    else:
        print("⚠️ Some endpoints have issues - check details above")
    
    print(f"\n🚂 Railway URL: {url}")
    print("📋 Next steps: Fix any issues identified above")

if __name__ == "__main__":
    main()
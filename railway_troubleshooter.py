#!/usr/bin/env python3
"""
Railway Deployment Troubleshooter
Helps diagnose Railway deployment issues step by step
"""

import requests
import time
import json
from datetime import datetime

def print_header(title):
    print(f"\n{'='*60}")
    print(f"🔍 {title}")
    print(f"{'='*60}")

def test_railway_url(url):
    """Test Railway URL and diagnose the specific error"""
    print_header("TESTING RAILWAY DEPLOYMENT")
    
    if not url.startswith('http'):
        url = 'https://' + url
    
    print(f"🌐 Testing URL: {url}")
    
    endpoints = [
        ('/', 'Root endpoint'),
        ('/ping', 'Health check ping'),
        ('/health', 'Health check detailed'),
        ('/docs', 'FastAPI documentation')
    ]
    
    for endpoint, description in endpoints:
        test_url = url + endpoint
        print(f"\n📍 Testing {description}: {endpoint}")
        
        try:
            # Try with longer timeout
            response = requests.get(test_url, timeout=30)
            
            print(f"✅ Status Code: {response.status_code}")
            print(f"📄 Content-Type: {response.headers.get('content-type', 'unknown')}")
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    print(f"📄 Response: {json.dumps(data, indent=2)[:300]}...")
                except:
                    print(f"📄 Response: {response.text[:200]}...")
            else:
                print(f"❌ Error Response: {response.text[:200]}...")
                
        except requests.exceptions.Timeout:
            print(f"⏰ TIMEOUT: Server took longer than 30 seconds to respond")
            print("   This suggests the app is not starting or is stuck")
            
        except requests.exceptions.ConnectionError as e:
            print(f"🔌 CONNECTION ERROR: {e}")
            print("   This suggests Railway deployment failed or app crashed")
            
        except requests.exceptions.HTTPError as e:
            print(f"📡 HTTP ERROR: {e}")
            
        except Exception as e:
            print(f"❌ UNEXPECTED ERROR: {e}")
    
    return False

def diagnose_common_railway_issues():
    """Diagnose common Railway deployment issues"""
    print_header("COMMON RAILWAY ISSUES DIAGNOSIS")
    
    print("🔍 Checking for common Railway deployment problems:")
    print()
    
    # Check local files
    import os
    files_to_check = {
        'Dockerfile': 'Docker build configuration',
        'requirements.txt': 'Python dependencies',
        'main.py': 'Application entry point',
        'railway.json': 'Railway deployment config'
    }
    
    for filename, description in files_to_check.items():
        if os.path.exists(filename):
            print(f"✅ {filename} - {description}")
        else:
            print(f"❌ {filename} - MISSING - {description}")
    
    print()
    print("🚨 COMMON RAILWAY FAILURE CAUSES:")
    print()
    print("1. ❌ BUILD FAILURES:")
    print("   - Missing or incorrect requirements.txt")
    print("   - Python version mismatch")
    print("   - Dependency conflicts")
    print()
    print("2. ❌ STARTUP FAILURES:")
    print("   - Import errors (missing modules)")
    print("   - Port binding issues")
    print("   - Environment variable problems")
    print()
    print("3. ❌ HEALTH CHECK FAILURES:")
    print("   - App starts but doesn't respond to /ping")
    print("   - Health check timeout (>120s)")
    print("   - Wrong health check path configured")
    print()
    print("4. ❌ RUNTIME CRASHES:")
    print("   - Unhandled exceptions during startup")
    print("   - Memory/resource limits exceeded")
    print("   - Database connection failures")

def get_railway_debugging_steps():
    """Provide Railway-specific debugging steps"""
    print_header("RAILWAY DEBUGGING STEPS")
    
    print("🔧 TO DIAGNOSE RAILWAY DEPLOYMENT ISSUES:")
    print()
    print("1. 📋 CHECK RAILWAY DASHBOARD LOGS:")
    print("   - Go to Railway Dashboard → Your Project")
    print("   - Click on 'Deployments' tab")
    print("   - Click on the latest deployment")
    print("   - Check 'Build Logs' and 'Deploy Logs'")
    print()
    print("2. 🔍 LOOK FOR SPECIFIC ERROR MESSAGES:")
    print("   - Build phase errors (requirements.txt issues)")
    print("   - Runtime phase errors (startup crashes)")
    print("   - Health check failures (/ping not responding)")
    print()
    print("3. ⚙️  CHECK ENVIRONMENT VARIABLES:")
    print("   - Railway Dashboard → Variables tab")
    print("   - Ensure PORT is NOT manually set (Railway handles this)")
    print("   - Check other required variables are present")
    print()
    print("4. 🔄 TRY MANUAL REDEPLOY:")
    print("   - Railway Dashboard → Deployments")
    print("   - Click 'Deploy Latest Commit'")
    print("   - Watch build/deploy logs in real-time")
    print()
    print("5. 📞 IF STILL FAILING:")
    print("   - Take screenshots of error logs")
    print("   - Note the specific error messages")
    print("   - Check Railway's status page for outages")

def check_railway_service_status():
    """Check if Railway itself has issues"""
    print_header("RAILWAY SERVICE STATUS CHECK")
    
    try:
        # Check Railway's status page
        response = requests.get("https://status.railway.app", timeout=10)
        if response.status_code == 200:
            print("✅ Railway service status page accessible")
        else:
            print(f"⚠️  Railway status page returned: {response.status_code}")
    except Exception as e:
        print(f"❌ Could not check Railway status: {e}")
    
    print()
    print("💡 IF RAILWAY HAS ISSUES:")
    print("   - Check https://status.railway.app")
    print("   - Check Railway's Discord/Twitter for announcements")
    print("   - Wait for service restoration")

def main():
    print("🚂 RAILWAY DEPLOYMENT TROUBLESHOOTER")
    print(f"Timestamp: {datetime.now().isoformat()}")
    
    # Get Railway URL from user
    railway_url = input("\n🌐 Enter your Railway URL (or press Enter to skip URL test): ").strip()
    
    if railway_url:
        test_railway_url(railway_url)
    
    diagnose_common_railway_issues()
    check_railway_service_status() 
    get_railway_debugging_steps()
    
    print_header("SUMMARY & NEXT STEPS")
    
    print("📋 IMMEDIATE ACTIONS:")
    print("1. 🔍 Check Railway Dashboard logs (most important)")
    print("2. 📸 Take screenshots of any error messages")
    print("3. 🔄 Try manual redeploy if logs show transient errors")
    print("4. ⚙️  Verify environment variables configuration")
    print()
    print("📞 NEED HELP?")
    print("- Share the specific error messages from Railway logs")
    print("- Include deployment timestamp")
    print("- Note which phase failed (build vs deploy vs health check)")

if __name__ == "__main__":
    main()
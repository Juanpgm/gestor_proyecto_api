#!/usr/bin/env python3
"""
Railway Debug Tool - Comprehensive diagnostics
Helps identify specific Railway deployment issues
"""

import os
import sys
import subprocess
import time
import json
from datetime import datetime
import urllib.request
import urllib.error

def print_section(title):
    print(f"\n{'='*60}")
    print(f"📋 {title}")
    print(f"{'='*60}")

def check_dockerfile():
    """Check Dockerfile configuration"""
    print_section("DOCKERFILE ANALYSIS")
    
    try:
        with open('Dockerfile', 'r', encoding='utf-8') as f:
            content = f.read()
        
        print("✅ Dockerfile found")
        
        # Check for potential issues
        issues = []
        
        if 'CMD' not in content:
            issues.append("❌ No CMD instruction found")
        
        if 'uvicorn' not in content:
            issues.append("❌ uvicorn not found in CMD")
        
        if '--host 0.0.0.0' not in content:
            issues.append("❌ Not listening on 0.0.0.0")
        
        if '${PORT:-8000}' not in content:
            issues.append("❌ Not using Railway PORT variable")
        
        # Check for emojis (problematic characters)
        if any(ord(char) > 127 for char in content):
            issues.append("⚠️  Non-ASCII characters found (may cause encoding issues)")
        
        if issues:
            print("🚨 ISSUES FOUND:")
            for issue in issues:
                print(f"  {issue}")
        else:
            print("✅ Dockerfile configuration looks good")
        
        # Show relevant lines
        lines = content.split('\n')
        cmd_lines = [line for line in lines if line.strip().startswith('CMD')]
        if cmd_lines:
            print(f"\n📄 CMD instruction:")
            for line in cmd_lines:
                print(f"  {line}")
    
    except FileNotFoundError:
        print("❌ Dockerfile not found")
    except Exception as e:
        print(f"❌ Error reading Dockerfile: {e}")

def check_railway_json():
    """Check railway.json configuration"""
    print_section("RAILWAY.JSON ANALYSIS")
    
    try:
        with open('railway.json', 'r') as f:
            config = json.load(f)
        
        print("✅ railway.json found")
        print(f"📄 Configuration: {json.dumps(config, indent=2)}")
        
        # Check configuration
        issues = []
        
        if 'deploy' not in config:
            issues.append("❌ No deploy configuration")
        else:
            deploy = config['deploy']
            
            if 'healthcheckPath' not in deploy:
                issues.append("❌ No healthcheck path configured")
            elif deploy['healthcheckPath'] != '/ping':
                issues.append(f"⚠️  Healthcheck path is {deploy['healthcheckPath']}, should be /ping")
            
            timeout = deploy.get('healthcheckTimeout', 30)
            if timeout < 60:
                issues.append(f"⚠️  Healthcheck timeout is {timeout}s, consider increasing")
        
        if issues:
            print("🚨 ISSUES FOUND:")
            for issue in issues:
                print(f"  {issue}")
        else:
            print("✅ railway.json configuration looks good")
            
    except FileNotFoundError:
        print("⚠️  railway.json not found - using Railway defaults")
    except json.JSONDecodeError as e:
        print(f"❌ railway.json has invalid JSON: {e}")
    except Exception as e:
        print(f"❌ Error reading railway.json: {e}")

def check_requirements():
    """Check requirements.txt"""
    print_section("REQUIREMENTS.TXT ANALYSIS")
    
    try:
        with open('requirements.txt', 'r') as f:
            requirements = f.read().strip().split('\n')
        
        print(f"✅ requirements.txt found with {len(requirements)} dependencies")
        
        # Check critical dependencies
        critical_deps = ['fastapi', 'uvicorn']
        missing_critical = []
        
        for dep in critical_deps:
            if not any(dep in req.lower() for req in requirements):
                missing_critical.append(dep)
        
        if missing_critical:
            print("❌ MISSING CRITICAL DEPENDENCIES:")
            for dep in missing_critical:
                print(f"  - {dep}")
        else:
            print("✅ All critical dependencies found")
        
        # Show first few dependencies
        print("\n📦 Dependencies (first 10):")
        for req in requirements[:10]:
            if req.strip() and not req.startswith('#'):
                print(f"  - {req}")
        
        if len(requirements) > 10:
            print(f"  ... and {len(requirements) - 10} more")
            
    except FileNotFoundError:
        print("❌ requirements.txt not found")
    except Exception as e:
        print(f"❌ Error reading requirements.txt: {e}")

def test_local_startup():
    """Test if app can start locally"""
    print_section("LOCAL STARTUP TEST")
    
    # Set Railway-like environment
    os.environ['PORT'] = '8001'  # Use different port to avoid conflicts
    os.environ['ENVIRONMENT'] = 'production'
    
    try:
        print("🔄 Testing application startup...")
        
        # Try to import main module
        import main
        print("✅ main.py imports successfully")
        
        # Check if app exists
        if hasattr(main, 'app'):
            print("✅ FastAPI app found")
        else:
            print("❌ No FastAPI app found in main.py")
            return False
        
        return True
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False
    except Exception as e:
        print(f"❌ Startup error: {e}")
        return False

def test_endpoints_local():
    """Test endpoints on local server"""
    print_section("LOCAL ENDPOINT TEST")
    
    port = 8001
    
    try:
        # Start server in background
        print(f"🚀 Starting server on port {port}...")
        
        cmd = [
            sys.executable, '-m', 'uvicorn', 
            'main:app', 
            '--host', '127.0.0.1', 
            '--port', str(port),
            '--log-level', 'error'  # Suppress logs
        ]
        
        process = subprocess.Popen(
            cmd, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE,
            text=True
        )
        
        # Wait for server to start
        time.sleep(3)
        
        if process.poll() is not None:
            stdout, stderr = process.communicate()
            print(f"❌ Server failed to start")
            print(f"STDOUT: {stdout}")
            print(f"STDERR: {stderr}")
            return False
        
        # Test endpoints
        base_url = f"http://127.0.0.1:{port}"
        endpoints = ['/ping', '/health', '/']
        
        results = {}
        
        for endpoint in endpoints:
            url = f"{base_url}{endpoint}"
            try:
                with urllib.request.urlopen(url, timeout=5) as response:
                    status_code = response.getcode()
                    if status_code == 200:
                        print(f"✅ {endpoint} - Status: {status_code}")
                        results[endpoint] = True
                    else:
                        print(f"⚠️  {endpoint} - Status: {status_code}")
                        results[endpoint] = False
            except urllib.error.HTTPError as e:
                print(f"❌ {endpoint} - HTTP Error: {e.code}")
                results[endpoint] = False
            except Exception as e:
                print(f"❌ {endpoint} - Error: {e}")
                results[endpoint] = False
        
        # Stop server
        process.terminate()
        process.wait(timeout=5)
        
        # Results
        success_count = sum(results.values())
        total_count = len(results)
        
        print(f"\n📊 Results: {success_count}/{total_count} endpoints working")
        
        if success_count == total_count:
            print("✅ All endpoints working locally")
            return True
        else:
            print("❌ Some endpoints failed locally")
            return False
            
    except Exception as e:
        print(f"❌ Local endpoint test failed: {e}")
        try:
            process.terminate()
        except:
            pass
        return False

def generate_railway_debug_info():
    """Generate debug information for Railway support"""
    print_section("RAILWAY DEBUG INFORMATION")
    
    info = {
        'timestamp': datetime.now().isoformat(),
        'python_version': sys.version,
        'platform': sys.platform,
        'files_present': {
            'Dockerfile': os.path.exists('Dockerfile'),
            'railway.json': os.path.exists('railway.json'),
            'requirements.txt': os.path.exists('requirements.txt'),
            'main.py': os.path.exists('main.py')
        }
    }
    
    # Check if git repo
    try:
        result = subprocess.run(['git', 'rev-parse', 'HEAD'], 
                              capture_output=True, text=True)
        if result.returncode == 0:
            info['git_commit'] = result.stdout.strip()[:8]
    except:
        pass
    
    print("📋 Debug Information for Railway Support:")
    print(json.dumps(info, indent=2))
    
    return info

def main():
    print("🔧 RAILWAY DEPLOYMENT DIAGNOSTICS")
    print(f"Timestamp: {datetime.now().isoformat()}")
    
    results = {}
    
    # Run all checks
    check_dockerfile()
    check_railway_json() 
    check_requirements()
    
    results['local_startup'] = test_local_startup()
    results['local_endpoints'] = test_endpoints_local()
    
    debug_info = generate_railway_debug_info()
    
    # Final summary
    print_section("FINAL DIAGNOSIS")
    
    success_count = sum(results.values())
    total_count = len(results)
    
    print(f"📊 Overall Status: {success_count}/{total_count} tests passed")
    
    if success_count == total_count:
        print("✅ LOCAL ENVIRONMENT OK - Issue likely Railway-specific")
        print("\n🔧 Railway-specific troubleshooting:")
        print("1. Check Railway deployment logs in dashboard")
        print("2. Verify environment variables are set in Railway")
        print("3. Ensure Railway has enough resources allocated")
        print("4. Try manual redeploy in Railway dashboard")
    else:
        print("❌ LOCAL ISSUES FOUND - Fix these first")
        print("\n🔧 Next steps:")
        print("1. Fix the issues identified above")
        print("2. Test locally until all tests pass")
        print("3. Commit and push changes")
        print("4. Redeploy on Railway")

if __name__ == "__main__":
    main()
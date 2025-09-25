#!/usr/bin/env python3
"""
Monitor Railway deployment in real-time
"""

import requests
import time
import json
from datetime import datetime

def test_endpoint(url, max_attempts=10, wait_seconds=30):
    """Test endpoint with retry logic"""
    print(f"🔍 Monitoring: {url}")
    print(f"⏱️  Will check every {wait_seconds} seconds for {max_attempts} attempts")
    print("=" * 60)
    
    for attempt in range(1, max_attempts + 1):
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"\n[{timestamp}] Attempt {attempt}/{max_attempts}")
        
        try:
            response = requests.get(url + "/ping", timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                print(f"✅ SUCCESS! Status: {response.status_code}")
                print(f"📄 Response: {json.dumps(data, indent=2)}")
                
                # Test health endpoint too
                health_response = requests.get(url + "/health", timeout=15)
                if health_response.status_code == 200:
                    health_data = health_response.json()
                    print(f"✅ Health check: {json.dumps(health_data, indent=2)}")
                
                print(f"\n🎉 DEPLOYMENT SUCCESSFUL!")
                print(f"🌐 Your API is live at: {url}")
                return True
                
            elif response.status_code == 502:
                print(f"🔄 Still getting 502 - Deployment might be in progress")
                try:
                    error_data = response.json()
                    request_id = error_data.get('request_id', 'unknown')
                    print(f"   Request ID: {request_id}")
                except:
                    pass
                    
            else:
                print(f"⚠️  Status: {response.status_code}")
                print(f"   Response: {response.text[:100]}...")
                
        except requests.exceptions.Timeout:
            print(f"⏰ Timeout - Server not responding yet")
        except requests.exceptions.ConnectionError:
            print(f"🔌 Connection error - Deployment might be restarting")
        except Exception as e:
            print(f"❌ Error: {e}")
        
        if attempt < max_attempts:
            print(f"⏳ Waiting {wait_seconds} seconds before next attempt...")
            time.sleep(wait_seconds)
    
    print(f"\n❌ DEPLOYMENT MONITORING COMPLETED")
    print(f"   After {max_attempts} attempts, deployment still not responding")
    print(f"   Check Railway Dashboard for detailed logs")
    return False

def main():
    print("🚂 RAILWAY DEPLOYMENT MONITOR")
    print("=" * 60)
    
    url = "https://gestorproyectoapi-production.up.railway.app"
    
    print(f"🎯 Target URL: {url}")
    print(f"📅 Started: {datetime.now().isoformat()}")
    
    success = test_endpoint(url, max_attempts=8, wait_seconds=30)
    
    if not success:
        print("\n📋 TROUBLESHOOTING STEPS:")
        print("1. Check Railway Dashboard → Deployments")
        print("2. Look for build/deploy errors in logs")
        print("3. Verify latest commit was deployed")
        print("4. Check if deployment is still in progress")

if __name__ == "__main__":
    main()
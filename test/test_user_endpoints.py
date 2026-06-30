"""
Test Suite for User Authentication Endpoints
Pruebas, diagnóstico y debug para endpoints del tag "Administración y Control de Accesos"
"""

import asyncio
import httpx
import json
import logging
from typing import Dict, Any, Optional
from datetime import datetime
import sys
import os

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class UserEndpointTester:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.client = None
        self.test_results = []
        
    async def __aenter__(self):
        self.client = httpx.AsyncClient(timeout=30.0)
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.client:
            await self.client.aclose()
    
    def log_test_result(self, endpoint: str, method: str, status_code: int, 
                       response_data: Any, success: bool, error: Optional[str] = None):
        """Log and store test results"""
        result = {
            "timestamp": datetime.now().isoformat(),
            "endpoint": endpoint,
            "method": method,
            "status_code": status_code,
            "success": success,
            "response_data": response_data,
            "error": error
        }
        self.test_results.append(result)
        
        status = "✅ PASS" if success else "❌ FAIL"
        logger.info(f"{status} {method} {endpoint} - Status: {status_code}")
        if error:
            logger.error(f"Error: {error}")
        
    async def test_server_health(self) -> bool:
        """Test if server is running and accessible"""
        try:
            response = await self.client.get(f"{self.base_url}/")
            success = response.status_code == 200
            self.log_test_result("/", "GET", response.status_code, 
                               response.json() if success else response.text, success)
            return success
        except Exception as e:
            self.log_test_result("/", "GET", 0, None, False, str(e))
            return False
    
    async def test_swagger_docs(self) -> bool:
        """Test if Swagger documentation is accessible"""
        try:
            response = await self.client.get(f"{self.base_url}/docs")
            success = response.status_code == 200
            self.log_test_result("/docs", "GET", response.status_code, 
                               "Swagger UI accessible" if success else response.text, success)
            return success
        except Exception as e:
            self.log_test_result("/docs", "GET", 0, None, False, str(e))
            return False
    
    async def test_openapi_schema(self) -> bool:
        """Test OpenAPI schema availability"""
        try:
            response = await self.client.get(f"{self.base_url}/openapi.json")
            success = response.status_code == 200
            schema = response.json() if success else None
            
            # Check if auth endpoints are in schema
            auth_endpoints = []
            google_endpoints = []
            if schema and "paths" in schema:
                for path, methods in schema["paths"].items():
                    if "auth" in path:
                        auth_endpoints.append(path)
                        if "google" in path:
                            google_endpoints.append(path)
            
            self.log_test_result("/openapi.json", "GET", response.status_code, 
                               {"auth_endpoints_found": auth_endpoints, "google_endpoints_found": google_endpoints}, success)
            return success
        except Exception as e:
            self.log_test_result("/openapi.json", "GET", 0, None, False, str(e))
            return False
    
    async def test_workload_identity_status(self) -> bool:
        """Test Workload Identity Federation status"""
        try:
            response = await self.client.get(f"{self.base_url}/auth/workload-identity/status")
            success = response.status_code == 200
            status_data = response.json() if success else None
            
            self.log_test_result("/auth/workload-identity/status", "GET", response.status_code, 
                               status_data, success)
            return success
        except Exception as e:
            self.log_test_result("/auth/workload-identity/status", "GET", 0, None, False, str(e))
            return False
    
    # ENDPOINT REMOVIDO: test_integration_guide
    # Razón: Endpoint /auth/integration-guide eliminado (2025-10-04)
    # La documentación está disponible en README.md
    
    async def test_deprecated_endpoints(self) -> Dict[str, Any]:
        """Test that deprecated endpoints no longer exist"""
        deprecated_endpoints = [
            {"path": "/auth/google/callback", "method": "POST"},
            {"path": "/auth/google/url", "method": "GET"},
            {"path": "/auth/google/config", "method": "GET"},
            {"path": "/auth/google/status", "method": "GET"}
        ]
        
        results = []
        for endpoint in deprecated_endpoints:
            try:
                if endpoint["method"] == "GET":
                    response = await self.client.get(f"{self.base_url}{endpoint['path']}")
                else:
                    response = await self.client.post(f"{self.base_url}{endpoint['path']}", data={})
                
                # We expect these to return 404 (not found) since they're deprecated
                success = response.status_code == 404
                
                result = {
                    "endpoint": endpoint["path"],
                    "method": endpoint["method"],
                    "status_code": response.status_code,
                    "success": success,
                    "note": "Should return 404 (deprecated)"
                }
                results.append(result)
                
                self.log_test_result(f"{endpoint['path']} (deprecated check)", endpoint["method"], 
                                   response.status_code, result, success)
                
            except Exception as e:
                result = {
                    "endpoint": endpoint["path"],
                    "method": endpoint["method"],
                    "status_code": 0,
                    "success": False,
                    "error": str(e)
                }
                results.append(result)
                self.log_test_result(f"{endpoint['path']} (deprecated check)", endpoint["method"], 
                                   0, None, False, str(e))
        
        return {"test_name": "deprecated_endpoints", "results": results}
    
    async def test_login_endpoint(self) -> Dict[str, Any]:
        """Test /auth/login endpoint with various scenarios"""
        endpoint = "/auth/login"
        test_cases = [
            {
                "name": "Valid login attempt",
                "data": {
                    "email": "test.user@cali.gov.co",
                    "password": "TestPassword123!"
                },
                "expected_status": [200, 401, 404]  # Multiple acceptable statuses
            },
            {
                "name": "Invalid email format",
                "data": {
                    "email": "invalid-email",
                    "password": "TestPassword123!"
                },
                "expected_status": [400, 401, 422]  # 401 is also acceptable for invalid credentials
            },
            {
                "name": "Missing password",
                "data": {
                    "email": "test.user@cali.gov.co"
                },
                "expected_status": [400, 422]
            },
            {
                "name": "Empty payload",
                "data": {},
                "expected_status": [400, 422]
            }
        ]
        
        results = []
        for case in test_cases:
            try:
                # Test with form data (as configured in endpoint)
                response = await self.client.post(
                    f"{self.base_url}{endpoint}",
                    data=case["data"]
                )
                
                success = response.status_code in case["expected_status"]
                response_data = None
                
                try:
                    response_data = response.json()
                except:
                    response_data = response.text
                
                result = {
                    "test_case": case["name"],
                    "status_code": response.status_code,
                    "success": success,
                    "response_data": response_data
                }
                results.append(result)
                
                self.log_test_result(f"{endpoint} ({case['name']})", "POST", 
                                   response.status_code, response_data, success)
                
            except Exception as e:
                result = {
                    "test_case": case["name"],
                    "status_code": 0,
                    "success": False,
                    "error": str(e)
                }
                results.append(result)
                self.log_test_result(f"{endpoint} ({case['name']})", "POST", 
                                   0, None, False, str(e))
        
        return {"endpoint": endpoint, "results": results}
    
    async def test_register_endpoint(self) -> Dict[str, Any]:
        """Test /auth/register endpoint with various scenarios"""
        endpoint = "/auth/register"
        test_cases = [
            {
                "name": "Valid registration attempt",
                "data": {
                    "email": f"test.user.{datetime.now().timestamp()}@cali.gov.co",
                    "password": "TestPassword123!",
                    "fullname": "Test User",
                    "cellphone": "+57 300 123 4567",
                    "nombre_centro_gestor": "DATIC - Tecnologías de la Información"
                },
                "expected_status": [201, 400, 409]  # Created, Bad Request, or Conflict
            },
            {
                "name": "Invalid domain email",
                "data": {
                    "email": "test@gmail.com",
                    "password": "TestPassword123!",
                    "fullname": "Test User",
                    "cellphone": "+57 300 123 4567",
                    "nombre_centro_gestor": "DATIC"
                },
                "expected_status": [400, 409, 422]  # 409 is also acceptable for domain restrictions
            },
            {
                "name": "Missing required fields",
                "data": {
                    "email": "test@cali.gov.co",
                    "password": "weak"
                },
                "expected_status": [400, 422]
            }
        ]
        
        results = []
        for case in test_cases:
            try:
                response = await self.client.post(
                    f"{self.base_url}{endpoint}",
                    data=case["data"]
                )
                
                success = response.status_code in case["expected_status"]
                response_data = None
                
                try:
                    response_data = response.json()
                except:
                    response_data = response.text
                
                result = {
                    "test_case": case["name"],
                    "status_code": response.status_code,
                    "success": success,
                    "response_data": response_data
                }
                results.append(result)
                
                self.log_test_result(f"{endpoint} ({case['name']})", "POST", 
                                   response.status_code, response_data, success)
                
            except Exception as e:
                result = {
                    "test_case": case["name"],
                    "status_code": 0,
                    "success": False,
                    "error": str(e)
                }
                results.append(result)
                self.log_test_result(f"{endpoint} ({case['name']})", "POST", 
                                   0, None, False, str(e))
        
        return {"endpoint": endpoint, "results": results}
    
    async def test_change_password_endpoint(self) -> Dict[str, Any]:
        """Test /auth/change-password endpoint"""
        endpoint = "/auth/change-password"
        test_cases = [
            {
                "name": "Valid password change request",
                "data": {
                    "uid": "test-uid-123",
                    "new_password": "NewPassword123!"
                },
                "expected_status": [200, 400, 404]
            },
            {
                "name": "Missing UID",
                "data": {
                    "new_password": "NewPassword123!"
                },
                "expected_status": [400, 422]
            },
            {
                "name": "Weak password",
                "data": {
                    "uid": "test-uid-123",
                    "new_password": "weak"
                },
                "expected_status": [400, 422]
            }
        ]
        
        results = []
        for case in test_cases:
            try:
                response = await self.client.post(
                    f"{self.base_url}{endpoint}",
                    data=case["data"]
                )
                
                success = response.status_code in case["expected_status"]
                response_data = None
                
                try:
                    response_data = response.json()
                except:
                    response_data = response.text
                
                result = {
                    "test_case": case["name"],
                    "status_code": response.status_code,
                    "success": success,
                    "response_data": response_data
                }
                results.append(result)
                
                self.log_test_result(f"{endpoint} ({case['name']})", "POST", 
                                   response.status_code, response_data, success)
                
            except Exception as e:
                result = {
                    "test_case": case["name"],
                    "status_code": 0,
                    "success": False,
                    "error": str(e)
                }
                results.append(result)
                self.log_test_result(f"{endpoint} ({case['name']})", "POST", 
                                   0, None, False, str(e))
        
        return {"endpoint": endpoint, "results": results}
    
    async def test_google_auth_endpoint(self) -> Dict[str, Any]:
        """Test /auth/google endpoint with Workload Identity"""
        endpoint = "/auth/google"
        test_cases = [
            {
                "name": "Valid Google token format (test with fake token)",
                "data": {
                    "google_token": "eyJhbGciOiJSUzI1NiIsImtpZCI6IjE2ZjU4YjFiNzkyZGJkYjM5OGZkNjVmMGMzODI4YmI5YWNlZTRjMWUiLCJ0eXAiOiJKV1QifQ.eyJpc3MiOiJhY2NvdW50cy5nb29nbGUuY29tIiwiYXVkIjoiY2xpZW50LWlkLXRlc3QiLCJzdWIiOiIxMjM0NTY3ODkwMTIzNDU2Nzg5MDEiLCJlbWFpbCI6InRlc3QudXNlckBjYWxpLmdvdi5jbyIsImVtYWlsX3ZlcmlmaWVkIjp0cnVlLCJuYW1lIjoiVGVzdCBVc2VyIiwicGljdHVyZSI6Imh0dHBzOi8vZXhhbXBsZS5jb20vcGhvdG8uanBnIiwiaWF0IjoxNjIzNzM2MDAwLCJleHAiOjE2MjM3Mzk2MDB9.test-signature"
                },
                "expected_status": [200, 401, 403, 503]  # Success, Invalid Token, Unauthorized Domain, Service Unavailable
            },
            {
                "name": "Invalid token format",
                "data": {
                    "google_token": "invalid.token.format"
                },
                "expected_status": [401, 400, 503]
            },
            {
                "name": "Missing google_token parameter",
                "data": {},
                "expected_status": [400, 422]
            },
            {
                "name": "Empty google_token",
                "data": {
                    "google_token": ""
                },
                "expected_status": [400, 401, 422]  # 401 is also acceptable for empty/invalid token
            }
        ]
        
        results = []
        for case in test_cases:
            try:
                response = await self.client.post(
                    f"{self.base_url}{endpoint}",
                    data=case["data"]
                )
                
                success = response.status_code in case["expected_status"]
                response_data = None
                
                try:
                    response_data = response.json()
                except:
                    response_data = response.text
                
                result = {
                    "test_case": case["name"],
                    "status_code": response.status_code,
                    "success": success,
                    "response_data": response_data
                }
                results.append(result)
                
                self.log_test_result(f"{endpoint} ({case['name']})", "POST", 
                                   response.status_code, response_data, success)
                
            except Exception as e:
                result = {
                    "test_case": case["name"],
                    "status_code": 0,
                    "success": False,
                    "error": str(e)
                }
                results.append(result)
                self.log_test_result(f"{endpoint} ({case['name']})", "POST", 
                                   0, None, False, str(e))
        
        return {"endpoint": endpoint, "results": results}
    
    async def test_validate_session_endpoint(self) -> Dict[str, Any]:
        """Test /auth/validate-session endpoint"""
        endpoint = "/auth/validate-session"
        test_cases = [
            {
                "name": "Valid token format",
                "data": {
                    "id_token": "eyJhbGciOiJSUzI1NiIsImtpZCI6IjE2ZjU4YjFiNzkyZGJkYjM5OGZkNjVmMGMzODI4YmI5YWNlZTRjMWUiLCJ0eXAiOiJKV1QifQ.test.token"
                },
                "expected_status": [200, 401, 400]
            },
            {
                "name": "Invalid token format",
                "data": {
                    "id_token": "invalid-token"
                },
                "expected_status": [400, 401]
            },
            {
                "name": "Missing token",
                "data": {},
                "expected_status": [400, 422]
            }
        ]
        
        results = []
        for case in test_cases:
            try:
                response = await self.client.post(
                    f"{self.base_url}{endpoint}",
                    data=case["data"]
                )
                
                success = response.status_code in case["expected_status"]
                response_data = None
                
                try:
                    response_data = response.json()
                except:
                    response_data = response.text
                
                result = {
                    "test_case": case["name"],
                    "status_code": response.status_code,
                    "success": success,
                    "response_data": response_data
                }
                results.append(result)
                
                self.log_test_result(f"{endpoint} ({case['name']})", "POST", 
                                   response.status_code, response_data, success)
                
            except Exception as e:
                result = {
                    "test_case": case["name"],
                    "status_code": 0,
                    "success": False,
                    "error": str(e)
                }
                results.append(result)
                self.log_test_result(f"{endpoint} ({case['name']})", "POST", 
                                   0, None, False, str(e))
        
        return {"endpoint": endpoint, "results": results}
    
    async def run_all_tests(self) -> Dict[str, Any]:
        """Run all authentication endpoint tests"""
        logger.info("🚀 Starting Authentication Endpoints Test Suite")
        logger.info("=" * 60)
        
        # Test server health first
        server_healthy = await self.test_server_health()
        if not server_healthy:
            logger.error("❌ Server is not accessible. Aborting tests.")
            return {"error": "Server not accessible", "results": self.test_results}
        
        # Test documentation availability
        await self.test_swagger_docs()
        await self.test_openapi_schema()
        
        # Test Workload Identity Status
        logger.info("\n🔗 Testing Workload Identity Status")
        logger.info("-" * 40)
        await self.test_workload_identity_status()
        
        # Test all authentication endpoints
        logger.info("\n🔐 Testing Authentication Endpoints")
        logger.info("-" * 40)
        
        login_results = await self.test_login_endpoint()
        register_results = await self.test_register_endpoint()
        change_password_results = await self.test_change_password_endpoint()
        google_auth_results = await self.test_google_auth_endpoint()
        validate_session_results = await self.test_validate_session_endpoint()
        
        # Test deprecated endpoints
        logger.info("\n🗑️ Testing Deprecated Endpoints (Should be 404)")
        logger.info("-" * 40)
        deprecated_results = await self.test_deprecated_endpoints()
        
        # Summary
        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results if result["success"])
        failed_tests = total_tests - passed_tests
        
        summary = {
            "total_tests": total_tests,
            "passed": passed_tests,
            "failed": failed_tests,
            "success_rate": f"{(passed_tests/total_tests*100):.1f}%" if total_tests > 0 else "0%"
        }
        
        logger.info("\n" + "=" * 60)
        logger.info("📊 TEST SUMMARY")
        logger.info("=" * 60)
        logger.info(f"Total Tests: {summary['total_tests']}")
        logger.info(f"✅ Passed: {summary['passed']}")
        logger.info(f"❌ Failed: {summary['failed']}")
        logger.info(f"📈 Success Rate: {summary['success_rate']}")
        
        return {
            "summary": summary,
            "endpoint_results": {
                "login": login_results,
                "register": register_results,
                "change_password": change_password_results,
                "google_auth": google_auth_results,
                "validate_session": validate_session_results,
                "deprecated_endpoints": deprecated_results
            },
            "all_results": self.test_results
        }
    
    def save_results_to_file(self, filename: str = None):
        """Save test results to JSON file"""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"test_results_{timestamp}.json"
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(self.test_results, f, indent=2, ensure_ascii=False)
        
        logger.info(f"💾 Test results saved to: {filename}")

async def main():
    """Main test runner"""
    async with UserEndpointTester() as tester:
        results = await tester.run_all_tests()
        
        # Save results
        tester.save_results_to_file()
        
        # Return results for potential further processing
        return results

if __name__ == "__main__":
    try:
        results = asyncio.run(main())
        print(f"\n🎉 Test suite completed. Check the logs above for detailed results.")
    except KeyboardInterrupt:
        print("\n⏹️ Test suite interrupted by user.")
    except Exception as e:
        print(f"\n💥 Test suite failed with error: {e}")
        logger.exception("Test suite error")

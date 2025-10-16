#!/usr/bin/env python3
"""
Monitor continuo para el endpoint /auth/register
Script para verificar el estado en producción y detectar problemas
"""

import requests
import time
import json
from datetime import datetime
import sys
import argparse

class RegisterEndpointMonitor:
    """
    Monitor para el endpoint de registro
    """
    
    def __init__(self, base_url, check_interval=60):
        self.base_url = base_url.rstrip('/')
        self.check_interval = check_interval
        self.errors_count = 0
        self.last_successful_check = None
        
    def check_health(self):
        """
        Verificar estado de salud del endpoint
        """
        try:
            response = requests.get(
                f"{self.base_url}/auth/register/health-check",
                timeout=30
            )
            
            result = {
                "timestamp": datetime.now().isoformat(),
                "status_code": response.status_code,
                "healthy": response.status_code == 200,
                "response_time": response.elapsed.total_seconds(),
                "details": None
            }
            
            try:
                result["details"] = response.json()
            except:
                result["details"] = {"error": "Invalid JSON response"}
            
            return result
            
        except requests.exceptions.Timeout:
            return {
                "timestamp": datetime.now().isoformat(),
                "status_code": 0,
                "healthy": False,
                "error": "Timeout",
                "response_time": None
            }
        except requests.exceptions.ConnectionError:
            return {
                "timestamp": datetime.now().isoformat(),
                "status_code": 0,
                "healthy": False,
                "error": "Connection Error",
                "response_time": None
            }
        except Exception as e:
            return {
                "timestamp": datetime.now().isoformat(),
                "status_code": 0,
                "healthy": False,
                "error": str(e),
                "response_time": None
            }
    
    def test_registration(self):
        """
        Probar el endpoint de registro con datos de prueba
        """
        test_data = {
            "email": f"test.{int(time.time())}@cali.gov.co",
            "password": "TestPassword123!",
            "confirmPassword": "TestPassword123!",
            "name": "Usuario de Prueba Monitor",
            "cellphone": "3001234567",
            "nombre_centro_gestor": "Secretaría de Hacienda"
        }
        
        try:
            response = requests.post(
                f"{self.base_url}/auth/register",
                json=test_data,
                headers={"Content-Type": "application/json"},
                timeout=30
            )
            
            result = {
                "timestamp": datetime.now().isoformat(),
                "status_code": response.status_code,
                "successful": response.status_code in [201, 409],  # 409 = usuario ya existe
                "response_time": response.elapsed.total_seconds(),
                "test_email": test_data["email"]
            }
            
            try:
                response_data = response.json()
                result["response"] = response_data
                
                # Analizar tipo de respuesta
                if response.status_code == 201:
                    result["result_type"] = "user_created"
                elif response.status_code == 409:
                    result["result_type"] = "user_exists"
                elif response.status_code == 400:
                    result["result_type"] = "validation_error"
                elif response.status_code == 503:
                    result["result_type"] = "service_unavailable"
                else:
                    result["result_type"] = "unknown_error"
                    
            except:
                result["response"] = {"error": "Invalid JSON"}
                result["result_type"] = "invalid_response"
            
            return result
            
        except Exception as e:
            return {
                "timestamp": datetime.now().isoformat(),
                "status_code": 0,
                "successful": False,
                "error": str(e),
                "response_time": None,
                "test_email": test_data["email"]
            }
    
    def run_comprehensive_check(self):
        """
        Ejecutar verificación completa
        """
        print(f"🔍 [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Verificando {self.base_url}")
        
        # 1. Health check
        health_result = self.check_health()
        print(f"   Health Check: {'✅' if health_result['healthy'] else '❌'} " +
              f"({health_result.get('status_code', 'N/A')})")
        
        if health_result.get('response_time'):
            print(f"   Response Time: {health_result['response_time']:.2f}s")
        
        # 2. Si health check pasa, probar registro
        if health_result['healthy']:
            print("   Probando registro...")
            register_result = self.test_registration()
            
            if register_result['successful']:
                print(f"   Registro: ✅ {register_result.get('result_type', 'unknown')}")
                self.last_successful_check = datetime.now()
                self.errors_count = 0
            else:
                print(f"   Registro: ❌ Status {register_result.get('status_code', 'N/A')}")
                self.errors_count += 1
                
                # Mostrar detalles del error
                if 'response' in register_result:
                    error_detail = register_result['response'].get('error', 'Unknown error')
                    print(f"   Error: {error_detail}")
        else:
            self.errors_count += 1
            error_detail = health_result.get('error', 'Health check failed')
            print(f"   Error: {error_detail}")
        
        # Mostrar estadísticas
        if self.last_successful_check:
            time_since_success = datetime.now() - self.last_successful_check
            print(f"   Último éxito: hace {time_since_success}")
        
        print(f"   Errores consecutivos: {self.errors_count}")
        
        return {
            "health": health_result,
            "registration": register_result if health_result['healthy'] else None,
            "errors_count": self.errors_count,
            "last_successful": self.last_successful_check.isoformat() if self.last_successful_check else None
        }
    
    def run_continuous_monitoring(self):
        """
        Ejecutar monitoreo continuo
        """
        print(f"🚀 Iniciando monitoreo continuo del endpoint /auth/register")
        print(f"🌐 URL: {self.base_url}")
        print(f"⏱️ Intervalo: {self.check_interval}s")
        print("=" * 60)
        
        try:
            while True:
                result = self.run_comprehensive_check()
                
                # Alertas
                if self.errors_count >= 3:
                    print(f"🚨 ALERTA: {self.errors_count} errores consecutivos!")
                
                if self.errors_count >= 5:
                    print("🆘 CRÍTICO: Servicio posiblemente caído!")
                
                print("-" * 60)
                time.sleep(self.check_interval)
                
        except KeyboardInterrupt:
            print("\n👋 Monitoreo detenido por usuario")
        except Exception as e:
            print(f"\n❌ Error en monitoreo: {e}")

def main():
    """
    Función principal
    """
    parser = argparse.ArgumentParser(description="Monitor del endpoint /auth/register")
    parser.add_argument("url", help="URL base de la API (ej: https://api.ejemplo.com)")
    parser.add_argument("--interval", type=int, default=60, help="Intervalo entre checks en segundos")
    parser.add_argument("--single", action="store_true", help="Ejecutar una sola verificación")
    parser.add_argument("--health-only", action="store_true", help="Solo health check")
    
    args = parser.parse_args()
    
    monitor = RegisterEndpointMonitor(args.url, args.interval)
    
    if args.single:
        if args.health_only:
            result = monitor.check_health()
            print(json.dumps(result, indent=2, ensure_ascii=False))
        else:
            result = monitor.run_comprehensive_check()
            print("\n📊 Resultado completo:")
            print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
    else:
        monitor.run_continuous_monitoring()

if __name__ == "__main__":
    # Si no hay argumentos, mostrar ayuda
    if len(sys.argv) == 1:
        print("🔧 MONITOR DEL ENDPOINT /auth/register")
        print("=" * 50)
        print("Uso:")
        print("  python monitor_register.py <URL_API>")
        print("  python monitor_register.py <URL_API> --single")
        print("  python monitor_register.py <URL_API> --health-only")
        print("")
        print("Ejemplos:")
        print("  python monitor_register.py https://api.ejemplo.com")
        print("  python monitor_register.py https://api.ejemplo.com --single")
        print("  python monitor_register.py http://localhost:8000 --interval 30")
        print("")
        print("Opciones:")
        print("  --interval N    Intervalo entre checks (default: 60s)")
        print("  --single        Una sola verificación")
        print("  --health-only   Solo health check")
        sys.exit(1)
    
    main()
"""
Script para Ejecutar Tests del Sistema de Autenticación
Ejecuta todos los tests y genera un reporte detallado
"""

import subprocess
import sys
import os
from datetime import datetime

# Colores para terminal
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'


def print_section(title):
    """Imprime una sección con formato"""
    print("\n" + "=" * 70)
    print(f"{BLUE}{title}{RESET}")
    print("=" * 70 + "\n")


def print_success(message):
    """Imprime mensaje de éxito"""
    print(f"{GREEN}✅ {message}{RESET}")


def print_error(message):
    """Imprime mensaje de error"""
    print(f"{RED}❌ {message}{RESET}")


def print_warning(message):
    """Imprime mensaje de advertencia"""
    print(f"{YELLOW}⚠️  {message}{RESET}")


def print_info(message):
    """Imprime mensaje informativo"""
    print(f"{BLUE}ℹ️  {message}{RESET}")


def check_pytest_installed():
    """Verifica que pytest esté instalado"""
    try:
        import pytest
        return True
    except ImportError:
        return False


def install_pytest():
    """Instala pytest si no está disponible"""
    print_warning("pytest no está instalado. Instalando...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pytest", "pytest-cov"])
        print_success("pytest instalado correctamente")
        return True
    except subprocess.CalledProcessError:
        print_error("No se pudo instalar pytest")
        return False


def run_unit_tests():
    """Ejecuta tests unitarios"""
    print_section("TESTS UNITARIOS - Sistema de Autenticación")
    
    cmd = [
        sys.executable, "-m", "pytest",
        "test/test_auth_system.py",
        "-v",
        "--tb=short",
        "--color=yes"
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=False, text=True)
        return result.returncode == 0
    except Exception as e:
        print_error(f"Error ejecutando tests unitarios: {e}")
        return False


def run_integration_tests():
    """Ejecuta tests de integración"""
    print_section("TESTS DE INTEGRACIÓN - Endpoints del API")
    
    cmd = [
        sys.executable, "-m", "pytest",
        "test/test_auth_endpoints.py",
        "-v",
        "--tb=short",
        "--color=yes"
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=False, text=True)
        return result.returncode == 0
    except Exception as e:
        print_error(f"Error ejecutando tests de integración: {e}")
        return False


def run_all_tests_with_coverage():
    """Ejecuta todos los tests con reporte de cobertura"""
    print_section("EJECUTANDO TODOS LOS TESTS CON COBERTURA")
    
    cmd = [
        sys.executable, "-m", "pytest",
        "test/test_auth_system.py",
        "test/test_auth_endpoints.py",
        "-v",
        "--tb=short",
        "--cov=auth_system",
        "--cov-report=term-missing",
        "--cov-report=html",
        "--color=yes"
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=False, text=True)
        
        if result.returncode == 0:
            print_success("\nTodos los tests pasaron correctamente")
            print_info("Reporte de cobertura HTML generado en: htmlcov/index.html")
            return True
        else:
            print_error("\nAlgunos tests fallaron")
            return False
    except Exception as e:
        print_error(f"Error ejecutando tests: {e}")
        return False


def run_specific_test_class(test_class):
    """Ejecuta una clase específica de tests"""
    print_section(f"EJECUTANDO: {test_class}")
    
    # Determinar archivo según el nombre de la clase
    if "Endpoint" in test_class or "Admin" in test_class:
        test_file = "test/test_auth_endpoints.py"
    else:
        test_file = "test/test_auth_system.py"
    
    cmd = [
        sys.executable, "-m", "pytest",
        f"{test_file}::{test_class}",
        "-v",
        "--tb=short",
        "--color=yes"
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=False, text=True)
        return result.returncode == 0
    except Exception as e:
        print_error(f"Error ejecutando test: {e}")
        return False


def show_test_summary():
    """Muestra resumen de tests disponibles"""
    print_section("TESTS DISPONIBLES")
    
    print("📦 Tests Unitarios (test_auth_system.py):")
    print("   • TestRolesConstants - Constantes de roles")
    print("   • TestPermissions - Sistema de permisos")
    print("   • TestUtils - Funciones utilitarias")
    print("   • TestMiddleware - Middlewares")
    print("   • TestRoleHierarchy - Jerarquía de roles")
    print("   • TestPermissionScopes - Scopes de permisos")
    print("   • TestFirebaseCollections - Colecciones Firebase")
    print("   • TestRolePermissionsCoverage - Cobertura de permisos")
    
    print("\n🌐 Tests de Integración (test_auth_endpoints.py):")
    print("   • TestPublicEndpoints - Endpoints públicos")
    print("   • TestAuthEndpoints - Autenticación")
    print("   • TestAdminUsersEndpoints - Administración usuarios")
    print("   • TestRolesEndpoints - Gestión de roles")
    print("   • TestRoleAssignment - Asignación de roles")
    print("   • TestTemporaryPermissions - Permisos temporales")
    print("   • TestAuditLogs - Logs de auditoría")
    print("   • TestSystemStats - Estadísticas del sistema")
    print("   • TestInputValidation - Validación de inputs")


def interactive_menu():
    """Menú interactivo para ejecutar tests"""
    while True:
        print_section("MENÚ DE TESTS - Sistema de Autenticación")
        
        print("1. Ejecutar TODOS los tests con cobertura")
        print("2. Ejecutar solo tests unitarios")
        print("3. Ejecutar solo tests de integración")
        print("4. Ver lista de tests disponibles")
        print("5. Ejecutar test específico")
        print("0. Salir")
        
        choice = input("\n👉 Selecciona una opción: ").strip()
        
        if choice == "1":
            run_all_tests_with_coverage()
        elif choice == "2":
            run_unit_tests()
        elif choice == "3":
            run_integration_tests()
        elif choice == "4":
            show_test_summary()
        elif choice == "5":
            print("\nClases de tests disponibles:")
            print("  - TestRolesConstants")
            print("  - TestPermissions")
            print("  - TestUtils")
            print("  - TestAdminUsersEndpoints")
            print("  - TestRoleAssignment")
            test_class = input("\nIngresa el nombre de la clase: ").strip()
            run_specific_test_class(test_class)
        elif choice == "0":
            print_info("¡Hasta luego!")
            break
        else:
            print_error("Opción inválida")
        
        input("\n✨ Presiona Enter para continuar...")


def main():
    """Función principal"""
    print_section("🧪 SISTEMA DE TESTS - Autenticación y Autorización")
    print(f"📅 Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Verificar pytest
    if not check_pytest_installed():
        if not install_pytest():
            print_error("No se puede continuar sin pytest")
            sys.exit(1)
    
    # Si se pasan argumentos, ejecutar modo no interactivo
    if len(sys.argv) > 1:
        arg = sys.argv[1].lower()
        
        if arg == "all":
            success = run_all_tests_with_coverage()
        elif arg == "unit":
            success = run_unit_tests()
        elif arg == "integration":
            success = run_integration_tests()
        elif arg == "quick":
            # Quick test: solo tests críticos
            print_info("Ejecutando tests críticos...")
            success = run_specific_test_class("TestRolesConstants")
            success = success and run_specific_test_class("TestPermissions")
        else:
            print_error(f"Argumento desconocido: {arg}")
            print_info("Argumentos válidos: all, unit, integration, quick")
            sys.exit(1)
        
        sys.exit(0 if success else 1)
    else:
        # Modo interactivo
        interactive_menu()


if __name__ == "__main__":
    main()

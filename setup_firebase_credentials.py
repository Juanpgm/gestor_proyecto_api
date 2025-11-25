"""
🔧 CONFIGURACIÓN RÁPIDA DE CREDENCIALES FIREBASE
=================================================

Este script ayuda a configurar las credenciales necesarias para generar
custom tokens en Firebase Admin SDK.

Opciones:
1. Configurar Service Account Key (recomendado para producción)
2. Usar Application Default Credentials (para desarrollo local)
3. Ver estado actual de credenciales
"""

import os
import sys
import json
import base64
from pathlib import Path

class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    BOLD = '\033[1m'
    END = '\033[0m'


def print_header():
    print(f"\n{Colors.BOLD}{Colors.CYAN}")
    print("╔═══════════════════════════════════════════════════════════════════╗")
    print("║   🔧 CONFIGURACIÓN DE CREDENCIALES FIREBASE                      ║")
    print("║   Para generación de Custom Tokens                               ║")
    print("╚═══════════════════════════════════════════════════════════════════╝")
    print(Colors.END)


def print_success(msg):
    print(f"{Colors.GREEN}✅ {msg}{Colors.END}")


def print_error(msg):
    print(f"{Colors.RED}❌ {msg}{Colors.END}")


def print_warning(msg):
    print(f"{Colors.YELLOW}⚠️  {msg}{Colors.END}")


def print_info(msg):
    print(f"{Colors.BLUE}ℹ️  {msg}{Colors.END}")


def check_current_credentials():
    """Verificar estado actual de credenciales"""
    print(f"\n{Colors.BOLD}ESTADO ACTUAL DE CREDENCIALES:{Colors.END}\n")
    
    status = []
    
    # 1. Service Account Key en variable de entorno
    if os.getenv("FIREBASE_SERVICE_ACCOUNT_KEY"):
        print_success("FIREBASE_SERVICE_ACCOUNT_KEY configurada")
        status.append("service_account_env")
    else:
        print_warning("FIREBASE_SERVICE_ACCOUNT_KEY no configurada")
    
    # 2. Google Application Credentials
    gac_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    if gac_path and os.path.exists(gac_path):
        print_success(f"GOOGLE_APPLICATION_CREDENTIALS: {gac_path}")
        status.append("gac_file")
    else:
        print_warning("GOOGLE_APPLICATION_CREDENTIALS no configurada")
    
    # 3. WIF Credentials
    if os.getenv("GOOGLE_APPLICATION_CREDENTIALS_JSON"):
        print_success("GOOGLE_APPLICATION_CREDENTIALS_JSON configurada (WIF)")
        status.append("wif")
    else:
        print_warning("GOOGLE_APPLICATION_CREDENTIALS_JSON no configurada")
    
    # 4. Application Default Credentials
    try:
        import google.auth
        credentials, project = google.auth.default()
        print_success(f"Application Default Credentials disponibles (Project: {project})")
        status.append("adc")
    except Exception as e:
        print_warning(f"Application Default Credentials no disponibles: {e}")
    
    print()
    if status:
        print_success(f"Métodos de autenticación disponibles: {', '.join(status)}")
        print_info("Firebase puede generar custom tokens ✅")
    else:
        print_error("No hay credenciales configuradas")
        print_warning("Firebase NO puede generar custom tokens ❌")
    
    return len(status) > 0


def setup_service_account():
    """Configurar Service Account Key"""
    print(f"\n{Colors.BOLD}CONFIGURAR SERVICE ACCOUNT KEY{Colors.END}\n")
    
    print_info("Necesitas el archivo JSON del Service Account de Firebase")
    print_info("Descárgalo desde: Firebase Console > Project Settings > Service Accounts")
    print()
    
    print(f"{Colors.BOLD}Opciones:{Colors.END}")
    print("1. Tengo el archivo JSON")
    print("2. Tengo el contenido en base64")
    print("3. Volver al menú principal")
    
    choice = input(f"\n{Colors.CYAN}Selecciona una opción (1-3): {Colors.END}").strip()
    
    if choice == "1":
        setup_from_json_file()
    elif choice == "2":
        setup_from_base64()
    elif choice == "3":
        return
    else:
        print_error("Opción inválida")


def setup_from_json_file():
    """Configurar desde archivo JSON"""
    print(f"\n{Colors.BOLD}CONFIGURAR DESDE ARCHIVO JSON{Colors.END}\n")
    
    file_path = input(f"{Colors.CYAN}Ruta al archivo JSON: {Colors.END}").strip()
    
    if not os.path.exists(file_path):
        print_error(f"Archivo no encontrado: {file_path}")
        return
    
    try:
        with open(file_path, 'r') as f:
            service_account = json.load(f)
        
        # Validar contenido
        required_keys = ['type', 'project_id', 'private_key_id', 'private_key', 'client_email']
        missing_keys = [k for k in required_keys if k not in service_account]
        
        if missing_keys:
            print_error(f"Archivo JSON inválido. Faltan campos: {', '.join(missing_keys)}")
            return
        
        print_success(f"Archivo válido - Project: {service_account['project_id']}")
        print_success(f"Service Account: {service_account['client_email']}")
        
        # Convertir a base64
        json_str = json.dumps(service_account)
        base64_encoded = base64.b64encode(json_str.encode()).decode()
        
        # Opción 1: Copiar al portapapeles (si pyperclip está disponible)
        try:
            import pyperclip
            pyperclip.copy(base64_encoded)
            print_success("Base64 copiado al portapapeles!")
        except ImportError:
            pass
        
        # Opción 2: Guardar en archivo .env
        print(f"\n{Colors.BOLD}¿Cómo quieres usar esta credencial?{Colors.END}")
        print("1. Configurar en variable de entorno (Railway, producción)")
        print("2. Guardar en archivo .env local")
        print("3. Solo mostrar el valor base64")
        
        option = input(f"\n{Colors.CYAN}Selecciona una opción (1-3): {Colors.END}").strip()
        
        if option == "1":
            print(f"\n{Colors.BOLD}CONFIGURACIÓN EN RAILWAY/PRODUCCIÓN:{Colors.END}")
            print(f"\n{Colors.YELLOW}Variable:{Colors.END} FIREBASE_SERVICE_ACCOUNT_KEY")
            print(f"{Colors.YELLOW}Valor:{Colors.END}")
            print(f"{base64_encoded[:100]}...")
            print(f"\n{Colors.GREEN}Copia el valor completo y agrégalo en Railway Dashboard{Colors.END}")
            
        elif option == "2":
            env_file = Path(".env")
            
            # Leer .env existente o crear nuevo
            env_content = ""
            if env_file.exists():
                with open(env_file, 'r') as f:
                    env_content = f.read()
            
            # Agregar o actualizar la variable
            if "FIREBASE_SERVICE_ACCOUNT_KEY=" in env_content:
                print_warning(".env ya tiene FIREBASE_SERVICE_ACCOUNT_KEY, será actualizada")
                lines = env_content.split('\n')
                new_lines = []
                for line in lines:
                    if line.startswith("FIREBASE_SERVICE_ACCOUNT_KEY="):
                        new_lines.append(f"FIREBASE_SERVICE_ACCOUNT_KEY={base64_encoded}")
                    else:
                        new_lines.append(line)
                env_content = '\n'.join(new_lines)
            else:
                env_content += f"\nFIREBASE_SERVICE_ACCOUNT_KEY={base64_encoded}\n"
            
            with open(env_file, 'w') as f:
                f.write(env_content)
            
            print_success(f"Credencial guardada en {env_file}")
            print_warning("Recuerda cargar las variables: source .env (Linux/Mac) o lee el archivo en PowerShell")
            
        elif option == "3":
            print(f"\n{Colors.BOLD}BASE64 ENCODED:{Colors.END}")
            print(base64_encoded)
            print(f"\n{Colors.INFO}Usa este valor para FIREBASE_SERVICE_ACCOUNT_KEY{Colors.END}")
        
        print_success("\n✅ Configuración completada!")
        
    except json.JSONDecodeError:
        print_error("El archivo no es un JSON válido")
    except Exception as e:
        print_error(f"Error: {e}")


def setup_from_base64():
    """Configurar desde base64"""
    print(f"\n{Colors.BOLD}CONFIGURAR DESDE BASE64{Colors.END}\n")
    print_info("Pega el valor base64 del Service Account Key:")
    
    base64_value = input(f"{Colors.CYAN}Base64: {Colors.END}").strip()
    
    try:
        # Decodificar y validar
        decoded = base64.b64decode(base64_value).decode('utf-8')
        service_account = json.loads(decoded)
        
        print_success(f"Base64 válido - Project: {service_account.get('project_id')}")
        
        # Guardar en .env
        env_file = Path(".env")
        with open(env_file, 'a') as f:
            f.write(f"\nFIREBASE_SERVICE_ACCOUNT_KEY={base64_value}\n")
        
        print_success(f"Credencial guardada en {env_file}")
        
    except Exception as e:
        print_error(f"Base64 inválido: {e}")


def setup_adc():
    """Configurar Application Default Credentials"""
    print(f"\n{Colors.BOLD}CONFIGURAR APPLICATION DEFAULT CREDENTIALS{Colors.END}\n")
    
    print_info("Este método es ideal para desarrollo local")
    print_info("Requiere Google Cloud SDK instalado")
    print()
    
    print(f"{Colors.BOLD}Pasos:{Colors.END}")
    print("1. Instala Google Cloud SDK: https://cloud.google.com/sdk/docs/install")
    print("2. Ejecuta: gcloud auth application-default login")
    print("3. Sigue las instrucciones en el navegador")
    print()
    
    print_warning("Nota: Este método solo funciona para desarrollo local")
    print_warning("Para producción, usa Service Account Key")
    
    input(f"\n{Colors.CYAN}Presiona Enter cuando hayas ejecutado el comando...{Colors.END}")
    
    # Verificar si funcionó
    try:
        import google.auth
        credentials, project = google.auth.default()
        print_success(f"✅ ADC configurado correctamente - Project: {project}")
    except Exception as e:
        print_error(f"ADC no configurado: {e}")


def show_instructions():
    """Mostrar instrucciones completas"""
    print(f"\n{Colors.BOLD}{Colors.CYAN}GUÍA COMPLETA DE CONFIGURACIÓN{Colors.END}\n")
    
    print(f"{Colors.BOLD}🔑 Obtener Service Account Key de Firebase:{Colors.END}\n")
    print("1. Ve a Firebase Console: https://console.firebase.google.com/")
    print("2. Selecciona tu proyecto")
    print("3. Ve a Project Settings (⚙️) > Service accounts")
    print("4. Click en 'Generate new private key'")
    print("5. Descarga el archivo JSON")
    
    print(f"\n{Colors.BOLD}🛠️ Configurar para Desarrollo Local:{Colors.END}\n")
    print("Opción A - Service Account:")
    print("  1. Ejecuta este script y selecciona opción 1")
    print("  2. Proporciona la ruta al archivo JSON")
    print("  3. Guarda en .env local")
    
    print("\nOpción B - Application Default Credentials:")
    print("  1. Instala Google Cloud SDK")
    print("  2. Ejecuta: gcloud auth application-default login")
    print("  3. Autentica con tu cuenta de Google")
    
    print(f"\n{Colors.BOLD}🚀 Configurar para Producción (Railway):{Colors.END}\n")
    print("1. Ejecuta este script y selecciona opción 1")
    print("2. Proporciona la ruta al archivo JSON")
    print("3. Copia el valor base64 generado")
    print("4. Ve a Railway Dashboard > Variables")
    print("5. Agrega: FIREBASE_SERVICE_ACCOUNT_KEY = <valor_base64>")
    
    print(f"\n{Colors.BOLD}🧪 Verificar Configuración:{Colors.END}\n")
    print("Ejecuta: python test_jwt_token_generation.py")
    print("Debe mostrar: '✅ Custom token generated successfully'")
    
    input(f"\n{Colors.CYAN}Presiona Enter para volver al menú...{Colors.END}")


def main():
    print_header()
    
    while True:
        print(f"\n{Colors.BOLD}MENÚ PRINCIPAL:{Colors.END}\n")
        print("1. Ver estado actual de credenciales")
        print("2. Configurar Service Account Key")
        print("3. Configurar Application Default Credentials (desarrollo local)")
        print("4. Ver instrucciones completas")
        print("5. Salir")
        
        choice = input(f"\n{Colors.CYAN}Selecciona una opción (1-5): {Colors.END}").strip()
        
        if choice == "1":
            check_current_credentials()
        elif choice == "2":
            setup_service_account()
        elif choice == "3":
            setup_adc()
        elif choice == "4":
            show_instructions()
        elif choice == "5":
            print(f"\n{Colors.GREEN}¡Hasta luego!{Colors.END}\n")
            break
        else:
            print_error("Opción inválida")


if __name__ == "__main__":
    main()

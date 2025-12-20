#!/usr/bin/env python3
"""
Script para configurar y probar el workflow de automatización de empréstito
Usa GitHub CLI y Firebase Admin SDK
"""

import subprocess
import sys
import json
from pathlib import Path

def run_command(cmd, capture=True):
    """Ejecutar comando y retornar resultado"""
    try:
        if capture:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, encoding='utf-8')
            return result.returncode, result.stdout.strip(), result.stderr.strip()
        else:
            result = subprocess.run(cmd, shell=True)
            return result.returncode, "", ""
    except Exception as e:
        return 1, "", str(e)

def check_gh_cli():
    """Verificar si GitHub CLI está instalado"""
    code, stdout, stderr = run_command("gh --version")
    if code == 0:
        print(f"✅ GitHub CLI instalado: {stdout.split()[2]}")
        return True
    else:
        print("❌ GitHub CLI no encontrado")
        print("💡 Instala con: winget install --id GitHub.cli")
        return False

def check_gh_auth():
    """Verificar autenticación de GitHub"""
    code, stdout, stderr = run_command("gh auth status")
    if code == 0:
        print("✅ Autenticado en GitHub")
        return True
    else:
        print("❌ No autenticado en GitHub")
        print("💡 Ejecuta: gh auth login")
        return False

def list_secrets():
    """Listar secrets configurados"""
    print("\n📋 Secrets configurados:")
    code, stdout, stderr = run_command("gh secret list")
    if code == 0:
        if stdout:
            print(stdout)
        else:
            print("  (ninguno)")
        return True
    else:
        print(f"❌ Error listando secrets: {stderr}")
        return False

def set_secret(name, value):
    """Configurar un secret"""
    cmd = f'gh secret set {name} --body "{value}"'
    code, stdout, stderr = run_command(cmd)
    if code == 0:
        print(f"✅ Secret {name} configurado")
        return True
    else:
        print(f"❌ Error configurando {name}: {stderr}")
        return False

def get_firebase_uid():
    """Obtener UID de Firebase mediante el service account"""
    print("\n🔍 Intentando obtener UID de Firebase...")
    
    try:
        import firebase_admin
        from firebase_admin import credentials, auth
        
        # Buscar service account
        possible_paths = [
            Path("serviceAccountKey.json"),
            Path("firebase-key.json"),
            Path("credentials.json")
        ]
        
        service_account_path = None
        for path in possible_paths:
            if path.exists():
                service_account_path = path
                break
        
        if not service_account_path:
            print("⚠️ No se encontró archivo de service account")
            print("💡 Busca archivos: serviceAccountKey.json, firebase-key.json")
            return None
        
        # Inicializar Firebase
        try:
            firebase_admin.get_app()
        except ValueError:
            cred = credentials.Certificate(str(service_account_path))
            firebase_admin.initialize_app(cred)
        
        # Listar primeros usuarios
        print("\n👥 Usuarios disponibles en Firebase:")
        page = auth.list_users()
        
        if not page.users:
            print("  (no hay usuarios)")
            print("\n💡 Crea un usuario de automatización:")
            create = input("¿Deseas crear un usuario de automatización? (s/n): ")
            if create.lower() == 's':
                email = input("Email para el usuario: ")
                password = input("Password (mínimo 6 caracteres): ")
                
                user = auth.create_user(
                    email=email,
                    password=password,
                    display_name="Automation Bot"
                )
                print(f"\n✅ Usuario creado exitosamente!")
                print(f"📧 Email: {user.email}")
                print(f"🔑 UID: {user.uid}")
                return user.uid
            return None
        
        for idx, user in enumerate(page.users[:5], 1):
            print(f"  {idx}. {user.email or 'Sin email'} - UID: {user.uid}")
        
        selection = input("\nSelecciona el número del usuario para automatización (o Enter para salir): ")
        if selection.isdigit():
            idx = int(selection) - 1
            if 0 <= idx < len(page.users):
                selected_user = page.users[idx]
                print(f"\n✅ Usuario seleccionado: {selected_user.email}")
                print(f"🔑 UID: {selected_user.uid}")
                return selected_user.uid
        
        return None
        
    except ImportError:
        print("⚠️ Firebase Admin SDK no instalado")
        print("💡 Instala con: pip install firebase-admin")
        return None
    except Exception as e:
        print(f"❌ Error accediendo a Firebase: {e}")
        return None

def check_workflow():
    """Verificar que el workflow existe"""
    print("\n🔍 Verificando workflows...")
    code, stdout, stderr = run_command("gh workflow list")
    if code == 0:
        if "Empréstito" in stdout or "emprestito-automation" in stdout:
            print("✅ Workflow de empréstito encontrado")
            print(stdout)
            return True
        else:
            print("⚠️ Workflow no encontrado en GitHub")
            print("💡 Asegúrate de hacer commit y push del archivo:")
            print("   .github/workflows/emprestito-automation.yml")
            return False
    else:
        print(f"❌ Error verificando workflows: {stderr}")
        return False

def run_workflow():
    """Ejecutar workflow manualmente"""
    print("\n🚀 Ejecutando workflow...")
    code, stdout, stderr = run_command("gh workflow run emprestito-automation.yml")
    if code == 0:
        print("✅ Workflow iniciado")
        print("\n💡 Ver progreso con:")
        print("   gh run list --workflow=emprestito-automation.yml")
        print("   gh run view --log")
        return True
    else:
        print(f"❌ Error ejecutando workflow: {stderr}")
        return False

def main():
    print("=" * 60)
    print("🔧 Configuración del Workflow de Automatización")
    print("=" * 60)
    
    # Verificar prerrequisitos
    if not check_gh_cli():
        return
    
    if not check_gh_auth():
        print("\n💡 Primero autentícate con: gh auth login")
        return
    
    # Listar secrets actuales
    list_secrets()
    
    # Menú interactivo
    while True:
        print("\n" + "=" * 60)
        print("📋 Menú de Configuración")
        print("=" * 60)
        print("1. Configurar API_BASE_URL")
        print("2. Configurar FIREBASE_AUTOMATION_UID (detectar automáticamente)")
        print("3. Configurar FIREBASE_AUTOMATION_UID (manualmente)")
        print("4. Ver secrets configurados")
        print("5. Verificar workflow en GitHub")
        print("6. Ejecutar workflow manualmente")
        print("7. Ver últimos runs")
        print("8. Salir")
        
        opcion = input("\nSelecciona una opción (1-8): ").strip()
        
        if opcion == "1":
            url = input("\n📝 Ingresa la URL de tu API (ej: https://tu-api.railway.app): ").strip()
            if url:
                # Remover trailing slash si existe
                url = url.rstrip('/')
                set_secret("API_BASE_URL", url)
        
        elif opcion == "2":
            uid = get_firebase_uid()
            if uid:
                set_secret("FIREBASE_AUTOMATION_UID", uid)
        
        elif opcion == "3":
            uid = input("\n📝 Ingresa el UID de Firebase: ").strip()
            if uid:
                set_secret("FIREBASE_AUTOMATION_UID", uid)
        
        elif opcion == "4":
            list_secrets()
        
        elif opcion == "5":
            check_workflow()
        
        elif opcion == "6":
            if check_workflow():
                run_workflow()
        
        elif opcion == "7":
            print("\n📊 Últimos runs:")
            run_command("gh run list --workflow=emprestito-automation.yml --limit 5", capture=False)
        
        elif opcion == "8":
            print("\n👋 ¡Hasta luego!")
            break
        
        else:
            print("❌ Opción inválida")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 Configuración cancelada por el usuario")
    except Exception as e:
        print(f"\n❌ Error inesperado: {e}")
        sys.exit(1)

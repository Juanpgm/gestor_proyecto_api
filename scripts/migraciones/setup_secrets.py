#!/usr/bin/env python3
"""Script rápido para obtener UID de Firebase y configurar secrets"""

import subprocess
import sys
import os
from pathlib import Path

DEFAULT_API_URL_FILE = Path(__file__).resolve().parent / "config" / "api_base_url.txt"


def get_default_api_url():
    """Obtener URL base por defecto desde variable de entorno o archivo central."""
    env_url = os.getenv("API_BASE_URL", "").strip().rstrip('/')
    if env_url:
        return env_url

    if DEFAULT_API_URL_FILE.exists():
        file_url = DEFAULT_API_URL_FILE.read_text(encoding='utf-8').strip().rstrip('/')
        if file_url:
            return file_url

    return "https://tu-api.railway.app"

def run_cmd(cmd):
    """Ejecutar comando"""
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, encoding='utf-8')
    return result.returncode, result.stdout.strip(), result.stderr.strip()

def get_firebase_uid():
    """Obtener UID de Firebase"""
    try:
        import firebase_admin
        from firebase_admin import credentials, auth
        
        # Inicializar Firebase
        try:
            firebase_admin.get_app()
        except ValueError:
            from database.firebase_config import initialize_firebase_app
            initialize_firebase_app()
        
        # Listar usuarios
        print("\n👥 Usuarios en Firebase:")
        page = auth.list_users()
        
        if not page.users:
            print("⚠️ No hay usuarios. Creando usuario de automatización...")
            user = auth.create_user(
                email='automation@emprestito.local',
                password='Automation2025!',
                display_name='Empréstito Automation Bot'
            )
            print(f"✅ Usuario creado: {user.email}")
            print(f"🔑 UID: {user.uid}")
            return user.uid
        
        # Seleccionar primer usuario admin o crear uno
        for user in page.users:
            if user.email:
                print(f"✅ Usando usuario: {user.email}")
                print(f"🔑 UID: {user.uid}")
                return user.uid
        
        # Si no hay usuarios con email, crear uno
        user = auth.create_user(
            email='automation@emprestito.local',
            password='Automation2025!',
            display_name='Empréstito Automation Bot'
        )
        print(f"✅ Usuario creado: {user.email}")
        print(f"🔑 UID: {user.uid}")
        return user.uid
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return None

# 1. Obtener UID
print("🔍 Obteniendo UID de Firebase...")
uid = get_firebase_uid()

if not uid:
    print("\n❌ No se pudo obtener el UID")
    print("💡 Ingresa manualmente el UID de un usuario de Firebase:")
    uid = input("UID: ").strip()
    if not uid:
        sys.exit(1)

# 2. Configurar API_BASE_URL
default_api_url = get_default_api_url()
print("\n📝 Configurando API_BASE_URL...")
print(f"💡 Ingresa la URL de tu API (default: {default_api_url})")
api_url = input("URL: ").strip()

if not api_url:
    print("⚠️ Usando URL por defecto centralizada...")
    api_url = default_api_url

api_url = api_url.rstrip('/')

# 3. Configurar secrets
print("\n🔐 Configurando secrets en GitHub...")

# Configurar API_BASE_URL
print(f"  - API_BASE_URL = {api_url}")
code, out, err = run_cmd(f'gh secret set API_BASE_URL --body "{api_url}"')
if code == 0:
    print("    ✅ Configurado")
else:
    print(f"    ❌ Error: {err}")

# Configurar FIREBASE_AUTOMATION_UID
print(f"  - FIREBASE_AUTOMATION_UID = {uid}")
code, out, err = run_cmd(f'gh secret set FIREBASE_AUTOMATION_UID --body "{uid}"')
if code == 0:
    print("    ✅ Configurado")
else:
    print(f"    ❌ Error: {err}")

# 4. Listar secrets
print("\n📋 Secrets configurados:")
code, out, err = run_cmd("gh secret list")
if code == 0:
    print(out)

print("\n✅ Configuración completada!")
print("\n💡 Próximos pasos:")
print("1. Haz commit y push del workflow:")
print("   git add .github/workflows/emprestito-automation.yml")
print("   git commit -m 'feat: workflow de automatización'")
print("   git push")
print("\n2. Ejecuta el workflow:")
print("   gh workflow run emprestito-automation.yml")
print("\n3. Ver el progreso:")
print("   gh run list --workflow=emprestito-automation.yml")

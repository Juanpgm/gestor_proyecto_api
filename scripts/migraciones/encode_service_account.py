#!/usr/bin/env python3
"""
Script para codificar service account JSON en base64
"""
import base64
import sys

print("🔧 Codificador de Service Account JSON")
print("Pega el contenido completo de tu archivo JSON de service account:")
print("(Presiona Ctrl+D o Ctrl+Z+Enter cuando termines)")
print()

try:
    # Leer todo el input
    json_content = sys.stdin.read().strip()

    if not json_content:
        print("❌ No se recibió contenido JSON")
        sys.exit(1)

    # Codificar en base64
    encoded = base64.b64encode(json_content.encode('utf-8')).decode('utf-8')

    print("\n✅ JSON codificado en base64:")
    print("=" * 50)
    print(encoded)
    print("=" * 50)
    print("\n📋 Copia este valor para FIREBASE_SERVICE_ACCOUNT_KEY")

except Exception as e:
    print(f"❌ Error: {e}")
    sys.exit(1)
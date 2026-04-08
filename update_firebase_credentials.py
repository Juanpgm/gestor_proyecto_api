"""
Codificar service account en base64 y actualizar .env
"""
import json
import base64

# Leer el archivo JSON
with open('credentials/calitrack-secret.json', 'r') as f:
    creds_json = f.read()

# Codificar en base64
creds_b64 = base64.b64encode(creds_json.encode('utf-8')).decode('utf-8')

print(f"✅ Credencial codificada: {len(creds_b64)} caracteres")
print(f"\n📋 Nueva variable de entorno:")
print(f"FIREBASE_SERVICE_ACCOUNT_KEY={creds_b64}")

# Leer .env actual
try:
    with open('.env', 'r', encoding='utf-8') as f:
        env_lines = f.readlines()
except FileNotFoundError:
    env_lines = []

# Actualizar o agregar FIREBASE_SERVICE_ACCOUNT_KEY
updated = False
new_lines = []
for line in env_lines:
    if line.startswith('FIREBASE_SERVICE_ACCOUNT_KEY='):
        new_lines.append(f'FIREBASE_SERVICE_ACCOUNT_KEY={creds_b64}\n')
        updated = True
        print(f"\n✏️  Actualizando línea existente en .env")
    else:
        new_lines.append(line)

if not updated:
    new_lines.append(f'\nFIREBASE_SERVICE_ACCOUNT_KEY={creds_b64}\n')
    print(f"\n➕ Agregando nueva línea a .env")

# Guardar .env actualizado
with open('.env', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

print(f"\n💾 Archivo .env actualizado correctamente")
print(f"\n🔥 Ahora reinicia el servidor uvicorn para aplicar los cambios")

"""
Script para verificar configuración de Google OAuth
"""
import os
from dotenv import load_dotenv

def verify_google_oauth_config():
    """Verificar configuración de Google OAuth"""
    load_dotenv()
    
    client_id = os.getenv('GOOGLE_CLIENT_ID')
    client_secret = os.getenv('GOOGLE_CLIENT_SECRET')
    
    print("🔍 VERIFICACIÓN DE GOOGLE OAUTH")
    print("=" * 50)
    
    if not client_id or client_id == 'desarrollo_google_client_id':
        print("❌ GOOGLE_CLIENT_ID no configurado o usando valor de desarrollo")
        print("   Sigue las instrucciones en GOOGLE_OAUTH_SETUP.md")
    else:
        print(f"✅ GOOGLE_CLIENT_ID: {client_id[:20]}...")
        
        # Verificar formato de Client ID
        if '.apps.googleusercontent.com' in client_id:
            print("✅ Formato de Client ID válido")
        else:
            print("⚠️  Formato de Client ID podría ser incorrecto")
    
    if not client_secret or client_secret == 'desarrollo_google_client_secret':
        print("❌ GOOGLE_CLIENT_SECRET no configurado o usando valor de desarrollo")
        print("   Sigue las instrucciones en GOOGLE_OAUTH_SETUP.md")
    else:
        print(f"✅ GOOGLE_CLIENT_SECRET: {client_secret[:10]}...")
        
        # Verificar formato de Client Secret
        if client_secret.startswith('GOCSPX-'):
            print("✅ Formato de Client Secret válido")
        else:
            print("⚠️  Formato de Client Secret podría ser incorrecto")
    
    print("\n📋 RESUMEN:")
    if (client_id and client_id != 'desarrollo_google_client_id' and 
        client_secret and client_secret != 'desarrollo_google_client_secret'):
        print("✅ Configuración de Google OAuth parece correcta")
        print("   Puedes probar los endpoints de autenticación con Google")
    else:
        print("⚠️  Configuración de Google OAuth incompleta")
        print("   Los endpoints de Google OAuth no funcionarán hasta configurar correctamente")
        print("   Consulta: GOOGLE_OAUTH_SETUP.md para instrucciones detalladas")

if __name__ == "__main__":
    verify_google_oauth_config()
"""
Script para diagnosticar y reparar Firebase Service Account Key
"""
import os
import json
import base64
import sys
from dotenv import load_dotenv

load_dotenv()

# Agregar ruta para imports
sys.path.insert(0, os.path.dirname(__file__))

def diagnose_key():
    """Diagnosticar problemas con la key"""
    key_b64 = os.getenv("FIREBASE_SERVICE_ACCOUNT_KEY")
    
    if not key_b64:
        print("❌ FIREBASE_SERVICE_ACCOUNT_KEY no encontrada en .env")
        return
    
    print(f"✅ Key encontrada: {len(key_b64)} caracteres")
    
    try:
        # Decodificar
        decoded = base64.b64decode(key_b64).decode('utf-8')
        print(f"✅ Decodificación exitosa: {len(decoded)} caracteres")
        
        # Parsear JSON
        creds = json.loads(decoded)
        print(f"✅ JSON válido")
        print(f"   Project: {creds.get('project_id')}")
        print(f"   Email: {creds.get('client_email')}")
        
        # Verificar private_key
        private_key = creds.get('private_key', '')
        print(f"\n🔍 Analizando private_key...")
        print(f"   Longitud: {len(private_key)} caracteres")
        print(f"   Inicia con: {private_key[:30]}")
        print(f"   Termina con: {private_key[-30:]}")
        
        # Detectar problema común
        if '\\n' in private_key and '\n' not in private_key:
            print("\n⚠️  PROBLEMA DETECTADO: private_key tiene \\\\n escapados")
            print("   La key tiene backslash-n literales en lugar de saltos de línea")
            
            # Reparar
            fixed_key = private_key.replace('\\n', '\n')
            creds['private_key'] = fixed_key
            
            # Recodificar
            fixed_json = json.dumps(creds)
            fixed_b64 = base64.b64encode(fixed_json.encode('utf-8')).decode('utf-8')
            
            print(f"\n✅ Key reparada!")
            print(f"   Nueva longitud: {len(fixed_b64)} caracteres")
            print(f"\n📋 Copia esta nueva key a tu .env:")
            print(f"FIREBASE_SERVICE_ACCOUNT_KEY={fixed_b64}")
            
            # Guardar en archivo
            with open('firebase_key_fixed.txt', 'w') as f:
                f.write(f"FIREBASE_SERVICE_ACCOUNT_KEY={fixed_b64}")
            print(f"\n💾 También guardada en: firebase_key_fixed.txt")
            
        elif '\n' in private_key:
            print("\n✅ private_key parece correcta (tiene saltos de línea reales)")
            
            # Verificar formato
            if not private_key.startswith('-----BEGIN'):
                print("⚠️  No inicia con -----BEGIN PRIVATE KEY-----")
            if not private_key.strip().endswith('-----'):
                print("⚠️  No termina con -----END PRIVATE KEY-----")
            
            # Intentar conectar con Firebase
            print("\n🔥 Intentando conectar a Firebase...")
            try:
                import firebase_admin
                from firebase_admin import credentials, firestore
                
                # Cerrar apps existentes
                try:
                    app = firebase_admin.get_app()
                    firebase_admin.delete_app(app)
                    print("   App existente eliminada")
                except:
                    pass
                
                # Inicializar con las credenciales
                cred = credentials.Certificate(creds)
                app = firebase_admin.initialize_app(cred, {
                    'projectId': creds.get('project_id')
                })
                print(f"   ✅ Firebase inicializado!")
                
                # Probar Firestore
                db = firestore.client()
                print(f"   ✅ Firestore client obtenido")
                
                # Intentar hacer una consulta
                collection_ref = db.collection('unidades_proyecto')
                docs = collection_ref.limit(1).stream()
                count = sum(1 for _ in docs)
                print(f"   ✅ Query exitoso! Documentos encontrados: {count}")
                
                print("\n✅ CONEXIÓN EXITOSA - Las credenciales son válidas!")
                
            except Exception as e:
                print(f"   ❌ Error conectando: {type(e).__name__}: {str(e)}")
                print(f"\n⚠️  Las credenciales parecen inválidas o han sido revocadas")
                print(f"   Solución: Regenera las credenciales en Firebase Console")
        
    except base64.binascii.Error as e:
        print(f"❌ Error decodificando base64: {e}")
    except json.JSONDecodeError as e:
        print(f"❌ Error parseando JSON: {e}")
    except Exception as e:
        print(f"❌ Error inesperado: {e}")

if __name__ == "__main__":
    print("="*60)
    print("🔥 DIAGNÓSTICO DE FIREBASE SERVICE ACCOUNT KEY")
    print("="*60)
    diagnose_key()

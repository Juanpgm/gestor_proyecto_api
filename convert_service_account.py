
import json
import base64

def convert_service_account_to_base64():
    """
    Convertir Service Account JSON a base64 para Railway
    """
    print("🔧 CONVERTIDOR SERVICE ACCOUNT A BASE64")
    print("=" * 50)
    
    # Solicitar contenido del archivo JSON
    print("Pegue el contenido completo del archivo service account JSON:")
    print("(Pegue y presione Enter dos veces cuando termine)")
    
    lines = []
    while True:
        try:
            line = input()
            if not line:
                break
            lines.append(line)
        except EOFError:
            break
    
    json_content = "\n".join(lines)
    
    try:
        # Validar que es JSON válido
        json_data = json.loads(json_content)
        
        # Verificar campos requeridos
        required_fields = ['type', 'project_id', 'private_key_id', 'private_key', 'client_email']
        missing_fields = [field for field in required_fields if field not in json_data]
        
        if missing_fields:
            print(f"❌ Error: Campos faltantes: {missing_fields}")
            return
        
        # Convertir a base64
        base64_encoded = base64.b64encode(json_content.encode('utf-8')).decode('utf-8')
        
        print("\n✅ CONVERSIÓN EXITOSA")
        print("=" * 50)
        print("📋 Información del Service Account:")
        print(f"  • Project ID: {json_data.get('project_id')}")
        print(f"  • Client Email: {json_data.get('client_email')}")
        print(f"  • Type: {json_data.get('type')}")
        
        print("\n🔑 VALOR PARA RAILWAY (copie esto):")
        print("-" * 50)
        print(base64_encoded)
        print("-" * 50)
        
        print("\n📝 INSTRUCCIONES:")
        print("1. Copie el valor base64 de arriba")
        print("2. Vaya a Railway Dashboard > Variables")
        print("3. Agregue variable: FIREBASE_SERVICE_ACCOUNT_KEY")
        print("4. Pegue el valor base64")
        print("5. Guarde y redeploy")
        
    except json.JSONDecodeError as e:
        print(f"❌ Error: JSON inválido - {e}")
    except Exception as e:
        print(f"❌ Error inesperado: {e}")

if __name__ == "__main__":
    convert_service_account_to_base64()

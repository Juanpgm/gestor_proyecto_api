"""
Verificar la estructura de nombre_up en Firebase
"""
import asyncio
from google.cloud import firestore

async def check_nombre_up_structure():
    """Verificar cómo está almacenado nombre_up en Firebase"""
    
    db = firestore.Client()
    
    print("=" * 80)
    print("🔍 VERIFICANDO ESTRUCTURA DE nombre_up EN FIREBASE")
    print("=" * 80)
    
    # Verificar UNP-1000 (debe tener nombre_up)
    test_upids = ['UNP-1000', 'UNP-1002', 'UNP-792', 'UNP-1']
    
    for upid in test_upids:
        print(f"\n📍 Verificando {upid}:")
        print("-" * 80)
        
        try:
            docs = db.collection('unidades_proyecto').where('upid', '==', upid).limit(1).stream()
            doc_found = False
            
            for doc in docs:
                doc_found = True
                data = doc.to_dict()
                
                # Verificar diferentes ubicaciones de nombre_up
                nombre_up_locations = {
                    'data.nombre_up': data.get('nombre_up'),
                    'data.properties.nombre_up': data.get('properties', {}).get('nombre_up') if isinstance(data.get('properties'), dict) else None,
                    'data.record.properties.nombre_up': data.get('record', {}).get('properties', {}).get('nombre_up') if isinstance(data.get('record'), dict) else None,
                }
                
                print(f"✅ Documento encontrado: {doc.id}")
                print(f"\nUbicaciones de nombre_up:")
                for location, value in nombre_up_locations.items():
                    if value:
                        print(f"   ✅ {location}: {value[:50]}..." if len(str(value)) > 50 else f"   ✅ {location}: {value}")
                    else:
                        print(f"   ❌ {location}: None")
                
                # Mostrar las claves principales del documento
                print(f"\n📋 Claves principales del documento:")
                print(f"   {list(data.keys())}")
                
                # Si hay 'properties', mostrar sus claves
                if 'properties' in data and isinstance(data['properties'], dict):
                    print(f"\n📋 Claves en 'properties':")
                    print(f"   {list(data['properties'].keys())[:10]}")  # Primeras 10
                
                # Si hay 'record', mostrar su estructura
                if 'record' in data and isinstance(data['record'], dict):
                    print(f"\n📋 Claves en 'record':")
                    print(f"   {list(data['record'].keys())}")
                    if 'properties' in data['record']:
                        print(f"   'record.properties' keys: {list(data['record']['properties'].keys())[:10]}")
            
            if not doc_found:
                print(f"❌ No se encontró documento con upid={upid}")
        
        except Exception as e:
            print(f"❌ Error: {e}")
    
    print("\n" + "=" * 80)

if __name__ == "__main__":
    asyncio.run(check_nombre_up_structure())

"""
Verificar estructura de datos en Firebase para entender cómo extraer campos
"""
from google.cloud import firestore
import json

db = firestore.Client()

print("=" * 80)
print("🔍 VERIFICANDO ESTRUCTURA DE DATOS EN FIREBASE")
print("=" * 80)

# Verificar un registro viejo (UNP-1) y uno nuevo (UNP-1000)
test_upids = ['UNP-1', 'UNP-1000']

for upid in test_upids:
    print(f"\n{'='*80}")
    print(f"📍 Analizando {upid}")
    print('='*80)
    
    docs = db.collection('unidades_proyecto').where('upid', '==', upid).limit(1).stream()
    
    for doc in docs:
        data = doc.to_dict()
        
        print(f"\n📋 Claves en el nivel superior del documento:")
        print(f"   {list(data.keys())}\n")
        
        # Verificar cada clave
        for key in data.keys():
            value = data[key]
            if isinstance(value, dict):
                print(f"📦 '{key}' es un diccionario con claves:")
                print(f"   {list(value.keys())[:20]}")  # Primeras 20 claves
                
                # Si tiene 'properties' dentro, mostrar también
                if 'properties' in value and isinstance(value['properties'], dict):
                    print(f"   └─ '{key}.properties' tiene claves:")
                    print(f"      {list(value['properties'].keys())[:20]}")
            elif isinstance(value, str) and len(value) > 100:
                print(f"📄 '{key}': <string largo, {len(value)} chars>")
            else:
                print(f"📄 '{key}': {value}")
        
        # Buscar 'nombre_up' en todas las ubicaciones posibles
        print(f"\n🔍 Buscando 'nombre_up' en diferentes ubicaciones:")
        
        locations_to_check = [
            ('data.nombre_up', data.get('nombre_up')),
            ('data.properties.nombre_up', data.get('properties', {}).get('nombre_up') if isinstance(data.get('properties'), dict) else None),
            ('data.record.nombre_up', data.get('record', {}).get('nombre_up') if isinstance(data.get('record'), dict) else None),
            ('data.record.properties.nombre_up', data.get('record', {}).get('properties', {}).get('nombre_up') if isinstance(data.get('record'), dict) else None),
        ]
        
        for location, value in locations_to_check:
            if value:
                display_value = value[:80] + "..." if len(str(value)) > 80 else value
                print(f"   ✅ {location}: {display_value}")
            else:
                print(f"   ❌ {location}: None")
        
        # Si hay 'geometry', mostrar su estructura
        if 'geometry' in data:
            geom = data['geometry']
            if isinstance(geom, str):
                try:
                    geom_obj = json.loads(geom)
                    print(f"\n🗺️ Geometría (parseada desde string):")
                    print(f"   Type: {geom_obj.get('type')}")
                    if 'coordinates' in geom_obj:
                        coords = geom_obj['coordinates']
                        if isinstance(coords, list) and len(coords) > 0:
                            print(f"   Coordinates (primeros 2): {coords[:2]}")
                except:
                    print(f"\n🗺️ Geometría: <string no-JSON, {len(geom)} chars>")
            elif isinstance(geom, dict):
                print(f"\n🗺️ Geometría (dict):")
                print(f"   Type: {geom.get('type')}")
        
        break  # Solo procesar el primer documento encontrado

print("\n" + "=" * 80)
print("🏁 FIN DE VERIFICACIÓN")
print("=" * 80)

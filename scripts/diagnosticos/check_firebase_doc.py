from database.firebase_config import get_firestore_client
import json

db = get_firestore_client()

# Obtener un documento específico
doc = db.collection('unidades_proyecto').document('UNP-1000').get()

if doc.exists:
    data = doc.to_dict()
    
    print(f"📄 Documento UNP-1000:")
    print(f"Total keys: {len(data.keys())}")
    print(f"\n🔑 Todos los campos:")
    
    for key in sorted(data.keys()):
        value = data[key]
        
        # Mostrar valor truncado
        if isinstance(value, str) and len(value) > 100:
            print(f"  - {key}: {value[:100]}... (string largo)")
        elif isinstance(value, dict):
            print(f"  - {key}: (dict con {len(value)} keys)")
        elif isinstance(value, list):
            print(f"  - {key}: (list con {len(value)} items)")
        else:
            print(f"  - {key}: {value}")
    
    # Verificar campos específicos
    print(f"\n📊 Campos importantes:")
    print(f"  - upid: {data.get('upid')}")
    print(f"  - nombre_up: {data.get('nombre_up')}")
    print(f"  - centro_gestor: {data.get('centro_gestor')}")
    print(f"  - geometry_type: {data.get('geometry_type')}")
    print(f"  - has_geometry: {data.get('has_geometry')}")
    
    # Verificar si geometry es string o dict
    geometry = data.get('geometry')
    if geometry:
        if isinstance(geometry, str):
            print(f"\n🔍 Geometry (STRING):")
            print(f"  Primeros 200 chars: {geometry[:200]}")
            
            # Intentar parsear
            try:
                geom_obj = json.loads(geometry)
                print(f"  ✅ Parseable como JSON")
                print(f"  Type: {geom_obj.get('type')}")
            except:
                print(f"  ❌ NO parseable como JSON")
        else:
            print(f"\n🔍 Geometry (DICT):")
            print(f"  Type: {geometry.get('type')}")
else:
    print("❌ Documento no encontrado")

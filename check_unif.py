from database.firebase_config import get_firestore_client
import json

db = get_firestore_client()

# Verificar UNP-TEST-UNIF-1
doc = db.collection('unidades_proyecto').document('UNP-TEST-UNIF-1').get()

if doc.exists:
    data = doc.to_dict()
    geometry = data.get('geometry')
    if isinstance(geometry, str):
        geometry = json.loads(geometry)
    
    print("\n" + "="*80)
    print("📄 UNP-TEST-UNIF-1 (Proyecto Vial Norte - UNIFICADO)")
    print("="*80)
    print(f"nombre_up: {data.get('nombre_up')}")
    print(f"presupuesto_base: {data.get('presupuesto_base')} (esperado: 150000)")
    print(f"avance_obra: {data.get('avance_obra')}")
    print(f"descripcion: {data.get('descripcion')}")
    print(f"geometry.type: {geometry.get('type')}")
    
    if geometry.get('type') == 'GeometryCollection':
        geometries = geometry.get('geometries', [])
        print(f"geometries count: {len(geometries)} (esperado: 3)")
        for i, geom in enumerate(geometries):
            print(f"  [{i}] {geom.get('type')}")
    
    print("\n✅ RESULTADO:")
    if data.get('presupuesto_base') == 150000:
        print("  ✓ Presupuesto correctamente sumado (150000)")
    else:
        print(f"  ⚠️  Presupuesto incorrecto: {data.get('presupuesto_base')}")
    
    if geometry.get('type') == 'GeometryCollection' and len(geometry.get('geometries', [])) == 3:
        print("  ✓ Geometrías correctamente combinadas (3 geometries)")
    else:
        print(f"  ⚠️  Geometrías incorrectas")
    
    # Limpiar
    print("\n🗑️  Eliminando documento de prueba...")
    db.collection('unidades_proyecto').document('UNP-TEST-UNIF-1').delete()
    print("✅ Documento eliminado")
else:
    print("⚠️  UNP-TEST-UNIF-1 no existe")

"""
Verificación simple de unificación
"""

import asyncio
import json
from database.firebase_config import get_firestore_client

async def verificar():
    db = get_firestore_client()
    
    # Verificar los documentos UNP-1161 y UNP-1162 (creados en el test)
    upids = ['UNP-1161', 'UNP-1162']
    
    print("\n" + "="*80)
    print("VERIFICACIÓN DE UNIFICACIÓN")
    print("="*80 + "\n")
    
    for upid in upids:
        doc = db.collection('unidades_proyecto').document(upid).get()
        
        if doc.exists:
            data = doc.to_dict()
            print(f"📄 {upid}:")
            print(f"   - nombre_up: {data.get('nombre_up')}")
            print(f"   - presupuesto_base: {data.get('presupuesto_base')}")
            print(f"   - avance_obra: {data.get('avance_obra')}")
            print(f"   - descripcion: {data.get('descripcion', 'N/A')}")
            print(f"   - nombre_centro_gestor: {data.get('nombre_centro_gestor', 'N/A')}")
            
            geometry = data.get('geometry')
            if isinstance(geometry, str):
                geometry = json.loads(geometry)
            print(f"   - geometry.type: {geometry.get('type')}")
            
            if geometry.get('type') == 'GeometryCollection':
                geometries = geometry.get('geometries', [])
                print(f"   - geometries count: {len(geometries)}")
                for i, geom in enumerate(geometries):
                    print(f"     [{i}] {geom.get('type')}")
            
            print()
        else:
            print(f"⚠️  {upid} no existe en Firebase\n")
    
    print("="*80)
    print("✅ VALIDACIÓN:")
    print("="*80)
    print("\nSi 'Proyecto Vial Norte' tiene:")
    print("   ✓ presupuesto_base = 150000 (suma de 100000 + 50000)")
    print("   ✓ geometry.type = GeometryCollection")
    print("   ✓ geometries count = 3 (LineString + LineString + Point)")
    print("   ✓ descripcion = 'Descripción adicional'")
    print("   ✓ avance_obra = 45.5")
    print("\nEntonces la UNIFICACIÓN funcionó correctamente ✅")

if __name__ == "__main__":
    asyncio.run(verificar())

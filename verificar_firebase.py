"""
Script para verificar cómo quedaron los datos en Firebase
"""

import asyncio
import sys
from pathlib import Path

# Agregar el directorio raíz al path
sys.path.insert(0, str(Path(__file__).parent))

from database.firebase_config import get_firestore_client


async def main():
    """Verificar datos en Firebase"""
    
    print("=" * 80)
    print("VERIFICACIÓN DE DATOS EN FIREBASE")
    print("=" * 80)
    print()
    
    # Obtener cliente de Firestore
    db = get_firestore_client()
    collection_ref = db.collection('unidades_proyecto')
    
    # Obtener primeros 5 documentos
    docs = collection_ref.limit(5).stream()
    
    print("📊 Primeros 5 documentos en la colección:")
    print()
    
    for idx, doc in enumerate(docs, 1):
        data = doc.to_dict()
        
        print(f"\n🔹 Documento {idx}: {doc.id}")
        print(f"   - UPID: {data.get('upid', 'N/A')}")
        print(f"   - Nombre UP: {data.get('nombre_up', 'N/A')}")
        print(f"   - Estado: {data.get('estado', 'N/A')}")
        print(f"   - Clase obra: {data.get('clase_obra', 'N/A')}")
        print(f"   - Geometry type: {data.get('geometry_type', 'N/A')}")
        print(f"   - Has geometry: {data.get('has_geometry', 'N/A')}")
        print(f"   - Has valid geometry: {data.get('has_valid_geometry', 'N/A')}")
        print(f"   - Loaded at: {data.get('loaded_at', 'N/A')}")
        
        # Mostrar tipo de geometry field
        geometry = data.get('geometry')
        if geometry:
            print(f"   - Geometry field type: {type(geometry).__name__}")
            if isinstance(geometry, str):
                print(f"   - Geometry (primeros 100 chars): {geometry[:100]}...")
    
    print()
    print("=" * 80)
    print("BUSCAR DOCUMENTOS CON UPID GENERADOS HOY")
    print("=" * 80)
    print()
    
    # Buscar documentos con UPID que contiene timestamp de hoy
    # Los UPIDs generados tienen formato: UP-20251103HHMMSS-xxxxx
    docs_today = collection_ref.where('upid', '>=', 'UP-20251103').where('upid', '<=', 'UP-20251104').limit(5).stream()
    
    count = 0
    for doc in docs_today:
        count += 1
        data = doc.to_dict()
        print(f"✅ Encontrado: {data.get('upid')} - {data.get('nombre_up')}")
    
    if count == 0:
        print("⚠️  No se encontraron documentos con UPIDs de hoy")
        
        # Intentar buscar cualquier documento con clase_obra = "Obra Vial"
        print()
        print("Buscando documentos con clase_obra='Obra Vial'...")
        docs_vial = collection_ref.where('clase_obra', '==', 'Obra Vial').limit(5).stream()
        
        vial_count = 0
        for doc in docs_vial:
            vial_count += 1
            data = doc.to_dict()
            print(f"✅ {data.get('upid')} - {data.get('nombre_up')}")
        
        if vial_count == 0:
            print("⚠️  Tampoco se encontraron documentos con clase_obra='Obra Vial'")
    else:
        print(f"\n✅ Total encontrados: {count}")
    
    print()
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())

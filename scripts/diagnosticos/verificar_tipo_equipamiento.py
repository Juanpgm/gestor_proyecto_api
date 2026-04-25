"""
Verificar que los documentos recién creados tengan tipo_equipamiento = 'Vías'
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from database.firebase_config import get_firestore_client


async def main():
    """Verificar documentos UNP-1161, 1162, 1163"""
    
    db = get_firestore_client()
    collection_ref = db.collection('unidades_proyecto')
    
    print("=" * 80)
    print("VERIFICACIÓN: tipo_equipamiento en documentos recién cargados")
    print("=" * 80)
    print()
    
    upids_to_check = ['UNP-1161', 'UNP-1162', 'UNP-1163']
    
    for upid in upids_to_check:
        doc = collection_ref.document(upid).get()
        
        if doc.exists:
            data = doc.to_dict()
            
            print(f"📄 Documento: {upid}")
            print(f"   - Nombre UP: {data.get('nombre_up', 'N/A')}")
            print(f"   - Clase obra: {data.get('clase_obra', 'N/A')}")
            print(f"   - tipo_equipamiento: {data.get('tipo_equipamiento', 'N/A')}")
            print(f"   - Estado: {data.get('estado', 'N/A')}")
            
            if data.get('tipo_equipamiento') == 'Vías':
                print(f"   ✅ CORRECTO: tipo_equipamiento = 'Vías'")
            else:
                print(f"   ❌ ERROR: tipo_equipamiento = '{data.get('tipo_equipamiento')}'")
            
            print()
        else:
            print(f"❌ Documento {upid} no encontrado")
            print()
    
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())

"""
Script para inspeccionar el formato de intervenciones en Firebase
"""

import sys
from pathlib import Path
import json

# Agregar el directorio raíz al path
sys.path.insert(0, str(Path(__file__).parent))

from database.firebase_config import get_firestore_client


def main():
    """Inspeccionar formato de intervenciones"""
    
    print("=" * 80)
    print("INSPECCIÓN DE FORMATO DE INTERVENCIONES")
    print("=" * 80)
    print()
    
    # Obtener cliente de Firestore
    db = get_firestore_client()
    collection_ref = db.collection('unidades_proyecto')
    
    # Obtener primeros 3 documentos
    docs = list(collection_ref.limit(3).stream())
    
    for idx, doc in enumerate(docs, 1):
        data = doc.to_dict()
        
        print(f"\n{'=' * 80}")
        print(f"🔹 DOCUMENTO {idx}: {doc.id}")
        print(f"{'=' * 80}")
        
        print(f"\n✓ UPID: {data.get('upid')}")
        print(f"✓ Nombre: {data.get('nombre_up')}")
        print(f"✓ Clase UP: {data.get('clase_up')}")
        print(f"✓ N° Intervenciones: {data.get('n_intervenciones')}")
        
        if 'intervenciones' in data:
            intervenciones = data['intervenciones']
            print(f"\n📦 Campo 'intervenciones':")
            print(f"   • Tipo: {type(intervenciones).__name__}")
            
            if isinstance(intervenciones, str):
                print(f"   • Es string - intentando parsear como JSON...")
                try:
                    parsed = json.loads(intervenciones)
                    print(f"   • Parseado exitosamente!")
                    print(f"   • Tipo parseado: {type(parsed).__name__}")
                    if isinstance(parsed, list):
                        print(f"   • Longitud: {len(parsed)}")
                        if parsed:
                            print(f"\n   📋 Primera intervención:")
                            print(json.dumps(parsed[0], indent=6, ensure_ascii=False))
                except Exception as e:
                    print(f"   ✗ Error parseando: {e}")
                    print(f"   • Contenido (primeros 200 chars): {intervenciones[:200]}")
            
            elif isinstance(intervenciones, list):
                print(f"   • Ya es lista")
                print(f"   • Longitud: {len(intervenciones)}")
                if intervenciones:
                    print(f"\n   📋 Primera intervención:")
                    if isinstance(intervenciones[0], dict):
                        print(json.dumps(intervenciones[0], indent=6, ensure_ascii=False))
                    else:
                        print(f"      Tipo: {type(intervenciones[0]).__name__}")
                        print(f"      Valor: {intervenciones[0]}")
    
    print()
    print("=" * 80)


if __name__ == "__main__":
    main()

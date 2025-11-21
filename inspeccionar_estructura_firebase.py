"""
Script para inspeccionar la estructura real de documentos en Firebase
"""

import asyncio
import sys
import json
from pathlib import Path

# Agregar el directorio raíz al path
sys.path.insert(0, str(Path(__file__).parent))

from database.firebase_config import get_firestore_client


async def main():
    """Inspeccionar estructura de documentos en Firebase"""
    
    print("=" * 80)
    print("INSPECCIÓN DETALLADA DE ESTRUCTURA EN FIREBASE")
    print("=" * 80)
    print()
    
    # Obtener cliente de Firestore
    db = get_firestore_client()
    collection_ref = db.collection('unidades_proyecto')
    
    # Obtener primeros 3 documentos
    docs = list(collection_ref.limit(3).stream())
    
    print(f"📊 Analizando {len(docs)} documentos de la colección 'unidades_proyecto':")
    print()
    
    for idx, doc in enumerate(docs, 1):
        data = doc.to_dict()
        
        print(f"\n{'=' * 80}")
        print(f"🔹 DOCUMENTO {idx}: {doc.id}")
        print(f"{'=' * 80}")
        
        # Mostrar TODAS las claves del primer nivel
        print(f"\n📋 Campos de primer nivel ({len(data.keys())} campos):")
        for key in sorted(data.keys()):
            value = data[key]
            value_type = type(value).__name__
            
            # Mostrar preview del valor
            if value is None:
                preview = "None"
            elif isinstance(value, (str, int, float, bool)):
                preview = str(value)[:50]
                if len(str(value)) > 50:
                    preview += "..."
            elif isinstance(value, dict):
                preview = f"dict con {len(value)} keys: {list(value.keys())[:3]}"
            elif isinstance(value, list):
                preview = f"list con {len(value)} items"
            else:
                preview = f"{value_type} object"
            
            print(f"   • {key:30s} [{value_type:15s}] = {preview}")
        
        # Si hay un campo 'properties', mostrarlo en detalle
        if 'properties' in data and isinstance(data['properties'], dict):
            print(f"\n📦 Dentro de 'properties' ({len(data['properties'].keys())} campos):")
            for key in sorted(data['properties'].keys()):
                value = data['properties'][key]
                value_type = type(value).__name__
                
                if value is None:
                    preview = "None"
                elif isinstance(value, (str, int, float, bool)):
                    preview = str(value)[:50]
                    if len(str(value)) > 50:
                        preview += "..."
                else:
                    preview = f"{value_type}"
                
                print(f"   • {key:30s} [{value_type:15s}] = {preview}")
        
        # Buscar campos relacionados con "clase"
        print(f"\n🔍 Campos relacionados con 'clase':")
        for key in data.keys():
            if 'clase' in key.lower():
                print(f"   ✓ Campo encontrado: '{key}' = {data[key]}")
        
        if 'properties' in data and isinstance(data['properties'], dict):
            for key in data['properties'].keys():
                if 'clase' in key.lower():
                    print(f"   ✓ Campo encontrado en properties: '{key}' = {data['properties'][key]}")
        
        if idx == 1:
            # Mostrar JSON completo del primer documento
            print(f"\n📄 JSON completo del primer documento:")
            print(json.dumps(data, indent=2, default=str, ensure_ascii=False)[:2000])
            print("...")
    
    print()
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())

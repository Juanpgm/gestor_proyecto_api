"""
Script para encontrar documentos CON frente_activo y ver su estructura
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from database.firebase_config import get_firestore_client

def encontrar_docs_con_frente_activo():
    """Encontrar documentos que tengan frente_activo"""
    
    print("\n" + "="*80)
    print("BÚSQUEDA: Documentos CON campo 'frente_activo'")
    print("="*80)
    
    db = get_firestore_client()
    if db is None:
        print("❌ No se pudo conectar a Firestore")
        return
    
    print("✅ Conectado a Firestore")
    print("\n🔍 Buscando primeros 10 documentos con 'frente_activo'...\n")
    
    docs = db.collection('unidades_proyecto').stream()
    
    encontrados = 0
    valores_unicos = set()
    
    for doc in docs:
        if encontrados >= 10:
            break
        
        doc_data = doc.to_dict()
        
        # Buscar frente_activo en ambos niveles
        frente_superior = doc_data.get('frente_activo')
        frente_properties = None
        
        if 'properties' in doc_data and isinstance(doc_data['properties'], dict):
            frente_properties = doc_data['properties'].get('frente_activo')
        
        if frente_superior or frente_properties:
            encontrados += 1
            upid = doc_data.get('upid') or doc_data.get('properties', {}).get('upid', 'N/A')
            
            print(f"📄 Doc {encontrados}: {doc.id}")
            print(f"   UPID: {upid}")
            
            if frente_superior:
                print(f"   ✅ frente_activo (nivel superior): '{frente_superior}'")
                print(f"      Tipo: {type(frente_superior).__name__}")
                valores_unicos.add(str(frente_superior))
            
            if frente_properties:
                print(f"   ✅ frente_activo (en properties): '{frente_properties}'")
                print(f"      Tipo: {type(frente_properties).__name__}")
                valores_unicos.add(str(frente_properties))
            
            # Mostrar estructura
            print(f"   📋 Estructura del documento:")
            print(f"      - Campos nivel superior: {list(doc_data.keys())[:15]}")
            
            if 'properties' in doc_data:
                props_keys = list(doc_data['properties'].keys())
                print(f"      - Campos en properties: {props_keys[:15]}")
                
                # Ver si frente_activo está en properties
                if 'frente_activo' in props_keys:
                    idx = props_keys.index('frente_activo')
                    print(f"      - 'frente_activo' en posición {idx} de properties")
            
            print()
    
    print("="*80)
    print(f"Total documentos con 'frente_activo': {encontrados}")
    print(f"Valores únicos encontrados: {len(valores_unicos)}")
    print("\nValores:")
    for valor in sorted(valores_unicos)[:20]:
        print(f"  - {valor}")
    print("="*80)

if __name__ == "__main__":
    encontrar_docs_con_frente_activo()

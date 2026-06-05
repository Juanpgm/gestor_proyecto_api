"""
Script para verificar específicamente el documento UNP-2238
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from database.firebase_config import get_firestore_client

def verificar_upn_2238():
    """Verificar el documento UNP-2238"""
    
    print("\n" + "="*80)
    print("VERIFICACIÓN: Documento UNP-2238")
    print("="*80)
    
    db = get_firestore_client()
    if db is None:
        print("❌ No se pudo conectar a Firestore")
        return
    
    print("✅ Conectado a Firestore")
    print("\n🔍 Buscando documento UNP-2238...\n")
    
    # Buscar por UPID
    docs = db.collection('unidades_proyecto').where('upid', '==', 'UNP-2238').stream()
    
    encontrado = False
    for doc in docs:
        encontrado = True
        doc_data = doc.to_dict()
        
        print(f"📄 Documento encontrado: {doc.id}")
        print(f"   UPID: {doc_data.get('upid')}")
        print(f"   Nombre: {doc_data.get('nombre_up')}")
        print(f"   Estado: {doc_data.get('estado')}")
        
        # Verificar frente_activo
        frente_superior = doc_data.get('frente_activo')
        frente_properties = None
        
        if 'properties' in doc_data and isinstance(doc_data['properties'], dict):
            frente_properties = doc_data['properties'].get('frente_activo')
        
        print(f"\n🔍 Verificación de 'frente_activo':")
        
        if frente_superior is not None:
            print(f"   ✅ Existe en nivel superior: '{frente_superior}'")
        else:
            print(f"   ❌ NO existe en nivel superior")
        
        if frente_properties is not None:
            print(f"   ✅ Existe en properties: '{frente_properties}'")
        else:
            print(f"   ❌ NO existe en properties")
        
        if frente_superior is None and frente_properties is None:
            print(f"\n⚠️ CONCLUSIÓN: Este documento NO tiene el campo 'frente_activo'")
            print(f"   Por eso no aparece en la salida del endpoint")
        
        # Mostrar todos los campos
        print(f"\n📋 TODOS los campos del documento ({len(doc_data)} campos):")
        for i, key in enumerate(sorted(doc_data.keys()), 1):
            value = doc_data[key]
            if isinstance(value, (str, int, float, bool, type(None))):
                value_str = str(value)[:50]
                print(f"   {i:2d}. {key}: {value_str}")
            else:
                print(f"   {i:2d}. {key}: <{type(value).__name__}>")
        
        # Verificar si tiene properties
        if 'properties' in doc_data:
            print(f"\n📋 Campos en properties:")
            props = doc_data['properties']
            for key in sorted(props.keys()):
                print(f"   - {key}")
    
    if not encontrado:
        print("❌ No se encontró el documento UNP-2238")
    
    print("\n" + "="*80)

if __name__ == "__main__":
    verificar_upn_2238()

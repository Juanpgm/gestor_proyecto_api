"""
Script de diagnóstico para verificar el campo frente_activo en Firestore
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from database.firebase_config import get_firestore_client

def diagnosticar_frente_activo():
    """Verificar presencia del campo frente_activo en Firestore"""
    
    print("\n" + "="*80)
    print("DIAGNÓSTICO: Campo 'frente_activo' en Firestore")
    print("="*80)
    
    db = get_firestore_client()
    if db is None:
        print("❌ No se pudo conectar a Firestore")
        return
    
    print("✅ Conectado a Firestore")
    
    # Obtener primeros 10 documentos
    docs = db.collection('unidades_proyecto').limit(10).stream()
    
    total_docs = 0
    docs_con_frente_activo = 0
    docs_con_frente_en_properties = 0
    valores_frente_activo = set()
    
    print("\n📋 Analizando primeros 10 documentos...\n")
    
    for doc in docs:
        total_docs += 1
        doc_data = doc.to_dict()
        upid = doc_data.get('upid') or doc_data.get('properties', {}).get('upid', 'N/A')
        
        # Verificar en nivel superior
        frente_nivel_superior = doc_data.get('frente_activo')
        
        # Verificar en properties
        frente_en_properties = None
        if 'properties' in doc_data and isinstance(doc_data['properties'], dict):
            frente_en_properties = doc_data['properties'].get('frente_activo')
        
        print(f"📄 Doc {total_docs}: {doc.id}")
        print(f"   UPID: {upid}")
        
        if frente_nivel_superior:
            print(f"   ✅ frente_activo (nivel superior): '{frente_nivel_superior}'")
            docs_con_frente_activo += 1
            valores_frente_activo.add(str(frente_nivel_superior))
        else:
            print(f"   ❌ frente_activo (nivel superior): No presente")
        
        if frente_en_properties:
            print(f"   ✅ frente_activo (en properties): '{frente_en_properties}'")
            docs_con_frente_en_properties += 1
            valores_frente_activo.add(str(frente_en_properties))
        else:
            print(f"   ❌ frente_activo (en properties): No presente")
        
        # Mostrar todos los campos del nivel superior
        campos_principales = [k for k in doc_data.keys() if k != 'properties']
        print(f"   📋 Campos principales ({len(campos_principales)}): {', '.join(campos_principales[:10])}")
        
        if 'properties' in doc_data:
            campos_properties = list(doc_data['properties'].keys())
            print(f"   📋 Campos en properties ({len(campos_properties)}): {', '.join(campos_properties[:10])}")
        
        print()
    
    print("="*80)
    print("RESUMEN")
    print("="*80)
    print(f"Total documentos analizados: {total_docs}")
    print(f"Documentos con 'frente_activo' (nivel superior): {docs_con_frente_activo} ({docs_con_frente_activo/total_docs*100:.1f}%)")
    print(f"Documentos con 'frente_activo' (en properties): {docs_con_frente_en_properties} ({docs_con_frente_en_properties/total_docs*100:.1f}%)")
    print(f"\nValores únicos encontrados: {len(valores_frente_activo)}")
    if valores_frente_activo:
        print("Valores:")
        for valor in sorted(valores_frente_activo):
            print(f"  - {valor}")
    
    print("\n" + "="*80)
    
    # Contar total en toda la colección
    print("\n📊 Contando en toda la colección...")
    all_docs = db.collection('unidades_proyecto').stream()
    
    total_en_coleccion = 0
    total_con_frente = 0
    
    for doc in all_docs:
        total_en_coleccion += 1
        doc_data = doc.to_dict()
        
        tiene_frente = (
            doc_data.get('frente_activo') or 
            (doc_data.get('properties', {}).get('frente_activo') if isinstance(doc_data.get('properties'), dict) else None)
        )
        
        if tiene_frente:
            total_con_frente += 1
    
    print(f"\n📈 Estadísticas totales:")
    print(f"   Total documentos: {total_en_coleccion}")
    print(f"   Con 'frente_activo': {total_con_frente} ({total_con_frente/total_en_coleccion*100:.1f}%)")
    print(f"   Sin 'frente_activo': {total_en_coleccion - total_con_frente} ({(total_en_coleccion - total_con_frente)/total_en_coleccion*100:.1f}%)")
    
    print("\n" + "="*80)

if __name__ == "__main__":
    diagnosticar_frente_activo()

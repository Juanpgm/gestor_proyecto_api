"""
Script para verificar si existen múltiples documentos con el mismo UPID
"""

import asyncio
import sys
from pathlib import Path
from collections import Counter

# Agregar el directorio raíz al path
sys.path.insert(0, str(Path(__file__).parent))

from database.firebase_config import get_firestore_client


def main():
    """Verificar UPIDs duplicados en Firebase"""
    
    print("=" * 80)
    print("VERIFICACIÓN DE UPIDs DUPLICADOS")
    print("=" * 80)
    print()
    
    # Obtener cliente de Firestore
    db = get_firestore_client()
    collection_ref = db.collection('unidades_proyecto')
    
    # Obtener TODOS los documentos (solo el campo upid para eficiencia)
    print("📥 Obteniendo todos los UPIDs de Firebase...")
    docs = collection_ref.stream()
    
    upids = []
    doc_count = 0
    
    for doc in docs:
        data = doc.to_dict()
        upid = data.get('upid')
        if upid:
            upids.append(upid)
        doc_count += 1
        
        if doc_count % 100 == 0:
            print(f"   Procesados {doc_count} documentos...")
    
    print(f"\n✅ Total de documentos procesados: {doc_count}")
    print(f"✅ Total de UPIDs encontrados: {len(upids)}")
    
    # Contar frecuencias
    upid_counts = Counter(upids)
    
    # Encontrar duplicados
    duplicados = {upid: count for upid, count in upid_counts.items() if count > 1}
    unicos = {upid: count for upid, count in upid_counts.items() if count == 1}
    
    print(f"\n📊 RESUMEN:")
    print(f"   • UPIDs únicos: {len(unicos)}")
    print(f"   • UPIDs duplicados: {len(duplicados)}")
    
    if duplicados:
        print(f"\n⚠️  SE ENCONTRARON {len(duplicados)} UPIDs CON MÚLTIPLES DOCUMENTOS:")
        print()
        
        # Mostrar los primeros 10 duplicados
        for idx, (upid, count) in enumerate(sorted(duplicados.items(), key=lambda x: x[1], reverse=True)[:10], 1):
            print(f"   {idx}. {upid}: {count} documentos")
        
        if len(duplicados) > 10:
            print(f"   ... y {len(duplicados) - 10} más")
        
        print(f"\n🎯 CONCLUSIÓN:")
        print(f"   La estructura actual YA TIENE múltiples intervenciones por UPID.")
        print(f"   Necesitamos AGRUPAR documentos por UPID en la nueva API.")
        
        # Mostrar ejemplo detallado de un UPID duplicado
        ejemplo_upid = list(duplicados.keys())[0]
        print(f"\n🔍 EJEMPLO DETALLADO: {ejemplo_upid} ({duplicados[ejemplo_upid]} documentos)")
        
        ejemplo_docs = list(collection_ref.where('upid', '==', ejemplo_upid).limit(3).stream())
        
        for idx, doc in enumerate(ejemplo_docs, 1):
            data = doc.to_dict()
            print(f"\n   📄 Documento {idx} (ID: {doc.id}):")
            print(f"      • nombre_up: {data.get('nombre_up', 'N/A')}")
            print(f"      • estado: {data.get('estado', 'N/A')}")
            print(f"      • tipo_equipamiento: {data.get('tipo_equipamiento', 'N/A')}")
            print(f"      • ano: {data.get('ano', 'N/A')}")
            print(f"      • presupuesto_base: {data.get('presupuesto_base', 'N/A')}")
            print(f"      • bpin: {data.get('bpin', 'N/A')}")
            print(f"      • direccion: {data.get('direccion', 'N/A')}")
    else:
        print(f"\n✅ NO SE ENCONTRARON DUPLICADOS:")
        print(f"   Cada UPID tiene exactamente UN documento.")
        print(f"   La estructura actual es 1:1 (un documento por unidad).")
        print(f"\n🎯 CONCLUSIÓN:")
        print(f"   NO necesitamos agrupar. Cada documento ya representa una unidad completa.")
        print(f"   Sin embargo, podemos preparar la estructura para soportar múltiples")
        print(f"   intervenciones en el futuro agregando un array 'intervenciones'.")
    
    print()
    print("=" * 80)


if __name__ == "__main__":
    main()

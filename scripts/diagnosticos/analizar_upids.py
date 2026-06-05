"""
Script para analizar el patrón de UPIDs en Firebase
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from database.firebase_config import get_firestore_client


async def main():
    """Analizar UPIDs existentes"""
    
    db = get_firestore_client()
    collection_ref = db.collection('unidades_proyecto')
    
    # Obtener todos los documentos (solo IDs)
    docs = collection_ref.limit(50).stream()
    
    print("=" * 80)
    print("ANÁLISIS DE UPIDs EXISTENTES")
    print("=" * 80)
    print()
    
    upids = []
    for doc in docs:
        doc_id = doc.id
        upids.append(doc_id)
    
    # Ordenar UPIDs
    upids.sort()
    
    print(f"Total documentos analizados: {len(upids)}")
    print()
    print("Primeros 20 UPIDs:")
    for upid in upids[:20]:
        print(f"  - {upid}")
    
    print()
    print("Últimos 10 UPIDs:")
    for upid in upids[-10:]:
        print(f"  - {upid}")
    
    # Detectar patrón
    print()
    print("=" * 80)
    print("DETECCIÓN DE PATRÓN")
    print("=" * 80)
    print()
    
    # Contar UPIDs con formato UNP-X (numérico)
    unp_numeric = [u for u in upids if u.startswith('UNP-') and u.split('-')[1].isdigit()]
    print(f"UPIDs con formato UNP-[número]: {len(unp_numeric)}")
    
    if unp_numeric:
        # Obtener el número más alto
        max_num = max([int(u.split('-')[1]) for u in unp_numeric])
        print(f"Número más alto: {max_num}")
        print(f"Siguiente UPID debería ser: UNP-{max_num + 1}")
    
    # Contar UPIDs con formato UP-timestamp-uuid
    up_timestamp = [u for u in upids if u.startswith('UP-2025')]
    print(f"\nUPIDs con formato UP-timestamp-uuid: {len(up_timestamp)}")
    
    print()
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())

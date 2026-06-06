"""
Script para eliminar datos de test de Firestore.
Busca documentos con el tag TEST_GESTION_REGISTROS en cualquier campo de texto.
"""

import sys, os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from database.firebase_config import get_firestore_client

TAG = "TEST_GESTION_REGISTROS"
COLECCIONES = [
    "unidades_proyecto",
    "intervenciones_unidades_proyecto",
    "solicitudes_cambios_unidad_proyecto",
    "solicitudes_cambios_intervencion",
]


def main():
    db = get_firestore_client()
    deleted = 0

    for col in COLECCIONES:
        docs = list(db.collection(col).stream())
        for doc in docs:
            d = doc.to_dict() or {}
            vals = list(d.values())
            if any(isinstance(v, str) and TAG in v for v in vals):
                label = (
                    d.get("nombre_centro_gestor") or d.get("intervencion_id") or doc.id
                )
                print(f"  [{col}] Eliminando {doc.id}: {label}")
                doc.reference.delete()
                deleted += 1

    print(f"\nTotal eliminados: {deleted}")


if __name__ == "__main__":
    main()

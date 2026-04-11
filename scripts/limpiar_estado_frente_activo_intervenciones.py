"""
Script de migración: elimina los campos 'estado' y 'frente_activo' de todos
los documentos en la colección 'intervenciones_unidades_proyecto' de Firebase.

Estos campos se calculan dinámicamente en cada consulta a partir de 'avance_obra'
y no deben persistirse en Firebase para evitar conflictos con la lógica de negocio.

Uso:
    python scripts/limpiar_estado_frente_activo_intervenciones.py
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Forzar UTF-8 en stdout para evitar errores de encoding en Windows
if sys.stdout.encoding != 'utf-8':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from database.firebase_config import get_firestore_client
from google.cloud import firestore


def limpiar_campos():
    db = get_firestore_client()
    if db is None:
        print("❌ No se pudo conectar a Firestore. Verifica las credenciales.")
        sys.exit(1)

    coleccion = db.collection('intervenciones_unidades_proyecto')

    print("⏳ Obteniendo documentos de 'intervenciones_unidades_proyecto'...")
    docs = list(coleccion.stream())
    total = len(docs)
    actualizados = 0
    sin_cambio = 0

    print(f"📄 Total documentos a revisar: {total}\n")

    for i, doc in enumerate(docs, start=1):
        data = doc.to_dict() or {}
        tiene_estado = 'estado' in data
        tiene_frente = 'frente_activo' in data

        if tiene_estado or tiene_frente:
            update_payload = {}
            if tiene_estado:
                update_payload['estado'] = firestore.DELETE_FIELD
            if tiene_frente:
                update_payload['frente_activo'] = firestore.DELETE_FIELD
            doc.reference.update(update_payload)
            campos_eliminados = [k for k in ('estado', 'frente_activo') if k in data]
            print(f"  [{i}/{total}] {doc.id} → eliminados: {campos_eliminados}")
            actualizados += 1
        else:
            sin_cambio += 1

        if i % 100 == 0:
            print(f"  ... procesados {i}/{total}")

    print(f"\n✅ Actualizados: {actualizados}")
    print(f"⏭  Sin cambio:  {sin_cambio}")
    print(f"📊 Total:        {total}")


if __name__ == "__main__":
    limpiar_campos()

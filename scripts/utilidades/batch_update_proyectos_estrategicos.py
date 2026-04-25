"""Recalcula proyectos_estrategicos para TODAS las unidades de proyecto en Firebase."""
import json
from main import get_firestore_client, _buscar_proyectos_estrategicos, _normalizar_geometry

db = get_firestore_client()

print("=== Escaneando todas las unidades de proyecto ===")
all_docs = list(db.collection('unidades_proyecto').stream())
print(f"Total documentos: {len(all_docs)}")

updated = 0
skipped_no_geom = 0
errors = 0

for doc in all_docs:
    d = doc.to_dict()
    upid = d.get('upid', doc.id)
    geom = d.get('geometry')

    if not isinstance(geom, dict) or not geom.get('type') or not geom.get('coordinates'):
        skipped_no_geom += 1
        continue

    try:
        nuevo_pe = _buscar_proyectos_estrategicos(geom)
    except Exception as e:
        errors += 1
        print(f"  ERROR {upid}: {e}")
        continue

    actual_pe = d.get('proyectos_estrategicos', [])
    if not isinstance(actual_pe, list):
        if isinstance(actual_pe, str):
            actual_pe = [v.strip() for v in actual_pe.split(",") if v.strip()]
        else:
            actual_pe = []

    if sorted(nuevo_pe) != sorted(actual_pe):
        db.collection('unidades_proyecto').document(doc.id).update({
            'proyectos_estrategicos': nuevo_pe
        })
        updated += 1
        print(f"  ACTUALIZADO {upid}: {actual_pe} -> {nuevo_pe}")

print(f"\n=== Resumen ===")
print(f"Total documentos: {len(all_docs)}")
print(f"Actualizados: {updated}")
print(f"Sin geometría: {skipped_no_geom}")
print(f"Errores: {errors}")
print(f"Sin cambios: {len(all_docs) - updated - skipped_no_geom - errors}")

# Verificar conteo final
docs_micro = list(db.collection('unidades_proyecto').where(
    'proyectos_estrategicos', 'array_contains', 'Microterritorios'
).stream())
print(f"\n=== Verificación final ===")
print(f"Unidades con 'Microterritorios' en Firebase: {len(docs_micro)}")

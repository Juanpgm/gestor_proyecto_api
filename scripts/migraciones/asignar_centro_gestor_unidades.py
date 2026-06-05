"""
Migración: propagar `nombre_centro_gestor` desde intervenciones_unidades_proyecto
hacia unidades_proyecto usando `upid` como clave de unión.

Motivo:
  Las 2360 unidades_proyecto no tienen `nombre_centro_gestor`, por lo que los
  usuarios con rol `admin_centro_gestor` no pueden ver/operar las unidades
  de su centro. Las 2507 intervenciones sí tienen `nombre_centro_gestor`
  (100%) y comparten `upid` con su unidad.

Estrategia:
  - Para cada upid, calcular el centro mayoritario entre sus intervenciones.
  - Si una unidad ya tiene `nombre_centro_gestor` no nulo, NO se sobreescribe
    salvo con --force.
  - Si una unidad tiene 0 intervenciones, queda sin asignar (se reporta).
  - Si las intervenciones de un upid tienen centros conflictivos, se asigna
    el mayoritario y se reporta el conflicto.

Uso:
  # Dry-run (no escribe):
  python back/scripts/migraciones/asignar_centro_gestor_unidades.py

  # Aplicar cambios:
  python back/scripts/migraciones/asignar_centro_gestor_unidades.py --apply

  # Sobrescribir incluso si ya hay valor:
  python back/scripts/migraciones/asignar_centro_gestor_unidades.py --apply --force
"""

import argparse
import os
import sys
from collections import Counter, defaultdict
from typing import Dict, Optional

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
BACK_DIR = os.path.abspath(os.path.join(THIS_DIR, "..", ".."))
if BACK_DIR not in sys.path:
    sys.path.insert(0, BACK_DIR)

from database.firebase_config import get_firestore_client  # noqa: E402


def _norm(value) -> Optional[str]:
    if value is None:
        return None
    s = str(value).strip()
    return s or None


def _upid_norm(value) -> Optional[str]:
    s = _norm(value)
    return s.upper() if s else None


def _unidad_centro(data: dict) -> Optional[str]:
    props = data.get("properties") if isinstance(data.get("properties"), dict) else {}
    for field in (
        "nombre_centro_gestor",
        "nombreCentroGestor",
        "nombre_centro",
        "centro_gestor",
    ):
        v = _norm(data.get(field))
        if v:
            return v
        if props:
            v = _norm(props.get(field))
            if v:
                return v
    return None


def build_upid_to_centro(db) -> Dict[str, Dict[str, int]]:
    """upid -> Counter de nombres de centro entre sus intervenciones."""
    out: Dict[str, Counter] = defaultdict(Counter)
    docs = list(db.collection("intervenciones_unidades_proyecto").stream())
    for d in docs:
        data = d.to_dict() or {}
        upid = _upid_norm(data.get("upid"))
        centro = _norm(data.get("nombre_centro_gestor")) or _norm(
            data.get("centro_gestor")
        )
        if upid and centro:
            out[upid][centro] += 1
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply", action="store_true", help="Aplicar los cambios (sin esto es dry-run)"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Sobreescribir aunque la unidad ya tenga centro",
    )
    args = parser.parse_args()

    db = get_firestore_client()
    if db is None:
        print("ERROR: Firestore no disponible")
        sys.exit(2)

    print(f"Modo: {'APLICAR ESCRITURAS' if args.apply else 'DRY-RUN (sin escribir)'}")
    print(f"Force overwrite: {args.force}\n")

    print("Construyendo mapa upid -> centro desde intervenciones...")
    upid_centros = build_upid_to_centro(db)
    print(f"  upids únicos con centro en intervenciones: {len(upid_centros)}\n")

    print("Procesando unidades_proyecto...")
    docs = list(db.collection("unidades_proyecto").stream())
    print(f"  total unidades: {len(docs)}\n")

    to_update = (
        []
    )  # list of (doc_ref, upid, centro_nuevo, centro_actual, conflict_info)
    skipped_has_value = 0
    skipped_no_upid = 0
    skipped_no_intervenciones = []
    conflicts = []  # (upid, counts)

    for d in docs:
        data = d.to_dict() or {}
        upid = _upid_norm(data.get("upid"))
        actual = _unidad_centro(data)

        if not upid:
            skipped_no_upid += 1
            continue

        if actual and not args.force:
            skipped_has_value += 1
            continue

        counts = upid_centros.get(upid)
        if not counts:
            skipped_no_intervenciones.append((d.id, upid))
            continue

        centro_mayoritario, _ = counts.most_common(1)[0]
        if len(counts) > 1:
            conflicts.append((upid, dict(counts)))

        if actual == centro_mayoritario and not args.force:
            continue

        to_update.append((d.reference, upid, centro_mayoritario, actual, dict(counts)))

    print(f"=== Resumen ===")
    print(f"  unidades a actualizar:                       {len(to_update)}")
    print(f"  saltadas (ya tienen centro, sin --force):    {skipped_has_value}")
    print(f"  saltadas (sin upid):                         {skipped_no_upid}")
    print(
        f"  saltadas (sin intervenciones asociadas):     {len(skipped_no_intervenciones)}"
    )
    print(f"  upids con conflicto multi-centro:            {len(conflicts)}")

    if skipped_no_intervenciones:
        print(f"\n  unidades sin intervenciones (primeras 20):")
        for doc_id, upid in skipped_no_intervenciones[:20]:
            print(f"    {doc_id} (upid={upid})")

    if conflicts:
        print(f"\n  conflictos (primeros 10) — se usará el mayoritario:")
        for upid, counts in conflicts[:10]:
            print(f"    upid={upid}: {counts}")

    # Distribución que se aplicaría
    distrib = Counter(centro for _, _, centro, _, _ in to_update)
    print(f"\n  distribución de centros a asignar:")
    for centro, n in distrib.most_common():
        print(f"    {n:>5}  {centro}")

    if not args.apply:
        print("\n[DRY-RUN] No se escribió nada. Use --apply para ejecutar.")
        return

    # Aplicar
    print(f"\nAplicando {len(to_update)} actualizaciones en batches de 400...")
    batch = db.batch()
    pending = 0
    written = 0
    for ref, _upid, centro, _actual, _counts in to_update:
        batch.update(ref, {"nombre_centro_gestor": centro})
        pending += 1
        if pending >= 400:
            batch.commit()
            written += pending
            print(f"  commit: {written}/{len(to_update)}")
            batch = db.batch()
            pending = 0
    if pending:
        batch.commit()
        written += pending
    print(f"  total escrito: {written}")
    print(
        "\nLISTO. Recomendación: ejecutar POST /unidades-proyecto/calidad-datos/analizar para regenerar el snapshot."
    )


if __name__ == "__main__":
    main()

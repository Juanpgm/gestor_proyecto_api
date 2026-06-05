"""
Diagnóstico rápido: ¿cuántos registros (unidades_proyecto e intervenciones_unidades_proyecto)
están etiquetados con el centro gestor indicado, y cómo aparece el nombre en los datos crudos?

Uso:
  python back/scripts/diagnosticos/check_centro_records.py "Secretaría del Deporte y la Recreación"
"""

import sys
import os
from collections import Counter

# Permitir imports desde el directorio back/
THIS_DIR = os.path.dirname(os.path.abspath(__file__))
BACK_DIR = os.path.abspath(os.path.join(THIS_DIR, "..", ".."))
if BACK_DIR not in sys.path:
    sys.path.insert(0, BACK_DIR)

from database.firebase_config import get_firestore_client  # noqa: E402


def _norm(s):
    if s is None:
        return None
    s = str(s).strip()
    return s if s else None


def _extract_center(data: dict):
    props = (
        data.get("properties", {}) if isinstance(data.get("properties"), dict) else {}
    )
    for f in (
        "nombre_centro_gestor",
        "nombreCentroGestor",
        "nombre_centro",
        "centro_gestor",
    ):
        v = _norm(data.get(f))
        if v is not None:
            return v, f
        v = _norm(props.get(f))
        if v is not None:
            return v, f"properties.{f}"
    return None, None


def main(target: str):
    db = get_firestore_client()
    if db is None:
        print("ERROR: Firestore no disponible")
        sys.exit(2)

    target_n = (target or "").strip().lower()
    print(f"Target centro: '{target}'  (lower='{target_n}')\n")

    for col in ("unidades_proyecto", "intervenciones_unidades_proyecto"):
        print(f"=== {col} ===")
        docs = list(db.collection(col).stream())
        print(f"  total docs: {len(docs)}")
        centers = Counter()
        matches_exact = 0
        matches_ci = 0
        matches_substr = 0
        for d in docs:
            data = d.to_dict() or {}
            v, src = _extract_center(data)
            centers[v or "<NONE>"] += 1
            if v is None:
                continue
            if v == target:
                matches_exact += 1
            if v.lower() == target_n:
                matches_ci += 1
            if target_n and (target_n in v.lower() or v.lower() in target_n):
                matches_substr += 1
        print(f"  match exacto:               {matches_exact}")
        print(f"  match case-insensitive:     {matches_ci}")
        print(f"  match substring (incluye):  {matches_substr}")
        print(f"  top 10 centros encontrados:")
        for name, n in centers.most_common(10):
            print(f"    {n:>4}  {name!r}")
        # Variantes que contienen 'deporte'
        print(f"  variantes que contienen 'deporte':")
        for name, n in centers.items():
            if name != "<NONE>" and "deporte" in name.lower():
                print(f"    {n:>4}  {name!r}")
        print()

    # Snapshot de calidad más reciente
    print("=== Último snapshot de calidad ===")
    latest = db.collection("unidades_proyecto_quality_latest").document("latest").get()
    if not latest.exists:
        print("  No hay snapshot 'latest'")
        return
    latest_d = latest.to_dict() or {}
    report_id = latest_d.get("report_id")
    print(f"  report_id: {report_id}")
    print(f"  filtro: {latest_d.get('filtro')}")
    if not report_id:
        return
    report = (
        db.collection("unidades_proyecto_quality_reports").document(report_id).get()
    )
    if not report.exists:
        print("  Report doc no existe")
        return
    grouped = ((report.to_dict() or {}).get("summary") or {}).get(
        "grouped_by_centro_gestor", {}
    )
    print(f"  grouped_by_centro_gestor keys ({len(grouped)}):")
    for k, v in grouped.items():
        marker = "  <-- MATCH" if k.lower() == target_n else ""
        print(
            f"    total={v.get('total_records'):>4}  with_issues={v.get('with_issues'):>3}  {k!r}{marker}"
        )


if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else "Secretaría del Deporte y la Recreación"
    main(arg)

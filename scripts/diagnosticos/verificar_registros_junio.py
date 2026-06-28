"""
Diagnostic: Verify whether June 2026 records exist in Firestore for
unidades_proyecto domain. Checks intervenciones, unidades_proyecto,
and the delete audit log.

Usage:
  python back/scripts/diagnosticos/verificar_registros_junio.py
  python back/scripts/diagnosticos/verificar_registros_junio.py --mes 2026-05
"""

import sys
import os
import argparse

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
BACK_DIR = os.path.abspath(os.path.join(THIS_DIR, "..", ".."))
if BACK_DIR not in sys.path:
    sys.path.insert(0, BACK_DIR)

from database.firebase_config import get_firestore_client  # noqa: E402


DATE_FIELDS = ("fecha_inicio", "fecha_fin", "created_at", "fecha_creacion", "fecha_actualizacion")


def _in_month(value: str, year: int, month: int) -> bool:
    if not value or not isinstance(value, str):
        return False
    prefix = f"{year}-{month:02d}"
    return value.startswith(prefix)


def check_collection(db, collection: str, year: int, month: int) -> dict:
    print(f"\n=== {collection} ===")
    docs = list(db.collection(collection).stream())
    total = len(docs)
    print(f"  Total docs in collection: {total}")

    hits = []
    no_date = 0
    for doc in docs:
        data = doc.to_dict() or {}
        matched_field = None
        matched_value = None
        for f in DATE_FIELDS:
            v = data.get(f)
            if v and isinstance(v, str) and _in_month(v, year, month):
                matched_field = f
                matched_value = v
                break
        if matched_field:
            hits.append({
                "doc_id": doc.id,
                "field": matched_field,
                "value": matched_value,
                "nombre_centro_gestor": data.get("nombre_centro_gestor", "<no campo>"),
                "upid": data.get("upid", data.get("intervencion_id", "")),
            })
        else:
            has_any_date = any(data.get(f) for f in DATE_FIELDS)
            if not has_any_date:
                no_date += 1

    print(f"  Docs with a date in {year}-{month:02d}: {len(hits)}")
    print(f"  Docs with no date fields at all: {no_date}")

    if hits:
        print(f"\n  Sample hits (first 20):")
        for h in hits[:20]:
            print(f"    doc_id={h['doc_id']}  field={h['field']}  value={h['value']}")
            print(f"           centro={h['nombre_centro_gestor']}  ref={h['upid']}")
    else:
        print(f"\n  No documents found with dates in {year}-{month:02d}.")
        print("  This does NOT necessarily mean data was deleted — it may mean the")
        print("  date fields use a different format or name. Check the samples below.")
        print(f"\n  Sample of date field values from first 5 docs:")
        for doc in list(db.collection(collection).stream())[:5]:
            data = doc.to_dict() or {}
            for f in DATE_FIELDS:
                v = data.get(f)
                if v:
                    print(f"    doc={doc.id}  {f}={str(v)[:40]!r}")

    return {"total": total, "hits": len(hits), "no_date": no_date}


def check_audit_log(db, year: int, month: int):
    print(f"\n=== cambios_implementados_unidades_proyecto (audit log) ===")
    prefix = f"{year}-{month:02d}"
    docs = list(db.collection("cambios_implementados_unidades_proyecto").stream())
    print(f"  Total audit entries: {len(docs)}")
    deletes_in_month = []
    for doc in docs:
        data = doc.to_dict() or {}
        for f in ("deleted_at", "created_at", "timestamp", "fecha"):
            v = data.get(f)
            if v and isinstance(v, str) and v.startswith(prefix):
                action = data.get("action", data.get("tipo_cambio", ""))
                if "delet" in str(action).lower() or "elimin" in str(action).lower():
                    deletes_in_month.append({
                        "doc_id": doc.id,
                        "action": action,
                        "field": f,
                        "value": v,
                        "data_preview": str(data)[:200],
                    })
                break

    if deletes_in_month:
        print(f"  DELETE audit entries in {year}-{month:02d}: {len(deletes_in_month)}")
        for d in deletes_in_month:
            print(f"    {d['doc_id']}: action={d['action']} at {d['value']}")
            print(f"      preview: {d['data_preview']}")
    else:
        print(f"  No DELETE entries found in {year}-{month:02d}.")

    return deletes_in_month


def check_pagination_risk(db):
    print(f"\n=== Pagination risk check (unidades_proyecto) ===")
    total_up = len(list(db.collection("unidades_proyecto").stream()))
    total_int = len(list(db.collection("intervenciones_unidades_proyecto").stream()))
    print(f"  unidades_proyecto total: {total_up}")
    print(f"  intervenciones_unidades_proyecto total: {total_int}")
    if total_up > 100:
        print(f"  WARNING: {total_up} UPs but default API limit is 100.")
        print(f"  Any client using the default ?limit=100 will silently miss {total_up - 100} records.")
    if total_int > 1000:
        print(f"  WARNING: {total_int} intervenciones may exceed default limits.")


def main():
    parser = argparse.ArgumentParser(description="Verify June records in Firestore")
    parser.add_argument("--mes", default="2026-06", help="Month to check (YYYY-MM). Default: 2026-06")
    args = parser.parse_args()

    try:
        year_str, month_str = args.mes.split("-")
        year, month = int(year_str), int(month_str)
    except ValueError:
        print(f"ERROR: Invalid --mes format. Use YYYY-MM (e.g. 2026-06)")
        sys.exit(1)

    print(f"Checking for records with dates in {year}-{month:02d}...")

    db = get_firestore_client()
    if db is None:
        print("ERROR: Firestore not available")
        sys.exit(2)

    results = {}
    for col in ("intervenciones_unidades_proyecto", "unidades_proyecto", "avances_unidades_proyecto"):
        results[col] = check_collection(db, col, year, month)

    check_audit_log(db, year, month)
    check_pagination_risk(db)

    print("\n=== Summary ===")
    for col, r in results.items():
        status = "FOUND" if r["hits"] > 0 else "NOT FOUND"
        print(f"  {col}: {status} ({r['hits']} docs with {year}-{month:02d} dates out of {r['total']} total)")

    any_found = any(r["hits"] > 0 for r in results.values())
    if any_found:
        print(f"\nConclusion: Data with {year}-{month:02d} dates EXISTS in Firestore.")
        print("The 'missing' records are likely a pagination or UI filter issue, not data loss.")
    else:
        print(f"\nConclusion: No data found with {year}-{month:02d} dates.")
        print("Either the data was deleted, uses a different date format, or was never saved with date fields.")
        print("Check the 'Sample of date field values' above to verify the date format used.")


if __name__ == "__main__":
    main()

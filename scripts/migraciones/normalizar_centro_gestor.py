"""
Migration: canonicalize nombre_centro_gestor across all key collections.

The post-filter in scope_records_by_centro uses canonicalize_centro() to
compare names. If names stored in Firestore differ from their canonical form
(different capitalization, accents, short aliases), valid records are silently
discarded for own_centro users.

This script finds all documents where the stored nombre_centro_gestor differs
from its canonical form, reports them, and (with --apply) updates them.

Collections checked:
  - unidades_proyecto
  - intervenciones_unidades_proyecto
  - contratos_emprestito
  - procesos_emprestito

Usage:
  # Dry-run (no writes):
  python back/scripts/migraciones/normalizar_centro_gestor.py

  # Apply changes:
  python back/scripts/migraciones/normalizar_centro_gestor.py --apply
"""

import sys
import os
import argparse
from collections import defaultdict

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
BACK_DIR = os.path.abspath(os.path.join(THIS_DIR, "..", ".."))
if BACK_DIR not in sys.path:
    sys.path.insert(0, BACK_DIR)

from database.firebase_config import get_firestore_client  # noqa: E402
from auth_system.centros_catalog import canonicalize_centro  # noqa: E402


COLLECTIONS = [
    "unidades_proyecto",
    "intervenciones_unidades_proyecto",
    "contratos_emprestito",
    "procesos_emprestito",
]

BATCH_SIZE = 400  # Firestore batch limit is 500; stay below it


def process_collection(db, collection: str, apply: bool) -> dict:
    print(f"\n=== {collection} ===")
    docs = list(db.collection(collection).stream())
    total = len(docs)
    print(f"  Total docs: {total}")

    needs_update = []
    no_campo = 0
    variants: dict[str, list[str]] = defaultdict(list)

    for doc in docs:
        data = doc.to_dict() or {}
        raw = data.get("nombre_centro_gestor")
        if not raw or not isinstance(raw, str) or not raw.strip():
            no_campo += 1
            continue
        canonical = canonicalize_centro(raw.strip())
        if canonical and canonical != raw.strip():
            needs_update.append((doc.reference, raw.strip(), canonical))
            variants[raw.strip()].append(canonical)

    print(f"  Docs without nombre_centro_gestor: {no_campo}")
    print(f"  Docs with non-canonical nombre_centro_gestor: {len(needs_update)}")

    if needs_update:
        print(f"\n  Non-canonical variants (raw → canonical):")
        shown = set()
        for _, raw, canon in needs_update[:30]:
            key = (raw, canon)
            if key not in shown:
                print(f"    {raw!r} → {canon!r}")
                shown.add(key)
        if len(needs_update) > 30:
            print(f"    ... and {len(needs_update) - 30} more")

    if apply and needs_update:
        print(f"\n  Applying updates in batches of {BATCH_SIZE}...")
        updated = 0
        for i in range(0, len(needs_update), BATCH_SIZE):
            batch = db.batch()
            chunk = needs_update[i : i + BATCH_SIZE]
            for ref, _, canonical in chunk:
                batch.update(ref, {"nombre_centro_gestor": canonical})
            batch.commit()
            updated += len(chunk)
            print(f"    Committed {updated}/{len(needs_update)} updates...")
        print(f"  Done. {updated} documents updated.")
    elif needs_update:
        print(f"\n  DRY-RUN: {len(needs_update)} documents would be updated. Use --apply to write.")

    return {"total": total, "no_campo": no_campo, "needs_update": len(needs_update)}


def main():
    parser = argparse.ArgumentParser(
        description="Canonicalize nombre_centro_gestor across Firestore collections"
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write changes to Firestore. Without this flag, runs as dry-run.",
    )
    args = parser.parse_args()

    if args.apply:
        print("MODE: APPLY (will write to Firestore)")
    else:
        print("MODE: DRY-RUN (no writes). Use --apply to commit changes.")

    db = get_firestore_client()
    if db is None:
        print("ERROR: Firestore not available")
        sys.exit(2)

    totals = {}
    for col in COLLECTIONS:
        totals[col] = process_collection(db, col, args.apply)

    print("\n=== Summary ===")
    grand_total_updates = 0
    for col, r in totals.items():
        grand_total_updates += r["needs_update"]
        print(f"  {col}: {r['needs_update']} of {r['total']} docs need update")

    if grand_total_updates == 0:
        print("\nAll nombre_centro_gestor values are already canonical. No action needed.")
    elif not args.apply:
        print(f"\nTotal: {grand_total_updates} documents would be updated.")
        print("Run with --apply to write changes.")
    else:
        print(f"\nTotal: {grand_total_updates} documents updated successfully.")


if __name__ == "__main__":
    main()

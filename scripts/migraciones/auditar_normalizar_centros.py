"""
Auditoría y normalización de `centro_gestor` contra el catálogo oficial.

Parte del saneamiento RBAC (política A): el filtrado por centro usa match exacto,
así que cualquier variante (tildes, abreviatura, typo) deja al usuario sin ver sus
datos. Este script:

  - AUDITA (default, read-only): lista los valores de centro en usuarios y en las
    colecciones de dominio, cuáles mapean al catálogo y cuáles NO, y qué usuarios
    quedarían "bloqueados" (su centro no mapea al catálogo) tras normalizar.
  - NORMALIZA (--apply): reescribe cada `nombre_centro_gestor` (y en usuarios también
    `centro_gestor_assigned` / `centro_gestor`) al valor canónico del catálogo.

ORDEN SEGURO (ver plan): correr la auditoría primero. Solo aplicar --apply cuando
la lista de "usuarios bloqueados" sea aceptable (idealmente vacía o ya remapeada en
el catálogo de alias). Normalizar registros ANTES de apretar el scoping en backend.

Uso:
  # Auditoría (no escribe):
  python back/scripts/migraciones/auditar_normalizar_centros.py

  # Normalizar registros de dominio + usuarios:
  python back/scripts/migraciones/auditar_normalizar_centros.py --apply

  # Solo usuarios / solo registros:
  python back/scripts/migraciones/auditar_normalizar_centros.py --apply --only users
  python back/scripts/migraciones/auditar_normalizar_centros.py --apply --only records
"""

import argparse
import os
import sys
from collections import Counter, defaultdict
from typing import Dict, List, Optional, Tuple

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
BACK_DIR = os.path.abspath(os.path.join(THIS_DIR, "..", ".."))
if BACK_DIR not in sys.path:
    sys.path.insert(0, BACK_DIR)

from database.firebase_config import get_firestore_client  # noqa: E402
from auth_system.centros_catalog import canonicalize_centro  # noqa: E402

# Colecciones de dominio que llevan `nombre_centro_gestor` usado para filtrar.
# Extender según el modelo real (subcolecciones de empréstito, etc.).
RECORD_COLLECTIONS: List[str] = [
    "unidades_proyecto",
    "intervenciones_unidades_proyecto",
    "contratos_emprestito",
    "ejecucion_presupuestal",
]

USER_CENTRO_FIELDS = ("nombre_centro_gestor", "centro_gestor_assigned", "centro_gestor")


def _norm(value) -> Optional[str]:
    if value is None:
        return None
    s = str(value).strip()
    return s or None


def _norm_roles(raw) -> List[str]:
    """Roles como lista normalizada, aceptando string o lista (datos inconsistentes)."""
    if raw is None:
        return []
    if isinstance(raw, str):
        r = raw.strip().lower()
        return [r] if r else []
    if isinstance(raw, (list, tuple, set)):
        return [str(x).strip().lower() for x in raw if str(x).strip()]
    return [str(raw).strip().lower()]


def audit_collection(db, collection: str, field: str = "nombre_centro_gestor") -> Dict:
    """Cuenta valores del campo de centro y su mapeo al catálogo (read-only)."""
    raw_counter: Counter = Counter()
    unmapped: Counter = Counter()
    total = 0
    for doc in db.collection(collection).stream():
        data = doc.to_dict() or {}
        value = _norm(data.get(field))
        total += 1
        if value is None:
            raw_counter["<vacío>"] += 1
            continue
        raw_counter[value] += 1
        if canonicalize_centro(value) is None:
            unmapped[value] += 1
    return {
        "collection": collection,
        "total": total,
        "distinct": len(raw_counter),
        "values": raw_counter,
        "unmapped": unmapped,
    }


def audit_users(db) -> Tuple[Dict, List[str]]:
    """Audita usuarios. Devuelve (resumen, lista de usuarios bloqueados)."""
    blocked: List[str] = []
    unmapped: Counter = Counter()
    total = 0
    for doc in db.collection("users").stream():
        data = doc.to_dict() or {}
        total += 1
        raw = None
        for f in USER_CENTRO_FIELDS:
            raw = _norm(data.get(f))
            if raw:
                break
        roles = _norm_roles(data.get("roles"))
        is_global = any(r in {"super_admin", "admin_general"} for r in roles)
        if is_global:
            continue
        if not raw:
            blocked.append(f"{doc.id} (sin centro asignado, roles={roles})")
            continue
        if canonicalize_centro(raw) is None:
            unmapped[raw] += 1
            blocked.append(f"{doc.id} (centro no mapea: '{raw}', roles={roles})")
    return {"total": total, "unmapped": unmapped}, blocked


def normalize_collection(db, collection: str, apply: bool, field: str = "nombre_centro_gestor") -> Dict:
    changed = 0
    skipped_unmapped = 0
    for doc in db.collection(collection).stream():
        data = doc.to_dict() or {}
        value = _norm(data.get(field))
        if value is None:
            continue
        canonical = canonicalize_centro(value)
        if canonical is None:
            skipped_unmapped += 1
            continue
        if canonical != value:
            changed += 1
            if apply:
                doc.reference.update({field: canonical})
    return {"collection": collection, "changed": changed, "skipped_unmapped": skipped_unmapped}


def normalize_users(db, apply: bool) -> Dict:
    changed = 0
    skipped_unmapped = 0
    for doc in db.collection("users").stream():
        data = doc.to_dict() or {}
        raw = None
        for f in USER_CENTRO_FIELDS:
            raw = _norm(data.get(f))
            if raw:
                break
        if raw is None:
            continue
        canonical = canonicalize_centro(raw)
        if canonical is None:
            skipped_unmapped += 1
            continue
        # Escribir el canónico en los tres campos (consolidación + shim de compat).
        update = {f: canonical for f in USER_CENTRO_FIELDS}
        if any(_norm(data.get(f)) != canonical for f in USER_CENTRO_FIELDS):
            changed += 1
            if apply:
                doc.reference.update(update)
    return {"changed": changed, "skipped_unmapped": skipped_unmapped}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Escribe los cambios (default: dry-run)")
    parser.add_argument("--only", choices=["users", "records"], help="Limitar a usuarios o registros")
    args = parser.parse_args()

    # La consola de Windows (cp1252) no encodea acentos/emojis; forzar UTF-8.
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    db = get_firestore_client()
    if db is None:
        print("ERROR: no se pudo conectar a Firestore")
        sys.exit(1)

    print("=" * 70)
    print("AUDITORÍA centro_gestor vs catálogo oficial")
    print("=" * 70)

    if args.only != "users":
        for coll in RECORD_COLLECTIONS:
            try:
                rep = audit_collection(db, coll)
            except Exception as exc:
                print(f"\n[{coll}] ERROR: {exc}")
                continue
            print(f"\n[{coll}] total={rep['total']} distinct={rep['distinct']}")
            if rep["unmapped"]:
                print(f"  [!] valores NO mapeables al catálogo ({len(rep['unmapped'])}):")
                for v, c in rep["unmapped"].most_common():
                    print(f"     - '{v}'  ({c} registros)")

    if args.only != "records":
        user_rep, blocked = audit_users(db)
        print(f"\n[users] total={user_rep['total']}")
        print(f"  [BLOQUEADOS] usuarios que quedarían BLOQUEADOS: {len(blocked)}")
        for b in blocked:
            print(f"     - {b}")
        if user_rep["unmapped"]:
            print("  [!] centros de usuario no mapeables:")
            for v, c in user_rep["unmapped"].most_common():
                print(f"     - '{v}'  ({c} usuarios)")

    if not args.apply:
        print("\n(DRY-RUN) No se escribió nada. Use --apply para normalizar.")
        return

    print("\n" + "=" * 70)
    print("NORMALIZACIÓN (--apply)")
    print("=" * 70)
    if args.only != "users":
        for coll in RECORD_COLLECTIONS:
            try:
                rep = normalize_collection(db, coll, apply=True)
                print(f"[{coll}] normalizados={rep['changed']} no_mapeables={rep['skipped_unmapped']}")
            except Exception as exc:
                print(f"[{coll}] ERROR: {exc}")
    if args.only != "records":
        rep = normalize_users(db, apply=True)
        print(f"[users] normalizados={rep['changed']} no_mapeables={rep['skipped_unmapped']}")
    print("\n[OK] Normalización aplicada.")


if __name__ == "__main__":
    main()

"""Inspecciona estructura de unidades_proyecto e intervenciones_unidades_proyecto."""

import sys, os, json

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
BACK_DIR = os.path.abspath(os.path.join(THIS_DIR, "..", ".."))
if BACK_DIR not in sys.path:
    sys.path.insert(0, BACK_DIR)
from database.firebase_config import get_firestore_client
from collections import Counter

db = get_firestore_client()

print("=== Muestra UNIDADES_PROYECTO ===")
for i, d in enumerate(db.collection("unidades_proyecto").limit(3).stream()):
    data = d.to_dict() or {}
    print(f"\n--- doc {i} id={d.id} ---")
    print(f"top-level keys: {sorted(data.keys())}")
    props = data.get("properties") or {}
    if isinstance(props, dict):
        print(f"properties keys: {sorted(props.keys())}")
    sample = {
        k: data.get(k)
        for k in (
            "upid",
            "UPID",
            "id_unidad",
            "nombre_centro_gestor",
            "centro_gestor",
            "nombreCentroGestor",
        )
    }
    print(f"campos clave top: {sample}")
    if isinstance(props, dict):
        sample_p = {
            k: props.get(k)
            for k in (
                "upid",
                "UPID",
                "id_unidad",
                "nombre_centro_gestor",
                "centro_gestor",
                "nombreCentroGestor",
            )
        }
        print(f"campos clave props: {sample_p}")

print("\n=== Muestra INTERVENCIONES ===")
for i, d in enumerate(
    db.collection("intervenciones_unidades_proyecto").limit(3).stream()
):
    data = d.to_dict() or {}
    print(f"\n--- doc {i} id={d.id} ---")
    print(f"top-level keys: {sorted(data.keys())}")
    sample = {
        k: data.get(k)
        for k in (
            "upid",
            "UPID",
            "intervencion_id",
            "nombre_centro_gestor",
            "centro_gestor",
        )
    }
    print(f"campos clave: {sample}")

# Cuántas unidades tienen upid?
print("\n=== Estadísticas upid en unidades ===")
docs = list(db.collection("unidades_proyecto").stream())
with_upid_top = 0
with_upid_prop = 0
upids = []
for d in docs:
    data = d.to_dict() or {}
    upid = data.get("upid") or data.get("UPID")
    if not upid:
        props = data.get("properties") or {}
        if isinstance(props, dict):
            upid = props.get("upid") or props.get("UPID")
            if upid:
                with_upid_prop += 1
    else:
        with_upid_top += 1
    if upid:
        upids.append(str(upid).upper())
print(f"  total unidades: {len(docs)}")
print(f"  con upid en top-level: {with_upid_top}")
print(f"  con upid en properties: {with_upid_prop}")
print(f"  upids únicos: {len(set(upids))}")

# Cuántas intervenciones tienen upid y centro?
print("\n=== Estadísticas en intervenciones ===")
idocs = list(db.collection("intervenciones_unidades_proyecto").stream())
upid_centro = {}
no_upid = 0
no_centro = 0
for d in idocs:
    data = d.to_dict() or {}
    upid = (data.get("upid") or data.get("UPID") or "").strip().upper()
    centro = (
        data.get("nombre_centro_gestor") or data.get("centro_gestor") or ""
    ).strip()
    if not upid:
        no_upid += 1
    if not centro:
        no_centro += 1
    if upid and centro:
        upid_centro.setdefault(upid, Counter())[centro] += 1
print(f"  total intervenciones: {len(idocs)}")
print(f"  sin upid: {no_upid}")
print(f"  sin centro: {no_centro}")
print(f"  upids únicos con centro: {len(upid_centro)}")

# ¿Cuántos upids de unidades matchearán?
unidades_upids = set(upids)
matchable = unidades_upids & set(upid_centro.keys())
print(
    f"  upids de unidades que matchean con intervenciones: {len(matchable)} / {len(unidades_upids)}"
)

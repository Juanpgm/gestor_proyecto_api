"""Diagnose geometry types that fail shapely_shape."""
from main import get_firestore_client
from shapely.geometry import shape as S
from collections import Counter

db = get_firestore_client()
docs = db.collection('unidades_proyecto').stream()

type_counter = Counter()
errors = []
total = 0
for doc in docs:
    total += 1
    d = doc.to_dict()
    g = d.get('geometry')
    if not isinstance(g, dict) or not g.get('type'):
        type_counter['NO_GEOMETRY'] += 1
        continue
    gtype = g.get('type')
    type_counter[gtype] += 1
    try:
        S(g)
    except Exception as e:
        errors.append((d.get('upid'), gtype, str(e)[:100], str(g.get('coordinates', ''))[:150]))

print(f"Total docs: {total}")
print(f"\nGeometry types:")
for t, c in type_counter.most_common():
    print(f"  {t}: {c}")
print(f"\nErrors: {len(errors)}")
for upid, gtype, err, coords in errors[:10]:
    print(f"  {upid} type={gtype} err={err}")
    print(f"    coords: {coords}")

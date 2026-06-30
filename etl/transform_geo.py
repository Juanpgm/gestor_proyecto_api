"""Pure geometry transforms for the Firestore -> PostGIS ETL.

Firestore stores each unidad-de-proyecto geometry as GeoJSON, but the encoding
is inconsistent across the dataset: sometimes a dict, sometimes a JSON string,
occasionally a double-encoded string, and `coordinates` is itself sometimes a
JSON/`ast`-style string. These helpers normalise all of that into a clean
GeoJSON geometry dict that PostGIS can ingest via `ST_GeomFromGeoJSON`.

Everything here is side-effect free and DB-free, so it is unit-testable on its
own and reused by the load step and the geometry round-trip tests.
"""

from __future__ import annotations

import ast
import json
from typing import Any, Optional

# Geometry types we expect in the dataset (RFC 7946 names, as PostGIS emits them).
GEOJSON_GEOMETRY_TYPES = frozenset(
    {"Point", "MultiPoint", "LineString", "MultiLineString", "Polygon", "MultiPolygon"}
)

# Longitude/latitude valid ranges (WGS84 / EPSG:4326).
_LNG_MIN, _LNG_MAX = -180.0, 180.0
_LAT_MIN, _LAT_MAX = -90.0, 90.0


def _loads_maybe(value: Any) -> Any:
    """Parse a string as JSON, falling back to a Python literal (single quotes)."""
    if not isinstance(value, str):
        return value
    text = value.strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except (ValueError, TypeError):
        try:
            return ast.literal_eval(text)
        except (ValueError, SyntaxError):
            return None


def parse_geometry(raw: Any) -> Optional[dict]:
    """Normalise a raw Firestore geometry value into a GeoJSON geometry dict.

    Handles: dicts, JSON strings, double-encoded strings, and a `coordinates`
    field that is itself a string. Returns ``None`` when the value cannot be
    interpreted as a valid GeoJSON geometry (no type / no coordinates).
    """
    geom = _loads_maybe(raw)
    # Unwrap a second layer if the first parse still produced a string.
    if isinstance(geom, str):
        geom = _loads_maybe(geom)
    if not isinstance(geom, dict):
        return None

    gtype = geom.get("type")
    coords = geom.get("coordinates")
    if gtype not in GEOJSON_GEOMETRY_TYPES:
        return None

    if isinstance(coords, str):
        coords = _loads_maybe(coords)
    if coords is None:
        return None

    return {"type": gtype, "coordinates": coords}


def is_placeholder_point(geom: Optional[dict]) -> bool:
    """True when the geometry is the sentinel ``Point [0, 0]`` placeholder."""
    if not geom or geom.get("type") != "Point":
        return False
    coords = geom.get("coordinates")
    if not isinstance(coords, (list, tuple)) or len(coords) < 2:
        return False
    try:
        return float(coords[0]) == 0.0 and float(coords[1]) == 0.0
    except (TypeError, ValueError):
        return False


def _iter_positions(coords: Any):
    """Yield ``[lng, lat, ...]`` positions from an arbitrarily nested coord array."""
    if isinstance(coords, (list, tuple)):
        if coords and isinstance(coords[0], (int, float)):
            yield coords
        else:
            for item in coords:
                yield from _iter_positions(item)


def coordinates_in_range(geom: Optional[dict]) -> bool:
    """True when every position falls within valid WGS84 lng/lat ranges."""
    if not geom:
        return False
    try:
        positions = list(_iter_positions(geom.get("coordinates")))
    except TypeError:
        return False
    if not positions:
        return False
    for pos in positions:
        try:
            lng, lat = float(pos[0]), float(pos[1])
        except (TypeError, ValueError, IndexError):
            return False
        if not (_LNG_MIN <= lng <= _LNG_MAX and _LAT_MIN <= lat <= _LAT_MAX):
            return False
    return True


def to_geojson_str(geom: Optional[dict]) -> Optional[str]:
    """Serialise a parsed geometry to a compact GeoJSON string for PostGIS.

    Accepts the same raw inputs as :func:`parse_geometry` for convenience.
    Returns ``None`` when the geometry is unusable.
    """
    parsed = geom if (isinstance(geom, dict) and "type" in geom) else parse_geometry(geom)
    parsed = parse_geometry(parsed)
    if parsed is None:
        return None
    return json.dumps(parsed, separators=(",", ":"))

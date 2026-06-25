"""
Exportación geoespacial — tabla única (UP + Intervenciones) a varios formatos.
==============================================================================

Construye una tabla plana donde cada fila es una intervención con los datos de
su Unidad de Proyecto (incluida la geometría de la UP) y el ``upid`` que las
vincula. Las UP sin intervenciones salen igual como una fila.

Esa tabla se serializa, a elección, en:
  - GeoJSON  (.geojson)
  - KML      (.kml)
  - KMZ      (.kmz, = KML comprimido)
  - Shapefile(.zip con .shp/.shx/.dbf/.prj/.cpg; si hay geometrías mixtas se
              separa un shapefile por tipo, porque un .shp admite un solo tipo)

Es el inverso de la importación combinada: los nombres de columna se truncan a
10 chars en shapefile (límite DBF) coincidiendo con los alias de importación,
de modo que el archivo descargado se puede volver a cargar.

El módulo es PURO (no toca Firestore): recibe listas de dicts y devuelve bytes.
"""

from __future__ import annotations

import io
import json
import zipfile
from typing import Any, Dict, List, Optional
from xml.sax.saxutils import escape

# Orden canónico de columnas de la tabla exportada.
EXPORT_COLUMNS: List[str] = [
    "upid",
    "intervencion_id",
    "nombre_up",
    "nombre_up_detalle",
    "tipo_equipamiento",
    "clase_up",
    "tipo_intervencion",
    "presupuesto_base",
    "avance_obra",
    "fuente_financiacion",
    "nombre_centro_gestor",
    "comuna_corregimiento",
    "barrio_vereda",
    "direccion",
    "bpin",
    "identificador",
    "ano",
    "fecha_inicio",
    "fecha_fin",
    "cantidad",
    "unidad",
    "referencia_contrato",
    "referencia_proceso",
    "url_proceso",
    "descripcion_intervencion",
]

# Campos cuyo valor proviene de la INTERVENCIÓN (pisan al de la UP en la fila).
_INTERVENCION_COLUMNS = {
    "intervencion_id",
    "tipo_intervencion",
    "presupuesto_base",
    "fuente_financiacion",
    "nombre_centro_gestor",
    "identificador",
    "fecha_inicio",
    "fecha_fin",
    "cantidad",
    "unidad",
    "clase_up",
    "bpin",
    "referencia_contrato",
    "referencia_proceso",
    "url_proceso",
    "descripcion_intervencion",
}

# WKT de WGS84 (lat/lon) para el .prj del shapefile.
_WGS84_PRJ = (
    'GEOGCS["GCS_WGS_1984",DATUM["D_WGS_1984",SPHEROID["WGS_1984",'
    '6378137.0,298.257223563]],PRIMEM["Greenwich",0.0],'
    'UNIT["Degree",0.0174532925199433]]'
)


def _coerce_geometry(geom: Any) -> Optional[Dict[str, Any]]:
    """Devuelve una geometría GeoJSON con ``coordinates`` como array real.

    En Firestore las coordenadas a veces se guardan como STRING JSON
    (p.ej. ``"[[-76.5,3.4],...]"``); hay que parsearlas o ni GeoJSON ni KML ni
    shapefile saldrían con geometría. Devuelve None si es inusable.
    """
    if not isinstance(geom, dict) or not geom.get("type"):
        return None
    coords = geom.get("coordinates")
    if isinstance(coords, str):
        try:
            coords = json.loads(coords)
        except (json.JSONDecodeError, ValueError):
            return None
    if coords is None:
        return None
    return {"type": geom.get("type"), "coordinates": coords}


def build_flat_features(
    ups: List[Dict[str, Any]],
    intervenciones_by_upid: Dict[str, List[Dict[str, Any]]],
) -> List[Dict[str, Any]]:
    """Arma la tabla plana: una fila por intervención (o una por UP si no tiene).

    Cada fila es ``{"geometry": <geom de la UP>, "properties": {col: valor}}``
    con todas las columnas de :data:`EXPORT_COLUMNS`.
    """
    features: List[Dict[str, Any]] = []
    for up in ups:
        upid = up.get("upid")
        geom = _coerce_geometry(up.get("geometry"))
        base = {col: up.get(col) for col in EXPORT_COLUMNS}
        base["upid"] = upid
        base["intervencion_id"] = None

        ints = intervenciones_by_upid.get(str(upid), []) if upid is not None else []
        if not ints:
            features.append({"geometry": geom, "properties": dict(base)})
            continue

        for it in ints:
            props = dict(base)
            for col in _INTERVENCION_COLUMNS:
                val = it.get(col)
                if val is not None:
                    props[col] = val
            props["upid"] = upid  # el vínculo siempre el de la UP
            features.append({"geometry": geom, "properties": props})
    return features


# ─── GeoJSON ────────────────────────────────────────────────────────────────


def to_geojson(features: List[Dict[str, Any]]) -> bytes:
    fc = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": f.get("geometry"),
                "properties": {c: f["properties"].get(c) for c in EXPORT_COLUMNS},
            }
            for f in features
        ],
    }
    return json.dumps(fc, ensure_ascii=False).encode("utf-8")


# ─── KML / KMZ ────────────────────────────────────────────────────────────────


def _coords_str(coords: List[List[float]]) -> str:
    return " ".join(f"{c[0]},{c[1]}" for c in coords if len(c) >= 2)


def _geometry_to_kml(geom: Optional[Dict[str, Any]]) -> str:
    if not geom or not geom.get("type"):
        return ""
    gtype = geom["type"]
    coords = geom.get("coordinates")
    if coords is None:
        return ""
    if gtype == "Point":
        return f"<Point><coordinates>{coords[0]},{coords[1]}</coordinates></Point>"
    if gtype == "LineString":
        return f"<LineString><coordinates>{_coords_str(coords)}</coordinates></LineString>"
    if gtype == "Polygon":
        rings = "".join(
            f"<outerBoundaryIs><LinearRing><coordinates>{_coords_str(ring)}"
            f"</coordinates></LinearRing></outerBoundaryIs>"
            if i == 0
            else f"<innerBoundaryIs><LinearRing><coordinates>{_coords_str(ring)}"
            f"</coordinates></LinearRing></innerBoundaryIs>"
            for i, ring in enumerate(coords)
        )
        return f"<Polygon>{rings}</Polygon>"
    if gtype == "MultiPoint":
        parts = "".join(f"<Point><coordinates>{c[0]},{c[1]}</coordinates></Point>" for c in coords)
        return f"<MultiGeometry>{parts}</MultiGeometry>"
    if gtype == "MultiLineString":
        parts = "".join(
            f"<LineString><coordinates>{_coords_str(line)}</coordinates></LineString>"
            for line in coords
        )
        return f"<MultiGeometry>{parts}</MultiGeometry>"
    if gtype == "MultiPolygon":
        polys = "".join(_geometry_to_kml({"type": "Polygon", "coordinates": poly}) for poly in coords)
        return f"<MultiGeometry>{polys}</MultiGeometry>"
    return ""


def to_kml(features: List[Dict[str, Any]], doc_name: str = "Unidades de Proyecto") -> bytes:
    placemarks = []
    for f in features:
        props = f["properties"]
        name = escape(str(props.get("upid") or props.get("nombre_up") or ""))
        data = "".join(
            f'<Data name="{escape(col)}"><value>{escape("" if props.get(col) is None else str(props.get(col)))}</value></Data>'
            for col in EXPORT_COLUMNS
        )
        geom_kml = _geometry_to_kml(f.get("geometry"))
        placemarks.append(
            f"<Placemark><name>{name}</name>"
            f"<ExtendedData>{data}</ExtendedData>{geom_kml}</Placemark>"
        )
    kml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<kml xmlns="http://www.opengis.net/kml/2.2"><Document>'
        f"<name>{escape(doc_name)}</name>{''.join(placemarks)}"
        "</Document></kml>"
    )
    return kml.encode("utf-8")


def to_kmz(features: List[Dict[str, Any]], doc_name: str = "Unidades de Proyecto") -> bytes:
    kml_bytes = to_kml(features, doc_name)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("doc.kml", kml_bytes)
    return buf.getvalue()


# ─── Shapefile ────────────────────────────────────────────────────────────────

def _norm_points(seq: Any) -> List[List[float]]:
    """Filtra una secuencia a puntos válidos ``[x, y]``.

    Descarta coordenadas malformadas que aparecen en datos reales (puntos con un
    solo valor, no numéricos, etc.) y que harían fallar a pyshp al calcular el bbox.
    """
    out: List[List[float]] = []
    if not isinstance(seq, (list, tuple)):
        return out
    for p in seq:
        if (
            isinstance(p, (list, tuple))
            and len(p) >= 2
            and isinstance(p[0], (int, float))
            and isinstance(p[1], (int, float))
        ):
            out.append([float(p[0]), float(p[1])])
    return out


def _normalize_geometry(geom: Optional[Dict[str, Any]]):
    """Normaliza una geometría GeoJSON a ``(categoria, gtype, coords_limpias)``.

    Devuelve ``None`` si es inusable (sin tipo, vacía o malformada) para que el
    shapefile la escriba como shape NULA en vez de romper toda la exportación.
    """
    if not isinstance(geom, dict):
        return None
    gtype = geom.get("type")
    coords = geom.get("coordinates")
    if isinstance(coords, str):  # coords a veces vienen como string JSON
        try:
            coords = json.loads(coords)
        except (json.JSONDecodeError, ValueError):
            return None
    if coords is None:
        return None
    if gtype == "Point":
        if (
            isinstance(coords, (list, tuple))
            and len(coords) >= 2
            and isinstance(coords[0], (int, float))
            and isinstance(coords[1], (int, float))
        ):
            return ("point", "Point", [float(coords[0]), float(coords[1])])
        return None
    if gtype == "MultiPoint":
        pts = _norm_points(coords)
        return ("point", "MultiPoint", pts) if pts else None
    if gtype == "LineString":
        pts = _norm_points(coords)
        return ("line", "LineString", pts) if len(pts) >= 2 else None
    if gtype == "MultiLineString":
        seq = coords if isinstance(coords, (list, tuple)) else []
        parts = [p for p in (_norm_points(line) for line in seq) if len(p) >= 2]
        return ("line", "MultiLineString", parts) if parts else None
    if gtype == "Polygon":
        seq = coords if isinstance(coords, (list, tuple)) else []
        rings = [r for r in (_norm_points(ring) for ring in seq) if len(r) >= 3]
        return ("polygon", "Polygon", rings) if rings else None
    if gtype == "MultiPolygon":
        polys = []
        for poly in coords if isinstance(coords, (list, tuple)) else []:
            seq = poly if isinstance(poly, (list, tuple)) else []
            rings = [r for r in (_norm_points(ring) for ring in seq) if len(r) >= 3]
            if rings:
                polys.append(rings)
        return ("polygon", "MultiPolygon", polys) if polys else None
    return None


def _dbf_field_names(columns: List[str]) -> Dict[str, str]:
    """Trunca nombres a 10 chars (límite DBF) y resuelve colisiones."""
    used = set()
    mapping: Dict[str, str] = {}
    for col in columns:
        base = col[:10]
        name = base
        i = 1
        while name in used:
            suffix = str(i)
            name = base[: 10 - len(suffix)] + suffix
            i += 1
        used.add(name)
        mapping[col] = name
    return mapping


def _write_geometry(w, norm) -> None:
    """Escribe la geometría normalizada en el writer pyshp (o NULA si no hay)."""
    if norm is None:
        w.null()
        return
    _, gtype, coords = norm
    if gtype == "Point":
        w.point(coords[0], coords[1])
    elif gtype == "MultiPoint":
        w.multipoint(coords)
    elif gtype == "LineString":
        w.line([coords])
    elif gtype == "MultiLineString":
        w.line(coords)
    elif gtype == "Polygon":
        w.poly(coords)
    elif gtype == "MultiPolygon":
        w.poly([ring for poly in coords for ring in poly])
    else:
        w.null()


def _write_one_shapefile(category: str, items: List[Any]):
    """Escribe un shapefile para una categoría homogénea.

    ``items`` es una lista de ``(norm, properties)`` donde ``norm`` es la geometría
    ya normalizada (o ``None``). Devuelve ``{ext: bytes}``.
    """
    import shapefile  # pyshp

    shape_type = {
        "point": shapefile.POINT,
        "line": shapefile.POLYLINE,
        "polygon": shapefile.POLYGON,
        "none": shapefile.NULL,
    }[category]

    shp, shx, dbf = io.BytesIO(), io.BytesIO(), io.BytesIO()
    w = shapefile.Writer(shp=shp, shx=shx, dbf=dbf, shapeType=shape_type)

    names = _dbf_field_names(EXPORT_COLUMNS)
    # Tamaño por campo en BYTES (no caracteres): el DBF mide en bytes y el texto en
    # español lleva tildes/ñ multibyte en UTF-8; usar len() perdería caracteres.
    sizes: Dict[str, int] = {}
    for col in EXPORT_COLUMNS:
        maxlen = 1
        for _norm, props in items:
            v = props.get(col)
            if v is not None:
                maxlen = max(maxlen, len(str(v).encode("utf-8")))
        sizes[col] = min(254, maxlen)
    for col in EXPORT_COLUMNS:
        w.field(names[col], "C", size=sizes[col])

    for norm, props in items:
        _write_geometry(w, norm)
        rec = ["" if props.get(c) is None else str(props.get(c)) for c in EXPORT_COLUMNS]
        w.record(*rec)

    w.close()
    return {"shp": shp.getvalue(), "shx": shx.getvalue(), "dbf": dbf.getvalue()}


def to_shapefile_zip(features: List[Dict[str, Any]], base_name: str = "unidades_proyecto") -> bytes:
    """Agrupa por tipo de geometría y devuelve un .zip con un shapefile por tipo.

    Normaliza cada geometría primero; las inusables/malformadas se exportan como
    shape NULA (no rompen la descarga).
    """
    groups: Dict[str, List[Any]] = {}
    for f in features:
        norm = _normalize_geometry(f.get("geometry"))
        cat = norm[0] if norm else "none"
        groups.setdefault(cat, []).append((norm, f.get("properties", {})))

    multi = len(groups) > 1
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for cat, feats in groups.items():
            parts = _write_one_shapefile(cat, feats)
            stem = f"{base_name}_{cat}" if multi else base_name
            zf.writestr(f"{stem}.shp", parts["shp"])
            zf.writestr(f"{stem}.shx", parts["shx"])
            zf.writestr(f"{stem}.dbf", parts["dbf"])
            zf.writestr(f"{stem}.prj", _WGS84_PRJ.encode("utf-8"))
            zf.writestr(f"{stem}.cpg", b"UTF-8")
    return buf.getvalue()


# ─── Dispatcher ───────────────────────────────────────────────────────────────

# formato -> (media_type, extensión de archivo)
FORMAT_SPEC = {
    "geojson": ("application/geo+json", "geojson"),
    "kml": ("application/vnd.google-earth.kml+xml", "kml"),
    "kmz": ("application/vnd.google-earth.kmz", "kmz"),
    "shp": ("application/zip", "zip"),
}


def export_features(features: List[Dict[str, Any]], formato: str, base_name: str) -> bytes:
    if formato == "geojson":
        return to_geojson(features)
    if formato == "kml":
        return to_kml(features, base_name)
    if formato == "kmz":
        return to_kmz(features, base_name)
    if formato == "shp":
        return to_shapefile_zip(features, base_name)
    raise ValueError(f"Formato no soportado: {formato}")

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
    "estado",
    "presupuesto_base",
    "avance_obra",
    "fuente_financiacion",
    "nombre_centro_gestor",
    "comuna_corregimiento",
    "barrio_vereda",
    "frente_activo",
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
    "estado",
    "presupuesto_base",
    "avance_obra",
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
        geom = up.get("geometry")
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

_GEOM_CATEGORY = {
    "Point": "point",
    "MultiPoint": "point",
    "LineString": "line",
    "MultiLineString": "line",
    "Polygon": "polygon",
    "MultiPolygon": "polygon",
}


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


def _write_one_shapefile(category: str, feats: List[Dict[str, Any]]):
    """Devuelve dict {ext: bytes} para una categoría de geometría homogénea."""
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
        for f in feats:
            v = f["properties"].get(col)
            if v is not None:
                maxlen = max(maxlen, len(str(v).encode("utf-8")))
        sizes[col] = min(254, maxlen)
    for col in EXPORT_COLUMNS:
        w.field(names[col], "C", size=sizes[col])

    for f in feats:
        geom = f.get("geometry") or {}
        gtype = geom.get("type")
        coords = geom.get("coordinates")
        if category == "point" and coords is not None:
            if gtype == "Point":
                w.point(coords[0], coords[1])
            else:  # MultiPoint
                w.multipoint(coords)
        elif category == "line" and coords is not None:
            lines = coords if gtype == "MultiLineString" else [coords]
            w.line(lines)
        elif category == "polygon" and coords is not None:
            parts = [ring for poly in coords for ring in poly] if gtype == "MultiPolygon" else coords
            w.poly(parts)
        else:
            w.null()
        rec = ["" if f["properties"].get(c) is None else str(f["properties"].get(c)) for c in EXPORT_COLUMNS]
        w.record(*rec)

    w.close()
    return {"shp": shp.getvalue(), "shx": shx.getvalue(), "dbf": dbf.getvalue()}


def to_shapefile_zip(features: List[Dict[str, Any]], base_name: str = "unidades_proyecto") -> bytes:
    """Agrupa por tipo de geometría y devuelve un .zip con un shapefile por tipo."""
    groups: Dict[str, List[Dict[str, Any]]] = {}
    for f in features:
        gtype = (f.get("geometry") or {}).get("type")
        cat = _GEOM_CATEGORY.get(gtype, "none")
        groups.setdefault(cat, []).append(f)

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

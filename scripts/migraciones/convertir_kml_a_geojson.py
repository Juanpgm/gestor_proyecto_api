"""
Convierte basemaps/proyectos_estrategicos/POLIGONOS EXPANDIDOS.kml a GeoJSON.
El archivo resultante queda en la misma carpeta como POLIGONOS_EXPANDIDOS.geojson
con propiedad "Name" por feature, compatible con _buscar_proyectos_estrategicos().
"""

import json
import os
import xml.etree.ElementTree as ET

KML_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "basemaps", "proyectos_estrategicos", "POLIGONOS EXPANDIDOS.kml",
)
GEOJSON_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "basemaps", "proyectos_estrategicos", "POLIGONOS_EXPANDIDOS.geojson",
)

NS = {"kml": "http://www.opengis.net/kml/2.2"}


def parse_coordinates(text: str) -> list:
    """Parsea string de coordenadas KML (lon,lat,alt) a lista GeoJSON [[lon, lat], ...]."""
    ring = []
    for triplet in text.strip().split():
        parts = triplet.split(",")
        lon, lat = float(parts[0]), float(parts[1])
        ring.append([lon, lat])
    return ring


def kml_to_geojson(kml_path: str) -> dict:
    tree = ET.parse(kml_path)
    root = tree.getroot()

    features = []
    for placemark in root.findall(".//kml:Placemark", NS):
        name_el = placemark.find("kml:name", NS)
        name = name_el.text.strip() if name_el is not None and name_el.text else ""

        polygon_el = placemark.find(".//kml:Polygon/kml:outerBoundaryIs/kml:LinearRing/kml:coordinates", NS)
        if polygon_el is None or not polygon_el.text:
            continue

        ring = parse_coordinates(polygon_el.text)

        feature = {
            "type": "Feature",
            "properties": {"Name": "Microterritorios", "Description": name},
            "geometry": {
                "type": "Polygon",
                "coordinates": [ring],
            },
        }
        features.append(feature)

    return {
        "type": "FeatureCollection",
        "name": "POLIGONOS_EXPANDIDOS",
        "crs": {
            "type": "name",
            "properties": {"name": "urn:ogc:def:crs:OGC:1.3:CRS84"},
        },
        "features": features,
    }


if __name__ == "__main__":
    geojson = kml_to_geojson(KML_PATH)
    with open(GEOJSON_PATH, "w", encoding="utf-8") as f:
        json.dump(geojson, f, ensure_ascii=False, indent=2)
    print(f"Convertidos {len(geojson['features'])} polígonos")
    for feat in geojson["features"]:
        print(f"  - {feat['properties']['Name']}")
    print(f"Guardado en: {GEOJSON_PATH}")

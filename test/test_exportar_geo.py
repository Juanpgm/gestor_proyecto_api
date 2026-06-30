"""
Tests — Exportación geoespacial (tabla única UP + intervenciones).
==================================================================
Cubre:
  - build_flat_features (1:N, UP sin intervención).
  - Serializadores: GeoJSON, KML, KMZ, Shapefile (incl. geometrías mixtas).
  - Endpoint GET /unidades-proyecto/exportar (formato + scoping por centro).
"""

import io
import json
import zipfile
from collections import defaultdict
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
import sys, os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from api.exportar_geo import (
    EXPORT_COLUMNS,
    build_flat_features,
    to_geojson,
    to_kml,
    to_kmz,
    to_shapefile_zip,
)

PT = {"type": "Point", "coordinates": [-76.53, 3.45]}
LN = {"type": "LineString", "coordinates": [[-76.53, 3.45], [-76.54, 3.46]]}


# ─── build_flat_features ───────────────────────────────────────────────────────


class TestBuildFlat:
    def test_una_up_con_dos_intervenciones(self):
        ups = [{"upid": "UNP-1", "nombre_up": "Parque", "geometry": PT}]
        ints = {
            "UNP-1": [
                {"upid": "UNP-1", "intervencion_id": "UNP-1-INT-1", "tipo_intervencion": "Bacheo"},
                {"upid": "UNP-1", "intervencion_id": "UNP-1-INT-2", "tipo_intervencion": "Pavimento"},
            ]
        }
        feats = build_flat_features(ups, ints)
        assert len(feats) == 2
        # Ambas filas llevan la geometría y el upid de la UP
        for f in feats:
            assert f["geometry"] == PT
            assert f["properties"]["upid"] == "UNP-1"
            assert f["properties"]["nombre_up"] == "Parque"
        assert {f["properties"]["intervencion_id"] for f in feats} == {
            "UNP-1-INT-1",
            "UNP-1-INT-2",
        }
        assert {f["properties"]["tipo_intervencion"] for f in feats} == {"Bacheo", "Pavimento"}

    def test_up_sin_intervencion_es_una_fila(self):
        ups = [{"upid": "UNP-2", "nombre_up": "Vacía", "geometry": None}]
        feats = build_flat_features(ups, {})
        assert len(feats) == 1
        assert feats[0]["properties"]["intervencion_id"] is None
        assert feats[0]["properties"]["upid"] == "UNP-2"

    def test_todas_las_columnas_presentes(self):
        ups = [{"upid": "UNP-3", "geometry": PT}]
        feats = build_flat_features(ups, {})
        assert set(feats[0]["properties"].keys()) == set(EXPORT_COLUMNS)


# ─── Serializadores ────────────────────────────────────────────────────────────


def _sample_feats():
    return build_flat_features(
        [{"upid": "UNP-1", "nombre_up": "Parque", "geometry": PT}],
        {"UNP-1": [{"upid": "UNP-1", "intervencion_id": "UNP-1-INT-1", "presupuesto_base": 500}]},
    )


class TestSerializers:
    def test_geojson_estructura(self):
        data = json.loads(to_geojson(_sample_feats()).decode("utf-8"))
        assert data["type"] == "FeatureCollection"
        assert len(data["features"]) == 1
        feat = data["features"][0]
        assert feat["geometry"] == PT
        assert feat["properties"]["upid"] == "UNP-1"
        assert feat["properties"]["presupuesto_base"] == 500

    def test_geojson_parsea_coordenadas_string(self):
        # En Firestore las coords a veces son string JSON; deben salir como array.
        feats = build_flat_features(
            [
                {
                    "upid": "U",
                    "geometry": {
                        "type": "LineString",
                        "coordinates": "[[-76.5, 3.4], [-76.6, 3.5]]",
                    },
                }
            ],
            {},
        )
        g = json.loads(to_geojson(feats).decode("utf-8"))["features"][0]["geometry"]
        assert g["type"] == "LineString"
        assert g["coordinates"] == [[-76.5, 3.4], [-76.6, 3.5]]

    def test_shapefile_con_coordenadas_string_tiene_geometria(self):
        import shapefile

        feats = build_flat_features(
            [
                {
                    "upid": "U",
                    "nombre_up": "x",
                    "geometry": {"type": "Point", "coordinates": "[-76.5, 3.4]"},
                }
            ],
            {},
        )
        out = to_shapefile_zip(feats, "t")
        zf = zipfile.ZipFile(io.BytesIO(out))
        stem = next(n[:-4] for n in zf.namelist() if n.endswith(".shp"))
        r = shapefile.Reader(
            shp=io.BytesIO(zf.read(stem + ".shp")),
            dbf=io.BytesIO(zf.read(stem + ".dbf")),
            shx=io.BytesIO(zf.read(stem + ".shx")),
        )
        assert r.shapeTypeName == "POINT"
        assert len(r.shape(0).points) == 1  # geometría presente, no nula

    def test_kml_tiene_placemark_y_coords(self):
        out = to_kml(_sample_feats()).decode("utf-8")
        assert out.startswith("<?xml")
        assert "<Placemark>" in out
        assert "-76.53,3.45" in out
        assert "UNP-1" in out

    def test_kmz_es_zip_con_doc_kml(self):
        out = to_kmz(_sample_feats())
        zf = zipfile.ZipFile(io.BytesIO(out))
        assert "doc.kml" in zf.namelist()
        assert b"<Placemark>" in zf.read("doc.kml")

    def test_shapefile_zip_legible(self):
        import shapefile

        out = to_shapefile_zip(_sample_feats(), base_name="test")
        zf = zipfile.ZipFile(io.BytesIO(out))
        names = zf.namelist()
        assert any(n.endswith(".shp") for n in names)
        assert any(n.endswith(".dbf") for n in names)
        assert any(n.endswith(".prj") for n in names)
        stem = next(n[:-4] for n in names if n.endswith(".shp"))
        r = shapefile.Reader(
            shp=io.BytesIO(zf.read(stem + ".shp")),
            dbf=io.BytesIO(zf.read(stem + ".dbf")),
            shx=io.BytesIO(zf.read(stem + ".shx")),
        )
        assert len(r) == 1
        rec = r.record(0).as_dict()
        # upid se exporta (nombre intacto, <=10 chars)
        assert rec.get("upid") == "UNP-1"

    def test_shapefile_conserva_tildes(self):
        # El tamaño de campo DBF se mide en bytes: "Vía"/"ñ" son multibyte en UTF-8.
        import shapefile

        feats = build_flat_features(
            [{"upid": "U", "nombre_up": "Vía local ñ", "geometry": PT}], {}
        )
        out = to_shapefile_zip(feats, "t")
        zf = zipfile.ZipFile(io.BytesIO(out))
        stem = next(n[:-4] for n in zf.namelist() if n.endswith(".shp"))
        r = shapefile.Reader(
            shp=io.BytesIO(zf.read(stem + ".shp")),
            dbf=io.BytesIO(zf.read(stem + ".dbf")),
            shx=io.BytesIO(zf.read(stem + ".shx")),
        )
        assert r.record(0).as_dict()["nombre_up"] == "Vía local ñ"

    def test_shapefile_tolera_geometrias_malformadas(self):
        # Reproduce el 500 de prod: una línea con un punto de un solo valor reventaba
        # pyshp en el cálculo del bbox. Ahora se sanea y no debe lanzar.
        import shapefile

        feats = build_flat_features(
            [
                {"upid": "OK", "nombre_up": "buena", "geometry": LN},
                {"upid": "BAD1", "nombre_up": "linea mala", "geometry": {"type": "LineString", "coordinates": [[-76.5, 3.4], [-76.5]]}},
                {"upid": "BAD2", "nombre_up": "punto malo", "geometry": {"type": "Point", "coordinates": [-76.5]}},
                {"upid": "BAD3", "nombre_up": "vacia", "geometry": {"type": "LineString", "coordinates": []}},
            ],
            {},
        )
        out = to_shapefile_zip(feats, "t")  # no debe lanzar
        zf = zipfile.ZipFile(io.BytesIO(out))
        # Todas las filas se exportan (las malas como geometría nula): 4 registros en total
        total = 0
        for n in zf.namelist():
            if n.endswith(".shp"):
                stem = n[:-4]
                r = shapefile.Reader(
                    shp=io.BytesIO(zf.read(stem + ".shp")),
                    dbf=io.BytesIO(zf.read(stem + ".dbf")),
                    shx=io.BytesIO(zf.read(stem + ".shx")),
                )
                total += len(r)
        assert total == 4

    def test_shapefile_geometrias_mixtas_se_separan(self):
        feats = build_flat_features(
            [
                {"upid": "P1", "nombre_up": "punto", "geometry": PT},
                {"upid": "L1", "nombre_up": "linea", "geometry": LN},
            ],
            {},
        )
        out = to_shapefile_zip(feats, base_name="mix")
        names = zipfile.ZipFile(io.BytesIO(out)).namelist()
        shps = [n for n in names if n.endswith(".shp")]
        # un shapefile por tipo de geometría
        assert len(shps) == 2
        assert any("point" in n for n in shps)
        assert any("line" in n for n in shps)


# ─── Firestore en memoria (FakeDB) ─────────────────────────────────────────────


class _FakeDoc:
    def __init__(self, data):
        self._data = dict(data)

    def to_dict(self):
        return dict(self._data)


class _FakeQuery:
    def __init__(self, docs):
        self._docs = list(docs)

    def where(self, field, op, value):
        return _FakeQuery([d for d in self._docs if d.get(field) == value])

    def stream(self):
        return iter(_FakeDoc(d) for d in self._docs)


class _FakeCollection:
    def __init__(self, store, name):
        self._store = store
        self._name = name

    def where(self, field, op, value):
        return _FakeQuery(list(self._store[self._name].values())).where(field, op, value)

    def stream(self):
        return _FakeQuery(list(self._store[self._name].values())).stream()


class FakeDB:
    def __init__(self):
        self.store = defaultdict(dict)

    def collection(self, name):
        return _FakeCollection(self.store, name)


@pytest.fixture
def export_client():
    from main import app

    fake_db = FakeDB()
    fake_db.store["unidades_proyecto"]["UNP-1"] = {
        "upid": "UNP-1",
        "nombre_up": "Parque",
        "nombre_centro_gestor": "DAGMA",
        "geometry": PT,
    }
    fake_db.store["intervenciones_unidades_proyecto"]["UNP-1-INT-1"] = {
        "upid": "UNP-1",
        "intervencion_id": "UNP-1-INT-1",
        "tipo_intervencion": "Bacheo",
        "nombre_centro_gestor": "DAGMA",
    }

    async def _fake_user(request):
        user = {
            "uid": "test_super_admin",
            "email": "admin@cali.gov.co",
            "roles": ["super_admin"],
            "is_active": True,
            "nombre_centro_gestor": None,
            "name": "Test Admin",
            "permissions": ["*"],
        }
        request.state.current_user = user
        return user

    patches = [
        patch(
            "firebase_admin.auth.verify_id_token",
            return_value={"uid": "test_super_admin", "email": "admin@cali.gov.co", "email_verified": True},
        ),
        patch("auth_system.decorators.get_user_with_permissions", side_effect=_fake_user),
        patch("api.routers.unidades_proyecto.get_firestore_client", return_value=fake_db),
    ]
    for p in patches:
        p.start()
    client = TestClient(app, raise_server_exceptions=False)
    client.headers.update({"Authorization": "Bearer test_token"})
    try:
        yield client, fake_db
    finally:
        for p in patches:
            p.stop()


class TestExportEndpoint:
    def test_geojson_descarga_tabla_unica(self, export_client):
        client, _ = export_client
        resp = client.get("/unidades-proyecto/exportar?formato=geojson")
        assert resp.status_code == 200, resp.text[:300]
        assert "geo+json" in resp.headers.get("content-type", "")
        assert "attachment" in resp.headers.get("content-disposition", "")
        data = resp.json()
        assert data["type"] == "FeatureCollection"
        assert len(data["features"]) == 1
        assert data["features"][0]["properties"]["upid"] == "UNP-1"
        assert data["features"][0]["properties"]["intervencion_id"] == "UNP-1-INT-1"

    def test_formato_invalido_400(self, export_client):
        client, _ = export_client
        resp = client.get("/unidades-proyecto/exportar?formato=xlsx")
        assert resp.status_code == 400

    def test_shp_devuelve_zip(self, export_client):
        client, _ = export_client
        resp = client.get("/unidades-proyecto/exportar?formato=shp")
        assert resp.status_code == 200, resp.text[:200]
        assert resp.headers.get("content-type") == "application/zip"
        zf = zipfile.ZipFile(io.BytesIO(resp.content))
        assert any(n.endswith(".shp") for n in zf.namelist())

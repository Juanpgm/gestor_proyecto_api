"""Isolated LOCAL API serving migrated data from PostgreSQL + PostGIS.

This app exists ONLY to test the v3 migration locally against the real Postgres
data, fully isolated from production:
  * imports NO Firebase and NO auth_system -> it physically cannot touch the
    production Firestore project,
  * reads only from the database in DATABASE_URL (local Docker by default),
  * no authentication (local-only; never deploy this).

Run:  uvicorn pg_app:app --port 8000   (with DATA_BACKEND=postgres)
The Next.js front can point NEXT_PUBLIC_API_BASE_URL at http://localhost:8000.

The actual read logic lives in ``infrastructure.postgres.unidades_read`` so this
isolated app and the full backend's ``/unidades-proyecto`` endpoint share one
implementation and never drift apart.
"""

from __future__ import annotations

from typing import Optional

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

from core_db.settings import get_db_settings
from domain.geospatial.entities import UPQuery
from infrastructure.postgres.unidades_read import fetch_enriched

app = FastAPI(
    title="CaliTrack — Local Postgres (isolated)",
    description="Read-only local API over the migrated PostGIS data. No Firebase, no auth.",
    version="3.0.0-local",
)

# The Next.js dev server (and its proxy) runs on :3000.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict:
    settings = get_db_settings()
    return {
        "status": "ok",
        "backend": settings.data_backend,
        "isolated": True,
        "firebase": False,
    }


@app.get("/unidades-proyecto", tags=["Unidades de Proyecto"])
async def consultar_unidades_proyecto(
    nombre_centro_gestor: Optional[str] = Query(None),
    only_valid_geometry: bool = Query(False),
    limit: Optional[int] = Query(None, ge=1, le=20000),
    offset: int = Query(0, ge=0),
) -> dict:
    """Master endpoint, served from Postgres. Same envelope as the legacy API
    ({success, data, count}) so the existing front consumes it unchanged. Each
    item is enriched with UP-level consolidated intervención fields."""
    query = UPQuery(
        centro_gestor=nombre_centro_gestor,
        only_valid_geometry=only_valid_geometry,
        limit=limit,
        offset=offset,
    )
    data, total = await fetch_enriched(query)
    return {"success": True, "count": total, "data": data, "source": "postgres"}


@app.get("/unidades-proyecto/geojson", tags=["Unidades de Proyecto"])
async def unidades_proyecto_geojson(
    nombre_centro_gestor: Optional[str] = Query(None),
    only_valid_geometry: bool = Query(True),
    limit: Optional[int] = Query(None, ge=1, le=20000),
    offset: int = Query(0, ge=0),
) -> dict:
    """GeoJSON FeatureCollection from PostGIS, with consolidated estado/avance/
    frente_activo in each feature's properties so the map can colour by them."""
    query = UPQuery(
        centro_gestor=nombre_centro_gestor,
        only_valid_geometry=only_valid_geometry,
        limit=limit,
        offset=offset,
    )
    data, _ = await fetch_enriched(query)
    features = []
    for d in data:
        geometry = d.pop("geometry", None)
        features.append({"type": "Feature", "geometry": geometry, "properties": d})
    return {"type": "FeatureCollection", "features": features}

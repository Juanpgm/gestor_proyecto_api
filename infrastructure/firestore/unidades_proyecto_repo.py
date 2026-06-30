"""Firestore read-only adapter for UnidadesProyectoRepository.

The Firestore client is synchronous/blocking. Every method that touches
Firestore offloads the IO to a worker thread via asyncio.to_thread so the
event loop is never blocked. Mapping (firestore_to_unidad) is pure and runs
inline after the thread returns.

Filtering (centro_gestor, only_valid_geometry, limit/offset) is applied in
Python after full collection retrieval — Firestore has no cheap server-side
count and its query API does not support the accent-insensitive matching the
domain requires.

upsert() raises NotImplementedError: this adapter is read-only in v3 parity
mode and must never write to production Firestore.
"""

from __future__ import annotations

import asyncio
import unicodedata
from typing import Any, Optional

from domain.geospatial.entities import UnidadProyecto, UPQuery
from etl.extract import COLLECTION_UNIDADES, get_firestore_db
from etl.transform import firestore_to_unidad


# ---------------------------------------------------------------------------
# Accent/case normaliser — mirrors infrastructure.postgres.unidades_read._norm
# so centro_gestor filtering behaves consistently across adapters.
# ---------------------------------------------------------------------------

def _norm(value: object) -> str:
    """Accent-insensitive, case-insensitive, space-collapsed comparison key."""
    if value is None:
        return ""
    text = unicodedata.normalize("NFKD", str(value))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return " ".join(text.casefold().split())


# ---------------------------------------------------------------------------
# Synchronous helpers (run inside asyncio.to_thread)
# ---------------------------------------------------------------------------

def _fetch_all_docs(db) -> list[dict[str, Any]]:
    docs: list[dict[str, Any]] = []
    for snap in db.collection(COLLECTION_UNIDADES).stream():
        data = snap.to_dict() or {}
        data.setdefault("_id", snap.id)
        docs.append(data)
    return docs


def _fetch_single_doc(db, upid: str) -> Optional[dict[str, Any]]:
    snap = db.collection(COLLECTION_UNIDADES).document(upid).get()
    if not snap.exists:
        return None
    data = snap.to_dict() or {}
    data.setdefault("_id", snap.id)
    return data


# ---------------------------------------------------------------------------
# Repository
# ---------------------------------------------------------------------------

class FirestoreUnidadesProyectoRepository:
    """Read-only Firestore adapter implementing UnidadesProyectoRepository.

    Args:
        db: An existing Firestore client. Pass ``None`` (default) to have the
            repository lazily resolve credentials via ``get_firestore_db()``
            on the first call. Inject an explicit client in tests.
    """

    def __init__(self, db=None) -> None:
        self._db = db

    def _get_db(self):
        if self._db is None:
            self._db = get_firestore_db()
        return self._db

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _all_mapped(self) -> list[UnidadProyecto]:
        """Fetch every document from Firestore and map to domain entities."""
        db = self._get_db()
        raw = await asyncio.to_thread(_fetch_all_docs, db)
        return [firestore_to_unidad(doc) for doc in raw]

    def _apply_filters(
        self,
        units: list[UnidadProyecto],
        query: UPQuery,
        paginate: bool = True,
    ) -> list[UnidadProyecto]:
        """Apply UPQuery predicates in Python after retrieval.

        centro_gestor filtering uses accent/case-insensitive comparison to
        mirror infrastructure.postgres.unidades_read.filter_unidades._norm.

        only_valid_geometry approximates the PostGIS generated column
        has_valid_geometry as ``geometry is not None`` (the Firestore side
        does not compute PostGIS validity, but a non-null geometry dict is
        the meaningful proxy).
        """
        if query.centro_gestor is not None:
            target = _norm(query.centro_gestor)
            units = [u for u in units if _norm(u.centro_gestor) == target]

        if query.only_valid_geometry:
            units = [u for u in units if u.geometry is not None]

        if paginate:
            units = units[query.offset :]
            if query.limit is not None:
                units = units[: query.limit]

        return units

    # ------------------------------------------------------------------
    # Port implementation
    # ------------------------------------------------------------------

    async def get(self, upid: str) -> Optional[UnidadProyecto]:
        db = self._get_db()
        raw = await asyncio.to_thread(_fetch_single_doc, db, upid)
        return firestore_to_unidad(raw) if raw is not None else None

    async def list(self, query: UPQuery = UPQuery()) -> list[UnidadProyecto]:
        units = await self._all_mapped()
        return self._apply_filters(units, query)

    async def count(self, query: UPQuery = UPQuery()) -> int:
        """Count matching unidades (no cheap server-side count in Firestore)."""
        units = await self._all_mapped()
        return len(self._apply_filters(units, query, paginate=False))

    async def upsert(self, up: UnidadProyecto) -> None:
        raise NotImplementedError(
            "Firestore adapter is read-only in v3 parity mode"
        )

    async def as_feature_collection(self, query: UPQuery = UPQuery()) -> dict:
        """Return a GeoJSON FeatureCollection matching the Postgres adapter's shape.

        Scalar numeric fields (presupuesto_base) are converted to float for JSON
        serialisation. Date fields are ISO-formatted strings. geometry_type is
        None for Firestore entities (PostGIS generated column, not available here).
        """
        units = await self.list(query)
        features = []
        for up in units:
            props = {
                "upid": up.upid,
                "nombre_up": up.nombre_up,
                "direccion": up.direccion,
                "barrio_vereda": up.barrio_vereda,
                "comuna_corregimiento": up.comuna_corregimiento,
                "municipio": up.municipio,
                "departamento": up.departamento,
                "tipo_equipamiento": up.tipo_equipamiento,
                "clase_up": up.clase_up,
                "centro_gestor": up.centro_gestor,
                "presupuesto_base": (
                    float(up.presupuesto_base)
                    if up.presupuesto_base is not None
                    else None
                ),
                "fuente_financiacion": up.fuente_financiacion,
                "ano": up.ano,
                "fecha_inicio": (
                    up.fecha_inicio.isoformat() if up.fecha_inicio is not None else None
                ),
                "fecha_fin": (
                    up.fecha_fin.isoformat() if up.fecha_fin is not None else None
                ),
                "bpin": up.bpin,
                "referencia_contrato": up.referencia_contrato,
                "referencia_proceso": up.referencia_proceso,
                "plataforma": up.plataforma,
                "geometry_type": up.geometry_type,
                "has_valid_geometry": up.has_valid_geometry,
            }
            features.append(
                {
                    "type": "Feature",
                    "geometry": up.geometry,
                    "properties": props,
                }
            )
        return {"type": "FeatureCollection", "features": features}

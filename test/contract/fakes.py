"""In-memory fake repositories implementing the geospatial ports.

Pure Python, no I/O. They let the contract suite run the SAME assertions
against a trivial reference implementation and against the real Postgres
adapter, proving both honour the port contract identically.
"""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal
from typing import Optional

from domain.geospatial.entities import (
    Avance,
    Intervencion,
    UnidadProyecto,
    UPQuery,
    recompute_avance_cache,
)


def _feature(up: UnidadProyecto) -> dict:
    props = {
        "upid": up.upid,
        "nombre_up": up.nombre_up,
        "centro_gestor": up.centro_gestor,
        "presupuesto_base": float(up.presupuesto_base) if up.presupuesto_base is not None else None,
        "ano": up.ano,
        "geometry_type": up.geometry_type,
        "has_valid_geometry": up.has_valid_geometry,
    }
    return {"type": "Feature", "geometry": up.geometry, "properties": props}


class InMemoryUnidadesProyectoRepository:
    def __init__(self) -> None:
        self._store: dict[str, UnidadProyecto] = {}

    def _filtered(self, query: UPQuery) -> list[UnidadProyecto]:
        items = list(self._store.values())
        if query.centro_gestor is not None:
            items = [u for u in items if u.centro_gestor == query.centro_gestor]
        if query.only_valid_geometry:
            items = [u for u in items if u.has_valid_geometry]
        items.sort(key=lambda u: u.upid)
        return items

    async def get(self, upid: str) -> Optional[UnidadProyecto]:
        return self._store.get(upid)

    async def list(self, query: UPQuery = UPQuery()) -> list[UnidadProyecto]:
        items = self._filtered(query)
        if query.offset:
            items = items[query.offset:]
        if query.limit is not None:
            items = items[: query.limit]
        return items

    async def count(self, query: UPQuery = UPQuery()) -> int:
        return len(self._filtered(query))

    async def upsert(self, up: UnidadProyecto) -> None:
        self._store[up.upid] = up

    async def as_feature_collection(self, query: UPQuery = UPQuery()) -> dict:
        ups = await self.list(query)
        return {"type": "FeatureCollection", "features": [_feature(u) for u in ups]}


class InMemoryIntervencionesRepository:
    def __init__(self) -> None:
        self._interv: dict[str, Intervencion] = {}
        self._avances: list[Avance] = []

    async def list_by_up(self, upid: str) -> list[Intervencion]:
        return sorted(
            (i for i in self._interv.values() if i.upid == upid),
            key=lambda i: i.intervencion_id,
        )

    async def upsert(self, intervencion: Intervencion) -> None:
        self._interv[intervencion.intervencion_id] = intervencion

    async def list_avances(self, intervencion_id: str) -> list[Avance]:
        return sorted(
            (a for a in self._avances if a.intervencion_id == intervencion_id),
            key=lambda a: (a.fecha, a.id or 0),
        )

    async def record_avance(self, avance: Avance) -> Optional[Decimal]:
        new_id = max((a.id or 0 for a in self._avances), default=0) + 1
        stored = replace(avance, id=new_id)
        self._avances.append(stored)
        same = [a for a in self._avances if a.intervencion_id == avance.intervencion_id]
        cache = recompute_avance_cache(same)
        current = self._interv.get(avance.intervencion_id)
        if current is not None:
            self._interv[avance.intervencion_id] = replace(current, avance_obra=cache)
        return cache

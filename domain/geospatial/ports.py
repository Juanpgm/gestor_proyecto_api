"""Repository ports for the geospatial aggregate (structural typing).

Adapters (Firestore, Postgres, in-memory fake) implement these Protocols.
Ports speak ONLY in domain entities — never Firestore dicts or ORM rows.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Optional, Protocol, runtime_checkable

from domain.geospatial.entities import (
    Avance,
    Intervencion,
    UnidadProyecto,
    UPQuery,
)


@runtime_checkable
class UnidadesProyectoRepository(Protocol):
    async def get(self, upid: str) -> Optional[UnidadProyecto]: ...

    async def list(self, query: UPQuery = UPQuery()) -> list[UnidadProyecto]: ...

    async def count(self, query: UPQuery = UPQuery()) -> int: ...

    async def upsert(self, up: UnidadProyecto) -> None: ...

    async def as_feature_collection(self, query: UPQuery = UPQuery()) -> dict: ...


@runtime_checkable
class IntervencionesRepository(Protocol):
    async def list_by_up(self, upid: str) -> list[Intervencion]: ...

    async def upsert(self, intervencion: Intervencion) -> None: ...

    async def list_avances(self, intervencion_id: str) -> list[Avance]: ...

    async def record_avance(self, avance: Avance) -> Optional[Decimal]:
        """Persist an avance and refresh the intervención's cached avance_obra.

        Returns the new cached value (latest avance), or None if none remain.
        """
        ...

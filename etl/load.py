"""Load domain entities into Postgres via the repository adapters.

Each row is loaded inside its own SAVEPOINT (``begin_nested``), so a single bad
row (constraint violation, unparseable geometry) is skipped and reported instead
of aborting the whole batch. Returns ``(loaded_count, errors)`` where errors is a
list of ``{"key": ..., "error": ...}``. Unidades/intervenciones upsert by PK
(idempotent); avances are appended and refresh the intervención cache.
"""

from __future__ import annotations

from typing import Iterable

from sqlalchemy.ext.asyncio import AsyncSession

from domain.geospatial.entities import Avance, Intervencion, UnidadProyecto
from infrastructure.postgres.intervenciones_repo import PostgresIntervencionesRepository
from infrastructure.postgres.unidades_proyecto_repo import PostgresUnidadesProyectoRepository

LoadResult = tuple[int, list[dict]]


async def _safe(session: AsyncSession, key: str, op, errors: list[dict]) -> bool:
    try:
        async with session.begin_nested():
            await op()
        return True
    except Exception as exc:  # noqa: BLE001 - we want to capture and continue
        errors.append({"key": key, "error": str(exc)[:300]})
        return False


async def load_unidades(session: AsyncSession, unidades: Iterable[UnidadProyecto]) -> LoadResult:
    repo = PostgresUnidadesProyectoRepository(session)
    ok, errors = 0, []
    for up in unidades:
        if await _safe(session, up.upid, lambda up=up: repo.upsert(up), errors):
            ok += 1
    return ok, errors


async def load_intervenciones(
    session: AsyncSession, intervenciones: Iterable[Intervencion]
) -> LoadResult:
    repo = PostgresIntervencionesRepository(session)
    ok, errors = 0, []
    for interv in intervenciones:
        if await _safe(session, interv.intervencion_id, lambda i=interv: repo.upsert(i), errors):
            ok += 1
    return ok, errors


async def load_avances(session: AsyncSession, avances: Iterable[Avance]) -> LoadResult:
    repo = PostgresIntervencionesRepository(session)
    ok, errors = 0, []
    for avance in avances:
        key = f"{avance.intervencion_id}@{avance.fecha.isoformat()}"
        if await _safe(session, key, lambda a=avance: repo.record_avance(a), errors):
            ok += 1
    return ok, errors

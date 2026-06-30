"""Dual-backend enriched read path for *unidades de proyecto* and *intervenciones*.

Observe-only seam for ``DATA_BACKEND=dual``: it runs BOTH the Postgres and the
Firestore enriched read paths, compares the two row-sets via ``etl.parity`` and
logs any divergence at WARNING, then returns the configured primary side
(``dual_read_primary``, default ``"firestore"``).

This module deliberately reuses the *exact* consolidation/flattening helpers of
``infrastructure.postgres.unidades_read`` (``up_to_dict``,
``consolidate_intervenciones``, ``CONSOLIDATED_KEYS``, ``intervencion_to_record``)
so the Firestore-sourced rows are byte-for-byte comparable with the Postgres ones
— no consolidation logic is duplicated here.

Fail-loud-on-primary semantics: when the configured primary side raises, ``_pick``
logs at ERROR and re-raises so the endpoint surfaces the outage immediately
(matching ``infrastructure.composite._runner.gather_dual``).  Only a
secondary-side failure is absorbed — logged at ERROR — and the primary result is
returned unchanged.

Note on parity scope: the comparison runs on the page-level result *before* the
router applies RBAC post-filters (centro scoping).  Divergence logs are
internal-only and may refer to records the caller will later drop.

The Firestore stack is imported lazily through ``ports_di`` so importing this
module never pulls the Google client libraries.
"""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from typing import Callable, Optional

from core_db.settings import get_db_settings
from domain.geospatial.consolidation import consolidate_intervenciones
from domain.geospatial.entities import UPQuery
from etl.parity import ParityReport, compare
from infrastructure.postgres.unidades_read import (
    CONSOLIDATED_KEYS,
    fetch_enriched,
    fetch_intervenciones_enriched,
    intervencion_to_record,
    up_to_dict,
)
from ports_di import firestore_intervenciones_repo, firestore_unidades_repo

_unidades_logger = logging.getLogger("dual.unidades")
_intervenciones_logger = logging.getLogger("dual.intervenciones")

# Stable fields compared between the two enriched UP row-sets. Keyed on ``upid``;
# the names match the flattened ``up_to_dict`` + consolidation output (note the
# Firestore-style ``nombre_centro_gestor`` alias), so both sides are comparable.
#
# ``num_intervenciones`` is excluded: the Firestore side is page-scoped (it
# fetches per-UP intervenciones only for the current page) while the Postgres
# side counts ALL interventions across the full dataset.  Additionally, 11 UPs
# are Firestore-only, so this field would systematically false-positive on every
# dual comparison.
DUAL_UNIDADES_COMPARE_FIELDS: tuple[str, ...] = (
    "upid",
    "nombre_up",
    "nombre_centro_gestor",
    "presupuesto_base",
    "ano",
    "estado",
    "avance_obra",
    "tipo_intervencion",
    "frente_activo",
)

# Stable fields compared between the two enriched intervención row-sets.
DUAL_INTERVENCIONES_COMPARE_FIELDS: tuple[str, ...] = (
    "intervencion_id",
    "upid",
    "tipo_intervencion",
    "avance_obra",
    "estado",
    "frente_activo",
)


def _primary() -> str:
    """The configured primary side, validated to a known backend name."""
    primary = get_db_settings().dual_read_primary
    return primary if primary in ("firestore", "postgres") else "firestore"


def _log_report(logger: logging.Logger, method_name: str, report: ParityReport) -> None:
    """Log a parity report — WARNING on divergence, DEBUG when the sides agree."""
    if report.ok:
        logger.debug("%s parity OK: %s", method_name, report.as_dict())
    else:
        logger.warning("%s parity DIVERGENCE: %s", method_name, report.as_dict())


def _pick(primary: str, fs_result, fs_ok: bool, pg_result, pg_ok: bool):
    """Return the primary side; re-raise when the primary side failed.

    Fail-loud semantics matching ``_runner.gather_dual``: a primary outage is
    logged at ERROR and re-raised so the endpoint errors rather than masking the
    failure behind a silent fallback.  A secondary failure is also logged at
    ERROR but the primary result is returned — the shadow read failed, the live
    path is intact.

    Both-fail edge case: the primary exception is re-raised (same code path as a
    primary-only failure; no separate check is needed).
    """
    _dual_logger = logging.getLogger("dual")
    if primary == "firestore":
        if not fs_ok:
            _dual_logger.error("primary 'firestore' failed: %r", fs_result)
            raise fs_result
        if not pg_ok:
            _dual_logger.error("secondary 'postgres' failed: %r", pg_result)
        return fs_result
    # primary == "postgres"
    if not pg_ok:
        _dual_logger.error("primary 'postgres' failed: %r", pg_result)
        raise pg_result
    if not fs_ok:
        _dual_logger.error("secondary 'firestore' failed: %r", fs_result)
    return pg_result


async def _fetch_enriched_firestore(
    query: UPQuery,
    *,
    up_repo_factory: Optional[Callable] = None,
    int_repo_factory: Optional[Callable] = None,
) -> tuple[list[dict], int]:
    """Build the enriched UP row-set from the Firestore adapters.

    Mirrors ``infrastructure.postgres.unidades_read.fetch_enriched`` exactly,
    only swapping the data source: the same ``up_to_dict`` flattening and
    ``consolidate_intervenciones`` merge are applied.  The Firestore intervenciones
    adapter has no ``list_all``, so intervenciones are fetched per listed UP
    concurrently (bounded by a semaphore to prevent unbounded fan-out) — which
    only covers the paginated page, matching the Postgres path's per-UP
    consolidation for that page.

    ``up_repo_factory`` / ``int_repo_factory`` default to the ``ports_di``
    constructors; override them in tests to inject in-memory fakes.
    """
    up_repo = (up_repo_factory or firestore_unidades_repo)()
    int_repo = (int_repo_factory or firestore_intervenciones_repo)()

    ups = await up_repo.list(query)
    # count() is intentionally omitted: it triggers a second full-collection scan
    # and the total is discarded by the router (_total).  total is derived from
    # the page length; the primary side's count is what the caller ultimately uses.

    _sem = asyncio.Semaphore(16)

    async def _bounded_list(upid: str) -> list:
        async with _sem:
            return await int_repo.list_by_up(upid)

    interv_lists = await asyncio.gather(
        *(_bounded_list(u.upid) for u in ups)
    )
    by_up: dict[str, list] = defaultdict(list)
    for u, intervs in zip(ups, interv_lists):
        by_up[u.upid] = list(intervs)

    enriched: list[dict] = []
    for u in ups:
        cons = consolidate_intervenciones(u, by_up.get(u.upid, []))
        d = up_to_dict(u)
        d.update({k: cons[k] for k in CONSOLIDATED_KEYS})
        d["n_intervenciones"] = d.get("num_intervenciones")
        enriched.append(d)
    return enriched, len(enriched)


async def fetch_enriched_dual(
    query: UPQuery,
    *,
    _fs_up_factory: Optional[Callable] = None,
    _fs_int_factory: Optional[Callable] = None,
    _pg_fetch_fn: Optional[Callable] = None,
) -> tuple[list[dict], int]:
    """Run both enriched UP read paths, compare + log, return the primary side.

    Returns ``(rows, total)`` from the configured ``dual_read_primary`` side.

    ``_fs_up_factory``, ``_fs_int_factory``, and ``_pg_fetch_fn`` are injection
    seams for unit tests; they default to the live ``ports_di`` constructors and
    ``fetch_enriched`` respectively.  Do not use them in production code.
    """
    primary = _primary()
    _pg = _pg_fetch_fn or fetch_enriched
    fs_result, pg_result = await asyncio.gather(
        _fetch_enriched_firestore(
            query,
            up_repo_factory=_fs_up_factory,
            int_repo_factory=_fs_int_factory,
        ),
        _pg(query),
        return_exceptions=True,
    )
    fs_ok = not isinstance(fs_result, BaseException)
    pg_ok = not isinstance(pg_result, BaseException)

    if not fs_ok:
        _unidades_logger.warning("firestore side failed: %r", fs_result)
    if not pg_ok:
        _unidades_logger.warning("postgres side failed: %r", pg_result)

    if fs_ok and pg_ok:
        report = compare(
            fs_result[0], pg_result[0], "upid", DUAL_UNIDADES_COMPARE_FIELDS
        )
        _log_report(_unidades_logger, "unidades", report)

    return _pick(primary, fs_result, fs_ok, pg_result, pg_ok)


async def _fetch_intervenciones_enriched_firestore(
    *,
    up_repo_factory: Optional[Callable] = None,
    int_repo_factory: Optional[Callable] = None,
) -> list[dict]:
    """Build the enriched intervención row-set from the Firestore adapters.

    Mirrors ``unidades_read.fetch_intervenciones_enriched``: parent-UP props are
    looked up the same way and ``intervencion_to_record`` flattens each row, so
    the derived ``estado`` / ``frente_activo`` agree with the Postgres path.
    Intervenciones are fetched per UP with bounded concurrency (semaphore of 16)
    because the Firestore adapter has no ``list_all``.

    ``up_repo_factory`` / ``int_repo_factory`` default to the ``ports_di``
    constructors; override them in tests to inject in-memory fakes.
    """
    up_repo = (up_repo_factory or firestore_unidades_repo)()
    int_repo = (int_repo_factory or firestore_intervenciones_repo)()

    ups = await up_repo.list(UPQuery())
    parents = {
        u.upid: {
            "nombre_centro_gestor": u.centro_gestor,
            "clase_up": u.clase_up,
            "tipo_equipamiento": u.tipo_equipamiento,
        }
        for u in ups
    }

    _sem = asyncio.Semaphore(16)

    async def _bounded_list(upid: str) -> list:
        async with _sem:
            return await int_repo.list_by_up(upid)

    interv_lists = await asyncio.gather(
        *(_bounded_list(u.upid) for u in ups)
    )
    records: list[dict] = []
    for intervs in interv_lists:
        for i in intervs:
            records.append(intervencion_to_record(i, parents.get(i.upid)))
    return records


async def fetch_intervenciones_enriched_dual(
    *,
    _fs_up_factory: Optional[Callable] = None,
    _fs_int_factory: Optional[Callable] = None,
    _pg_fetch_fn: Optional[Callable] = None,
) -> list[dict]:
    """Run both enriched intervención read paths, compare + log, return primary.

    Returns the configured ``dual_read_primary`` side's wire records (same shape
    as ``unidades_read.fetch_intervenciones_enriched``).

    ``_fs_up_factory``, ``_fs_int_factory``, and ``_pg_fetch_fn`` are injection
    seams for unit tests; they default to the live ``ports_di`` constructors and
    ``fetch_intervenciones_enriched`` respectively.  Do not use them in production
    code.
    """
    primary = _primary()
    _pg = _pg_fetch_fn or fetch_intervenciones_enriched
    fs_result, pg_result = await asyncio.gather(
        _fetch_intervenciones_enriched_firestore(
            up_repo_factory=_fs_up_factory,
            int_repo_factory=_fs_int_factory,
        ),
        _pg(),
        return_exceptions=True,
    )
    fs_ok = not isinstance(fs_result, BaseException)
    pg_ok = not isinstance(pg_result, BaseException)

    if not fs_ok:
        _intervenciones_logger.warning("firestore side failed: %r", fs_result)
    if not pg_ok:
        _intervenciones_logger.warning("postgres side failed: %r", pg_result)

    if fs_ok and pg_ok:
        report = compare(
            fs_result,
            pg_result,
            "intervencion_id",
            DUAL_INTERVENCIONES_COMPARE_FIELDS,
        )
        _log_report(_intervenciones_logger, "intervenciones", report)

    return _pick(primary, fs_result, fs_ok, pg_result, pg_ok)

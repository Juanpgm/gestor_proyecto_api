"""Dual-read composite adapter for UnidadesProyectoRepository.

Wraps a Firestore read adapter and a Postgres adapter. Every read runs BOTH
sides concurrently and compares the results field-by-field (via etl.parity),
logging any divergence at WARNING. The configured ``primary`` side's result is
returned. Writes always go to Postgres.

Comparison is deliberately scoped to stable, raw fields. Derived/unstable fields
(estado, frente_activo) and geometry (geometry, geometry_type, has_valid_geometry)
are excluded — geometry equality is a PostGIS (ST_Equals) concern, not a dict
comparison, and estado is recomputed at the boundary on both sides.
"""

from __future__ import annotations

import logging
from typing import Any, Optional, Sequence

from domain.geospatial.entities import UnidadProyecto, UPQuery
from etl.parity import ParityReport, compare
from infrastructure.composite._runner import gather_dual

# Key used to align records across the two backends.
_KEY_FIELD = "upid"

# Proven stable field set: matched cleanly in the 100-UP parity check.
# Widen via the ``compare_fields`` constructor argument when needed.
DEFAULT_UNIDADES_COMPARE_FIELDS: tuple[str, ...] = (
    "upid",
    "nombre_up",
    "centro_gestor",
    "presupuesto_base",
    "ano",
)


class DualUnidadesProyectoRepository:
    """Composite UnidadesProyectoRepository running Firestore + Postgres in parallel.

    Args:
        firestore_repo: The Firestore read adapter.
        postgres_repo: The Postgres adapter (also the write target).
        primary: Which side's result is returned ("firestore" or "postgres").
        compare_fields: Raw fields to checksum-compare. Defaults to the proven
            narrow set; widen for deeper divergence audits.
        logger: Optional logger; defaults to this module's logger.
    """

    def __init__(
        self,
        firestore_repo: Any,
        postgres_repo: Any,
        *,
        primary: str = "firestore",
        compare_fields: Optional[Sequence[str]] = None,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        if primary not in ("firestore", "postgres"):
            raise ValueError(
                f"primary must be 'firestore' or 'postgres', got {primary!r}"
            )
        self._fs = firestore_repo
        self._pg = postgres_repo
        self._primary = primary
        self._compare_fields: list[str] = (
            list(compare_fields)
            if compare_fields is not None
            else list(DEFAULT_UNIDADES_COMPARE_FIELDS)
        )
        self._log = logger or logging.getLogger(__name__)
        # The most recent ParityReport produced by a comparing read. Exposed so
        # verification tooling can inspect divergences without re-querying.
        self.last_report: Optional[ParityReport] = None

    # ------------------------------------------------------------------
    # Comparison helpers
    # ------------------------------------------------------------------

    def _entity_record(self, entity: UnidadProyecto) -> dict[str, Any]:
        """Project a domain entity to the {key + compare_fields} dict parity needs."""
        fields = {_KEY_FIELD, *self._compare_fields}
        return {f: getattr(entity, f, None) for f in fields}

    def _records_from_result(self, method_name: str, result: Any) -> list[dict[str, Any]]:
        """Normalise a read result into a list of comparable dicts."""
        if result is None:
            return []
        if method_name == "get":
            return [self._entity_record(result)]
        if method_name == "list":
            return [self._entity_record(e) for e in result]
        if method_name == "as_feature_collection":
            return [f.get("properties", {}) for f in result.get("features", [])]
        return []

    def _compare(self, method_name: str, fs_result: Any, pg_result: Any) -> ParityReport:
        """Run etl.parity.compare (Firestore=left, Postgres=right) and log divergence."""
        left = self._records_from_result(method_name, fs_result)
        right = self._records_from_result(method_name, pg_result)
        report = compare(left, right, key_field=_KEY_FIELD, fields=self._compare_fields)
        self.last_report = report
        if not report.ok:
            self._log.warning(
                "dual-read divergence in unidades.%s: %s",
                method_name,
                report.as_dict(),
            )
        return report

    def _compare_count(self, method_name: str, fs_result: Any, pg_result: Any) -> None:
        """Counts compare as plain integers — no key alignment applies."""
        if fs_result != pg_result:
            self._log.warning(
                "dual-read divergence in unidades.%s: firestore=%s postgres=%s",
                method_name,
                fs_result,
                pg_result,
            )

    # ------------------------------------------------------------------
    # Port implementation
    # ------------------------------------------------------------------

    async def get(self, upid: str) -> Optional[UnidadProyecto]:
        return await gather_dual(
            self._fs.get(upid),
            self._pg.get(upid),
            primary=self._primary,
            logger=self._log,
            method_name="get",
            on_both=self._compare,
        )

    async def list(self, query: UPQuery = UPQuery()) -> list[UnidadProyecto]:
        return await gather_dual(
            self._fs.list(query),
            self._pg.list(query),
            primary=self._primary,
            logger=self._log,
            method_name="list",
            on_both=self._compare,
        )

    async def count(self, query: UPQuery = UPQuery()) -> int:
        return await gather_dual(
            self._fs.count(query),
            self._pg.count(query),
            primary=self._primary,
            logger=self._log,
            method_name="count",
            on_both=self._compare_count,
        )

    async def as_feature_collection(self, query: UPQuery = UPQuery()) -> dict:
        return await gather_dual(
            self._fs.as_feature_collection(query),
            self._pg.as_feature_collection(query),
            primary=self._primary,
            logger=self._log,
            method_name="as_feature_collection",
            on_both=self._compare,
        )

    async def upsert(self, up: UnidadProyecto) -> None:
        """Writes always go to Postgres (Firestore is read-only in v3 parity mode)."""
        await self._pg.upsert(up)

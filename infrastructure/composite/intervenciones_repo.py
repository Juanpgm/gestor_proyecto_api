"""Dual-read composite adapter for IntervencionesRepository.

Same pattern as the unidades composite: reads run Firestore + Postgres
concurrently, results are compared and divergence logged at WARNING, and the
configured ``primary`` side's result is returned. Writes (upsert, record_avance)
always go to Postgres.

list_by_up is compared field-by-field keyed on intervencion_id. list_avances
is compared by record count only: Firestore avances carry no stable numeric id
(``firestore_to_avance`` leaves ``id`` None), so the BIGSERIAL ids on the
Postgres side cannot be aligned with Firestore avances — a field-level key would
be meaningless. The count check still surfaces missing/extra avances.
"""

from __future__ import annotations

import logging
from typing import Any, Optional, Sequence

from decimal import Decimal

from domain.geospatial.entities import Avance, Intervencion
from etl.parity import ParityReport, compare
from infrastructure.composite._runner import gather_dual

# Key used to align intervención records across the two backends.
_KEY_FIELD = "intervencion_id"

# Stable raw fields shared by both sides. estado is excluded (derived property).
DEFAULT_INTERVENCIONES_COMPARE_FIELDS: tuple[str, ...] = (
    "intervencion_id",
    "upid",
    "tipo_intervencion",
    "avance_obra",
    "estado_manual",
)


class DualIntervencionesRepository:
    """Composite IntervencionesRepository running Firestore + Postgres in parallel.

    Args:
        firestore_repo: The Firestore read adapter.
        postgres_repo: The Postgres adapter (also the write target).
        primary: Which side's result is returned ("firestore" or "postgres").
        compare_fields: Raw fields to checksum-compare for list_by_up.
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
            else list(DEFAULT_INTERVENCIONES_COMPARE_FIELDS)
        )
        self._log = logger or logging.getLogger(__name__)
        # Most recent ParityReport from a list_by_up comparison.
        self.last_report: Optional[ParityReport] = None

    # ------------------------------------------------------------------
    # Comparison helpers
    # ------------------------------------------------------------------

    def _entity_record(self, entity: Intervencion) -> dict[str, Any]:
        fields = {_KEY_FIELD, *self._compare_fields}
        return {f: getattr(entity, f, None) for f in fields}

    def _compare_intervenciones(
        self, method_name: str, fs_result: Any, pg_result: Any
    ) -> ParityReport:
        """Field-level parity for intervención lists, keyed on intervencion_id."""
        left = [self._entity_record(e) for e in (fs_result or [])]
        right = [self._entity_record(e) for e in (pg_result or [])]
        report = compare(left, right, key_field=_KEY_FIELD, fields=self._compare_fields)
        self.last_report = report
        if not report.ok:
            self._log.warning(
                "dual-read divergence in intervenciones.%s: %s",
                method_name,
                report.as_dict(),
            )
        return report

    def _compare_avances(
        self, method_name: str, fs_result: Any, pg_result: Any
    ) -> None:
        """Count-only comparison — Firestore avances have no alignable id."""
        fs_len = len(fs_result or [])
        pg_len = len(pg_result or [])
        if fs_len != pg_len:
            self._log.warning(
                "dual-read divergence in intervenciones.%s: "
                "firestore=%d avances postgres=%d avances",
                method_name,
                fs_len,
                pg_len,
            )

    # ------------------------------------------------------------------
    # Port implementation
    # ------------------------------------------------------------------

    async def list_by_up(self, upid: str) -> list[Intervencion]:
        return await gather_dual(
            self._fs.list_by_up(upid),
            self._pg.list_by_up(upid),
            primary=self._primary,
            logger=self._log,
            method_name="list_by_up",
            on_both=self._compare_intervenciones,
        )

    async def list_avances(self, intervencion_id: str) -> list[Avance]:
        return await gather_dual(
            self._fs.list_avances(intervencion_id),
            self._pg.list_avances(intervencion_id),
            primary=self._primary,
            logger=self._log,
            method_name="list_avances",
            on_both=self._compare_avances,
        )

    async def upsert(self, intervencion: Intervencion) -> None:
        """Writes always go to Postgres (Firestore is read-only in v3 parity mode)."""
        await self._pg.upsert(intervencion)

    async def record_avance(self, avance: Avance) -> Optional[Decimal]:
        """Writes always go to Postgres (Firestore is read-only in v3 parity mode)."""
        return await self._pg.record_avance(avance)

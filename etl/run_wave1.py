"""Wave-1 ETL runner: Firestore (read-only) -> PostgreSQL + PostGIS.

Orchestrates extract -> transform -> load -> parity for the geospatial core.
Read-only against Firestore; writes only to the local/Neon Postgres in
DATABASE_URL. Requires read-only credentials for `calitrack-44403`; without
them it exits with a clear message (the schema, seed and tests still work).

Usage:
    python -m etl.run_wave1 [--limit N] [--dry-run]
"""

from __future__ import annotations

import argparse
import asyncio
import logging

from core_db.engine import AsyncSessionLocal
from etl import extract, load
from etl.extract import FirestoreUnavailableError
from etl.parity import compare
from etl.transform import (
    firestore_to_avance,
    firestore_to_intervencion,
    firestore_to_unidad,
)

logger = logging.getLogger("etl.run_wave1")

_UP_PARITY_FIELDS = ["upid", "nombre_up", "centro_gestor", "presupuesto_base", "ano"]


async def _run(limit: int | None, dry_run: bool) -> int:
    # --- Extract (read-only Firestore) ---
    try:
        raw_unidades = extract.extract_unidades(limit)
        raw_intervenciones = extract.extract_intervenciones(limit)
        raw_avances = extract.extract_avances(limit)
    except FirestoreUnavailableError as exc:
        logger.error("Cannot run live ETL: %s", exc)
        return 2

    # --- Transform (pure) ---
    from dataclasses import replace

    unidades = [firestore_to_unidad(d) for d in raw_unidades]
    intervenciones = [firestore_to_intervencion(d) for d in raw_intervenciones]
    # Avance docs carry intervencion_id but not upid; derive upid from its
    # intervención so the (NOT NULL) FK is satisfied.
    int_to_up = {i.intervencion_id: i.upid for i in intervenciones}
    avances = [
        replace(a, upid=a.upid or int_to_up.get(a.intervencion_id))
        for a in (firestore_to_avance(d) for d in raw_avances)
    ]
    logger.info(
        "Transformed %d unidades, %d intervenciones, %d avances",
        len(unidades), len(intervenciones), len(avances),
    )

    if dry_run:
        logger.info("Dry run: skipping load.")
        return 0

    # --- Load (Postgres), resilient per-row ---
    from infrastructure.postgres.unidades_proyecto_repo import (
        PostgresUnidadesProyectoRepository,
    )
    from domain.geospatial.entities import UPQuery

    async with AsyncSessionLocal() as session:
        n_up, up_errors = await load.load_unidades(session, unidades)
        n_int, int_errors = await load.load_intervenciones(session, intervenciones)
        n_av, av_errors = await load.load_avances(session, avances)
        await session.commit()

    logger.info("Loaded unidades=%d (errors=%d), intervenciones=%d (errors=%d), avances=%d (errors=%d)",
                n_up, len(up_errors), n_int, len(int_errors), n_av, len(av_errors))
    for label, errs in (("unidades", up_errors), ("intervenciones", int_errors), ("avances", av_errors)):
        for e in errs[:5]:
            logger.warning("  %s load error [%s]: %s", label, e["key"], e["error"])

    # --- Parity: read Postgres back and compare to the transformed Firestore set ---
    def _proj(u):
        return {"upid": u.upid, "nombre_up": u.nombre_up, "centro_gestor": u.centro_gestor,
                "presupuesto_base": u.presupuesto_base, "ano": u.ano}

    loaded_upids = {u.upid for u in unidades} - {e["key"] for e in up_errors}
    fs_records = [_proj(u) for u in unidades if u.upid in loaded_upids]

    async with AsyncSessionLocal() as session:
        repo = PostgresUnidadesProyectoRepository(session)
        pg_unidades = await repo.list(UPQuery())
    pg_records = [_proj(u) for u in pg_unidades if u.upid in loaded_upids]

    report = compare(fs_records, pg_records, "upid", _UP_PARITY_FIELDS)
    logger.info("Parity (unidades loaded): %s", report.as_dict())
    return 0 if report.ok else 1


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    parser = argparse.ArgumentParser(description="Wave-1 Firestore -> Postgres ETL")
    parser.add_argument("--limit", type=int, default=None, help="Max docs per collection")
    parser.add_argument("--dry-run", action="store_true", help="Extract+transform only")
    args = parser.parse_args()
    return asyncio.run(_run(args.limit, args.dry_run))


if __name__ == "__main__":
    raise SystemExit(main())

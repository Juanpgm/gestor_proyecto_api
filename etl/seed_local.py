"""Seed representative local data for development and testing.

Usage (from back/ directory):
    python -m etl.seed_local

Idempotent: deletes rows for the seed upids first (cascade removes
intervenciones and avances), then re-inserts via the repository adapters
so the real adapter path is exercised.

Does NOT touch Firestore or any external service.
"""

from __future__ import annotations

import asyncio
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import text

from core_db.engine import AsyncSessionLocal
from domain.geospatial.entities import Avance, Intervencion, UnidadProyecto
from infrastructure.postgres.intervenciones_repo import PostgresIntervencionesRepository
from infrastructure.postgres.unidades_proyecto_repo import PostgresUnidadesProyectoRepository

# Upids managed by this seed script.
SEED_UPIDS = ["UNP-1001", "UNP-1002", "UNP-1003", "UNP-1004", "UNP-1005"]

# ---------------------------------------------------------------------------
# Fixture data
# ---------------------------------------------------------------------------

SEED_UPS: list[UnidadProyecto] = [
    UnidadProyecto(
        upid="UNP-1001",
        nombre_up="Corredor vial Carrera 1",
        direccion="Carrera 1 entre Calles 10 y 20",
        barrio_vereda="Centro",
        comuna_corregimiento="La Candelaria",
        municipio="Cali",
        departamento="Valle del Cauca",
        tipo_equipamiento="Via",
        clase_up="Obra vial",
        centro_gestor="Secretaría de Infraestructura",
        presupuesto_base=Decimal("1000000000"),
        fuente_financiacion="SGR",
        ano=2023,
        fecha_inicio=date(2023, 1, 15),
        fecha_fin=date(2024, 6, 30),
        geometry={
            "type": "LineString",
            "coordinates": [[-76.5320, 3.3980], [-76.5280, 3.4010]],
        },
    ),
    UnidadProyecto(
        upid="UNP-1002",
        nombre_up="Parque lineal Rio Cali",
        direccion="Avenida 2N",
        barrio_vereda="Santa Monica",
        comuna_corregimiento="El Pais",
        municipio="Cali",
        departamento="Valle del Cauca",
        tipo_equipamiento="Parque",
        clase_up="Obras equipamientos",
        centro_gestor="Secretaría de Movilidad",
        presupuesto_base=Decimal("500000000"),
        fuente_financiacion="PGM",
        ano=2022,
        fecha_inicio=date(2022, 3, 1),
        fecha_fin=date(2023, 12, 31),
        geometry={
            "type": "Polygon",
            "coordinates": [[
                [-76.5250, 3.4100],
                [-76.5220, 3.4100],
                [-76.5220, 3.4080],
                [-76.5250, 3.4080],
                [-76.5250, 3.4100],
            ]],
        },
    ),
    UnidadProyecto(
        upid="UNP-1003",
        nombre_up="Cerramiento parque El Poblado",
        direccion="Carrera 98 # 16-100",
        barrio_vereda="El Poblado",
        comuna_corregimiento="Aguablanca",
        municipio="Cali",
        departamento="Valle del Cauca",
        tipo_equipamiento="Parque",
        clase_up="Obras equipamientos",
        centro_gestor="DAGMA",
        presupuesto_base=Decimal("200000000"),
        fuente_financiacion="PGM",
        ano=2024,
        geometry={
            "type": "Point",
            "coordinates": [-76.5100, 3.3950],
        },
    ),
    UnidadProyecto(
        # Point [0,0] placeholder -- has_valid_geometry will be False (DB rule).
        upid="UNP-1004",
        nombre_up="UP con coordenadas sin localizar",
        municipio="Cali",
        departamento="Valle del Cauca",
        centro_gestor="Secretaría de Infraestructura",
        presupuesto_base=Decimal("100000000"),
        ano=2021,
        geometry={
            "type": "Point",
            "coordinates": [0.0, 0.0],
        },
    ),
    UnidadProyecto(
        # No geometry registered yet.
        upid="UNP-1005",
        nombre_up="UP sin geometria registrada",
        municipio="Cali",
        departamento="Valle del Cauca",
        centro_gestor="Secretaría de Movilidad",
        geometry=None,
    ),
]

SEED_INTERVENCIONES: list[Intervencion] = [
    Intervencion(
        intervencion_id="INT-1001-A",
        upid="UNP-1001",
        ano=2023,
        tipo_intervencion="Construccion",
        presupuesto_base=Decimal("1000000000"),
        avance_obra=Decimal("0"),
        fuente_financiacion="SGR",
    ),
    Intervencion(
        intervencion_id="INT-1001-B",
        upid="UNP-1001",
        ano=2023,
        tipo_intervencion="Mantenimiento",
        presupuesto_base=Decimal("50000000"),
        avance_obra=Decimal("45.5"),
        estado_manual="Suspendido",
        fuente_financiacion="PGM",
    ),
    Intervencion(
        intervencion_id="INT-1002-A",
        upid="UNP-1002",
        ano=2022,
        tipo_intervencion="Construccion",
        presupuesto_base=Decimal("500000000"),
        avance_obra=Decimal("100"),
        fuente_financiacion="PGM",
    ),
    Intervencion(
        intervencion_id="INT-1003-A",
        upid="UNP-1003",
        ano=2024,
        tipo_intervencion="Construccion",
        presupuesto_base=Decimal("200000000"),
        avance_obra=Decimal("0"),
        fuente_financiacion="PGM",
    ),
]

# Avances for INT-1001-A -- exercises the recompute cache logic.
SEED_AVANCES: list[Avance] = [
    Avance(
        upid="UNP-1001",
        intervencion_id="INT-1001-A",
        avance_obra=Decimal("10"),
        fecha=datetime(2024, 1, 15, tzinfo=timezone.utc),
        descripcion="Primer reporte de avance",
        etapa="Alistamiento",
    ),
    Avance(
        upid="UNP-1001",
        intervencion_id="INT-1001-A",
        avance_obra=Decimal("30"),
        fecha=datetime(2024, 2, 20, tzinfo=timezone.utc),
        descripcion="Cimentacion completada",
        etapa="Construccion",
    ),
    Avance(
        upid="UNP-1001",
        intervencion_id="INT-1001-A",
        avance_obra=Decimal("60"),
        fecha=datetime(2024, 3, 25, tzinfo=timezone.utc),
        descripcion="Obra al 60 porciento",
        etapa="Construccion",
    ),
]

# ---------------------------------------------------------------------------
# Seed logic
# ---------------------------------------------------------------------------


async def _clean(session) -> None:
    """Delete seed upids in dependency order.

    Cascade (ON DELETE CASCADE) handles avances and intervenciones automatically
    when we delete from unidades_proyecto.
    """
    placeholders = ", ".join(f"'{u}'" for u in SEED_UPIDS)
    await session.execute(
        text(f"DELETE FROM unidades_proyecto WHERE upid IN ({placeholders})")
    )


async def _insert(session) -> None:
    up_repo = PostgresUnidadesProyectoRepository(session)
    int_repo = PostgresIntervencionesRepository(session)

    for up in SEED_UPS:
        await up_repo.upsert(up)
    await session.flush()

    for intervencion in SEED_INTERVENCIONES:
        await int_repo.upsert(intervencion)
    await session.flush()

    # record_avance flushes internally and recomputes avance_obra on INT-1001-A.
    # After the loop INT-1001-A.avance_obra will equal the latest avance (60).
    for avance in SEED_AVANCES:
        await int_repo.record_avance(avance)


async def main() -> None:
    async with AsyncSessionLocal() as session:
        await _clean(session)
        await session.flush()
        await _insert(session)
        await session.commit()

    print("Seed complete.")
    print(f"  Unidades de proyecto : {len(SEED_UPS)}")
    print(f"  Intervenciones       : {len(SEED_INTERVENCIONES)}")
    print(f"  Avances              : {len(SEED_AVANCES)}")
    print("  INT-1001-A avance_obra cache -> 60 (latest avance by fecha)")
    print("  INT-1001-B estado_manual = 'Suspendido' (whitelist override)")


if __name__ == "__main__":
    asyncio.run(main())

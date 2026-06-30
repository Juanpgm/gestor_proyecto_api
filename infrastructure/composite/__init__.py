"""Composite (dual-read) adapters for the geospatial aggregate.

These wrap a Firestore read adapter and a Postgres adapter, running both sides
concurrently on every read, comparing the results (via etl.parity) and logging
divergence at WARNING. The configured ``primary`` side's result is returned;
writes always go to Postgres. Used during the Firestore -> Postgres migration
to prove parity and to fail safe if one backend hiccups.
"""

from __future__ import annotations

from infrastructure.composite.intervenciones_repo import (
    DEFAULT_INTERVENCIONES_COMPARE_FIELDS,
    DualIntervencionesRepository,
)
from infrastructure.composite.unidades_proyecto_repo import (
    DEFAULT_UNIDADES_COMPARE_FIELDS,
    DualUnidadesProyectoRepository,
)

__all__ = [
    "DualUnidadesProyectoRepository",
    "DualIntervencionesRepository",
    "DEFAULT_UNIDADES_COMPARE_FIELDS",
    "DEFAULT_INTERVENCIONES_COMPARE_FIELDS",
]

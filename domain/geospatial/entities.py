"""Domain entities for the geospatial aggregate.

Frozen dataclasses with no I/O and no ORM/Firestore coupling. Adapters map
their storage rows/documents to these and back. `estado` is NEVER stored as
authority — it is derived from `avance_obra` + `estado_manual` on access.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Iterable, Optional

from domain.geospatial.estado import calcular_estado


@dataclass(frozen=True)
class UnidadProyecto:
    """A unidad de proyecto. `geometry` is a GeoJSON geometry dict (or None).

    `geometry_type` and `has_valid_geometry` are DB-derived (PostGIS generated
    columns); adapters fill them on read and ignore them on write.
    """

    upid: str
    nombre_up: Optional[str] = None
    direccion: Optional[str] = None
    barrio_vereda: Optional[str] = None
    comuna_corregimiento: Optional[str] = None
    municipio: Optional[str] = None
    departamento: Optional[str] = None
    tipo_equipamiento: Optional[str] = None
    clase_up: Optional[str] = None
    centro_gestor: Optional[str] = None
    presupuesto_base: Optional[Decimal] = None
    fuente_financiacion: Optional[str] = None
    ano: Optional[int] = None
    fecha_inicio: Optional[date] = None
    fecha_fin: Optional[date] = None
    bpin: Optional[str] = None
    referencia_contrato: Optional[str] = None
    referencia_proceso: Optional[str] = None
    plataforma: Optional[str] = None
    geometry: Optional[dict] = None
    geometry_type: Optional[str] = None
    has_valid_geometry: bool = False


@dataclass(frozen=True)
class Intervencion:
    """An intervención on a unidad de proyecto.

    `avance_obra` is the cached latest progress value. `estado` is derived.
    """

    intervencion_id: str
    upid: str
    ano: Optional[int] = None
    tipo_intervencion: Optional[str] = None
    presupuesto_base: Optional[Decimal] = None
    avance_obra: Optional[Decimal] = None
    cantidad: Optional[Decimal] = None
    fecha_inicio: Optional[date] = None
    fecha_fin: Optional[date] = None
    fuente_financiacion: Optional[str] = None
    bpin: Optional[str] = None
    referencia_contrato: Optional[str] = None
    referencia_proceso: Optional[str] = None
    url_proceso: Optional[str] = None
    descripcion: Optional[str] = None
    estado_manual: Optional[str] = None

    @property
    def estado(self) -> str:
        """Ephemeral estado, derived once at the data boundary."""
        return calcular_estado(self.avance_obra, self.estado_manual)


@dataclass(frozen=True)
class Avance:
    """A progress report. The latest one (by fecha) feeds the intervención cache."""

    upid: str
    intervencion_id: str
    avance_obra: Decimal
    fecha: datetime
    id: Optional[int] = None
    descripcion: Optional[str] = None
    etapa: Optional[str] = None
    volumen_ejecutado: Optional[Decimal] = None
    archivo_s3_key: Optional[str] = None


@dataclass(frozen=True)
class UPQuery:
    """Filter for listing unidades de proyecto. centro_gestor scopes by the
    authenticated principal (auth stays in Firebase; the name is passed in)."""

    centro_gestor: Optional[str] = None
    only_valid_geometry: bool = False
    limit: Optional[int] = None
    offset: int = 0


def recompute_avance_cache(avances: Iterable[Avance]) -> Optional[Decimal]:
    """Return the avance_obra of the most recent report (by fecha, then id).

    Pure reproduction of the Firestore cache rule: the intervención's
    `avance_obra` mirrors the latest avance; ``None`` when there are none.
    """
    latest = None
    for a in avances:
        if latest is None or (a.fecha, a.id or 0) > (latest.fecha, latest.id or 0):
            latest = a
    return latest.avance_obra if latest is not None else None

"""Shared Postgres read path for *unidades de proyecto*.

Single source of truth for reading unidades from Postgres, used by BOTH:
  * the isolated local app ``pg_app.py``, and
  * the full backend's ``GET /unidades-proyecto`` endpoint when
    ``DATA_BACKEND=postgres`` (the v3 migration seam).

Centralising it here prevents the two apps from drifting apart — the same
divergence ``auth_system/centro_scoping.py`` warns about for centro filtering.

This module imports NO Firebase and NO web framework, so it stays unit-testable
in isolation (see ``test/unit/test_unidades_pg_filter.py``).
"""

from __future__ import annotations

import unicodedata
from collections import defaultdict
from decimal import Decimal
from typing import Optional

from core_db.engine import AsyncSessionLocal
from domain.geospatial.consolidation import consolidate_intervenciones
from domain.geospatial.entities import Intervencion, UnidadProyecto, UPQuery
from domain.geospatial.estado import clasificar_frente_activo, convert_to_float
from infrastructure.postgres.intervenciones_repo import PostgresIntervencionesRepository
from infrastructure.postgres.unidades_proyecto_repo import PostgresUnidadesProyectoRepository

# UP-level fields merged from intervención consolidation onto each UP.
CONSOLIDATED_KEYS = (
    "estado",
    "avance_obra",
    "tipo_intervencion",
    "frente_activo",
    "num_intervenciones",
)


def _num(value: Optional[Decimal]) -> Optional[float]:
    return float(value) if value is not None else None


def up_to_dict(u: UnidadProyecto) -> dict:
    """Flat dict using the field names the front already expects.

    Note ``centro_gestor`` is emitted as ``nombre_centro_gestor`` (the Firestore
    field name) so the existing front consumes Postgres rows unchanged.
    """
    return {
        "upid": u.upid,
        "nombre_up": u.nombre_up,
        "nombre_centro_gestor": u.centro_gestor,
        "presupuesto_base": _num(u.presupuesto_base),
        "ano": u.ano,
        "municipio": u.municipio,
        "departamento": u.departamento,
        "comuna_corregimiento": u.comuna_corregimiento,
        "barrio_vereda": u.barrio_vereda,
        "tipo_equipamiento": u.tipo_equipamiento,
        "clase_up": u.clase_up,
        "fuente_financiacion": u.fuente_financiacion,
        "bpin": u.bpin,
        "referencia_contrato": u.referencia_contrato,
        "referencia_proceso": u.referencia_proceso,
        "fecha_inicio": u.fecha_inicio.isoformat() if u.fecha_inicio else None,
        "fecha_fin": u.fecha_fin.isoformat() if u.fecha_fin else None,
        "plataforma": u.plataforma,
        "geometry": u.geometry,
        "geometry_type": u.geometry_type,
        "has_valid_geometry": u.has_valid_geometry,
    }


async def fetch_enriched(query: UPQuery) -> tuple[list[dict], int]:
    """Load unidades + all intervenciones once, then merge UP-level consolidated
    fields (estado / avance_obra / tipo_intervencion / frente_activo) onto each.

    Returns ``(rows, total)`` where ``total`` is the count ignoring limit/offset.
    """
    async with AsyncSessionLocal() as session:
        up_repo = PostgresUnidadesProyectoRepository(session)
        int_repo = PostgresIntervencionesRepository(session)
        ups = await up_repo.list(query)
        total = await up_repo.count(query)
        all_intervenciones = await int_repo.list_all()

    by_up: dict[str, list] = defaultdict(list)
    for interv in all_intervenciones:
        by_up[interv.upid].append(interv)

    enriched = []
    for u in ups:
        cons = consolidate_intervenciones(u, by_up.get(u.upid, []))
        d = up_to_dict(u)
        d.update({k: cons[k] for k in CONSOLIDATED_KEYS})
        # The front's AttributeSchema reads ``n_intervenciones``; expose an alias
        # alongside the consolidation's ``num_intervenciones``.
        d["n_intervenciones"] = d.get("num_intervenciones")
        enriched.append(d)
    return enriched, total


def _norm(value: object) -> str:
    """Accent-insensitive, case-insensitive, space-collapsed comparison key."""
    if value is None:
        return ""
    text = unicodedata.normalize("NFKD", str(value))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return " ".join(text.casefold().split())


def filter_unidades(
    data: list[dict],
    *,
    upid: Optional[str] = None,
    estado: Optional[str] = None,
    tipo_intervencion: Optional[str] = None,
    clase_up: Optional[str] = None,
    tipo_equipamiento: Optional[str] = None,
    comuna_corregimiento: Optional[str] = None,
    barrio_vereda: Optional[str] = None,
    frente_activo: Optional[str] = None,
    fuente_financiacion: Optional[str] = None,
    ano: Optional[int] = None,
) -> list[dict]:
    """Apply the remaining (non-centro) filters client-side over enriched rows.

    Centro, limit and offset are pushed down to SQL via ``UPQuery``; the filters
    here mirror the Firestore path's behaviour for the rest. Text comparisons are
    accent/case-insensitive. ``estado`` is matched on the already-consolidated
    value. ``proyectos_estrategicos`` is not stored on the Postgres entity, so it
    is intentionally not filtered here.
    """
    # (field_in_row, requested_value) pairs compared with accent/case folding.
    text_filters = [
        ("upid", upid),
        ("estado", estado),
        ("tipo_intervencion", tipo_intervencion),
        ("clase_up", clase_up),
        ("tipo_equipamiento", tipo_equipamiento),
        ("comuna_corregimiento", comuna_corregimiento),
        ("barrio_vereda", barrio_vereda),
        ("frente_activo", frente_activo),
        ("fuente_financiacion", fuente_financiacion),
    ]
    active_text = [(field, _norm(val)) for field, val in text_filters if val]

    out = []
    for row in data:
        if not isinstance(row, dict):
            continue
        if any(_norm(row.get(field)) != target for field, target in active_text):
            continue
        if ano is not None and row.get("ano") != ano:
            continue
        out.append(row)
    return out


# ---------------------------------------------------------------------------
# Intervenciones read path (GET /intervenciones)
# ---------------------------------------------------------------------------

# Wire shape the front expects from /intervenciones (mirrors the Firestore
# endpoint's selected fields), plus the derived ``frente_activo``.
_INTERVENCION_TEXT_FIELDS = (
    "upid",
    "intervencion_id",
    "tipo_intervencion",
    "clase_up",
    "tipo_equipamiento",
    "fuente_financiacion",
    "referencia_contrato",
    "referencia_proceso",
    "url_proceso",
    "identificador",
    "unidad",
)
_INTERVENCION_NUMERIC_FIELDS = (
    "avance_obra",
    "presupuesto_base",
    "cantidad",
    "bpin",
)


def intervencion_to_record(i: Intervencion, parent: Optional[dict]) -> dict:
    """Flatten an Intervencion + its parent UP props into the front's wire shape.

    ``estado`` and ``frente_activo`` are derived from the same domain rules used
    everywhere else (``Intervencion.estado`` / ``clasificar_frente_activo``), so
    the Postgres and Firestore paths agree.
    """
    parent = parent or {}
    clase_up = parent.get("clase_up")
    tipo_equipamiento = parent.get("tipo_equipamiento")
    frente_activo = clasificar_frente_activo(
        {
            "avance_obra": i.avance_obra,
            "presupuesto_base": i.presupuesto_base,
            "tipo_intervencion": i.tipo_intervencion,
            "estado": i.estado_manual,
        },
        {"clase_up": clase_up, "tipo_equipamiento": tipo_equipamiento},
    )
    return {
        "avance_obra": convert_to_float(i.avance_obra),
        "bpin": i.bpin,
        "cantidad": _num(i.cantidad),
        "clase_up": clase_up,
        "estado": i.estado,
        "fecha_fin": i.fecha_fin.isoformat() if i.fecha_fin else None,
        "fecha_inicio": i.fecha_inicio.isoformat() if i.fecha_inicio else None,
        "fuente_financiacion": i.fuente_financiacion,
        "identificador": None,
        "intervencion_id": i.intervencion_id,
        "nombre_centro_gestor": parent.get("nombre_centro_gestor"),
        "presupuesto_base": _num(i.presupuesto_base),
        "referencia_contrato": i.referencia_contrato,
        "referencia_proceso": i.referencia_proceso,
        "tipo_equipamiento": tipo_equipamiento,
        "tipo_intervencion": i.tipo_intervencion,
        "unidad": None,
        "upid": i.upid,
        "url_proceso": i.url_proceso,
        "frente_activo": frente_activo,
    }


async def fetch_intervenciones_enriched() -> list[dict]:
    """Load all intervenciones, enriched with parent-UP props (centro, clase_up,
    tipo_equipamiento) and derived estado/frente_activo. Returns wire dicts."""
    async with AsyncSessionLocal() as session:
        up_repo = PostgresUnidadesProyectoRepository(session)
        int_repo = PostgresIntervencionesRepository(session)
        ups = await up_repo.list(UPQuery())
        intervenciones = await int_repo.list_all()

    parents = {
        u.upid: {
            "nombre_centro_gestor": u.centro_gestor,
            "clase_up": u.clase_up,
            "tipo_equipamiento": u.tipo_equipamiento,
        }
        for u in ups
    }
    return [intervencion_to_record(i, parents.get(i.upid)) for i in intervenciones]


def filter_intervenciones(
    data: list[dict],
    *,
    estado: Optional[str] = None,
    **exact: object,
) -> list[dict]:
    """Apply /intervenciones filters client-side over enriched records.

    Text fields use accent/case-insensitive comparison; numeric fields use exact
    float comparison; ``estado`` is matched on the derived value. Unknown/None
    filters are ignored. Centro scoping is applied separately by the caller.
    """
    active_text = [
        (f, _norm(exact[f])) for f in _INTERVENCION_TEXT_FIELDS if exact.get(f)
    ]
    active_num = []
    for f in _INTERVENCION_NUMERIC_FIELDS:
        val = exact.get(f)
        if val is not None:
            active_num.append((f, convert_to_float(val)))
    estado_target = _norm(estado) if estado else None

    out = []
    for row in data:
        if not isinstance(row, dict):
            continue
        if estado_target is not None and _norm(row.get("estado")) != estado_target:
            continue
        if any(_norm(row.get(f)) != target for f, target in active_text):
            continue
        if any(convert_to_float(row.get(f)) != target for f, target in active_num):
            continue
        out.append(row)
    return out

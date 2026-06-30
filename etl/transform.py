"""Map raw Firestore documents to domain entities (pure, testable).

Field-name mapping + type coercion only; geometry parsing is delegated to
``transform_geo``. The estado rule is honoured at the boundary: a Firestore
`estado` is carried over ONLY when it is a manual whitelist value
(Suspendido / Inaugurado); otherwise it is dropped and re-derived from avance.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping, Optional

from domain.geospatial.entities import Avance, Intervencion, UnidadProyecto
from domain.geospatial.estado import ESTADOS_MANUALES_NORM, normalizar_estado
from etl.transform_geo import parse_geometry


def _dec(value: Any) -> Optional[Decimal]:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None


def _int(value: Any) -> Optional[int]:
    d = _dec(value)
    return int(d) if d is not None else None


def _date(value: Any) -> Optional[date]:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).date()
    except ValueError:
        return None


def _datetime(value: Any) -> Optional[datetime]:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def _sid(value: Any) -> Optional[str]:
    """String id or None — never the literal string 'None'."""
    return str(value) if value is not None else None


def _estado_manual(estado: Any) -> Optional[str]:
    """Keep the stored estado only if it is a manual whitelist value."""
    if estado and normalizar_estado(str(estado)) in ESTADOS_MANUALES_NORM:
        return str(estado).strip()
    return None


def firestore_to_unidad(doc: Mapping[str, Any]) -> UnidadProyecto:
    return UnidadProyecto(
        upid=str(doc.get("upid") or doc.get("_id")),
        nombre_up=doc.get("nombre_up"),
        direccion=doc.get("direccion"),
        barrio_vereda=doc.get("barrio_vereda"),
        comuna_corregimiento=doc.get("comuna_corregimiento"),
        municipio=doc.get("municipio"),
        departamento=doc.get("departamento"),
        tipo_equipamiento=doc.get("tipo_equipamiento"),
        clase_up=doc.get("clase_up"),
        centro_gestor=doc.get("nombre_centro_gestor"),
        presupuesto_base=_dec(doc.get("presupuesto_base")),
        fuente_financiacion=doc.get("fuente_financiacion"),
        ano=_int(doc.get("ano")),
        fecha_inicio=_date(doc.get("fecha_inicio")),
        fecha_fin=_date(doc.get("fecha_fin")),
        bpin=(str(doc["bpin"]) if doc.get("bpin") is not None else None),
        referencia_contrato=doc.get("referencia_contrato"),
        referencia_proceso=doc.get("referencia_proceso"),
        plataforma=doc.get("plataforma"),
        geometry=parse_geometry(doc.get("geometry")),
    )


def firestore_to_intervencion(doc: Mapping[str, Any]) -> Intervencion:
    return Intervencion(
        intervencion_id=str(doc.get("intervencion_id") or doc.get("_id")),
        upid=_sid(doc.get("upid")),
        ano=_int(doc.get("ano")),
        tipo_intervencion=doc.get("tipo_intervencion"),
        presupuesto_base=_dec(doc.get("presupuesto_base")),
        avance_obra=_dec(doc.get("avance_obra")),
        cantidad=_dec(doc.get("cantidad")),
        fecha_inicio=_date(doc.get("fecha_inicio")),
        fecha_fin=_date(doc.get("fecha_fin")),
        fuente_financiacion=doc.get("fuente_financiacion"),
        bpin=(str(doc["bpin"]) if doc.get("bpin") is not None else None),
        referencia_contrato=doc.get("referencia_contrato"),
        referencia_proceso=doc.get("referencia_proceso"),
        url_proceso=doc.get("url_proceso"),
        descripcion=doc.get("descripcion_intervencion") or doc.get("descripcion"),
        estado_manual=_estado_manual(doc.get("estado")),
    )


def firestore_to_avance(doc: Mapping[str, Any]) -> Avance:
    return Avance(
        upid=_sid(doc.get("upid")),
        intervencion_id=_sid(doc.get("intervencion_id")),
        avance_obra=_dec(doc.get("avance_obra")) or Decimal("0"),
        fecha=_datetime(doc.get("fecha_avance") or doc.get("fecha") or doc.get("created_at"))
        or datetime(1970, 1, 1),
        descripcion=doc.get("descripcion_avance") or doc.get("descripcion"),
        etapa=doc.get("etapa"),
        volumen_ejecutado=_dec(doc.get("volumen_ejecutado")),
        archivo_s3_key=doc.get("archivo_s3_key"),
    )

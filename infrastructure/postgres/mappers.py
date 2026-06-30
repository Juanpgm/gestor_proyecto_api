"""Pure mapping helpers: ORM rows / objects -> domain entities and vice-versa.

No I/O -- all functions are side-effect free.
"""

from __future__ import annotations

import json
from decimal import Decimal
from typing import Optional

from domain.geospatial.entities import Avance, Intervencion, UnidadProyecto


def row_to_unidad(row) -> UnidadProyecto:
    """Map a SQLAlchemy Row (with geojson label + centro_gestor label) to domain entity.

    Expected columns: all UnidadProyecto scalar columns + geojson (str|None) from
    ST_AsGeoJSON, geometry_type and has_valid_geometry (computed), centro_gestor
    (name, str|None from outerjoin on CentroGestor).
    """
    geojson_str = row.geojson
    geometry = json.loads(geojson_str) if geojson_str else None
    return UnidadProyecto(
        upid=row.upid,
        nombre_up=row.nombre_up,
        direccion=row.direccion,
        barrio_vereda=row.barrio_vereda,
        comuna_corregimiento=row.comuna_corregimiento,
        municipio=row.municipio,
        departamento=row.departamento,
        tipo_equipamiento=row.tipo_equipamiento,
        clase_up=row.clase_up,
        centro_gestor=row.centro_gestor,  # name string from the join
        presupuesto_base=row.presupuesto_base,
        fuente_financiacion=row.fuente_financiacion,
        ano=row.ano,
        fecha_inicio=row.fecha_inicio,
        fecha_fin=row.fecha_fin,
        bpin=row.bpin,
        referencia_contrato=row.referencia_contrato,
        referencia_proceso=row.referencia_proceso,
        plataforma=row.plataforma,
        geometry=geometry,
        geometry_type=row.geometry_type,
        # has_valid_geometry is a nullable bool (None when geom is NULL) -> default False
        has_valid_geometry=bool(row.has_valid_geometry) if row.has_valid_geometry is not None else False,
    )


def row_to_intervencion(row_or_obj) -> Intervencion:
    """Map an ORM instance or Row for intervenciones_unidades_proyecto to domain entity."""
    return Intervencion(
        intervencion_id=row_or_obj.intervencion_id,
        upid=row_or_obj.upid,
        ano=row_or_obj.ano,
        tipo_intervencion=row_or_obj.tipo_intervencion,
        presupuesto_base=row_or_obj.presupuesto_base,
        avance_obra=row_or_obj.avance_obra,
        cantidad=row_or_obj.cantidad,
        fecha_inicio=row_or_obj.fecha_inicio,
        fecha_fin=row_or_obj.fecha_fin,
        fuente_financiacion=row_or_obj.fuente_financiacion,
        bpin=row_or_obj.bpin,
        referencia_contrato=row_or_obj.referencia_contrato,
        referencia_proceso=row_or_obj.referencia_proceso,
        url_proceso=row_or_obj.url_proceso,
        descripcion=row_or_obj.descripcion,
        estado_manual=row_or_obj.estado_manual,
    )


def row_to_avance(row_or_obj) -> Avance:
    """Map an ORM instance or Row for avances_unidades_proyecto to domain entity."""
    return Avance(
        id=row_or_obj.id,
        upid=row_or_obj.upid,
        intervencion_id=row_or_obj.intervencion_id,
        avance_obra=row_or_obj.avance_obra,
        descripcion=row_or_obj.descripcion,
        etapa=row_or_obj.etapa,
        volumen_ejecutado=row_or_obj.volumen_ejecutado,
        archivo_s3_key=row_or_obj.archivo_s3_key,
        fecha=row_or_obj.fecha,
    )


def unidad_to_values(up: UnidadProyecto, centro_gestor_id: Optional[int]) -> dict:
    """Return a column->value dict for insert/upsert.

    Excludes:
    - geom (caller injects the ST_SetSRID/ST_GeomFromGeoJSON expression)
    - generated columns: geometry_type, has_geometry, has_valid_geometry
    - created_at / updated_at (server defaults; updated_at set to func.now() in upsert)
    """
    return {
        "upid": up.upid,
        "nombre_up": up.nombre_up,
        "direccion": up.direccion,
        "barrio_vereda": up.barrio_vereda,
        "comuna_corregimiento": up.comuna_corregimiento,
        "municipio": up.municipio,
        "departamento": up.departamento,
        "tipo_equipamiento": up.tipo_equipamiento,
        "clase_up": up.clase_up,
        "centro_gestor_id": centro_gestor_id,
        "presupuesto_base": up.presupuesto_base,
        "fuente_financiacion": up.fuente_financiacion,
        "ano": up.ano,
        "fecha_inicio": up.fecha_inicio,
        "fecha_fin": up.fecha_fin,
        "bpin": up.bpin,
        "referencia_contrato": up.referencia_contrato,
        "referencia_proceso": up.referencia_proceso,
        "plataforma": up.plataforma,
    }


def intervencion_to_values(i: Intervencion) -> dict:
    """Return a column->value dict for intervención insert/upsert.

    Excludes created_at / updated_at (set via server defaults and func.now()).
    """
    return {
        "intervencion_id": i.intervencion_id,
        "upid": i.upid,
        "ano": i.ano,
        "tipo_intervencion": i.tipo_intervencion,
        "presupuesto_base": i.presupuesto_base,
        "avance_obra": i.avance_obra,
        "cantidad": i.cantidad,
        "fecha_inicio": i.fecha_inicio,
        "fecha_fin": i.fecha_fin,
        "fuente_financiacion": i.fuente_financiacion,
        "bpin": i.bpin,
        "referencia_contrato": i.referencia_contrato,
        "referencia_proceso": i.referencia_proceso,
        "url_proceso": i.url_proceso,
        "descripcion": i.descripcion,
        "estado_manual": i.estado_manual,
    }


def avance_to_values(a: Avance) -> dict:
    """Return a column->value dict for avance insert.

    Excludes id when None so BIGSERIAL auto-assigns it; includes it when
    explicitly set (e.g. for idempotent replays).
    Excludes created_at (server default).
    """
    values: dict = {
        "upid": a.upid,
        "intervencion_id": a.intervencion_id,
        "avance_obra": a.avance_obra,
        "descripcion": a.descripcion,
        "etapa": a.etapa,
        "volumen_ejecutado": a.volumen_ejecutado,
        "archivo_s3_key": a.archivo_s3_key,
        "fecha": a.fecha,
    }
    if a.id is not None:
        values["id"] = a.id
    return values

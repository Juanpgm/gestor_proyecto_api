"""Postgres + PostGIS adapter for UnidadesProyectoRepository.

Implements the port from domain/geospatial/ports.py using SQLAlchemy 2.0
async sessions and GeoAlchemy2 geometry functions.
"""

from __future__ import annotations

import json
from decimal import Decimal
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from domain.geospatial.entities import UnidadProyecto, UPQuery
from infrastructure.postgres.mappers import row_to_unidad, unidad_to_values
from infrastructure.postgres.models.geospatial import (
    CentroGestor as CentroGestorORM,
    UnidadProyecto as UnidadProyectoORM,
)


class PostgresUnidadesProyectoRepository:
    """Postgres implementation of UnidadesProyectoRepository.

    The caller owns the session lifecycle (commit / rollback). This class
    only flushes to make generated-column reads consistent within the same
    unit of work.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _base_select(self):
        """Select all domain-relevant columns + geojson + centro_gestor name."""
        UP = UnidadProyectoORM
        CG = CentroGestorORM
        return (
            select(
                UP.upid,
                UP.nombre_up,
                UP.direccion,
                UP.barrio_vereda,
                UP.comuna_corregimiento,
                UP.municipio,
                UP.departamento,
                UP.tipo_equipamiento,
                UP.clase_up,
                UP.presupuesto_base,
                UP.fuente_financiacion,
                UP.ano,
                UP.fecha_inicio,
                UP.fecha_fin,
                UP.bpin,
                UP.referencia_contrato,
                UP.referencia_proceso,
                UP.plataforma,
                UP.geometry_type,
                UP.has_valid_geometry,
                func.ST_AsGeoJSON(UP.geom).label("geojson"),
                CG.nombre.label("centro_gestor"),
            )
            .outerjoin(CG, UP.centro_gestor_id == CG.id)
        )

    def _apply_filters(self, stmt, query: UPQuery, include_pagination: bool = True):
        """Append WHERE clauses and optional LIMIT/OFFSET from a UPQuery."""
        UP = UnidadProyectoORM
        CG = CentroGestorORM

        if query.centro_gestor is not None:
            # The outerjoin is already in _base_select; filtering here makes it
            # behave as an inner join for this predicate.
            stmt = stmt.where(CG.nombre == query.centro_gestor)

        if query.only_valid_geometry:
            stmt = stmt.where(UP.has_valid_geometry.is_(True))

        if include_pagination:
            if query.limit is not None:
                stmt = stmt.limit(query.limit)
            stmt = stmt.offset(query.offset)

        return stmt

    async def _resolve_centro_id(self, nombre: Optional[str]) -> Optional[int]:
        """Get-or-create a CentroGestor by name.

        Returns None when nombre is None (allows NULL centro_gestor_id on UP).
        Thread-safe for concurrent inserts via on_conflict_do_nothing + re-select.
        """
        if nombre is None:
            return None

        CG = CentroGestorORM
        result = await self.session.execute(select(CG.id).where(CG.nombre == nombre))
        existing_id = result.scalar_one_or_none()
        if existing_id is not None:
            return existing_id

        # Insert, ignoring race-condition duplicates.
        await self.session.execute(
            pg_insert(CG).values(nombre=nombre).on_conflict_do_nothing()
        )
        await self.session.flush()

        # Re-select handles both the happy path and the conflict-do-nothing path.
        result = await self.session.execute(select(CG.id).where(CG.nombre == nombre))
        return result.scalar_one()

    # ------------------------------------------------------------------
    # Port implementation
    # ------------------------------------------------------------------

    async def get(self, upid: str) -> Optional[UnidadProyecto]:
        UP = UnidadProyectoORM
        stmt = self._base_select().where(UP.upid == upid)
        result = await self.session.execute(stmt)
        row = result.one_or_none()
        return row_to_unidad(row) if row is not None else None

    async def list(self, query: UPQuery = UPQuery()) -> list[UnidadProyecto]:
        stmt = self._apply_filters(self._base_select(), query)
        result = await self.session.execute(stmt)
        return [row_to_unidad(row) for row in result.all()]

    async def count(self, query: UPQuery = UPQuery()) -> int:
        """Return the total number of matching unidades (ignores limit/offset)."""
        UP = UnidadProyectoORM
        CG = CentroGestorORM
        stmt = (
            select(func.count())
            .select_from(UP)
            .outerjoin(CG, UP.centro_gestor_id == CG.id)
        )
        stmt = self._apply_filters(stmt, query, include_pagination=False)
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def upsert(self, up: UnidadProyecto) -> None:
        """Insert or update a unidad de proyecto.

        Resolves centro_gestor name -> FK id (get-or-create).
        Builds the PostGIS geometry expression from the domain geometry dict.
        Does NOT commit -- caller is responsible for the transaction.
        """
        UP = UnidadProyectoORM
        centro_gestor_id = await self._resolve_centro_id(up.centro_gestor)
        values = unidad_to_values(up, centro_gestor_id)

        # PostGIS geometry expression; None clears the column.
        geom_expr = (
            func.ST_SetSRID(func.ST_GeomFromGeoJSON(json.dumps(up.geometry)), 4326)
            if up.geometry is not None
            else None
        )

        stmt = pg_insert(UP).values(**values, geom=geom_expr)

        # All writable columns eligible for update on conflict.
        # Excludes: upid (PK), created_at (set once), geometry_type /
        # has_geometry / has_valid_geometry (DB-generated STORED columns).
        updatable_cols = [
            "nombre_up", "direccion", "barrio_vereda", "comuna_corregimiento",
            "municipio", "departamento", "tipo_equipamiento", "clase_up",
            "centro_gestor_id", "presupuesto_base", "fuente_financiacion",
            "ano", "fecha_inicio", "fecha_fin", "bpin", "referencia_contrato",
            "referencia_proceso", "plataforma", "geom",
        ]
        set_ = {col: getattr(stmt.excluded, col) for col in updatable_cols}
        set_["updated_at"] = func.now()

        stmt = stmt.on_conflict_do_update(index_elements=["upid"], set_=set_)
        await self.session.execute(stmt)
        await self.session.flush()

    async def as_feature_collection(self, query: UPQuery = UPQuery()) -> dict:
        """Return a GeoJSON FeatureCollection for the matching unidades.

        Scalar numeric fields (presupuesto_base) are converted to float for
        JSON serialisation. Date fields are ISO-formatted strings.
        """
        units = await self.list(query)
        features = []
        for up in units:
            props = {
                "upid": up.upid,
                "nombre_up": up.nombre_up,
                "direccion": up.direccion,
                "barrio_vereda": up.barrio_vereda,
                "comuna_corregimiento": up.comuna_corregimiento,
                "municipio": up.municipio,
                "departamento": up.departamento,
                "tipo_equipamiento": up.tipo_equipamiento,
                "clase_up": up.clase_up,
                "centro_gestor": up.centro_gestor,
                "presupuesto_base": (
                    float(up.presupuesto_base) if up.presupuesto_base is not None else None
                ),
                "fuente_financiacion": up.fuente_financiacion,
                "ano": up.ano,
                "fecha_inicio": up.fecha_inicio.isoformat() if up.fecha_inicio is not None else None,
                "fecha_fin": up.fecha_fin.isoformat() if up.fecha_fin is not None else None,
                "bpin": up.bpin,
                "referencia_contrato": up.referencia_contrato,
                "referencia_proceso": up.referencia_proceso,
                "plataforma": up.plataforma,
                "geometry_type": up.geometry_type,
                "has_valid_geometry": up.has_valid_geometry,
            }
            features.append({
                "type": "Feature",
                "geometry": up.geometry,
                "properties": props,
            })
        return {"type": "FeatureCollection", "features": features}

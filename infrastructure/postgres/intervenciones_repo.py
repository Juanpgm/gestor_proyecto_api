"""Postgres adapter for IntervencionesRepository.

Implements the port from domain/geospatial/ports.py using SQLAlchemy 2.0
async sessions. All writes are flushed but NOT committed -- the caller owns
the transaction.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Optional

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from domain.geospatial.entities import Avance, Intervencion
from infrastructure.postgres.mappers import (
    avance_to_values,
    intervencion_to_values,
    row_to_avance,
    row_to_intervencion,
)
from infrastructure.postgres.models.geospatial import (
    AvanceUnidadProyecto as AvanceORM,
    IntervencionUnidadProyecto as IntervencionORM,
)


class PostgresIntervencionesRepository:
    """Postgres implementation of IntervencionesRepository."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_by_up(self, upid: str) -> list[Intervencion]:
        """Return all intervenciones for a given upid, ordered by intervencion_id."""
        stmt = (
            select(IntervencionORM)
            .where(IntervencionORM.upid == upid)
            .order_by(IntervencionORM.intervencion_id)
        )
        result = await self.session.execute(stmt)
        return [row_to_intervencion(obj) for obj in result.scalars().all()]

    async def list_all(self) -> list[Intervencion]:
        """Return every intervención (one query) for batch consolidation."""
        stmt = select(IntervencionORM).order_by(IntervencionORM.upid)
        result = await self.session.execute(stmt)
        return [row_to_intervencion(obj) for obj in result.scalars().all()]

    async def upsert(self, intervencion: Intervencion) -> None:
        """Insert or update an intervención row.

        upid is NOT updated on conflict (FK must not change after creation).
        """
        values = intervencion_to_values(intervencion)
        stmt = pg_insert(IntervencionORM).values(**values)

        # Excludes: intervencion_id (PK), upid (FK -- must not change), created_at.
        updatable_cols = [
            "ano", "tipo_intervencion", "presupuesto_base", "avance_obra",
            "cantidad", "fecha_inicio", "fecha_fin", "fuente_financiacion",
            "bpin", "referencia_contrato", "referencia_proceso", "url_proceso",
            "descripcion", "estado_manual",
        ]
        set_ = {col: getattr(stmt.excluded, col) for col in updatable_cols}
        set_["updated_at"] = func.now()

        stmt = stmt.on_conflict_do_update(index_elements=["intervencion_id"], set_=set_)
        await self.session.execute(stmt)
        await self.session.flush()

    async def list_avances(self, intervencion_id: str) -> list[Avance]:
        """Return all avances for a given intervencion_id, ordered by fecha asc, id asc."""
        stmt = (
            select(AvanceORM)
            .where(AvanceORM.intervencion_id == intervencion_id)
            .order_by(AvanceORM.fecha.asc(), AvanceORM.id.asc())
        )
        result = await self.session.execute(stmt)
        return [row_to_avance(obj) for obj in result.scalars().all()]

    async def record_avance(self, avance: Avance) -> Optional[Decimal]:
        """Persist an avance and refresh the intervención's cached avance_obra.

        Steps:
        1. Insert the avance (BIGSERIAL id auto-assigned).
        2. Query the latest avance_obra for the intervención (by fecha DESC, id DESC).
        3. Update intervenciones.avance_obra with that value.
        4. Flush so the change is visible within the same unit of work.

        Returns the new cached value, or None if the intervencion has no avances.
        """
        values = avance_to_values(avance)
        await self.session.execute(pg_insert(AvanceORM).values(**values))
        await self.session.flush()

        # Determine latest avance_obra for this intervención.
        latest_stmt = (
            select(AvanceORM.avance_obra)
            .where(AvanceORM.intervencion_id == avance.intervencion_id)
            .order_by(AvanceORM.fecha.desc(), AvanceORM.id.desc())
            .limit(1)
        )
        result = await self.session.execute(latest_stmt)
        latest_avance: Optional[Decimal] = result.scalar_one_or_none()

        if latest_avance is not None:
            await self.session.execute(
                update(IntervencionORM)
                .where(IntervencionORM.intervencion_id == avance.intervencion_id)
                .values(avance_obra=latest_avance, updated_at=func.now())
            )
            await self.session.flush()

        return latest_avance

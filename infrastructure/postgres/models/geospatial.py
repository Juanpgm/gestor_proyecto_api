"""SQLAlchemy 2.0 ORM models for Wave-1 geospatial tables.

Generated columns (geometry_type, has_geometry, has_valid_geometry) are
declared as server-side read-only columns.  The Alembic migration owns the
GENERATED ALWAYS AS ... STORED expression; SQLAlchemy never emits it.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from geoalchemy2 import Geometry
from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Computed,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    Numeric,
    SmallInteger,
    String,
    Text,
    func,
)
from sqlalchemy import TIMESTAMP
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core_db.base import Base

# Postgres TIMESTAMPTZ — timezone-aware timestamp type reused across models.
TIMESTAMPTZ = TIMESTAMP(timezone=True)


class CentroGestor(Base):
    """Dimension table for management centres (centros gestores)."""

    __tablename__ = "centros_gestores"

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True, autoincrement=True)
    nombre: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")

    # Relationships
    unidades: Mapped[list["UnidadProyecto"]] = relationship(back_populates="centro_gestor")


class UnidadProyecto(Base):
    """Core geospatial unit of project (unidad de proyecto)."""

    __tablename__ = "unidades_proyecto"

    __table_args__ = (
        CheckConstraint(r"upid ~ '^UNP-[0-9]+$'", name="ck_unidades_proyecto_upid_format"),
        CheckConstraint("presupuesto_base >= 0", name="ck_unidades_proyecto_presupuesto_base"),
        CheckConstraint("ano BETWEEN 2000 AND 2100", name="ck_unidades_proyecto_ano"),
        Index("gix_up_geom", "geom", postgresql_using="gist"),
        # Partial index on valid geometries — created via op.execute in migration
        # because it references the generated column has_valid_geometry.
        # Index("gix_up_geom_valid", "geom", postgresql_using="gist",
        #       postgresql_where="has_valid_geometry"),  # handled in migration
    )

    upid: Mapped[str] = mapped_column(String, primary_key=True)
    nombre_up: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    direccion: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    barrio_vereda: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    comuna_corregimiento: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    municipio: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    departamento: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    tipo_equipamiento: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    clase_up: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    centro_gestor_id: Mapped[Optional[int]] = mapped_column(
        SmallInteger,
        ForeignKey("centros_gestores.id"),
        nullable=True,
        index=True,
    )

    presupuesto_base: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 2), nullable=True)
    fuente_financiacion: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ano: Mapped[Optional[int]] = mapped_column(SmallInteger, nullable=True)
    fecha_inicio: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    fecha_fin: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    bpin: Mapped[Optional[str]] = mapped_column(Text, nullable=True, index=True)
    referencia_contrato: Mapped[Optional[str]] = mapped_column(Text, nullable=True, index=True)
    referencia_proceso: Mapped[Optional[str]] = mapped_column(Text, nullable=True, index=True)
    plataforma: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Actual geometry column — supports Point/Line/Polygon/Multi variants.
    geom: Mapped[Optional[object]] = mapped_column(
        Geometry(geometry_type="GEOMETRY", srid=4326), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMPTZ, nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMPTZ, nullable=False, server_default=func.now()
    )

    # DB-generated columns (GENERATED ALWAYS AS ... STORED).
    # SQLAlchemy reads these but never writes them; the migration owns the expression.
    # DB-generated (STORED) columns — read-only, the migration owns the expressions.
    geometry_type: Mapped[Optional[str]] = mapped_column(
        Text, Computed("GeometryType(geom)", persisted=True), nullable=True
    )
    has_geometry: Mapped[Optional[bool]] = mapped_column(
        Boolean, Computed("geom IS NOT NULL", persisted=True), nullable=True
    )
    has_valid_geometry: Mapped[Optional[bool]] = mapped_column(
        Boolean,
        Computed(
            "geom IS NOT NULL AND ST_IsValid(geom) AND NOT "
            "(GeometryType(geom) = 'POINT' AND ST_X(geom) = 0 AND ST_Y(geom) = 0)",
            persisted=True,
        ),
        nullable=True,
    )

    # Relationships
    centro_gestor: Mapped[Optional["CentroGestor"]] = relationship(back_populates="unidades")
    intervenciones: Mapped[list["IntervencionUnidadProyecto"]] = relationship(
        back_populates="unidad", cascade="all, delete-orphan"
    )
    avances: Mapped[list["AvanceUnidadProyecto"]] = relationship(
        back_populates="unidad", cascade="all, delete-orphan"
    )
    reconocimientos: Mapped[list["Reconocimiento360"]] = relationship(
        back_populates="unidad", cascade="all, delete-orphan"
    )
    solicitudes: Mapped[list["SolicitudCambioUnidadProyecto"]] = relationship(
        back_populates="unidad"
    )


class IntervencionUnidadProyecto(Base):
    """An intervention record linked to a unidad_proyecto."""

    __tablename__ = "intervenciones_unidades_proyecto"

    __table_args__ = (
        CheckConstraint("presupuesto_base >= 0", name="ck_intervenciones_unidades_proyecto_presupuesto_base"),
        CheckConstraint(
            "avance_obra BETWEEN 0 AND 100",
            name="ck_intervenciones_unidades_proyecto_avance_obra",
        ),
        # CHECK on estado_manual uses unaccent() — added via op.execute in migration.
        Index("ix_intervenciones_unidades_proyecto_upid", "upid"),
        Index("ix_intervenciones_unidades_proyecto_referencia_proceso", "referencia_proceso"),
        # Partial index for frente activo — added via op.execute in migration.
    )

    intervencion_id: Mapped[str] = mapped_column(String, primary_key=True)
    upid: Mapped[str] = mapped_column(
        Text, ForeignKey("unidades_proyecto.upid", ondelete="CASCADE"), nullable=False
    )
    ano: Mapped[Optional[int]] = mapped_column(SmallInteger, nullable=True)
    tipo_intervencion: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    presupuesto_base: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 2), nullable=True)
    avance_obra: Mapped[Optional[Decimal]] = mapped_column(Numeric(6, 3), nullable=True)
    cantidad: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 3), nullable=True)
    fecha_inicio: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    fecha_fin: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    fuente_financiacion: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    bpin: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    referencia_contrato: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    referencia_proceso: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    url_proceso: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    descripcion: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # Only 'Suspendido' / 'Inaugurado' accepted (accent-insensitive CHECK in DB).
    estado_manual: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMPTZ, nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMPTZ, nullable=False, server_default=func.now()
    )

    # Relationships
    unidad: Mapped["UnidadProyecto"] = relationship(back_populates="intervenciones")
    avances: Mapped[list["AvanceUnidadProyecto"]] = relationship(
        back_populates="intervencion", cascade="all, delete-orphan"
    )
    solicitudes: Mapped[list["SolicitudCambioIntervencion"]] = relationship(
        back_populates="intervencion"
    )


class AvanceUnidadProyecto(Base):
    """Append-only progress record for an intervention."""

    __tablename__ = "avances_unidades_proyecto"

    __table_args__ = (
        CheckConstraint(
            "avance_obra BETWEEN 0 AND 100",
            name="ck_avances_unidades_proyecto_avance_obra",
        ),
        Index("ix_avance_interv_fecha", "intervencion_id", "fecha"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    upid: Mapped[str] = mapped_column(
        Text, ForeignKey("unidades_proyecto.upid", ondelete="CASCADE"), nullable=False
    )
    intervencion_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("intervenciones_unidades_proyecto.intervencion_id", ondelete="CASCADE"),
        nullable=False,
    )
    avance_obra: Mapped[Decimal] = mapped_column(Numeric(6, 3), nullable=False)
    descripcion: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    etapa: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    volumen_ejecutado: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 3), nullable=True)
    archivo_s3_key: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    fecha: Mapped[datetime] = mapped_column(TIMESTAMPTZ, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMPTZ, nullable=False, server_default=func.now()
    )

    # Relationships
    unidad: Mapped["UnidadProyecto"] = relationship(back_populates="avances")
    intervencion: Mapped["IntervencionUnidadProyecto"] = relationship(back_populates="avances")


class Reconocimiento360(Base):
    """360-degree photo record associated with a unidad_proyecto."""

    __tablename__ = "reconocimiento_360"

    __table_args__ = (
        Index("gix_360_gps", "coordinates_gps", postgresql_using="gist"),
        Index("ix_reconocimiento_360_upid", "upid"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    upid: Mapped[str] = mapped_column(
        Text, ForeignKey("unidades_proyecto.upid", ondelete="CASCADE"), nullable=False
    )
    coordinates_gps: Mapped[Optional[object]] = mapped_column(
        Geometry(geometry_type="POINT", srid=4326), nullable=True
    )
    s3_key_antes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    s3_key_durante: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    s3_key_despues: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    registrado_por: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    fecha: Mapped[datetime] = mapped_column(TIMESTAMPTZ, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMPTZ, nullable=False, server_default=func.now()
    )

    # Relationships
    unidad: Mapped["UnidadProyecto"] = relationship(back_populates="reconocimientos")


class SolicitudCambioUnidadProyecto(Base):
    """Change request for a unidad_proyecto (workflow: pending -> approved/rejected)."""

    __tablename__ = "solicitudes_cambios_unidades_proyecto"

    __table_args__ = (
        Index(
            "ix_sol_up_estado",
            "estado",
            postgresql_where="estado = 'pending'",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    upid: Mapped[str] = mapped_column(
        Text, ForeignKey("unidades_proyecto.upid"), nullable=False
    )
    # estado_solicitud enum: pending | approved | rejected — enforced by DB enum type.
    estado: Mapped[str] = mapped_column(
        String, nullable=False, server_default="pending"
    )
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    solicitado_por: Mapped[str] = mapped_column(Text, nullable=False)
    revisado_por: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    motivo_rechazo: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMPTZ, nullable=False, server_default=func.now()
    )
    decided_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMPTZ, nullable=True)

    # Relationships
    unidad: Mapped["UnidadProyecto"] = relationship(back_populates="solicitudes")
    cambios: Mapped[list["CambioImplementadoUnidadProyecto"]] = relationship(
        back_populates="solicitud"
    )


class SolicitudCambioIntervencion(Base):
    """Change request for an intervention record."""

    __tablename__ = "solicitudes_cambios_intervenciones"

    __table_args__ = (
        Index(
            "ix_sol_int_estado",
            "estado",
            postgresql_where="estado = 'pending'",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    intervencion_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("intervenciones_unidades_proyecto.intervencion_id"),
        nullable=False,
    )
    estado: Mapped[str] = mapped_column(String, nullable=False, server_default="pending")
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    solicitado_por: Mapped[str] = mapped_column(Text, nullable=False)
    revisado_por: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    motivo_rechazo: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMPTZ, nullable=False, server_default=func.now()
    )
    decided_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMPTZ, nullable=True)

    # Relationships
    intervencion: Mapped["IntervencionUnidadProyecto"] = relationship(back_populates="solicitudes")
    cambios: Mapped[list["CambioImplementadoIntervencion"]] = relationship(
        back_populates="solicitud"
    )


class CambioImplementadoUnidadProyecto(Base):
    """Append-only audit record of approved changes applied to a unidad_proyecto."""

    __tablename__ = "cambios_implementados_unidades_proyecto"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    solicitud_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("solicitudes_cambios_unidades_proyecto.id"),
        nullable=True,
    )
    upid: Mapped[str] = mapped_column(Text, nullable=False)
    diff: Mapped[dict] = mapped_column(JSONB, nullable=False)
    aplicado_por: Mapped[str] = mapped_column(Text, nullable=False)
    aplicado_at: Mapped[datetime] = mapped_column(
        TIMESTAMPTZ, nullable=False, server_default=func.now()
    )

    # Relationships
    solicitud: Mapped[Optional["SolicitudCambioUnidadProyecto"]] = relationship(
        back_populates="cambios"
    )


class CambioImplementadoIntervencion(Base):
    """Append-only audit record of approved changes applied to an intervention."""

    __tablename__ = "cambios_implementados_intervenciones"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    solicitud_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("solicitudes_cambios_intervenciones.id"),
        nullable=True,
    )
    intervencion_id: Mapped[str] = mapped_column(Text, nullable=False)
    diff: Mapped[dict] = mapped_column(JSONB, nullable=False)
    aplicado_por: Mapped[str] = mapped_column(Text, nullable=False)
    aplicado_at: Mapped[datetime] = mapped_column(
        TIMESTAMPTZ, nullable=False, server_default=func.now()
    )

    # Relationships
    solicitud: Mapped[Optional["SolicitudCambioIntervencion"]] = relationship(
        back_populates="cambios"
    )


class UpQualityReport(Base):
    """Quality report summarising a data-quality scan run."""

    __tablename__ = "up_quality_reports"

    __table_args__ = (
        Index(
            "ux_quality_latest",
            "scope",
            unique=True,
            postgresql_where="is_latest",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    run_at: Mapped[datetime] = mapped_column(
        TIMESTAMPTZ, nullable=False, server_default=func.now()
    )
    scope: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[dict] = mapped_column(JSONB, nullable=False)
    is_latest: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")

    issues: Mapped[list["UpQualityIssue"]] = relationship(
        back_populates="report", cascade="all, delete-orphan"
    )


class UpQualityIssue(Base):
    """Individual data-quality issue found in a quality report."""

    __tablename__ = "up_quality_issues"

    __table_args__ = (
        Index("ix_issues_sev", "severity", "report_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    report_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("up_quality_reports.id", ondelete="CASCADE"),
        nullable=False,
    )
    upid: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    intervencion_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # issue_severity enum: S1/S2/S3/S4 — enforced by DB enum type.
    severity: Mapped[str] = mapped_column(String, nullable=False)
    code: Mapped[str] = mapped_column(Text, nullable=False)
    detail: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    report: Mapped["UpQualityReport"] = relationship(back_populates="issues")

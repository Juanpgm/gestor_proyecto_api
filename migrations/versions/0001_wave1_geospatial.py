"""Wave 1 — geospatial core schema.

Revision ID: 0001_wave1
Revises: None
Create Date: 2026-06-29

Hand-written migration.  Creates all extensions, enums, function, tables,
generated columns, indexes, and the v_intervenciones view for Wave 1.

Downgrade drops objects in reverse FK order.  Extensions (postgis, unaccent,
pgcrypto) are left in place — dropping postgis is destructive on shared DBs.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from geoalchemy2 import Geometry
from sqlalchemy.dialects.postgresql import ENUM as PG_ENUM, JSONB, UUID as PG_UUID

# revision identifiers, used by Alembic.
revision: str = "0001_wave1"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Shared ENUM type objects. create_type=False so op.create_table never auto-emits
# CREATE TYPE; the types are created exactly once via .create(checkfirst=True).
estado_solicitud_enum = PG_ENUM(
    "pending", "approved", "rejected", name="estado_solicitud", create_type=False
)
issue_severity_enum = PG_ENUM(
    "S1", "S2", "S3", "S4", name="issue_severity", create_type=False
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _exec(sql: str) -> None:
    op.execute(sa.text(sql))


# ---------------------------------------------------------------------------
# Upgrade
# ---------------------------------------------------------------------------

def upgrade() -> None:
    # 1. Extensions
    _exec("CREATE EXTENSION IF NOT EXISTS postgis")
    _exec("CREATE EXTENSION IF NOT EXISTS unaccent")
    _exec("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    # 1b. IMMUTABLE wrapper around unaccent().
    #     unaccent() is only STABLE, so it cannot be used directly in index
    #     expressions or generated columns. Naming the dictionary explicitly
    #     ('unaccent') makes the wrapper safe to mark IMMUTABLE (documented trick).
    _exec(r"""
CREATE OR REPLACE FUNCTION f_unaccent(text)
RETURNS text LANGUAGE sql IMMUTABLE PARALLEL SAFE STRICT AS
$func$ SELECT unaccent('unaccent', $1) $func$;
""")

    # 2. Enum types (created once; columns reference the same create_type=False objects).
    bind = op.get_bind()
    estado_solicitud_enum.create(bind, checkfirst=True)
    issue_severity_enum.create(bind, checkfirst=True)

    # 3. calcular_estado function
    #    IMMUTABLE — relies on f_unaccent (immutable) instead of raw unaccent.
    _exec(r"""
CREATE OR REPLACE FUNCTION calcular_estado(avance NUMERIC, estado_manual TEXT)
RETURNS TEXT IMMUTABLE LANGUAGE sql AS $func$
  SELECT CASE
    WHEN estado_manual IS NOT NULL
         AND lower(f_unaccent(estado_manual)) IN ('suspendido','inaugurado')
      THEN estado_manual
    WHEN avance IS NULL OR avance < 0.5  THEN 'En alistamiento'
    WHEN avance >= 99.5                  THEN 'Terminado'
    ELSE 'En ejecución'
  END;
$func$;
""")

    # 4. centros_gestores
    op.create_table(
        "centros_gestores",
        sa.Column("id", sa.SmallInteger, primary_key=True, autoincrement=True),
        sa.Column("nombre", sa.Text, nullable=False),
        sa.Column("activo", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.UniqueConstraint("nombre", name="uq_centros_gestores_nombre"),
    )
    # Functional index on normalized name (uses unaccent — must be via execute).
    _exec("CREATE INDEX ix_centros_norm ON centros_gestores (lower(f_unaccent(nombre)))")

    # 5. unidades_proyecto — base columns only; generated columns follow via ALTER.
    op.create_table(
        "unidades_proyecto",
        sa.Column("upid", sa.Text, primary_key=True),
        sa.Column("nombre_up", sa.Text, nullable=True),
        sa.Column("direccion", sa.Text, nullable=True),
        sa.Column("barrio_vereda", sa.Text, nullable=True),
        sa.Column("comuna_corregimiento", sa.Text, nullable=True),
        sa.Column("municipio", sa.Text, nullable=True),
        sa.Column("departamento", sa.Text, nullable=True),
        sa.Column("tipo_equipamiento", sa.Text, nullable=True),
        sa.Column("clase_up", sa.Text, nullable=True),
        sa.Column(
            "centro_gestor_id",
            sa.SmallInteger,
            sa.ForeignKey("centros_gestores.id", name="fk_up_centro_gestor_id"),
            nullable=True,
        ),
        sa.Column("presupuesto_base", sa.Numeric(18, 2), nullable=True),
        sa.Column("fuente_financiacion", sa.Text, nullable=True),
        sa.Column("ano", sa.SmallInteger, nullable=True),
        sa.Column("fecha_inicio", sa.Date, nullable=True),
        sa.Column("fecha_fin", sa.Date, nullable=True),
        sa.Column("bpin", sa.Text, nullable=True),
        sa.Column("referencia_contrato", sa.Text, nullable=True),
        sa.Column("referencia_proceso", sa.Text, nullable=True),
        sa.Column("plataforma", sa.Text, nullable=True),
        sa.Column("geom", Geometry(geometry_type="GEOMETRY", srid=4326), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        # Named CHECK constraints.
        sa.CheckConstraint(r"upid ~ '^UNP-[0-9]+$'", name="ck_unidades_proyecto_upid_format"),
        sa.CheckConstraint("presupuesto_base >= 0", name="ck_unidades_proyecto_presupuesto_base"),
        sa.CheckConstraint("ano BETWEEN 2000 AND 2100", name="ck_unidades_proyecto_ano"),
    )

    # Generated columns — must be added via ALTER TABLE (PostGIS functions are STABLE).
    _exec("""
ALTER TABLE unidades_proyecto
  ADD COLUMN geometry_type TEXT
    GENERATED ALWAYS AS (GeometryType(geom)) STORED
""")
    _exec("""
ALTER TABLE unidades_proyecto
  ADD COLUMN has_geometry BOOLEAN
    GENERATED ALWAYS AS (geom IS NOT NULL) STORED
""")
    _exec("""
ALTER TABLE unidades_proyecto
  ADD COLUMN has_valid_geometry BOOLEAN
    GENERATED ALWAYS AS (
      geom IS NOT NULL
      AND ST_IsValid(geom)
      AND NOT (GeometryType(geom) = 'POINT' AND ST_X(geom) = 0 AND ST_Y(geom) = 0)
    ) STORED
""")

    # Indexes for unidades_proyecto.
    _exec("CREATE INDEX gix_up_geom ON unidades_proyecto USING GIST (geom)")
    op.create_index("ix_up_centro_gestor_id", "unidades_proyecto", ["centro_gestor_id"])
    _exec("CREATE INDEX ix_up_bpin ON unidades_proyecto (bpin) WHERE bpin IS NOT NULL")
    op.create_index("ix_up_referencia_contrato", "unidades_proyecto", ["referencia_contrato"])
    op.create_index("ix_up_referencia_proceso", "unidades_proyecto", ["referencia_proceso"])
    _exec(
        "CREATE INDEX gix_up_geom_valid ON unidades_proyecto USING GIST (geom) "
        "WHERE has_valid_geometry"
    )

    # 6. intervenciones_unidades_proyecto
    op.create_table(
        "intervenciones_unidades_proyecto",
        sa.Column("intervencion_id", sa.Text, primary_key=True),
        sa.Column(
            "upid",
            sa.Text,
            sa.ForeignKey(
                "unidades_proyecto.upid",
                ondelete="CASCADE",
                name="fk_intervenciones_upid",
            ),
            nullable=False,
        ),
        sa.Column("ano", sa.SmallInteger, nullable=True),
        sa.Column("tipo_intervencion", sa.Text, nullable=True),
        sa.Column("presupuesto_base", sa.Numeric(18, 2), nullable=True),
        sa.Column("avance_obra", sa.Numeric(6, 3), nullable=True),
        sa.Column("cantidad", sa.Numeric(18, 3), nullable=True),
        sa.Column("fecha_inicio", sa.Date, nullable=True),
        sa.Column("fecha_fin", sa.Date, nullable=True),
        sa.Column("fuente_financiacion", sa.Text, nullable=True),
        sa.Column("bpin", sa.Text, nullable=True),
        sa.Column("referencia_contrato", sa.Text, nullable=True),
        sa.Column("referencia_proceso", sa.Text, nullable=True),
        sa.Column("url_proceso", sa.Text, nullable=True),
        sa.Column("descripcion", sa.Text, nullable=True),
        sa.Column("estado_manual", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "presupuesto_base >= 0",
            name="ck_intervenciones_unidades_proyecto_presupuesto_base",
        ),
        sa.CheckConstraint(
            "avance_obra BETWEEN 0 AND 100",
            name="ck_intervenciones_unidades_proyecto_avance_obra",
        ),
    )

    # CHECK on estado_manual uses unaccent() — added via execute to avoid quoting issues.
    _exec("""
ALTER TABLE intervenciones_unidades_proyecto
  ADD CONSTRAINT ck_intervenciones_estado_manual
  CHECK (
    estado_manual IS NULL
    OR lower(f_unaccent(estado_manual)) IN ('suspendido','inaugurado')
  )
""")

    op.create_index(
        "ix_intervenciones_unidades_proyecto_upid",
        "intervenciones_unidades_proyecto",
        ["upid"],
    )
    op.create_index(
        "ix_intervenciones_unidades_proyecto_referencia_proceso",
        "intervenciones_unidades_proyecto",
        ["referencia_proceso"],
    )
    _exec(
        "CREATE INDEX ix_int_frente_activo ON intervenciones_unidades_proyecto (upid) "
        "WHERE presupuesto_base >= 100000000"
    )

    # 7. v_intervenciones view
    _exec("""
CREATE VIEW v_intervenciones AS
  SELECT i.*, calcular_estado(i.avance_obra, i.estado_manual) AS estado
  FROM intervenciones_unidades_proyecto i
""")

    # 8. avances_unidades_proyecto
    op.create_table(
        "avances_unidades_proyecto",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column(
            "upid",
            sa.Text,
            sa.ForeignKey(
                "unidades_proyecto.upid",
                ondelete="CASCADE",
                name="fk_avances_upid",
            ),
            nullable=False,
        ),
        sa.Column(
            "intervencion_id",
            sa.Text,
            sa.ForeignKey(
                "intervenciones_unidades_proyecto.intervencion_id",
                ondelete="CASCADE",
                name="fk_avances_intervencion_id",
            ),
            nullable=False,
        ),
        sa.Column("avance_obra", sa.Numeric(6, 3), nullable=False),
        sa.Column("descripcion", sa.Text, nullable=True),
        sa.Column("etapa", sa.Text, nullable=True),
        sa.Column("volumen_ejecutado", sa.Numeric(18, 3), nullable=True),
        sa.Column("archivo_s3_key", sa.Text, nullable=True),
        sa.Column("fecha", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "avance_obra BETWEEN 0 AND 100",
            name="ck_avances_unidades_proyecto_avance_obra",
        ),
    )
    # Composite descending index: use execute because Alembic create_index
    # does not natively express DESC on a composite key portably.
    _exec(
        "CREATE INDEX ix_avance_interv_fecha "
        "ON avances_unidades_proyecto (intervencion_id, fecha DESC)"
    )

    # 9. reconocimiento_360
    op.create_table(
        "reconocimiento_360",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column(
            "upid",
            sa.Text,
            sa.ForeignKey(
                "unidades_proyecto.upid",
                ondelete="CASCADE",
                name="fk_reconocimiento_360_upid",
            ),
            nullable=False,
        ),
        sa.Column(
            "coordinates_gps",
            Geometry(geometry_type="POINT", srid=4326),
            nullable=True,
        ),
        sa.Column("s3_key_antes", sa.Text, nullable=True),
        sa.Column("s3_key_durante", sa.Text, nullable=True),
        sa.Column("s3_key_despues", sa.Text, nullable=True),
        sa.Column("registrado_por", sa.Text, nullable=True),
        sa.Column("fecha", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    _exec("CREATE INDEX gix_360_gps ON reconocimiento_360 USING GIST (coordinates_gps)")
    op.create_index("ix_reconocimiento_360_upid", "reconocimiento_360", ["upid"])

    # 10. solicitudes_cambios_unidades_proyecto
    op.create_table(
        "solicitudes_cambios_unidades_proyecto",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column(
            "upid",
            sa.Text,
            sa.ForeignKey(
                "unidades_proyecto.upid",
                name="fk_sol_cambios_up_upid",
            ),
            nullable=False,
        ),
        sa.Column(
            "estado",
            estado_solicitud_enum,
            nullable=False,
            server_default="pending",
        ),
        sa.Column("payload", JSONB(), nullable=False),
        sa.Column("solicitado_por", sa.Text, nullable=False),
        sa.Column("revisado_por", sa.Text, nullable=True),
        sa.Column("motivo_rechazo", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("decided_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    _exec(
        "CREATE INDEX ix_sol_up_estado ON solicitudes_cambios_unidades_proyecto (estado) "
        "WHERE estado = 'pending'"
    )

    # 11. solicitudes_cambios_intervenciones
    op.create_table(
        "solicitudes_cambios_intervenciones",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column(
            "intervencion_id",
            sa.Text,
            sa.ForeignKey(
                "intervenciones_unidades_proyecto.intervencion_id",
                name="fk_sol_cambios_int_intervencion_id",
            ),
            nullable=False,
        ),
        sa.Column(
            "estado",
            estado_solicitud_enum,
            nullable=False,
            server_default="pending",
        ),
        sa.Column("payload", JSONB(), nullable=False),
        sa.Column("solicitado_por", sa.Text, nullable=False),
        sa.Column("revisado_por", sa.Text, nullable=True),
        sa.Column("motivo_rechazo", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("decided_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    _exec(
        "CREATE INDEX ix_sol_int_estado ON solicitudes_cambios_intervenciones (estado) "
        "WHERE estado = 'pending'"
    )

    # 12. cambios_implementados_unidades_proyecto
    op.create_table(
        "cambios_implementados_unidades_proyecto",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column(
            "solicitud_id",
            sa.BigInteger,
            sa.ForeignKey(
                "solicitudes_cambios_unidades_proyecto.id",
                name="fk_cambios_impl_up_solicitud_id",
            ),
            nullable=True,
        ),
        sa.Column("upid", sa.Text, nullable=False),
        sa.Column("diff", JSONB(), nullable=False),
        sa.Column("aplicado_por", sa.Text, nullable=False),
        sa.Column(
            "aplicado_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    # 13. cambios_implementados_intervenciones
    op.create_table(
        "cambios_implementados_intervenciones",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column(
            "solicitud_id",
            sa.BigInteger,
            sa.ForeignKey(
                "solicitudes_cambios_intervenciones.id",
                name="fk_cambios_impl_int_solicitud_id",
            ),
            nullable=True,
        ),
        sa.Column("intervencion_id", sa.Text, nullable=False),
        sa.Column("diff", JSONB(), nullable=False),
        sa.Column("aplicado_por", sa.Text, nullable=False),
        sa.Column(
            "aplicado_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    # 14. up_quality_reports
    op.create_table(
        "up_quality_reports",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column(
            "run_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("scope", sa.Text, nullable=False),
        sa.Column("summary", JSONB(), nullable=False),
        sa.Column(
            "is_latest", sa.Boolean, nullable=False, server_default=sa.text("false")
        ),
    )
    _exec(
        "CREATE UNIQUE INDEX ux_quality_latest ON up_quality_reports (scope) "
        "WHERE is_latest"
    )

    # 15. up_quality_issues
    op.create_table(
        "up_quality_issues",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column(
            "report_id",
            sa.BigInteger,
            sa.ForeignKey(
                "up_quality_reports.id",
                ondelete="CASCADE",
                name="fk_up_quality_issues_report_id",
            ),
            nullable=False,
        ),
        sa.Column("upid", sa.Text, nullable=True),
        sa.Column("intervencion_id", sa.Text, nullable=True),
        sa.Column(
            "severity",
            issue_severity_enum,
            nullable=False,
        ),
        sa.Column("code", sa.Text, nullable=False),
        sa.Column("detail", JSONB(), nullable=True),
    )
    op.create_index("ix_issues_sev", "up_quality_issues", ["severity", "report_id"])

    # 16. user_sessions  (needs pgcrypto for gen_random_uuid())
    op.create_table(
        "user_sessions",
        sa.Column(
            "id",
            PG_UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("user_uid", sa.Text, nullable=False),
        sa.Column("centro_gestor_id", sa.SmallInteger, nullable=True),
        sa.Column(
            "started_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "last_seen_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("ended_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("user_agent", sa.Text, nullable=True),
        sa.Column("ip_hash", sa.Text, nullable=True),
    )

    # 17. activity_events
    op.create_table(
        "activity_events",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column(
            "session_id",
            PG_UUID(as_uuid=True),
            sa.ForeignKey(
                "user_sessions.id",
                name="fk_activity_events_session_id",
            ),
            nullable=True,
        ),
        sa.Column("user_uid", sa.Text, nullable=False),
        sa.Column(
            "occurred_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("feature", sa.Text, nullable=False),
        sa.Column("action", sa.Text, nullable=False),
        sa.Column("entity_type", sa.Text, nullable=True),
        sa.Column("entity_id", sa.Text, nullable=True),
        sa.Column("metadata", JSONB(), nullable=True),
    )
    op.create_index("ix_events_session", "activity_events", ["session_id", "occurred_at"])
    op.create_index("ix_events_feature", "activity_events", ["feature", "occurred_at"])
    op.create_index("ix_events_user", "activity_events", ["user_uid", "occurred_at"])


# ---------------------------------------------------------------------------
# Downgrade — drop in reverse FK order
# ---------------------------------------------------------------------------

def downgrade() -> None:
    # activity_events -> user_sessions
    op.drop_index("ix_events_user", table_name="activity_events")
    op.drop_index("ix_events_feature", table_name="activity_events")
    op.drop_index("ix_events_session", table_name="activity_events")
    op.drop_table("activity_events")
    op.drop_table("user_sessions")

    # quality
    op.drop_index("ix_issues_sev", table_name="up_quality_issues")
    op.drop_table("up_quality_issues")
    _exec("DROP INDEX IF EXISTS ux_quality_latest")
    op.drop_table("up_quality_reports")

    # audit / change implementation
    op.drop_table("cambios_implementados_intervenciones")
    op.drop_table("cambios_implementados_unidades_proyecto")

    # change requests
    _exec("DROP INDEX IF EXISTS ix_sol_int_estado")
    op.drop_table("solicitudes_cambios_intervenciones")
    _exec("DROP INDEX IF EXISTS ix_sol_up_estado")
    op.drop_table("solicitudes_cambios_unidades_proyecto")

    # reconocimiento_360
    _exec("DROP INDEX IF EXISTS gix_360_gps")
    op.drop_index("ix_reconocimiento_360_upid", table_name="reconocimiento_360")
    op.drop_table("reconocimiento_360")

    # avances
    _exec("DROP INDEX IF EXISTS ix_avance_interv_fecha")
    op.drop_table("avances_unidades_proyecto")

    # view + intervenciones
    _exec("DROP VIEW IF EXISTS v_intervenciones")
    _exec("DROP INDEX IF EXISTS ix_int_frente_activo")
    op.drop_index(
        "ix_intervenciones_unidades_proyecto_referencia_proceso",
        table_name="intervenciones_unidades_proyecto",
    )
    op.drop_index(
        "ix_intervenciones_unidades_proyecto_upid",
        table_name="intervenciones_unidades_proyecto",
    )
    op.drop_table("intervenciones_unidades_proyecto")

    # unidades_proyecto
    _exec("DROP INDEX IF EXISTS gix_up_geom_valid")
    op.drop_index("ix_up_referencia_proceso", table_name="unidades_proyecto")
    op.drop_index("ix_up_referencia_contrato", table_name="unidades_proyecto")
    _exec("DROP INDEX IF EXISTS ix_up_bpin")
    op.drop_index("ix_up_centro_gestor_id", table_name="unidades_proyecto")
    _exec("DROP INDEX IF EXISTS gix_up_geom")
    op.drop_table("unidades_proyecto")

    # centros_gestores
    _exec("DROP INDEX IF EXISTS ix_centros_norm")
    op.drop_table("centros_gestores")

    # functions
    _exec("DROP FUNCTION IF EXISTS calcular_estado(NUMERIC, TEXT)")
    _exec("DROP FUNCTION IF EXISTS f_unaccent(text)")

    # enums
    _exec("DROP TYPE IF EXISTS issue_severity")
    _exec("DROP TYPE IF EXISTS estado_solicitud")

    # Extensions intentionally left in place.

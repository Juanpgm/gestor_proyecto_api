"""Alembic async migration environment.

Runs migrations using SQLAlchemy's async engine (asyncpg driver).  PostGIS-
managed objects are excluded from autogenerate so Alembic never tries to drop
or modify spatial_ref_sys, topology, or tiger schemas.
"""

from __future__ import annotations

import asyncio
import os
import sys

# Ensure back/ is on sys.path so that core_db and infrastructure are importable.
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from logging.config import fileConfig

from alembic import context
from geoalchemy2 import alembic_helpers
from sqlalchemy.ext.asyncio import create_async_engine

from core_db.base import Base
from core_db.settings import get_db_settings

# Import model modules so their tables are registered on Base.metadata.
import infrastructure.postgres.models.geospatial  # noqa: F401
import infrastructure.postgres.models.metrics  # noqa: F401

# ---------------------------------------------------------------------------
# Alembic Config object
# ---------------------------------------------------------------------------
config = context.config

# Interpret the config file for Python logging if present.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# ---------------------------------------------------------------------------
# PostGIS / extension exclusion helpers
# ---------------------------------------------------------------------------
_POSTGIS_TABLES = frozenset({"spatial_ref_sys"})
_EXCLUDED_SCHEMAS = frozenset({"tiger", "tiger_data", "topology"})


def _calitrack_include_object(obj, name, type_, reflected, compare_to):
    """Return False for PostGIS-managed objects that must never be touched."""
    if type_ == "table":
        schema = getattr(obj, "schema", None)
        if name in _POSTGIS_TABLES:
            return False
        if schema in _EXCLUDED_SCHEMAS:
            return False
    if type_ == "schema" and name in _EXCLUDED_SCHEMAS:
        return False
    return True


def _include_object(obj, name, type_, reflected, compare_to):
    """Compose geoalchemy2's include_object with our PostGIS exclusion filter."""
    # GeoAlchemy2 may exclude geometry_columns / geography_columns views.
    if not alembic_helpers.include_object(obj, name, type_, reflected, compare_to):
        return False
    return _calitrack_include_object(obj, name, type_, reflected, compare_to)


# ---------------------------------------------------------------------------
# Offline migrations (generate SQL script without a live DB connection)
# ---------------------------------------------------------------------------
def run_migrations_offline() -> None:
    url = get_db_settings().database_url
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_object=_include_object,
        render_item=alembic_helpers.render_item,
        process_revision_directives=alembic_helpers.writer,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


# ---------------------------------------------------------------------------
# Online migrations (async engine)
# ---------------------------------------------------------------------------
def do_run_migrations(connection):
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        include_object=_include_object,
        render_item=alembic_helpers.render_item,
        process_revision_directives=alembic_helpers.writer,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    url = get_db_settings().database_url
    connectable = create_async_engine(
        url,
        echo=False,
        connect_args={"statement_cache_size": 0},
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())

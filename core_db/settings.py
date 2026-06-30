"""Database settings loaded from environment variables / .env file."""

from __future__ import annotations

import functools

from pydantic_settings import BaseSettings, SettingsConfigDict


class DbSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Primary connection URL (asyncpg driver).
    # Local dev default uses host port 5433 (5432 is taken by a native PG service).
    database_url: str = (
        "postgresql+asyncpg://calitrack:calitrack@localhost:5433/calitrack_dev"
    )

    # Echo SQL statements to stdout (useful for debugging; keep False in prod).
    db_echo: bool = False

    # Active data backend: firestore | postgres | dual
    data_backend: str = "firestore"

    # Which adapter is the primary read source when data_backend="dual".
    dual_read_primary: str = "firestore"


@functools.lru_cache(maxsize=1)
def get_db_settings() -> DbSettings:
    """Return a cached singleton of DbSettings."""
    return DbSettings()

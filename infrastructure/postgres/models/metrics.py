"""SQLAlchemy 2.0 ORM models for session and activity tracking tables."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

import uuid

from sqlalchemy import BigInteger, ForeignKey, Index, SmallInteger, Text, TIMESTAMP, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core_db.base import Base

# Postgres TIMESTAMPTZ — timezone-aware timestamp type reused across models.
TIMESTAMPTZ = TIMESTAMP(timezone=True)

_UUID = PG_UUID(as_uuid=True)


class UserSession(Base):
    """Tracks individual authenticated user sessions (Firebase uid stored opaquely)."""

    __tablename__ = "user_sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        _UUID,  # type: ignore[arg-type]
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    user_uid: Mapped[str] = mapped_column(Text, nullable=False)
    centro_gestor_id: Mapped[Optional[int]] = mapped_column(SmallInteger, nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        TIMESTAMPTZ, nullable=False, server_default=func.now()
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        TIMESTAMPTZ, nullable=False, server_default=func.now()
    )
    ended_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMPTZ, nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # SHA-256 hash of the client IP — no raw PII stored.
    ip_hash: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    events: Mapped[list["ActivityEvent"]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )


class ActivityEvent(Base):
    """Append-only activity log entry for feature-level usage analytics."""

    __tablename__ = "activity_events"

    __table_args__ = (
        Index("ix_events_session", "session_id", "occurred_at"),
        Index("ix_events_feature", "feature", "occurred_at"),
        Index("ix_events_user", "user_uid", "occurred_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    session_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        _UUID,  # type: ignore[arg-type]
        ForeignKey("user_sessions.id"),
        nullable=True,
    )
    user_uid: Mapped[str] = mapped_column(Text, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(
        TIMESTAMPTZ, nullable=False, server_default=func.now()
    )
    feature: Mapped[str] = mapped_column(Text, nullable=False)
    action: Mapped[str] = mapped_column(Text, nullable=False)
    entity_type: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    entity_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # `metadata` is reserved by the Declarative API, so the Python attribute is
    # renamed while the DB column keeps the name "metadata".
    event_metadata: Mapped[Optional[dict]] = mapped_column(
        "metadata", JSONB, nullable=True
    )

    session: Mapped[Optional["UserSession"]] = relationship(back_populates="events")

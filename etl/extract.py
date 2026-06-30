"""Firestore extraction for the v3 ETL (read-only).

Reuses the existing Firebase client. If credentials are not configured locally
(the common case on a dev machine without the `calitrack-44403` service
account), the functions raise a clear, actionable error instead of failing
obscurely — the rest of the pipeline (transform, parity, seed) stays usable.
"""

from __future__ import annotations

import logging
from typing import Any, Iterator

logger = logging.getLogger(__name__)

# Firestore collection names for the Wave-1 geospatial core.
COLLECTION_UNIDADES = "unidades_proyecto"
COLLECTION_INTERVENCIONES = "intervenciones_unidades_proyecto"
COLLECTION_AVANCES = "avances_unidades_proyecto"


class FirestoreUnavailableError(RuntimeError):
    """Raised when Firestore credentials are not configured for extraction."""


def get_firestore_db():
    """Return a Firestore client or raise FirestoreUnavailableError.

    Credentials resolution lives in `database/firebase_config.py`. Locally this
    needs the `calitrack-44403` read-only service account (or ADC); without it
    we fail loudly so the operator knows to provide credentials.
    """
    try:
        from database.firebase_config import get_firestore_client
    except Exception as exc:  # pragma: no cover - import wiring
        raise FirestoreUnavailableError(
            f"Could not import Firebase config: {exc}"
        ) from exc

    db = get_firestore_client()
    if db is None:
        raise FirestoreUnavailableError(
            "Firestore client unavailable. Configure read-only credentials for "
            "project 'calitrack-44403' (service account JSON or `gcloud auth "
            "application-default login`) before running the live ETL."
        )
    return db


def extract_collection(name: str, limit: int | None = None) -> Iterator[dict[str, Any]]:
    """Stream documents of a Firestore collection as dicts (id under '_id')."""
    db = get_firestore_db()
    query = db.collection(name)
    if limit is not None:
        query = query.limit(limit)
    count = 0
    for doc in query.stream():
        data = doc.to_dict() or {}
        data.setdefault("_id", doc.id)
        yield data
        count += 1
    logger.info("Extracted %d documents from %s", count, name)


def extract_unidades(limit: int | None = None) -> list[dict[str, Any]]:
    return list(extract_collection(COLLECTION_UNIDADES, limit))


def extract_intervenciones(limit: int | None = None) -> list[dict[str, Any]]:
    return list(extract_collection(COLLECTION_INTERVENCIONES, limit))


def extract_avances(limit: int | None = None) -> list[dict[str, Any]]:
    return list(extract_collection(COLLECTION_AVANCES, limit))

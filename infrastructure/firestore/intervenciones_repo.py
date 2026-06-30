"""Firestore read-only adapter for IntervencionesRepository.

IO is offloaded to threads via asyncio.to_thread because the Firestore SDK
is synchronous/blocking. Mapping via firestore_to_intervencion /
firestore_to_avance stays inline (pure functions).

upsert() and record_avance() raise NotImplementedError: this adapter is
read-only in v3 parity mode and must never write to production Firestore.
"""

from __future__ import annotations

import asyncio
from decimal import Decimal
from typing import Any, Optional

from google.cloud.firestore_v1 import FieldFilter

from domain.geospatial.entities import Avance, Intervencion
from etl.extract import COLLECTION_AVANCES, COLLECTION_INTERVENCIONES, get_firestore_db
from etl.transform import firestore_to_avance, firestore_to_intervencion


# ---------------------------------------------------------------------------
# Synchronous helpers (run inside asyncio.to_thread)
# ---------------------------------------------------------------------------

def _fetch_intervenciones_by_up(db, upid: str) -> list[dict[str, Any]]:
    docs: list[dict[str, Any]] = []
    for snap in (
        db.collection(COLLECTION_INTERVENCIONES)
        .where(filter=FieldFilter("upid", "==", upid))
        .stream()
    ):
        data = snap.to_dict() or {}
        data.setdefault("_id", snap.id)
        docs.append(data)
    return docs


def _fetch_avances_by_intervencion(
    db, intervencion_id: str
) -> list[dict[str, Any]]:
    docs: list[dict[str, Any]] = []
    for snap in (
        db.collection(COLLECTION_AVANCES)
        .where(filter=FieldFilter("intervencion_id", "==", intervencion_id))
        .stream()
    ):
        data = snap.to_dict() or {}
        data.setdefault("_id", snap.id)
        docs.append(data)
    return docs


# ---------------------------------------------------------------------------
# Repository
# ---------------------------------------------------------------------------

class FirestoreIntervencionesRepository:
    """Read-only Firestore adapter implementing IntervencionesRepository.

    Args:
        db: An existing Firestore client. Pass ``None`` (default) to have the
            repository lazily resolve credentials via ``get_firestore_db()``
            on the first call. Inject an explicit client in tests.
    """

    def __init__(self, db=None) -> None:
        self._db = db

    def _get_db(self):
        if self._db is None:
            self._db = get_firestore_db()
        return self._db

    async def list_by_up(self, upid: str) -> list[Intervencion]:
        """Return all intervenciones for a given upid from Firestore."""
        db = self._get_db()
        raw = await asyncio.to_thread(_fetch_intervenciones_by_up, db, upid)
        return [firestore_to_intervencion(doc) for doc in raw]

    async def upsert(self, intervencion: Intervencion) -> None:
        raise NotImplementedError(
            "Firestore adapter is read-only in v3 parity mode"
        )

    async def list_avances(self, intervencion_id: str) -> list[Avance]:
        """Return all avances for a given intervencion_id from Firestore."""
        db = self._get_db()
        raw = await asyncio.to_thread(
            _fetch_avances_by_intervencion, db, intervencion_id
        )
        return [firestore_to_avance(doc) for doc in raw]

    async def record_avance(self, avance: Avance) -> Optional[Decimal]:
        raise NotImplementedError(
            "Firestore adapter is read-only in v3 parity mode"
        )

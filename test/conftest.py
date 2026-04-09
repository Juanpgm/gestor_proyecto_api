"""
Shared fixtures for all tests.
Provides mocked Firebase services and FastAPI TestClient.
"""

import pytest
import sys
import os
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone

# Ensure project root is on the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """FastAPI TestClient"""
    from main import app
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def mock_firebase_user():
    """Mock de usuario autenticado de Firebase"""
    user = MagicMock()
    user.uid = "test_uid_123"
    user.email = "test@example.com"
    user.display_name = "Test User"
    user.email_verified = True
    user.phone_number = "+573001234567"
    user.user_metadata = MagicMock()
    user.user_metadata.creation_timestamp = int(datetime.now(timezone.utc).timestamp() * 1000)
    return user


@pytest.fixture
def mock_firestore_db():
    """Mock Firestore client that returns empty collections by default"""
    db = MagicMock()
    # Default: empty collection stream
    db.collection.return_value.stream.return_value = iter([])
    db.collection.return_value.document.return_value.get.return_value = MagicMock(exists=False)
    return db


@pytest.fixture
def mock_super_admin_context(mock_firebase_user, mock_firestore_db):
    """Patch Firebase auth + Firestore to simulate a super_admin user"""
    mock_firestore_db.collection.return_value.document.return_value.get.return_value = MagicMock(
        exists=True,
        to_dict=MagicMock(return_value={
            "uid": "admin_uid",
            "email": "admin@cali.gov.co",
            "roles": ["super_admin"],
            "is_active": True,
            "nombre_centro_gestor": "DATIC",
            "name": "Admin User",
        }),
    )

    patches = {
        "verify": patch(
            "firebase_admin.auth.verify_id_token",
            return_value={"uid": "admin_uid", "email": "admin@cali.gov.co", "email_verified": True},
        ),
        "firestore": patch(
            "database.firebase_config.get_firestore_client",
            return_value=mock_firestore_db,
        ),
    }

    mocks = {k: p.start() for k, p in patches.items()}
    yield mocks
    for p in patches.values():
        p.stop()

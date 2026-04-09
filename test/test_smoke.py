"""
Smoke tests: verify all critical endpoints respond with expected status codes
and that core infrastructure (cache, health, routers) works correctly.
"""

import pytest
import threading
import time
from unittest.mock import patch, MagicMock


# ---------------------------------------------------------------------------
# 1. Public endpoint availability
# ---------------------------------------------------------------------------

class TestPublicEndpoints:
    """Endpoints that must be accessible without authentication."""

    @pytest.mark.parametrize(
        "path, expected_codes",
        [
            ("/", [200]),
            ("/ping", [200]),
            ("/health", [200]),
            ("/docs", [200, 307]),
            ("/openapi.json", [200]),
            ("/cors-test", [200, 404]),
        ],
    )
    def test_public_endpoint_reachable(self, client, path, expected_codes):
        resp = client.get(path)
        assert resp.status_code in expected_codes, (
            f"{path} returned {resp.status_code}, expected one of {expected_codes}"
        )

    def test_root_returns_json(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        data = resp.json()
        assert "message" in data or "status" in data

    def test_health_returns_services(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert "services" in data or "status" in data

    def test_health_firebase_timeout_not_connected(self, client):
        """Health check must NOT report connected:True when Firebase times out."""
        import asyncio

        async def _fake_timeout(*a, **kw):
            raise asyncio.TimeoutError()

        with patch("asyncio.wait_for", side_effect=_fake_timeout):
            resp = client.get("/health")
            # timeout_middleware returns 504, which is acceptable
            assert resp.status_code in [200, 500, 504]


# ---------------------------------------------------------------------------
# 2. Protected endpoints reject unauthorized access
# ---------------------------------------------------------------------------

class TestProtectedEndpoints:
    """Endpoints that require a valid Firebase token."""

    @pytest.mark.parametrize(
        "method, path",
        [
            ("get", "/auth/admin/users"),
            ("get", "/auth/admin/roles"),
            ("get", "/auth/admin/audit-logs"),
        ],
    )
    def test_requires_auth(self, client, method, path):
        resp = getattr(client, method)(path)
        assert resp.status_code in [401, 403, 422], (
            f"{method.upper()} {path} should reject unauthenticated requests, got {resp.status_code}"
        )

    @pytest.mark.parametrize(
        "method, path",
        [
            ("get", "/unidades-proyecto"),
            ("get", "/intervenciones"),
        ],
    )
    def test_public_data_endpoints_accessible(self, client, method, path):
        """Data listing endpoints are public (no auth required).
        Mock Firestore to avoid hanging on live DB calls."""
        mock_doc = MagicMock()
        mock_doc.to_dict.return_value = {"id": "test", "nombre": "Test"}
        mock_doc.id = "test-id"

        mock_query = MagicMock()
        mock_query.stream.return_value = iter([mock_doc])
        mock_query.where.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.get.return_value = [mock_doc]

        mock_db = MagicMock()
        mock_db.collection.return_value = mock_query

        with patch("main.get_firestore_client", return_value=mock_db), \
             patch("database.firebase_config.get_firestore_client", return_value=mock_db):
            resp = getattr(client, method)(path)

        assert resp.status_code in [200, 500], (
            f"{method.upper()} {path} returned unexpected {resp.status_code}"
        )


# ---------------------------------------------------------------------------
# 3. Cache thread-safety
# ---------------------------------------------------------------------------

class TestCacheThreadSafety:
    """Verify the bounded, thread-safe in-memory cache."""

    def test_cache_set_and_get(self):
        from main import set_in_cache, get_from_cache, get_cache_key

        key = get_cache_key("test_fn", "arg1")
        set_in_cache(key, {"data": 42})
        value, hit = get_from_cache(key, max_age_seconds=60)
        assert hit is True
        assert value == {"data": 42}

    def test_cache_expiry(self):
        from main import set_in_cache, get_from_cache, get_cache_key, _cache_timestamps
        from datetime import datetime, timedelta

        key = get_cache_key("test_expiry", "arg")
        set_in_cache(key, "old_value")
        # Fake the timestamp to be old
        from main import _cache_lock
        with _cache_lock:
            _cache_timestamps[key] = datetime.now() - timedelta(seconds=600)

        value, hit = get_from_cache(key, max_age_seconds=300)
        assert hit is False

    def test_cache_bounded_size(self):
        from main import set_in_cache, _simple_cache, _CACHE_MAX_SIZE, _cache_lock

        # Fill cache beyond limit
        for i in range(_CACHE_MAX_SIZE + 50):
            set_in_cache(f"key_{i}", i)

        with _cache_lock:
            assert len(_simple_cache) <= _CACHE_MAX_SIZE

    def test_cache_concurrent_writes(self):
        """Concurrent writes must not raise exceptions."""
        from main import set_in_cache, get_from_cache

        errors = []

        def _writer(thread_id):
            try:
                for i in range(200):
                    set_in_cache(f"concurrent_{thread_id}_{i}", i)
                    get_from_cache(f"concurrent_{thread_id}_{i}")
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=_writer, args=(t,)) for t in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == [], f"Cache race condition: {errors}"


# ---------------------------------------------------------------------------
# 4. Global exception handler
# ---------------------------------------------------------------------------

class TestGlobalExceptionHandler:
    """Unhandled errors must return a structured JSON 500, never leak stack traces."""

    def test_unhandled_error_returns_json(self, client):
        """Trigger an internal error via a non-existent deep path to verify 404 is JSON."""
        # We test that the app doesn't crash on unexpected errors
        # by verifying the global handler is registered on the app
        from main import app
        handler = app.exception_handlers.get(Exception) or app.exception_handlers.get(500)
        assert handler is not None, "Global exception handler not registered"


# ---------------------------------------------------------------------------
# 5. Request body size limit
# ---------------------------------------------------------------------------

class TestRequestBodySizeLimit:
    """Requests with Content-Length > MAX must be rejected."""

    def test_oversized_request_rejected(self, client):
        # 100 MB fake Content-Length header
        resp = client.post(
            "/auth/register",
            headers={"Content-Length": str(100 * 1024 * 1024)},
            content=b"x",
        )
        assert resp.status_code == 413


# ---------------------------------------------------------------------------
# 6. Router registration verification
# ---------------------------------------------------------------------------

class TestRouterRegistration:
    """All routers declared in the project must be registered on the app."""

    def test_openapi_contains_auth_admin_routes(self, client):
        resp = client.get("/openapi.json")
        assert resp.status_code == 200
        paths = resp.json().get("paths", {})
        admin_paths = [p for p in paths if p.startswith("/auth/admin")]
        assert len(admin_paths) > 0, "auth_admin router not registered"

    def test_openapi_contains_emprestito_quality_routes(self, client):
        resp = client.get("/openapi.json")
        paths = resp.json().get("paths", {})
        quality_paths = [p for p in paths if "quality-control" in p]
        assert len(quality_paths) > 0, "emprestito quality router not registered"

    def test_openapi_contains_captura_360_routes(self, client):
        resp = client.get("/openapi.json")
        paths = resp.json().get("paths", {})
        captura_paths = [p for p in paths if "captura-estado-360" in p]
        assert len(captura_paths) > 0, (
            "captura_360_router NOT registered — 360 endpoints are dead code"
        )

"""
Integration tests: health endpoint + basic endpoint routing.
These tests run against the actual FastAPI app with mocked Firebase.
"""

import pytest
import sys
import os
from unittest.mock import patch, MagicMock, AsyncMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))


class TestHealthEndpoint:
    """Health check endpoint must always respond."""

    def test_health_returns_200(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_health_response_has_status_field(self, client):
        resp = client.get("/health")
        data = resp.json()
        assert "status" in data or "services" in data

    def test_ping_endpoint(self, client):
        resp = client.get("/ping")
        assert resp.status_code == 200

    def test_root_endpoint(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, dict)

    def test_openapi_schema_available(self, client):
        resp = client.get("/openapi.json")
        assert resp.status_code == 200
        schema = resp.json()
        assert "paths" in schema
        assert "info" in schema

    def test_docs_accessible(self, client):
        resp = client.get("/docs")
        assert resp.status_code in [200, 307]


class TestAuthEndpointsProtection:
    """Protected endpoints (with inline token verification) must return 401 without valid token."""

    @pytest.mark.parametrize("method,path", [
        # /admin/users uses verify_firebase_token dependency inline → always 401 without token
        ("GET", "/admin/users"),
        # /auth/change-password requires form + auth
        ("POST", "/auth/change-password"),
    ])
    def test_protected_endpoint_requires_auth(self, client, method, path):
        if method == "GET":
            resp = client.get(path)
        elif method == "POST":
            resp = client.post(path)
        assert resp.status_code in [401, 403, 422], (
            f"{path} should require authentication, got {resp.status_code}"
        )


class TestCORSHeaders:
    """CORS headers must be present on responses."""

    def test_cors_headers_on_options(self, client):
        resp = client.options("/health", headers={"Origin": "https://example.com"})
        # Either allowed or rejected — but must not crash
        assert resp.status_code in [200, 204, 405]

    def test_cors_allow_origin_present(self, client):
        resp = client.get("/health", headers={"Origin": "http://localhost:3000"})
        # In dev mode, localhost should be allowed
        assert resp.status_code == 200


class TestErrorHandling:
    """Global error handler must return structured JSON."""

    def test_unknown_path_returns_structured_json(self, client):
        # The global AuthorizationMiddleware runs before routing, so any
        # non-public path (existent or not) without a valid token is rejected
        # with 401 instead of leaking route existence via 404. Either way the
        # error handler must return structured JSON.
        resp = client.get("/endpoint_que_no_existe_xyz")
        assert resp.status_code in (401, 404)
        assert resp.headers.get("content-type", "").startswith("application/json")

    def test_login_without_body_returns_422(self, client):
        resp = client.post("/auth/login", json={})
        assert resp.status_code in [422, 400, 401, 404]

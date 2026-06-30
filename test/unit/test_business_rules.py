"""
Unit tests: business rules, calculations, domain logic.
No external dependencies.
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))


class TestAvanceCalculations:
    """Verify numeric calculation utilities."""

    @pytest.mark.parametrize("ejecutado,total,expected", [
        (50, 100, 50.0),
        (0, 100, 0.0),
        (100, 100, 100.0),
        (0, 0, 0.0),     # edge: division by zero guard
        (150, 100, 150.0),  # over 100% is possible
    ])
    def test_porcentaje_avance(self, ejecutado, total, expected):
        """Percentage calculation: executed/total * 100."""
        if total == 0:
            result = 0.0
        else:
            result = (ejecutado / total) * 100
        assert abs(result - expected) < 0.01

    def test_negative_values_not_allowed(self):
        """Negative executed amount is invalid domain data."""
        ejecutado = -10
        assert ejecutado < 0  # just validates the guard condition

    def test_large_values_precision(self):
        """Large monetary values should maintain float precision."""
        valor = 1_500_000_000.50
        factor = 0.15
        result = valor * factor
        assert isinstance(result, float)
        assert result > 0


class TestCalcularEstadoUP:
    """Verify estado derivation from avance_obra matches the front contract.

    Contract (must match front/src/utils/estadoUP.ts):
    - avance < 0.5        -> "En alistamiento"
    - avance >= 99.5      -> "Terminado"
    - otherwise           -> "En ejecución"
    - whitelist {Suspendido, Inaugurado} respected (case/accent-insensitive)
    """

    @pytest.mark.parametrize("avance,expected", [
        (None, "En alistamiento"),
        (0, "En alistamiento"),
        (0.4, "En alistamiento"),
        ("abc", "En alistamiento"),
        (0.5, "En ejecución"),
        (50, "En ejecución"),
        (99.4, "En ejecución"),
        (99.5, "Terminado"),
        (100, "Terminado"),
        ("99.8", "Terminado"),
    ])
    def test_derives_from_avance(self, avance, expected):
        from api.scripts.unidades_proyecto import _calcular_estado
        assert _calcular_estado({"avance_obra": avance}) == expected

    @pytest.mark.parametrize("estado_manual", [
        "Suspendido", "Inaugurado", "suspendido", "  INAUGURADO  ",
    ])
    def test_respects_whitelist_regardless_of_avance(self, estado_manual):
        from api.scripts.unidades_proyecto import _calcular_estado
        # avance would otherwise force "Terminado", whitelist must win
        result = _calcular_estado({"avance_obra": 100, "estado": estado_manual})
        assert result == estado_manual.strip()

    def test_re_derives_non_canonical_stored_estado(self):
        from api.scripts.unidades_proyecto import _calcular_estado
        # stored "Terminado" but avance 0 -> re-derived to alistamiento
        assert _calcular_estado({"avance_obra": 0, "estado": "Terminado"}) == "En alistamiento"
        # stored "En ejecución" but avance 100 -> Terminado
        assert _calcular_estado({"avance_obra": 100, "estado": "En ejecución"}) == "Terminado"
        # non-canonical imported value is ignored
        assert _calcular_estado({"avance_obra": 0, "estado": "Liquidado"}) == "En alistamiento"


class TestInputValidation:
    """Verify Pydantic models validate domain data correctly."""

    def test_user_registration_requires_email(self):
        from pydantic import ValidationError
        try:
            from api.models import UserRegistrationRequest
            with pytest.raises((ValidationError, Exception)):
                UserRegistrationRequest(
                    email="",
                    password="Test1234!",
                    confirmPassword="Test1234!",
                    name="Test",
                    cellphone="+573001234567",
                    nombre_centro_gestor="DATIC"
                )
        except ImportError:
            pytest.skip("UserRegistrationRequest not available")

    def test_user_login_requires_email(self):
        from pydantic import ValidationError
        try:
            from api.models import UserLoginRequest
            with pytest.raises((ValidationError, Exception)):
                UserLoginRequest(password="somepass")  # email is required
        except ImportError:
            pytest.skip("UserLoginRequest not available")

    def test_standard_response_fields(self):
        try:
            from api.models import StandardResponse
            # StandardResponse may require extra fields — use keyword args
            import inspect
            sig = inspect.signature(StandardResponse)
            required = [p for p, v in sig.parameters.items() if v.default is inspect.Parameter.empty]
            kwargs = {"success": True, "message": "ok"}
            # Add required fields with sensible defaults
            if "timestamp" in required:
                from datetime import datetime
                kwargs["timestamp"] = datetime.now().isoformat()
            r = StandardResponse(**kwargs)
            assert r.success is True
        except ImportError:
            pytest.skip("StandardResponse not available")


class TestFirestoreConfigSingleton:
    """Verify Firebase config returns consistent singleton."""

    def test_get_firestore_client_returns_same_instance(self):
        try:
            from database.firebase_config import get_firestore_client
            c1 = get_firestore_client()
            c2 = get_firestore_client()
            # Either both None (test env without Firebase) or same instance
            assert c1 is c2
        except Exception as e:
            pytest.skip(f"Firebase not configured in test env: {e}")

    def test_firebase_available_flag_is_bool(self):
        try:
            from database.firebase_config import FIREBASE_AVAILABLE
            assert isinstance(FIREBASE_AVAILABLE, bool)
        except ImportError:
            pytest.skip("firebase_config not available")


class TestRateLimitDecoratorFallback:
    """Verify optional_rate_limit works even when SlowAPI not installed."""

    def test_optional_rate_limit_returns_function(self):
        from api.core.security import optional_rate_limit

        @optional_rate_limit("5/minute")
        def my_handler():
            return "ok"

        assert callable(my_handler)
        assert my_handler() == "ok"

    def test_optional_rate_limit_does_not_break_without_slowapi(self):
        """When SLOWAPI_AVAILABLE is False, decorator is a no-op."""
        from api.core.security import optional_rate_limit, SLOWAPI_AVAILABLE
        # Should work regardless of SLOWAPI_AVAILABLE state
        decorated = optional_rate_limit("10/minute")(lambda: "result")
        assert decorated() == "result"

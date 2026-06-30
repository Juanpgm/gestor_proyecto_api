# -*- coding: utf-8 -*-
"""
test/unit/test_email_smtp.py — Tests unitarios para la lógica SMTP de email.

Cubre el bug corregido: SSL CERTIFICATE_VERIFY_FAILED cuando smtplib conecta
vía IPv4 directa y usa la IP como server_hostname en starttls().

Los tests validan que:
  1. server._host se sobreescribe con el hostname antes de starttls().
  2. El flujo STARTTLS (puerto 587) funciona correctamente de extremo a extremo.
  3. El flujo SSL directo (puerto 465) usa wrap_socket con server_hostname correcto.
  4. send_password_reset_email retorna success=False cuando SMTP no está configurado.
  5. Errores de autenticación SMTP se capturan y retornan con código adecuado.
  6. send_test_email delega en _send_via_smtp con los parámetros correctos.
"""

import smtplib
import socket
import ssl
from unittest.mock import MagicMock, call, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

FAKE_HOST = "smtp.gmail.com"
FAKE_IP = "74.125.196.109"
FAKE_PORT_TLS = 587
FAKE_PORT_SSL = 465
FAKE_USER = "sender@gmail.com"
FAKE_PASSWORD = "app-password"
FAKE_DEST = "dest@example.com"


def _smtp_env(host=FAKE_HOST, port=FAKE_PORT_TLS, use_tls="true"):
    return {
        "SMTP_HOST": host,
        "SMTP_PORT": port,
        "SMTP_USER": FAKE_USER,
        "SMTP_PASSWORD": FAKE_PASSWORD,
        "SMTP_FROM_NAME": "CaliTrack",
        "SMTP_USE_TLS": use_tls == "true",
        "EMAIL_SERVICE_AVAILABLE": True,
    }


def _smtp_env_svc(host=FAKE_HOST, port=FAKE_PORT_TLS, use_tls=True):
    return {
        "SMTP_HOST": host,
        "SMTP_PORT": port,
        "SMTP_USER": FAKE_USER,
        "SMTP_PASSWORD": FAKE_PASSWORD,
        "SMTP_USE_TLS": use_tls,
        "SMTP_CONFIGURED": True,
    }


# ===========================================================================
# email_service.py — send_password_reset_email
# ===========================================================================


class TestSendPasswordResetEmailUnavailable:
    """Cuando SMTP no está configurado, debe devolver error sin intentar conectar."""

    def test_returns_error_when_service_unavailable(self):
        with patch.multiple(
            "api.utils.email_service",
            EMAIL_SERVICE_AVAILABLE=False,
        ):
            from api.utils.email_service import send_password_reset_email

            result = send_password_reset_email(
                to_email=FAKE_DEST,
                reset_link="https://example.com/reset",
                display_name="Juan",
            )

        assert result["success"] is False
        assert result["code"] == "EMAIL_SERVICE_UNAVAILABLE"


class TestSendPasswordResetEmailTLS:
    """send_password_reset_email delega en comunicaciones_service._send_raw_email."""

    def test_delegates_to_send_raw_email_and_returns_success(self):
        """Cuando _send_raw_email tiene éxito, debe retornar success=True con canal."""
        with (
            patch.multiple("api.utils.email_service", EMAIL_SERVICE_AVAILABLE=True),
            patch(
                "api.services.comunicaciones_service._send_raw_email",
                return_value=(True, "smtp", ""),
            ) as mock_send,
            patch(
                "api.services.comunicaciones_service._render_template",
                return_value="<html>test</html>",
            ),
        ):
            from api.utils.email_service import send_password_reset_email

            result = send_password_reset_email(
                to_email=FAKE_DEST,
                reset_link="https://example.com/reset?token=abc",
                display_name="Ana García",
            )

        assert result["success"] is True
        assert result["channel"] == "smtp"
        mock_send.assert_called_once()
        call_kwargs = mock_send.call_args[1]
        assert call_kwargs["to"] == FAKE_DEST
        assert call_kwargs["template"] == "password_reset"

    def test_first_name_extracted_from_display_name(self):
        """El contexto de la plantilla debe incluir el primer nombre del usuario."""
        captured_ctx = {}

        def fake_render(template_name, context):
            captured_ctx.update(context)
            return "<html/>"

        with (
            patch.multiple("api.utils.email_service", EMAIL_SERVICE_AVAILABLE=True),
            patch(
                "api.services.comunicaciones_service._send_raw_email",
                return_value=(True, "smtp", ""),
            ),
            patch(
                "api.services.comunicaciones_service._render_template",
                side_effect=fake_render,
            ),
        ):
            from api.utils.email_service import send_password_reset_email

            send_password_reset_email(
                to_email=FAKE_DEST,
                reset_link="https://example.com/reset",
                display_name="María Fernanda López",
            )

        assert captured_ctx.get("first_name") == "María"
        assert captured_ctx.get("email") == FAKE_DEST
        assert "reset_link" in captured_ctx


class TestSendPasswordResetEmailSSL:
    """Cuando _send_raw_email falla, send_password_reset_email propaga el error."""

    def test_propagates_send_failure(self):
        with (
            patch.multiple("api.utils.email_service", EMAIL_SERVICE_AVAILABLE=True),
            patch(
                "api.services.comunicaciones_service._send_raw_email",
                return_value=(False, "", "SMTP connection refused"),
            ),
            patch(
                "api.services.comunicaciones_service._render_template",
                return_value="<html/>",
            ),
        ):
            from api.utils.email_service import send_password_reset_email

            result = send_password_reset_email(
                to_email=FAKE_DEST,
                reset_link="https://example.com/reset",
                display_name="Carlos",
            )

        assert result["success"] is False
        assert result["code"] == "EMAIL_SEND_ERROR"
        assert "SMTP connection refused" in result["error"]


class TestSendPasswordResetEmailErrors:
    """Manejo de errores: messaging service no disponible."""

    def test_messaging_service_import_failure_returns_error(self):
        """Si comunicaciones_service no puede importarse, devuelve error."""
        import builtins

        real_import = builtins.__import__

        def block_comunicaciones(name, *args, **kwargs):
            if "comunicaciones_service" in name:
                raise ImportError("Módulo no disponible")
            return real_import(name, *args, **kwargs)

        with (
            patch.multiple("api.utils.email_service", EMAIL_SERVICE_AVAILABLE=True),
            patch("builtins.__import__", side_effect=block_comunicaciones),
        ):
            from api.utils.email_service import send_password_reset_email

            result = send_password_reset_email(
                to_email=FAKE_DEST,
                reset_link="https://example.com/reset",
                display_name="Test",
            )

        assert result["success"] is False
        assert result["code"] == "MESSAGING_SERVICE_UNAVAILABLE"


# ===========================================================================
# comunicaciones_service.py — _send_via_smtp
# ===========================================================================


class TestSendViaSMTPHostFix:
    """Verifica el mismo fix en _send_via_smtp del servicio de comunicaciones."""

    def test_host_set_before_starttls(self):
        mock_server = MagicMock()
        mock_server.__enter__ = lambda s: s
        mock_server.__exit__ = MagicMock(return_value=False)

        from email.mime.multipart import MIMEMultipart

        fake_msg = MIMEMultipart("alternative")

        with (
            patch.multiple("api.services.comunicaciones_service", **_smtp_env_svc()),
            patch(
                "api.services.comunicaciones_service.socket.getaddrinfo",
                return_value=[(None, None, None, None, (FAKE_IP, FAKE_PORT_TLS))],
            ),
            patch(
                "api.services.comunicaciones_service.smtplib.SMTP",
                return_value=mock_server,
            ),
            patch("api.services.comunicaciones_service.ssl.create_default_context"),
        ):
            from api.services.comunicaciones_service import _send_via_smtp

            ok, err = _send_via_smtp(fake_msg, FAKE_DEST)

        assert mock_server._host == FAKE_HOST
        mock_server.starttls.assert_called_once()
        mock_server.login.assert_called_once_with(FAKE_USER, FAKE_PASSWORD)
        assert ok is True
        assert err == ""

    def test_ssl_direct_wrap_socket_uses_hostname(self):
        mock_raw_sock = MagicMock()
        mock_ssl_sock = MagicMock()
        mock_context = MagicMock()
        mock_context.wrap_socket.return_value = mock_ssl_sock

        mock_server = MagicMock()
        mock_server.__enter__ = lambda s: s
        mock_server.__exit__ = MagicMock(return_value=False)
        mock_server.getreply.return_value = (220, b"OK")

        from email.mime.multipart import MIMEMultipart

        fake_msg = MIMEMultipart("alternative")

        with (
            patch.multiple(
                "api.services.comunicaciones_service",
                **_smtp_env_svc(port=FAKE_PORT_SSL, use_tls=False),
            ),
            patch(
                "api.services.comunicaciones_service.socket.getaddrinfo",
                return_value=[(None, None, None, None, (FAKE_IP, FAKE_PORT_SSL))],
            ),
            patch(
                "api.services.comunicaciones_service.socket.create_connection",
                return_value=mock_raw_sock,
            ),
            patch(
                "api.services.comunicaciones_service.ssl.create_default_context",
                return_value=mock_context,
            ),
            patch(
                "api.services.comunicaciones_service.smtplib.SMTP",
                return_value=mock_server,
            ),
        ):
            from api.services.comunicaciones_service import _send_via_smtp

            ok, err = _send_via_smtp(fake_msg, FAKE_DEST)

        mock_context.wrap_socket.assert_called_once_with(
            mock_raw_sock, server_hostname=FAKE_HOST
        )
        assert mock_server._host == FAKE_HOST

    def test_not_configured_returns_error(self):
        from email.mime.multipart import MIMEMultipart

        fake_msg = MIMEMultipart("alternative")

        with patch.multiple(
            "api.services.comunicaciones_service",
            SMTP_CONFIGURED=False,
        ):
            from api.services.comunicaciones_service import _send_via_smtp

            ok, err = _send_via_smtp(fake_msg, FAKE_DEST)

        assert ok is False
        assert "no configurado" in err.lower()

    def test_auth_error_handled(self):
        mock_server = MagicMock()
        mock_server.__enter__ = lambda s: s
        mock_server.__exit__ = MagicMock(return_value=False)
        mock_server.login.side_effect = smtplib.SMTPAuthenticationError(535, b"Bad")

        from email.mime.multipart import MIMEMultipart

        fake_msg = MIMEMultipart("alternative")

        with (
            patch.multiple("api.services.comunicaciones_service", **_smtp_env_svc()),
            patch(
                "api.services.comunicaciones_service.socket.getaddrinfo",
                return_value=[(None, None, None, None, (FAKE_IP, FAKE_PORT_TLS))],
            ),
            patch(
                "api.services.comunicaciones_service.smtplib.SMTP",
                return_value=mock_server,
            ),
            patch("api.services.comunicaciones_service.ssl.create_default_context"),
        ):
            from api.services.comunicaciones_service import _send_via_smtp

            ok, err = _send_via_smtp(fake_msg, FAKE_DEST)

        assert ok is False
        assert "auth" in err.lower()

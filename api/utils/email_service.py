# -*- coding: utf-8 -*-
"""
api/utils/email_service.py — Servicio de envío de correos electrónicos HTML.

Envía correos transaccionales (recuperación de contraseña, verificación, etc.)
usando SMTP con plantilla HTML completa en español.

Configuración requerida (variables de entorno):
    SMTP_HOST       — Servidor SMTP (p. ej. smtp.gmail.com)
    SMTP_PORT       — Puerto SMTP (587 para TLS, 465 para SSL)
    SMTP_USER       — Usuario / correo remitente
    SMTP_PASSWORD   — Contraseña o App Password
    SMTP_FROM_NAME  — Nombre visible del remitente (default: CaliTrack)
    SMTP_USE_TLS    — "true" para STARTTLS (default), "false" para SSL directo
"""

import logging
import os
import smtplib
import socket
import ssl
import uuid
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuración desde entorno
# ---------------------------------------------------------------------------
SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM_NAME = os.getenv("SMTP_FROM_NAME", "CaliTrack")
SMTP_USE_TLS = os.getenv("SMTP_USE_TLS", "true").lower() != "false"

EMAIL_SERVICE_AVAILABLE = bool(SMTP_HOST and SMTP_USER and SMTP_PASSWORD)


# ---------------------------------------------------------------------------
# Plantilla HTML
# ---------------------------------------------------------------------------


def _build_password_reset_html(display_name: str, reset_link: str, email: str) -> str:
    year = datetime.now().year
    first_name = display_name.split()[0] if display_name else "Usuario"

    return f"""<!DOCTYPE html>
<html lang="es" xmlns="http://www.w3.org/1999/xhtml">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <meta http-equiv="X-UA-Compatible" content="IE=edge" />
  <!--[if mso]>
  <noscript>
    <xml><o:OfficeDocumentSettings><o:PixelsPerInch>96</o:PixelsPerInch></o:OfficeDocumentSettings></xml>
  </noscript>
  <![endif]-->
  <title>Restablece tu contraseña - CaliTrack</title>
  <style>
    body {{ margin: 0; padding: 0; background-color: #f0f4f8; font-family: 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; }}
    .wrapper {{ width: 100%; background-color: #f0f4f8; padding: 32px 0; }}
    .container {{ max-width: 560px; margin: 0 auto; background-color: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 24px rgba(0,0,0,0.08); }}
    .header {{ background: linear-gradient(135deg, #1a56db 0%, #1e429f 100%); padding: 36px 40px 32px; text-align: center; }}
    .header-logo {{ font-size: 26px; font-weight: 700; color: #ffffff; letter-spacing: -0.5px; margin: 0; }}
    .header-logo span {{ color: #93c5fd; }}
    .header-subtitle {{ color: #bfdbfe; font-size: 13px; margin: 6px 0 0; }}
    .body {{ padding: 40px 40px 32px; }}
    .greeting {{ font-size: 18px; font-weight: 600; color: #111827; margin: 0 0 16px; }}
    .text {{ font-size: 15px; color: #374151; line-height: 1.7; margin: 0 0 20px; }}
    .highlight-box {{ background-color: #eff6ff; border-left: 4px solid #3b82f6; border-radius: 6px; padding: 16px 20px; margin: 24px 0; }}
    .highlight-box p {{ margin: 0; font-size: 14px; color: #1e40af; line-height: 1.6; }}
    .btn-container {{ text-align: center; margin: 32px 0; }}
    .btn {{ display: inline-block; background: linear-gradient(135deg, #1a56db 0%, #1e429f 100%); color: #ffffff !important; text-decoration: none; font-size: 15px; font-weight: 600; padding: 14px 36px; border-radius: 8px; letter-spacing: 0.3px; mso-padding-alt: 0; }}
    .btn:hover {{ background: #1e40af; }}
    .divider {{ border: none; border-top: 1px solid #e5e7eb; margin: 28px 0; }}
    .fallback-link {{ font-size: 13px; color: #6b7280; text-align: center; }}
    .fallback-link a {{ color: #1a56db; word-break: break-all; }}
    .expiry-note {{ font-size: 13px; color: #9ca3af; text-align: center; margin-top: 12px; }}
    .security-note {{ background-color: #fefce8; border-radius: 6px; padding: 14px 18px; margin: 24px 0 0; }}
    .security-note p {{ margin: 0; font-size: 13px; color: #713f12; line-height: 1.6; }}
    .footer {{ background-color: #f9fafb; border-top: 1px solid #e5e7eb; padding: 24px 40px; text-align: center; }}
    .footer p {{ margin: 0 0 6px; font-size: 12px; color: #9ca3af; line-height: 1.6; }}
    .footer a {{ color: #6b7280; text-decoration: none; }}
    @media only screen and (max-width: 600px) {{
      .body {{ padding: 28px 24px 24px; }}
      .header {{ padding: 28px 24px 24px; }}
      .footer {{ padding: 20px 24px; }}
    }}
  </style>
</head>
<body>
  <div class="wrapper">
    <div class="container">

      <!-- CABECERA -->
      <div class="header">
        <p class="header-logo">Cali<span>Track</span></p>
        <p class="header-subtitle">Sistema de Gestión de Proyectos — Alcaldía de Cali</p>
      </div>

      <!-- CUERPO -->
      <div class="body">
        <p class="greeting">Hola, {first_name} 👋</p>

        <p class="text">
          Recibimos una solicitud para <strong>restablecer la contraseña</strong>
          de tu cuenta en CaliTrack asociada al correo
          <strong>{email}</strong>.
        </p>

        <div class="highlight-box">
          <p>
            🔐 Para crear una nueva contraseña, haz clic en el botón de abajo.
            El enlace es válido por <strong>1 hora</strong> y solo puede usarse una vez.
          </p>
        </div>

        <!-- BOTÓN CTA -->
        <div class="btn-container">
          <!--[if mso]>
          <v:roundrect xmlns:v="urn:schemas-microsoft-com:vml" xmlns:w="urn:schemas-microsoft-com:office:word"
            href="{reset_link}" style="height:48px;v-text-anchor:middle;width:220px;" arcsize="17%"
            fillcolor="#1a56db">
            <w:anchorlock/>
            <center style="color:#ffffff;font-family:sans-serif;font-size:15px;font-weight:bold;">
              Restablecer contraseña
            </center>
          </v:roundrect>
          <![endif]-->
          <!--[if !mso]><!-->
          <a href="{reset_link}" class="btn" target="_blank" rel="noopener noreferrer">
            🔑 Restablecer mi contraseña
          </a>
          <!--<![endif]-->
        </div>

        <p class="expiry-note">⏱ Este enlace expira en <strong>1 hora</strong>.</p>

        <hr class="divider" />

        <p class="fallback-link">
          ¿El botón no funciona? Copia y pega este enlace en tu navegador:<br />
          <a href="{reset_link}" target="_blank" rel="noopener noreferrer">{reset_link}</a>
        </p>

        <div class="security-note">
          <p>
            ⚠️ <strong>Aviso de seguridad:</strong> Si tú no solicitaste este cambio,
            puedes ignorar este correo. Tu contraseña actual seguirá siendo la misma
            y nadie podrá acceder a tu cuenta sin ella.
          </p>
        </div>
      </div>

      <!-- PIE DE PÁGINA -->
      <div class="footer">
        <p>Este es un correo automático, por favor no respondas a este mensaje.</p>
        <p>
          CaliTrack · Alcaldía de Santiago de Cali<br />
          Secretaría de Infraestructura y Valorización
        </p>
        <p style="margin-top:10px;">
          &copy; {year} CaliTrack — Todos los derechos reservados.
        </p>
      </div>

    </div>
  </div>
</body>
</html>"""


def _build_password_reset_text(display_name: str, reset_link: str, email: str) -> str:
    """Versión en texto plano para clientes sin soporte HTML (mejora entregabilidad)."""
    first_name = display_name.split()[0] if display_name else "Usuario"
    return f"""Hola, {first_name}.

Recibimos una solicitud para restablecer la contraseña de tu cuenta en CaliTrack ({email}).

Para crear una nueva contraseña, visita el siguiente enlace:
{reset_link}

Este enlace expira en 1 hora y solo puede usarse una vez.

Si no solicitaste este cambio, ignora este correo. Tu contraseña actual seguirá siendo la misma.

---
CaliTrack — Alcaldía de Santiago de Cali
Este es un mensaje automático, por favor no respondas.
"""


# ---------------------------------------------------------------------------
# Función principal
# ---------------------------------------------------------------------------


def send_password_reset_email(
    to_email: str,
    reset_link: str,
    display_name: str = "",
) -> dict:
    """
    Envía el correo de recuperación de contraseña con plantilla HTML.

    Returns:
        {"success": True} o {"success": False, "error": str}
    """
    if not EMAIL_SERVICE_AVAILABLE:
        logger.warning(
            "Email service not configured (SMTP_HOST/SMTP_USER/SMTP_PASSWORD missing). "
            "Set these env vars to enable custom email sending."
        )
        return {
            "success": False,
            "error": "Servicio de correo no configurado",
            "code": "EMAIL_SERVICE_UNAVAILABLE",
        }

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = "Restablece tu contraseña de CaliTrack"
        msg["From"] = f"{SMTP_FROM_NAME} <{SMTP_USER}>"
        msg["To"] = to_email
        msg["Reply-To"] = f"{SMTP_FROM_NAME} <{SMTP_USER}>"
        # Message-ID único mejora la entregabilidad y evita duplicados
        msg["Message-ID"] = f"<{uuid.uuid4()}@calitrack>"
        # Cabeceras que ayudan a evitar la carpeta de spam
        msg["X-Mailer"] = "CaliTrack Mailer 1.0"
        msg["X-Priority"] = "3"
        msg["Precedence"] = "transactional"

        text_part = MIMEText(
            _build_password_reset_text(display_name, reset_link, to_email),
            "plain",
            "utf-8",
        )
        html_part = MIMEText(
            _build_password_reset_html(display_name, reset_link, to_email),
            "html",
            "utf-8",
        )
        # El orden importa: adjuntar plain primero, HTML al final (preferred)
        msg.attach(text_part)
        msg.attach(html_part)

        context = ssl.create_default_context()

        # Resolver hostname manualmente forzando IPv4 para evitar ENETUNREACH en Railway
        try:
            host_ipv4 = socket.getaddrinfo(SMTP_HOST, SMTP_PORT, socket.AF_INET)[0][4][
                0
            ]
        except Exception:
            host_ipv4 = SMTP_HOST  # fallback al hostname si no se puede resolver

        if SMTP_USE_TLS:
            with smtplib.SMTP(host_ipv4, SMTP_PORT, timeout=15) as server:
                server.ehlo(SMTP_HOST)
                server.starttls(context=context)
                server.ehlo(SMTP_HOST)
                server.login(SMTP_USER, SMTP_PASSWORD)
                server.sendmail(SMTP_USER, to_email, msg.as_string())
        else:
            # SSL directo (puerto 465)
            with smtplib.SMTP_SSL(
                host_ipv4, SMTP_PORT, context=context, timeout=15
            ) as server:
                server.ehlo(SMTP_HOST)
                server.login(SMTP_USER, SMTP_PASSWORD)
                server.sendmail(SMTP_USER, to_email, msg.as_string())

        logger.info(f"Password reset email sent to {to_email}")
        return {"success": True}

    except smtplib.SMTPAuthenticationError:
        logger.error("SMTP authentication failed — check SMTP_USER and SMTP_PASSWORD")
        return {
            "success": False,
            "error": "Error de autenticación SMTP",
            "code": "SMTP_AUTH_ERROR",
        }
    except smtplib.SMTPException as exc:
        logger.error(f"SMTP error sending to {to_email}: {exc}")
        return {
            "success": False,
            "error": "Error enviando correo",
            "code": "SMTP_ERROR",
        }
    except Exception as exc:
        logger.error(f"Unexpected error sending reset email to {to_email}: {exc}")
        return {
            "success": False,
            "error": "Error inesperado al enviar correo",
            "code": "EMAIL_SEND_ERROR",
        }

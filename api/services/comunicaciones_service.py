# -*- coding: utf-8 -*-
"""
api/services/comunicaciones_service.py
======================================

Motor de envío de correos masivos y transaccionales para CaliTrack.

Características:

- **Doble canal**: SMTP (Gmail App Password) como canal primario en local /
  servidores que permitan SMTP, y Gmail API (OAuth2) como fallback si está
  configurado. La selección es automática según las variables de entorno.
- **Plantillas Jinja2** HTML responsivas (table-based) compatibles con Outlook
  y Gmail.
- **Resolución de audiencias**: ``all``, ``centros_gestores:n1|n2``,
  ``roles:r1,r2``, ``emails:a,b``, ``uids:u1,u2``.
- **Cuota diaria** configurable con alertas (default 200 envíos/24h, alerta al
  80 %, bloqueo al 95 %).
- **Adjuntos arbitrarios** (multipart MIME).
- **Log de cada envío** en Firestore (``notifications_log``).
- Tolerante a fallos: si Firestore no está disponible, los logs y el control
  de cuota se degradan en lugar de romper el envío.

Variables de entorno relevantes
-------------------------------

SMTP (canal primario por defecto):

    SMTP_HOST           — smtp.gmail.com
    SMTP_PORT           — 587 (TLS) ó 465 (SSL)
    SMTP_USER           — cuenta@gmail.com
    SMTP_PASSWORD       — App Password (16 chars sin espacios)
    SMTP_FROM_NAME      — Nombre visible del remitente (default "CaliTrack")
    SMTP_USE_TLS        — "true" (default) para STARTTLS

Gmail API (canal fallback / preferido en producción Railway/Cloud Run):

    GMAIL_CLIENT_ID
    GMAIL_CLIENT_SECRET
    GMAIL_REFRESH_TOKEN
    GMAIL_SENDER        — cuenta que autorizó el refresh_token

Control de cuota / alertas:

    EMAIL_DAILY_QUOTA   — default 200
    EMAIL_QUOTA_WARN    — default 0.80
    EMAIL_QUOTA_BLOCK   — default 0.95
    ADMIN_ALERT_EMAIL   — destino opcional para alertas de cuota
    FRONTEND_URL        — URL del frontend (CTA por defecto)
"""

from __future__ import annotations

import base64
import logging
import mimetypes
import os
import re
import smtplib
import socket
import ssl
import unicodedata
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.mime.application import MIMEApplication
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Configuración desde entorno
# ---------------------------------------------------------------------------

SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587") or "587")
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM_NAME = os.getenv("SMTP_FROM_NAME", "CaliTrack")
SMTP_USE_TLS = (os.getenv("SMTP_USE_TLS", "true") or "true").lower() != "false"

GMAIL_CLIENT_ID = os.getenv("GMAIL_CLIENT_ID", "")
GMAIL_CLIENT_SECRET = os.getenv("GMAIL_CLIENT_SECRET", "")
GMAIL_REFRESH_TOKEN = os.getenv("GMAIL_REFRESH_TOKEN", "")
GMAIL_SENDER = os.getenv("GMAIL_SENDER", "") or SMTP_USER

DAILY_EMAIL_QUOTA = int(os.getenv("EMAIL_DAILY_QUOTA", "200") or "200")
QUOTA_WARN_THRESHOLD = float(os.getenv("EMAIL_QUOTA_WARN", "0.80") or "0.80")
QUOTA_BLOCK_THRESHOLD = float(os.getenv("EMAIL_QUOTA_BLOCK", "0.95") or "0.95")
ADMIN_ALERT_EMAIL = os.getenv("ADMIN_ALERT_EMAIL", "")
FRONTEND_URL = os.getenv("FRONTEND_URL", "")

SMTP_CONFIGURED = bool(SMTP_HOST and SMTP_USER and SMTP_PASSWORD)
GMAIL_API_CONFIGURED = bool(
    GMAIL_CLIENT_ID and GMAIL_CLIENT_SECRET and GMAIL_REFRESH_TOKEN
)


# ---------------------------------------------------------------------------
# Jinja2 / plantillas
# ---------------------------------------------------------------------------

_TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates" / "emails"

try:
    from jinja2 import Environment, FileSystemLoader, select_autoescape

    _jinja_env: Optional[Environment] = Environment(
        loader=FileSystemLoader(str(_TEMPLATES_DIR)),
        autoescape=select_autoescape(["html", "xml"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )
except Exception as exc:  # pragma: no cover - jinja2 viene con fastapi
    logger.error("Jinja2 no disponible: %s", exc)
    _jinja_env = None


def _render_template(name: str, context: Dict[str, Any]) -> str:
    """Renderiza una plantilla Jinja2 con tolerancia a fallos."""
    if _jinja_env is None:
        # Fallback minimalista — sólo envuelve el HTML del mensaje.
        message_html = context.get("message_html", "")
        subject = context.get("subject", "Notificación")
        return (
            "<!DOCTYPE html><html><body>"
            f"<h2>{subject}</h2>{message_html}</body></html>"
        )
    try:
        template = _jinja_env.get_template(name)
        return template.render(**context)
    except Exception as exc:
        logger.error("Error renderizando plantilla %s: %s", name, exc)
        return f"<html><body>{context.get('message_html', '')}</body></html>"


# ---------------------------------------------------------------------------
# Firestore helpers (logs y control de cuota)
# ---------------------------------------------------------------------------


def _get_db():
    try:
        from database.firebase_config import get_firestore_client

        return get_firestore_client()
    except Exception as exc:  # pragma: no cover
        logger.debug("Firestore no disponible para logs de notificación: %s", exc)
        return None


_LOG_COLLECTION = "notifications_log"
_ALERTS_COLLECTION = "notifications_alerts"


def _log_notification(
    to: str,
    subject: str,
    template: str,
    status: str,
    error: str = "",
    channel: str = "",
    sent_by: str = "",
) -> None:
    """Registra el resultado del envío en Firestore (best effort)."""
    db = _get_db()
    if db is None:
        return
    try:
        db.collection(_LOG_COLLECTION).add(
            {
                "to": to,
                "subject": subject[:200],
                "template": template,
                "status": status,
                "error": error[:500] if error else "",
                "channel": channel,
                "sent_by": sent_by,
                "sent_at": datetime.now(timezone.utc),
            }
        )
    except Exception as exc:  # pragma: no cover
        logger.warning("No se pudo registrar log de notificación: %s", exc)


_count_cache: dict = {"value": 0, "expires": 0.0}


def _count_sent_last_24h() -> int:
    """Cuenta correos enviados en las últimas 24 h (best effort, cache 5 min)."""
    import time

    now = time.monotonic()
    if now < _count_cache["expires"]:
        return _count_cache["value"]

    db = _get_db()
    if db is None:
        return 0
    try:
        from google.cloud.firestore_v1 import FieldFilter

        since = datetime.now(timezone.utc) - timedelta(hours=24)
        query = (
            db.collection(_LOG_COLLECTION)
            .where(filter=FieldFilter("status", "==", "sent"))
            .where(filter=FieldFilter("sent_at", ">=", since))
        )
        result = sum(1 for _ in query.stream())
        _count_cache["value"] = result
        _count_cache["expires"] = now + 300  # cache 5 minutos
        return result
    except Exception as exc:
        logger.warning("No se pudo contar envíos en 24h: %s", exc)
        _count_cache["expires"] = now + 300  # no reintentar hasta 5 min
        return _count_cache["value"]


def _maybe_alert_quota(count: int) -> None:
    """Envía una alerta de cuota una sola vez por día si se alcanza el umbral."""
    if not ADMIN_ALERT_EMAIL:
        return
    warn_count = int(DAILY_EMAIL_QUOTA * QUOTA_WARN_THRESHOLD)
    if count < warn_count:
        return
    db = _get_db()
    today_key = f"quota-warn-{datetime.now(timezone.utc).strftime('%Y-%m-%d')}"
    if db is not None:
        try:
            doc_ref = db.collection(_ALERTS_COLLECTION).document(today_key)
            if doc_ref.get().exists:
                return
            doc_ref.set(
                {
                    "kind": "quota_warning",
                    "count_24h": count,
                    "quota": DAILY_EMAIL_QUOTA,
                    "created_at": datetime.now(timezone.utc),
                }
            )
        except Exception as exc:
            logger.warning("No se pudo registrar alerta de cuota: %s", exc)
    try:
        subject = (
            f"[CaliTrack] Cuota de correo al {int(count / DAILY_EMAIL_QUOTA * 100)}%"
        )
        html = _render_template(
            "generic_announcement.html",
            {
                "subject": subject,
                "header_color": "#f9a825",
                "header_title": f"CaliTrack — {subject}",
                "header_subtitle": "Alerta automática del servicio de correo",
                "priority": "warning",
                "message_html": (
                    f"<p>Se han enviado <strong>{count}</strong> correos en las últimas 24 h "
                    f"sobre una cuota de <strong>{DAILY_EMAIL_QUOTA}</strong>.</p>"
                ),
                "cta_url": "",
                "cta_label": "",
            },
        )
        _send_raw_email(ADMIN_ALERT_EMAIL, subject, html, template="quota_alert")
    except Exception as exc:  # pragma: no cover
        logger.warning("No se pudo enviar alerta de cuota a admin: %s", exc)


# ---------------------------------------------------------------------------
# Construcción MIME
# ---------------------------------------------------------------------------


@dataclass
class EmailAttachment:
    """Adjunto genérico para correos."""

    filename: str
    content: bytes
    mime_type: Optional[str] = None

    def attach_to(self, msg: MIMEMultipart) -> None:
        ctype = self.mime_type
        if not ctype:
            ctype, _ = mimetypes.guess_type(self.filename)
            ctype = ctype or "application/octet-stream"
        maintype, _, subtype = ctype.partition("/")
        if maintype == "application" or not subtype:
            part = MIMEApplication(self.content, _subtype=subtype or "octet-stream")
        else:
            part = MIMEBase(maintype, subtype)
            part.set_payload(self.content)
            from email.encoders import encode_base64

            encode_base64(part)
        part.add_header(
            "Content-Disposition", f'attachment; filename="{self.filename}"'
        )
        msg.attach(part)


def _build_mime_message(
    sender_email: str,
    sender_name: str,
    to: str,
    subject: str,
    html_body: str,
    attachments: Optional[Sequence[EmailAttachment]] = None,
    text_body: Optional[str] = None,
) -> MIMEMultipart:
    """Crea un mensaje MIME multipart/alternative listo para enviar."""
    container_subtype = "mixed" if attachments else "alternative"
    msg = MIMEMultipart(container_subtype)
    msg["From"] = formataddr((sender_name, sender_email))
    msg["To"] = to
    msg["Subject"] = subject
    msg["Reply-To"] = formataddr((sender_name, sender_email))
    msg["Message-ID"] = f"<{uuid.uuid4()}@calitrack>"
    msg["X-Mailer"] = "CaliTrack Mailer 2.0"
    msg["X-Priority"] = "3"
    msg["Precedence"] = "transactional"

    body = MIMEMultipart("alternative")
    body.attach(MIMEText(text_body or _html_to_text(html_body), "plain", "utf-8"))
    body.attach(MIMEText(html_body, "html", "utf-8"))

    if attachments:
        msg.attach(body)
        for att in attachments:
            att.attach_to(msg)
    else:
        # multipart/alternative directo
        for part in body.get_payload():
            msg.attach(part)

    return msg


_TAG_RE = re.compile(r"<[^>]+>")


def _html_to_text(html: str) -> str:
    """Conversión muy simple HTML → texto plano para clientes sin soporte HTML."""
    cleaned = re.sub(r"<\s*br\s*/?>", "\n", html, flags=re.IGNORECASE)
    cleaned = re.sub(r"</\s*p\s*>", "\n\n", cleaned, flags=re.IGNORECASE)
    cleaned = _TAG_RE.sub("", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


# ---------------------------------------------------------------------------
# Canal Gmail API (OAuth2)
# ---------------------------------------------------------------------------


def _get_gmail_service():
    """Instancia un cliente Gmail API renovando el access_token automáticamente."""
    if not GMAIL_API_CONFIGURED:
        return None
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build

        creds = Credentials(
            token=None,
            refresh_token=GMAIL_REFRESH_TOKEN,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=GMAIL_CLIENT_ID,
            client_secret=GMAIL_CLIENT_SECRET,
            scopes=["https://www.googleapis.com/auth/gmail.send"],
        )
        creds.refresh(Request())
        return build("gmail", "v1", credentials=creds, cache_discovery=False)
    except Exception as exc:
        logger.error("Gmail API no disponible: %s", exc)
        return None


def _send_via_gmail_api(msg: MIMEMultipart, to: str) -> Tuple[bool, str]:
    service = _get_gmail_service()
    if service is None:
        return False, "Gmail API no inicializada"
    try:
        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode("utf-8")
        service.users().messages().send(userId="me", body={"raw": raw}).execute()
        return True, ""
    except Exception as exc:
        logger.error("Error enviando vía Gmail API a %s: %s", to, exc)
        return False, str(exc)


# ---------------------------------------------------------------------------
# Canal SMTP (Gmail App Password)
# ---------------------------------------------------------------------------


def _send_via_smtp(msg: MIMEMultipart, to: str) -> Tuple[bool, str]:
    if not SMTP_CONFIGURED:
        return False, "SMTP no configurado"
    try:
        context = ssl.create_default_context()
        try:
            host_ipv4 = socket.getaddrinfo(SMTP_HOST, SMTP_PORT, socket.AF_INET)[0][4][
                0
            ]
        except Exception:
            host_ipv4 = SMTP_HOST

        if SMTP_USE_TLS:
            with smtplib.SMTP(host_ipv4, SMTP_PORT, timeout=20) as server:
                # Restore hostname so starttls() uses it as SNI server_hostname.
                # Connecting via raw IPv4 sets server._host to the IP, which
                # causes "IP address mismatch" during certificate verification.
                server._host = SMTP_HOST
                server.ehlo(SMTP_HOST)
                server.starttls(context=context)
                server.ehlo(SMTP_HOST)
                server.login(SMTP_USER, SMTP_PASSWORD)
                server.sendmail(SMTP_USER, to, msg.as_string())
        else:
            # SSL directo (puerto 465): construir socket IPv4 con SNI correcto
            raw_sock = socket.create_connection((host_ipv4, SMTP_PORT), timeout=20)
            ssl_sock = context.wrap_socket(raw_sock, server_hostname=SMTP_HOST)
            with smtplib.SMTP(timeout=20) as server:
                server.sock = ssl_sock
                server._host = SMTP_HOST
                code, msg_ = server.getreply()  # leer saludo del servidor
                if code != 220:
                    raise smtplib.SMTPConnectError(code, msg_)
                server.ehlo(SMTP_HOST)
                server.login(SMTP_USER, SMTP_PASSWORD)
                server.sendmail(SMTP_USER, to, msg.as_string())
        return True, ""
    except smtplib.SMTPAuthenticationError as exc:
        logger.error("SMTP auth error: %s", exc)
        return False, "SMTP authentication error"
    except Exception as exc:
        logger.error("Error enviando vía SMTP a %s: %s", to, exc)
        return False, str(exc)


# ---------------------------------------------------------------------------
# Envío unificado (con / sin control de cuota)
# ---------------------------------------------------------------------------


def get_active_channel() -> str:
    """Devuelve el canal de envío activo: gmail_api / smtp / none."""
    if SMTP_CONFIGURED:
        return "smtp"
    if GMAIL_API_CONFIGURED:
        return "gmail_api"
    return "none"


def _send_raw_email(
    to: str,
    subject: str,
    html_body: str,
    attachments: Optional[Sequence[EmailAttachment]] = None,
    template: str = "",
    text_body: Optional[str] = None,
    sent_by: str = "",
) -> Tuple[bool, str, str]:
    """Envío directo sin control de cuota. Devuelve (ok, channel, error)."""
    sender_email = SMTP_USER or GMAIL_SENDER
    sender_name = SMTP_FROM_NAME

    if not sender_email:
        msg = "No hay remitente configurado (SMTP_USER o GMAIL_SENDER)"
        logger.error(msg)
        _log_notification(to, subject, template, "failed", msg, "", sent_by)
        return False, "", msg

    mime = _build_mime_message(
        sender_email=sender_email,
        sender_name=sender_name,
        to=to,
        subject=subject,
        html_body=html_body,
        attachments=attachments,
        text_body=text_body,
    )

    ok = False
    channel = ""
    last_error = ""

    if SMTP_CONFIGURED:
        ok, last_error = _send_via_smtp(mime, to)
        channel = "smtp" if ok else channel
        if not ok and GMAIL_API_CONFIGURED:
            logger.warning("SMTP falló para %s, intentando Gmail API…", to)
            ok, last_error = _send_via_gmail_api(mime, to)
            channel = "gmail_api" if ok else channel
    elif GMAIL_API_CONFIGURED:
        ok, last_error = _send_via_gmail_api(mime, to)
        channel = "gmail_api" if ok else channel
    else:
        last_error = "Ningún canal de envío configurado"
        logger.error(last_error)

    _log_notification(
        to=to,
        subject=subject,
        template=template,
        status="sent" if ok else "failed",
        error=last_error,
        channel=channel,
        sent_by=sent_by,
    )
    return ok, channel, last_error


def _send_email(
    to: str,
    subject: str,
    html_body: str,
    attachments: Optional[Sequence[EmailAttachment]] = None,
    template: str = "",
    text_body: Optional[str] = None,
    sent_by: str = "",
) -> Tuple[bool, str, str]:
    """Envío con control de cuota."""
    count = _count_sent_last_24h()
    block_at = int(DAILY_EMAIL_QUOTA * QUOTA_BLOCK_THRESHOLD)
    if count >= block_at:
        _log_notification(
            to,
            subject,
            template,
            "blocked_quota",
            error=f"Cuota diaria alcanzada ({count}/{DAILY_EMAIL_QUOTA})",
            sent_by=sent_by,
        )
        _maybe_alert_quota(count)
        return False, "", "Cuota diaria de correo alcanzada"
    _maybe_alert_quota(count)
    return _send_raw_email(
        to=to,
        subject=subject,
        html_body=html_body,
        attachments=attachments,
        template=template,
        text_body=text_body,
        sent_by=sent_by,
    )


# ---------------------------------------------------------------------------
# API pública — broadcast con plantilla
# ---------------------------------------------------------------------------


PRIORITY_COLORS = {
    "info": "#1a56db",  # Azul CaliTrack
    "warning": "#f59e0b",  # Ámbar
    "urgent": "#dc2626",  # Rojo
}


def render_announcement_html(
    subject: str,
    message_html: str,
    priority: str = "info",
    cta_url: str = "",
    cta_label: str = "",
    header_subtitle: str = "",
) -> str:
    """Renderiza la plantilla de anuncio genérico."""
    header_color = PRIORITY_COLORS.get(priority, PRIORITY_COLORS["info"])
    return _render_template(
        "generic_announcement.html",
        {
            "subject": subject,
            "header_color": header_color,
            "header_title": f"CaliTrack — {subject}",
            "header_subtitle": header_subtitle,
            "priority": priority,
            "message_html": message_html,
            "cta_url": cta_url,
            "cta_label": cta_label,
        },
    )


def send_announcement_email(
    to: str,
    subject: str,
    message_html: str,
    priority: str = "info",
    cta_url: str = "",
    cta_label: str = "",
    attachments: Optional[Sequence[EmailAttachment]] = None,
    sent_by: str = "",
) -> Tuple[bool, str, str]:
    """Envía un anuncio individual aplicando la plantilla genérica."""
    html = render_announcement_html(
        subject=subject,
        message_html=message_html,
        priority=priority,
        cta_url=cta_url,
        cta_label=cta_label,
    )
    return _send_email(
        to=to,
        subject=subject,
        html_body=html,
        attachments=attachments,
        template="broadcast",
        sent_by=sent_by,
    )


def send_test_email(to: str, sent_by: str = "") -> Tuple[bool, str, str]:
    """Correo de prueba para validar la configuración SMTP/Gmail API."""
    subject = "Prueba de configuración de correo — CaliTrack"
    html = render_announcement_html(
        subject=subject,
        message_html=(
            "<p>Este es un correo de <strong>prueba</strong> generado desde el "
            "panel de administración de CaliTrack.</p>"
            "<p>Si lo recibiste, el canal de envío está funcionando correctamente.</p>"
        ),
        priority="info",
        cta_url=FRONTEND_URL or "",
        cta_label="Ir a CaliTrack" if FRONTEND_URL else "",
        header_subtitle="Notificación generada automáticamente",
    )
    return _send_email(
        to=to,
        subject=subject,
        html_body=html,
        template="test",
        sent_by=sent_by,
    )


# ---------------------------------------------------------------------------
# Resolución de audiencias
# ---------------------------------------------------------------------------


def _normalize_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip().lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r"[\s_\-]+", " ", text)
    return text.strip()


def _normalize_roles(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    if isinstance(value, (list, tuple, set)):
        return [str(v).strip() for v in value if str(v).strip()]
    return [str(value).strip()] if str(value).strip() else []


def _extract_email(user_data: Dict[str, Any]) -> str:
    email = (
        user_data.get("email")
        or user_data.get("correo")
        or user_data.get("Email")
        or ""
    )
    if not isinstance(email, str):
        return ""
    email = email.strip()
    return email if email and "@" in email else ""


def _extract_name(user_data: Dict[str, Any]) -> str:
    return (
        user_data.get("full_name")
        or user_data.get("display_name")
        or user_data.get("nombre")
        or ""
    )


def _extract_user_centro(user_data: Dict[str, Any]) -> str:
    return (
        user_data.get("nombre_centro_gestor")
        or user_data.get("centro_gestor_assigned")
        or user_data.get("centro_gestor")
        or ""
    )


def resolve_audience(audience: str) -> List[Tuple[str, str]]:
    """Devuelve la lista ``[(email, nombre), ...]`` para una audiencia dada.

    Formatos aceptados:

    - ``all``
    - ``activos`` (mismo que ``all`` pero filtra ``is_active != False``)
    - ``centros_gestores:n1|n2|...``  (separador ``|``)
    - ``roles:r1,r2,...``
    - ``uids:uid1,uid2,...``
    - ``emails:a@b.com,c@d.com``
    """
    audience = (audience or "").strip()
    if not audience:
        raise ValueError("audiencia vacía")

    db = _get_db()

    # Audiencias que no requieren Firestore
    if audience.lower().startswith("emails:"):
        raw = audience.split(":", 1)[1]
        seen: set[str] = set()
        out: List[Tuple[str, str]] = []
        for raw_email in re.split(r"[\s,;]+", raw):
            em = raw_email.strip()
            if em and "@" in em and em.lower() not in seen:
                seen.add(em.lower())
                out.append((em, ""))
        return out

    if db is None:
        raise RuntimeError("Firestore no disponible para resolver audiencia")

    # ------------------------------------------------------------------
    if audience.lower() in ("all", "todos"):
        out = []
        seen = set()
        for udoc in db.collection("users").stream():
            ud = udoc.to_dict() or {}
            email = _extract_email(ud)
            if email and email.lower() not in seen:
                seen.add(email.lower())
                out.append((email, _extract_name(ud)))
        return out

    if audience.lower() in ("activos", "active"):
        out = []
        seen = set()
        for udoc in db.collection("users").stream():
            ud = udoc.to_dict() or {}
            if ud.get("is_active") is False:
                continue
            email = _extract_email(ud)
            if email and email.lower() not in seen:
                seen.add(email.lower())
                out.append((email, _extract_name(ud)))
        return out

    if audience.lower().startswith(("centro_gestor:", "centros_gestores:")):
        raw = audience.split(":", 1)[1]
        target_names = {
            _normalize_text(n) for n in re.split(r"[|;]+", raw) if n.strip()
        }
        if not target_names:
            return []
        out = []
        seen = set()
        for udoc in db.collection("users").stream():
            ud = udoc.to_dict() or {}
            centro = _normalize_text(_extract_user_centro(ud))
            if centro and centro in target_names:
                email = _extract_email(ud)
                if email and email.lower() not in seen:
                    seen.add(email.lower())
                    out.append((email, _extract_name(ud)))
        return out

    if audience.lower().startswith(("role:", "roles:")):
        raw = audience.split(":", 1)[1]
        target_roles = {
            r.strip().lower() for r in re.split(r"[,;|]+", raw) if r.strip()
        }
        if not target_roles:
            return []
        out = []
        seen = set()
        for udoc in db.collection("users").stream():
            ud = udoc.to_dict() or {}
            user_roles = {r.lower() for r in _normalize_roles(ud.get("roles"))}
            single_role = str(ud.get("role") or ud.get("rol") or "").strip().lower()
            if single_role:
                user_roles.add(single_role)
            if user_roles & target_roles:
                email = _extract_email(ud)
                if email and email.lower() not in seen:
                    seen.add(email.lower())
                    out.append((email, _extract_name(ud)))
        return out

    if audience.lower().startswith(("uid:", "uids:")):
        raw = audience.split(":", 1)[1]
        uids = [u.strip() for u in re.split(r"[,;|\s]+", raw) if u.strip()]
        out = []
        seen = set()
        for uid in uids:
            try:
                udoc = db.collection("users").document(uid).get()
            except Exception:
                continue
            if not udoc.exists:
                continue
            ud = udoc.to_dict() or {}
            email = _extract_email(ud)
            if email and email.lower() not in seen:
                seen.add(email.lower())
                out.append((email, _extract_name(ud)))
        return out

    raise ValueError(f"Formato de audiencia inválido: {audience}")


# ---------------------------------------------------------------------------
# Broadcast batch
# ---------------------------------------------------------------------------


def deliver_broadcast(
    recipients: Iterable[Tuple[str, str]],
    subject: str,
    message_html: str,
    priority: str = "info",
    cta_url: str = "",
    cta_label: str = "",
    attachments: Optional[Sequence[EmailAttachment]] = None,
    sent_by: str = "",
) -> Dict[str, Any]:
    """Envía el broadcast a todos los destinatarios. Diseñado para ejecutarse
    como BackgroundTask (síncrono)."""
    sent = 0
    failed = 0
    blocked = 0
    errors: List[Dict[str, str]] = []

    html = render_announcement_html(
        subject=subject,
        message_html=message_html,
        priority=priority,
        cta_url=cta_url,
        cta_label=cta_label,
    )

    for email, _name in recipients:
        if not email:
            continue
        ok, _channel, err = _send_email(
            to=email,
            subject=subject,
            html_body=html,
            attachments=attachments,
            template="broadcast",
            sent_by=sent_by,
        )
        if ok:
            sent += 1
        elif err and "cuota" in err.lower():
            blocked += 1
            errors.append({"to": email, "error": err})
        else:
            failed += 1
            errors.append({"to": email, "error": err})

    return {
        "sent": sent,
        "failed": failed,
        "blocked": blocked,
        "errors": errors[:20],  # limitar la respuesta
    }


# ---------------------------------------------------------------------------
# Salud / historial
# ---------------------------------------------------------------------------


def get_notifications_health() -> Dict[str, Any]:
    """Estado del servicio de envío (para badge UI)."""
    sent_24h = _count_sent_last_24h()
    quota_pct = (
        round(sent_24h / DAILY_EMAIL_QUOTA * 100, 1) if DAILY_EMAIL_QUOTA else 0.0
    )
    return {
        "smtp_configured": SMTP_CONFIGURED,
        "gmail_api_configured": GMAIL_API_CONFIGURED,
        "active_channel": get_active_channel(),
        "smtp_host": SMTP_HOST if SMTP_CONFIGURED else "",
        "smtp_port": SMTP_PORT if SMTP_CONFIGURED else 0,
        "sender": GMAIL_SENDER or SMTP_USER or "",
        "sender_name": SMTP_FROM_NAME,
        "frontend_url": FRONTEND_URL,
        "daily_quota": DAILY_EMAIL_QUOTA,
        "sent_last_24h": sent_24h,
        "quota_remaining": max(0, DAILY_EMAIL_QUOTA - sent_24h),
        "warn_threshold": int(QUOTA_WARN_THRESHOLD * 100),
        "block_threshold": int(QUOTA_BLOCK_THRESHOLD * 100),
        "quota_usage_pct": quota_pct,
    }


def list_recent_logs(limit: int = 50) -> List[Dict[str, Any]]:
    """Devuelve los últimos N envíos registrados (ordenados por fecha desc)."""
    db = _get_db()
    if db is None:
        return []
    try:
        from google.cloud.firestore_v1 import Query

        docs = (
            db.collection(_LOG_COLLECTION)
            .order_by("sent_at", direction=Query.DESCENDING)
            .limit(max(1, min(int(limit), 500)))
            .stream()
        )
        out = []
        for doc in docs:
            data = doc.to_dict() or {}
            data["id"] = doc.id
            sent_at = data.get("sent_at")
            if isinstance(sent_at, datetime):
                data["sent_at"] = sent_at.isoformat()
            out.append(data)
        return out
    except Exception as exc:
        logger.warning("No se pudieron obtener logs de notificaciones: %s", exc)
        return []

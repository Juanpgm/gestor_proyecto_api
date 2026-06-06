# -*- coding: utf-8 -*-
"""
api/routers/comunicaciones.py
=============================

Router del módulo de Comunicaciones / Anuncios.

Endpoints:

- ``POST /comunicaciones/broadcast``         — Enviar anuncio masivo (multipart).
- ``POST /comunicaciones/audiencia/preview`` — Previsualizar destinatarios.
- ``GET  /comunicaciones/health``            — Estado del canal de envío.
- ``POST /comunicaciones/test``              — Enviar correo de prueba.
- ``GET  /comunicaciones/historial``         — Últimos envíos registrados.
- ``GET  /comunicaciones/roles``             — Catálogo de roles.
- ``GET  /comunicaciones/centros-gestores``  — Catálogo de centros gestores.

Permisos:

- ``broadcast`` y ``test``: roles ``super_admin`` y ``admin_general``.
- ``health``, ``audiencia/preview``, ``historial``, ``roles``,
  ``centros-gestores``: cualquier usuario con sesión válida que tenga permiso
  ``manage:users`` / ``manage:roles`` / ``view:audit_logs`` o sea
  ``super_admin``/``admin_general``.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
)
from pydantic import BaseModel, Field

from api.services.comunicaciones_service import (
    EmailAttachment,
    deliver_broadcast,
    get_notifications_health,
    list_recent_logs,
    resolve_audience,
    send_test_email,
)
from auth_system.constants import ROLES
from auth_system.decorators import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/comunicaciones", tags=["Comunicaciones"])


# ---------------------------------------------------------------------------
# Helpers de autorización
# ---------------------------------------------------------------------------

_SENDER_ROLES = {"super_admin", "admin_general"}
_VIEWER_ROLES = {
    "super_admin",
    "admin_general",
    "admin_centro_gestor",
}
_VIEWER_PERMISSIONS = {
    "manage:users",
    "manage:roles",
    "view:audit_logs",
    "send:comunicaciones",
}


def _user_roles(user: Dict[str, Any]) -> set:
    raw = user.get("roles") or []
    if isinstance(raw, str):
        return {raw}
    return {str(r) for r in raw if r}


def _user_permissions(user: Dict[str, Any]) -> set:
    raw = user.get("permissions") or []
    if isinstance(raw, str):
        return {raw}
    return {str(p) for p in raw if p}


def _is_super_or_general(user: Dict[str, Any]) -> bool:
    return bool(_user_roles(user) & _SENDER_ROLES)


def _require_sender(user: Dict[str, Any]) -> None:
    if _is_super_or_general(user):
        return
    if "*" in _user_permissions(user):
        return
    if "send:comunicaciones" in _user_permissions(user):
        return
    raise HTTPException(
        status_code=403,
        detail=(
            "Acceso denegado: el envío de comunicaciones requiere rol "
            "super_admin, admin_general o el permiso send:comunicaciones."
        ),
    )


def _require_viewer(user: Dict[str, Any]) -> None:
    if _user_roles(user) & _VIEWER_ROLES:
        return
    perms = _user_permissions(user)
    if "*" in perms or perms & _VIEWER_PERMISSIONS:
        return
    raise HTTPException(
        status_code=403,
        detail="Acceso denegado al módulo de comunicaciones.",
    )


# ---------------------------------------------------------------------------
# Modelos
# ---------------------------------------------------------------------------


class AudiencePreviewRequest(BaseModel):
    audience: str = Field(
        ...,
        description="all | centros_gestores:n1|n2 | roles:r1,r2 | uids:u1,u2 | emails:a,b",
    )
    max_preview: int = Field(20, ge=0, le=200)


class AudiencePreviewResponse(BaseModel):
    audience: str
    recipients_count: int
    preview: List[Dict[str, str]]


class BroadcastResponse(BaseModel):
    success: bool
    audience: str
    recipients_count: int
    status: str
    message: str


class TestEmailResponse(BaseModel):
    sent: bool
    to: str
    channel: str = ""
    error: str = ""


# ---------------------------------------------------------------------------
# Helpers comunes
# ---------------------------------------------------------------------------

_MAX_ATTACHMENT_SIZE = 10 * 1024 * 1024  # 10 MB / archivo
_MAX_TOTAL_ATTACHMENT_SIZE = 20 * 1024 * 1024  # 20 MB total


async def _collect_attachments(
    files: Optional[List[UploadFile]],
) -> List[EmailAttachment]:
    if not files:
        return []
    attachments: List[EmailAttachment] = []
    total = 0
    for upload in files:
        if not upload or not upload.filename:
            continue
        content = await upload.read()
        size = len(content)
        if size == 0:
            continue
        if size > _MAX_ATTACHMENT_SIZE:
            raise HTTPException(
                status_code=413,
                detail=(
                    f"El adjunto '{upload.filename}' excede el límite de "
                    f"{_MAX_ATTACHMENT_SIZE // (1024 * 1024)} MB."
                ),
            )
        total += size
        if total > _MAX_TOTAL_ATTACHMENT_SIZE:
            raise HTTPException(
                status_code=413,
                detail=(
                    f"El tamaño total de los adjuntos excede el límite de "
                    f"{_MAX_TOTAL_ATTACHMENT_SIZE // (1024 * 1024)} MB."
                ),
            )
        attachments.append(
            EmailAttachment(
                filename=upload.filename,
                content=content,
                mime_type=upload.content_type,
            )
        )
    return attachments


def _validate_subject(subject: str) -> str:
    subject = (subject or "").strip()
    if len(subject) < 3:
        raise HTTPException(
            status_code=400, detail="El asunto debe tener al menos 3 caracteres."
        )
    if len(subject) > 200:
        raise HTTPException(
            status_code=400, detail="El asunto no puede exceder 200 caracteres."
        )
    return subject


def _validate_message(message_html: str) -> str:
    message_html = (message_html or "").strip()
    if not message_html:
        raise HTTPException(
            status_code=400, detail="El cuerpo del mensaje no puede estar vacío."
        )
    if len(message_html) > 500_000:
        raise HTTPException(
            status_code=413,
            detail="El cuerpo del mensaje excede el tamaño permitido (500 KB).",
        )
    return message_html


def _validate_priority(priority: str) -> str:
    if priority not in ("info", "warning", "urgent"):
        raise HTTPException(
            status_code=400,
            detail="Prioridad inválida (use info, warning o urgent).",
        )
    return priority


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/health")
async def health(
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Estado del servicio de envío de correos."""
    _require_viewer(current_user)
    health_data = get_notifications_health()
    health_data["can_send"] = _is_super_or_general(current_user)
    return health_data


@router.post("/audiencia/preview", response_model=AudiencePreviewResponse)
async def audiencia_preview(
    payload: AudiencePreviewRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> AudiencePreviewResponse:
    """Resuelve una audiencia y devuelve el conteo + muestra."""
    _require_viewer(current_user)
    try:
        recipients = resolve_audience(payload.audience)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    preview = [
        {"email": email, "name": name}
        for email, name in recipients[: payload.max_preview]
    ]
    return AudiencePreviewResponse(
        audience=payload.audience,
        recipients_count=len(recipients),
        preview=preview,
    )


@router.post("/test", response_model=TestEmailResponse)
async def enviar_prueba(
    to: Optional[str] = Query(None, description="Email destino (opcional)"),
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> TestEmailResponse:
    """Envía un correo de prueba al destino indicado (o al usuario actual)."""
    _require_sender(current_user)
    destination = (to or current_user.get("email") or "").strip()
    if not destination or "@" not in destination:
        raise HTTPException(
            status_code=400,
            detail="Debe proporcionar un email destino válido (?to=...).",
        )
    sent_by = current_user.get("uid") or current_user.get("email", "")
    ok, channel, err = send_test_email(destination, sent_by=str(sent_by))
    return TestEmailResponse(sent=ok, to=destination, channel=channel, error=err)


@router.post("/broadcast", response_model=BroadcastResponse)
async def broadcast(
    background_tasks: BackgroundTasks,
    subject: str = Form(...),
    message_html: str = Form(...),
    audience: str = Form(...),
    priority: str = Form("info"),
    cta_url: str = Form(""),
    cta_label: str = Form(""),
    extra_emails: str = Form(""),
    attachments: Optional[List[UploadFile]] = File(None),
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> BroadcastResponse:
    """Envía un anuncio masivo a la audiencia indicada.

    El envío se procesa en background; la respuesta es inmediata con el
    conteo de destinatarios resueltos.
    """
    _require_sender(current_user)

    subject = _validate_subject(subject)
    message_html = _validate_message(message_html)
    priority = _validate_priority(priority)

    try:
        recipients = resolve_audience(audience)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    # Permitir agregar emails extra independientes del campo audience
    extra_emails = (extra_emails or "").strip()
    if extra_emails:
        try:
            extra_recipients = resolve_audience(f"emails:{extra_emails}")
        except ValueError:
            extra_recipients = []
        existing = {email.lower() for email, _ in recipients}
        for email, name in extra_recipients:
            if email.lower() not in existing:
                recipients.append((email, name))
                existing.add(email.lower())

    if not recipients:
        raise HTTPException(
            status_code=404,
            detail="La audiencia es válida pero no contiene destinatarios.",
        )

    email_attachments = await _collect_attachments(attachments)
    sent_by = str(current_user.get("uid") or current_user.get("email") or "")

    background_tasks.add_task(
        deliver_broadcast,
        recipients=recipients,
        subject=subject,
        message_html=message_html,
        priority=priority,
        cta_url=cta_url,
        cta_label=cta_label,
        attachments=email_attachments,
        sent_by=sent_by,
    )

    return BroadcastResponse(
        success=True,
        audience=audience,
        recipients_count=len(recipients),
        status="queued",
        message=(
            f"Encolados {len(recipients)} envíos. El procesamiento ocurre en background."
        ),
    )


@router.get("/historial")
async def historial(
    limit: int = Query(50, ge=1, le=500),
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Histórico reciente de envíos del módulo de comunicaciones."""
    _require_viewer(current_user)
    items = list_recent_logs(limit=limit)
    return {"success": True, "count": len(items), "data": items}


@router.get("/roles")
async def listar_roles(
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Catálogo de roles disponible para construir audiencias."""
    _require_viewer(current_user)
    catalog = [
        {
            "id": role_id,
            "name": role_data.get("name", role_id),
            "level": role_data.get("level", 99),
            "description": role_data.get("description", ""),
        }
        for role_id, role_data in ROLES.items()
    ]
    catalog.sort(key=lambda r: r["level"])
    return {"success": True, "data": catalog}


@router.get("/centros-gestores")
async def listar_centros_gestores(
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Lista de nombres de centros gestores (a partir de los usuarios)."""
    _require_viewer(current_user)
    try:
        from database.firebase_config import get_firestore_client

        db = get_firestore_client()
    except Exception:
        db = None
    if db is None:
        return {"success": False, "data": [], "error": "Firestore no disponible"}

    nombres: set[str] = set()
    try:
        for udoc in db.collection("users").stream():
            ud = udoc.to_dict() or {}
            for key in (
                "nombre_centro_gestor",
                "centro_gestor_assigned",
                "centro_gestor",
            ):
                value = ud.get(key)
                if isinstance(value, str) and value.strip():
                    nombres.add(value.strip())
                    break
    except Exception as exc:
        logger.warning("Error obteniendo centros gestores: %s", exc)

    return {
        "success": True,
        "count": len(nombres),
        "data": sorted(nombres, key=lambda s: s.lower()),
    }

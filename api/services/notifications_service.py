"""
Servicio de notificaciones para CaliTrack.

Gestiona la creación y consulta de notificaciones en Firestore.

Colección: `notificaciones`
Documento:
  - id: str (UUID)
  - tipo: 'solicitud_aprobada' | 'solicitud_rechazada' | 'nueva_solicitud'
  - categoria: 'solicitud_cambio'
  - titulo: str
  - mensaje: str
  - actor_nombre: str         — quien realizó la acción
  - actor_role: str
  - actor_centro_gestor: str | None
  - destinatario_role: str    — 'admin_centro_gestor' | 'admin_general' | 'super_admin'
  - destinatario_centro_gestor: str | None  — filtra a qué CG va (solo para admin_centro_gestor)
  - modulo: str               — 'emprestito' | 'unidades_proyecto' | 'intervenciones'
  - referencia_id: str | None — ID o referencia del objeto afectado
  - leida: bool               (default False)
  - leida_en: str | None      (ISO timestamp, para TTL 7d)
  - created_at: str           (ISO timestamp)
"""

import logging
import uuid
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

NOTIFICACIONES_COLLECTION = "notificaciones"

# Roles que reciben notificaciones de nuevas solicitudes
ROLES_SUPERVISORES = ["admin_general", "super_admin"]


def _get_db():
    try:
        from database.firebase_config import get_firestore_client

        return get_firestore_client()
    except Exception as e:
        logger.warning(f"Firestore no disponible para notificaciones: {e}")
        return None


def _now_iso() -> str:
    return datetime.now().isoformat()


# ---------------------------------------------------------------------------
# Core: crear notificación
# ---------------------------------------------------------------------------


def crear_notificacion(
    tipo: str,
    titulo: str,
    mensaje: str,
    actor_nombre: str,
    actor_role: str,
    actor_centro_gestor: Optional[str],
    destinatario_role: str,
    modulo: str,
    referencia_id: Optional[str] = None,
    destinatario_centro_gestor: Optional[str] = None,
) -> Optional[str]:
    """
    Crea una notificación individual en Firestore.
    Retorna el doc_id si tuvo éxito, None si falló.
    """
    db = _get_db()
    if db is None:
        return None

    try:
        doc_id = str(uuid.uuid4())
        data = {
            "id": doc_id,
            "tipo": tipo,
            "categoria": "solicitud_cambio",
            "titulo": titulo,
            "mensaje": mensaje,
            "actor_nombre": actor_nombre,
            "actor_role": actor_role,
            "actor_centro_gestor": actor_centro_gestor,
            "destinatario_role": destinatario_role,
            "destinatario_centro_gestor": destinatario_centro_gestor,
            "modulo": modulo,
            "referencia_id": referencia_id,
            "leida": False,
            "leida_en": None,
            "created_at": _now_iso(),
        }
        db.collection(NOTIFICACIONES_COLLECTION).document(doc_id).set(data)
        logger.debug(
            f"Notificación creada: {doc_id} tipo={tipo} dest={destinatario_role}"
        )
        return doc_id
    except Exception as e:
        logger.error(f"Error creando notificación: {e}")
        return None


# ---------------------------------------------------------------------------
# Tier 1: notificar admin_centro_gestor cuando su solicitud fue resuelta
# ---------------------------------------------------------------------------


def notificar_solicitud_resuelta(
    tipo: str,  # 'solicitud_aprobada' | 'solicitud_rechazada'
    nombre_centro_gestor_solicitante: str,
    actor_nombre: str,
    actor_role: str,
    actor_centro_gestor: Optional[str],
    modulo: str,
    referencia_id: Optional[str] = None,
    motivo_rechazo: Optional[str] = None,
) -> int:
    """
    Notifica a todos los admin_centro_gestor del centro gestor afectado.
    Retorna el número de notificaciones creadas.
    """
    accion = "aprobada" if tipo == "solicitud_aprobada" else "rechazada"
    titulo = f"Solicitud de cambio {accion}"

    if tipo == "solicitud_aprobada":
        mensaje = (
            f"Su solicitud de cambio en {modulo} fue aprobada. "
            f"Aprobado por: {actor_nombre} ({actor_role})"
        )
    else:
        razon = f" Motivo: {motivo_rechazo}" if motivo_rechazo else ""
        mensaje = (
            f"Su solicitud de cambio en {modulo} fue rechazada.{razon} "
            f"Rechazado por: {actor_nombre} ({actor_role})"
        )

    if actor_centro_gestor:
        mensaje += f" — {actor_centro_gestor}"

    doc_id = crear_notificacion(
        tipo=tipo,
        titulo=titulo,
        mensaje=mensaje,
        actor_nombre=actor_nombre,
        actor_role=actor_role,
        actor_centro_gestor=actor_centro_gestor,
        destinatario_role="admin_centro_gestor",
        destinatario_centro_gestor=nombre_centro_gestor_solicitante,
        modulo=modulo,
        referencia_id=referencia_id,
    )
    return 1 if doc_id else 0


# ---------------------------------------------------------------------------
# Tier 2: notificar admin_general y super_admin cuando hay nueva solicitud
# ---------------------------------------------------------------------------


def notificar_nueva_solicitud(
    actor_nombre: str,
    actor_role: str,
    actor_centro_gestor: Optional[str],
    modulo: str,
    tipo_registro: str,
    referencia_id: Optional[str] = None,
) -> int:
    """
    Crea una notificación para cada rol supervisor (admin_general, super_admin).
    Retorna el número de notificaciones creadas.
    """
    titulo = f"Nueva solicitud de cambio — {modulo}"
    cg_info = f" ({actor_centro_gestor})" if actor_centro_gestor else ""
    mensaje = (
        f"Nueva solicitud de cambio en {modulo} ({tipo_registro}). "
        f"Enviada por: {actor_nombre} ({actor_role}){cg_info}"
    )

    creadas = 0
    for rol in ROLES_SUPERVISORES:
        doc_id = crear_notificacion(
            tipo="nueva_solicitud",
            titulo=titulo,
            mensaje=mensaje,
            actor_nombre=actor_nombre,
            actor_role=actor_role,
            actor_centro_gestor=actor_centro_gestor,
            destinatario_role=rol,
            destinatario_centro_gestor=None,
            modulo=modulo,
            referencia_id=referencia_id,
        )
        if doc_id:
            creadas += 1

    return creadas

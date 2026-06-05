"""
Asignar Rol y (opcionalmente) Centro Gestor a un Usuario
Crea o actualiza el documento del usuario en Firestore con el rol indicado.
Si el usuario es 'huérfano' (existe en Auth pero no en Firestore), lo crea.
También sincroniza custom claims de Firebase Auth.

Uso:
    python back/scripts/asignar_rol_centro.py --email <email> --rol <rol> [--centro "<centro>"] [--yes]

Roles válidos:  super_admin, admin_general, admin_centro_gestor, editor_datos,
                gestor_contratos, analista, visualizador, publico

Ejemplo:
    python back/scripts/asignar_rol_centro.py \\
        --email sisco1927@gmail.com \\
        --rol admin_centro_gestor \\
        --centro "Secretaría del Deporte y la Recreación"
"""

import argparse
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from database.firebase_config import (  # noqa: E402
    FIREBASE_AVAILABLE,
    ensure_firebase_configured,
    get_firestore_client,
)
from auth_system.constants import FIREBASE_COLLECTIONS, ROLES  # noqa: E402
from firebase_admin import auth  # noqa: E402

ROLES_QUE_REQUIEREN_CENTRO = {"admin_centro_gestor"}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Asigna rol y centro gestor a un usuario.")
    p.add_argument("--email", required=True)
    p.add_argument("--rol", required=True, choices=sorted(ROLES.keys()))
    p.add_argument(
        "--centro",
        default=None,
        help="Nombre del centro gestor (requerido para admin_centro_gestor)",
    )
    p.add_argument("--yes", action="store_true", help="No pedir confirmación")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    email = args.email.strip().lower()
    rol = args.rol
    centro = args.centro.strip() if args.centro else None

    if rol in ROLES_QUE_REQUIEREN_CENTRO and not centro:
        print(f"❌ El rol '{rol}' requiere --centro")
        return 1

    if not FIREBASE_AVAILABLE or not ensure_firebase_configured():
        print("❌ Firebase no disponible")
        return 2

    try:
        user = auth.get_user_by_email(email)
    except auth.UserNotFoundError:
        print(f"❌ No existe en Firebase Auth: {email}")
        return 3

    print(f"\nUsuario:  {user.email}  ({user.uid})")
    print(f"Rol:      {rol}")
    if centro:
        print(f"Centro:   {centro}")

    if not args.yes:
        ans = input("\n¿Confirmar? (sí/no): ").strip().lower()
        if ans not in ("si", "sí", "s", "y", "yes"):
            print("Cancelado.")
            return 0

    db = get_firestore_client()
    user_ref = db.collection(FIREBASE_COLLECTIONS["users"]).document(user.uid)
    user_doc = user_ref.get()
    now = datetime.now(timezone.utc)

    if user_doc.exists:
        old = user_doc.to_dict() or {}
        old_roles = old.get("roles")
        print(f"\nDocumento existente. Roles anteriores: {old_roles!r}")
        update = {
            "roles": [rol],
            "updated_at": now,
            "updated_by": "system_script",
        }
        if centro:
            update["centro_gestor_assigned"] = centro
            update["nombre_centro_gestor"] = centro  # compatibilidad
        user_ref.update(update)
    else:
        print("\n✨ Creando documento de usuario (huérfano en Auth).")
        doc = {
            "uid": user.uid,
            "email": user.email,
            "full_name": user.display_name or email.split("@")[0],
            "roles": [rol],
            "email_verified": user.email_verified,
            "phone_verified": False,
            "is_active": True,
            "created_at": now,
            "updated_at": now,
            "updated_by": "system_script",
            "last_login_at": None,
        }
        if centro:
            doc["centro_gestor_assigned"] = centro
            doc["nombre_centro_gestor"] = centro
        user_ref.set(doc)
        old_roles = []

    # Sincronizar custom claims (best-effort; el backend usa Firestore como fuente de verdad)
    try:
        claims = dict(user.custom_claims or {})
        claims["role"] = rol
        claims["roles"] = [rol]
        if centro:
            claims["centro_gestor"] = centro
        auth.set_custom_user_claims(user.uid, claims)
        print("✅ Custom claims actualizadas")
    except Exception as e:
        print(f"⚠️  No se pudieron actualizar custom claims: {e}")

    # Audit log
    try:
        db.collection(FIREBASE_COLLECTIONS["audit_logs"]).add(
            {
                "timestamp": now,
                "action": "assign_role_via_script",
                "user_uid": "system",
                "target_user_uid": user.uid,
                "target_user_email": user.email,
                "old_roles": old_roles,
                "new_roles": [rol],
                "centro_gestor_assigned": centro,
                "reason": "asignar_rol_centro.py CLI",
            }
        )
    except Exception as e:
        print(f"⚠️  No se pudo escribir audit log: {e}")

    print(
        "\n✅ Rol asignado. El usuario debe cerrar sesión y volver a iniciar para refrescar token."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

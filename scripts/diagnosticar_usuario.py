"""
Diagnóstico de Usuario
Inspecciona el estado completo de un usuario en Firebase Auth + Firestore para
detectar las causas típicas de errores 401/403 en la app (usuario huérfano,
rol sin permisos, custom claims desincronizados, etc.).

Uso:
    python back/scripts/diagnosticar_usuario.py <email>
"""

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
from auth_system.permissions import get_user_permissions  # noqa: E402
from firebase_admin import auth  # noqa: E402


def _print_section(title: str) -> None:
    print("\n" + "-" * 60)
    print(title)
    print("-" * 60)


def diagnose(email: str) -> int:
    print("=" * 60)
    print(f"DIAGNÓSTICO DE USUARIO: {email}")
    print("=" * 60)

    if not FIREBASE_AVAILABLE or not ensure_firebase_configured():
        print("❌ Firebase no disponible / no configurado")
        return 2

    # 1) Firebase Auth
    _print_section("1) Firebase Authentication")
    try:
        user = auth.get_user_by_email(email)
    except auth.UserNotFoundError:
        print(f"❌ No existe en Firebase Auth: {email}")
        print("   → El usuario debe registrarse primero (POST /auth/register)")
        return 3
    except Exception as e:
        print(f"❌ Error consultando Firebase Auth: {e}")
        return 4

    print(f"✅ Encontrado en Firebase Auth")
    print(f"   UID:             {user.uid}")
    print(f"   Email:           {user.email}")
    print(f"   Email verified:  {user.email_verified}")
    print(f"   Disabled:        {user.disabled}")
    print(f"   Display name:    {user.display_name or '(sin nombre)'}")
    print(f"   Custom claims:   {user.custom_claims or {}}")

    # 2) Firestore - documento de usuario
    _print_section("2) Firestore: colección 'users'")
    db = get_firestore_client()
    user_ref = db.collection(FIREBASE_COLLECTIONS["users"]).document(user.uid)
    user_doc = user_ref.get()

    if not user_doc.exists:
        print(f"❌ NO existe documento en Firestore para UID={user.uid}")
        print("   → Usuario HUÉRFANO: existe en Auth pero no en Firestore.")
        print("   → Esto causará 404/401 en endpoints protegidos.")
        print("   → Solución: ejecutar asignar_rol_centro.py para crearlo.")
        return 5

    data = user_doc.to_dict() or {}
    print(f"✅ Documento existe")
    print(f"   roles:                    {data.get('roles')!r}")
    print(f"   centro_gestor_assigned:   {data.get('centro_gestor_assigned')!r}")
    print(f"   nombre_centro_gestor:     {data.get('nombre_centro_gestor')!r}")
    print(f"   is_active:                {data.get('is_active')!r}")
    print(f"   email_verified:           {data.get('email_verified')!r}")
    print(f"   created_at:               {data.get('created_at')!r}")
    print(f"   updated_at:               {data.get('updated_at')!r}")

    # 3) Permisos efectivos
    _print_section("3) Permisos efectivos (calculados)")
    perms = get_user_permissions(user.uid, db)
    if not perms:
        print("❌ Sin permisos efectivos")
    else:
        print(f"✅ {len(perms)} permisos:")
        for p in sorted(perms):
            print(f"   - {p}")

    # 4) Diagnóstico de Unidades de Proyecto
    _print_section("4) Acceso a 'Unidades de Proyecto'")
    has_read = any(
        p in perms or p == "*"
        for p in (
            "read:unidades",
            "read:unidades:own_centro",
            "read:unidades:basic",
            "*",
        )
    )
    has_write = any(
        p in perms or p == "*"
        for p in ("write:unidades", "write:unidades:own_centro", "*")
    )
    has_delete = any(
        p in perms or p == "*"
        for p in ("delete:unidades", "delete:unidades:own_centro", "*")
    )
    print(f"   read:unidades     → {'✅' if has_read else '❌'}")
    print(f"   write:unidades    → {'✅' if has_write else '❌'}")
    print(f"   delete:unidades   → {'✅' if has_delete else '❌'}")

    cg = data.get("centro_gestor_assigned") or data.get("nombre_centro_gestor")
    needs_cg = any(
        p.endswith(":own_centro")
        for p in perms
        if p.startswith(("read:", "write:", "delete:"))
    )
    if needs_cg and not cg:
        print("⚠️  El rol exige centro_gestor pero NO está asignado → 403 garantizado.")

    # 5) Diagnóstico de consistencia con custom claims
    _print_section("5) Consistencia roles (Firestore ↔ custom claims)")
    fs_roles = data.get("roles")
    if isinstance(fs_roles, str):
        fs_roles = [fs_roles]
    fs_roles = fs_roles or []
    claims_role = (user.custom_claims or {}).get("role") or (
        user.custom_claims or {}
    ).get("roles")
    if isinstance(claims_role, str):
        claims_role = [claims_role]
    claims_role = claims_role or []
    if set(fs_roles) != set(claims_role) and claims_role:
        print(f"⚠️  Desincronizados: Firestore={fs_roles} vs Claims={claims_role}")
    else:
        print(
            f"✅ Coinciden o Auth no tiene claims (esto es OK, el sistema usa Firestore)"
        )

    # 6) Resumen
    _print_section("6) Resumen / Acción sugerida")
    role_names = [r for r in fs_roles if r in ROLES]
    if not role_names:
        print("❌ Sin rol válido. Asignar uno con:")
        print(
            f'   python back/scripts/asignar_rol_centro.py --email {email} --rol admin_centro_gestor --centro "<NOMBRE>"'
        )
        return 6
    if not has_read:
        print(f"⚠️  Rol(es) {role_names} NO tienen read:unidades.")
        print("   → Para acceder a 'Gestionar Unidades de Proyecto' usar:")
        print(
            f'   python back/scripts/asignar_rol_centro.py --email {email} --rol admin_centro_gestor --centro "<NOMBRE>"'
        )
        return 7
    print("✅ Usuario aparentemente bien configurado para Unidades de Proyecto.")
    return 0


def main() -> None:
    if len(sys.argv) < 2:
        print("Uso: python back/scripts/diagnosticar_usuario.py <email>")
        sys.exit(1)
    email = sys.argv[1].strip().lower()
    sys.exit(diagnose(email))


if __name__ == "__main__":
    main()

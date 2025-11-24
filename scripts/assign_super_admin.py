"""
Script para Asignar el Rol de Super Admin
Asigna el rol 'super_admin' a un usuario específico

Uso:
python scripts/assign_super_admin.py <email_usuario>

Ejemplo:
python scripts/assign_super_admin.py admin@cali.gov.co
"""

import sys
import os
from datetime import datetime, timezone

# Agregar el directorio raíz al path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from database.firebase_config import get_firestore_client, FIREBASE_AVAILABLE, ensure_firebase_configured
from auth_system.constants import FIREBASE_COLLECTIONS
from firebase_admin import auth


def find_user_by_email(email: str):
    """
    Busca un usuario por email en Firebase Authentication
    
    Args:
        email: Email del usuario
    
    Returns:
        UserRecord si se encuentra, None en caso contrario
    """
    try:
        user = auth.get_user_by_email(email)
        return user
    except auth.UserNotFoundError:
        return None
    except Exception as e:
        print(f"❌ Error buscando usuario: {e}")
        return None


def assign_super_admin(email: str):
    """
    Asigna el rol super_admin a un usuario
    
    Args:
        email: Email del usuario
    
    Returns:
        True si fue exitoso, False en caso contrario
    """
    if not FIREBASE_AVAILABLE:
        print("❌ Firebase no está disponible")
        return False
    
    # Asegurar que Firebase esté inicializado
    if not ensure_firebase_configured():
        print("❌ No se pudo inicializar Firebase")
        return False
    
    try:
        # Buscar usuario por email
        print(f"\n🔍 Buscando usuario: {email}")
        user = find_user_by_email(email)
        
        if not user:
            print(f"❌ No se encontró un usuario con email: {email}")
            print("\n💡 Sugerencias:")
            print("   1. Verifica que el email sea correcto")
            print("   2. Asegúrate de que el usuario esté registrado en Firebase Auth")
            print("   3. Puedes registrar el usuario primero usando /auth/register")
            return False
        
        print(f"✅ Usuario encontrado:")
        print(f"   UID: {user.uid}")
        print(f"   Email: {user.email}")
        print(f"   Display Name: {user.display_name or 'No configurado'}")
        
        # Obtener o crear documento del usuario en Firestore
        db = get_firestore_client()
        user_ref = db.collection(FIREBASE_COLLECTIONS["users"]).document(user.uid)
        user_doc = user_ref.get()
        
        if user_doc.exists:
            print(f"\n📝 Actualizando roles del usuario existente...")
            user_data = user_doc.to_dict()
            old_roles = user_data.get('roles', [])
            print(f"   Roles anteriores: {old_roles}")
        else:
            print(f"\n✨ Creando nuevo documento de usuario en Firestore...")
            old_roles = []
        
        # Asignar super_admin
        new_roles = ['super_admin']
        
        user_document = {
            'uid': user.uid,
            'email': user.email,
            'full_name': user.display_name or email.split('@')[0],
            'roles': new_roles,
            'email_verified': user.email_verified,
            'phone_verified': False,
            'is_active': True,
            'updated_at': datetime.now(timezone.utc),
            'updated_by': 'system_script'
        }
        
        # Si es nuevo, agregar created_at
        if not user_doc.exists:
            user_document['created_at'] = datetime.now(timezone.utc)
            user_document['last_login_at'] = None
        
        # Guardar
        user_ref.set(user_document, merge=True)
        
        print(f"\n✅ Roles actualizados exitosamente:")
        print(f"   Nuevos roles: {new_roles}")
        
        # Registrar en audit_logs
        db.collection(FIREBASE_COLLECTIONS["audit_logs"]).add({
            'timestamp': datetime.now(timezone.utc),
            'action': 'assign_super_admin',
            'user_uid': 'system',
            'target_user_uid': user.uid,
            'target_user_email': user.email,
            'old_roles': old_roles,
            'new_roles': new_roles,
            'reason': 'Initial super admin assignment via script'
        })
        
        print(f"\n📊 El usuario ahora tiene los siguientes privilegios:")
        print(f"   • Control total del sistema")
        print(f"   • Gestión de usuarios y roles")
        print(f"   • Acceso a todos los recursos")
        print(f"   • Visualización de audit logs")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Error asignando super_admin: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Función principal del script"""
    print("=" * 60)
    print("👑 ASIGNACIÓN DE ROL SUPER ADMIN")
    print("=" * 60)
    
    if not FIREBASE_AVAILABLE:
        print("\n❌ Error: Firebase no está configurado correctamente")
        print("   Verifica las variables de entorno y credenciales")
        sys.exit(1)
    
    # Inicializar Firebase
    print("\n🔧 Inicializando Firebase...")
    if not ensure_firebase_configured():
        print("❌ Error: No se pudo inicializar Firebase")
        print("   Verifica las variables de entorno y credenciales")
        sys.exit(1)
    print("✅ Firebase inicializado correctamente")
    
    # Verificar argumentos
    if len(sys.argv) < 2:
        print("\n❌ Error: Debes proporcionar el email del usuario")
        print("\n📝 Uso:")
        print(f"   python {sys.argv[0]} <email_usuario>")
        print("\n💡 Ejemplo:")
        print(f"   python {sys.argv[0]} admin@cali.gov.co")
        sys.exit(1)
    
    email = sys.argv[1].strip().lower()
    
    # Validar formato de email básico
    if '@' not in email or '.' not in email:
        print(f"\n❌ Error: '{email}' no parece ser un email válido")
        sys.exit(1)
    
    # Confirmar acción
    print(f"\n⚠️  ADVERTENCIA:")
    print(f"   Estás a punto de asignar el rol 'super_admin' a:")
    print(f"   📧 {email}")
    print(f"\n   Este usuario tendrá control total del sistema.")
    
    confirm = input("\n¿Continuar? (sí/no): ").strip().lower()
    
    if confirm not in ['sí', 'si', 's', 'yes', 'y']:
        print("\n❌ Operación cancelada")
        sys.exit(0)
    
    # Asignar super admin
    if not assign_super_admin(email):
        print("\n❌ La asignación falló")
        sys.exit(1)
    
    print("\n" + "=" * 60)
    print("✅ ASIGNACIÓN COMPLETADA EXITOSAMENTE")
    print("=" * 60)
    
    print("\n📝 Próximos pasos:")
    print("   1. El usuario puede iniciar sesión en la aplicación")
    print("   2. Tendrá acceso a /auth/admin/* endpoints")
    print("   3. Puede gestionar otros usuarios y roles")


if __name__ == "__main__":
    main()

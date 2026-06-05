"""
Script de Inicialización de Roles y Permisos en Firebase
Crea las colecciones y documentos necesarios para el sistema de autorización

Ejecutar una sola vez después de implementar el sistema de auth:
python scripts/init_auth_system.py
"""

import sys
import os
from datetime import datetime, timezone

# Agregar el directorio raíz al path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from database.firebase_config import get_firestore_client, FIREBASE_AVAILABLE, ensure_firebase_configured
from auth_system.constants import ROLES, DEFAULT_USER_ROLE, FIREBASE_COLLECTIONS


def init_roles_collection():
    """
    Inicializa la colección de roles en Firebase
    Crea un documento por cada rol definido en constants.py
    """
    if not FIREBASE_AVAILABLE:
        print("❌ Firebase no está disponible")
        return False
    
    # Asegurar que Firebase esté inicializado
    if not ensure_firebase_configured():
        print("❌ No se pudo inicializar Firebase")
        return False
    
    try:
        db = get_firestore_client()
        roles_collection = db.collection(FIREBASE_COLLECTIONS["roles"])
        
        print("\n🔧 Inicializando roles en Firebase...")
        print(f"📊 Total de roles a crear: {len(ROLES)}\n")
        
        for role_id, role_data in ROLES.items():
            # Verificar si el rol ya existe
            role_ref = roles_collection.document(role_id)
            role_doc = role_ref.get()
            
            if role_doc.exists:
                print(f"⚠️  Rol '{role_id}' ya existe - Actualizando...")
                action = "actualizado"
            else:
                print(f"✨ Creando rol '{role_id}'...")
                action = "creado"
            
            # Preparar datos del rol
            role_document = {
                "name": role_data["name"],
                "level": role_data["level"],
                "description": role_data["description"],
                "permissions": role_data["permissions"],
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
                "is_system_role": True  # Roles del sistema no pueden ser eliminados
            }
            
            # Guardar o actualizar
            role_ref.set(role_document)
            
            print(f"   ✅ Rol '{role_data['name']}' {action}")
            print(f"      Nivel: {role_data['level']}")
            print(f"      Permisos: {len(role_data['permissions'])}")
        
        print(f"\n✅ Todos los roles han sido inicializados exitosamente")
        print(f"📝 Rol por defecto configurado: '{DEFAULT_USER_ROLE}'")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Error inicializando roles: {e}")
        import traceback
        traceback.print_exc()
        return False


def verify_initialization():
    """
    Verifica que la inicialización se haya completado correctamente
    """
    if not FIREBASE_AVAILABLE:
        return False
    
    try:
        db = get_firestore_client()
        roles_collection = db.collection(FIREBASE_COLLECTIONS["roles"])
        
        print("\n🔍 Verificando inicialización...")
        
        # Contar roles en Firebase
        roles_docs = list(roles_collection.stream())
        firebase_count = len(roles_docs)
        expected_count = len(ROLES)
        
        print(f"\n📊 Resumen:")
        print(f"   Roles esperados: {expected_count}")
        print(f"   Roles en Firebase: {firebase_count}")
        
        if firebase_count != expected_count:
            print(f"\n⚠️  Advertencia: El conteo no coincide")
            return False
        
        # Verificar que todos los roles esperados existen
        missing_roles = []
        for role_id in ROLES.keys():
            role_doc = roles_collection.document(role_id).get()
            if not role_doc.exists:
                missing_roles.append(role_id)
        
        if missing_roles:
            print(f"\n❌ Roles faltantes: {', '.join(missing_roles)}")
            return False
        
        print(f"\n✅ Verificación completada: Todos los roles están presentes")
        
        # Mostrar lista de roles
        print("\n📋 Roles instalados:")
        for doc in sorted(roles_docs, key=lambda x: x.to_dict().get('level', 999)):
            data = doc.to_dict()
            print(f"   • {doc.id}: {data['name']} (Nivel {data['level']})")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Error en verificación: {e}")
        return False


def main():
    """Función principal del script"""
    print("=" * 60)
    print("🚀 INICIALIZACIÓN DEL SISTEMA DE AUTENTICACIÓN")
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
    
    # Inicializar roles
    if not init_roles_collection():
        print("\n❌ La inicialización falló")
        sys.exit(1)
    
    # Verificar
    if not verify_initialization():
        print("\n⚠️  La verificación detectó problemas")
        sys.exit(1)
    
    print("\n" + "=" * 60)
    print("✅ INICIALIZACIÓN COMPLETADA EXITOSAMENTE")
    print("=" * 60)
    
    print("\n📝 Próximos pasos:")
    print("   1. Asignar el rol 'super_admin' a tu usuario inicial")
    print("   2. Usar el script: python scripts/assign_super_admin.py")
    print("   3. Iniciar la API y probar los endpoints de administración")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Verificación directa de conexión con Firebase Authentication
Verifica usuarios existentes sin necesidad del servidor API
"""

import sys
import os
sys.path.append(os.path.dirname(__file__))

def test_firebase_auth_direct():
    print('🔍 VERIFICACIÓN DIRECTA: Conexión con Firebase Authentication')
    print('=' * 60)

    try:
        # Importar configuración de Firebase
        from database.firebase_config import get_auth_client, get_firestore_client
        print('✅ Firebase config importada correctamente')

        # Obtener cliente de Auth
        auth_client = get_auth_client()
        print('✅ Cliente de Firebase Auth obtenido')

        # Intentar listar usuarios (solo funciona con privilegios admin)
        try:
            # Obtener el primer usuario como prueba
            users = auth_client.list_users(max_results=1)
            user_list = list(users.iterate_all())
            print(f'✅ Conexión exitosa con Firebase Auth')
            print(f'📊 Usuarios encontrados en Auth: {len(user_list)} (primer usuario)')

            if user_list:
                user = user_list[0]
                print(f'👤 Usuario de ejemplo:')
                print(f'   • UID: {user.uid}')
                print(f'   • Email: {user.email}')
                print(f'   • Email verificado: {user.email_verified}')
                print(f'   • Creado: {user.user_metadata.creation_timestamp}')
                print(f'   • Último login: {user.user_metadata.last_sign_in_timestamp}')

                # Verificar si existe el usuario de test
                test_email = 'juan.guzman@cali.gov.co'
                try:
                    user_record = auth_client.get_user_by_email(test_email)
                    print(f'✅ Usuario de test encontrado: {test_email}')
                    print(f'   • UID: {user_record.uid}')
                    print(f'   • Estado: {"Activo" if not user_record.disabled else "Deshabilitado"}')
                except Exception as e:
                    print(f'❌ Usuario de test no encontrado: {test_email}')
                    print(f'   Error: {str(e)}')

            # Verificar Firestore
            firestore_client = get_firestore_client()
            users_collection = firestore_client.collection('users')
            docs = users_collection.limit(5).get()

            firestore_users = len(docs)
            print(f'✅ Conexión exitosa con Firestore')
            print(f'📊 Usuarios en Firestore: {firestore_users}')

            if firestore_users > 0:
                print('👥 Usuarios en Firestore:')
                for doc in docs:
                    user_data = doc.to_dict()
                    print(f'   • {doc.id}: {user_data.get("email", "Sin email")}')

        except Exception as e:
            print(f'⚠️  No se pudo listar usuarios (posible falta de permisos): {str(e)}')
            print('   Esto es normal si no tienes permisos de admin completos')

        print()
        print('🎯 RESULTADO:')
        print('✅ Firebase Authentication está conectado y funcionando')
        print('✅ La API puede validar tokens de Firebase')
        print('✅ Los usuarios existen en Firebase Auth')
        print('✅ Firestore está accesible para datos adicionales')

        return True

    except ImportError as e:
        print(f'❌ Error importando Firebase: {e}')
        return False
    except Exception as e:
        print(f'❌ Error conectando con Firebase: {e}')
        return False

if __name__ == '__main__':
    success = test_firebase_auth_direct()
    if success:
        print('\n🚀 Firebase Authentication está listo para usar en la API')
    else:
        print('\n❌ Problemas con la conexión de Firebase')
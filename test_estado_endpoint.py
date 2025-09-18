#!/usr/bin/env python3
"""
Test rápido para el nuevo endpoint de actualización de estado por referencia
"""
import requests

BASE_URL = "http://127.0.0.1:8001"

def test_update_estado_by_referencia():
    """Test del endpoint PUT /procesos/referencia/{ref} - solo estado_proceso_secop"""
    
    print("🔍 Testing endpoint especializado para estado_proceso_secop...")
    
    # Primero obtener la lista de procesos para tener una referencia válida
    try:
        response = requests.get(f"{BASE_URL}/procesos/", params={"limit": 1})
        if response.status_code == 200:
            procesos = response.json()
            if procesos:
                referencia_proceso = procesos[0]["referencia_proceso"]
                estado_actual = procesos[0].get("estado_proceso_secop", "N/A")
                print(f"📋 Usando referencia: {referencia_proceso}")
                print(f"📊 Estado actual: {estado_actual}")
                
                # Probar actualización de estado_proceso_secop
                nuevo_estado = "Actualizado - Test API"
                response = requests.put(
                    f"{BASE_URL}/procesos/referencia/{referencia_proceso}",
                    params={"estado": nuevo_estado}
                )
                
                print(f"Status Code: {response.status_code}")
                if response.status_code == 200:
                    data = response.json()
                    print(f"✅ estado_proceso_secop actualizado correctamente")
                    print(f"   Referencia: {data['referencia_proceso']}")
                    print(f"   Estado anterior: {estado_actual}")
                    print(f"   Estado nuevo: {data['estado_proceso_secop']}")
                    print(f"   Updated at: {data.get('updated_at', 'N/A')}")
                    
                    # Verificar que solo se cambió el estado
                    if data['estado_proceso_secop'] == nuevo_estado:
                        print(f"✅ Confirmado: estado_proceso_secop actualizado correctamente")
                    else:
                        print(f"❌ Error: estado no se actualizó correctamente")
                        
                else:
                    print(f"❌ Error: {response.text}")
                    
            else:
                print("⚠️ No hay procesos disponibles para testear")
        else:
            print(f"❌ Error obteniendo procesos: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Error en test: {e}")

def test_error_cases():
    """Test de casos de error"""
    print("\n🔍 Testing casos de error...")
    
    # Test con referencia inexistente
    try:
        response = requests.put(
            f"{BASE_URL}/procesos/referencia/REF-INEXISTENTE",
            params={"estado": "Test"}
        )
        print(f"Referencia inexistente - Status: {response.status_code}")
        if response.status_code == 404:
            print("✅ Error 404 correcto para referencia inexistente")
        else:
            print(f"⚠️ Status inesperado: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Error en test de error: {e}")

if __name__ == "__main__":
    print("🚀 Test del endpoint PUT /procesos/referencia/{referencia_proceso}")
    print("   Especializado en actualizar solo estado_proceso_secop")
    print("=" * 65)
    
    test_update_estado_by_referencia()
    test_error_cases()
    
    print("\n✅ Tests completados")
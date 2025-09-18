"""
Tests específicos para endpoints de procesos
"""
import requests
import json
from datetime import datetime, date
from decimal import Decimal
import time

# Configuración de la API
BASE_URL = "http://127.0.0.1:8001"
TEST_PROCESO_ID = None

def test_procesos_health():
    """Test básico de conectividad"""
    print("🔍 Testing Procesos Endpoints Connectivity...")
    response = requests.get(f"{BASE_URL}/health")
    assert response.status_code == 200
    print("✅ API conectada")

def test_list_procesos():
    """Test de listado de procesos"""
    print("🔍 Testing List Procesos...")
    response = requests.get(f"{BASE_URL}/procesos/", params={"limit": 5})
    assert response.status_code == 200
    data = response.json()
    print(f"✅ Listado OK: {len(data)} procesos obtenidos")
    
    # Test con filtros
    response = requests.get(f"{BASE_URL}/procesos/", params={
        "banco": "SECOP",
        "limit": 3
    })
    assert response.status_code == 200
    data = response.json()
    print(f"✅ Filtro por banco OK: {len(data)} procesos")

def test_create_proceso():
    """Test de creación de proceso"""
    global TEST_PROCESO_ID
    print("🔍 Testing Create Proceso...")
    
    proceso_data = {
        "referencia_proceso": f"PROC-TEST-{int(time.time())}",
        "banco": "SECOP II",
        "objeto": "Proceso de prueba para testing de API",
        "valor_total": 25000000,
        "estado_proceso_secop": "En Planeación",
        "descripcion": "Proceso creado automáticamente para tests",
        "modalidad": "Licitación Pública",
        "numero_contacto": "3001234567"
    }
    
    response = requests.post(f"{BASE_URL}/procesos/", json=proceso_data)
    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    assert data["referencia_proceso"] == proceso_data["referencia_proceso"]
    
    TEST_PROCESO_ID = data["id"]
    print(f"✅ Proceso creado OK: ID {TEST_PROCESO_ID}")

def test_get_created_proceso():
    """Test de obtención del proceso creado"""
    global TEST_PROCESO_ID
    if not TEST_PROCESO_ID:
        print("⚠️ Skipping - No proceso ID available")
        return
    
    print("🔍 Testing Get Created Proceso...")
    response = requests.get(f"{BASE_URL}/procesos/{TEST_PROCESO_ID}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == TEST_PROCESO_ID
    print(f"✅ Get Proceso OK: {data['referencia_proceso']}")

def test_update_proceso():
    """Test de actualización de proceso"""
    global TEST_PROCESO_ID
    if not TEST_PROCESO_ID:
        print("⚠️ Skipping - No proceso ID available")
        return
    
    print("🔍 Testing Update Proceso...")
    
    update_data = {
        "valor_total": 35000000,
        "estado_proceso_secop": "En Evaluación",
        "observaciones": "Actualizado via test automatizado"
    }
    
    try:
        response = requests.put(f"{BASE_URL}/procesos/{TEST_PROCESO_ID}", json=update_data)
        print(f"Update response status: {response.status_code}")
        print(f"Update response text: {response.text}")
        
        assert response.status_code == 200
        data = response.json()
        assert float(data["valor_total"]) == 35000000
        assert data["estado_proceso_secop"] == "En Evaluación"
        print(f"✅ Update Proceso OK: Valor actualizado a {data['valor_total']}")
    except Exception as e:
        print(f"❌ Update failed: {e}")
        raise

def test_update_referencia_contrato():
    """Test de actualización específica de referencia_contrato"""
    global TEST_PROCESO_ID
    if not TEST_PROCESO_ID:
        print("⚠️ Skipping - No proceso ID available")
        return
    
    print("🔍 Testing Update Referencia Contrato...")
    
    nueva_referencia = f"CONT-REF-{int(time.time())}"
    response = requests.put(
        f"{BASE_URL}/procesos/{TEST_PROCESO_ID}/referencia-contrato",
        params={"referencia_contrato": nueva_referencia}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["referencia_contrato"] == nueva_referencia
    print(f"✅ Update Referencia Contrato OK: {nueva_referencia}")

def test_get_proceso_by_reference():
    """Test de búsqueda por referencia"""
    global TEST_PROCESO_ID
    if not TEST_PROCESO_ID:
        print("⚠️ Skipping - No proceso ID available")
        return
    
    print("🔍 Testing Get Proceso by Reference...")
    
    # Primero obtener la referencia del proceso de test
    response = requests.get(f"{BASE_URL}/procesos/{TEST_PROCESO_ID}")
    proceso_data = response.json()
    referencia = proceso_data["referencia_proceso"]
    
    # Buscar por referencia
    response = requests.get(f"{BASE_URL}/procesos/referencia/{referencia}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == TEST_PROCESO_ID
    print(f"✅ Get by Reference OK: {referencia}")

def test_get_procesos_by_contrato():
    """Test de búsqueda de procesos por contrato"""
    global TEST_PROCESO_ID
    if not TEST_PROCESO_ID:
        print("⚠️ Skipping - No proceso ID available")
        return
    
    print("🔍 Testing Get Procesos by Contrato...")
    
    # Obtener referencia_contrato del proceso de test
    response = requests.get(f"{BASE_URL}/procesos/{TEST_PROCESO_ID}")
    proceso_data = response.json()
    referencia_contrato = proceso_data.get("referencia_contrato")
    
    if referencia_contrato:
        response = requests.get(f"{BASE_URL}/procesos/contrato/{referencia_contrato}")
        assert response.status_code == 200
        data = response.json()
        print(f"✅ Get by Contrato OK: {len(data)} procesos")
    else:
        print("✅ No referencia_contrato - test skipped")

def test_get_procesos_by_banco():
    """Test de búsqueda por banco"""
    print("🔍 Testing Get Procesos by Banco...")
    
    response = requests.get(f"{BASE_URL}/procesos/banco/SECOP")
    assert response.status_code == 200
    data = response.json()
    print(f"✅ Get by Banco OK: {len(data)} procesos de SECOP")

def test_proceso_contrato_index():
    """Test del endpoint de índice proceso-contrato"""
    print("🔍 Testing Proceso-Contrato Index...")
    
    response = requests.get(f"{BASE_URL}/procesos/index/proceso-contrato")
    assert response.status_code == 200
    data = response.json()
    print(f"✅ Index OK: {len(data)} relaciones proceso-contrato")
    
    if data:
        # Verificar estructura del primer elemento
        first_item = data[0]
        required_fields = ['referencia_proceso', 'referencia_contrato', 'proceso_id', 'estado_proceso', 'valor_total']
        for field in required_fields:
            assert field in first_item
        print(f"✅ Estructura de índice correcta")

def test_validation_errors_procesos():
    """Test de validaciones y manejo de errores para procesos"""
    print("🔍 Testing Validation Errors Procesos...")
    
    # Intentar crear proceso con datos inválidos
    invalid_data = {
        "referencia_proceso": "",  # Vacío - debe fallar
        "banco": "",  # Vacío - debe fallar
        "objeto": "",  # Vacío - debe fallar
        "valor_total": -1000,  # Negativo - debe fallar
        "estado_proceso_secop": ""  # Vacío - debe fallar
    }
    
    response = requests.post(f"{BASE_URL}/procesos/", json=invalid_data)
    assert response.status_code == 422  # FastAPI usa 422 para errores de validación
    data = response.json()
    # FastAPI devuelve errores en formato estándar: {"detail": [...]}
    assert "detail" in data
    assert isinstance(data["detail"], list)  # Lista de errores de validación
    print(f"✅ Validation Errors OK: {len(data['detail'])} errores detectados")

def test_not_found_errors_procesos():
    """Test de errores de proceso no encontrado"""
    print("🔍 Testing Not Found Errors Procesos...")
    
    # Buscar proceso inexistente
    response = requests.get(f"{BASE_URL}/procesos/99999")
    assert response.status_code == 404
    print("✅ Not Found Error OK")
    
    # Intentar actualizar proceso inexistente
    response = requests.put(f"{BASE_URL}/procesos/99999", json={
        "valor_total": 1000000
    })
    assert response.status_code == 404
    print("✅ Update Not Found Error OK")

def test_delete_proceso():
    """Test de eliminación de proceso (al final para limpiar)"""
    global TEST_PROCESO_ID
    if not TEST_PROCESO_ID:
        print("⚠️ Skipping - No proceso ID available")
        return
    
    print("🔍 Testing Delete Proceso...")
    
    response = requests.delete(f"{BASE_URL}/procesos/{TEST_PROCESO_ID}")
    assert response.status_code == 204
    
    # Verificar que fue eliminado
    response = requests.get(f"{BASE_URL}/procesos/{TEST_PROCESO_ID}")
    assert response.status_code == 404
    
    print(f"✅ Delete Proceso OK: {TEST_PROCESO_ID} eliminado")

def run_procesos_tests():
    """Ejecutar todos los tests de procesos"""
    print("🚀 Iniciando Tests de Endpoints de Procesos")
    print("=" * 60)
    
    tests = [
        test_procesos_health,
        test_list_procesos,
        test_create_proceso,
        test_get_created_proceso,
        test_update_proceso,
        test_update_referencia_contrato,
        test_get_proceso_by_reference,
        test_get_procesos_by_contrato,
        test_get_procesos_by_banco,
        test_proceso_contrato_index,
        test_validation_errors_procesos,
        test_not_found_errors_procesos,
        test_delete_proceso  # Último para limpiar
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"❌ {test.__name__} FAILED: {str(e)}")
            failed += 1
        print()
    
    print("=" * 60)
    print(f"📊 RESUMEN DE TESTS DE PROCESOS:")
    print(f"✅ Pasados: {passed}")
    print(f"❌ Fallidos: {failed}")
    print(f"📈 Tasa de éxito: {(passed/(passed+failed)*100):.1f}%")
    
    if failed == 0:
        print("🎉 ¡TODOS LOS TESTS DE PROCESOS PASARON!")
    else:
        print(f"⚠️ {failed} tests fallaron. Revisar logs.")

if __name__ == "__main__":
    run_procesos_tests()
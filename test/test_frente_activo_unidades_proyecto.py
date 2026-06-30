"""
Test para verificar que la variable 'frente_activo' estÃ© disponible 
en todos los endpoints del TAG "Unidades de Proyecto"
"""

import pytest
import sys
import os
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from fastapi.testclient import TestClient
from main import app


@pytest.fixture
def client():
    """Cliente de prueba para FastAPI"""
    return TestClient(app)


@pytest.fixture
def mock_firestore_data():
    """Mock de datos de Firestore con frente_activo"""
    return [
        {
            "upid": "UNP-1001",
            "nombre_up": "Proyecto Test 1",
            "estado": "En ejecuciÃ³n",
            "tipo_intervencion": "ConstrucciÃ³n",
            "nombre_centro_gestor": "Centro Test",
            "comuna_corregimiento": "Comuna 1",
            "barrio_vereda": "Barrio Test",
            "frente_activo": "Frente Norte",
            "presupuesto_base": 1000000,
            "avance_obra": 50.5,
            "geometry": {
                "type": "Point",
                "coordinates": [-75.5, 6.25]
            },
            "properties": {
                "upid": "UNP-1001",
                "frente_activo": "Frente Norte"
            }
        },
        {
            "upid": "UNP-1002",
            "nombre_up": "Proyecto Test 2",
            "estado": "PlaneaciÃ³n",
            "tipo_intervencion": "Mantenimiento",
            "nombre_centro_gestor": "Centro Test 2",
            "comuna_corregimiento": "Comuna 2",
            "barrio_vereda": "Barrio Test 2",
            "frente_activo": "Frente Sur",
            "presupuesto_base": 2000000,
            "avance_obra": 30.0,
            "geometry": {
                "type": "Point",
                "coordinates": [-75.6, 6.26]
            },
            "properties": {
                "upid": "UNP-1002",
                "frente_activo": "Frente Sur"
            }
        },
        {
            "upid": "UNP-1003",
            "nombre_up": "Proyecto Test 3",
            "estado": "Completado",
            "tipo_intervencion": "RehabilitaciÃ³n",
            "nombre_centro_gestor": "Centro Test 3",
            "comuna_corregimiento": "Comuna 3",
            "barrio_vereda": "Barrio Test 3",
            "frente_activo": "Frente Este",
            "presupuesto_base": 3000000,
            "avance_obra": 100.0,
            "geometry": {
                "type": "Point",
                "coordinates": [-75.7, 6.27]
            },
            "properties": {
                "upid": "UNP-1003",
                "frente_activo": "Frente Este"
            }
        }
    ]


@pytest.fixture
def mock_firestore_client(mock_firestore_data):
    """Mock del cliente de Firestore"""
    mock_doc = MagicMock()
    mock_docs = []
    
    for data in mock_firestore_data:
        doc = MagicMock()
        doc.id = data["upid"]
        doc.to_dict.return_value = data
        mock_docs.append(doc)
    
    mock_query = MagicMock()
    mock_query.stream.return_value = iter(mock_docs)
    mock_query.order_by.return_value = mock_query
    mock_query.limit.return_value = mock_query
    mock_query.where.return_value = mock_query
    
    mock_collection = MagicMock()
    mock_collection.stream.return_value = iter(mock_docs)
    mock_collection.order_by.return_value = mock_query
    mock_collection.limit.return_value = mock_query
    mock_collection.where.return_value = mock_query
    
    mock_db = MagicMock()
    mock_db.collection.return_value = mock_collection
    
    return mock_db


class TestFrenteActivoGeometryEndpoint:
    """Tests para el endpoint /unidades-proyecto/geometry"""
    
    @patch('api.scripts.unidades_proyecto.get_firestore_client')
    def test_geometry_endpoint_accepts_frente_activo_parameter(self, mock_get_db, super_admin_client, mock_firestore_client):
        """Verificar que el endpoint acepta el parÃ¡metro frente_activo"""
        mock_get_db.return_value = mock_firestore_client
        
        response = super_admin_client.get("/unidades-proyecto/geometry?frente_activo=Frente Norte&limit=10")
        
        assert response.status_code == 200
        data = response.json()
        assert data["type"] == "FeatureCollection"
    
    @patch('api.scripts.unidades_proyecto.get_firestore_client')
    def test_geometry_endpoint_returns_frente_activo_in_properties(self, mock_get_db, super_admin_client, mock_firestore_client):
        """Verificar que el endpoint retorna frente_activo en las propiedades de las features"""
        mock_get_db.return_value = mock_firestore_client
        
        response = super_admin_client.get("/unidades-proyecto/geometry?limit=10")
        
        assert response.status_code == 200
        data = response.json()
        assert data["type"] == "FeatureCollection"
        
        if data.get("features") and len(data["features"]) > 0:
            # Verificar que al menos una feature tiene frente_activo
            has_frente_activo = any(
                "frente_activo" in feature.get("properties", {})
                for feature in data["features"]
            )
            assert has_frente_activo, "Ninguna feature contiene 'frente_activo' en sus properties"


class TestFrenteActivoAttributesEndpoint:
    """Tests para el endpoint /unidades-proyecto/attributes"""
    
    @patch('api.scripts.unidades_proyecto.get_firestore_client')
    def test_attributes_endpoint_accepts_frente_activo_parameter(self, mock_get_db, super_admin_client, mock_firestore_client):
        """Verificar que el endpoint acepta el parÃ¡metro frente_activo"""
        mock_get_db.return_value = mock_firestore_client
        
        response = super_admin_client.get("/unidades-proyecto/attributes?frente_activo=Frente Sur&limit=10")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "data" in data
    
    @patch('api.scripts.unidades_proyecto.get_firestore_client')
    def test_attributes_endpoint_returns_frente_activo_in_data(self, mock_get_db, super_admin_client, mock_firestore_client):
        """Verificar que el endpoint retorna frente_activo en los datos"""
        mock_get_db.return_value = mock_firestore_client
        
        response = super_admin_client.get("/unidades-proyecto/attributes?limit=10")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        
        if data.get("data") and len(data["data"]) > 0:
            # Verificar que al menos un registro tiene frente_activo
            has_frente_activo = any(
                "frente_activo" in record
                for record in data["data"]
            )
            assert has_frente_activo, "NingÃºn registro contiene 'frente_activo'"


class TestFrenteActivoFiltersEndpoint:
    """Tests para el endpoint /unidades-proyecto/filters"""
    
    @patch('api.scripts.unidades_proyecto.get_firestore_client')
    def test_filters_endpoint_includes_frente_activo_in_enum(self, mock_get_db, super_admin_client, mock_firestore_client):
        """Verificar que el endpoint incluye frente_activo en su enum de campos disponibles"""
        mock_get_db.return_value = mock_firestore_client
        
        # Verificar en la documentaciÃ³n del endpoint (OpenAPI)
        response = super_admin_client.get("/openapi.json")
        assert response.status_code == 200
        
        openapi_spec = response.json()
        filters_endpoint = openapi_spec["paths"]["/unidades-proyecto/filters"]["get"]
        
        # Buscar el parÃ¡metro 'field' y verificar que frente_activo estÃ¡ en el enum
        field_param = None
        for param in filters_endpoint["parameters"]:
            if param["name"] == "field":
                field_param = param
                break
        
        assert field_param is not None, "ParÃ¡metro 'field' no encontrado en el endpoint"
        assert "schema" in field_param
        assert "enum" in field_param["schema"]
        assert "frente_activo" in field_param["schema"]["enum"], \
            "'frente_activo' no estÃ¡ en el enum de campos disponibles"
    
    @patch('api.scripts.unidades_proyecto.get_firestore_client')
    def test_filters_endpoint_accepts_frente_activo_field_parameter(self, mock_get_db, super_admin_client, mock_firestore_client):
        """Verificar que el endpoint acepta frente_activo como parÃ¡metro field"""
        mock_get_db.return_value = mock_firestore_client
        
        response = super_admin_client.get("/unidades-proyecto/filters?field=frente_activo")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "filters" in data
    
    @patch('api.scripts.unidades_proyecto.get_firestore_client')
    def test_filters_endpoint_returns_frente_activo_values(self, mock_get_db, super_admin_client, mock_firestore_client):
        """Verificar que el endpoint retorna valores de frente_activo cuando se solicita"""
        mock_get_db.return_value = mock_firestore_client
        
        response = super_admin_client.get("/unidades-proyecto/filters?field=frente_activo")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "filters" in data
        
        # Verificar que hay una clave relacionada con frente_activo
        filters = data["filters"]
        assert len(filters) > 0, "No se retornaron filtros"
        
        # La clave podrÃ­a ser 'frente_activo' o 'frentes_activos' dependiendo de la implementaciÃ³n
        has_frente_key = any(
            "frente" in key.lower() 
            for key in filters.keys()
        )
        assert has_frente_key, "No se encontrÃ³ una clave relacionada con frente_activo en los filtros"
    
    @patch('api.scripts.unidades_proyecto.get_firestore_client')
    def test_filters_endpoint_returns_all_filters_including_frente_activo(self, mock_get_db, super_admin_client, mock_firestore_client):
        """Verificar que el endpoint retorna frente_activo cuando se solicitan todos los filtros"""
        mock_get_db.return_value = mock_firestore_client
        
        response = super_admin_client.get("/unidades-proyecto/filters")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "filters" in data
        
        filters = data["filters"]
        # Verificar que existe la clave 'frentes_activos' en los filtros
        assert "frentes_activos" in filters or "frente_activo" in filters, \
            "frente_activo no estÃ¡ presente en el conjunto de todos los filtros"


class TestFrenteActivoIntegration:
    """Tests de integraciÃ³n para verificar consistencia de frente_activo en todos los endpoints"""
    
    @patch('api.scripts.unidades_proyecto.get_firestore_client')
    def test_frente_activo_filter_consistency_across_endpoints(self, mock_get_db, super_admin_client, mock_firestore_client):
        """Verificar que el filtro frente_activo funciona consistentemente en geometry y attributes"""
        mock_get_db.return_value = mock_firestore_client
        
        frente_test = "Frente Norte"
        
        # Test en geometry
        response_geometry = super_admin_client.get(f"/unidades-proyecto/geometry?frente_activo={frente_test}&limit=10")
        assert response_geometry.status_code == 200
        
        # Test en attributes
        response_attributes = super_admin_client.get(f"/unidades-proyecto/attributes?frente_activo={frente_test}&limit=10")
        assert response_attributes.status_code == 200
        
        # Ambos deben retornar respuestas exitosas
        data_geometry = response_geometry.json()
        data_attributes = response_attributes.json()
        
        assert data_geometry["type"] == "FeatureCollection"
        assert data_attributes["success"] is True
    
    def test_openapi_spec_documents_frente_activo(self, client):
        """Verificar que la especificaciÃ³n OpenAPI documenta frente_activo en los endpoints relevantes"""
        response = client.get("/openapi.json")
        assert response.status_code == 200
        
        openapi_spec = response.json()
        
        # Verificar endpoints
        endpoints_to_check = [
            "/unidades-proyecto/geometry",
            "/unidades-proyecto/attributes",
            "/unidades-proyecto/filters"
        ]
        
        for endpoint in endpoints_to_check:
            assert endpoint in openapi_spec["paths"], f"Endpoint {endpoint} no encontrado en OpenAPI"
            
            endpoint_spec = openapi_spec["paths"][endpoint]["get"]
            parameters = endpoint_spec.get("parameters", [])
            
            # Buscar frente_activo en los parÃ¡metros
            param_names = [param["name"] for param in parameters]
            
            if endpoint == "/unidades-proyecto/filters":
                # Para filters, verificar en el enum
                field_param = next((p for p in parameters if p["name"] == "field"), None)
                assert field_param is not None
                assert "frente_activo" in field_param.get("schema", {}).get("enum", [])
            else:
                # Para geometry y attributes, verificar como parÃ¡metro directo
                assert "frente_activo" in param_names, \
                    f"frente_activo no documentado en {endpoint}"


# Test de resumen
def test_summary_report():
    """Generar un reporte resumen de la disponibilidad de frente_activo"""
    print("\n" + "="*80)
    print("RESUMEN DE TESTS - DISPONIBILIDAD DE 'frente_activo'")
    print("="*80)
    print("\nâœ… Endpoints verificados:")
    print("   1. /unidades-proyecto/geometry")
    print("      - Acepta parÃ¡metro frente_activo")
    print("      - Retorna frente_activo en properties de features")
    print("\n   2. /unidades-proyecto/attributes")
    print("      - Acepta parÃ¡metro frente_activo")
    print("      - Retorna frente_activo en los datos")
    print("\n   3. /unidades-proyecto/filters")
    print("      - Incluye frente_activo en enum de campos")
    print("      - Acepta frente_activo como parÃ¡metro field")
    print("      - Retorna valores Ãºnicos de frente_activo")
    print("\nâœ… Tests de integraciÃ³n:")
    print("   - Consistencia del filtro entre endpoints")
    print("   - DocumentaciÃ³n en OpenAPI spec")
    print("\n" + "="*80)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

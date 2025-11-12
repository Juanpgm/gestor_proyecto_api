"""
Locust Load Testing para Gestor Proyecto API
=============================================

Este archivo define escenarios de carga para simular usuarios reales
interactuando con la API.

Uso:
    # Web UI
    locust -f locustfile.py --host=http://localhost:8000
    
    # Headless
    locust -f locustfile.py --host=http://localhost:8000 \
           --users 50 --spawn-rate 5 --run-time 5m --headless

Autor: GitHub Copilot
Fecha: 2024-11-12
"""

from locust import HttpUser, task, between, tag
import random


class ReadHeavyUser(HttpUser):
    """
    Usuario que realiza principalmente operaciones de lectura.
    Simula dashboards y vistas de datos.
    """
    wait_time = between(1, 3)  # Espera entre 1-3 segundos entre requests
    weight = 7  # 70% de los usuarios son de este tipo
    
    @task(5)
    @tag("geometrias", "read")
    def get_geometry(self):
        """Obtener geometrías con paginación"""
        limit = random.choice([50, 100, 200])
        self.client.get(
            f"/unidades-proyecto/geometry?limit={limit}",
            name="/unidades-proyecto/geometry [paginated]"
        )
    
    @task(4)
    @tag("atributos", "read")
    def get_attributes(self):
        """Obtener atributos tabulares"""
        limit = random.choice([50, 100, 200])
        self.client.get(
            f"/unidades-proyecto/attributes?limit={limit}",
            name="/unidades-proyecto/attributes [paginated]"
        )
    
    @task(3)
    @tag("filtros", "read")
    def get_filters(self):
        """Obtener opciones de filtros"""
        self.client.get("/unidades-proyecto/filters")
    
    @task(3)
    @tag("contratos", "read")
    def get_contratos(self):
        """Obtener contratos empréstito"""
        self.client.get("/contratos_emprestito_all")
    
    @task(2)
    @tag("procesos", "read")
    def get_procesos(self):
        """Obtener procesos empréstito"""
        self.client.get("/procesos_emprestito_all")
    
    @task(2)
    @tag("proyectos", "read")
    def get_proyectos(self):
        """Obtener proyectos presupuestales"""
        self.client.get("/proyectos-presupuestales/all")
    
    @task(1)
    @tag("centros", "read")
    def get_centros_gestores(self):
        """Obtener centros gestores únicos"""
        self.client.get("/centros-gestores/nombres-unicos")
    
    @task(1)
    @tag("health", "read")
    def health_check(self):
        """Health check"""
        self.client.get("/health")


class AdminUser(HttpUser):
    """
    Usuario administrador que realiza operaciones CRUD.
    Simula gestión de datos y actualizaciones.
    """
    wait_time = between(2, 5)  # Espera más tiempo entre operaciones
    weight = 2  # 20% de los usuarios son admins
    
    @task(3)
    @tag("admin", "read")
    def get_all_users(self):
        """Obtener listado de usuarios"""
        self.client.get("/admin/users")
    
    @task(2)
    @tag("admin", "read")
    def get_firebase_status(self):
        """Verificar estado de Firebase"""
        self.client.get("/firebase/status")
    
    @task(2)
    @tag("admin", "read")
    def get_collections(self):
        """Obtener colecciones Firebase"""
        self.client.get("/firebase/collections")
    
    @task(1)
    @tag("reportes", "read")
    def get_reportes(self):
        """Obtener reportes de contratos"""
        self.client.get("/reportes_contratos/")
    
    @task(1)
    @tag("emprestito", "read")
    def get_pagos(self):
        """Obtener pagos empréstito"""
        self.client.get("/contratos_pagos_all")


class DashboardUser(HttpUser):
    """
    Usuario de dashboard que realiza consultas específicas y filtradas.
    Simula análisis de datos y reportes.
    """
    wait_time = between(3, 7)  # Dashboard users hacen análisis más pausados
    weight = 1  # 10% de los usuarios son de dashboard
    
    def on_start(self):
        """Setup inicial - obtener opciones de filtros"""
        self.centros_gestores = []
        try:
            response = self.client.get("/centros-gestores/nombres-unicos")
            if response.status_code == 200:
                data = response.json()
                self.centros_gestores = data.get("data", [])[:5]  # Primeros 5
        except:
            pass
    
    @task(4)
    @tag("dashboard", "filtered")
    def filtered_geometry(self):
        """Consulta filtrada de geometrías"""
        if self.centros_gestores:
            centro = random.choice(self.centros_gestores)
            self.client.get(
                f"/unidades-proyecto/geometry?nombre_centro_gestor={centro}&limit=100",
                name="/unidades-proyecto/geometry [filtered]"
            )
    
    @task(3)
    @tag("dashboard", "filtered")
    def filtered_attributes(self):
        """Consulta filtrada de atributos"""
        if self.centros_gestores:
            centro = random.choice(self.centros_gestores)
            self.client.get(
                f"/unidades-proyecto/attributes?nombre_centro_gestor={centro}&limit=100",
                name="/unidades-proyecto/attributes [filtered]"
            )
    
    @task(2)
    @tag("dashboard", "init")
    def init_contratos(self):
        """Inicialización de contratos para seguimiento"""
        if self.centros_gestores:
            centro = random.choice(self.centros_gestores)
            self.client.get(
                f"/contratos/init_contratos_seguimiento?nombre_centro_gestor={centro}",
                name="/contratos/init_contratos_seguimiento [filtered]"
            )
    
    @task(2)
    @tag("dashboard", "download")
    def download_geojson(self):
        """Descarga de GeoJSON"""
        self.client.get(
            "/unidades-proyecto/download-geojson?limit=100",
            name="/unidades-proyecto/download-geojson [limited]"
        )
    
    @task(1)
    @tag("dashboard", "bancos")
    def get_bancos(self):
        """Obtener bancos empréstito"""
        self.client.get("/bancos_emprestito_all")


class MobileApiUser(HttpUser):
    """
    Usuario de API móvil con consultas más pequeñas y frecuentes.
    Simula apps móviles con límites de datos.
    """
    wait_time = between(2, 4)
    weight = 2  # 20% usuarios móviles (agregando los 3 tipos = 10 total)
    
    @task(5)
    @tag("mobile", "small")
    def small_geometry_request(self):
        """Request pequeño de geometrías (mobile-friendly)"""
        self.client.get(
            "/unidades-proyecto/geometry?limit=20",
            name="/unidades-proyecto/geometry [mobile]"
        )
    
    @task(4)
    @tag("mobile", "small")
    def small_attributes_request(self):
        """Request pequeño de atributos"""
        self.client.get(
            "/unidades-proyecto/attributes?limit=20",
            name="/unidades-proyecto/attributes [mobile]"
        )
    
    @task(2)
    @tag("mobile", "filters")
    def get_filters_mobile(self):
        """Opciones de filtros para móvil"""
        fields = ["estado", "tipo_intervencion", "nombre_centro_gestor"]
        field = random.choice(fields)
        self.client.get(
            f"/unidades-proyecto/filters?field={field}",
            name="/unidades-proyecto/filters [mobile]"
        )
    
    @task(1)
    @tag("mobile", "ping")
    def ping_check(self):
        """Health check desde móvil"""
        self.client.get("/ping")


# Configuración de escenarios personalizados
class StressTestScenario(HttpUser):
    """
    Escenario de stress test para endpoints críticos.
    Úsalo con: locust -f locustfile.py --users 100 --spawn-rate 10
    """
    wait_time = between(0.5, 1.5)  # Requests más agresivos
    
    # Solo activar si ejecutas con tag: --tags stress
    @task
    @tag("stress")
    def stress_geometry(self):
        """Stress test en geometrías"""
        self.client.get("/unidades-proyecto/geometry?limit=500")
    
    @task
    @tag("stress")
    def stress_contratos(self):
        """Stress test en contratos"""
        self.client.get("/contratos_emprestito_all")


if __name__ == "__main__":
    """
    Ejemplos de comandos útiles:
    
    # Test básico con 10 usuarios
    locust -f locustfile.py --host=http://localhost:8000 --users 10 --spawn-rate 1 --run-time 2m --headless
    
    # Test de carga moderada
    locust -f locustfile.py --host=http://localhost:8000 --users 50 --spawn-rate 5 --run-time 5m --headless
    
    # Test de stress
    locust -f locustfile.py --host=http://localhost:8000 --users 100 --spawn-rate 10 --run-time 10m --headless --tags stress
    
    # Solo operaciones de lectura
    locust -f locustfile.py --host=http://localhost:8000 --users 30 --spawn-rate 3 --run-time 3m --headless --tags read
    
    # Test de dashboard filtrado
    locust -f locustfile.py --host=http://localhost:8000 --users 20 --spawn-rate 2 --run-time 5m --headless --tags dashboard
    
    # Test móvil
    locust -f locustfile.py --host=http://localhost:8000 --users 40 --spawn-rate 4 --run-time 3m --headless --tags mobile
    """
    print("Ejecuta Locust con los comandos mostrados arriba")
    print("O inicia el Web UI con: locust -f locustfile.py --host=http://localhost:8000")

# Guía Rápida: Test de Performance

## 🚀 Setup Inicial

### 1. Instalar dependencias de testing

```bash
# Instalar dependencias de testing
pip install -r requirements-test.txt
```

### 2. Verificar que el servidor esté corriendo

```bash
# Iniciar el servidor en una terminal
uvicorn main:app --reload --port 8000

# En otra terminal, verificar que esté disponible
curl http://localhost:8000/ping
```

## 📊 Ejecutar Tests de Performance

### Test Completo

```bash
# Ejecutar todos los tests de performance
python test_all_endpoints_performance.py
```

**Output esperado:**

- Tiempo de respuesta por endpoint
- Clasificación de performance (Excelente/Bueno/Aceptable/Lento/Muy Lento)
- Top 10 endpoints más lentos
- Top 5 endpoints más rápidos
- Reporte JSON con resultados detallados

### Configuración del Test

Puedes ajustar los parámetros editando el archivo `test_all_endpoints_performance.py`:

```python
# Configuración
BASE_URL = "http://localhost:8000"  # URL de tu servidor
NUM_ITERATIONS = 3  # Número de veces que se prueba cada endpoint
TIMEOUT_SECONDS = 30  # Timeout para evitar que el test se cuelgue

# Umbrales de rendimiento (en segundos)
EXCELLENT = 0.5
GOOD = 1.0
ACCEPTABLE = 3.0
SLOW = 5.0
```

## 📈 Interpretar Resultados

### Clasificación de Performance

| Categoría        | Tiempo | Acción Requerida        |
| ---------------- | ------ | ----------------------- |
| 🟢 **EXCELENTE** | < 0.5s | Mantener                |
| 🟢 **BUENO**     | 0.5-1s | Monitorear              |
| 🟡 **ACEPTABLE** | 1-3s   | Considerar optimización |
| 🟠 **LENTO**     | 3-5s   | Optimizar pronto        |
| 🔴 **MUY LENTO** | > 5s   | Optimizar urgentemente  |

### Reporte JSON

El test genera un archivo `performance_report_YYYYMMDD_HHMMSS.json` con:

- Timestamp del test
- Resultados detallados por endpoint
- Estadísticas agregadas
- Lista de endpoints fallidos

## 🔧 Optimizaciones Rápidas

### 1. Para endpoints lentos de datos masivos

**Problema:** `/unidades-proyecto/geometry` tarda >5s

**Solución rápida:**

```python
# Agregar paginación obligatoria
@app.get("/unidades-proyecto/geometry")
async def export_geometry_for_nextjs(
    limit: int = Query(100, le=500),  # Máximo 500
    offset: int = Query(0, ge=0)
):
    # ... aplicar limit y offset en query ...
```

### 2. Para endpoints de lectura frecuente

**Problema:** Mismo endpoint consultado muchas veces

**Solución rápida:**

```python
# Agregar GZIP compression (en main.py)
from fastapi.middleware.gzip import GZipMiddleware

app.add_middleware(GZipMiddleware, minimum_size=1000)
```

### 3. Para APIs externas lentas

**Problema:** Endpoints que llaman SECOP/TVEC tardan mucho

**Solución rápida:**

```python
# Usar background tasks (en main.py)
from fastapi import BackgroundTasks

@app.post("/emprestito/obtener-procesos-secop-async")
async def obtener_procesos_async(
    background_tasks: BackgroundTasks,
    referencias: List[str]
):
    job_id = str(uuid.uuid4())
    background_tasks.add_task(process_referencias, job_id, referencias)
    return {"job_id": job_id, "status": "processing"}
```

## 🧪 Load Testing con Locust

Para simular múltiples usuarios:

### 1. Crear archivo de test

```python
# locustfile.py
from locust import HttpUser, task, between

class APIUser(HttpUser):
    wait_time = between(1, 3)

    @task(3)
    def get_geometry(self):
        self.client.get("/unidades-proyecto/geometry?limit=100")

    @task(2)
    def get_contratos(self):
        self.client.get("/contratos_emprestito_all")

    @task(1)
    def health_check(self):
        self.client.get("/health")
```

### 2. Ejecutar load test

```bash
# Iniciar Locust web UI
locust -f locustfile.py --host=http://localhost:8000

# Abrir en navegador: http://localhost:8089
# Configurar: 10 usuarios, spawn rate 1 user/s
```

### 3. Ejecutar load test headless

```bash
# Test automático sin UI
locust -f locustfile.py \
  --host=http://localhost:8000 \
  --users 10 \
  --spawn-rate 1 \
  --run-time 1m \
  --headless
```

## 📋 Checklist de Optimización

Después de ejecutar los tests, usa este checklist:

### Inmediato (hoy)

- [ ] Ejecutar `test_all_endpoints_performance.py`
- [ ] Identificar endpoints >5s
- [ ] Agregar GZIP middleware
- [ ] Documentar endpoints críticos

### Esta semana

- [ ] Implementar paginación en endpoints masivos
- [ ] Agregar índices en Firestore para queries frecuentes
- [ ] Agregar rate limiting en endpoints auth
- [ ] Crear índices compuestos según queries

### Este mes

- [ ] Implementar Redis para caché
- [ ] Refactorizar queries síncronas a async
- [ ] Implementar background tasks para procesamiento pesado
- [ ] Setup monitoring con Prometheus

## 🐛 Troubleshooting

### Error: "No se puede conectar al servidor"

```bash
# Verificar que el servidor esté corriendo
curl http://localhost:8000/ping

# Si no responde, iniciar servidor
uvicorn main:app --reload --port 8000
```

### Error: "ModuleNotFoundError: No module named 'colorama'"

```bash
# Instalar dependencias de testing
pip install -r requirements-test.txt
```

### Error: "Timeout en múltiples endpoints"

Posibles causas:

1. Firebase no está configurado correctamente
2. Colecciones muy grandes sin índices
3. Red lenta

Solución:

```python
# Aumentar timeout en test
TIMEOUT_SECONDS = 60  # Aumentar a 60s
```

## 📚 Recursos Adicionales

- **Documentación completa:** Ver `docs/OPTIMIZACION_PERFORMANCE.md`
- **Estrategias de caché:** Ver sección de Redis en documentación
- **Índices Firestore:** Ver `firestore.indexes.json`
- **Best practices FastAPI:** https://fastapi.tiangolo.com/advanced/performance/

## 🆘 Soporte

Si encuentras problemas:

1. Revisar logs del servidor
2. Verificar que Firebase esté conectado: `/firebase/status`
3. Ejecutar health check: `/health`
4. Revisar reporte JSON generado por el test

---

**Última actualización:** 2024-11-12  
**Autor:** GitHub Copilot

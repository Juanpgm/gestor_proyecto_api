# Optimización de Performance - Gestor Proyecto API

## 📊 Resumen Ejecutivo

Este documento contiene estrategias detalladas para mejorar el rendimiento de la API, basadas en análisis de endpoints y mejores prácticas.

**Fecha de análisis:** 2024-11-12  
**Herramienta:** test_all_endpoints_performance.py

---

## 🎯 Objetivos de Performance

| Categoría           | Tiempo Target | Estado Actual | Prioridad |
| ------------------- | ------------- | ------------- | --------- |
| Endpoints críticos  | < 500ms       | Variable      | 🔴 Alta   |
| Endpoints estándar  | < 1s          | Variable      | 🟡 Media  |
| Endpoints complejos | < 3s          | Variable      | 🟢 Baja   |

---

## 🔍 Análisis de Endpoints Críticos

### 1. Endpoints de Geometrías y Datos Masivos

**Endpoints afectados:**

- `/unidades-proyecto/geometry`
- `/unidades-proyecto/attributes`
- `/unidades-proyecto/download-geojson`

**Problemas identificados:**

- ❌ Carga completa de colecciones sin paginación efectiva
- ❌ Serialización de geometrías complejas (GeometryCollection, MultiPolygon)
- ❌ Sin caché de resultados frecuentes
- ❌ Procesamiento síncrono de miles de registros

**Optimizaciones recomendadas:**

#### 1.1 Implementar Caché con Redis

```python
import redis
import json
from functools import wraps

# Configuración Redis
redis_client = redis.Redis(
    host=os.getenv("REDIS_HOST", "localhost"),
    port=int(os.getenv("REDIS_PORT", 6379)),
    decode_responses=True
)

def cache_response(expire_seconds=300):
    """Decorator para cachear respuestas"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Generar cache key basado en función y argumentos
            cache_key = f"cache:{func.__name__}:{hash(str(args) + str(kwargs))}"

            # Intentar obtener del caché
            cached = redis_client.get(cache_key)
            if cached:
                return json.loads(cached)

            # Si no está en caché, ejecutar función
            result = await func(*args, **kwargs)

            # Guardar en caché
            redis_client.setex(
                cache_key,
                expire_seconds,
                json.dumps(result, default=str)
            )

            return result
        return wrapper
    return decorator

# Uso en endpoints
@cache_response(expire_seconds=600)  # 10 minutos
async def get_unidades_proyecto_geometry(filters):
    # ... código existente ...
    pass
```

#### 1.2 Paginación Obligatoria

```python
@app.get("/unidades-proyecto/geometry")
async def export_geometry_for_nextjs(
    page: int = Query(1, ge=1, description="Número de página"),
    page_size: int = Query(100, ge=10, le=500, description="Registros por página"),
    # ... otros parámetros ...
):
    """
    Implementar paginación efectiva:
    - Límite máximo de 500 registros por request
    - Usar cursores de Firestore para paginación eficiente
    """
    offset = (page - 1) * page_size

    # Usar cursor-based pagination en Firestore
    query = collection_ref.limit(page_size)

    if offset > 0:
        # Obtener último documento de la página anterior
        last_doc = get_last_document_of_previous_page(page - 1, page_size)
        if last_doc:
            query = query.start_after(last_doc)

    # ... resto del código ...
```

#### 1.3 Compresión de Respuestas

```python
from fastapi.middleware.gzip import GZipMiddleware

# Agregar en main.py después de crear app
app.add_middleware(GZipMiddleware, minimum_size=1000)
```

#### 1.4 Streaming de Datos Grandes

```python
from fastapi.responses import StreamingResponse
import io

@app.get("/unidades-proyecto/download-geojson-stream")
async def download_geojson_streaming():
    """Versión streaming para datasets grandes"""

    async def generate_geojson():
        yield '{"type":"FeatureCollection","features":['

        is_first = True
        async for feature in fetch_features_generator():
            if not is_first:
                yield ','
            yield json.dumps(feature, default=str)
            is_first = False

        yield ']}'

    return StreamingResponse(
        generate_geojson(),
        media_type="application/geo+json"
    )
```

---

### 2. Endpoints de Empréstito y Contratos

**Endpoints afectados:**

- `/contratos_emprestito_all`
- `/procesos_emprestito_all`
- `/contratos_pagos_all`

**Problemas identificados:**

- ❌ Queries sin límites que cargan todas las colecciones
- ❌ Falta de índices en Firestore
- ❌ Múltiples queries anidadas (N+1 problem)
- ❌ Sin agregación en Firestore

**Optimizaciones recomendadas:**

#### 2.1 Crear Índices en Firestore

```javascript
// firestore.indexes.json
{
  "indexes": [
    {
      "collectionGroup": "contratos_emprestito",
      "queryScope": "COLLECTION",
      "fields": [
        { "fieldPath": "nombre_centro_gestor", "order": "ASCENDING" },
        { "fieldPath": "fecha_creacion", "order": "DESCENDING" }
      ]
    },
    {
      "collectionGroup": "procesos_emprestito",
      "queryScope": "COLLECTION",
      "fields": [
        { "fieldPath": "plataforma", "order": "ASCENDING" },
        { "fieldPath": "fecha_actualizacion", "order": "DESCENDING" }
      ]
    },
    {
      "collectionGroup": "contratos_pagos",
      "queryScope": "COLLECTION",
      "fields": [
        { "fieldPath": "referencia_contrato", "order": "ASCENDING" },
        { "fieldPath": "fecha_pago", "order": "DESCENDING" }
      ]
    }
  ]
}
```

#### 2.2 Batch Queries y Agregación

```python
from google.cloud.firestore_v1 import FieldFilter
from google.cloud.firestore_v1.aggregation import AggregationQuery

async def get_contratos_emprestito_optimized(
    limit: int = 100,
    offset: int = 0,
    filters: dict = None
):
    """Versión optimizada con batch queries"""

    # Query base
    query = db.collection('contratos_emprestito')

    # Aplicar filtros
    if filters:
        for field, value in filters.items():
            query = query.where(filter=FieldFilter(field, "==", value))

    # Agregar orden y límite
    query = query.order_by("fecha_creacion", direction="DESCENDING")

    # Obtener count total (sin cargar documentos)
    count_query = AggregationQuery(query)
    count_query.count()
    count_result = count_query.get()
    total_count = count_result[0][0].value

    # Obtener documentos con paginación
    docs = query.offset(offset).limit(limit).stream()

    results = [doc.to_dict() for doc in docs]

    return {
        "success": True,
        "data": results,
        "count": len(results),
        "total_count": total_count,
        "page": offset // limit + 1,
        "page_size": limit,
        "has_next": (offset + limit) < total_count
    }
```

#### 2.3 Background Tasks para Procesamiento Pesado

```python
from fastapi import BackgroundTasks
from datetime import datetime
import uuid

# Diccionario para tracking de jobs (en producción usar Redis)
background_jobs = {}

@app.post("/emprestito/obtener-procesos-secop-async")
async def obtener_procesos_secop_async(
    background_tasks: BackgroundTasks,
    referencias: List[str]
):
    """Versión async para procesamiento masivo"""

    job_id = str(uuid.uuid4())
    background_jobs[job_id] = {
        "status": "processing",
        "started_at": datetime.now().isoformat(),
        "total": len(referencias),
        "processed": 0
    }

    # Lanzar tarea en background
    background_tasks.add_task(
        process_referencias_batch,
        job_id,
        referencias
    )

    return {
        "success": True,
        "job_id": job_id,
        "message": "Procesamiento iniciado en background",
        "status_endpoint": f"/emprestito/job-status/{job_id}"
    }

@app.get("/emprestito/job-status/{job_id}")
async def get_job_status(job_id: str):
    """Consultar estado de job en background"""
    if job_id not in background_jobs:
        raise HTTPException(404, "Job no encontrado")

    return background_jobs[job_id]
```

---

### 3. Endpoints de Autenticación

**Endpoints afectados:**

- `/auth/register`
- `/auth/login`
- `/auth/validate-session`

**Problemas identificados:**

- ❌ Validaciones síncronas que bloquean el thread
- ❌ Múltiples queries a Firestore por request
- ❌ Sin rate limiting para prevenir abuso

**Optimizaciones recomendadas:**

#### 3.1 Rate Limiting

```python
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

# Configurar rate limiter
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

@app.post("/auth/register")
@limiter.limit("5/minute")  # Máximo 5 registros por minuto por IP
async def register_user(request: Request, registration_data: UserRegistrationRequest):
    # ... código existente ...
    pass

@app.post("/auth/login")
@limiter.limit("10/minute")  # Máximo 10 intentos de login por minuto
async def login_user(request: Request, login_data: UserLoginRequest):
    # ... código existente ...
    pass
```

#### 3.2 Caché de Sesiones

```python
# Cachear validaciones de sesión exitosas
@cache_response(expire_seconds=300)  # 5 minutos
async def validate_user_session_cached(id_token: str):
    # ... validación de token ...
    pass
```

---

## 🚀 Optimizaciones Generales Aplicables a Todos los Endpoints

### 1. Connection Pooling

```python
# En database/firebase_config.py
from google.cloud.firestore import Client

# Usar un pool de conexiones
_firestore_client = None

def get_firestore_client():
    global _firestore_client
    if _firestore_client is None:
        _firestore_client = Client(
            project=PROJECT_ID,
            # Configuraciones de pool
            credentials=credentials
        )
    return _firestore_client
```

### 2. Async/Await Consistente

```python
# Convertir funciones síncronas a async donde sea posible
import asyncio
from concurrent.futures import ThreadPoolExecutor

executor = ThreadPoolExecutor(max_workers=10)

async def run_sync_in_thread(func, *args):
    """Ejecutar función síncrona en thread pool"""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(executor, func, *args)
```

### 3. Response Compression Headers

```python
# Middleware para agregar headers de compresión
@app.middleware("http")
async def add_compression_headers(request: Request, call_next):
    response = await call_next(request)

    # Sugerir compresión al cliente
    if request.headers.get("accept-encoding"):
        response.headers["vary"] = "Accept-Encoding"

    return response
```

### 4. Prefetch y Batch Loading

```python
async def batch_fetch_documents(doc_refs: List[str], collection: str):
    """Obtener múltiples documentos en una sola query"""
    db = get_firestore_client()

    # Dividir en batches de 10 (límite de Firestore)
    batch_size = 10
    all_docs = []

    for i in range(0, len(doc_refs), batch_size):
        batch = doc_refs[i:i + batch_size]
        docs = db.collection(collection).where("__name__", "in", batch).stream()
        all_docs.extend([doc.to_dict() for doc in docs])

    return all_docs
```

---

## 📈 Monitoreo y Métricas

### 1. Implementar Logging Estructurado

```python
import logging
import json
from datetime import datetime

class PerformanceLogger:
    def __init__(self):
        self.logger = logging.getLogger("performance")

    def log_request(self, endpoint: str, method: str, duration: float,
                   status_code: int, user_id: str = None):
        """Log de performance por request"""
        log_data = {
            "timestamp": datetime.now().isoformat(),
            "endpoint": endpoint,
            "method": method,
            "duration_ms": round(duration * 1000, 2),
            "status_code": status_code,
            "user_id": user_id
        }
        self.logger.info(json.dumps(log_data))

# Middleware para logging
@app.middleware("http")
async def log_performance(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    duration = time.time() - start_time

    perf_logger.log_request(
        endpoint=request.url.path,
        method=request.method,
        duration=duration,
        status_code=response.status_code
    )

    # Agregar header de timing
    response.headers["X-Response-Time"] = f"{duration:.3f}s"

    return response
```

### 2. Métricas con Prometheus

```python
from prometheus_client import Counter, Histogram, make_asgi_app

# Métricas
request_count = Counter(
    'api_requests_total',
    'Total API requests',
    ['method', 'endpoint', 'status']
)

request_duration = Histogram(
    'api_request_duration_seconds',
    'API request duration',
    ['method', 'endpoint']
)

# Exponer métricas
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)
```

---

## 🔧 Plan de Implementación

### Fase 1: Optimizaciones Rápidas (1-2 días)

✅ **Prioridad Alta:**

1. Agregar GZIP middleware
2. Implementar paginación obligatoria en endpoints masivos
3. Agregar rate limiting en auth endpoints
4. Crear índices en Firestore

**Impacto esperado:** 30-40% mejora en endpoints críticos

### Fase 2: Caché y Redis (3-5 días)

✅ **Prioridad Media:**

1. Configurar Redis
2. Implementar caché en endpoints de lectura frecuente
3. Agregar TTL strategies
4. Monitoring de hit rate

**Impacto esperado:** 50-70% mejora en endpoints cacheados

### Fase 3: Arquitectura Async (1-2 semanas)

✅ **Prioridad Media:**

1. Refactorizar queries síncronas a async
2. Implementar background tasks
3. Connection pooling optimizado
4. Batch processing

**Impacto esperado:** 20-30% mejora general

### Fase 4: Monitoreo y Observabilidad (1 semana)

✅ **Prioridad Baja:**

1. Implementar logging estructurado
2. Métricas con Prometheus
3. Dashboard de performance
4. Alertas automáticas

**Impacto esperado:** Visibilidad completa de performance

---

## 📊 Métricas de Éxito

### KPIs a Monitorear

| Métrica           | Valor Actual | Target      | Método de Medición |
| ----------------- | ------------ | ----------- | ------------------ |
| P50 Response Time | TBD          | < 500ms     | Prometheus         |
| P95 Response Time | TBD          | < 2s        | Prometheus         |
| P99 Response Time | TBD          | < 5s        | Prometheus         |
| Cache Hit Rate    | N/A          | > 70%       | Redis Stats        |
| Error Rate        | TBD          | < 0.1%      | Logs               |
| Throughput        | TBD          | > 100 req/s | Load Test          |

---

## 🧪 Testing y Validación

### Script de Performance Tests

```bash
# Ejecutar test completo
python test_all_endpoints_performance.py

# Ejecutar test específico de endpoint
python -c "from test_all_endpoints_performance import EndpointTester; \
           t = EndpointTester('http://localhost:8000'); \
           t.test_endpoint('GET', '/contratos_emprestito_all', 'Test'); \
           t.generate_report()"
```

### Load Testing con Locust

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

```bash
# Ejecutar load test
locust -f locustfile.py --host=http://localhost:8000
```

---

## 📚 Referencias y Recursos

- [FastAPI Performance Tips](https://fastapi.tiangolo.com/advanced/performance/)
- [Firestore Best Practices](https://firebase.google.com/docs/firestore/best-practices)
- [Redis Caching Strategies](https://redis.io/docs/manual/patterns/caching/)
- [Python Async Best Practices](https://docs.python.org/3/library/asyncio.html)

---

## 🤝 Contribución

Para sugerir optimizaciones adicionales:

1. Ejecutar `test_all_endpoints_performance.py`
2. Documentar resultados en issue de GitHub
3. Proponer solución con benchmark

---

**Última actualización:** 2024-11-12  
**Próxima revisión:** 2024-12-12

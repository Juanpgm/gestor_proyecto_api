# 📊 Testing y Optimización de Performance

Este directorio contiene toda la documentación y herramientas para evaluar y mejorar el rendimiento de la API Gestor de Proyectos.

## 📁 Contenido

### Documentos

- **`GUIA_TEST_PERFORMANCE.md`** - Guía rápida para ejecutar tests de performance
- **`OPTIMIZACION_PERFORMANCE.md`** - Estrategias detalladas de optimización con código
- **`ARCHITECTURE_DECISION.md`** - Decisiones arquitectónicas del proyecto (documento existente)

### Scripts de Testing

Ubicados en el directorio raíz del proyecto:

- **`test_all_endpoints_performance.py`** - Test completo de todos los endpoints
- **`locustfile.py`** - Configuración de load testing con Locust
- **`requirements-test.txt`** - Dependencias necesarias para testing

## 🚀 Quick Start

### 1. Instalar dependencias

```bash
pip install -r requirements-test.txt
```

### 2. Iniciar servidor

```bash
uvicorn main:app --reload --port 8000
```

### 3. Ejecutar test de performance

```bash
python test_all_endpoints_performance.py
```

### 4. (Opcional) Ejecutar load testing

```bash
# Web UI interactivo
locust -f locustfile.py --host=http://localhost:8000

# Headless (automático)
locust -f locustfile.py --host=http://localhost:8000 \
  --users 50 --spawn-rate 5 --run-time 5m --headless
```

## 📈 ¿Qué miden estos tests?

### Test de Performance Individual (`test_all_endpoints_performance.py`)

**Mide:**

- ⏱️ Tiempo de respuesta promedio por endpoint
- 📊 Tiempo mínimo, máximo y desviación estándar
- 🎯 Clasificación de performance (Excelente/Bueno/Aceptable/Lento/Muy Lento)
- 🔍 Identificación de endpoints críticos que requieren optimización

**Output:**

- Reporte en consola con colores
- Archivo JSON con resultados detallados (`performance_report_YYYYMMDD_HHMMSS.json`)
- Top 10 endpoints más lentos
- Top 5 endpoints más rápidos
- Estadísticas generales

**Umbrales de performance:**

- 🟢 **EXCELENTE**: < 0.5s
- 🟢 **BUENO**: 0.5-1s
- 🟡 **ACEPTABLE**: 1-3s
- 🟠 **LENTO**: 3-5s
- 🔴 **MUY LENTO**: > 5s

### Load Testing con Locust (`locustfile.py`)

**Mide:**

- 👥 Comportamiento con múltiples usuarios concurrentes
- 📈 Throughput (requests por segundo)
- 💥 Punto de quiebre del sistema
- 🎲 Distribución de requests según tipo de usuario
- ⚡ Response time percentiles (P50, P95, P99)

**Tipos de usuarios simulados:**

1. **ReadHeavyUser** (70%): Usuarios que solo leen datos (dashboards)
2. **AdminUser** (20%): Usuarios administrativos con operaciones CRUD
3. **DashboardUser** (10%): Usuarios con consultas filtradas y análisis
4. **MobileApiUser** (20% alternativo): Apps móviles con requests pequeños

## 🎯 Interpretación de Resultados

### Indicadores Críticos

| Indicador         | Valor Ideal | Requiere Atención Si |
| ----------------- | ----------- | -------------------- |
| P50 Response Time | < 500ms     | > 1s                 |
| P95 Response Time | < 2s        | > 5s                 |
| P99 Response Time | < 5s        | > 10s                |
| Error Rate        | < 0.1%      | > 1%                 |
| Requests/sec      | > 100       | < 50                 |

### Ejemplos de Análisis

#### ✅ Sistema Saludable

```
P50: 350ms
P95: 1.2s
P99: 2.8s
Error Rate: 0.05%
Throughput: 150 req/s
```

#### ⚠️ Requiere Optimización

```
P50: 1.5s      ← Lento para caso típico
P95: 8.2s      ← Muy lento para usuarios
P99: 15.4s     ← Timeouts probables
Error Rate: 2% ← Muchos errores
Throughput: 35 req/s ← Bajo
```

#### 🔴 Sistema Crítico

```
P50: 5.2s      ← Todos los requests lentos
P95: 25s       ← Sistema colapsando
P99: 60s       ← Timeouts constantes
Error Rate: 15% ← Sistema inestable
Throughput: 10 req/s ← Casi inservible
```

## 🔧 Optimizaciones Comunes

### Para Endpoints Lentos (>3s)

1. **Agregar paginación**

   ```python
   limit: int = Query(100, le=500)
   ```

2. **Implementar caché**

   ```python
   @cache_response(expire_seconds=300)
   ```

3. **Índices en Firestore**
   ```javascript
   // firestore.indexes.json
   {
     "collectionGroup": "coleccion",
     "fields": [...]
   }
   ```

### Para Alta Concurrencia

1. **Connection pooling**
2. **Rate limiting**
3. **GZIP compression**
4. **Background tasks**

Ver **`OPTIMIZACION_PERFORMANCE.md`** para detalles completos.

## 📊 Workflow de Testing Recomendado

### 1. Baseline (Primera vez)

```bash
# Ejecutar test inicial
python test_all_endpoints_performance.py

# Guardar reporte como baseline
cp performance_report_*.json baseline_report.json
```

### 2. Desarrollo (Cada cambio importante)

```bash
# Test rápido después de cambios
python test_all_endpoints_performance.py

# Comparar con baseline
# (manualmente o con herramienta de diff)
```

### 3. Pre-Release (Antes de deploy)

```bash
# Test de performance completo
python test_all_endpoints_performance.py

# Load test moderado
locust -f locustfile.py --host=http://localhost:8000 \
  --users 50 --spawn-rate 5 --run-time 10m --headless

# Verificar métricas críticas
```

### 4. Post-Release (Después de deploy)

```bash
# Load test en producción (con precaución)
locust -f locustfile.py --host=https://tu-api.com \
  --users 20 --spawn-rate 2 --run-time 5m --headless

# Monitorear métricas de producción
```

## 🎓 Aprende Más

### Recursos Internos

- **GUIA_TEST_PERFORMANCE.md** - Tutorial paso a paso
- **OPTIMIZACION_PERFORMANCE.md** - Estrategias avanzadas con código
- **locustfile.py** - Ejemplos de escenarios de carga

### Recursos Externos

- [FastAPI Performance](https://fastapi.tiangolo.com/advanced/performance/)
- [Firestore Best Practices](https://firebase.google.com/docs/firestore/best-practices)
- [Locust Documentation](https://docs.locust.io/)
- [Redis Caching](https://redis.io/docs/manual/patterns/caching/)

## 🐛 Troubleshooting

### Test falla con "Connection refused"

**Solución:** Verificar que el servidor esté corriendo

```bash
curl http://localhost:8000/ping
```

### Todos los endpoints timeout

**Solución:** Aumentar timeout o verificar Firebase

```python
TIMEOUT_SECONDS = 60  # En test_all_endpoints_performance.py
```

### Locust no instala

**Solución:** Actualizar pip y reinstalar

```bash
pip install --upgrade pip
pip install -r requirements-test.txt --force-reinstall
```

## 📞 Soporte

Si encuentras problemas o tienes sugerencias:

1. Revisar logs del servidor
2. Ejecutar `/health` y `/firebase/status`
3. Consultar `GUIA_TEST_PERFORMANCE.md`
4. Crear issue en GitHub con:
   - Comando ejecutado
   - Error completo
   - Archivo JSON generado

## 🗓️ Mantenimiento

**Frecuencia recomendada:**

- ✅ **Daily:** Health checks automáticos
- ✅ **Weekly:** Test de performance completo
- ✅ **Monthly:** Load testing exhaustivo
- ✅ **Per Release:** Validación completa pre-deploy

**Próxima revisión:** 2024-12-12

---

**Última actualización:** 2024-11-12  
**Herramientas:** Python 3.11+, Locust 2.32+, FastAPI 0.116+

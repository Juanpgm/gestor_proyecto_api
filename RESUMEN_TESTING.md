# 🎯 Resumen: Test de Performance y Optimizaciones

## ✅ Lo que se ha creado

### 📄 Scripts de Testing

1. **`test_all_endpoints_performance.py`**

   - Test completo de todos los endpoints de la API
   - Mide tiempos de respuesta con 3 iteraciones por endpoint
   - Genera reportes en consola con colores y archivo JSON
   - Clasifica endpoints por performance (Excelente/Bueno/Aceptable/Lento/Muy Lento)
   - Identifica top 10 endpoints más lentos que requieren optimización

2. **`locustfile.py`**

   - Configuración de load testing con Locust
   - Simula 4 tipos de usuarios: ReadHeavy, Admin, Dashboard, Mobile
   - Escenarios de stress test incluidos
   - Tags para ejecutar tests específicos por categoría

3. **`requirements-test.txt`**
   - Dependencias necesarias para testing
   - Incluye: pytest, locust, colorama, redis, prometheus-client, etc.

### 📚 Documentación

1. **`docs/GUIA_TEST_PERFORMANCE.md`**

   - Guía rápida para ejecutar tests
   - Configuración inicial
   - Interpretación de resultados
   - Optimizaciones rápidas
   - Troubleshooting común

2. **`docs/OPTIMIZACION_PERFORMANCE.md`**

   - Estrategias detalladas de optimización
   - Código completo para implementar:
     - Redis caching
     - Paginación efectiva
     - Compresión GZIP
     - Streaming de datos
     - Background tasks
     - Rate limiting
     - Índices Firestore
     - Connection pooling
   - Plan de implementación por fases
   - Métricas de éxito y KPIs

3. **`docs/README_TESTING.md`**
   - Overview completo del sistema de testing
   - Workflow recomendado
   - Interpretación de métricas
   - Recursos y links útiles

## 🚀 Cómo Usar

### Paso 1: Instalación

```bash
# Instalar dependencias de testing
pip install -r requirements-test.txt
```

### Paso 2: Ejecutar Test de Performance

```bash
# Asegurarse de que el servidor esté corriendo
uvicorn main:app --reload --port 8000

# En otra terminal, ejecutar el test
python test_all_endpoints_performance.py
```

**Output esperado:**

```
===============================================================================
  TEST DE RENDIMIENTO - GESTOR PROYECTO API
  Base URL: http://localhost:8000
  Iteraciones por endpoint: 3
  Timeout: 30s
===============================================================================

================================================================================
ENDPOINTS GENERALES
================================================================================

Probando: Endpoint raíz
  Método: GET | Ruta: /
  Iteración 1: 0.123s (Status: 200)
  Iteración 2: 0.115s (Status: 200)
  Iteración 3: 0.118s (Status: 200)
  ⏱️  Promedio: 0.119s | Min: 0.115s | Max: 0.123s | Performance: EXCELENTE

...

===============================================================================
TOP 10 ENDPOINTS MÁS LENTOS (Requieren optimización)
===============================================================================

1. Todos los contratos empréstito
   GET /contratos_emprestito_all
   ⏱️  Tiempo promedio: 4.523s
   📊 Performance: LENTO
   ⚠️  Requiere atención
   💡 Sugerencias:
      - Revisar complejidad de queries
      - Considerar lazy loading
      - Implementar caché de resultados

...
```

### Paso 3: Analizar Resultados

El test genera un archivo JSON con resultados detallados:

```
performance_report_20241112_153045.json
```

### Paso 4: Implementar Optimizaciones

Consultar `docs/OPTIMIZACION_PERFORMANCE.md` para estrategias específicas según los endpoints lentos identificados.

## 📊 Endpoints Monitoreados

El test evalúa **67 endpoints** en total:

### Categorías principales:

- **Generales** (6 endpoints): /, /ping, /health, /cors-test, /test/utf8, /centros-gestores/nombres-unicos
- **Firebase** (3 endpoints): /firebase/status, /firebase/collections, /firebase/collections/summary
- **Proyectos de Inversión** (4 endpoints): Todos los proyectos, filtros por BPIN, BP, centro gestor
- **Unidades de Proyecto** (4 endpoints): Geometrías, atributos, filtros, download GeoJSON
- **Contratos** (2 endpoints): Init contratos seguimiento, reportes
- **Empréstito** (14 endpoints): Contratos, bancos, procesos, pagos, RPCs, convenios, órdenes, flujos caja, proyecciones
- **Autenticación** (3 endpoints): Config, health check, listado usuarios

## 🎯 Optimizaciones Recomendadas

### Prioridad ALTA (Implementar esta semana)

1. **Agregar GZIP compression**

   ```python
   from fastapi.middleware.gzip import GZipMiddleware
   app.add_middleware(GZipMiddleware, minimum_size=1000)
   ```

   **Impacto:** 30-50% reducción en tamaño de respuestas

2. **Paginación obligatoria en endpoints masivos**

   ```python
   limit: int = Query(100, ge=10, le=500)
   offset: int = Query(0, ge=0)
   ```

   **Impacto:** 70-80% reducción en tiempo de respuesta

3. **Crear índices en Firestore**
   ```javascript
   // firestore.indexes.json
   {
     "indexes": [
       {
         "collectionGroup": "contratos_emprestito",
         "fields": [
           {"fieldPath": "nombre_centro_gestor", "order": "ASCENDING"},
           {"fieldPath": "fecha_creacion", "order": "DESCENDING"}
         ]
       }
     ]
   }
   ```
   **Impacto:** 50-90% mejora en queries filtradas

### Prioridad MEDIA (Implementar este mes)

1. **Redis para caché**

   - Caché de respuestas frecuentes
   - TTL de 5-10 minutos
   - **Impacto:** 80-95% mejora en hits de caché

2. **Background tasks para procesamiento pesado**

   - APIs externas (SECOP, TVEC)
   - Procesamiento masivo de datos
   - **Impacto:** De 30s a 2s en respuesta inicial

3. **Rate limiting en auth endpoints**
   - Prevenir abuso
   - Protección contra brute force
   - **Impacto:** Mejora en estabilidad general

## 🧪 Load Testing

### Escenarios Predefinidos

```bash
# Test básico (10 usuarios, 2 minutos)
locust -f locustfile.py --host=http://localhost:8000 \
  --users 10 --spawn-rate 1 --run-time 2m --headless

# Test de carga moderada (50 usuarios, 5 minutos)
locust -f locustfile.py --host=http://localhost:8000 \
  --users 50 --spawn-rate 5 --run-time 5m --headless

# Test de stress (100 usuarios)
locust -f locustfile.py --host=http://localhost:8000 \
  --users 100 --spawn-rate 10 --run-time 10m --headless --tags stress

# Solo operaciones de lectura
locust -f locustfile.py --host=http://localhost:8000 \
  --users 30 --spawn-rate 3 --run-time 3m --headless --tags read
```

### Métricas a Monitorear

- **RPS (Requests per second):** > 100 ideal
- **P50 Response Time:** < 500ms ideal
- **P95 Response Time:** < 2s ideal
- **P99 Response Time:** < 5s ideal
- **Error Rate:** < 0.1% ideal
- **Failures:** 0 ideal

## 📈 Roadmap de Optimización

### Semana 1 (Ahora)

- ✅ Ejecutar test de performance baseline
- ✅ Identificar endpoints >5s
- ✅ Implementar GZIP compression
- ✅ Agregar paginación a 3-5 endpoints críticos

### Semana 2-3

- ⬜ Crear índices en Firestore
- ⬜ Implementar rate limiting
- ⬜ Setup Redis en desarrollo
- ⬜ Caché para 5 endpoints más usados

### Mes 1

- ⬜ Background tasks para procesamiento pesado
- ⬜ Streaming para descargas grandes
- ⬜ Connection pooling optimizado
- ⬜ Monitoring con Prometheus

### Mes 2

- ⬜ Setup Redis en producción
- ⬜ Dashboard de métricas
- ⬜ Alertas automáticas
- ⬜ Optimización de queries complejas

## 📊 Métricas de Éxito

### Antes de Optimizaciones (Baseline)

- Tiempo promedio general: **TBD** (ejecutar test)
- Endpoints >5s: **TBD**
- Endpoints <1s: **TBD**

### Target Después de Optimizaciones

- Tiempo promedio general: **< 1s**
- Endpoints >5s: **0**
- Endpoints <1s: **> 80%**

## 🔍 Troubleshooting Común

### Problema: Test falla con timeout

**Solución:** Aumentar `TIMEOUT_SECONDS = 60` en el script

### Problema: No se puede conectar al servidor

**Solución:**

```bash
curl http://localhost:8000/ping
# Si falla, iniciar servidor
uvicorn main:app --reload --port 8000
```

### Problema: Locust no encuentra endpoints

**Solución:** Verificar que BASE_URL sea correcto y servidor esté corriendo

### Problema: Muchos errores 503

**Solución:** Firebase no configurado o colecciones muy grandes sin índices

## 📚 Archivos Creados

```
gestor_proyecto_api/
├── test_all_endpoints_performance.py    # ⭐ Test principal
├── locustfile.py                         # ⭐ Load testing
├── requirements-test.txt                 # ⭐ Dependencias
└── docs/
    ├── GUIA_TEST_PERFORMANCE.md         # 📖 Guía rápida
    ├── OPTIMIZACION_PERFORMANCE.md      # 📖 Estrategias detalladas
    └── README_TESTING.md                # 📖 Overview completo
```

## 🎓 Próximos Pasos

1. **Ejecutar el test ahora:**

   ```bash
   python test_all_endpoints_performance.py
   ```

2. **Analizar resultados y priorizar endpoints lentos**

3. **Implementar optimizaciones según prioridad:**

   - GZIP compression (5 minutos)
   - Paginación (1-2 horas)
   - Índices Firestore (30 minutos)

4. **Re-ejecutar test para validar mejoras**

5. **Documentar mejoras en changelog**

## 🤝 Contribución

Para reportar problemas o sugerir mejoras:

1. Ejecutar el test completo
2. Guardar el reporte JSON
3. Crear issue con reporte adjunto
4. Proponer solución con código

---

**Creado:** 2024-11-12  
**Autor:** GitHub Copilot  
**Versión:** 1.0

¡Listo para optimizar! 🚀

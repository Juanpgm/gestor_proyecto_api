# Skill: Endpoints FastAPI de Alta Concurrencia

## Objetivo

Optimizar endpoints críticos para alta concurrencia manteniendo latencia estable, seguridad y robustez.

## Principios

- Minimizar trabajo por request.
- Evitar bloqueos del event loop.
- Aplicar límites explícitos a operaciones costosas.
- Mantener respuestas predecibles bajo carga.

## Reglas de diseño para Copilot

1. **Asincronía correcta**
   - En endpoints `async`, evitar llamadas bloqueantes de red/IO sin estrategia adecuada.
   - Encapsular operaciones pesadas fuera del request path cuando sea viable.
2. **Validación y serialización eficiente**
   - Validar solo lo necesario para el caso de uso.
   - Evitar payloads gigantes y campos redundantes.
3. **Acceso a datos eficiente**
   - Evitar consultas N+1 y lecturas repetidas.
   - Reutilizar resultados en el mismo ciclo de request cuando aplique.
4. **Control de presión (backpressure)**
   - Timeouts explícitos para llamadas externas.
   - Límites de tamaño de entrada/paginación.

## Patrones recomendados

- Paginación obligatoria en listados grandes.
- Degradación controlada ante servicios externos lentos.
- Cache selectiva para lecturas de alta frecuencia (si el dominio lo permite).
- Procesamiento diferido para tareas no críticas al request.

## Errores y resiliencia

- Responder códigos HTTP consistentes para timeout, dependencia externa caída y validación.
- Evitar filtrar detalles internos en errores.
- Registrar métricas operativas por endpoint (latencia, tasa de error, p95/p99).

## Seguridad bajo carga

- Validar autenticación/autorización antes de operaciones costosas.
- Prevenir abuso con límites de request por cliente/identidad cuando aplique.
- Sanitizar inputs para evitar payloads maliciosos o excesivos.

## Pruebas de rendimiento

- Definir escenarios `locust` para:
  - carga nominal
  - picos concurrentes
  - estrés sostenido
- Medir p50/p95/p99, error rate y throughput.
- Comparar baseline vs. cambios para detectar regresiones.

## Checklist operativo

- [ ] ¿El endpoint evita operaciones bloqueantes críticas?
- [ ] ¿Tiene límites de paginación/tamaño/timeout?
- [ ] ¿El acceso a Firestore evita lecturas redundantes?
- [ ] ¿Se midió rendimiento antes y después?
- [ ] ¿Se conservó seguridad y contrato de respuesta?

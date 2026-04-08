# Skill: Reglas Operativas por Entorno (Local / Staging / Producción)

## Objetivo

Forzar que Copilot adapte propuestas de código y operación según entorno, reduciendo riesgos de seguridad, regresiones y errores de despliegue.

## Entornos soportados

- `local`: desarrollo rápido y depuración.
- `staging`: validación pre-producción con datos/servicios controlados.
- `prod`: operación estable, segura y trazable.

## Reglas globales (aplican en todos los entornos)

- Nunca exponer secretos, tokens, llaves de service account o credenciales en código/logs.
- Mantener contratos de API compatibles salvo requerimiento explícito de breaking change.
- Registrar errores con contexto útil sin datos sensibles.
- Validar entradas con Pydantic y respuestas consistentes.

## Local

### Objetivo

Acelerar desarrollo y pruebas sin comprometer buenas prácticas.

### Reglas

- Permitir logging más detallado, pero sin secretos.
- Usar datasets/mocks de prueba cuando sea posible para evitar tocar datos reales.
- Habilitar herramientas de diagnóstico y scripts de verificación rápida.
- Priorizar feedback rápido con pruebas específicas.

### Validación mínima sugerida

- `pytest -q --maxfail=1`
- Pruebas directas del endpoint modificado.

## Staging

### Objetivo

Simular producción con controles de calidad reforzados.

### Reglas

- Configuración lo más cercana posible a producción.
- Activar métricas de latencia/error por endpoint crítico.
- Validar integraciones externas (Firebase/Firestore/Auth) con credenciales de entorno seguro.
- Ejecutar smoke tests y pruebas de regresión del área impactada.

### Validación mínima sugerida

- `pytest -q`
- `pytest --cov=. --cov-report=term-missing`
- Escenarios de carga focalizados con `locust` para endpoints críticos.

## Producción

### Objetivo

Garantizar disponibilidad, seguridad y trazabilidad operativa.

### Reglas

- Cambios graduales y reversibles (feature flags/rollout controlado).
- Endpoints críticos con timeouts y manejo explícito de fallos externos.
- Prohibido activar debug detallado o logs con payload sensible.
- Mantener límites de entrada, paginación y controles anti abuso.
- Requerir plan de rollback para cambios de alto impacto.

### Gate de despliegue recomendado

- Evidencia de pruebas en staging.
- Verificación de métricas base (latencia p95/p99 y tasa de error).
- Confirmación de variables de entorno y secretos.

## Decisiones que Copilot debe tomar por defecto

- Si el entorno no está explícito: asumir `staging` para validación y `local` para desarrollo.
- En tareas sensibles (auth, pagos, escritura masiva): aplicar reglas de `prod` desde diseño.
- Ante ambigüedad operativa: priorizar seguridad y reversibilidad sobre velocidad.

## Checklist operativo

- [ ] ¿El cambio define claramente el entorno objetivo?
- [ ] ¿La configuración y validaciones son adecuadas para ese entorno?
- [ ] ¿Se evitó exponer secretos en código/logs?
- [ ] ¿Existe plan de rollback si el cambio impacta producción?
- [ ] ¿Hay evidencia de pruebas acordes al riesgo?

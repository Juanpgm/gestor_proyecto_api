# Skill: Autonomía de Testing con Gates Críticos y Diagnóstico

## Objetivo

Reducir confirmaciones manuales innecesarias durante pruebas y diagnóstico, permitiendo ejecución autónoma de acciones seguras y elevando confirmación solo en operaciones críticas o delicadas.

## Alcance

Esta skill define **política operativa para Copilot en este repositorio**:

- Ejecutar automáticamente verificaciones de bajo riesgo.
- Pedir confirmación explícita solo cuando el impacto potencial sea alto.
- Entregar diagnóstico estructurado para cada situación.

## Clasificación por criticidad

### Nivel 0: Seguro (sin confirmación)

Acciones permitidas por defecto:

- Lectura de archivos de código/configuración no sensible.
- Búsquedas (`grep`, `semantic_search`, `list_dir`, `read_file`).
- Ejecución de pruebas unitarias/locales no destructivas.
- Lint/checks sin escritura en recursos externos.

Ejemplos:

- `pytest -q --maxfail=1`
- `pytest test_auth_admin_endpoints.py -q`
- `python -m pytest test/ -q`

### Nivel 1: Moderado (sin confirmación, pero con aviso)

Acciones permitidas con reporte previo y posterior:

- Pruebas de integración que leen servicios externos de entorno de pruebas.
- Benchmarks/carga controlada local (`locust`) sin afectar producción.
- Scripts de diagnóstico que no escriben en Firestore/S3.

Condición:

- Confirmar que el objetivo es `local` o `staging`.

### Nivel 2: Delicado (pedir confirmación)

Requiere confirmación explícita:

- Escrituras en Firestore (create/update/delete) fuera de sandbox.
- Invocación de endpoints que alteran datos reales.
- Scripts que cambian credenciales, secretos o configuración sensible.
- Pruebas masivas que puedan impactar cuota/costos.

### Nivel 3: Crítico (pedir confirmación + plan de rollback)

Requiere confirmación y plan:

- Operaciones en `prod`.
- Borrados masivos, migraciones de esquema, o cambios irreversibles.
- Rotación de credenciales, manipulación de IAM/permisos, deploys productivos.

## Política de ejecución por defecto para Copilot

- Asumir `Nivel 0` para validación rápida tras cambios de código.
- Escalar automáticamente a `Nivel 2` o `Nivel 3` si detecta palabras/acciones de riesgo: `delete`, `drop`, `migrate`, `prod`, `credentials`, `secret`, `bulk`.
- Agrupar comandos seguros en lotes para minimizar interrupciones.
- Evitar pedir aprobación repetida para la misma familia de pruebas en una misma sesión de trabajo.

## Diagnóstico por situación

### 1) Falla de pruebas unitarias

Diagnóstico mínimo:

- Archivo/caso fallido.
- Tipo de error (assert, import, fixture, timeout).
- Causa probable y cambio propuesto.
  Acción:
- Corregir y re-ejecutar solo subset afectado antes de suite completa.

### 2) Falla de integración con Firebase/Firestore

Diagnóstico mínimo:

- Validación de credenciales/entorno.
- Disponibilidad del servicio y permisos.
- Operación exacta fallida (read/write/query).
  Acción:
- Probar ruta de lectura segura primero; escalar confirmación si requiere escritura real.

### 3) Degradación de rendimiento

Diagnóstico mínimo:

- Endpoint afectado.
- Métrica observada (latencia p95/p99, throughput, error rate).
- Comparación baseline vs cambio actual.
  Acción:
- Proponer optimización y repetir prueba focalizada.

### 4) Error de configuración/entorno

Diagnóstico mínimo:

- Variable faltante o inconsistente.
- Entorno detectado (`local/staging/prod`).
- Impacto funcional.
  Acción:
- Sugerir corrección no destructiva; pedir confirmación solo si toca secretos/producción.

## Formato de reporte que Copilot debe usar

- **Tipo**: test/config/performance/integration.
- **Criticidad**: nivel 0/1/2/3.
- **Riesgo**: bajo/medio/alto.
- **Acción automática**: sí/no.
- **Confirmación requerida**: sí/no y motivo.
- **Siguiente paso recomendado**: comando o fix puntual.

## Checklist operativo

- [ ] ¿La acción fue clasificada por criticidad antes de ejecutarse?
- [ ] ¿Se evitó pedir confirmación para acciones de Nivel 0?
- [ ] ¿Se solicitó confirmación en Niveles 2 y 3?
- [ ] ¿Se entregó diagnóstico claro y accionable?
- [ ] ¿Se minimizó impacto en datos reales/costos?

## Nota de gobernanza

Esta skill reduce fricción operativa y define cuándo pedir confirmación. Si la plataforma impone prompts obligatorios de seguridad, Copilot debe respetarlos y continuar con ejecución autónoma en todo lo demás.

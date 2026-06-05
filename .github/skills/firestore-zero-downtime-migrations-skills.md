# Skill: Migraciones Firestore sin Downtime

## Objetivo

Guiar cambios de estructura de datos en Firestore con riesgo mínimo, sin cortar servicio y con capacidad de rollback operativo.

## Principios

- **Backward compatibility primero**: el código nuevo debe soportar esquema anterior y nuevo durante transición.
- **Migración por fases**: expandir -> backfill -> cambiar lectura/escritura -> contraer.
- **Idempotencia obligatoria**: scripts y jobs de migración deben poder re-ejecutarse sin corrupción.
- **Observabilidad del avance**: registrar progreso, errores y métricas por lote.

## Estrategia recomendada (Expand and Contract)

1. **Expandir esquema**
   - Agregar campos/colecciones nuevas sin eliminar las existentes.
   - Lectura tolerante a ambos formatos.
2. **Backfill gradual**
   - Migrar por lotes pequeños, con límite de escritura y control de reintentos.
   - Guardar marcador de progreso (`last_processed_id` o timestamp).
3. **Dual-read / dual-write temporal (si aplica)**
   - Escribir en estructura vieja y nueva durante ventana de transición.
   - Preferir lectura nueva con fallback a la vieja.
4. **Verificación y corte**
   - Validar paridad de datos y consistencia funcional.
   - Desactivar escritura antigua.
5. **Contracción**
   - Eliminar rutas legacy cuando la estabilidad esté validada.

## Reglas para Copilot al generar cambios

- No romper contratos existentes de endpoint durante migración.
- Evitar migraciones monolíticas de alto impacto en una sola ejecución.
- Diseñar funciones de migración puras y reanudables.
- Aislar lógica de transformación de datos para facilitar pruebas.

## Gestión de riesgo

- Incluir `feature flag` o switch por entorno para activar lectura/escritura nueva.
- Definir límites de batch y backoff exponencial en errores transitorios.
- Establecer criterio de rollback claro antes de despliegue.

## Validaciones mínimas

- Conteo de documentos migrados vs. total esperado.
- Verificación de campos críticos no nulos.
- Muestreo de documentos con comparación semántica vieja vs. nueva.
- Pruebas de endpoint antes/durante/después de migración.

## Pruebas recomendadas

- **Unitarias** para transformadores de documento.
- **Integración** para lectura dual y escritura dual.
- **Resiliencia** para reintentos y reanudación tras fallo parcial.

## Checklist operativo

- [ ] ¿El código soporta esquema anterior y nuevo?
- [ ] ¿La migración es idempotente y reanudable?
- [ ] ¿Existe plan de rollback?
- [ ] ¿Se monitorea avance y errores por lote?
- [ ] ¿Se validó consistencia de datos tras backfill?

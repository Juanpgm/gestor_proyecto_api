# Skill: FastAPI + Firebase API Engineering (Avanzado)

## Objetivo

Esta skill guía a Copilot para proponer código robusto, testeable, seguro y performante en este repositorio `gestor_proyecto_api`.

## Stack y contexto del proyecto

- Backend principal: `FastAPI` + `Uvicorn`.
- Persistencia y servicios: `Firebase Admin SDK` + `Firestore`.
- Testing: `pytest`, `pytest-asyncio`, `pytest-cov`, `httpx`.
- Performance: `locust`.
- Seguridad/Auth: JWT, Firebase Auth, credenciales por entorno.

## Reglas de trabajo para Copilot

1. **Cambios mínimos y enfocados**
   - Evitar refactors masivos si no son requeridos por la tarea.
   - Mantener estilo existente y compatibilidad de endpoints.
2. **Diseño de API estable**
   - Mantener contratos de request/response.
   - Validar entrada con modelos `Pydantic` y mensajes de error claros.
3. **Asincronía correcta**
   - No bloquear event loop en endpoints `async`.
   - Evitar operaciones I/O pesadas sin patrón asíncrono o encapsulado.
4. **Errores y observabilidad**
   - Manejar errores con `HTTPException` y logs accionables.
   - Incluir contexto útil (endpoint, entidad, id de operación) sin exponer secretos.
5. **Seguridad primero**
   - Nunca exponer llaves, tokens, service accounts o secretos en código/logs.
   - Usar variables de entorno y verificar configuración segura.

## Skill de testing (prioridad alta)

- Para cada cambio funcional, proponer o ajustar pruebas en:
  - Endpoints (`test_*endpoint*.py`).
  - Reglas de negocio críticas (auth, validaciones, escritura en Firestore).
- Preferir pruebas específicas antes de pruebas globales.
- Validar al menos:
  - Caso exitoso.
  - Caso de validación inválida.
  - Caso de error externo (Firebase/Firestore no disponible o respuesta inesperada).

### Comandos de validación sugeridos

- `pytest -q`
- `pytest -q --maxfail=1`
- `pytest --cov=. --cov-report=term-missing`

## Skill de calidad de código

- Favorecer funciones pequeñas y legibles.
- Eliminar duplicación cuando el beneficio sea claro y local.
- Mantener nombres explícitos y coherentes con dominio (`contrato`, `frente`, `intervencion`, etc.).
- Tipar parámetros y retornos en funciones nuevas o modificadas.

## Skill de rendimiento

1. **Firestore eficiente**
   - Leer solo campos necesarios cuando sea posible.
   - Evitar lecturas repetidas en loops; agrupar consultas cuando aplique.
2. **FastAPI eficiente**
   - Minimizar trabajo por request.
   - Evitar serialización innecesaria de payloads grandes.
3. **Carga y regresión**
   - Si un endpoint es crítico o masivo, sugerir prueba con `locust`.
   - Identificar riesgos de latencia antes de introducir lógica adicional en hot paths.

## Skill de Firebase/Firestore

- Centralizar acceso a cliente/configuración en módulos de `database/` o capa equivalente.
- Validar existencia de documentos y campos opcionales antes de usarlos.
- Diseñar escritura idempotente cuando sea posible.
- Manejar errores de SDK de Firebase con mensajes operativos y fallback claro.

## Skill de buenas prácticas para PR/cambios

- Incluir resumen breve de:
  - Qué cambió.
  - Riesgo técnico.
  - Cómo se validó (tests/comandos).
- Si no se ejecutaron pruebas, declararlo explícitamente y por qué.

## Checklist operativo para Copilot

Antes de finalizar una propuesta de cambio:

- [ ] ¿Se mantiene el contrato del endpoint?
- [ ] ¿Hay validación de entrada/salida suficiente?
- [ ] ¿Se maneja correctamente el error de Firebase/Firestore?
- [ ] ¿El cambio evita degradar rendimiento en rutas críticas?
- [ ] ¿Hay pruebas nuevas/actualizadas para el comportamiento modificado?
- [ ] ¿No se filtraron secretos o credenciales?

## Modo estricto (cuando la tarea es sensible)

Para autenticación, autorización, datos financieros, o escritura masiva:

- Aplicar validación defensiva adicional.
- Requerir pruebas de error y borde.
- Priorizar seguridad y consistencia sobre micro-optimizaciones.

# Repositorio de Skills para Copilot

Esta carpeta contiene habilidades especializadas para mejorar la calidad de las propuestas de código en este proyecto.

## Skills disponibles

- `fastapi-firebase-api-skills.md`: guía avanzada para desarrollo de APIs con FastAPI + Python + Firebase/Firestore, con foco en:
  - testing
  - calidad de código
  - rendimiento
  - seguridad
  - buenas prácticas operativas
- `firestore-zero-downtime-migrations-skills.md`: estrategia y checklist para migraciones de esquema en Firestore sin downtime (expand/contract, backfill, dual-read/write, rollback).
- `fastapi-high-concurrency-endpoints-skills.md`: prácticas para endpoints de alta concurrencia en FastAPI (latencia, límites, resiliencia, pruebas de carga).
- `environment-operational-rules-skills.md`: reglas operativas por entorno (`local`, `staging`, `prod`) para ajustar seguridad, validación, observabilidad y despliegue.
- `smart-testing-autonomy-and-critical-gates-skills.md`: política para ejecutar pruebas/diagnóstico con mínima fricción, solicitando confirmación solo en acciones delicadas o críticas.

## Convención para nuevas skills

- Crear un archivo por dominio técnico.
- Nombrar con formato: `area-tecnica-skills.md`.
- Incluir siempre: objetivo, reglas, checklist y comandos de validación.

# Informe de Endpoints sin Autenticación con Error

- Fecha: 2026-03-04T02:22:22.708232
- Total endpoints con error (excluyendo 401/403): 36
- Criterio: escaneo automático de rutas FastAPI con payload mínimo y placeholders tipados para path params.

## 1. POST /auth/validate-session

- Código observado: `400`
- Ruta probada: `/auth/validate-session`
- Detalle: `{"error": "Token requerido", "message": "Proporcione el token en el header Authorization o en el body como id_token", "code": "TOKEN_REQUIRED"}`
- Recomendaciones:
  - Revisar manejo de errores para separar fallas de validación (4xx) de fallas internas (5xx).
  - Añadir pruebas de integración para este caso de error y su mensaje esperado.

## 2. DELETE /emprestito/eliminar-convenio-transferencia/{referencia_contrato}

- Código observado: `404`
- Ruta probada: `/emprestito/eliminar-convenio-transferencia/CONT-TEST`
- Detalle: `No se encontró ningún convenio con referencia_contrato: CONT-TEST`
- Recomendaciones:
  - Confirmar si el comportamiento esperado para recurso inexistente es 404 o 204 idempotente.
  - Documentar explícitamente en OpenAPI el caso de no encontrado y ejemplo de respuesta.

## 3. DELETE /emprestito/eliminar-orden-compra/{numero_orden}

- Código observado: `404`
- Ruta probada: `/emprestito/eliminar-orden-compra/OC-TEST`
- Detalle: `No se encontró ninguna orden de compra con numero_orden: OC-TEST`
- Recomendaciones:
  - Confirmar si el comportamiento esperado para recurso inexistente es 404 o 204 idempotente.
  - Documentar explícitamente en OpenAPI el caso de no encontrado y ejemplo de respuesta.

## 4. POST /auth/change-password

- Código observado: `422`
- Ruta probada: `/auth/change-password`
- Detalle: `[{"type": "missing", "loc": ["body", "uid"], "msg": "Field required", "input": null}, {"type": "missing", "loc": ["body", "new_password"], "msg": "Field required", "input": null}]`
- Recomendaciones:
  - Agregar ejemplos completos en Swagger/OpenAPI para evitar llamadas vacías (body/query/form).
  - Convertir validaciones de campos requeridos en mensajes de negocio más claros para frontend.
  - Evaluar valores por defecto en campos opcionales para reducir errores evitables.

## 5. POST /auth/google

- Código observado: `422`
- Ruta probada: `/auth/google`
- Detalle: `[{"type": "missing", "loc": ["body", "google_token"], "msg": "Field required", "input": null}]`
- Recomendaciones:
  - Agregar ejemplos completos en Swagger/OpenAPI para evitar llamadas vacías (body/query/form).
  - Convertir validaciones de campos requeridos en mensajes de negocio más claros para frontend.
  - Evaluar valores por defecto en campos opcionales para reducir errores evitables.

## 6. POST /auth/login

- Código observado: `422`
- Ruta probada: `/auth/login`
- Detalle: `[{"type": "missing", "loc": ["body", "email"], "msg": "Field required", "input": {}}, {"type": "missing", "loc": ["body", "password"], "msg": "Field required", "input": {}}]`
- Recomendaciones:
  - Agregar ejemplos completos en Swagger/OpenAPI para evitar llamadas vacías (body/query/form).
  - Convertir validaciones de campos requeridos en mensajes de negocio más claros para frontend.
  - Evaluar valores por defecto en campos opcionales para reducir errores evitables.

## 7. POST /auth/register

- Código observado: `422`
- Ruta probada: `/auth/register`
- Detalle: `[{"type": "missing", "loc": ["body", "email"], "msg": "Field required", "input": {}}, {"type": "missing", "loc": ["body", "password"], "msg": "Field required", "input": {}}, {"type": "missing", "loc": ["body", "confirmPassword"], "msg": "Field required", "input": {}}, {"type": "missing", "loc": ["body", "name"], "msg": "Field required", "input": {}}, {"type": "missing", "loc": ["body", "cellphone"], "msg": "Field required", "input": {}}, {"type": "missing", "loc": ["body", "nombre_centro_gestor"], "msg": "Field required", "input": {}}]`
- Recomendaciones:
  - Agregar ejemplos completos en Swagger/OpenAPI para evitar llamadas vacías (body/query/form).
  - Convertir validaciones de campos requeridos en mensajes de negocio más claros para frontend.
  - Evaluar valores por defecto en campos opcionales para reducir errores evitables.

## 8. POST /crear_intervencion

- Código observado: `422`
- Ruta probada: `/crear_intervencion`
- Detalle: `[{"type": "missing", "loc": ["body", "upid"], "msg": "Field required", "input": null}]`
- Recomendaciones:
  - Agregar ejemplos completos en Swagger/OpenAPI para evitar llamadas vacías (body/query/form).
  - Convertir validaciones de campos requeridos en mensajes de negocio más claros para frontend.
  - Evaluar valores por defecto en campos opcionales para reducir errores evitables.

## 9. DELETE /eliminar_intervencion

- Código observado: `422`
- Ruta probada: `/eliminar_intervencion`
- Detalle: `[{"type": "missing", "loc": ["query", "intervencion_id"], "msg": "Field required", "input": null}]`
- Recomendaciones:
  - Agregar ejemplos completos en Swagger/OpenAPI para evitar llamadas vacías (body/query/form).
  - Convertir validaciones de campos requeridos en mensajes de negocio más claros para frontend.
  - Evaluar valores por defecto en campos opcionales para reducir errores evitables.

## 10. DELETE /eliminar_unidad_proyecto

- Código observado: `422`
- Ruta probada: `/eliminar_unidad_proyecto`
- Detalle: `[{"type": "missing", "loc": ["query", "upid"], "msg": "Field required", "input": null}]`
- Recomendaciones:
  - Agregar ejemplos completos en Swagger/OpenAPI para evitar llamadas vacías (body/query/form).
  - Convertir validaciones de campos requeridos en mensajes de negocio más claros para frontend.
  - Evaluar valores por defecto en campos opcionales para reducir errores evitables.

## 11. POST /emprestito/cargar-convenio-transferencia

- Código observado: `422`
- Ruta probada: `/emprestito/cargar-convenio-transferencia`
- Detalle: `[{"type": "missing", "loc": ["body", "referencia_contrato"], "msg": "Field required", "input": null}, {"type": "missing", "loc": ["body", "nombre_centro_gestor"], "msg": "Field required", "input": null}, {"type": "missing", "loc": ["body", "banco"], "msg": "Field required", "input": null}, {"type": "missing", "loc": ["body", "objeto_contrato"], "msg": "Field required", "input": null}, {"type": "missing", "loc": ["body", "valor_contrato"], "msg": "Field required", "input": null}, {"type": "missing", "loc": ["body", "nombre_resumido_proceso"], "msg": "Field required", "input": null}]`
- Recomendaciones:
  - Agregar ejemplos completos en Swagger/OpenAPI para evitar llamadas vacías (body/query/form).
  - Convertir validaciones de campos requeridos en mensajes de negocio más claros para frontend.
  - Evaluar valores por defecto en campos opcionales para reducir errores evitables.

## 12. POST /emprestito/cargar-orden-compra

- Código observado: `422`
- Ruta probada: `/emprestito/cargar-orden-compra`
- Detalle: `[{"type": "missing", "loc": ["body", "numero_orden"], "msg": "Field required", "input": null}, {"type": "missing", "loc": ["body", "nombre_centro_gestor"], "msg": "Field required", "input": null}, {"type": "missing", "loc": ["body", "nombre_banco"], "msg": "Field required", "input": null}, {"type": "missing", "loc": ["body", "nombre_resumido_proceso"], "msg": "Field required", "input": null}, {"type": "missing", "loc": ["body", "valor_proyectado"], "msg": "Field required", "input": null}]`
- Recomendaciones:
  - Agregar ejemplos completos en Swagger/OpenAPI para evitar llamadas vacías (body/query/form).
  - Convertir validaciones de campos requeridos en mensajes de negocio más claros para frontend.
  - Evaluar valores por defecto en campos opcionales para reducir errores evitables.

## 13. POST /emprestito/cargar-pago

- Código observado: `422`
- Ruta probada: `/emprestito/cargar-pago`
- Detalle: `[{"type": "missing", "loc": ["body", "numero_rpc"], "msg": "Field required", "input": null}, {"type": "missing", "loc": ["body", "valor_pago"], "msg": "Field required", "input": null}, {"type": "missing", "loc": ["body", "fecha_transaccion"], "msg": "Field required", "input": null}, {"type": "missing", "loc": ["body", "referencia_contrato"], "msg": "Field required", "input": null}, {"type": "missing", "loc": ["body", "nombre_centro_gestor"], "msg": "Field required", "input": null}]`
- Recomendaciones:
  - Agregar ejemplos completos en Swagger/OpenAPI para evitar llamadas vacías (body/query/form).
  - Convertir validaciones de campos requeridos en mensajes de negocio más claros para frontend.
  - Evaluar valores por defecto en campos opcionales para reducir errores evitables.

## 14. POST /emprestito/cargar-proceso

- Código observado: `422`
- Ruta probada: `/emprestito/cargar-proceso`
- Detalle: `[{"type": "missing", "loc": ["body", "referencia_proceso"], "msg": "Field required", "input": null}, {"type": "missing", "loc": ["body", "nombre_centro_gestor"], "msg": "Field required", "input": null}, {"type": "missing", "loc": ["body", "nombre_banco"], "msg": "Field required", "input": null}, {"type": "missing", "loc": ["body", "plataforma"], "msg": "Field required", "input": null}]`
- Recomendaciones:
  - Agregar ejemplos completos en Swagger/OpenAPI para evitar llamadas vacías (body/query/form).
  - Convertir validaciones de campos requeridos en mensajes de negocio más claros para frontend.
  - Evaluar valores por defecto en campos opcionales para reducir errores evitables.

## 15. POST /emprestito/cargar-rpc

- Código observado: `422`
- Ruta probada: `/emprestito/cargar-rpc`
- Detalle: `[{"type": "missing", "loc": ["body", "numero_rpc"], "msg": "Field required", "input": null}, {"type": "missing", "loc": ["body", "beneficiario_id"], "msg": "Field required", "input": null}, {"type": "missing", "loc": ["body", "beneficiario_nombre"], "msg": "Field required", "input": null}, {"type": "missing", "loc": ["body", "descripcion_rpc"], "msg": "Field required", "input": null}, {"type": "missing", "loc": ["body", "fecha_contabilizacion"], "msg": "Field required", "input": null}, {"type": "missing", "loc": ["body", "fecha_impresion"], "msg": "Field required", "input": null}, {"type": "missing", "loc": ["body", "estado_liberacion"], "msg": "Field required", "input": null}, {"type": "mis`
- Recomendaciones:
  - Agregar ejemplos completos en Swagger/OpenAPI para evitar llamadas vacías (body/query/form).
  - Convertir validaciones de campos requeridos en mensajes de negocio más claros para frontend.
  - Evaluar valores por defecto en campos opcionales para reducir errores evitables.

## 16. POST /emprestito/flujo-caja/cargar-excel

- Código observado: `422`
- Ruta probada: `/emprestito/flujo-caja/cargar-excel`
- Detalle: `[{"type": "missing", "loc": ["body", "archivo_excel"], "msg": "Field required", "input": null}]`
- Recomendaciones:
  - Agregar ejemplos completos en Swagger/OpenAPI para evitar llamadas vacías (body/query/form).
  - Convertir validaciones de campos requeridos en mensajes de negocio más claros para frontend.
  - Evaluar valores por defecto en campos opcionales para reducir errores evitables.

## 17. PUT /emprestito/modificar-contrato

- Código observado: `422`
- Ruta probada: `/emprestito/modificar-contrato`
- Detalle: `[{"type": "missing", "loc": ["query", "referencia_contrato"], "msg": "Field required", "input": null}]`
- Recomendaciones:
  - Agregar ejemplos completos en Swagger/OpenAPI para evitar llamadas vacías (body/query/form).
  - Convertir validaciones de campos requeridos en mensajes de negocio más claros para frontend.
  - Evaluar valores por defecto en campos opcionales para reducir errores evitables.

## 18. PUT /emprestito/modificar-convenio-transferencia

- Código observado: `422`
- Ruta probada: `/emprestito/modificar-convenio-transferencia`
- Detalle: `[{"type": "missing", "loc": ["body", "doc_id"], "msg": "Field required", "input": null}]`
- Recomendaciones:
  - Agregar ejemplos completos en Swagger/OpenAPI para evitar llamadas vacías (body/query/form).
  - Convertir validaciones de campos requeridos en mensajes de negocio más claros para frontend.
  - Evaluar valores por defecto en campos opcionales para reducir errores evitables.

## 19. PUT /emprestito/modificar-orden-compra

- Código observado: `422`
- Ruta probada: `/emprestito/modificar-orden-compra`
- Detalle: `[{"type": "missing", "loc": ["query", "numero_orden"], "msg": "Field required", "input": null}]`
- Recomendaciones:
  - Agregar ejemplos completos en Swagger/OpenAPI para evitar llamadas vacías (body/query/form).
  - Convertir validaciones de campos requeridos en mensajes de negocio más claros para frontend.
  - Evaluar valores por defecto en campos opcionales para reducir errores evitables.

## 20. PUT /emprestito/modificar-proceso

- Código observado: `422`
- Ruta probada: `/emprestito/modificar-proceso`
- Detalle: `[{"type": "missing", "loc": ["query", "referencia_proceso"], "msg": "Field required", "input": null}]`
- Recomendaciones:
  - Agregar ejemplos completos en Swagger/OpenAPI para evitar llamadas vacías (body/query/form).
  - Convertir validaciones de campos requeridos en mensajes de negocio más claros para frontend.
  - Evaluar valores por defecto en campos opcionales para reducir errores evitables.

## 21. PUT /emprestito/modificar-rpc

- Código observado: `422`
- Ruta probada: `/emprestito/modificar-rpc`
- Detalle: `[{"type": "missing", "loc": ["body", "numero_rpc"], "msg": "Field required", "input": null}, {"type": "missing", "loc": ["body", "datos_actualizacion"], "msg": "Field required", "input": null}]`
- Recomendaciones:
  - Agregar ejemplos completos en Swagger/OpenAPI para evitar llamadas vacías (body/query/form).
  - Convertir validaciones de campos requeridos en mensajes de negocio más claros para frontend.
  - Evaluar valores por defecto en campos opcionales para reducir errores evitables.

## 22. PUT /emprestito/modificar-valores/contrato-secop/{referencia_contrato}

- Código observado: `422`
- Ruta probada: `/emprestito/modificar-valores/contrato-secop/CONT-TEST`
- Detalle: `[{"type": "missing", "loc": ["body", "change_motivo"], "msg": "Field required", "input": null}, {"type": "missing", "loc": ["body", "change_support_file"], "msg": "Field required", "input": null}]`
- Recomendaciones:
  - Agregar ejemplos completos en Swagger/OpenAPI para evitar llamadas vacías (body/query/form).
  - Convertir validaciones de campos requeridos en mensajes de negocio más claros para frontend.
  - Evaluar valores por defecto en campos opcionales para reducir errores evitables.

## 23. PUT /emprestito/modificar-valores/convenio/{referencia_contrato}

- Código observado: `422`
- Ruta probada: `/emprestito/modificar-valores/convenio/CONT-TEST`
- Detalle: `[{"type": "missing", "loc": ["body", "change_motivo"], "msg": "Field required", "input": null}, {"type": "missing", "loc": ["body", "change_support_file"], "msg": "Field required", "input": null}]`
- Recomendaciones:
  - Agregar ejemplos completos en Swagger/OpenAPI para evitar llamadas vacías (body/query/form).
  - Convertir validaciones de campos requeridos en mensajes de negocio más claros para frontend.
  - Evaluar valores por defecto en campos opcionales para reducir errores evitables.

## 24. PUT /emprestito/modificar-valores/orden-compra/{numero_orden}

- Código observado: `422`
- Ruta probada: `/emprestito/modificar-valores/orden-compra/OC-TEST`
- Detalle: `[{"type": "missing", "loc": ["body", "change_motivo"], "msg": "Field required", "input": null}, {"type": "missing", "loc": ["body", "change_support_file"], "msg": "Field required", "input": null}]`
- Recomendaciones:
  - Agregar ejemplos completos en Swagger/OpenAPI para evitar llamadas vacías (body/query/form).
  - Convertir validaciones de campos requeridos en mensajes de negocio más claros para frontend.
  - Evaluar valores por defecto en campos opcionales para reducir errores evitables.

## 25. PUT /emprestito/modificar-valores/proceso/{referencia_proceso}

- Código observado: `422`
- Ruta probada: `/emprestito/modificar-valores/proceso/PROC-TEST`
- Detalle: `[{"type": "missing", "loc": ["body", "change_motivo"], "msg": "Field required", "input": null}, {"type": "missing", "loc": ["body", "change_support_file"], "msg": "Field required", "input": null}]`
- Recomendaciones:
  - Agregar ejemplos completos en Swagger/OpenAPI para evitar llamadas vacías (body/query/form).
  - Convertir validaciones de campos requeridos en mensajes de negocio más claros para frontend.
  - Evaluar valores por defecto en campos opcionales para reducir errores evitables.

## 26. PUT /modificar/intervencion

- Código observado: `422`
- Ruta probada: `/modificar/intervencion`
- Detalle: `[{"type": "missing", "loc": ["body", "intervencion_id"], "msg": "Field required", "input": {}}, {"type": "missing", "loc": ["body", "aprobado"], "msg": "Field required", "input": {}}]`
- Recomendaciones:
  - Agregar ejemplos completos en Swagger/OpenAPI para evitar llamadas vacías (body/query/form).
  - Convertir validaciones de campos requeridos en mensajes de negocio más claros para frontend.
  - Evaluar valores por defecto en campos opcionales para reducir errores evitables.

## 27. PUT /modificar/unidad_proyecto

- Código observado: `422`
- Ruta probada: `/modificar/unidad_proyecto`
- Detalle: `[{"type": "missing", "loc": ["query", "upid"], "msg": "Field required", "input": null}, {"type": "missing", "loc": ["query", "aprobado"], "msg": "Field required", "input": null}, {"type": "missing", "loc": ["query", "extra_data_"], "msg": "Field required", "input": null}]`
- Recomendaciones:
  - Agregar ejemplos completos en Swagger/OpenAPI para evitar llamadas vacías (body/query/form).
  - Convertir validaciones de campos requeridos en mensajes de negocio más claros para frontend.
  - Evaluar valores por defecto en campos opcionales para reducir errores evitables.

## 28. POST /registrar_avance_up

- Código observado: `422`
- Ruta probada: `/registrar_avance_up`
- Detalle: `[{"type": "missing", "loc": ["body", "avance_obra"], "msg": "Field required", "input": null}, {"type": "missing", "loc": ["body", "observaciones"], "msg": "Field required", "input": null}, {"type": "missing", "loc": ["body", "intervencion_id"], "msg": "Field required", "input": null}, {"type": "missing", "loc": ["body", "registro_fotografico"], "msg": "Field required", "input": null}]`
- Recomendaciones:
  - Agregar ejemplos completos en Swagger/OpenAPI para evitar llamadas vacías (body/query/form).
  - Convertir validaciones de campos requeridos en mensajes de negocio más claros para frontend.
  - Evaluar valores por defecto en campos opcionales para reducir errores evitables.

## 29. POST /reportes_contratos/

- Código observado: `422`
- Ruta probada: `/reportes_contratos/`
- Detalle: `[{"type": "missing", "loc": ["body", "referencia_contrato"], "msg": "Field required", "input": null}, {"type": "missing", "loc": ["body", "observaciones"], "msg": "Field required", "input": null}, {"type": "missing", "loc": ["body", "avance_fisico"], "msg": "Field required", "input": null}, {"type": "missing", "loc": ["body", "avance_financiero"], "msg": "Field required", "input": null}, {"type": "missing", "loc": ["body", "alertas_descripcion"], "msg": "Field required", "input": null}, {"type": "missing", "loc": ["body", "alertas_es_alerta"], "msg": "Field required", "input": null}, {"type": "missing", "loc": ["body", "archivos_evidencia"], "msg": "Field required", "input": null}]`
- Recomendaciones:
  - Agregar ejemplos completos en Swagger/OpenAPI para evitar llamadas vacías (body/query/form).
  - Convertir validaciones de campos requeridos en mensajes de negocio más claros para frontend.
  - Evaluar valores por defecto en campos opcionales para reducir errores evitables.

## 30. GET /rpc_documentos_temporales

- Código observado: `422`
- Ruta probada: `/rpc_documentos_temporales`
- Detalle: `[{"type": "missing", "loc": ["query", "numero_rpc"], "msg": "Field required", "input": null}]`
- Recomendaciones:
  - Agregar ejemplos completos en Swagger/OpenAPI para evitar llamadas vacías (body/query/form).
  - Convertir validaciones de campos requeridos en mensajes de negocio más claros para frontend.
  - Evaluar valores por defecto en campos opcionales para reducir errores evitables.

## 31. POST /emprestito/crear-tabla-proyecciones

- Código observado: `500`
- Ruta probada: `/emprestito/crear-tabla-proyecciones`
- Detalle: `Error creando tabla de proyecciones: No se encontró el Google Sheets con ID: 11-sdLwINHHwRit8b9jnnXcO2phhuEVUpXM6q6yv8DYo. Verifica que el service account firebase-adminsdk-fbsvc@calitrack-44403.iam.gserviceaccount.com tenga acceso al documento.`
- Recomendaciones:
  - Validar conectividad/permisos al Google Sheet en startup y fallar rápido con diagnóstico accionable.
  - Mover IDs sensibles de documentos a variables de entorno y validar su existencia en health checks.

## 32. GET /emprestito/historial-cambios

- Código observado: `500`
- Ruta probada: `/emprestito/historial-cambios`
- Detalle: `{"success": false, "error": "Firebase no disponible"}`
- Recomendaciones:
  - Revisar manejo de errores para separar fallas de validación (4xx) de fallas internas (5xx).
  - Añadir pruebas de integración para este caso de error y su mensaje esperado.

## 33. DELETE /emprestito/proceso/{referencia_proceso}

- Código observado: `500`
- Ruta probada: `/emprestito/proceso/PROC-TEST`
- Detalle: `{"success": false, "error": "Función no implementada temporalmente"}`
- Recomendaciones:
  - Retirar temporalmente el endpoint de OpenAPI o cambiarlo a 501 Not Implemented con contrato explícito.
  - Agregar ticket técnico y fecha objetivo para implementación o deprecación definitiva.

## 34. GET /firebase/collections/summary

- Código observado: `500`
- Ruta probada: `/firebase/collections/summary`
- Detalle: `Error obteniendo resumen: Error obteniendo resumen: unsupported operand type(s) for +: 'int' and 'str'`
- Recomendaciones:
  - Normalizar tipos antes de agregaciones (cast de strings numéricos a int/float, manejo de null).
  - Agregar validaciones defensivas por documento para aislar registros corruptos sin romper todo el endpoint.

## 35. GET /reportes_contratos/centro_gestor/{nombre_centro_gestor}

- Código observado: `500`
- Ruta probada: `/reportes_contratos/centro_gestor/test`
- Detalle: `Error obteniendo reportes: Error obteniendo reportes: 400 The query requires an index. You can create it here: https://console.firebase.google.com/v1/r/project/calitrack-44403/firestore/indexes?create_composite=Clpwcm9qZWN0cy9jYWxpdHJhY2stNDQ0MDMvZGF0YWJhc2VzLyhkZWZhdWx0KS9jb2xsZWN0aW9uR3JvdXBzL3JlcG9ydGVzX2NvbnRyYXRvcy9pbmRleGVzL18QARoYChRub21icmVfY2VudHJvX2dlc3RvchABGhEKDWZlY2hhX3JlcG9ydGUQAhoMCghfX25hbWVfXxAC`
- Recomendaciones:
  - Crear el índice compuesto faltante en Firestore y versionarlo en firestore.indexes.json.
  - Agregar fallback de consulta o mensaje operativo claro cuando el índice no exista.

## 36. GET /metrics

- Código observado: `503`
- Ruta probada: `/metrics`
- Detalle: `Prometheus metrics not available`
- Recomendaciones:
  - Si Prometheus está deshabilitado por entorno, ocultar la ruta o responder 200 con estado 'disabled'.
  - Agregar feature-flag de observabilidad para evitar alertas falsas en monitores externos.

# Resumen de Campos Disponibles en Endpoints PUT de Empréstito

## 📋 Descripción General

Los tres endpoints PUT han sido actualizados para incluir **exactamente los campos que existen en cada colección de Firebase**. Cada campo está disponible como parámetro Query en Swagger UI, facilitando las pruebas sin necesidad de construir JSON complejo.

---

## 1️⃣ `/emprestito/modificar-orden-compra`

**Colección:** `ordenes_compra_emprestito` (35 campos)
**Identificador:** `numero_orden` (REQUERIDO)

### Parámetros Query disponibles:

| Campo                        | Tipo   | Obligatorio | Descripción                      |
| ---------------------------- | ------ | ----------- | -------------------------------- |
| `numero_orden`               | string | ✅ SÍ       | Número de orden a modificar      |
| `ano_orden`                  | int    | ❌          | Año de la orden                  |
| `bp`                         | string | ❌          | BP                               |
| `bpin`                       | string | ❌          | BPIN                             |
| `estado`                     | string | ❌          | Estado de la orden               |
| `estado_orden`               | string | ❌          | Estado de la orden (alternativo) |
| `fecha_actualizacion`        | string | ❌          | Fecha de actualización           |
| `fecha_creacion`             | string | ❌          | Fecha de creación                |
| `fecha_enriquecimiento_tvec` | string | ❌          | Fecha de enriquecimiento TVEC    |
| `fecha_guardado`             | string | ❌          | Fecha de guardado                |
| `fecha_publicacion_orden`    | string | ❌          | Fecha de publicación de la orden |
| `fecha_vencimiento_orden`    | string | ❌          | Fecha de vencimiento de la orden |
| `fuente_datos`               | string | ❌          | Fuente de datos                  |
| `items`                      | string | ❌          | Items (JSON array como string)   |
| `modalidad_contratacion`     | string | ❌          | Modalidad de contratación        |
| `nit_entidad`                | string | ❌          | NIT de la entidad                |
| `nit_proveedor`              | string | ❌          | NIT del proveedor                |
| `nombre_banco`               | string | ❌          | Nombre del banco                 |
| `nombre_centro_gestor`       | string | ❌          | Nombre del centro gestor         |
| `nombre_proveedor`           | string | ❌          | Nombre del proveedor             |
| `nombre_resumido_proceso`    | string | ❌          | Nombre resumido del proceso      |
| `objeto_orden`               | string | ❌          | Objeto de la orden               |
| `observaciones`              | string | ❌          | Observaciones sobre la orden     |
| `ordenador_gasto`            | string | ❌          | Ordenador de gasto               |
| `plataforma_origen`          | string | ❌          | Plataforma de origen             |
| `rama_entidad`               | string | ❌          | Rama de la entidad               |
| `sector`                     | string | ❌          | Sector                           |
| `solicitante`                | string | ❌          | Solicitante                      |
| `solicitud_id`               | string | ❌          | ID de solicitud                  |
| `tipo`                       | string | ❌          | Tipo                             |
| `tipo_documento`             | string | ❌          | Tipo de documento                |
| `valor_orden`                | float  | ❌          | Valor de la orden                |
| `valor_proyectado`           | float  | ❌          | Valor proyectado                 |
| `datos_json`                 | string | ❌          | JSON con campos adicionales      |

### Ejemplo de uso en Swagger:

```
numero_orden: 152488
estado: completado
valor_orden: 5000000
modalidad_contratacion: licitación pública
```

---

## 2️⃣ `/emprestito/modificar-proceso`

**Colección:** `procesos_emprestito` (38 campos)
**Identificador:** `referencia_proceso` (REQUERIDO)

### Parámetros Query disponibles:

| Campo                          | Tipo   | Obligatorio | Descripción                        |
| ------------------------------ | ------ | ----------- | ---------------------------------- |
| `referencia_proceso`           | string | ✅ SÍ       | Referencia del proceso a modificar |
| `adjudicado`                   | string | ❌          | Adjudicado                         |
| `bp`                           | string | ❌          | BP                                 |
| `conteo_respuestas_ofertas`    | int    | ❌          | Conteo de respuestas de ofertas    |
| `descripcion_proceso`          | string | ❌          | Descripción del proceso            |
| `duracion`                     | int    | ❌          | Duración                           |
| `estado_proceso`               | string | ❌          | Estado del proceso                 |
| `estado_resumen`               | string | ❌          | Estado resumen                     |
| `fase`                         | string | ❌          | Fase                               |
| `fecha_actualizacion`          | string | ❌          | Fecha de actualización             |
| `fecha_actualizacion_completa` | string | ❌          | Fecha de actualización completa    |
| `fecha_creacion`               | string | ❌          | Fecha de creación                  |
| `fecha_publicacion`            | string | ❌          | Fecha de publicación               |
| `fecha_publicacion_fase`       | string | ❌          | Fecha de publicación fase          |
| `fecha_publicacion_fase_3`     | string | ❌          | Fecha de publicación fase 3        |
| `id_paa`                       | string | ❌          | ID PAA                             |
| `modalidad_contratacion`       | string | ❌          | Modalidad de contratación          |
| `nombre_banco`                 | string | ❌          | Nombre del banco                   |
| `nombre_centro_gestor`         | string | ❌          | Nombre del centro gestor           |
| `nombre_proceso`               | string | ❌          | Nombre del proceso                 |
| `nombre_resumido_proceso`      | string | ❌          | Nombre resumido del proceso        |
| `nombre_unidad`                | string | ❌          | Nombre de unidad                   |
| `numero_lotes`                 | int    | ❌          | Número de lotes                    |
| `observaciones_test`           | string | ❌          | Observaciones test                 |
| `plataforma`                   | string | ❌          | Plataforma                         |
| `proceso_contractual`          | string | ❌          | Proceso contractual                |
| `proveedores_con_invitacion`   | string | ❌          | Proveedores con invitación         |
| `proveedores_invitados`        | string | ❌          | Proveedores invitados              |
| `proveedores_que_manifestaron` | string | ❌          | Proveedores que manifestaron       |
| `respuestas_externas`          | string | ❌          | Respuestas externas                |
| `respuestas_procedimiento`     | string | ❌          | Respuestas procedimiento           |
| `tipo_contrato`                | string | ❌          | Tipo de contrato                   |
| `unidad_duracion`              | string | ❌          | Unidad de duración                 |
| `urlproceso`                   | string | ❌          | URL del proceso                    |
| `valor_proyectado`             | float  | ❌          | Valor proyectado                   |
| `valor_publicacion`            | float  | ❌          | Valor de publicación               |
| `visualizaciones_proceso`      | int    | ❌          | Visualizaciones del proceso        |
| `datos_json`                   | string | ❌          | JSON con campos adicionales        |

### Ejemplo de uso en Swagger:

```
referencia_proceso: 4162.010.32.1.1058-2025
estado_proceso: ejecutado
valor_proyectado: 25000000
fase: licitación
```

---

## 3️⃣ `/emprestito/modificar-contrato`

**Colección:** `contratos_emprestito` (35 campos)
**Identificador:** `referencia_contrato` (REQUERIDO)

### Parámetros Query disponibles:

| Campo                    | Tipo   | Obligatorio | Descripción                         |
| ------------------------ | ------ | ----------- | ----------------------------------- |
| `referencia_contrato`    | string | ✅ SÍ       | Referencia del contrato a modificar |
| `_dataset_source`        | string | ❌          | Fuente del dataset                  |
| `banco`                  | string | ❌          | Banco                               |
| `bp`                     | string | ❌          | BP                                  |
| `bpin`                   | string | ❌          | BPIN                                |
| `descripcion_proceso`    | string | ❌          | Descripción del proceso             |
| `entidad_contratante`    | string | ❌          | Entidad contratante                 |
| `estado_contrato`        | string | ❌          | Estado del contrato                 |
| `fecha_actualizacion`    | string | ❌          | Fecha de actualización              |
| `fecha_fin_contrato`     | string | ❌          | Fecha de fin del contrato           |
| `fecha_firma_contrato`   | string | ❌          | Fecha de firma del contrato         |
| `fecha_guardado`         | string | ❌          | Fecha de guardado                   |
| `fecha_inicio_contrato`  | string | ❌          | Fecha de inicio del contrato        |
| `fuente_datos`           | string | ❌          | Fuente de datos                     |
| `id_contrato`            | string | ❌          | ID del contrato                     |
| `modalidad_contratacion` | string | ❌          | Modalidad de contratación           |
| `nit_contratista`        | string | ❌          | NIT del contratista                 |
| `nit_entidad`            | string | ❌          | NIT de la entidad                   |
| `nombre_centro_gestor`   | string | ❌          | Nombre del centro gestor            |
| `nombre_contratista`     | string | ❌          | Nombre del contratista              |
| `nombre_procedimiento`   | string | ❌          | Nombre del procedimiento            |
| `objeto_contrato`        | string | ❌          | Objeto del contrato                 |
| `observaciones_test`     | string | ❌          | Observaciones test                  |
| `ordenador_gasto`        | string | ❌          | Ordenador de gasto                  |
| `proceso_contractual`    | string | ❌          | Proceso contractual                 |
| `referencia_proceso`     | string | ❌          | Referencia del proceso              |
| `representante_legal`    | string | ❌          | Representante legal                 |
| `sector`                 | string | ❌          | Sector                              |
| `supervisor`             | string | ❌          | Supervisor                          |
| `tipo_contrato`          | string | ❌          | Tipo de contrato                    |
| `urlproceso`             | string | ❌          | URL del proceso                     |
| `valor_contrato`         | float  | ❌          | Valor del contrato                  |
| `valor_pagado`           | float  | ❌          | Valor pagado                        |
| `version_esquema`        | string | ❌          | Versión del esquema                 |
| `datos_json`             | string | ❌          | JSON con campos adicionales         |

### Ejemplo de uso en Swagger:

```
referencia_contrato: 4134.010.26.1.0577-2025
estado_contrato: vigente
valor_contrato: 50000000
nombre_contratista: Empresa S.A.
```

---

## ✅ Características Comunes a los Tres Endpoints

✅ **Actualización selectiva**: Solo se modifican los campos especificados
✅ **Preservación de datos**: Los campos no incluidos mantienen sus valores originales
✅ **Identificación única**: Se busca por el campo identificador específico de cada colección
✅ **Validación**: Verifica que el registro exista antes de actualizar
✅ **Flexibilidad**: Parámetro `datos_json` para campos adicionales no listados explícitamente
✅ **Respuestas claras**: Incluyen lista de campos actualizados y timestamp
✅ **Integración Swagger**: Todos los parámetros aparecen como textbox en la interfaz

---

## 📌 Notas Importantes

1. **Parámetro `datos_json`**: Para campos adicionales o no listados, envía un JSON válido

   Ejemplo:

   ```
   datos_json: {"campo_personalizado": "valor", "otro_campo": 123}
   ```

2. **Tipos de datos**:
   - `string`: Texto libre
   - `int`: Números enteros
   - `float`: Números decimales
   - Fechas: Formato ISO 8601 (YYYY-MM-DD o YYYY-MM-DDTHH:MM:SS)

3. **Campos obligatorios**: Solo el identificador (`numero_orden`, `referencia_proceso`, `referencia_contrato`)

4. **Validación**: Si no se envía al menos un parámetro adicional, el endpoint retorna error 400

---

## 🔗 Acceder a Swagger UI

Visita `http://localhost:8000/docs` para probar los endpoints interactivamente con todos los parámetros disponibles.

---

**Última actualización:** 20 de Enero de 2026
**Estado:** ✅ Todos los endpoints funcionando con campos de Firebase

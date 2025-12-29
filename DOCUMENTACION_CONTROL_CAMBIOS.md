# 📋 Sistema de Control de Cambios y Auditoría para Empréstito

## 🎯 Descripción General

Se ha implementado un sistema completo de control de cambios y auditoría para los endpoints de modificación de valores en las colecciones de empréstito. Cada cambio realizado se registra automáticamente en una nueva colección de Firebase llamada `emprestito_control_cambios` con toda la información de trazabilidad.

---

## 🆕 Colección de Auditoría: `emprestito_control_cambios`

### Estructura de Datos:

```javascript
{
  // Identificación del cambio
  "change_id": "uuid-único",                    // ID único para cada cambio
  "change_timestamp": "2025-12-28T10:30:00",   // Timestamp del cambio

  // Justificación y soporte
  "change_motivo": "Texto justificando el cambio",
  "change_support_file": "https://s3.../documento.pdf",  // URL del documento en S3
  "support_file_name": "documento_soporte.pdf",
  "support_file_size": 102400,                  // Tamaño en bytes
  "support_file_type": ".pdf",

  // Información del cambio
  "tipo_coleccion": "contratos",               // procesos, ordenes, convenios, contratos
  "identificador": "CONT-2024-001",            // ID del documento modificado
  "campo_modificado": "valor_contrato",        // Campo que se modificó

  // Valores
  "valor_anterior": 1000000.0,
  "valor_nuevo": 1500000.0,
  "diferencia": 500000.0,                      // valor_nuevo - valor_anterior

  // Metadata
  "usuario": "Sistema",                         // Usuario que realizó el cambio
  "endpoint_usado": "/emprestito/modificar-valores/contrato-secop"
}
```

---

## 📂 Archivos Creados/Modificados

### 1. **Nuevo Archivo**: `api/scripts/control_cambios_emprestito.py`

Módulo dedicado al control de cambios con las siguientes funciones:

#### `registrar_cambio_valor()`

- Registra cada cambio en Firebase
- Sube documento soporte a S3 si se proporciona
- Genera ID único (UUID) para cada cambio
- Calcula diferencia entre valores
- Valida tipos de archivo permitidos

#### `_subir_archivo_soporte_s3()`

- Sube archivos a S3 con estructura organizada
- Valida tipo de archivo (PDF, XLSX, DOCX, PNG, JPG)
- Limita tamaño máximo a 10 MB
- Genera URLs accesibles

#### `obtener_historial_cambios()`

- Consulta historial de cambios
- Permite filtros por tipo y identificador
- Ordena por timestamp descendente
- Limita número de resultados

### Estructura en S3:

```
contratos-emprestito/
└── control-cambios-docs/
    ├── procesos/
    │   └── {referencia_proceso}/
    │       └── {change_id}_{filename}
    ├── ordenes/
    │   └── {numero_orden}/
    │       └── {change_id}_{filename}
    ├── convenios/
    │   └── {referencia_contrato}/
    │       └── {change_id}_{filename}
    └── contratos/
        └── {referencia_contrato}/
            └── {change_id}_{filename}
```

---

### 2. **Modificado**: `api/scripts/__init__.py`

Agregadas exportaciones:

```python
from .control_cambios_emprestito import (
    registrar_cambio_valor,
    obtener_historial_cambios
)
```

---

### 3. **Modificado**: `main.py`

#### Importaciones actualizadas:

- Agregadas funciones de control de cambios en ambas secciones de imports

#### Endpoints PUT actualizados (4 endpoints):

**Nuevos parámetros Form agregados a todos los endpoints:**

```python
change_motivo: str = Form(..., description="Justificación del cambio (obligatorio)")
change_support_file: Optional[UploadFile] = File(None, description="Documento soporte (PDF, XLSX, DOCX, etc.)")
```

**Lógica de auditoría agregada después de cada actualización exitosa:**

```python
# Registrar en auditoría
auditoria_resultado = await registrar_cambio_valor(
    tipo_coleccion="...",
    identificador="...",
    campo_modificado="...",
    valor_anterior=...,
    valor_nuevo=...,
    motivo=change_motivo,
    archivo_soporte=change_support_file,
    usuario=None,
    endpoint_usado="..."
)

# Agregar info de auditoría a respuesta
resultado["auditoria"] = auditoria_resultado
```

#### Endpoints Actualizados:

1. **PUT** `/emprestito/modificar-valores/proceso/{referencia_proceso}`

   - Colección: `procesos_emprestito`
   - Campo: `valor_publicacion`
   - Tipo colección auditoría: `"procesos"`

2. **PUT** `/emprestito/modificar-valores/orden-compra/{numero_orden}`

   - Colección: `ordenes_compra_emprestito`
   - Campos: `valor_orden`, `valor_proyectado`
   - Tipo colección auditoría: `"ordenes"`

3. **PUT** `/emprestito/modificar-valores/convenio/{referencia_contrato}`

   - Colección: `convenios_transferencias_emprestito`
   - Campo: `valor_contrato`
   - Tipo colección auditoría: `"convenios"`

4. **PUT** `/emprestito/modificar-valores/contrato-secop/{referencia_contrato}`
   - Colección: `contratos_emprestito`
   - Campo: `valor_contrato`
   - Tipo colección auditoría: `"contratos"`

#### Nuevo Endpoint de Consulta:

**GET** `/emprestito/historial-cambios`

Parámetros Query:

- `tipo_coleccion` (opcional): Filtrar por tipo (procesos, ordenes, convenios, contratos)
- `identificador` (opcional): Filtrar por ID específico
- `limite` (opcional): Número máximo de registros (1-200, default: 50)

Respuesta:

```json
{
  "success": true,
  "total_cambios": 15,
  "cambios": [...]
}
```

---

### 4. **Nuevo Archivo**: `test_modificar_valores_control_cambios.py`

Suite completa de pruebas que incluye:

#### Tests Implementados:

1. **Test Proceso SECOP**

   - Verifica endpoint con documento PDF de prueba
   - Valida registro de auditoría
   - Usa datos ficticios (no modifica datos reales)

2. **Test Orden de Compra**

   - Prueba modificación de múltiples valores
   - Verifica valor_orden y valor_proyectado
   - Valida auditoría

3. **Test Convenio**

   - Prueba modificación de valor_contrato
   - Verifica auditoría

4. **Test Contrato SECOP**

   - Prueba modificación de valor_contrato
   - Verifica auditoría

5. **Test Historial de Cambios**

   - Consulta sin filtros
   - Consulta con filtro por tipo
   - Verifica estructura de respuesta

6. **Test Validaciones**
   - Valida que rechace request sin `change_motivo`
   - Valida que rechace request sin valor
   - Verifica códigos de error correctos

#### Características del Test:

- Output con colores para fácil lectura
- Usa datos ficticios para evitar modificar datos reales
- Genera PDF de prueba temporal (requiere `reportlab`)
- Limpia archivos temporales automáticamente
- Verifica conectividad con el servidor antes de tests

---

## 🔒 Validaciones Implementadas

### En Endpoints PUT:

1. **Parámetro `change_motivo`**:

   - ✅ **Obligatorio** en todos los endpoints
   - ✅ Tipo: `str`
   - ✅ FastAPI Form con `...` (required)

2. **Parámetro `change_support_file`**:

   - ✅ **Opcional** en todos los endpoints
   - ✅ Tipo: `UploadFile`
   - ✅ Tipos permitidos: PDF, XLSX, XLS, DOCX, DOC, PNG, JPG, JPEG
   - ✅ Tamaño máximo: 10 MB

3. **Valores numéricos**:
   - ✅ Conversión automática a `float()`
   - ✅ Validación de valores requeridos

### En Función de Auditoría:

1. **Archivo soporte**:

   - ✅ Validación de extensión
   - ✅ Validación de tamaño (máx 10 MB)
   - ✅ Sanitización de nombre de archivo
   - ✅ Metadata en objeto S3

2. **Registro en Firebase**:
   - ✅ Generación de UUID único
   - ✅ Timestamp automático
   - ✅ Cálculo de diferencia entre valores
   - ✅ Manejo de errores sin afectar actualización principal

---

## 📊 Respuesta de Endpoints

### Estructura de Respuesta Exitosa:

```json
{
  "success": true,
  "message": "Proceso SECOP actualizado exitosamente",
  "referencia_proceso": "SCMGSU-CM-003-2024",
  "coleccion": "procesos_emprestito",
  "documento_id": "xyz123",
  "campos_modificados": ["valor_publicacion"],
  "valores_anteriores": {
    "valor_publicacion": 1000000.0
  },
  "valores_nuevos": {
    "valor_publicacion": 1500000.0
  },
  "timestamp": "2025-12-28T10:30:00",

  // Nueva sección de auditoría
  "auditoria": {
    "success": true,
    "message": "Cambio registrado exitosamente en auditoría",
    "change_id": "uuid-123-456",
    "change_timestamp": "2025-12-28T10:30:00",
    "cambio_registrado": {
      "change_id": "uuid-123-456",
      "change_timestamp": "2025-12-28T10:30:00",
      "change_motivo": "Ajuste por modificación contractual",
      "change_support_file": "https://contratos-emprestito.s3.us-east-1.amazonaws.com/...",
      "support_file_name": "documento_soporte.pdf",
      "support_file_size": 102400,
      "support_file_type": ".pdf",
      "tipo_coleccion": "procesos",
      "identificador": "SCMGSU-CM-003-2024",
      "campo_modificado": "valor_publicacion",
      "valor_anterior": 1000000.0,
      "valor_nuevo": 1500000.0,
      "diferencia": 500000.0,
      "usuario": "Sistema",
      "endpoint_usado": "/emprestito/modificar-valores/proceso"
    }
  }
}
```

### Si Auditoría Falla (no afecta la actualización):

```json
{
  // ... datos de actualización exitosa ...
  "auditoria": {
    "success": false,
    "error": "Mensaje de error"
  },
  "auditoria_warning": "Cambio realizado pero no se pudo registrar en auditoría"
}
```

---

## 🧪 Cómo Ejecutar los Tests

### 1. Asegúrate de que el servidor está corriendo:

```bash
uvicorn main:app --reload
```

### 2. (Opcional) Instala reportlab para tests completos:

```bash
pip install reportlab
```

### 3. Ejecuta la suite de tests:

```bash
python test_modificar_valores_control_cambios.py
```

### Salida Esperada:

```
================================================================================
        🧪 SUITE DE PRUEBAS: ENDPOINTS DE MODIFICACIÓN DE VALORES
================================================================================

ℹ️  Verificando funcionalidad de control de cambios y auditoría
ℹ️  API Base URL: http://localhost:8000
ℹ️  Fecha: 2025-12-28 10:30:00
✅ ✓ Servidor API está corriendo en http://localhost:8000

================================================================================
                 TEST 1: Modificar Valor de Proceso SECOP
================================================================================

ℹ️  URL: http://localhost:8000/emprestito/modificar-valores/proceso/SCMGSU-TEST-001-2025
...
```

---

## 📝 Uso en Producción

### Ejemplo con cURL:

```bash
# Modificar valor de proceso SECOP
curl -X PUT "http://localhost:8000/emprestito/modificar-valores/proceso/SCMGSU-CM-003-2024" \
  -F "valor_publicacion=5000000.0" \
  -F "change_motivo=Ajuste por modificación contractual según acta 123" \
  -F "change_support_file=@/path/to/documento_soporte.pdf"

# Consultar historial de cambios
curl -X GET "http://localhost:8000/emprestito/historial-cambios?limite=10"

# Consultar cambios de un contrato específico
curl -X GET "http://localhost:8000/emprestito/historial-cambios?tipo_coleccion=contratos&identificador=CONT-2024-001"
```

### Ejemplo con Python:

```python
import requests

# Modificar valor
url = "http://localhost:8000/emprestito/modificar-valores/contrato-secop/CONT-2024-001"
form_data = {
    "valor_contrato": 4000000.0,
    "change_motivo": "Ajuste por adición al contrato"
}
files = {
    "change_support_file": open("documento_soporte.pdf", "rb")
}

response = requests.put(url, data=form_data, files=files)
print(response.json())

# Consultar historial
url = "http://localhost:8000/emprestito/historial-cambios"
params = {"tipo_coleccion": "contratos", "limite": 20}
response = requests.get(url, params=params)
print(response.json())
```

---

## ✅ Características Implementadas

- ✅ 4 endpoints PUT con auditoría completa
- ✅ Registro automático en Firebase (`emprestito_control_cambios`)
- ✅ Carga de documentos soporte a S3
- ✅ Validación de tipos de archivo
- ✅ Validación de tamaño de archivo (máx 10 MB)
- ✅ Generación de UUID único por cambio
- ✅ Cálculo automático de diferencias
- ✅ Endpoint de consulta de historial con filtros
- ✅ Manejo de errores sin afectar actualización principal
- ✅ Suite completa de tests
- ✅ Documentación en código (docstrings)
- ✅ Estructura organizada en S3
- ✅ Metadata en objetos S3

---

## 🔐 Seguridad y Buenas Prácticas

1. **Trazabilidad completa**: Cada cambio tiene ID único y timestamp
2. **Documento soporte**: Opción de adjuntar evidencia
3. **Justificación obligatoria**: Campo `change_motivo` requerido
4. **Persistencia en S3**: Documentos almacenados de forma permanente
5. **Estructura organizada**: Archivos clasificados por tipo y identificador
6. **No afecta operación**: Si auditoría falla, actualización sigue siendo exitosa
7. **Validación de archivos**: Solo tipos permitidos, tamaño máximo
8. **Sanitización**: Nombres de archivo sanitizados para seguridad

---

## 📚 Próximos Pasos Recomendados

1. ✅ Ejecutar suite de tests
2. ⏳ Validar con datos reales en ambiente de pruebas
3. ⏳ Integrar con sistema de autenticación (campo `usuario`)
4. ⏳ Implementar notificaciones (email/Slack) para cambios críticos
5. ⏳ Crear dashboard de visualización de cambios
6. ⏳ Implementar permisos por rol para endpoints
7. ⏳ Agregar filtros adicionales en historial (fecha, usuario, rango de valores)
8. ⏳ Implementar exportación de historial a Excel/PDF

---

## 📞 Soporte

Para preguntas o problemas:

- Verificar logs del servidor para errores
- Revisar colección `emprestito_control_cambios` en Firebase
- Verificar bucket S3 `contratos-emprestito/control-cambios-docs/`
- Ejecutar tests para validar funcionalidad

---

**Fecha de implementación**: 2025-12-28  
**Versión**: 1.0.0  
**Estado**: ✅ Completado y listo para pruebas

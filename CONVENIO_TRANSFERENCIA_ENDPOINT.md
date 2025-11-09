# Endpoint de Convenios de Transferencia - Empréstito

## 📝 Resumen de Implementación

Se ha creado exitosamente el endpoint POST para cargar convenios de transferencia en la gestión de empréstito.

## 🎯 Endpoint Creado

**POST** `/emprestito/cargar-convenio-transferencia`

**Tag:** "Gestión de Empréstito"

**Colección Firebase:** `convenios_transferencias_emprestito`

## 📋 Parámetros

### Obligatorios

- `referencia_contrato`: Referencia única del contrato/convenio
- `nombre_centro_gestor`: Centro gestor responsable
- `banco`: Nombre del banco
- `objeto_contrato`: Descripción del objeto del contrato
- `valor_contrato`: Valor del contrato en pesos colombianos

### Opcionales

- `bp`: Código BP
- `bpin`: Código BPIN (Banco de Programas y Proyectos de Inversión Nacional)
- `valor_convenio`: Valor específico del convenio
- `urlproceso`: URL del proceso de contratación
- `fecha_inicio_contrato`: Fecha de inicio del contrato
- `fecha_fin_contrato`: Fecha de finalización del contrato
- `modalidad_contrato`: Modalidad de contratación
- `ordenador_gastor`: Ordenador del gasto
- `tipo_contrato`: Tipo de contrato
- `estado_contrato`: Estado actual del contrato
- `sector`: Sector al que pertenece

## 🔧 Archivos Modificados

1. **api/scripts/emprestito_operations.py**

   - ✅ Agregada función `cargar_convenio_transferencia()`
   - Validación de campos obligatorios
   - Validación de duplicados por `referencia_contrato`
   - Creación de documento en Firestore

2. **api/scripts/**init**.py**

   - ✅ Exportada función `cargar_convenio_transferencia`
   - ✅ Agregada función dummy para caso sin Firebase

3. **main.py**

   - ✅ Importada función `cargar_convenio_transferencia`
   - ✅ Creado endpoint POST `/emprestito/cargar-convenio-transferencia`
   - Documentación completa con ejemplos
   - Manejo de errores y respuestas HTTP

4. **test_convenio_transferencia.py** (NUEVO)
   - ✅ Script de prueba del endpoint
   - Prueba de creación básica
   - Prueba de validación de duplicados
   - Prueba de validación de campos obligatorios

## ✨ Características Implementadas

### Validaciones

- ✅ Validación de campos obligatorios
- ✅ Validación de duplicados por `referencia_contrato`
- ✅ Validación de disponibilidad de Firebase

### Respuestas HTTP

- ✅ **201 Created**: Convenio creado exitosamente
- ✅ **409 Conflict**: Convenio duplicado
- ✅ **400 Bad Request**: Error en validación de campos
- ✅ **500 Internal Server Error**: Error del servidor

### Datos Guardados

```json
{
  "referencia_contrato": "string",
  "nombre_centro_gestor": "string",
  "bp": "string | null",
  "bpin": "string | null",
  "objeto_contrato": "string",
  "valor_contrato": "number",
  "valor_convenio": "number | null",
  "urlproceso": "string | null",
  "banco": "string",
  "fecha_inicio_contrato": "string | null",
  "fecha_fin_contrato": "string | null",
  "modalidad_contrato": "string | null",
  "ordenador_gastor": "string | null",
  "tipo_contrato": "string | null",
  "estado_contrato": "string | null",
  "sector": "string | null",
  "fecha_creacion": "datetime",
  "fecha_actualizacion": "datetime",
  "estado": "activo",
  "tipo": "convenio_transferencia_manual"
}
```

## 🧪 Pruebas

### Ejecutar el script de prueba:

```bash
python test_convenio_transferencia.py
```

### Ejemplo con curl:

```bash
curl -X POST "http://localhost:8000/emprestito/cargar-convenio-transferencia" \
  -F "referencia_contrato=CONV-TEST-001-2024" \
  -F "nombre_centro_gestor=Secretaría de Salud" \
  -F "banco=Banco Mundial" \
  -F "objeto_contrato=Convenio de transferencia para equipamiento médico" \
  -F "valor_contrato=1500000000" \
  -F "bp=BP-2024-001" \
  -F "bpin=2024000010001" \
  -F "valor_convenio=1200000000" \
  -F "modalidad_contrato=Convenio de Transferencia" \
  -F "estado_contrato=Activo"
```

### Ejemplo con Python requests:

```python
import requests

datos = {
    "referencia_contrato": "CONV-TEST-001-2024",
    "nombre_centro_gestor": "Secretaría de Salud",
    "banco": "Banco Mundial",
    "objeto_contrato": "Convenio de transferencia para equipamiento médico",
    "valor_contrato": 1500000000.0,
    "bp": "BP-2024-001",
    "bpin": "2024000010001",
    "valor_convenio": 1200000000.0,
    "modalidad_contrato": "Convenio de Transferencia",
    "estado_contrato": "Activo"
}

response = requests.post(
    "http://localhost:8000/emprestito/cargar-convenio-transferencia",
    data=datos
)

print(response.json())
```

## 📊 Documentación Swagger

Una vez que el servidor esté corriendo, puedes acceder a la documentación interactiva en:

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

Busca el endpoint en la sección **"Gestión de Empréstito"** con el nombre:
**"🟢 Cargar Convenio de Transferencia"**

## ✅ Estado

- [x] Función auxiliar creada
- [x] Función exportada correctamente
- [x] Endpoint implementado
- [x] Documentación completa
- [x] Manejo de errores
- [x] Script de prueba creado
- [x] Sin errores de sintaxis

## 🚀 Siguiente Paso

Para probar el endpoint:

1. Asegúrate de que el servidor esté corriendo:

   ```bash
   uvicorn main:app --reload
   ```

2. Ejecuta el script de prueba:

   ```bash
   python test_convenio_transferencia.py
   ```

3. O accede a la documentación Swagger en http://localhost:8000/docs

---

**Implementado el:** 9 de noviembre de 2025

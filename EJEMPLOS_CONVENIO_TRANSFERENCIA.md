# Ejemplos de Uso - Endpoint Convenios de Transferencia

## 📚 Casos de Uso Comunes

### 1. Crear un Convenio Básico (Solo campos obligatorios)

```bash
curl -X POST "http://localhost:8000/emprestito/cargar-convenio-transferencia" \
  -F "referencia_contrato=CONV-SALUD-001-2024" \
  -F "nombre_centro_gestor=Secretaría de Salud" \
  -F "banco=Banco Mundial" \
  -F "objeto_contrato=Adquisición de equipos médicos especializados" \
  -F "valor_contrato=2500000000"
```

**Respuesta esperada (201):**

```json
{
  "success": true,
  "message": "Convenio de transferencia CONV-SALUD-001-2024 guardado exitosamente",
  "doc_id": "abc123xyz",
  "data": {
    "referencia_contrato": "CONV-SALUD-001-2024",
    "nombre_centro_gestor": "Secretaría de Salud",
    "banco": "Banco Mundial",
    "objeto_contrato": "Adquisición de equipos médicos especializados",
    "valor_contrato": 2500000000,
    "fecha_creacion": "2024-11-09T...",
    "estado": "activo"
  },
  "coleccion": "convenios_transferencias_emprestito",
  "timestamp": "2024-11-09T..."
}
```

---

### 2. Crear un Convenio Completo (Todos los campos)

```bash
curl -X POST "http://localhost:8000/emprestito/cargar-convenio-transferencia" \
  -F "referencia_contrato=CONV-EDUC-002-2024" \
  -F "nombre_centro_gestor=Secretaría de Educación" \
  -F "banco=Banco Interamericano de Desarrollo" \
  -F "objeto_contrato=Modernización de infraestructura educativa" \
  -F "valor_contrato=5000000000" \
  -F "bp=BP-EDU-2024-02" \
  -F "bpin=2024000020001" \
  -F "valor_convenio=4500000000" \
  -F "urlproceso=https://www.contratos.gov.co/proceso/12345" \
  -F "fecha_inicio_contrato=2024-03-01" \
  -F "fecha_fin_contrato=2025-12-31" \
  -F "modalidad_contrato=Convenio Interadministrativo" \
  -F "ordenador_gastor=María González López" \
  -F "tipo_contrato=Obra Pública" \
  -F "estado_contrato=En Ejecución" \
  -F "sector=Educación"
```

---

### 3. Python - Crear Convenio

```python
import requests
import json

url = "http://localhost:8000/emprestito/cargar-convenio-transferencia"

# Datos del convenio
datos = {
    "referencia_contrato": "CONV-INFRA-003-2024",
    "nombre_centro_gestor": "Secretaría de Infraestructura",
    "banco": "Banco Mundial",
    "objeto_contrato": "Construcción y mantenimiento de vías terciarias",
    "valor_contrato": 8000000000.0,
    "bp": "BP-INF-2024-03",
    "bpin": "2024000030001",
    "valor_convenio": 7500000000.0,
    "modalidad_contrato": "Transferencia de Recursos",
    "tipo_contrato": "Infraestructura",
    "estado_contrato": "Activo",
    "sector": "Infraestructura",
    "fecha_inicio_contrato": "2024-01-15",
    "fecha_fin_contrato": "2025-12-31"
}

try:
    response = requests.post(url, data=datos, timeout=30)

    if response.status_code == 201:
        resultado = response.json()
        print("✅ Convenio creado exitosamente!")
        print(f"ID: {resultado['doc_id']}")
        print(f"Mensaje: {resultado['message']}")
    elif response.status_code == 409:
        print("⚠️ El convenio ya existe (duplicado)")
        print(response.json())
    else:
        print(f"❌ Error: {response.status_code}")
        print(response.json())

except Exception as e:
    print(f"❌ Error de conexión: {e}")
```

---

### 4. JavaScript/Node.js - Crear Convenio

```javascript
const axios = require("axios");
const FormData = require("form-data");

async function crearConvenio() {
  const form = new FormData();

  // Campos obligatorios
  form.append("referencia_contrato", "CONV-SALUD-004-2024");
  form.append("nombre_centro_gestor", "Secretaría de Salud");
  form.append("banco", "Banco Mundial");
  form.append("objeto_contrato", "Dotación de centros de salud");
  form.append("valor_contrato", "3000000000");

  // Campos opcionales
  form.append("bp", "BP-SAL-2024-04");
  form.append("bpin", "2024000040001");
  form.append("modalidad_contrato", "Convenio de Transferencia");
  form.append("estado_contrato", "Activo");

  try {
    const response = await axios.post(
      "http://localhost:8000/emprestito/cargar-convenio-transferencia",
      form,
      { headers: form.getHeaders() }
    );

    console.log("✅ Convenio creado:", response.data);
    return response.data;
  } catch (error) {
    if (error.response?.status === 409) {
      console.log("⚠️ Convenio duplicado:", error.response.data);
    } else {
      console.error("❌ Error:", error.response?.data || error.message);
    }
  }
}

crearConvenio();
```

---

### 5. Manejo de Errores Comunes

#### Error: Campo Obligatorio Faltante

```json
{
  "success": false,
  "error": "El campo 'banco' es obligatorio",
  "message": "Error al procesar el convenio de transferencia",
  "timestamp": "2024-11-09T..."
}
```

#### Error: Convenio Duplicado

```json
{
  "success": false,
  "error": "Ya existe un convenio de transferencia con referencia: CONV-SALUD-001-2024",
  "duplicate": true,
  "existing_data": {
    "doc_id": "xyz789abc",
    "referencia_contrato": "CONV-SALUD-001-2024"
  },
  "message": "Ya existe un convenio de transferencia con esta referencia",
  "timestamp": "2024-11-09T..."
}
```

#### Error: Firebase no disponible

```json
{
  "error": "Servicios de empréstito no disponibles",
  "message": "Firebase o dependencias no configuradas correctamente",
  "code": "EMPRESTITO_SERVICES_UNAVAILABLE"
}
```

---

### 6. Validar antes de crear

Puedes verificar si un convenio ya existe antes de crearlo consultando la colección:

```python
import requests

def convenio_existe(referencia):
    # Este endpoint aún no existe, pero sería útil implementarlo
    # Por ahora, puedes intentar crear y manejar el error 409
    return False

# Uso
referencia = "CONV-SALUD-001-2024"
if not convenio_existe(referencia):
    # Crear convenio
    pass
else:
    print("El convenio ya existe")
```

---

### 7. Batch Insert - Cargar múltiples convenios

```python
import requests
import time

convenios = [
    {
        "referencia_contrato": "CONV-A-001-2024",
        "nombre_centro_gestor": "Secretaría A",
        "banco": "Banco Mundial",
        "objeto_contrato": "Proyecto A",
        "valor_contrato": 1000000000
    },
    {
        "referencia_contrato": "CONV-B-002-2024",
        "nombre_centro_gestor": "Secretaría B",
        "banco": "BID",
        "objeto_contrato": "Proyecto B",
        "valor_contrato": 2000000000
    },
    # ... más convenios
]

url = "http://localhost:8000/emprestito/cargar-convenio-transferencia"
resultados = []

for convenio in convenios:
    try:
        response = requests.post(url, data=convenio, timeout=30)

        if response.status_code == 201:
            print(f"✅ {convenio['referencia_contrato']} - Creado")
            resultados.append({"status": "success", "referencia": convenio['referencia_contrato']})
        elif response.status_code == 409:
            print(f"⚠️ {convenio['referencia_contrato']} - Ya existe")
            resultados.append({"status": "duplicate", "referencia": convenio['referencia_contrato']})
        else:
            print(f"❌ {convenio['referencia_contrato']} - Error {response.status_code}")
            resultados.append({"status": "error", "referencia": convenio['referencia_contrato']})

        time.sleep(0.5)  # Pequeña pausa entre requests

    except Exception as e:
        print(f"❌ {convenio['referencia_contrato']} - Excepción: {e}")
        resultados.append({"status": "exception", "referencia": convenio['referencia_contrato']})

# Resumen
print(f"\n📊 Resumen:")
print(f"Total: {len(resultados)}")
print(f"Exitosos: {sum(1 for r in resultados if r['status'] == 'success')}")
print(f"Duplicados: {sum(1 for r in resultados if r['status'] == 'duplicate')}")
print(f"Errores: {sum(1 for r in resultados if r['status'] in ['error', 'exception'])}")
```

---

### 8. Integración con Swagger UI

1. Abre tu navegador en: http://localhost:8000/docs
2. Busca la sección **"Gestión de Empréstito"**
3. Encuentra el endpoint **POST /emprestito/cargar-convenio-transferencia**
4. Click en **"Try it out"**
5. Llena los campos del formulario
6. Click en **"Execute"**
7. Verás la respuesta del servidor

---

## 🔍 Filtros y Consultas (Futuros endpoints sugeridos)

### Sugerencias de endpoints complementarios:

1. **GET** `/emprestito/convenios-transferencia`

   - Listar todos los convenios

2. **GET** `/emprestito/convenio-transferencia/{referencia}`

   - Obtener un convenio específico

3. **PUT** `/emprestito/convenio-transferencia/{referencia}`

   - Actualizar un convenio existente

4. **DELETE** `/emprestito/convenio-transferencia/{referencia}`

   - Eliminar un convenio

5. **GET** `/emprestito/convenios-transferencia/centro-gestor/{nombre}`

   - Filtrar por centro gestor

6. **GET** `/emprestito/convenios-transferencia/banco/{nombre}`
   - Filtrar por banco

---

## 📝 Notas Importantes

1. **Campos de fecha**: Se reciben como strings en formato ISO (YYYY-MM-DD)
2. **Valores numéricos**: `valor_contrato` y `valor_convenio` son floats
3. **Validación de duplicados**: Se realiza por `referencia_contrato`
4. **Timestamps automáticos**: `fecha_creacion` y `fecha_actualizacion` se agregan automáticamente
5. **Estado por defecto**: Todos los convenios se crean con `estado: "activo"`

---

**Última actualización:** 9 de noviembre de 2025

# Migración al Endpoint Unificado de Unidades de Proyecto

## 📋 Resumen

Se ha creado un **endpoint unificado** `/unidades-proyecto` que consolida múltiples endpoints especializados en una sola API flexible y consistente.

## 🎯 Endpoint Unificado

```
GET /unidades-proyecto
```

### Modos de Operación

El endpoint soporta 4 modos mediante el parámetro `mode`:

1. **`mode=attributes`** (por defecto) - Datos tabulares sin geometrías
2. **`mode=geometry`** - Datos geoespaciales en formato GeoJSON
3. **`mode=filters`** - Valores únicos para filtros
4. **`mode=single`** - Unidad específica por UPID

---

## 🔄 Guía de Migración

### 1. Endpoint `/unidades-proyecto/attributes`

**❌ Deprecado:**

```
GET /unidades-proyecto/attributes?nombre_centro_gestor=X&limit=100
```

**✅ Nuevo:**

```
GET /unidades-proyecto?mode=attributes&nombre_centro_gestor=X&limit=100
```

O simplemente (attributes es el modo por defecto):

```
GET /unidades-proyecto?nombre_centro_gestor=X&limit=100
```

---

### 2. Endpoint `/unidades-proyecto/geometry`

**❌ Deprecado:**

```
GET /unidades-proyecto/geometry?tipo_equipamiento=Vías&limit=500
```

**✅ Nuevo:**

```
GET /unidades-proyecto?mode=geometry&tipo_equipamiento=Vías&limit=500
```

---

### 3. Endpoint `/unidades-proyecto/filters`

**❌ Deprecado:**

```
GET /unidades-proyecto/filters?field=estado&limit=20
```

**✅ Nuevo:**

```
GET /unidades-proyecto?mode=filters&filter_field=estado&filter_limit=20
```

**Nota:** Los parámetros cambiaron de `field` → `filter_field` y `limit` → `filter_limit` para evitar conflictos.

---

### 4. Endpoint `/unidades-proyecto/{upid}`

**❌ Deprecado:**

```
GET /unidades-proyecto/UNP-1978
```

**✅ Nuevo:**

```
GET /unidades-proyecto?mode=single&upid=UNP-1978
```

---

## 🆕 Mejoras del Endpoint Unificado

### 1. API Más Consistente

Todos los endpoints ahora comparten la misma estructura base y parámetros comunes.

### 2. Filtros Mejorados

Nuevos filtros numéricos con rangos:

- `presupuesto_base_min` / `presupuesto_base_max`
- `avance_obra_min` / `avance_obra_max`

### 3. Más Parámetros de Filtrado

- `fuente_financiacion` - Fuente de financiación
- `ano` - Año de ejecución
- `referencia_contrato` - Referencia del contrato
- `referencia_proceso` - Referencia del proceso

### 4. Mejor Documentación

El endpoint unificado tiene documentación exhaustiva con ejemplos de uso para cada modo.

---

## 📊 Ejemplos Completos

### Ejemplo 1: Obtener tabla de proyectos activos

```bash
GET /unidades-proyecto?estado=En ejecución&limit=50&offset=0
```

### Ejemplo 2: Obtener geometrías para mapa con bbox

```bash
GET /unidades-proyecto?mode=geometry&tipo_equipamiento=Vías&include_bbox=true
```

### Ejemplo 3: Obtener todos los valores de filtro

```bash
GET /unidades-proyecto?mode=filters
```

### Ejemplo 4: Obtener filtros de un campo específico

```bash
GET /unidades-proyecto?mode=filters&filter_field=nombre_centro_gestor
```

### Ejemplo 5: Obtener unidad específica

```bash
GET /unidades-proyecto?mode=single&upid=UNP-1000
```

### Ejemplo 6: Filtrar por rango de presupuesto

```bash
GET /unidades-proyecto?presupuesto_base_min=1000000&presupuesto_base_max=5000000&limit=100
```

### Ejemplo 7: Búsqueda textual

```bash
GET /unidades-proyecto?nombre_up=parque&direccion=calle&comuna_corregimiento=Comuna%201
```

---

## 🔧 Compatibilidad

Los endpoints antiguos se mantienen **activos pero marcados como deprecated** en la documentación de Swagger/OpenAPI.

Se recomienda migrar al nuevo endpoint unificado para:

- Mejor rendimiento
- API más consistente
- Acceso a nuevas funcionalidades
- Soporte a largo plazo

---

## ⚙️ Parámetros Completos

### Parámetros de Modo

- `mode` - Modo de operación: `attributes`, `geometry`, `filters`, `single`

### Filtros de Búsqueda Exacta

- `upid` - ID de unidad
- `nombre_centro_gestor` - Centro gestor
- `tipo_intervencion` - Tipo de intervención
- `estado` - Estado del proyecto
- `clase_up` - Clase de unidad
- `tipo_equipamiento` - Tipo de equipamiento
- `comuna_corregimiento` - Comuna/corregimiento
- `barrio_vereda` - Barrio/vereda
- `frente_activo` - Frente activo
- `fuente_financiacion` - Fuente de financiación
- `ano` - Año

### Búsquedas Parciales

- `nombre_up` - Búsqueda en nombre (contiene)
- `direccion` - Búsqueda en dirección (contiene)
- `referencia_contrato` - Referencia contrato
- `referencia_proceso` - Referencia proceso

### Filtros Numéricos

- `presupuesto_base_min` - Presupuesto mínimo
- `presupuesto_base_max` - Presupuesto máximo
- `avance_obra_min` - Avance mínimo %
- `avance_obra_max` - Avance máximo %

### Configuración

- `include_bbox` - Incluir bounding box (solo geometry)
- `include_intervenciones` - Incluir intervenciones
- `limit` - Límite de resultados
- `offset` - Offset para paginación
- `debug` - Modo debug

### Parámetros para mode=filters

- `filter_field` - Campo específico para filtros
- `filter_limit` - Límite de valores únicos

---

## 📚 Recursos Adicionales

- Documentación API: `/docs` o `/redoc`
- Código fuente: `main.py` líneas 1893-2193
- Scripts: `api/scripts/unidades_proyecto.py`

---

## ❓ Preguntas Frecuentes

### ¿Por qué crear un endpoint unificado?

1. **Mantenibilidad**: Un solo endpoint es más fácil de mantener que múltiples endpoints especializados
2. **Consistencia**: API más predecible y fácil de usar
3. **Flexibilidad**: Fácil agregar nuevos modos o parámetros
4. **Documentación**: Más clara y centralizada

### ¿Cuándo se eliminarán los endpoints antiguos?

Los endpoints antiguos se mantendrán indefinidamente por compatibilidad, pero **no recibirán nuevas funcionalidades**. Se recomienda migrar al endpoint unificado.

### ¿Hay diferencias en la respuesta?

No, las respuestas son idénticas. Solo cambia la forma de invocar el endpoint.

### ¿El rendimiento es diferente?

El endpoint unificado tiene el **mismo rendimiento** o mejor, ya que comparte la misma lógica interna optimizada.

---

**Fecha de creación**: 15 de febrero de 2026  
**Versión**: 1.0  
**Autor**: Sistema de Gestión de Proyectos

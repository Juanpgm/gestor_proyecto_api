# 📘 GUÍA DE USO - NUEVOS ENDPOINTS DE INTERVENCIONES

**Fecha**: 2025-01-19  
**Versión API**: Compatible con estructura de intervenciones anidadas

---

## 🎯 Resumen de Cambios

La API ahora soporta una **nueva estructura anidada** donde cada Unidad de Proyecto puede contener **múltiples intervenciones**. Los datos se organizan de la siguiente manera:

```javascript
{
  "type": "Feature",
  "geometry": {...},
  "properties": {
    "upid": "UNP-1",
    "nombre_up": "I.E. Liceo Departamental",
    "clase_up": "Obras equipamientos",
    "n_intervenciones": 1,
    "intervenciones": [
      {
        "intervencion_id": "UNP-1-01",
        "estado": "Terminado",
        "ano": 2024,
        "tipo_intervencion": "Adecuaciones",
        "presupuesto_base": 412000000,
        "avance_obra": 100.0,
        "frente_activo": "No aplica"
      }
    ]
  }
}
```

---

## 🔵 ENDPOINT 1: Obtener Unidad Específica

### `GET /unidades-proyecto/{upid}`

Retorna una unidad de proyecto específica con todas sus intervenciones.

### Ejemplo de Uso

```javascript
// Obtener unidad UNP-1
fetch("/unidades-proyecto/UNP-1")
  .then((res) => res.json())
  .then((unidad) => {
    console.log(unidad.properties.nombre_up);
    console.log(`Total intervenciones: ${unidad.properties.n_intervenciones}`);

    // Iterar por intervenciones
    unidad.properties.intervenciones.forEach((interv) => {
      console.log(`- ${interv.intervencion_id}: ${interv.estado}`);
    });
  });
```

### Respuesta

```json
{
  "type": "Feature",
  "geometry": {
    "type": "Point",
    "coordinates": [-76.5319, 3.4372]
  },
  "properties": {
    "upid": "UNP-1",
    "nombre_up": "I.E. Liceo Departamental",
    "direccion": "Carrera 5 # 13-71",
    "clase_up": "Obras equipamientos",
    "n_intervenciones": 1,
    "intervenciones": [
      {
        "intervencion_id": "UNP-1-01",
        "referencia_proceso": ["4143.010.32.0469-2024"],
        "referencia_contrato": ["4143.010.26.1314-2024"],
        "estado": "Terminado",
        "tipo_intervencion": "Adecuaciones",
        "fuente_financiacion": "Presupuesto Participativo",
        "presupuesto_base": 412000000,
        "ano": 2024,
        "avance_obra": 100.0,
        "fecha_inicio": "2024-05-09T00:00:00",
        "fecha_fin": "2025-01-15T00:00:00",
        "frente_activo": "No aplica"
      }
    ]
  }
}
```

---

## 🔵 ENDPOINT 2: Buscar Intervención Específica

### `GET /intervenciones/{intervencion_id}`

Busca una intervención específica en todas las unidades de proyecto.

### Ejemplo de Uso

```javascript
// Buscar intervención UNP-1-01
fetch("/intervenciones/UNP-1-01")
  .then((res) => res.json())
  .then((data) => {
    console.log(`Unidad: ${data.unidad.nombre_up}`);
    console.log(`Estado: ${data.intervencion.estado}`);
    console.log(`Año: ${data.intervencion.ano}`);
  });
```

### Respuesta

```json
{
  "unidad": {
    "upid": "UNP-1",
    "nombre_up": "I.E. Liceo Departamental",
    "direccion": "Carrera 5 # 13-71",
    "clase_up": "Obras equipamientos",
    "geometry": {
      "type": "Point",
      "coordinates": [-76.5319, 3.4372]
    }
  },
  "intervencion": {
    "intervencion_id": "UNP-1-01",
    "estado": "Terminado",
    "tipo_intervencion": "Adecuaciones",
    "presupuesto_base": 412000000,
    "ano": 2024,
    "avance_obra": 100.0,
    "frente_activo": "No aplica"
  }
}
```

---

## 🔵 ENDPOINT 3: Filtrar Intervenciones

### `GET /intervenciones`

Filtra unidades de proyecto por criterios de sus intervenciones.

### Parámetros (Query Params)

| Parámetro           | Tipo    | Descripción               | Valores Ejemplo                 |
| ------------------- | ------- | ------------------------- | ------------------------------- |
| `estado`            | string  | Estado de la intervención | "Terminado", "En ejecución"     |
| `tipo_intervencion` | string  | Tipo de intervención      | "Mantenimiento", "Adecuaciones" |
| `ano`               | integer | Año de la intervención    | 2024, 2025                      |
| `frente_activo`     | string  | Estado del frente de obra | "Sí", "No", "No aplica"         |

### Ejemplos de Uso

#### Ejemplo 1: Filtrar por estado

```javascript
// Obtener intervenciones terminadas
fetch("/intervenciones?estado=Terminado")
  .then((res) => res.json())
  .then((data) => {
    console.log(`Total unidades: ${data.features.length}`);

    // Contar intervenciones terminadas
    let total_terminadas = 0;
    data.features.forEach((f) => {
      const terminadas = f.properties.intervenciones.filter(
        (i) => i.estado === "Terminado"
      );
      total_terminadas += terminadas.length;
    });
    console.log(`Total intervenciones terminadas: ${total_terminadas}`);
  });
```

**Resultado**: 263 unidades con 322 intervenciones terminadas

#### Ejemplo 2: Filtrar por tipo y año

```javascript
// Obtener mantenimientos de 2025
fetch("/intervenciones?tipo_intervencion=Mantenimiento&ano=2025")
  .then((res) => res.json())
  .then((data) => {
    console.log(`Mantenimientos 2025: ${data.features.length} unidades`);
  });
```

#### Ejemplo 3: Combinar filtros

```javascript
// Terminados en 2024 con frente activo
fetch("/intervenciones?estado=Terminado&ano=2024&frente_activo=No aplica")
  .then((res) => res.json())
  .then((data) => {
    console.log(`Resultados: ${data.features.length}`);
  });
```

### Respuesta

```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "geometry": {...},
      "properties": {
        "upid": "UNP-1",
        "nombre_up": "I.E. Liceo Departamental",
        "n_intervenciones": 1,
        "intervenciones": [
          {
            "intervencion_id": "UNP-1-01",
            "estado": "Terminado",
            "ano": 2024,
            "presupuesto_base": 412000000
          }
        ]
      }
    }
  ]
}
```

**Nota**: El endpoint retorna unidades completas que tienen **al menos una intervención** que cumple los criterios de filtro. Cada unidad puede tener múltiples intervenciones (algunas que cumplen el filtro y otras que no).

---

## 🔵 ENDPOINT 4: Obtener Frentes Activos

### `GET /frentes-activos`

Retorna unidades de proyecto que tienen frentes de obra activos.

### Ejemplo de Uso

```javascript
// Obtener todas las unidades con frentes activos
fetch("/frentes-activos")
  .then((res) => res.json())
  .then((data) => {
    console.log(`Unidades con frentes activos: ${data.features.length}`);

    // Contar total de frentes activos
    let total_frentes = 0;
    data.features.forEach((f) => {
      const con_frente = f.properties.intervenciones.filter(
        (i) => i.frente_activo === "Sí"
      );
      total_frentes += con_frente.length;
    });
    console.log(`Total frentes activos: ${total_frentes}`);
  });
```

### Respuesta

```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "geometry": {...},
      "properties": {
        "upid": "UNP-108",
        "nombre_up": "I.E. Golondrinas",
        "n_intervenciones": 1,
        "intervenciones": [
          {
            "intervencion_id": "UNP-108-01",
            "estado": "En ejecución",
            "frente_activo": "Sí",
            "avance_obra": 45.0
          }
        ]
      }
    }
  ]
}
```

**Resultado**: 78 frentes activos en 62 unidades

---

## 📊 ENDPOINT EXISTENTE: Atributos Tabulares

### `GET /unidades-proyecto/attributes`

El endpoint de atributos **también soporta la nueva estructura** de intervenciones. Ahora parsea correctamente las intervenciones como arrays de diccionarios.

### Ejemplo de Uso

```javascript
// Obtener primeros 10 registros con estado Terminado
fetch("/unidades-proyecto/attributes?estado=Terminado&limit=10")
  .then((res) => res.json())
  .then((data) => {
    console.log(`Registros: ${data.count}`);

    data.data.forEach((record) => {
      console.log(`${record.upid}: ${record.nombre_up}`);
      console.log(`  Intervenciones: ${record.n_intervenciones}`);

      // Las intervenciones están parseadas como diccionarios
      record.intervenciones.forEach((i) => {
        console.log(`  - ${i.intervencion_id}: ${i.estado}`);
      });
    });
  });
```

### Filtros Soportados

Los filtros `estado`, `tipo_intervencion` y `frente_activo` ahora **buscan dentro del array de intervenciones**:

```javascript
// Estos filtros buscan en las intervenciones anidadas
fetch(
  "/unidades-proyecto/attributes?estado=Terminado&tipo_intervencion=Mantenimiento"
);
```

---

## 🔄 Compatibilidad con Estructura Antigua

Todos los endpoints mantienen **retrocompatibilidad** con documentos en estructura plana (antigua). La API detecta automáticamente el formato:

- **Nueva estructura**: Si el documento tiene campo `intervenciones` como array → parsea y usa directamente
- **Estructura antigua**: Si el documento es plano → transforma automáticamente a estructura con intervenciones

---

## ✅ Cambios de Nomenclatura

### `clase_obra` → `clase_up`

El campo `clase_obra` ha sido renombrado a `clase_up` (Clase de Unidad de Proyecto). La API:

1. ✅ Retorna `clase_up` en todos los endpoints
2. ✅ Acepta `clase_up` en filtros
3. ✅ Mantiene soporte para `clase_obra` en filtros (retrocompatibilidad)

```javascript
// Ambos funcionan
fetch("/unidades-proyecto/attributes?clase_up=Obras equipamientos");
fetch("/unidades-proyecto/attributes?clase_obra=Obras equipamientos"); // También funciona
```

---

## 📈 Ejemplos Prácticos

### Ejemplo 1: Dashboard de Intervenciones por Estado

```javascript
async function obtenerEstadisticasEstado() {
  const response = await fetch("/unidades-proyecto/geometry");
  const data = await response.json();

  const estadisticas = {};

  data.features.forEach((feature) => {
    const intervenciones = feature.properties.intervenciones || [];
    intervenciones.forEach((i) => {
      if (!estadisticas[i.estado]) {
        estadisticas[i.estado] = 0;
      }
      estadisticas[i.estado]++;
    });
  });

  console.log("Intervenciones por Estado:", estadisticas);
  // Output: { "Terminado": 322, "En ejecución": 156, ... }
}
```

### Ejemplo 2: Mapa de Frentes Activos con Leaflet

```javascript
async function mostrarFrentesActivos() {
  const response = await fetch("/frentes-activos");
  const data = await response.json();

  const map = L.map("map").setView([3.4372, -76.5319], 12);
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png").addTo(map);

  L.geoJSON(data, {
    onEachFeature: (feature, layer) => {
      const props = feature.properties;
      const frentes = props.intervenciones.filter(
        (i) => i.frente_activo === "Sí"
      );

      layer.bindPopup(`
        <strong>${props.nombre_up}</strong><br>
        UPID: ${props.upid}<br>
        Frentes Activos: ${frentes.length}
      `);
    },
  }).addTo(map);
}
```

### Ejemplo 3: Tabla de Intervenciones con DataTables

```javascript
async function cargarTablaIntervenciones() {
  const response = await fetch(
    "/unidades-proyecto/attributes?estado=En ejecución"
  );
  const data = await response.json();

  const rows = [];

  data.data.forEach((record) => {
    record.intervenciones.forEach((i) => {
      if (i.estado === "En ejecución") {
        rows.push({
          upid: record.upid,
          nombre_up: record.nombre_up,
          intervencion_id: i.intervencion_id,
          tipo_intervencion: i.tipo_intervencion,
          presupuesto_base: i.presupuesto_base,
          avance_obra: i.avance_obra,
        });
      }
    });
  });

  $("#tabla").DataTable({
    data: rows,
    columns: [
      { data: "upid", title: "UPID" },
      { data: "nombre_up", title: "Nombre Unidad" },
      { data: "intervencion_id", title: "ID Intervención" },
      { data: "tipo_intervencion", title: "Tipo" },
      {
        data: "presupuesto_base",
        title: "Presupuesto",
        render: $.fn.dataTable.render.number(",", ".", 0, "$"),
      },
      {
        data: "avance_obra",
        title: "Avance (%)",
        render: (data) => `${data}%`,
      },
    ],
  });
}
```

---

## 🚀 Próximos Pasos

1. **Explorar la API**: Prueba los endpoints con diferentes filtros
2. **Integrar en Frontend**: Actualiza tus aplicaciones para usar la nueva estructura
3. **Optimizar Consultas**: Usa filtros específicos para reducir carga de datos
4. **Reportar Issues**: Cualquier problema o sugerencia, crear issue en el repositorio

---

## 📚 Referencias

- **Documentación Completa**: [CAMBIOS_API_FRONTEND.md](./CAMBIOS_API_FRONTEND.md)
- **Resumen de Cambios**: [RESUMEN_CAMBIOS_IMPLEMENTADOS.md](./RESUMEN_CAMBIOS_IMPLEMENTADOS.md)
- **Análisis Firebase**: [ANALISIS_ESTRUCTURA_FIREBASE.md](./ANALISIS_ESTRUCTURA_FIREBASE.md)

---

**Fecha de Actualización**: 2025-01-19  
**Versión**: 1.0  
**Autor**: GitHub Copilot

# Endpoint: Descarga de Tabla Excel - Unidades de Proyecto

## 📌 Resumen

Nuevo endpoint `GET /unidades-proyecto/download-table` que permite descargar todos los datos de la colección `unidades_proyecto` en formato Excel (.xlsx).

## 🎯 Endpoint

```
GET /unidades-proyecto/download-table
```

**Tag**: `Unidades de Proyecto`

## ✅ Características

- ✅ **Formato Excel (.xlsx)**: Compatible con Microsoft Excel, Google Sheets, LibreOffice
- ✅ **Todos los campos tabulares**: 33 columnas con información completa
- ✅ **Filtros flexibles**: Por centro gestor, estado, ubicación, tipo de equipamiento, etc.
- ✅ **UTF-8**: Soporte completo para caracteres especiales
- ✅ **Headers descriptivos**: Nombres de columnas legibles en español
- ✅ **Formato profesional**: Encabezados con estilo (fondo azul, texto blanco, centrado)
- ✅ **Congelación de paneles**: Primera fila congelada para facilitar navegación
- ✅ **Ancho automático**: Columnas ajustadas al contenido
- ✅ **Timestamp en nombre**: Archivo nombrado con fecha y hora de descarga

## 📊 Campos incluidos (33 columnas)

1. UPID
2. Nombre UP
3. Nombre UP Detalle
4. Estado
5. Tipo Intervención
6. Clase Obra
7. Tipo Equipamiento
8. Centro Gestor
9. Centro Gestor (Código)
10. Comuna/Corregimiento
11. Barrio/Vereda
12. Dirección
13. Presupuesto Base
14. Presupuesto Total UP
15. Avance Obra (%)
16. BPIN
17. Año
18. Fuente Financiación
19. Referencia Contrato
20. Referencia Proceso
21. Plataforma
22. URL Proceso
23. Fecha Inicio
24. Fecha Inicio Estandarizada
25. Fecha Fin
26. Identificador
27. Cantidad
28. Unidad Medida
29. Fuera Rango
30. Tiene Geometría
31. Fecha Creación
32. Fecha Actualización
33. Timestamp Procesamiento

## 🔧 Parámetros de consulta (opcionales)

| Parámetro              | Tipo    | Descripción                                  |
| ---------------------- | ------- | -------------------------------------------- |
| `nombre_centro_gestor` | string  | Filtrar por centro gestor                    |
| `tipo_intervencion`    | string  | Filtrar por tipo de intervención             |
| `estado`               | string  | Filtrar por estado del proyecto              |
| `upid`                 | string  | Filtrar por ID específico                    |
| `clase_obra`           | string  | Filtrar por clase de obra                    |
| `tipo_equipamiento`    | string  | Filtrar por tipo de equipamiento             |
| `comuna_corregimiento` | string  | Filtrar por comuna o corregimiento           |
| `barrio_vereda`        | string  | Filtrar por barrio o vereda                  |
| `limit`                | integer | Límite de registros (1-10000, default=todos) |

## 📝 Ejemplos de uso

### 1. Descargar todos los registros

```bash
GET /unidades-proyecto/download-table
```

**Respuesta**: Archivo Excel con ~1730 registros (256 KB)

### 2. Filtrar por centro gestor

```bash
GET /unidades-proyecto/download-table?nombre_centro_gestor=Secretaría de Educación
```

### 3. Filtrar por estado y comuna

```bash
GET /unidades-proyecto/download-table?estado=Activo&comuna_corregimiento=COMUNA 01
```

### 4. Limitar resultados

```bash
GET /unidades-proyecto/download-table?limit=100
```

### 5. Filtros múltiples

```bash
GET /unidades-proyecto/download-table?nombre_centro_gestor=Secretaría de Infraestructura&clase_obra=Obra Vial&limit=50
```

## 📥 Respuesta

**Content-Type**: `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`

**Headers**:

- `Content-Disposition`: `attachment; filename=unidades_proyecto_YYYYMMDD_HHMMSS.xlsx`
- `Access-Control-Expose-Headers`: `Content-Disposition`

**Nombre del archivo**: `unidades_proyecto_20251118_165711.xlsx` (con timestamp)

## 🎯 Casos de uso

1. **Reportes gerenciales**: Crear informes ejecutivos en Excel
2. **Análisis de datos**: Análisis en Excel, Power BI, Tableau
3. **Seguimiento de proyectos**: Control y monitoreo de avances
4. **Auditoría**: Revisión y verificación de información
5. **Integración**: Importar a otros sistemas de gestión
6. **Backup**: Exportar datos para respaldo

## 📊 Resultados de pruebas

✅ **Prueba 1**: Descarga de 50 registros - 12.7 KB - OK
✅ **Prueba 2**: Filtrado por centro gestor - OK
✅ **Prueba 3**: Descarga completa (1730 registros) - 256 KB - OK

## 💡 Notas técnicas

- El endpoint usa `get_unidades_proyecto_attributes()` para obtener datos sin geometría (mejor performance)
- Formato de columnas optimizado para lectura en Excel
- Conversión automática de listas a strings separados por comas
- Booleanos convertidos a "Sí"/"No"
- Primera fila congelada para facilitar navegación
- Rate limiting: 20 requests/minuto

## 🔗 Endpoints relacionados

- `GET /unidades-proyecto/geometry` - Obtener geometrías en formato GeoJSON
- `GET /unidades-proyecto/attributes` - Obtener atributos en formato JSON
- `GET /unidades-proyecto/download-geojson` - Descargar en formato GeoJSON
- `GET /unidades-proyecto/dashboard` - Dashboard con métricas y estadísticas

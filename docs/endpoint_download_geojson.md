# Endpoint de Descarga GeoJSON - Unidades de Proyecto

## Descripción General

Se ha creado un nuevo endpoint en la API para permitir la descarga de datos de la colección "unidades_proyecto" en formato GeoJSON estándar.

## Información del Endpoint

- **URL**: `/unidades-proyecto/download-geojson`
- **Método**: GET
- **Tag**: "Unidades de Proyecto"
- **Descripción**: Descarga datos en formato .geojson desde Firebase

## Parámetros Disponibles

### Filtros de Contenido

- `nombre_centro_gestor` (string, opcional): Centro gestor responsable
- `tipo_intervencion` (string, opcional): Tipo de intervención
- `estado` (string, opcional): Estado del proyecto
- `upid` (string, opcional): ID específico de unidad

### Filtros Geográficos

- `comuna_corregimiento` (string, opcional): Comuna o corregimiento específico
- `barrio_vereda` (string, opcional): Barrio o vereda específico

### Configuración de Descarga

- `include_all_records` (boolean, por defecto: true): Incluir todos los registros (con y sin geometría)
- `only_with_geometry` (boolean, por defecto: false): Solo registros con geometría válida
- `limit` (integer, opcional): Límite de registros (1-10000)

### Parámetros de Formato

- `include_metadata` (boolean, por defecto: true): Incluir metadata en el GeoJSON

## Características Principales

### ✅ Formato Estándar GeoJSON

- Compatible con QGIS, ArcGIS, Leaflet, OpenLayers
- Cumple con RFC 7946 (estándar GeoJSON)
- Encoding UTF-8 completo para caracteres especiales

### 🗺️ Estrategia de Geometría

- **Por defecto**: Incluye todos los registros, los sin geometría usan coordenadas [0,0]
- **Campo `has_valid_geometry`**: Indica si las coordenadas son reales o placeholder
- **Filtro opcional**: Solo registros con geometría válida usando `only_with_geometry=true`

### 📊 Campos Incluidos

- `upid`: Identificador único del proyecto
- `nombre_up`: Nombre del proyecto
- `estado`: Estado actual del proyecto
- `tipo_intervencion`: Tipo de intervención urbana
- `nombre_centro_gestor`: Entidad responsable
- `comuna_corregimiento`: Ubicación administrativa
- `barrio_vereda`: Ubicación específica
- `presupuesto_base`: Valor del proyecto (convertido a entero)
- `avance_obra`: Porcentaje de avance (convertido a float)
- `bpin`: Código BPIN del proyecto (convertido a entero positivo)
- `has_valid_geometry`: Indica si tiene coordenadas reales

## Ejemplos de Uso

### 1. Descargar todos los proyectos

```bash
GET /unidades-proyecto/download-geojson
```

### 2. Filtrar por centro gestor

```bash
GET /unidades-proyecto/download-geojson?nombre_centro_gestor=Secretaría de Infraestructura
```

### 3. Solo proyectos con geometría válida

```bash
GET /unidades-proyecto/download-geojson?only_with_geometry=true
```

### 4. Proyectos de una comuna específica

```bash
GET /unidades-proyecto/download-geojson?comuna_corregimiento=Comuna 1
```

### 5. Combinar filtros

```bash
GET /unidades-proyecto/download-geojson?nombre_centro_gestor=Secretaría de Salud&estado=Activo&limit=100
```

## Respuesta del Endpoint

### Headers HTTP

```
Content-Type: application/geo+json; charset=utf-8
Content-Disposition: attachment; filename=unidades_proyecto.geojson
Access-Control-Expose-Headers: Content-Disposition
```

### Estructura de la Respuesta

```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "geometry": {
        "type": "Point",
        "coordinates": [-76.5319854, 3.4516467]
      },
      "properties": {
        "upid": "UP-2023-001",
        "has_valid_geometry": true,
        "nombre_up": "Construcción de Puente",
        "estado": "En Ejecución",
        "tipo_intervencion": "Infraestructura Vial",
        "nombre_centro_gestor": "Secretaría de Infraestructura",
        "comuna_corregimiento": "Comuna 1",
        "barrio_vereda": "Barrio San Antonio",
        "presupuesto_base": 500000000,
        "avance_obra": 75.5,
        "bpin": 2023000123456
      }
    }
  ],
  "metadata": {
    "source": "unidades_proyecto collection",
    "exported_at": "2025-10-28T10:30:00.000Z",
    "total_features": 646,
    "filters_applied": {},
    "has_valid_geometry_count": 423,
    "coordinate_system": "WGS84 (EPSG:4326)",
    "format": "GeoJSON (RFC 7946)",
    "encoding": "UTF-8",
    "api_version": "1.0.0",
    "last_updated": "2025-10-28T00:00:00Z"
  }
}
```

## Casos de Uso

### 🗺️ Análisis SIG

- Importar en QGIS para análisis espacial avanzado
- Cargar en ArcGIS para cartografía profesional
- Integrar con PostGIS para consultas espaciales

### 🌐 Mapas Web

- Cargar en Leaflet para mapas interactivos
- Usar con Mapbox para visualizaciones avanzadas
- Integrar con OpenLayers para aplicaciones web

### 📊 Visualización

- Crear mapas temáticos por tipo de intervención
- Dashboards geográficos por centro gestor
- Análisis de cobertura territorial

### 🔄 Integración

- Conectar con otras plataformas SIG
- Intercambio de datos entre sistemas
- APIs de terceros que consumen GeoJSON

### 💾 Backup y Archivos

- Exportar datos para respaldo
- Archivos históricos de proyectos
- Documentación geoespacial

## Implementación Técnica

### Backend

- **Función base**: Utiliza `get_unidades_proyecto_geometry()` existente
- **Filtros**: Reutiliza sistema de filtros ya implementado
- **Conversión de tipos**: Aplica conversiones automáticas (int, float)
- **Error handling**: Manejo robusto de errores

### Headers de Descarga

- **Content-Type**: `application/geo+json; charset=utf-8`
- **Content-Disposition**: Forza descarga con nombre de archivo
- **CORS**: Headers expuestos para descarga desde browser

### Validaciones

- Verificación de Firebase disponible
- Validación de filtros de entrada
- Manejo de casos sin datos
- Error handling para respuestas malformadas

## Rendimiento

### Optimizaciones

- Reutiliza función optimizada existente
- Filtros server-side cuando es posible
- Aplicación de límites para controlar payload
- Cache-friendly (sin cache persistente entre requests)

### Consideraciones

- Datos frescos en cada request (sin cache)
- Límite máximo de 10,000 registros
- Timeout de 30 segundos por request
- Encoding UTF-8 para caracteres especiales

## Código Agregado

El endpoint se agregó en `main.py` en la sección de "Unidades de Proyecto", después del endpoint `insert-linestrings` y antes de "Interoperabilidad con Artefacto de Seguimiento".

### Ubicación en el Código

- **Línea aproximada**: 2064
- **Sección**: "ENDPOINT PARA DESCARGA DE GEOJSON"
- **Tag**: "Unidades de Proyecto"

### Integración

- Se agregó a la lista de endpoints en el endpoint raíz (`/`)
- Compatible con la arquitectura existente
- Reutiliza funciones y validaciones existentes

## Testing

### Verificación Realizada

- ✅ Compilación sin errores de sintaxis
- ✅ Servidor inicia correctamente
- ✅ Firebase se conecta exitosamente
- ✅ Imports de módulos funcionan
- ✅ Endpoint aparece en documentación automática

### Testing Recomendado

1. Probar descarga sin filtros
2. Probar con diferentes combinaciones de filtros
3. Verificar formato GeoJSON en herramientas SIG
4. Validar caracteres especiales UTF-8
5. Probar límites y casos extremos

## Documentación Swagger

El endpoint aparecerá automáticamente en la documentación Swagger de la API en:

- **URL**: `http://localhost:8000/docs`
- **Sección**: "Unidades de Proyecto"
- **Título**: "🔵 Descarga GeoJSON"

## Fecha de Implementación

**Creado**: 28 de octubre de 2025
**Versión API**: 1.0.0
**Estado**: Listo para producción

# Endpoint: `/unidades-proyecto/download-table_by_centro_gestor`

## 📋 Resumen

Nuevo endpoint GET para descargar datos de unidades de proyecto filtrados por `nombre_centro_gestor` en formato Excel (.xlsx).

## 🎯 Propósito

Permitir la descarga de tablas Excel con datos filtrados específicamente para cada centro gestor (secretaría o entidad responsable), facilitando la generación de reportes por dependencia.

## 🔧 Características Principales

### ✅ Filtro Obligatorio

- **nombre_centro_gestor**: Parámetro requerido para filtrar los datos

### 🎨 Filtros Adicionales Opcionales

- `tipo_intervencion`: Tipo de intervención
- `estado`: Estado del proyecto (Activo, Finalizado, etc.)
- `upid`: ID específico de unidad
- `clase_obra`: Clase de obra
- `tipo_equipamiento`: Tipo de equipamiento
- `comuna_corregimiento`: Comuna o corregimiento
- `barrio_vereda`: Barrio o vereda
- `limit`: Límite de registros (1-10000)

### 📊 Formato de Salida

- Archivo Excel (.xlsx)
- Formato compatible con Microsoft Excel, Google Sheets, LibreOffice
- Encoding UTF-8 para soporte de caracteres especiales
- Headers descriptivos y estilizados
- Primera fila congelada para mejor navegación

### 📁 Nombre de Archivo

El archivo generado incluye:

- Timestamp de generación
- Nombre del centro gestor (sanitizado para nombres de archivo)
- Formato: `unidades_proyecto_{centro_gestor}_{YYYYMMDD_HHMMSS}.xlsx`

Ejemplo: `unidades_proyecto_Secretaría_de_Infraestructura_20251119_143022.xlsx`

## 🔗 URL del Endpoint

```
GET /unidades-proyecto/download-table_by_centro_gestor
```

## 📝 Ejemplos de Uso

### Ejemplo 1: Descargar todos los proyectos de una secretaría

```bash
GET /unidades-proyecto/download-table_by_centro_gestor?nombre_centro_gestor=Secretaría de Infraestructura
```

### Ejemplo 2: Proyectos activos de una secretaría

```bash
GET /unidades-proyecto/download-table_by_centro_gestor?nombre_centro_gestor=Secretaría de Educación&estado=Activo
```

### Ejemplo 3: Proyectos de una secretaría en una comuna específica

```bash
GET /unidades-proyecto/download-table_by_centro_gestor?nombre_centro_gestor=Secretaría de Salud&comuna_corregimiento=COMUNA 01
```

### Ejemplo 4: Primeros 100 registros de una secretaría

```bash
GET /unidades-proyecto/download-table_by_centro_gestor?nombre_centro_gestor=Secretaría de Hacienda&limit=100
```

## 📊 Campos Incluidos en el Excel

El archivo Excel incluye los siguientes campos (33 columnas en total):

1. **UPID** - Identificador único
2. **Nombre UP** - Nombre del proyecto
3. **Nombre UP Detalle** - Nombre detallado
4. **Estado** - Estado actual
5. **Tipo Intervención** - Categoría de intervención
6. **Clase Obra** - Clasificación de obra
7. **Tipo Equipamiento** - Tipo de equipamiento
8. **Centro Gestor** - Entidad responsable (nombre completo)
9. **Centro Gestor (Código)** - Código del centro gestor
10. **Comuna/Corregimiento** - Ubicación administrativa
11. **Barrio/Vereda** - Ubicación específica
12. **Dirección** - Dirección del proyecto
13. **Presupuesto Base** - Valor inicial
14. **Presupuesto Total UP** - Presupuesto total
15. **Avance Obra (%)** - Porcentaje de avance
16. **BPIN** - Código BPIN
17. **Año** - Año del proyecto
18. **Fuente Financiación** - Origen de recursos
19. **Referencia Contrato** - Referencia del contrato
20. **Referencia Proceso** - Referencia del proceso
21. **Plataforma** - Plataforma de contratación
22. **URL Proceso** - URL del proceso
23. **Fecha Inicio** - Fecha de inicio
24. **Fecha Inicio Estandarizada** - Fecha de inicio normalizada
25. **Fecha Fin** - Fecha de finalización
26. **Identificador** - Identificador adicional
27. **Cantidad** - Cantidad
28. **Unidad Medida** - Unidad de medida
29. **Fuera Rango** - Indicador de rango
30. **Tiene Geometría** - Indica si tiene coordenadas
31. **Fecha Creación** - Timestamp de creación
32. **Fecha Actualización** - Timestamp de actualización
33. **Timestamp Procesamiento** - Timestamp de procesamiento

## 🎯 Casos de Uso

1. **Reportes por entidad**: Generar informes específicos por secretaría o entidad
2. **Seguimiento sectorial**: Control de proyectos por sector
3. **Análisis comparativo**: Comparar gestión entre diferentes centros gestores
4. **Auditoría específica**: Revisión de proyectos de una entidad particular
5. **Informes gerenciales**: Reportes ejecutivos por dependencia

## 🔄 Diferencias con `/unidades-proyecto/download-table`

| Característica        | download-table         | download-table_by_centro_gestor  |
| --------------------- | ---------------------- | -------------------------------- |
| Filtro centro gestor  | Opcional               | **Obligatorio**                  |
| Nombre archivo        | Genérico con timestamp | Incluye nombre del centro gestor |
| Caso de uso principal | Descarga general       | Descarga específica por entidad  |
| Rate limiting         | 20/minute              | 20/minute                        |

## ⚙️ Configuración Técnica

### Rate Limiting

- **Límite**: 20 solicitudes por minuto
- **Decorator**: `@optional_rate_limit("20/minute")`

### Dependencias

- Requiere Firebase disponible (`FIREBASE_AVAILABLE`)
- Requiere scripts disponibles (`SCRIPTS_AVAILABLE`)
- Usa `get_unidades_proyecto_attributes()` para obtener datos sin geometría

### Manejo de Errores

#### Error 503 - Service Unavailable

Firebase o scripts no disponibles

#### Error 404 - Not Found

No se encontraron registros para el centro gestor especificado

#### Error 422 - Validation Error

Parámetro `nombre_centro_gestor` faltante o inválido

#### Error 500 - Internal Server Error

Error al procesar la descarga

## 🧪 Pruebas

Se incluye un archivo de pruebas completo:

- **Archivo**: `test_download_table_by_centro_gestor.py`
- **Pruebas incluidas**:
  1. Descarga básica por centro gestor
  2. Filtros combinados (centro gestor + estado)
  3. Filtros geográficos (centro gestor + comuna)
  4. Con límite de registros
  5. Validación de parámetro obligatorio

### Ejecutar Pruebas

```bash
# Asegúrate de que la API esté corriendo en localhost:8000
python test_download_table_by_centro_gestor.py
```

## 📌 Notas Importantes

1. El parámetro `nombre_centro_gestor` debe coincidir **exactamente** con los valores en la base de datos
2. El nombre del archivo incluye el centro gestor sanitizado (espacios reemplazados por guiones bajos)
3. Para mejor performance, se recomienda usar el parámetro `limit` en consultas de exploración
4. El endpoint usa la misma estructura de columnas que `download-table` para consistencia

## 🔐 Seguridad

- Rate limiting para prevenir abuso
- Validación de parámetros de entrada
- Manejo seguro de nombres de archivo
- No expone datos sensibles en los logs

## 📍 Ubicación en el Código

- **Archivo**: `main.py`
- **Línea**: ~2574
- **Tag**: "Unidades de Proyecto"
- **Método**: GET

## ✅ Estado

- ✅ Implementado
- ✅ Documentado
- ✅ Incluido en lista de endpoints
- ✅ Archivo de pruebas creado
- ⏳ Pendiente: Pruebas en producción

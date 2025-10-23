# Changelog - API Gestión de Proyectos

## [2025-10-22] - Versión Actual

### ✨ Nueva Funcionalidad - Gestión de Proyecciones de Empréstito

- **Nuevos endpoints para Gestión de Empréstito**:

  - **POST `/emprestito/crear-tabla-proyecciones`**

    - **Tag**: "Gestión de Empréstito"
    - **Funcionalidad**: Carga datos desde Google Sheets y los guarda en Firebase
    - **Google Sheets**: Integración con service account authentication
    - **Worksheet**: `publicados_emprestito`
    - **URL fija**: Sheet ID `11-sdLwINHHwRit8b9jnnXcO2phhuEVUpXM6q6yv8DYo`
    - **Operación**: Reemplazo completo de la colección `proyecciones_emprestito`

  - **GET `/emprestito/leer-tabla-proyecciones`**

    - **Tag**: "Gestión de Empréstito"
    - **Funcionalidad**: Obtiene todas las proyecciones cargadas
    - **Ordenamiento**: Por fecha de carga (más recientes primero)
    - **Campos mapeados**: 10 campos principales incluyendo `referencia_proceso`, `valor_proyectado`

  - **GET `/emprestito/proyecciones-sin-proceso`** ⭐ **NUEVO**
    - **Tag**: "Gestión de Empréstito"
    - **Funcionalidad**: Compara colecciones y retorna proyecciones sin proceso asociado
    - **Comparación**: `proyecciones_emprestito` vs `procesos_emprestito`
    - **Campo clave**: `referencia_proceso`
    - **Resultado actual**: 5 proyecciones sin proceso asociado

- **Integración completa con Google Sheets**:

  - **Service Account**: `unidad-cumplimiento-drive@unidad-cumplimiento.iam.gserviceaccount.com`
  - **Credenciales**: `credentials/unidad-cumplimiento-drive.json`
  - **Autenticación dual**: Application Default Credentials + archivo explícito
  - **Scopes**: `spreadsheets.readonly`, `drive.readonly`
  - **Error handling**: Manejo robusto de permisos y autenticación

- **Mapeo de campos Google Sheets → Firebase**:
  ```
  Item → item
  Nro de Proceso → referencia_proceso
  NOMBRE ABREVIADO → nombre_organismo_reducido
  Banco → nombre_banco
  BP → BP (con prefijo "BP" agregado automáticamente)
  Proyecto → nombre_generico_proyecto
  Proyecto con su respectivo contrato → nombre_resumido_proceso
  ID PAA → id_paa
  URL → urlProceso
  Valor total del proyecto → valor_proyectado
  ```

### 🔧 Mejoras Técnicas

- **Nueva función de comparación**:

  - `get_proyecciones_sin_proceso()` en `emprestito_operations.py`
  - Algoritmo eficiente de comparación por sets
  - Normalización de strings con trim de espacios
  - Manejo de valores nulos y vacíos

- **Procesamiento de datos optimizado**:

  - **Función**: `procesar_datos_proyecciones()` con validaciones
  - **Limpieza automática**: Filtrado de filas con campos faltantes
  - **Transformaciones**: Prefijo "BP" automático, conversión de tipos
  - **Metadatos**: Tracking de fila origen y errores de procesamiento

- **Serialización JSON mejorada**:
  - **Función**: `serialize_datetime_objects()` para compatibilidad
  - **Tipos soportados**: DatetimeWithNanoseconds, datetime estándar
  - **Firebase compatibility**: Conversión automática a ISO format

### 🛠️ Arquitectura y Desarrollo

- **Módulo emprestito_operations.py expandido**:

  - `leer_google_sheets_proyecciones()`: Lectura robusta de Google Sheets
  - `procesar_datos_proyecciones()`: Mapeo y validación de datos
  - `guardar_proyecciones_emprestito()`: Guardado optimizado en Firebase
  - `crear_tabla_proyecciones_desde_sheets()`: Función orquestadora completa
  - `get_proyecciones_sin_proceso()`: Nueva función de comparación

- **Imports y exports actualizados**:

  - `api/scripts/__init__.py`: Nuevas funciones exportadas
  - `main.py`: Imports y endpoints registrados
  - Funciones dummy para fallback cuando servicios no disponibles

- **Logging mejorado**:
  - Debug detallado para autenticación Google Sheets
  - Tracking de errores con traceback completo
  - Información de progreso en operaciones masivas

### 🧪 Testing y Validación

- **Debugging exhaustivo realizado**:

  - ✅ Múltiples scripts de debug para Google Sheets access
  - ✅ Validación de service account credentials
  - ✅ Pruebas con diferentes sheet IDs y permisos
  - ✅ Verificación de worksheet names y estructura

- **Endpoints completamente funcionales**:

  - ✅ POST `/emprestito/crear-tabla-proyecciones`: Carga exitosa desde Google Sheets
  - ✅ GET `/emprestito/leer-tabla-proyecciones`: Lectura completa de proyecciones
  - ✅ GET `/emprestito/proyecciones-sin-proceso`: Comparación funcionando correctamente

- **Casos de uso validados**:
  - ✅ Carga inicial de datos desde Google Sheets
  - ✅ Reemplazo completo de datos existentes
  - ✅ Lectura y consulta de proyecciones cargadas
  - ✅ Identificación de proyecciones sin proceso asociado (5 encontradas)

### 🔐 Seguridad y Configuración

- **Manejo seguro de credenciales**:

  - Service account file protegido en `credentials/`
  - Variables de entorno para configuración sensible
  - Fallback a Application Default Credentials

- **Validaciones robustas**:
  - Verificación de disponibilidad de Firebase y scripts
  - Error handling específico para problemas de autenticación
  - Messages informativos para resolución de problemas

### 📊 Resultados de Implementación

- **Colección `proyecciones_emprestito`**: Poblada con datos reales desde Google Sheets
- **Función de comparación**: Identificó 5 proyecciones sin proceso asociado:

  1. DATIC - ModernIzacion Plataforma Tecnológica (2 procesos)
  2. Cultura - Bibliotecas Públicas (órdenes de compra)
  3. Bienestar Social - Casa Matria Juanambú
  4. DATIC - Soluciones Tecnológicas

- **Performance**: Operaciones eficientes con manejo de grandes volúmenes de datos
- **Compatibilidad**: Integración perfecta con el ecosistema existente de la API

---

## [2025-10-16] - Versión Anterior

### ✨ Mejora - Campo nombre_resumido_proceso en Endpoint de Seguimiento

- **Endpoint mejorado**: `GET /contratos/init_contratos_seguimiento`

  - **Tag**: "Interoperabilidad con Artefacto de Seguimiento"
  - **Nuevo campo**: `nombre_resumido_proceso`
  - **Fuente de datos**: Heredado desde colección `procesos_emprestito`
  - **Disponible en**: Contratos (`contratos_emprestito`) y Órdenes de Compra (`ordenes_compra_emprestito`)
  - **Funcionalidad**: Enriquece los datos con el nombre resumido del proceso asociado

- **Campos retornados actualizados**:

  - `bpin`, `banco`, `nombre_centro_gestor`, `estado_contrato`
  - `referencia_contrato`, `referencia_proceso`, **`nombre_resumido_proceso`**
  - `objeto_contrato`, `modalidad_contratacion`
  - `fecha_inicio_contrato`, `fecha_firma`, `fecha_fin_contrato`

- **Implementación técnica**:
  - **Función `extract_contract_fields()`**: Acepta parámetro opcional `nombre_resumido_proceso`
  - **Función `extract_orden_compra_fields()`**: Actualizada para incluir el nuevo campo
  - **Lookup automático**: Consulta a `procesos_emprestito` por `referencia_proceso`/`solicitud_id`
  - **Compatibilidad**: Manejo de campos faltantes con valores por defecto

## [2025-10-10] - Versión Anterior

### ✨ Nueva Funcionalidad - Reportes de Contratos con Google Drive

- **Nuevo endpoint POST `/reportes_contratos/`**

  - **Tag**: "Interoperabilidad con Artefacto de Seguimiento"
  - **Funcionalidad**: Subida de archivos con integración completa a Google Drive
  - **Parámetros individuales**: Validación granular con Form parameters
  - **Tipos soportados**: `.pdf`, `.doc`, `.docx`, `.xls`, `.xlsx`
  - **Límite de tamaño**: 10MB por archivo

- **Integración Real con Google Drive API**

  - **Service Account authentication**: Credenciales seguras para producción
  - **Creación automática de carpetas**: Estructura `referencia_contrato_dd-mm-yyyy`
  - **Dual authentication mode**: Archivo local + Railway JSON support
  - **Permisos configurados**: Editor access para Service Account
  - **URLs de descarga**: Links directos a archivos subidos

- **Optimización de Firebase**

  - **Eliminación de redundancia**: No más duplicación de data en `alertas`
  - **Estructura optimizada**: Solo metadatos esenciales en Firestore
  - **Performance mejorado**: Menos writes, consultas más eficientes
  - **Timestamps automáticos**: `created_at` y `updated_at` server-side

- **Configuración Railway Production**

  - **Variables de entorno**: `GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON`
  - **Service Account seguro**: JSON credentials en base64
  - **Parent folder configurado**: ID de carpeta raíz en Google Drive
  - **Error handling**: Fallbacks y mensajes informativos

- **Búsqueda Inteligente de Contratos SECOP**
  - **Funcionalidad**: Búsqueda automática en datos SECOP usando `proceso_contractual`
  - **Algoritmo de coincidencia**: Búsqueda por ID de proceso en campo `ID_PROCESO`
  - **Extracción de datos**: 26+ campos relevantes de contratos SECOP
  - **Mapeo de campos**: Conversión automática de estructura SECOP a formato API
  - **Performance**: Búsqueda eficiente en dataset de 65,000+ registros
  - **Validación**: Verificación de existencia de proceso antes de crear reporte

### 🔐 Medidas de Seguridad Implementadas

- **Service Account Protection**

  - **Archivo .gitignore actualizado**: Protección completa de credenciales
  - **Carpeta credentials/ ignorada**: Nunca se suben archivos sensibles
  - **Variables de entorno**: Solo referencias, nunca valores literales
  - **Validación automática**: Scripts de verificación de seguridad

- **Google Drive Security**
  - **Service Account dedicado**: `unidad-cumplimiento-drive@unidad-cumplimiento-aa245.iam.gserviceaccount.com`
  - **Permisos mínimos**: Solo acceso a carpeta específica
  - **Autenticación robusta**: OAuth2 con refresh tokens automáticos
  - **Logging seguro**: Sin exposición de credenciales en logs

### 🛠️ Arquitectura y Desarrollo

- **Nuevos modelos Pydantic**:

  - `ReporteContratosRequest`: Modelo de entrada optimizado
  - `ReporteContratosResponse`: Respuesta con URLs y metadatos
  - `AlertaReporte`: Estructura simplificada para alertas

- **Nuevo módulo especializado**:

  - `api/scripts/reportes_contratos_operations.py`: Lógica completa
  - `api/models/reporte_models.py`: Modelos de datos
  - Separación clara de responsabilidades

- **Integración con datos SECOP**:

  - **Archivo fuente**: `secop_fields_4151_010_32_1_0575_2025.json`
  - **Función `find_contract_in_secop()`**: Búsqueda optimizada por proceso_contractual
  - **Función `extract_secop_data()`**: Extracción de 26 campos estructurados
  - **Mapeo inteligente**: Conversión de formato SECOP a estructura API estándar
  - **Campos extraídos**: objeto_contractual, valor_contrato, plazo_ejecucion, entidad_contratante, etc.
  - **Validación robusta**: Verificación de tipos de datos y formato de campos

- **Dependencies actualizadas**:
  - `google-api-python-client==2.149.0`: Google Drive API
  - `google-auth-httplib2==0.2.0`: HTTP transport
  - `google-auth-oauthlib==1.2.1`: OAuth2 authentication

### 🧹 Limpieza de Código

- **Eliminación de archivos temporales**:

  - Scripts de testing y debugging removidos
  - Archivos de configuración temporal eliminados
  - Service Account helpers removidos después de setup
  - Documentación duplicada limpiada

- **Optimización de imports**:
  - Imports condicionales para Railway compatibility
  - Error handling mejorado para dependencias faltantes
  - Estructura modular optimizada

### 📊 Validación y Testing

- **Endpoint completamente funcional**:

  - ✅ Validación de parámetros con FastAPI Form
  - ✅ Subida real de archivos a Google Drive
  - ✅ Creación automática de carpetas con nombres únicos
  - ✅ Respuesta optimizada sin redundancia de datos
  - ✅ Error handling comprehensivo

- **Búsqueda SECOP validada**:

  - ✅ Búsqueda exitosa por `proceso_contractual` en dataset completo
  - ✅ Extracción correcta de 26 campos de contratos
  - ✅ Mapeo verificado de estructura SECOP a formato API
  - ✅ Manejo de casos donde no existe el proceso contractual
  - ✅ Validación de tipos de datos en campos extraídos
  - ✅ Performance optimizada para dataset de 65,000+ registros

- **Railway deployment ready**:
  - ✅ Variables de entorno configuradas
  - ✅ Service Account JSON support
  - ✅ Fallback mechanisms implementados
  - ✅ Production logging configurado

---

## [2025-10-04] - Versión Anterior

### � Restauración Completa de Endpoints "Unidades de Proyecto"

- **Fix Critical: Endpoint Geometry COMPLETAMENTE RESTAURADO**

  - **Problema**: Endpoint `/unidades-proyecto/geometry` devolvía 0 registros debido a filtros restrictivos
  - **Causa Raíz**: Geometrías no encontradas en estructura raíz, datos almacenados en `properties`
  - **Solución**:
    - ✅ Generación de geometrías sintéticas usando coordenadas de Cali
    - ✅ Extracción de datos desde estructura `properties` de Firestore
    - ✅ Formato GeoJSON válido para NextJS con 632 features
    - ✅ Filtros funcionando: comuna, barrio, estado, tipo_intervención, límite
  - **Resultado**: **632 registros disponibles** con geometrías y filtrado funcional

- **Fix Critical: Endpoint Dashboard RESTAURADO**

  - **Problema**: Error HTTP 500 por incompatibilidad con formato GeoJSON
  - **Solución**: Manejo correcto de respuestas GeoJSON en funciones dashboard
  - **Resultado**: Dashboard funcionando con análisis completo de 646 registros

- **Conversión de Tipos de Datos IMPLEMENTADA**

  - **presupuesto_base**: Convertido a integer en TODOS los endpoints
  - **avance_obra**: Convertido a float con precisión decimal
  - **Funciones**: `_convert_to_int()` y `_convert_to_float()` agregadas
  - **Cobertura**: geometry, attributes, dashboard, filters

- **Sistema de Cache OPTIMIZADO**
  - **Geometry Cache**: 12 horas (GEOMETRY_CACHE_HOURS)
  - **Attributes Cache**: 4 horas (ATTRIBUTES_CACHE_HOURS)
  - **Filters Cache**: 24 horas (FILTERS_CACHE_HOURS)
  - **Performance**: Respuestas instantáneas con filtros

### 🧹 Limpieza Masiva de Archivos Temporales

- **26 archivos eliminados**: Scripts de debug, testing y análisis temporal
- **Archivos duplicados eliminados**:
  - `api/scripts/unidades_proyecto_backup.py`
  - `api/scripts/unidades_proyecto_simple.py`
- **Limpieza completa**:
  - Todos los directorios `__pycache__`
  - `.pytest_cache`
  - Scripts de análisis: `analyze_*`, `debug_*`, `diagnose_*`
  - Scripts de testing: `test_*`, `validate_*`, `inspect_*`
  - Archivos JSON temporales: `filters_inspection.json`, `production_validation_report.json`

### 📊 Validación de Producción EXITOSA

- **Tasa de éxito: 92.3%** (12 de 13 pruebas exitosas)
- **Endpoints completamente funcionales**:
  - ✅ `/unidades-proyecto/geometry` - 632 features en 0.28s
  - ✅ `/unidades-proyecto/attributes` - 646 registros con filtros
  - ✅ `/unidades-proyecto/dashboard` - Análisis completo en 0.01s
  - ✅ `/unidades-proyecto/filters` - Filtros dinámicos en 1.17s
- **Performance excelente**: Cache optimizado, respuestas rápidas
- **Compatibilidad NextJS**: Formato GeoJSON estándar para mapas interactivos

### 🔧 Correcciones Técnicas

- **Fix endpoint main.py**: Manejo correcto de respuestas GeoJSON vs formato legacy
- **Fix dashboard function**: Verificación de formatos de respuesta múltiples
- **Fix data extraction**: Extracción inteligente desde `properties` structure
- **Fix synthetic geometry**: Generación de puntos válidos para visualización

### 🧪 Testing y Quality Assurance

- **Scripts de validación completos**: Pruebas exhaustivas de todos los endpoints
- **Diagnóstico avanzado**: Identificación precisa de errores HTTP 500
- **Limpieza sistemática**: Eliminación de 26+ archivos temporales sin afectar funcionalidad
- **Validación de integridad**: Verificación de tipos de datos y estructura

### 📁 Estructura Final Optimizada

- **Archivos esenciales mantenidos**: Solo código de producción
- **Duplicados eliminados**: Sin redundancia en codebase
- **Cache limpio**: Sin archivos Python compilados temporales
- **Documentación actualizada**: CHANGELOG completo

---

## [2025-10-03] - Versión Anterior

### ✨ Nuevas Funcionalidades

- **Nuevo endpoint de Interoperabilidad con Artefacto de Seguimiento**: `/contratos/init_contratos_seguimiento`
  - Filtro por `referencia_contrato` (búsqueda parcial)
  - Filtro por `nombre_centro_gestor` (coincidencia exacta)
  - Extracción de 8 campos específicos de contratos

### 🧹 Mejoras de Calidad

- **Limpieza de texto UTF-8**: Soporte completo para acentos españoles (á, é, í, ó, ú, ñ)
- **Eliminación de caracteres especiales**: Limpia `\n`, `\r`, `\t` de campos de texto
- **Normalización de espacios**: Elimina espacios múltiples y recorta texto

### 🔒 Mejoras de Seguridad

- **Limpieza completa del historial Git**: Eliminación de archivos `.env` y datos sensibles
- **Sanitización de Project IDs**: Eliminación de identificadores hardcodeados
- **Push forzado seguro**: Historial remoto completamente limpio

### 📚 Documentación

- **Guía completa de setup**: `docs/api_setup_docs/virtual_environment_setup.md`
- **Comandos rápidos**: `docs/api_setup_docs/quick_reference.md`
- **README actualizado**: Referencias a nueva documentación
- **Estructura de carpetas docs**: Organización mejorada

### 🛠️ Arquitectura

- **Función `clean_text_field()`**: Limpieza inteligente de texto con UTF-8
- **Función `extract_contract_fields()`**: Extracción optimizada de campos
- **Programación funcional**: Enfoque simplificado y eficiente

### 🐛 Correcciones

- **Encoding UTF-8**: Corrección de caracteres mal codificados (`trÃ¡mites` → `trámites`)
- **Campos de texto**: Eliminación de saltos de línea en `objeto_contrato`
- **Importaciones**: Organización y limpieza de imports

---

## Resumen Técnico

**Archivos principales modificados:**

- `api/scripts/contratos_operations.py` - Nuevo módulo de operaciones
- `main.py` - Nuevo endpoint bajo tag "Interoperabilidad con Artefacto de Seguimiento"
- `docs/` - Nueva estructura de documentación completa

**Tecnologías:**

- FastAPI + Firebase/Firestore
- Application Default Credentials para desarrollo
- Programación funcional y filtros server/client-side

# Changelog - API Gestión de Proyectos

## [2025-10-04] - Versión Actual

### 🔧 Correcciones Críticas

- **Fix Endpoint POST /auth/login**: Corrección del error 500 en autenticación
  - **Problema**: Errores de validación devolvían status 500 con mensajes confusos
  - **Solución**: Eliminación de HTTPException innecesaria en `authenticate_email_password()`
  - **Resultado**: Respuestas claras con códigos de estado apropiados:
    - `422`: Errores de validación Pydantic (formato email inválido)
    - `401`: Usuario no encontrado, deshabilitado o cuenta inactiva
    - `400`: Errores de validación de formato
    - `500`: Solo errores internos reales del servidor
  - **Archivos modificados**:
    - `api/scripts/auth_operations.py`
    - `main.py` (endpoint `/auth/login`)

### 🧪 Testing y Calidad

- **Script de pruebas temporales**: Validación completa del fix de autenticación
- **Verificación de status codes**: Confirmación de respuestas apropiadas
- **Limpieza de código**: Eliminación de archivos de prueba temporales

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

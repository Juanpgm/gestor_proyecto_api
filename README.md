# API - Unidad de Cumplimiento V - 3.0.0

## 🚀 Descripción

API completamente refactorizada usando **programación funcional** para la gestión de datos municipales. La API se conecta a una base de datos PostgreSQL con 11 tablas de datos de proyectos, contratación pública, ejecución presupuestal y gestión de usuarios.

## ✨ Características Principales

- **Arquitectura Funcional**: Código refactorizado usando paradigmas de programación funcional
- **Endpoint Único**: Un solo endpoint optimizado que proporciona estadísticas completas de la base de datos
- **Conexión Optimizada**: Configuración de base de datos con cache y pooling de conexiones
- **Código Limpio**: Eliminación de duplicaciones y código obsoleto
- **Documentación Automática**: Swagger UI y ReDoc integrados

## 🛠️ Estructura del Proyecto

```
gestor_proyecto_api/
├── main.py                 # API principal
├── config.py              # Configuración funcional de base de datos
├── requirements.txt       # Dependencias optimizadas
├── api/
│   ├── __init__.py        # Módulo API
│   └── models.py          # Modelos de datos (11 tablas)
├── env/                   # Entorno virtual
└── README.md             # Esta documentación
```

## 📊 Modelos de Datos

La API gestiona 11 tablas con datos municipales:

### Proyectos y Equipamientos

1. **unidad_proyecto** - Unidades de proyecto de infraestructura municipal
2. **datos_caracteristicos_proyecto** - Datos característicos y descriptivos
3. **ejecucion_presupuestal** - Ejecución presupuestal mensual
4. **movimiento_presupuestal** - Movimientos y modificaciones presupuestales

### Contratación Pública DACP

5. **proceso_contratacion_dacp** - Procesos de contratación (SECOP II, etc.)
6. **orden_compra_dacp** - Órdenes de compra (TVEC, etc.)
7. **paa_dacp** - Plan Anual de Adquisiciones
8. **emp_paa_dacp** - Plan Anual de Adquisiciones - Empréstito

### Gestión de Usuarios

9. **usuarios** - Usuarios del sistema
10. **roles** - Roles y niveles de acceso
11. **tokens_seguridad** - Tokens de seguridad y autenticación

## 🔧 Instalación y Configuración

### 1. Activar Entorno Virtual

```powershell
.\env\Scripts\Activate.ps1
```

### 2. Instalar Dependencias

```powershell
pip install -r requirements.txt
```

### 3. Configurar Variables de Entorno

Crear archivo `.env.local` con:

```env
ENVIRONMENT=local
DB_HOST=localhost
DB_PORT=5432
DB_NAME=tu_base_datos
DB_USER=tu_usuario
DB_PASSWORD=tu_contraseña
```

### 4. Ejecutar la API

```powershell
python main.py
```

O usando uvicorn:

```powershell
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

## 📡 Endpoints Disponibles

### Endpoint Principal

- **GET `/database/summary`** - Resumen completo de todas las tablas con:
  - Conteo de registros por tabla
  - Estadísticas básicas (promedio, mínimo, máximo) de columnas numéricas
  - Descripción de cada tabla
  - Totales generales

### Endpoints de Sistema

- **GET `/`** - Información general de la API
- **GET `/health`** - Estado de salud de la API y base de datos
- **GET `/docs`** - Documentación Swagger UI
- **GET `/redoc`** - Documentación ReDoc

## 📈 Ejemplo de Respuesta

```json
{
  "database_overview": {
    "api_info": {
      "name": "API Gestor Municipal",
      "version": "3.0.0",
      "environment": "development",
      "timestamp": "2024-01-21T10:30:00"
    },
    "database_info": {
      "connected": true,
      "total_tables": 11,
      "available_tables": ["unidad_proyecto", "datos_caracteristicos_proyecto", ...]
    }
  },
  "total_records": 150000,
  "tables": {
    "unidad_proyecto": {
      "description": "Unidades de proyecto - Equipamientos de infraestructura municipal",
      "statistics": {
        "count": 5420,
        "presupuesto_base_avg": 450000000.50,
        "presupuesto_base_min": 100000.00,
        "presupuesto_base_max": 15000000000.00
      }
    }
  },
  "summary": {
    "tables_analyzed": 11,
    "tables_with_data": 8,
    "total_records_all_tables": 150000
  }
}
```

## 🎯 Características Técnicas

### Programación Funcional

- **Funciones puras**: Sin efectos secundarios
- **Inmutabilidad**: Estructuras de datos inmutables
- **Funciones de orden superior**: `reduce`, `map`, `filter`
- **Cache**: Uso de `@lru_cache` para optimización
- **Composición**: Funciones pequeñas y componibles

### Optimizaciones

- **Pooling de conexiones**: Configuración optimizada de SQLAlchemy
- **Cache de configuración**: Variables y configuraciones con cache
- **Manejo de errores**: Exceptions centralizadas
- **Validación automática**: Tipos con Pydantic

### Seguridad

- **Validación de entrada**: Sanitización automática
- **Manejo seguro de consultas**: Uso de `text()` para SQL
- **Conexiones seguras**: Pool de conexiones controlado

## 🚀 Mejoras Implementadas

1. **Eliminación de código duplicado**: Refactorización completa
2. **Arquitectura simplificada**: De múltiples routers a endpoint único optimizado
3. **Conexión robusta**: Manejo de errores y reconexión automática
4. **Documentación automática**: OpenAPI/Swagger integrado
5. **Configuración flexible**: Soporte para múltiples entornos
6. **Performance optimizada**: Cache y pooling de conexiones

## 📝 Comandos Útiles

```powershell
# Activar entorno
.\env\Scripts\Activate.ps1

# Ejecutar API
python main.py

# Ejecutar con uvicorn
uvicorn main:app --reload

# Probar conexión
python -c "from config import test_database_connection; print(test_database_connection())"

# Verificar modelos
python -c "from api.models import Base; print('Modelos OK')"
```

## 🌐 URLs de Acceso

- **API**: http://localhost:8000
- **Documentación**: http://localhost:8001/docs
- **ReDoc**: http://localhost:8000/redoc
- **Health Check**: http://localhost:8000/health
- **Resumen DB**: http://localhost:8000/database/summary

---

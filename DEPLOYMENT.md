# 🚀 Guía de Despliegue - API Gestor de Proyectos

Esta guía te ayudará a desplegar la API tanto en un entorno local como en Railway.

## 📋 Requisitos Previos

### Para desarrollo local:

- Python 3.8+
- PostgreSQL instalado y configurado
- PowerShell (Windows) o Bash (Unix/Linux/macOS)

### Para Railway:

- Cuenta en [Railway](https://railway.app)
- Base de datos PostgreSQL configurada en Railway
- Variable `DATABASE_URL` obtenida de Railway

## 🏠 Despliegue Local

### 1. Configuración de Base de Datos Local

Asegúrate de tener PostgreSQL ejecutándose localmente con:

- Host: `localhost`
- Puerto: `5432`
- Base de datos: `dev`
- Usuario: `postgres`
- Contraseña: `root`

### 2. Configuración del Entorno

El archivo `.env.local` ya está configurado con los valores por defecto:

```env
DB_HOST=localhost
DB_PORT=5432
DB_NAME=dev
DB_USER=postgres
DB_PASSWORD=root
DB_SCHEMA=public
APP_ENV=development
```

### 3. Ejecutar Localmente

#### En Windows (PowerShell):

```powershell
# Ejecutar con configuración básica
.\deploy_local.ps1

# Ejecutar en puerto personalizado con reload
.\deploy_local.ps1 -Port 8080 -Reload

# Ejecutar en modo debug
.\deploy_local.ps1 -Debug -Reload
```

#### En Unix/Linux/macOS:

```bash
# Hacer ejecutable el script
chmod +x deploy_local.sh

# Ejecutar con configuración básica
./deploy_local.sh

# Ejecutar en puerto personalizado con reload
./deploy_local.sh 8080 true

# Ejecutar en modo debug
./deploy_local.sh 8001 true true
```

### 4. URLs de Acceso Local

- **API**: http://127.0.0.1:8001
- **Documentación**: http://127.0.0.1:8001/docs
- **Health Check**: http://127.0.0.1:8001/health

## 🚂 Despliegue en Railway

### 1. Configuración de Railway

1. Crea un proyecto en Railway
2. Añade una base de datos PostgreSQL
3. Copia la `DATABASE_URL` desde el dashboard de Railway
4. Actualiza el archivo `.env.railway` con tu `DATABASE_URL`

### 2. Configuración del Archivo .env.railway

El archivo `.env.railway` no necesita contener la `DATABASE_URL` porque Railway la proporciona automáticamente como variable de entorno:

```env
# Configuración del logging
LOG_LEVEL=INFO
LOG_FILE=logs/app.log

# Configuración de la aplicación
APP_NAME=API Gestor de Proyectos - Production
APP_VERSION=1.0.0
APP_ENV=production

# Configuración de Conexión para producción
CONNECTION_TIMEOUT=30
POOL_SIZE=10 
MAX_OVERFLOW=20

# Configuración adicional para Railway
PORT=8000
HOST=0.0.0.0
```

**Importante**: Railway inyecta automáticamente la variable `DATABASE_URL` cuando despliegas.

### 3. Test de Configuración Railway

#### En Windows (PowerShell):

```powershell
# Verificar configuración antes del despliegue
.\deploy_railway.ps1 -Test
```

#### En Unix/Linux/macOS:

```bash
# Hacer ejecutable el script
chmod +x deploy_railway.sh

# Verificar configuración antes del despliegue
./deploy_railway.sh 8000 0.0.0.0 true
```

### 4. Desplegar en Railway

#### Opción A: Usar scripts locales para prueba

#### En Windows (PowerShell):

```powershell
# Ejecutar servidor para Railway
.\deploy_railway.ps1

# Ejecutar en puerto personalizado
.\deploy_railway.ps1 -Port 8080
```

#### En Unix/Linux/macOS:

```bash
# Ejecutar servidor para Railway
./deploy_railway.sh

# Ejecutar en puerto personalizado
./deploy_railway.sh 8080
```

#### Opción B: Despliegue directo en Railway

1. **Conecta tu repositorio** a Railway desde el dashboard
2. **Configura las variables de entorno** en Railway:
   ```
   ENVIRONMENT=railway
   ```
3. **Railway proporcionará automáticamente** la `DATABASE_URL`
4. **Railway detectará automáticamente** el `Procfile` y desplegará

#### Opción C: Inicializar base de datos

Para inicializar las tablas en Railway:

```powershell
# Inicializar con variable de entorno de Railway
.\init_database.ps1 -Railway

# O con URL específica para pruebas
.\init_database.ps1 -Railway -DatabaseUrl "postgresql://user:pass@host:port/db"
```

### 5. Archivos de Configuración para Railway

El proyecto incluye:

- **`Procfile`**: Define el comando de inicio para Railway
- **`railway.toml`**: Configuración específica de Railway
- **`.env.railway`**: Variables de entorno para producción

## 🔧 Estructura de Archivos de Configuración

```
gestor_proyecto_api/
├── .env.local          # Variables para desarrollo local
├── .env.railway        # Variables para Railway
├── config.py           # Configuración adaptativa según entorno
├── deploy_local.ps1    # Script despliegue local (Windows)
├── deploy_local.sh     # Script despliegue local (Unix/Linux/macOS)
├── deploy_railway.ps1  # Script despliegue Railway (Windows)
├── deploy_railway.sh   # Script despliegue Railway (Unix/Linux/macOS)
├── Procfile            # Comando de inicio para Railway
├── railway.toml        # Configuración Railway
└── requirements.txt    # Dependencias Python
```

## 🌍 Variables de Entorno

### Variable ENVIRONMENT

La aplicación detecta automáticamente el entorno usando la variable `ENVIRONMENT`:

- `ENVIRONMENT=local` → Usa `.env.local`
- `ENVIRONMENT=railway` → Usa `.env.railway`
- Sin definir → Usa `.env` (fallback)

### Variables por Entorno

| Variable       | Local       | Railway    | Descripción                       |
| -------------- | ----------- | ---------- | --------------------------------- |
| `DB_HOST`      | ✅          | ❌         | Host de base de datos local       |
| `DB_PORT`      | ✅          | ❌         | Puerto de base de datos local     |
| `DB_NAME`      | ✅          | ❌         | Nombre de base de datos local     |
| `DB_USER`      | ✅          | ❌         | Usuario de base de datos local    |
| `DB_PASSWORD`  | ✅          | ❌         | Contraseña de base de datos local |
| `DATABASE_URL` | ❌          | ✅         | URL completa de Railway           |
| `APP_ENV`      | development | production | Modo de la aplicación             |
| `LOG_LEVEL`    | DEBUG       | INFO       | Nivel de logging                  |
| `PORT`         | 8001        | 8000       | Puerto del servidor               |

## 🧪 Verificación del Despliegue

### Health Check

Ambos entornos exponen un endpoint de salud:

```bash
# Local
curl http://127.0.0.1:8001/health

# Railway (reemplaza con tu URL)
curl https://tu-app.railway.app/health
```

### Respuesta esperada:

```json
{
  "status": "healthy",
  "service": "API Gestor de Proyectos",
  "version": "1.0.0",
  "database": "connected",
  "timestamp": "2025-09-17T..."
}
```

## 📝 Comandos Útiles

### Crear entorno virtual:

```bash
python -m venv env
```

### Activar entorno virtual:

```bash
# Windows
.\env\Scripts\Activate.ps1

# Unix/Linux/macOS
source env/bin/activate
```

### Instalar dependencias:

```bash
pip install -r requirements.txt
```

### Ejecutar directamente con uvicorn:

```bash
# Local
ENVIRONMENT=local uvicorn main:app --host 127.0.0.1 --port 8001 --reload

# Railway (simulación local)
ENVIRONMENT=railway uvicorn main:app --host 0.0.0.0 --port 8000
```

## 🐛 Solución de Problemas

### Error de conexión a base de datos local

1. Verifica que PostgreSQL esté ejecutándose
2. Confirma las credenciales en `.env.local`
3. Crea la base de datos `dev` si no existe

### Error de conexión a Railway

1. Verifica que la `DATABASE_URL` en `.env.railway` sea correcta
2. Confirma que la base de datos Railway esté activa
3. Ejecuta el test: `.\deploy_railway.ps1 -Test`

### Variables de entorno no cargadas

1. Verifica que el archivo `.env.*` existe
2. Confirma que `ENVIRONMENT` esté configurada correctamente
3. Revisa que no haya espacios extra en las variables

## 🚀 Próximos Pasos

1. **Configurar CI/CD**: Integra Railway con GitHub Actions
2. **Monitoreo**: Configura logging y métricas en Railway
3. **Seguridad**: Implementa HTTPS y autenticación
4. **Backup**: Configura respaldos automáticos de la base de datos

---

**¿Necesitas ayuda?** Revisa los logs de los scripts o contacta al equipo de desarrollo.

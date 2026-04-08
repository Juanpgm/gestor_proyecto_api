# 🐍 Configuración de Entorno Virtual para API de Gestión de Proyectos

## 📋 Tabla de Contenidos

1. [Prerrequisitos](#-prerrequisitos)
2. [Configuración del Entorno Virtual](#-configuración-del-entorno-virtual)
3. [Configuración de Firebase](#-configuración-de-firebase)
4. [Configuración de Variables de Entorno](#-configuración-de-variables-de-entorno)
5. [Instalación de Dependencias](#-instalación-de-dependencias)
6. [Pruebas de Conexión](#-pruebas-de-conexión)
7. [Ejecución de la API](#-ejecución-de-la-api)
8. [Solución de Problemas](#-solución-de-problemas)

---

## 🔧 Prerrequisitos

### Software Requerido

- **Python 3.8+** ([Descargar](https://www.python.org/downloads/))
- **Git** ([Descargar](https://git-scm.com/downloads))
- **Google Cloud CLI** ([Descargar](https://cloud.google.com/sdk/docs/install))
- **Firebase CLI** ([Instalar](https://firebase.google.com/docs/cli#install-cli-windows))

### Verificar Instalación

```bash
# Verificar Python
python --version
# Debería mostrar: Python 3.8.x o superior

# Verificar pip
pip --version

# Verificar Git
git --version

# Verificar Google Cloud CLI
gcloud --version

# Verificar Firebase CLI
firebase --version
```

---

## 🐍 Configuración del Entorno Virtual

### 1. Clonar el Repositorio

```bash
git clone https://github.com/Juanpgm/gestor_proyecto_api.git
cd gestor_proyecto_api
```

### 2. Crear Entorno Virtual

#### En Windows (PowerShell/CMD)

```powershell
# Crear entorno virtual
python -m venv venv_api

# Activar entorno virtual
.\venv_api\Scripts\Activate.ps1
# O en CMD: .\venv_api\Scripts\activate.bat
```

#### En macOS/Linux

```bash
# Crear entorno virtual
python3 -m venv venv_api

# Activar entorno virtual
source venv_api/bin/activate
```

### 3. Verificar Activación

```bash
# El prompt debería mostrar (venv_api)
which python  # En Windows: where python
# Debería mostrar la ruta del entorno virtual
```

---

## 🔥 Configuración de Firebase

### 1. Crear Proyecto Firebase

1. Ve a [Firebase Console](https://console.firebase.google.com/)
2. Clic en **"Crear un proyecto"**
3. Nombra tu proyecto (ej: `mi-api-pruebas`)
4. Habilita Google Analytics (opcional)
5. Clic en **"Crear proyecto"**

### 2. Configurar Firestore Database

1. En el panel de Firebase, ve a **"Firestore Database"**
2. Clic en **"Crear base de datos"**
3. Selecciona **"Comenzar en modo de prueba"**
4. Elige una ubicación (ej: `us-central1`)
5. Clic en **"Listo"**

### 3. Crear Colecciones de Prueba

En Firestore, crea estas colecciones con documentos de ejemplo:

#### Colección: `contratos_emprestito`

```json
{
  "id": "contrato_001",
  "registro_origen": {
    "bpin": "2024001000001",
    "banco": "Banco de la República",
    "nombre_centro_gestor": "Departamento Administrativo de Tecnologías de la Información y las Comunicaciones",
    "estado_contrato": "Activo",
    "referencia_contrato": "CONT-2024-001",
    "referencia_proceso": "PROC-2024-001",
    "objeto_contrato": "Desarrollo de sistema de gestión",
    "modalidad_contratacion": "Contratación directa"
  }
}
```

#### Colección: `unidades_proyecto` (opcional)

```json
{
  "id": "unidad_001",
  "nombre": "Unidad de Desarrollo",
  "descripcion": "Unidad encargada del desarrollo de software",
  "activa": true
}
```

---

## 🔐 Configuración de Variables de Entorno

### 1. Copiar Template de Configuración

```bash
# Copiar el archivo de ejemplo
cp .env.example .env
```

### 2. Obtener Credenciales de Firebase

#### Opción A: Application Default Credentials (Recomendado para desarrollo)

```bash
# Autenticarse con Google Cloud
gcloud auth login

# Configurar proyecto predeterminado
gcloud config set project TU_PROJECT_ID

# Configurar Application Default Credentials
gcloud auth application-default login
```

#### Opción B: Service Account Key

1. En Firebase Console, ve a **"Configuración del proyecto"** ⚙️
2. Pestaña **"Cuentas de servicio"**
3. Clic en **"Generar nueva clave privada"**
4. Descargar el archivo JSON
5. Convertir a Base64:

```bash
# En Windows (PowerShell)
$json = Get-Content "path/to/serviceAccountKey.json" -Raw
$bytes = [System.Text.Encoding]::UTF8.GetBytes($json)
$base64 = [Convert]::ToBase64String($bytes)
Write-Output $base64

# En macOS/Linux
base64 -i serviceAccountKey.json -o serviceAccountKey.base64
```

### 3. Configurar Archivo .env

Edita el archivo `.env` con tus valores:

```env
# FIREBASE CONFIGURATION
FIREBASE_PROJECT_ID=tu-proyecto-firebase-id
GOOGLE_CLOUD_PROJECT=tu-proyecto-firebase-id

# AUTHENTICATION (Elige UNA opción)
# Opción 1: Application Default Credentials (ya configurado con gcloud)
# No necesitas configurar nada más

# Opción 2: Service Account Key
# FIREBASE_SERVICE_ACCOUNT_KEY=tu-clave-base64-aqui

# FIRESTORE SETTINGS
FIRESTORE_BATCH_SIZE=500
FIRESTORE_TIMEOUT=30

# API SETTINGS
PORT=8000
ENVIRONMENT=development
```

### 4. Verificar Configuración

```bash
# Verificar que las variables se cargan correctamente
python -c "import os; print('Project ID:', os.getenv('FIREBASE_PROJECT_ID', 'NO CONFIGURADO'))"
```

---

## 📦 Instalación de Dependencias

### 1. Actualizar pip

```bash
python -m pip install --upgrade pip
```

### 2. Instalar Dependencias

```bash
pip install -r requirements.txt
```

### 3. Verificar Instalación

```bash
pip list | grep -E "(fastapi|firebase|google)"
```

Deberías ver algo como:

```
fastapi                   0.104.1
firebase-admin            6.2.0
google-cloud-firestore    2.11.1
google-auth               2.23.3
```

---

## 🧪 Pruebas de Conexión

### 1. Probar Conexión a Firebase

```bash
python -c "
from database.firebase_config import FirebaseManager
status = FirebaseManager.test_connection()
print('Status:', status)
"
```

**Salida esperada:**

```json
{
  "connected": true,
  "message": "Connected to tu-proyecto-id",
  "collections_found": 2,
  "environment": "local"
}
```

### 2. Probar Configuración de API

```bash
python -c "
import os
from database.firebase_config import PROJECT_ID
print(f'Project ID configurado: {PROJECT_ID}')
print(f'Puerto: {os.getenv(\"PORT\", \"8000\")}')
print(f'Entorno: {os.getenv(\"ENVIRONMENT\", \"development\")}')
"
```

---

## 🚀 Ejecución de la API

### 1. Iniciar Servidor

```bash
python main.py
```

**Salida esperada:**

```
INFO:     Started server process [12345]
INFO:     Waiting for application startup.
🚀 Initializing Firebase: tu-proyecto-id
💻 Local environment - using Application Default Credentials
✅ Firebase initialized with Application Default Credentials
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000
```

### 2. Verificar Estado de la API

Abre otro terminal y ejecuta:

```bash
curl http://localhost:8000/health
```

**Respuesta esperada:**

```json
{
  "status": "healthy",
  "timestamp": "2025-10-03T15:30:00.000000",
  "services": {
    "api": "running",
    "firebase": {
      "connected": true,
      "message": "Connected to tu-proyecto-id",
      "collections_found": 2,
      "environment": "local"
    }
  },
  "port": "8000",
  "environment": "development"
}
```

### 3. Probar Endpoints

```bash
# Probar endpoint de contratos
curl "http://localhost:8000/contratos/init_contratos_seguimiento" | python -m json.tool

# Probar con filtros
curl "http://localhost:8000/contratos/init_contratos_seguimiento?referencia_contrato=CONT" | python -m json.tool
```

### 4. Acceder a Documentación

Visita en tu navegador: http://localhost:8000/docs

---

## 🔧 Solución de Problemas

### Error: "No module named 'firebase_admin'"

```bash
# Verificar que el entorno virtual esté activado
pip install firebase-admin google-cloud-firestore
```

### Error: "Application Default Credentials not found"

```bash
# Configurar credenciales
gcloud auth application-default login
```

### Error: "Permission denied" en Firestore

1. Verifica que las reglas de Firestore estén en modo de prueba
2. O configura reglas más permisivas:

```javascript
// Reglas de Firestore (temporales para desarrollo)
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {
    match /{document=**} {
      allow read, write: if true;
    }
  }
}
```

### Error: "Port already in use"

```bash
# Cambiar puerto en .env
PORT=8001

# O matar proceso en puerto 8000
# Windows
netstat -ano | findstr :8000
taskkill /PID <PID> /F

# macOS/Linux
lsof -ti:8000 | xargs kill -9
```

### Problemas con Entorno Virtual

```bash
# Desactivar entorno actual
deactivate

# Eliminar entorno virtual
rm -rf venv_api  # Linux/macOS
Remove-Item -Recurse -Force venv_api  # Windows PowerShell

# Crear nuevo entorno
python -m venv venv_api
```

---

## 📚 Recursos Adicionales

### Documentación Oficial

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Firebase Admin SDK](https://firebase.google.com/docs/admin/setup)
- [Google Cloud Authentication](https://cloud.google.com/docs/authentication/getting-started)

### Comandos Útiles

```bash
# Ver logs detallados
python main.py --log-level debug

# Verificar estructura del proyecto
tree .  # Linux/macOS
Get-ChildItem -Recurse  # Windows PowerShell

# Exportar dependencias actuales
pip freeze > requirements_local.txt
```

### Estructura del Proyecto

```
gestor_proyecto_api/
├── api/
│   └── scripts/
│       ├── contratos_operations.py
│       └── firebase_operations.py
├── database/
│   └── firebase_config.py
├── docs/
│   └── api_setup_docs/
│       └── virtual_environment_setup.md
├── .env.example
├── .gitignore
├── main.py
├── requirements.txt
└── SETUP.md
```

---

## ✨ ¡Listo para Desarrollar!

Una vez completados todos los pasos, tendrás:

- ✅ Entorno virtual configurado
- ✅ Firebase conectado con tu base de datos de prueba
- ✅ API funcionando en `http://localhost:8000`
- ✅ Documentación interactiva en `http://localhost:8000/docs`
- ✅ Endpoint de contratos funcionando

**¡Tu API está lista para desarrollo y pruebas!** 🎉

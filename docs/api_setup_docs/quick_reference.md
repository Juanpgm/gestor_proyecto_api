# 🚀 Comandos Rápidos - API Setup

## ⚡ Setup Rápido (5 minutos)

### 1. Clonar y Configurar

```bash
git clone https://github.com/Juanpgm/gestor_proyecto_api.git
cd gestor_proyecto_api
python -m venv venv_api
```

### 2. Activar Entorno (Windows)

```powershell
.\venv_api\Scripts\Activate.ps1
```

### 3. Activar Entorno (macOS/Linux)

```bash
source venv_api/bin/activate
```

### 4. Instalar y Configurar

```bash
pip install -r requirements.txt
cp .env.example .env
gcloud auth application-default login
```

### 5. Ejecutar

```bash
python main.py
```

---

## 🔧 Comandos de Desarrollo

### Gestión del Entorno Virtual

```bash
# Activar entorno
# Windows: .\venv_api\Scripts\Activate.ps1
# macOS/Linux: source venv_api/bin/activate

# Desactivar entorno
deactivate

# Recrear entorno virtual
deactivate
rm -rf venv_api  # Linux/macOS
Remove-Item -Recurse -Force venv_api  # Windows
python -m venv venv_api
```

### Gestión de Dependencias

```bash
# Instalar dependencias
pip install -r requirements.txt

# Actualizar dependencias
pip install --upgrade -r requirements.txt

# Exportar dependencias actuales
pip freeze > requirements_backup.txt

# Instalar nueva dependencia
pip install nombre-paquete
pip freeze > requirements.txt
```

### Firebase y Google Cloud

```bash
# Autenticación
gcloud auth login
gcloud auth application-default login

# Configurar proyecto
gcloud config set project TU_PROJECT_ID
gcloud config get-value project

# Verificar credenciales
gcloud auth list
gcloud auth application-default print-access-token
```

### Pruebas de la API

```bash
# Health check
curl http://localhost:8000/health

# Documentación
open http://localhost:8000/docs  # macOS
start http://localhost:8000/docs  # Windows

# Endpoint de contratos
curl "http://localhost:8000/contratos/init_contratos_seguimiento"

# Con filtros
curl "http://localhost:8000/contratos/init_contratos_seguimiento?referencia_contrato=test"
```

---

## 🐛 Debug y Troubleshooting

### Verificar Configuración

```bash
# Verificar Python y pip
python --version && pip --version

# Verificar variables de entorno
python -c "import os; print('Project:', os.getenv('FIREBASE_PROJECT_ID'))"

# Verificar Firebase
python -c "from database.firebase_config import FirebaseManager; print(FirebaseManager.test_connection())"

# Verificar puerto
netstat -ano | findstr :8000  # Windows
lsof -ti:8000  # macOS/Linux
```

### Logs y Debugging

```bash
# Ejecutar con logs detallados
python main.py --log-level debug

# Ver logs de Firebase
export GOOGLE_APPLICATION_CREDENTIALS_DEBUG=1  # Linux/macOS
$env:GOOGLE_APPLICATION_CREDENTIALS_DEBUG=1  # Windows PowerShell
python main.py
```

### Limpiar y Reiniciar

```bash
# Limpiar cache de Python
find . -type d -name "__pycache__" -exec rm -rf {} +  # Linux/macOS
Get-ChildItem -Recurse -Directory -Name "__pycache__" | Remove-Item -Recurse -Force  # Windows

# Reiniciar servidor (matar proceso)
# Windows
taskkill /f /im python.exe
# macOS/Linux
pkill -f "python main.py"
```

---

## 📝 Variables de Entorno Clave

### Archivo .env Mínimo

```env
FIREBASE_PROJECT_ID=tu-proyecto-id
GOOGLE_CLOUD_PROJECT=tu-proyecto-id
PORT=8000
ENVIRONMENT=development
```

### Variables Opcionales

```env
FIRESTORE_BATCH_SIZE=500
FIRESTORE_TIMEOUT=30
FIREBASE_SERVICE_ACCOUNT_KEY=tu-clave-base64  # Solo si no usas ADC
```

---

## 🎯 Endpoints Disponibles

### Health Check

```
GET /health
```

### Contratos

```
GET /contratos/init_contratos_seguimiento
GET /contratos/init_contratos_seguimiento?referencia_contrato=VALUE
GET /contratos/init_contratos_seguimiento?nombre_centro_gestor=VALUE
GET /contratos/init_contratos_seguimiento?referencia_contrato=VALUE&nombre_centro_gestor=VALUE
```

### Documentación

```
GET /docs          # Swagger UI
GET /redoc         # ReDoc
GET /openapi.json  # OpenAPI Schema
```

---

## 🔍 Verificación Final

### Checklist de Setup Exitoso

- [ ] Python 3.8+ instalado
- [ ] Entorno virtual activado (prompt muestra `(venv_api)`)
- [ ] Dependencias instaladas sin errores
- [ ] Archivo `.env` configurado
- [ ] Google Cloud autenticado
- [ ] Firebase proyecto creado
- [ ] Servidor inicia sin errores
- [ ] `/health` responde correctamente
- [ ] `/docs` carga la documentación

### Comando de Verificación Completa

```bash
python -c "
print('=== VERIFICACIÓN DE SETUP ===')
import sys
print(f'Python: {sys.version}')

import os
print(f'Project ID: {os.getenv(\"FIREBASE_PROJECT_ID\", \"❌ NO CONFIGURADO\")}')
print(f'Puerto: {os.getenv(\"PORT\", \"8000\")}')

from database.firebase_config import FirebaseManager
status = FirebaseManager.test_connection()
print(f'Firebase: {\"✅ Conectado\" if status[\"connected\"] else \"❌ Error\"}')

print('=== SETUP COMPLETO ===')
"
```

---

## 🚨 Problemas Comunes

| Error                                       | Solución                                  |
| ------------------------------------------- | ----------------------------------------- |
| `ModuleNotFoundError: No module named 'X'`  | `pip install -r requirements.txt`         |
| `Application Default Credentials not found` | `gcloud auth application-default login`   |
| `Port 8000 already in use`                  | Cambiar `PORT=8001` en `.env`             |
| `Permission denied` Firebase                | Verificar reglas de Firestore             |
| `Invalid project ID`                        | Verificar `FIREBASE_PROJECT_ID` en `.env` |

¡Con esta guía rápida puedes tener la API funcionando en minutos! 🎉

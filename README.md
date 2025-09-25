# 🚀 Gestor de Proyectos API

API REST simple para gestión de proyectos con Firebase/Firestore.

## ⚡ Inicio Rápido

### 1. Configurar

```bash
git clone <tu-repo>
cd gestor_proyecto_api
```

### 2. Variables de Entorno

Edita `.env`:

```env
FIREBASE_PROJECT_ID=tu-proyecto-id
GOOGLE_CLOUD_PROJECT=tu-proyecto-id
PORT=8000
```

### 3. Ejecutar

#### Con Python:

```bash
pip install -r requirements.txt
python main.py
```

#### Con Docker:

```bash
docker-compose up --build
```

La API estará en: `http://localhost:8000`

## 📋 Endpoints

- `GET /` - Información de la API
- `GET /health` - Estado de salud
- `GET /docs` - Documentación Swagger
- `GET /unidades-proyecto` - Todas las unidades de proyecto
- `GET /unidades-proyecto/summary` - Resumen estadístico
- `GET /unidades-proyecto/filter` - Filtrar unidades

## 🌐 Despliegue

### Railway.app (Recomendado)

1. Conecta tu repo en [railway.app](https://railway.app)
2. Configura las variables de entorno
3. ¡Listo!

### Render.com

1. Conecta tu repo en [render.com](https://render.com)
2. Configura variables en el dashboard
3. Despliega

### Docker en cualquier plataforma

```bash
docker build -t gestor-proyecto-api .
docker run -p 8000:8000 --env-file .env gestor-proyecto-api
```

## 📁 Estructura

```
gestor_proyecto_api/
├── main.py              # Aplicación FastAPI
├── database/config.py   # Configuración Firebase
├── api/scripts/         # Lógica de negocio
├── Dockerfile           # Para contenedorización
├── requirements.txt     # Dependencias
└── .env                # Configuración
```

¡Listo para usar! 🎉

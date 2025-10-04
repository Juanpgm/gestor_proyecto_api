# 🚀 Gestor de Proyectos API

API REST para interoperabilidad con artefacto de seguimiento con Firebase/Firestore.

## 📚 Documentación Completa

### 🐍 Para Desarrollo Local

**[Guía Completa de Setup Virtual Environment](docs/api_setup_docs/virtual_environment_setup.md)**

- Configuración paso a paso con entornos virtuales
- Configuración de Firebase y base de datos de prueba
- Solución de problemas detallada

### ⚡ Para Desarrolladores Experimentados

**[Comandos Rápidos](docs/api_setup_docs/quick_reference.md)**

- Setup en 5 minutos
- Comandos de desarrollo frecuentes
- Troubleshooting rápido

## ⚡ Inicio Rápido

### 1. Configurar

```bash
git clone https://github.com/Juanpgm/gestor_proyecto_api.git
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

### Sistema

- `GET /health` - Estado de salud de la API
- `GET /docs` - Documentación Swagger interactiva
- `GET /redoc` - Documentación ReDoc

### Interoperabilidad con Artefacto de Seguimiento

- `GET /contratos/init_contratos_seguimiento` - Datos de contratos
  - `?referencia_contrato=VALUE` - Filtro por referencia
  - `?nombre_centro_gestor=VALUE` - Filtro por centro gestor

### Legacy (Unidades de Proyecto)

- `GET /unidades-proyecto` - Todas las unidades de proyecto
- `GET /unidades-proyecto/summary` - Resumen estadístico

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
├── main.py                    # Aplicación FastAPI principal
├── database/
│   └── firebase_config.py     # Configuración Firebase/Firestore
├── api/scripts/               # Lógica de negocio
│   ├── contratos_operations.py
│   └── firebase_operations.py
├── docs/                      # 📚 Documentación completa
│   ├── README.md              # Índice de documentación
│   └── api_setup_docs/        # Guías de setup
├── .env.example              # Template de configuración
├── requirements.txt          # Dependencias Python
└── Dockerfile               # Para contenedorización
```

## 🔐 Configuración de Seguridad

- ✅ Archivos `.env` excluidos del repositorio
- ✅ Application Default Credentials para desarrollo local
- ✅ Service Account Keys para producción
- ✅ Variables de entorno para configuración sensible

**📖 Ver [documentación completa](docs/) para configuración detallada.**

¡Listo para usar! 🎉

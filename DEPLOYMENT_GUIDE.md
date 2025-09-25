# 🚀 Guía de Despliegue Simple

## 1. Railway.app (⭐ MÁS FÁCIL)

1. Ve a [railway.app](https://railway.app)
2. Conecta tu repositorio GitHub
3. Configura estas variables:
   - `FIREBASE_PROJECT_ID=tu-proyecto-firebase`
   - `GOOGLE_CLOUD_PROJECT=tu-proyecto-firebase`
4. Railway despliega automáticamente

**URL final:** `https://tu-proyecto.up.railway.app`

## 2. Render.com

1. Ve a [render.com](https://render.com)
2. Conecta tu repositorio
3. Selecciona "Web Service"
4. Configura:
   - Build Command: (vacío)
   - Start Command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
5. Variables de entorno:
   - `FIREBASE_PROJECT_ID=tu-proyecto-firebase`
   - `GOOGLE_CLOUD_PROJECT=tu-proyecto-firebase`

## 3. Docker (Cualquier plataforma)

```bash
# Construir imagen
docker build -t gestor-proyecto-api .

# Ejecutar
docker run -p 8000:8000 \
  -e FIREBASE_PROJECT_ID=tu-proyecto \
  -e GOOGLE_CLOUD_PROJECT=tu-proyecto \
  gestor-proyecto-api
```

## 4. Heroku

```bash
# Instalar Heroku CLI
heroku login
heroku create tu-app-name

# Configurar variables
heroku config:set FIREBASE_PROJECT_ID=tu-proyecto
heroku config:set GOOGLE_CLOUD_PROJECT=tu-proyecto

# Desplegar
git push heroku main
```

## ✅ Variables Mínimas Requeridas

```env
FIREBASE_PROJECT_ID=tu-proyecto-firebase
GOOGLE_CLOUD_PROJECT=tu-proyecto-firebase
```

## 🧪 Verificar Despliegue

Una vez desplegado, verifica:

```bash
curl https://tu-dominio.com/health
```

Debe responder:

```json
{
  "status": "healthy",
  "services": {
    "api": "running",
    "firebase": { "connected": true }
  }
}
}
```

¡Listo! 🎉

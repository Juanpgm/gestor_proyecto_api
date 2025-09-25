# 🚂 Despliegue en Railway - Guía Completa

## 📋 **PRE-REQUISITOS:**

- [ ] Cuenta en GitHub (tu código ya está ahí)
- [ ] Cuenta en [Railway.app](https://railway.app) (gratis)
- [ ] Proyecto Firebase activo (`dev-test-e778d`)

## 🚀 **PASOS PARA DESPLEGAR:**

### 1. **Subir código a GitHub** (si no lo has hecho)

```bash
git add .
git commit -m "Preparado para Railway deployment"
git push origin master
```

### 2. **Conectar con Railway**

1. Ve a [railway.app](https://railway.app)
2. Haz clic en **"Start a New Project"**
3. Selecciona **"Deploy from GitHub repo"**
4. Autoriza Railway a acceder a tu GitHub
5. Selecciona el repositorio: `Juanpgm/gestor_proyecto_api`
6. Railway detectará automáticamente el `Dockerfile`

### 3. **Configurar Variables de Entorno**

En Railway Dashboard, ve a **"Variables"** y agrega:

```env
FIREBASE_PROJECT_ID=dev-test-e778d
GOOGLE_CLOUD_PROJECT=dev-test-e778d
PORT=8000
ENVIRONMENT=production
FIRESTORE_BATCH_SIZE=500
FIRESTORE_TIMEOUT=30
```

### 4. **Verificar Despliegue**

- Railway te dará una URL como: `https://tu-app.up.railway.app`
- Prueba los endpoints:
  - `GET /` - Información básica
  - `GET /health` - Estado de la API
  - `GET /firebase/status` - Conexión con Firebase

## ⚙️ **CONFIGURACIÓN AUTOMÁTICA:**

Railway detecta automáticamente:

- ✅ `Dockerfile` para el build
- ✅ `railway.json` para configuración
- ✅ Puerto desde variable `$PORT`
- ✅ Health check en `/health`

## 🔧 **COMANDOS ÚTILES:**

### Logs en tiempo real:

```bash
# Instalar Railway CLI (opcional)
npm install -g @railway/cli
railway login
railway logs
```

### Redeploy manual:

```bash
railway up
```

## 🌐 **DOMINIO PERSONALIZADO (Opcional):**

1. En Railway Dashboard → **"Settings"**
2. **"Domains"** → **"Custom Domain"**
3. Agrega tu dominio: `api.tudominio.com`
4. Configura DNS según las instrucciones

## 📊 **MONITOREO:**

### Métricas disponibles en Railway:

- CPU Usage
- Memory Usage
- Network Traffic
- Response Times
- Error Rates

### Endpoints para monitorear:

- `GET /health` - Estado general
- `GET /firebase/status` - Conexión Firebase
- `GET /firebase/collections/summary` - Estadísticas DB

## 💰 **COSTO:**

- **Plan Starter:** $5/mes (500 horas de ejecución)
- **Plan Pro:** $20/mes (sin límites + más recursos)

## 🚨 **TROUBLESHOOTING:**

### Error: "Firebase not initialized"

- Verificar `FIREBASE_PROJECT_ID` en variables
- Verificar que el proyecto existe en Firebase Console

### Error: "Application failed to respond"

- **Causa:** La aplicación no inicia correctamente
- **Solución 1:** Verificar variables de entorno en Railway Dashboard
- **Solución 2:** Revisar logs de Railway para errores específicos
- **Solución 3:** Hacer redeploy después de configurar variables

### Error: "Invalid value for '--port': '$PORT' is not a valid integer"

- **Solución:** Dockerfile simplificado maneja automáticamente `$PORT`
- Railway asigna `$PORT` automáticamente
- Usa puerto 8000 por defecto si `$PORT` no está disponible

### Error: "Port binding failed"

- Railway asigna `$PORT` automáticamente
- No hardcodear puerto 8000
- Verificar que la aplicación escuche en `0.0.0.0`

### Error: "Firebase not initialized"

- Verificar `FIREBASE_PROJECT_ID` y `GOOGLE_CLOUD_PROJECT` en Railway
- Ambas variables deben tener el mismo valor: `dev-test-e778d`
- Verificar que el proyecto Firebase exista y esté activo

### Error: Build fails

- Verificar `requirements.txt`
- Revisar logs de build en Railway Dashboard
- Asegurar que todas las dependencias sean compatibles

## ✅ **CHECKLIST FINAL:**

- [ ] Variables de entorno configuradas
- [ ] Health check responde OK
- [ ] Endpoints principales funcionan
- [ ] Firebase conectado correctamente
- [ ] Logs sin errores críticos

## 🎉 **¡LISTO!**

Tu API estará disponible en: `https://tu-app.up.railway.app`

**Próximos pasos:**

1. Configurar dominio personalizado
2. Monitorear logs y métricas
3. Configurar alertas de rendimiento

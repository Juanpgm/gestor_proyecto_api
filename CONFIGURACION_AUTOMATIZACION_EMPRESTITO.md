# 🔄 Configuración de Automatización de Pipeline de Empréstito

## 📋 Resumen

Se ha creado un workflow de GitHub Actions que ejecuta automáticamente el pipeline de empréstito con los siguientes endpoints de manera secuencial:

1. `/emprestito/crear-tabla-proyecciones`
2. `/emprestito/obtener-procesos-secop`
3. `/emprestito/obtener-contratos-secop`
4. `/emprestito/obtener-ordenes-compra-TVEC`

## ⏰ Horarios de Ejecución

El pipeline se ejecuta automáticamente a las siguientes horas (UTC):

- **00:00 UTC** (19:00 Colombia día anterior)
- **05:00 UTC** (00:00 Colombia)
- **10:00 UTC** (05:00 Colombia)
- **15:00 UTC** (10:00 Colombia)
- **17:00 UTC** (12:00 Colombia)
- **22:00 UTC** (17:00 Colombia)

> ⚠️ **Nota sobre zona horaria**: GitHub Actions usa UTC por defecto. Los horarios mostrados entre paréntesis son para Colombia (UTC-5). Ajusta según tu zona horaria.

## 🔧 Configuración Requerida

### 1. Configurar Secrets en GitHub

Debes configurar los siguientes secrets en tu repositorio de GitHub:

#### a) Navegar a la configuración de secrets:

```
Tu Repositorio → Settings → Secrets and variables → Actions → New repository secret
```

#### b) Crear los siguientes secrets:

**Secret 1: `API_BASE_URL`**

- **Nombre**: `API_BASE_URL`
- **Valor**: La URL base de tu API (ejemplo: `https://tu-api.railway.app` o `https://tu-dominio.com`)
- **Descripción**: URL donde está desplegada tu API

**Secret 2: `FIREBASE_ID_TOKEN`**

- **Nombre**: `FIREBASE_ID_TOKEN`
- **Valor**: Token de autenticación de Firebase
- **Descripción**: Token de Firebase para autenticar las requests

### 2. Obtener el Firebase ID Token

Tienes varias opciones para obtener el token:

#### Opción A: Desde tu aplicación frontend (Recomendado para tokens de larga duración)

```javascript
// En tu app NextJS o frontend
import { getAuth } from "firebase/auth";

const auth = getAuth();
const user = auth.currentUser;

if (user) {
  const idToken = await user.getIdToken();
  console.log("ID Token:", idToken);
}
```

#### Opción B: Crear un Service Account Token (Recomendado para automatización)

1. Ve a [Firebase Console](https://console.firebase.google.com/)
2. Selecciona tu proyecto
3. Ve a: **Project Settings → Service Accounts**
4. Click en **Generate new private key**
5. Descarga el archivo JSON

Luego, usa este script para generar un custom token:

```python
import firebase_admin
from firebase_admin import credentials, auth
import json

# Cargar el service account
cred = credentials.Certificate('path/to/serviceAccountKey.json')
firebase_admin.initialize_app(cred)

# Crear un custom token para un usuario específico
uid = 'tu-usuario-uid'  # Reemplaza con un UID de usuario válido
custom_token = auth.create_custom_token(uid)
print(f"Custom Token: {custom_token.decode()}")

# Nota: Este custom token debe ser intercambiado por un ID token
# usando la API de Firebase Auth
```

#### Opción C: Usar un token de usuario admin manualmente

1. Inicia sesión en tu aplicación con un usuario que tenga permisos
2. Abre las DevTools del navegador (F12)
3. Ve a la pestaña **Application → Local Storage**
4. Busca el token de Firebase (generalmente bajo la clave del proyecto)

> ⚠️ **Importante**: Los ID tokens de Firebase expiran después de 1 hora. Para automatización, considera:
>
> - Usar un **custom token** que no expira
> - Implementar un endpoint en tu API que refresque el token automáticamente
> - Configurar un sistema de refresh tokens

### 3. Verificar la Configuración

#### Probar manualmente el workflow:

1. Ve a tu repositorio en GitHub
2. Click en la pestaña **Actions**
3. Selecciona el workflow **"🔄 Empréstito Data Pipeline Automation"**
4. Click en **"Run workflow"** (botón azul)
5. Selecciona la branch y click en **"Run workflow"**

Esto ejecutará el pipeline inmediatamente para verificar que todo funciona.

## 📁 Archivo Creado

El workflow se encuentra en:

```
.github/workflows/emprestito-automation.yml
```

## 🔍 Monitoreo

### Ver los logs de ejecución:

1. Ve a **Actions** en tu repositorio
2. Click en el workflow específico
3. Revisa los logs de cada paso

### Notificaciones:

GitHub enviará notificaciones por email si el workflow falla. También puedes configurar notificaciones adicionales usando:

- Slack webhooks
- Discord webhooks
- Microsoft Teams
- O cualquier otro servicio de notificaciones

## 🛠️ Solución de Problemas Comunes

### Error: 401 Unauthorized

- **Causa**: Token de Firebase inválido o expirado
- **Solución**: Regenera el token y actualiza el secret `FIREBASE_ID_TOKEN`

### Error: 404 Not Found

- **Causa**: URL de la API incorrecta
- **Solución**: Verifica que `API_BASE_URL` apunte a tu API correcta

### Error: Timeout

- **Causa**: El endpoint está tardando mucho en responder
- **Solución**: Los timeouts están configurados en el código (5-10 minutos). Si necesitas más tiempo, ajusta los valores en `main.py`

### Pipeline se salta pasos

- **Causa**: Un paso anterior falló
- **Solución**: El pipeline es secuencial. Si un paso falla, los siguientes se saltarán. Revisa los logs del paso que falló.

## 🔐 Seguridad

- ✅ Nunca cometas tokens o secrets en el código
- ✅ Usa GitHub Secrets para almacenar información sensible
- ✅ Rota los tokens periódicamente
- ✅ Usa tokens con los mínimos permisos necesarios
- ✅ Considera implementar un sistema de refresh tokens automático

## 📝 Comandos Útiles

### Listar secrets configurados (desde CLI):

```bash
gh secret list
```

### Agregar un secret (desde CLI):

```bash
gh secret set API_BASE_URL --body "https://tu-api.com"
gh secret set FIREBASE_ID_TOKEN --body "tu-token-aqui"
```

### Ver ejecuciones del workflow (desde CLI):

```bash
gh run list --workflow=emprestito-automation.yml
```

### Ver logs de una ejecución específica:

```bash
gh run view <run-id> --log
```

## 🎯 Próximos Pasos

1. ✅ Configurar los secrets en GitHub
2. ✅ Hacer un test manual del workflow
3. ✅ Verificar que los horarios sean correctos para tu zona horaria
4. 🔄 Implementar un sistema de refresh de tokens (opcional pero recomendado)
5. 📊 Configurar notificaciones adicionales (opcional)

## 📞 Soporte

Si tienes problemas con la configuración, revisa:

- Los logs en GitHub Actions
- La documentación de Firebase Authentication
- La documentación de GitHub Actions Secrets

---

**Creado**: $(date)
**Workflow**: `.github/workflows/emprestito-automation.yml`

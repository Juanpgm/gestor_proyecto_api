# Guía para obtener Google OAuth Credentials

## Pasos para configurar Google OAuth:

### 1. Ir a Google Cloud Console

- Visita: https://console.cloud.google.com/
- Crea un proyecto nuevo o selecciona uno existente

### 2. Habilitar APIs necesarias

- Ve a "APIs & Services" > "Library"
- Busca y habilita "Google+ API" o "Google Identity"
- También puedes habilitar "Gmail API" si necesitas envío de emails

### 3. Crear credenciales OAuth 2.0

- Ve a "APIs & Services" > "Credentials"
- Haz clic en "Create Credentials" > "OAuth 2.0 Client IDs"
- Selecciona "Web application"

### 4. Configurar la aplicación web

- Nombre: "Gestor Proyecto API"
- Authorized JavaScript origins:
  - http://localhost:8001
  - http://127.0.0.1:8001
  - https://tu-dominio-produccion.com (cuando tengas)
- Authorized redirect URIs:
  - http://localhost:8001/auth/google/callback
  - http://127.0.0.1:8001/auth/google/callback
  - https://tu-dominio-produccion.com/auth/google/callback

### 5. Obtener las credenciales

Después de crear, obtendrás:

- Client ID: algo como "123456789-abcdefg.apps.googleusercontent.com"
- Client Secret: algo como "GOCSPX-abcdefghijklmnop"

### 6. Configurar en .env

Reemplaza en tu archivo .env:

```
GOOGLE_CLIENT_ID=tu_client_id_aqui
GOOGLE_CLIENT_SECRET=tu_client_secret_aqui
```

## Para desarrollo local (OPCIONAL):

Si solo quieres probar sin configurar Google OAuth, puedes usar estos valores de prueba:

```
GOOGLE_CLIENT_ID=test_client_id_for_development
GOOGLE_CLIENT_SECRET=test_client_secret_for_development
```

⚠️ IMPORTANTE: Los valores de prueba no funcionarán para autenticación real con Google.

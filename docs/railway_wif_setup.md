# 🚀 Configuración de GOOGLE_APPLICATION_CREDENTIALS_JSON en Railway

## 📋 Guía Paso a Paso

### 1. 🔑 Generar Credenciales de Workload Identity Federation

Primero necesitas generar las credenciales WIF ejecutando el script PowerShell:

```powershell
# En tu workspace local
.\setup_workload_identity.ps1
```

Este script creará un archivo similar a `workload-identity-credentials.json` con contenido como:

```json
{
  "type": "external_account",
  "audience": "//iam.googleapis.com/projects/123456789/locations/global/workloadIdentityPools/railway-pool/providers/railway-provider",
  "subject_token_type": "urn:ietf:params:oauth:token-type:jwt",
  "token_url": "https://sts.googleapis.com/v1/token",
  "service_account_impersonation_url": "https://iamcredentials.googleapis.com/v1/projects/-/serviceAccounts/railway-wif@tu-proyecto.iam.gserviceaccount.com:generateAccessToken",
  "client_id": "client-id-generado",
  "credential_source": {
    "environment_id": "aws1",
    "regional_cred_verification_url": "https://sts.{region}.amazonaws.com/",
    "url": "http://169.254.169.254/latest/meta-data/iam/security-credentials",
    "format": {
      "type": "json",
      "subject_token_field_name": "Token"
    }
  }
}
```

### 2. 📋 Configurar Variable en Railway Dashboard

1. **Accede a tu proyecto en Railway Dashboard**
2. **Ve a la pestaña "Variables"**
3. **Agrega una nueva variable:**
   - **Nombre**: `GOOGLE_APPLICATION_CREDENTIALS_JSON`
   - **Valor**: El contenido COMPLETO del archivo JSON **en una sola línea** (sin espacios ni saltos de línea)

### 3. 🔄 Formato Correcto para Railway

**✅ CORRECTO - Todo en una línea:**

```
{"type":"external_account","audience":"//iam.googleapis.com/projects/123456789/locations/global/workloadIdentityPools/railway-pool/providers/railway-provider","subject_token_type":"urn:ietf:params:oauth:token-type:jwt","token_url":"https://sts.googleapis.com/v1/token","service_account_impersonation_url":"https://iamcredentials.googleapis.com/v1/projects/-/serviceAccounts/railway-wif@tu-proyecto.iam.gserviceaccount.com:generateAccessToken","client_id":"client-id-generado","credential_source":{"environment_id":"aws1","regional_cred_verification_url":"https://sts.{region}.amazonaws.com/","url":"http://169.254.169.254/latest/meta-data/iam/security-credentials","format":{"type":"json","subject_token_field_name":"Token"}}}
```

**❌ INCORRECTO - Con formato:**

```json
{
  "type": "external_account",
  "audience": "//iam.googleapis.com/projects/123456789/..."
  // NO pongas el JSON formateado
}
```

### 4. 🎛️ Variables Adicionales Requeridas

También configura estas variables en Railway:

```bash
# ID del proyecto Firebase
FIREBASE_PROJECT_ID=tu-proyecto-firebase-id

# Entorno de producción
ENVIRONMENT=production

# URL del frontend (opcional, para CORS)
FRONTEND_URL=https://tu-frontend.vercel.app
```

### 5. 🔧 Comandos Útiles para Preparar el JSON

Si necesitas convertir el archivo JSON a una sola línea:

**En PowerShell:**

```powershell
# Leer archivo y convertir a una línea
$json = Get-Content "workload-identity-credentials.json" -Raw | ConvertFrom-Json
$compactJson = $json | ConvertTo-Json -Compress -Depth 10
Write-Output $compactJson
```

**En Linux/Mac:**

```bash
# Usando jq para compactar el JSON
jq -c . workload-identity-credentials.json
```

### 6. ✅ Verificar Configuración

Después de configurar las variables, verifica que funcione:

1. **Deploy tu aplicación en Railway**
2. **Accede al endpoint de salud:**
   ```
   GET https://tu-app.railway.app/health
   ```
3. **Debe retornar:**
   ```json
   {
     "status": "healthy",
     "firebase_connected": true,
     "auth_method": "workload_identity_federation"
   }
   ```

### 7. 🚨 Solución de Problemas

**Si el endpoint /health muestra error:**

1. **Verifica los logs de Railway** para ver errores específicos
2. **Confirma que el JSON esté en una sola línea** sin caracteres especiales
3. **Asegúrate de que FIREBASE_PROJECT_ID coincida** con tu proyecto real
4. **Verifica que el Service Account tenga permisos** de Firebase Admin

**Logs típicos de éxito:**

```
🔑 Workload Identity Federation available
✅ Workload Identity credentials configured
✅ Firebase initialized with Workload Identity Federation
```

### 8. 🔒 Seguridad

- ✅ **WIF no expone claves de larga duración**
- ✅ **Tokens se renuevan automáticamente**
- ✅ **Principio de menor privilegio aplicado**
- ✅ **Auditoría completa en Google Cloud**

### 9. 📝 Alternativa con Service Account (No Recomendada)

Si WIF no funciona, puedes usar como fallback:

```bash
# Convertir service account a base64
FIREBASE_SERVICE_ACCOUNT_KEY=ewogICJ0eXBlIjogInNlcnZpY2VfYWNjb3VudCIsCiAgInByb2plY3RfaWQiOi...
```

Pero **WIF es siempre la opción más segura** para producción.

---

## 🎉 ¡Listo!

Tu aplicación ahora usará Workload Identity Federation para autenticarse con Firebase de forma segura en Railway.

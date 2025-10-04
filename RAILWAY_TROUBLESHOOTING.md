# 🚨 GUÍA DE SOLUCIÓN DE PROBLEMAS - RAILWAY WIF

## ❌ Problemas Comunes y Soluciones

### 1. **Error: "Unable to retrieve Identity Pool subject token"** ⭐ PROBLEMA COMÚN

```
❌ Síntoma: La aplicación no puede obtener el token OIDC de Railway
❌ Causa: Railway ya NO proporciona RAILWAY_TOKEN automáticamente
🔧 Solución INMEDIATA:
   - ✅ Usa Service Account Key: .\fix_railway_no_token.ps1
   - ✅ Método más seguro y estable que WIF
   - ✅ Funciona inmediatamente sin configuración adicional

🧪 Alternativa experimental:
   - GitHub OIDC: .\github_oidc_alternative.ps1 (solo para usuarios avanzados)
```

### 2. **Error: "Workload Identity Federation failed"**

```
❌ Síntoma: WIF no puede autenticar con Google Cloud
🔧 Solución:
   - Verifica que tu Railway Project ID esté correctamente configurado en IAM
   - Confirma que railway-firebase@unidad-cumplimiento-aa245.iam.gserviceaccount.com existe
   - Revisa los permisos del Workload Identity Pool
```

### 3. **Error: "Firebase not configured"**

```
❌ Síntoma: La aplicación no encuentra las credenciales de Firebase
🔧 Solución:
   - Verifica que FIREBASE_PROJECT_ID=unidad-cumplimiento-aa245
   - Confirma que GOOGLE_APPLICATION_CREDENTIALS_JSON esté configurado correctamente
   - Asegúrate de que el JSON no tenga caracteres especiales o saltos de línea extra
```

### 4. **Error: "Permission denied" en Firestore**

```
❌ Síntoma: La aplicación se conecta pero no puede leer/escribir en Firestore
🔧 Solución:
   - Verifica que el service account tenga roles:
     * roles/firebase.admin
     * roles/datastore.user
   - Ejecuta: gcloud projects get-iam-policy unidad-cumplimiento-aa245
```

## 🔍 Comandos de Diagnóstico

### Verificar configuración local:

```powershell
# Ejecutar diagnósticos
python verify_wif_setup.py
python verify_railway_config.py

# Ver configuración actual de gcloud
gcloud config list
gcloud auth list
```

### Verificar en Railway (después del deploy):

```bash
# Endpoint de verificación
curl https://tu-app.railway.app/auth/workload-identity/status

# Ver logs de Railway
# Ve a Railway Dashboard > tu-proyecto > Deploy logs
```

## 🚀 Orden de Prioridad de Autenticación

Tu aplicación intenta autenticarse en este orden:

1. **🥇 Workload Identity Federation** (GOOGLE_APPLICATION_CREDENTIALS_JSON)

   - Más seguro
   - Recomendado para producción
   - Usa tokens temporales

2. **🥈 Application Default Credentials** (local development)

   - Solo funciona localmente
   - Usa: gcloud auth application-default login

3. **🥉 Service Account Key** (FIREBASE_SERVICE_ACCOUNT_KEY)
   - Fallback para emergencias
   - Menos seguro (clave permanente)
   - Solo si WIF no funciona

## 🛠️ Scripts de Ayuda

```powershell
# Configurar variables para Railway
.\railway_production_setup.ps1

# Generar Service Account de emergencia
.\generate_service_account_fallback.ps1

# Diagnosticar problemas
python diagnose_railway_auth.py
python verify_wif_setup.py
```

## 📞 Checklist de Deployment

Antes de hacer deploy en Railway:

- [ ] ✅ Todas las variables están configuradas en Railway Dashboard
- [ ] ✅ GOOGLE_APPLICATION_CREDENTIALS_JSON es una línea JSON válida
- [ ] ✅ FIREBASE_PROJECT_ID=unidad-cumplimiento-aa245
- [ ] ✅ ENVIRONMENT=production
- [ ] ✅ El Workload Identity Pool existe en Google Cloud
- [ ] ✅ El service account railway-firebase@unidad-cumplimiento-aa245.iam.gserviceaccount.com existe
- [ ] ✅ Los permisos IAM están configurados correctamente

## 🆘 Solución de Emergencia

Si nada funciona, usa Service Account Key temporal:

```powershell
# Generar clave de emergencia
.\generate_service_account_fallback.ps1

# En Railway, usar FIREBASE_SERVICE_ACCOUNT_KEY en lugar de GOOGLE_APPLICATION_CREDENTIALS_JSON
```

## 📧 Información de Contacto

Si necesitas ayuda adicional:

- 📖 Revisa: RAILWAY_WIF_SETUP.md
- 🔍 Ejecuta: python verify_wif_setup.py
- 🛠️ Genera fallback: .\generate_service_account_fallback.ps1

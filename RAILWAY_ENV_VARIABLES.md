# 🚀 Variables de Entorno para Railway

## Variables CRÍTICAS para el funcionamiento en producción:

### 1. Configuración Firebase Principal
```bash
FIREBASE_PROJECT_ID=unidad-cumplimiento-aa245
GOOGLE_CLOUD_PROJECT=unidad-cumplimiento-aa245
```

### 2. Configuración Firebase Secundaria (para compatibilidad)
```bash
FIREBASE_PROJECT_ID_UNIDAD=unidad-cumplimiento-aa245
GOOGLE_CLOUD_PROJECT_UNIDAD=unidad-cumplimiento-aa245
```

### 3. Configuración Firestore
```bash
FIRESTORE_BATCH_SIZE=500
FIRESTORE_TIMEOUT=30
```

### 4. Credenciales de Service Account (CRÍTICO para Railway)
Railway no puede usar gcloud ADC como en desarrollo local, por lo que NECESITAS una de estas opciones:

#### Opción A - Service Account Key (Recomendado para Railway):
```bash
FIREBASE_SERVICE_ACCOUNT_KEY=<contenido-completo-del-json-service-account-codificado-en-base64>
```

#### Opción B - Variables individuales del Service Account:
```bash
FIREBASE_CLIENT_EMAIL=service-account@unidad-cumplimiento-aa245.iam.gserviceaccount.com
FIREBASE_PRIVATE_KEY=-----BEGIN PRIVATE KEY-----\n<clave-privada>\n-----END PRIVATE KEY-----
FIREBASE_PROJECT_ID=unidad-cumplimiento-aa245
```

## 🔧 Cómo configurar en Railway:

1. Ve a tu proyecto en Railway Dashboard
2. Click en "Variables" 
3. Agrega cada variable una por una
4. Para FIREBASE_SERVICE_ACCOUNT_KEY: 
   - Descarga el service account JSON de Firebase Console
   - Codifícalo en base64: `base64 -i service-account.json`
   - Pega el resultado completo como valor

## ⚡ Verificación de funcionamiento:

Una vez configuradas las variables, Railway debería mostrar en los logs:
```
✅ Firebase auto-config loaded successfully - FIREBASE_AVAILABLE: True
✅ Firebase initialized - production environment
```

En lugar de:
```
❌ Firebase not available - API running in limited mode
```
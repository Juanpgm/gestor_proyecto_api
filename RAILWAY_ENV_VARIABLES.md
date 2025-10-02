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

### 4. Workload Identity Federation (RECOMENDADO para Railway)

Esta es la forma más segura de autenticar con Firebase sin usar service account keys:

#### Variables para Workload Identity Federation:

```bash
# Configuración del Workload Identity Pool
GOOGLE_CLOUD_PROJECT=unidad-cumplimiento-aa245
GOOGLE_APPLICATION_CREDENTIALS=/tmp/workload-identity-credentials.json

# Configuración específica de Workload Identity
WIF_PROVIDER=projects/PROJECT_NUMBER/locations/global/workloadIdentityPools/POOL_ID/providers/PROVIDER_ID
WIF_SERVICE_ACCOUNT=railway-service@unidad-cumplimiento-aa245.iam.gserviceaccount.com

# Token para Railway (se genera automáticamente por Railway)
RAILWAY_TOKEN_FILE=/tmp/railway-token
```

#### Configuración alternativa simplificada:
```bash
# Solo las variables esenciales si ya tienes WIF configurado
GOOGLE_CLOUD_PROJECT=unidad-cumplimiento-aa245
GOOGLE_APPLICATION_CREDENTIALS_JSON=<json-completo-del-workload-identity-credentials>
```

## 🔧 Cómo configurar en Railway:

### Opción 1: Workload Identity Federation (RECOMENDADO)

1. **Ejecuta el script de configuración**:
   ```powershell
   # En PowerShell
   .\setup_workload_identity.ps1
   
   # O en Bash/Linux
   chmod +x setup_workload_identity.sh
   ./setup_workload_identity.sh
   ```

2. **En Railway Dashboard**:
   - Ve a tu proyecto → "Variables"
   - Agrega estas variables:
   ```
   GOOGLE_CLOUD_PROJECT=unidad-cumplimiento-aa245
   FIREBASE_PROJECT_ID=unidad-cumplimiento-aa245
   FIRESTORE_BATCH_SIZE=500
   FIRESTORE_TIMEOUT=30
   GOOGLE_APPLICATION_CREDENTIALS_JSON=<contenido-del-archivo-railway-workload-identity.json>
   ```

### Opción 2: Service Account Key (Alternativa)

1. Ve a Firebase Console → Service accounts → Generate new private key
2. Codifica en base64: `base64 -i service-account.json`
3. En Railway: `FIREBASE_SERVICE_ACCOUNT_KEY=<base64-resultado>`

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

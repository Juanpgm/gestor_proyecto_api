# 🔐 Configuración de Workload Identity Federation para Railway

## ¿Qué es Workload Identity Federation?

Permite que Railway se autentique con Google Cloud sin necesidad de service account keys, usando el identity token de Railway.

## 📋 Pasos de configuración:

### 1. Crear Workload Identity Pool

```bash
# 1. Habilitar las APIs necesarias
gcloud services enable iamcredentials.googleapis.com
gcloud services enable sts.googleapis.com

# 2. Crear el Workload Identity Pool
gcloud iam workload-identity-pools create railway-pool \
    --project=unidad-cumplimiento-aa245 \
    --location=global \
    --display-name="Railway Workload Identity Pool"

# 3. Crear el Provider para Railway
gcloud iam workload-identity-pools providers create-oidc railway-provider \
    --project=unidad-cumplimiento-aa245 \
    --location=global \
    --workload-identity-pool=railway-pool \
    --issuer-uri=https://railway.app \
    --attribute-mapping="google.subject=assertion.sub,attribute.project_id=assertion.project_id" \
    --attribute-condition="assertion.aud=='railway'"
```

### 2. Crear Service Account para Railway

```bash
# 1. Crear service account
gcloud iam service-accounts create railway-service \
    --project=unidad-cumplimiento-aa245 \
    --description="Service account for Railway deployment" \
    --display-name="Railway Service Account"

# 2. Dar permisos de Firebase/Firestore
gcloud projects add-iam-policy-binding unidad-cumplimiento-aa245 \
    --member="serviceAccount:railway-service@unidad-cumplimiento-aa245.iam.gserviceaccount.com" \
    --role="roles/firebase.admin"

gcloud projects add-iam-policy-binding unidad-cumplimiento-aa245 \
    --member="serviceAccount:railway-service@unidad-cumplimiento-aa245.iam.gserviceaccount.com" \
    --role="roles/datastore.user"
```

### 3. Configurar IAM Binding

```bash
# Permitir que Railway impersone el service account
gcloud iam service-accounts add-iam-policy-binding \
    railway-service@unidad-cumplimiento-aa245.iam.gserviceaccount.com \
    --project=unidad-cumplimiento-aa245 \
    --role="roles/iam.workloadIdentityUser" \
    --member="principalSet://iam.googleapis.com/projects/PROJECT_NUMBER/locations/global/workloadIdentityPools/railway-pool/attribute.project_id/YOUR_RAILWAY_PROJECT_ID"
```

### 4. Obtener información del Provider

```bash
# Obtener el provider path completo
gcloud iam workload-identity-pools providers describe railway-provider \
    --project=unidad-cumplimiento-aa245 \
    --location=global \
    --workload-identity-pool=railway-pool \
    --format="value(name)"
```

### 5. Generar archivo de credenciales

```bash
# Generar el JSON de credenciales para Railway
gcloud iam workload-identity-pools create-cred-config \
    projects/PROJECT_NUMBER/locations/global/workloadIdentityPools/railway-pool/providers/railway-provider \
    --service-account=railway-service@unidad-cumplimiento-aa245.iam.gserviceaccount.com \
    --output-file=railway-workload-identity.json
```

## 🚀 Variables para Railway

Una vez completados los pasos anteriores, configura estas variables en Railway:

```bash
# Proyecto
GOOGLE_CLOUD_PROJECT=unidad-cumplimiento-aa245
FIREBASE_PROJECT_ID=unidad-cumplimiento-aa245

# Workload Identity
GOOGLE_APPLICATION_CREDENTIALS_JSON=<contenido-completo-del-archivo-railway-workload-identity.json>

# Firestore
FIRESTORE_BATCH_SIZE=500
FIRESTORE_TIMEOUT=30
```

## ⚠️ Notas importantes:

1. **PROJECT_NUMBER**: Reemplaza con el número de tu proyecto (no el ID)
2. **YOUR_RAILWAY_PROJECT_ID**: Reemplaza con el ID de tu proyecto Railway
3. El archivo `railway-workload-identity.json` debe ser copiado completo como variable de entorno
4. Railway automáticamente proveerá el token de identidad necesario

## ✅ Ventajas de Workload Identity Federation:

- ✅ Más seguro (no hay keys privadas)
- ✅ Tokens temporales y rotación automática
- ✅ Mejor auditabilidad
- ✅ Cumple con mejores prácticas de seguridad
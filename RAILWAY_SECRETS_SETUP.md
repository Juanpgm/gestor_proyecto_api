# � WORKLOAD IDENTITY FEDERATION SETUP GUIDE

## 🎯 ¿Qué es Workload Identity Federation (WIF)?

- **Más seguro**: No hay claves JSON que rotar
- **Tokens temporales**: Autenticación automática con Google Cloud
- **Zero secrets**: No necesitas almacenar credenciales

## �️ PASO 1: Configurar WIF en Google Cloud

### 1.1 Crear Workload Identity Pool

```bash
# Habilitar APIs necesarias
gcloud services enable iamcredentials.googleapis.com
gcloud services enable sts.googleapis.com

# Crear pool de identidades
gcloud iam workload-identity-pools create "github-pool" \
  --project="dev-test-e778d" \
  --location="global" \
  --display-name="GitHub Actions Pool"
```

### 1.2 Crear Provider para GitHub Actions

```bash
gcloud iam workload-identity-pools providers create-oidc "github-provider" \
  --project="dev-test-e778d" \
  --location="global" \
  --workload-identity-pool="github-pool" \
  --display-name="GitHub Actions Provider" \
  --attribute-mapping="google.subject=assertion.sub,attribute.actor=assertion.actor,attribute.repository=assertion.repository,attribute.repository_owner=assertion.repository_owner" \
  --issuer-uri="https://token.actions.githubusercontent.com"
```

### 1.3 Crear Service Account (si no existe)

```bash
gcloud iam service-accounts create "github-actions-sa" \
  --project="dev-test-e778d" \
  --display-name="GitHub Actions Service Account"

# Dar permisos a Firebase
gcloud projects add-iam-policy-binding "dev-test-e778d" \
  --member="serviceAccount:github-actions-sa@dev-test-e778d.iam.gserviceaccount.com" \
  --role="roles/firebase.admin"

gcloud projects add-iam-policy-binding "dev-test-e778d" \
  --member="serviceAccount:github-actions-sa@dev-test-e778d.iam.gserviceaccount.com" \
  --role="roles/datastore.user"
```

### 1.4 Configurar IAM Binding

```bash
gcloud iam service-accounts add-iam-policy-binding \
  "github-actions-sa@dev-test-e778d.iam.gserviceaccount.com" \
  --project="dev-test-e778d" \
  --role="roles/iam.workloadIdentityUser" \
  --member="principalSet://iam.googleapis.com/projects/PROJECT_NUMBER/locations/global/workloadIdentityPools/github-pool/attribute.repository/Juanpgm/gestor_proyecto_api"
```

## 🔑 PASO 2: Configurar GitHub Secrets (SOLO 2 secrets!)

Ve a: `https://github.com/Juanpgm/gestor_proyecto_api/settings/secrets/actions`

**Secrets necesarios:**

1. **`WIF_PROVIDER_ID`**

   ```
   projects/PROJECT_NUMBER/locations/global/workloadIdentityPools/github-pool/providers/github-provider
   ```

2. **`WIF_SERVICE_ACCOUNT`**
   ```
   github-actions-sa@dev-test-e778d.iam.gserviceaccount.com
   ```

## 🚀 PASO 3: Railway Configuration (Método híbrido)

Para **Railway**, aún necesitas un Service Account (Railway no soporta WIF nativamente):

### Variables de entorno en Railway:

```
FIREBASE_PROJECT_ID=dev-test-e778d
GOOGLE_CLOUD_PROJECT=dev-test-e778d
FIREBASE_SERVICE_ACCOUNT_KEY=[base64-encoded-service-account]
```

### 🔧 Crear Service Account para Railway:

```bash
gcloud iam service-accounts create "railway-sa" \
  --project="dev-test-e778d" \
  --display-name="Railway Service Account"

gcloud projects add-iam-policy-binding "dev-test-e778d" \
  --member="serviceAccount:railway-sa@dev-test-e778d.iam.gserviceaccount.com" \
  --role="roles/firebase.admin"

# Generar clave para Railway
gcloud iam service-accounts keys create railway-key.json \
  --iam-account="railway-sa@dev-test-e778d.iam.gserviceaccount.com"

# Convertir a Base64
base64 -i railway-key.json > railway-key-base64.txt
```

## 📋 RESUMEN: Dos configuraciones diferentes

### 🐙 GitHub Actions: WIF (Sin secrets!)

- `WIF_PROVIDER_ID`
- `WIF_SERVICE_ACCOUNT`

### 🚄 Railway: Service Account tradicional

- `FIREBASE_PROJECT_ID`
- `GOOGLE_CLOUD_PROJECT`
- `FIREBASE_SERVICE_ACCOUNT_KEY` (Base64)

## � Obtener PROJECT_NUMBER:

```bash
gcloud projects describe dev-test-e778d --format="value(projectNumber)"
```

## ✅ Verificar configuración:

```bash
# Test WIF
gcloud auth print-identity-token \
  --audiences=https://iam.googleapis.com/projects/PROJECT_NUMBER/locations/global/workloadIdentityPools/github-pool/providers/github-provider
```

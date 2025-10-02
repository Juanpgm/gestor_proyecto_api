#!/bin/bash

# 🔐 Script de configuración automática de Workload Identity Federation para Railway
# Ejecuta este script después de tener configurado gcloud con tu proyecto

PROJECT_ID="unidad-cumplimiento-aa245"
POOL_ID="railway-pool"
PROVIDER_ID="railway-provider"
SERVICE_ACCOUNT_NAME="railway-service"

echo "🚀 Configurando Workload Identity Federation para Railway..."
echo "Proyecto: $PROJECT_ID"

# Obtener el número del proyecto
PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format="value(projectNumber)")
echo "📊 Número del proyecto: $PROJECT_NUMBER"

# 1. Habilitar APIs necesarias
echo "📡 Habilitando APIs necesarias..."
gcloud services enable iamcredentials.googleapis.com --project=$PROJECT_ID
gcloud services enable sts.googleapis.com --project=$PROJECT_ID
gcloud services enable firebase.googleapis.com --project=$PROJECT_ID

# 2. Crear Workload Identity Pool
echo "🏊 Creando Workload Identity Pool..."
gcloud iam workload-identity-pools create $POOL_ID \
    --project=$PROJECT_ID \
    --location=global \
    --display-name="Railway Workload Identity Pool" \
    --description="Pool para autenticación de Railway con Firebase"

# 3. Crear Provider OIDC para Railway
echo "🔗 Creando Provider OIDC para Railway..."
gcloud iam workload-identity-pools providers create-oidc $PROVIDER_ID \
    --project=$PROJECT_ID \
    --location=global \
    --workload-identity-pool=$POOL_ID \
    --issuer-uri="https://railway.app" \
    --attribute-mapping="google.subject=assertion.sub,attribute.project_id=assertion.project_id" \
    --attribute-condition="assertion.aud=='railway'"

# 4. Crear Service Account
echo "👤 Creando Service Account..."
gcloud iam service-accounts create $SERVICE_ACCOUNT_NAME \
    --project=$PROJECT_ID \
    --description="Service Account para Railway deployment con Firebase" \
    --display-name="Railway Firebase Service Account"

# 5. Asignar permisos Firebase
echo "🔐 Asignando permisos Firebase..."
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:$SERVICE_ACCOUNT_NAME@$PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/firebase.admin"

gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:$SERVICE_ACCOUNT_NAME@$PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/datastore.user"

# 6. Permitir que Railway use el Service Account
echo "🚂 Configurando permisos para Railway..."
echo "⚠️  IMPORTANTE: Necesitas obtener tu Railway Project ID de https://railway.app/dashboard"
echo "📝 Formato del Railway Project ID: algo como 'a1b2c3d4-e5f6-7890-ab12-cd34ef567890'"
read -p "🔤 Ingresa tu Railway Project ID: " RAILWAY_PROJECT_ID

gcloud iam service-accounts add-iam-policy-binding \
    $SERVICE_ACCOUNT_NAME@$PROJECT_ID.iam.gserviceaccount.com \
    --project=$PROJECT_ID \
    --role="roles/iam.workloadIdentityUser" \
    --member="principalSet://iam.googleapis.com/projects/$PROJECT_NUMBER/locations/global/workloadIdentityPools/$POOL_ID/attribute.project_id/$RAILWAY_PROJECT_ID"

# 7. Generar archivo de credenciales
echo "📄 Generando archivo de credenciales..."
PROVIDER_PATH="projects/$PROJECT_NUMBER/locations/global/workloadIdentityPools/$POOL_ID/providers/$PROVIDER_ID"

gcloud iam workload-identity-pools create-cred-config \
    $PROVIDER_PATH \
    --service-account=$SERVICE_ACCOUNT_NAME@$PROJECT_ID.iam.gserviceaccount.com \
    --output-file=railway-workload-identity.json

echo ""
echo "✅ ¡Configuración completada!"
echo ""
echo "📋 Variables para Railway Dashboard:"
echo "GOOGLE_CLOUD_PROJECT=$PROJECT_ID"
echo "FIREBASE_PROJECT_ID=$PROJECT_ID"
echo "FIRESTORE_BATCH_SIZE=500"
echo "FIRESTORE_TIMEOUT=30"
echo ""
echo "📄 El archivo 'railway-workload-identity.json' ha sido generado."
echo "🔐 Copia TODO el contenido de este archivo como variable:"
echo "    GOOGLE_APPLICATION_CREDENTIALS_JSON=<contenido-completo-del-archivo>"
echo ""
echo "📖 Para ver el contenido del archivo:"
echo "    cat railway-workload-identity.json"
echo ""
echo "🚀 Una vez configuradas las variables en Railway, tu API debería conectar automáticamente con Firebase."
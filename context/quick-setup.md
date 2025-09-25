# 🚀 Configuración Rápida - Proyectos Cali ETL

## ⚡ Setup de 5 minutos

### 1. Instalar Google Cloud CLI

```bash
# Windows
winget install Google.CloudSDK

# Linux
curl https://sdk.cloud.google.com | bash

# macOS
brew install --cask google-cloud-sdk
```

### 2. Configurar proyecto

```bash
gcloud config set project dev-test-e778d
gcloud auth login
gcloud auth application-default login
```

### 3. Habilitar servicios

```bash
gcloud services enable firebase.googleapis.com firestore.googleapis.com
gcloud firestore databases create --location=us-central1
```

### 4. Probar configuración

```bash
python database/config.py
```

## 🎯 Variables de Entorno

Archivo `.env` ya configurado:

```env
FIREBASE_PROJECT_ID=dev-test-e778d
FIRESTORE_BATCH_SIZE=500
FIRESTORE_TIMEOUT=30
```

## 📦 Dependencias Python

```bash
pip install firebase-admin python-dotenv
```

## ✅ Verificación

Si ves este mensaje, todo está listo:

```
✅ Firebase listo para ETL
🎯 Configuración completada exitosamente
💾 Sistema listo para cargar datos
```

## 🔗 Enlaces Útiles

- [Firebase Console](https://console.firebase.google.com/project/dev-test-e778d)
- [Google Cloud Console](https://console.cloud.google.com/firestore?project=dev-test-e778d)
- [Documentación completa](./firebase-workload-identity-setup.md)

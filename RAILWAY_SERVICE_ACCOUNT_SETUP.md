# 🔑 Cómo obtener Service Account para Railway

## Pasos para obtener las credenciales:

### 1. Firebase Console

1. Ve a Firebase Console: https://console.firebase.google.com/
2. Selecciona tu proyecto: `unidad-cumplimiento-aa245`
3. Ve a "Project Settings" (ícono de engranaje)
4. Pestaña "Service accounts"
5. Click en "Generate new private key"
6. Descarga el archivo JSON

### 2. Preparar para Railway

```bash
# Codifica el archivo JSON en base64
base64 -i path/to/service-account.json

# O en Windows PowerShell:
[Convert]::ToBase64String([System.IO.File]::ReadAllBytes("path\to\service-account.json"))
```

### 3. En Railway Dashboard

1. Variables → Add Variable
2. Nombre: `FIREBASE_SERVICE_ACCOUNT_KEY`
3. Valor: El string base64 completo (sin saltos de línea)

### 4. Variables adicionales requeridas:

```
FIREBASE_PROJECT_ID=unidad-cumplimiento-aa245
GOOGLE_CLOUD_PROJECT=unidad-cumplimiento-aa245
FIRESTORE_BATCH_SIZE=500
FIRESTORE_TIMEOUT=30
```

## ✅ Verificación

Una vez configurado, en los logs de Railway deberías ver:

```
✅ Using Service Account credentials for unidad-cumplimiento-aa245
✅ Firebase initialized successfully
```

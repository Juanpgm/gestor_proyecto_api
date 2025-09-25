# 🔐 Configuración de Firebase con Workload Identity Federation

## 📋 Introducción

Este documento proporciona instrucciones completas para configurar Firebase usando **Workload Identity Federation**, eliminando la necesidad de archivos de claves de cuenta de servicio estáticas. Esta es la práctica de seguridad recomendada por Google Cloud.

## 🎯 Ventajas de Workload Identity Federation

- ✅ **Sin archivos de claves estáticas** - Mayor seguridad
- ✅ **Rotación automática de credenciales** - Reduce riesgos
- ✅ **Auditoría completa** - Trazabilidad de accesos
- ✅ **Principio de menor privilegio** - Permisos granulares
- ✅ **Compatible con múltiples entornos** - Desarrollo y producción

## 🛠️ Requisitos Previos

- Cuenta de Google Cloud con proyecto Firebase
- Permisos de administrador en el proyecto
- Acceso a terminal/línea de comandos

## 📦 Instalación de Google Cloud CLI

### Windows

#### Opción 1: Winget (Recomendado)

```powershell
winget install Google.CloudSDK
```

#### Opción 2: Chocolatey

```powershell
choco install gcloudsdk
```

#### Opción 3: Descarga directa

1. Descargar desde: https://cloud.google.com/sdk/docs/install-sdk
2. Ejecutar el instalador descargado
3. Seguir las instrucciones en pantalla

### Linux

#### Ubuntu/Debian

```bash
# Añadir repositorio de Google Cloud
echo "deb [signed-by=/usr/share/keyrings/cloud.google.gpg] https://packages.cloud.google.com/apt cloud-sdk main" | sudo tee -a /etc/apt/sources.list.d/google-cloud-sdk.list

# Importar clave pública de Google Cloud
curl https://packages.cloud.google.com/apt/doc/apt-key.gpg | sudo apt-key --keyring /usr/share/keyrings/cloud.google.gpg add -

# Instalar
sudo apt-get update && sudo apt-get install google-cloud-cli
```

#### CentOS/RHEL/Fedora

```bash
# Crear archivo de repositorio
sudo tee -a /etc/yum.repos.d/google-cloud-sdk.repo << EOM
[google-cloud-cli]
name=Google Cloud CLI
baseurl=https://packages.cloud.google.com/yum/repos/cloud-sdk-el8-x86_64
enabled=1
gpgcheck=1
repo_gpgcheck=0
gpgkey=https://packages.cloud.google.com/yum/doc/yum-key.gpg
       https://packages.cloud.google.com/yum/doc/rpm-package-key.gpg
EOM

# Instalar
sudo dnf install google-cloud-cli
```

#### Script universal

```bash
curl https://sdk.cloud.google.com | bash
exec -l $SHELL
```

### macOS

#### Homebrew

```bash
brew install --cask google-cloud-sdk
```

#### Script manual

```bash
curl https://sdk.cloud.google.com | bash
exec -l $SHELL
```

## 🔧 Configuración Inicial

### 1. Verificar instalación

```bash
gcloud --version
```

### 2. Inicializar gcloud

```bash
gcloud init
```

### 3. Configurar proyecto

```bash
# Reemplazar YOUR_PROJECT_ID con tu ID de proyecto
gcloud config set project YOUR_PROJECT_ID
```

### 4. Autenticación

```bash
# Autenticación para uso personal
gcloud auth login

# Configurar Application Default Credentials (ADC)
gcloud auth application-default login
```

## 🔥 Configuración de Firebase

### 1. Habilitar APIs necesarias

```bash
# API de Firebase Admin
gcloud services enable firebase.googleapis.com

# API de Firestore
gcloud services enable firestore.googleapis.com

# API de Firebase Hosting (opcional)
gcloud services enable firebasehosting.googleapis.com
```

### 2. Crear base de datos Firestore

```bash
# Crear base de datos en modo nativo
gcloud firestore databases create --location=us-central1

# Verificar creación
gcloud firestore databases list
```

### 3. Configurar reglas de seguridad (opcional)

```bash
# Para desarrollo (permitir lectura/escritura)
gcloud firestore indexes create --index-from-file=firestore.indexes.json
```

## 🌍 Configuración de Variables de Entorno

### Crear archivo `.env`

```env
# ID del proyecto Firebase
FIREBASE_PROJECT_ID=your-project-id

# Configuración ETL (opcional)
FIRESTORE_BATCH_SIZE=500
FIRESTORE_TIMEOUT=30
FIREBASE_RETRY_ATTEMPTS=3
```

### Variables del sistema (alternativa)

```bash
# Linux/macOS
export FIREBASE_PROJECT_ID="your-project-id"
export GOOGLE_CLOUD_PROJECT="your-project-id"

# Windows PowerShell
$env:FIREBASE_PROJECT_ID = "your-project-id"
$env:GOOGLE_CLOUD_PROJECT = "your-project-id"

# Windows CMD
set FIREBASE_PROJECT_ID=your-project-id
set GOOGLE_CLOUD_PROJECT=your-project-id
```

## 🏗️ Configuración para Entornos Específicos

### Desarrollo Local

```bash
# Usar credenciales personales
gcloud auth application-default login
```

### Google Cloud Platform (GCP)

```bash
# Las credenciales se obtienen automáticamente del metadata server
# No requiere configuración adicional
```

### Amazon Web Services (AWS)

```bash
# Configurar Workload Identity Federation
gcloud iam workload-identity-pools create POOL_ID \
    --project=PROJECT_ID \
    --location=global \
    --display-name="AWS Pool"

# Configurar proveedor AWS
gcloud iam workload-identity-pools providers create-aws PROVIDER_ID \
    --project=PROJECT_ID \
    --location=global \
    --workload-identity-pool=POOL_ID \
    --account-id=AWS_ACCOUNT_ID
```

### Microsoft Azure

```bash
# Configurar pool de identidad
gcloud iam workload-identity-pools create POOL_ID \
    --project=PROJECT_ID \
    --location=global \
    --display-name="Azure Pool"

# Configurar proveedor Azure
gcloud iam workload-identity-pools providers create-oidc PROVIDER_ID \
    --project=PROJECT_ID \
    --location=global \
    --workload-identity-pool=POOL_ID \
    --issuer-uri=https://login.microsoftonline.com/TENANT_ID/v2.0 \
    --allowed-audiences=AUDIENCE
```

### Docker/Kubernetes

```yaml
# Ejemplo de configuración en Kubernetes
apiVersion: v1
kind: ServiceAccount
metadata:
  name: workload-identity-sa
  annotations:
    iam.gke.io/gcp-service-account: GSA_NAME@PROJECT_ID.iam.gserviceaccount.com

---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: app
spec:
  template:
    spec:
      serviceAccountName: workload-identity-sa
      containers:
        - name: app
          image: your-app
          env:
            - name: GOOGLE_CLOUD_PROJECT
              value: "your-project-id"
```

## 🧪 Verificación de Configuración

### Script de prueba

```python
#!/usr/bin/env python3
"""Script para verificar la configuración de Firebase"""

import os
from database.config import setup_firebase, test_connection

def main():
    print("🔍 Verificando configuración de Firebase...")

    # Mostrar variables de entorno
    project_id = os.getenv('FIREBASE_PROJECT_ID', 'No configurado')
    print(f"📊 Project ID: {project_id}")

    # Probar configuración
    if setup_firebase():
        print("✅ Configuración exitosa")

        # Probar conexión
        if test_connection():
            print("✅ Conexión a Firestore exitosa")
        else:
            print("❌ Error de conexión a Firestore")
    else:
        print("❌ Error en configuración")

if __name__ == "__main__":
    main()
```

### Comandos de verificación

```bash
# Verificar autenticación
gcloud auth list

# Verificar proyecto activo
gcloud config get-value project

# Verificar APIs habilitadas
gcloud services list --enabled

# Probar acceso a Firestore
gcloud firestore collections list
```

## 🚨 Resolución de Problemas

### Error: "Default credentials not found"

```bash
# Solución: Configurar ADC
gcloud auth application-default login
```

### Error: "Permission denied"

```bash
# Verificar roles del usuario
gcloud projects get-iam-policy PROJECT_ID

# Agregar rol necesario
gcloud projects add-iam-policy-binding PROJECT_ID \
    --member="user:EMAIL" \
    --role="roles/firebase.admin"
```

### Error: "Firestore database does not exist"

```bash
# Crear base de datos
gcloud firestore databases create --location=us-central1
```

### Error: "API not enabled"

```bash
# Habilitar APIs necesarias
gcloud services enable firebase.googleapis.com firestore.googleapis.com
```

## 🔒 Mejores Prácticas de Seguridad

### Roles y Permisos Mínimos

```bash
# Para desarrollo
gcloud projects add-iam-policy-binding PROJECT_ID \
    --member="user:EMAIL" \
    --role="roles/firebase.develop"

# Para producción
gcloud projects add-iam-policy-binding PROJECT_ID \
    --member="serviceAccount:SA_EMAIL" \
    --role="roles/datastore.user"
```

### Rotación de Credenciales

```bash
# Las credenciales ADC se renuevan automáticamente
# Para forzar renovación:
gcloud auth application-default login --force
```

### Auditoría y Monitoreo

```bash
# Habilitar logs de auditoría
gcloud logging sinks create firestore-audit \
    bigquery.googleapis.com/projects/PROJECT_ID/datasets/DATASET_ID \
    --log-filter='resource.type="gce_instance"'
```

## 📊 Monitoreo y Alertas

### Configurar alertas de uso

```bash
# Crear política de alerta para cuota de Firestore
gcloud alpha monitoring policies create --policy-from-file=alert-policy.yaml
```

### Métricas importantes

- Operaciones de lectura/escritura por minuto
- Errores de autenticación
- Uso de cuota
- Latencia de operaciones

## 🔄 Migración desde Cuentas de Servicio

### 1. Backup de configuración actual

```bash
# Exportar configuración actual
gcloud config configurations create backup-config
```

### 2. Remover archivos de claves

```bash
# Eliminar referencias a archivos JSON
unset GOOGLE_APPLICATION_CREDENTIALS
```

### 3. Configurar Workload Identity

```bash
# Seguir pasos de configuración ADC
gcloud auth application-default login
```

### 4. Actualizar código

```python
# Antes (con archivo de clave)
from google.oauth2 import service_account
credentials = service_account.Credentials.from_service_account_file('key.json')

# Después (con ADC)
from google.auth import default
credentials, project = default()
```

## 📚 Recursos Adicionales

- [Documentación oficial de Workload Identity Federation](https://cloud.google.com/iam/docs/workload-identity-federation)
- [Guía de migración de cuentas de servicio](https://cloud.google.com/docs/authentication/external/set-up-adc)
- [Mejores prácticas de seguridad](https://cloud.google.com/security/best-practices)
- [Firebase Admin SDK](https://firebase.google.com/docs/admin/setup)

## 🆘 Soporte

Para problemas específicos del proyecto:

1. Verificar logs con `gcloud logging read`
2. Consultar la documentación oficial
3. Crear issue en el repositorio del proyecto

---

**Última actualización:** Septiembre 2025  
**Versión:** 1.0  
**Compatibilidad:** Google Cloud SDK 502.0.0+

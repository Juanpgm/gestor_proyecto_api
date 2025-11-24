# 🚀 Configuración de S3 para Producción

## 🔐 Seguridad de Credenciales

### ✅ Estado Actual de Protección

Las credenciales AWS están **COMPLETAMENTE PROTEGIDAS** y no se subirán a GitHub:

```
✅ credentials/                      → Ignorado en .gitignore
✅ credentials/**                    → Ignorado en .gitignore
✅ context/                          → Ignorado en .gitignore
✅ context/**                        → Ignorado en .gitignore
✅ *.json                           → Ignorado en .gitignore (todos los JSON)
✅ credentials/aws_credentials.json  → NO está en git tracking
```

### 📋 Archivos Seguros

- ✅ `credentials/aws_credentials.json` → **PRIVADO** (contiene credenciales reales)
- ✅ `context/aws_credentials.json` → **PRIVADO** (copia para compatibilidad)
- ✅ `credentials/aws_credentials.json.example` → **PÚBLICO** (plantilla sin credenciales)

---

## 🏗️ Configuración para Desarrollo

### Opción 1: Usar Archivo Local (Ya Configurado)

```bash
# El archivo ya existe en:
credentials/aws_credentials.json
```

El código automáticamente busca credenciales en:

1. `credentials/aws_credentials.json` (ubicación principal)
2. `context/aws_credentials.json` (ubicación legacy)
3. Variables de entorno (fallback para producción)

### Verificar que Funciona

```powershell
python test_s3_connection.py
```

**Resultado esperado:**

```
✅ IMPORT
✅ BOTO3
✅ CREDENTIALS
✅ INIT
✅ BUCKET
✅ UPLOAD
✅ LIST

🎉 ¡Todas las pruebas pasaron! S3 está completamente funcional
```

---

## 🌐 Configuración para Producción

### Opción Recomendada: Variables de Entorno

En producción (Railway, Heroku, AWS, etc.), **NO subas archivos de credenciales**.
Usa variables de entorno en su lugar.

### 1️⃣ Configurar Variables de Entorno en Railway

```bash
# En Railway Dashboard → Variables
AWS_ACCESS_KEY_ID=TU_ACCESS_KEY_ID_AQUI
AWS_SECRET_ACCESS_KEY=TU_SECRET_ACCESS_KEY_AQUI
AWS_REGION=us-east-1
S3_BUCKET_EMPRESTITO=contratos-emprestito
S3_BUCKET_NAME=unidades-proyecto-documents
```

### 2️⃣ Configurar en Heroku

```bash
heroku config:set AWS_ACCESS_KEY_ID=TU_ACCESS_KEY_ID_AQUI
heroku config:set AWS_SECRET_ACCESS_KEY=TU_SECRET_ACCESS_KEY_AQUI
heroku config:set AWS_REGION=us-east-1
heroku config:set S3_BUCKET_EMPRESTITO=contratos-emprestito
heroku config:set S3_BUCKET_NAME=unidades-proyecto-documents
```

### 3️⃣ Configurar en Docker

**docker-compose.yml:**

```yaml
version: "3.8"
services:
  api:
    build: .
    environment:
      - AWS_ACCESS_KEY_ID=${AWS_ACCESS_KEY_ID}
      - AWS_SECRET_ACCESS_KEY=${AWS_SECRET_ACCESS_KEY}
      - AWS_REGION=us-east-1
      - S3_BUCKET_EMPRESTITO=contratos-emprestito
      - S3_BUCKET_NAME=unidades-proyecto-documents
    env_file:
      - .env.production # Archivo local NO subido a git
```

**Crear .env.production (NO subir a git):**

```env
AWS_ACCESS_KEY_ID=TU_ACCESS_KEY_ID_AQUI
AWS_SECRET_ACCESS_KEY=TU_SECRET_ACCESS_KEY_AQUI
AWS_REGION=us-east-1
S3_BUCKET_EMPRESTITO=contratos-emprestito
S3_BUCKET_NAME=unidades-proyecto-documents
```

### 4️⃣ Configurar en AWS EC2 / Linux

**Opción A: Variables de entorno en el sistema**

```bash
# Agregar al archivo ~/.bashrc o ~/.profile
export AWS_ACCESS_KEY_ID="TU_ACCESS_KEY_ID_AQUI"
export AWS_SECRET_ACCESS_KEY="TU_SECRET_ACCESS_KEY_AQUI"
export AWS_REGION="us-east-1"
export S3_BUCKET_EMPRESTITO="contratos-emprestito"
export S3_BUCKET_NAME="unidades-proyecto-documents"

# Recargar
source ~/.bashrc
```

**Opción B: Usar IAM Role (Más seguro en AWS)**
Si tu aplicación corre en EC2, ECS o Lambda, usa un IAM Role en lugar de credenciales:

1. Crear un IAM Role con permisos S3
2. Asociar el Role a tu instancia EC2/ECS/Lambda
3. El código detectará automáticamente las credenciales del role

---

## 🔄 Cómo Funciona el Sistema de Credenciales

El código tiene un **sistema de fallback inteligente**:

```python
# 1. Intenta cargar desde archivo local (desarrollo)
credentials/aws_credentials.json

# 2. Si no existe, intenta la ubicación legacy
context/aws_credentials.json

# 3. Si no existe, usa variables de entorno (producción)
AWS_ACCESS_KEY_ID
AWS_SECRET_ACCESS_KEY
AWS_REGION
S3_BUCKET_EMPRESTITO
```

Esto permite:

- ✅ **Desarrollo**: Usar archivo local `credentials/aws_credentials.json`
- ✅ **Producción**: Usar variables de entorno (más seguro)
- ✅ **Sin cambios de código**: El mismo código funciona en ambos ambientes

---

## 🛡️ Mejores Prácticas de Seguridad

### ✅ Hacer (DO)

- ✅ Usar variables de entorno en producción
- ✅ Mantener `credentials/` en `.gitignore`
- ✅ Rotar las credenciales cada 90 días
- ✅ Usar IAM Roles cuando sea posible (en AWS)
- ✅ Limitar permisos del usuario IAM solo a lo necesario
- ✅ Usar archivos `.env` locales (no subidos a git)

### ❌ No Hacer (DON'T)

- ❌ Subir `credentials/aws_credentials.json` a GitHub
- ❌ Compartir credenciales por email o chat
- ❌ Hardcodear credenciales en el código
- ❌ Usar credenciales root de AWS
- ❌ Dar permisos de administrador completo
- ❌ Usar las mismas credenciales en múltiples proyectos

---

## 🔑 Crear Credenciales AWS (Si necesitas nuevas)

### Paso 1: Ir a AWS IAM

1. Acceder a: https://console.aws.amazon.com/iam/
2. Click en **Users** → Tu usuario
3. Tab **Security credentials**
4. **Access keys** → **Create access key**

### Paso 2: Configurar Permisos

Tu usuario IAM necesita esta política mínima:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "S3EmprestitoAccess",
      "Effect": "Allow",
      "Action": [
        "s3:PutObject",
        "s3:GetObject",
        "s3:DeleteObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::contratos-emprestito",
        "arn:aws:s3:::contratos-emprestito/*",
        "arn:aws:s3:::unidades-proyecto-documents",
        "arn:aws:s3:::unidades-proyecto-documents/*"
      ]
    }
  ]
}
```

### Paso 3: Guardar Credenciales de Forma Segura

Opciones recomendadas:

- **1Password** / **LastPass** - Gestores de contraseñas
- **AWS Secrets Manager** - Servicio nativo de AWS
- **HashiCorp Vault** - Para equipos grandes
- **Archivo local encriptado** - Solo para desarrollo

---

## 🧪 Verificación Post-Configuración

### Test Local

```powershell
python test_s3_connection.py
```

### Test desde Producción

```bash
# Conectarse al servidor de producción
ssh user@your-server

# Verificar variables de entorno
env | grep AWS

# Probar conexión
python3 test_s3_connection.py
```

---

## 📊 Checklist de Seguridad

Antes de desplegar a producción, verifica:

- [ ] ✅ `credentials/aws_credentials.json` está en `.gitignore`
- [ ] ✅ No hay credenciales hardcodeadas en el código
- [ ] ✅ Variables de entorno configuradas en el servidor
- [ ] ✅ IAM User tiene permisos mínimos necesarios
- [ ] ✅ Credenciales almacenadas en gestor seguro
- [ ] ✅ `.env.production` está en `.gitignore`
- [ ] ✅ Bucket S3 tiene acceso bloqueado público
- [ ] ✅ Versionamiento habilitado en S3 (auditoría)
- [ ] ✅ Logging habilitado en S3 (CloudTrail)
- [ ] ✅ MFA habilitado en cuenta AWS

---

## 🚨 Qué Hacer si las Credenciales se Filtran

### Acción Inmediata (0-5 minutos)

1. **Deshabilitar las credenciales comprometidas**

   ```bash
   # En AWS IAM Console → Users → Security credentials
   # Click en "Make inactive" en el Access Key comprometido
   ```

2. **Crear nuevas credenciales**

   ```bash
   # Crear nuevo Access Key en AWS IAM
   # Actualizar en producción inmediatamente
   ```

3. **Eliminar credenciales comprometidas**
   ```bash
   # Después de actualizar producción, eliminar el Access Key viejo
   ```

### Investigación (5-30 minutos)

4. **Revisar CloudTrail** para actividad sospechosa
5. **Revisar facturas AWS** por cargos inesperados
6. **Cambiar todas las contraseñas** relacionadas

### Prevención (30+ minutos)

7. **Revisar todo el historial de Git**

   ```bash
   git log --all --full-history -- "**/*credentials*"
   ```

8. **Si está en Git, usar herramientas de limpieza**

   ```bash
   # BFG Repo-Cleaner o git-filter-repo
   bfg --delete-files credentials.json
   git push --force
   ```

9. **Notificar al equipo** sobre el incidente

---

## 📞 Soporte

Si tienes problemas:

1. Revisar los logs: `logs/` o salida de consola
2. Verificar variables de entorno: `env | grep AWS`
3. Probar conexión manualmente: `python test_s3_connection.py`
4. Verificar permisos IAM en AWS Console
5. Revisar CloudTrail para errores de acceso

---

**Última actualización**: 2024-11-24  
**Estado**: ✅ CONFIGURADO Y SEGURO  
**Ambiente**: Desarrollo ✅ | Producción ⚙️ (pendiente deployment)

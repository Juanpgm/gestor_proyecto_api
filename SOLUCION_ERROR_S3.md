# 🔧 Solución al Error de Subida a S3

## 🎯 Diagnóstico del Problema

**Estado actual del sistema:**

- ✅ **Frontend**: Funcionando correctamente - Los modales envían los datos en formato `multipart/form-data`
- ✅ **Backend - Recepción**: Funcionando correctamente - Recibe y parsea los archivos
- ✅ **Backend - Validación**: Funcionando correctamente - Valida tipos de archivo
- ❌ **Backend - S3**: **ERROR** - Falla al subir archivos al bucket de AWS S3

## 🔍 Causa Raíz del Error

El archivo de credenciales AWS **NO EXISTE** en el sistema:

- **Archivo requerido**: `context/aws_credentials.json`
- **Estado actual**: ❌ NO ENCONTRADO

El código intenta cargar las credenciales desde este archivo:

```python
# En s3_document_manager.py línea 53
def __init__(self, credentials_path: str = "context/aws_credentials.json"):
```

Cuando no encuentra el archivo, intenta usar variables de entorno, pero estas tampoco están configuradas.

---

## ✅ Solución Paso a Paso

### **Opción 1: Usar Archivo de Credenciales (Recomendado para desarrollo)**

#### Paso 1: Crear el archivo de credenciales

Copiar el archivo de ejemplo y renombrarlo:

```powershell
# Desde la raíz del proyecto
Copy-Item "context\aws_credentials.json.example" "context\aws_credentials.json"
```

#### Paso 2: Editar el archivo con tus credenciales reales

Abrir `context/aws_credentials.json` y reemplazar con tus credenciales AWS:

```json
{
  "aws_access_key_id": "AKIAIOSFODNN7EXAMPLE",
  "aws_secret_access_key": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
  "aws_region": "us-east-1",
  "bucket_name": "unidades-proyecto-documents",
  "bucket_name_emprestito": "contratos-emprestito"
}
```

**Donde obtener las credenciales:**

1. Ir a AWS Console → IAM → Users → Tu usuario
2. Ir a "Security credentials"
3. En "Access keys" → "Create access key"
4. Copiar el `Access key ID` y `Secret access key`

#### Paso 3: Verificar que el archivo NO se suba a Git

El archivo `.gitignore` ya debería incluir:

```
context/aws_credentials.json
```

Verificar con:

```powershell
Get-Content .gitignore | Select-String "aws_credentials"
```

---

### **Opción 2: Usar Variables de Entorno (Recomendado para producción)**

#### Paso 1: Crear o editar el archivo `.env`

Si no existe, crear el archivo `.env` en la raíz del proyecto:

```env
# AWS S3 Configuration
AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE
AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
AWS_REGION=us-east-1
S3_BUCKET_EMPRESTITO=contratos-emprestito
```

#### Paso 2: Cargar las variables de entorno

En tu script de inicio o en el servidor, las variables se cargarán automáticamente desde `.env`.

Si ejecutas localmente:

```powershell
# PowerShell
$env:AWS_ACCESS_KEY_ID = "AKIAIOSFODNN7EXAMPLE"
$env:AWS_SECRET_ACCESS_KEY = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
$env:AWS_REGION = "us-east-1"
$env:S3_BUCKET_EMPRESTITO = "contratos-emprestito"
```

---

## 🔐 Configuración del Bucket S3

### Paso 1: Verificar que el bucket existe

1. Ir a AWS Console → S3
2. Buscar el bucket `contratos-emprestito`
3. Si NO existe, crearlo:
   - Click en "Create bucket"
   - Nombre: `contratos-emprestito`
   - Región: `us-east-1`
   - Block Public Access: **Todas las opciones marcadas** (bucket privado)

### Paso 2: Configurar permisos IAM

Tu usuario de AWS debe tener los siguientes permisos sobre el bucket:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:PutObject",
        "s3:GetObject",
        "s3:DeleteObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::contratos-emprestito",
        "arn:aws:s3:::contratos-emprestito/*"
      ]
    }
  ]
}
```

**Aplicar la política:**

1. Ir a IAM → Users → Tu usuario
2. Click en "Add permissions" → "Attach policies directly"
3. Click en "Create policy" → Pegar el JSON
4. Nombrar: `ContratosEmprestitoS3Access`
5. Asociar al usuario

---

## 🧪 Verificar la Solución

### Test 1: Verificar que boto3 está instalado

```powershell
pip list | Select-String "boto3"
```

Si no está instalado:

```powershell
pip install boto3
```

### Test 2: Verificar credenciales

Ejecutar este script de prueba:

```python
# test_s3_connection.py
import os
import json
from api.utils.s3_document_manager import S3DocumentManager

try:
    # Intentar inicializar S3Manager
    s3_manager = S3DocumentManager()
    print("✅ S3DocumentManager inicializado correctamente")
    print(f"   Bucket: {s3_manager.bucket_name}")
    print(f"   Región: {s3_manager.region}")

    # Verificar que el bucket existe
    if s3_manager.verify_bucket_exists():
        print("✅ Bucket accesible")
    else:
        print("❌ Bucket no accesible")

except FileNotFoundError:
    print("❌ Archivo de credenciales no encontrado")
    print("   Crear: context/aws_credentials.json")
except Exception as e:
    print(f"❌ Error: {e}")
```

Ejecutar:

```powershell
python test_s3_connection.py
```

**Resultado esperado:**

```
✅ S3DocumentManager inicializado correctamente
   Bucket: contratos-emprestito
   Región: us-east-1
✅ Bucket accesible
```

### Test 3: Probar el endpoint completo

Una vez configurado, probar el endpoint de RPC:

```bash
curl -X POST "http://localhost:8000/emprestito/cargar-rpc" \
  -F "numero_rpc=RPC-TEST-001" \
  -F "beneficiario_id=123456789" \
  -F "beneficiario_nombre=Test Proveedor" \
  -F "descripcion_rpc=Prueba de subida" \
  -F "fecha_contabilizacion=2024-11-24" \
  -F "fecha_impresion=2024-11-24" \
  -F "estado_liberacion=Liberado" \
  -F "bp=BP-TEST-001" \
  -F "valor_rpc=1000000" \
  -F "nombre_centro_gestor=Centro Test" \
  -F "referencia_contrato=CONT-TEST-001" \
  -F "documentos=@test_file.pdf"
```

---

## 📋 Checklist de Verificación

Completar estos pasos en orden:

- [ ] **Paso 1**: Verificar que boto3 está instalado (`pip install boto3`)
- [ ] **Paso 2**: Crear `context/aws_credentials.json` con credenciales reales
- [ ] **Paso 3**: Verificar que el archivo NO está en Git (`.gitignore`)
- [ ] **Paso 4**: Verificar que el bucket `contratos-emprestito` existe en AWS
- [ ] **Paso 5**: Verificar permisos IAM del usuario AWS
- [ ] **Paso 6**: Ejecutar `test_s3_connection.py` para verificar conectividad
- [ ] **Paso 7**: Probar el endpoint con un archivo real
- [ ] **Paso 8**: Verificar en AWS S3 que el archivo se subió correctamente

---

## 🔄 Flujo Corregido

```
Usuario llena modal → Envía datos + archivos (multipart/form-data)
           ↓
Backend recibe request → Valida tipos de archivo
           ↓
Backend lee credenciales → Inicializa S3DocumentManager
           ↓
S3Manager valida archivos → Genera S3 keys
           ↓
S3Manager sube a AWS S3 → Obtiene URLs
           ↓
Backend guarda en Firebase → Incluye referencias S3
           ↓
Respuesta al frontend → Con URLs de documentos
```

---

## 🚨 Errores Comunes y Soluciones

### Error: "boto3 no está instalado"

**Solución**: `pip install boto3`

### Error: "Archivo de credenciales no encontrado"

**Solución**: Crear `context/aws_credentials.json` con credenciales válidas

### Error: "NoCredentialsError"

**Solución**: Verificar que las credenciales en el archivo son correctas

### Error: "Bucket no existe"

**Solución**: Crear el bucket `contratos-emprestito` en AWS S3 (región us-east-1)

### Error: "AccessDenied"

**Solución**: Verificar permisos IAM - el usuario debe tener `s3:PutObject`, `s3:GetObject`, `s3:ListBucket`

### Error: "InvalidAccessKeyId"

**Solución**: Las credenciales AWS son inválidas - generar nuevas desde IAM

### Error: "SignatureDoesNotMatch"

**Solución**: El `aws_secret_access_key` es incorrecto - verificar que se copió completo

---

## 📞 Soporte

Si después de seguir estos pasos sigues teniendo problemas:

1. Revisar los logs del backend para el error específico
2. Verificar en AWS CloudTrail si hay intentos de acceso
3. Confirmar que las credenciales son las correctas
4. Verificar conectividad de red con AWS

---

**Última actualización**: 2024-11-24  
**Estado**: ✅ DOCUMENTADO - Pendiente configuración por usuario

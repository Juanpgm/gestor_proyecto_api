# 🚨 SOLUCIÓN INMEDIATA - Error al Subir Archivos a S3

## 📊 Diagnóstico Confirmado

**Estado del Sistema:**

- ✅ Frontend: Funcionando correctamente
- ✅ Backend (recepción): Funcionando correctamente
- ✅ Backend (validación): Funcionando correctamente
- ❌ **Backend (S3)**: **FALLO - Archivo de credenciales no existe**

## 🎯 Causa del Error

**El archivo de credenciales AWS está faltante:**

```
❌ context/aws_credentials.json → NO EXISTE
```

## ✅ Solución en 3 Pasos (5 minutos)

### **OPCIÓN 1: Configurador Automático (Recomendado)** ⭐

Ejecuta el script interactivo que te guiará paso a paso:

```powershell
python setup_aws_credentials.py
```

El script te pedirá:

1. AWS Access Key ID
2. AWS Secret Access Key
3. Región (por defecto: us-east-1)
4. Nombre del bucket (por defecto: contratos-emprestito)

---

### **OPCIÓN 2: Configuración Manual**

#### Paso 1: Copiar el archivo de ejemplo

```powershell
Copy-Item "context\aws_credentials.json.example" "context\aws_credentials.json"
```

#### Paso 2: Editar con tus credenciales

Abrir `context/aws_credentials.json` y reemplazar:

```json
{
  "aws_access_key_id": "TU_ACCESS_KEY_ID_REAL",
  "aws_secret_access_key": "TU_SECRET_KEY_REAL",
  "aws_region": "us-east-1",
  "bucket_name": "unidades-proyecto-documents",
  "bucket_name_emprestito": "contratos-emprestito"
}
```

**¿Dónde obtener las credenciales?**

1. Ir a: https://console.aws.amazon.com/iam/
2. Ir a: Users → [Tu Usuario] → Security credentials
3. En "Access keys" → "Create access key"
4. Copiar el Access Key ID y Secret Access Key

#### Paso 3: Verificar instalación de boto3

```powershell
pip install boto3
```

---

## 🧪 Verificar que Funciona

Ejecutar el script de prueba:

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

## 🔐 Verificar Seguridad

El archivo `.gitignore` ya protege tus credenciales:

- ✅ `context/` está ignorado
- ✅ `*.json` está ignorado

**Nunca** compartas o subas a Git el archivo `context/aws_credentials.json`

---

## ⚠️ Troubleshooting

### Error: "Bucket no existe"

**Solución:** Crear el bucket en AWS S3

1. Ir a: https://s3.console.aws.amazon.com/
2. Click en "Create bucket"
3. Nombre: `contratos-emprestito`
4. Región: `us-east-1`
5. Block Public Access: **Todas marcadas**
6. Click "Create bucket"

### Error: "AccessDenied"

**Solución:** Tu usuario AWS necesita permisos sobre el bucket

Agregar esta política IAM a tu usuario:

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

### Error: "boto3 no está instalado"

**Solución:**

```powershell
pip install boto3
```

### Error: "NoCredentialsError"

**Solución:** Las credenciales en el archivo son incorrectas

- Verificar que copiaste correctamente el Access Key y Secret Key
- Asegurarte de que no hay espacios extra
- Regenerar las credenciales desde AWS IAM si es necesario

---

## 📋 Checklist Rápido

Completa esto en orden:

- [ ] **1.** Ejecutar `python setup_aws_credentials.py` O copiar manualmente el archivo
- [ ] **2.** Editar `context/aws_credentials.json` con credenciales reales
- [ ] **3.** Verificar que `pip install boto3` está instalado
- [ ] **4.** Ejecutar `python test_s3_connection.py` para verificar
- [ ] **5.** Crear bucket `contratos-emprestito` en AWS (si no existe)
- [ ] **6.** Configurar permisos IAM (si hay error de acceso)
- [ ] **7.** Probar el endpoint completo desde el frontend

---

## 🎬 Probar el Sistema Completo

Una vez configurado, desde el frontend:

1. Abrir el modal de "Cargar RPC" o "Registrar Pago"
2. Llenar los campos obligatorios
3. Adjuntar al menos 1 documento (PDF, DOCX, XLS, etc.)
4. Click en "Guardar"

**Respuesta esperada:**

```json
{
  "success": true,
  "message": "RPC guardado exitosamente con 2 documentos",
  "documentos_count": 2
}
```

---

## 📞 Si Nada Funciona

1. **Revisar logs del backend** para el error exacto
2. **Verificar en AWS CloudTrail** si hay intentos de acceso
3. **Confirmar credenciales** generando nuevas desde AWS IAM
4. **Contactar soporte AWS** si los permisos no funcionan

---

## 📚 Documentación Completa

Para información detallada, consulta:

- `SOLUCION_ERROR_S3.md` - Solución completa con detalles técnicos
- `SETUP_S3_EMPRESTITO.md` - Configuración inicial del sistema
- `test_s3_connection.py` - Script de pruebas

---

**Tiempo estimado de solución:** 5-10 minutos  
**Última actualización:** 2024-11-24  
**Estado:** ✅ SOLUCIÓN DOCUMENTADA

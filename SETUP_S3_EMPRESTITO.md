# 📦 Configuración del Bucket S3 para Documentos de Empréstito

## 🎯 Objetivo

Crear y configurar el bucket `contratos-emprestito` en AWS S3 con las carpetas necesarias para almacenar documentos de RPC y pagos.

## 📋 Requisitos Previos

- Cuenta de AWS activa
- Credenciales AWS configuradas (Access Key ID y Secret Access Key)
- Python 3.8+ con boto3 instalado

---

## 🚀 Paso 1: Crear el Bucket en AWS S3

### Opción A: Mediante la Consola Web de AWS

1. **Ir a la consola de S3**

   - Acceder a https://s3.console.aws.amazon.com/

2. **Crear nuevo bucket**

   - Click en "Create bucket"
   - Nombre del bucket: `contratos-emprestito`
   - Región: `us-east-1` (misma que el bucket existente)
   - Block Public Access: **Mantener todas las opciones marcadas** (bucket privado)
   - Versioning: **Habilitado** (recomendado para auditoría)
   - Encryption: **Enable** con SSE-S3

3. **Confirmar creación**
   - Click en "Create bucket"

### Opción B: Mediante AWS CLI

```bash
# Crear el bucket
aws s3api create-bucket --bucket contratos-emprestito --region us-east-1

# Habilitar versionamiento
aws s3api put-bucket-versioning --bucket contratos-emprestito --versioning-configuration Status=Enabled

# Habilitar encriptación
aws s3api put-bucket-encryption --bucket contratos-emprestito --server-side-encryption-configuration '{
  "Rules": [{
    "ApplyServerSideEncryptionByDefault": {
      "SSEAlgorithm": "AES256"
    }
  }]
}'
```

---

## 🔐 Paso 2: Configurar Permisos IAM

### Política IAM Recomendada

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "ContratosEmprestitoFullAccess",
      "Effect": "Allow",
      "Action": [
        "s3:PutObject",
        "s3:GetObject",
        "s3:DeleteObject",
        "s3:ListBucket",
        "s3:GetObjectVersion",
        "s3:ListBucketVersions"
      ],
      "Resource": [
        "arn:aws:s3:::contratos-emprestito",
        "arn:aws:s3:::contratos-emprestito/*"
      ]
    }
  ]
}
```

### Aplicar la Política

1. Ir a **IAM Console** → **Users** → Tu usuario
2. Click en **Add permissions** → **Attach policies directly**
3. Click en **Create policy** → Pegar el JSON de arriba
4. Nombrar la política: `ContratosEmprestitoS3Access`
5. Asociar la política al usuario

---

## 📁 Paso 3: Estructura de Carpetas

La estructura se creará automáticamente al subir el primer documento, pero puedes pre-crearla:

```
contratos-emprestito/
├── contratos-rpc-docs/          # Documentos de RPC
│   ├── {numero_rpc}/            # Una carpeta por RPC
│   │   └── {timestamp}_{filename}
│   └── ...
└── contratos-pagos-docs/        # Documentos de pagos
    ├── {numero_rpc}/            # Una carpeta por RPC
    │   └── {timestamp}_{filename}
    └── ...
```

**Ejemplo real:**

```
contratos-emprestito/
├── contratos-rpc-docs/
│   └── RPC-2024-001/
│       ├── 20241122_143022_contrato_firmado.pdf
│       ├── 20241122_143045_anexo_tecnico.docx
│       └── 20241122_143105_presupuesto.xlsx
└── contratos-pagos-docs/
    └── RPC-2024-001/
        ├── 20241125_091530_comprobante_pago.pdf
        └── 20241125_091545_certificacion.pdf
```

---

## ⚙️ Paso 4: Actualizar Credenciales Locales

El archivo `context/aws_credentials.json` ya está configurado con el bucket:

```json
{
  "aws_access_key_id": "TU_ACCESS_KEY_AQUI",
  "aws_secret_access_key": "TU_SECRET_KEY_AQUI",
  "aws_region": "us-east-1",
  "bucket_name": "unidades-proyecto-documents",
  "bucket_name_emprestito": "contratos-emprestito"
}
```

**✅ Ya está configurado en tu proyecto**

---

## 🧪 Paso 5: Probar la Configuración

### 1. Instalar dependencias

```bash
pip install boto3
```

### 2. Ejecutar el script de prueba

```bash
python test_emprestito_documentos.py
```

### Resultado esperado:

```
🧪 TEST 1: Verificar conexión a S3
✅ S3DocumentManager inicializado correctamente
   Bucket: contratos-emprestito
   Región: us-east-1
✅ Bucket 'contratos-emprestito' existe y es accesible

🧪 TEST 2: Validar documentos
✅ PDF válido: Archivo válido
✅ Archivo grande rechazado: Archivo excede el tamaño máximo de 10MB
✅ Extensión no permitida rechazada: Tipo de archivo no permitido: .exe
✅ DOCX válido: Archivo válido

🧪 TEST 3: Subir documento de prueba a S3
✅ Documento subido exitosamente
   Archivo: documento_prueba_rpc.txt
   S3 Key: contratos-rpc-docs/RPC-TEST-001/20241122_143530_documento_prueba_rpc.txt
   URL: https://contratos-emprestito.s3.us-east-1.amazonaws.com/...

📊 RESUMEN DE PRUEBAS
✅ PASS - Conexión a S3
✅ PASS - Validación de documentos
✅ PASS - Subida individual
✅ PASS - Subida múltiple

✅ Total: 4/4 pruebas exitosas
🎉 ¡Todas las pruebas pasaron exitosamente!
```

---

## 🔄 Paso 6: Probar los Endpoints

### Endpoint 1: Cargar RPC con Documentos

```bash
curl -X POST "http://localhost:8000/emprestito/cargar-rpc" \
  -H "Content-Type: multipart/form-data" \
  -F "numero_rpc=RPC-2024-001" \
  -F "beneficiario_id=890123456" \
  -F "beneficiario_nombre=Proveedor ABC S.A.S." \
  -F "descripcion_rpc=Suministro de equipos" \
  -F "fecha_contabilizacion=2024-11-22" \
  -F "fecha_impresion=2024-11-22" \
  -F "estado_liberacion=Liberado" \
  -F "bp=BP-2024-001" \
  -F "valor_rpc=50000000" \
  -F "nombre_centro_gestor=Secretaría de Salud" \
  -F "referencia_contrato=CONT-SALUD-001-2024" \
  -F "documentos=@/ruta/al/contrato.pdf" \
  -F "documentos=@/ruta/al/anexo.docx"
```

**Respuesta esperada:**

```json
{
  "success": true,
  "message": "RPC RPC-2024-001 guardado exitosamente con 2 documentos",
  "doc_id": "abc123...",
  "coleccion": "rpc_contratos_emprestito",
  "documentos_count": 2,
  "timestamp": "2024-11-22T14:35:30.123456"
}
```

### Endpoint 2: Cargar Pago con Documentos

```bash
curl -X POST "http://localhost:8000/emprestito/cargar-pago" \
  -H "Content-Type: multipart/form-data" \
  -F "numero_rpc=RPC-2024-001" \
  -F "valor_pago=10000000" \
  -F "fecha_transaccion=2024-11-22" \
  -F "referencia_contrato=CONT-SALUD-001-2024" \
  -F "nombre_centro_gestor=Secretaría de Salud" \
  -F "documentos=@/ruta/al/comprobante.pdf" \
  -F "documentos=@/ruta/al/certificacion.pdf"
```

**Respuesta esperada:**

```json
{
  "success": true,
  "message": "Pago registrado exitosamente para RPC RPC-2024-001 con 2 documentos",
  "doc_id": "def456...",
  "coleccion": "pagos_emprestito",
  "documentos_count": 2,
  "timestamp": "2024-11-22T14:40:15.789012"
}
```

---

## 📊 Verificar Documentos en Firebase

Los documentos subidos a S3 se registran en Firebase con la siguiente estructura:

### Colección: `rpc_contratos_emprestito`

```json
{
  "numero_rpc": "RPC-2024-001",
  "beneficiario_id": "890123456",
  "beneficiario_nombre": "Proveedor ABC S.A.S.",
  "descripcion_rpc": "Suministro de equipos",
  "valor_rpc": 50000000,
  "referencia_contrato": "CONT-SALUD-001-2024",
  "nombre_centro_gestor": "Secretaría de Salud",
  "documentos_s3": [
    {
      "success": true,
      "filename": "contrato.pdf",
      "s3_key": "contratos-rpc-docs/RPC-2024-001/20241122_143530_contrato.pdf",
      "s3_url": "https://contratos-emprestito.s3.us-east-1.amazonaws.com/...",
      "size": 245678,
      "content_type": "application/pdf",
      "upload_date": "2024-11-22T14:35:30.123456"
    },
    {
      "success": true,
      "filename": "anexo.docx",
      "s3_key": "contratos-rpc-docs/RPC-2024-001/20241122_143535_anexo.docx",
      "s3_url": "https://contratos-emprestito.s3.us-east-1.amazonaws.com/...",
      "size": 123456,
      "content_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
      "upload_date": "2024-11-22T14:35:35.789012"
    }
  ],
  "fecha_creacion": "2024-11-22T14:35:30",
  "fecha_actualizacion": "2024-11-22T14:35:30",
  "estado": "activo",
  "tipo": "rpc_manual"
}
```

### Colección: `pagos_emprestito`

```json
{
  "numero_rpc": "RPC-2024-001",
  "valor_pago": 10000000,
  "fecha_transaccion": "2024-11-22",
  "referencia_contrato": "CONT-SALUD-001-2024",
  "nombre_centro_gestor": "Secretaría de Salud",
  "documentos_s3": [
    {
      "success": true,
      "filename": "comprobante.pdf",
      "s3_key": "contratos-pagos-docs/RPC-2024-001/20241122_144015_comprobante.pdf",
      "s3_url": "https://contratos-emprestito.s3.us-east-1.amazonaws.com/...",
      "size": 189234,
      "content_type": "application/pdf",
      "upload_date": "2024-11-22T14:40:15.123456"
    }
  ],
  "fecha_registro": "2024-11-22T14:40:15",
  "fecha_creacion": "2024-11-22T14:40:15",
  "fecha_actualizacion": "2024-11-22T14:40:15",
  "estado": "registrado",
  "tipo": "pago_manual"
}
```

---

## ✅ Checklist de Implementación

- [x] Agregar boto3 a requirements.txt
- [x] Crear módulo s3_document_manager.py
- [x] Actualizar aws_credentials.json con bucket_name_emprestito
- [x] Modificar funciones cargar_rpc_emprestito y cargar_pago_emprestito
- [x] Actualizar endpoints en main.py con parámetro documentos
- [x] Crear script de pruebas test_emprestito_documentos.py
- [ ] **Crear bucket 'contratos-emprestito' en AWS S3**
- [ ] **Configurar permisos IAM**
- [ ] **Instalar boto3: `pip install boto3`**
- [ ] **Ejecutar tests: `python test_emprestito_documentos.py`**
- [ ] **Probar endpoints con documentos reales**

---

## 🔧 Solución de Problemas

### Error: "boto3 no está instalado"

```bash
pip install boto3
```

### Error: "Bucket no existe o no es accesible"

- Verificar que el bucket `contratos-emprestito` existe en us-east-1
- Crear el bucket siguiendo el Paso 1

### Error: "NoCredentialsError"

- Verificar que `context/aws_credentials.json` tiene las credenciales correctas
- Las credenciales deben tener los mismos valores que el bucket existente

### Error: "AccessDenied"

- Verificar permisos IAM (Paso 2)
- Asegurar que el usuario tiene permisos sobre el bucket

### Error al subir archivos grandes

- Límite actual: 10MB por archivo
- Para archivos más grandes, modificar el valor en `validate_document_file()`

---

## 📝 Notas Importantes

1. **Seguridad**: Los documentos se almacenan en un bucket privado con acceso controlado
2. **Versionamiento**: Se recomienda habilitar versionamiento en S3 para auditoría
3. **Costos**: S3 cobra por almacenamiento y transferencia de datos
4. **Eliminación**: Los documentos eliminados del código NO se eliminan automáticamente de S3
5. **Backup**: Considerar configurar replicación cross-region para documentos críticos

---

## 🎓 Próximos Pasos Sugeridos

1. **Implementar endpoint de consulta de documentos**

   - GET `/emprestito/rpc/{numero_rpc}/documentos`
   - GET `/emprestito/pago/{pago_id}/documentos`

2. **Implementar endpoint de descarga de documentos**

   - GET `/emprestito/documento/{s3_key}/download`

3. **Agregar autenticación**

   - Proteger endpoints de carga con JWT
   - Implementar roles y permisos

4. **Implementar lifecycle policies en S3**

   - Mover documentos antiguos a Glacier después de X meses
   - Configurar expiración automática si es necesario

5. **Agregar logs y auditoría**
   - Registrar quién sube documentos
   - Registrar accesos a documentos

---

**Fecha de implementación**: 2024-11-22  
**Estado**: ✅ IMPLEMENTADO - Pendiente configuración de bucket AWS

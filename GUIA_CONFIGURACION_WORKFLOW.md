# 🚀 Configuración del Workflow de Automatización - Con WIF

## ✅ Archivo Creado

El workflow está en: `.github/workflows/emprestito-automation.yml`

**Estado**: ✅ Sin errores de sintaxis (solo warnings normales de secrets faltantes)

## 🔐 Configuración de Secrets en GitHub (OBLIGATORIO)

### Paso 1: Autenticarte en GitHub CLI

```powershell
# Autenticarte con GitHub
gh auth login

# Selecciona:
# - GitHub.com
# - HTTPS
# - Login with a web browser
```

### Paso 2: Configurar los Secrets

Ejecuta estos comandos desde tu terminal (PowerShell):

```powershell
# Navegar a tu proyecto
cd A:\programing_workspace\gestor_proyecto_api

# 1. Configurar la URL de tu API
gh secret set API_BASE_URL --body "https://tu-api.railway.app"
# Reemplaza con la URL real de tu API en Railway

# 2. Configurar el UID de Firebase para automatización
# Necesitas el UID de un usuario existente en Firebase
gh secret set FIREBASE_AUTOMATION_UID --body "tu-uid-de-firebase"
# Puedes obtenerlo desde Firebase Console > Authentication > Users

# 3. Ya tienes estos secrets configurados de antes:
# - WIF_PROVIDER_ID
# - WIF_SERVICE_ACCOUNT
# Puedes verificar con:
gh secret list
```

## 🔍 Cómo Obtener el UID de Firebase

### Opción A: Desde Firebase Console (Recomendado)

1. Ve a [Firebase Console](https://console.firebase.google.com/)
2. Selecciona tu proyecto: `dev-test-e778d`
3. Ve a **Authentication** → **Users**
4. Selecciona un usuario con permisos de admin
5. Copia el **UID** (algo como: `abc123xyz456...`)

### Opción B: Crear un usuario específico para automatización

```powershell
# Ejecutar Python para crear usuario de automatización
python
```

```python
import firebase_admin
from firebase_admin import credentials, auth

# Inicializar Firebase (ajusta la ruta a tu service account)
cred = credentials.Certificate('path/to/serviceAccountKey.json')
firebase_admin.initialize_app(cred)

# Crear usuario para automatización
user = auth.create_user(
    email='automation@tu-dominio.com',
    password='UnPasswordSeguro123!',
    display_name='Automation Bot'
)

print(f"✅ Usuario creado con UID: {user.uid}")
print(f"📧 Email: {user.email}")
print(f"🔑 Usa este UID para FIREBASE_AUTOMATION_UID")
```

## 🧪 Probar el Workflow

### 1. Verificar que el workflow está detectado

```powershell
gh workflow list
```

Deberías ver: `🔄 Empréstito Data Pipeline Automation`

### 2. Ejecutar manualmente el workflow

```powershell
# Ejecutar el workflow en la branch actual
gh workflow run emprestito-automation.yml

# Ver el progreso
gh run list --workflow=emprestito-automation.yml

# Ver los logs de la última ejecución
gh run view --log
```

### 3. Ver los logs en tiempo real (desde la web)

```powershell
# Abrir GitHub Actions en el navegador
gh browse --branch main
# Luego ve a la pestaña "Actions"
```

## 📋 Checklist de Configuración

- [ ] GitHub CLI instalado (`gh --version`)
- [ ] Autenticado en GitHub (`gh auth status`)
- [ ] Secret `API_BASE_URL` configurado
- [ ] Secret `FIREBASE_AUTOMATION_UID` configurado
- [ ] Secrets WIF ya configurados (`WIF_PROVIDER_ID`, `WIF_SERVICE_ACCOUNT`)
- [ ] Workflow commiteado y pusheado a GitHub
- [ ] Prueba manual ejecutada exitosamente

## 🔧 Comandos Útiles

```powershell
# Ver todos los secrets configurados
gh secret list

# Eliminar un secret (si necesitas recrearlo)
gh secret delete SECRET_NAME

# Ver el estado de autenticación
gh auth status

# Ver workflows disponibles
gh workflow list

# Ver runs recientes
gh run list --limit 5

# Ver detalles de un run específico
gh run view RUN_ID --log

# Cancelar un run en progreso
gh run cancel RUN_ID

# Re-ejecutar un run fallido
gh run rerun RUN_ID
```

## 🎯 Cómo Funciona el Workflow

1. **Autenticación con WIF**: GitHub Actions se autentica con Google Cloud usando Workload Identity Federation
2. **Genera Custom Token**: Usa Firebase Admin SDK para crear un custom token para el usuario de automatización
3. **Ejecuta Endpoints**: Llama secuencialmente a los 4 endpoints usando el custom token
4. **Validación**: Verifica que cada endpoint responda con HTTP 200
5. **Logging**: Registra todas las respuestas y errores

## ⏰ Horarios Programados (UTC)

- 00:00 UTC
- 05:00 UTC
- 10:00 UTC
- 15:00 UTC
- 17:00 UTC
- 22:00 UTC

**Horario Colombia (UTC-5)**:

- 19:00 (día anterior)
- 00:00
- 05:00
- 10:00
- 12:00
- 17:00

## 🚨 Solución de Problemas

### Error: "Context access might be invalid"

✅ **Normal**: Son solo warnings de VS Code porque los secrets no existen localmente. Se resolverán al configurarlos en GitHub.

### Error: "Invalid token" o "401 Unauthorized"

1. Verifica que `FIREBASE_AUTOMATION_UID` sea correcto
2. Verifica que el usuario existe en Firebase Authentication
3. Verifica que los secrets WIF estén configurados correctamente

### Error: "404 Not Found"

1. Verifica que `API_BASE_URL` sea correcta (sin / al final)
2. Verifica que tu API esté desplegada y funcionando

### El workflow no se ejecuta automáticamente

1. Verifica que el workflow esté en la branch `main` o `master`
2. Los cron schedules solo funcionan en la branch default del repo
3. Puede tardar hasta 5 minutos en activarse después del primer push

## 📝 Siguiente Paso

Ejecuta estos comandos en tu terminal:

```powershell
# 1. Autenticarte (si no lo has hecho)
gh auth login

# 2. Verificar autenticación
gh auth status

# 3. Configurar secrets
gh secret set API_BASE_URL --body "https://tu-api.railway.app"
gh secret set FIREBASE_AUTOMATION_UID --body "tu-uid-aqui"

# 4. Verificar secrets
gh secret list

# 5. Ver si el workflow está disponible (después de hacer commit y push)
gh workflow list

# 6. Ejecutar prueba manual
gh workflow run emprestito-automation.yml
```

## 📦 Commit y Push

Si aún no has hecho commit del workflow:

```powershell
# Navegar al proyecto
cd A:\programing_workspace\gestor_proyecto_api

# Ver archivos modificados
git status

# Agregar el workflow
git add .github/workflows/emprestito-automation.yml

# Commit
git commit -m "feat: Agregar workflow de automatización para pipeline de empréstito"

# Push
git push origin main
```

---

**Documentación creada**: 2025-12-20
**Workflow**: `.github/workflows/emprestito-automation.yml`
**Status**: ✅ Listo para configurar secrets y probar

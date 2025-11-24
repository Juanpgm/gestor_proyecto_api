# 🔐 Sistema de Autenticación y Autorización

Sistema completo de gestión de usuarios, roles y permisos para el Gestor de Proyectos Cali.

## 📋 Características

- ✅ **Autenticación basada en Firebase**: Integración completa con Firebase Authentication
- ✅ **Sistema de roles jerárquico**: 8 roles predefinidos con niveles de privilegio
- ✅ **Permisos granulares**: Control fino sobre acciones y recursos
- ✅ **Middleware de autorización**: Protección automática de endpoints
- ✅ **Auditoría completa**: Registro automático de todas las acciones importantes
- ✅ **Permisos temporales**: Asignación de permisos con expiración
- ✅ **Scope por centro gestor**: Restricción de acceso por entidad

## 📊 Roles del Sistema

| Rol                     | Nivel | Descripción                                    |
| ----------------------- | ----- | ---------------------------------------------- |
| **super_admin**         | 0     | Control total del sistema, gestión de usuarios |
| **admin_general**       | 1     | Administración de datos y roles (sin usuarios) |
| **admin_centro_gestor** | 2     | Administración de su centro gestor             |
| **editor_datos**        | 3     | Edición sin eliminación                        |
| **gestor_contratos**    | 3     | Gestión exclusiva de contratos                 |
| **analista**            | 4     | Análisis y exportación                         |
| **visualizador**        | 5     | **ROL POR DEFECTO** - Solo lectura básica      |
| **publico**             | 6     | Acceso público limitado                        |

## 🚀 Instalación y Configuración

### 1. Inicializar Roles en Firebase

```bash
python scripts/init_auth_system.py
```

Este script:

- Crea la colección `roles` en Firestore
- Inicializa todos los roles con sus permisos
- Verifica la instalación correcta

### 2. Asignar Super Admin Inicial

```bash
python scripts/assign_super_admin.py admin@cali.gov.co
```

Este script:

- Busca el usuario por email en Firebase Auth
- Asigna el rol `super_admin`
- Registra la acción en audit logs

## 📁 Estructura del Sistema

```
auth_system/
├── __init__.py           # Exports principales
├── constants.py          # Roles, permisos y configuración
├── models.py            # Modelos Pydantic
├── permissions.py       # Lógica de permisos
├── decorators.py        # Decoradores de protección
├── middleware.py        # Middlewares de auth y audit
└── utils.py             # Funciones auxiliares

api/routers/
└── auth_admin.py        # Router de administración

scripts/
├── init_auth_system.py      # Inicialización
└── assign_super_admin.py    # Asignar super admin
```

## 🔧 Uso en Endpoints

### Proteger con Permiso Específico

```python
from fastapi import Depends
from auth_system.decorators import require_permission, get_current_user

@app.post("/proyectos")
@require_permission("write:proyectos")
async def create_proyecto(
    data: dict,
    current_user: dict = Depends(get_current_user)
):
    print(f"Usuario: {current_user['email']}")
    print(f"Roles: {current_user['roles']}")
    # Tu lógica aquí
    pass
```

### Proteger con Rol Específico

```python
from auth_system.decorators import require_role

@app.delete("/admin/purge")
@require_role(["super_admin"])
async def purge_data(current_user: dict = Depends(get_current_user)):
    # Solo super_admin puede ejecutar esto
    pass
```

### Autenticación Opcional

```python
from auth_system.decorators import optional_auth
from typing import Optional

@app.get("/public-or-private")
async def endpoint(current_user: Optional[dict] = Depends(optional_auth())):
    if current_user:
        return {"message": "Authenticated", "user": current_user['email']}
    return {"message": "Public access"}
```

## 📡 Endpoints de Administración

Todos bajo `/auth/admin/*` - Requieren permisos específicos

### Gestión de Usuarios

```http
GET /auth/admin/users
GET /auth/admin/users/{uid}
POST /auth/admin/users/{uid}/roles
POST /auth/admin/users/{uid}/temporary-permissions
DELETE /auth/admin/users/{uid}/temporary-permissions/{permission}
```

### Gestión de Roles

```http
GET /auth/admin/roles
GET /auth/admin/roles/{role_id}
```

### Auditoría

```http
GET /auth/admin/audit-logs?limit=100&user_uid={uid}&action={action}
```

### Estadísticas

```http
GET /auth/admin/system/stats
```

## 🔒 Permisos Disponibles

### Formato: `action:resource[:scope]`

#### Acciones

- `read` - Lectura
- `write` - Escritura
- `delete` - Eliminación
- `manage` - Gestión administrativa
- `upload` / `download` - Carga/Descarga
- `export` - Exportación
- `view` - Visualización

#### Recursos

- `proyectos` - Proyectos presupuestales
- `unidades` - Unidades de proyecto
- `contratos` - Contratos
- `users` - Usuarios
- `roles` - Roles
- `audit_logs` - Logs de auditoría

#### Scopes (Opcional)

- `:own_centro` - Solo su centro gestor
- `:public` - Solo datos públicos
- `:basic` - Solo información básica

### Ejemplos

```
read:proyectos              # Leer todos los proyectos
read:proyectos:own_centro   # Leer solo de su centro
write:proyectos             # Crear/actualizar proyectos
delete:proyectos            # Eliminar proyectos
manage:users                # Gestionar usuarios (solo super_admin)
```

## 🛡️ Middlewares

### AuthorizationMiddleware

Protege automáticamente todos los endpoints excepto los públicos:

```python
from auth_system.middleware import AuthorizationMiddleware

app.add_middleware(
    AuthorizationMiddleware,
    public_paths=["/", "/docs", "/auth/login", "/auth/register"]
)
```

### AuditLogMiddleware

Registra automáticamente todas las acciones POST/PUT/DELETE:

```python
from auth_system.middleware import AuditLogMiddleware

app.add_middleware(
    AuditLogMiddleware,
    enable_logging=True
)
```

## 📝 Flujo de Registro y Autenticación

### Nuevo Usuario

1. **Registro**: `POST /auth/register`

   - Usuario se registra con email/password
   - **Se asigna automáticamente rol `visualizador`**
   - Se crea documento en Firestore

2. **Login**: `POST /auth/login`

   - Usuario inicia sesión
   - Obtiene token de Firebase
   - Token incluye permisos del rol asignado

3. **Acceso**: Usuario puede:

   - Ver datos básicos (permisos de visualizador)
   - NO puede crear, editar o eliminar
   - NO puede exportar datos

4. **Escalamiento**: Super Admin puede:
   - Cambiar el rol del usuario
   - Otorgar permisos temporales
   - Asignar a un centro gestor específico

### Validación de Sesión

```http
POST /auth/validate-session
Authorization: Bearer {firebase_token}

{
  "success": true,
  "user": {
    "uid": "abc123",
    "email": "user@cali.gov.co",
    "roles": ["visualizador"],
    "permissions": ["read:proyectos:basic", ...],
    "centro_gestor_assigned": "SECRETARIA DE SALUD"
  }
}
```

## 🔍 Consulta de Permisos

### Desde Python

```python
from auth_system.permissions import get_user_permissions, has_permission

# Obtener todos los permisos de un usuario
permissions = get_user_permissions(user_uid)

# Verificar permiso específico
if has_permission(user_uid, "write:proyectos"):
    # Usuario puede escribir proyectos
    pass
```

### Desde Endpoint

El decorador `get_current_user` incluye automáticamente los permisos:

```python
@app.get("/mi-endpoint")
async def mi_endpoint(current_user: dict = Depends(get_current_user)):
    print(current_user['permissions'])
    # ['read:proyectos', 'write:unidades', ...]
```

## 📊 Logs de Auditoría

Todos los logs incluyen:

- `timestamp` - Fecha y hora
- `user_uid` - UID del usuario
- `user_email` - Email del usuario
- `action` - Acción realizada
- `endpoint` - Endpoint llamado
- `method` - Método HTTP
- `status_code` - Código de respuesta
- `process_time_seconds` - Tiempo de procesamiento

### Ejemplo de Log

```json
{
  "timestamp": "2025-11-24T15:30:00Z",
  "user_uid": "abc123",
  "user_email": "admin@cali.gov.co",
  "action": "assign_roles",
  "target_user_uid": "def456",
  "old_roles": ["visualizador"],
  "new_roles": ["editor_datos"],
  "reason": "Promoción a editor"
}
```

## 🚨 Troubleshooting

### Error: "Token inválido o expirado"

- Verificar que el token de Firebase no haya expirado (1 hora)
- Renovar token desde el frontend
- Verificar configuración de Firebase en variables de entorno

### Error: "Usuario no encontrado"

- Verificar que el usuario esté registrado en Firebase Auth
- Verificar que exista el documento en Firestore `users/{uid}`
- Ejecutar script de registro si es necesario

### Error: "Permiso denegado"

- Verificar roles del usuario: `GET /auth/admin/users/{uid}`
- Verificar permisos del rol: `GET /auth/admin/roles/{role_id}`
- Considerar otorgar permiso temporal si es necesario

## 📚 Referencias

- [API Auth Integration Guide](../context/API_AUTH_INTEGRATION_GUIDE.md)
- [Frontend Integration Guide](../context/FRONTEND_AUTH_INTEGRATION.md)
- [Configuración Rol Por Defecto](../context/CONFIGURACION_ROL_POR_DEFECTO.md)

## ✅ Checklist de Implementación

- [x] Crear módulo `auth_system/`
- [x] Definir roles y permisos
- [x] Implementar modelos Pydantic
- [x] Crear sistema de validación de permisos
- [x] Implementar decoradores de autorización
- [x] Crear middlewares de auth y audit
- [x] Desarrollar endpoints de administración
- [x] Integrar con main.py
- [x] Crear scripts de inicialización
- [ ] Ejecutar `init_auth_system.py`
- [ ] Asignar primer super admin
- [ ] Probar endpoints protegidos
- [ ] Configurar frontend

---

**Versión**: 1.0.0  
**Fecha**: 24 de Noviembre 2025  
**Autor**: Sistema de Auth para Gestor de Proyectos Cali

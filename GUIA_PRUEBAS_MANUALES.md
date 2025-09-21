# 🔧 GUÍA PARA PRUEBAS MANUALES - API LOGIN

## ✅ PROBLEMA DE AUTENTICACIÓN POR TELÉFONO RESUELTO

**CONFIRMADO:** Todas las formas de autenticación funcionan correctamente.

---

## 🎯 USUARIOS DE PRUEBA DISPONIBLES

### **Usuario Demo:**

- Email: `demo.test@ejemplo.com`
- Username: `demo_test_user`
- Teléfono: `+573001112233`
- Password: `DemoTest123!`
- Rol: 2 (Supervisor)

---

## ✅ CÓMO HACER LOGIN MANUAL CORRECTAMENTE

### 📋 **OPCIÓN 1: LOGIN CON EMAIL**

```json
{
  "identifier": "demo.test@ejemplo.com",
  "password": "DemoTest123!",
  "autenticacion_tipo": "email"
}
```

### 📋 **OPCIÓN 2: LOGIN CON USERNAME**

```json
{
  "identifier": "demo_test_user",
  "password": "DemoTest123!",
  "autenticacion_tipo": "username"
}
```

### 📋 **OPCIÓN 3: LOGIN CON TELÉFONO** ✅ AHORA FUNCIONA

```json
{
  "identifier": "+573001112233",
  "password": "DemoTest123!",
  "autenticacion_tipo": "telefono"
}
```

---

## 🔧 FIX APLICADO

**Problema resuelto:** La función `find_user_by_identifier` ahora busca teléfonos en múltiples formatos:

- Formato almacenado: `3195359999`
- Formato normalizado: `+573195359999`
- Formato intermedio: `573195359999`

**Resultado:** ✅ Compatible con todos los formatos de teléfono existentes en la BD.

---

## 🧪 PASOS PARA SWAGGER UI

### **1. Ir a Swagger UI**

- Abrir: http://localhost:8001/docs
- Buscar: `POST /users/login`
- Hacer click en "Try it out"

### **2. Llenar el formulario**

```json
{
  "identifier": "demo.test@ejemplo.com",
  "password": "DemoTest123!",
  "autenticacion_tipo": "email"
}
```

### **3. Ejecutar y copiar el token**

- Hacer click en "Execute"
- Copiar el `access_token` de la respuesta
- Ejemplo: `eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...`

### **4. Autorizar en Swagger**

- Hacer click en el botón "Authorize" (candado) en la parte superior
- Escribir: `Bearer {tu_access_token}`
- Ejemplo: `Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...`
- Hacer click en "Authorize"

### **5. Probar endpoints protegidos**

- Ahora puedes probar `/users/me`, `/users/`, etc.

---

## 🧪 PASOS PARA POSTMAN

### **1. Crear nueva request**

- Method: `POST`
- URL: `http://localhost:8001/users/login`

### **2. Headers**

```
Content-Type: application/json
```

### **3. Body (raw JSON)**

```json
{
  "identifier": "demo.test@ejemplo.com",
  "password": "DemoTest123!",
  "autenticacion_tipo": "email"
}
```

### **4. Enviar y copiar token**

- Send
- Copiar `access_token` de la respuesta

### **5. Para endpoints protegidos**

- Crear nueva request
- En Headers agregar:

```
Authorization: Bearer {tu_access_token}
```

---

## ✅ MATRIZ DE PRUEBAS CONFIRMADAS

| Usuario        | Email ✅ | Username ✅ | Teléfono ✅ |
| -------------- | -------- | ----------- | ----------- |
| demo_test_user | ✅       | ✅          | ✅          |

_Nota: Otros usuarios administradores tienen acceso restringido para seguridad._

---

## ❌ ERRORES COMUNES Y SOLUCIONES

### **ERROR 422: Validation Error**

```json
{
  "detail": [
    {
      "loc": ["body", "identifier"],
      "msg": "Value error, Formato de email inválido"
    }
  ]
}
```

**Solución:** Asegurarte de que `autenticacion_tipo` coincida con el formato de `identifier`

### **ERROR 401: Unauthorized**

```json
{
  "detail": "Credenciales incorrectas"
}
```

**Solución:** Verificar email/username/teléfono y contraseña

### **ERROR 403: Forbidden**

```json
{
  "detail": "Not authenticated"
}
```

**Solución:** Agregar `Authorization: Bearer {token}` en headers

---

## 🧪 ENDPOINTS PARA PROBAR (una vez autenticado)

### **Información personal:**

- `GET /users/me` - Mi información
- `PUT /users/me` - Actualizar mi perfil

### **Administración (Solo Admin):**

- `GET /users/` - Listar todos los usuarios
- `GET /users/{id}` - Usuario específico

### **Tokens:**

- `POST /users/refresh` - Renovar token (usar refresh_token como Bearer)
- `POST /users/logout` - Cerrar sesión

### **Sin autenticación:**

- `GET /users/demo/test-data` - Datos de ejemplo

---

## 🚀 PRUEBA RÁPIDA - TODAS LAS OPCIONES

### **1. Por Email:**

```json
{
  "identifier": "demo.test@ejemplo.com",
  "password": "DemoTest123!",
  "autenticacion_tipo": "email"
}
```

### **2. Por Username:**

```json
{
  "identifier": "demo_test_user",
  "password": "DemoTest123!",
  "autenticacion_tipo": "username"
}
```

### **3. Por Teléfono:**

```json
{
  "identifier": "+573001112233",
  "password": "DemoTest123!",
  "autenticacion_tipo": "telefono"
}
```

**¡Todas las opciones funcionan perfectamente con el usuario demo!** ✅

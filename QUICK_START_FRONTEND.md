# 🚀 INICIO RÁPIDO - Implementación Frontend (5 minutos)

## 📦 1. Instalar Firebase

```bash
npm install firebase
```

## 🔑 2. Variables de Entorno

Crear `.env.local` en el frontend:

```bash
NEXT_PUBLIC_FIREBASE_API_KEY=tu_api_key_aqui
NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN=unidad-cumplimiento-aa245.firebaseapp.com
NEXT_PUBLIC_FIREBASE_PROJECT_ID=unidad-cumplimiento-aa245
NEXT_PUBLIC_API_URL=http://localhost:8000
```

**¿Dónde obtener estos valores?**

1. Ve a: https://console.firebase.google.com/
2. Selecciona proyecto: `unidad-cumplimiento-aa245`
3. Settings ⚙️ → General → Your apps → Firebase SDK snippet → Config

## 📁 3. Estructura de Archivos

```
tu-frontend/
├── lib/
│   └── firebase.ts          ← Copiar desde IMPLEMENTACION_FRONTEND.md
├── services/
│   └── auth.service.ts      ← Copiar desde IMPLEMENTACION_FRONTEND.md
├── hooks/
│   └── useAuth.ts           ← Copiar desde IMPLEMENTACION_FRONTEND.md
└── components/
    ├── LoginForm.tsx        ← Copiar desde IMPLEMENTACION_FRONTEND.md
    └── ProtectedRoute.tsx   ← Copiar desde IMPLEMENTACION_FRONTEND.md
```

## 🎯 4. Código Esencial

### Configurar Firebase (`lib/firebase.ts`)

```typescript
import { initializeApp } from "firebase/app";
import { getAuth } from "firebase/auth";

const firebaseConfig = {
  apiKey: process.env.NEXT_PUBLIC_FIREBASE_API_KEY,
  authDomain: process.env.NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN,
  projectId: process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID,
};

const app = initializeApp(firebaseConfig);
export const auth = getAuth(app);
```

### Login Simple

```typescript
import { signInWithEmailAndPassword } from "firebase/auth";
import { auth } from "@/lib/firebase";

async function login(email: string, password: string) {
  // 1. Login con Firebase
  const userCredential = await signInWithEmailAndPassword(
    auth,
    email,
    password
  );

  // 2. Obtener token
  const idToken = await userCredential.user.getIdToken();

  // 3. Validar con backend
  const response = await fetch("http://localhost:8000/auth/validate-session", {
    method: "POST",
    headers: { Authorization: `Bearer ${idToken}` },
  });

  const data = await response.json();
  return { user: data.user, idToken };
}
```

### Hacer peticiones autenticadas

```typescript
async function fetchProtectedData() {
  const user = auth.currentUser;
  const idToken = await user.getIdToken();

  const response = await fetch("http://localhost:8000/api/protected", {
    headers: { Authorization: `Bearer ${idToken}` },
  });

  return response.json();
}
```

## 🧪 5. Prueba Rápida

```typescript
// En tu componente o consola del navegador
import { signInWithEmailAndPassword } from "firebase/auth";
import { auth } from "./lib/firebase";

// Test login
signInWithEmailAndPassword(auth, "test@idrd.gov.co", "password")
  .then(async (credential) => {
    const token = await credential.user.getIdToken();
    console.log("✅ Token:", token);

    // Test backend
    const res = await fetch("http://localhost:8000/auth/validate-session", {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
    });

    const data = await res.json();
    console.log("✅ Backend data:", data);
  })
  .catch((error) => console.error("❌ Error:", error));
```

## ✅ Checklist Mínimo

- [ ] `npm install firebase`
- [ ] Crear `.env.local` con credenciales
- [ ] Crear `lib/firebase.ts`
- [ ] Probar login básico
- [ ] Verificar que el token funciona con el backend

## 📚 Documentación Completa

Para implementación completa con hooks, context, componentes, etc.:
→ Ver `IMPLEMENTACION_FRONTEND.md`

---

**¿Listo en 5 minutos?** Sigue solo estos pasos y tendrás autenticación básica funcionando. Después expande con los componentes completos de `IMPLEMENTACION_FRONTEND.md`.

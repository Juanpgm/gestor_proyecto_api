# 🚀 Guía de Deployment - API + Next.js Frontend

## Arquitectura de Deployment Recomendada

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Frontend      │    │      API         │    │   Firebase      │
│   (Vercel)      │───▶│   (Railway)      │───▶│   (Firestore)   │
│   Next.js       │    │   FastAPI        │    │   Database      │
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

## 1. 🛤️ Deployment de la API (Railway)

### Configuración en Railway

Tu API ya está configurada para Railway. Asegúrate de tener estas variables de entorno:

```env
# Variables de entorno en Railway
FIREBASE_PROJECT_ID=tu-proyecto-firebase
FIREBASE_PRIVATE_KEY_ID=tu-private-key-id
FIREBASE_PRIVATE_KEY=-----BEGIN PRIVATE KEY-----\ntu-private-key\n-----END PRIVATE KEY-----\n
FIREBASE_CLIENT_EMAIL=tu-service-account@tu-proyecto.iam.gserviceaccount.com
FIREBASE_CLIENT_ID=tu-client-id
PORT=8000
ENVIRONMENT=production
```

### Verificar que la API funciona:

1. **Health Check:**

   ```bash
   curl https://tu-api-railway.up.railway.app/health
   ```

2. **Endpoint Next.js:**
   ```bash
   curl https://tu-api-railway.up.railway.app/unidades-proyecto/nextjs-export?format=nextjs&max_records=10
   ```

## 2. 🌐 Deployment del Frontend (Vercel)

### 2.1 Preparar el proyecto Next.js

```bash
# En tu directorio de frontend
npm create-next-app@latest gestor-proyectos-frontend
cd gestor-proyectos-frontend

# Instalar dependencias
npm install swr axios @headlessui/react @heroicons/react
npm install chart.js react-chartjs-2
npm install leaflet react-leaflet react-leaflet-cluster
npm install -D @types/leaflet tailwindcss postcss autoprefixer
npx tailwindcss init -p
```

### 2.2 Estructura de proyecto recomendada

```
gestor-proyectos-frontend/
├── pages/
│   ├── index.js                 # Página principal
│   ├── dashboard.js             # Dashboard ejecutivo
│   ├── unidades-proyecto.js     # Lista de proyectos
│   └── mapa.js                  # Vista de mapa
├── components/
│   ├── UnidadesList.js
│   ├── UnidadesTable.js
│   ├── UnidadesFilters.js
│   ├── UnidadesStats.js
│   ├── UnidadesMapa.js
│   ├── SearchBox.js
│   ├── LoadingSpinner.js
│   └── ErrorMessage.js
├── hooks/
│   └── useUnidades.js
├── lib/
│   └── api.js
├── types/
│   └── unidades.ts
├── styles/
│   └── globals.css
├── public/
├── .env.local
├── .env.production
├── next.config.js
├── tailwind.config.js
└── package.json
```

### 2.3 Configuración para Vercel

#### `vercel.json`

```json
{
  "project": "gestor-proyectos-frontend",
  "builds": [
    {
      "src": "next.config.js",
      "use": "@vercel/next"
    }
  ],
  "regions": ["iad1"],
  "env": {
    "NEXT_PUBLIC_API_URL": "@next_public_api_url"
  }
}
```

#### Variables de entorno en Vercel:

1. Ve a tu dashboard de Vercel
2. Selecciona tu proyecto
3. Ve a Settings > Environment Variables
4. Agrega:
   ```
   NEXT_PUBLIC_API_URL = https://tu-api-railway.up.railway.app
   ```

### 2.4 Scripts de package.json optimizados

```json
{
  "name": "gestor-proyectos-frontend",
  "version": "1.0.0",
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start",
    "lint": "next lint",
    "type-check": "tsc --noEmit",
    "build:analyze": "ANALYZE=true next build"
  },
  "dependencies": {
    "next": "14.0.0",
    "react": "18.2.0",
    "react-dom": "18.2.0",
    "swr": "^2.2.0",
    "axios": "^1.5.0",
    "@headlessui/react": "^1.7.17",
    "@heroicons/react": "^2.0.18",
    "chart.js": "^4.4.0",
    "react-chartjs-2": "^5.2.0",
    "leaflet": "^1.9.4",
    "react-leaflet": "^4.2.1",
    "react-leaflet-cluster": "^2.1.0"
  },
  "devDependencies": {
    "@types/node": "20.5.0",
    "@types/react": "18.2.21",
    "@types/leaflet": "^1.9.4",
    "typescript": "5.1.6",
    "tailwindcss": "^3.3.3",
    "postcss": "^8.4.29",
    "autoprefixer": "^10.4.15",
    "eslint": "8.47.0",
    "eslint-config-next": "13.4.19"
  }
}
```

## 3. 🔐 Configuración de CORS y Seguridad

### 3.1 Actualizar CORS en la API

Tu API ya tiene CORS configurado, pero asegúrate de agregar tu dominio de Vercel:

```python
# En main.py - actualizar la lista origins
origins = [
    # Producción - Tu dominio de Vercel
    "https://tu-proyecto.vercel.app",
    "https://gestor-proyectos-frontend.vercel.app",

    # Desarrollo local
    "http://localhost:3000",
    "http://localhost:3001",
    "http://127.0.0.1:3000",
]
```

### 3.2 Configuración de seguridad en Next.js

#### `next.config.js` con seguridad

```javascript
/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  swcMinify: true,

  // Configuración de imágenes
  images: {
    domains: ["tu-api-railway.up.railway.app"],
  },

  // Headers de seguridad
  async headers() {
    return [
      {
        source: "/(.*)",
        headers: [
          {
            key: "X-Frame-Options",
            value: "DENY",
          },
          {
            key: "X-Content-Type-Options",
            value: "nosniff",
          },
          {
            key: "Referrer-Policy",
            value: "origin-when-cross-origin",
          },
          {
            key: "X-XSS-Protection",
            value: "1; mode=block",
          },
        ],
      },
    ];
  },

  // Rewrites para API (opcional)
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${process.env.NEXT_PUBLIC_API_URL}/:path*`,
      },
    ];
  },
};

module.exports = nextConfig;
```

## 4. 📊 Monitoreo y Analytics

### 4.1 Configurar Vercel Analytics

```bash
npm install @vercel/analytics
```

#### `pages/_app.js`

```javascript
import { Analytics } from "@vercel/analytics/react";
import "../styles/globals.css";

export default function App({ Component, pageProps }) {
  return (
    <>
      <Component {...pageProps} />
      <Analytics />
    </>
  );
}
```

### 4.2 Monitoreo de API (Railway)

La API ya incluye logging. Para monitoreo adicional, puedes agregar:

```python
# En main.py - middleware de métricas
@app.middleware("http")
async def add_metrics_middleware(request: Request, call_next):
    start_time = datetime.now()
    response = await call_next(request)
    process_time = datetime.now() - start_time

    # Log métricas
    print(f"📊 {request.method} {request.url.path} - {response.status_code} - {process_time.total_seconds():.3f}s")

    response.headers["X-Process-Time"] = str(process_time.total_seconds())
    return response
```

## 5. 🚀 Comandos de Deployment

### Deployment automático con Git

#### Para la API (Railway):

```bash
# La API se autodeploya cuando haces push a main/master
git add .
git commit -m "Update API with Next.js integration"
git push origin master
```

#### Para el Frontend (Vercel):

```bash
# Conectar con Vercel CLI (una sola vez)
npm install -g vercel
vercel login
vercel link

# Deploy manual
vercel --prod

# O configurar deployment automático desde GitHub
# 1. Conectar repo en vercel.com
# 2. Configurar auto-deploy en push a main
```

## 6. 🧪 Testing de la Integración

### Script de prueba completo:

```javascript
// test-integration.js
const axios = require("axios");

const API_URL = "https://tu-api-railway.up.railway.app";
const FRONTEND_URL = "https://tu-proyecto.vercel.app";

async function testIntegration() {
  console.log("🧪 Testing API + Frontend Integration\n");

  try {
    // 1. Test API Health
    console.log("1. Testing API Health...");
    const health = await axios.get(`${API_URL}/health`);
    console.log("✅ API Health OK", health.data.status);

    // 2. Test CORS
    console.log("\n2. Testing CORS...");
    const corsTest = await axios.get(
      `${API_URL}/unidades-proyecto/nextjs-export?max_records=1`,
      {
        headers: { Origin: FRONTEND_URL },
      }
    );
    console.log("✅ CORS OK");

    // 3. Test Next.js Endpoint
    console.log("\n3. Testing Next.js Optimized Endpoint...");
    const nextjsData = await axios.get(
      `${API_URL}/unidades-proyecto/nextjs-export`,
      {
        params: {
          format: "nextjs",
          include_charts: true,
          include_filters: true,
          max_records: 10,
        },
      }
    );
    console.log("✅ Next.js Endpoint OK");
    console.log(
      `   - Unidades: ${nextjsData.data.data?.unidades?.length || 0}`
    );
    console.log(
      `   - Charts: ${nextjsData.data.ui_components?.charts ? "Yes" : "No"}`
    );
    console.log(
      `   - Filters: ${nextjsData.data.ui_components?.filters ? "Yes" : "No"}`
    );

    // 4. Test Search
    console.log("\n4. Testing Search...");
    const searchResult = await axios.get(
      `${API_URL}/unidades-proyecto/search`,
      {
        params: { q: "proyecto", page_size: 5 },
      }
    );
    console.log("✅ Search OK");
    console.log(`   - Results: ${searchResult.data.unidades?.length || 0}`);

    console.log("\n🎉 All tests passed! Integration is working correctly.");
  } catch (error) {
    console.error("❌ Test failed:", error.response?.data || error.message);
  }
}

testIntegration();
```

Ejecutar test:

```bash
node test-integration.js
```

## 7. 📱 Performance y Optimizaciones

### 7.1 Optimizaciones de Next.js

#### `pages/_document.js`

```javascript
import { Html, Head, Main, NextScript } from "next/document";

export default function Document() {
  return (
    <Html lang="es">
      <Head>
        <meta name="viewport" content="width=device-width, initial-scale=1.0" />
        <link rel="preconnect" href="https://tu-api-railway.up.railway.app" />
        <link rel="dns-prefetch" href="https://tu-api-railway.up.railway.app" />
      </Head>
      <body>
        <Main />
        <NextScript />
      </body>
    </Html>
  );
}
```

### 7.2 Optimización de bundle

#### `next.config.js` con optimizaciones

```javascript
const withBundleAnalyzer = require("@next/bundle-analyzer")({
  enabled: process.env.ANALYZE === "true",
});

module.exports = withBundleAnalyzer({
  // ... configuración anterior

  // Optimizaciones de bundle
  experimental: {
    optimizeCss: true,
  },

  // Compresión
  compress: true,

  // Eliminación de código no utilizado
  swcMinify: true,
});
```

## 8. ✅ Checklist Final

### Pre-deployment:

- [ ] API funcionando en Railway
- [ ] Variables de entorno configuradas
- [ ] CORS configurado correctamente
- [ ] Firebase conectado y funcionando

### Frontend:

- [ ] Proyecto Next.js creado
- [ ] Dependencias instaladas
- [ ] Componentes implementados
- [ ] Hooks configurados
- [ ] Variables de entorno configuradas

### Testing:

- [ ] API responde correctamente
- [ ] CORS funciona desde el frontend
- [ ] Datos se cargan correctamente
- [ ] Filtros y búsqueda funcionan
- [ ] Responsive design funciona

### Production:

- [ ] Deploy en Vercel exitoso
- [ ] DNS configurado (si tienes dominio propio)
- [ ] Analytics configurado
- [ ] Monitoreo configurado
- [ ] Performance optimizada

## 🎯 URLs Finales

Una vez deployado, tendrás:

- **API:** `https://tu-api-railway.up.railway.app`
- **Frontend:** `https://tu-proyecto.vercel.app`
- **Health Check:** `https://tu-api-railway.up.railway.app/health`
- **Next.js Endpoint:** `https://tu-api-railway.up.railway.app/unidades-proyecto/nextjs-export`

¡Con esta configuración tendrás una aplicación completa, escalable y optimizada! 🚀

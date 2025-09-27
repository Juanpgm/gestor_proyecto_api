# 🚀 Guía de Integración Next.js - Gestor de Proyectos API

## 📋 Paso a Paso para conectar tu Frontend Next.js

### 1. 📦 Instalación de Dependencias en Next.js

```bash
# Instalar SWR para data fetching
npm install swr

# Instalar axios para requests HTTP
npm install axios

# Instalar librerías de UI (opcional pero recomendado)
npm install @headlessui/react @heroicons/react

# Para gráficos (opcional)
npm install chart.js react-chartjs-2

# Para mapas (opcional)
npm install leaflet react-leaflet
npm install -D @types/leaflet
```

### 2. 🔧 Configuración Base

#### 2.1 Crear archivo de configuración API (`lib/api.js`)

```javascript
// lib/api.js
import axios from "axios";

// Configuración base de la API
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
  headers: {
    "Content-Type": "application/json",
    Accept: "application/json",
  },
});

// Interceptor para manejar errores
api.interceptors.response.use(
  (response) => response,
  (error) => {
    console.error("API Error:", error);
    return Promise.reject(error);
  }
);

// Endpoints específicos
export const endpoints = {
  // Endpoint optimizado para Next.js
  nextjsExport: "/unidades-proyecto/nextjs-export",

  // Endpoints generales
  unidades: "/unidades-proyecto",
  search: "/unidades-proyecto/search",
  filters: "/unidades-proyecto/filters",
  export: "/unidades-proyecto/export",

  // Endpoints de salud
  health: "/health",
  ping: "/ping",
};
```

#### 2.2 Variables de entorno (`.env.local`)

```env
# .env.local
NEXT_PUBLIC_API_URL=http://localhost:8000
# Para producción:
# NEXT_PUBLIC_API_URL=https://tu-api-railway.up.railway.app
```

### 3. 📊 Hooks personalizados con SWR

#### 3.1 Hook principal para unidades (`hooks/useUnidades.js`)

```javascript
// hooks/useUnidades.js
import useSWR from "swr";
import { api, endpoints } from "../lib/api";

// Fetcher optimizado para SWR
const fetcher = async (url, params = {}) => {
  const response = await api.get(url, { params });
  return response.data;
};

// Hook principal para obtener unidades
export function useUnidades(options = {}) {
  const {
    format = "nextjs",
    include_charts = true,
    include_filters = true,
    max_records = 1000,
    ...filters
  } = options;

  const params = {
    format,
    include_charts,
    include_filters,
    max_records,
    ...filters,
  };

  const { data, error, mutate, isLoading } = useSWR(
    [endpoints.nextjsExport, params],
    ([url, params]) => fetcher(url, params),
    {
      revalidateOnFocus: false,
      revalidateOnReconnect: true,
      refreshInterval: 300000, // 5 minutos
      dedupingInterval: 60000, // 1 minuto
    }
  );

  return {
    unidades: data?.data?.unidades || [],
    charts: data?.ui_components?.charts || null,
    filters: data?.ui_components?.filters || null,
    summary: data?.data?.summary || {},
    columns: data?.ui_components?.table_columns || [],
    total: data?.data?.summary?.total || 0,
    loading: isLoading,
    error,
    refresh: mutate,
  };
}

// Hook para búsqueda
export function useUnidadesBusqueda(query, filtros = {}) {
  const params = {
    q: query,
    format: "frontend",
    include_charts: false,
    page_size: 50,
    ...filtros,
  };

  const shouldFetch = query && query.length >= 2;

  const { data, error, isLoading } = useSWR(
    shouldFetch ? [endpoints.search, params] : null,
    ([url, params]) => fetcher(url, params),
    {
      revalidateOnFocus: false,
      dedupingInterval: 30000, // 30 segundos para búsquedas
    }
  );

  return {
    resultados: data?.unidades || [],
    total: data?.total || 0,
    loading: isLoading,
    error,
  };
}

// Hook para opciones de filtros
export function useFiltros() {
  const { data, error, isLoading } = useSWR(endpoints.filters, fetcher, {
    revalidateOnFocus: false,
    refreshInterval: 3600000, // 1 hora - los filtros cambian poco
  });

  return {
    filtros: data?.filters || {},
    loading: isLoading,
    error,
  };
}
```

### 4. 🎨 Componentes de UI

#### 4.1 Componente principal de lista (`components/UnidadesList.js`)

```javascript
// components/UnidadesList.js
import { useState } from "react";
import { useUnidades, useFiltros } from "../hooks/useUnidades";
import UnidadesTable from "./UnidadesTable";
import UnidadesFilters from "./UnidadesFilters";
import UnidadesStats from "./UnidadesStats";
import LoadingSpinner from "./LoadingSpinner";
import ErrorMessage from "./ErrorMessage";

export default function UnidadesList() {
  const [filtrosActivos, setFiltrosActivos] = useState({});

  const { unidades, charts, summary, columns, loading, error, refresh } =
    useUnidades({
      format: "nextjs",
      include_charts: true,
      include_filters: true,
      ...filtrosActivos,
    });

  const { filtros: opcionesFiltros } = useFiltros();

  if (loading) return <LoadingSpinner />;
  if (error) return <ErrorMessage error={error} onRetry={refresh} />;

  return (
    <div className="space-y-6">
      {/* Estadísticas */}
      <UnidadesStats summary={summary} charts={charts} />

      {/* Filtros */}
      <UnidadesFilters
        opciones={opcionesFiltros}
        filtrosActivos={filtrosActivos}
        onChange={setFiltrosActivos}
      />

      {/* Tabla de resultados */}
      <UnidadesTable unidades={unidades} columns={columns} loading={loading} />
    </div>
  );
}
```

#### 4.2 Componente de tabla (`components/UnidadesTable.js`)

```javascript
// components/UnidadesTable.js
import { useState } from "react";

export default function UnidadesTable({ unidades, columns, loading }) {
  const [sortField, setSortField] = useState(null);
  const [sortDirection, setSortDirection] = useState("asc");

  const handleSort = (field) => {
    if (sortField === field) {
      setSortDirection(sortDirection === "asc" ? "desc" : "asc");
    } else {
      setSortField(field);
      setSortDirection("asc");
    }
  };

  const sortedUnidades = [...unidades].sort((a, b) => {
    if (!sortField) return 0;

    const aVal = a[sortField] || "";
    const bVal = b[sortField] || "";

    if (sortDirection === "asc") {
      return aVal.toString().localeCompare(bVal.toString());
    } else {
      return bVal.toString().localeCompare(aVal.toString());
    }
  });

  return (
    <div className="bg-white shadow-sm rounded-lg overflow-hidden">
      <div className="px-6 py-4 border-b border-gray-200">
        <h3 className="text-lg font-medium text-gray-900">
          Unidades de Proyecto ({unidades.length})
        </h3>
      </div>

      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              {columns.map((column) => (
                <th
                  key={column.key}
                  onClick={() => column.sortable && handleSort(column.key)}
                  className={`px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider ${
                    column.sortable ? "cursor-pointer hover:bg-gray-100" : ""
                  }`}
                >
                  <div className="flex items-center space-x-1">
                    <span>{column.label}</span>
                    {column.sortable && (
                      <span className="text-gray-400">
                        {sortField === column.key
                          ? sortDirection === "asc"
                            ? "↑"
                            : "↓"
                          : "↕"}
                      </span>
                    )}
                  </div>
                </th>
              ))}
            </tr>
          </thead>

          <tbody className="bg-white divide-y divide-gray-200">
            {sortedUnidades.map((unidad, index) => (
              <tr key={unidad.id || index} className="hover:bg-gray-50">
                {columns.map((column) => (
                  <td
                    key={column.key}
                    className="px-6 py-4 whitespace-nowrap text-sm text-gray-900"
                  >
                    {renderCellValue(unidad[column.key], column.key)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function renderCellValue(value, fieldKey) {
  if (!value) return "-";

  // Casos especiales
  if (fieldKey === "completitud") {
    return `${value}%`;
  }

  if (fieldKey === "coordenadas" && value) {
    return `${value.latitude?.toFixed(4)}, ${value.longitude?.toFixed(4)}`;
  }

  // Truncar texto largo
  if (typeof value === "string" && value.length > 50) {
    return <span title={value}>{value.substring(0, 47)}...</span>;
  }

  return value;
}
```

#### 4.3 Componente de filtros (`components/UnidadesFilters.js`)

```javascript
// components/UnidadesFilters.js
import { useState } from "react";

export default function UnidadesFilters({
  opciones,
  filtrosActivos,
  onChange,
}) {
  const [filtrosLocales, setFiltrosLocales] = useState(filtrosActivos);

  const handleFilterChange = (campo, valor) => {
    const nuevosFiltros = {
      ...filtrosLocales,
      [campo]: valor || undefined,
    };

    // Remover filtros vacíos
    Object.keys(nuevosFiltros).forEach((key) => {
      if (!nuevosFiltros[key]) {
        delete nuevosFiltros[key];
      }
    });

    setFiltrosLocales(nuevosFiltros);
    onChange(nuevosFiltros);
  };

  const limpiarFiltros = () => {
    setFiltrosLocales({});
    onChange({});
  };

  return (
    <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-200">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-medium text-gray-900">Filtros</h3>
        <button
          onClick={limpiarFiltros}
          className="text-sm text-blue-600 hover:text-blue-800"
        >
          Limpiar filtros
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Filtro por estado */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Estado
          </label>
          <select
            value={filtrosLocales.estado || ""}
            onChange={(e) => handleFilterChange("estado", e.target.value)}
            className="w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="">Todos</option>
            {opciones.estados?.map((estado) => (
              <option key={estado.value} value={estado.value}>
                {estado.label} ({estado.count})
              </option>
            ))}
          </select>
        </div>

        {/* Filtro por año */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Año
          </label>
          <select
            value={filtrosLocales.ano || ""}
            onChange={(e) => handleFilterChange("ano", e.target.value)}
            className="w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="">Todos</option>
            {opciones.anos?.map((ano) => (
              <option key={ano.value} value={ano.value}>
                {ano.label} ({ano.count})
              </option>
            ))}
          </select>
        </div>

        {/* Filtro por comuna */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Comuna/Corregimiento
          </label>
          <select
            value={filtrosLocales.comuna_corregimiento || ""}
            onChange={(e) =>
              handleFilterChange("comuna_corregimiento", e.target.value)
            }
            className="w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="">Todas</option>
            {opciones.comunas?.map((comuna) => (
              <option key={comuna.value} value={comuna.value}>
                {comuna.label} ({comuna.count})
              </option>
            ))}
          </select>
        </div>

        {/* Filtro por fuente de financiación */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Fuente Financiación
          </label>
          <select
            value={filtrosLocales.fuente_financiacion || ""}
            onChange={(e) =>
              handleFilterChange("fuente_financiacion", e.target.value)
            }
            className="w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="">Todas</option>
            {opciones.fuentes_financiacion?.map((fuente) => (
              <option key={fuente.value} value={fuente.value}>
                {fuente.label} ({fuente.count})
              </option>
            ))}
          </select>
        </div>
      </div>
    </div>
  );
}
```

### 5. 📈 Componente de estadísticas y gráficos

#### 5.1 Componente de estadísticas (`components/UnidadesStats.js`)

```javascript
// components/UnidadesStats.js
import { Bar, Pie, Doughnut } from "react-chartjs-2";
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  Title,
  Tooltip,
  Legend,
  ArcElement,
} from "chart.js";

ChartJS.register(
  CategoryScale,
  LinearScale,
  BarElement,
  Title,
  Tooltip,
  Legend,
  ArcElement
);

export default function UnidadesStats({ summary, charts }) {
  if (!summary || !charts) return null;

  const estadosData = {
    labels: charts.by_estado?.map((item) => item.label) || [],
    datasets: [
      {
        label: "Proyectos por Estado",
        data: charts.by_estado?.map((item) => item.value) || [],
        backgroundColor: [
          "#3B82F6",
          "#10B981",
          "#F59E0B",
          "#EF4444",
          "#8B5CF6",
        ],
      },
    ],
  };

  const anosData = {
    labels: charts.by_ano?.map((item) => item.label) || [],
    datasets: [
      {
        label: "Proyectos por Año",
        data: charts.by_ano?.map((item) => item.value) || [],
        backgroundColor: "#3B82F6",
        borderColor: "#2563EB",
        borderWidth: 1,
      },
    ],
  };

  return (
    <div className="space-y-6">
      {/* Métricas principales */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <StatCard
          title="Total Proyectos"
          value={summary.total}
          icon="📊"
          color="blue"
        />
        <StatCard
          title="Con Coordenadas"
          value={summary.con_coordenadas}
          subtitle={`${(
            (summary.con_coordenadas / summary.total) *
            100
          ).toFixed(1)}%`}
          icon="📍"
          color="green"
        />
        <StatCard
          title="Estados Únicos"
          value={summary.estados_unicos}
          icon="🏷️"
          color="yellow"
        />
        <StatCard
          title="Completitud Promedio"
          value={`${summary.completeness_avg?.toFixed(1)}%`}
          icon="✅"
          color="purple"
        />
      </div>

      {/* Gráficos */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-white p-6 rounded-lg shadow-sm">
          <h3 className="text-lg font-medium text-gray-900 mb-4">
            Distribución por Estado
          </h3>
          <div className="h-64">
            <Doughnut
              data={estadosData}
              options={{ maintainAspectRatio: false }}
            />
          </div>
        </div>

        <div className="bg-white p-6 rounded-lg shadow-sm">
          <h3 className="text-lg font-medium text-gray-900 mb-4">
            Proyectos por Año
          </h3>
          <div className="h-64">
            <Bar data={anosData} options={{ maintainAspectRatio: false }} />
          </div>
        </div>
      </div>
    </div>
  );
}

function StatCard({ title, value, subtitle, icon, color }) {
  const colorClasses = {
    blue: "bg-blue-50 border-blue-200 text-blue-700",
    green: "bg-green-50 border-green-200 text-green-700",
    yellow: "bg-yellow-50 border-yellow-200 text-yellow-700",
    purple: "bg-purple-50 border-purple-200 text-purple-700",
  };

  return (
    <div className={`p-6 rounded-lg border-2 ${colorClasses[color]}`}>
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm font-medium opacity-75">{title}</p>
          <p className="text-2xl font-bold">{value}</p>
          {subtitle && <p className="text-sm opacity-60">{subtitle}</p>}
        </div>
        <div className="text-3xl">{icon}</div>
      </div>
    </div>
  );
}
```

### 6. 🗺️ Componente de mapa (opcional)

#### 6.1 Mapa con marcadores (`components/UnidadesMapa.js`)

```javascript
// components/UnidadesMapa.js
import { useEffect, useState } from "react";
import dynamic from "next/dynamic";

// Importar Leaflet dinámicamente para evitar problemas de SSR
const MapContainer = dynamic(
  () => import("react-leaflet").then((mod) => mod.MapContainer),
  { ssr: false }
);

const TileLayer = dynamic(
  () => import("react-leaflet").then((mod) => mod.TileLayer),
  { ssr: false }
);

const Marker = dynamic(
  () => import("react-leaflet").then((mod) => mod.Marker),
  { ssr: false }
);

const Popup = dynamic(() => import("react-leaflet").then((mod) => mod.Popup), {
  ssr: false,
});

export default function UnidadesMapa({ unidades }) {
  const [isClient, setIsClient] = useState(false);

  useEffect(() => {
    setIsClient(true);
  }, []);

  const unidadesConCoordenadas = unidades.filter((u) => u.coordenadas);

  // Centro por defecto (Medellín)
  const center = [6.2442, -75.5812];

  if (!isClient) {
    return (
      <div className="bg-gray-100 rounded-lg h-96 flex items-center justify-center">
        <p>Cargando mapa...</p>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-lg shadow-sm overflow-hidden">
      <div className="p-4 border-b border-gray-200">
        <h3 className="text-lg font-medium text-gray-900">
          Mapa de Unidades ({unidadesConCoordenadas.length} con coordenadas)
        </h3>
      </div>

      <div className="h-96">
        <MapContainer
          center={center}
          zoom={11}
          style={{ height: "100%", width: "100%" }}
        >
          <TileLayer
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          />

          {unidadesConCoordenadas.map((unidad, index) => (
            <Marker
              key={unidad.id || index}
              position={[
                unidad.coordenadas.latitude,
                unidad.coordenadas.longitude,
              ]}
            >
              <Popup>
                <div className="space-y-2">
                  <h4 className="font-medium">{unidad.nombre_up}</h4>
                  <p>
                    <strong>UPID:</strong> {unidad.upid}
                  </p>
                  <p>
                    <strong>Estado:</strong> {unidad.estado}
                  </p>
                  <p>
                    <strong>Comuna:</strong> {unidad.comuna_corregimiento}
                  </p>
                </div>
              </Popup>
            </Marker>
          ))}
        </MapContainer>
      </div>
    </div>
  );
}
```

### 7. 📱 Página principal (`pages/unidades-proyecto.js`)

```javascript
// pages/unidades-proyecto.js
import { useState } from "react";
import Head from "next/head";
import UnidadesList from "../components/UnidadesList";
import UnidadesMapa from "../components/UnidadesMapa";
import { useUnidades } from "../hooks/useUnidades";

export default function UnidadesProyectoPage() {
  const [vistaActiva, setVistaActiva] = useState("lista");
  const { unidades, loading } = useUnidades();

  return (
    <>
      <Head>
        <title>Unidades de Proyecto - Gestor</title>
        <meta name="description" content="Gestión de unidades de proyecto" />
      </Head>

      <div className="min-h-screen bg-gray-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          {/* Header */}
          <div className="mb-8">
            <h1 className="text-3xl font-bold text-gray-900">
              Unidades de Proyecto
            </h1>
            <p className="mt-2 text-gray-600">
              Gestión y visualización de unidades de proyecto
            </p>
          </div>

          {/* Navegación de vistas */}
          <div className="mb-6">
            <nav className="flex space-x-4">
              <button
                onClick={() => setVistaActiva("lista")}
                className={`px-4 py-2 rounded-lg font-medium ${
                  vistaActiva === "lista"
                    ? "bg-blue-100 text-blue-700"
                    : "text-gray-600 hover:bg-gray-100"
                }`}
              >
                📊 Lista y Estadísticas
              </button>
              <button
                onClick={() => setVistaActiva("mapa")}
                className={`px-4 py-2 rounded-lg font-medium ${
                  vistaActiva === "mapa"
                    ? "bg-blue-100 text-blue-700"
                    : "text-gray-600 hover:bg-gray-100"
                }`}
              >
                🗺️ Mapa
              </button>
            </nav>
          </div>

          {/* Contenido */}
          {vistaActiva === "lista" ? (
            <UnidadesList />
          ) : (
            <UnidadesMapa unidades={unidades} />
          )}
        </div>
      </div>
    </>
  );
}
```

### 8. 🚀 Configuración de producción

#### 8.1 Variables de entorno para producción

```env
# .env.production
NEXT_PUBLIC_API_URL=https://tu-api-railway.up.railway.app
```

#### 8.2 Configuración de Next.js (`next.config.js`)

```javascript
// next.config.js
/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  swcMinify: true,

  // Configuración para el dominio de la API
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${process.env.NEXT_PUBLIC_API_URL}/:path*`,
      },
    ];
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
        ],
      },
    ];
  },
};

module.exports = nextConfig;
```

### 9. 📝 Tipos TypeScript (opcional pero recomendado)

#### 9.1 Tipos de datos (`types/unidades.ts`)

```typescript
// types/unidades.ts
export interface UnidadProyecto {
  id: string;
  upid: string;
  bpin: string;
  nombre_up: string;
  estado: string;
  ano: string;
  comuna_corregimiento: string;
  barrio_vereda: string;
  coordenadas: {
    latitude: number;
    longitude: number;
  } | null;
  fuente_financiacion: string;
  tipo_intervencion: string;
  nombre_centro_gestor: string;
  tiene_coordenadas: boolean;
  completitud: number;
}

export interface APIResponse<T> {
  success: boolean;
  data: T;
  total?: number;
  error?: string;
  cached?: boolean;
}

export interface ChartData {
  by_estado: Array<{ label: string; value: number }>;
  by_ano: Array<{ label: string; value: number }>;
  by_comuna: Array<{ label: string; value: number }>;
  by_fuente: Array<{ label: string; value: number }>;
  by_tipo_intervencion: Array<{ label: string; value: number }>;
}

export interface FilterOptions {
  estados: Array<{ value: string; label: string; count: number }>;
  anos: Array<{ value: string; label: string; count: number }>;
  comunas: Array<{ value: string; label: string; count: number }>;
  fuentes_financiacion: Array<{ value: string; label: string; count: number }>;
  tipos_intervencion: Array<{ value: string; label: string; count: number }>;
  centros_gestores: Array<{ value: string; label: string; count: number }>;
}
```

### 10. 🎯 Comandos para desarrollo

```json
// package.json scripts
{
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start",
    "type-check": "tsc --noEmit"
  }
}
```

### 11. ✅ Checklist de implementación

- [ ] Instalar dependencias necesarias
- [ ] Configurar variables de entorno
- [ ] Crear archivo de configuración de API
- [ ] Implementar hooks personalizados
- [ ] Crear componentes de UI básicos
- [ ] Probar conexión con la API
- [ ] Implementar filtros y búsqueda
- [ ] Agregar gráficos (opcional)
- [ ] Implementar mapa (opcional)
- [ ] Configurar para producción

### 🔧 URLs de la API que puedes usar:

1. **Endpoint optimizado para Next.js:**

   ```
   GET /unidades-proyecto/nextjs-export?format=nextjs&include_charts=true&include_filters=true
   ```

2. **Búsqueda:**

   ```
   GET /unidades-proyecto/search?q=texto&estado=En ejecución&ano=2024
   ```

3. **Filtros:**

   ```
   GET /unidades-proyecto/filters
   ```

4. **Health check:**
   ```
   GET /health
   ```

Esta guía te permitirá conectar completamente tu API con Next.js manteniendo los nombres originales de los campos de la base de datos (`nombre_up` y `nombre_centro_gestor`) y proporcionando una experiencia optimizada para el frontend.

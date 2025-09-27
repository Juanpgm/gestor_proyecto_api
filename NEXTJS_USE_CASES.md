# 🎯 Casos de Uso Específicos - Next.js + API

## Ejemplos prácticos de implementación

### 1. 📊 Dashboard Ejecutivo Completo

```javascript
// pages/executive-dashboard.js
import { useState, useEffect } from "react";
import { useUnidades } from "../hooks/useUnidades";
import { Line, Bar, Doughnut } from "react-chartjs-2";

export default function ExecutiveDashboard() {
  const [periodo, setPeriodo] = useState("2024");

  const { unidades, charts, summary, loading } = useUnidades({
    ano: periodo,
    format: "nextjs",
    include_charts: true,
    max_records: 2000,
  });

  // KPIs calculados
  const kpis = {
    totalProyectos: summary.total || 0,
    proyectosActivos: unidades.filter((u) => u.estado === "En ejecución")
      .length,
    cobertura: summary.con_coordenadas || 0,
    completitudPromedio: summary.completeness_avg || 0,
  };

  const metricsCards = [
    {
      title: "Total Proyectos",
      value: kpis.totalProyectos,
      change: "+12%",
      icon: "📊",
      color: "blue",
    },
    {
      title: "En Ejecución",
      value: kpis.proyectosActivos,
      change: "+5%",
      icon: "🚀",
      color: "green",
    },
    {
      title: "Con Geolocalización",
      value: kpis.cobertura,
      change: `${((kpis.cobertura / kpis.totalProyectos) * 100).toFixed(1)}%`,
      icon: "📍",
      color: "purple",
    },
    {
      title: "Completitud Promedio",
      value: `${kpis.completitudPromedio.toFixed(1)}%`,
      change: "+2.3%",
      icon: "✅",
      color: "yellow",
    },
  ];

  return (
    <div className="min-h-screen bg-gray-50 p-8">
      <div className="max-w-7xl mx-auto">
        {/* Header Ejecutivo */}
        <div className="mb-8">
          <div className="flex justify-between items-center">
            <div>
              <h1 className="text-3xl font-bold text-gray-900">
                Dashboard Ejecutivo
              </h1>
              <p className="text-gray-600">
                Vista general de proyectos {periodo}
              </p>
            </div>

            <select
              value={periodo}
              onChange={(e) => setPeriodo(e.target.value)}
              className="px-4 py-2 border border-gray-300 rounded-lg"
            >
              <option value="2024">2024</option>
              <option value="2023">2023</option>
              <option value="2022">2022</option>
            </select>
          </div>
        </div>

        {/* KPIs Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
          {metricsCards.map((metric, index) => (
            <KPICard key={index} {...metric} loading={loading} />
          ))}
        </div>

        {/* Gráficos Principales */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 mb-8">
          <ChartCard
            title="Distribución por Estado"
            subtitle="Estado actual de los proyectos"
          >
            <Doughnut
              data={prepareEstadosChart(charts?.by_estado)}
              options={{ maintainAspectRatio: false }}
            />
          </ChartCard>

          <ChartCard
            title="Evolución Mensual"
            subtitle="Proyectos iniciados por mes"
          >
            <Line
              data={prepareTimelineChart(unidades)}
              options={{
                maintainAspectRatio: false,
                responsive: true,
              }}
            />
          </ChartCard>
        </div>

        {/* Tabla Top Proyectos */}
        <div className="bg-white rounded-lg shadow-sm p-6">
          <h3 className="text-lg font-medium mb-4">Proyectos Destacados</h3>
          <TopProyectosTable unidades={unidades.slice(0, 10)} />
        </div>
      </div>
    </div>
  );
}

// Componentes auxiliares
function KPICard({ title, value, change, icon, color, loading }) {
  const colorClasses = {
    blue: "bg-blue-50 border-blue-200",
    green: "bg-green-50 border-green-200",
    purple: "bg-purple-50 border-purple-200",
    yellow: "bg-yellow-50 border-yellow-200",
  };

  if (loading) {
    return (
      <div className="animate-pulse bg-gray-100 p-6 rounded-lg border-2">
        <div className="h-16"></div>
      </div>
    );
  }

  return (
    <div className={`p-6 rounded-lg border-2 ${colorClasses[color]}`}>
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm font-medium text-gray-600">{title}</p>
          <p className="text-2xl font-bold text-gray-900">{value}</p>
          <p className="text-sm text-green-600">{change}</p>
        </div>
        <div className="text-3xl">{icon}</div>
      </div>
    </div>
  );
}

function ChartCard({ title, subtitle, children }) {
  return (
    <div className="bg-white p-6 rounded-lg shadow-sm">
      <div className="mb-4">
        <h3 className="text-lg font-medium text-gray-900">{title}</h3>
        <p className="text-sm text-gray-600">{subtitle}</p>
      </div>
      <div className="h-64">{children}</div>
    </div>
  );
}
```

### 2. 🗺️ Mapa Interactivo Avanzado

```javascript
// components/MapaAvanzado.js
import { useState, useEffect } from "react";
import dynamic from "next/dynamic";
import { useUnidades } from "../hooks/useUnidades";

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
const MarkerClusterGroup = dynamic(() => import("react-leaflet-cluster"), {
  ssr: false,
});

export default function MapaAvanzado() {
  const [filtroMapa, setFiltroMapa] = useState({});
  const [capaActiva, setCapaActiva] = useState("satelite");

  const { unidades, loading } = useUnidades({
    ...filtroMapa,
    format: "nextjs",
  });

  const unidadesConCoordenadas = unidades.filter((u) => u.coordenadas);

  const capas = {
    satelite:
      "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
    calles: "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
    topografico: "https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png",
  };

  // Crear iconos personalizados por estado
  const createCustomIcon = (estado) => {
    const colores = {
      "En ejecución": "#10B981",
      Terminado: "#3B82F6",
      "En proceso": "#F59E0B",
      Suspendido: "#EF4444",
    };

    if (typeof window !== "undefined") {
      const L = require("leaflet");
      return new L.DivIcon({
        html: `<div style="background-color: ${
          colores[estado] || "#6B7280"
        }; width: 20px; height: 20px; border-radius: 50%; border: 2px solid white; box-shadow: 0 2px 4px rgba(0,0,0,0.2);"></div>`,
        className: "custom-marker",
        iconSize: [20, 20],
        iconAnchor: [10, 10],
      });
    }
    return null;
  };

  const estadisticasPorComuna = unidadesConCoordenadas.reduce((acc, unidad) => {
    const comuna = unidad.comuna_corregimiento || "Sin definir";
    if (!acc[comuna]) {
      acc[comuna] = { total: 0, estados: {} };
    }
    acc[comuna].total++;
    acc[comuna].estados[unidad.estado] =
      (acc[comuna].estados[unidad.estado] || 0) + 1;
    return acc;
  }, {});

  if (typeof window === "undefined") {
    return (
      <div className="h-96 bg-gray-100 rounded-lg flex items-center justify-center">
        Cargando mapa...
      </div>
    );
  }

  return (
    <div className="bg-white rounded-lg shadow-sm overflow-hidden">
      {/* Controles del Mapa */}
      <div className="p-4 bg-gray-50 border-b flex flex-wrap justify-between items-center">
        <div className="flex space-x-4 mb-2 sm:mb-0">
          <select
            value={capaActiva}
            onChange={(e) => setCapaActiva(e.target.value)}
            className="px-3 py-1 border border-gray-300 rounded text-sm"
          >
            <option value="satelite">🛰️ Satélite</option>
            <option value="calles">🗺️ Calles</option>
            <option value="topografico">🏔️ Topográfico</option>
          </select>

          <select
            value={filtroMapa.estado || ""}
            onChange={(e) =>
              setFiltroMapa({
                ...filtroMapa,
                estado: e.target.value || undefined,
              })
            }
            className="px-3 py-1 border border-gray-300 rounded text-sm"
          >
            <option value="">Todos los estados</option>
            <option value="En ejecución">En ejecución</option>
            <option value="Terminado">Terminado</option>
            <option value="En proceso">En proceso</option>
          </select>
        </div>

        <div className="text-sm text-gray-600">
          📍 {unidadesConCoordenadas.length} proyectos georreferenciados
        </div>
      </div>

      {/* Mapa */}
      <div className="h-96 relative">
        <MapContainer
          center={[6.2442, -75.5812]}
          zoom={11}
          style={{ height: "100%", width: "100%" }}
        >
          <TileLayer
            url={capas[capaActiva]}
            attribution="&copy; OpenStreetMap contributors"
          />

          <MarkerClusterGroup>
            {unidadesConCoordenadas.map((unidad, index) => (
              <Marker
                key={unidad.id || index}
                position={[
                  unidad.coordenadas.latitude,
                  unidad.coordenadas.longitude,
                ]}
                icon={createCustomIcon(unidad.estado)}
              >
                <Popup maxWidth={300}>
                  <ProyectoPopup unidad={unidad} />
                </Popup>
              </Marker>
            ))}
          </MarkerClusterGroup>
        </MapContainer>

        {loading && (
          <div className="absolute inset-0 bg-white bg-opacity-75 flex items-center justify-center">
            <div className="text-center">
              <div className="animate-spin h-8 w-8 border-b-2 border-blue-600 rounded-full mx-auto mb-2"></div>
              <p className="text-sm text-gray-600">Cargando proyectos...</p>
            </div>
          </div>
        )}
      </div>

      {/* Leyenda y Estadísticas */}
      <div className="p-4 bg-gray-50 border-t">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <h4 className="font-medium text-gray-900 mb-2">Leyenda</h4>
            <div className="flex flex-wrap gap-4 text-sm">
              <div className="flex items-center">
                <div className="w-3 h-3 bg-green-500 rounded-full mr-2"></div>
                En ejecución
              </div>
              <div className="flex items-center">
                <div className="w-3 h-3 bg-blue-500 rounded-full mr-2"></div>
                Terminado
              </div>
              <div className="flex items-center">
                <div className="w-3 h-3 bg-yellow-500 rounded-full mr-2"></div>
                En proceso
              </div>
              <div className="flex items-center">
                <div className="w-3 h-3 bg-red-500 rounded-full mr-2"></div>
                Suspendido
              </div>
            </div>
          </div>

          <div>
            <h4 className="font-medium text-gray-900 mb-2">Top Comunas</h4>
            <div className="text-sm">
              {Object.entries(estadisticasPorComuna)
                .sort(([, a], [, b]) => b.total - a.total)
                .slice(0, 3)
                .map(([comuna, stats]) => (
                  <div key={comuna} className="flex justify-between">
                    <span>{comuna}</span>
                    <span className="font-medium">{stats.total}</span>
                  </div>
                ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

// Componente del popup del proyecto
function ProyectoPopup({ unidad }) {
  return (
    <div className="space-y-2">
      <h4 className="font-bold text-blue-900">{unidad.nombre_up}</h4>

      <div className="grid grid-cols-2 gap-2 text-sm">
        <div>
          <span className="font-medium">UPID:</span>
          <div>{unidad.upid}</div>
        </div>
        <div>
          <span className="font-medium">BPIN:</span>
          <div>{unidad.bpin}</div>
        </div>
      </div>

      <div className="text-sm">
        <div className="flex justify-between">
          <span className="font-medium">Estado:</span>
          <span
            className={`px-2 py-1 rounded text-xs ${getEstadoColor(
              unidad.estado
            )}`}
          >
            {unidad.estado}
          </span>
        </div>
      </div>

      <div className="text-sm">
        <span className="font-medium">Ubicación:</span>
        <div>{unidad.comuna_corregimiento}</div>
        {unidad.barrio_vereda && (
          <div className="text-gray-600">{unidad.barrio_vereda}</div>
        )}
      </div>

      <div className="text-sm">
        <span className="font-medium">Centro Gestor:</span>
        <div>{unidad.nombre_centro_gestor}</div>
      </div>

      <div className="pt-2 border-t">
        <button className="text-blue-600 hover:text-blue-800 text-sm font-medium">
          Ver detalles completos →
        </button>
      </div>
    </div>
  );
}

function getEstadoColor(estado) {
  const colores = {
    "En ejecución": "bg-green-100 text-green-800",
    Terminado: "bg-blue-100 text-blue-800",
    "En proceso": "bg-yellow-100 text-yellow-800",
    Suspendido: "bg-red-100 text-red-800",
  };
  return colores[estado] || "bg-gray-100 text-gray-800";
}
```

### 3. 📱 Vista Mobile-First Optimizada

```javascript
// components/MobileUnidadesList.js
import { useState } from "react";
import { useUnidades, useUnidadesBusqueda } from "../hooks/useUnidades";

export default function MobileUnidadesList() {
  const [searchQuery, setSearchQuery] = useState("");
  const [showFilters, setShowFilters] = useState(false);
  const [filtros, setFiltros] = useState({});

  const { unidades, loading } = useUnidades(filtros);
  const { resultados } = useUnidadesBusqueda(searchQuery);

  const displayData = searchQuery.length >= 2 ? resultados : unidades;

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header Mobile */}
      <div className="bg-white shadow-sm sticky top-0 z-10">
        <div className="px-4 py-3">
          <h1 className="text-xl font-bold text-gray-900">Proyectos</h1>

          {/* Búsqueda Mobile */}
          <div className="mt-3 relative">
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Buscar proyectos..."
              className="w-full pl-10 pr-12 py-2 bg-gray-100 border-0 rounded-full focus:bg-white focus:ring-2 focus:ring-blue-500"
            />
            <div className="absolute left-3 top-2.5">🔍</div>
            <button
              onClick={() => setShowFilters(!showFilters)}
              className="absolute right-3 top-2"
            >
              ⚙️
            </button>
          </div>
        </div>

        {/* Filtros Mobile Collapse */}
        {showFilters && (
          <div className="px-4 pb-4 border-t bg-gray-50">
            <MobileFilters filtros={filtros} onChange={setFiltros} />
          </div>
        )}
      </div>

      {/* Lista Mobile */}
      <div className="px-4 py-4">
        {loading ? (
          <MobileSkeletonLoader />
        ) : (
          <div className="space-y-3">
            {displayData.map((unidad, index) => (
              <MobileProyectoCard key={unidad.id || index} unidad={unidad} />
            ))}
          </div>
        )}

        {displayData.length === 0 && !loading && (
          <div className="text-center py-12">
            <div className="text-gray-400 text-5xl mb-4">📋</div>
            <p className="text-gray-500">No se encontraron proyectos</p>
          </div>
        )}
      </div>
    </div>
  );
}

function MobileProyectoCard({ unidad }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden">
      <div
        className="p-4 cursor-pointer"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="flex justify-between items-start">
          <div className="flex-1 min-w-0">
            <h3 className="font-medium text-gray-900 truncate">
              {unidad.nombre_up}
            </h3>
            <p className="text-sm text-gray-600 mt-1">UPID: {unidad.upid}</p>
          </div>

          <div className="flex items-center ml-4">
            <span
              className={`px-2 py-1 text-xs rounded-full ${getEstadoMobileColor(
                unidad.estado
              )}`}
            >
              {unidad.estado}
            </span>
            <span className="ml-2 text-gray-400">{expanded ? "▲" : "▼"}</span>
          </div>
        </div>

        <div className="mt-2 flex items-center text-sm text-gray-500">
          <span>📍</span>
          <span className="ml-1 truncate">{unidad.comuna_corregimiento}</span>
          {unidad.coordenadas && (
            <span className="ml-2 text-green-600">🗺️</span>
          )}
        </div>
      </div>

      {expanded && (
        <div className="px-4 pb-4 border-t bg-gray-50">
          <div className="space-y-2 text-sm">
            <div className="flex justify-between">
              <span className="text-gray-600">BPIN:</span>
              <span className="font-medium">{unidad.bpin}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-600">Año:</span>
              <span className="font-medium">{unidad.ano}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-600">Centro Gestor:</span>
              <span className="font-medium text-right flex-1 ml-2">
                {unidad.nombre_centro_gestor}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-600">Fuente:</span>
              <span className="font-medium text-right flex-1 ml-2">
                {unidad.fuente_financiacion}
              </span>
            </div>

            {unidad.coordenadas && (
              <div className="mt-3 pt-3 border-t">
                <button className="w-full bg-blue-50 text-blue-700 py-2 rounded-lg text-sm font-medium">
                  📍 Ver en mapa
                </button>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function MobileFilters({ filtros, onChange }) {
  return (
    <div className="space-y-3 mt-3">
      <select
        value={filtros.estado || ""}
        onChange={(e) =>
          onChange({ ...filtros, estado: e.target.value || undefined })
        }
        className="w-full p-2 border border-gray-300 rounded-lg text-sm"
      >
        <option value="">Todos los estados</option>
        <option value="En ejecución">En ejecución</option>
        <option value="Terminado">Terminado</option>
      </select>

      <select
        value={filtros.ano || ""}
        onChange={(e) =>
          onChange({ ...filtros, ano: e.target.value || undefined })
        }
        className="w-full p-2 border border-gray-300 rounded-lg text-sm"
      >
        <option value="">Todos los años</option>
        <option value="2024">2024</option>
        <option value="2023">2023</option>
      </select>
    </div>
  );
}

function MobileSkeletonLoader() {
  return (
    <div className="space-y-3">
      {[1, 2, 3, 4, 5].map((i) => (
        <div key={i} className="bg-white rounded-lg p-4 animate-pulse">
          <div className="h-4 bg-gray-200 rounded w-3/4 mb-2"></div>
          <div className="h-3 bg-gray-200 rounded w-1/2 mb-2"></div>
          <div className="h-3 bg-gray-200 rounded w-2/3"></div>
        </div>
      ))}
    </div>
  );
}

function getEstadoMobileColor(estado) {
  const colores = {
    "En ejecución": "bg-green-100 text-green-800",
    Terminado: "bg-blue-100 text-blue-800",
    "En proceso": "bg-yellow-100 text-yellow-800",
    Suspendido: "bg-red-100 text-red-800",
  };
  return colores[estado] || "bg-gray-100 text-gray-800";
}
```

Estos ejemplos te muestran implementaciones completas y específicas para diferentes casos de uso. Todos mantienen los nombres correctos de los campos de la base de datos (`nombre_up` y `nombre_centro_gestor`) y están optimizados para trabajar con tu API. 🚀

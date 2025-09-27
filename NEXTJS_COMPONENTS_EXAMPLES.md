# 🔧 Componentes Auxiliares para Next.js

## Componentes de utilidad necesarios para la integración

### 1. LoadingSpinner.js

```javascript
// components/LoadingSpinner.js
export default function LoadingSpinner({
  size = "medium",
  message = "Cargando...",
}) {
  const sizeClasses = {
    small: "h-4 w-4",
    medium: "h-8 w-8",
    large: "h-12 w-12",
  };

  return (
    <div className="flex flex-col items-center justify-center p-8">
      <div
        className={`animate-spin rounded-full border-b-2 border-blue-600 ${sizeClasses[size]}`}
      ></div>
      {message && <p className="mt-4 text-sm text-gray-600">{message}</p>}
    </div>
  );
}
```

### 2. ErrorMessage.js

```javascript
// components/ErrorMessage.js
export default function ErrorMessage({ error, onRetry }) {
  const getErrorMessage = (error) => {
    if (error?.response?.data?.detail) {
      return error.response.data.detail;
    }
    if (error?.message) {
      return error.message;
    }
    return "Ha ocurrido un error inesperado";
  };

  return (
    <div className="bg-red-50 border border-red-200 rounded-lg p-6">
      <div className="flex items-center">
        <div className="flex-shrink-0">
          <span className="text-red-400 text-xl">⚠️</span>
        </div>
        <div className="ml-3 flex-1">
          <h3 className="text-sm font-medium text-red-800">
            Error al cargar los datos
          </h3>
          <div className="mt-2 text-sm text-red-700">
            <p>{getErrorMessage(error)}</p>
          </div>
        </div>
      </div>

      {onRetry && (
        <div className="mt-4">
          <button
            onClick={onRetry}
            className="bg-red-100 hover:bg-red-200 text-red-800 px-4 py-2 rounded-md text-sm font-medium transition-colors"
          >
            Reintentar
          </button>
        </div>
      )}
    </div>
  );
}
```

### 3. SearchBox.js

```javascript
// components/SearchBox.js
import { useState, useEffect } from "react";
import { useUnidadesBusqueda } from "../hooks/useUnidades";

export default function SearchBox({
  onResultSelect,
  placeholder = "Buscar por UPID, BPIN, nombre...",
}) {
  const [query, setQuery] = useState("");
  const [showResults, setShowResults] = useState(false);

  const { resultados, loading } = useUnidadesBusqueda(query);

  useEffect(() => {
    setShowResults(query.length >= 2 && resultados.length > 0);
  }, [query, resultados]);

  const handleSelect = (unidad) => {
    setShowResults(false);
    setQuery("");
    onResultSelect(unidad);
  };

  return (
    <div className="relative">
      <div className="relative">
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder={placeholder}
          className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
        />
        <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
          <span className="text-gray-400">🔍</span>
        </div>
        {loading && (
          <div className="absolute inset-y-0 right-0 pr-3 flex items-center">
            <div className="animate-spin h-4 w-4 border-b-2 border-blue-600 rounded-full"></div>
          </div>
        )}
      </div>

      {showResults && (
        <div className="absolute z-10 mt-1 w-full bg-white rounded-lg shadow-lg border border-gray-200 max-h-96 overflow-y-auto">
          {resultados.map((unidad, index) => (
            <button
              key={unidad.id || index}
              onClick={() => handleSelect(unidad)}
              className="w-full px-4 py-3 text-left hover:bg-gray-50 border-b border-gray-100 last:border-b-0"
            >
              <div className="font-medium text-gray-900">
                {unidad.nombre_up}
              </div>
              <div className="text-sm text-gray-600">
                UPID: {unidad.upid} | BPIN: {unidad.bpin}
              </div>
              <div className="text-xs text-gray-500">
                {unidad.comuna_corregimiento} | {unidad.estado}
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
```

### 4. ExportButton.js

```javascript
// components/ExportButton.js
import { useState } from "react";
import { api, endpoints } from "../lib/api";

export default function ExportButton({ filtros = {}, formato = "csv" }) {
  const [exporting, setExporting] = useState(false);

  const handleExport = async () => {
    setExporting(true);

    try {
      const params = {
        format: formato,
        ...filtros,
      };

      const response = await api.get(endpoints.export, {
        params,
        responseType: "blob", // Para archivos
      });

      // Crear y descargar archivo
      const blob = new Blob([response.data]);
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `unidades_proyecto_${
        new Date().toISOString().split("T")[0]
      }.${formato}`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);
    } catch (error) {
      console.error("Error exportando:", error);
      alert("Error al exportar los datos");
    } finally {
      setExporting(false);
    }
  };

  const formatLabels = {
    csv: "Excel (CSV)",
    json: "JSON",
    geojson: "GeoJSON (Mapas)",
  };

  return (
    <button
      onClick={handleExport}
      disabled={exporting}
      className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
    >
      {exporting ? (
        <>
          <div className="animate-spin -ml-1 mr-2 h-4 w-4 border-b-2 border-white rounded-full"></div>
          Exportando...
        </>
      ) : (
        <>
          <span className="mr-2">📊</span>
          Exportar {formatLabels[formato]}
        </>
      )}
    </button>
  );
}
```

## 🚀 Ejemplo de uso completo en una página

### pages/dashboard.js

```javascript
// pages/dashboard.js
import { useState } from "react";
import Head from "next/head";
import { useUnidades, useFiltros } from "../hooks/useUnidades";
import UnidadesStats from "../components/UnidadesStats";
import UnidadesTable from "../components/UnidadesTable";
import UnidadesFilters from "../components/UnidadesFilters";
import SearchBox from "../components/SearchBox";
import ExportButton from "../components/ExportButton";
import LoadingSpinner from "../components/LoadingSpinner";
import ErrorMessage from "../components/ErrorMessage";

export default function Dashboard() {
  const [filtrosActivos, setFiltrosActivos] = useState({});
  const [unidadSeleccionada, setUnidadSeleccionada] = useState(null);

  const { unidades, charts, summary, columns, loading, error, refresh } =
    useUnidades({
      format: "nextjs",
      include_charts: true,
      include_filters: true,
      ...filtrosActivos,
    });

  const { filtros: opcionesFiltros, loading: loadingFiltros } = useFiltros();

  if (loading && !unidades.length)
    return <LoadingSpinner size="large" message="Cargando dashboard..." />;
  if (error) return <ErrorMessage error={error} onRetry={refresh} />;

  return (
    <>
      <Head>
        <title>Dashboard - Gestor de Proyectos</title>
        <meta name="description" content="Dashboard de unidades de proyecto" />
      </Head>

      <div className="min-h-screen bg-gray-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          {/* Header */}
          <div className="mb-8">
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between">
              <div>
                <h1 className="text-3xl font-bold text-gray-900">
                  Dashboard de Proyectos
                </h1>
                <p className="mt-2 text-gray-600">
                  Gestión y análisis de unidades de proyecto
                </p>
              </div>

              <div className="mt-4 sm:mt-0 flex space-x-3">
                <ExportButton filtros={filtrosActivos} formato="csv" />
                <ExportButton filtros={filtrosActivos} formato="json" />
                <button
                  onClick={refresh}
                  className="inline-flex items-center px-4 py-2 border border-gray-300 text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50"
                  disabled={loading}
                >
                  🔄 Actualizar
                </button>
              </div>
            </div>
          </div>

          {/* Búsqueda rápida */}
          <div className="mb-6">
            <div className="max-w-md">
              <SearchBox
                onResultSelect={setUnidadSeleccionada}
                placeholder="Buscar proyecto por UPID, BPIN o nombre..."
              />
            </div>
          </div>

          {/* Estadísticas */}
          <div className="mb-8">
            <UnidadesStats summary={summary} charts={charts} />
          </div>

          {/* Filtros */}
          <div className="mb-6">
            <UnidadesFilters
              opciones={opcionesFiltros}
              filtrosActivos={filtrosActivos}
              onChange={setFiltrosActivos}
            />
          </div>

          {/* Resultado de búsqueda */}
          {unidadSeleccionada && (
            <div className="mb-6 bg-blue-50 border border-blue-200 rounded-lg p-4">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="font-medium text-blue-900">
                    Proyecto seleccionado: {unidadSeleccionada.nombre_up}
                  </h3>
                  <p className="text-sm text-blue-700">
                    UPID: {unidadSeleccionada.upid} | Estado:{" "}
                    {unidadSeleccionada.estado}
                  </p>
                </div>
                <button
                  onClick={() => setUnidadSeleccionada(null)}
                  className="text-blue-600 hover:text-blue-800"
                >
                  ✕
                </button>
              </div>
            </div>
          )}

          {/* Tabla de datos */}
          <UnidadesTable
            unidades={unidades}
            columns={columns}
            loading={loading}
          />

          {/* Footer con información */}
          <div className="mt-8 text-center text-sm text-gray-500">
            {loading ? (
              <p>Actualizando datos...</p>
            ) : (
              <p>
                Mostrando {unidades.length} de {summary.total} proyectos
                {filtrosActivos && Object.keys(filtrosActivos).length > 0 && (
                  <span> (filtrados)</span>
                )}
              </p>
            )}
          </div>
        </div>
      </div>
    </>
  );
}
```

## 📱 Responsive Design con Tailwind CSS

Asegúrate de tener Tailwind CSS configurado:

```bash
npm install -D tailwindcss postcss autoprefixer
npx tailwindcss init -p
```

Y en tu `tailwind.config.js`:

```javascript
// tailwind.config.js
module.exports = {
  content: [
    "./pages/**/*.{js,ts,jsx,tsx}",
    "./components/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {},
  },
  plugins: [],
};
```

## 🔍 Testing (opcional)

Para testear los componentes:

```bash
npm install -D @testing-library/react @testing-library/jest-dom jest-environment-jsdom
```

Ejemplo de test para el hook:

```javascript
// __tests__/useUnidades.test.js
import { renderHook, waitFor } from "@testing-library/react";
import { SWRConfig } from "swr";
import { useUnidades } from "../hooks/useUnidades";

const wrapper = ({ children }) => (
  <SWRConfig value={{ dedupingInterval: 0 }}>{children}</SWRConfig>
);

test("useUnidades returns data correctly", async () => {
  const { result } = renderHook(() => useUnidades(), { wrapper });

  await waitFor(() => {
    expect(result.current.loading).toBe(false);
  });

  expect(result.current.unidades).toBeDefined();
});
```

Con esta guía completa tienes todo lo necesario para integrar tu API con Next.js manteniendo los nombres originales de los campos de la base de datos! 🚀

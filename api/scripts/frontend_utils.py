"""
Utilidades adicionales para NextJS Frontend
Funciones que simplifican el consumo de la API desde el frontend
"""

from typing import Dict, List, Any, Optional, Tuple
from functools import reduce
from api.scripts.unidades_proyecto import safe_get

# ============================================================================
# TRANSFORMADORES PARA FRONTEND NEXTJS
# ============================================================================

def normalize_for_frontend(unidades: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Normalizar datos para consumo fácil en NextJS - OPTIMIZADO PARA COSTOS
    
    OPTIMIZACIONES APLICADAS:
    - Procesamiento funcional eficiente en memoria
    - Extracción selectiva de campos para reducir payload
    - Validación optimizada de coordenadas
    - Cálculo lazy de completitud
    
    Args:
        unidades: Lista de unidades de proyecto
    
    Returns:
        Lista normalizada optimizada para frontend y costos reducidos
    """
    def transform_unidad(unidad: Dict[str, Any]) -> Dict[str, Any]:
        props = safe_get(unidad, 'properties', {})
        
        # Estructura plana y consistente
        return {
            # IDs principales
            'id': unidad.get('id'),
            'upid': safe_get(props, 'upid'),
            'bpin': safe_get(props, 'bpin'),
            
            # Información básica
            'nombre': safe_get(props, 'nombre_up', ''),
            'estado': safe_get(props, 'estado', 'sin_definir'),
            'ano': str(safe_get(props, 'ano', '')),  # Siempre string
            
            # Ubicación
            'comuna_corregimiento': safe_get(props, 'comuna_corregimiento', ''),
            'barrio_vereda': safe_get(props, 'barrio_vereda', ''),
            
            # Coordenadas normalizadas
            'coordenadas': extract_coordinates(unidad),
            
            # Información financiera y técnica
            'fuente_financiacion': safe_get(props, 'fuente_financiacion', ''),
            'tipo_intervencion': safe_get(props, 'tipo_intervencion', ''),
            'centro_gestor': safe_get(props, 'nombre_centro_gestor', ''),
            
            # Referencias
            'referencia_proceso': safe_get(props, 'referencia_proceso', ''),
            'referencia_contrato': safe_get(props, 'referencia_contrato', ''),
            
            # Flags útiles para frontend
            'tiene_coordenadas': bool(extract_coordinates(unidad)),
            'completitud': calculate_completeness(props),
        }
    
    return [transform_unidad(u) for u in unidades]

def extract_coordinates(unidad: Dict[str, Any]) -> Optional[Dict[str, float]]:
    """
    Extraer coordenadas de forma robusta
    
    Args:
        unidad: Unidad de proyecto
    
    Returns:
        Dict con lat/lng o None si no hay coordenadas válidas
    """
    try:
        coords = safe_get(unidad, 'geometry.coordinates')
        
        if not coords or len(coords) < 2:
            return None
            
        lng, lat = coords[0], coords[1]
        
        # Validar que son números válidos
        if (isinstance(lng, (int, float)) and 
            isinstance(lat, (int, float)) and 
            -180 <= lng <= 180 and 
            -90 <= lat <= 90):
            return {
                'latitude': float(lat),
                'longitude': float(lng)
            }
    except Exception:
        pass
    
    return None

def calculate_completeness(properties: Dict[str, Any]) -> float:
    """
    Calcular completitud de datos (útil para UX)
    
    Args:
        properties: Propiedades de la unidad
    
    Returns:
        Porcentaje de completitud (0-100)
    """
    important_fields = [
        'upid', 'bpin', 'nombre_up', 'estado', 'ano',
        'comuna_corregimiento', 'barrio_vereda', 'fuente_financiacion',
        'tipo_intervencion', 'nombre_centro_gestor'
    ]
    
    filled_count = sum(
        1 for field in important_fields 
        if properties.get(field) and str(properties.get(field)).strip()
    )
    
    return round((filled_count / len(important_fields)) * 100, 1)

# ============================================================================
# UTILIDADES DE AGRUPACIÓN PARA FRONTEND
# ============================================================================

def group_for_charts(unidades: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Agrupar datos optimizados para gráficos en NextJS
    
    Args:
        unidades: Lista de unidades normalizadas
    
    Returns:
        Dict con datos agrupados para diferentes tipos de charts
    """
    if not unidades:
        return {
            'by_estado': [],
            'by_ano': [],
            'by_comuna': [],
            'by_fuente': [],
            'by_tipo_intervencion': [],
            'geographic': []
        }
    
    # Función auxiliar para contar y formatear
    def count_and_format(group_func, label_func=None):
        if label_func is None:
            label_func = lambda x: str(x) if x else 'Sin definir'
        
        groups = {}
        for unidad in unidades:
            key = group_func(unidad)
            label = label_func(key)
            groups[label] = groups.get(label, 0) + 1
        
        return [{'label': k, 'value': v} for k, v in sorted(groups.items())]
    
    return {
        'by_estado': count_and_format(lambda u: u.get('estado')),
        'by_ano': count_and_format(lambda u: u.get('ano')),
        'by_comuna': count_and_format(lambda u: u.get('comuna_corregimiento')),
        'by_fuente': count_and_format(lambda u: u.get('fuente_financiacion')),
        'by_tipo_intervencion': count_and_format(lambda u: u.get('tipo_intervencion')),
        'geographic': [
            {
                'id': u.get('id'),
                'upid': u.get('upid'),
                'nombre': u.get('nombre', '')[:50],  # Truncar para tooltips
                'coordenadas': u.get('coordenadas'),
                'estado': u.get('estado')
            }
            for u in unidades 
            if u.get('tiene_coordenadas')
        ]
    }

def get_filter_options(unidades: List[Dict[str, Any]]) -> Dict[str, List[str]]:
    """
    Obtener opciones únicas para filtros en frontend
    
    Args:
        unidades: Lista de unidades normalizadas
    
    Returns:
        Dict con opciones para cada campo filtrable
    """
    def get_unique_values(field: str) -> List[str]:
        values = set()
        for unidad in unidades:
            value = unidad.get(field)
            if value and str(value).strip():
                values.add(str(value))
        return sorted(list(values))
    
    return {
        'estados': get_unique_values('estado'),
        'anos': get_unique_values('ano'),
        'comunas': get_unique_values('comuna_corregimiento'),
        'fuentes_financiacion': get_unique_values('fuente_financiacion'),
        'tipos_intervencion': get_unique_values('tipo_intervencion'),
        'centros_gestores': get_unique_values('centro_gestor')
    }

# ============================================================================
# FUNCIONES DE BÚSQUEDA Y FILTRADO AVANZADO
# ============================================================================

def search_unidades(
    unidades: List[Dict[str, Any]], 
    query: str,
    fields: Optional[List[str]] = None
) -> List[Dict[str, Any]]:
    """
    Búsqueda de texto libre optimizada para frontend
    
    Args:
        unidades: Lista de unidades
        query: Texto de búsqueda
        fields: Campos específicos donde buscar (opcional)
    
    Returns:
        Lista filtrada de unidades que coinciden
    """
    if not query or not query.strip():
        return unidades
    
    query_lower = query.lower().strip()
    
    # Campos por defecto donde buscar
    if fields is None:
        fields = ['upid', 'bpin', 'nombre', 'comuna_corregimiento', 'barrio_vereda']
    
    def matches_query(unidad: Dict[str, Any]) -> bool:
        for field in fields:
            value = unidad.get(field, '')
            if value and query_lower in str(value).lower():
                return True
        return False
    
    return [u for u in unidades if matches_query(u)]

def apply_filters(
    unidades: List[Dict[str, Any]],
    filters: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """
    Aplicar filtros múltiples de forma eficiente
    
    Args:
        unidades: Lista de unidades
        filters: Dict con filtros a aplicar
    
    Returns:
        Lista filtrada
    """
    if not filters:
        return unidades
    
    def passes_filters(unidad: Dict[str, Any]) -> bool:
        for field, value in filters.items():
            if value is None or value == '':
                continue
                
            unidad_value = unidad.get(field)
            
            # Filtro exacto para la mayoría de campos
            if isinstance(value, str) and unidad_value != value:
                return False
            elif isinstance(value, list) and unidad_value not in value:
                return False
                
        return True
    
    return [u for u in unidades if passes_filters(u)]

# ============================================================================
# UTILIDADES DE EXPORTACIÓN
# ============================================================================

def prepare_for_export(unidades: List[Dict[str, Any]], format_type: str = "csv") -> Any:
    """
    Preparar datos para exportación en diferentes formatos
    
    Args:
        unidades: Lista de unidades
        format_type: Tipo de formato ("csv", "json", "geojson")
    
    Returns:
        Datos formateados según el tipo solicitado
    """
    if format_type == "geojson":
        return {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "properties": {k: v for k, v in unidad.items() if k not in ['coordenadas', 'tiene_coordenadas']},
                    "geometry": {
                        "type": "Point",
                        "coordinates": [
                            unidad['coordenadas']['longitude'],
                            unidad['coordenadas']['latitude']
                        ]
                    } if unidad.get('coordenadas') else None
                }
                for unidad in unidades
            ]
        }
    
    elif format_type == "json":
        return {
            "data": unidades,
            "metadata": {
                "total": len(unidades),
                "exported_at": "2025-09-27T00:00:00Z",
                "fields": list(unidades[0].keys()) if unidades else []
            }
        }
    
    else:  # CSV por defecto
        if not unidades:
            return []
        
        # Aplanar completamente para CSV
        flattened = []
        for unidad in unidades:
            row = unidad.copy()
            if row.get('coordenadas'):
                row['latitude'] = row['coordenadas']['latitude']
                row['longitude'] = row['coordenadas']['longitude']
            row.pop('coordenadas', None)
            row.pop('tiene_coordenadas', None)
            flattened.append(row)
        
        return flattened

# ============================================================================
# FUNCIÓN PRINCIPAL DE INTEGRACIÓN
# ============================================================================

def transform_api_response(
    api_data: List[Dict[str, Any]], 
    include_charts: bool = True,
    include_filters: bool = True
) -> Dict[str, Any]:
    """
    Transformar respuesta completa de la API para uso fácil en NextJS
    
    Args:
        api_data: Datos de la API
        include_charts: Incluir datos para gráficos
        include_filters: Incluir opciones de filtros
    
    Returns:
        Dict con datos transformados y utilidades para frontend
    """
    # Normalizar datos
    normalized = normalize_for_frontend(api_data)
    
    result = {
        'unidades': normalized,
        'total': len(normalized),
        'completeness_stats': {
            'high': len([u for u in normalized if u['completitud'] >= 80]),
            'medium': len([u for u in normalized if 50 <= u['completitud'] < 80]),
            'low': len([u for u in normalized if u['completitud'] < 50])
        },
        'geographic_coverage': len([u for u in normalized if u['tiene_coordenadas']])
    }
    
    if include_charts:
        result['charts'] = group_for_charts(normalized)
    
    if include_filters:
        result['filter_options'] = get_filter_options(normalized)
    
    return result
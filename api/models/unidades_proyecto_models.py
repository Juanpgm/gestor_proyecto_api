"""
Modelos de datos para la colección 'unidades_proyecto' en Firebase
Esquema completo para gestionar unidades de proyecto con información geográfica
Incluye soporte para múltiples intervenciones por unidad
"""

from typing import Optional, Dict, Any, List, Union
from datetime import datetime
from pydantic import BaseModel, Field, validator
import re


class GeometryPoint(BaseModel):
    """Modelo para geometría tipo Point (GeoJSON)"""
    type: str = Field(default="Point", description="Tipo de geometría GeoJSON")
    coordinates: List[float] = Field(..., description="Coordenadas [lng, lat] o [lng, lat, elevation]")
    
    @validator('type')
    def validate_type(cls, v):
        if v != "Point":
            raise ValueError("El tipo debe ser 'Point'")
        return v
    
    @validator('coordinates')
    def validate_coordinates(cls, v):
        if not isinstance(v, list) or len(v) < 2:
            raise ValueError("Coordenadas deben tener al menos [lng, lat]")
        # Validar rango de coordenadas
        lng, lat = v[0], v[1]
        if not (-180 <= lng <= 180):
            raise ValueError(f"Longitud {lng} fuera de rango [-180, 180]")
        if not (-90 <= lat <= 90):
            raise ValueError(f"Latitud {lat} fuera de rango [-90, 90]")
        return v


class GeometryLineString(BaseModel):
    """Modelo para geometría tipo LineString (GeoJSON)"""
    type: str = Field(default="LineString", description="Tipo de geometría GeoJSON")
    coordinates: List[List[float]] = Field(..., description="Array de coordenadas [[lng, lat], ...]")
    
    @validator('type')
    def validate_type(cls, v):
        if v != "LineString":
            raise ValueError("El tipo debe ser 'LineString'")
        return v
    
    @validator('coordinates')
    def validate_coordinates(cls, v):
        if not isinstance(v, list) or len(v) < 2:
            raise ValueError("LineString debe tener al menos 2 puntos")
        for coord in v:
            if not isinstance(coord, list) or len(coord) < 2:
                raise ValueError("Cada punto debe tener [lng, lat]")
        return v


class GeometryPolygon(BaseModel):
    """Modelo para geometría tipo Polygon (GeoJSON)"""
    type: str = Field(default="Polygon", description="Tipo de geometría GeoJSON")
    coordinates: List[List[List[float]]] = Field(..., description="Array de anillos de coordenadas")
    
    @validator('type')
    def validate_type(cls, v):
        if v != "Polygon":
            raise ValueError("El tipo debe ser 'Polygon'")
        return v


class GeometryMultiLineString(BaseModel):
    """Modelo para geometría tipo MultiLineString (GeoJSON)"""
    type: str = Field(default="MultiLineString", description="Tipo de geometría GeoJSON")
    coordinates: List[List[List[float]]] = Field(..., description="Array de LineStrings")
    
    @validator('type')
    def validate_type(cls, v):
        if v != "MultiLineString":
            raise ValueError("El tipo debe ser 'MultiLineString'")
        return v


class Intervencion(BaseModel):
    """
    Modelo para una intervención dentro de una unidad de proyecto
    Representa una actividad o proyecto específico en una ubicación
    """
    # Identificador único de la intervención
    intervencion_id: str = Field(..., description="ID único de la intervención (generado o desde datos)")
    
    # Información temporal
    ano: Optional[int] = Field(None, description="Año de la intervención")
    fecha_inicio: Optional[str] = Field(None, description="Fecha de inicio")
    fecha_fin: Optional[str] = Field(None, description="Fecha de finalización")
    
    # Estado y clasificación
    estado: Optional[str] = Field(None, description="Estado: En ejecución, Terminado, etc.")
    tipo_intervencion: Optional[str] = Field(None, description="Tipo de intervención")
    frente_activo: Optional[str] = Field(None, description="Estado del frente: Frente activo, Inactivo, No aplica")
    
    # Información financiera
    presupuesto_base: Optional[float] = Field(None, description="Presupuesto base de la intervención")
    fuente_financiacion: Optional[str] = Field(None, description="Fuente de financiación")
    
    # Progreso
    avance_obra: Optional[float] = Field(None, description="Porcentaje de avance (0-100)")
    cantidad: Optional[int] = Field(None, description="Cantidad o volumen de obra")
    
    # Referencias
    bpin: Optional[str] = Field(None, description="Código BPIN")
    referencia_contrato: Optional[str] = Field(None, description="Referencia del contrato")
    referencia_proceso: Optional[str] = Field(None, description="Referencia del proceso")
    url_proceso: Optional[str] = Field(None, description="URL del proceso en SECOP")
    
    # Descripción
    descripcion_intervencion: Optional[str] = Field(None, description="Descripción de la intervención")
    
    class Config:
        extra = "allow"
        schema_extra = {
            "example": {
                "intervencion_id": "UNP-1978-0",
                "ano": 2024,
                "estado": "Terminado",
                "tipo_intervencion": "Obras",
                "presupuesto_base": 55041504.84,
                "avance_obra": 100.0,
                "frente_activo": "Frente activo",
                "fuente_financiacion": "Recursos Propios",
                "fecha_inicio": "2024-01-15T00:00:00",
                "fecha_fin": "2024-12-31T00:00:00"
            }
        }


class UnidadProyectoConIntervenciones(BaseModel):
    """
    Modelo para unidad de proyecto con array de intervenciones
    Nueva estructura que agrupa múltiples intervenciones por ubicación
    """
    # Identificadores
    upid: str = Field(..., description="ID único de la unidad de proyecto")
    
    # Información básica de la unidad
    nombre_up: Optional[str] = Field(None, description="Nombre de la unidad de proyecto")
    nombre_up_detalle: Optional[str] = Field(None, description="Detalle adicional del nombre")
    
    # Ubicación
    direccion: Optional[str] = Field(None, description="Dirección física")
    barrio_vereda: Optional[str] = Field(None, description="Barrio o vereda")
    comuna_corregimiento: Optional[str] = Field(None, description="Comuna o corregimiento")
    departamento: Optional[str] = Field(None, description="Departamento")
    municipio: Optional[str] = Field(None, description="Municipio")
    
    # Clasificación
    tipo_equipamiento: Optional[str] = Field(None, description="Tipo de equipamiento")
    clase_up: Optional[str] = Field(None, description="Clase de la unidad de proyecto")
    
    # Gestión
    nombre_centro_gestor: Optional[str] = Field(None, description="Centro gestor responsable")
    identificador: Optional[str] = Field(None, description="Identificador tipo")
    
    # Intervenciones
    n_intervenciones: int = Field(default=0, description="Número de intervenciones en esta unidad")
    intervenciones: List[Intervencion] = Field(default=[], description="Array de intervenciones")
    
    # Metadatos geométricos (sin la geometría en sí)
    geometry_type: Optional[str] = Field(None, description="Tipo de geometría")
    has_geometry: bool = Field(False, description="Indica si tiene geometría válida")
    has_valid_geometry: bool = Field(False, description="Indica si las coordenadas son reales")
    
    class Config:
        extra = "allow"
        schema_extra = {
            "example": {
                "upid": "UNP-1978",
                "nombre_up": "Carrera 118 Entre Calle 15 Y 16",
                "direccion": "Carrera 118 Entre Calle 15 Y 16",
                "barrio_vereda": "Parcelaciones Pance",
                "comuna_corregimiento": "PANCE",
                "tipo_equipamiento": "Vias",
                "clase_up": "Obra Vial",
                "nombre_centro_gestor": "Secretaría de Infraestructura",
                "n_intervenciones": 1,
                "intervenciones": [
                    {
                        "intervencion_id": "UNP-1978-0",
                        "ano": 2024,
                        "estado": "Terminado",
                        "presupuesto_base": 55041504.84,
                        "avance_obra": 100.0
                    }
                ]
            }
        }


class UnidadProyectoProperties(BaseModel):
    """
    Properties/Atributos de una Unidad de Proyecto
    Basado en la estructura del GeoJSON y Firebase existente
    """
    # Identificadores
    upid: str = Field(..., description="ID único de la unidad de proyecto (UUID o similar)")
    bpin: Optional[str] = Field(None, description="Código BPIN del proyecto (puede tener prefijo '-')")
    
    # Información básica
    nombre_up: Optional[str] = Field(None, description="Nombre de la unidad de proyecto")
    nombre_up_detalle: Optional[str] = Field(None, description="Detalle adicional del nombre")
    descripcion_intervencion: Optional[str] = Field(None, description="Descripción de la intervención")
    
    # Clasificación
    estado: Optional[str] = Field(None, description="Estado del proyecto: Finalizado, En Ejecución, etc.")
    tipo_intervencion: Optional[str] = Field(None, description="Tipo de intervención del proyecto")
    clase_up: Optional[str] = Field(None, description="Clasificación de la unidad de proyecto: Obra Vial, etc.")
    tipo_equipamiento: Optional[str] = Field(None, description="Tipo de equipamiento del proyecto")
    identificador: Optional[str] = Field(None, description="Identificador del tipo: Grupo Operativo, etc.")
    
    # Ubicación
    direccion: Optional[str] = Field(None, description="Dirección física del proyecto")
    departamento: Optional[str] = Field(None, description="Departamento")
    municipio: Optional[str] = Field(None, description="Municipio")
    comuna_corregimiento: Optional[str] = Field(None, description="Comuna o corregimiento")
    barrio_vereda: Optional[str] = Field(None, description="Barrio o vereda")
    
    # Información financiera
    presupuesto_base: Optional[float] = Field(None, description="Presupuesto base del proyecto")
    fuente_financiacion: Optional[str] = Field(None, description="Fuente de financiación")
    
    # Información de ejecución
    avance_obra: Optional[float] = Field(None, description="Porcentaje de avance de la obra (0-100)")
    cantidad: Optional[int] = Field(None, description="Cantidad o volumen de obra")
    
    # Fechas
    ano: Optional[str] = Field(None, description="Año del proyecto")
    fecha_inicio: Optional[str] = Field(None, description="Fecha de inicio (formato ISO o string)")
    fecha_fin: Optional[str] = Field(None, description="Fecha de finalización")
    
    # Gestión
    nombre_centro_gestor: Optional[str] = Field(None, description="Centro gestor del proyecto")
    referencia_contrato: Optional[str] = Field(None, description="Referencia del contrato")
    referencia_proceso: Optional[str] = Field(None, description="Referencia del proceso")
    
    # Metadatos geométricos
    geometry_type: Optional[str] = Field(None, description="Tipo de geometría: Point, LineString, etc.")
    has_geometry: bool = Field(False, description="Indica si tiene geometría válida")
    has_valid_geometry: bool = Field(False, description="Indica si las coordenadas son reales (no [0,0])")
    centros_gravedad: bool = Field(False, description="Indica si es centro de gravedad")
    geometry_bounds: Optional[Dict[str, Any]] = Field(None, description="Bounding box de la geometría")
    
    # Campos adicionales
    plataforma: Optional[str] = Field(None, description="Plataforma o sistema de origen")
    microtio: Optional[str] = Field(None, description="Campo microtio")
    
    # Timestamps
    created_at: Optional[str] = Field(None, description="Fecha de creación del registro")
    processed_timestamp: Optional[str] = Field(None, description="Timestamp de procesamiento")
    
    class Config:
        extra = "allow"  # Permitir campos adicionales
        
    @validator('presupuesto_base', pre=True)
    def parse_presupuesto(cls, v):
        """Convertir presupuesto a float, manejando strings con formato"""
        if v is None or v == '' or str(v).strip() in ['null', 'None', 'nan', 'NaN']:
            return None
        try:
            if isinstance(v, str):
                # Remover formato de moneda
                cleaned = v.strip().replace(',', '').replace('$', '').replace(' ', '')
                return float(cleaned) if cleaned else None
            return float(v)
        except (ValueError, TypeError):
            return None
    
    @validator('avance_obra', pre=True)
    def parse_avance(cls, v):
        """Convertir avance a float (porcentaje)"""
        if v is None or v == '' or str(v).strip() in ['null', 'None', 'nan', 'NaN']:
            return None
        try:
            if isinstance(v, str):
                cleaned = v.strip().replace('%', '').replace(' ', '').replace(',', '.')
                return float(cleaned) if cleaned else None
            return float(v)
        except (ValueError, TypeError):
            return None
    
    @validator('bpin', pre=True)
    def parse_bpin(cls, v):
        """Limpiar BPIN eliminando prefijos y caracteres especiales"""
        if v is None or v == '' or str(v).strip() in ['null', 'None', 'nan', 'NaN']:
            return None
        try:
            cleaned = str(v).strip()
            # Eliminar prefijo '-' si existe
            if cleaned.startswith('-'):
                cleaned = cleaned[1:]
            # Eliminar caracteres no numéricos
            cleaned = re.sub(r'[^\d]', '', cleaned)
            return cleaned if cleaned else None
        except:
            return None
    
    @validator('cantidad', pre=True)
    def parse_cantidad(cls, v):
        """Convertir cantidad a int"""
        if v is None or v == '' or str(v).strip() in ['null', 'None', 'nan', 'NaN']:
            return None
        try:
            if isinstance(v, str):
                cleaned = v.strip().replace(',', '').replace(' ', '')
                return int(float(cleaned)) if cleaned else None
            return int(float(v))
        except (ValueError, TypeError):
            return None


class UnidadProyectoGeoJSON(BaseModel):
    """
    Modelo completo GeoJSON Feature para una Unidad de Proyecto
    Compatible con GeoJSON RFC 7946
    """
    type: str = Field(default="Feature", description="Tipo GeoJSON")
    geometry: Optional[Union[GeometryPoint, GeometryLineString, GeometryPolygon, GeometryMultiLineString, Dict]] = Field(
        None, description="Geometría GeoJSON (Point, LineString, Polygon, MultiLineString)"
    )
    properties: UnidadProyectoProperties = Field(..., description="Propiedades de la unidad de proyecto")
    
    @validator('type')
    def validate_type(cls, v):
        if v != "Feature":
            raise ValueError("El tipo debe ser 'Feature'")
        return v
    
    class Config:
        extra = "forbid"
        schema_extra = {
            "example": {
                "type": "Feature",
                "geometry": {
                    "type": "LineString",
                    "coordinates": [
                        [-76.52525386713229, 3.4121562648113843, 0.0],
                        [-76.52525185771958, 3.412174573663092, 0.0]
                    ]
                },
                "properties": {
                    "upid": "UP-2024-001",
                    "bpin": "2023760010180",
                    "nombre_up": "Calle 16 Entre Carrera 46A Y Carrera 39",
                    "estado": "Finalizado",
                    "clase_up": "Obra Vial",
                    "comuna_corregimiento": "COMUNA 10",
                    "barrio_vereda": "El Guabal",
                    "presupuesto_base": 63564349.18,
                    "avance_obra": 100.0,
                    "ano": "2024",
                    "nombre_centro_gestor": "Secretaría de Infraestructura",
                    "geometry_type": "LineString",
                    "has_geometry": True,
                    "has_valid_geometry": True
                }
            }
        }


class UnidadProyectoFirestore(BaseModel):
    """
    Modelo para almacenar en Firestore
    Estructura plana con geometría embebida
    """
    # ID del documento (upid)
    upid: str = Field(..., description="ID único (será el ID del documento en Firestore)")
    
    # Geometría (almacenada como dict)
    geometry: Optional[Dict[str, Any]] = Field(None, description="Geometría GeoJSON serializada")
    geometry_type: Optional[str] = Field(None, description="Tipo de geometría")
    has_geometry: bool = Field(False, description="Indica si tiene geometría")
    has_valid_geometry: bool = Field(False, description="Indica si las coordenadas son válidas")
    
    # Todos los campos de properties en el nivel raíz
    bpin: Optional[str] = None
    nombre_up: Optional[str] = None
    nombre_up_detalle: Optional[str] = None
    descripcion_intervencion: Optional[str] = None
    estado: Optional[str] = None
    tipo_intervencion: Optional[str] = None
    clase_up: Optional[str] = None
    tipo_equipamiento: Optional[str] = None
    identificador: Optional[str] = None
    direccion: Optional[str] = None
    departamento: Optional[str] = None
    municipio: Optional[str] = None
    comuna_corregimiento: Optional[str] = None
    barrio_vereda: Optional[str] = None
    presupuesto_base: Optional[float] = None
    fuente_financiacion: Optional[str] = None
    avance_obra: Optional[float] = None
    cantidad: Optional[int] = None
    ano: Optional[str] = None
    fecha_inicio: Optional[str] = None
    fecha_fin: Optional[str] = None
    nombre_centro_gestor: Optional[str] = None
    referencia_contrato: Optional[str] = None
    referencia_proceso: Optional[str] = None
    centros_gravedad: bool = False
    geometry_bounds: Optional[Dict[str, Any]] = None
    plataforma: Optional[str] = None
    microtio: Optional[str] = None
    created_at: Optional[str] = None
    processed_timestamp: Optional[str] = None
    
    # Timestamp de actualización
    updated_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    
    def to_firestore_dict(self) -> Dict[str, Any]:
        """Convertir a diccionario para Firestore, excluyendo valores None"""
        import json
        
        # Obtener datos excluyendo None y upid
        data = self.dict(exclude_none=True, exclude={'upid'})
        
        # Serializar geometría como JSON string para Firestore
        # Firestore no acepta objetos anidados complejos con listas de coordenadas
        if 'geometry' in data and data['geometry'] is not None:
            data['geometry'] = json.dumps(data['geometry'])
        
        return data
    
    @classmethod
    def from_geojson_feature(cls, feature: Dict[str, Any], upid: Optional[str] = None):
        """
        Crear instancia desde un GeoJSON Feature
        
        Args:
            feature: Dict con estructura GeoJSON Feature
            upid: ID único opcional (se genera si no se proporciona)
        """
        import uuid
        
        properties = feature.get('properties', {})
        geometry = feature.get('geometry')
        
        # Generar upid si no existe
        if not upid:
            upid = properties.get('upid') or f"UP-{uuid.uuid4().hex[:12]}"
        
        # Detectar tipo de geometría y validez
        geometry_type = None
        has_geometry = False
        has_valid_geometry = False
        
        if geometry:
            geometry_type = geometry.get('type')
            has_geometry = True
            
            # Validar si tiene coordenadas reales (no [0,0])
            coords = geometry.get('coordinates', [])
            if coords:
                if geometry_type == 'Point':
                    has_valid_geometry = not (coords[0] == 0 and coords[1] == 0)
                elif geometry_type in ['LineString', 'MultiLineString', 'Polygon']:
                    has_valid_geometry = True  # Asumimos que multi-coord son válidas
        
        return cls(
            upid=upid,
            geometry=geometry,
            geometry_type=geometry_type,
            has_geometry=has_geometry,
            has_valid_geometry=has_valid_geometry,
            **properties
        )
    
    class Config:
        extra = "allow"  # Permitir campos adicionales del GeoJSON


class UnidadProyectoCollectionResponse(BaseModel):
    """Respuesta de la colección de unidades de proyecto"""
    type: str = Field(default="FeatureCollection", description="Tipo GeoJSON")
    features: List[UnidadProyectoGeoJSON] = Field(default=[], description="Lista de features")
    properties: Dict[str, Any] = Field(
        default={},
        description="Metadata de la colección"
    )
    
    @validator('type')
    def validate_type(cls, v):
        if v != "FeatureCollection":
            raise ValueError("El tipo debe ser 'FeatureCollection'")
        return v

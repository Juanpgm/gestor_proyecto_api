"""
Catálogo canónico de Centros Gestores.

Única fuente de verdad de los nombres oficiales de centro gestor. Se usa para:
  - validar el centro_gestor en el registro de usuarios,
  - normalizar/canonicalizar valores existentes (usuarios y registros de dominio),
  - servir el picklist del frontend (en vez de derivarlo de datos sucios).

Regla de comparación: normalización NFD (sin tildes) + lower + espacios colapsados.
Debe mantenerse en paralelo con la versión TS del frontend
(``front/src/utils/centrosCatalog.ts``).
"""

from __future__ import annotations

import re
import unicodedata
from typing import Dict, List, Optional

# ---------------------------------------------------------------------------
# Catálogo oficial (canónico). Fuente: front/public/data/ejecucion_presupuestal/
# centro_gestor.json. Cambios aquí deben replicarse en el frontend.
# ---------------------------------------------------------------------------
CENTROS_GESTORES: List[str] = [
    # Núcleo con datos de ejecución (centro_gestor.json).
    "Secretaría de Gobierno",
    "Departamento Administrativo de Gestión Jurídica Pública",
    "Departamento Administrativo de Control Interno",
    "Departamento Administrativo de Control Disciplinario Interno",
    "Departamento Administrativo de Hacienda",
    "Departamento Administrativo de Planeación Municipal",
    "Departamento Administrativo de Gestión del Medio Ambiente - DAGMA",
    "Secretaría de Salud Pública",
    "Secretaría de Cultura",
    "Secretaría de Seguridad y Justicia",
    "Secretaría de Bienestar Social",
    "Departamento Administrativo de Desarrollo e Innovación Institucional",
    "Secretaría de Desarrollo Económico",
    "Unidad Administrativa Especial de Servicios Públicos",
    "Secretaría del Deporte y la Recreación",
    "Secretaría de Infraestructura",
    "Secretaría de Desarrollo Territorial y Participación Ciudadana",
    "Secretaría de Educación",
    "Secretaría de Gestión del Riesgo de Emergencias y Desastres",
    # Centros adicionales ofrecidos en el registro (no aparecen en datos de
    # ejecución todavía pero son centros válidos de la Alcaldía). Unión para no
    # rechazar usuarios legítimos. Revisar contra el catálogo oficial definitivo.
    "Departamento Administrativo de Tecnologías de la Información y las Comunicaciones",
    "Departamento Administrativo de Contratación Pública",
    "Secretaría de Vivienda Social y Hábitat",
    "Secretaría de Movilidad",
    "Secretaría de Paz y Cultura Ciudadana",
    "Secretaría de Turismo",
    "Unidad Administrativa Especial de Gestión de Bienes y Servicios",
]

# Centros INTERNOS especiales: NO seleccionables en el registro (no están en
# CENTROS_GESTORES, así que no aparecen en el picklist), pero válidos y con
# VISIBILIDAD GLOBAL (equipo administrador). Excepción interna deliberada.
INTERNAL_GLOBAL_CENTROS: List[str] = [
    "Calitrack",
]


def normalize_centro(value: object) -> str:
    """Forma normalizada para comparación: sin tildes, minúsculas, espacios colapsados."""
    text = str(value or "")
    text = unicodedata.normalize("NFD", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    text = text.strip().lower()
    text = re.sub(r"\s+", " ", text)
    return text


# Mapa normalizado -> nombre canónico. Cubre el catálogo + alias conocidos
# (variantes históricas, abreviaturas y spellings divergentes detectados en
# el frontend legacy OPEN_ACCESS_CENTROS y en datos reales).
_CANON_BY_NORMALIZED: Dict[str, str] = {
    normalize_centro(name): name
    for name in (*CENTROS_GESTORES, *INTERNAL_GLOBAL_CENTROS)
}

# Normalizados de los centros internos con visibilidad global.
_INTERNAL_GLOBAL_NORMALIZED = {normalize_centro(n) for n in INTERNAL_GLOBAL_CENTROS}

# Alias conocidos (normalizado_variante -> nombre canónico). Extender con lo que
# arroje el script de auditoría sobre los datos reales antes de normalizar en prod.
_ALIASES_RAW: Dict[str, str] = {
    # Planeación (legacy sin "Municipal")
    "departamento administrativo de planeacion": "Departamento Administrativo de Planeación Municipal",
    "departamento administrativo de planeacion municipal": "Departamento Administrativo de Planeación Municipal",
    # DAGMA (con y sin sufijo)
    "departamento administrativo de gestion del medio ambiente": "Departamento Administrativo de Gestión del Medio Ambiente - DAGMA",
    "dagma": "Departamento Administrativo de Gestión del Medio Ambiente - DAGMA",
    # Control Disciplinario (legacy con "de Instrucción")
    "departamento administrativo de control disciplinario interno de instruccion": "Departamento Administrativo de Control Disciplinario Interno",
    # Gestión del Riesgo / DAGRD
    "dagrd": "Secretaría de Gestión del Riesgo de Emergencias y Desastres",
    "dagrd - departamento administrativo de gestion del riesgo": "Secretaría de Gestión del Riesgo de Emergencias y Desastres",
    "departamento administrativo de gestion del riesgo": "Secretaría de Gestión del Riesgo de Emergencias y Desastres",
    "departamento administrativo de gestion del riesgo de emergencias y desastres": "Secretaría de Gestión del Riesgo de Emergencias y Desastres",
    # DATIC (acrónimo de Tecnologías de la Información y las Comunicaciones)
    "datic": "Departamento Administrativo de Tecnologías de la Información y las Comunicaciones",
}

_ALIASES: Dict[str, str] = {
    normalize_centro(variant): canonical for variant, canonical in _ALIASES_RAW.items()
}


def canonicalize_centro(value: object) -> Optional[str]:
    """Devuelve el nombre canónico del centro, o ``None`` si no se reconoce.

    Reconoce: coincidencia exacta (normalizada) con el catálogo y alias conocidos.
    """
    key = normalize_centro(value)
    if not key:
        return None
    if key in _CANON_BY_NORMALIZED:
        return _CANON_BY_NORMALIZED[key]
    return _ALIASES.get(key)


def is_valid_centro(value: object) -> bool:
    """True si el valor puede mapearse a un centro gestor del catálogo."""
    return canonicalize_centro(value) is not None


def is_global_view_centro(value: object) -> bool:
    """True si el centro es interno y otorga visibilidad global (p.ej. ``Calitrack``)."""
    return normalize_centro(value) in _INTERNAL_GLOBAL_NORMALIZED

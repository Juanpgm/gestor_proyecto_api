"""
Primitiva ÚNICA de filtrado de records por centro_gestor.

Toda comparación de un record contra un centro gestor debe pasar por aquí. La
comparación es normalizada (sin tildes, minúsculas, espacios colapsados) vía
``centros_catalog.normalize_centro`` — la misma regla del catálogo canónico.

Antes existían tres reglas de comparación divergentes (control de acceso con
``!=`` crudo, filtrado de datos normalizado, query Firestore exacto). Esta
función centraliza el filtrado de records para que ningún router reimplemente
la comparación y diverja de nuevo.
"""

from __future__ import annotations

import logging
from typing import Any, List, Optional

from auth_system.centros_catalog import canonicalize_centro, normalize_centro

logger = logging.getLogger(__name__)

# Campos donde un record puede llevar su centro gestor, en orden de prioridad.
# Espeja la convención del backend (``nombre_centro_gestor`` primario,
# ``centro_gestor`` fallback legacy).
_CENTRO_FIELDS = ("nombre_centro_gestor", "centro_gestor")


def _match_key(value: Any) -> str:
    """Clave de comparación CANÓNICA: mapea forma corta/alias al canónico y luego
    normaliza. Si el valor no es un centro reconocible, cae a la normalización
    simple. Espeja ``centroMatchKey`` del frontend (centroGestorAccess.ts)."""
    return normalize_centro(canonicalize_centro(value) or value)


def same_centro(a: Any, b: Any) -> bool:
    """True si ``a`` y ``b`` refieren al mismo centro gestor (comparación canónica).

    Primitiva escalar para comparar dos valores de centro (p.ej. ruteo de
    notificaciones, métricas filtradas). Equivalente a la usada para filtrar
    listas: forma corta/alias/tilde del mismo centro se consideran iguales.
    """
    return _match_key(a) == _match_key(b)


def _record_centro(row: dict) -> Optional[Any]:
    """Devuelve el primer valor de centro presente en el record (sin normalizar)."""
    for field in _CENTRO_FIELDS:
        val = row.get(field)
        if val:
            return val
    return None


def scope_records_by_centro(
    data: List[Any], centro: Optional[str], *, log_label: Optional[str] = None
) -> List[Any]:
    """Filtra una lista de dicts al ``centro`` efectivo.

    - ``centro`` falsy (None / "") → sin filtro (caso global): devuelve ``data``.
    - Compara la forma normalizada del centro del record contra la del ``centro``.
    - Los elementos que no son dict se preservan tal cual.

    Observabilidad: si el filtro descarta TODOS los records de una lista no
    vacía, loguea ``warning`` — señal típica de un string de centro no canónico
    (datos sucios) que dejaría al usuario sin ver nada en silencio.
    """
    if not centro or not isinstance(data, list):
        return data
    target = _match_key(centro)
    out: List[Any] = []
    for row in data:
        if not isinstance(row, dict):
            out.append(row)
            continue
        if _match_key(_record_centro(row)) == target:
            out.append(row)
    if data and not out:
        logger.warning(
            "scope_records_by_centro descartó los %d records para centro=%r "
            "(label=%s): posible mismatch por string no canónico en los datos",
            len(data),
            centro,
            log_label or "?",
        )
    return out

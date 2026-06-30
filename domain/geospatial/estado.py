"""Pure derivation rules for the ephemeral `estado` and `frente_activo`.

Port of the legacy logic in ``api/scripts/unidades_proyecto.py``
(``_calcular_estado`` / ``_clasificar_frente_activo``). These functions are
side-effect free and take primitives, so the same rule can be exercised by:

* the Firestore adapter (which has no SQL),
* the Postgres adapter (whose SQL ``calcular_estado`` mirrors this), and
* contract tests asserting all three agree.

Contract (must match the SQL function and front/src/utils/estadoUP.ts):
    avance < 0.5 (or None / non-numeric) -> "En alistamiento"
    avance >= 99.5                       -> "Terminado"
    otherwise                            -> "En ejecución"
A stored estado is honoured only when it is a manual whitelist value
("Suspendido" / "Inaugurado"), case/accent-insensitive, and returned verbatim.
"""

from __future__ import annotations

import unicodedata
from typing import Any, Mapping, Optional

# Avance (%) below which an intervención is considered "En alistamiento".
AVANCE_MIN_EN_EJECUCION = 0.5
# Avance (%) at/above which an intervención is considered "Terminado".
AVANCE_MAX_EN_EJECUCION = 99.5
# Manually-imputed estados that are respected verbatim (normalized whitelist).
ESTADOS_MANUALES_NORM = frozenset({"suspendido", "inaugurado"})

ESTADO_EN_ALISTAMIENTO = "En alistamiento"
ESTADO_EN_EJECUCION = "En ejecución"
ESTADO_TERMINADO = "Terminado"

# Frente activo classification.
PRESUPUESTO_MINIMO_FRENTE = 100_000_000
_TIPOS_EQUIPAMIENTO_EXCLUIDOS = frozenset(
    {"Vivienda mejoramiento", "Vivienda nueva", "Adquisición de predios", "Señalización vial"}
)
_TIPOS_INTERVENCION_EXCLUIDOS = frozenset(
    {"Mantenimiento", "Estudios y diseños", "Transferencia directa"}
)
_CLASES_VALIDAS = frozenset({"Obras equipamientos", "Obra vial", "Obra Vial"})
_CLASES_SUBSIDIO = frozenset({"Subsidios"})


def normalizar_estado(texto: str) -> str:
    """Fold accents, trim and lowercase an estado string for comparison."""
    sin_acentos = "".join(
        c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn"
    )
    return sin_acentos.strip().lower()


def convert_to_float(value: Any) -> Optional[float]:
    """Best-effort float coercion mirroring legacy ``_convert_to_float``.

    Handles European decimals ("50,75"), thousand separators, "%", whitespace
    and the null-ish sentinels. Returns ``None`` when the value is not numeric.
    """
    if value is None or value == "" or str(value).strip() in {"null", "None", "nan", "NaN"}:
        return None
    try:
        if isinstance(value, str):
            cleaned = value.strip().replace("%", "").replace(" ", "")
            if "," in cleaned and cleaned.count(",") == 1:
                comma_pos = cleaned.find(",")
                # Comma within the last 3 chars -> decimal separator; else thousands.
                if len(cleaned) - comma_pos <= 3:
                    cleaned = cleaned.replace(",", ".")
                else:
                    cleaned = cleaned.replace(",", "")
            else:
                cleaned = cleaned.replace(",", "")
            if cleaned:
                return float(cleaned)
            return None
        return float(value)
    except (ValueError, TypeError):
        return None


def calcular_estado(avance_obra: Any, estado_manual: Any = None) -> str:
    """Derive the ephemeral estado from avance, honouring the manual whitelist."""
    if estado_manual:
        estado_str = str(estado_manual).strip()
        if normalizar_estado(estado_str) in ESTADOS_MANUALES_NORM:
            return estado_str

    avance = convert_to_float(avance_obra)
    if avance is None or avance < AVANCE_MIN_EN_EJECUCION:
        return ESTADO_EN_ALISTAMIENTO
    if avance >= AVANCE_MAX_EN_EJECUCION:
        return ESTADO_TERMINADO
    return ESTADO_EN_EJECUCION


def clasificar_frente_activo(
    intervencion: Mapping[str, Any], unidad_props: Mapping[str, Any]
) -> str:
    """Classify whether an intervención is a relevant civil-works active front.

    Mirrors legacy ``_clasificar_frente_activo``: excludes subsidios, low budget,
    non-relevant equipment/intervention types and non-civil-works classes.
    """
    clase_up = unidad_props.get("clase_up")
    tipo_equipamiento = unidad_props.get("tipo_equipamiento")
    tipo_intervencion = intervencion.get("tipo_intervencion")

    estado = calcular_estado(intervencion.get("avance_obra"), intervencion.get("estado"))

    if clase_up and clase_up in _CLASES_SUBSIDIO:
        return "No aplica"
    if tipo_intervencion and "subsidio" in str(tipo_intervencion).lower():
        return "No aplica"

    presupuesto = convert_to_float(intervencion.get("presupuesto_base"))
    if presupuesto is None or presupuesto < PRESUPUESTO_MINIMO_FRENTE:
        return "No aplica"

    condiciones_base = (
        clase_up in _CLASES_VALIDAS
        and tipo_equipamiento not in _TIPOS_EQUIPAMIENTO_EXCLUIDOS
        and tipo_intervencion not in _TIPOS_INTERVENCION_EXCLUIDOS
    )

    if estado == ESTADO_EN_EJECUCION and condiciones_base:
        return "Frente activo"
    if estado == "Suspendido" and condiciones_base:
        return "Inactivo"
    return "No aplica"

"""Consolidate a unidad de proyecto's intervenciones into UP-level fields.

A UP has many intervenciones; the map colours by UP, so we collapse them into
a single estado / avance_obra / tipo_intervencion / frente_activo. Pure and
DB-free. Mirrors the front's consolidation (unidades-proyecto.service.ts):

* avance_obra: presupuesto-weighted average (arithmetic mean when total = 0),
* estado: the shared estado if all agree, else "Varios estados",
* tipo_intervencion: the shared value, else "Varios",
* frente_activo: the highest-priority classification across intervenciones.
"""

from __future__ import annotations

from typing import Optional, Sequence

from domain.geospatial.entities import Intervencion, UnidadProyecto
from domain.geospatial.estado import clasificar_frente_activo, convert_to_float

_FRENTE_PRIORITY = {"Frente activo": 2, "Inactivo": 1, "No aplica": 0}


def consolidate_intervenciones(
    up: UnidadProyecto, intervenciones: Sequence[Intervencion]
) -> dict:
    """Return UP-level {estado, avance_obra, tipo_intervencion, frente_activo,
    num_intervenciones} from a UP and its intervenciones."""
    if not intervenciones:
        return {
            "estado": "Sin estado",
            "avance_obra": None,
            "tipo_intervencion": None,
            "frente_activo": "No aplica",
            "num_intervenciones": 0,
        }

    # Presupuesto-weighted average of avance.
    weighted_sum = 0.0
    total_pres = 0.0
    plain = []
    for i in intervenciones:
        av = convert_to_float(i.avance_obra) or 0.0
        pres = convert_to_float(i.presupuesto_base) or 0.0
        plain.append(av)
        weighted_sum += av * pres
        total_pres += pres
    avance: Optional[float] = (
        weighted_sum / total_pres if total_pres > 0 else (sum(plain) / len(plain))
    )

    estados = {i.estado for i in intervenciones}
    estado = next(iter(estados)) if len(estados) == 1 else "Varios estados"

    tipos = {i.tipo_intervencion for i in intervenciones if i.tipo_intervencion}
    if len(tipos) == 1:
        tipo = next(iter(tipos))
    elif len(tipos) > 1:
        tipo = "Varios"
    else:
        tipo = None

    up_props = {"clase_up": up.clase_up, "tipo_equipamiento": up.tipo_equipamiento}
    best_frente = "No aplica"
    for i in intervenciones:
        fa = clasificar_frente_activo(
            {
                "avance_obra": i.avance_obra,
                "presupuesto_base": i.presupuesto_base,
                "tipo_intervencion": i.tipo_intervencion,
                "estado": i.estado_manual,
            },
            up_props,
        )
        if _FRENTE_PRIORITY.get(fa, 0) > _FRENTE_PRIORITY.get(best_frente, 0):
            best_frente = fa

    return {
        "estado": estado,
        "avance_obra": round(avance, 2) if avance is not None else None,
        "tipo_intervencion": tipo,
        "frente_activo": best_frente,
        "num_intervenciones": len(intervenciones),
    }

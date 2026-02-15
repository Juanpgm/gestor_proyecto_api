"""
Metricas de calidad para unidades_proyecto e intervenciones_unidades_proyecto.
Calcula indicadores extendidos y cachea el resultado por 24 horas.
"""

from datetime import datetime, timezone
import uuid
from typing import Any, Dict, Optional

from database.firebase_config import get_firestore_client
from api.scripts.emprestito_cache import with_cache
from api.scripts.unidades_proyecto import _convert_to_float, _convert_to_int


REQUIRED_UNIDADES_FIELDS = [
    "upid",
    "nombre_up",
    "nombre_centro_gestor",
    "clase_up",
    "tipo_equipamiento",
    "comuna_corregimiento"
]

REQUIRED_INTERV_FIELDS = [
    "upid",
    "estado",
    "tipo_intervencion",
    "presupuesto_base",
    "avance_obra",
    "ano"
]


def _normalize_str(value: Any) -> Optional[str]:
    if value is None:
        return None
    value_str = str(value).strip()
    return value_str if value_str else None


def _is_valid_lat_lon(lat: Any, lon: Any) -> bool:
    if lat is None or lon is None:
        return False
    try:
        lat_val = float(lat)
        lon_val = float(lon)
    except (ValueError, TypeError):
        return False
    return 2.0 <= lat_val <= 5.0 and -78.0 <= lon_val <= -75.0


def _extract_geometry_flags(doc_data: Dict[str, Any]) -> Dict[str, bool]:
    props = doc_data.get("properties", {}) if isinstance(doc_data.get("properties"), dict) else {}
    geometry = doc_data.get("geometry") or props.get("geometry")
    coords = doc_data.get("coordinates") or props.get("coordinates")
    lat = doc_data.get("lat") or props.get("lat")
    lon = doc_data.get("lon") or doc_data.get("lng") or props.get("lon") or props.get("lng")

    has_geometry = geometry is not None or coords is not None or (lat is not None and lon is not None)
    has_valid_coordinates = _is_valid_lat_lon(lat, lon)

    if geometry and isinstance(geometry, dict):
        geom_coords = geometry.get("coordinates")
        if isinstance(geom_coords, (list, tuple)) and len(geom_coords) >= 2:
            if geom_coords[0] == 0 and geom_coords[1] == 0:
                has_valid_coordinates = False
    if coords and isinstance(coords, (list, tuple)) and len(coords) >= 2:
        if coords[0] == 0 and coords[1] == 0:
            has_valid_coordinates = False

    return {
        "has_geometry": bool(has_geometry),
        "has_valid_coordinates": bool(has_valid_coordinates)
    }


def _estado_vs_avance_inconsistente(estado: Any, avance: Any) -> bool:
    estado_val = _normalize_str(estado)
    if estado_val is None:
        return False
    avance_val = _convert_to_float(avance)
    if avance_val is None:
        return False

    if avance_val == 0 and estado_val != "En alistamiento":
        return True
    if avance_val >= 100 and estado_val != "Terminado":
        return True
    if 0 < avance_val < 100 and estado_val != "En ejecucion" and estado_val != "En ejecución":
        return True
    return False


def _update_missing_fields(doc_data: Dict[str, Any], required_fields: list, counters: Dict[str, int]) -> None:
    props = doc_data.get("properties", {}) if isinstance(doc_data.get("properties"), dict) else {}
    for field in required_fields:
        value = doc_data.get(field)
        if value is None and isinstance(props, dict):
            value = props.get(field)
        if _normalize_str(value) is None:
            counters[field] = counters.get(field, 0) + 1


def _save_quality_metrics(db, report: Dict[str, Any]) -> None:
    history_collection = db.collection("unidades_proyecto_quality_metrics_history")
    latest_collection = db.collection("unidades_proyecto_quality_metrics_latest")

    history_collection.add(report)
    latest_collection.document("latest").set(report)


@with_cache(ttl_seconds=86400)
async def get_unidades_proyecto_quality_metrics() -> Dict[str, Any]:
    """Calcula metricas de calidad extendidas para unidades e intervenciones."""
    db = get_firestore_client()
    if db is None:
        return {
            "success": False,
            "error": "No se pudo conectar a Firestore"
        }

    unidades_total = 0
    unidades_missing = {field: 0 for field in REQUIRED_UNIDADES_FIELDS}
    unidades_with_geometry = 0
    unidades_with_valid_geometry = 0
    unidades_with_fecha_inicio = 0
    unidades_with_fecha_fin = 0
    upid_set = set()
    duplicate_upids = 0

    unidades_query = db.collection("unidades_proyecto")
    for doc in unidades_query.stream():
        doc_data = doc.to_dict()
        unidades_total += 1

        props = doc_data.get("properties", {}) if isinstance(doc_data.get("properties"), dict) else {}
        upid = doc_data.get("upid") or props.get("upid")
        if upid:
            if upid in upid_set:
                duplicate_upids += 1
            upid_set.add(upid)

        _update_missing_fields(doc_data, REQUIRED_UNIDADES_FIELDS, unidades_missing)

        geometry_flags = _extract_geometry_flags(doc_data)
        if geometry_flags["has_geometry"]:
            unidades_with_geometry += 1
        if geometry_flags["has_valid_coordinates"]:
            unidades_with_valid_geometry += 1

        fecha_inicio = doc_data.get("fecha_inicio") or props.get("fecha_inicio")
        fecha_fin = doc_data.get("fecha_fin") or props.get("fecha_fin")
        if _normalize_str(fecha_inicio) is not None:
            unidades_with_fecha_inicio += 1
        if _normalize_str(fecha_fin) is not None:
            unidades_with_fecha_fin += 1

    interv_total = 0
    interv_missing = {field: 0 for field in REQUIRED_INTERV_FIELDS}
    interv_invalid_ranges = {
        "avance_obra": 0,
        "presupuesto_base": 0,
        "ano": 0
    }
    interv_estado_avance_inconsistente = 0
    interv_intervencion_id_dupes = 0
    intervencion_id_set = set()
    interv_orphans = 0
    intervenciones_por_upid = {}

    interv_query = db.collection("intervenciones_unidades_proyecto")
    for doc in interv_query.stream():
        doc_data = doc.to_dict()
        interv_total += 1

        _update_missing_fields(doc_data, REQUIRED_INTERV_FIELDS, interv_missing)

        intervencion_id = doc_data.get("intervencion_id") or doc.id
        if intervencion_id in intervencion_id_set:
            interv_intervencion_id_dupes += 1
        else:
            intervencion_id_set.add(intervencion_id)

        upid = doc_data.get("upid") or doc_data.get("properties", {}).get("upid")
        if not upid or upid not in upid_set:
            interv_orphans += 1
        else:
            intervenciones_por_upid[upid] = intervenciones_por_upid.get(upid, 0) + 1

        avance = _convert_to_float(doc_data.get("avance_obra"))
        if avance is not None and (avance < 0 or avance > 100):
            interv_invalid_ranges["avance_obra"] += 1

        presupuesto = _convert_to_float(doc_data.get("presupuesto_base"))
        if presupuesto is not None and presupuesto < 0:
            interv_invalid_ranges["presupuesto_base"] += 1

        ano = _convert_to_int(doc_data.get("ano"))
        if ano is not None and (ano < 2000 or ano > 2100):
            interv_invalid_ranges["ano"] += 1

        if _estado_vs_avance_inconsistente(doc_data.get("estado"), doc_data.get("avance_obra")):
            interv_estado_avance_inconsistente += 1

    unidades_sin_intervenciones = max(unidades_total - len(intervenciones_por_upid), 0)

    total_records = unidades_total + interv_total
    total_issues = (
        sum(unidades_missing.values()) +
        sum(interv_missing.values()) +
        sum(interv_invalid_ranges.values()) +
        duplicate_upids +
        interv_intervencion_id_dupes +
        interv_orphans +
        unidades_sin_intervenciones +
        (unidades_total - unidades_with_valid_geometry) +
        interv_estado_avance_inconsistente
    )

    quality_score = 100.0
    if total_records > 0:
        penalty_ratio = min(total_issues / total_records, 1)
        quality_score = round(max(0.0, (1 - penalty_ratio) * 100), 2)

    now_iso = datetime.now(timezone.utc).isoformat()
    report_id = f"{datetime.now(timezone.utc).strftime('%Y%m%d')}-{uuid.uuid4().hex[:8]}"

    result = {
        "success": True,
        "report_id": report_id,
        "generated_at": now_iso,
        "overall": {
            "total_records": total_records,
            "total_issues": total_issues,
            "quality_score": quality_score
        },
        "collections": {
            "unidades_proyecto": {
                "total": unidades_total,
                "missing_fields": unidades_missing,
                "geometry": {
                    "with_geometry": unidades_with_geometry,
                    "with_valid_coordinates": unidades_with_valid_geometry
                },
                "temporal": {
                    "with_fecha_inicio": unidades_with_fecha_inicio,
                    "with_fecha_fin": unidades_with_fecha_fin
                },
                "duplicates": {
                    "upid_duplicates": duplicate_upids
                },
                "unidades_sin_intervenciones": unidades_sin_intervenciones
            },
            "intervenciones_unidades_proyecto": {
                "total": interv_total,
                "missing_fields": interv_missing,
                "invalid_ranges": interv_invalid_ranges,
                "estado_vs_avance_inconsistente": interv_estado_avance_inconsistente,
                "duplicates": {
                    "intervencion_id_duplicates": interv_intervencion_id_dupes
                },
                "orphans": {
                    "intervenciones_sin_unidad": interv_orphans
                }
            }
        }
    }

    _save_quality_metrics(db, result)
    return result

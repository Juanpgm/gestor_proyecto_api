"""
Métricas de calidad para unidades_proyecto e intervenciones_unidades_proyecto.
Marco alineado con ISO 8000, ISO/IEC 25012 y DAMA-DMBOK.
"""

from datetime import datetime, timezone
import uuid
from typing import Any, Dict, List, Optional

from database.firebase_config import get_firestore_client
from api.scripts.emprestito_cache import with_cache
from api.scripts.unidades_proyecto import _convert_to_float


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
    "avance_obra"
]

SEVERITY_WEIGHTS = {
    "S1": 0.40,
    "S2": 0.30,
    "S3": 0.20,
    "S4": 0.10
}

SEVERITY_DESCRIPTIONS = {
    "S1": "Crítico",
    "S2": "Alto",
    "S3": "Medio",
    "S4": "Bajo"
}


def _get_field_value(doc_data: Dict[str, Any], field: str) -> Any:
    props = doc_data.get("properties", {}) if isinstance(doc_data.get("properties"), dict) else {}
    value = doc_data.get(field)
    if value is None and isinstance(props, dict):
        value = props.get(field)
    return value


def _volume_band(affected_pct: float) -> str:
    if affected_pct > 10:
        return "alto"
    if affected_pct >= 1:
        return "medio"
    return "bajo"


def _priority_from_matrix(severity: str, volume_band: str) -> Dict[str, str]:
    matrix = {
        "S1": {"alto": "P1", "medio": "P1", "bajo": "P2"},
        "S2": {"alto": "P1", "medio": "P2", "bajo": "P3"},
        "S3": {"alto": "P2", "medio": "P3", "bajo": "P4"},
        "S4": {"alto": "P3", "medio": "P4", "bajo": "P5"}
    }
    labels = {
        "P1": "Urgente",
        "P2": "Alta",
        "P3": "Media",
        "P4": "Baja",
        "P5": "Backlog"
    }
    priority = matrix.get(severity, {}).get(volume_band, "P5")
    return {
        "code": priority,
        "label": labels[priority]
    }


def _classify_dqs(score: float) -> Dict[str, str]:
    if score >= 95:
        return {
            "status": "optimo",
            "semaforo": "verde",
            "label": "Óptimo"
        }
    if score >= 85:
        return {
            "status": "aceptable",
            "semaforo": "amarillo",
            "label": "Aceptable"
        }
    return {
        "status": "critico",
        "semaforo": "rojo",
        "label": "Crítico"
    }


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
    for field in required_fields:
        value = _get_field_value(doc_data, field)
        if _normalize_str(value) is None:
            counters[field] = counters.get(field, 0) + 1


def _save_quality_metrics(db, report: Dict[str, Any]) -> None:
    history_collection = db.collection("unidades_proyecto_quality_metrics_history")
    latest_collection = db.collection("unidades_proyecto_quality_metrics_latest")

    history_collection.add(report)
    latest_collection.document("latest").set(report)


def _compute_dimension_stats(rules: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    by_dimension: Dict[str, Dict[str, Any]] = {}
    for rule in rules:
        dimension = rule.get("dimension", "sin_dimension")
        if dimension not in by_dimension:
            by_dimension[dimension] = {
                "dimension": dimension,
                "rules": 0,
                "avg_compliance": 0.0,
                "affected_records": 0,
                "_scores": []
            }
        by_dimension[dimension]["rules"] += 1
        by_dimension[dimension]["affected_records"] += rule["scope"]["affected_records"]
        by_dimension[dimension]["_scores"].append(rule["result"]["compliance_pct"])

    stats: List[Dict[str, Any]] = []
    for _, entry in by_dimension.items():
        scores = entry.pop("_scores", [])
        entry["avg_compliance"] = round(sum(scores) / len(scores), 2) if scores else 100.0
        stats.append(entry)

    return sorted(stats, key=lambda item: item["avg_compliance"])


def _extract_history(db, limit: int = 30) -> List[Dict[str, Any]]:
    try:
        docs = list(db.collection("unidades_proyecto_quality_metrics_history").stream())
    except Exception:
        return []

    snapshots: List[Dict[str, Any]] = []
    for doc in docs:
        data = doc.to_dict() or {}
        snapshots.append({
            "report_id": data.get("report_id", doc.id),
            "generated_at": data.get("generated_at"),
            "dqs_score": (data.get("dqs") or {}).get("score", data.get("overall", {}).get("quality_score", 0.0)),
            "classification": (data.get("dqs") or {}).get("classification", _classify_dqs(float(data.get("overall", {}).get("quality_score", 0.0) or 0.0))),
            "total_issues": data.get("overall", {}).get("total_issues", 0),
            "priorities": data.get("priorities", {})
        })

    snapshots.sort(key=lambda item: str(item.get("generated_at") or ""), reverse=True)
    return snapshots[:max(limit, 1)]


def _build_center_breakdown(center_stats: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    center_rows: List[Dict[str, Any]] = []

    for center_name, stats in center_stats.items():
        total = stats["total"]
        required_slots = total * len(REQUIRED_INTERV_FIELDS)
        missing_required = sum(stats["missing_fields"].values())

        center_rules = [
            _build_rule(
                rule_id="CG-COMP-001",
                name="Completitud mínima por centro gestor",
                dimension="completitud",
                severity="S2",
                collection="intervenciones_unidades_proyecto",
                total_records=required_slots,
                affected_records=missing_required,
                description="Campos obligatorios en intervenciones por centro gestor."
            ),
            _build_rule(
                rule_id="CG-VAL-001",
                name="Validez numérica por centro gestor",
                dimension="validez_conformidad",
                severity="S2",
                collection="intervenciones_unidades_proyecto",
                total_records=total,
                affected_records=stats["invalid_ranges"]["avance_obra"] + stats["invalid_ranges"]["presupuesto_base"],
                description="Rangos de avance_obra y presupuesto_base por centro gestor."
            ),
            _build_rule(
                rule_id="CG-CONS-001",
                name="Consistencia estado vs avance por centro gestor",
                dimension="consistencia",
                severity="S2",
                collection="intervenciones_unidades_proyecto",
                total_records=total,
                affected_records=stats["estado_avance_inconsistente"],
                description="Coherencia estado vs avance por centro gestor."
            ),
            _build_rule(
                rule_id="CG-TIME-001",
                name="Oportunidad temporal por centro gestor",
                dimension="oportunidad_actualidad",
                severity="S3",
                collection="intervenciones_unidades_proyecto",
                total_records=total * 2,
                affected_records=(total - stats["with_fecha_inicio"]) + (total - stats["with_fecha_fin"]),
                description="Disponibilidad de fecha_inicio y fecha_fin por centro gestor."
            ),
            _build_rule(
                rule_id="CG-UNI-001",
                name="Unicidad de intervención por centro gestor",
                dimension="unicidad",
                severity="S1",
                collection="intervenciones_unidades_proyecto",
                total_records=total,
                affected_records=stats["intervencion_id_duplicates"],
                description="Duplicidad de intervencion_id dentro del centro gestor."
            )
        ]

        center_dqs = _compute_weighted_dqs(center_rules)
        center_priorities = {
            "p1": len([r for r in center_rules if r["priority"]["code"] == "P1"]),
            "p2": len([r for r in center_rules if r["priority"]["code"] == "P2"]),
            "p3": len([r for r in center_rules if r["priority"]["code"] == "P3"]),
            "p4": len([r for r in center_rules if r["priority"]["code"] == "P4"]),
            "p5": len([r for r in center_rules if r["priority"]["code"] == "P5"])
        }

        center_rows.append({
            "nombre_centro_gestor": center_name,
            "total_intervenciones": total,
            "dqs": center_dqs,
            "priorities": center_priorities,
            "issues": {
                "missing_required_fields": missing_required,
                "invalid_ranges": stats["invalid_ranges"],
                "estado_vs_avance_inconsistente": stats["estado_avance_inconsistente"],
                "intervencion_id_duplicates": stats["intervencion_id_duplicates"],
                "without_fecha_inicio": total - stats["with_fecha_inicio"],
                "without_fecha_fin": total - stats["with_fecha_fin"]
            }
        })

    center_rows.sort(key=lambda item: (item["dqs"]["score"], -item["total_intervenciones"]))
    return center_rows


def _build_rule(
    *,
    rule_id: str,
    name: str,
    dimension: str,
    severity: str,
    collection: str,
    total_records: int,
    affected_records: int,
    description: str
) -> Dict[str, Any]:
    compliance = 100.0
    affected_pct = 0.0
    if total_records > 0:
        affected_pct = round((affected_records / total_records) * 100, 2)
        compliance = round(max(0.0, 100.0 - affected_pct), 2)

    volume = _volume_band(affected_pct)
    priority = _priority_from_matrix(severity, volume)

    return {
        "rule_id": rule_id,
        "name": name,
        "description": description,
        "collection": collection,
        "dimension": dimension,
        "severity": {
            "code": severity,
            "label": SEVERITY_DESCRIPTIONS.get(severity, severity),
            "weight": SEVERITY_WEIGHTS.get(severity, 0.10)
        },
        "scope": {
            "evaluated_records": total_records,
            "affected_records": affected_records,
            "affected_pct": affected_pct
        },
        "result": {
            "compliance_pct": compliance,
            "passed_records": max(total_records - affected_records, 0),
            "failed_records": affected_records
        },
        "priority": {
            **priority,
            "volume_band": volume
        }
    }


def _compute_weighted_dqs(rules: List[Dict[str, Any]]) -> Dict[str, Any]:
    weighted_sum = 0.0
    total_weight = 0.0

    by_severity = {
        "S1": {"rules": 0, "avg_compliance": 0.0},
        "S2": {"rules": 0, "avg_compliance": 0.0},
        "S3": {"rules": 0, "avg_compliance": 0.0},
        "S4": {"rules": 0, "avg_compliance": 0.0}
    }
    severity_acc = {"S1": [], "S2": [], "S3": [], "S4": []}

    for rule in rules:
        severity_code = rule["severity"]["code"]
        weight = rule["severity"]["weight"]
        score = rule["result"]["compliance_pct"]
        weighted_sum += score * weight
        total_weight += weight
        severity_acc.setdefault(severity_code, []).append(score)

    for severity_code, scores in severity_acc.items():
        if scores:
            by_severity[severity_code] = {
                "rules": len(scores),
                "avg_compliance": round(sum(scores) / len(scores), 2)
            }

    dqs = round((weighted_sum / total_weight), 2) if total_weight > 0 else 100.0
    return {
        "score": dqs,
        "classification": _classify_dqs(dqs),
        "weights": SEVERITY_WEIGHTS,
        "by_severity": by_severity
    }


@with_cache(ttl_seconds=86400)
async def get_unidades_proyecto_quality_metrics(
    nombre_centro_gestor: Optional[str] = None,
    history_limit: int = 30
) -> Dict[str, Any]:
    """Calcula métricas de calidad alineadas a ISO 25012/DAMA para unidades e intervenciones."""
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
    upid_to_centro_gestor: Dict[str, str] = {}
    duplicate_upids = 0

    unidades_query = db.collection("unidades_proyecto")
    for doc in unidades_query.stream():
        doc_data = doc.to_dict()
        unidades_total += 1

        upid = _get_field_value(doc_data, "upid")
        if upid:
            if upid in upid_set:
                duplicate_upids += 1
            upid_set.add(upid)
            centro_unidad = _normalize_str(_get_field_value(doc_data, "nombre_centro_gestor"))
            if centro_unidad is not None:
                upid_to_centro_gestor[upid] = centro_unidad

        _update_missing_fields(doc_data, REQUIRED_UNIDADES_FIELDS, unidades_missing)

        geometry_flags = _extract_geometry_flags(doc_data)
        if geometry_flags["has_geometry"]:
            unidades_with_geometry += 1
        if geometry_flags["has_valid_coordinates"]:
            unidades_with_valid_geometry += 1

        fecha_inicio = _get_field_value(doc_data, "fecha_inicio")
        fecha_fin = _get_field_value(doc_data, "fecha_fin")
        if _normalize_str(fecha_inicio) is not None:
            unidades_with_fecha_inicio += 1
        if _normalize_str(fecha_fin) is not None:
            unidades_with_fecha_fin += 1

    interv_total = 0
    interv_missing = {field: 0 for field in REQUIRED_INTERV_FIELDS}
    interv_invalid_ranges = {
        "avance_obra": 0,
        "presupuesto_base": 0
    }
    interv_estado_avance_inconsistente = 0
    interv_intervencion_id_dupes = 0
    intervencion_id_set = set()
    interv_orphans = 0
    intervenciones_por_upid = {}
    interv_with_fecha_inicio = 0
    interv_with_fecha_fin = 0
    center_stats: Dict[str, Dict[str, Any]] = {}

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

        upid = _get_field_value(doc_data, "upid")
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

        if _estado_vs_avance_inconsistente(doc_data.get("estado"), doc_data.get("avance_obra")):
            interv_estado_avance_inconsistente += 1

        fecha_inicio_interv = _normalize_str(_get_field_value(doc_data, "fecha_inicio"))
        fecha_fin_interv = _normalize_str(_get_field_value(doc_data, "fecha_fin"))
        if fecha_inicio_interv is not None:
            interv_with_fecha_inicio += 1
        if fecha_fin_interv is not None:
            interv_with_fecha_fin += 1

        center_name = _normalize_str(_get_field_value(doc_data, "nombre_centro_gestor"))
        if center_name is None and upid:
            center_name = upid_to_centro_gestor.get(upid)
        if center_name is None:
            center_name = "Sin centro gestor"

        if center_name not in center_stats:
            center_stats[center_name] = {
                "total": 0,
                "missing_fields": {field: 0 for field in REQUIRED_INTERV_FIELDS},
                "invalid_ranges": {"avance_obra": 0, "presupuesto_base": 0},
                "estado_avance_inconsistente": 0,
                "with_fecha_inicio": 0,
                "with_fecha_fin": 0,
                "intervencion_ids_seen": set(),
                "intervencion_id_duplicates": 0
            }

        stats = center_stats[center_name]
        stats["total"] += 1

        for field in REQUIRED_INTERV_FIELDS:
            if _normalize_str(_get_field_value(doc_data, field)) is None:
                stats["missing_fields"][field] += 1

        if avance is not None and (avance < 0 or avance > 100):
            stats["invalid_ranges"]["avance_obra"] += 1
        if presupuesto is not None and presupuesto < 0:
            stats["invalid_ranges"]["presupuesto_base"] += 1

        if _estado_vs_avance_inconsistente(doc_data.get("estado"), doc_data.get("avance_obra")):
            stats["estado_avance_inconsistente"] += 1

        if fecha_inicio_interv is not None:
            stats["with_fecha_inicio"] += 1
        if fecha_fin_interv is not None:
            stats["with_fecha_fin"] += 1

        if intervencion_id in stats["intervencion_ids_seen"]:
            stats["intervencion_id_duplicates"] += 1
        else:
            stats["intervencion_ids_seen"].add(intervencion_id)

    unidades_sin_intervenciones = max(unidades_total - len(intervenciones_por_upid), 0)

    total_records = unidades_total + interv_total

    rules: List[Dict[str, Any]] = []

    rules.append(_build_rule(
        rule_id="UP-COMP-001",
        name="Completitud campos obligatorios unidades_proyecto",
        dimension="completitud",
        severity="S2",
        collection="unidades_proyecto",
        total_records=unidades_total * len(REQUIRED_UNIDADES_FIELDS),
        affected_records=sum(unidades_missing.values()),
        description="Valida presencia de campos obligatorios de unidad de proyecto."
    ))
    rules.append(_build_rule(
        rule_id="UP-VAL-001",
        name="Validez geoespacial unidades_proyecto",
        dimension="validez_conformidad",
        severity="S2",
        collection="unidades_proyecto",
        total_records=unidades_total,
        affected_records=max(unidades_total - unidades_with_valid_geometry, 0),
        description="Verifica coordenadas válidas y no nulas para localización geográfica."
    ))
    rules.append(_build_rule(
        rule_id="UP-UNI-001",
        name="Unicidad de UPID en unidades_proyecto",
        dimension="unicidad",
        severity="S1",
        collection="unidades_proyecto",
        total_records=unidades_total,
        affected_records=duplicate_upids,
        description="UPID no debe repetirse entre unidades de proyecto."
    ))
    rules.append(_build_rule(
        rule_id="UP-CONS-001",
        name="Cobertura de intervenciones por unidad",
        dimension="consistencia",
        severity="S3",
        collection="unidades_proyecto",
        total_records=unidades_total,
        affected_records=unidades_sin_intervenciones,
        description="Evalúa relación esperada unidad-intervención (unidades sin intervenciones asociadas)."
    ))

    rules.append(_build_rule(
        rule_id="INT-COMP-001",
        name="Completitud campos obligatorios intervenciones",
        dimension="completitud",
        severity="S2",
        collection="intervenciones_unidades_proyecto",
        total_records=interv_total * len(REQUIRED_INTERV_FIELDS),
        affected_records=sum(interv_missing.values()),
        description="Valida presencia de campos obligatorios en intervenciones."
    ))
    rules.append(_build_rule(
        rule_id="INT-VAL-001",
        name="Validez de rangos numéricos intervenciones",
        dimension="validez_conformidad",
        severity="S2",
        collection="intervenciones_unidades_proyecto",
        total_records=interv_total,
        affected_records=sum(interv_invalid_ranges.values()),
        description="Valida avance_obra entre 0-100 y presupuesto_base no negativo."
    ))
    rules.append(_build_rule(
        rule_id="INT-CONS-001",
        name="Consistencia estado vs avance de obra",
        dimension="consistencia",
        severity="S2",
        collection="intervenciones_unidades_proyecto",
        total_records=interv_total,
        affected_records=interv_estado_avance_inconsistente,
        description="Valida coherencia semántica entre estado de intervención y avance_obra."
    ))
    rules.append(_build_rule(
        rule_id="INT-UNI-001",
        name="Unicidad de intervencion_id",
        dimension="unicidad",
        severity="S1",
        collection="intervenciones_unidades_proyecto",
        total_records=interv_total,
        affected_records=interv_intervencion_id_dupes,
        description="intervencion_id no debe repetirse en intervenciones."
    ))
    rules.append(_build_rule(
        rule_id="INT-CONS-002",
        name="Integridad referencial de UPID en intervenciones",
        dimension="consistencia",
        severity="S1",
        collection="intervenciones_unidades_proyecto",
        total_records=interv_total,
        affected_records=interv_orphans,
        description="Cada intervención debe referenciar una unidad de proyecto existente."
    ))
    rules.append(_build_rule(
        rule_id="INT-TIME-001",
        name="Oportunidad/actualidad de fechas intervención",
        dimension="oportunidad_actualidad",
        severity="S3",
        collection="intervenciones_unidades_proyecto",
        total_records=interv_total * 2,
        affected_records=(interv_total - interv_with_fecha_inicio) + (interv_total - interv_with_fecha_fin),
        description="Verifica disponibilidad de fecha_inicio y fecha_fin para monitoreo temporal."
    ))

    dqs = _compute_weighted_dqs(rules)
    quality_score = dqs["score"]

    total_issues = sum(rule["scope"]["affected_records"] for rule in rules)

    now_iso = datetime.now(timezone.utc).isoformat()
    report_id = f"{datetime.now(timezone.utc).strftime('%Y%m%d')}-{uuid.uuid4().hex[:8]}"

    center_breakdown = _build_center_breakdown(center_stats)
    if nombre_centro_gestor:
        center_breakdown = [
            center for center in center_breakdown
            if center["nombre_centro_gestor"] == nombre_centro_gestor
        ]

    dimension_stats = _compute_dimension_stats(rules)
    top_rules = sorted(rules, key=lambda rule: rule["scope"]["affected_pct"], reverse=True)[:10]

    result = {
        "success": True,
        "report_id": report_id,
        "generated_at": now_iso,
        "framework": {
            "standards": ["ISO 8000", "ISO/IEC 25012", "DAMA-DMBOK"],
            "dimensions": [
                "completitud",
                "exactitud",
                "consistencia",
                "validez_conformidad",
                "unicidad",
                "oportunidad_actualidad"
            ]
        },
        "overall": {
            "total_records": total_records,
            "total_issues": total_issues,
            "quality_score": quality_score
        },
        "dqs": dqs,
        "rules": rules,
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
                "temporal": {
                    "with_fecha_inicio": interv_with_fecha_inicio,
                    "with_fecha_fin": interv_with_fecha_fin
                },
                "estado_vs_avance_inconsistente": interv_estado_avance_inconsistente,
                "duplicates": {
                    "intervencion_id_duplicates": interv_intervencion_id_dupes
                },
                "orphans": {
                    "intervenciones_sin_unidad": interv_orphans
                }
            }
        },
        "priorities": {
            "p1": len([r for r in rules if r["priority"]["code"] == "P1"]),
            "p2": len([r for r in rules if r["priority"]["code"] == "P2"]),
            "p3": len([r for r in rules if r["priority"]["code"] == "P3"]),
            "p4": len([r for r in rules if r["priority"]["code"] == "P4"]),
            "p5": len([r for r in rules if r["priority"]["code"] == "P5"])
        },
        "resumen": {
            "report_id": report_id,
            "generated_at": now_iso,
            "data_quality_score": dqs["score"],
            "clasificacion": dqs["classification"],
            "total_reglas": len(rules),
            "total_registros": total_records,
            "total_hallazgos": total_issues,
            "prioridades": {
                "p1": len([r for r in rules if r["priority"]["code"] == "P1"]),
                "p2": len([r for r in rules if r["priority"]["code"] == "P2"]),
                "p3": len([r for r in rules if r["priority"]["code"] == "P3"]),
                "p4": len([r for r in rules if r["priority"]["code"] == "P4"]),
                "p5": len([r for r in rules if r["priority"]["code"] == "P5"])
            },
            "hallazgos_principales": top_rules[:5]
        },
        "registros": {
            "rules": rules,
            "count": len(rules)
        },
        "por_centro_gestor": {
            "filtro_aplicado": nombre_centro_gestor,
            "total_centros": len(center_breakdown),
            "centros": center_breakdown
        },
        "metadatos": {
            "standards": ["ISO 8000", "ISO/IEC 25012", "DAMA-DMBOK"],
            "dimensions": [
                "completitud",
                "exactitud",
                "consistencia",
                "validez_conformidad",
                "unicidad",
                "oportunidad_actualidad"
            ],
            "collections_evaluadas": ["unidades_proyecto", "intervenciones_unidades_proyecto"],
            "cache_ttl_seconds": 86400,
            "history_limit": max(history_limit, 1)
        },
        "estadisticas_globales": {
            "overall": {
                "total_records": total_records,
                "total_issues": total_issues,
                "quality_score": quality_score
            },
            "by_dimension": dimension_stats,
            "by_collection": {
                "unidades_proyecto": {
                    "total": unidades_total,
                    "issues": sum(unidades_missing.values()) + (unidades_total - unidades_with_valid_geometry) + duplicate_upids + unidades_sin_intervenciones
                },
                "intervenciones_unidades_proyecto": {
                    "total": interv_total,
                    "issues": sum(interv_missing.values()) + sum(interv_invalid_ranges.values()) + interv_estado_avance_inconsistente + interv_intervencion_id_dupes + interv_orphans
                }
            }
        }
    }

    _save_quality_metrics(db, result)

    history_items = _extract_history(db, history_limit)
    result["historial"] = {
        "items": history_items,
        "count": len(history_items)
    }

    if nombre_centro_gestor:
        result["resumen"]["contexto"] = {
            "nombre_centro_gestor": nombre_centro_gestor,
            "matching_centros": len(center_breakdown)
        }

    return result

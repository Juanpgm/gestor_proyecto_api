"""Calidad de datos de Unidades de Proyecto con snapshots persistidos y detalle paginado."""

from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import uuid
from typing import Any, Dict, List, Optional, Tuple

from api.scripts.unidades_proyecto import _convert_to_float
from database.firebase_config import get_firestore_client


QUALITY_REPORTS_COLLECTION = "unidades_proyecto_quality_reports"
QUALITY_LATEST_COLLECTION = "unidades_proyecto_quality_latest"
QUALITY_RECORDS_SUBCOLLECTION = "records"
QUALITY_ISSUES_SUBCOLLECTION = "issues"

# Colecciones espejadas para consulta directa sin navegar subcolecciones
QUALITY_UNIDADES_RECORDS_COLLECTION = "unidades_proyecto_quality_unidades_records"
QUALITY_INTERV_RECORDS_COLLECTION = "unidades_proyecto_quality_intervenciones_records"
QUALITY_ISSUES_COLLECTION = "unidades_proyecto_quality_issues"

SEVERITY_DESCRIPTIONS = {
    "S1": "Critico",
    "S2": "Alto",
    "S3": "Medio",
    "S4": "Bajo",
}

SEVERITY_RANK = {
    "S1": 4,
    "S2": 3,
    "S3": 2,
    "S4": 1,
}

SEVERITY_WEIGHTS = {
    "S1": 0.40,
    "S2": 0.30,
    "S3": 0.20,
    "S4": 0.10,
}

CORE_REQUIRED_UNIDAD_FIELDS = [
    "upid",
    "nombre_up",
    "nombre_centro_gestor",
]

CORE_REQUIRED_INTERV_FIELDS = [
    "intervencion_id",
    "upid",
    "estado",
    "tipo_intervencion",
]

FOCUS_FIELDS = ["presupuesto_base", "fecha_inicio", "fecha_fin", "geometry"]


def _normalize_str(value: Any) -> Optional[str]:
    if value is None:
        return None
    value_str = str(value).strip()
    return value_str if value_str else None


def _normalize_upid(value: Any) -> Optional[str]:
    upid = _normalize_str(value)
    if upid is None:
        return None
    return upid.upper()


def _now_colombia_iso() -> str:
    tz = ZoneInfo("America/Bogota")
    return datetime.now(tz).isoformat()


def _get_field_value(doc_data: Dict[str, Any], field: str) -> Any:
    props = doc_data.get("properties", {}) if isinstance(doc_data.get("properties"), dict) else {}
    value = doc_data.get(field)
    if value is None:
        value = props.get(field)
    return value


def _extract_nombre_centro_gestor(doc_data: Dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
    """
    Extrae nombre_centro_gestor priorizando el nombre correcto del campo.
    Se admite fallback por compatibilidad con datos históricos heterogéneos.
    """
    props = doc_data.get("properties", {}) if isinstance(doc_data.get("properties"), dict) else {}
    ordered_fields = [
        "nombre_centro_gestor",  # campo canónico
        "nombreCentroGestor",
        "nombre_centro",
        "centro_gestor",         # fallback legacy
    ]

    for field in ordered_fields:
        top_val = _normalize_str(doc_data.get(field))
        if top_val is not None:
            return top_val, field

        prop_val = _normalize_str(props.get(field))
        if prop_val is not None:
            return prop_val, f"properties.{field}"

    return None, None


def _parse_date(value: Any) -> bool:
    text = _normalize_str(value)
    if text is None:
        return False
    parse_formats = [
        "%Y-%m-%d",
        "%Y/%m/%d",
        "%d/%m/%Y",
        "%d-%m-%Y",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%S.%f",
    ]
    for fmt in parse_formats:
        try:
            datetime.strptime(text, fmt)
            return True
        except ValueError:
            continue
    try:
        datetime.fromisoformat(text.replace("Z", "+00:00"))
        return True
    except ValueError:
        return False


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

    has_geometry = bool(geometry is not None or coords is not None or (lat is not None and lon is not None))
    has_valid_coordinates = _is_valid_lat_lon(lat, lon)

    if isinstance(geometry, dict):
        geom_coords = geometry.get("coordinates")
        if isinstance(geom_coords, (list, tuple)) and len(geom_coords) >= 2:
            if geom_coords[0] == 0 and geom_coords[1] == 0:
                has_valid_coordinates = False

    if isinstance(coords, (list, tuple)) and len(coords) >= 2:
        if coords[0] == 0 and coords[1] == 0:
            has_valid_coordinates = False

    return {
        "exists": has_geometry,
        "is_valid": bool(has_valid_coordinates),
    }


def _severity_from_issues(issues: List[Dict[str, Any]]) -> Optional[str]:
    if not issues:
        return None
    return max((issue.get("severity", "S4") for issue in issues), key=lambda sev: SEVERITY_RANK.get(sev, 0))


def _classify_dqs(score: float) -> Dict[str, str]:
    if score >= 95:
        return {"status": "optimo", "semaforo": "verde", "label": "Optimo"}
    if score >= 85:
        return {"status": "aceptable", "semaforo": "amarillo", "label": "Aceptable"}
    return {"status": "critico", "semaforo": "rojo", "label": "Critico"}


def _priority_from_matrix(severity: str, volume_band: str) -> Dict[str, str]:
    matrix = {
        "S1": {"alto": "P1", "medio": "P1", "bajo": "P2"},
        "S2": {"alto": "P1", "medio": "P2", "bajo": "P3"},
        "S3": {"alto": "P2", "medio": "P3", "bajo": "P4"},
        "S4": {"alto": "P3", "medio": "P4", "bajo": "P5"},
    }
    labels = {
        "P1": "Urgente",
        "P2": "Alta",
        "P3": "Media",
        "P4": "Baja",
        "P5": "Backlog",
    }
    code = matrix.get(severity, {}).get(volume_band, "P5")
    return {"code": code, "label": labels[code], "volume_band": volume_band}


def _volume_band(affected_pct: float) -> str:
    if affected_pct > 10:
        return "alto"
    if affected_pct >= 1:
        return "medio"
    return "bajo"


def _build_issue(field: str, severity: str, reason: str, record_type: str) -> Dict[str, Any]:
    return {
        "field": field,
        "severity": severity,
        "severity_label": SEVERITY_DESCRIPTIONS.get(severity, severity),
        "reason": reason,
        "record_type": record_type,
    }


def _evaluate_focus_fields(doc_data: Dict[str, Any], record_type: str) -> Tuple[Dict[str, Dict[str, Any]], List[Dict[str, Any]]]:
    assessment: Dict[str, Dict[str, Any]] = {}
    issues: List[Dict[str, Any]] = []

    presupuesto_raw = _get_field_value(doc_data, "presupuesto_base")
    presupuesto_num = _convert_to_float(presupuesto_raw)
    presupuesto_exists = _normalize_str(presupuesto_raw) is not None
    presupuesto_valid = bool(presupuesto_num is not None and presupuesto_num >= 0)
    assessment["presupuesto_base"] = {
        "exists": presupuesto_exists,
        "is_valid": presupuesto_valid,
        "value": presupuesto_raw,
    }
    if not presupuesto_exists:
        issues.append(_build_issue("presupuesto_base", "S2", "missing", record_type))
    elif not presupuesto_valid:
        issues.append(_build_issue("presupuesto_base", "S2", "invalid_negative_or_non_numeric", record_type))

    for field in ["fecha_inicio", "fecha_fin"]:
        value = _get_field_value(doc_data, field)
        exists = _normalize_str(value) is not None
        valid = _parse_date(value) if exists else False
        assessment[field] = {
            "exists": exists,
            "is_valid": valid,
            "value": value,
        }
        if not exists:
            issues.append(_build_issue(field, "S3", "missing", record_type))
        elif not valid:
            issues.append(_build_issue(field, "S3", "invalid_date_format", record_type))

    geometry_flags = _extract_geometry_flags(doc_data)
    assessment["geometry"] = {
        "exists": geometry_flags["exists"],
        "is_valid": geometry_flags["is_valid"],
    }
    if not geometry_flags["exists"]:
        issues.append(_build_issue("geometry", "S2", "missing", record_type))
    elif not geometry_flags["is_valid"]:
        issues.append(_build_issue("geometry", "S2", "invalid_coordinates", record_type))

    return assessment, issues


def _evaluate_required_fields(doc_data: Dict[str, Any], required_fields: List[str], record_type: str) -> List[Dict[str, Any]]:
    issues: List[Dict[str, Any]] = []
    for field in required_fields:
        if _normalize_str(_get_field_value(doc_data, field)) is None:
            issues.append(_build_issue(field, "S2", "missing_required", record_type))
    return issues


def _compute_weighted_dqs(total_records: int, total_issues: int, severity_counter: Dict[str, int]) -> Dict[str, Any]:
    if total_records <= 0:
        return {
            "score": 100.0,
            "classification": _classify_dqs(100.0),
            "by_severity": {k: {"count": 0, "weighted_impact": 0.0} for k in SEVERITY_WEIGHTS.keys()},
        }

    weighted_impact = 0.0
    by_severity: Dict[str, Dict[str, Any]] = {}
    for sev, count in severity_counter.items():
        impact = (count / total_records) * 100.0
        by_severity[sev] = {
            "count": count,
            "weighted_impact": round(impact * SEVERITY_WEIGHTS[sev], 2),
        }
        weighted_impact += impact * SEVERITY_WEIGHTS[sev]

    score = round(max(0.0, 100.0 - weighted_impact), 2)
    return {
        "score": score,
        "classification": _classify_dqs(score),
        "by_severity": by_severity,
        "raw": {
            "total_records": total_records,
            "total_issues": total_issues,
        },
    }


def _build_rules(summary: Dict[str, Any]) -> List[Dict[str, Any]]:
    rules_input = [
        ("UP-QA-001", "Completitud de campos foco en unidades", "unidades_proyecto", "S2", summary["unidades"]["missing_focus_total"], summary["unidades"]["total"] * len(FOCUS_FIELDS)),
        ("UP-QA-002", "Completitud de campos base en unidades", "unidades_proyecto", "S2", summary["unidades"]["missing_required_total"], summary["unidades"]["total"] * len(CORE_REQUIRED_UNIDAD_FIELDS)),
        ("INT-QA-001", "Completitud de campos foco en intervenciones", "intervenciones_unidades_proyecto", "S2", summary["intervenciones"]["missing_focus_total"], summary["intervenciones"]["total"] * len(FOCUS_FIELDS)),
        ("INT-QA-002", "Completitud de campos base en intervenciones", "intervenciones_unidades_proyecto", "S2", summary["intervenciones"]["missing_required_total"], summary["intervenciones"]["total"] * len(CORE_REQUIRED_INTERV_FIELDS)),
        ("INT-QA-003", "Integridad referencial UPID", "intervenciones_unidades_proyecto", "S1", summary["intervenciones"]["orphan_upid"], summary["intervenciones"]["total"]),
        ("INT-QA-004", "Unicidad de intervencion_id", "intervenciones_unidades_proyecto", "S1", summary["intervenciones"]["duplicate_intervencion_id"], summary["intervenciones"]["total"]),
    ]

    rules: List[Dict[str, Any]] = []
    for rule_id, name, collection, severity, affected, total in rules_input:
        affected_pct = round(((affected / total) * 100), 2) if total > 0 else 0.0
        volume_band = _volume_band(affected_pct)
        rules.append(
            {
                "rule_id": rule_id,
                "name": name,
                "collection": collection,
                "severity": {
                    "code": severity,
                    "label": SEVERITY_DESCRIPTIONS.get(severity, severity),
                },
                "scope": {
                    "evaluated_records": total,
                    "affected_records": affected,
                    "affected_pct": affected_pct,
                },
                "priority": _priority_from_matrix(severity, volume_band),
            }
        )
    return rules


def _get_db():
    db = get_firestore_client()
    if db is None:
        raise RuntimeError("No se pudo conectar a Firestore")
    return db


def _report_summary_payload(report_id: str, generated_at: str, nombre_centro_gestor: Optional[str], summary: Dict[str, Any], rules: List[Dict[str, Any]], dqs: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "report_id": report_id,
        "generated_at": generated_at,
        "filtro": {
            "nombre_centro_gestor": nombre_centro_gestor,
        },
        "framework": {
            "standards": ["ISO 8000", "ISO/IEC 25012", "DAMA-DMBOK"],
            "dimensions": ["completitud", "validez_conformidad", "consistencia", "unicidad", "oportunidad_actualidad"],
            "focus_fields": FOCUS_FIELDS,
        },
        "summary": summary,
        "dqs": dqs,
        "rules": rules,
        "collections": {
            "report_collection": QUALITY_REPORTS_COLLECTION,
            "records_subcollection": QUALITY_RECORDS_SUBCOLLECTION,
            "issues_subcollection": QUALITY_ISSUES_SUBCOLLECTION,
            "latest_collection": QUALITY_LATEST_COLLECTION,
            "records_by_type": {
                "unidades": QUALITY_UNIDADES_RECORDS_COLLECTION,
                "intervenciones": QUALITY_INTERV_RECORDS_COLLECTION,
            },
            "issues_flat_collection": QUALITY_ISSUES_COLLECTION,
        },
    }


def _matches_center_filter(center_value: Optional[str], center_filter: Optional[str]) -> bool:
    if not center_filter:
        return True
    center = _normalize_str(center_value)
    if center is None:
        return False
    return center.lower() == center_filter.lower()


def _new_center_group_entry() -> Dict[str, Any]:
    return {
        "total_records": 0,
        "with_issues": 0,
        "unidades": 0,
        "intervenciones": 0,
        "severity": {"S1": 0, "S2": 0, "S3": 0, "S4": 0},
        "focus_fields": {
            "unidad": {field: {"missing": 0, "invalid": 0} for field in FOCUS_FIELDS},
            "intervencion": {field: {"missing": 0, "invalid": 0} for field in FOCUS_FIELDS},
        },
    }


def _persist_quality_snapshot(db, report_id: str, payload: Dict[str, Any], records: List[Dict[str, Any]]) -> None:
    report_ref = db.collection(QUALITY_REPORTS_COLLECTION).document(report_id)
    report_ref.set(payload)

    db.collection(QUALITY_LATEST_COLLECTION).document("latest").set(
        {
            "report_id": report_id,
            "generated_at": payload.get("generated_at"),
            "filtro": payload.get("filtro", {}),
        }
    )

    batch = db.batch()
    writes = 0
    issue_counter = 0

    def _commit_batch_if_needed() -> None:
        nonlocal batch, writes
        if writes >= 400:
            batch.commit()
            batch = db.batch()
            writes = 0

    for item in records:
        record_uid = item["record_uid"]
        record_type = item.get("record_type")

        # Registro dentro del snapshot
        doc_ref = report_ref.collection(QUALITY_RECORDS_SUBCOLLECTION).document(record_uid)
        batch.set(doc_ref, item)
        writes += 1

        # Registro espejo por tipo para consultas directas
        flat_payload = {
            **item,
            "report_id": report_id,
        }
        if record_type == "unidad":
            unit_ref = db.collection(QUALITY_UNIDADES_RECORDS_COLLECTION).document(f"{report_id}__{record_uid}")
            batch.set(unit_ref, flat_payload)
            writes += 1
        elif record_type == "intervencion":
            interv_ref = db.collection(QUALITY_INTERV_RECORDS_COLLECTION).document(f"{report_id}__{record_uid}")
            batch.set(interv_ref, flat_payload)
            writes += 1

        # Persistir cada issue como documento individual
        for issue in item.get("issues", []) or []:
            issue_counter += 1
            issue_id = f"{record_uid}__{issue_counter}"
            issue_payload = {
                "report_id": report_id,
                "record_uid": record_uid,
                "record_type": record_type,
                "source_collection": item.get("source_collection"),
                "source_doc_id": item.get("source_doc_id"),
                "nombre_centro_gestor": item.get("nombre_centro_gestor"),
                "upid": item.get("upid"),
                "intervencion_id": item.get("intervencion_id"),
                "generated_at": item.get("generated_at"),
                "field": issue.get("field"),
                "severity": issue.get("severity"),
                "severity_label": issue.get("severity_label"),
                "reason": issue.get("reason"),
                "issue": issue,
            }

            # Dentro del snapshot
            issue_ref = report_ref.collection(QUALITY_ISSUES_SUBCOLLECTION).document(issue_id)
            batch.set(issue_ref, issue_payload)
            writes += 1

            # Colección plana global
            flat_issue_ref = db.collection(QUALITY_ISSUES_COLLECTION).document(f"{report_id}__{issue_id}")
            batch.set(flat_issue_ref, issue_payload)
            writes += 1

        _commit_batch_if_needed()

    if writes > 0:
        batch.commit()


async def generate_unidades_proyecto_quality_report(
    nombre_centro_gestor: Optional[str] = None,
    persist: bool = True,
) -> Dict[str, Any]:
    """Genera snapshot completo de calidad y guarda detalle por registro para lectura paginada."""
    db = _get_db()
    center_filter = _normalize_str(nombre_centro_gestor)

    generated_at = _now_colombia_iso()
    report_id = f"quality-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6]}"

    unidades_docs = list(db.collection("unidades_proyecto").stream())
    unidades_by_upid: Dict[str, int] = {}
    upid_to_center: Dict[str, str] = {}

    for doc in unidades_docs:
        data = doc.to_dict() or {}
        upid = _normalize_upid(_get_field_value(data, "upid"))
        center, _ = _extract_nombre_centro_gestor(data)
        if upid:
            unidades_by_upid[upid] = unidades_by_upid.get(upid, 0) + 1
            if center:
                upid_to_center[upid] = center

    interv_docs = list(db.collection("intervenciones_unidades_proyecto").stream())
    intervencion_id_counts: Dict[str, int] = {}
    for doc in interv_docs:
        data = doc.to_dict() or {}
        intervencion_id = _normalize_str(_get_field_value(data, "intervencion_id")) or doc.id
        intervencion_id_counts[intervencion_id] = intervencion_id_counts.get(intervencion_id, 0) + 1

    records: List[Dict[str, Any]] = []
    summary = {
        "total_records": 0,
        "records_with_issues": 0,
        "records_without_issues": 0,
        "by_severity": {"S1": 0, "S2": 0, "S3": 0, "S4": 0},
        "unidades": {
            "total": 0,
            "with_issues": 0,
            "missing_focus_total": 0,
            "missing_required_total": 0,
            "by_field": {field: {"missing": 0, "invalid": 0} for field in FOCUS_FIELDS},
        },
        "intervenciones": {
            "total": 0,
            "with_issues": 0,
            "missing_focus_total": 0,
            "missing_required_total": 0,
            "orphan_upid": 0,
            "duplicate_intervencion_id": 0,
            "by_field": {field: {"missing": 0, "invalid": 0} for field in FOCUS_FIELDS},
        },
        "grouped_by_centro_gestor": {},
    }

    record_index = 0

    for doc in unidades_docs:
        data = doc.to_dict() or {}
        upid = _normalize_upid(_get_field_value(data, "upid"))
        center, center_source = _extract_nombre_centro_gestor(data)
        center = center or "Sin centro gestor"
        if not _matches_center_filter(center, center_filter):
            continue

        required_issues = _evaluate_required_fields(data, CORE_REQUIRED_UNIDAD_FIELDS, "unidad")
        focus_assessment, focus_issues = _evaluate_focus_fields(data, "unidad")
        issues = required_issues + focus_issues

        if upid and unidades_by_upid.get(upid, 0) > 1:
            issues.append(_build_issue("upid", "S1", "duplicate_upid", "unidad"))

        severity = _severity_from_issues(issues)
        has_issues = bool(issues)

        summary["total_records"] += 1
        summary["unidades"]["total"] += 1
        if has_issues:
            summary["records_with_issues"] += 1
            summary["unidades"]["with_issues"] += 1
            if severity:
                summary["by_severity"][severity] += 1
        else:
            summary["records_without_issues"] += 1

        summary["unidades"]["missing_required_total"] += len([x for x in required_issues if x["reason"] == "missing_required"])

        for field in FOCUS_FIELDS:
            entry = focus_assessment.get(field, {})
            if not entry.get("exists", False):
                summary["unidades"]["by_field"][field]["missing"] += 1
                summary["unidades"]["missing_focus_total"] += 1
            elif not entry.get("is_valid", False):
                summary["unidades"]["by_field"][field]["invalid"] += 1

        grouped = summary["grouped_by_centro_gestor"].setdefault(
            center,
            _new_center_group_entry(),
        )
        grouped["total_records"] += 1
        grouped["unidades"] += 1
        if has_issues:
            grouped["with_issues"] += 1
        if severity:
            grouped["severity"][severity] += 1

        for field in FOCUS_FIELDS:
            entry = focus_assessment.get(field, {})
            if not entry.get("exists", False):
                grouped["focus_fields"]["unidad"][field]["missing"] += 1
            elif not entry.get("is_valid", False):
                grouped["focus_fields"]["unidad"][field]["invalid"] += 1

        records.append(
            {
                "record_uid": f"unidad-{doc.id}",
                "record_index": record_index,
                "report_id": report_id,
                "generated_at": generated_at,
                "record_type": "unidad",
                "source_collection": "unidades_proyecto",
                "source_doc_id": doc.id,
                "upid": upid,
                "intervencion_id": None,
                "nombre_centro_gestor": center,
                "nombre_centro_gestor_source": center_source or "not_found",
                "focus_fields": focus_assessment,
                "issues": issues,
                "issues_count": len(issues),
                "has_issues": has_issues,
                "max_severity": severity,
                "group_keys": {
                    "centro_gestor": center,
                    "record_type": "unidad",
                },
            }
        )
        record_index += 1

    for doc in interv_docs:
        data = doc.to_dict() or {}
        upid = _normalize_upid(_get_field_value(data, "upid"))
        center, center_source = _extract_nombre_centro_gestor(data)
        if center is None and upid is not None:
            center = upid_to_center.get(upid)
            if center is not None:
                center_source = "unidad_por_upid"
        center = center or "Sin centro gestor"
        if not _matches_center_filter(center, center_filter):
            continue

        required_issues = _evaluate_required_fields(data, CORE_REQUIRED_INTERV_FIELDS, "intervencion")
        focus_assessment, focus_issues = _evaluate_focus_fields(data, "intervencion")
        issues = required_issues + focus_issues

        intervencion_id = _normalize_str(_get_field_value(data, "intervencion_id")) or doc.id

        if upid is None or upid not in unidades_by_upid:
            issues.append(_build_issue("upid", "S1", "orphan_upid", "intervencion"))

        if intervencion_id_counts.get(intervencion_id, 0) > 1:
            issues.append(_build_issue("intervencion_id", "S1", "duplicate_intervencion_id", "intervencion"))

        severity = _severity_from_issues(issues)
        has_issues = bool(issues)

        summary["total_records"] += 1
        summary["intervenciones"]["total"] += 1
        if has_issues:
            summary["records_with_issues"] += 1
            summary["intervenciones"]["with_issues"] += 1
            if severity:
                summary["by_severity"][severity] += 1
        else:
            summary["records_without_issues"] += 1

        summary["intervenciones"]["missing_required_total"] += len([x for x in required_issues if x["reason"] == "missing_required"])

        orphan = any(x["reason"] == "orphan_upid" for x in issues)
        duplicate_interv = any(x["reason"] == "duplicate_intervencion_id" for x in issues)
        if orphan:
            summary["intervenciones"]["orphan_upid"] += 1
        if duplicate_interv:
            summary["intervenciones"]["duplicate_intervencion_id"] += 1

        for field in FOCUS_FIELDS:
            entry = focus_assessment.get(field, {})
            if not entry.get("exists", False):
                summary["intervenciones"]["by_field"][field]["missing"] += 1
                summary["intervenciones"]["missing_focus_total"] += 1
            elif not entry.get("is_valid", False):
                summary["intervenciones"]["by_field"][field]["invalid"] += 1

        grouped = summary["grouped_by_centro_gestor"].setdefault(
            center,
            _new_center_group_entry(),
        )
        grouped["total_records"] += 1
        grouped["intervenciones"] += 1
        if has_issues:
            grouped["with_issues"] += 1
        if severity:
            grouped["severity"][severity] += 1

        for field in FOCUS_FIELDS:
            entry = focus_assessment.get(field, {})
            if not entry.get("exists", False):
                grouped["focus_fields"]["intervencion"][field]["missing"] += 1
            elif not entry.get("is_valid", False):
                grouped["focus_fields"]["intervencion"][field]["invalid"] += 1

        records.append(
            {
                "record_uid": f"intervencion-{doc.id}",
                "record_index": record_index,
                "report_id": report_id,
                "generated_at": generated_at,
                "record_type": "intervencion",
                "source_collection": "intervenciones_unidades_proyecto",
                "source_doc_id": doc.id,
                "upid": upid,
                "intervencion_id": intervencion_id,
                "nombre_centro_gestor": center,
                "nombre_centro_gestor_source": center_source or "not_found",
                "focus_fields": focus_assessment,
                "issues": issues,
                "issues_count": len(issues),
                "has_issues": has_issues,
                "max_severity": severity,
                "group_keys": {
                    "centro_gestor": center,
                    "record_type": "intervencion",
                },
            }
        )
        record_index += 1

    dqs = _compute_weighted_dqs(
        total_records=summary["total_records"],
        total_issues=summary["records_with_issues"],
        severity_counter=summary["by_severity"],
    )
    rules = _build_rules(summary)

    report_payload = _report_summary_payload(
        report_id=report_id,
        generated_at=generated_at,
        nombre_centro_gestor=center_filter,
        summary=summary,
        rules=rules,
        dqs=dqs,
    )

    if persist:
        _persist_quality_snapshot(db, report_id, report_payload, records)

    return {
        "success": True,
        "report_id": report_id,
        "generated_at": generated_at,
        "persisted": persist,
        "summary": summary,
        "dqs": dqs,
        "rules": rules,
        "preview": {
            "records_total": len(records),
            "first_records": records[:5],
        },
        "collections": report_payload["collections"],
    }


def _read_latest_report_id(db) -> Optional[str]:
    latest_doc = db.collection(QUALITY_LATEST_COLLECTION).document("latest").get()
    if not latest_doc.exists:
        return None
    return (latest_doc.to_dict() or {}).get("report_id")


async def get_unidades_proyecto_quality_summary(
    report_id: Optional[str] = None,
    history_limit: int = 10,
    auto_generate: bool = False,
    nombre_centro_gestor: Optional[str] = None,
) -> Dict[str, Any]:
    """Obtiene resumen de calidad desde snapshot persistido; opcionalmente autogenera si no existe."""
    db = _get_db()

    selected_report_id = report_id or _read_latest_report_id(db)

    if selected_report_id is None and auto_generate:
        generated = await generate_unidades_proyecto_quality_report(
            nombre_centro_gestor=nombre_centro_gestor,
            persist=True,
        )
        selected_report_id = generated.get("report_id")

    if selected_report_id is None:
        return {
            "success": False,
            "error": "No existe snapshot de calidad. Ejecuta POST /unidades-proyecto/calidad-datos/analizar.",
        }

    report_doc = db.collection(QUALITY_REPORTS_COLLECTION).document(selected_report_id).get()
    if not report_doc.exists:
        return {
            "success": False,
            "error": f"No se encontro report_id: {selected_report_id}",
        }

    payload = report_doc.to_dict() or {}
    history = await get_unidades_proyecto_quality_history(limit=history_limit)

    return {
        "success": True,
        "report_id": selected_report_id,
        "generated_at": payload.get("generated_at"),
        "framework": payload.get("framework", {}),
        "summary": payload.get("summary", {}),
        "dqs": payload.get("dqs", {}),
        "rules": payload.get("rules", []),
        "historial": history,
    }


async def get_unidades_proyecto_quality_history(limit: int = 20) -> Dict[str, Any]:
    """Obtiene historial de snapshots de calidad guardados."""
    db = _get_db()
    items: List[Dict[str, Any]] = []
    docs = list(db.collection(QUALITY_REPORTS_COLLECTION).stream())
    docs.sort(key=lambda doc: str((doc.to_dict() or {}).get("generated_at") or ""), reverse=True)

    for doc in docs[:max(1, min(limit, 200))]:
        data = doc.to_dict() or {}
        items.append(
            {
                "report_id": data.get("report_id", doc.id),
                "generated_at": data.get("generated_at"),
                "filtro": data.get("filtro", {}),
                "dqs_score": (data.get("dqs") or {}).get("score"),
                "classification": (data.get("dqs") or {}).get("classification"),
                "total_records": (data.get("summary") or {}).get("total_records", 0),
                "records_with_issues": (data.get("summary") or {}).get("records_with_issues", 0),
            }
        )

    return {
        "success": True,
        "count": len(items),
        "items": items,
    }


async def get_unidades_proyecto_quality_centros_paginated(
    report_id: Optional[str] = None,
    page_size: int = 25,
    page_token: Optional[int] = None,
    only_with_issues: bool = False,
    sort_by: str = "issue_rate",
) -> Dict[str, Any]:
    """Retorna agregados por nombre_centro_gestor con paginacion por offset."""
    db = _get_db()
    selected_report_id = report_id or _read_latest_report_id(db)

    if selected_report_id is None:
        return {
            "success": False,
            "error": "No existe snapshot de calidad. Ejecuta POST /unidades-proyecto/calidad-datos/analizar.",
        }

    report_doc = db.collection(QUALITY_REPORTS_COLLECTION).document(selected_report_id).get()
    if not report_doc.exists:
        return {
            "success": False,
            "error": f"No se encontro report_id: {selected_report_id}",
        }

    payload = report_doc.to_dict() or {}
    grouped = (payload.get("summary") or {}).get("grouped_by_centro_gestor", {})

    rows: List[Dict[str, Any]] = []
    for center_name, stats in grouped.items():
        total = int(stats.get("total_records", 0) or 0)
        with_issues = int(stats.get("with_issues", 0) or 0)
        issue_rate = round((with_issues / total) * 100, 2) if total > 0 else 0.0
        if only_with_issues and with_issues <= 0:
            continue

        rows.append(
            {
                "nombre_centro_gestor": center_name,
                "total_records": total,
                "with_issues": with_issues,
                "without_issues": max(total - with_issues, 0),
                "issue_rate_pct": issue_rate,
                "unidades": int(stats.get("unidades", 0) or 0),
                "intervenciones": int(stats.get("intervenciones", 0) or 0),
                "severity": stats.get("severity", {"S1": 0, "S2": 0, "S3": 0, "S4": 0}),
                "focus_fields": stats.get("focus_fields", _new_center_group_entry()["focus_fields"]),
            }
        )

    if sort_by == "name":
        rows.sort(key=lambda row: (row.get("nombre_centro_gestor") or "").lower())
    elif sort_by == "total_records":
        rows.sort(key=lambda row: row.get("total_records", 0), reverse=True)
    elif sort_by == "with_issues":
        rows.sort(key=lambda row: row.get("with_issues", 0), reverse=True)
    else:
        rows.sort(key=lambda row: (row.get("issue_rate_pct", 0.0), row.get("with_issues", 0)), reverse=True)

    offset = max(0, page_token or 0)
    size = max(1, min(page_size, 200))
    paged = rows[offset: offset + size]
    next_token = offset + size if offset + size < len(rows) else None

    return {
        "success": True,
        "report_id": selected_report_id,
        "sort_by": sort_by,
        "only_with_issues": only_with_issues,
        "count": len(paged),
        "total_centros": len(rows),
        "page_size": size,
        "page_token": offset,
        "next_page_token": next_token,
        "has_more": next_token is not None,
        "centros": paged,
    }


def _record_matches_filters(
    record: Dict[str, Any],
    record_type: Optional[str],
    has_issues: Optional[bool],
    nombre_centro_gestor: Optional[str],
) -> bool:
    if record_type and (record.get("record_type") or "").lower() != record_type.lower():
        return False
    if has_issues is not None and bool(record.get("has_issues")) != has_issues:
        return False
    if nombre_centro_gestor:
        center = _normalize_str(record.get("nombre_centro_gestor"))
        if center is None or center.lower() != nombre_centro_gestor.lower():
            return False
    return True


async def get_unidades_proyecto_quality_records_paginated(
    report_id: Optional[str] = None,
    page_size: int = 50,
    page_token: Optional[int] = None,
    record_type: Optional[str] = None,
    has_issues: Optional[bool] = None,
    nombre_centro_gestor: Optional[str] = None,
) -> Dict[str, Any]:
    """Retorna detalle uno a uno de registros evaluados con paginacion por cursor numerico."""
    db = _get_db()
    selected_report_id = report_id or _read_latest_report_id(db)

    if selected_report_id is None:
        return {
            "success": False,
            "error": "No existe snapshot de calidad. Ejecuta POST /unidades-proyecto/calidad-datos/analizar.",
        }

    report_ref = db.collection(QUALITY_REPORTS_COLLECTION).document(selected_report_id)
    report_doc = report_ref.get()
    if not report_doc.exists:
        return {
            "success": False,
            "error": f"No se encontro report_id: {selected_report_id}",
        }

    sanitized_page_size = max(1, min(page_size, 200))
    token = page_token if isinstance(page_token, int) else -1

    results: List[Dict[str, Any]] = []
    scanned = 0
    has_more = False
    last_scanned_index = token
    guard = 0

    while len(results) < sanitized_page_size and guard < 6:
        guard += 1
        chunk_size = min(max(sanitized_page_size * 4, 50), 500)
        query = report_ref.collection(QUALITY_RECORDS_SUBCOLLECTION).where("record_index", ">", last_scanned_index).order_by("record_index").limit(chunk_size)
        docs = list(query.stream())

        if not docs:
            has_more = False
            break

        scanned += len(docs)

        for doc in docs:
            row = doc.to_dict() or {}
            idx = int(row.get("record_index", -1))
            if idx > last_scanned_index:
                last_scanned_index = idx
            if _record_matches_filters(row, record_type, has_issues, _normalize_str(nombre_centro_gestor)):
                results.append(row)
                if len(results) >= sanitized_page_size:
                    break

        if len(docs) < chunk_size:
            has_more = len(results) >= sanitized_page_size and last_scanned_index >= 0
            break

        has_more = True

    next_page_token = last_scanned_index if has_more else None

    return {
        "success": True,
        "report_id": selected_report_id,
        "page_size": sanitized_page_size,
        "page_token": token if token >= 0 else None,
        "next_page_token": next_page_token,
        "has_more": bool(has_more),
        "scanned_records": scanned,
        "filters": {
            "record_type": record_type,
            "has_issues": has_issues,
            "nombre_centro_gestor": nombre_centro_gestor,
        },
        "count": len(results),
        "records": results,
    }


async def get_unidades_proyecto_quality_issues_paginated(
    report_id: Optional[str] = None,
    page_size: int = 100,
    page_token: Optional[int] = None,
    record_type: Optional[str] = None,
    severity: Optional[str] = None,
    field: Optional[str] = None,
    nombre_centro_gestor: Optional[str] = None,
) -> Dict[str, Any]:
    """Retorna issues individuales persistidos con paginacion por offset."""
    db = _get_db()
    selected_report_id = report_id or _read_latest_report_id(db)

    if selected_report_id is None:
        return {
            "success": False,
            "error": "No existe snapshot de calidad. Ejecuta POST /unidades-proyecto/calidad-datos/analizar.",
        }

    if severity is not None and severity not in {"S1", "S2", "S3", "S4"}:
        return {
            "success": False,
            "error": "severity debe ser S1, S2, S3 o S4",
        }

    issues_docs = list(db.collection(QUALITY_ISSUES_COLLECTION).where("report_id", "==", selected_report_id).stream())
    rows: List[Dict[str, Any]] = []
    for doc in issues_docs:
        row = doc.to_dict() or {}
        if record_type and (row.get("record_type") or "").lower() != record_type.lower():
            continue
        if severity and row.get("severity") != severity:
            continue
        if field and (row.get("field") or "").lower() != field.lower():
            continue
        if nombre_centro_gestor:
            center = _normalize_str(row.get("nombre_centro_gestor"))
            if center is None or center.lower() != _normalize_str(nombre_centro_gestor).lower():
                continue
        rows.append(row)

    rows.sort(
        key=lambda item: (
            -SEVERITY_RANK.get(item.get("severity"), 0),
            str(item.get("record_uid") or ""),
            str(item.get("field") or ""),
        )
    )

    size = max(1, min(page_size, 200))
    offset = max(0, page_token or 0)
    paged = rows[offset: offset + size]
    next_token = offset + size if offset + size < len(rows) else None

    return {
        "success": True,
        "report_id": selected_report_id,
        "filters": {
            "record_type": record_type,
            "severity": severity,
            "field": field,
            "nombre_centro_gestor": nombre_centro_gestor,
        },
        "count": len(paged),
        "total_issues": len(rows),
        "page_size": size,
        "page_token": offset,
        "next_page_token": next_token,
        "has_more": next_token is not None,
        "issues": paged,
    }


async def get_unidades_proyecto_quality_missing_centros_paginated(
    report_id: Optional[str] = None,
    page_size: int = 100,
    page_token: Optional[int] = None,
    record_type: Optional[str] = None,
) -> Dict[str, Any]:
    """Lista candidatos de corrección donde nombre_centro_gestor no fue encontrado."""
    db = _get_db()
    selected_report_id = report_id or _read_latest_report_id(db)

    if selected_report_id is None:
        return {
            "success": False,
            "error": "No existe snapshot de calidad. Ejecuta POST /unidades-proyecto/calidad-datos/analizar.",
        }

    report_ref = db.collection(QUALITY_REPORTS_COLLECTION).document(selected_report_id)
    report_doc = report_ref.get()
    if not report_doc.exists:
        return {
            "success": False,
            "error": f"No se encontro report_id: {selected_report_id}",
        }

    docs = list(report_ref.collection(QUALITY_RECORDS_SUBCOLLECTION).stream())
    rows: List[Dict[str, Any]] = []
    for doc in docs:
        row = doc.to_dict() or {}
        if row.get("nombre_centro_gestor_source") != "not_found":
            continue

        if record_type and (row.get("record_type") or "").lower() != record_type.lower():
            continue

        rows.append(
            {
                "report_id": selected_report_id,
                "record_uid": row.get("record_uid"),
                "record_type": row.get("record_type"),
                "source_collection": row.get("source_collection"),
                "source_doc_id": row.get("source_doc_id"),
                "upid": row.get("upid"),
                "intervencion_id": row.get("intervencion_id"),
                "nombre_centro_gestor": row.get("nombre_centro_gestor"),
                "nombre_centro_gestor_source": row.get("nombre_centro_gestor_source"),
                "issues_count": row.get("issues_count", 0),
                "max_severity": row.get("max_severity"),
                "focus_fields": row.get("focus_fields", {}),
                "suggested_fix": "Agregar campo nombre_centro_gestor en documento fuente",
            }
        )

    rows.sort(key=lambda item: (str(item.get("record_type") or ""), str(item.get("source_doc_id") or "")))

    size = max(1, min(page_size, 200))
    offset = max(0, page_token or 0)
    paged = rows[offset: offset + size]
    next_token = offset + size if offset + size < len(rows) else None

    by_type = {
        "unidad": len([r for r in rows if r.get("record_type") == "unidad"]),
        "intervencion": len([r for r in rows if r.get("record_type") == "intervencion"]),
    }

    return {
        "success": True,
        "report_id": selected_report_id,
        "count": len(paged),
        "total_candidates": len(rows),
        "by_type": by_type,
        "filters": {
            "record_type": record_type,
            "source": "nombre_centro_gestor_source=not_found",
        },
        "page_size": size,
        "page_token": offset,
        "next_page_token": next_token,
        "has_more": next_token is not None,
        "candidates": paged,
    }


async def get_unidades_proyecto_quality_metrics(
    nombre_centro_gestor: Optional[str] = None,
    history_limit: Optional[int] = None,
) -> Dict[str, Any]:
    """Compatibilidad legacy: ahora retorna resumen desde snapshot (sin payload masivo de registros)."""
    return await get_unidades_proyecto_quality_summary(
        report_id=None,
        history_limit=history_limit or 10,
        auto_generate=True,
        nombre_centro_gestor=nombre_centro_gestor,
    )

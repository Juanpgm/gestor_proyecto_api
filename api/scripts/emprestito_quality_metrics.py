"""Calidad de datos de Empréstito con snapshots persistidos y detalle paginado.

Evalúa calidad sobre las 6 colecciones de empréstito:
- contratos_emprestito
- procesos_emprestito
- ordenes_compra_emprestito
- convenios_transferencias_emprestito
- pagos_emprestito
- rpc_contratos_emprestito

Modelado desde unidades_proyecto_quality_metrics.py (DQS scoring, severidades S1-S4, ISO/DAMA).
"""

from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import uuid
import logging
from typing import Any, Dict, List, Optional

from database.firebase_config import get_firestore_client

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Colecciones Firestore
# ---------------------------------------------------------------------------
EMPRESTITO_QUALITY_REPORTS = "emprestito_quality_reports"
EMPRESTITO_QUALITY_LATEST = "emprestito_quality_latest"
EMPRESTITO_QUALITY_RECORDS = "emprestito_quality_records"
EMPRESTITO_QUALITY_ISSUES = "emprestito_quality_issues"

# Colecciones fuente
SOURCE_COLLECTIONS = {
    "contrato": "contratos_emprestito",
    "proceso": "procesos_emprestito",
    "orden_compra": "ordenes_compra_emprestito",
    "convenio": "convenios_transferencias_emprestito",
    "pago": "pagos_emprestito",
    "rpc": "rpc_contratos_emprestito",
}

# ---------------------------------------------------------------------------
# Severidades y DQS (mismo sistema que unidades_proyecto_quality_metrics)
# ---------------------------------------------------------------------------
SEVERITY_DESCRIPTIONS = {
    "S1": "Critico",
    "S2": "Alto",
    "S3": "Medio",
    "S4": "Bajo",
}

SEVERITY_RANK = {"S1": 4, "S2": 3, "S3": 2, "S4": 1}

SEVERITY_WEIGHTS = {"S1": 0.40, "S2": 0.30, "S3": 0.20, "S4": 0.10}

# ---------------------------------------------------------------------------
# Campos requeridos por tipo de registro
# ---------------------------------------------------------------------------
REQUIRED_FIELDS = {
    "contrato": ["referencia_contrato", "estado_contrato", "nombre_centro_gestor"],
    "proceso": ["referencia_proceso", "nombre_centro_gestor", "plataforma"],
    "orden_compra": ["numero_orden", "nombre_centro_gestor"],
    "convenio": ["referencia_contrato", "nombre_centro_gestor"],
    "pago": ["referencia_contrato", "monto_pagado"],
    "rpc": ["numero_rpc", "beneficiario_nombre"],
}

# Campos numéricos que deben ser válidos (>= 0) si existen
NUMERIC_FIELDS = {
    "contrato": ["valor_contrato", "valor_adiciones"],
    "proceso": ["valor_publicacion", "valor_proyectado"],
    "orden_compra": ["valor_orden"],
    "convenio": ["valor_convenio"],
    "pago": ["monto_pagado"],
    "rpc": [],
}

# Campo que identifica cada tipo de registro
IDENTIFIER_FIELD = {
    "contrato": "referencia_contrato",
    "proceso": "referencia_proceso",
    "orden_compra": "numero_orden",
    "convenio": "referencia_contrato",
    "pago": "referencia_contrato",
    "rpc": "numero_rpc",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _normalize_str(value: Any) -> Optional[str]:
    if value is None:
        return None
    s = str(value).strip()
    return s if s else None


def _now_colombia_iso() -> str:
    return datetime.now(ZoneInfo("America/Bogota")).isoformat()


def _get_db():
    db = get_firestore_client()
    if db is None:
        raise RuntimeError("No se pudo conectar a Firestore")
    return db


def _safe_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def _extract_centro_gestor(doc_data: Dict[str, Any]) -> Optional[str]:
    for field in ["nombre_centro_gestor", "nombreCentroGestor", "centro_gestor"]:
        val = _normalize_str(doc_data.get(field))
        if val is not None:
            return val
    return None


def _classify_dqs(score: float) -> Dict[str, str]:
    if score >= 95:
        return {"status": "optimo", "semaforo": "verde", "label": "Optimo"}
    if score >= 85:
        return {"status": "aceptable", "semaforo": "amarillo", "label": "Aceptable"}
    return {"status": "critico", "semaforo": "rojo", "label": "Critico"}


def _severity_from_issues(issues: List[Dict[str, Any]]) -> Optional[str]:
    if not issues:
        return None
    return max((i.get("severity", "S4") for i in issues), key=lambda s: SEVERITY_RANK.get(s, 0))


def _build_issue(field: str, severity: str, reason: str, record_type: str) -> Dict[str, Any]:
    return {
        "field": field,
        "severity": severity,
        "severity_label": SEVERITY_DESCRIPTIONS.get(severity, severity),
        "reason": reason,
        "record_type": record_type,
    }


def _volume_band(affected_pct: float) -> str:
    if affected_pct > 10:
        return "alto"
    if affected_pct >= 1:
        return "medio"
    return "bajo"


def _priority_from_matrix(severity: str, vol_band: str) -> Dict[str, str]:
    matrix = {
        "S1": {"alto": "P1", "medio": "P1", "bajo": "P2"},
        "S2": {"alto": "P1", "medio": "P2", "bajo": "P3"},
        "S3": {"alto": "P2", "medio": "P3", "bajo": "P4"},
        "S4": {"alto": "P3", "medio": "P4", "bajo": "P5"},
    }
    labels = {"P1": "Urgente", "P2": "Alta", "P3": "Media", "P4": "Baja", "P5": "Backlog"}
    code = matrix.get(severity, {}).get(vol_band, "P5")
    return {"code": code, "label": labels[code], "volume_band": vol_band}


def _compute_weighted_dqs(total_records: int, severity_counter: Dict[str, int]) -> Dict[str, Any]:
    if total_records <= 0:
        return {
            "score": 100.0,
            "classification": _classify_dqs(100.0),
            "by_severity": {k: {"count": 0, "weighted_impact": 0.0} for k in SEVERITY_WEIGHTS},
        }
    weighted_impact = 0.0
    by_severity: Dict[str, Dict[str, Any]] = {}
    for sev, count in severity_counter.items():
        impact = (count / total_records) * 100.0
        by_severity[sev] = {
            "count": count,
            "weighted_impact": round(impact * SEVERITY_WEIGHTS.get(sev, 0.1), 2),
        }
        weighted_impact += impact * SEVERITY_WEIGHTS.get(sev, 0.1)
    score = round(max(0.0, 100.0 - weighted_impact), 2)
    return {
        "score": score,
        "classification": _classify_dqs(score),
        "by_severity": by_severity,
        "raw": {"total_records": total_records},
    }


# ---------------------------------------------------------------------------
# Evaluación de un documento
# ---------------------------------------------------------------------------
def _evaluate_document(doc_data: Dict[str, Any], record_type: str) -> List[Dict[str, Any]]:
    """Evalúa un documento y retorna lista de issues encontrados."""
    issues: List[Dict[str, Any]] = []

    # 1. Campos requeridos faltantes
    for field in REQUIRED_FIELDS.get(record_type, []):
        if _normalize_str(doc_data.get(field)) is None:
            issues.append(_build_issue(field, "S2", "missing_required", record_type))

    # 2. Campos numéricos inválidos
    for field in NUMERIC_FIELDS.get(record_type, []):
        raw = doc_data.get(field)
        if raw is not None:
            num = _safe_float(raw)
            if num is None:
                issues.append(_build_issue(field, "S3", "invalid_numeric", record_type))
            elif num < 0:
                issues.append(_build_issue(field, "S3", "negative_value", record_type))

    return issues


# ---------------------------------------------------------------------------
# Generación del reporte completo
# ---------------------------------------------------------------------------
async def generate_emprestito_quality_report(
    nombre_centro_gestor: Optional[str] = None,
    persist: bool = True,
) -> Dict[str, Any]:
    """Genera snapshot completo de calidad de empréstito y persiste en Firestore."""
    db = _get_db()
    center_filter = _normalize_str(nombre_centro_gestor)
    generated_at = _now_colombia_iso()
    report_id = f"emp-quality-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6]}"

    # Cargar procesos para validación de integridad referencial
    procesos_refs: set = set()
    try:
        for doc in db.collection("procesos_emprestito").stream():
            data = doc.to_dict() or {}
            ref = _normalize_str(data.get("referencia_proceso"))
            if ref:
                procesos_refs.add(ref)
    except Exception as e:
        logger.warning(f"No se pudieron cargar procesos para validación cruzada: {e}")

    contratos_refs: set = set()
    try:
        for doc in db.collection("contratos_emprestito").stream():
            data = doc.to_dict() or {}
            ref = _normalize_str(data.get("referencia_contrato"))
            if ref:
                contratos_refs.add(ref)
    except Exception as e:
        logger.warning(f"No se pudieron cargar contratos para validación cruzada: {e}")

    records: List[Dict[str, Any]] = []
    summary: Dict[str, Any] = {
        "total_records": 0,
        "records_with_issues": 0,
        "records_without_issues": 0,
        "by_severity": {"S1": 0, "S2": 0, "S3": 0, "S4": 0},
        "by_tipo_registro": {},
        "grouped_by_centro_gestor": {},
    }

    record_index = 0
    duplicate_tracker: Dict[str, Dict[str, int]] = {rt: {} for rt in SOURCE_COLLECTIONS}

    # Pre-scan para detectar duplicados
    for record_type, collection_name in SOURCE_COLLECTIONS.items():
        try:
            id_field = IDENTIFIER_FIELD[record_type]
            for doc in db.collection(collection_name).stream():
                data = doc.to_dict() or {}
                ref = _normalize_str(data.get(id_field))
                if ref:
                    duplicate_tracker[record_type][ref] = duplicate_tracker[record_type].get(ref, 0) + 1
        except Exception as e:
            logger.warning(f"Error pre-escaneando {collection_name}: {e}")

    # Evaluar cada colección
    for record_type, collection_name in SOURCE_COLLECTIONS.items():
        tipo_summary = {
            "total": 0,
            "with_issues": 0,
            "missing_required_total": 0,
            "invalid_numeric_total": 0,
            "duplicate_total": 0,
            "orphan_reference_total": 0,
        }

        try:
            docs = list(db.collection(collection_name).stream())
        except Exception as e:
            logger.error(f"Error leyendo {collection_name}: {e}")
            summary["by_tipo_registro"][record_type] = tipo_summary
            continue

        for doc in docs:
            data = doc.to_dict() or {}
            center = _extract_centro_gestor(data) or "Sin centro gestor"

            if center_filter and center.lower() != center_filter.lower():
                continue

            issues = _evaluate_document(data, record_type)

            # 3. Duplicados por referencia
            id_field = IDENTIFIER_FIELD[record_type]
            ref_val = _normalize_str(data.get(id_field))
            if ref_val and duplicate_tracker[record_type].get(ref_val, 0) > 1:
                issues.append(_build_issue(id_field, "S1", "duplicate_reference", record_type))

            # 4. Integridad referencial
            if record_type == "contrato":
                proc_ref = _normalize_str(data.get("referencia_proceso"))
                if proc_ref and proc_ref not in procesos_refs:
                    issues.append(_build_issue("referencia_proceso", "S1", "orphan_process_reference", record_type))
            elif record_type == "pago":
                cont_ref = _normalize_str(data.get("referencia_contrato"))
                if cont_ref and cont_ref not in contratos_refs:
                    issues.append(_build_issue("referencia_contrato", "S1", "orphan_contract_reference", record_type))
            elif record_type == "orden_compra":
                proc_ref = _normalize_str(data.get("referencia_proceso"))
                if proc_ref and proc_ref not in procesos_refs:
                    issues.append(_build_issue("referencia_proceso", "S2", "orphan_process_reference", record_type))

            severity = _severity_from_issues(issues)
            has_issues = bool(issues)

            # Actualizar contadores
            summary["total_records"] += 1
            tipo_summary["total"] += 1
            if has_issues:
                summary["records_with_issues"] += 1
                tipo_summary["with_issues"] += 1
                if severity:
                    summary["by_severity"][severity] = summary["by_severity"].get(severity, 0) + 1
            else:
                summary["records_without_issues"] += 1

            # Contadores detallados
            for issue in issues:
                reason = issue.get("reason", "")
                if reason == "missing_required":
                    tipo_summary["missing_required_total"] += 1
                elif reason in ("invalid_numeric", "negative_value"):
                    tipo_summary["invalid_numeric_total"] += 1
                elif reason == "duplicate_reference":
                    tipo_summary["duplicate_total"] += 1
                elif "orphan" in reason:
                    tipo_summary["orphan_reference_total"] += 1

            # Agrupar por centro gestor
            cg = summary["grouped_by_centro_gestor"].setdefault(center, {
                "total_records": 0,
                "with_issues": 0,
                "by_tipo_registro": {},
                "severity": {"S1": 0, "S2": 0, "S3": 0, "S4": 0},
            })
            cg["total_records"] += 1
            cg["by_tipo_registro"][record_type] = cg["by_tipo_registro"].get(record_type, 0) + 1
            if has_issues:
                cg["with_issues"] += 1
            if severity:
                cg["severity"][severity] = cg["severity"].get(severity, 0) + 1

            records.append({
                "record_uid": f"{record_type}-{doc.id}",
                "record_index": record_index,
                "report_id": report_id,
                "generated_at": generated_at,
                "record_type": record_type,
                "source_collection": collection_name,
                "source_doc_id": doc.id,
                "identifier": ref_val,
                "nombre_centro_gestor": center,
                "issues": issues,
                "issues_count": len(issues),
                "has_issues": has_issues,
                "max_severity": severity,
            })
            record_index += 1

        summary["by_tipo_registro"][record_type] = tipo_summary

    # DQS
    dqs = _compute_weighted_dqs(summary["total_records"], summary["by_severity"])

    # Rules
    rules = _build_rules(summary)

    report_payload = {
        "report_id": report_id,
        "generated_at": generated_at,
        "filtro": {"nombre_centro_gestor": center_filter},
        "framework": {
            "standards": ["ISO 8000", "ISO/IEC 25012", "DAMA-DMBOK"],
            "dimensions": ["completitud", "validez_conformidad", "consistencia", "unicidad", "integridad_referencial"],
            "collections_evaluated": list(SOURCE_COLLECTIONS.values()),
        },
        "summary": summary,
        "dqs": dqs,
        "rules": rules,
    }

    if persist:
        _persist_snapshot(db, report_id, report_payload, records)

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
    }


def _build_rules(summary: Dict[str, Any]) -> List[Dict[str, Any]]:
    rules: List[Dict[str, Any]] = []
    by_tipo = summary.get("by_tipo_registro", {})

    rules_input = []
    for record_type, tipo_data in by_tipo.items():
        total = tipo_data.get("total", 0)
        collection = SOURCE_COLLECTIONS.get(record_type, record_type)

        if tipo_data.get("missing_required_total", 0) > 0:
            rules_input.append((
                f"EMP-{record_type.upper()}-001",
                f"Completitud de campos requeridos en {record_type}",
                collection, "S2",
                tipo_data["missing_required_total"], total,
            ))
        if tipo_data.get("invalid_numeric_total", 0) > 0:
            rules_input.append((
                f"EMP-{record_type.upper()}-002",
                f"Validez de campos numéricos en {record_type}",
                collection, "S3",
                tipo_data["invalid_numeric_total"], total,
            ))
        if tipo_data.get("duplicate_total", 0) > 0:
            rules_input.append((
                f"EMP-{record_type.upper()}-003",
                f"Unicidad de referencia en {record_type}",
                collection, "S1",
                tipo_data["duplicate_total"], total,
            ))
        if tipo_data.get("orphan_reference_total", 0) > 0:
            rules_input.append((
                f"EMP-{record_type.upper()}-004",
                f"Integridad referencial en {record_type}",
                collection, "S1",
                tipo_data["orphan_reference_total"], total,
            ))

    for rule_id, name, collection, severity, affected, total in rules_input:
        affected_pct = round((affected / total) * 100, 2) if total > 0 else 0.0
        vol = _volume_band(affected_pct)
        rules.append({
            "rule_id": rule_id,
            "name": name,
            "collection": collection,
            "severity": {"code": severity, "label": SEVERITY_DESCRIPTIONS.get(severity, severity)},
            "scope": {
                "evaluated_records": total,
                "affected_records": affected,
                "affected_pct": affected_pct,
            },
            "priority": _priority_from_matrix(severity, vol),
        })

    return rules


def _persist_snapshot(db, report_id: str, payload: Dict[str, Any], records: List[Dict[str, Any]]) -> None:
    """Persiste snapshot y registros en Firestore."""
    report_ref = db.collection(EMPRESTITO_QUALITY_REPORTS).document(report_id)
    report_ref.set(payload)

    db.collection(EMPRESTITO_QUALITY_LATEST).document("latest").set({
        "report_id": report_id,
        "generated_at": payload.get("generated_at"),
        "filtro": payload.get("filtro", {}),
    })

    batch = db.batch()
    writes = 0

    for item in records:
        record_uid = item["record_uid"]

        # Registro en colección plana
        flat_ref = db.collection(EMPRESTITO_QUALITY_RECORDS).document(f"{report_id}__{record_uid}")
        batch.set(flat_ref, {**item, "report_id": report_id})
        writes += 1

        # Issues individuales
        for idx, issue in enumerate(item.get("issues", [])):
            issue_id = f"{record_uid}__{idx}"
            issue_payload = {
                "report_id": report_id,
                "record_uid": record_uid,
                "record_type": item.get("record_type"),
                "source_collection": item.get("source_collection"),
                "source_doc_id": item.get("source_doc_id"),
                "identifier": item.get("identifier"),
                "nombre_centro_gestor": item.get("nombre_centro_gestor"),
                "generated_at": item.get("generated_at"),
                **issue,
            }
            issue_ref = db.collection(EMPRESTITO_QUALITY_ISSUES).document(f"{report_id}__{issue_id}")
            batch.set(issue_ref, issue_payload)
            writes += 1

        if writes >= 400:
            batch.commit()
            batch = db.batch()
            writes = 0

    if writes > 0:
        batch.commit()


# ---------------------------------------------------------------------------
# Lectura de reportes
# ---------------------------------------------------------------------------
def _read_latest_report_id(db) -> Optional[str]:
    latest = db.collection(EMPRESTITO_QUALITY_LATEST).document("latest").get()
    if not latest.exists:
        return None
    return (latest.to_dict() or {}).get("report_id")


async def get_emprestito_quality_summary(
    report_id: Optional[str] = None,
    nombre_centro_gestor: Optional[str] = None,
    auto_generate: bool = False,
) -> Dict[str, Any]:
    """Obtiene resumen de calidad desde snapshot persistido."""
    db = _get_db()
    selected = report_id or _read_latest_report_id(db)

    if selected is None and auto_generate:
        gen = await generate_emprestito_quality_report(nombre_centro_gestor=nombre_centro_gestor, persist=True)
        selected = gen.get("report_id")

    if selected is None:
        return {
            "success": False,
            "error": "No existe snapshot de calidad de empréstito. Ejecuta POST /emprestito/quality-control/analyze primero.",
        }

    report_doc = db.collection(EMPRESTITO_QUALITY_REPORTS).document(selected).get()
    if not report_doc.exists:
        return {"success": False, "error": f"No se encontró report_id: {selected}"}

    payload = report_doc.to_dict() or {}

    # quality_score y error_rate derivados del DQS
    dqs = payload.get("dqs", {})
    summ = payload.get("summary", {})
    total = summ.get("total_records", 0)
    with_issues = summ.get("records_with_issues", 0)

    return {
        "success": True,
        "report_id": selected,
        "generated_at": payload.get("generated_at"),
        "quality_score": dqs.get("score", 0),
        "error_rate": round((with_issues / total) * 100, 2) if total > 0 else 0.0,
        "severity_distribution": summ.get("by_severity", {}),
        "framework": payload.get("framework", {}),
        "summary": summ,
        "dqs": dqs,
        "rules": payload.get("rules", []),
    }


async def get_emprestito_quality_records(
    report_id: Optional[str] = None,
    page: int = 1,
    limit: int = 50,
    centro_gestor: Optional[str] = None,
    tipo_registro: Optional[str] = None,
) -> Dict[str, Any]:
    """Retorna registros individuales evaluados con paginación offset."""
    db = _get_db()
    selected = report_id or _read_latest_report_id(db)

    if selected is None:
        return {"success": False, "error": "No existe snapshot de calidad de empréstito."}

    # Leer todos los registros del reporte
    query = db.collection(EMPRESTITO_QUALITY_RECORDS)
    docs = [d for d in query.stream() if (d.to_dict() or {}).get("report_id") == selected]

    all_records = []
    for d in docs:
        data = d.to_dict() or {}
        # Filtros
        if tipo_registro and data.get("record_type") != tipo_registro:
            continue
        if centro_gestor and (data.get("nombre_centro_gestor") or "").lower() != centro_gestor.lower():
            continue
        all_records.append(data)

    all_records.sort(key=lambda r: r.get("record_index", 0))

    # Paginar
    size = max(1, min(limit, 200))
    offset = (max(1, page) - 1) * size
    paged = all_records[offset:offset + size]
    total_pages = max(1, -(-len(all_records) // size))

    return {
        "success": True,
        "report_id": selected,
        "page": page,
        "limit": size,
        "total_records": len(all_records),
        "total_pages": total_pages,
        "has_more": page < total_pages,
        "records": paged,
    }


async def get_emprestito_quality_by_centro_gestor(
    report_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Retorna métricas agrupadas por centro gestor."""
    db = _get_db()
    selected = report_id or _read_latest_report_id(db)

    if selected is None:
        return {"success": False, "error": "No existe snapshot de calidad de empréstito."}

    report_doc = db.collection(EMPRESTITO_QUALITY_REPORTS).document(selected).get()
    if not report_doc.exists:
        return {"success": False, "error": f"No se encontró report_id: {selected}"}

    payload = report_doc.to_dict() or {}
    grouped = (payload.get("summary") or {}).get("grouped_by_centro_gestor", {})

    centros = []
    for name, stats in grouped.items():
        total = stats.get("total_records", 0)
        with_issues = stats.get("with_issues", 0)
        centros.append({
            "nombre_centro_gestor": name,
            "total_records": total,
            "with_issues": with_issues,
            "without_issues": max(total - with_issues, 0),
            "issue_rate_pct": round((with_issues / total) * 100, 2) if total > 0 else 0.0,
            "by_tipo_registro": stats.get("by_tipo_registro", {}),
            "severity": stats.get("severity", {"S1": 0, "S2": 0, "S3": 0, "S4": 0}),
        })

    centros.sort(key=lambda c: c.get("issue_rate_pct", 0), reverse=True)

    return {
        "success": True,
        "report_id": selected,
        "total_centros": len(centros),
        "centros": centros,
    }


async def get_emprestito_quality_stats() -> Dict[str, Any]:
    """Estadísticas globales del sistema de empréstito."""
    db = _get_db()

    stats: Dict[str, Any] = {"collections": {}}

    for record_type, collection_name in SOURCE_COLLECTIONS.items():
        try:
            count = 0
            for _ in db.collection(collection_name).stream():
                count += 1
            stats["collections"][record_type] = {
                "collection": collection_name,
                "total_documents": count,
            }
        except Exception as e:
            stats["collections"][record_type] = {
                "collection": collection_name,
                "total_documents": 0,
                "error": str(e),
            }

    # Info del último reporte de calidad
    latest_id = _read_latest_report_id(db)
    if latest_id:
        report_doc = db.collection(EMPRESTITO_QUALITY_REPORTS).document(latest_id).get()
        if report_doc.exists:
            data = report_doc.to_dict() or {}
            stats["latest_quality_report"] = {
                "report_id": latest_id,
                "generated_at": data.get("generated_at"),
                "quality_score": (data.get("dqs") or {}).get("score"),
                "total_records": (data.get("summary") or {}).get("total_records", 0),
                "records_with_issues": (data.get("summary") or {}).get("records_with_issues", 0),
            }
        else:
            stats["latest_quality_report"] = None
    else:
        stats["latest_quality_report"] = None

    # Contar reportes de calidad existentes
    try:
        reports_count = sum(1 for _ in db.collection(EMPRESTITO_QUALITY_REPORTS).stream())
        stats["total_quality_reports"] = reports_count
    except Exception:
        stats["total_quality_reports"] = 0

    return {"success": True, "stats": stats}

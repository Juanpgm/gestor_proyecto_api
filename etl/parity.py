"""Parity checks between Firestore and Postgres datasets.

Pure, dataset-in/report-out helpers (no DB connection) so they are unit-testable
and reusable from `run_wave1`. The live runner feeds them records pulled from
each side; geometry equality is checked in SQL (ST_Equals) by the runner and the
result fed in as a per-record flag.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Iterable, Mapping


def _normalize(value: Any) -> Any:
    """Stable, comparable representation of a scalar field value."""
    if isinstance(value, Decimal):
        # Normalize trailing zeros so 100 == 100.000.
        return format(value.normalize(), "f")
    if isinstance(value, float):
        return format(Decimal(str(value)).normalize(), "f")
    if isinstance(value, str):
        return value.strip()
    return value


def checksum_record(record: Mapping[str, Any], fields: Iterable[str]) -> str:
    """SHA-256 over the normalized, field-ordered projection of a record."""
    projection = [(f, _normalize(record.get(f))) for f in sorted(fields)]
    payload = json.dumps(projection, ensure_ascii=False, default=str, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass
class ParityReport:
    key_field: str
    total_left: int = 0
    total_right: int = 0
    missing_in_right: list[str] = field(default_factory=list)
    missing_in_left: list[str] = field(default_factory=list)
    changed: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not (self.missing_in_right or self.missing_in_left or self.changed)

    def as_dict(self) -> dict[str, Any]:
        return {
            "key_field": self.key_field,
            "total_left": self.total_left,
            "total_right": self.total_right,
            "missing_in_right": self.missing_in_right,
            "missing_in_left": self.missing_in_left,
            "changed": self.changed,
            "ok": self.ok,
        }


def compare(
    left: Iterable[Mapping[str, Any]],
    right: Iterable[Mapping[str, Any]],
    key_field: str,
    fields: Iterable[str],
) -> ParityReport:
    """Compare two record sets by key and field checksums.

    `left` is typically Firestore, `right` Postgres. Reports keys missing on
    either side and keys whose field checksums diverge.
    """
    fields = list(fields)
    left_map = {str(r[key_field]): r for r in left}
    right_map = {str(r[key_field]): r for r in right}

    report = ParityReport(
        key_field=key_field, total_left=len(left_map), total_right=len(right_map)
    )
    report.missing_in_right = sorted(set(left_map) - set(right_map))
    report.missing_in_left = sorted(set(right_map) - set(left_map))
    for key in sorted(set(left_map) & set(right_map)):
        if checksum_record(left_map[key], fields) != checksum_record(right_map[key], fields):
            report.changed.append(key)
    return report

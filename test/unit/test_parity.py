"""Unit tests for the pure ETL parity helpers."""

from decimal import Decimal

import pytest

from etl.parity import checksum_record, compare

pytestmark = pytest.mark.unit

FIELDS = ["upid", "nombre_up", "presupuesto_base"]


class TestChecksumRecord:
    def test_equal_records_same_checksum(self):
        a = {"upid": "UNP-1", "nombre_up": "A", "presupuesto_base": Decimal("100.00")}
        b = {"upid": "UNP-1", "nombre_up": "A", "presupuesto_base": 100.0}
        assert checksum_record(a, FIELDS) == checksum_record(b, FIELDS)

    def test_trailing_zero_decimal_is_equal(self):
        a = {"upid": "UNP-1", "nombre_up": "A", "presupuesto_base": Decimal("100")}
        b = {"upid": "UNP-1", "nombre_up": "A", "presupuesto_base": Decimal("100.000")}
        assert checksum_record(a, FIELDS) == checksum_record(b, FIELDS)

    def test_difference_changes_checksum(self):
        a = {"upid": "UNP-1", "nombre_up": "A", "presupuesto_base": Decimal("100")}
        b = {"upid": "UNP-1", "nombre_up": "B", "presupuesto_base": Decimal("100")}
        assert checksum_record(a, FIELDS) != checksum_record(b, FIELDS)


class TestCompare:
    def test_identical_sets_are_ok(self):
        left = [{"upid": "UNP-1", "nombre_up": "A", "presupuesto_base": 1},
                {"upid": "UNP-2", "nombre_up": "B", "presupuesto_base": 2}]
        right = list(left)
        report = compare(left, right, "upid", FIELDS)
        assert report.ok
        assert report.total_left == 2 and report.total_right == 2

    def test_detects_missing_and_changed(self):
        left = [{"upid": "UNP-1", "nombre_up": "A", "presupuesto_base": 1},
                {"upid": "UNP-2", "nombre_up": "B", "presupuesto_base": 2}]
        right = [{"upid": "UNP-1", "nombre_up": "A-mod", "presupuesto_base": 1}]
        report = compare(left, right, "upid", FIELDS)
        assert report.missing_in_right == ["UNP-2"]
        assert report.changed == ["UNP-1"]
        assert not report.ok

"""Unit tests for the pure ETL geometry transforms."""

import json

import pytest

from etl.transform_geo import (
    coordinates_in_range,
    is_placeholder_point,
    parse_geometry,
    to_geojson_str,
)

pytestmark = pytest.mark.unit

LINE = {"type": "LineString", "coordinates": [[-76.5, 3.4], [-76.4, 3.5]]}
POINT = {"type": "Point", "coordinates": [-76.5, 3.4]}


class TestParseGeometry:
    def test_passthrough_dict(self):
        assert parse_geometry(LINE) == LINE

    def test_json_string(self):
        assert parse_geometry(json.dumps(LINE)) == LINE

    def test_double_encoded_string(self):
        assert parse_geometry(json.dumps(json.dumps(LINE))) == LINE

    def test_coordinates_as_string(self):
        raw = {"type": "LineString", "coordinates": "[[-76.5, 3.4], [-76.4, 3.5]]"}
        assert parse_geometry(raw) == LINE

    def test_python_literal_single_quotes(self):
        raw = "{'type': 'Point', 'coordinates': [-76.5, 3.4]}"
        assert parse_geometry(raw) == POINT

    @pytest.mark.parametrize("bad", [None, "", "not json", 123, {"type": "Nope", "coordinates": []},
                                     {"coordinates": [1, 2]}, {"type": "Point"}])
    def test_invalid_returns_none(self, bad):
        assert parse_geometry(bad) is None


class TestPlaceholderPoint:
    def test_detects_zero_zero(self):
        assert is_placeholder_point({"type": "Point", "coordinates": [0, 0]}) is True

    def test_real_point_is_not_placeholder(self):
        assert is_placeholder_point(POINT) is False

    def test_line_is_not_placeholder(self):
        assert is_placeholder_point(LINE) is False


class TestCoordinatesInRange:
    def test_valid(self):
        assert coordinates_in_range(LINE) is True

    def test_out_of_range_lng(self):
        assert coordinates_in_range({"type": "Point", "coordinates": [-999, 3.4]}) is False

    def test_empty_is_false(self):
        assert coordinates_in_range({"type": "LineString", "coordinates": []}) is False


class TestToGeojsonStr:
    def test_roundtrip(self):
        s = to_geojson_str(LINE)
        assert json.loads(s) == LINE

    def test_from_string_input(self):
        s = to_geojson_str(json.dumps(POINT))
        assert json.loads(s) == POINT

    def test_invalid_returns_none(self):
        assert to_geojson_str("garbage") is None

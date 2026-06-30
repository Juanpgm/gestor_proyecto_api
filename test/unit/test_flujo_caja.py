"""
Unit tests: flujo de caja Excel parsing.

Regression guard for the month parser: it must accept any "mmm-yy" month
(not a hardcoded fiscal-year range) so the cash-flow report keeps working
across year boundaries.
"""

import io
import os
import sys

import pandas as pd
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from api.scripts.flujo_caja_operations import process_flujo_caja_excel  # noqa: E402


SHEET = "CONTRATOS - Seguimiento"
BASE = {
    'Responsable': ['Ana'],
    'Organismo': ['Secretaria X'],
    'Banco': ['BID'],
    'BP Proyecto': ['BP-001'],
    'Descripcion BP': ['Proyecto demo'],
}


def _to_xlsx_bytes(df: pd.DataFrame) -> bytes:
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name=SHEET, index=False)
    return buffer.getvalue()


def test_parses_months_outside_old_hardcoded_range():
    # jul-26 / ago-26 were outside the previous hardcoded jul-25..jun-26 range.
    df = pd.DataFrame({
        **BASE,
        'Desembolso jul-26': [1000.0],
        'Desembolso ago-26': [2000.0],
    })

    result = process_flujo_caja_excel(_to_xlsx_bytes(df), 'flujo.xlsx')

    assert result['success'] is True
    records = result['data']
    assert len(records) == 2

    by_month = {r['mes']: r for r in records}
    assert set(by_month) == {'jul-26', 'ago-26'}
    assert by_month['jul-26']['periodo'].startswith('2026-07-01')
    assert by_month['ago-26']['periodo'].startswith('2026-08-01')
    assert by_month['jul-26']['desembolso'] == 1000.0


def test_parses_months_across_year_boundary():
    df = pd.DataFrame({
        **BASE,
        'Desembolso dic-27': [500.0],
        'Desembolso ene-28': [750.0],
    })

    result = process_flujo_caja_excel(_to_xlsx_bytes(df), 'flujo.xlsx')

    assert result['success'] is True
    by_month = {r['mes']: r for r in result['data']}
    assert by_month['dic-27']['periodo'].startswith('2027-12-01')
    assert by_month['ene-28']['periodo'].startswith('2028-01-01')


def test_drops_zero_amounts_and_unknown_months():
    df = pd.DataFrame({
        **BASE,
        'Desembolso jul-26': [0.0],          # zero -> excluded
        'Desembolso xxx-26': [1234.0],       # unrecognized month -> dropped
        'Desembolso feb-26': [99.0],         # valid
    })

    result = process_flujo_caja_excel(_to_xlsx_bytes(df), 'flujo.xlsx')

    assert result['success'] is True
    months = {r['mes'] for r in result['data']}
    assert months == {'feb-26'}

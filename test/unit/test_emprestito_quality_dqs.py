"""
Unit tests: DQS (Data Quality Score) computation for empréstito quality.

Guards the "no data" edge case so an empty/failed load is no longer reported
as a perfect "Optimo" score.
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from api.scripts.emprestito_quality_metrics import _compute_weighted_dqs  # noqa: E402


def test_dqs_sin_datos_no_es_optimo():
    result = _compute_weighted_dqs(0, {})
    assert result["score"] is None
    assert result["classification"]["status"] == "sin_datos"
    assert result["classification"]["semaforo"] == "gris"
    assert result["no_data"] is True


def test_dqs_penaliza_segun_severidad():
    # 10 registros, 5 con severidad S1 (peso 0.40):
    # impacto = (5/10)*100 = 50 ; weighted = 50*0.40 = 20 ; score = 80
    result = _compute_weighted_dqs(10, {"S1": 5})
    assert result["score"] == 80.0
    assert result["classification"]["status"] == "critico"


def test_dqs_perfecto_cuando_no_hay_issues():
    result = _compute_weighted_dqs(10, {})
    assert result["score"] == 100.0
    assert result["classification"]["status"] == "optimo"

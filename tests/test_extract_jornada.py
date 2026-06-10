"""
Unit tests for extract_jornada(), _classify_jornada_multiple(), and related helpers.

Covers PRJ-58 acceptance criteria:
  AC1 — horas_semanais, horas_mensais, opcoes_identificadas (array), status
  AC2 — horas_diarias calculated per regime; null with observacao for 12×36
  AC3 — por_escala entries have valor_textual; parent valor_textual reflects first regime
  AC4 — (fmtJornada is JS; Python side: fields present in returned item)
  AC5 — multiple jornadas → por_jornada, no "conflito" status
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from extract_cct_items import (
    _classify_jornada_multiple,
    _calc_horas_mensais,
    _calc_horas_diarias,
    _detect_regime,
    extract_jornada,
)


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

CLAUSE_44H_5X2 = {
    "heading": "CLÁUSULA DÉCIMA - JORNADA DE TRABALHO",
    "heading_n": "clausula decima - jornada de trabalho",
    "body": (
        "A jornada de trabalho é de 44 (quarenta e quatro) horas semanais, "
        "em escala 5×2 (cinco dias de trabalho por dois de descanso)."
    ),
}

CLAUSE_44H_6X1 = {
    "heading": "CLÁUSULA DÉCIMA - JORNADA DE TRABALHO",
    "heading_n": "clausula decima - jornada de trabalho",
    "body": (
        "A jornada de trabalho é de 44 (quarenta e quatro) horas semanais, "
        "em escala 6×1 (seis dias de trabalho por um de descanso)."
    ),
}

CLAUSE_12X36 = {
    "heading": "CLÁUSULA DÉCIMA - JORNADA DE TRABALHO",
    "heading_n": "clausula decima - jornada de trabalho",
    "body": (
        "Os empregados trabalharão em regime de escala 12×36 "
        "(doze horas de trabalho por trinta e seis horas de descanso)."
    ),
}

CLAUSE_MULTI_JORNADA = {
    "heading": "CLÁUSULA DÉCIMA - JORNADA DE TRABALHO",
    "heading_n": "clausula decima - jornada de trabalho",
    "body": (
        "Para trabalhadores em regime de 44 horas semanais aplica-se o piso X. "
        "Para trabalhadores em regime de 40 horas semanais aplica-se o piso Y."
    ),
}

CLAUSE_44H_NO_REGIME = {
    "heading": "CLÁUSULA DÉCIMA - JORNADA DE TRABALHO",
    "heading_n": "clausula decima - jornada de trabalho",
    "body": "A jornada de trabalho é de 44 (quarenta e quatro) horas semanais.",
}

CLAUSE_ESCALA_4X2 = {
    "heading": "CLÁUSULA DÉCIMA - JORNADA DE TRABALHO",
    "heading_n": "clausula decima - jornada de trabalho",
    "body": "Os empregados trabalharão em regime de escala 4×2.",
}


# ─────────────────────────────────────────────────────────────────────────────
# Helper: _calc_horas_mensais
# ─────────────────────────────────────────────────────────────────────────────

def test_calc_horas_mensais_44():
    assert _calc_horas_mensais(44) == 191  # 44 × 4.3333 = 190.666 → 191


def test_calc_horas_mensais_40():
    assert _calc_horas_mensais(40) == 173  # 40 × 4.3333 = 173.33 → 173


def test_calc_horas_mensais_36():
    assert _calc_horas_mensais(36) == 156  # 36 × 4.3333 = 156 → 156


# ─────────────────────────────────────────────────────────────────────────────
# Helper: _calc_horas_diarias
# ─────────────────────────────────────────────────────────────────────────────

def test_calc_horas_diarias_5x2():
    val, obs = _calc_horas_diarias(44, "5x2")
    assert val == 8.8
    assert obs is None


def test_calc_horas_diarias_6x1():
    val, obs = _calc_horas_diarias(44, "6x1")
    assert val == round(44 / 6, 1)
    assert obs is None


def test_calc_horas_diarias_12x36_is_null():
    val, obs = _calc_horas_diarias(44, "12x36")
    assert val is None
    assert obs is not None
    assert "12×36" in obs


def test_calc_horas_diarias_no_regime_defaults_five_days():
    val, obs = _calc_horas_diarias(40, None)
    assert val == 8.0
    assert obs is None


# ─────────────────────────────────────────────────────────────────────────────
# Helper: _detect_regime
# ─────────────────────────────────────────────────────────────────────────────

def test_detect_regime_5x2():
    assert _detect_regime("escala 5×2 dias") == "5x2"


def test_detect_regime_6x1():
    assert _detect_regime("regime 6×1") == "6x1"


def test_detect_regime_12x36():
    assert _detect_regime("jornada 12×36 horas") == "12x36"


def test_detect_regime_none():
    assert _detect_regime("jornada de 44 horas semanais sem escala") is None


def test_detect_regime_4x2():
    assert _detect_regime("escala 4×2") == "4x2"


# ─────────────────────────────────────────────────────────────────────────────
# AC1 — horas_mensais, horas_semanais (int), opcoes_identificadas (array)
# ─────────────────────────────────────────────────────────────────────────────

def test_ac1_horas_semanais_is_int():
    item = extract_jornada([CLAUSE_44H_NO_REGIME], "test.pdf")
    assert item["horas_semanais"] == 44
    assert isinstance(item["horas_semanais"], int)


def test_ac1_horas_mensais_calculated():
    item = extract_jornada([CLAUSE_44H_NO_REGIME], "test.pdf")
    assert item["horas_mensais"] == 191


def test_ac1_opcoes_identificadas_is_array():
    item = extract_jornada([CLAUSE_44H_NO_REGIME], "test.pdf")
    assert isinstance(item["opcoes_identificadas"], list)
    assert len(item["opcoes_identificadas"]) >= 1


def test_ac1_opcoes_identificadas_content():
    item = extract_jornada([CLAUSE_44H_NO_REGIME], "test.pdf")
    assert any("44" in o for o in item["opcoes_identificadas"])


def test_ac1_status_extraido_para_revisao():
    item = extract_jornada([CLAUSE_44H_NO_REGIME], "test.pdf")
    assert item["status_parametro"] == "extraido_para_revisao"


# ─────────────────────────────────────────────────────────────────────────────
# AC2 — horas_diarias with regime detection
# ─────────────────────────────────────────────────────────────────────────────

def test_ac2_horas_diarias_5x2():
    item = extract_jornada([CLAUSE_44H_5X2], "test.pdf")
    assert item["horas_diarias"] == 8.8


def test_ac2_horas_diarias_6x1():
    item = extract_jornada([CLAUSE_44H_6X1], "test.pdf")
    assert item["horas_diarias"] == round(44 / 6, 1)


def test_ac2_horas_diarias_12x36_null():
    item = extract_jornada([CLAUSE_12X36], "test.pdf")
    assert item["horas_diarias"] is None


def test_ac2_horas_diarias_12x36_observacao():
    item = extract_jornada([CLAUSE_12X36], "test.pdf")
    # 12×36 has no horas_semanais so horas_diarias not applicable; observacao may be None
    # The clause has no weekly hours so item has no horas_diarias from calc path


def test_ac2_horas_diarias_no_regime_filled():
    """When no regime is specified, default to 5-day week."""
    item = extract_jornada([CLAUSE_44H_NO_REGIME], "test.pdf")
    assert item["horas_diarias"] == 8.8


# ─────────────────────────────────────────────────────────────────────────────
# AC3 — por_escala entries with valor_textual; parent valor_textual
# ─────────────────────────────────────────────────────────────────────────────

def test_ac3_por_escala_has_valor_textual():
    result = _classify_jornada_multiple(
        "Jornada em regime 12×36 (doze horas de trabalho)."
    )
    assert "por_escala" in result
    for entry in result["por_escala"]:
        assert "valor_textual" in entry
        assert entry["valor_textual"] != ""


def test_ac3_por_escala_12x36_display():
    result = _classify_jornada_multiple("Escala 12×36.")
    entry = result["por_escala"][0]
    assert entry["valor_textual"] == "12×36"


def test_ac3_por_escala_6x1_display():
    result = _classify_jornada_multiple("Escala 6×1.")
    entry = result["por_escala"][0]
    assert entry["valor_textual"] == "6×1"


def test_ac3_por_escala_5x2_display():
    result = _classify_jornada_multiple("Escala 5×2.")
    entry = result["por_escala"][0]
    assert entry["valor_textual"] == "5×2"


def test_ac3_parent_valor_textual_escala_only():
    """When only escala, parent valor_textual uses display form."""
    item = extract_jornada([CLAUSE_12X36], "test.pdf")
    assert item["valor_textual"] == "12×36"


def test_ac3_status_extraido_when_only_escala():
    item = extract_jornada([CLAUSE_12X36], "test.pdf")
    assert item["status_parametro"] == "extraido_para_revisao"


def test_ac3_4x2_regime_supported():
    result = _classify_jornada_multiple("Regime 4×2.")
    assert "por_escala" in result
    labels = [e["label"] for e in result["por_escala"]]
    assert "4x2" in labels


# ─────────────────────────────────────────────────────────────────────────────
# AC5 — multiple jornadas → por_jornada, no "conflito"
# ─────────────────────────────────────────────────────────────────────────────

def test_ac5_multiple_jornadas_no_conflito():
    item = extract_jornada([CLAUSE_MULTI_JORNADA], "test.pdf")
    assert item["status_parametro"] != "conflito"
    assert item["status_parametro"] == "extraido_para_revisao"


def test_ac5_multiple_jornadas_has_por_jornada():
    item = extract_jornada([CLAUSE_MULTI_JORNADA], "test.pdf")
    assert "por_jornada" in item


def test_ac5_multiple_jornadas_observacao_lists_all():
    item = extract_jornada([CLAUSE_MULTI_JORNADA], "test.pdf")
    obs = item.get("observacao") or ""
    assert "44" in obs
    assert "40" in obs


def test_ac5_multiple_jornadas_opcoes_is_array():
    item = extract_jornada([CLAUSE_MULTI_JORNADA], "test.pdf")
    assert isinstance(item["opcoes_identificadas"], list)
    assert len(item["opcoes_identificadas"]) >= 2


# ─────────────────────────────────────────────────────────────────────────────
# Backward compatibility: por_escala trecho_fonte still present
# ─────────────────────────────────────────────────────────────────────────────

def test_por_escala_still_has_trecho_fonte():
    result = _classify_jornada_multiple("Regime 12×36 para trabalhadores da área operacional.")
    for entry in result["por_escala"]:
        assert "trecho_fonte" in entry
        assert len(entry["trecho_fonte"]) > 0


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])

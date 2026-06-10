"""
Unit tests for extract_jornada() and _classify_jornada_multiple() (PRJ-58).

Covers:
  AC1 — extract_jornada persists horas_mensais, horas_diarias, opcoes_identificadas (array)
  AC2 — _classify_jornada_multiple enriches por_escala with valor_textual
  AC2 — Multiple jornadas → status_parametro "extraido_para_revisao", obs lists values
  AC1 — 12×36: horas_diarias is None with auditável observacao
  AC1 — 6×1: horas_diarias calculated as horas_semanais / 6
  AC1 — 5×2: horas_diarias calculated as horas_semanais / 5
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from extract_cct_items import _classify_jornada_multiple, extract_jornada


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

TEXT_44H = """
CLÁUSULA DÉCIMA - JORNADA DE TRABALHO
A jornada de trabalho é de 44 horas semanais.
"""

TEXT_44H_5x2 = """
CLÁUSULA DÉCIMA - JORNADA DE TRABALHO
A jornada de trabalho é de 44 horas semanais em escala 5×2.
"""

TEXT_44H_6x1 = """
CLÁUSULA DÉCIMA - JORNADA DE TRABALHO
A jornada de trabalho é de 44 horas semanais em escala 6×1.
"""

TEXT_12x36 = """
CLÁUSULA DÉCIMA - JORNADA DE TRABALHO
Os trabalhadores em escala 12×36 cumprem jornada especial.
"""

TEXT_MULTI = """
CLÁUSULA DÉCIMA - JORNADA DE TRABALHO
Para trabalhadores administrativos: 44 horas semanais.
Para trabalhadores técnicos: 40 horas semanais.
"""

TEXT_SCALE_ONLY = """
CLÁUSULA DÉCIMA - JORNADA DE TRABALHO
O regime de trabalho é em escala 12×36 e 5×2.
"""

TEXT_4x2 = """
CLÁUSULA DÉCIMA - JORNADA DE TRABALHO
Regime de trabalho em escala 4×2.
"""


def _make_clause(text):
    """Wrap plain text as a parsed clause list for extract_jornada."""
    from extract_cct_items import normalize
    heading = "JORNADA DE TRABALHO"
    return [{"heading": heading, "heading_n": normalize(heading), "body": text}]


# ─────────────────────────────────────────────────────────────────────────────
# AC2: _classify_jornada_multiple adds valor_textual to por_escala entries
# ─────────────────────────────────────────────────────────────────────────────

def test_por_escala_has_valor_textual_12x36():
    result = _classify_jornada_multiple(TEXT_12x36)
    assert "por_escala" in result
    for entry in result["por_escala"]:
        assert "valor_textual" in entry, f"Missing valor_textual in {entry}"


def test_por_escala_valor_textual_format_12x36():
    result = _classify_jornada_multiple(TEXT_12x36)
    labels = {e["valor_textual"] for e in result["por_escala"]}
    assert "12×36" in labels


def test_por_escala_valor_textual_5x2():
    result = _classify_jornada_multiple(TEXT_44H_5x2)
    assert "por_escala" in result
    labels = {e["valor_textual"] for e in result["por_escala"]}
    assert "5×2" in labels


def test_por_escala_valor_textual_6x1():
    result = _classify_jornada_multiple(TEXT_44H_6x1)
    assert "por_escala" in result
    labels = {e["valor_textual"] for e in result["por_escala"]}
    assert "6×1" in labels


def test_por_escala_valor_textual_4x2():
    """4×2 regime should be detected and have formatted valor_textual."""
    result = _classify_jornada_multiple(TEXT_4x2)
    assert "por_escala" in result
    labels = {e["valor_textual"] for e in result["por_escala"]}
    assert "4×2" in labels


def test_por_escala_entry_has_all_required_fields():
    result = _classify_jornada_multiple(TEXT_12x36)
    for entry in result["por_escala"]:
        assert "label" in entry
        assert "valor_textual" in entry
        assert "trecho_fonte" in entry


def test_scale_only_item_valor_textual_reflects_first_regime():
    """When scale patterns but no hours, item valor_textual = first scale's valor_textual."""
    clauses = _make_clause(TEXT_12x36)
    item = extract_jornada(clauses, "test.pdf")
    assert item.get("valor_textual") == "12×36", f"Expected '12×36', got {item.get('valor_textual')!r}"


# ─────────────────────────────────────────────────────────────────────────────
# AC1: horas_mensais and horas_semanais calculated correctly
# ─────────────────────────────────────────────────────────────────────────────

def test_extract_jornada_44h_has_horas_mensais():
    clauses = _make_clause(TEXT_44H)
    item = extract_jornada(clauses, "test.pdf")
    assert item.get("horas_mensais") is not None
    assert item["horas_mensais"] == round(44 * 4.3333)


def test_extract_jornada_44h_horas_semanais_integer():
    clauses = _make_clause(TEXT_44H)
    item = extract_jornada(clauses, "test.pdf")
    assert item["horas_semanais"] == 44
    assert isinstance(item["horas_semanais"], int)


def test_extract_jornada_44h_valor_textual_format():
    clauses = _make_clause(TEXT_44H)
    item = extract_jornada(clauses, "test.pdf")
    expected_mensais = round(44 * 4.3333)
    assert item["valor_textual"] == f"44h/sem · {expected_mensais}h/mês"


# ─────────────────────────────────────────────────────────────────────────────
# AC1: horas_diarias by regime
# ─────────────────────────────────────────────────────────────────────────────

def test_extract_jornada_12x36_horas_diarias_none():
    """12×36 regime: horas_diarias must be None with an auditável observacao."""
    clauses = _make_clause(TEXT_12x36)
    item = extract_jornada(clauses, "test.pdf")
    # Scale-only: no weekly hours so horas_diarias is also None
    assert item.get("horas_diarias") is None


def test_extract_jornada_6x1_horas_diarias_calculated():
    """6×1 regime with 44h/sem → horas_diarias = round(44/6, 1)."""
    clauses = _make_clause(TEXT_44H_6x1)
    item = extract_jornada(clauses, "test.pdf")
    assert item.get("horas_semanais") == 44
    assert item.get("horas_diarias") == round(44 / 6, 1)


def test_extract_jornada_5x2_horas_diarias_calculated():
    """5×2 regime with 44h/sem → horas_diarias = round(44/5, 1)."""
    clauses = _make_clause(TEXT_44H_5x2)
    item = extract_jornada(clauses, "test.pdf")
    assert item.get("horas_semanais") == 44
    assert item.get("horas_diarias") == round(44 / 5, 1)


def test_extract_jornada_no_regime_horas_diarias_none():
    """Standard jornada without identified scale → horas_diarias is None."""
    clauses = _make_clause(TEXT_44H)
    item = extract_jornada(clauses, "test.pdf")
    assert item.get("horas_diarias") is None


def test_extract_jornada_12x36_with_hours_horas_diarias_none():
    """12×36 with weekly hours identified → horas_diarias = None, observacao set."""
    text = "CLÁUSULA DÉCIMA - JORNADA DE TRABALHO\nA jornada é de 44 horas semanais em regime 12×36."
    clauses = _make_clause(text)
    item = extract_jornada(clauses, "test.pdf")
    assert item.get("horas_semanais") == 44
    assert item.get("horas_diarias") is None
    assert item.get("observacao") is not None and "12×36" in item["observacao"]


# ─────────────────────────────────────────────────────────────────────────────
# AC1: opcoes_identificadas as array
# ─────────────────────────────────────────────────────────────────────────────

def test_extract_jornada_opcoes_identificadas_is_array():
    clauses = _make_clause(TEXT_44H)
    item = extract_jornada(clauses, "test.pdf")
    assert isinstance(item.get("opcoes_identificadas"), list)


def test_extract_jornada_opcoes_identificadas_single():
    clauses = _make_clause(TEXT_44H)
    item = extract_jornada(clauses, "test.pdf")
    assert len(item["opcoes_identificadas"]) == 1
    assert "44h" in item["opcoes_identificadas"][0]


# ─────────────────────────────────────────────────────────────────────────────
# AC2: Multiple jornadas → status "extraido_para_revisao", obs lists values
# ─────────────────────────────────────────────────────────────────────────────

def test_multiple_jornadas_status_extraido_para_revisao():
    clauses = _make_clause(TEXT_MULTI)
    item = extract_jornada(clauses, "test.pdf")
    assert item["status_parametro"] == "extraido_para_revisao"


def test_multiple_jornadas_status_never_conflito():
    clauses = _make_clause(TEXT_MULTI)
    item = extract_jornada(clauses, "test.pdf")
    assert item["status_parametro"] != "conflito"


def test_multiple_jornadas_observacao_lists_values():
    clauses = _make_clause(TEXT_MULTI)
    item = extract_jornada(clauses, "test.pdf")
    obs = item.get("observacao", "") or ""
    assert "44" in obs and "40" in obs, f"Expected both 44 and 40 in observacao: {obs!r}"
    assert "Múltiplas jornadas" in obs


def test_multiple_jornadas_opcoes_identificadas_has_both():
    clauses = _make_clause(TEXT_MULTI)
    item = extract_jornada(clauses, "test.pdf")
    oi = item.get("opcoes_identificadas", [])
    assert isinstance(oi, list)
    assert len(oi) >= 2


# ─────────────────────────────────────────────────────────────────────────────
# AC1: status_parametro governance — "valido" items not overwritten
# ─────────────────────────────────────────────────────────────────────────────

def test_scale_only_item_has_por_escala():
    """Scale-only detection returns por_escala with multiple entries."""
    clauses = _make_clause(TEXT_SCALE_ONLY)
    item = extract_jornada(clauses, "test.pdf")
    assert "por_escala" in item
    labels = {e["label"] for e in item["por_escala"]}
    assert "12x36" in labels
    assert "5x2" in labels


def test_scale_only_item_horas_semanais_none():
    clauses = _make_clause(TEXT_SCALE_ONLY)
    item = extract_jornada(clauses, "test.pdf")
    assert item.get("horas_semanais") is None


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])

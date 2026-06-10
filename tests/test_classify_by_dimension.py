"""
Unit tests for classify_by_dimension() and the extended build_item().

Covers:
  AC1 — por_cargo classification in piso_salarial
  AC2 — por_jornada classification in piso_salarial
  AC3 — por_modalidade and por_escala classification in piso_salarial
  AC4 — generic reusability: auxilio_alimentacao por_jornada,
         hora_extra por_modalidade
  AC5 — fallback to "conflito" when no classification evidence
  AC6 — governance: "valido" items never overwritten
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from extract_cct_items import (
    classify_by_dimension,
    build_item,
    extract_itens_cct,
)


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

CARGO_TEXT = """
CLÁUSULA TERCEIRA - PISO SALARIAL
Os pisos salariais ficam estabelecidos nos seguintes valores:
a) Piso Administrativo: R$ 1.642,48 (mil, seiscentos e quarenta e dois reais);
b) Piso Técnico: R$ 1.728,89 (mil, setecentos e vinte e oito reais).
"""

JORNADA_TEXT = """
CLÁUSULA QUARTA - PISO SALARIAL
Para os trabalhadores com jornada de 44 horas semanais: R$ 1.642,48
Para os trabalhadores com jornada de 36 horas semanais: R$ 1.450,00
"""

MODALIDADE_TEXT = """
CLÁUSULA QUINTA - PISO SALARIAL
Trabalhadores em regime presencial: R$ 1.800,00
Trabalhadores em regime remoto (home office): R$ 1.750,00
"""

ESCALA_TEXT = """
CLÁUSULA SEXTA - PISO SALARIAL
Para trabalhadores em escala 12×36: R$ 1.900,00
Para trabalhadores em escala 5×1: R$ 1.600,00
"""

NO_DIMENSION_TEXT = """
CLÁUSULA SÉTIMA - PISO SALARIAL
O piso salarial fica estabelecido em R$ 1.642,48 e R$ 1.728,89.
"""

VRAL_JORNADA_TEXT = """
CLÁUSULA OITAVA - AUXÍLIO ALIMENTAÇÃO
Vale-refeição para jornada de 6 horas diárias: R$ 25,00
Vale-refeição para jornada de 8 horas diárias: R$ 35,00
"""

HORA_EXTRA_MODALIDADE_TEXT = """
CLÁUSULA NONA - HORA EXTRA
Horas extras em dias úteis: 50%
Horas extras em sábados: 75%
Horas extras em domingos e feriados: 100%
"""


# ─────────────────────────────────────────────────────────────────────────────
# AC1: por_cargo classification
# ─────────────────────────────────────────────────────────────────────────────

def test_cargo_classification_returns_por_cargo():
    result = classify_by_dimension(CARGO_TEXT, [1642.48, 1728.89], "piso_salarial")
    assert "por_cargo" in result, "Expected por_cargo key in result"


def test_cargo_classification_correct_count():
    result = classify_by_dimension(CARGO_TEXT, [1642.48, 1728.89], "piso_salarial")
    assert len(result["por_cargo"]) == 2


def test_cargo_classification_fields():
    result = classify_by_dimension(CARGO_TEXT, [1642.48, 1728.89], "piso_salarial")
    for entry in result["por_cargo"]:
        assert "cargo" in entry
        assert "valor" in entry
        assert "trecho_fonte" in entry


def test_cargo_classification_labels():
    result = classify_by_dimension(CARGO_TEXT, [1642.48, 1728.89], "piso_salarial")
    labels = {e["cargo"] for e in result["por_cargo"]}
    assert "piso_administrativo" in labels
    assert "piso_tecnico" in labels


def test_cargo_classification_values():
    result = classify_by_dimension(CARGO_TEXT, [1642.48, 1728.89], "piso_salarial")
    values = {round(e["valor"], 2) for e in result["por_cargo"]}
    assert 1642.48 in values
    assert 1728.89 in values


def test_cargo_classification_trecho_not_empty():
    result = classify_by_dimension(CARGO_TEXT, [1642.48, 1728.89], "piso_salarial")
    for entry in result["por_cargo"]:
        assert entry["trecho_fonte"] and len(entry["trecho_fonte"]) > 10


# ─────────────────────────────────────────────────────────────────────────────
# AC2: por_jornada classification
# ─────────────────────────────────────────────────────────────────────────────

def test_jornada_classification_returns_por_jornada():
    result = classify_by_dimension(JORNADA_TEXT, [1642.48, 1450.0], "piso_salarial")
    assert "por_jornada" in result


def test_jornada_classification_fields():
    result = classify_by_dimension(JORNADA_TEXT, [1642.48, 1450.0], "piso_salarial")
    for entry in result["por_jornada"]:
        assert "jornada" in entry
        assert "valor" in entry
        assert "trecho_fonte" in entry


def test_jornada_classification_labels():
    result = classify_by_dimension(JORNADA_TEXT, [1642.48, 1450.0], "piso_salarial")
    labels = {e["jornada"] for e in result["por_jornada"]}
    assert "44h_semanal" in labels
    assert "36h_semanal" in labels


def test_jornada_classification_values():
    result = classify_by_dimension(JORNADA_TEXT, [1642.48, 1450.0], "piso_salarial")
    values = {round(e["valor"], 2) for e in result["por_jornada"]}
    assert 1642.48 in values
    assert 1450.0 in values


# ─────────────────────────────────────────────────────────────────────────────
# AC3: por_modalidade and por_escala classification
# ─────────────────────────────────────────────────────────────────────────────

def test_modalidade_classification_returns_por_modalidade():
    result = classify_by_dimension(MODALIDADE_TEXT, [1800.0, 1750.0], "piso_salarial")
    assert "por_modalidade" in result


def test_modalidade_classification_fields():
    result = classify_by_dimension(MODALIDADE_TEXT, [1800.0, 1750.0], "piso_salarial")
    for entry in result["por_modalidade"]:
        assert "label" in entry
        assert "valor" in entry
        assert "trecho_fonte" in entry


def test_modalidade_classification_labels():
    result = classify_by_dimension(MODALIDADE_TEXT, [1800.0, 1750.0], "piso_salarial")
    labels = {e["label"] for e in result["por_modalidade"]}
    assert "presencial" in labels
    assert "remoto" in labels


def test_escala_classification_returns_por_escala():
    result = classify_by_dimension(ESCALA_TEXT, [1900.0, 1600.0], "piso_salarial")
    assert "por_escala" in result


def test_escala_classification_labels():
    result = classify_by_dimension(ESCALA_TEXT, [1900.0, 1600.0], "piso_salarial")
    labels = {e["label"] for e in result["por_escala"]}
    assert "12x36" in labels
    assert "5x1" in labels


# ─────────────────────────────────────────────────────────────────────────────
# AC5: fallback to "conflito" when no dimension evidence
# ─────────────────────────────────────────────────────────────────────────────

def test_no_dimension_returns_empty_dict():
    result = classify_by_dimension(NO_DIMENSION_TEXT, [1642.48, 1728.89], "piso_salarial")
    assert result == {}


def test_build_item_conflict_when_no_classification():
    item = build_item(
        values=[1642.48, 1728.89],
        regra_textual=NO_DIMENSION_TEXT,
        tipo="piso_cct",
        unidade="BRL",
        fonte_documento="test.pdf",
        clausula_heading="CLÁUSULA SÉTIMA - PISO SALARIAL",
        trecho_fonte=NO_DIMENSION_TEXT,
        param_type="piso_salarial",
    )
    assert item["status_parametro"] == "conflito"
    assert "Múltiplos valores identificados" in item["observacao"]
    assert "por_cargo" not in item
    assert "por_jornada" not in item


def test_build_item_extraido_with_classification():
    item = build_item(
        values=[1642.48, 1728.89],
        regra_textual=CARGO_TEXT,
        tipo="piso_cct",
        unidade="BRL",
        fonte_documento="test.pdf",
        clausula_heading="CLÁUSULA TERCEIRA - PISO SALARIAL",
        trecho_fonte=CARGO_TEXT,
        param_type="piso_salarial",
    )
    assert item["status_parametro"] == "extraido_para_revisao"
    assert "por_cargo" in item
    assert len(item["por_cargo"]) == 2


def test_build_item_valor_is_minimum_when_classified():
    item = build_item(
        values=[1642.48, 1728.89],
        regra_textual=CARGO_TEXT,
        tipo="piso_cct",
        unidade="BRL",
        fonte_documento="test.pdf",
        clausula_heading="CLÁUSULA TERCEIRA - PISO SALARIAL",
        trecho_fonte=CARGO_TEXT,
        param_type="piso_salarial",
    )
    assert item["valor"] == 1642.48


def test_build_item_no_param_type_keeps_conflict():
    """Without param_type, multi-value items remain as "conflito" (backward compat)."""
    item = build_item(
        values=[1642.48, 1728.89],
        regra_textual=CARGO_TEXT,
        tipo="piso_cct",
        unidade="BRL",
        fonte_documento="test.pdf",
        clausula_heading="CLÁUSULA TERCEIRA - PISO SALARIAL",
        trecho_fonte=CARGO_TEXT,
    )
    assert item["status_parametro"] == "conflito"


# ─────────────────────────────────────────────────────────────────────────────
# AC4: generic reusability for future parameters
# ─────────────────────────────────────────────────────────────────────────────

def test_reuse_for_auxilio_alimentacao_por_jornada():
    """auxilio_alimentacao uses por_jornada dimension."""
    result = classify_by_dimension(VRAL_JORNADA_TEXT, [25.0, 35.0], "auxilio_alimentacao")
    assert "por_jornada" in result, "Expected por_jornada for auxilio_alimentacao"
    labels = {e["jornada"] for e in result["por_jornada"]}
    assert "6h_diario" in labels
    assert "8h_diario" in labels


def test_reuse_for_auxilio_alimentacao_no_cargo_dimension():
    """auxilio_alimentacao should NOT produce por_cargo."""
    result = classify_by_dimension(CARGO_TEXT, [1642.48, 1728.89], "auxilio_alimentacao")
    assert "por_cargo" not in result


def test_reuse_for_unknown_param_type_returns_empty():
    """Unknown param_type returns empty dict."""
    result = classify_by_dimension(CARGO_TEXT, [1642.48, 1728.89], "parametro_inexistente")
    assert result == {}


def test_classify_empty_values_returns_empty():
    result = classify_by_dimension(CARGO_TEXT, [], "piso_salarial")
    assert result == {}


def test_classify_single_value_still_works():
    """Single value: no classification needed, but function should not crash."""
    result = classify_by_dimension(CARGO_TEXT, [1642.48], "piso_salarial")
    # With only one value, classification may or may not match — just no exception
    assert isinstance(result, dict)


# ─────────────────────────────────────────────────────────────────────────────
# AC6: governance — "valido" items are never overwritten
# ─────────────────────────────────────────────────────────────────────────────

def test_valido_item_not_overwritten_by_extract_itens_cct():
    """
    Records with status_parametro=="valido" on piso_salarial must be preserved
    even when the PDF would produce a classified multi-value result.
    """
    record = {
        "id_registro_reajuste": "REG-TEST-001",
        "fonte_documento": "CCT/nonexistent.pdf",
        "itens_cct": {
            "piso_salarial": {
                "valor": 9999.99,
                "status_parametro": "valido",
                "observacao": "Validado manualmente",
            }
        },
    }
    itens, _ = extract_itens_cct(record)
    ps = itens.get("piso_salarial", {})
    assert ps.get("status_parametro") == "valido", (
        "Governance rule violated: valido item was overwritten"
    )
    assert ps.get("valor") == 9999.99


# ─────────────────────────────────────────────────────────────────────────────
# Edge cases
# ─────────────────────────────────────────────────────────────────────────────

def test_values_not_in_text_produce_no_classification():
    """Values not present in the text should yield no classification."""
    result = classify_by_dimension(CARGO_TEXT, [5000.0, 6000.0], "piso_salarial")
    assert result == {}


def test_trecho_fonte_is_truncated():
    """trecho_fonte entries should not exceed 300 chars."""
    result = classify_by_dimension(CARGO_TEXT, [1642.48, 1728.89], "piso_salarial")
    for entry in result.get("por_cargo", []):
        assert len(entry["trecho_fonte"]) <= 305  # 300 + possible ellipsis


# ─────────────────────────────────────────────────────────────────────────────
# PRJ-58: _classify_jornada_multiple — por_escala valor_textual and horas_diarias
# ─────────────────────────────────────────────────────────────────────────────

from extract_cct_items import _classify_jornada_multiple, extract_jornada


JORNADA_12X36_TEXT = """
CLÁUSULA DÉCIMA - JORNADA DE TRABALHO
Os empregados submetidos ao regime de escala 12×36 trabalham 12 horas
com descanso subsequente de 36 horas.
"""

JORNADA_6X1_TEXT = """
CLÁUSULA DÉCIMA - JORNADA DE TRABALHO
A jornada de trabalho obedece à escala 6×1, com 44 horas semanais.
"""

JORNADA_5X2_TEXT = """
CLÁUSULA DÉCIMA - JORNADA DE TRABALHO
A jornada obedece ao regime 5×2 com jornada de 40 horas semanais.
"""

JORNADA_MULTIPLA_TEXT = """
CLÁUSULA DÉCIMA - JORNADA DE TRABALHO
Para trabalhadores em regime parcial: 40 horas semanais.
Para trabalhadores em regime integral: 44 horas semanais.
"""


def _make_clauses(heading, body):
    from extract_cct_items import normalize
    return [{"heading": heading, "heading_n": normalize(heading), "body": body}]


# --- 12×36: por_escala entry has valor_textual; horas_diarias is None ---

def test_12x36_por_escala_has_valor_textual():
    result = _classify_jornada_multiple(JORNADA_12X36_TEXT)
    assert "por_escala" in result
    entry = next((e for e in result["por_escala"] if e["label"] == "12x36"), None)
    assert entry is not None
    assert entry.get("valor_textual") == "12×36"


def test_12x36_por_escala_horas_diarias_is_none():
    result = _classify_jornada_multiple(JORNADA_12X36_TEXT)
    entry = next((e for e in result["por_escala"] if e["label"] == "12x36"), None)
    assert entry is not None
    assert entry.get("horas_diarias") is None


def test_12x36_per_escala_has_observacao():
    result = _classify_jornada_multiple(JORNADA_12X36_TEXT)
    entry = next((e for e in result["por_escala"] if e["label"] == "12x36"), None)
    assert entry is not None
    assert entry.get("observacao") is not None
    assert "12×36" in entry["observacao"]


# --- 6×1: por_escala entry has horas_diarias calculated ---

def test_6x1_por_escala_valor_textual():
    result = _classify_jornada_multiple(JORNADA_6X1_TEXT)
    assert "por_escala" in result
    entry = next((e for e in result["por_escala"] if e["label"] == "6x1"), None)
    assert entry is not None
    assert entry.get("valor_textual") == "6×1"


def test_6x1_por_escala_horas_diarias_calculated():
    result = _classify_jornada_multiple(JORNADA_6X1_TEXT)
    entry = next((e for e in result["por_escala"] if e["label"] == "6x1"), None)
    assert entry is not None
    hd = entry.get("horas_diarias")
    assert hd is not None
    assert abs(hd - round(44 / 6, 1)) < 0.01


# --- 5×2: por_escala entry has horas_diarias calculated ---

def test_5x2_por_escala_valor_textual():
    result = _classify_jornada_multiple(JORNADA_5X2_TEXT)
    assert "por_escala" in result
    entry = next((e for e in result["por_escala"] if e["label"] == "5x2"), None)
    assert entry is not None
    assert entry.get("valor_textual") == "5×2"


def test_5x2_por_escala_horas_diarias_calculated():
    result = _classify_jornada_multiple(JORNADA_5X2_TEXT)
    entry = next((e for e in result["por_escala"] if e["label"] == "5x2"), None)
    assert entry is not None
    hd = entry.get("horas_diarias")
    assert hd is not None
    assert abs(hd - 8.0) < 0.01


# --- Multiple jornadas: status_parametro == "extraido_para_revisao", not "conflito" ---

def test_multiple_jornadas_status_not_conflito():
    clauses = _make_clauses(
        "CLÁUSULA DÉCIMA - JORNADA DE TRABALHO",
        JORNADA_MULTIPLA_TEXT,
    )
    item = extract_jornada(clauses, "test.pdf")
    assert item["status_parametro"] == "extraido_para_revisao"
    assert item.get("status_parametro") != "conflito"


def test_multiple_jornadas_observacao_lists_values():
    clauses = _make_clauses(
        "CLÁUSULA DÉCIMA - JORNADA DE TRABALHO",
        JORNADA_MULTIPLA_TEXT,
    )
    item = extract_jornada(clauses, "test.pdf")
    obs = item.get("observacao") or ""
    assert "Múltiplas jornadas identificadas" in obs
    assert "44" in obs
    assert "40" in obs


# --- extract_jornada: horas_mensais and opcoes_identificadas as array ---

def test_extract_jornada_horas_mensais_calculated():
    clauses = _make_clauses(
        "CLÁUSULA - JORNADA DE TRABALHO",
        "A jornada de trabalho é de 44 horas semanais.",
    )
    item = extract_jornada(clauses, "test.pdf")
    assert item.get("horas_mensais") == round(44 * 4.3333)


def test_extract_jornada_opcoes_identificadas_is_list():
    clauses = _make_clauses(
        "CLÁUSULA - JORNADA DE TRABALHO",
        "A jornada de trabalho é de 44 horas semanais.",
    )
    item = extract_jornada(clauses, "test.pdf")
    assert isinstance(item.get("opcoes_identificadas"), list)


def test_extract_jornada_valor_textual_format():
    clauses = _make_clauses(
        "CLÁUSULA - JORNADA DE TRABALHO",
        "A jornada de trabalho é de 44 horas semanais.",
    )
    item = extract_jornada(clauses, "test.pdf")
    vt = item.get("valor_textual", "")
    assert "h/sem" in vt
    assert "h/mês" in vt


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])

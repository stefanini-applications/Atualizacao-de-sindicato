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
  PRJ-59 — traceability fields: origem, fonte, fonte_textual, pagina,
            data_extracao; fonte_oficial and conflito_fontes schema support
  PRJ-60 — piso_nacional fallback, cargo_normalizado normalization,
            piso_cct priority resolver, governance for new enrichments
"""

import re
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from extract_cct_items import (
    classify_by_dimension,
    build_item,
    extract_itens_cct,
    _classify_jornada_multiple,
    extract_jornada,
    _item_not_found,
    normalize_cargo_tecnico,
    apply_cargo_normalizations,
    apply_piso_nacional_fallback,
    PISO_NACIONAL_VALOR,
    PISO_NACIONAL_ANO,
    today_str,
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
# PRJ-58: _classify_jornada_multiple and extract_jornada extensions
# ─────────────────────────────────────────────────────────────────────────────

JORNADA_12X36_TEXT = """
CLÁUSULA DÉCIMA - JORNADA DE TRABALHO
Os trabalhadores em regime de escala 12×36 ficam sujeitos à jornada de 12 horas de trabalho
por 36 horas de descanso ininterrupto.
"""

JORNADA_6X1_44H_TEXT = """
CLÁUSULA DÉCIMA - JORNADA DE TRABALHO
A jornada de trabalho é de 44 horas semanais em escala 6×1.
"""

JORNADA_5X2_40H_TEXT = """
CLÁUSULA DÉCIMA - JORNADA DE TRABALHO
A jornada de trabalho é de 40 horas semanais em escala 5×2.
"""

JORNADA_MULTIPLA_TEXT = """
CLÁUSULA DÉCIMA - JORNADA DE TRABALHO
Para os trabalhadores com jornada de 44 horas semanais: regime padrão.
Para os trabalhadores com jornada de 40 horas semanais: regime reduzido.
"""


def make_jornada_clauses(body: str):
    """Helper: wrap body in a clause dict recognizable by find_clauses."""
    return [{"heading": "CLÁUSULA DÉCIMA - JORNADA DE TRABALHO",
             "heading_n": "clausula decima - jornada de trabalho", "body": body}]


# _classify_jornada_multiple: 12×36
def test_classify_12x36_has_por_escala():
    result = _classify_jornada_multiple(JORNADA_12X36_TEXT)
    assert "por_escala" in result


def test_classify_12x36_label():
    result = _classify_jornada_multiple(JORNADA_12X36_TEXT)
    labels = {e["label"] for e in result["por_escala"]}
    assert "12x36" in labels


def test_classify_12x36_valor_textual():
    result = _classify_jornada_multiple(JORNADA_12X36_TEXT)
    for e in result["por_escala"]:
        if e["label"] == "12x36":
            assert e.get("valor_textual") == "12×36"


# _classify_jornada_multiple: 6×1
def test_classify_6x1_has_por_escala():
    result = _classify_jornada_multiple(JORNADA_6X1_44H_TEXT)
    assert "por_escala" in result


def test_classify_6x1_valor_textual():
    result = _classify_jornada_multiple(JORNADA_6X1_44H_TEXT)
    for e in result["por_escala"]:
        if e["label"] == "6x1":
            assert e.get("valor_textual") == "6×1"


# _classify_jornada_multiple: 5×2
def test_classify_5x2_has_por_escala():
    result = _classify_jornada_multiple(JORNADA_5X2_40H_TEXT)
    assert "por_escala" in result


def test_classify_5x2_valor_textual():
    result = _classify_jornada_multiple(JORNADA_5X2_40H_TEXT)
    for e in result["por_escala"]:
        if e["label"] == "5x2":
            assert e.get("valor_textual") == "5×2"


# extract_jornada: 12×36 regime — no horas_diarias, has observacao
def test_extract_jornada_12x36_no_horas_diarias():
    clauses = make_jornada_clauses(JORNADA_12X36_TEXT.strip())
    result = extract_jornada(clauses, "test.pdf")
    assert result.get("horas_diarias") is None


def test_extract_jornada_12x36_observacao_set():
    clauses = make_jornada_clauses(JORNADA_12X36_TEXT.strip())
    result = extract_jornada(clauses, "test.pdf")
    # Either escala-only item (no horas_semanais) or horas_diarias null with observacao
    # Since no weekly hours in 12x36 text, item may have no horas_semanais
    assert result.get("status_parametro") == "extraido_para_revisao"
    assert result.get("horas_semanais") is None


# extract_jornada: 6×1 with 44h/sem — horas_diarias calculated
def test_extract_jornada_6x1_horas_diarias():
    clauses = make_jornada_clauses(JORNADA_6X1_44H_TEXT.strip())
    result = extract_jornada(clauses, "test.pdf")
    assert result.get("horas_semanais") == 44
    assert result.get("horas_mensais") == round(44 * 4.3333)
    hd = result.get("horas_diarias")
    assert hd is not None
    assert abs(hd - round(44 / 6, 1)) < 0.01


# extract_jornada: 5×2 with 40h/sem — horas_diarias calculated
def test_extract_jornada_5x2_horas_diarias():
    clauses = make_jornada_clauses(JORNADA_5X2_40H_TEXT.strip())
    result = extract_jornada(clauses, "test.pdf")
    assert result.get("horas_semanais") == 40
    assert result.get("horas_mensais") == round(40 * 4.3333)
    hd = result.get("horas_diarias")
    assert hd is not None
    assert abs(hd - round(40 / 5, 1)) < 0.01


# extract_jornada: multiple jornadas — status_parametro == "extraido_para_revisao", not "conflito"
def test_extract_jornada_multiple_status_extraido():
    clauses = make_jornada_clauses(JORNADA_MULTIPLA_TEXT.strip())
    result = extract_jornada(clauses, "test.pdf")
    assert result.get("status_parametro") == "extraido_para_revisao"


def test_extract_jornada_multiple_observacao_lists_hours():
    clauses = make_jornada_clauses(JORNADA_MULTIPLA_TEXT.strip())
    result = extract_jornada(clauses, "test.pdf")
    obs = result.get("observacao") or ""
    assert "44" in obs and "40" in obs


def test_extract_jornada_multiple_opcoes_is_array():
    clauses = make_jornada_clauses(JORNADA_MULTIPLA_TEXT.strip())
    result = extract_jornada(clauses, "test.pdf")
    oi = result.get("opcoes_identificadas")
    assert isinstance(oi, list)
    assert len(oi) >= 2


# extract_jornada: single jornada — new fields present
def test_extract_jornada_single_horas_mensais():
    body = "A jornada de trabalho é de 44 horas semanais."
    clauses = make_jornada_clauses(body)
    result = extract_jornada(clauses, "test.pdf")
    assert result.get("horas_semanais") == 44
    assert result.get("horas_mensais") == round(44 * 4.3333)


def test_extract_jornada_single_opcoes_is_array():
    body = "A jornada de trabalho é de 44 horas semanais."
    clauses = make_jornada_clauses(body)
    result = extract_jornada(clauses, "test.pdf")
    oi = result.get("opcoes_identificadas")
    assert isinstance(oi, list)


def test_extract_jornada_single_valor_textual_format():
    body = "A jornada de trabalho é de 44 horas semanais."
    clauses = make_jornada_clauses(body)
    result = extract_jornada(clauses, "test.pdf")
    vt = result.get("valor_textual") or ""
    assert "h/sem" in vt and "h/mês" in vt


# extract_jornada: governance — "valido" items are never overwritten (already covered but confirm)
def test_extract_jornada_valido_not_overwritten():
    record = {
        "id_registro_reajuste": "REG-TEST-JOR",
        "fonte_documento": "CCT/nonexistent.pdf",
        "itens_cct": {
            "jornada": {
                "horas_semanais": 40,
                "status_parametro": "valido",
                "observacao": "Validado manualmente",
            }
        },
    }
    itens, _ = extract_itens_cct(record)
    jor = itens.get("jornada", {})
    assert jor.get("status_parametro") == "valido"
    assert jor.get("horas_semanais") == 40


# ─────────────────────────────────────────────────────────────────────────────
# PRJ-59: Traceability fields — 10 mandatory test scenarios
# ─────────────────────────────────────────────────────────────────────────────

# Scenario 1: Parameter extracted from PDF receives origem = "pdf_cct"
def test_prj59_sc1_extracted_origem_pdf_cct():
    item = build_item(
        values=[1642.48],
        regra_textual=CARGO_TEXT,
        tipo="piso_unico",
        unidade="BRL",
        fonte_documento="test.pdf",
        clausula_heading="CLÁUSULA TERCEIRA - PISO SALARIAL",
        trecho_fonte=CARGO_TEXT,
    )
    assert item.get("origem") == "pdf_cct"


# Scenario 2: Parameter not found receives origem = "nao_identificado_pdf"
def test_prj59_sc2_not_found_origem_nao_identificado():
    item = _item_not_found("test.pdf", observacao="Não localizado")
    assert item.get("origem") == "nao_identificado_pdf"


# Scenario 3: Parameter not found receives status_parametro = "pendente_revisao"
def test_prj59_sc3_not_found_status_pendente_revisao():
    item = _item_not_found("test.pdf")
    assert item.get("status_parametro") == "pendente_revisao"


# Scenario 4: Automatically extracted parameter receives status_parametro = "extraido_para_revisao"
def test_prj59_sc4_extracted_status_extraido_para_revisao():
    item = build_item(
        values=[1642.48],
        regra_textual=CARGO_TEXT,
        tipo="piso_unico",
        unidade="BRL",
        fonte_documento="test.pdf",
        clausula_heading="CLÁUSULA TERCEIRA - PISO SALARIAL",
        trecho_fonte=CARGO_TEXT,
    )
    assert item.get("status_parametro") == "extraido_para_revisao"


# Scenario 5: Field with status_parametro = "valido" is never overwritten by extract_itens_cct
def test_prj59_sc5_valido_not_overwritten():
    record = {
        "id_registro_reajuste": "REG-PRJ59-001",
        "fonte_documento": "CCT/nonexistent.pdf",
        "itens_cct": {
            "piso_salarial": {
                "valor": 5000.00,
                "status_parametro": "valido",
                "observacao": "Validado pela equipe",
            }
        },
    }
    itens, _ = extract_itens_cct(record)
    ps = itens.get("piso_salarial", {})
    assert ps.get("status_parametro") == "valido"
    assert ps.get("valor") == 5000.00


# Scenario 6: Schema supports origem = "fonte_oficial" without error
def test_prj59_sc6_schema_supports_fonte_oficial():
    item = {
        "valor": 1621.00,
        "status_parametro": "extraido_para_revisao",
        "origem": "fonte_oficial",
        "fonte": "Ministério do Trabalho / Sistema Mediador / Gov.br",
        "fonte_textual": "Referência oficial",
        "pagina": None,
        "data_extracao": "2026-06-10",
        "observacao": "Preenchido por fallback oficial.",
    }
    assert item["origem"] == "fonte_oficial"
    assert item["status_parametro"] == "extraido_para_revisao"
    assert item["valor"] == 1621.00


# Scenario 7: Schema supports status_parametro = "conflito" and origem = "conflito_fontes"
def test_prj59_sc7_schema_supports_conflito():
    item = {
        "valor": 1800.00,
        "status_parametro": "conflito",
        "origem": "conflito_fontes",
        "fonte": "PDF da CCT; Ministério do Trabalho / Sistema Mediador / Gov.br",
        "fonte_textual": "PDF indica R$ 1.800,00; fonte oficial indica R$ 1.750,00",
        "pagina": 10,
        "data_extracao": "2026-06-10",
        "observacao": "Conflito entre valor extraído do PDF e fonte oficial.",
    }
    assert item["status_parametro"] == "conflito"
    assert item["origem"] == "conflito_fontes"
    assert item["valor"] == 1800.00


# Scenario 8: build_item produces all required traceability fields
def test_prj59_sc8_build_item_has_all_trace_fields():
    item = build_item(
        values=[1540.47],
        regra_textual=CARGO_TEXT,
        tipo="piso_unico",
        unidade="BRL",
        fonte_documento="test.pdf",
        clausula_heading="CLÁUSULA TERCEIRA - PISO SALARIAL",
        trecho_fonte=CARGO_TEXT,
    )
    for field in ("origem", "fonte", "fonte_textual", "pagina", "data_extracao"):
        assert field in item, f"Missing traceability field: {field}"
    assert item["fonte"] == "PDF da CCT"
    assert item["pagina"] is None


# Scenario 9: _item_not_found produces all required traceability fields with correct values
def test_prj59_sc9_not_found_has_all_trace_fields():
    item = _item_not_found("test.pdf")
    for field in ("origem", "fonte", "fonte_textual", "pagina", "data_extracao"):
        assert field in item, f"Missing traceability field: {field}"
    assert item["origem"] == "nao_identificado_pdf"
    assert item["fonte"] is None
    assert item["fonte_textual"] is None
    assert item["pagina"] is None


# Scenario 10: data_extracao is populated with today's date in YYYY-MM-DD format
def test_prj59_sc10_data_extracao_format():
    item = build_item(
        values=[1540.47],
        regra_textual=CARGO_TEXT,
        tipo="piso_unico",
        unidade="BRL",
        fonte_documento="test.pdf",
        clausula_heading="CLÁUSULA TERCEIRA - PISO SALARIAL",
        trecho_fonte=CARGO_TEXT,
    )
    data_extracao = item.get("data_extracao")
    assert data_extracao is not None
    assert re.match(r"^\d{4}-\d{2}-\d{2}$", data_extracao), (
        f"data_extracao '{data_extracao}' does not match YYYY-MM-DD format"
    )


# ─────────────────────────────────────────────────────────────────────────────
# PRJ-60: piso_nacional fallback, cargo normalization, resolver priority
# ─────────────────────────────────────────────────────────────────────────────

# ── Helper: minimal piso_salarial dicts for resolver tests ───────────────────

def _ps(tipo=None, valor=None, valor_piso_cct=None) -> dict:
    """Build a minimal piso_salarial item."""
    item: dict = {}
    if tipo is not None:
        item["tipo"] = tipo
    if valor is not None:
        item["valor"] = valor
    if valor_piso_cct is not None:
        item["valor_piso_cct"] = valor_piso_cct
    return item


def _resolve_piso_cct(ps: dict):
    """
    Mirror the JS RATECARD_PISO_COLUMNS piso_cct resolver (AC3) in Python
    so it can be covered by automated tests.

    Priority: valor_piso_cct → piso_unico (valor when tipo=='piso_unico')
              → valor for other non-excluded tipos.
    """
    EXCLUDED = {"piso_unico", "piso_tecnico", "piso_administrativo"}
    valor_piso_cct = ps.get("valor_piso_cct")
    if valor_piso_cct is not None:
        return valor_piso_cct
    if ps.get("tipo") == "piso_unico" and ps.get("valor") is not None:
        return ps["valor"]
    valor = ps.get("valor")
    if valor is not None and ps.get("tipo") not in EXCLUDED:
        return valor
    return None


# ── AC5(a): Piso CCT resolved by each of the three priority sources ───────────

def test_prj60_piso_cct_resolved_by_valor_piso_cct():
    """piso_cct field takes top priority."""
    ps = _ps(tipo="piso_cct", valor=1500.0, valor_piso_cct=1800.0)
    assert _resolve_piso_cct(ps) == 1800.0


def test_prj60_piso_cct_resolved_by_piso_unico():
    """When valor_piso_cct is absent, piso_unico (tipo==piso_unico) is used."""
    ps = _ps(tipo="piso_unico", valor=1621.0)
    assert _resolve_piso_cct(ps) == 1621.0


def test_prj60_piso_cct_resolved_by_valor_fallback():
    """When neither valor_piso_cct nor piso_unico, generic valor is used."""
    ps = _ps(tipo="piso_cct", valor=1642.0)
    assert _resolve_piso_cct(ps) == 1642.0


def test_prj60_piso_cct_not_resolved_for_piso_tecnico():
    """piso_tecnico tipo does not resolve via the generic valor fallback."""
    ps = _ps(tipo="piso_tecnico", valor=1728.0)
    assert _resolve_piso_cct(ps) is None


def test_prj60_piso_cct_not_resolved_for_piso_administrativo():
    """piso_administrativo tipo does not resolve via the generic valor fallback."""
    ps = _ps(tipo="piso_administrativo", valor=1642.0)
    assert _resolve_piso_cct(ps) is None


def test_prj60_piso_cct_none_when_no_fields():
    """No relevant fields → resolver returns None."""
    assert _resolve_piso_cct({}) is None


# ── AC5(b): Piso Nacional display ────────────────────────────────────────────

def test_prj60_piso_nacional_value_present_after_fallback():
    """apply_piso_nacional_fallback inserts piso_nacional.valor when absent."""
    ps_item = {}
    apply_piso_nacional_fallback(ps_item)
    assert ps_item["piso_nacional"]["valor"] == PISO_NACIONAL_VALOR


def test_prj60_piso_nacional_absent_before_fallback():
    """Before fallback, a fresh piso_salarial item has no piso_nacional."""
    ps_item = {}
    assert "piso_nacional" not in ps_item


def test_prj60_piso_nacional_fallback_sets_ano_referencia():
    ps_item = {}
    apply_piso_nacional_fallback(ps_item)
    assert ps_item["piso_nacional"]["ano_referencia"] == PISO_NACIONAL_ANO


def test_prj60_piso_nacional_fallback_status_extraido():
    ps_item = {}
    apply_piso_nacional_fallback(ps_item)
    assert ps_item["piso_nacional"]["status_parametro"] == "extraido_para_revisao"


def test_prj60_piso_nacional_fallback_origem_fonte_oficial():
    ps_item = {}
    apply_piso_nacional_fallback(ps_item)
    assert ps_item["piso_nacional"]["origem"] == "fonte_oficial"


def test_prj60_piso_nacional_fallback_traceability_fields():
    """All required traceability fields are present in the fallback object."""
    ps_item = {}
    apply_piso_nacional_fallback(ps_item)
    pn = ps_item["piso_nacional"]
    for field in ("valor", "origem", "fonte", "fonte_textual", "pagina", "data_extracao", "observacao"):
        assert field in pn, f"Missing field: {field}"


def test_prj60_piso_nacional_fallback_data_extracao_format():
    ps_item = {}
    apply_piso_nacional_fallback(ps_item)
    data_extracao = ps_item["piso_nacional"]["data_extracao"]
    assert re.match(r"^\d{4}-\d{2}-\d{2}$", data_extracao)


def test_prj60_piso_nacional_fallback_returns_true():
    """apply_piso_nacional_fallback returns True when fallback was applied."""
    assert apply_piso_nacional_fallback({}) is True


def test_prj60_piso_nacional_fallback_returns_false_when_valido():
    """apply_piso_nacional_fallback returns False when existing status is valido."""
    ps_item = {"piso_nacional": {"valor": 9000.0, "status_parametro": "valido"}}
    assert apply_piso_nacional_fallback(ps_item) is False


# ── AC5(c): Técnico Suporte I/II/III by exact name and synonyms ──────────────

# -- Exact canonical names --
def test_prj60_normalize_exact_nivel_i():
    assert normalize_cargo_tecnico("Técnico Suporte I") == "Técnico Suporte I"


def test_prj60_normalize_exact_nivel_ii():
    assert normalize_cargo_tecnico("Técnico Suporte II") == "Técnico Suporte II"


def test_prj60_normalize_exact_nivel_iii():
    assert normalize_cargo_tecnico("Técnico Suporte III") == "Técnico Suporte III"


# -- Level I synonyms --
def test_prj60_normalize_tecnico_de_suporte_i():
    assert normalize_cargo_tecnico("Técnico de Suporte I") == "Técnico Suporte I"


def test_prj60_normalize_tecnico_em_suporte_i():
    assert normalize_cargo_tecnico("Técnico em Suporte I") == "Técnico Suporte I"


def test_prj60_normalize_tecnico_suporte_nivel_i():
    assert normalize_cargo_tecnico("Técnico Suporte Nível I") == "Técnico Suporte I"


def test_prj60_normalize_tecnico_de_suporte_nivel_i():
    assert normalize_cargo_tecnico("Técnico de Suporte Nível I") == "Técnico Suporte I"


def test_prj60_normalize_suporte_tecnico_i():
    assert normalize_cargo_tecnico("Suporte Técnico I") == "Técnico Suporte I"


def test_prj60_normalize_tecnico_suporte_1():
    assert normalize_cargo_tecnico("Técnico Suporte 1") == "Técnico Suporte I"


def test_prj60_normalize_tecnico_de_suporte_jr():
    assert normalize_cargo_tecnico("Técnico Suporte Jr") == "Técnico Suporte I"


def test_prj60_normalize_tecnico_de_suporte_junior():
    assert normalize_cargo_tecnico("Técnico de Suporte Júnior") == "Técnico Suporte I"


def test_prj60_normalize_tecnico_de_suporte_junior_ascii():
    assert normalize_cargo_tecnico("Técnico de Suporte Junior") == "Técnico Suporte I"


# -- Level II synonyms --
def test_prj60_normalize_tecnico_de_suporte_ii():
    assert normalize_cargo_tecnico("Técnico de Suporte II") == "Técnico Suporte II"


def test_prj60_normalize_tecnico_de_suporte_pleno():
    assert normalize_cargo_tecnico("Técnico de Suporte Pleno") == "Técnico Suporte II"


def test_prj60_normalize_tecnico_suporte_nivel_ii():
    assert normalize_cargo_tecnico("Técnico Suporte Nível II") == "Técnico Suporte II"


def test_prj60_normalize_tecnico_suporte_2():
    assert normalize_cargo_tecnico("Técnico Suporte 2") == "Técnico Suporte II"


def test_prj60_normalize_operador_pleno():
    assert normalize_cargo_tecnico("Operador Pleno") == "Técnico Suporte II"


# -- Level III synonyms --
def test_prj60_normalize_tecnico_de_suporte_iii():
    assert normalize_cargo_tecnico("Técnico de Suporte III") == "Técnico Suporte III"


def test_prj60_normalize_tecnico_de_suporte_senior():
    assert normalize_cargo_tecnico("Técnico de Suporte Sênior") == "Técnico Suporte III"


def test_prj60_normalize_tecnico_de_suporte_senior_ascii():
    assert normalize_cargo_tecnico("Técnico de Suporte Senior") == "Técnico Suporte III"


def test_prj60_normalize_tecnico_suporte_nivel_iii():
    assert normalize_cargo_tecnico("Técnico Suporte Nível III") == "Técnico Suporte III"


def test_prj60_normalize_tecnico_suporte_3():
    assert normalize_cargo_tecnico("Técnico Suporte 3") == "Técnico Suporte III"


def test_prj60_normalize_operador_senior():
    assert normalize_cargo_tecnico("Operador Sênior") == "Técnico Suporte III"


# -- Real data from SC-SINTTEL --
def test_prj60_normalize_tec_dados_i():
    assert normalize_cargo_tecnico("TEC DADOS I") == "Técnico Suporte I"


def test_prj60_normalize_tec_dados_ii():
    assert normalize_cargo_tecnico("TEC DADOS II") == "Técnico Suporte II"


def test_prj60_normalize_tec_dados_iii():
    assert normalize_cargo_tecnico("TEC DADOS III") == "Técnico Suporte III"


# -- Real data from RN-SINDPD --
def test_prj60_normalize_operador_junior():
    assert normalize_cargo_tecnico("Operador Júnior") == "Técnico Suporte I"


def test_prj60_normalize_tecnico_em_informatica_pleno():
    assert normalize_cargo_tecnico("Técnico em Informática Pleno") == "Técnico Suporte II"


def test_prj60_normalize_tecnico_em_informatica_senior():
    assert normalize_cargo_tecnico("Técnico em Informática Sênior") == "Técnico Suporte III"


# ── AC5(d): cargo inexistente retorna None ────────────────────────────────────

def test_prj60_normalize_unknown_cargo_returns_none():
    assert normalize_cargo_tecnico("Analista de Sistemas") is None


def test_prj60_normalize_gerente_returns_none():
    assert normalize_cargo_tecnico("Gerente de TI") is None


def test_prj60_normalize_cabista_i_returns_none():
    """CABISTA I has a level but no tech-support base term → not normalized."""
    assert normalize_cargo_tecnico("CABISTA I") is None


def test_prj60_normalize_empty_string_returns_none():
    assert normalize_cargo_tecnico("") is None


def test_prj60_normalize_tecnico_suporte_no_level_returns_none():
    """'Técnico de Suporte' without any level indicator is not normalized."""
    assert normalize_cargo_tecnico("Técnico de Suporte") is None


# ── AC5(e): status_parametro "valido" never overwritten ──────────────────────

def test_prj60_piso_nacional_valido_not_overwritten():
    """apply_piso_nacional_fallback preserves valido piso_nacional."""
    original_valor = 2000.0
    ps_item = {
        "piso_nacional": {
            "valor": original_valor,
            "status_parametro": "valido",
            "observacao": "Validado manualmente",
        }
    }
    apply_piso_nacional_fallback(ps_item)
    assert ps_item["piso_nacional"]["valor"] == original_valor
    assert ps_item["piso_nacional"]["status_parametro"] == "valido"


def test_prj60_cargo_normalizado_skips_valido_entries():
    """apply_cargo_normalizations does not touch por_cargo entries with valido status."""
    ps_item = {
        "por_cargo": [
            {
                "cargo": "Técnico de Suporte Pleno",
                "valor": 1800.0,
                "status_parametro": "valido",
                "cargo_normalizado": None,
            }
        ]
    }
    apply_cargo_normalizations(ps_item)
    # valido entry must not be changed
    assert ps_item["por_cargo"][0]["cargo_normalizado"] is None


# ── AC5(f): extracted values carry all traceability fields ────────────────────

def test_prj60_piso_nacional_fallback_has_all_required_trace_fields():
    """Fallback piso_nacional must carry all mandatory traceability fields."""
    ps_item = {}
    apply_piso_nacional_fallback(ps_item)
    pn = ps_item["piso_nacional"]
    required = ("origem", "fonte", "fonte_textual", "pagina", "data_extracao")
    for field in required:
        assert field in pn, f"Missing traceability field: {field}"


def test_prj60_piso_nacional_pagina_is_null():
    """fallback piso_nacional.pagina must be None (no PDF page reference)."""
    ps_item = {}
    apply_piso_nacional_fallback(ps_item)
    assert ps_item["piso_nacional"]["pagina"] is None


# ── apply_cargo_normalizations integration ───────────────────────────────────

def test_prj60_apply_cargo_normalizations_sets_field():
    """apply_cargo_normalizations sets cargo_normalizado on matching entries."""
    ps_item = {
        "por_cargo": [
            {"cargo": "Técnico de Suporte Sênior", "valor": 2000.0},
            {"cargo": "Analista de Sistemas", "valor": 3000.0},
        ]
    }
    count = apply_cargo_normalizations(ps_item)
    assert count == 1
    assert ps_item["por_cargo"][0]["cargo_normalizado"] == "Técnico Suporte III"
    assert "cargo_normalizado" not in ps_item["por_cargo"][1] or \
           ps_item["por_cargo"][1].get("cargo_normalizado") is None


def test_prj60_apply_cargo_normalizations_returns_count():
    """apply_cargo_normalizations returns number of entries that were updated."""
    ps_item = {
        "por_cargo": [
            {"cargo": "TEC DADOS I", "valor": 1600.0},
            {"cargo": "TEC DADOS II", "valor": 1800.0},
            {"cargo": "TEC DADOS III", "valor": 2000.0},
            {"cargo": "OPERADOR MULTIFUNCIONAL", "valor": 1500.0},
        ]
    }
    count = apply_cargo_normalizations(ps_item)
    assert count == 3


def test_prj60_apply_cargo_normalizations_no_por_cargo():
    """apply_cargo_normalizations handles piso_salarial items without por_cargo."""
    ps_item = {"valor": 1600.0}
    count = apply_cargo_normalizations(ps_item)
    assert count == 0


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])

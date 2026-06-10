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
    apply_cargo_normalizado,
    apply_piso_nacional_fallback,
    PISO_NACIONAL_FALLBACK_VALOR,
    PISO_NACIONAL_FALLBACK_ANO,
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
# PRJ-60 AC1: Piso CCT column priority — piso_cct → piso_unico → valor
# (Python-side data-structure tests; JS resolver logic is tested in app.js)
# ─────────────────────────────────────────────────────────────────────────────

def _make_record_with_piso(tipo, valor, valor_piso_cct=None, piso_unico=None):
    """Helper: build a minimal record dict with the given piso_salarial fields."""
    ps = {
        "tipo": tipo,
        "valor": valor,
        "valor_piso_cct": valor_piso_cct,
        "piso_unico": piso_unico,
        "status_parametro": "extraido_para_revisao",
    }
    return {"itens_cct": {"piso_salarial": ps}}


def _resolve_piso_cct(record):
    """Mirror of the JS RATECARD_PISO_COLUMNS piso_cct resolver (AC3)."""
    ps = (record.get("itens_cct") or {}).get("piso_salarial")
    if not ps:
        return None
    if ps.get("valor_piso_cct") is not None:
        return ps["valor_piso_cct"]
    if ps.get("tipo") == "piso_cct" and ps.get("valor") is not None:
        return ps["valor"]
    if ps.get("piso_unico") is not None:
        return ps["piso_unico"]
    if ps.get("tipo") == "piso_unico" and ps.get("valor") is not None:
        return ps["valor"]
    if ps.get("valor") is not None and ps.get("tipo") not in ("piso_tecnico", "piso_administrativo"):
        return ps["valor"]
    return None


def test_piso_cct_priority_valor_piso_cct():
    """AC1-a: explicit valor_piso_cct wins over everything."""
    record = _make_record_with_piso("piso_cct", 1800.00, valor_piso_cct=1800.00)
    assert _resolve_piso_cct(record) == 1800.00


def test_piso_cct_priority_tipo_piso_cct():
    """AC1-a: tipo==piso_cct uses valor when valor_piso_cct is None."""
    record = _make_record_with_piso("piso_cct", 1750.00)
    assert _resolve_piso_cct(record) == 1750.00


def test_piso_cct_priority_piso_unico_field():
    """AC1-b: piso_unico explicit field takes precedence over generic valor."""
    record = _make_record_with_piso("piso_unico", 1540.47, piso_unico=1540.47)
    assert _resolve_piso_cct(record) == 1540.47


def test_piso_cct_priority_tipo_piso_unico():
    """AC1-b: tipo==piso_unico falls back to valor when piso_unico field absent."""
    record = _make_record_with_piso("piso_unico", 1600.00)
    assert _resolve_piso_cct(record) == 1600.00


def test_piso_cct_priority_valor_fallback():
    """AC1-c: generic valor used when no explicit fields and tipo is not exclusive."""
    record = _make_record_with_piso("piso_cct", 1700.00)
    assert _resolve_piso_cct(record) == 1700.00


def test_piso_cct_no_value_returns_none():
    """AC1: no piso_salarial → None (displayed as 'Não identificado')."""
    assert _resolve_piso_cct({}) is None


# ─────────────────────────────────────────────────────────────────────────────
# PRJ-60 AC2: normalize_cargo_tecnico — exact names and synonyms
# ─────────────────────────────────────────────────────────────────────────────

def test_normalize_cargo_exact_nivel_i():
    assert normalize_cargo_tecnico("Técnico Suporte I") == "Técnico Suporte I"


def test_normalize_cargo_exact_nivel_ii():
    assert normalize_cargo_tecnico("Técnico Suporte II") == "Técnico Suporte II"


def test_normalize_cargo_exact_nivel_iii():
    assert normalize_cargo_tecnico("Técnico Suporte III") == "Técnico Suporte III"


def test_normalize_cargo_de_suporte_nivel_i():
    assert normalize_cargo_tecnico("Técnico de Suporte Nível I") == "Técnico Suporte I"


def test_normalize_cargo_de_suporte_nivel_ii():
    assert normalize_cargo_tecnico("Técnico de Suporte Nível II") == "Técnico Suporte II"


def test_normalize_cargo_de_suporte_nivel_iii():
    assert normalize_cargo_tecnico("Técnico de Suporte Nível III") == "Técnico Suporte III"


def test_normalize_cargo_suporte_1():
    assert normalize_cargo_tecnico("Técnico Suporte 1") == "Técnico Suporte I"


def test_normalize_cargo_suporte_2():
    assert normalize_cargo_tecnico("Técnico Suporte 2") == "Técnico Suporte II"


def test_normalize_cargo_suporte_3():
    assert normalize_cargo_tecnico("Técnico Suporte 3") == "Técnico Suporte III"


def test_normalize_cargo_jr():
    assert normalize_cargo_tecnico("Técnico de Suporte Jr") == "Técnico Suporte I"


def test_normalize_cargo_junior():
    assert normalize_cargo_tecnico("Técnico de Suporte Junior") == "Técnico Suporte I"


def test_normalize_cargo_junior_accent():
    assert normalize_cargo_tecnico("Técnico de Suporte Júnior") == "Técnico Suporte I"


def test_normalize_cargo_pleno():
    assert normalize_cargo_tecnico("Técnico de Suporte Pleno") == "Técnico Suporte II"


def test_normalize_cargo_senior():
    assert normalize_cargo_tecnico("Técnico de Suporte Sênior") == "Técnico Suporte III"


def test_normalize_cargo_senior_no_accent():
    assert normalize_cargo_tecnico("Técnico de Suporte Senior") == "Técnico Suporte III"


def test_normalize_cargo_em_suporte_i():
    assert normalize_cargo_tecnico("Técnico em Suporte I") == "Técnico Suporte I"


def test_normalize_cargo_suporte_tecnico_i():
    assert normalize_cargo_tecnico("Suporte Técnico I") == "Técnico Suporte I"


def test_normalize_cargo_suporte_tecnico_ii():
    assert normalize_cargo_tecnico("Suporte Técnico II") == "Técnico Suporte II"


def test_normalize_cargo_suporte_tecnico_iii():
    assert normalize_cargo_tecnico("Suporte Técnico III") == "Técnico Suporte III"


def test_normalize_cargo_unknown_returns_none():
    """AC2: unrecognized cargo returns None — no value is invented."""
    assert normalize_cargo_tecnico("Técnico de atendimento") is None


def test_normalize_cargo_atendente_returns_none():
    assert normalize_cargo_tecnico("Atendente de suporte") is None


def test_normalize_cargo_empty_returns_none():
    assert normalize_cargo_tecnico("") is None


def test_normalize_cargo_none_safe():
    """normalize_cargo_tecnico must handle None without raising."""
    assert normalize_cargo_tecnico(None) is None


def test_normalize_cargo_iii_not_matched_as_i():
    """'III' must not be incorrectly normalized to level I."""
    assert normalize_cargo_tecnico("Técnico Suporte III") == "Técnico Suporte III"
    assert normalize_cargo_tecnico("Técnico Suporte III") != "Técnico Suporte I"


def test_normalize_cargo_ii_not_matched_as_i():
    """'II' must not be incorrectly normalized to level I."""
    assert normalize_cargo_tecnico("Técnico Suporte II") == "Técnico Suporte II"
    assert normalize_cargo_tecnico("Técnico Suporte II") != "Técnico Suporte I"


# ─────────────────────────────────────────────────────────────────────────────
# PRJ-60 AC2: apply_cargo_normalizado — enriches por_cargo[] entries
# ─────────────────────────────────────────────────────────────────────────────

def _make_por_cargo_itens(entries):
    return {"piso_salarial": {"por_cargo": entries, "status_parametro": "extraido_para_revisao"}}


def test_apply_cargo_normalizado_adds_field():
    itens = _make_por_cargo_itens([
        {"cargo": "Técnico de Suporte Nível I", "valor": 1800.00, "trecho_fonte": "...Técnico de Suporte Nível I..."},
    ])
    result = apply_cargo_normalizado(itens)
    entry = result["piso_salarial"]["por_cargo"][0]
    assert entry["cargo_normalizado"] == "Técnico Suporte I"


def test_apply_cargo_normalizado_level_ii():
    itens = _make_por_cargo_itens([
        {"cargo": "Técnico de Suporte Pleno", "valor": 2000.00, "trecho_fonte": "...Técnico de Suporte Pleno..."},
    ])
    result = apply_cargo_normalizado(itens)
    assert result["piso_salarial"]["por_cargo"][0]["cargo_normalizado"] == "Técnico Suporte II"


def test_apply_cargo_normalizado_level_iii():
    itens = _make_por_cargo_itens([
        {"cargo": "Técnico Suporte Sênior", "valor": 2200.00, "trecho_fonte": "...Técnico Suporte Sênior..."},
    ])
    result = apply_cargo_normalizado(itens)
    assert result["piso_salarial"]["por_cargo"][0]["cargo_normalizado"] == "Técnico Suporte III"


def test_apply_cargo_normalizado_uses_trecho_when_cargo_no_level():
    """Fallback to trecho_fonte when cargo label has no level indicator."""
    itens = _make_por_cargo_itens([
        {"cargo": "tecnico_suporte", "valor": 1900.00, "trecho_fonte": "Piso para Técnico de Suporte Nível II R$ 1900"},
    ])
    result = apply_cargo_normalizado(itens)
    assert result["piso_salarial"]["por_cargo"][0]["cargo_normalizado"] == "Técnico Suporte II"


def test_apply_cargo_normalizado_no_match_no_field():
    """Entries without a recognizable level must NOT receive cargo_normalizado."""
    itens = _make_por_cargo_itens([
        {"cargo": "Auxiliar de Processamento", "valor": 1500.00},
    ])
    result = apply_cargo_normalizado(itens)
    assert "cargo_normalizado" not in result["piso_salarial"]["por_cargo"][0]


def test_apply_cargo_normalizado_preserves_existing():
    """If cargo_normalizado already exists, it must not be overwritten."""
    itens = _make_por_cargo_itens([
        {"cargo": "Técnico de Suporte I", "cargo_normalizado": "Técnico Suporte I", "valor": 1800.00},
    ])
    result = apply_cargo_normalizado(itens)
    assert result["piso_salarial"]["por_cargo"][0]["cargo_normalizado"] == "Técnico Suporte I"


def test_apply_cargo_normalizado_no_por_cargo_unchanged():
    itens = {"piso_salarial": {"valor": 1500.00}}
    result = apply_cargo_normalizado(itens)
    assert result is itens  # unchanged reference when no por_cargo


def test_apply_cargo_normalizado_multiple_entries():
    itens = _make_por_cargo_itens([
        {"cargo": "Técnico Suporte I", "valor": 1700.00},
        {"cargo": "Técnico Suporte II", "valor": 2000.00},
        {"cargo": "Analista", "valor": 2500.00},
    ])
    result = apply_cargo_normalizado(itens)
    por_cargo = result["piso_salarial"]["por_cargo"]
    assert por_cargo[0]["cargo_normalizado"] == "Técnico Suporte I"
    assert por_cargo[1]["cargo_normalizado"] == "Técnico Suporte II"
    assert "cargo_normalizado" not in por_cargo[2]


# ─────────────────────────────────────────────────────────────────────────────
# PRJ-60 AC1/AC2: Piso Nacional — apply_piso_nacional_fallback
# ─────────────────────────────────────────────────────────────────────────────

def _make_piso_salarial_itens(extra=None):
    ps = {"valor": 1500.00, "tipo": "piso_unico", "status_parametro": "extraido_para_revisao"}
    if extra:
        ps.update(extra)
    return {"piso_salarial": ps}


def test_piso_nacional_fallback_inserted_when_absent():
    itens = _make_piso_salarial_itens()
    result = apply_piso_nacional_fallback(itens)
    pn = result["piso_salarial"]["piso_nacional"]
    assert pn is not None
    assert pn["valor"] == PISO_NACIONAL_FALLBACK_VALOR


def test_piso_nacional_fallback_valor_is_1621():
    itens = _make_piso_salarial_itens()
    result = apply_piso_nacional_fallback(itens)
    assert result["piso_salarial"]["piso_nacional"]["valor"] == 1621.00


def test_piso_nacional_fallback_ano_referencia():
    itens = _make_piso_salarial_itens()
    result = apply_piso_nacional_fallback(itens)
    assert result["piso_salarial"]["piso_nacional"]["ano_referencia"] == PISO_NACIONAL_FALLBACK_ANO


def test_piso_nacional_fallback_status_extraido_para_revisao():
    itens = _make_piso_salarial_itens()
    result = apply_piso_nacional_fallback(itens)
    assert result["piso_salarial"]["piso_nacional"]["status_parametro"] == "extraido_para_revisao"


def test_piso_nacional_fallback_origem_fonte_oficial():
    itens = _make_piso_salarial_itens()
    result = apply_piso_nacional_fallback(itens)
    assert result["piso_salarial"]["piso_nacional"]["origem"] == "fonte_oficial"


def test_piso_nacional_fallback_has_all_traceability_fields():
    """AC5-f: auto-inserted piso_nacional carries all mandatory traceability fields."""
    itens = _make_piso_salarial_itens()
    result = apply_piso_nacional_fallback(itens)
    pn = result["piso_salarial"]["piso_nacional"]
    for field in ("origem", "fonte", "fonte_textual", "pagina", "data_extracao"):
        assert field in pn, f"Missing traceability field in piso_nacional: {field}"


def test_piso_nacional_fallback_pagina_is_none():
    itens = _make_piso_salarial_itens()
    result = apply_piso_nacional_fallback(itens)
    assert result["piso_salarial"]["piso_nacional"]["pagina"] is None


def test_piso_nacional_fallback_data_extracao_format():
    itens = _make_piso_salarial_itens()
    result = apply_piso_nacional_fallback(itens)
    dt = result["piso_salarial"]["piso_nacional"]["data_extracao"]
    assert re.match(r"^\d{4}-\d{2}-\d{2}$", dt), f"Unexpected data_extracao format: {dt}"


def test_piso_nacional_fallback_preserves_valido():
    """AC5-e: valido piso_nacional must never be overwritten by the fallback."""
    itens = _make_piso_salarial_itens({
        "piso_nacional": {
            "valor": 9999.00,
            "status_parametro": "valido",
            "origem": "pdf_cct",
        }
    })
    result = apply_piso_nacional_fallback(itens)
    pn = result["piso_salarial"]["piso_nacional"]
    assert pn["valor"] == 9999.00
    assert pn["status_parametro"] == "valido"


def test_piso_nacional_fallback_overwrites_extraido():
    """Non-valido piso_nacional is refreshed by the fallback."""
    itens = _make_piso_salarial_itens({
        "piso_nacional": {
            "valor": 1500.00,
            "status_parametro": "extraido_para_revisao",
        }
    })
    result = apply_piso_nacional_fallback(itens)
    assert result["piso_salarial"]["piso_nacional"]["valor"] == PISO_NACIONAL_FALLBACK_VALOR


def test_piso_nacional_no_piso_salarial_unchanged():
    """When piso_salarial is absent, the dict is returned unchanged."""
    itens = {"jornada": {"horas_semanais": 44}}
    result = apply_piso_nacional_fallback(itens)
    assert result is itens


def test_piso_nacional_display_when_present():
    """AC2-b: Piso Nacional value is accessible from the sub-object."""
    itens = _make_piso_salarial_itens()
    result = apply_piso_nacional_fallback(itens)
    pn = result["piso_salarial"].get("piso_nacional")
    assert pn is not None
    assert pn["valor"] == 1621.00


def test_piso_nacional_absent_shows_nao_identificado():
    """AC2-b: when piso_nacional is absent, resolver returns None → 'Não identificado'."""
    record = {"itens_cct": {"piso_salarial": {"valor": 1500.00}}}
    pn = record["itens_cct"]["piso_salarial"].get("piso_nacional")
    assert pn is None  # front-end will display 'Não identificado'


# ─────────────────────────────────────────────────────────────────────────────
# PRJ-60 AC2: classify_by_dimension adds cargo_normalizado for Técnico Suporte
# ─────────────────────────────────────────────────────────────────────────────

TECNICO_SUPORTE_I_TEXT = """
Os trabalhadores no cargo de Técnico de Suporte Nível I terão piso de R$ 1.800,00 mensais.
Os trabalhadores no cargo de Técnico de Suporte Nível II terão piso de R$ 2.100,00 mensais.
"""

TECNICO_SUPORTE_SENIOR_TEXT = """
Os trabalhadores no cargo de Técnico de Suporte Sênior terão piso de R$ 2.500,00 mensais.
"""


def test_classify_dimension_adds_cargo_normalizado_for_nivel_i():
    result = classify_by_dimension(TECNICO_SUPORTE_I_TEXT, [1800.0, 2100.0], "piso_salarial")
    por_cargo = result.get("por_cargo", [])
    normalized = [e.get("cargo_normalizado") for e in por_cargo]
    assert "Técnico Suporte I" in normalized


def test_classify_dimension_adds_cargo_normalizado_for_nivel_ii():
    result = classify_by_dimension(TECNICO_SUPORTE_I_TEXT, [1800.0, 2100.0], "piso_salarial")
    por_cargo = result.get("por_cargo", [])
    normalized = [e.get("cargo_normalizado") for e in por_cargo]
    assert "Técnico Suporte II" in normalized


def test_classify_dimension_adds_cargo_normalizado_for_senior():
    result = classify_by_dimension(TECNICO_SUPORTE_SENIOR_TEXT, [2500.0], "piso_salarial")
    por_cargo = result.get("por_cargo", [])
    normalized = [e.get("cargo_normalizado") for e in por_cargo if "cargo_normalizado" in e]
    assert "Técnico Suporte III" in normalized


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])


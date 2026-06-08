"""
Unit tests for classify_by_dimension (PRJ-54).

Covers:
    AC1 — Classification by cargo for piso_salarial
    AC2 — Classification by jornada for piso_salarial
    AC3 — Classification by modalidade and escala for piso_salarial
    AC4 — Generic / reusable architecture (multiple param_types)
    AC5 — Fallback to "conflito" when no classification evidence
    AC6 — Governance: "valido" items are never overwritten
"""

import pytest

from extract_cct_items import (
    DIMENSION_PATTERNS,
    PARAM_PATTERN_MAP,
    build_item,
    classify_by_dimension,
    extract_piso_salarial,
    merge_itens_cct,
    parse_clauses,
)

# ──────────────────────────────────────────────────────────────────────────────
# Fixtures — realistic CCT clause texts
# ──────────────────────────────────────────────────────────────────────────────

CLAUSE_CARGO = """\
CLÁUSULA DÉCIMA - PISO SALARIAL
Os pisos salariais ficam estabelecidos conforme abaixo:
Piso administrativo: R$ 1.642,48 (hum mil, seiscentos e quarenta e dois reais e quarenta e oito centavos)
Piso técnico: R$ 1.728,89 (hum mil, setecentos e vinte e oito reais e oitenta e nove centavos)
"""

CLAUSE_JORNADA = """\
CLÁUSULA DÉCIMA - PISO SALARIAL
O piso salarial é estabelecido de acordo com a jornada:
44 horas semanais: R$ 1.850,00 mensais
36 horas semanais: R$ 1.540,00 mensais
"""

CLAUSE_MODALIDADE = """\
CLÁUSULA DÉCIMA - PISO SALARIAL
Os valores mínimos são:
Trabalho presencial: R$ 2.100,00
Trabalho remoto: R$ 1.980,00
"""

CLAUSE_ESCALA = """\
CLÁUSULA DÉCIMA - PISO SALARIAL
Regime 12x36: R$ 2.200,00 mensais
Regime 6x1: R$ 1.900,00 mensais
"""

CLAUSE_NO_EVIDENCE = """\
CLÁUSULA DÉCIMA - PISO SALARIAL
O piso salarial fica estabelecido em R$ 1.642,48 ou R$ 1.728,89 conforme negociação.
"""

CLAUSE_SINGLE_VALUE = """\
CLÁUSULA DÉCIMA - PISO SALARIAL
O piso salarial fica estabelecido em R$ 1.642,48 mensais.
"""

# Additional fixtures for reusability / future param types (AC4)

CLAUSE_VR_JORNADA = """\
CLÁUSULA VIGÉSIMA - AUXÍLIO ALIMENTAÇÃO
O auxílio alimentação será:
Jornada de 8 horas: R$ 35,00 por dia
Jornada de 6 horas: R$ 20,00 por dia
"""

CLAUSE_HORA_EXTRA_MODALIDADE = """\
CLÁUSULA DÉCIMA QUINTA - HORA EXTRA
As horas extraordinárias serão remuneradas com os seguintes adicionais:
Dias úteis: 50%
Sábado: 75%
Domingo: 100%
"""

# ──────────────────────────────────────────────────────────────────────────────
# AC1 — por_cargo
# ──────────────────────────────────────────────────────────────────────────────

class TestClassifyByCargo:
    def test_returns_por_cargo_with_two_entries(self):
        result = classify_by_dimension(CLAUSE_CARGO, [1642.48, 1728.89], "piso_salarial")
        assert "por_cargo" in result
        assert len(result["por_cargo"]) == 2

    def test_cargo_entry_has_required_fields(self):
        result = classify_by_dimension(CLAUSE_CARGO, [1642.48, 1728.89], "piso_salarial")
        entry = result["por_cargo"][0]
        assert "cargo" in entry
        assert "valor" in entry
        assert "trecho_fonte" in entry

    def test_cargo_values_match_input(self):
        result = classify_by_dimension(CLAUSE_CARGO, [1642.48, 1728.89], "piso_salarial")
        valores = {round(e["valor"], 2) for e in result["por_cargo"]}
        assert 1642.48 in valores
        assert 1728.89 in valores

    def test_cargo_labels_are_identified(self):
        result = classify_by_dimension(CLAUSE_CARGO, [1642.48, 1728.89], "piso_salarial")
        labels = {e["cargo"] for e in result["por_cargo"]}
        assert "Administrativo" in labels
        assert "Técnico" in labels

    def test_trecho_fonte_is_non_empty(self):
        result = classify_by_dimension(CLAUSE_CARGO, [1642.48, 1728.89], "piso_salarial")
        for entry in result["por_cargo"]:
            assert entry["trecho_fonte"]


# ──────────────────────────────────────────────────────────────────────────────
# AC2 — por_jornada
# ──────────────────────────────────────────────────────────────────────────────

class TestClassifyByJornada:
    def test_returns_por_jornada(self):
        result = classify_by_dimension(CLAUSE_JORNADA, [1850.0, 1540.0], "piso_salarial")
        assert "por_jornada" in result

    def test_jornada_entry_has_required_fields(self):
        result = classify_by_dimension(CLAUSE_JORNADA, [1850.0, 1540.0], "piso_salarial")
        entry = result["por_jornada"][0]
        assert "jornada" in entry
        assert "valor" in entry
        assert "trecho_fonte" in entry

    def test_jornada_labels_detected(self):
        result = classify_by_dimension(CLAUSE_JORNADA, [1850.0, 1540.0], "piso_salarial")
        labels = {e["jornada"] for e in result["por_jornada"]}
        assert any("44h" in l or "36h" in l for l in labels)

    def test_jornada_values_assigned(self):
        result = classify_by_dimension(CLAUSE_JORNADA, [1850.0, 1540.0], "piso_salarial")
        valores = {round(e["valor"], 2) for e in result["por_jornada"]}
        assert 1850.0 in valores or 1540.0 in valores


# ──────────────────────────────────────────────────────────────────────────────
# AC3 — por_modalidade and por_escala
# ──────────────────────────────────────────────────────────────────────────────

class TestClassifyByModalidade:
    def test_returns_por_modalidade(self):
        result = classify_by_dimension(CLAUSE_MODALIDADE, [2100.0, 1980.0], "piso_salarial")
        assert "por_modalidade" in result

    def test_modalidade_entry_has_label_field(self):
        result = classify_by_dimension(CLAUSE_MODALIDADE, [2100.0, 1980.0], "piso_salarial")
        entry = result["por_modalidade"][0]
        assert "label" in entry
        assert "valor" in entry
        assert "trecho_fonte" in entry

    def test_modalidade_labels_detected(self):
        result = classify_by_dimension(CLAUSE_MODALIDADE, [2100.0, 1980.0], "piso_salarial")
        labels = {e["label"] for e in result["por_modalidade"]}
        assert "Presencial" in labels or "Remoto" in labels


class TestClassifyByEscala:
    def test_returns_por_escala(self):
        result = classify_by_dimension(CLAUSE_ESCALA, [2200.0, 1900.0], "piso_salarial")
        assert "por_escala" in result

    def test_escala_entry_has_label_field(self):
        result = classify_by_dimension(CLAUSE_ESCALA, [2200.0, 1900.0], "piso_salarial")
        entry = result["por_escala"][0]
        assert "label" in entry
        assert "valor" in entry
        assert "trecho_fonte" in entry

    def test_escala_labels_detected(self):
        result = classify_by_dimension(CLAUSE_ESCALA, [2200.0, 1900.0], "piso_salarial")
        labels = {e["label"] for e in result["por_escala"]}
        assert "12×36" in labels or "6×1" in labels


# ──────────────────────────────────────────────────────────────────────────────
# AC4 — Generic architecture / reusability
# ──────────────────────────────────────────────────────────────────────────────

class TestGenericArchitecture:
    def test_param_type_not_referenced_in_return_keys(self):
        """Return keys must be dimension-based, never param-specific."""
        result = classify_by_dimension(CLAUSE_CARGO, [1642.48, 1728.89], "piso_salarial")
        for key in result:
            assert key.startswith("por_"), f"Unexpected key: {key}"
            assert "piso" not in key

    def test_param_pattern_map_covers_future_params(self):
        """All future params mentioned in the spec must be in PARAM_PATTERN_MAP."""
        expected = {"auxilio_alimentacao", "hora_extra", "adicional_noturno", "sobreaviso", "plr", "jornada"}
        for param in expected:
            assert param in PARAM_PATTERN_MAP, f"{param} missing from PARAM_PATTERN_MAP"

    def test_dimension_patterns_non_empty(self):
        for dim in ("cargo", "jornada", "modalidade", "escala"):
            assert dim in DIMENSION_PATTERNS
            assert len(DIMENSION_PATTERNS[dim]) > 0

    def test_vr_va_by_jornada_reusability(self):
        """classify_by_dimension with auxilio_alimentacao applies jornada patterns."""
        result = classify_by_dimension(CLAUSE_VR_JORNADA, [35.0, 20.0], "auxilio_alimentacao")
        assert "por_jornada" in result, "Should classify VR/VA by jornada"

    def test_hora_extra_by_modalidade_reusability(self):
        """For hora_extra, PARAM_PATTERN_MAP selects only modalidade dimension."""
        dims = PARAM_PATTERN_MAP["hora_extra"]
        assert "modalidade" in dims
        # Verify cargo is NOT in hora_extra's dimensions
        assert "cargo" not in dims

    def test_single_value_returns_empty(self):
        """classify_by_dimension must return empty dict when values has < 2 items."""
        result = classify_by_dimension(CLAUSE_SINGLE_VALUE, [1642.48], "piso_salarial")
        assert result == {}


# ──────────────────────────────────────────────────────────────────────────────
# AC5 — Fallback to "conflito" when no classification evidence
# ──────────────────────────────────────────────────────────────────────────────

class TestFallbackToConflito:
    def test_classify_returns_empty_without_evidence(self):
        result = classify_by_dimension(CLAUSE_NO_EVIDENCE, [1642.48, 1728.89], "piso_salarial")
        assert result == {}

    def test_build_item_status_conflito_without_classification(self):
        item = build_item(
            values=[1642.48, 1728.89],
            regra_textual=CLAUSE_NO_EVIDENCE,
            tipo="piso_cct",
            unidade="BRL",
            fonte_documento="test.pdf",
            clausula_heading="CLÁUSULA DÉCIMA - PISO SALARIAL",
            trecho_fonte=CLAUSE_NO_EVIDENCE,
            param_type="piso_salarial",
        )
        assert item["status_parametro"] == "conflito"
        assert "por_cargo" not in item
        assert "por_jornada" not in item

    def test_build_item_conflito_observacao_contains_values(self):
        item = build_item(
            values=[1642.48, 1728.89],
            regra_textual=CLAUSE_NO_EVIDENCE,
            tipo="piso_cct",
            unidade="BRL",
            fonte_documento="test.pdf",
            clausula_heading="CLÁUSULA DÉCIMA - PISO SALARIAL",
            trecho_fonte=CLAUSE_NO_EVIDENCE,
            param_type="piso_salarial",
        )
        assert "1642.48" in item["observacao"] or "1728.89" in item["observacao"]


# ──────────────────────────────────────────────────────────────────────────────
# AC1 (extended) — build_item integration for classified cargo
# ──────────────────────────────────────────────────────────────────────────────

class TestBuildItemWithClassification:
    def test_status_is_extraido_para_revisao_when_classified(self):
        item = build_item(
            values=[1642.48, 1728.89],
            regra_textual=CLAUSE_CARGO,
            tipo="piso_cct",
            unidade="BRL",
            fonte_documento="test.pdf",
            clausula_heading="CLÁUSULA DÉCIMA - PISO SALARIAL",
            trecho_fonte=CLAUSE_CARGO,
            param_type="piso_salarial",
        )
        assert item["status_parametro"] == "extraido_para_revisao"

    def test_por_cargo_present_in_item(self):
        item = build_item(
            values=[1642.48, 1728.89],
            regra_textual=CLAUSE_CARGO,
            tipo="piso_cct",
            unidade="BRL",
            fonte_documento="test.pdf",
            clausula_heading="CLÁUSULA DÉCIMA - PISO SALARIAL",
            trecho_fonte=CLAUSE_CARGO,
            param_type="piso_salarial",
        )
        assert "por_cargo" in item
        assert isinstance(item["por_cargo"], list)
        assert len(item["por_cargo"]) >= 1

    def test_top_level_valor_is_minimum_when_classified(self):
        item = build_item(
            values=[1728.89, 1642.48],
            regra_textual=CLAUSE_CARGO,
            tipo="piso_cct",
            unidade="BRL",
            fonte_documento="test.pdf",
            clausula_heading="CLÁUSULA DÉCIMA - PISO SALARIAL",
            trecho_fonte=CLAUSE_CARGO,
            param_type="piso_salarial",
        )
        assert round(item["valor"], 2) == 1642.48, "Top-level valor must be the minimum"

    def test_no_classification_without_param_type(self):
        """Without param_type, multiple values must fall back to 'conflito'."""
        item = build_item(
            values=[1642.48, 1728.89],
            regra_textual=CLAUSE_CARGO,
            tipo="piso_cct",
            unidade="BRL",
            fonte_documento="test.pdf",
            clausula_heading="CLÁUSULA DÉCIMA - PISO SALARIAL",
            trecho_fonte=CLAUSE_CARGO,
        )
        assert item["status_parametro"] == "conflito"
        assert "por_cargo" not in item


# ──────────────────────────────────────────────────────────────────────────────
# AC6 — Governance: validated items are never overwritten
# ──────────────────────────────────────────────────────────────────────────────

class TestGovernance:
    def test_merge_preserves_valido_items(self):
        existing = {
            "piso_salarial": {
                "valor": 2000.0,
                "status_parametro": "valido",
                "data_validacao": "2025-01-01T00:00:00",
            }
        }
        new_items = {
            "piso_salarial": {
                "valor": 1642.48,
                "status_parametro": "extraido_para_revisao",
                "por_cargo": [{"cargo": "Técnico", "valor": 1642.48, "trecho_fonte": "..."}],
            }
        }
        merged = merge_itens_cct(existing, new_items)
        assert merged["piso_salarial"]["status_parametro"] == "valido"
        assert merged["piso_salarial"]["valor"] == 2000.0
        assert "por_cargo" not in merged["piso_salarial"]

    def test_merge_overwrites_conflito_items(self):
        existing = {
            "piso_salarial": {
                "valor": None,
                "status_parametro": "conflito",
            }
        }
        new_items = {
            "piso_salarial": {
                "valor": 1642.48,
                "status_parametro": "extraido_para_revisao",
                "por_cargo": [{"cargo": "Administrativo", "valor": 1642.48, "trecho_fonte": "..."}],
            }
        }
        merged = merge_itens_cct(existing, new_items)
        assert merged["piso_salarial"]["status_parametro"] == "extraido_para_revisao"

    def test_extract_piso_salarial_respects_governance(self):
        """
        Even if the PDF has multiple salary values, a record with status 'valido'
        must not be overwritten by extract_itens_cct.
        """
        clauses = parse_clauses(CLAUSE_CARGO)
        existing = {"piso_salarial": {"valor": 9999.0, "status_parametro": "valido"}}
        new_item = extract_piso_salarial(clauses, "test.pdf")
        merged = merge_itens_cct(existing, {"piso_salarial": new_item})
        assert merged["piso_salarial"]["valor"] == 9999.0
        assert merged["piso_salarial"]["status_parametro"] == "valido"

"""
Unit tests for classify_by_dimension and related build_item/extract_piso_salarial
changes introduced in PRJ-54.

Covers AC1–AC6.
"""

import sys
import os
import inspect
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from extract_cct_items import (
    classify_by_dimension,
    build_item,
    extract_piso_salarial,
    merge_itens_cct,
    extract_itens_cct,
    parse_clauses,
    PARAM_DIMENSION_CONFIG,
    _ALL_DIMENSION_PATTERNS,
)


# ──────────────────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────────────────

CARGO_TEXT = (
    "CLÁUSULA TERCEIRA - PISO SALARIAL\n"
    "Piso Administrativo: R$ 1.642,48 mensais para os empregados que exerçam "
    "funções administrativas.\n"
    "Piso Técnico: R$ 1.728,89 mensais para os empregados que exerçam funções "
    "técnicas, de suporte ou operacionais.\n"
)

JORNADA_TEXT = (
    "CLÁUSULA QUARTA - PISO SALARIAL\n"
    "Para os empregados com jornada de 44 horas semanais, o piso salarial será "
    "de R$ 1.728,89.\n"
    "Para os empregados com jornada de 36 horas semanais, o piso salarial será "
    "de R$ 1.450,00.\n"
)

MODALIDADE_TEXT = (
    "CLÁUSULA QUINTA - PISO SALARIAL\n"
    "Empregados em regime presencial: R$ 1.728,89 mensais.\n"
    "Empregados em regime de teletrabalho (remoto): R$ 1.850,00 mensais.\n"
)

ESCALA_TEXT = (
    "CLÁUSULA SEXTA - PISO SALARIAL\n"
    "Empregados em escala 12x36: R$ 1.900,00 mensais.\n"
    "Empregados em escala 6x1: R$ 1.642,48 mensais.\n"
)

NO_EVIDENCE_TEXT = (
    "CLÁUSULA SÉTIMA - PISO SALARIAL\n"
    "Os salários dos empregados serão reajustados conforme os valores "
    "R$ 1.642,48 e R$ 1.728,89, a critério da empresa.\n"
)

VR_JORNADA_TEXT = (
    "CLÁUSULA OITAVA - AUXÍLIO ALIMENTAÇÃO\n"
    "O auxílio alimentação para jornada de 6 horas por dia será de R$ 18,00.\n"
    "Para jornada de 8 horas por dia, o valor será de R$ 28,00.\n"
)


# ──────────────────────────────────────────────────────────────────────────────
# AC1 — Classification by cargo (piso salarial)
# ──────────────────────────────────────────────────────────────────────────────

class TestClassifyByCargo:
    def test_returns_por_cargo_entries(self):
        result = classify_by_dimension(CARGO_TEXT, [1642.48, 1728.89], "piso_salarial")
        assert "por_cargo" in result
        assert len(result["por_cargo"]) >= 2

    def test_cargo_entry_fields(self):
        result = classify_by_dimension(CARGO_TEXT, [1642.48, 1728.89], "piso_salarial")
        for entry in result["por_cargo"]:
            assert "cargo" in entry
            assert "valor" in entry
            assert "trecho_fonte" in entry

    def test_cargo_values_assigned_correctly(self):
        result = classify_by_dimension(CARGO_TEXT, [1642.48, 1728.89], "piso_salarial")
        by_label = {e["cargo"]: e["valor"] for e in result["por_cargo"]}
        assert by_label.get("piso_administrativo") == pytest.approx(1642.48, abs=0.01)
        assert by_label.get("piso_tecnico") == pytest.approx(1728.89, abs=0.01)

    def test_each_value_assigned_once(self):
        result = classify_by_dimension(CARGO_TEXT, [1642.48, 1728.89], "piso_salarial")
        vals = [e["valor"] for e in result["por_cargo"]]
        assert len(vals) == len(set(round(v, 2) for v in vals)), "Values must not repeat"

    def test_trecho_fonte_is_nonempty_string(self):
        result = classify_by_dimension(CARGO_TEXT, [1642.48, 1728.89], "piso_salarial")
        for entry in result["por_cargo"]:
            assert isinstance(entry["trecho_fonte"], str)
            assert len(entry["trecho_fonte"]) > 0


# ──────────────────────────────────────────────────────────────────────────────
# AC2 — Classification by jornada (piso salarial)
# ──────────────────────────────────────────────────────────────────────────────

class TestClassifyByJornada:
    def test_returns_por_jornada_entries(self):
        result = classify_by_dimension(JORNADA_TEXT, [1728.89, 1450.00], "piso_salarial")
        assert "por_jornada" in result

    def test_jornada_entry_fields(self):
        result = classify_by_dimension(JORNADA_TEXT, [1728.89, 1450.00], "piso_salarial")
        for entry in result["por_jornada"]:
            assert "jornada" in entry
            assert "valor" in entry
            assert "trecho_fonte" in entry

    def test_jornada_44h_assigned(self):
        result = classify_by_dimension(JORNADA_TEXT, [1728.89, 1450.00], "piso_salarial")
        by_jornada = {e["jornada"]: e["valor"] for e in result["por_jornada"]}
        assert "44h_semana" in by_jornada
        assert by_jornada["44h_semana"] == pytest.approx(1728.89, abs=0.01)

    def test_jornada_36h_assigned(self):
        result = classify_by_dimension(JORNADA_TEXT, [1728.89, 1450.00], "piso_salarial")
        by_jornada = {e["jornada"]: e["valor"] for e in result["por_jornada"]}
        assert "36h_semana" in by_jornada
        assert by_jornada["36h_semana"] == pytest.approx(1450.00, abs=0.01)

    def test_status_extraido_para_revisao_via_build_item(self):
        classification = classify_by_dimension(JORNADA_TEXT, [1728.89, 1450.00], "piso_salarial")
        item = build_item(
            values=[1728.89, 1450.00],
            regra_textual=JORNADA_TEXT,
            tipo="piso_cct",
            unidade="BRL",
            fonte_documento="doc.pdf",
            clausula_heading="CLÁUSULA - PISO",
            trecho_fonte=JORNADA_TEXT,
            classification=classification,
        )
        assert item["status_parametro"] == "extraido_para_revisao"


# ──────────────────────────────────────────────────────────────────────────────
# AC3 — Classification by modalidade and escala (piso salarial)
# ──────────────────────────────────────────────────────────────────────────────

class TestClassifyByModalidade:
    def test_returns_por_modalidade_entries(self):
        result = classify_by_dimension(MODALIDADE_TEXT, [1728.89, 1850.00], "piso_salarial")
        assert "por_modalidade" in result

    def test_modalidade_entry_fields(self):
        result = classify_by_dimension(MODALIDADE_TEXT, [1728.89, 1850.00], "piso_salarial")
        for entry in result["por_modalidade"]:
            assert "label" in entry
            assert "valor" in entry
            assert "trecho_fonte" in entry

    def test_presencial_assigned(self):
        result = classify_by_dimension(MODALIDADE_TEXT, [1728.89, 1850.00], "piso_salarial")
        labels = {e["label"]: e["valor"] for e in result["por_modalidade"]}
        assert "presencial" in labels
        assert labels["presencial"] == pytest.approx(1728.89, abs=0.01)

    def test_remoto_assigned(self):
        result = classify_by_dimension(MODALIDADE_TEXT, [1728.89, 1850.00], "piso_salarial")
        labels = {e["label"]: e["valor"] for e in result["por_modalidade"]}
        assert "remoto" in labels
        assert labels["remoto"] == pytest.approx(1850.00, abs=0.01)


class TestClassifyByEscala:
    def test_returns_por_escala_entries(self):
        result = classify_by_dimension(ESCALA_TEXT, [1900.00, 1642.48], "piso_salarial")
        assert "por_escala" in result

    def test_escala_entry_fields(self):
        result = classify_by_dimension(ESCALA_TEXT, [1900.00, 1642.48], "piso_salarial")
        for entry in result["por_escala"]:
            assert "label" in entry
            assert "valor" in entry
            assert "trecho_fonte" in entry

    def test_12x36_assigned(self):
        result = classify_by_dimension(ESCALA_TEXT, [1900.00, 1642.48], "piso_salarial")
        labels = {e["label"]: e["valor"] for e in result["por_escala"]}
        assert "12x36" in labels
        assert labels["12x36"] == pytest.approx(1900.00, abs=0.01)

    def test_status_extraido_para_revisao_via_build_item(self):
        classification = classify_by_dimension(ESCALA_TEXT, [1900.00, 1642.48], "piso_salarial")
        item = build_item(
            values=[1900.00, 1642.48],
            regra_textual=ESCALA_TEXT,
            tipo="piso_cct",
            unidade="BRL",
            fonte_documento="doc.pdf",
            clausula_heading="CLÁUSULA - PISO",
            trecho_fonte=ESCALA_TEXT,
            classification=classification,
        )
        assert item["status_parametro"] == "extraido_para_revisao"


# ──────────────────────────────────────────────────────────────────────────────
# AC4 — Generic architecture: same function works for different param_types
# ──────────────────────────────────────────────────────────────────────────────

class TestGenericArchitecture:
    def test_auxilio_alimentacao_por_jornada(self):
        """VR/VA with jornada dimension — reuses classify_by_dimension without changes."""
        result = classify_by_dimension(VR_JORNADA_TEXT, [18.00, 28.00], "auxilio_alimentacao")
        assert "por_jornada" in result
        assert "por_cargo" not in result

    def test_auxilio_jornada_entry_has_correct_keys(self):
        result = classify_by_dimension(VR_JORNADA_TEXT, [18.00, 28.00], "auxilio_alimentacao")
        for entry in result["por_jornada"]:
            assert "jornada" in entry
            assert "valor" in entry
            assert "trecho_fonte" in entry

    def test_hora_extra_por_modalidade(self):
        text = (
            "Hora extra em dias úteis: R$ 50,00.\n"
            "Hora extra em sábado: R$ 75,00.\n"
            "Hora extra em domingo: R$ 100,00.\n"
        )
        result = classify_by_dimension(text, [50.00, 75.00, 100.00], "hora_extra")
        assert "por_modalidade" in result
        assert "por_cargo" not in result
        assert "por_jornada" not in result

    def test_plr_por_cargo(self):
        text = (
            "PLR para cargo técnico: R$ 2.000,00.\n"
            "PLR para cargo operacional: R$ 1.500,00.\n"
        )
        result = classify_by_dimension(text, [2000.00, 1500.00], "plr")
        assert "por_cargo" in result
        assert "por_modalidade" not in result

    def test_unknown_param_uses_all_dimensions(self):
        """Unknown param_type falls back to all dimensions without raising."""
        result = classify_by_dimension(CARGO_TEXT, [1642.48, 1728.89], "parametro_futuro")
        assert isinstance(result, dict)

    def test_function_signature(self):
        """classify_by_dimension(text, values, param_type) — AC4 requirement."""
        sig = inspect.signature(classify_by_dimension)
        params = list(sig.parameters.keys())
        assert params == ["text", "values", "param_type"]

    def test_pattern_dicts_non_empty_for_all_dimensions(self):
        for dim in ("cargo", "jornada", "modalidade", "escala"):
            assert dim in _ALL_DIMENSION_PATTERNS
            assert len(_ALL_DIMENSION_PATTERNS[dim]) > 0

    def test_param_config_covers_future_params(self):
        """PARAM_DIMENSION_CONFIG already includes future parameters (AC4)."""
        for param in ("auxilio_alimentacao", "hora_extra", "adicional_noturno",
                      "sobreaviso", "plr", "jornada"):
            assert param in PARAM_DIMENSION_CONFIG
            assert len(PARAM_DIMENSION_CONFIG[param]) > 0

    def test_result_contains_only_dimension_keys(self):
        """Return value must not contain param-specific keys like 'piso_salarial'."""
        result = classify_by_dimension(CARGO_TEXT, [1642.48, 1728.89], "piso_salarial")
        allowed_keys = {"por_cargo", "por_jornada", "por_modalidade", "por_escala"}
        assert set(result.keys()).issubset(allowed_keys)


# ──────────────────────────────────────────────────────────────────────────────
# AC5 — Fallback to "conflito" without textual evidence
# ──────────────────────────────────────────────────────────────────────────────

class TestFallbackConflito:
    def test_classify_returns_empty_on_no_evidence(self):
        result = classify_by_dimension(NO_EVIDENCE_TEXT, [1642.48, 1728.89], "piso_salarial")
        assert result == {}

    def test_build_item_conflito_when_classification_none(self):
        item = build_item(
            values=[1642.48, 1728.89],
            regra_textual="texto",
            tipo="piso_cct",
            unidade="BRL",
            fonte_documento="doc.pdf",
            clausula_heading="CLÁUSULA - PISO",
            trecho_fonte="texto",
            classification=None,
        )
        assert item["status_parametro"] == "conflito"
        assert "Múltiplos valores identificados" in (item["observacao"] or "")

    def test_build_item_conflito_when_classification_empty(self):
        item = build_item(
            values=[1642.48, 1728.89],
            regra_textual="texto",
            tipo="piso_cct",
            unidade="BRL",
            fonte_documento="doc.pdf",
            clausula_heading="CLÁUSULA - PISO",
            trecho_fonte="texto",
            classification={},
        )
        assert item["status_parametro"] == "conflito"

    def test_extract_piso_salarial_fallback_to_conflito(self):
        """Clause with multiple values but no classifiable evidence → conflito."""
        text = (
            "CLÁUSULA TERCEIRA - PISO SALARIAL\n"
            "Os salários serão R$ 1.642,48 e R$ 1.728,89 conforme avaliação.\n"
        )
        clauses = parse_clauses(text)
        item = extract_piso_salarial(clauses, "doc.pdf")
        assert item["status_parametro"] == "conflito"
        assert "por_cargo" not in item
        assert "por_jornada" not in item
        assert "por_modalidade" not in item
        assert "por_escala" not in item


# ──────────────────────────────────────────────────────────────────────────────
# AC6 — Non-regression: "valido" items must not be overwritten
# ──────────────────────────────────────────────────────────────────────────────

class TestGovernanceValido:
    def test_merge_preserves_valido(self):
        existing = {
            "piso_salarial": {
                "valor": 1642.48,
                "status_parametro": "valido",
                "tipo": "piso_unico",
            }
        }
        new_itens = {
            "piso_salarial": {
                "valor": 9999.99,
                "status_parametro": "extraido_para_revisao",
                "tipo": "piso_cct",
                "por_cargo": [{"cargo": "tecnico", "valor": 9999.99, "trecho_fonte": "x"}],
            }
        }
        merged = merge_itens_cct(existing, new_itens)
        assert merged["piso_salarial"]["valor"] == pytest.approx(1642.48)
        assert merged["piso_salarial"]["status_parametro"] == "valido"
        assert "por_cargo" not in merged["piso_salarial"]

    def test_extract_itens_cct_skips_valido(self):
        record = {
            "fonte_documento": "nonexistent_file_ac6.pdf",
            "itens_cct": {
                "piso_salarial": {
                    "valor": 1642.48,
                    "status_parametro": "valido",
                }
            },
        }
        itens, _ = extract_itens_cct(record)
        assert itens["piso_salarial"]["status_parametro"] == "valido"
        assert itens["piso_salarial"]["valor"] == pytest.approx(1642.48)

    def test_valido_item_has_no_classification_subestruturas(self):
        """Validated item must never gain por_cargo etc. from classification pass."""
        existing = {
            "piso_salarial": {"valor": 1642.48, "status_parametro": "valido"}
        }
        new_itens = {
            "piso_salarial": {
                "valor": 1900.00,
                "status_parametro": "extraido_para_revisao",
                "por_cargo": [{"cargo": "tecnico", "valor": 1900.00, "trecho_fonte": "x"}],
            }
        }
        merged = merge_itens_cct(existing, new_itens)
        for key in ("por_cargo", "por_jornada", "por_modalidade", "por_escala"):
            assert key not in merged["piso_salarial"]


# ──────────────────────────────────────────────────────────────────────────────
# build_item with classification — status and valor fields
# ──────────────────────────────────────────────────────────────────────────────

class TestBuildItemWithClassification:
    def _classification(self):
        return {
            "por_cargo": [
                {"cargo": "piso_administrativo", "valor": 1642.48, "trecho_fonte": "..."},
                {"cargo": "piso_tecnico", "valor": 1728.89, "trecho_fonte": "..."},
            ]
        }

    def test_status_extraido_para_revisao(self):
        item = build_item(
            values=[1642.48, 1728.89],
            regra_textual="texto",
            tipo="piso_cct",
            unidade="BRL",
            fonte_documento="doc.pdf",
            clausula_heading="CLÁUSULA - PISO",
            trecho_fonte="texto",
            classification=self._classification(),
        )
        assert item["status_parametro"] == "extraido_para_revisao"

    def test_valor_is_minimum_of_classified(self):
        item = build_item(
            values=[1728.89, 1642.48],
            regra_textual="texto",
            tipo="piso_cct",
            unidade="BRL",
            fonte_documento="doc.pdf",
            clausula_heading="CLÁUSULA - PISO",
            trecho_fonte="texto",
            classification=self._classification(),
        )
        assert item["valor"] == pytest.approx(1642.48, abs=0.01)

    def test_por_cargo_embedded_in_item(self):
        item = build_item(
            values=[1642.48, 1728.89],
            regra_textual="texto",
            tipo="piso_cct",
            unidade="BRL",
            fonte_documento="doc.pdf",
            clausula_heading="CLÁUSULA - PISO",
            trecho_fonte="texto",
            classification=self._classification(),
        )
        assert "por_cargo" in item
        assert len(item["por_cargo"]) == 2

    def test_single_value_unclassified(self):
        item = build_item(
            values=[1642.48],
            regra_textual="texto",
            tipo="piso_unico",
            unidade="BRL",
            fonte_documento="doc.pdf",
            clausula_heading="CLÁUSULA - PISO",
            trecho_fonte="texto",
        )
        assert item["status_parametro"] == "extraido_para_revisao"
        assert item["valor"] == pytest.approx(1642.48, abs=0.01)
        assert "por_cargo" not in item


# ──────────────────────────────────────────────────────────────────────────────
# extract_piso_salarial integration
# ──────────────────────────────────────────────────────────────────────────────

class TestExtractPisoSalarialIntegration:
    def test_single_value_no_subestrutura(self):
        text = (
            "CLÁUSULA TERCEIRA - PISO SALARIAL\n"
            "O piso salarial é de R$ 1.642,48 mensais para todos os empregados.\n"
        )
        clauses = parse_clauses(text)
        item = extract_piso_salarial(clauses, "doc.pdf")
        assert item["status_parametro"] == "extraido_para_revisao"
        for key in ("por_cargo", "por_jornada", "por_modalidade", "por_escala"):
            assert key not in item

    def test_classified_multiple_values_not_conflito(self):
        clauses = parse_clauses(CARGO_TEXT)
        item = extract_piso_salarial(clauses, "doc.pdf")
        assert item["status_parametro"] == "extraido_para_revisao"
        assert "por_cargo" in item

    def test_tipo_field_preserved(self):
        clauses = parse_clauses(CARGO_TEXT)
        item = extract_piso_salarial(clauses, "doc.pdf")
        assert item.get("tipo") in ("piso_tecnico", "piso_administrativo", "piso_cct", "piso_unico")

    def test_unclassifiable_multiple_values_conflito(self):
        text = (
            "CLÁUSULA TERCEIRA - PISO SALARIAL\n"
            "Os salários serão R$ 1.642,48 e R$ 1.728,89 conforme avaliação da empresa.\n"
        )
        clauses = parse_clauses(text)
        item = extract_piso_salarial(clauses, "doc.pdf")
        assert item["status_parametro"] == "conflito"
        assert "por_cargo" not in item


# ──────────────────────────────────────────────────────────────────────────────
# Edge cases
# ──────────────────────────────────────────────────────────────────────────────

class TestEdgeCases:
    def test_empty_values_returns_empty(self):
        result = classify_by_dimension(CARGO_TEXT, [], "piso_salarial")
        assert result == {}

    def test_empty_text_returns_empty(self):
        result = classify_by_dimension("", [1642.48], "piso_salarial")
        assert result == {}

    def test_value_not_in_window_skipped(self):
        """A value not near any pattern match must not appear in results."""
        result = classify_by_dimension(CARGO_TEXT, [9999.00], "piso_salarial")
        all_vals = [e["valor"] for entries in result.values() for e in entries]
        assert 9999.00 not in all_vals

    def test_no_duplicate_values_across_entries_in_same_dimension(self):
        result = classify_by_dimension(CARGO_TEXT, [1642.48, 1728.89], "piso_salarial")
        if "por_cargo" in result:
            vals = [round(e["valor"], 2) for e in result["por_cargo"]]
            assert len(vals) == len(set(vals))

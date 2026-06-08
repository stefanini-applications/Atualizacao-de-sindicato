"""
Unit tests for classify_by_dimension and related helpers in extract_cct_items.py.

Validates:
  AC1 — por_cargo classification in piso_salarial
  AC2 — por_jornada classification in piso_salarial
  AC3 — por_modalidade and por_escala classification
  AC4 — generic, parameter-agnostic architecture (reusable for other params)
  AC5 — fallback to "conflito" when no classification evidence is found
  AC6 — governance: "valido" items are never overwritten
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from extract_cct_items import (
    classify_by_dimension,
    build_item,
    merge_itens_cct,
)


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures — realistic CCT clause text snippets
# ─────────────────────────────────────────────────────────────────────────────

CLAUSE_CARGO = (
    "CLÁUSULA TERCEIRA – PISO SALARIAL\n"
    "Os empregadores pagarão os seguintes pisos salariais:\n"
    "Piso Administrativo: R$ 1.642,48 (um mil seiscentos e quarenta e dois reais e quarenta e oito centavos)\n"
    "Piso Técnico: R$ 1.728,89 (um mil setecentos e vinte e oito reais e oitenta e nove centavos)\n"
)

CLAUSE_JORNADA = (
    "CLÁUSULA QUARTA – PISO SALARIAL\n"
    "Para trabalhadores em jornada de 44 horas semanais, o piso será R$ 1.642,48.\n"
    "Para trabalhadores em jornada de 36 horas semanais, o piso será R$ 1.412,00.\n"
)

CLAUSE_MODALIDADE = (
    "CLÁUSULA QUINTA – PISO SALARIAL\n"
    "Para empregados em regime presencial: R$ 1.800,00 mensais.\n"
    "Para empregados em regime remoto (teletrabalho): R$ 1.950,00 mensais.\n"
)

CLAUSE_ESCALA = (
    "CLÁUSULA SEXTA – PISO SALARIAL\n"
    "Empregados em escala 12x36: R$ 2.100,00.\n"
    "Empregados em escala 6x1: R$ 1.900,00.\n"
)

CLAUSE_NO_EVIDENCE = (
    "CLÁUSULA SÉTIMA – PISO SALARIAL\n"
    "O piso salarial da categoria é de R$ 1.642,48 e R$ 1.728,89.\n"
)

CLAUSE_HORA_EXTRA_MODALIDADE = (
    "CLÁUSULA OITAVA – HORA EXTRA\n"
    "Horas extras realizadas em dias úteis serão remuneradas com adicional de 50%.\n"
    "Horas extras em sábado serão de 75%.\n"
    "Domingos e feriados: 100%.\n"
)

CLAUSE_VR_JORNADA = (
    "CLÁUSULA NONA – AUXÍLIO ALIMENTAÇÃO\n"
    "Para jornada de 6 horas diárias: R$ 18,00 por dia útil.\n"
    "Para jornada de 8 horas diárias: R$ 25,00 por dia útil.\n"
)


# ─────────────────────────────────────────────────────────────────────────────
# AC1 — por_cargo in piso_salarial
# ─────────────────────────────────────────────────────────────────────────────

class TestPorCargo:
    def test_classifies_administrativo_and_tecnico(self):
        result = classify_by_dimension(CLAUSE_CARGO, [1642.48, 1728.89], "piso_salarial")
        assert "por_cargo" in result
        cargos = {e["cargo"] for e in result["por_cargo"]}
        assert "Administrativo" in cargos
        assert "Técnico" in cargos

    def test_each_entry_has_required_fields(self):
        result = classify_by_dimension(CLAUSE_CARGO, [1642.48, 1728.89], "piso_salarial")
        for entry in result["por_cargo"]:
            assert "cargo" in entry
            assert "valor" in entry
            assert "trecho_fonte" in entry
            assert isinstance(entry["valor"], float)
            assert isinstance(entry["trecho_fonte"], str)
            assert len(entry["trecho_fonte"]) > 0

    def test_values_are_correctly_assigned(self):
        result = classify_by_dimension(CLAUSE_CARGO, [1642.48, 1728.89], "piso_salarial")
        by_cargo = {e["cargo"]: e["valor"] for e in result["por_cargo"]}
        assert by_cargo["Administrativo"] == pytest.approx(1642.48)
        assert by_cargo["Técnico"] == pytest.approx(1728.89)


# ─────────────────────────────────────────────────────────────────────────────
# AC2 — por_jornada in piso_salarial
# ─────────────────────────────────────────────────────────────────────────────

class TestPorJornada:
    def test_classifies_jornadas(self):
        result = classify_by_dimension(CLAUSE_JORNADA, [1642.48, 1412.0], "piso_salarial")
        assert "por_jornada" in result
        assert len(result["por_jornada"]) >= 2

    def test_jornada_entries_have_required_fields(self):
        result = classify_by_dimension(CLAUSE_JORNADA, [1642.48, 1412.0], "piso_salarial")
        for entry in result["por_jornada"]:
            assert "jornada" in entry
            assert "valor" in entry
            assert "trecho_fonte" in entry

    def test_44h_and_36h_labels(self):
        result = classify_by_dimension(CLAUSE_JORNADA, [1642.48, 1412.0], "piso_salarial")
        labels = {e["jornada"] for e in result["por_jornada"]}
        assert "44h semanais" in labels
        assert "36h semanais" in labels


# ─────────────────────────────────────────────────────────────────────────────
# AC3 — por_modalidade and por_escala
# ─────────────────────────────────────────────────────────────────────────────

class TestPorModalidade:
    def test_classifies_presencial_and_remoto(self):
        result = classify_by_dimension(CLAUSE_MODALIDADE, [1800.0, 1950.0], "piso_salarial")
        assert "por_modalidade" in result
        labels = {e["label"] for e in result["por_modalidade"]}
        assert "Presencial" in labels
        assert "Remoto" in labels

    def test_modalidade_entries_have_required_fields(self):
        result = classify_by_dimension(CLAUSE_MODALIDADE, [1800.0, 1950.0], "piso_salarial")
        for entry in result["por_modalidade"]:
            assert "label" in entry
            assert "valor" in entry
            assert "trecho_fonte" in entry


class TestPorEscala:
    def test_classifies_12x36_and_6x1(self):
        result = classify_by_dimension(CLAUSE_ESCALA, [2100.0, 1900.0], "piso_salarial")
        assert "por_escala" in result
        labels = {e["label"] for e in result["por_escala"]}
        assert "12x36" in labels
        assert "6x1" in labels

    def test_escala_entries_have_required_fields(self):
        result = classify_by_dimension(CLAUSE_ESCALA, [2100.0, 1900.0], "piso_salarial")
        for entry in result["por_escala"]:
            assert "label" in entry
            assert "valor" in entry
            assert "trecho_fonte" in entry


# ─────────────────────────────────────────────────────────────────────────────
# AC4 — generic architecture: reusable for other param_types
# ─────────────────────────────────────────────────────────────────────────────

class TestGenericArchitecture:
    def test_hora_extra_por_modalidade(self):
        """hora_extra should classify by modalidade (dia útil, sábado, domingo, feriado)."""
        # The clause contains % values, not BRL, but classify_by_dimension works
        # on any numeric list; here we test with BRL-like float stubs to verify
        # pattern matching applies to hora_extra param_type.
        clause = (
            "CLÁUSULA – HORA EXTRA\n"
            "Dias úteis: R$ 50,00 por hora.\n"
            "Sábados: R$ 75,00 por hora.\n"
        )
        result = classify_by_dimension(clause, [50.0, 75.0], "hora_extra")
        assert "por_modalidade" in result
        labels = {e["label"] for e in result["por_modalidade"]}
        assert "Dia Útil" in labels
        assert "Sábado" in labels

    def test_auxilio_alimentacao_por_jornada(self):
        """auxilio_alimentacao uses jornada patterns (6h, 8h, integral, parcial)."""
        result = classify_by_dimension(CLAUSE_VR_JORNADA, [18.0, 25.0], "auxilio_alimentacao")
        assert "por_jornada" in result
        labels = {e["jornada"] for e in result["por_jornada"]}
        assert "6 horas" in labels
        assert "8 horas" in labels

    def test_function_returns_no_param_specific_keys(self):
        """classify_by_dimension must not reference piso_salarial in its return value."""
        result = classify_by_dimension(CLAUSE_CARGO, [1642.48, 1728.89], "piso_salarial")
        # None of the returned keys should embed "piso_salarial"
        for key in result:
            assert "piso_salarial" not in key

    def test_single_value_returns_empty(self):
        """Function requires at least 2 values to classify."""
        result = classify_by_dimension(CLAUSE_CARGO, [1642.48], "piso_salarial")
        assert result == {}

    def test_empty_values_returns_empty(self):
        result = classify_by_dimension(CLAUSE_CARGO, [], "piso_salarial")
        assert result == {}

    def test_unknown_param_type_falls_back_to_default(self):
        """Unknown param_type should fall back to _default patterns."""
        result = classify_by_dimension(CLAUSE_CARGO, [1642.48, 1728.89], "parametro_futuro_xyz")
        assert "por_cargo" in result


# ─────────────────────────────────────────────────────────────────────────────
# AC5 — fallback to "conflito" when no classification evidence
# ─────────────────────────────────────────────────────────────────────────────

class TestFallbackConflito:
    def test_no_evidence_returns_empty_dict(self):
        result = classify_by_dimension(CLAUSE_NO_EVIDENCE, [1642.48, 1728.89], "piso_salarial")
        assert result == {}

    def test_build_item_conflito_without_param_type(self):
        """Without param_type, build_item should still produce conflito for multiple values."""
        item = build_item(
            values=[1642.48, 1728.89],
            regra_textual=CLAUSE_NO_EVIDENCE,
            tipo="piso_cct",
            unidade="BRL",
            fonte_documento="CCT/test.pdf",
            clausula_heading="CLÁUSULA SÉTIMA",
            trecho_fonte=CLAUSE_NO_EVIDENCE,
        )
        assert item["status_parametro"] == "conflito"
        assert "por_cargo" not in item
        assert "por_jornada" not in item

    def test_build_item_conflito_when_text_has_no_evidence(self):
        """Even with param_type, no matching evidence → conflito."""
        item = build_item(
            values=[1642.48, 1728.89],
            regra_textual=CLAUSE_NO_EVIDENCE,
            tipo="piso_cct",
            unidade="BRL",
            fonte_documento="CCT/test.pdf",
            clausula_heading="CLÁUSULA SÉTIMA",
            trecho_fonte=CLAUSE_NO_EVIDENCE,
            param_type="piso_salarial",
        )
        assert item["status_parametro"] == "conflito"
        assert "por_cargo" not in item

    def test_build_item_preserves_conflito_observation(self):
        item = build_item(
            values=[1642.48, 1728.89],
            regra_textual=CLAUSE_NO_EVIDENCE,
            tipo="piso_cct",
            unidade="BRL",
            fonte_documento="CCT/test.pdf",
            clausula_heading="CLÁUSULA SÉTIMA",
            trecho_fonte=CLAUSE_NO_EVIDENCE,
            param_type="piso_salarial",
        )
        assert "1642.48" in item["observacao"] or "1728.89" in item["observacao"]


# ─────────────────────────────────────────────────────────────────────────────
# AC5+AC1 — build_item integration: classified result upgrades status
# ─────────────────────────────────────────────────────────────────────────────

class TestBuildItemIntegration:
    def test_classified_status_is_extraido_para_revisao(self):
        item = build_item(
            values=[1642.48, 1728.89],
            regra_textual=CLAUSE_CARGO,
            tipo="piso_cct",
            unidade="BRL",
            fonte_documento="CCT/test.pdf",
            clausula_heading="CLÁUSULA TERCEIRA",
            trecho_fonte=CLAUSE_CARGO,
            param_type="piso_salarial",
        )
        assert item["status_parametro"] == "extraido_para_revisao"

    def test_classified_item_contains_por_cargo(self):
        item = build_item(
            values=[1642.48, 1728.89],
            regra_textual=CLAUSE_CARGO,
            tipo="piso_cct",
            unidade="BRL",
            fonte_documento="CCT/test.pdf",
            clausula_heading="CLÁUSULA TERCEIRA",
            trecho_fonte=CLAUSE_CARGO,
            param_type="piso_salarial",
        )
        assert "por_cargo" in item
        assert len(item["por_cargo"]) >= 2

    def test_top_level_valor_is_minimum_classified(self):
        """Top-level valor should be the minimum value from classified items."""
        item = build_item(
            values=[1642.48, 1728.89],
            regra_textual=CLAUSE_CARGO,
            tipo="piso_cct",
            unidade="BRL",
            fonte_documento="CCT/test.pdf",
            clausula_heading="CLÁUSULA TERCEIRA",
            trecho_fonte=CLAUSE_CARGO,
            param_type="piso_salarial",
        )
        assert item["valor"] == pytest.approx(1642.48)

    def test_single_value_not_classified(self):
        """Single value should not trigger classification."""
        item = build_item(
            values=[1642.48],
            regra_textual=CLAUSE_CARGO,
            tipo="piso_unico",
            unidade="BRL",
            fonte_documento="CCT/test.pdf",
            clausula_heading="CLÁUSULA TERCEIRA",
            trecho_fonte=CLAUSE_CARGO,
            param_type="piso_salarial",
        )
        assert item["status_parametro"] == "extraido_para_revisao"
        assert "por_cargo" not in item


# ─────────────────────────────────────────────────────────────────────────────
# AC6 — governance: "valido" items never overwritten
# ─────────────────────────────────────────────────────────────────────────────

class TestGovernance:
    def test_valido_item_not_overwritten_by_merge(self):
        existing = {
            "piso_salarial": {
                "valor": 1500.0,
                "status_parametro": "valido",
                "tipo": "piso_unico",
            }
        }
        new_item = build_item(
            values=[1642.48, 1728.89],
            regra_textual=CLAUSE_CARGO,
            tipo="piso_cct",
            unidade="BRL",
            fonte_documento="CCT/test.pdf",
            clausula_heading="CLÁUSULA TERCEIRA",
            trecho_fonte=CLAUSE_CARGO,
            param_type="piso_salarial",
        )
        new_itens = {"piso_salarial": new_item}
        merged = merge_itens_cct(existing, new_itens)

        assert merged["piso_salarial"]["status_parametro"] == "valido"
        assert merged["piso_salarial"]["valor"] == 1500.0
        assert "por_cargo" not in merged["piso_salarial"]

    def test_non_valido_item_is_overwritten(self):
        existing = {
            "piso_salarial": {
                "valor": None,
                "status_parametro": "conflito",
            }
        }
        new_item = build_item(
            values=[1642.48, 1728.89],
            regra_textual=CLAUSE_CARGO,
            tipo="piso_cct",
            unidade="BRL",
            fonte_documento="CCT/test.pdf",
            clausula_heading="CLÁUSULA TERCEIRA",
            trecho_fonte=CLAUSE_CARGO,
            param_type="piso_salarial",
        )
        new_itens = {"piso_salarial": new_item}
        merged = merge_itens_cct(existing, new_itens)

        assert merged["piso_salarial"]["status_parametro"] == "extraido_para_revisao"
        assert "por_cargo" in merged["piso_salarial"]

#!/usr/bin/env python3
"""
Unit tests for classify_by_dimension and the updated build_item behavior.

Coverage:
  AC1 — classify by cargo for piso_salarial
  AC2 — classify by jornada for piso_salarial
  AC3 — classify by modalidade and escala for piso_salarial
  AC4 — generic/reusable: same function works for auxilio_alimentacao (jornada),
         hora_extra (modalidade), plr (cargo)
  AC5 — fallback to "conflito" when no textual evidence found
  AC6 — build_item preserves governance ("valido" items not overwritten via
         extract_itens_cct's merge logic; tested indirectly via build_item status)
"""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from extract_cct_items import (
    classify_by_dimension,
    build_item,
    PARAM_DIMENSIONS,
    CARGO_PATTERNS,
    JORNADA_PATTERNS,
    MODALIDADE_PATTERNS,
    ESCALA_PATTERNS,
)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _labels(entries: list[dict], field: str) -> list[str]:
    return [e[field] for e in entries]


def _values(entries: list[dict]) -> list[float]:
    return [e["valor"] for e in entries]


# ─────────────────────────────────────────────────────────────────────────────
# AC1 — Classification by cargo
# ─────────────────────────────────────────────────────────────────────────────

def test_classify_cargo_piso_administrativo():
    text = (
        "CLÁUSULA TERCEIRA - PISO SALARIAL\n"
        "Piso Administrativo: R$ 1.642,48 mensais.\n"
        "Piso Técnico: R$ 1.728,89 mensais."
    )
    result = classify_by_dimension(text, [1642.48, 1728.89], "piso_salarial")
    cargos = result["por_cargo"]
    assert len(cargos) == 2
    labels = _labels(cargos, "cargo")
    assert "piso_administrativo" in labels
    assert "piso_tecnico" in labels
    assert all("trecho_fonte" in c for c in cargos)


def test_classify_cargo_values_correct():
    text = (
        "Piso para Auxiliar Administrativo: R$ 1.500,00.\n"
        "Piso para Analista: R$ 2.200,00."
    )
    result = classify_by_dimension(text, [1500.0, 2200.0], "piso_salarial")
    cargos = result["por_cargo"]
    labels = _labels(cargos, "cargo")
    vals = {e["cargo"]: e["valor"] for e in cargos}
    assert "piso_administrativo" in labels or "auxiliar" in labels
    assert "analista" in labels
    assert vals.get("analista") == 2200.0


def test_classify_cargo_supervisor():
    text = (
        "O Supervisor receberá piso de R$ 3.000,00.\n"
        "O Atendente receberá R$ 1.800,00."
    )
    result = classify_by_dimension(text, [3000.0, 1800.0], "piso_salarial")
    labels = _labels(result["por_cargo"], "cargo")
    assert "supervisor" in labels
    assert "atendente" in labels


def test_classify_cargo_trecho_fonte_present():
    text = "Piso técnico de suporte: R$ 2.100,00 por mês."
    result = classify_by_dimension(text, [2100.0], "piso_salarial")
    cargos = result["por_cargo"]
    assert len(cargos) == 1
    assert cargos[0]["trecho_fonte"]  # not empty


# ─────────────────────────────────────────────────────────────────────────────
# AC2 — Classification by jornada
# ─────────────────────────────────────────────────────────────────────────────

def test_classify_jornada_horas_semanais():
    text = (
        "Trabalhadores com jornada de 44 horas semanais: R$ 1.800,00.\n"
        "Trabalhadores com jornada de 36 horas semanais: R$ 1.500,00."
    )
    result = classify_by_dimension(text, [1800.0, 1500.0], "piso_salarial")
    jornadas = result["por_jornada"]
    labels = _labels(jornadas, "jornada")
    assert "44h_semana" in labels
    assert "36h_semana" in labels


def test_classify_jornada_mensalista_horista():
    text = (
        "Para mensalistas: R$ 2.000,00.\n"
        "Para horistas: R$ 12,00 por hora."
    )
    result = classify_by_dimension(text, [2000.0, 12.0], "piso_salarial")
    labels = _labels(result["por_jornada"], "jornada")
    assert "mensalista" in labels
    assert "horista" in labels


def test_classify_jornada_diarias():
    text = (
        "Empregados com jornada de 6 horas diárias: R$ 1.200,00.\n"
        "Empregados com jornada de 8 horas diárias: R$ 1.600,00."
    )
    result = classify_by_dimension(text, [1200.0, 1600.0], "piso_salarial")
    labels = _labels(result["por_jornada"], "jornada")
    assert "6h_diarias" in labels
    assert "8h_diarias" in labels


# ─────────────────────────────────────────────────────────────────────────────
# AC3 — Classification by modalidade and escala
# ─────────────────────────────────────────────────────────────────────────────

def test_classify_modalidade_presencial_remoto():
    text = (
        "Regime presencial: R$ 1.900,00.\n"
        "Regime remoto: R$ 1.700,00."
    )
    result = classify_by_dimension(text, [1900.0, 1700.0], "piso_salarial")
    labels = _labels(result["por_modalidade"], "label")
    assert "presencial" in labels
    assert "remoto" in labels


def test_classify_modalidade_dias_uteis():
    text = (
        "Piso para dias úteis: R$ 1.500,00.\n"
        "Piso para feriados: R$ 2.000,00."
    )
    result = classify_by_dimension(text, [1500.0, 2000.0], "piso_salarial")
    labels = _labels(result["por_modalidade"], "label")
    assert "dia_util" in labels
    assert "feriado" in labels


def test_classify_escala_12x36():
    text = (
        "Empregados na escala 12x36: R$ 2.300,00.\n"
        "Empregados na escala 6x1: R$ 1.900,00."
    )
    result = classify_by_dimension(text, [2300.0, 1900.0], "piso_salarial")
    labels = _labels(result["por_escala"], "label")
    assert "12x36" in labels
    assert "6x1" in labels


def test_classify_escala_5x2():
    text = "Regime 5x2: R$ 1.750,00 mensais."
    result = classify_by_dimension(text, [1750.0], "piso_salarial")
    labels = _labels(result["por_escala"], "label")
    assert "5x2" in labels


# ─────────────────────────────────────────────────────────────────────────────
# AC4 — Generic / reusable across param types
# ─────────────────────────────────────────────────────────────────────────────

def test_param_dimensions_coverage():
    """All expected param types are registered."""
    for param in ("piso_salarial", "auxilio_alimentacao", "hora_extra",
                  "adicional_noturno", "sobreaviso", "plr", "jornada"):
        assert param in PARAM_DIMENSIONS, f"{param} missing from PARAM_DIMENSIONS"


def test_classify_auxilio_alimentacao_by_jornada():
    """auxilio_alimentacao should only use jornada dimension."""
    text = (
        "Vale-refeição para jornada de 6 horas diárias: R$ 25,00.\n"
        "Vale-refeição para jornada de 8 horas diárias: R$ 35,00."
    )
    result = classify_by_dimension(text, [25.0, 35.0], "auxilio_alimentacao")
    # Only jornada dimension is applicable
    assert result["por_cargo"] == []
    assert result["por_modalidade"] == []
    assert result["por_escala"] == []
    labels = _labels(result["por_jornada"], "jornada")
    assert "6h_diarias" in labels
    assert "8h_diarias" in labels


def test_classify_hora_extra_by_modalidade():
    """hora_extra should only use modalidade dimension."""
    text = (
        "Adicional para dias úteis: 50%... valor base R$ 15,00.\n"
        "Adicional para domingos: 100%... valor base R$ 20,00."
    )
    result = classify_by_dimension(text, [15.0, 20.0], "hora_extra")
    assert result["por_cargo"] == []
    assert result["por_jornada"] == []
    assert result["por_escala"] == []
    labels = _labels(result["por_modalidade"], "label")
    assert "dia_util" in labels
    assert "domingo" in labels


def test_classify_plr_by_cargo():
    """plr should only use cargo dimension."""
    text = (
        "PLR para técnicos: R$ 1.200,00.\n"
        "PLR para operacionais: R$ 900,00."
    )
    result = classify_by_dimension(text, [1200.0, 900.0], "plr")
    assert result["por_jornada"] == []
    assert result["por_modalidade"] == []
    assert result["por_escala"] == []
    labels = _labels(result["por_cargo"], "cargo")
    assert "tecnico" in labels
    assert "operacional" in labels


def test_classify_returns_empty_dims_when_no_match_in_dim():
    """Dimensions with no matching keywords return empty lists."""
    text = "Piso Administrativo: R$ 1.642,48. Piso Técnico: R$ 1.728,89."
    result = classify_by_dimension(text, [1642.48, 1728.89], "piso_salarial")
    # There is cargo evidence but no jornada/modalidade/escala
    assert len(result["por_cargo"]) > 0
    assert result["por_jornada"] == []
    assert result["por_modalidade"] == []
    assert result["por_escala"] == []


def test_classify_no_duplicate_entries():
    """Same label+value pair should not be duplicated even if keyword appears twice."""
    text = (
        "Piso técnico R$ 1.728,89. Empregados técnicos receberão R$ 1.728,89."
    )
    result = classify_by_dimension(text, [1728.89], "piso_salarial")
    tecnico_entries = [e for e in result["por_cargo"] if e["cargo"] == "piso_tecnico" or e["cargo"] == "tecnico"]
    assert len(tecnico_entries) == 1


# ─────────────────────────────────────────────────────────────────────────────
# AC5 — Fallback to "conflito" when no textual evidence
# ─────────────────────────────────────────────────────────────────────────────

def test_classify_returns_all_empty_when_no_evidence():
    text = "Os salários serão de R$ 1.500,00 e R$ 1.800,00 conforme tabela."
    result = classify_by_dimension(text, [1500.0, 1800.0], "piso_salarial")
    assert result["por_cargo"] == []
    assert result["por_jornada"] == []
    assert result["por_modalidade"] == []
    assert result["por_escala"] == []


def test_build_item_conflito_fallback_no_evidence():
    """build_item sets status='conflito' when no dimension evidence."""
    text = "Os pisos serão R$ 1.500,00 e R$ 1.800,00."
    item = build_item(
        values=[1500.0, 1800.0],
        regra_textual=text,
        tipo="piso_cct",
        unidade="BRL",
        fonte_documento="CCT/test.pdf",
        clausula_heading="CLÁUSULA PISO SALARIAL",
        trecho_fonte=text,
        param_type="piso_salarial",
    )
    assert item["status_parametro"] == "conflito"
    assert "1500.0" in item["observacao"] or "1500" in item["observacao"]
    assert "por_cargo" not in item
    assert "por_jornada" not in item


def test_build_item_conflito_without_param_type():
    """build_item sets status='conflito' when param_type is not supplied."""
    text = "Piso Administrativo: R$ 1.642,48. Piso Técnico: R$ 1.728,89."
    item = build_item(
        values=[1642.48, 1728.89],
        regra_textual=text,
        tipo="piso_cct",
        unidade="BRL",
        fonte_documento="CCT/test.pdf",
        clausula_heading="CLÁUSULA PISO SALARIAL",
        trecho_fonte=text,
        # param_type intentionally omitted
    )
    assert item["status_parametro"] == "conflito"


# ─────────────────────────────────────────────────────────────────────────────
# AC1/AC3 combined — build_item integration with classification
# ─────────────────────────────────────────────────────────────────────────────

def test_build_item_classified_status_extraido():
    """build_item sets status='extraido_para_revisao' when classification succeeds."""
    text = (
        "Piso Administrativo: R$ 1.642,48 mensais.\n"
        "Piso Técnico: R$ 1.728,89 mensais."
    )
    item = build_item(
        values=[1642.48, 1728.89],
        regra_textual=text,
        tipo="piso_cct",
        unidade="BRL",
        fonte_documento="CCT/test.pdf",
        clausula_heading="CLÁUSULA PISO SALARIAL",
        trecho_fonte=text,
        param_type="piso_salarial",
    )
    assert item["status_parametro"] == "extraido_para_revisao"
    assert "por_cargo" in item
    assert len(item["por_cargo"]) == 2


def test_build_item_valor_is_minimum_when_classified():
    """Top-level valor should be the minimum value when classification succeeds (AC1)."""
    text = (
        "Piso Administrativo: R$ 1.642,48.\n"
        "Piso Técnico: R$ 1.728,89."
    )
    item = build_item(
        values=[1728.89, 1642.48],  # higher value first
        regra_textual=text,
        tipo="piso_cct",
        unidade="BRL",
        fonte_documento="CCT/test.pdf",
        clausula_heading="CLÁUSULA PISO SALARIAL",
        trecho_fonte=text,
        param_type="piso_salarial",
    )
    assert item["valor"] == 1642.48


def test_build_item_jornada_classification():
    text = (
        "Jornada de 44 horas semanais: R$ 1.800,00.\n"
        "Jornada de 36 horas semanais: R$ 1.500,00."
    )
    item = build_item(
        values=[1800.0, 1500.0],
        regra_textual=text,
        tipo="piso_cct",
        unidade="BRL",
        fonte_documento="CCT/test.pdf",
        clausula_heading="CLÁUSULA PISO SALARIAL",
        trecho_fonte=text,
        param_type="piso_salarial",
    )
    assert item["status_parametro"] == "extraido_para_revisao"
    assert "por_jornada" in item
    labels = [e["jornada"] for e in item["por_jornada"]]
    assert "44h_semana" in labels
    assert "36h_semana" in labels


def test_build_item_escala_classification():
    text = (
        "Escala 12x36: R$ 2.200,00 mensais.\n"
        "Escala 5x2: R$ 1.900,00 mensais."
    )
    item = build_item(
        values=[2200.0, 1900.0],
        regra_textual=text,
        tipo="piso_cct",
        unidade="BRL",
        fonte_documento="CCT/test.pdf",
        clausula_heading="CLÁUSULA PISO SALARIAL",
        trecho_fonte=text,
        param_type="piso_salarial",
    )
    assert item["status_parametro"] == "extraido_para_revisao"
    assert "por_escala" in item
    labels = [e["label"] for e in item["por_escala"]]
    assert "12x36" in labels
    assert "5x2" in labels


# ─────────────────────────────────────────────────────────────────────────────
# AC6 — Single-value items unaffected by classification logic
# ─────────────────────────────────────────────────────────────────────────────

def test_build_item_single_value_unchanged():
    """Single-value items keep status extraido_para_revisao without sub-structures."""
    text = "Piso salarial único: R$ 1.642,48."
    item = build_item(
        values=[1642.48],
        regra_textual=text,
        tipo="piso_unico",
        unidade="BRL",
        fonte_documento="CCT/test.pdf",
        clausula_heading="CLÁUSULA PISO",
        trecho_fonte=text,
        param_type="piso_salarial",
    )
    assert item["status_parametro"] == "extraido_para_revisao"
    assert "por_cargo" not in item
    assert item["valor"] == 1642.48


# ─────────────────────────────────────────────────────────────────────────────
# Pattern dictionary extensibility sanity checks
# ─────────────────────────────────────────────────────────────────────────────

def test_pattern_dicts_are_non_empty():
    assert len(CARGO_PATTERNS) > 0
    assert len(JORNADA_PATTERNS) > 0
    assert len(MODALIDADE_PATTERNS) > 0
    assert len(ESCALA_PATTERNS) > 0


def test_jornada_patterns_cover_future_auxilio_alimentacao():
    """Patterns for 6h/8h diárias are present to support auxilio_alimentacao."""
    jornada_labels = [label for label, _ in JORNADA_PATTERNS]
    assert "6h_diarias" in jornada_labels
    assert "8h_diarias" in jornada_labels
    assert "mensalista" in jornada_labels
    assert "horista" in jornada_labels


def test_modalidade_patterns_cover_future_hora_extra():
    """Patterns for dia_util/sábado/domingo/feriado present for hora_extra."""
    modalidade_labels = [label for label, _ in MODALIDADE_PATTERNS]
    assert "dia_util" in modalidade_labels
    assert "sabado" in modalidade_labels
    assert "domingo" in modalidade_labels
    assert "feriado" in modalidade_labels


def test_escala_patterns_cover_future_adicional_noturno():
    """Scale patterns for 12x36 and 6x1 present for adicional_noturno."""
    escala_labels = [label for label, _ in ESCALA_PATTERNS]
    assert "12x36" in escala_labels
    assert "6x1" in escala_labels


def test_modalidade_patterns_cover_sobreaviso():
    """Sobreaviso patterns (acionado, disponivel) present."""
    modalidade_labels = [label for label, _ in MODALIDADE_PATTERNS]
    assert "acionado" in modalidade_labels
    assert "disponivel" in modalidade_labels


# ─────────────────────────────────────────────────────────────────────────────
# Runner
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import traceback

    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    passed = failed = 0
    for fn in tests:
        try:
            fn()
            print(f"  ✓  {fn.__name__}")
            passed += 1
        except Exception as exc:
            print(f"  ✗  {fn.__name__}: {exc}")
            traceback.print_exc()
            failed += 1

    print(f"\n{passed} passed, {failed} failed")
    sys.exit(1 if failed else 0)

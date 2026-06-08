#!/usr/bin/env python3
"""
Unit tests for extract_cct_items.py — PRJ-54.

Covers:
  AC1  – classify_by_dimension → por_cargo for piso_salarial
  AC2  – classify_by_dimension → por_jornada for piso_salarial
  AC3  – classify_by_dimension → por_modalidade / por_escala for piso_salarial
  AC4  – classify_by_dimension is generic: same function works for other param_types
  AC5  – fallback to "conflito" when no dimension evidence is present
  AC6  – build_item / extract_piso_salarial never overwrite status "valido"
         (governance rule tested via merge_itens_cct)
"""

import unittest

from extract_cct_items import (
    CARGO_PATTERNS,
    ESCALA_PATTERNS,
    JORNADA_PATTERNS,
    MODALIDADE_PATTERNS,
    _PARAM_DIMENSIONS,
    build_item,
    classify_by_dimension,
    merge_itens_cct,
)


# ──────────────────────────────────────────────────────────────────────────────
# Fixtures — realistic CCT clause fragments
# ──────────────────────────────────────────────────────────────────────────────

CARGO_CLAUSE = """
CLÁUSULA SEGUNDA - PISOS SALARIAIS
Os pisos salariais ficam estabelecidos da seguinte forma:
a) Piso Administrativo: R$ 1.642,48 (mil seiscentos e quarenta e dois reais e quarenta
   e oito centavos) para os trabalhadores que exercem funções administrativas.
b) Piso Técnico: R$ 1.728,89 (mil setecentos e vinte e oito reais e oitenta e nove
   centavos) para os trabalhadores que exercem funções técnicas.
"""

JORNADA_CLAUSE = """
CLÁUSULA TERCEIRA - PISO SALARIAL
O piso salarial para a jornada de 44 horas semanais será de R$ 1.800,00.
Para os trabalhadores em regime de 36 horas semanais, o piso salarial será
de R$ 1.500,00, conforme negociação coletiva.
"""

MODALIDADE_CLAUSE = """
CLÁUSULA QUARTA - PISO SALARIAL
Para os trabalhadores em regime presencial o piso é de R$ 1.950,00 mensais.
Para os trabalhadores em home office o piso é de R$ 1.850,00 mensais, haja vista
a redução de custos de deslocamento.
"""

ESCALA_CLAUSE = """
CLÁUSULA QUINTA - PISO SALARIAL
Trabalhadores em escala 12×36: R$ 2.100,00.
Trabalhadores em escala 5×1: R$ 1.900,00.
"""

NO_EVIDENCE_CLAUSE = """
CLÁUSULA SEXTA - PISO SALARIAL
Fica estabelecido o piso salarial para a categoria conforme acordo entre as partes.
Valores apurados: R$ 1.642,48 e R$ 1.728,89 sem distinção adicional.
"""

# Para AC4 – VR/VA por jornada (auxilio_alimentacao)
VA_JORNADA_CLAUSE = """
CLÁUSULA SÉTIMA - AUXÍLIO ALIMENTAÇÃO
Para jornada de 6 horas diárias: R$ 18,00 por dia.
Para jornada de 8 horas diárias: R$ 32,00 por dia.
"""

# Para AC4 – hora extra por modalidade
HORA_EXTRA_CLAUSE = """
CLÁUSULA OITAVA - HORA EXTRA
Horas extras em dias úteis serão remuneradas com acréscimo de R$ 50,00 por hora.
Horas extras em domingos com acréscimo de R$ 80,00 por hora.
"""


# ──────────────────────────────────────────────────────────────────────────────
# AC1 — Classificação por cargo
# ──────────────────────────────────────────────────────────────────────────────

class TestClassifyByCargo(unittest.TestCase):
    def setUp(self):
        self.result = classify_by_dimension(
            CARGO_CLAUSE, [1642.48, 1728.89], "piso_salarial"
        )

    def test_por_cargo_present(self):
        self.assertIn("por_cargo", self.result)

    def test_por_cargo_has_two_entries(self):
        self.assertEqual(len(self.result["por_cargo"]), 2)

    def test_por_cargo_entry_fields(self):
        for entry in self.result["por_cargo"]:
            self.assertIn("cargo", entry)
            self.assertIn("valor", entry)
            self.assertIn("trecho_fonte", entry)

    def test_por_cargo_values_are_correct(self):
        vals = {round(e["valor"], 2) for e in self.result["por_cargo"]}
        self.assertEqual(vals, {1642.48, 1728.89})

    def test_no_spurious_dimensions(self):
        # No jornada/modalidade/escala evidence in the cargo clause
        self.assertNotIn("por_jornada", self.result)
        self.assertNotIn("por_modalidade", self.result)
        self.assertNotIn("por_escala", self.result)


# ──────────────────────────────────────────────────────────────────────────────
# AC2 — Classificação por jornada
# ──────────────────────────────────────────────────────────────────────────────

class TestClassifyByJornada(unittest.TestCase):
    def setUp(self):
        self.result = classify_by_dimension(
            JORNADA_CLAUSE, [1800.0, 1500.0], "piso_salarial"
        )

    def test_por_jornada_present(self):
        self.assertIn("por_jornada", self.result)

    def test_por_jornada_has_two_entries(self):
        self.assertEqual(len(self.result["por_jornada"]), 2)

    def test_por_jornada_entry_fields(self):
        for entry in self.result["por_jornada"]:
            self.assertIn("jornada", entry)
            self.assertIn("valor", entry)
            self.assertIn("trecho_fonte", entry)

    def test_por_jornada_values_are_correct(self):
        vals = {round(e["valor"], 2) for e in self.result["por_jornada"]}
        self.assertEqual(vals, {1800.0, 1500.0})


# ──────────────────────────────────────────────────────────────────────────────
# AC3 — Classificação por modalidade e escala
# ──────────────────────────────────────────────────────────────────────────────

class TestClassifyByModalidade(unittest.TestCase):
    def setUp(self):
        self.result = classify_by_dimension(
            MODALIDADE_CLAUSE, [1950.0, 1850.0], "piso_salarial"
        )

    def test_por_modalidade_present(self):
        self.assertIn("por_modalidade", self.result)

    def test_por_modalidade_entry_fields(self):
        for entry in self.result["por_modalidade"]:
            self.assertIn("label", entry)
            self.assertIn("valor", entry)
            self.assertIn("trecho_fonte", entry)

    def test_por_modalidade_values(self):
        vals = {round(e["valor"], 2) for e in self.result["por_modalidade"]}
        self.assertEqual(vals, {1950.0, 1850.0})


class TestClassifyByEscala(unittest.TestCase):
    def setUp(self):
        self.result = classify_by_dimension(
            ESCALA_CLAUSE, [2100.0, 1900.0], "piso_salarial"
        )

    def test_por_escala_present(self):
        self.assertIn("por_escala", self.result)

    def test_por_escala_entry_fields(self):
        for entry in self.result["por_escala"]:
            self.assertIn("label", entry)
            self.assertIn("valor", entry)
            self.assertIn("trecho_fonte", entry)

    def test_por_escala_values(self):
        vals = {round(e["valor"], 2) for e in self.result["por_escala"]}
        self.assertEqual(vals, {2100.0, 1900.0})


# ──────────────────────────────────────────────────────────────────────────────
# AC4 — Generic / reusable architecture
# ──────────────────────────────────────────────────────────────────────────────

class TestClassifyGenericArchitecture(unittest.TestCase):
    """Validates that classify_by_dimension works for future param_types."""

    def test_auxilio_alimentacao_por_jornada(self):
        result = classify_by_dimension(
            VA_JORNADA_CLAUSE, [18.0, 32.0], "auxilio_alimentacao"
        )
        self.assertIn("por_jornada", result)
        vals = {round(e["valor"], 2) for e in result["por_jornada"]}
        self.assertEqual(vals, {18.0, 32.0})

    def test_hora_extra_por_modalidade(self):
        result = classify_by_dimension(
            HORA_EXTRA_CLAUSE, [50.0, 80.0], "hora_extra"
        )
        self.assertIn("por_modalidade", result)
        vals = {round(e["valor"], 2) for e in result["por_modalidade"]}
        self.assertEqual(vals, {50.0, 80.0})

    def test_auxilio_alimentacao_does_not_return_cargo(self):
        # auxilio_alimentacao only uses jornada dimension
        result = classify_by_dimension(
            VA_JORNADA_CLAUSE, [18.0, 32.0], "auxilio_alimentacao"
        )
        self.assertNotIn("por_cargo", result)
        self.assertNotIn("por_modalidade", result)
        self.assertNotIn("por_escala", result)

    def test_function_returns_no_param_specific_keys(self):
        # The result dict must never contain 'piso_salarial' or param names as keys
        result = classify_by_dimension(
            CARGO_CLAUSE, [1642.48, 1728.89], "piso_salarial"
        )
        for key in result:
            self.assertTrue(
                key.startswith("por_"),
                f"Unexpected key '{key}' — classify_by_dimension must only return por_* keys",
            )

    def test_param_dimensions_config_covers_all_future_params(self):
        expected_params = {
            "piso_salarial", "auxilio_alimentacao", "hora_extra",
            "adicional_noturno", "sobreaviso", "plr", "jornada",
        }
        self.assertTrue(expected_params.issubset(set(_PARAM_DIMENSIONS.keys())))

    def test_pattern_dicts_are_non_empty(self):
        self.assertGreater(len(CARGO_PATTERNS), 0)
        self.assertGreater(len(JORNADA_PATTERNS), 0)
        self.assertGreater(len(MODALIDADE_PATTERNS), 0)
        self.assertGreater(len(ESCALA_PATTERNS), 0)

    def test_single_value_returns_empty(self):
        result = classify_by_dimension(CARGO_CLAUSE, [1642.48], "piso_salarial")
        self.assertEqual(result, {})


# ──────────────────────────────────────────────────────────────────────────────
# AC5 — Fallback to "conflito" without classification evidence
# ──────────────────────────────────────────────────────────────────────────────

class TestFallbackConflito(unittest.TestCase):
    def test_classify_returns_empty_without_evidence(self):
        result = classify_by_dimension(
            NO_EVIDENCE_CLAUSE, [1642.48, 1728.89], "piso_salarial"
        )
        self.assertEqual(result, {})

    def test_build_item_produces_conflito_without_classification(self):
        item = build_item(
            values=[1642.48, 1728.89],
            regra_textual=NO_EVIDENCE_CLAUSE,
            tipo="piso_cct",
            unidade="BRL",
            fonte_documento="CCT/test.pdf",
            clausula_heading="CLÁUSULA - PISO SALARIAL",
            trecho_fonte=NO_EVIDENCE_CLAUSE,
            classification=None,
        )
        self.assertEqual(item["status_parametro"], "conflito")
        self.assertIn("Múltiplos valores identificados", item["observacao"])
        self.assertNotIn("por_cargo", item)
        self.assertNotIn("por_jornada", item)

    def test_build_item_produces_extraido_with_classification(self):
        classification = classify_by_dimension(
            CARGO_CLAUSE, [1642.48, 1728.89], "piso_salarial"
        )
        item = build_item(
            values=[1642.48, 1728.89],
            regra_textual=CARGO_CLAUSE,
            tipo="piso_cct",
            unidade="BRL",
            fonte_documento="CCT/test.pdf",
            clausula_heading="CLÁUSULA - PISO SALARIAL",
            trecho_fonte=CARGO_CLAUSE,
            classification=classification,
        )
        self.assertEqual(item["status_parametro"], "extraido_para_revisao")
        self.assertIn("por_cargo", item)


# ──────────────────────────────────────────────────────────────────────────────
# AC1 (additional) — top-level valor = minimum classified value
# ──────────────────────────────────────────────────────────────────────────────

class TestBuildItemMinimumValor(unittest.TestCase):
    def test_top_level_valor_is_minimum(self):
        classification = classify_by_dimension(
            CARGO_CLAUSE, [1642.48, 1728.89], "piso_salarial"
        )
        item = build_item(
            values=[1642.48, 1728.89],
            regra_textual=CARGO_CLAUSE,
            tipo="piso_cct",
            unidade="BRL",
            fonte_documento="CCT/test.pdf",
            clausula_heading="CLÁUSULA - PISO SALARIAL",
            trecho_fonte=CARGO_CLAUSE,
            classification=classification,
        )
        self.assertAlmostEqual(item["valor"], 1642.48, places=2)


# ──────────────────────────────────────────────────────────────────────────────
# AC6 — Governance: "valido" items are never overwritten
# ──────────────────────────────────────────────────────────────────────────────

class TestGovernanceValido(unittest.TestCase):
    def test_merge_preserves_valido_item(self):
        existing = {
            "piso_salarial": {
                "valor": 1642.48,
                "status_parametro": "valido",
                "observacao": "Aprovado pelo analista",
            }
        }
        new_itens = {
            "piso_salarial": {
                "valor": 1728.89,
                "status_parametro": "extraido_para_revisao",
                "por_cargo": [{"cargo": "Técnico", "valor": 1728.89, "trecho_fonte": "..."}],
            }
        }
        merged = merge_itens_cct(existing, new_itens)
        # The existing valido item must not be overwritten
        self.assertEqual(merged["piso_salarial"]["status_parametro"], "valido")
        self.assertAlmostEqual(merged["piso_salarial"]["valor"], 1642.48)
        self.assertNotIn("por_cargo", merged["piso_salarial"])

    def test_merge_overwrites_conflito_item(self):
        existing = {
            "piso_salarial": {
                "valor": None,
                "status_parametro": "conflito",
            }
        }
        new_itens = {
            "piso_salarial": {
                "valor": 1642.48,
                "status_parametro": "extraido_para_revisao",
            }
        }
        merged = merge_itens_cct(existing, new_itens)
        self.assertEqual(merged["piso_salarial"]["status_parametro"], "extraido_para_revisao")


if __name__ == "__main__":
    unittest.main()

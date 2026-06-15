"""
Testes automatizados para enrich_mte_fallback.py (PRJ-65).

Cobre todos os cenários críticos de governança exigidos em AC5:
  (a) campo pendente_revisao sem valor PDF recebe origem "fonte_oficial_mte"
      quando MTE tem evidência.
  (b) campo com status_parametro "valido" nunca é sobrescrito.
  (c) campo com origem "pdf_cct" e valor não nulo nunca é sobrescrito,
      independentemente do status_parametro.
  (d) divergência PDF × MTE gera status_parametro "conflito" com opcoes_identificadas.
  (e) Piso Nacional não preenche cargos/benefícios/adicionais/PLR/jornada/hora
      extra/sobreaviso.
  (f) campo não encontrado em nenhuma fonte mantém pendente_revisao.
  (g) base_parametros_sindicais.json e .js são atualizados somente quando há
      dados reais encontrados.
  (h) stub/interface retorna None, não altera a base e registra limitação
      explícita quando API MTE está indisponível.
"""

import copy
import json
import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from enrich_mte_fallback import (
    ELIGIBLE_FIELDS,
    MTE_FONTE_LABEL,
    _is_field_enrichable,
    _is_field_pdf_protected,
    _is_field_valid_protected,
    _piso_nacional_eligible,
    enrich_from_mte_fallback,
    lookup_mte_instrumento_coletivo,
    run_enrichment,
)

# ──────────────────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────────────────

FIELD_PENDENTE = {
    "valor": None,
    "percentual": None,
    "valor_textual": None,
    "status_parametro": "pendente_revisao",
    "origem": "nao_identificado_pdf",
    "fonte": None,
    "fonte_textual": None,
    "data_extracao": "2026-06-01",
}

FIELD_VALIDO = {
    "valor": 1500.00,
    "percentual": None,
    "status_parametro": "valido",
    "origem": "pdf_cct",
    "fonte": "PDF da CCT",
    "fonte_textual": "CLÁUSULA TERCEIRA ...",
    "data_extracao": "2026-06-01",
}

FIELD_PDF_EXTRAIDO = {
    "valor": 1540.47,
    "percentual": None,
    "status_parametro": "extraido_para_revisao",
    "origem": "pdf_cct",
    "fonte": "PDF da CCT",
    "fonte_textual": "CLÁUSULA TERCEIRA ...",
    "data_extracao": "2026-06-01",
}

FIELD_PDF_NULL_VALUE = {
    "valor": None,
    "percentual": None,
    "status_parametro": "extraido_para_revisao",
    "origem": "pdf_cct",
    "fonte": "PDF da CCT",
    "fonte_textual": "CLÁUSULA TERCEIRA — cláusula localizada",
    "data_extracao": "2026-06-01",
}

MTE_CAMPO_VALIDO = {
    "valor": 1620.00,
    "percentual": None,
    "fonte_textual": "Cláusula 3ª do instrumento registrado no Sistema Mediador",
    "observacao": "Extraído do Sistema Mediador MTE",
}

MTE_CAMPO_PERCENTUAL = {
    "valor": None,
    "percentual": 25.0,
    "fonte_textual": "Adicional noturno: 25% conforme cláusula 7ª",
    "observacao": "Extraído do Sistema Mediador MTE",
}


def _make_record(overrides: dict | None = None) -> dict:
    """Create a minimal record for testing."""
    base = {
        "id_registro_reajuste": "REG-TEST-2025",
        "uf": "SP",
        "sindicato": "Sindicato Teste",
        "categoria": "Tecnologia",
        "ano_referencia": 2025,
        "itens_cct": {
            "piso_salarial": copy.deepcopy(FIELD_PENDENTE),
            "adicional_noturno": copy.deepcopy(FIELD_PENDENTE),
            "auxilio_alimentacao": copy.deepcopy(FIELD_PENDENTE),
            "plr": copy.deepcopy(FIELD_PENDENTE),
            "hora_extra": copy.deepcopy(FIELD_PENDENTE),
            "sobreaviso": copy.deepcopy(FIELD_PENDENTE),
            "jornada": copy.deepcopy(FIELD_PENDENTE),
        },
    }
    if overrides:
        for k, v in overrides.items():
            if k == "itens_cct":
                base["itens_cct"].update(v)
            else:
                base[k] = v
    return base


def _make_instrumento(campos: dict) -> dict:
    """Create a minimal MTE instrumento_coletivo dict."""
    return {
        "numero_registro": "MTE-2025-TEST",
        "tipo": "CCT",
        "vigencia_inicio": "2025-01-01",
        "vigencia_fim": "2025-12-31",
        "campos": campos,
    }


def _make_base_json(records: list[dict]) -> dict:
    """Create a minimal base_parametros_sindicais.json structure."""
    return {
        "data_geracao": "2026-06-15T00:00:00+00:00",
        "registros": records,
    }


# ──────────────────────────────────────────────────────────────────────────────
# AC5(a) — campo pendente recebe origem "fonte_oficial_mte" quando MTE tem dados
# ──────────────────────────────────────────────────────────────────────────────


class TestEnrichmentFromMTE(unittest.TestCase):
    """AC5(a): MTE enriches pending fields correctly."""

    def test_pending_field_enriched_with_mte_valor(self):
        record = _make_record()
        instrumento = _make_instrumento({"piso_salarial": MTE_CAMPO_VALIDO})

        metrics = enrich_from_mte_fallback(record, instrumento)

        field = record["itens_cct"]["piso_salarial"]
        self.assertEqual(field["status_parametro"], "extraido_para_revisao")
        self.assertEqual(field["origem"], "fonte_oficial_mte")
        self.assertEqual(field["fonte"], MTE_FONTE_LABEL)
        self.assertEqual(field["valor"], 1620.00)
        self.assertIsNotNone(field["fonte_textual"])
        self.assertIsNotNone(field["data_extracao"])
        self.assertEqual(metrics["preenchidos_mte"], 1)

    def test_pending_field_enriched_with_mte_percentual(self):
        record = _make_record()
        instrumento = _make_instrumento({"adicional_noturno": MTE_CAMPO_PERCENTUAL})

        metrics = enrich_from_mte_fallback(record, instrumento)

        field = record["itens_cct"]["adicional_noturno"]
        self.assertEqual(field["status_parametro"], "extraido_para_revisao")
        self.assertEqual(field["origem"], "fonte_oficial_mte")
        self.assertEqual(field["percentual"], 25.0)
        self.assertEqual(metrics["preenchidos_mte"], 1)

    def test_all_required_traceability_fields_present(self):
        """AC4: every MTE-enriched field must have full traceability."""
        record = _make_record()
        instrumento = _make_instrumento({"piso_salarial": MTE_CAMPO_VALIDO})
        enrich_from_mte_fallback(record, instrumento)

        field = record["itens_cct"]["piso_salarial"]
        for required_key in (
            "valor", "status_parametro", "origem", "fonte", "fonte_textual",
            "data_extracao", "observacao",
        ):
            self.assertIn(required_key, field, f"Missing traceability key: {required_key}")
        self.assertEqual(field["status_parametro"], "extraido_para_revisao")
        self.assertEqual(field["origem"], "fonte_oficial_mte")
        self.assertEqual(field["fonte"], MTE_FONTE_LABEL)


# ──────────────────────────────────────────────────────────────────────────────
# AC5(b) — campos com status "valido" nunca são sobrescritos
# ──────────────────────────────────────────────────────────────────────────────


class TestValidoProtection(unittest.TestCase):
    """AC5(b): fields with status_parametro "valido" must never be overwritten."""

    def test_valido_field_not_overwritten_by_mte(self):
        record = _make_record({"itens_cct": {"piso_salarial": copy.deepcopy(FIELD_VALIDO)}})
        instrumento = _make_instrumento({"piso_salarial": MTE_CAMPO_VALIDO})

        enrich_from_mte_fallback(record, instrumento)

        field = record["itens_cct"]["piso_salarial"]
        self.assertEqual(field["status_parametro"], "valido")
        self.assertEqual(field["valor"], 1500.00)
        self.assertEqual(field["origem"], "pdf_cct")

    def test_valido_field_not_overwritten_by_piso_nacional(self):
        record = _make_record({"itens_cct": {"piso_salarial": copy.deepcopy(FIELD_VALIDO)}})

        metrics = enrich_from_mte_fallback(record, None, piso_nacional_valor=1412.00)

        field = record["itens_cct"]["piso_salarial"]
        self.assertEqual(field["status_parametro"], "valido")
        self.assertEqual(field["valor"], 1500.00)
        self.assertEqual(metrics["preenchidos_piso_nacional"], 0)

    def test_is_field_valid_protected_true(self):
        self.assertTrue(_is_field_valid_protected(FIELD_VALIDO))

    def test_is_field_valid_protected_false_for_pending(self):
        self.assertFalse(_is_field_valid_protected(FIELD_PENDENTE))


# ──────────────────────────────────────────────────────────────────────────────
# AC5(c) — campos com origem "pdf_cct" e valor não nulo nunca são sobrescritos
# ──────────────────────────────────────────────────────────────────────────────


class TestPdfCctProtection(unittest.TestCase):
    """AC5(c): fields with origem "pdf_cct" and non-null value never overwritten."""

    def test_pdf_cct_extraido_not_overwritten_by_mte_same_value(self):
        """Same value → no conflict, field remains unchanged."""
        field_same = copy.deepcopy(FIELD_PDF_EXTRAIDO)
        record = _make_record({"itens_cct": {"piso_salarial": field_same}})
        instrumento = _make_instrumento({
            "piso_salarial": {"valor": 1540.47, "fonte_textual": "MTE confirm"},
        })

        enrich_from_mte_fallback(record, instrumento)

        field = record["itens_cct"]["piso_salarial"]
        # Same value: no conflict raised, pdf value preserved
        self.assertEqual(field["valor"], 1540.47)
        self.assertNotEqual(field.get("status_parametro"), "conflito")

    def test_pdf_cct_null_value_is_enrichable(self):
        """origem pdf_cct but null value → enrichable by MTE."""
        record = _make_record({"itens_cct": {"piso_salarial": copy.deepcopy(FIELD_PDF_NULL_VALUE)}})
        instrumento = _make_instrumento({"piso_salarial": MTE_CAMPO_VALIDO})

        metrics = enrich_from_mte_fallback(record, instrumento)

        field = record["itens_cct"]["piso_salarial"]
        self.assertEqual(field["status_parametro"], "extraido_para_revisao")
        self.assertEqual(field["origem"], "fonte_oficial_mte")
        self.assertEqual(metrics["preenchidos_mte"], 1)

    def test_is_field_pdf_protected_true(self):
        self.assertTrue(_is_field_pdf_protected(FIELD_PDF_EXTRAIDO))

    def test_is_field_pdf_protected_false_null_value(self):
        self.assertFalse(_is_field_pdf_protected(FIELD_PDF_NULL_VALUE))

    def test_is_field_pdf_protected_false_non_pdf_origin(self):
        self.assertFalse(_is_field_pdf_protected(FIELD_PENDENTE))


# ──────────────────────────────────────────────────────────────────────────────
# AC5(d) — divergência PDF × MTE gera status "conflito" com opcoes_identificadas
# ──────────────────────────────────────────────────────────────────────────────


class TestConflictDetection(unittest.TestCase):
    """AC5(d): PDF×MTE divergence → status "conflito" with opcoes_identificadas."""

    def _conflicting_record(self) -> tuple[dict, dict]:
        field = copy.deepcopy(FIELD_PDF_EXTRAIDO)  # valor=1540.47, origem=pdf_cct
        record = _make_record({"itens_cct": {"piso_salarial": field}})
        instrumento = _make_instrumento({
            "piso_salarial": {"valor": 1620.00, "fonte_textual": "MTE contradicts PDF"},
        })
        return record, instrumento

    def test_conflict_status_is_conflito(self):
        record, instrumento = self._conflicting_record()
        metrics = enrich_from_mte_fallback(record, instrumento)

        field = record["itens_cct"]["piso_salarial"]
        self.assertEqual(field["status_parametro"], "conflito")
        self.assertEqual(metrics["conflitos"], 1)

    def test_conflict_origem_is_conflito_pdf_mte(self):
        record, instrumento = self._conflicting_record()
        enrich_from_mte_fallback(record, instrumento)

        field = record["itens_cct"]["piso_salarial"]
        self.assertEqual(field["origem"], "conflito_pdf_mte")

    def test_conflict_has_opcoes_identificadas(self):
        record, instrumento = self._conflicting_record()
        enrich_from_mte_fallback(record, instrumento)

        field = record["itens_cct"]["piso_salarial"]
        self.assertIn("opcoes_identificadas", field)
        opcoes = field["opcoes_identificadas"]
        self.assertEqual(len(opcoes), 2)
        fontes = {o["fonte"] for o in opcoes}
        self.assertIn("pdf_cct", fontes)
        self.assertIn("fonte_oficial_mte", fontes)

    def test_conflict_preserves_both_values(self):
        record, instrumento = self._conflicting_record()
        enrich_from_mte_fallback(record, instrumento)

        field = record["itens_cct"]["piso_salarial"]
        opcoes_vals = {o["valor"] for o in field["opcoes_identificadas"]}
        self.assertIn(1540.47, opcoes_vals)
        self.assertIn(1620.00, opcoes_vals)


# ──────────────────────────────────────────────────────────────────────────────
# AC5(e) — Piso Nacional não preenche cargos/benefícios/adicionais/PLR/etc.
# ──────────────────────────────────────────────────────────────────────────────


class TestPisoNacionalRestrictions(unittest.TestCase):
    """AC5(e): Piso Nacional only for piso geral, never for other fields."""

    FORBIDDEN_FIELDS = [
        "adicional_noturno",
        "auxilio_alimentacao",
        "plr",
        "hora_extra",
        "sobreaviso",
        "jornada",
    ]

    def test_piso_nacional_not_applied_to_forbidden_fields(self):
        record = _make_record()
        metrics = enrich_from_mte_fallback(record, None, piso_nacional_valor=1412.00)

        for campo in self.FORBIDDEN_FIELDS:
            field = record["itens_cct"][campo]
            self.assertNotEqual(
                field.get("origem"), "fonte_oficial_nacional",
                f"Piso Nacional indevidamente aplicado ao campo '{campo}'"
            )
        # Piso Nacional CAN be applied to piso_salarial (not forbidden),
        # so count is 1 — the check above confirms none of the FORBIDDEN_FIELDS got it.
        self.assertEqual(metrics["preenchidos_piso_nacional"], 1,
                         "Piso Nacional deveria ter sido aplicado ao piso_salarial (campo permitido)")

    def test_piso_nacional_not_applied_to_por_cargo_piso(self):
        """Piso Nacional must NOT be applied when piso_salarial has por_cargo."""
        field_com_cargo = copy.deepcopy(FIELD_PENDENTE)
        field_com_cargo["por_cargo"] = [
            {"cargo": "piso_tecnico", "valor": None, "trecho_fonte": "..."}
        ]
        record = _make_record({"itens_cct": {"piso_salarial": field_com_cargo}})

        metrics = enrich_from_mte_fallback(record, None, piso_nacional_valor=1412.00)

        field = record["itens_cct"]["piso_salarial"]
        self.assertNotEqual(field.get("origem"), "fonte_oficial_nacional")
        self.assertEqual(metrics["preenchidos_piso_nacional"], 0)

    def test_piso_nacional_applied_to_eligible_piso_salarial(self):
        """Piso Nacional CAN be applied to generic piso_salarial (no por_cargo)."""
        record = _make_record()
        metrics = enrich_from_mte_fallback(record, None, piso_nacional_valor=1412.00)

        field = record["itens_cct"]["piso_salarial"]
        self.assertEqual(field["origem"], "fonte_oficial_nacional")
        self.assertEqual(field["valor"], 1412.00)
        self.assertEqual(field["status_parametro"], "extraido_para_revisao")
        self.assertEqual(metrics["preenchidos_piso_nacional"], 1)

    def test_piso_nacional_eligible_helper_true(self):
        self.assertTrue(_piso_nacional_eligible(FIELD_PENDENTE))

    def test_piso_nacional_eligible_helper_false_with_por_cargo(self):
        field = copy.deepcopy(FIELD_PENDENTE)
        field["por_cargo"] = [{"cargo": "analista_suporte_i", "valor": None}]
        self.assertFalse(_piso_nacional_eligible(field))

    def test_piso_nacional_not_applied_when_mte_already_filled(self):
        """Piso Nacional must NOT apply when MTE already filled piso_salarial."""
        record = _make_record()
        instrumento = _make_instrumento({"piso_salarial": MTE_CAMPO_VALIDO})
        metrics = enrich_from_mte_fallback(record, instrumento, piso_nacional_valor=1412.00)

        field = record["itens_cct"]["piso_salarial"]
        self.assertEqual(field["origem"], "fonte_oficial_mte")
        self.assertEqual(field["valor"], 1620.00)
        self.assertEqual(metrics["preenchidos_piso_nacional"], 0)


# ──────────────────────────────────────────────────────────────────────────────
# AC5(f) — campo não encontrado mantém pendente_revisao
# ──────────────────────────────────────────────────────────────────────────────


class TestFieldRemainsAsPendente(unittest.TestCase):
    """AC5(f): fields not found in any source remain as pendente_revisao."""

    def test_all_fields_remain_pending_when_no_mte_no_piso_nacional(self):
        record = _make_record()
        metrics = enrich_from_mte_fallback(record, None, piso_nacional_valor=None)

        for campo in ELIGIBLE_FIELDS:
            field = record["itens_cct"].get(campo, {})
            self.assertEqual(
                field.get("status_parametro"), "pendente_revisao",
                f"Campo '{campo}' deveria permanecer como pendente_revisao"
            )
        self.assertEqual(metrics["preenchidos_mte"], 0)
        self.assertEqual(metrics["preenchidos_piso_nacional"], 0)

    def test_unmatched_mte_campo_leaves_field_pending(self):
        record = _make_record()
        # MTE only has piso_salarial; other fields remain pending
        instrumento = _make_instrumento({"piso_salarial": MTE_CAMPO_VALIDO})
        metrics = enrich_from_mte_fallback(record, instrumento)

        for campo in ("adicional_noturno", "plr", "hora_extra", "sobreaviso", "jornada"):
            field = record["itens_cct"].get(campo, {})
            self.assertEqual(
                field.get("status_parametro"), "pendente_revisao",
                f"Campo '{campo}' deveria permanecer como pendente_revisao"
            )


# ──────────────────────────────────────────────────────────────────────────────
# AC5(g) — JSON/JS atualizados somente com dados reais
# ──────────────────────────────────────────────────────────────────────────────


class TestPersistenceGating(unittest.TestCase):
    """AC5(g): JSON and JS files are only written when real data is found."""

    def _write_temp_base(self, records: list[dict]) -> str:
        tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        )
        json.dump(_make_base_json(records), tmp, ensure_ascii=False, indent=2)
        tmp.flush()
        tmp.close()
        return tmp.name

    def test_json_not_modified_when_no_real_data(self):
        record = _make_record()
        json_path = self._write_temp_base([record])
        original_mtime = os.path.getmtime(json_path)

        with patch("enrich_mte_fallback.lookup_mte_instrumento_coletivo", return_value=None), \
             patch("enrich_mte_fallback._export_js"):
            run_enrichment(json_path=json_path, dry_run=False, ids=None, piso_nacional_valor=None)

        new_mtime = os.path.getmtime(json_path)
        self.assertEqual(
            original_mtime, new_mtime,
            "JSON foi modificado mesmo sem dados reais — violação de AC3/AC7"
        )
        os.unlink(json_path)

    def test_json_modified_when_real_data_found(self):
        record = _make_record()
        json_path = self._write_temp_base([record])

        fake_instrumento = _make_instrumento({"piso_salarial": MTE_CAMPO_VALIDO})

        with patch("enrich_mte_fallback.lookup_mte_instrumento_coletivo", return_value=fake_instrumento), \
             patch("enrich_mte_fallback._export_js"):
            metrics = run_enrichment(json_path=json_path, dry_run=False, ids=None)

        self.assertGreater(metrics["preenchidos_mte"], 0)
        # Verify the JSON was actually modified
        with open(json_path, "r", encoding="utf-8") as f:
            saved = json.load(f)
        piso = saved["registros"][0]["itens_cct"]["piso_salarial"]
        self.assertEqual(piso["origem"], "fonte_oficial_mte")
        os.unlink(json_path)

    def test_dry_run_does_not_write_json(self):
        record = _make_record()
        json_path = self._write_temp_base([record])
        original_mtime = os.path.getmtime(json_path)

        fake_instrumento = _make_instrumento({"piso_salarial": MTE_CAMPO_VALIDO})

        with patch("enrich_mte_fallback.lookup_mte_instrumento_coletivo", return_value=fake_instrumento), \
             patch("enrich_mte_fallback._export_js"):
            run_enrichment(json_path=json_path, dry_run=True)

        new_mtime = os.path.getmtime(json_path)
        self.assertEqual(
            original_mtime, new_mtime,
            "JSON foi modificado em modo dry-run — não deveria ser"
        )
        os.unlink(json_path)


# ──────────────────────────────────────────────────────────────────────────────
# AC5(h) — stub retorna None, não altera base, registra limitação explícita
# ──────────────────────────────────────────────────────────────────────────────


class TestMTEStub(unittest.TestCase):
    """AC5(h): stub returns None, doesn't modify base, logs limitation."""

    def test_lookup_returns_none(self):
        result = lookup_mte_instrumento_coletivo(
            uf="SP", sindicato="Sintespra", categoria="TI",
            ano=2025, cnpj=None, tipo_instrumento="CCT",
        )
        self.assertIsNone(result)

    def test_stub_logs_warning(self):
        with self.assertLogs("enrich_mte_fallback", level="WARNING") as cm:
            lookup_mte_instrumento_coletivo(
                uf="RJ", sindicato="Sindpd", categoria="Processamento de Dados", ano=2024
            )
        self.assertTrue(
            any("MTE API indisponível" in msg or "indispon" in msg.lower() for msg in cm.output),
            "Stub deve registrar explicitamente que API MTE está indisponível"
        )

    def test_run_enrichment_returns_zero_metrics_when_api_unavailable(self):
        record = _make_record()

        import tempfile
        tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        )
        json.dump(_make_base_json([record]), tmp, ensure_ascii=False, indent=2)
        tmp.flush()
        tmp.close()

        with patch("enrich_mte_fallback._export_js"):
            metrics = run_enrichment(
                json_path=tmp.name, dry_run=False, ids=None, piso_nacional_valor=None
            )

        self.assertEqual(metrics["preenchidos_mte"], 0)
        self.assertEqual(metrics["conflitos"], 0)
        self.assertEqual(metrics["preenchidos_piso_nacional"], 0)
        self.assertFalse(metrics["api_mte_disponivel"])
        os.unlink(tmp.name)

    def test_base_not_modified_when_stub_returns_none(self):
        """Even after run_enrichment, JSON must be unchanged when stub returns None."""
        record = _make_record()
        tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        )
        json.dump(_make_base_json([record]), tmp, ensure_ascii=False, indent=2)
        tmp.flush()
        tmp.close()

        original_mtime = os.path.getmtime(tmp.name)

        with patch("enrich_mte_fallback._export_js"):
            run_enrichment(json_path=tmp.name, dry_run=False, piso_nacional_valor=None)

        new_mtime = os.path.getmtime(tmp.name)
        self.assertEqual(
            original_mtime, new_mtime,
            "JSON modificado mesmo quando stub retorna None — violação de AC3"
        )
        os.unlink(tmp.name)


# ──────────────────────────────────────────────────────────────────────────────
# Testes adicionais de governança
# ──────────────────────────────────────────────────────────────────────────────


class TestGovernanceHelpers(unittest.TestCase):
    """Additional helper / governance unit tests."""

    def test_enrichable_returns_false_for_valido(self):
        self.assertFalse(_is_field_enrichable(FIELD_VALIDO))

    def test_enrichable_returns_false_for_pdf_cct_with_value(self):
        self.assertFalse(_is_field_enrichable(FIELD_PDF_EXTRAIDO))

    def test_enrichable_returns_true_for_pending(self):
        self.assertTrue(_is_field_enrichable(FIELD_PENDENTE))

    def test_enrichable_returns_true_for_pdf_cct_null_value(self):
        self.assertTrue(_is_field_enrichable(FIELD_PDF_NULL_VALUE))

    def test_record_without_itens_cct_returns_zero_metrics(self):
        record = {"id_registro_reajuste": "X", "uf": "SP"}
        metrics = enrich_from_mte_fallback(record, None)
        self.assertEqual(metrics["preenchidos_mte"], 0)
        self.assertEqual(metrics["pendentes"], 0)

    def test_metrics_sum_correctly(self):
        """preenchidos_mte + pendentes = total fields processed (when no conflict)."""
        record = _make_record()
        instrumento = _make_instrumento({"piso_salarial": MTE_CAMPO_VALIDO})
        metrics = enrich_from_mte_fallback(record, instrumento)

        total = metrics["preenchidos_mte"] + metrics["pendentes"] + metrics["conflitos"]
        self.assertEqual(total, len(ELIGIBLE_FIELDS))

    def test_piso_nacional_requires_non_none_valor(self):
        """Piso Nacional must not trigger when piso_nacional_valor is None."""
        record = _make_record()
        metrics = enrich_from_mte_fallback(record, None, piso_nacional_valor=None)
        field = record["itens_cct"]["piso_salarial"]
        self.assertNotEqual(field.get("origem"), "fonte_oficial_nacional")
        self.assertEqual(metrics["preenchidos_piso_nacional"], 0)

    def test_eligible_fields_constant_contains_all_expected(self):
        expected = {"piso_salarial", "adicional_noturno", "auxilio_alimentacao",
                    "plr", "hora_extra", "sobreaviso", "jornada"}
        self.assertEqual(set(ELIGIBLE_FIELDS.keys()), expected)

    def test_only_piso_salarial_is_piso_nacional_eligible(self):
        """Only piso_salarial maps to True in ELIGIBLE_FIELDS."""
        piso_nacional_true = [k for k, v in ELIGIBLE_FIELDS.items() if v is True]
        self.assertEqual(piso_nacional_true, ["piso_salarial"])


if __name__ == "__main__":
    unittest.main()

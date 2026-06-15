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


# ──────────────────────────────────────────────────────────────────────────────
# PRJ-66 — 12 novos cenários de teste (AC1–AC7)
# ──────────────────────────────────────────────────────────────────────────────

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from parse_mte_instrumento import build_fonte_oficial_mte, parse_mte_instrumento


# ── Scenario 1: registro sem fonte_oficial_mte não quebra (AC1) ──────────────


class TestPRJ66_AC1_NoFonteOficialMTE(unittest.TestCase):
    """AC1: Record without fonte_oficial_mte section must not raise errors."""

    def test_record_without_fonte_oficial_mte_does_not_break(self):
        record = _make_record()
        self.assertNotIn("fonte_oficial_mte", record)

        # enrich_from_mte_fallback must not raise even without fonte_oficial_mte
        metrics = enrich_from_mte_fallback(record, None)
        self.assertEqual(metrics["preenchidos_mte"], 0)

    def test_run_enrichment_with_missing_fonte_oficial_mte_field(self):
        record = _make_record()
        tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        )
        json.dump(_make_base_json([record]), tmp, ensure_ascii=False, indent=2)
        tmp.flush()
        tmp.close()

        try:
            with patch("enrich_mte_fallback.lookup_mte_instrumento_coletivo", return_value=None), \
                 patch("enrich_mte_fallback._export_js"):
                metrics = run_enrichment(json_path=tmp.name, dry_run=True)
            self.assertEqual(metrics["registros_processados"], 1)
        finally:
            os.unlink(tmp.name)


# ── Scenario 2: URL oficial registra referência sem alterar itens_cct (AC4) ──


class TestPRJ66_AC4_UrlReferenceNoItensChange(unittest.TestCase):
    """AC4: URL reference saves fonte_oficial_mte without modifying itens_cct."""

    def test_url_reference_registered_no_itens_cct_change(self):
        instrumento = parse_mte_instrumento(
            tipo_referencia="url",
            url="https://mediador.mte.gov.br/instrumento/12345",
        )
        self.assertIsNotNone(instrumento)
        self.assertEqual(instrumento["campos"], {})
        self.assertEqual(instrumento["tipo_referencia"], "url")

    def test_url_fonte_oficial_mte_status_localizado(self):
        instrumento = parse_mte_instrumento(
            tipo_referencia="url",
            url="https://mediador.mte.gov.br/instrumento/12345",
        )
        fonte = build_fonte_oficial_mte(
            tipo_referencia="url",
            instrumento=instrumento,
            url="https://mediador.mte.gov.br/instrumento/12345",
        )
        self.assertEqual(fonte["status_consulta"], "localizado")
        self.assertEqual(fonte["tipo_referencia"], "url")

    def test_url_reference_does_not_enrich_itens_cct_via_run_enrichment(self):
        record = _make_record()
        tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        )
        json.dump(_make_base_json([record]), tmp, ensure_ascii=False, indent=2)
        tmp.flush()
        tmp.close()

        try:
            with patch("enrich_mte_fallback._export_js"):
                metrics = run_enrichment(
                    json_path=tmp.name,
                    dry_run=True,
                    mte_source="https://mediador.mte.gov.br/instrumento/12345",
                    mte_tipo="url",
                )
            self.assertEqual(metrics["preenchidos_mte"], 0)
        finally:
            os.unlink(tmp.name)


# ── Scenario 3: arquivo processável preenche campo pendente (AC2 / AC7) ──────


class TestPRJ66_AC2_ArquivoProcessavel(unittest.TestCase):
    """AC2/AC7: processable MTE file fills pending field with traceability."""

    def test_mte_file_with_campos_fills_pending_field(self):
        record = _make_record()
        instrumento_fake = _make_instrumento({"piso_salarial": MTE_CAMPO_VALIDO})

        with patch("enrich_mte_fallback.parse_mte_instrumento", return_value=instrumento_fake), \
             patch("enrich_mte_fallback._export_js"):
            tmp = tempfile.NamedTemporaryFile(
                mode="w", suffix=".json", delete=False, encoding="utf-8"
            )
            json.dump(_make_base_json([record]), tmp, ensure_ascii=False, indent=2)
            tmp.flush()
            tmp.close()

            try:
                metrics = run_enrichment(
                    json_path=tmp.name,
                    dry_run=True,
                    mte_file="/tmp/fake_instrumento.pdf",
                    mte_tipo="arquivo",
                )
                self.assertGreater(metrics["preenchidos_mte"], 0)
            finally:
                os.unlink(tmp.name)


# ── Scenario 4: campo pdf_cct com valor não é sobrescrito (AC3) ──────────────


class TestPRJ66_AC3_PdfCctProtection(unittest.TestCase):
    """AC3: pdf_cct field with non-null value must not be overwritten."""

    def test_pdf_cct_field_not_overwritten(self):
        record = _make_record({"itens_cct": {"piso_salarial": copy.deepcopy(FIELD_PDF_EXTRAIDO)}})
        instrumento = _make_instrumento({"piso_salarial": MTE_CAMPO_VALIDO})

        enrich_from_mte_fallback(record, instrumento)

        field = record["itens_cct"]["piso_salarial"]
        # Different values → conflict, not overwrite
        self.assertNotEqual(field.get("status_parametro"), "extraido_para_revisao")
        # Original value preserved in opcoes_identificadas
        if field.get("status_parametro") == "conflito":
            vals = {o["valor"] for o in field["opcoes_identificadas"]}
            self.assertIn(1540.47, vals)


# ── Scenario 5: campo valido não é sobrescrito (AC3) ─────────────────────────


class TestPRJ66_AC3_ValidoProtection(unittest.TestCase):
    """AC3: field with status_parametro 'valido' must never be overwritten."""

    def test_valido_not_overwritten_by_mte(self):
        record = _make_record({"itens_cct": {"piso_salarial": copy.deepcopy(FIELD_VALIDO)}})
        instrumento = _make_instrumento({"piso_salarial": MTE_CAMPO_VALIDO})

        enrich_from_mte_fallback(record, instrumento)

        field = record["itens_cct"]["piso_salarial"]
        self.assertEqual(field["status_parametro"], "valido")
        self.assertEqual(field["valor"], 1500.00)


# ── Scenario 6: divergência PDF × MTE vira conflito (AC3) ────────────────────


class TestPRJ66_AC3_ConflictDetection(unittest.TestCase):
    """AC3: PDF vs MTE divergence must produce status 'conflito'."""

    def test_divergence_produces_conflito(self):
        record = _make_record({"itens_cct": {"piso_salarial": copy.deepcopy(FIELD_PDF_EXTRAIDO)}})
        instrumento = _make_instrumento({"piso_salarial": MTE_CAMPO_VALIDO})  # 1620 != 1540.47

        metrics = enrich_from_mte_fallback(record, instrumento)

        field = record["itens_cct"]["piso_salarial"]
        self.assertEqual(field["status_parametro"], "conflito")
        self.assertEqual(metrics["conflitos"], 1)
        opcoes_fontes = {o["fonte"] for o in field["opcoes_identificadas"]}
        self.assertIn("pdf_cct", opcoes_fontes)
        self.assertIn("fonte_oficial_mte", opcoes_fontes)


# ── Scenario 7: Piso Nacional só entra para piso geral (AC5 rule) ────────────


class TestPRJ66_PisoNacionalOnlyForPisoGeral(unittest.TestCase):
    """Piso Nacional must only be applied to general piso_salarial."""

    def test_piso_nacional_applied_only_to_piso_geral(self):
        record = _make_record()
        metrics = enrich_from_mte_fallback(record, None, piso_nacional_valor=1412.00)

        piso = record["itens_cct"]["piso_salarial"]
        self.assertEqual(piso["origem"], "fonte_oficial_nacional")
        self.assertEqual(metrics["preenchidos_piso_nacional"], 1)

        for campo in ("adicional_noturno", "auxilio_alimentacao", "plr",
                      "hora_extra", "sobreaviso", "jornada"):
            f = record["itens_cct"][campo]
            self.assertNotEqual(f.get("origem"), "fonte_oficial_nacional",
                                f"Piso Nacional indevidamente aplicado a '{campo}'")

    def test_piso_nacional_blocked_for_por_cargo(self):
        field = copy.deepcopy(FIELD_PENDENTE)
        field["por_cargo"] = [{"cargo": "analista_suporte_i", "valor": None}]
        record = _make_record({"itens_cct": {"piso_salarial": field}})

        metrics = enrich_from_mte_fallback(record, None, piso_nacional_valor=1412.00)
        self.assertEqual(metrics["preenchidos_piso_nacional"], 0)


# ── Scenario 8: métricas emitidas corretamente (AC5) ─────────────────────────


class TestPRJ66_AC5_MetricsReport(unittest.TestCase):
    """AC5: metrics report must include all required fields."""

    def test_metrics_contain_all_required_keys(self):
        record = _make_record()
        tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        )
        json.dump(_make_base_json([record]), tmp, ensure_ascii=False, indent=2)
        tmp.flush()
        tmp.close()

        try:
            with patch("enrich_mte_fallback.lookup_mte_instrumento_coletivo", return_value=None), \
                 patch("enrich_mte_fallback._export_js"):
                metrics = run_enrichment(json_path=tmp.name, dry_run=True)

            required_keys = {
                "registros_processados",
                "instrumentos_mte_localizados",
                "instrumentos_mte_nao_localizados",
                "preenchidos_mte",
                "pendentes",
                "conflitos",
                "preenchidos_piso_nacional",
                "json_js_atualizado",
            }
            for key in required_keys:
                self.assertIn(key, metrics, f"Chave obrigatória ausente nas métricas: {key}")
        finally:
            os.unlink(tmp.name)

    def test_json_js_atualizado_false_when_no_real_data(self):
        record = _make_record()
        tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        )
        json.dump(_make_base_json([record]), tmp, ensure_ascii=False, indent=2)
        tmp.flush()
        tmp.close()

        try:
            with patch("enrich_mte_fallback.lookup_mte_instrumento_coletivo", return_value=None), \
                 patch("enrich_mte_fallback._export_js"):
                metrics = run_enrichment(json_path=tmp.name, dry_run=False, piso_nacional_valor=None)
            self.assertFalse(metrics["json_js_atualizado"])
        finally:
            os.unlink(tmp.name)


# ── Scenario 9: dry-run não altera JSON/JS (AC2) ─────────────────────────────


class TestPRJ66_AC2_DryRunNoWrite(unittest.TestCase):
    """AC2: --dry-run must not modify any file."""

    def test_dry_run_does_not_write_files(self):
        record = _make_record()
        tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        )
        json.dump(_make_base_json([record]), tmp, ensure_ascii=False, indent=2)
        tmp.flush()
        tmp.close()
        original_mtime = os.path.getmtime(tmp.name)

        try:
            instrumento_fake = _make_instrumento({"piso_salarial": MTE_CAMPO_VALIDO})
            with patch("enrich_mte_fallback.lookup_mte_instrumento_coletivo",
                       return_value=instrumento_fake), \
                 patch("enrich_mte_fallback._export_js") as mock_export:
                metrics = run_enrichment(json_path=tmp.name, dry_run=True)

            self.assertFalse(metrics["json_js_atualizado"])
            self.assertEqual(os.path.getmtime(tmp.name), original_mtime)
            mock_export.assert_not_called()
        finally:
            os.unlink(tmp.name)


# ── Scenario 10: execução real atualiza JSON/JS quando há dado real (AC2) ────


class TestPRJ66_AC2_RealRunUpdatesFiles(unittest.TestCase):
    """AC2: real run must update JSON and JS when real data is found."""

    def test_real_run_updates_json_and_js(self):
        record = _make_record()
        tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        )
        json.dump(_make_base_json([record]), tmp, ensure_ascii=False, indent=2)
        tmp.flush()
        tmp.close()

        try:
            instrumento_fake = _make_instrumento({"piso_salarial": MTE_CAMPO_VALIDO})
            with patch("enrich_mte_fallback.lookup_mte_instrumento_coletivo",
                       return_value=instrumento_fake), \
                 patch("enrich_mte_fallback._export_js") as mock_export:
                metrics = run_enrichment(json_path=tmp.name, dry_run=False)

            self.assertTrue(metrics["json_js_atualizado"])
            mock_export.assert_called_once()

            with open(tmp.name, "r", encoding="utf-8") as f:
                saved = json.load(f)
            piso = saved["registros"][0]["itens_cct"]["piso_salarial"]
            self.assertEqual(piso["origem"], "fonte_oficial_mte")
        finally:
            os.unlink(tmp.name)


# ── Scenario 11: referência manual sem fonte_textual não preenche itens_cct (AC6) ──


class TestPRJ66_AC6_ManualNoFonteTextual(unittest.TestCase):
    """AC6: 'manual' reference must NOT fill itens_cct without fonte_textual."""

    def test_manual_reference_produces_empty_campos(self):
        instrumento = parse_mte_instrumento(
            tipo_referencia="manual",
            codigo_instrumento="MTE-CCT-2025-SP-001",
            observacao="Referência registrada pelo operador",
        )
        self.assertIsNotNone(instrumento)
        self.assertEqual(instrumento["campos"], {})
        self.assertEqual(instrumento["tipo_referencia"], "manual")

    def test_manual_reference_does_not_enrich_itens_cct(self):
        record = _make_record()
        instrumento = parse_mte_instrumento(
            tipo_referencia="manual",
            codigo_instrumento="MTE-CCT-2025-SP-001",
        )

        # enrich_from_mte_fallback with empty campos → no fields filled
        metrics = enrich_from_mte_fallback(record, instrumento)
        self.assertEqual(metrics["preenchidos_mte"], 0)

        for campo in record["itens_cct"].values():
            self.assertNotEqual(
                campo.get("origem"), "fonte_oficial_mte",
                "Campo preenchido via referência manual sem fonte_textual — violação AC6"
            )

    def test_manual_reference_via_run_enrichment_no_itens_change(self):
        record = _make_record()
        tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        )
        json.dump(_make_base_json([record]), tmp, ensure_ascii=False, indent=2)
        tmp.flush()
        tmp.close()

        try:
            with patch("enrich_mte_fallback._export_js"):
                metrics = run_enrichment(
                    json_path=tmp.name,
                    dry_run=True,
                    mte_source="MTE-CCT-2025-SP-001",
                    mte_tipo="manual",
                )
            self.assertEqual(metrics["preenchidos_mte"], 0)
        finally:
            os.unlink(tmp.name)


# ── Scenario 12: parser MTE isolado, retorna dict compatível (AC7) ───────────


class TestPRJ66_AC7_ParserIsolation(unittest.TestCase):
    """AC7: MTE parser operates independently and returns compatible dict."""

    def test_parser_returns_compatible_dict_structure(self):
        """parse_mte_instrumento must return dict compatible with enrich_from_mte_fallback."""
        instrumento = parse_mte_instrumento(
            tipo_referencia="url",
            url="https://mediador.mte.gov.br/instrumento/99999",
        )
        self.assertIsNotNone(instrumento)
        # Required top-level keys
        for key in ("numero_registro", "tipo", "vigencia_inicio", "vigencia_fim",
                    "url_documento", "campos"):
            self.assertIn(key, instrumento, f"Chave obrigatória ausente: {key}")
        self.assertIsInstance(instrumento["campos"], dict)

    def test_parser_with_arquivo_nonexistent_returns_none(self):
        instrumento = parse_mte_instrumento(
            file_path="/tmp/arquivo_que_nao_existe.pdf",
            tipo_referencia="arquivo",
        )
        self.assertIsNone(instrumento)

    def test_parser_does_not_import_extract_cct_items(self):
        """Parser must NOT use any module from the CCT PDF extraction pipeline."""
        import parse_mte_instrumento as pmi_module

        source_path = pmi_module.__file__
        with open(source_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        # Check that no non-comment, non-docstring line contains a Python import
        # of extract_cct_items. We match only actual import statements (start of line).
        import re as _re
        import_pattern = _re.compile(
            r"^\s*(?:import\s+extract_cct_items|from\s+extract_cct_items\s+import)",
        )
        violations = [
            line.rstrip() for line in lines if import_pattern.match(line)
        ]
        self.assertEqual(
            violations, [],
            f"parse_mte_instrumento.py contém importação proibida do pipeline CCT:\n"
            + "\n".join(violations),
        )

    def test_enrich_from_mte_fallback_accepts_parser_output(self):
        """enrich_from_mte_fallback must work with parse_mte_instrumento output."""
        instrumento_url = parse_mte_instrumento(
            tipo_referencia="url",
            url="https://mediador.mte.gov.br/instrumento/12345",
        )
        # URL type → empty campos → no fields changed, but function must not raise
        record = _make_record()
        metrics = enrich_from_mte_fallback(record, instrumento_url)
        self.assertEqual(metrics["preenchidos_mte"], 0)

    def test_build_fonte_oficial_mte_structure(self):
        """build_fonte_oficial_mte must produce the required fonte_oficial_mte schema."""
        instrumento = parse_mte_instrumento(
            tipo_referencia="url",
            url="https://mediador.mte.gov.br/instrumento/12345",
        )
        fonte = build_fonte_oficial_mte(
            tipo_referencia="url",
            instrumento=instrumento,
            url="https://mediador.mte.gov.br/instrumento/12345",
        )
        required_keys = {
            "disponivel", "tipo_referencia", "url", "codigo_instrumento",
            "arquivo_origem", "data_consulta", "status_consulta", "observacao",
        }
        for key in required_keys:
            self.assertIn(key, fonte, f"Chave obrigatória ausente em fonte_oficial_mte: {key}")

    def test_parser_invalid_tipo_referencia_returns_none(self):
        result = parse_mte_instrumento(
            tipo_referencia="invalido",
        )
        self.assertIsNone(result)

    def test_parser_arquivo_without_file_path_returns_none(self):
        result = parse_mte_instrumento(
            file_path=None,
            tipo_referencia="arquivo",
        )
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()

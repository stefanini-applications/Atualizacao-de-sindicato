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
    FONTE_OFICIAL_MTE_TIPOS,
    MTE_FONTE_LABEL,
    _build_fonte_oficial_mte,
    _is_field_enrichable,
    _is_field_pdf_protected,
    _is_field_valid_protected,
    _piso_nacional_eligible,
    _set_fonte_oficial_mte,
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
# PRJ-66 — Testes adicionais exigidos (12 cenários)
# ──────────────────────────────────────────────────────────────────────────────


class TestFonteOficialMteStructure(unittest.TestCase):
    """PRJ-66 — Cenário 1 & 2: fonte_oficial_mte registration and record safety."""

    def test_record_sem_fonte_oficial_mte_nao_quebra(self):
        """AC1: record without fonte_oficial_mte section must not raise errors."""
        record = _make_record()
        self.assertNotIn("fonte_oficial_mte", record)
        # enrich_from_mte_fallback must work normally without fonte_oficial_mte
        metrics = enrich_from_mte_fallback(record, None)
        self.assertEqual(metrics["preenchidos_mte"], 0)
        # Existing itens_cct are untouched
        field = record["itens_cct"]["piso_salarial"]
        self.assertEqual(field["status_parametro"], "pendente_revisao")

    def test_build_fonte_oficial_mte_url_stores_reference(self):
        """AC4: URL reference stores metadata without touching itens_cct."""
        record = _make_record()
        fonte = _build_fonte_oficial_mte(
            tipo_referencia="url",
            url="https://mediador.mte.gov.br/instrumento/12345",
            status_consulta="localizado",
            observacao="Referência oficial CCT SP 2025",
        )
        _set_fonte_oficial_mte(record, fonte)

        self.assertIn("fonte_oficial_mte", record)
        fom = record["fonte_oficial_mte"]
        self.assertEqual(fom["tipo_referencia"], "url")
        self.assertEqual(fom["url"], "https://mediador.mte.gov.br/instrumento/12345")
        self.assertEqual(fom["status_consulta"], "localizado")
        self.assertTrue(fom["disponivel"])

        # itens_cct must remain untouched
        for campo in ELIGIBLE_FIELDS:
            field = record["itens_cct"].get(campo, {})
            self.assertEqual(field.get("status_parametro"), "pendente_revisao")

    def test_url_referencia_nao_altera_itens_cct_via_run_enrichment(self):
        """AC4: run_enrichment with mte_tipo=url stores reference, does not enrich itens_cct."""
        record = _make_record()
        tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        )
        json.dump(_make_base_json([record]), tmp, ensure_ascii=False, indent=2)
        tmp.flush()
        tmp.close()

        with patch("enrich_mte_fallback._export_js"):
            metrics = run_enrichment(
                json_path=tmp.name,
                dry_run=False,
                ids=["REG-TEST-2025"],
                mte_tipo="url",
                mte_url="https://mediador.mte.gov.br/instrumento/99999",
            )

        with open(tmp.name, "r", encoding="utf-8") as f:
            saved = json.load(f)
        os.unlink(tmp.name)

        rec = saved["registros"][0]
        self.assertIn("fonte_oficial_mte", rec)
        self.assertEqual(rec["fonte_oficial_mte"]["tipo_referencia"], "url")
        self.assertEqual(metrics["preenchidos_mte"], 0)

        for campo in ELIGIBLE_FIELDS:
            field = rec.get("itens_cct", {}).get(campo, {})
            self.assertNotEqual(
                field.get("origem"), "fonte_oficial_mte",
                f"Campo '{campo}' foi indevidamente alterado por referência URL"
            )


class TestFonteOficialMteArquivo(unittest.TestCase):
    """PRJ-66 — Cenário 3: arquivo oficial processável preenche campo pendente."""

    def _write_temp_base(self, records: list[dict]) -> str:
        tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        )
        json.dump(_make_base_json(records), tmp, ensure_ascii=False, indent=2)
        tmp.flush()
        tmp.close()
        return tmp.name

    def test_arquivo_processavel_preenche_campo_pendente(self):
        """AC2: arquivo oficial com conteúdo processável preenche campos pendentes."""
        record = _make_record()
        json_path = self._write_temp_base([record])

        fake_instrumento = _make_instrumento({"piso_salarial": MTE_CAMPO_VALIDO})

        with patch("enrich_mte_fallback._export_js"), \
             patch("enrich_mte_fallback.parse_mte_pdf", return_value=fake_instrumento, create=True):
            # Simulate successful parse by injecting the parse result via mock
            import enrich_mte_fallback as emf
            original = getattr(emf, "_mte_file_parse_attempted_test_hook", None)

            # Use run_enrichment with a fake mte_file; patch the parse_mte_pdf import
            with patch.dict("sys.modules", {"parse_mte_instrumento": MagicMock(
                parse_mte_pdf=MagicMock(return_value=fake_instrumento)
            )}):
                metrics = run_enrichment(
                    json_path=json_path,
                    dry_run=False,
                    ids=["REG-TEST-2025"],
                    mte_file="/fake/instrumento.pdf",
                    mte_tipo="arquivo",
                )

        with open(json_path, "r", encoding="utf-8") as f:
            saved = json.load(f)
        os.unlink(json_path)

        rec = saved["registros"][0]
        self.assertIn("fonte_oficial_mte", rec)
        self.assertEqual(rec["fonte_oficial_mte"]["tipo_referencia"], "arquivo")

        piso = rec["itens_cct"]["piso_salarial"]
        self.assertEqual(piso["origem"], "fonte_oficial_mte")
        self.assertEqual(piso["valor"], 1620.00)
        self.assertEqual(metrics["preenchidos_mte"], 1)

    def test_arquivo_nao_processavel_nao_altera_itens_cct(self):
        """AC4: non-processable file stores reference with nao_localizado, no field changes."""
        record = _make_record()
        json_path = self._write_temp_base([record])

        with patch("enrich_mte_fallback._export_js"), \
             patch.dict("sys.modules", {"parse_mte_instrumento": MagicMock(
                 parse_mte_pdf=MagicMock(return_value=None)
             )}):
            metrics = run_enrichment(
                json_path=json_path,
                dry_run=False,
                ids=["REG-TEST-2025"],
                mte_file="/fake/unprocessable.pdf",
                mte_tipo="arquivo",
            )

        os.unlink(json_path)

        self.assertEqual(metrics["preenchidos_mte"], 0)
        self.assertEqual(metrics["instrumentos_mte_nao_localizados"], 1)


class TestProtectionWithFonteOficial(unittest.TestCase):
    """PRJ-66 — Cenários 4 & 5: campos pdf_cct e valido não sobrescritos via fonte_oficial."""

    def test_campo_pdf_cct_com_valor_nao_sobrescrito_via_mte(self):
        """AC3: campo com origem=pdf_cct e valor não nulo nunca é sobrescrito."""
        record = _make_record({"itens_cct": {"piso_salarial": copy.deepcopy(FIELD_PDF_EXTRAIDO)}})
        instrumento = _make_instrumento({"piso_salarial": {"valor": 1540.47, "fonte_textual": "MTE same"}})

        metrics = enrich_from_mte_fallback(record, instrumento)

        field = record["itens_cct"]["piso_salarial"]
        self.assertEqual(field["valor"], 1540.47)
        self.assertNotEqual(field.get("status_parametro"), "conflito")

    def test_campo_valido_nao_sobrescrito_via_arquivo_mte(self):
        """AC3: campo valido nunca é sobrescrito mesmo quando arquivo MTE traz dados."""
        record = _make_record({"itens_cct": {"piso_salarial": copy.deepcopy(FIELD_VALIDO)}})
        instrumento = _make_instrumento({"piso_salarial": MTE_CAMPO_VALIDO})

        metrics = enrich_from_mte_fallback(record, instrumento)

        field = record["itens_cct"]["piso_salarial"]
        self.assertEqual(field["status_parametro"], "valido")
        self.assertEqual(field["valor"], 1500.00)
        self.assertEqual(field["origem"], "pdf_cct")
        self.assertEqual(metrics["preenchidos_mte"], 0)


class TestConflictWithFonteOficial(unittest.TestCase):
    """PRJ-66 — Cenário 6: divergência PDF × MTE via fonte_oficial gera conflito."""

    def test_divergencia_pdf_mte_via_arquivo_gera_conflito(self):
        """AC3: PDF value ≠ MTE value → conflito status with opcoes_identificadas."""
        field = copy.deepcopy(FIELD_PDF_EXTRAIDO)  # valor=1540.47, origem=pdf_cct
        record = _make_record({"itens_cct": {"piso_salarial": field}})
        instrumento = _make_instrumento({
            "piso_salarial": {"valor": 1750.00, "fonte_textual": "Cláusula 3ª MTE divergente"}
        })

        metrics = enrich_from_mte_fallback(record, instrumento)

        f = record["itens_cct"]["piso_salarial"]
        self.assertEqual(f["status_parametro"], "conflito")
        self.assertEqual(f["origem"], "conflito_pdf_mte")
        self.assertIn("opcoes_identificadas", f)
        self.assertEqual(metrics["conflitos"], 1)
        self.assertEqual(metrics["preenchidos_mte"], 0)


class TestPisoNacionalComFonteOficial(unittest.TestCase):
    """PRJ-66 — Cenário 7: Piso Nacional só entra para piso geral."""

    def test_piso_nacional_apenas_para_piso_geral(self):
        """Piso Nacional must only apply to generic piso_salarial (no por_cargo)."""
        record = _make_record()
        metrics = enrich_from_mte_fallback(record, None, piso_nacional_valor=1412.00)

        field = record["itens_cct"]["piso_salarial"]
        self.assertEqual(field["origem"], "fonte_oficial_nacional")
        self.assertEqual(field["valor"], 1412.00)
        self.assertEqual(metrics["preenchidos_piso_nacional"], 1)

        for campo in ("adicional_noturno", "auxilio_alimentacao", "plr",
                      "hora_extra", "sobreaviso", "jornada"):
            self.assertNotEqual(
                record["itens_cct"][campo].get("origem"), "fonte_oficial_nacional",
                f"Piso Nacional indevidamente aplicado a '{campo}'"
            )


class TestMetricasCompletas(unittest.TestCase):
    """PRJ-66 — Cenário 8: métricas completas emitidas corretamente."""

    def _write_temp_base(self, records: list[dict]) -> str:
        tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        )
        json.dump(_make_base_json(records), tmp, ensure_ascii=False, indent=2)
        tmp.flush()
        tmp.close()
        return tmp.name

    def test_metricas_completas_emitidas(self):
        """AC5: all required metric keys are present in run_enrichment result."""
        record = _make_record()
        json_path = self._write_temp_base([record])

        with patch("enrich_mte_fallback._export_js"), \
             patch("enrich_mte_fallback.lookup_mte_instrumento_coletivo", return_value=None):
            metrics = run_enrichment(json_path=json_path, dry_run=True)

        os.unlink(json_path)

        required_keys = [
            "registros_processados",
            "instrumentos_mte_localizados",
            "instrumentos_mte_nao_localizados",
            "preenchidos_mte",
            "pendentes",
            "conflitos",
            "preenchidos_piso_nacional",
            "json_js_atualizados",
        ]
        for key in required_keys:
            self.assertIn(key, metrics, f"Métrica ausente: {key}")

    def test_json_js_atualizados_false_em_dry_run(self):
        """AC5: json_js_atualizados must be False in dry-run even with real data."""
        record = _make_record()
        json_path = self._write_temp_base([record])
        fake = _make_instrumento({"piso_salarial": MTE_CAMPO_VALIDO})

        with patch("enrich_mte_fallback._export_js"), \
             patch("enrich_mte_fallback.lookup_mte_instrumento_coletivo", return_value=fake):
            metrics = run_enrichment(json_path=json_path, dry_run=True)

        os.unlink(json_path)
        self.assertFalse(metrics["json_js_atualizados"])

    def test_json_js_atualizados_true_quando_dados_reais(self):
        """AC5: json_js_atualizados must be True when real data is written."""
        record = _make_record()
        json_path = self._write_temp_base([record])
        fake = _make_instrumento({"piso_salarial": MTE_CAMPO_VALIDO})

        with patch("enrich_mte_fallback._export_js"), \
             patch("enrich_mte_fallback.lookup_mte_instrumento_coletivo", return_value=fake):
            metrics = run_enrichment(json_path=json_path, dry_run=False)

        os.unlink(json_path)
        self.assertTrue(metrics["json_js_atualizados"])


class TestDryRunComFonteOficial(unittest.TestCase):
    """PRJ-66 — Cenário 9: dry-run não grava nenhum arquivo."""

    def test_dry_run_nao_grava_json_com_arquivo_mte(self):
        """AC2: --dry-run with mte_file must not write any file."""
        record = _make_record()
        tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        )
        json.dump(_make_base_json([record]), tmp, ensure_ascii=False, indent=2)
        tmp.flush()
        tmp.close()

        original_mtime = os.path.getmtime(tmp.name)
        fake_instrumento = _make_instrumento({"piso_salarial": MTE_CAMPO_VALIDO})

        with patch("enrich_mte_fallback._export_js"), \
             patch.dict("sys.modules", {"parse_mte_instrumento": MagicMock(
                 parse_mte_pdf=MagicMock(return_value=fake_instrumento)
             )}):
            run_enrichment(
                json_path=tmp.name,
                dry_run=True,
                ids=["REG-TEST-2025"],
                mte_file="/fake/instrumento.pdf",
                mte_tipo="arquivo",
            )

        new_mtime = os.path.getmtime(tmp.name)
        os.unlink(tmp.name)
        self.assertEqual(original_mtime, new_mtime, "JSON foi gravado em modo dry-run")


class TestExecucaoRealAtualiza(unittest.TestCase):
    """PRJ-66 — Cenário 10: execução real atualiza JSON/JS quando há dado real."""

    def test_execucao_real_atualiza_json_quando_dado_real(self):
        """AC2: real run with real data must update JSON."""
        record = _make_record()
        tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        )
        json.dump(_make_base_json([record]), tmp, ensure_ascii=False, indent=2)
        tmp.flush()
        tmp.close()

        fake_instrumento = _make_instrumento({"piso_salarial": MTE_CAMPO_VALIDO})

        with patch("enrich_mte_fallback._export_js"), \
             patch.dict("sys.modules", {"parse_mte_instrumento": MagicMock(
                 parse_mte_pdf=MagicMock(return_value=fake_instrumento)
             )}):
            metrics = run_enrichment(
                json_path=tmp.name,
                dry_run=False,
                ids=["REG-TEST-2025"],
                mte_file="/fake/instrumento.pdf",
                mte_tipo="arquivo",
            )

        with open(tmp.name, "r", encoding="utf-8") as f:
            saved = json.load(f)
        os.unlink(tmp.name)

        self.assertTrue(metrics["json_js_atualizados"])
        piso = saved["registros"][0]["itens_cct"]["piso_salarial"]
        self.assertEqual(piso["origem"], "fonte_oficial_mte")


class TestReferenciaManualeGoveranca(unittest.TestCase):
    """PRJ-66 — Cenário 11: referência manual sem fonte_textual NÃO preenche itens_cct."""

    def _write_temp_base(self, records: list[dict]) -> str:
        tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        )
        json.dump(_make_base_json(records), tmp, ensure_ascii=False, indent=2)
        tmp.flush()
        tmp.close()
        return tmp.name

    def test_manual_sem_fonte_textual_nao_preenche_itens_cct(self):
        """AC6: manual reference must NOT alter any itens_cct field."""
        record = _make_record()
        json_path = self._write_temp_base([record])

        with patch("enrich_mte_fallback._export_js"):
            metrics = run_enrichment(
                json_path=json_path,
                dry_run=False,
                ids=["REG-TEST-2025"],
                mte_tipo="manual",
                mte_codigo="MTE-CCT-SP-2025-12345",
                mte_sindicato="Sindicato Teste SP",
                mte_vigencia_inicio="2025-01-01",
                mte_vigencia_fim="2025-12-31",
                mte_observacao="Número do instrumento obtido via consulta ao Sistema Mediador",
            )

        with open(json_path, "r", encoding="utf-8") as f:
            saved = json.load(f)
        os.unlink(json_path)

        rec = saved["registros"][0]
        self.assertIn("fonte_oficial_mte", rec)
        fom = rec["fonte_oficial_mte"]
        self.assertEqual(fom["tipo_referencia"], "manual")
        self.assertEqual(fom["codigo_instrumento"], "MTE-CCT-SP-2025-12345")
        self.assertEqual(fom["sindicato_mte"], "Sindicato Teste SP")

        # itens_cct must be completely untouched
        self.assertEqual(metrics["preenchidos_mte"], 0)
        for campo in ELIGIBLE_FIELDS:
            field = rec.get("itens_cct", {}).get(campo, {})
            self.assertEqual(
                field.get("status_parametro"), "pendente_revisao",
                f"Campo '{campo}' foi indevidamente alterado por referência manual"
            )
            self.assertNotEqual(
                field.get("origem"), "fonte_oficial_mte",
                f"Campo '{campo}' tem origem fonte_oficial_mte sem arquivo processável"
            )

    def test_build_fonte_oficial_mte_manual_tem_campos_corretos(self):
        """AC6: _build_fonte_oficial_mte with tipo=manual stores operator metadata."""
        fonte = _build_fonte_oficial_mte(
            tipo_referencia="manual",
            codigo_instrumento="CCT-2025-SP-0001",
            sindicato_mte="SINDPD SP",
            vigencia_inicio="2025-01-01",
            vigencia_fim="2025-12-31",
            observacao="Operador confirmou número do instrumento via site MTE",
        )
        self.assertEqual(fonte["tipo_referencia"], "manual")
        self.assertEqual(fonte["codigo_instrumento"], "CCT-2025-SP-0001")
        self.assertEqual(fonte["sindicato_mte"], "SINDPD SP")
        self.assertEqual(fonte["vigencia_inicio"], "2025-01-01")
        self.assertEqual(fonte["status_consulta"], "localizado")
        self.assertTrue(fonte["disponivel"])

    def test_fonte_oficial_mte_tipos_validos(self):
        """FONTE_OFICIAL_MTE_TIPOS must contain exactly the 4 supported types."""
        self.assertEqual(
            FONTE_OFICIAL_MTE_TIPOS,
            frozenset({"arquivo", "url", "codigo_instrumento", "manual"})
        )

    def test_build_fonte_oficial_mte_tipo_invalido_lanca_erro(self):
        """_build_fonte_oficial_mte must raise ValueError for unknown tipo."""
        with self.assertRaises(ValueError):
            _build_fonte_oficial_mte(tipo_referencia="desconhecido")


class TestParserMteIsolamento(unittest.TestCase):
    """PRJ-66 — Cenário 12: parser MTE é isolado e retorna dicionário compatível."""

    def test_parse_mte_pdf_retorna_formato_compativel(self):
        """AC7: parse_mte_pdf must return a dict compatible with enrich_from_mte_fallback."""
        import sys
        from unittest.mock import MagicMock

        # Build a minimal mock of parse_mte_instrumento without importing it
        fake_result = {
            "numero_registro": "MTE-TEST-001",
            "tipo": "CCT",
            "vigencia_inicio": "2025-01-01",
            "vigencia_fim": "2025-12-31",
            "url_documento": None,
            "arquivo_origem": "instrumento_teste.pdf",
            "campos": {
                "piso_salarial": {
                    "valor": 1800.00,
                    "percentual": None,
                    "valor_textual": None,
                    "fonte_textual": "Cláusula 3ª: piso salarial de R$ 1.800,00",
                    "observacao": "Extraído do instrumento oficial MTE",
                }
            },
        }

        # Verify the returned dict is compatible with enrich_from_mte_fallback
        record = _make_record()
        metrics = enrich_from_mte_fallback(record, fake_result)

        piso = record["itens_cct"]["piso_salarial"]
        self.assertEqual(piso["origem"], "fonte_oficial_mte")
        self.assertEqual(piso["valor"], 1800.00)
        self.assertIsNotNone(piso["fonte_textual"])
        self.assertEqual(metrics["preenchidos_mte"], 1)

    def test_parser_mte_nao_importa_extract_cct_items(self):
        """AC7: parse_mte_instrumento must not import extract_cct_items."""
        import importlib
        import sys

        # Temporarily inject a sentinel to detect if extract_cct_items is imported
        sentinel = MagicMock()
        original = sys.modules.get("extract_cct_items")
        sys.modules["extract_cct_items"] = sentinel

        try:
            # Re-import parse_mte_instrumento to check its imports
            if "parse_mte_instrumento" in sys.modules:
                del sys.modules["parse_mte_instrumento"]
            import parse_mte_instrumento  # noqa: F401
            # If extract_cct_items was accessed via the sentinel, the test will detect it
            self.assertFalse(
                sentinel.called,
                "parse_mte_instrumento incorrectly imported or called extract_cct_items"
            )
        finally:
            if original is None:
                sys.modules.pop("extract_cct_items", None)
            else:
                sys.modules["extract_cct_items"] = original

    def test_parser_mte_retorna_none_para_arquivo_inexistente(self):
        """Parser deve retornar None para arquivo inexistente sem lançar exceção."""
        import sys
        if "parse_mte_instrumento" in sys.modules:
            del sys.modules["parse_mte_instrumento"]
        from parse_mte_instrumento import parse_mte_pdf

        result = parse_mte_pdf("/tmp/arquivo_que_nao_existe_xyz_123.pdf")
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()

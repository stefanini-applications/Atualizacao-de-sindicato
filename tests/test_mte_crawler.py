"""
Testes automatizados para mte_crawler.py (PRJ-68).

Cobre os 10 cenários obrigatórios definidos na US:
  1.  Busca localizada — instrumento encontrado; campos preenchidos com fonte_textual.
  2.  Busca não localizada — status_consulta "nao_localizado"; campos permanecem pendentes.
  3.  Erro ou bloqueio — CAPTCHA/bloqueio/erro de rede; status registrado; sem contorno.
  4.  Dry-run — --dry-run não grava JSON, JS nem relatório.
  5.  Conflito PDF × MTE — valor MTE diverge; campo recebe status "conflito".
  6.  Proteção pdf_cct — campo com origem "pdf_cct" e valor não nulo não é alterado.
  7.  Proteção valido — campo com status_parametro "valido" não é alterado.
  8.  Piso Nacional restrito — só para piso_salarial geral; nunca cargos/benefícios/etc.
  9.  Campo sem fonte_textual — campo não preenchido quando fonte_textual ausente.
  10. Relatório gerado — reports/mte_auto_lookup_report.json criado com schema correto.
"""

import copy
import json
import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mte_crawler import (
    _build_search_params,
    _detect_block,
    _has_pending_fields,
    _is_pdf_bytes,
    download_mte_instrument,
    extract_mte_text_or_pdf,
    run_auto_lookup,
    search_mte_instrument,
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

MTE_CAMPO_VALIDO = {
    "valor": 1620.00,
    "percentual": None,
    "fonte_textual": "Cláusula 3ª do instrumento registrado no Sistema Mediador",
    "observacao": "Extraído do Sistema Mediador MTE",
}

MTE_CAMPO_SEM_FONTE_TEXTUAL = {
    "valor": 1620.00,
    "percentual": None,
    "fonte_textual": "",
    "observacao": "Campo sem evidência textual",
}


def _make_record(overrides: dict | None = None) -> dict:
    """Create a minimal record for testing."""
    base = {
        "id_registro_reajuste": "REG-TEST-2025",
        "uf": "SP",
        "sindicato": "Sindicato Teste",
        "categoria": "Tecnologia",
        "ano_referencia": 2025,
        "vigencia_inicio": "2025-01-01",
        "vigencia_fim": "2025-12-31",
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
        "url_documento": "https://example.com/instrumento.pdf",
        "campos": campos,
    }


def _make_base_json(records: list[dict]) -> dict:
    """Create a minimal base_parametros_sindicais.json structure."""
    return {
        "data_geracao": "2026-06-15T00:00:00+00:00",
        "registros": records,
    }


def _write_temp_base(records: list[dict]) -> str:
    """Write a temp JSON file with the given records, return its path."""
    tmp = tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, encoding="utf-8"
    )
    json.dump(_make_base_json(records), tmp, ensure_ascii=False, indent=2)
    tmp.flush()
    tmp.close()
    return tmp.name


# ──────────────────────────────────────────────────────────────────────────────
# Cenário 1 — Busca localizada
# ──────────────────────────────────────────────────────────────────────────────


class TestBuscaLocalizada(unittest.TestCase):
    """Cenário 1: instrumento encontrado; campos pendentes preenchidos com fonte_textual."""

    def _run_with_mock_instrumento(self) -> tuple[dict, dict]:
        record = _make_record()
        instrumento = _make_instrumento({"piso_salarial": MTE_CAMPO_VALIDO})

        fake_search_result = {
            "disponivel": True,
            "tipo_referencia": "crawler",
            "url": "https://www3.mte.gov.br/instrumento/12345.pdf",
            "codigo_instrumento": "12345",
            "data_consulta": "2026-06-17",
            "status_consulta": "localizado",
            "_content": b"%PDF-1.4 fake pdf content",
            "_text": None,
            "_content_type": "application/pdf",
        }

        with patch("mte_crawler.search_mte_instrument", return_value=fake_search_result), \
             patch("mte_crawler.download_mte_instrument", return_value=fake_search_result), \
             patch("mte_crawler.extract_mte_text_or_pdf", return_value=instrumento):
            from mte_crawler import _process_record
            per_record = _process_record(record)

        return record, per_record

    def test_piso_salarial_preenchido_com_origem_mte(self):
        record, _ = self._run_with_mock_instrumento()
        field = record["itens_cct"]["piso_salarial"]
        self.assertEqual(field["status_parametro"], "extraido_para_revisao")
        self.assertEqual(field["origem"], "fonte_oficial_mte")

    def test_piso_salarial_tem_fonte_textual(self):
        record, _ = self._run_with_mock_instrumento()
        field = record["itens_cct"]["piso_salarial"]
        self.assertIsNotNone(field.get("fonte_textual"))
        self.assertNotEqual(field.get("fonte_textual"), "")

    def test_fonte_oficial_mte_registrada_no_record(self):
        record, _ = self._run_with_mock_instrumento()
        self.assertIn("fonte_oficial_mte", record)
        fom = record["fonte_oficial_mte"]
        self.assertEqual(fom["tipo_referencia"], "crawler")
        self.assertEqual(fom["status_consulta"], "localizado")
        self.assertTrue(fom["disponivel"])

    def test_per_record_campos_preenchidos_nao_vazio(self):
        _, per_record = self._run_with_mock_instrumento()
        self.assertIn("piso_salarial", per_record.get("campos_preenchidos", []))

    def test_per_record_status_busca_localizado(self):
        _, per_record = self._run_with_mock_instrumento()
        self.assertEqual(per_record["status_busca"], "localizado")

    def test_per_record_url_localizada_preenchida(self):
        _, per_record = self._run_with_mock_instrumento()
        self.assertIsNotNone(per_record.get("url_localizada"))


# ──────────────────────────────────────────────────────────────────────────────
# Cenário 2 — Busca não localizada
# ──────────────────────────────────────────────────────────────────────────────


class TestBuscaNaoLocalizada(unittest.TestCase):
    """Cenário 2: instrumento não encontrado; campos permanecem pendentes."""

    def _run_nao_localizado(self) -> tuple[dict, dict]:
        record = _make_record()
        fake_search_result = {
            "disponivel": False,
            "tipo_referencia": "crawler",
            "url": None,
            "codigo_instrumento": None,
            "data_consulta": "2026-06-17",
            "status_consulta": "nao_localizado",
            "_content": None,
            "_text": None,
        }

        with patch("mte_crawler.search_mte_instrument", return_value=fake_search_result):
            from mte_crawler import _process_record
            per_record = _process_record(record)

        return record, per_record

    def test_campos_permanecem_pendentes(self):
        record, _ = self._run_nao_localizado()
        for campo_name, field in record["itens_cct"].items():
            self.assertEqual(
                field.get("status_parametro"),
                "pendente_revisao",
                f"Campo '{campo_name}' deveria permanecer pendente_revisao",
            )

    def test_status_busca_nao_localizado(self):
        _, per_record = self._run_nao_localizado()
        self.assertEqual(per_record["status_busca"], "nao_localizado")

    def test_fonte_oficial_mte_registrada_com_nao_localizado(self):
        record, _ = self._run_nao_localizado()
        fom = record.get("fonte_oficial_mte", {})
        self.assertEqual(fom.get("status_consulta"), "nao_localizado")
        self.assertFalse(fom.get("disponivel"))

    def test_campos_preenchidos_vazio(self):
        _, per_record = self._run_nao_localizado()
        self.assertEqual(per_record.get("campos_preenchidos", []), [])

    def test_json_nao_alterado_sem_dados_reais(self):
        """JSON must not be written when nothing was found or changed (AC3)."""
        record = _make_record()
        json_path = _write_temp_base([record])
        original_mtime = os.path.getmtime(json_path)

        fake_nao_localizado = {
            "disponivel": False,
            "tipo_referencia": "crawler",
            "url": None,
            "codigo_instrumento": None,
            "data_consulta": "2026-06-17",
            "status_consulta": "nao_localizado",
            "_content": None,
            "_text": None,
        }

        with patch("mte_crawler.search_mte_instrument", return_value=fake_nao_localizado):
            # run_auto_lookup should not touch the file when no data found
            run_auto_lookup(
                json_path=json_path,
                dry_run=False,
                pending_only=False,
            )

        new_mtime = os.path.getmtime(json_path)
        self.assertEqual(
            original_mtime,
            new_mtime,
            "JSON foi modificado mesmo sem dados reais — violação de AC3",
        )
        os.unlink(json_path)


# ──────────────────────────────────────────────────────────────────────────────
# Cenário 3 — Erro ou bloqueio (CAPTCHA / HTTP 403 / conexão)
# ──────────────────────────────────────────────────────────────────────────────


class TestBloqueioEErro(unittest.TestCase):
    """Cenário 3: CAPTCHA/bloqueio/erro → status registrado, sem tentativa de contorno."""

    def _run_with_status(self, status: str) -> tuple[dict, dict]:
        record = _make_record()
        fake_result = {
            "disponivel": False,
            "tipo_referencia": "crawler",
            "url": None,
            "codigo_instrumento": None,
            "data_consulta": "2026-06-17",
            "status_consulta": status,
            "_content": None,
            "_text": None,
            "_error": f"Simulado: {status}",
        }
        with patch("mte_crawler.search_mte_instrument", return_value=fake_result):
            from mte_crawler import _process_record
            per_record = _process_record(record)
        return record, per_record

    def test_bloqueado_campos_permanecem_pendentes(self):
        record, _ = self._run_with_status("bloqueado")
        for campo_name, field in record["itens_cct"].items():
            self.assertEqual(
                field.get("status_parametro"),
                "pendente_revisao",
                f"Campo '{campo_name}' deve permanecer pendente após bloqueio",
            )

    def test_erro_campos_permanecem_pendentes(self):
        record, _ = self._run_with_status("erro")
        for campo_name, field in record["itens_cct"].items():
            self.assertEqual(
                field.get("status_parametro"),
                "pendente_revisao",
                f"Campo '{campo_name}' deve permanecer pendente após erro",
            )

    def test_status_busca_bloqueado(self):
        _, per_record = self._run_with_status("bloqueado")
        self.assertEqual(per_record["status_busca"], "bloqueado")

    def test_status_busca_erro(self):
        _, per_record = self._run_with_status("erro")
        self.assertEqual(per_record["status_busca"], "erro")

    def test_fonte_oficial_mte_registra_bloqueado(self):
        record, _ = self._run_with_status("bloqueado")
        fom = record.get("fonte_oficial_mte", {})
        self.assertEqual(fom.get("status_consulta"), "bloqueado")

    def test_detect_block_http_403(self):
        self.assertTrue(_detect_block(403, ""))

    def test_detect_block_http_429(self):
        self.assertTrue(_detect_block(429, ""))

    def test_detect_block_captcha_in_html(self):
        self.assertTrue(_detect_block(200, "<html><body>Please complete CAPTCHA</body></html>"))

    def test_detect_block_recaptcha_in_html(self):
        self.assertTrue(_detect_block(200, "recaptcha challenge"))

    def test_detect_block_ok_normal_html(self):
        self.assertFalse(_detect_block(200, "<html><body>Resultado da busca</body></html>"))

    def test_search_returns_bloqueado_on_403(self):
        """search_mte_instrument registers bloqueado on HTTP 403."""
        fake_resp = MagicMock()
        fake_resp.status_code = 403
        fake_resp.text = "Forbidden"

        mock_requests = MagicMock()
        mock_session = MagicMock()
        mock_session.get.return_value = fake_resp
        mock_requests.Session.return_value = mock_session
        mock_requests.exceptions.Timeout = TimeoutError
        mock_requests.exceptions.ConnectionError = ConnectionError

        record = _make_record()
        import sys
        with patch.dict(sys.modules, {"requests": mock_requests}):
            result = search_mte_instrument(record)

        self.assertEqual(result["status_consulta"], "bloqueado")
        self.assertFalse(result["disponivel"])

    def test_search_returns_erro_on_timeout(self):
        """search_mte_instrument registers erro on timeout."""
        mock_requests = MagicMock()
        mock_session = MagicMock()
        mock_session.get.side_effect = TimeoutError("timed out")
        mock_requests.Session.return_value = mock_session
        mock_requests.exceptions.Timeout = TimeoutError
        mock_requests.exceptions.ConnectionError = ConnectionError

        record = _make_record()
        import sys
        with patch.dict(sys.modules, {"requests": mock_requests}):
            result = search_mte_instrument(record)

        self.assertEqual(result["status_consulta"], "erro")
        self.assertFalse(result["disponivel"])

    def test_search_returns_erro_on_connection_error(self):
        """search_mte_instrument registers erro on connection failure."""
        mock_requests = MagicMock()
        mock_session = MagicMock()
        mock_session.get.side_effect = ConnectionError("no route to host")
        mock_requests.Session.return_value = mock_session
        mock_requests.exceptions.Timeout = TimeoutError
        mock_requests.exceptions.ConnectionError = ConnectionError

        record = _make_record()
        import sys
        with patch.dict(sys.modules, {"requests": mock_requests}):
            result = search_mte_instrument(record)

        self.assertEqual(result["status_consulta"], "erro")
        self.assertFalse(result["disponivel"])

    def test_search_no_bypass_attempt_on_captcha(self):
        """No retry or bypass attempted when CAPTCHA is detected."""
        fake_resp = MagicMock()
        fake_resp.status_code = 200
        fake_resp.text = "Please solve the captcha to continue"

        mock_requests = MagicMock()
        mock_session = MagicMock()
        mock_session.get.return_value = fake_resp
        mock_requests.Session.return_value = mock_session
        mock_requests.exceptions.Timeout = TimeoutError
        mock_requests.exceptions.ConnectionError = ConnectionError

        record = _make_record()
        import sys
        with patch.dict(sys.modules, {"requests": mock_requests}):
            result = search_mte_instrument(record)

        # Should only have been called once (no retry/bypass)
        self.assertEqual(mock_session.get.call_count, 1)
        self.assertEqual(result["status_consulta"], "bloqueado")


# ──────────────────────────────────────────────────────────────────────────────
# Cenário 4 — Dry-run
# ──────────────────────────────────────────────────────────────────────────────


class TestDryRun(unittest.TestCase):
    """Cenário 4: --dry-run não grava JSON, JS nem relatório."""

    def _fake_localizado_result(self):
        return {
            "disponivel": True,
            "tipo_referencia": "crawler",
            "url": "https://www3.mte.gov.br/instrumento/12345.pdf",
            "codigo_instrumento": "12345",
            "data_consulta": "2026-06-17",
            "status_consulta": "localizado",
            "_content": b"%PDF fake",
            "_text": None,
            "_content_type": "application/pdf",
        }

    def test_dry_run_does_not_write_json(self):
        record = _make_record()
        json_path = _write_temp_base([record])
        original_mtime = os.path.getmtime(json_path)
        instrumento = _make_instrumento({"piso_salarial": MTE_CAMPO_VALIDO})

        with patch("mte_crawler.search_mte_instrument", return_value=self._fake_localizado_result()), \
             patch("mte_crawler.download_mte_instrument", return_value=self._fake_localizado_result()), \
             patch("mte_crawler.extract_mte_text_or_pdf", return_value=instrumento):
            run_auto_lookup(
                json_path=json_path,
                dry_run=True,
                pending_only=False,
            )

        new_mtime = os.path.getmtime(json_path)
        self.assertEqual(
            original_mtime,
            new_mtime,
            "JSON foi modificado em modo dry-run — violação de AC3",
        )
        os.unlink(json_path)

    def test_dry_run_does_not_write_report(self):
        record = _make_record()
        json_path = _write_temp_base([record])
        instrumento = _make_instrumento({"piso_salarial": MTE_CAMPO_VALIDO})

        with tempfile.TemporaryDirectory() as tmp_report_dir:
            with patch("mte_crawler.search_mte_instrument", return_value=self._fake_localizado_result()), \
                 patch("mte_crawler.download_mte_instrument", return_value=self._fake_localizado_result()), \
                 patch("mte_crawler.extract_mte_text_or_pdf", return_value=instrumento):
                run_auto_lookup(
                    json_path=json_path,
                    dry_run=True,
                    pending_only=False,
                    report_dir=tmp_report_dir,
                )

            report_path = os.path.join(tmp_report_dir, "mte_auto_lookup_report.json")
            self.assertFalse(
                os.path.exists(report_path),
                "Relatório foi criado em modo dry-run — violação de AC3",
            )

        os.unlink(json_path)

    def test_dry_run_returns_report_dict_in_memory(self):
        """Even with --dry-run, the function returns the report dict in memory."""
        record = _make_record()
        json_path = _write_temp_base([record])
        instrumento = _make_instrumento({"piso_salarial": MTE_CAMPO_VALIDO})

        with patch("mte_crawler.search_mte_instrument", return_value=self._fake_localizado_result()), \
             patch("mte_crawler.download_mte_instrument", return_value=self._fake_localizado_result()), \
             patch("mte_crawler.extract_mte_text_or_pdf", return_value=instrumento):
            report = run_auto_lookup(
                json_path=json_path,
                dry_run=True,
                pending_only=False,
            )

        self.assertTrue(report.get("dry_run"))
        self.assertIn("totais", report)
        self.assertIn("detalhes", report)
        os.unlink(json_path)


# ──────────────────────────────────────────────────────────────────────────────
# Cenário 5 — Conflito PDF × MTE
# ──────────────────────────────────────────────────────────────────────────────


class TestConflitoPdfMte(unittest.TestCase):
    """Cenário 5: valor MTE diverge de valor PDF → campo recebe status "conflito"."""

    def _run_conflito(self) -> dict:
        # Record with a pdf_cct value already filled
        record = _make_record({
            "itens_cct": {
                "piso_salarial": copy.deepcopy(FIELD_PDF_EXTRAIDO),  # valor=1540.47
            }
        })
        # MTE returns a different value
        instrumento = _make_instrumento({
            "piso_salarial": {
                "valor": 1620.00,
                "fonte_textual": "Cláusula 3ª MTE contradiz PDF",
                "observacao": "MTE extraído",
            }
        })
        fake_result = {
            "disponivel": True,
            "tipo_referencia": "crawler",
            "url": "https://example.com/instrumento.pdf",
            "codigo_instrumento": "99999",
            "data_consulta": "2026-06-17",
            "status_consulta": "localizado",
            "_content": b"%PDF fake",
            "_text": None,
            "_content_type": "application/pdf",
        }
        with patch("mte_crawler.search_mte_instrument", return_value=fake_result), \
             patch("mte_crawler.download_mte_instrument", return_value=fake_result), \
             patch("mte_crawler.extract_mte_text_or_pdf", return_value=instrumento):
            from mte_crawler import _process_record
            _process_record(record)
        return record

    def test_conflito_status_parametro(self):
        record = self._run_conflito()
        field = record["itens_cct"]["piso_salarial"]
        self.assertEqual(field["status_parametro"], "conflito")

    def test_conflito_origem(self):
        record = self._run_conflito()
        field = record["itens_cct"]["piso_salarial"]
        self.assertEqual(field["origem"], "conflito_pdf_mte")

    def test_conflito_tem_opcoes_identificadas(self):
        record = self._run_conflito()
        field = record["itens_cct"]["piso_salarial"]
        self.assertIn("opcoes_identificadas", field)
        opcoes = field["opcoes_identificadas"]
        self.assertEqual(len(opcoes), 2)
        fontes = {o["fonte"] for o in opcoes}
        self.assertIn("pdf_cct", fontes)
        self.assertIn("fonte_oficial_mte", fontes)

    def test_conflito_preserva_ambos_valores(self):
        record = self._run_conflito()
        opcoes = record["itens_cct"]["piso_salarial"]["opcoes_identificadas"]
        valores = {o["valor"] for o in opcoes}
        self.assertIn(1540.47, valores)
        self.assertIn(1620.00, valores)


# ──────────────────────────────────────────────────────────────────────────────
# Cenário 6 — Proteção de campo pdf_cct
# ──────────────────────────────────────────────────────────────────────────────


class TestProtecaoPdfCct(unittest.TestCase):
    """Cenário 6: campo com origem "pdf_cct" e valor não nulo não é alterado."""

    def _run_with_pdf_field_and_same_mte_value(self) -> dict:
        record = _make_record({
            "itens_cct": {
                "piso_salarial": copy.deepcopy(FIELD_PDF_EXTRAIDO),  # valor=1540.47
            }
        })
        instrumento = _make_instrumento({
            "piso_salarial": {
                "valor": 1540.47,  # Same value → no conflict
                "fonte_textual": "Confirma valor PDF",
            }
        })
        fake_result = {
            "disponivel": True, "tipo_referencia": "crawler",
            "url": "https://example.com/i.pdf", "codigo_instrumento": None,
            "data_consulta": "2026-06-17", "status_consulta": "localizado",
            "_content": b"%PDF", "_text": None, "_content_type": "application/pdf",
        }
        with patch("mte_crawler.search_mte_instrument", return_value=fake_result), \
             patch("mte_crawler.download_mte_instrument", return_value=fake_result), \
             patch("mte_crawler.extract_mte_text_or_pdf", return_value=instrumento):
            from mte_crawler import _process_record
            _process_record(record)
        return record

    def test_pdf_cct_valor_nao_sobrescrito_mesmo_valor(self):
        record = self._run_with_pdf_field_and_same_mte_value()
        field = record["itens_cct"]["piso_salarial"]
        # When same value: no conflict, pdf value preserved, status unchanged
        self.assertEqual(field["valor"], 1540.47)
        self.assertNotEqual(field.get("status_parametro"), "conflito")

    def test_pdf_cct_com_mte_diferente_gera_conflito_nao_sobrescreve(self):
        """pdf_cct field with different MTE value → conflict recorded, PDF value NOT replaced."""
        record = _make_record({
            "itens_cct": {
                "piso_salarial": copy.deepcopy(FIELD_PDF_EXTRAIDO),  # valor=1540.47
            }
        })
        instrumento = _make_instrumento({
            "piso_salarial": {
                "valor": 1800.00,
                "fonte_textual": "MTE diverge do PDF",
            }
        })
        fake_result = {
            "disponivel": True, "tipo_referencia": "crawler",
            "url": "https://example.com/i.pdf", "codigo_instrumento": None,
            "data_consulta": "2026-06-17", "status_consulta": "localizado",
            "_content": b"%PDF", "_text": None, "_content_type": "application/pdf",
        }
        with patch("mte_crawler.search_mte_instrument", return_value=fake_result), \
             patch("mte_crawler.download_mte_instrument", return_value=fake_result), \
             patch("mte_crawler.extract_mte_text_or_pdf", return_value=instrumento):
            from mte_crawler import _process_record
            _process_record(record)

        field = record["itens_cct"]["piso_salarial"]
        # Conflict recorded but PDF value (1540.47) NOT replaced by MTE value (1800.00)
        self.assertEqual(field["status_parametro"], "conflito")
        opcoes = field.get("opcoes_identificadas", [])
        pdf_opcao = next((o for o in opcoes if o["fonte"] == "pdf_cct"), None)
        self.assertIsNotNone(pdf_opcao)
        self.assertEqual(pdf_opcao["valor"], 1540.47)


# ──────────────────────────────────────────────────────────────────────────────
# Cenário 7 — Proteção de campo valido
# ──────────────────────────────────────────────────────────────────────────────


class TestProtecaoValido(unittest.TestCase):
    """Cenário 7: campo com status_parametro "valido" não é alterado em nenhuma circunstância."""

    def _run_with_valido_field(self) -> dict:
        record = _make_record({
            "itens_cct": {
                "piso_salarial": copy.deepcopy(FIELD_VALIDO),  # status_parametro=valido
            }
        })
        instrumento = _make_instrumento({
            "piso_salarial": {
                "valor": 9999.00,
                "fonte_textual": "Tentativa de sobrescrever campo valido",
            }
        })
        fake_result = {
            "disponivel": True, "tipo_referencia": "crawler",
            "url": "https://example.com/i.pdf", "codigo_instrumento": None,
            "data_consulta": "2026-06-17", "status_consulta": "localizado",
            "_content": b"%PDF", "_text": None, "_content_type": "application/pdf",
        }
        with patch("mte_crawler.search_mte_instrument", return_value=fake_result), \
             patch("mte_crawler.download_mte_instrument", return_value=fake_result), \
             patch("mte_crawler.extract_mte_text_or_pdf", return_value=instrumento):
            from mte_crawler import _process_record
            _process_record(record)
        return record

    def test_valido_status_parametro_preservado(self):
        record = self._run_with_valido_field()
        field = record["itens_cct"]["piso_salarial"]
        self.assertEqual(field["status_parametro"], "valido")

    def test_valido_valor_preservado(self):
        record = self._run_with_valido_field()
        field = record["itens_cct"]["piso_salarial"]
        self.assertEqual(field["valor"], 1500.00)

    def test_valido_origem_preservada(self):
        record = self._run_with_valido_field()
        field = record["itens_cct"]["piso_salarial"]
        self.assertEqual(field["origem"], "pdf_cct")


# ──────────────────────────────────────────────────────────────────────────────
# Cenário 8 — Piso Nacional restrito
# ──────────────────────────────────────────────────────────────────────────────


class TestPisoNacionalRestrito(unittest.TestCase):
    """Cenário 8: Piso Nacional somente para piso_salarial geral; nunca cargos/benefícios."""

    FORBIDDEN_FIELDS = [
        "adicional_noturno",
        "auxilio_alimentacao",
        "plr",
        "hora_extra",
        "sobreaviso",
        "jornada",
    ]

    def _run_no_mte_with_piso_nacional(self) -> dict:
        """Run pipeline with no MTE result but Piso Nacional available."""
        from enrich_mte_fallback import enrich_from_mte_fallback
        record = _make_record()
        enrich_from_mte_fallback(record, None, piso_nacional_valor=1412.00)
        return record

    def test_piso_nacional_nao_aplicado_a_campos_proibidos(self):
        record = self._run_no_mte_with_piso_nacional()
        for campo in self.FORBIDDEN_FIELDS:
            field = record["itens_cct"].get(campo, {})
            self.assertNotEqual(
                field.get("origem"),
                "fonte_oficial_nacional",
                f"Piso Nacional indevidamente aplicado a '{campo}'",
            )

    def test_piso_nacional_aplicado_ao_piso_salarial(self):
        record = self._run_no_mte_with_piso_nacional()
        field = record["itens_cct"]["piso_salarial"]
        self.assertEqual(field["origem"], "fonte_oficial_nacional")
        self.assertEqual(field["valor"], 1412.00)

    def test_piso_nacional_nao_aplicado_com_por_cargo(self):
        """Piso Nacional must NOT be applied when piso_salarial has por_cargo."""
        from enrich_mte_fallback import enrich_from_mte_fallback
        import copy as _copy
        field_com_cargo = _copy.deepcopy(FIELD_PENDENTE)
        field_com_cargo["por_cargo"] = [{"cargo": "piso_tecnico", "valor": None}]
        record = _make_record({"itens_cct": {"piso_salarial": field_com_cargo}})
        metrics = enrich_from_mte_fallback(record, None, piso_nacional_valor=1412.00)
        field = record["itens_cct"]["piso_salarial"]
        self.assertNotEqual(field.get("origem"), "fonte_oficial_nacional")
        self.assertEqual(metrics["preenchidos_piso_nacional"], 0)


# ──────────────────────────────────────────────────────────────────────────────
# Cenário 9 — Campo sem fonte_textual permanece pendente
# ──────────────────────────────────────────────────────────────────────────────


class TestCampoSemFonteTextual(unittest.TestCase):
    """Cenário 9: campo não preenchido quando fonte_textual está ausente ou vazia."""

    def test_extract_returns_none_when_no_fonte_textual(self):
        """extract_mte_text_or_pdf returns None when no campo has fonte_textual."""
        instrumento_sem_fonte = {
            "numero_registro": None,
            "tipo": "CCT",
            "vigencia_inicio": None,
            "vigencia_fim": None,
            "url_documento": None,
            "campos": {
                "piso_salarial": MTE_CAMPO_SEM_FONTE_TEXTUAL,  # fonte_textual=""
            },
        }

        fake_result = {
            "disponivel": True,
            "tipo_referencia": "crawler",
            "url": "https://example.com/i.pdf",
            "codigo_instrumento": None,
            "data_consulta": "2026-06-17",
            "status_consulta": "localizado",
            "_content": b"%PDF fake",
            "_text": None,
            "_content_type": "application/pdf",
        }

        with patch("mte_crawler._parse_pdf_content", return_value=instrumento_sem_fonte):
            extracted = extract_mte_text_or_pdf(fake_result)

        self.assertIsNone(
            extracted,
            "extract_mte_text_or_pdf deve retornar None quando nenhum campo tem fonte_textual",
        )

    def test_campo_permanece_pendente_sem_fonte_textual(self):
        """When fonte_textual is absent, field must remain pendente_revisao."""
        record = _make_record()
        instrumento_sem_fonte = {
            "numero_registro": None,
            "tipo": "CCT",
            "vigencia_inicio": None,
            "vigencia_fim": None,
            "url_documento": None,
            "campos": {
                "piso_salarial": MTE_CAMPO_SEM_FONTE_TEXTUAL,
            },
        }
        fake_result = {
            "disponivel": True, "tipo_referencia": "crawler",
            "url": "https://example.com/i.pdf", "codigo_instrumento": None,
            "data_consulta": "2026-06-17", "status_consulta": "localizado",
            "_content": b"%PDF", "_text": None, "_content_type": "application/pdf",
        }
        with patch("mte_crawler.search_mte_instrument", return_value=fake_result), \
             patch("mte_crawler.download_mte_instrument", return_value=fake_result), \
             patch("mte_crawler._parse_pdf_content", return_value=instrumento_sem_fonte):
            from mte_crawler import _process_record
            _process_record(record)

        field = record["itens_cct"]["piso_salarial"]
        self.assertEqual(
            field.get("status_parametro"),
            "pendente_revisao",
            "Campo deve permanecer pendente_revisao quando fonte_textual está vazia",
        )

    def test_extract_returns_only_campos_with_fonte_textual(self):
        """Only campos with non-empty fonte_textual are returned."""
        instrumento_parcial = {
            "numero_registro": None,
            "tipo": "CCT",
            "vigencia_inicio": None,
            "vigencia_fim": None,
            "url_documento": None,
            "campos": {
                "piso_salarial": MTE_CAMPO_VALIDO,           # fonte_textual OK
                "adicional_noturno": MTE_CAMPO_SEM_FONTE_TEXTUAL,  # sem fonte_textual
            },
        }
        fake_result = {
            "disponivel": True, "tipo_referencia": "crawler",
            "url": "https://example.com/i.pdf", "codigo_instrumento": None,
            "data_consulta": "2026-06-17", "status_consulta": "localizado",
            "_content": b"%PDF", "_text": None, "_content_type": "application/pdf",
        }

        with patch("mte_crawler._parse_pdf_content", return_value=instrumento_parcial):
            extracted = extract_mte_text_or_pdf(fake_result)

        self.assertIsNotNone(extracted)
        campos = extracted.get("campos", {})
        self.assertIn("piso_salarial", campos)
        self.assertNotIn(
            "adicional_noturno",
            campos,
            "Campo sem fonte_textual não deveria estar no instrumento extraído",
        )


# ──────────────────────────────────────────────────────────────────────────────
# Cenário 10 — Relatório gerado (AC5)
# ──────────────────────────────────────────────────────────────────────────────


class TestRelatorioGerado(unittest.TestCase):
    """Cenário 10: relatório mte_auto_lookup_report.json criado com schema do AC5."""

    def _run_and_get_report(
        self, status: str = "localizado", instrumento=None
    ) -> tuple[str, dict]:
        record = _make_record()
        json_path = _write_temp_base([record])

        if instrumento is None:
            instrumento = _make_instrumento({"piso_salarial": MTE_CAMPO_VALIDO})

        fake_result = {
            "disponivel": status == "localizado",
            "tipo_referencia": "crawler",
            "url": "https://example.com/i.pdf" if status == "localizado" else None,
            "codigo_instrumento": "12345" if status == "localizado" else None,
            "data_consulta": "2026-06-17",
            "status_consulta": status,
            "_content": b"%PDF" if status == "localizado" else None,
            "_text": None,
            "_content_type": "application/pdf" if status == "localizado" else None,
        }

        with tempfile.TemporaryDirectory() as tmp_report_dir:
            with patch("mte_crawler.search_mte_instrument", return_value=fake_result), \
                 patch("mte_crawler.download_mte_instrument", return_value=fake_result), \
                 patch("mte_crawler.extract_mte_text_or_pdf", return_value=instrumento if status == "localizado" else None), \
                 patch("mte_crawler.EXPORT_SCRIPT", "/dev/null"):
                run_auto_lookup(
                    json_path=json_path,
                    dry_run=False,
                    pending_only=False,
                    report_dir=tmp_report_dir,
                )
            report_path = os.path.join(tmp_report_dir, "mte_auto_lookup_report.json")
            with open(report_path, "r", encoding="utf-8") as f:
                report = json.load(f)

        os.unlink(json_path)
        return report_path, report

    def test_relatorio_existe_apos_execucao_real(self):
        """Report file is created after a real (non-dry-run) execution."""
        record = _make_record()
        json_path = _write_temp_base([record])
        instrumento = _make_instrumento({"piso_salarial": MTE_CAMPO_VALIDO})
        fake_result = {
            "disponivel": True, "tipo_referencia": "crawler",
            "url": "https://example.com/i.pdf", "codigo_instrumento": "111",
            "data_consulta": "2026-06-17", "status_consulta": "localizado",
            "_content": b"%PDF", "_text": None, "_content_type": "application/pdf",
        }

        with tempfile.TemporaryDirectory() as tmp_report_dir:
            with patch("mte_crawler.search_mte_instrument", return_value=fake_result), \
                 patch("mte_crawler.download_mte_instrument", return_value=fake_result), \
                 patch("mte_crawler.extract_mte_text_or_pdf", return_value=instrumento), \
                 patch("mte_crawler.EXPORT_SCRIPT", "/dev/null"):
                run_auto_lookup(
                    json_path=json_path, dry_run=False,
                    pending_only=False, report_dir=tmp_report_dir,
                )
            report_path = os.path.join(tmp_report_dir, "mte_auto_lookup_report.json")
            self.assertTrue(
                os.path.exists(report_path),
                "mte_auto_lookup_report.json deve existir após execução real",
            )

        os.unlink(json_path)

    def test_relatorio_tem_totais_globais(self):
        _, report = self._run_and_get_report()
        self.assertIn("totais", report)
        totais = report["totais"]
        for key in (
            "registros_avaliados",
            "instrumentos_localizados",
            "instrumentos_nao_localizados",
            "instrumentos_com_erro",
            "instrumentos_bloqueados",
            "campos_preenchidos",
            "campos_pendentes",
            "campos_conflito",
            "campos_piso_nacional",
            "arquivos_atualizados",
        ):
            self.assertIn(key, totais, f"Campo obrigatório ausente nos totais: {key}")

    def test_relatorio_tem_detalhes_por_registro(self):
        _, report = self._run_and_get_report()
        self.assertIn("detalhes", report)
        self.assertIsInstance(report["detalhes"], list)
        self.assertGreater(len(report["detalhes"]), 0)

    def test_relatorio_detalhe_tem_campos_obrigatorios(self):
        _, report = self._run_and_get_report()
        detail = report["detalhes"][0]
        required_keys = (
            "registro_id", "uf", "sindicato", "categoria", "ano",
            "status_busca", "url_localizada", "codigo_instrumento",
            "campos_preenchidos", "campos_pendentes", "campos_conflito",
            "observacao",
        )
        for key in required_keys:
            self.assertIn(key, detail, f"Campo obrigatório ausente no detalhe: {key}")

    def test_relatorio_totais_contagem_correta_localizado(self):
        _, report = self._run_and_get_report(status="localizado")
        self.assertEqual(report["totais"]["registros_avaliados"], 1)
        self.assertEqual(report["totais"]["instrumentos_localizados"], 1)
        self.assertEqual(report["totais"]["instrumentos_nao_localizados"], 0)

    def test_relatorio_totais_contagem_nao_localizado(self):
        _, report = self._run_and_get_report(status="nao_localizado")
        self.assertEqual(report["totais"]["instrumentos_nao_localizados"], 1)
        self.assertEqual(report["totais"]["instrumentos_localizados"], 0)

    def test_relatorio_data_execucao_presente(self):
        _, report = self._run_and_get_report()
        self.assertIn("data_execucao", report)
        self.assertIsNotNone(report["data_execucao"])

    def test_relatorio_dry_run_false_em_execucao_real(self):
        _, report = self._run_and_get_report()
        self.assertFalse(report.get("dry_run"))


# ──────────────────────────────────────────────────────────────────────────────
# Testes de utilitários e helpers
# ──────────────────────────────────────────────────────────────────────────────


class TestHelpers(unittest.TestCase):
    """Unit tests for helper functions."""

    def test_has_pending_fields_true(self):
        record = _make_record()
        self.assertTrue(_has_pending_fields(record))

    def test_has_pending_fields_false_all_valido(self):
        record = _make_record({
            "itens_cct": {f: copy.deepcopy(FIELD_VALIDO) for f in [
                "piso_salarial", "adicional_noturno", "auxilio_alimentacao",
                "plr", "hora_extra", "sobreaviso", "jornada",
            ]}
        })
        self.assertFalse(_has_pending_fields(record))

    def test_has_pending_fields_false_no_itens_cct(self):
        record = {"id_registro_reajuste": "X"}
        self.assertFalse(_has_pending_fields(record))

    def test_build_search_params_uf_and_ano(self):
        record = _make_record({"uf": "SP", "ano_referencia": 2025})
        params = _build_search_params(record)
        self.assertIn("CodUF", params)
        self.assertEqual(params["CodUF"], "35")
        self.assertEqual(params["AnoInstCo"], "2025")

    def test_build_search_params_tipo_cct(self):
        record = _make_record()
        params = _build_search_params(record)
        self.assertEqual(params.get("TipoInstCo"), "C")

    def test_build_search_params_vigencia_inicio_converted(self):
        record = _make_record({"vigencia_inicio": "2025-01-15"})
        params = _build_search_params(record)
        self.assertEqual(params.get("DtVigenciaIni"), "15/01/2025")

    def test_is_pdf_bytes_true(self):
        self.assertTrue(_is_pdf_bytes(b"%PDF-1.4 content"))

    def test_is_pdf_bytes_false(self):
        self.assertFalse(_is_pdf_bytes(b"<html><body>not a pdf</body></html>"))

    def test_detect_block_http_503(self):
        self.assertTrue(_detect_block(503, ""))

    def test_detect_block_access_denied(self):
        self.assertTrue(_detect_block(200, "Access Denied — your IP has been blocked"))

    def test_detect_block_normal_200(self):
        self.assertFalse(_detect_block(200, "Resultado encontrado: CCT SP 2025"))

    def test_search_result_structure(self):
        """search_mte_instrument result always has required keys."""
        fake_resp = MagicMock()
        fake_resp.status_code = 200
        fake_resp.text = "Nenhum instrumento encontrado."

        mock_requests = MagicMock()
        mock_session = MagicMock()
        mock_session.get.return_value = fake_resp
        mock_requests.Session.return_value = mock_session
        mock_requests.exceptions.Timeout = TimeoutError
        mock_requests.exceptions.ConnectionError = ConnectionError

        record = _make_record()
        import sys
        with patch.dict(sys.modules, {"requests": mock_requests}):
            result = search_mte_instrument(record)

        for key in ("disponivel", "tipo_referencia", "url", "codigo_instrumento",
                    "data_consulta", "status_consulta"):
            self.assertIn(key, result, f"Chave obrigatória ausente no resultado: {key}")
        self.assertEqual(result["tipo_referencia"], "crawler")

    def test_pending_only_skips_non_pending_records(self):
        """With pending_only=True, records without pending fields are skipped."""
        all_valido_record = _make_record({
            "itens_cct": {f: copy.deepcopy(FIELD_VALIDO) for f in [
                "piso_salarial", "adicional_noturno", "auxilio_alimentacao",
                "plr", "hora_extra", "sobreaviso", "jornada",
            ]}
        })
        json_path = _write_temp_base([all_valido_record])

        with patch("mte_crawler.search_mte_instrument") as mock_search:
            run_auto_lookup(
                json_path=json_path,
                dry_run=True,
                pending_only=True,
            )
            mock_search.assert_not_called()

        os.unlink(json_path)

    def test_download_returns_unchanged_when_not_localizado(self):
        """download_mte_instrument is a no-op when status is not localizado."""
        result = {
            "disponivel": False,
            "status_consulta": "nao_localizado",
            "url": None,
        }
        returned = download_mte_instrument(result)
        self.assertIs(returned, result)
        self.assertIsNone(returned.get("_content"))

    def test_extract_returns_none_when_not_localizado(self):
        """extract_mte_text_or_pdf returns None when status is not localizado."""
        result = {"status_consulta": "nao_localizado", "_content": None, "_text": None}
        self.assertIsNone(extract_mte_text_or_pdf(result))

    def test_fonte_oficial_mte_tipo_crawler_aceito(self):
        """'crawler' is a valid tipo_referencia in enrich_mte_fallback."""
        from enrich_mte_fallback import FONTE_OFICIAL_MTE_TIPOS, _build_fonte_oficial_mte
        self.assertIn("crawler", FONTE_OFICIAL_MTE_TIPOS)
        # Should not raise
        fonte = _build_fonte_oficial_mte(
            "crawler",
            url="https://example.com",
            status_consulta="localizado",
        )
        self.assertEqual(fonte["tipo_referencia"], "crawler")


# ──────────────────────────────────────────────────────────────────────────────
# Testes de isolamento (AC1)
# ──────────────────────────────────────────────────────────────────────────────


class TestIsolamento(unittest.TestCase):
    """AC1: mte_crawler.py must not import extract_cct_items, app.js, index.html, style.css."""

    def test_extract_cct_items_not_imported(self):
        """mte_crawler.py must never import extract_cct_items."""
        import ast
        import mte_crawler

        # Parse the AST to find actual import statements, not docstring mentions
        source_path = mte_crawler.__file__
        with open(source_path, "r", encoding="utf-8") as f:
            source = f.read()

        tree = ast.parse(source)
        imported_names: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imported_names.append(alias.name)
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        imported_names.append(node.module)

        forbidden = [name for name in imported_names if "extract_cct_items" in name]
        self.assertEqual(
            forbidden,
            [],
            f"mte_crawler.py não deve importar extract_cct_items; encontrado: {forbidden}",
        )

    def test_three_mandatory_functions_exist(self):
        """search_mte_instrument, download_mte_instrument, extract_mte_text_or_pdf must exist."""
        import mte_crawler
        self.assertTrue(callable(mte_crawler.search_mte_instrument))
        self.assertTrue(callable(mte_crawler.download_mte_instrument))
        self.assertTrue(callable(mte_crawler.extract_mte_text_or_pdf))

    def test_run_auto_lookup_exists(self):
        import mte_crawler
        self.assertTrue(callable(mte_crawler.run_auto_lookup))


if __name__ == "__main__":
    unittest.main(verbosity=2)

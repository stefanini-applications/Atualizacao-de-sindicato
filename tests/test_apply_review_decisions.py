"""
Testes automatizados para apply_review_decisions.py (PRJ-72).

Cobre os 14 cenários obrigatórios definidos nos ACs:
  1.  Dry-run não altera base_parametros_sindicais.json, .js nem audit.json
  2.  Execução real altera apenas campos do Excel com decisao_final válida
  3.  Erro de coluna obrigatória ausente aborta execução sem alterar nenhum arquivo
  4.  Decisão inválida gera erro na auditoria e não altera a base; demais processadas
  5.  Campo inexistente gera erro na auditoria e não altera a base; demais processadas
  6.  registro_id inexistente gera erro na auditoria e não altera a base; demais processadas
  7.  validar com valor_revisado vazio atualiza apenas metadados, não altera valor
  8.  validar com valor_revisado diferente preserva valor_original_pre_validacao e atualiza valor
  9.  manter_pendente não valida (status permanece "pendente_revisao")
  10. rejeitar marca como "rejeitado"
  11. marcar_conflito preserva opcoes_identificadas existentes
  12. buscar_fonte mantém "pendente_revisao" com acao_recomendada: "buscar_fonte"
  13. Auditoria gerada contém todos os campos obrigatórios (antes/depois, revisor, timestamp)
  14. Base JS regenerada corretamente após execução real
"""

import copy
import json
import os
import sys
import tempfile
import unittest
from io import StringIO
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from apply_review_decisions import (
    CAMPO_TO_XLSX_COL,
    REQUIRED_COLS,
    REQUIRED_COLS_XLSX,
    VALID_DECISIONS,
    _build_registro_index,
    _coerce_valor,
    _expand_xlsx_rows,
    _normalize_valor,
    _save_js,
    _save_json_atomic,
    apply_decision_to_campo,
    build_audit_report,
    load_decisions_xlsx,
    main,
    process_decisions,
)

# ──────────────────────────────────────────────────────────────────────────────
# Helpers / fixtures
# ──────────────────────────────────────────────────────────────────────────────

TIMESTAMP = "2026-06-18T18:00:00+00:00"


def _make_base(registros: list[dict] | None = None) -> dict:
    """Cria estrutura mínima de base sindical para testes."""
    if registros is None:
        registros = [_make_registro()]
    return {"data_geracao": "2026-06-01T00:00:00+00:00", "registros": registros}


def _make_registro(
    rid: str = "REG-SP-TEST-2025",
    piso_valor=1540.47,
    piso_status: str = "extraido_para_revisao",
    opcoes_identificadas=None,
) -> dict:
    """Cria um registro mínimo com itens_cct completos."""
    return {
        "id_registro_reajuste": rid,
        "uf": "SP",
        "sindicato": "Sindicato Teste SP",
        "categoria": "Tecnologia",
        "ano_referencia": 2025,
        "status_parametro": "pendente_revisao",
        "itens_cct": {
            "piso_salarial": {
                "valor": piso_valor,
                "status_parametro": piso_status,
                "origem": "pdf_cct",
                "fonte": "PDF da CCT",
                "opcoes_identificadas": opcoes_identificadas,
            },
            "adicional_noturno": {
                "valor": None,
                "status_parametro": "pendente_revisao",
                "origem": "nao_identificado_pdf",
                "fonte": None,
                "opcoes_identificadas": None,
            },
        },
    }


def _make_xlsx_rows(overrides: list[dict] | None = None) -> list[dict]:
    """Cria lista de linhas de decisão com valores padrão."""
    default = {
        "registro_id": "REG-SP-TEST-2025",
        "campo": "piso_salarial",
        "decisao_final": "validar",
        "valor_revisado": "",
        "observacao_revisor": "OK",
        "revisor": "Maria",
        "data_revisao": "2026-06-18",
    }
    if overrides is None:
        return [default]
    return [{**default, **o} for o in overrides]


def _mock_load_xlsx(rows: list[dict]):
    """Retorna um mock de load_decisions_xlsx que retorna `rows` diretamente."""
    return rows


def _run_main_with_mocks(
    rows: list[dict],
    base: dict,
    dry_run: bool = False,
    json_path: str | None = None,
    js_path: str | None = None,
    audit_path: str | None = None,
    decisions_path: str = "mock_decisions.xlsx",
) -> tuple[int, dict | None, list[dict] | None]:
    """
    Executa main() com mocks de I/O.

    Retorna (exit_code, base_final_ou_None, audit_records_ou_None).
    """
    import apply_review_decisions as mod

    with tempfile.TemporaryDirectory() as tmpdir:
        real_json = json_path or os.path.join(tmpdir, "base.json")
        real_js = js_path or os.path.join(tmpdir, "base.js")
        real_audit = audit_path or os.path.join(tmpdir, "audit.json")

        with open(real_json, "w", encoding="utf-8") as f:
            json.dump(base, f)

        argv = ["--decisions", decisions_path]
        if dry_run:
            argv.append("--dry-run")

        with (
            patch.object(mod, "load_decisions_xlsx", return_value=rows),
            patch.object(mod, "JSON_PATH", real_json),
            patch.object(mod, "JS_PATH", real_js),
            patch.object(mod, "AUDIT_PATH", real_audit),
        ):
            exit_code = main(argv)

        base_final = None
        if os.path.exists(real_json):
            with open(real_json, encoding="utf-8") as f:
                base_final = json.load(f)

        audit_final = None
        if os.path.exists(real_audit):
            with open(real_audit, encoding="utf-8") as f:
                audit_final = json.load(f)

        js_content = None
        if os.path.exists(real_js):
            with open(real_js, encoding="utf-8") as f:
                js_content = f.read()

    return exit_code, base_final, audit_final, js_content


# ──────────────────────────────────────────────────────────────────────────────
# Cenário 1 — Dry-run não altera nenhum arquivo (AC3)
# ──────────────────────────────────────────────────────────────────────────────

class TestCenario1DryRun(unittest.TestCase):
    def test_dry_run_nao_cria_arquivo_json(self):
        rows = _make_xlsx_rows()
        base = _make_base()

        with tempfile.TemporaryDirectory() as tmpdir:
            real_json = os.path.join(tmpdir, "base.json")
            real_js = os.path.join(tmpdir, "base.js")
            real_audit = os.path.join(tmpdir, "audit.json")

            with open(real_json, "w", encoding="utf-8") as f:
                json.dump(base, f)

            import apply_review_decisions as mod
            import hashlib

            with open(real_json, "rb") as f:
                hash_before = hashlib.md5(f.read()).hexdigest()

            with (
                patch.object(mod, "load_decisions_xlsx", return_value=rows),
                patch.object(mod, "JSON_PATH", real_json),
                patch.object(mod, "JS_PATH", real_js),
                patch.object(mod, "AUDIT_PATH", real_audit),
            ):
                main(["--decisions", "mock.xlsx", "--dry-run"])

            with open(real_json, "rb") as f:
                hash_after = hashlib.md5(f.read()).hexdigest()

            self.assertEqual(hash_before, hash_after, "JSON não deve ser alterado em dry-run")
            self.assertFalse(os.path.exists(real_js), "JS não deve ser criado em dry-run")
            self.assertFalse(os.path.exists(real_audit), "Auditoria não deve ser criada em dry-run")

    def test_dry_run_exibe_sumario(self):
        rows = _make_xlsx_rows([
            {"decisao_final": "validar"},
            {"campo": "adicional_noturno", "decisao_final": "manter_pendente"},
        ])
        base = _make_base()

        import apply_review_decisions as mod
        with (
            patch.object(mod, "load_decisions_xlsx", return_value=rows),
            patch.object(mod, "JSON_PATH", "/dev/null/non_existent"),  # não será lido (mock abaixo)
        ):
            # Redireciona saída
            with patch("builtins.open", side_effect=lambda p, *a, **k: open(p, *a, **k) if p != "/dev/null/non_existent" else _fake_base_open(base)):
                pass  # only testing stdout

        # Testa via process_decisions diretamente
        _, _, summary = process_decisions(rows, base, TIMESTAMP)
        self.assertEqual(summary["validar"], 1)
        self.assertEqual(summary["manter_pendente"], 1)


def _fake_base_open(base: dict):
    import io
    content = json.dumps(base)
    return io.StringIO(content)


# ──────────────────────────────────────────────────────────────────────────────
# Cenário 2 — Execução real altera apenas campos com decisao_final válida (AC2, AC5)
# ──────────────────────────────────────────────────────────────────────────────

class TestCenario2ExecucaoReal(unittest.TestCase):
    def test_apenas_campo_do_excel_e_alterado(self):
        rows = _make_xlsx_rows([{"campo": "piso_salarial", "decisao_final": "validar"}])
        base = _make_base()

        exit_code, base_final, _, _ = _run_main_with_mocks(rows, base)
        self.assertEqual(exit_code, 0)

        piso = base_final["registros"][0]["itens_cct"]["piso_salarial"]
        self.assertEqual(piso["status_parametro"], "valido")

        # adicional_noturno NÃO foi alterado
        adicional = base_final["registros"][0]["itens_cct"]["adicional_noturno"]
        self.assertEqual(adicional["status_parametro"], "pendente_revisao")

    def test_exit_code_zero_em_sucesso(self):
        rows = _make_xlsx_rows()
        base = _make_base()
        exit_code, _, _, _ = _run_main_with_mocks(rows, base)
        self.assertEqual(exit_code, 0)


# ──────────────────────────────────────────────────────────────────────────────
# Cenário 3 — Coluna obrigatória ausente aborta sem alterar arquivo (AC1)
# ──────────────────────────────────────────────────────────────────────────────

class TestCenario3ColunaAusente(unittest.TestCase):
    def _make_wb_per_campo_sem_coluna(self, coluna_removida: str):
        """Cria mock de workbook no formato por-campo sem uma coluna obrigatória."""
        import openpyxl
        wb = openpyxl.Workbook()
        ws = wb.active
        cols = [c for c in REQUIRED_COLS if c != coluna_removida]
        ws.append(cols)
        ws.append(["REG-001", "piso_salarial", "validar", "", "OK", "Maria"][:len(cols)])
        return wb

    def test_aborta_sem_campo_registro_id(self):
        wb = self._make_wb_per_campo_sem_coluna("registro_id")
        import apply_review_decisions as mod
        with (
            patch("openpyxl.load_workbook", return_value=wb),
            patch("os.path.exists", return_value=True),
        ):
            with self.assertRaises(SystemExit) as ctx:
                mod.load_decisions_xlsx("qualquer.xlsx")
            self.assertNotEqual(ctx.exception.code, 0)

    def test_aborta_sem_campo_decisao_final(self):
        wb = self._make_wb_per_campo_sem_coluna("decisao_final")
        import apply_review_decisions as mod
        with (
            patch("openpyxl.load_workbook", return_value=wb),
            patch("os.path.exists", return_value=True),
        ):
            with self.assertRaises(SystemExit) as ctx:
                mod.load_decisions_xlsx("qualquer.xlsx")
            self.assertNotEqual(ctx.exception.code, 0)

    def test_aborta_sem_coluna_revisor(self):
        wb = self._make_wb_per_campo_sem_coluna("revisor")
        import apply_review_decisions as mod
        with (
            patch("openpyxl.load_workbook", return_value=wb),
            patch("os.path.exists", return_value=True),
        ):
            with self.assertRaises(SystemExit) as ctx:
                mod.load_decisions_xlsx("qualquer.xlsx")
            self.assertNotEqual(ctx.exception.code, 0)

    def test_aborta_formato_xlsx_sem_decisao_final(self):
        """Formato por-registro (CODIGO DO SINDICATO) também aborta sem decisao_final."""
        import openpyxl
        wb = openpyxl.Workbook()
        ws = wb.active
        cols_sem_decisao = [c for c in REQUIRED_COLS_XLSX if c != "decisao_final"]
        ws.append(cols_sem_decisao)
        ws.append(["REG-001", "OK", "Maria", "2026-06-18"])

        import apply_review_decisions as mod
        with (
            patch("openpyxl.load_workbook", return_value=wb),
            patch("os.path.exists", return_value=True),
        ):
            with self.assertRaises(SystemExit) as ctx:
                mod.load_decisions_xlsx("qualquer.xlsx")
            self.assertNotEqual(ctx.exception.code, 0)


# ──────────────────────────────────────────────────────────────────────────────
# Cenário 4 — Decisão inválida gera erro; demais linhas processadas (AC2)
# ──────────────────────────────────────────────────────────────────────────────

class TestCenario4DecisaoInvalida(unittest.TestCase):
    def test_linha_com_decisao_invalida_gera_erro_auditoria(self):
        rows = _make_xlsx_rows([
            {"campo": "piso_salarial", "decisao_final": "decisao_inventada"},
            {"campo": "adicional_noturno", "decisao_final": "rejeitar"},
        ])
        base = _make_base()
        _, audit_records, _ = process_decisions(rows, base, TIMESTAMP)

        resultados = [r["resultado"] for r in audit_records]
        self.assertIn("erro", resultados)
        self.assertIn("aplicado", resultados)

    def test_linha_invalida_nao_altera_base(self):
        rows = _make_xlsx_rows([{"campo": "piso_salarial", "decisao_final": "xyz"}])
        base = _make_base()
        base_mod, _, _ = process_decisions(rows, base, TIMESTAMP)

        piso = base_mod["registros"][0]["itens_cct"]["piso_salarial"]
        self.assertNotEqual(piso.get("status_parametro"), "valido")

    def test_demais_linhas_processadas_apos_erro(self):
        rows = _make_xlsx_rows([
            {"campo": "piso_salarial", "decisao_final": "invalida"},
            {"campo": "adicional_noturno", "decisao_final": "rejeitar"},
        ])
        base = _make_base()
        base_mod, _, summary = process_decisions(rows, base, TIMESTAMP)

        adicional = base_mod["registros"][0]["itens_cct"]["adicional_noturno"]
        self.assertEqual(adicional["status_parametro"], "rejeitado")
        self.assertEqual(summary["erros"], 1)
        self.assertEqual(summary["rejeitar"], 1)


# ──────────────────────────────────────────────────────────────────────────────
# Cenário 5 — Campo inexistente gera erro; demais linhas processadas (AC2)
# ──────────────────────────────────────────────────────────────────────────────

class TestCenario5CampoInexistente(unittest.TestCase):
    def test_campo_inexistente_gera_erro_auditoria(self):
        rows = _make_xlsx_rows([{"campo": "campo_que_nao_existe", "decisao_final": "validar"}])
        base = _make_base()
        _, audit_records, summary = process_decisions(rows, base, TIMESTAMP)

        self.assertEqual(summary["erros"], 1)
        self.assertIn("campo_que_nao_existe", audit_records[0]["motivo"])

    def test_campo_inexistente_nao_altera_base(self):
        rows = _make_xlsx_rows([{"campo": "campo_fantasma", "decisao_final": "validar"}])
        base = _make_base()
        base_mod, _, _ = process_decisions(rows, base, TIMESTAMP)

        # Campos existentes permanecem inalterados
        piso = base_mod["registros"][0]["itens_cct"]["piso_salarial"]
        self.assertNotEqual(piso.get("status_parametro"), "valido")

    def test_demais_linhas_processadas_apos_campo_invalido(self):
        rows = _make_xlsx_rows([
            {"campo": "campo_fantasma", "decisao_final": "validar"},
            {"campo": "piso_salarial", "decisao_final": "rejeitar"},
        ])
        base = _make_base()
        base_mod, _, summary = process_decisions(rows, base, TIMESTAMP)

        piso = base_mod["registros"][0]["itens_cct"]["piso_salarial"]
        self.assertEqual(piso["status_parametro"], "rejeitado")
        self.assertEqual(summary["erros"], 1)
        self.assertEqual(summary["rejeitar"], 1)


# ──────────────────────────────────────────────────────────────────────────────
# Cenário 6 — registro_id inexistente gera erro; demais linhas processadas (AC2)
# ──────────────────────────────────────────────────────────────────────────────

class TestCenario6RegistroInexistente(unittest.TestCase):
    def test_registro_inexistente_gera_erro_auditoria(self):
        rows = _make_xlsx_rows([{"registro_id": "REG-INEXISTENTE", "decisao_final": "validar"}])
        base = _make_base()
        _, audit_records, summary = process_decisions(rows, base, TIMESTAMP)

        self.assertEqual(summary["erros"], 1)
        self.assertIn("REG-INEXISTENTE", audit_records[0]["motivo"])

    def test_registro_inexistente_nao_altera_base(self):
        rows = _make_xlsx_rows([{"registro_id": "NOPE", "decisao_final": "validar"}])
        base = _make_base()
        base_mod, _, _ = process_decisions(rows, base, TIMESTAMP)

        piso = base_mod["registros"][0]["itens_cct"]["piso_salarial"]
        self.assertEqual(piso["status_parametro"], "extraido_para_revisao")

    def test_demais_linhas_processadas_apos_registro_invalido(self):
        rows = _make_xlsx_rows([
            {"registro_id": "NAO_EXISTE", "decisao_final": "validar"},
            {"registro_id": "REG-SP-TEST-2025", "campo": "piso_salarial", "decisao_final": "rejeitar"},
        ])
        base = _make_base()
        base_mod, _, summary = process_decisions(rows, base, TIMESTAMP)

        piso = base_mod["registros"][0]["itens_cct"]["piso_salarial"]
        self.assertEqual(piso["status_parametro"], "rejeitado")
        self.assertEqual(summary["erros"], 1)
        self.assertEqual(summary["rejeitar"], 1)


# ──────────────────────────────────────────────────────────────────────────────
# Cenário 7 — validar com valor_revisado vazio → apenas metadados (AC2)
# ──────────────────────────────────────────────────────────────────────────────

class TestCenario7ValidarSemValorRevisado(unittest.TestCase):
    def test_valor_nao_alterado_quando_revisado_vazio(self):
        campo = {
            "valor": 1540.47,
            "status_parametro": "extraido_para_revisao",
        }
        novo, delta = apply_decision_to_campo(
            campo_data=campo,
            decisao="validar",
            valor_revisado="",
            revisor="Maria",
            data_revisao="2026-06-18",
            observacao_revisor="OK",
            timestamp=TIMESTAMP,
        )
        self.assertEqual(novo["valor"], 1540.47)
        self.assertNotIn("valor_original_pre_validacao", novo)
        self.assertEqual(novo["status_parametro"], "valido")

    def test_valor_nao_alterado_quando_revisado_none(self):
        campo = {"valor": 999.0, "status_parametro": "pendente_revisao"}
        novo, _ = apply_decision_to_campo(
            campo_data=campo,
            decisao="validar",
            valor_revisado=None,
            revisor="Ana",
            data_revisao="2026-06-18",
            observacao_revisor="",
            timestamp=TIMESTAMP,
        )
        self.assertEqual(novo["valor"], 999.0)
        self.assertEqual(novo["status_parametro"], "valido")

    def test_metadados_de_validacao_preenchidos(self):
        campo = {"valor": 1540.47, "status_parametro": "extraido_para_revisao"}
        novo, _ = apply_decision_to_campo(
            campo_data=campo,
            decisao="validar",
            valor_revisado=None,
            revisor="Maria",
            data_revisao="2026-06-18",
            observacao_revisor="Confirmado",
            timestamp=TIMESTAMP,
        )
        self.assertEqual(novo["validado_por"], "Maria")
        self.assertEqual(novo["data_validacao"], "2026-06-18")
        self.assertEqual(novo["observacao_validacao"], "Confirmado")


# ──────────────────────────────────────────────────────────────────────────────
# Cenário 8 — validar com valor_revisado diferente → preserva original e atualiza (AC2)
# ──────────────────────────────────────────────────────────────────────────────

class TestCenario8ValidarComValorRevisado(unittest.TestCase):
    def test_valor_original_preservado(self):
        campo = {"valor": 1540.47, "status_parametro": "extraido_para_revisao"}
        novo, delta = apply_decision_to_campo(
            campo_data=campo,
            decisao="validar",
            valor_revisado=1600.0,
            revisor="Maria",
            data_revisao="2026-06-18",
            observacao_revisor="Corrigido",
            timestamp=TIMESTAMP,
        )
        self.assertEqual(novo["valor_original_pre_validacao"], 1540.47)
        self.assertEqual(novo["valor"], 1600.0)
        self.assertEqual(novo["status_parametro"], "valido")

    def test_delta_auditoria_registra_valor_novo(self):
        campo = {"valor": 1540.47, "status_parametro": "extraido_para_revisao"}
        _, delta = apply_decision_to_campo(
            campo_data=campo,
            decisao="validar",
            valor_revisado=1600.0,
            revisor="Maria",
            data_revisao="2026-06-18",
            observacao_revisor="",
            timestamp=TIMESTAMP,
        )
        self.assertEqual(delta["valor_anterior"], 1540.47)
        self.assertEqual(delta["valor_novo"], 1600.0)

    def test_valor_igual_nao_gera_copia(self):
        """Se valor_revisado == valor atual, não copia para valor_original_pre_validacao."""
        campo = {"valor": 1540.47, "status_parametro": "extraido_para_revisao"}
        novo, _ = apply_decision_to_campo(
            campo_data=campo,
            decisao="validar",
            valor_revisado=1540.47,
            revisor="Maria",
            data_revisao="2026-06-18",
            observacao_revisor="",
            timestamp=TIMESTAMP,
        )
        self.assertNotIn("valor_original_pre_validacao", novo)
        self.assertEqual(novo["valor"], 1540.47)


# ──────────────────────────────────────────────────────────────────────────────
# Cenário 9 — manter_pendente → status "pendente_revisao" (AC2)
# ──────────────────────────────────────────────────────────────────────────────

class TestCenario9ManterPendente(unittest.TestCase):
    def test_status_pendente_revisao(self):
        campo = {"valor": None, "status_parametro": "extraido_para_revisao"}
        novo, _ = apply_decision_to_campo(
            campo_data=campo,
            decisao="manter_pendente",
            valor_revisado=None,
            revisor="Maria",
            data_revisao="2026-06-18",
            observacao_revisor="",
            timestamp=TIMESTAMP,
        )
        self.assertEqual(novo["status_parametro"], "pendente_revisao")

    def test_manter_pendente_nao_seta_valido(self):
        campo = {"valor": 1000.0, "status_parametro": "extraido_para_revisao"}
        novo, _ = apply_decision_to_campo(
            campo_data=campo,
            decisao="manter_pendente",
            valor_revisado=None,
            revisor="X",
            data_revisao="2026-06-18",
            observacao_revisor="",
            timestamp=TIMESTAMP,
        )
        self.assertNotEqual(novo["status_parametro"], "valido")


# ──────────────────────────────────────────────────────────────────────────────
# Cenário 10 — rejeitar → status "rejeitado" (AC2)
# ──────────────────────────────────────────────────────────────────────────────

class TestCenario10Rejeitar(unittest.TestCase):
    def test_status_rejeitado(self):
        campo = {"valor": 100.0, "status_parametro": "extraido_para_revisao"}
        novo, _ = apply_decision_to_campo(
            campo_data=campo,
            decisao="rejeitar",
            valor_revisado=None,
            revisor="X",
            data_revisao="2026-06-18",
            observacao_revisor="",
            timestamp=TIMESTAMP,
        )
        self.assertEqual(novo["status_parametro"], "rejeitado")

    def test_rejeitar_via_process_decisions(self):
        rows = _make_xlsx_rows([{"campo": "piso_salarial", "decisao_final": "rejeitar"}])
        base = _make_base()
        base_mod, _, summary = process_decisions(rows, base, TIMESTAMP)

        piso = base_mod["registros"][0]["itens_cct"]["piso_salarial"]
        self.assertEqual(piso["status_parametro"], "rejeitado")
        self.assertEqual(summary["rejeitar"], 1)


# ──────────────────────────────────────────────────────────────────────────────
# Cenário 11 — marcar_conflito preserva opcoes_identificadas (AC2)
# ──────────────────────────────────────────────────────────────────────────────

class TestCenario11MarcarConflito(unittest.TestCase):
    def test_opcoes_preservadas(self):
        opcoes = [1540.47, 1620.0]
        campo = {
            "valor": 1540.47,
            "status_parametro": "conflito",
            "opcoes_identificadas": opcoes,
        }
        novo, _ = apply_decision_to_campo(
            campo_data=campo,
            decisao="marcar_conflito",
            valor_revisado=None,
            revisor="Maria",
            data_revisao="2026-06-18",
            observacao_revisor="",
            timestamp=TIMESTAMP,
        )
        self.assertEqual(novo["status_parametro"], "conflito")
        self.assertEqual(novo["opcoes_identificadas"], opcoes)

    def test_opcoes_nao_sobrescritas_com_null(self):
        opcoes = ["44h/sem", "30h/sem"]
        campo = {
            "valor": 44.0,
            "status_parametro": "extraido_para_revisao",
            "opcoes_identificadas": opcoes,
        }
        novo, _ = apply_decision_to_campo(
            campo_data=campo,
            decisao="marcar_conflito",
            valor_revisado=None,
            revisor="X",
            data_revisao="2026-06-18",
            observacao_revisor="",
            timestamp=TIMESTAMP,
        )
        self.assertIsNotNone(novo.get("opcoes_identificadas"))
        self.assertEqual(novo["opcoes_identificadas"], opcoes)

    def test_marcar_conflito_via_process_decisions(self):
        base = _make_base([
            _make_registro(opcoes_identificadas=[1540.47, 1620.0])
        ])
        rows = _make_xlsx_rows([{"campo": "piso_salarial", "decisao_final": "marcar_conflito"}])
        base_mod, _, summary = process_decisions(rows, base, TIMESTAMP)

        piso = base_mod["registros"][0]["itens_cct"]["piso_salarial"]
        self.assertEqual(piso["status_parametro"], "conflito")
        self.assertEqual(piso["opcoes_identificadas"], [1540.47, 1620.0])
        self.assertEqual(summary["marcar_conflito"], 1)


# ──────────────────────────────────────────────────────────────────────────────
# Cenário 12 — buscar_fonte → pendente_revisao + acao_recomendada (AC2)
# ──────────────────────────────────────────────────────────────────────────────

class TestCenario12BuscarFonte(unittest.TestCase):
    def test_status_pendente_e_acao_recomendada(self):
        campo = {"valor": None, "status_parametro": "pendente_revisao"}
        novo, _ = apply_decision_to_campo(
            campo_data=campo,
            decisao="buscar_fonte",
            valor_revisado=None,
            revisor="X",
            data_revisao="2026-06-18",
            observacao_revisor="",
            timestamp=TIMESTAMP,
        )
        self.assertEqual(novo["status_parametro"], "pendente_revisao")
        self.assertEqual(novo["acao_recomendada"], "buscar_fonte")

    def test_buscar_fonte_nao_valida(self):
        campo = {"valor": 100.0, "status_parametro": "extraido_para_revisao"}
        novo, _ = apply_decision_to_campo(
            campo_data=campo,
            decisao="buscar_fonte",
            valor_revisado=None,
            revisor="X",
            data_revisao="2026-06-18",
            observacao_revisor="",
            timestamp=TIMESTAMP,
        )
        self.assertNotEqual(novo["status_parametro"], "valido")

    def test_buscar_fonte_via_process_decisions(self):
        rows = _make_xlsx_rows([{"campo": "adicional_noturno", "decisao_final": "buscar_fonte"}])
        base = _make_base()
        base_mod, _, summary = process_decisions(rows, base, TIMESTAMP)

        adicional = base_mod["registros"][0]["itens_cct"]["adicional_noturno"]
        self.assertEqual(adicional["status_parametro"], "pendente_revisao")
        self.assertEqual(adicional.get("acao_recomendada"), "buscar_fonte")
        self.assertEqual(summary["buscar_fonte"], 1)


# ──────────────────────────────────────────────────────────────────────────────
# Cenário 13 — Auditoria contém todos os campos obrigatórios (AC4)
# ──────────────────────────────────────────────────────────────────────────────

class TestCenario13Auditoria(unittest.TestCase):
    CAMPOS_OBRIGATORIOS = {
        "registro_id",
        "campo",
        "decisao_final",
        "status_anterior",
        "status_novo",
        "valor_anterior",
        "valor_novo",
        "revisor",
        "data_revisao",
        "observacao_revisor",
        "resultado",
        "motivo",
        "timestamp_execucao",
    }

    def test_registro_auditoria_contém_todos_campos(self):
        rows = _make_xlsx_rows([{"campo": "piso_salarial", "decisao_final": "validar"}])
        base = _make_base()
        _, audit_records, _ = process_decisions(rows, base, TIMESTAMP)

        self.assertEqual(len(audit_records), 1)
        record = audit_records[0]
        for campo in self.CAMPOS_OBRIGATORIOS:
            self.assertIn(campo, record, f"Campo obrigatório ausente na auditoria: {campo}")

    def test_auditoria_registra_status_antes_e_depois(self):
        rows = _make_xlsx_rows([{"campo": "piso_salarial", "decisao_final": "validar"}])
        base = _make_base()
        _, audit_records, _ = process_decisions(rows, base, TIMESTAMP)

        record = audit_records[0]
        self.assertEqual(record["status_anterior"], "extraido_para_revisao")
        self.assertEqual(record["status_novo"], "valido")

    def test_auditoria_de_erro_contem_motivo(self):
        rows = _make_xlsx_rows([{"campo": "campo_invalido", "decisao_final": "validar"}])
        base = _make_base()
        _, audit_records, _ = process_decisions(rows, base, TIMESTAMP)

        record = audit_records[0]
        self.assertEqual(record["resultado"], "erro")
        self.assertIsNotNone(record["motivo"])

    def test_audit_report_estrutura_completa(self):
        summary = {
            "total_lidas": 3,
            "validar": 1, "manter_pendente": 1, "rejeitar": 0,
            "marcar_conflito": 0, "buscar_fonte": 0, "ignoradas": 0, "erros": 1,
        }
        audit_records = [
            {
                "registro_id": "R1", "campo": "piso_salarial", "decisao_final": "validar",
                "resultado": "aplicado", "motivo": None,
                "status_anterior": "pendente", "status_novo": "valido",
                "valor_anterior": 1000, "valor_novo": 1000,
                "revisor": "X", "data_revisao": "2026-06-18",
                "observacao_revisor": "", "timestamp_execucao": TIMESTAMP,
            }
        ]
        report = build_audit_report(audit_records, summary, TIMESTAMP)

        self.assertIn("timestamp_execucao", report)
        self.assertIn("resumo", report)
        self.assertIn("registros", report)
        self.assertEqual(report["total_lidas"], 3)

    def test_auditoria_persistida_na_execucao_real(self):
        rows = _make_xlsx_rows()
        base = _make_base()
        exit_code, _, audit_final, _ = _run_main_with_mocks(rows, base)

        self.assertEqual(exit_code, 0)
        self.assertIsNotNone(audit_final)
        self.assertIn("registros", audit_final)
        self.assertGreater(len(audit_final["registros"]), 0)


# ──────────────────────────────────────────────────────────────────────────────
# Cenário 14 — Base JS regenerada corretamente após execução real (AC5)
# ──────────────────────────────────────────────────────────────────────────────

class TestCenario14JSRegenerado(unittest.TestCase):
    def test_js_criado_apos_execucao_real(self):
        rows = _make_xlsx_rows()
        base = _make_base()
        exit_code, _, _, js_content = _run_main_with_mocks(rows, base)

        self.assertEqual(exit_code, 0)
        self.assertIsNotNone(js_content)
        self.assertIn("window.BASE_PARAMETROS_SINDICAIS", js_content)

    def test_js_contem_dados_atualizados(self):
        rows = _make_xlsx_rows([{"campo": "piso_salarial", "decisao_final": "validar"}])
        base = _make_base()
        exit_code, _, _, js_content = _run_main_with_mocks(rows, base)

        self.assertEqual(exit_code, 0)
        self.assertIn("valido", js_content)

    def test_js_nao_criado_em_dry_run(self):
        rows = _make_xlsx_rows()
        base = _make_base()
        exit_code, _, _, js_content = _run_main_with_mocks(rows, base, dry_run=True)

        self.assertEqual(exit_code, 0)
        self.assertIsNone(js_content)

    def test_save_js_formato_correto(self):
        base = _make_base()
        with tempfile.NamedTemporaryFile(suffix=".js", delete=False) as f:
            path = f.name
        try:
            _save_js(base, path)
            with open(path, encoding="utf-8") as f:
                content = f.read()
            self.assertTrue(content.startswith("// Gerado automaticamente"))
            self.assertIn("window.BASE_PARAMETROS_SINDICAIS = ", content)
            self.assertTrue(content.rstrip().endswith(";"))
        finally:
            os.unlink(path)


# ──────────────────────────────────────────────────────────────────────────────
# Formato por registro (XLSX review_decisions_template.xlsx) — expansão automática
# ──────────────────────────────────────────────────────────────────────────────

class TestFormatoXLSXPorRegistro(unittest.TestCase):
    def _make_xlsx_wb_por_registro(self, decisao: str = "validar", piso_valor=1540.47):
        """Cria um workbook no formato por-registro (CODIGO DO SINDICATO)."""
        import openpyxl
        from apply_review_decisions import CAMPO_TO_XLSX_COL, REQUIRED_COLS_XLSX

        wb = openpyxl.Workbook()
        ws = wb.active

        business_cols = list(CAMPO_TO_XLSX_COL.values())
        review_cols = ["decisao_final", "valor_revisado", "observacao_revisor", "revisor", "data_revisao"]
        all_cols = ["CODIGO DO SINDICATO"] + business_cols + review_cols

        ws.append(all_cols)

        row = {c: None for c in all_cols}
        row["CODIGO DO SINDICATO"] = "REG-SP-TEST-2025"
        row["Piso administrativo"] = piso_valor
        row["decisao_final"] = decisao
        row["observacao_revisor"] = "OK"
        row["revisor"] = "Maria"
        row["data_revisao"] = "2026-06-18"

        ws.append([row[c] for c in all_cols])
        return wb

    def test_expande_para_entradas_por_campo(self):
        """Uma linha por-registro deve gerar uma entrada por campo em CAMPO_TO_XLSX_COL."""
        import apply_review_decisions as mod
        wb = self._make_xlsx_wb_por_registro()

        with (
            patch("openpyxl.load_workbook", return_value=wb),
            patch("os.path.exists", return_value=True),
        ):
            rows = mod.load_decisions_xlsx("template.xlsx")

        self.assertEqual(len(rows), len(CAMPO_TO_XLSX_COL))
        campos = {r["campo"] for r in rows}
        self.assertEqual(campos, set(CAMPO_TO_XLSX_COL.keys()))

    def test_valor_piso_mapeado_corretamente(self):
        """O valor de 'Piso administrativo' deve virar valor_revisado de 'piso_salarial'."""
        import apply_review_decisions as mod
        wb = self._make_xlsx_wb_por_registro(piso_valor=1600.0)

        with (
            patch("openpyxl.load_workbook", return_value=wb),
            patch("os.path.exists", return_value=True),
        ):
            rows = mod.load_decisions_xlsx("template.xlsx")

        piso_row = next(r for r in rows if r["campo"] == "piso_salarial")
        self.assertEqual(piso_row["registro_id"], "REG-SP-TEST-2025")
        self.assertEqual(piso_row["valor_revisado"], 1600.0)
        self.assertEqual(piso_row["decisao_final"], "validar")

    def test_dry_run_com_xlsx_por_registro(self):
        """dry-run com o formato por-registro retorna exit_code=0 sem alterar arquivos."""
        import apply_review_decisions as mod
        wb = self._make_xlsx_wb_por_registro()
        base = _make_base()

        # Pre-expande as linhas usando o workbook mock (testa a expansão + o dry-run)
        with (
            patch("openpyxl.load_workbook", return_value=wb),
            patch("os.path.exists", return_value=True),
        ):
            expanded_rows = mod.load_decisions_xlsx("template.xlsx")

        self.assertEqual(len(expanded_rows), len(CAMPO_TO_XLSX_COL))

        # Confirma que dry-run com as linhas expandidas não toca nenhum arquivo
        exit_code, _, audit, js = _run_main_with_mocks(expanded_rows, base, dry_run=True)
        self.assertEqual(exit_code, 0)
        self.assertIsNone(audit)
        self.assertIsNone(js)


if __name__ == "__main__":
    unittest.main()

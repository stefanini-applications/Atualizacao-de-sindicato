"""
Testes automatizados para generate_review_queue.py (PRJ-69).

Cobre os 12 cenários obrigatórios definidos no AC5:
  1.  Campo extraido_para_revisao entra na fila
  2.  Campo pendente_revisao entra na fila
  3.  Campo conflito entra na fila
  4.  Campo valido NÃO entra na fila
  5.  Prioridade alta para conflito
  6.  Prioridade alta para campo crítico
  7.  acao_sugerida: validar quando há fonte_textual
  8.  acao_sugerida: revisar_conflito quando há conflito
  9.  acao_sugerida: buscar_fonte quando está pendente
  10. --dry-run não cria arquivo
  11. Relatório final contém todos os campos obrigatórios e totais agregados
  12. base_parametros_sindicais.json e .js não são alterados
"""

import copy
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from generate_review_queue import (
    CAMPOS_CRITICOS,
    ELIGIBLE_ORIGENS,
    ELIGIBLE_STATUSES,
    _build_item,
    _calc_acao_sugerida,
    _calc_prioridade,
    _build_totals,
    _is_eligible,
    build_review_queue,
    generate_report,
    main,
    save_report,
)

# ──────────────────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────────────────

FIELD_EXTRAIDO = {
    "valor": 1540.47,
    "percentual": None,
    "status_parametro": "extraido_para_revisao",
    "origem": "pdf_cct",
    "fonte": "PDF da CCT",
    "fonte_textual": "CLÁUSULA TERCEIRA - PISO SALARIAL ...",
    "data_extracao": "2026-06-15",
    "observacao": None,
    "opcoes_identificadas": None,
}

FIELD_PENDENTE = {
    "valor": None,
    "percentual": None,
    "status_parametro": "pendente_revisao",
    "origem": "nao_identificado_pdf",
    "fonte": None,
    "fonte_textual": None,
    "data_extracao": "2026-06-15",
    "observacao": "Cláusula não localizada",
    "opcoes_identificadas": None,
}

FIELD_CONFLITO = {
    "valor": 1600.0,
    "percentual": None,
    "status_parametro": "conflito",
    "origem": "conflito_pdf_mte",
    "fonte": "PDF da CCT",
    "fonte_textual": "CLÁUSULA TERCEIRA ...",
    "data_extracao": "2026-06-15",
    "observacao": "Divergência PDF vs MTE",
    "opcoes_identificadas": [1540.47, 1620.0],
}

FIELD_VALIDO = {
    "valor": 1500.00,
    "percentual": None,
    "status_parametro": "valido",
    "origem": "pdf_cct",
    "fonte": "PDF da CCT",
    "fonte_textual": "CLÁUSULA TERCEIRA ...",
    "data_extracao": "2026-06-15",
    "observacao": None,
    "opcoes_identificadas": None,
}

FIELD_MTE = {
    "valor": 1412.0,
    "percentual": None,
    "status_parametro": "extraido_para_revisao",
    "origem": "fonte_oficial_mte",
    "fonte": "Sistema Mediador / MTE",
    "fonte_textual": "Instrumento MTE ...",
    "data_extracao": "2026-06-15",
    "observacao": None,
    "opcoes_identificadas": None,
}


def _make_record(itens_cct: dict | None = None, overrides: dict | None = None) -> dict:
    base = {
        "id_registro_reajuste": "REG-TEST-2025",
        "uf": "SP",
        "sindicato": "Sindicato Teste",
        "categoria": "Tecnologia",
        "ano_referencia": 2025,
        "status_parametro": "extraido_para_revisao",
        "itens_cct": itens_cct or {},
    }
    if overrides:
        base.update(overrides)
    return base


def _make_base(records: list[dict]) -> dict:
    return {"data_geracao": "2026-06-15T00:00:00+00:00", "registros": records}


# ──────────────────────────────────────────────────────────────────────────────
# Cenário 1 — Campo extraido_para_revisao entra na fila
# ──────────────────────────────────────────────────────────────────────────────

class TestCenario1ExtraidoEntraFila(unittest.TestCase):
    def test_extraido_para_revisao_e_elegivel(self):
        self.assertTrue(_is_eligible(FIELD_EXTRAIDO))

    def test_extraido_aparece_na_fila(self):
        record = _make_record({"piso_salarial": copy.deepcopy(FIELD_EXTRAIDO)})
        base = _make_base([record])
        itens = build_review_queue(base)
        campos = [i["campo"] for i in itens]
        self.assertIn("piso_salarial", campos)


# ──────────────────────────────────────────────────────────────────────────────
# Cenário 2 — Campo pendente_revisao entra na fila
# ──────────────────────────────────────────────────────────────────────────────

class TestCenario2PendenteEntraFila(unittest.TestCase):
    def test_pendente_revisao_e_elegivel(self):
        self.assertTrue(_is_eligible(FIELD_PENDENTE))

    def test_pendente_aparece_na_fila(self):
        record = _make_record({"hora_extra": copy.deepcopy(FIELD_PENDENTE)})
        base = _make_base([record])
        itens = build_review_queue(base)
        campos = [i["campo"] for i in itens]
        self.assertIn("hora_extra", campos)


# ──────────────────────────────────────────────────────────────────────────────
# Cenário 3 — Campo conflito entra na fila
# ──────────────────────────────────────────────────────────────────────────────

class TestCenario3ConflitoEntraFila(unittest.TestCase):
    def test_conflito_e_elegivel(self):
        self.assertTrue(_is_eligible(FIELD_CONFLITO))

    def test_conflito_aparece_na_fila(self):
        record = _make_record({"jornada": copy.deepcopy(FIELD_CONFLITO)})
        base = _make_base([record])
        itens = build_review_queue(base)
        campos = [i["campo"] for i in itens]
        self.assertIn("jornada", campos)


# ──────────────────────────────────────────────────────────────────────────────
# Cenário 4 — Campo valido NÃO entra na fila
# ──────────────────────────────────────────────────────────────────────────────

class TestCenario4ValidoNaoEntraFila(unittest.TestCase):
    def test_valido_nao_e_elegivel(self):
        self.assertFalse(_is_eligible(FIELD_VALIDO))

    def test_valido_nao_aparece_na_fila(self):
        record = _make_record({
            "piso_salarial": copy.deepcopy(FIELD_VALIDO),
            "hora_extra": copy.deepcopy(FIELD_PENDENTE),
        })
        base = _make_base([record])
        itens = build_review_queue(base)
        campos = [i["campo"] for i in itens]
        self.assertNotIn("piso_salarial", campos)
        self.assertIn("hora_extra", campos)

    def test_fila_vazia_quando_todos_validos(self):
        record = _make_record({
            "piso_salarial": copy.deepcopy(FIELD_VALIDO),
            "jornada": copy.deepcopy(FIELD_VALIDO),
        })
        base = _make_base([record])
        self.assertEqual(build_review_queue(base), [])


# ──────────────────────────────────────────────────────────────────────────────
# Cenário 5 — Prioridade alta para conflito
# ──────────────────────────────────────────────────────────────────────────────

class TestCenario5PrioridadeAltaConflito(unittest.TestCase):
    def test_status_conflito_gera_prioridade_alta(self):
        self.assertEqual(_calc_prioridade("qualquer_campo", FIELD_CONFLITO), "alta")

    def test_origem_conflito_pdf_mte_gera_prioridade_alta(self):
        field = {**FIELD_EXTRAIDO, "origem": "conflito_pdf_mte", "status_parametro": "extraido_para_revisao"}
        self.assertEqual(_calc_prioridade("qualquer_campo", field), "alta")


# ──────────────────────────────────────────────────────────────────────────────
# Cenário 6 — Prioridade alta para campo crítico
# ──────────────────────────────────────────────────────────────────────────────

class TestCenario6PrioridadeAltaCampoCritico(unittest.TestCase):
    def test_campo_critico_pendente_e_alta(self):
        for campo in ["piso_salarial", "hora_extra", "jornada", "adicional_noturno", "vr", "va"]:
            with self.subTest(campo=campo):
                self.assertEqual(_calc_prioridade(campo, FIELD_PENDENTE), "alta")

    def test_campo_critico_via_mte_e_alta(self):
        self.assertEqual(_calc_prioridade("piso_salarial", FIELD_MTE), "alta")

    def test_campo_nao_critico_pendente_e_baixa(self):
        campo_nao_critico = "plr"
        field = {**FIELD_PENDENTE, "fonte_textual": None}
        prioridade = _calc_prioridade(campo_nao_critico, field)
        self.assertEqual(prioridade, "baixa")


# ──────────────────────────────────────────────────────────────────────────────
# Cenário 7 — acao_sugerida: validar quando há fonte_textual
# ──────────────────────────────────────────────────────────────────────────────

class TestCenario7AcaoValidar(unittest.TestCase):
    def test_extraido_com_fonte_textual_sugere_validar(self):
        self.assertEqual(_calc_acao_sugerida(FIELD_EXTRAIDO), "validar")

    def test_extraido_sem_fonte_textual_sugere_manter_pendente(self):
        field = {**FIELD_EXTRAIDO, "fonte_textual": None}
        self.assertEqual(_calc_acao_sugerida(field), "manter_pendente")


# ──────────────────────────────────────────────────────────────────────────────
# Cenário 8 — acao_sugerida: revisar_conflito quando há conflito
# ──────────────────────────────────────────────────────────────────────────────

class TestCenario8AcaoRevisarConflito(unittest.TestCase):
    def test_status_conflito_sugere_revisar_conflito(self):
        self.assertEqual(_calc_acao_sugerida(FIELD_CONFLITO), "revisar_conflito")

    def test_origem_conflito_pdf_mte_sugere_revisar_conflito(self):
        field = {**FIELD_EXTRAIDO, "origem": "conflito_pdf_mte", "status_parametro": "extraido_para_revisao"}
        self.assertEqual(_calc_acao_sugerida(field), "revisar_conflito")


# ──────────────────────────────────────────────────────────────────────────────
# Cenário 9 — acao_sugerida: buscar_fonte quando está pendente
# ──────────────────────────────────────────────────────────────────────────────

class TestCenario9AcaoBuscarFonte(unittest.TestCase):
    def test_pendente_revisao_sugere_buscar_fonte(self):
        self.assertEqual(_calc_acao_sugerida(FIELD_PENDENTE), "buscar_fonte")

    def test_nao_identificado_pdf_sugere_buscar_fonte(self):
        field = {**FIELD_PENDENTE, "origem": "nao_identificado_pdf_mte"}
        self.assertEqual(_calc_acao_sugerida(field), "buscar_fonte")


# ──────────────────────────────────────────────────────────────────────────────
# Cenário 10 — --dry-run não cria arquivo
# ──────────────────────────────────────────────────────────────────────────────

class TestCenario10DryRunNaoCriaArquivo(unittest.TestCase):
    def test_dry_run_nao_grava_arquivo(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # Cria base mínima temporária
            base = _make_base([_make_record({"piso_salarial": copy.deepcopy(FIELD_PENDENTE)})])
            base_path = os.path.join(tmpdir, "base_parametros_sindicais.json")
            report_path = os.path.join(tmpdir, "parametros_revisao.json")

            with open(base_path, "w", encoding="utf-8") as fh:
                json.dump(base, fh)

            # Invoca main apontando para tmpdir
            import generate_review_queue as grq
            orig_json = grq.JSON_PATH
            orig_report = grq.REPORT_PATH
            orig_reports_dir = grq.REPORTS_DIR
            try:
                grq.JSON_PATH = base_path
                grq.REPORT_PATH = report_path
                grq.REPORTS_DIR = tmpdir
                result = main(["--dry-run"])
            finally:
                grq.JSON_PATH = orig_json
                grq.REPORT_PATH = orig_report
                grq.REPORTS_DIR = orig_reports_dir

            self.assertEqual(result, 0)
            self.assertFalse(os.path.exists(report_path))

    def test_sem_dry_run_grava_arquivo(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            base = _make_base([_make_record({"piso_salarial": copy.deepcopy(FIELD_PENDENTE)})])
            base_path = os.path.join(tmpdir, "base_parametros_sindicais.json")
            report_path = os.path.join(tmpdir, "parametros_revisao.json")

            with open(base_path, "w", encoding="utf-8") as fh:
                json.dump(base, fh)

            import generate_review_queue as grq
            orig_json = grq.JSON_PATH
            orig_report = grq.REPORT_PATH
            orig_reports_dir = grq.REPORTS_DIR
            try:
                grq.JSON_PATH = base_path
                grq.REPORT_PATH = report_path
                grq.REPORTS_DIR = tmpdir
                result = main([])
            finally:
                grq.JSON_PATH = orig_json
                grq.REPORT_PATH = orig_report
                grq.REPORTS_DIR = orig_reports_dir

            self.assertEqual(result, 0)
            self.assertTrue(os.path.exists(report_path))


# ──────────────────────────────────────────────────────────────────────────────
# Cenário 11 — Relatório contém todos os campos obrigatórios e totais
# ──────────────────────────────────────────────────────────────────────────────

class TestCenario11CamposObrigatoriosETotais(unittest.TestCase):
    CAMPOS_ITEM = {
        "registro_id", "uf", "sindicato", "categoria", "ano",
        "campo", "valor", "status_parametro", "origem", "fonte",
        "fonte_textual", "data_extracao", "observacao", "opcoes_identificadas",
        "prioridade_revisao", "acao_sugerida",
    }
    TOTAIS_AGREGADOS = {
        "total_itens_revisao", "total_prioridade_alta", "total_prioridade_media",
        "total_prioridade_baixa", "total_conflitos", "total_pendentes",
        "total_extraidos_para_revisao", "total_por_origem", "total_por_campo",
        "total_por_uf", "total_por_sindicato",
    }
    CAMPOS_CABECALHO = {"data_execucao", "dry_run"}

    def _make_full_base(self):
        record = _make_record({
            "piso_salarial": copy.deepcopy(FIELD_EXTRAIDO),
            "hora_extra": copy.deepcopy(FIELD_PENDENTE),
            "jornada": copy.deepcopy(FIELD_CONFLITO),
        })
        return _make_base([record])

    def test_cabecalho_presente(self):
        report = generate_report(self._make_full_base(), dry_run=False)
        for campo in self.CAMPOS_CABECALHO:
            self.assertIn(campo, report, f"Campo ausente no cabeçalho: {campo}")

    def test_totais_presentes(self):
        report = generate_report(self._make_full_base(), dry_run=False)
        for campo in self.TOTAIS_AGREGADOS:
            self.assertIn(campo, report, f"Total agregado ausente: {campo}")

    def test_campos_obrigatorios_em_cada_item(self):
        report = generate_report(self._make_full_base(), dry_run=False)
        self.assertGreater(len(report["itens"]), 0)
        for item in report["itens"]:
            for campo in self.CAMPOS_ITEM:
                self.assertIn(campo, item, f"Campo obrigatório ausente em item: {campo}")

    def test_totais_agregados_corretos(self):
        report = generate_report(self._make_full_base(), dry_run=False)
        self.assertEqual(report["total_itens_revisao"], 3)
        self.assertIsInstance(report["total_por_origem"], dict)
        self.assertIsInstance(report["total_por_campo"], dict)
        self.assertIsInstance(report["total_por_uf"], dict)
        self.assertIsInstance(report["total_por_sindicato"], dict)
        # soma deve fechar
        self.assertEqual(
            report["total_prioridade_alta"] + report["total_prioridade_media"] + report["total_prioridade_baixa"],
            report["total_itens_revisao"],
        )

    def test_dry_run_true_no_relatorio(self):
        report = generate_report(self._make_full_base(), dry_run=True)
        self.assertTrue(report["dry_run"])

    def test_dry_run_false_no_relatorio(self):
        report = generate_report(self._make_full_base(), dry_run=False)
        self.assertFalse(report["dry_run"])


# ──────────────────────────────────────────────────────────────────────────────
# Cenário 12 — base_parametros_sindicais.json e .js não são alterados
# ──────────────────────────────────────────────────────────────────────────────

class TestCenario12BaseNaoAlterada(unittest.TestCase):
    def test_base_json_nao_modificada(self):
        """generate_report não altera a base em memória."""
        base = _make_base([
            _make_record({
                "piso_salarial": copy.deepcopy(FIELD_PENDENTE),
                "jornada": copy.deepcopy(FIELD_CONFLITO),
            })
        ])
        base_original = copy.deepcopy(base)
        generate_report(base, dry_run=False)
        self.assertEqual(base, base_original)

    def test_campos_protegidos_nao_escritos(self):
        """status_parametro, valor, origem e fonte_textual não são modificados."""
        field = copy.deepcopy(FIELD_PENDENTE)
        base = _make_base([_make_record({"hora_extra": field})])
        original_status = field["status_parametro"]
        original_valor = field["valor"]
        original_origem = field["origem"]
        original_fonte_textual = field["fonte_textual"]

        generate_report(base, dry_run=False)

        self.assertEqual(field["status_parametro"], original_status)
        self.assertEqual(field["valor"], original_valor)
        self.assertEqual(field["origem"], original_origem)
        self.assertEqual(field["fonte_textual"], original_fonte_textual)

    def test_base_json_real_nao_modificada_no_disco(self):
        """Execução completa (sem dry_run) não toca base_parametros_sindicais.json."""
        import generate_review_queue as grq
        json_path = grq.JSON_PATH
        if not os.path.exists(json_path):
            self.skipTest("base_parametros_sindicais.json não encontrado")

        with open(json_path, "rb") as fh:
            conteudo_antes = fh.read()

        with tempfile.TemporaryDirectory() as tmpdir:
            orig_report = grq.REPORT_PATH
            orig_reports_dir = grq.REPORTS_DIR
            try:
                grq.REPORT_PATH = os.path.join(tmpdir, "parametros_revisao.json")
                grq.REPORTS_DIR = tmpdir
                main([])
            finally:
                grq.REPORT_PATH = orig_report
                grq.REPORTS_DIR = orig_reports_dir

        with open(json_path, "rb") as fh:
            conteudo_depois = fh.read()

        self.assertEqual(conteudo_antes, conteudo_depois)

    def test_base_js_nao_modificado_no_disco(self):
        """Execução completa não toca base_parametros_sindicais.js."""
        import generate_review_queue as grq
        js_path = os.path.join(os.path.dirname(grq.JSON_PATH), "base_parametros_sindicais.js")
        if not os.path.exists(js_path):
            self.skipTest("base_parametros_sindicais.js não encontrado")

        with open(js_path, "rb") as fh:
            conteudo_antes = fh.read()

        with tempfile.TemporaryDirectory() as tmpdir:
            orig_report = grq.REPORT_PATH
            orig_reports_dir = grq.REPORTS_DIR
            try:
                grq.REPORT_PATH = os.path.join(tmpdir, "parametros_revisao.json")
                grq.REPORTS_DIR = tmpdir
                main([])
            finally:
                grq.REPORT_PATH = orig_report
                grq.REPORTS_DIR = orig_reports_dir

        with open(js_path, "rb") as fh:
            conteudo_depois = fh.read()

        self.assertEqual(conteudo_antes, conteudo_depois)


# ──────────────────────────────────────────────────────────────────────────────
# Testes adicionais de filtragem por origem (AC2)
# ──────────────────────────────────────────────────────────────────────────────

class TestFiltragemPorOrigem(unittest.TestCase):
    def test_fonte_oficial_mte_entra_na_fila(self):
        field = {**FIELD_VALIDO, "origem": "fonte_oficial_mte"}
        self.assertTrue(_is_eligible(field))

    def test_nao_identificado_pdf_mte_entra_na_fila(self):
        field = {**FIELD_PENDENTE, "origem": "nao_identificado_pdf_mte"}
        self.assertTrue(_is_eligible(field))

    def test_pdf_cct_valido_nao_entra_na_fila(self):
        self.assertFalse(_is_eligible(FIELD_VALIDO))


if __name__ == "__main__":
    unittest.main()

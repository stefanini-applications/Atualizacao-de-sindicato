"""
Testes automatizados para apply_review_decisions.py (PRJ-72).

Cobre os 14 cenários obrigatórios definidos nos ACs:
  1.  Dry-run não altera base_parametros_sindicais.json, .js nem audit.json
  2.  Execução real altera apenas campos do Excel com decisao_final válida
  3.  Coluna obrigatória ausente aborta execução sem alterar nenhum arquivo
  4.  Decisão inválida → erro na auditoria, demais linhas processadas
  5.  Campo inexistente → erro na auditoria, demais linhas processadas
  6.  registro_id inexistente → erro na auditoria, demais linhas processadas
  7.  validar com valor_revisado vazio → apenas metadados, não altera valor
  8.  validar com valor_revisado diferente → valor_original_pre_validacao + valor novo
  9.  manter_pendente → status "pendente_revisao"
  10. rejeitar → status "rejeitado"
  11. marcar_conflito → preserva opcoes_identificadas existentes
  12. buscar_fonte → status "pendente_revisao" + acao_recomendada: "buscar_fonte"
  13. Auditoria contém todos os campos obrigatórios (antes/depois, revisor, timestamp)
  14. Base JS regenerada corretamente após execução real
"""

import copy
import json
import os
import sys
import tempfile
import unittest
from io import StringIO
from unittest.mock import MagicMock, call, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from apply_review_decisions import (
    REQUIRED_COLUMNS,
    VALID_DECISIONS,
    _coerce_value,
    _find_registro,
    _is_empty,
    apply_decision,
    load_base,
    main,
    print_dry_run_summary,
    process_decisions,
    regenerate_js,
    save_json_atomic,
)

# ──────────────────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────────────────

CAMPO_PISO = {
    "valor": 1540.47,
    "percentual": None,
    "valor_textual": None,
    "tipo": "piso_unico",
    "unidade": "BRL",
    "status_parametro": "extraido_para_revisao",
    "origem": "pdf_cct",
    "fonte": "PDF da CCT",
    "fonte_textual": "CLÁUSULA TERCEIRA - PISO SALARIAL R$ 1.540,47",
    "data_extracao": "2026-06-15",
}

CAMPO_JORNADA_COM_OPCOES = {
    "valor": 44.0,
    "percentual": None,
    "tipo": "jornada",
    "unidade": "h/semana",
    "opcoes_identificadas": ["44h/semana", "30h/semana", "26h/semana"],
    "status_parametro": "extraido_para_revisao",
    "origem": "pdf_cct",
    "fonte": "PDF da CCT",
    "data_extracao": "2026-06-15",
}

CAMPO_ADICIONAL_PENDENTE = {
    "valor": None,
    "percentual": None,
    "status_parametro": "pendente_revisao",
    "origem": "nao_identificado_pdf",
    "fonte": None,
    "data_extracao": "2026-06-15",
}

REGISTRO_BASE = {
    "id_registro_reajuste": "REG-SP-TEST-2025",
    "uf": "SP",
    "sindicato": "Sindicato Teste SP",
    "categoria": "Tecnologia",
    "ano_referencia": 2025,
    "status_parametro": "extraido_para_revisao",
    "conflito": False,
    "itens_cct": {
        "piso_salarial": None,  # will be deep-copied per test
        "jornada": None,
        "adicional_noturno": None,
    },
}

TIMESTAMP = "2026-06-18T12:00:00+00:00"


def _make_base(*campo_tuples) -> dict:
    """
    Cria base mínima com um registro contendo os campos fornecidos.
    campo_tuples: (nome_campo, campo_dict)
    """
    reg = copy.deepcopy(REGISTRO_BASE)
    reg["itens_cct"] = {}
    for nome, dados in campo_tuples:
        reg["itens_cct"][nome] = copy.deepcopy(dados)
    return {"data_geracao": "2026-06-15T00:00:00+00:00", "registros": [reg]}


def _row(
    registro_id="REG-SP-TEST-2025",
    campo="piso_salarial",
    decisao_final="validar",
    valor_revisado="",
    observacao_revisor="Ok revisado",
    revisor="Ana Lima",
    data_revisao="2026-06-18",
) -> dict:
    return {
        "registro_id": registro_id,
        "campo": campo,
        "decisao_final": decisao_final,
        "valor_revisado": valor_revisado,
        "observacao_revisor": observacao_revisor,
        "revisor": revisor,
        "data_revisao": data_revisao,
    }


# ──────────────────────────────────────────────────────────────────────────────
# Cenário 3 — Coluna obrigatória ausente aborta execução (AC1)
# ──────────────────────────────────────────────────────────────────────────────

class TestCenario3ColunaObrigatoriaAusente(unittest.TestCase):
    """Ausência de coluna obrigatória deve abortar sem alterar nenhum arquivo."""

    def _make_xlsx_with_missing_col(self, missing_col: str, tmp_dir: str) -> str:
        import openpyxl
        wb = openpyxl.Workbook()
        ws = wb.active
        cols = [c for c in sorted(REQUIRED_COLUMNS) if c != missing_col]
        ws.append(cols)
        ws.append(["REG-SP-TEST-2025", "piso_salarial", "validar", "", "", ""])
        path = os.path.join(tmp_dir, "decisions_missing.xlsx")
        wb.save(path)
        return path

    def test_aborta_com_coluna_ausente_sem_alterar_base(self):
        from apply_review_decisions import load_excel_decisions

        with tempfile.TemporaryDirectory() as tmp:
            xlsx_path = self._make_xlsx_with_missing_col("decisao_final", tmp)
            with self.assertRaises(SystemExit) as ctx:
                load_excel_decisions(xlsx_path)
            self.assertNotEqual(ctx.exception.code, 0)

    def test_main_aborta_sem_criar_arquivos(self):
        with tempfile.TemporaryDirectory() as tmp:
            import openpyxl
            wb = openpyxl.Workbook()
            ws = wb.active
            # Missing "campo"
            ws.append(["registro_id", "decisao_final", "valor_revisado",
                        "observacao_revisor", "revisor", "data_revisao"])
            ws.append(["REG-SP-TEST-2025", "validar", "", "", "Ana", "2026-06-18"])
            xlsx_path = os.path.join(tmp, "bad.xlsx")
            wb.save(xlsx_path)

            json_path = os.path.join(tmp, "base.json")
            js_path = os.path.join(tmp, "base.js")
            audit_path = os.path.join(tmp, "audit.json")

            with self.assertRaises(SystemExit) as ctx:
                with patch("apply_review_decisions.BASE_JSON_PATH", json_path), \
                     patch("apply_review_decisions.BASE_JS_PATH", js_path), \
                     patch("apply_review_decisions.AUDIT_PATH", audit_path):
                    main(["--decisions", xlsx_path])

            self.assertNotEqual(ctx.exception.code, 0)
            self.assertFalse(os.path.exists(json_path))
            self.assertFalse(os.path.exists(js_path))
            self.assertFalse(os.path.exists(audit_path))


# ──────────────────────────────────────────────────────────────────────────────
# Helpers para criar XLSX válido
# ──────────────────────────────────────────────────────────────────────────────

def _make_valid_xlsx(rows: list[dict], tmp_dir: str, filename="decisions.xlsx") -> str:
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    cols = sorted(REQUIRED_COLUMNS)
    ws.append(cols)
    for row in rows:
        ws.append([row.get(c, "") for c in cols])
    path = os.path.join(tmp_dir, filename)
    wb.save(path)
    return path


def _make_base_json(base: dict, tmp_dir: str) -> str:
    path = os.path.join(tmp_dir, "base.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(base, fh, ensure_ascii=False, indent=2)
    return path


# ──────────────────────────────────────────────────────────────────────────────
# Cenário 1 — Dry-run não altera arquivos (AC3)
# ──────────────────────────────────────────────────────────────────────────────

class TestCenario1DryRun(unittest.TestCase):

    def test_dry_run_nao_altera_base_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = _make_base(("piso_salarial", CAMPO_PISO))
            json_path = _make_base_json(base, tmp)
            js_path = os.path.join(tmp, "base.js")
            audit_path = os.path.join(tmp, "audit.json")

            original_content = open(json_path, encoding="utf-8").read()

            xlsx_path = _make_valid_xlsx([_row()], tmp)

            with patch("apply_review_decisions.BASE_JSON_PATH", json_path), \
                 patch("apply_review_decisions.BASE_JS_PATH", js_path), \
                 patch("apply_review_decisions.AUDIT_PATH", audit_path):
                result = main(["--decisions", xlsx_path, "--dry-run"])

            self.assertEqual(result, 0)
            self.assertEqual(open(json_path, encoding="utf-8").read(), original_content)
            self.assertFalse(os.path.exists(js_path))
            self.assertFalse(os.path.exists(audit_path))

    def test_dry_run_exibe_sumario_no_terminal(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = _make_base(("piso_salarial", CAMPO_PISO))
            json_path = _make_base_json(base, tmp)
            xlsx_path = _make_valid_xlsx([_row()], tmp)

            with patch("apply_review_decisions.BASE_JSON_PATH", json_path), \
                 patch("apply_review_decisions.BASE_JS_PATH", os.path.join(tmp, "base.js")), \
                 patch("apply_review_decisions.AUDIT_PATH", os.path.join(tmp, "audit.json")), \
                 patch("sys.stdout", new_callable=StringIO) as mock_out:
                main(["--decisions", xlsx_path, "--dry-run"])

            output = mock_out.getvalue()
            self.assertIn("dry-run", output.lower())
            self.assertIn("1", output)  # 1 decisão lida


# ──────────────────────────────────────────────────────────────────────────────
# Cenário 2 — Execução real altera apenas campos com decisao_final válida (AC2, AC5)
# ──────────────────────────────────────────────────────────────────────────────

class TestCenario2ExecucaoReal(unittest.TestCase):

    def test_altera_apenas_campo_presente_no_excel(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = _make_base(
                ("piso_salarial", CAMPO_PISO),
                ("adicional_noturno", CAMPO_ADICIONAL_PENDENTE),
            )
            json_path = _make_base_json(base, tmp)
            js_path = os.path.join(tmp, "base.js")
            audit_path = os.path.join(tmp, "audit.json")

            # Only piso_salarial has a decision
            xlsx_path = _make_valid_xlsx([_row(campo="piso_salarial")], tmp)

            with patch("apply_review_decisions.BASE_JSON_PATH", json_path), \
                 patch("apply_review_decisions.BASE_JS_PATH", js_path), \
                 patch("apply_review_decisions.AUDIT_PATH", audit_path):
                result = main(["--decisions", xlsx_path])

            self.assertEqual(result, 0)
            saved = json.load(open(json_path, encoding="utf-8"))
            reg = saved["registros"][0]

            # piso_salarial must be validated
            self.assertEqual(reg["itens_cct"]["piso_salarial"]["status_parametro"], "valido")
            # adicional_noturno must be unchanged
            self.assertEqual(
                reg["itens_cct"]["adicional_noturno"]["status_parametro"], "pendente_revisao"
            )


# ──────────────────────────────────────────────────────────────────────────────
# Cenário 4 — Decisão inválida gera erro, demais linhas processadas (AC2)
# ──────────────────────────────────────────────────────────────────────────────

class TestCenario4DecisaoInvalida(unittest.TestCase):

    def test_decisao_invalida_gera_erro_demais_processadas(self):
        base = _make_base(
            ("piso_salarial", CAMPO_PISO),
            ("adicional_noturno", CAMPO_ADICIONAL_PENDENTE),
        )
        decisions = [
            _row(campo="piso_salarial", decisao_final="decisao_inexistente"),
            _row(campo="adicional_noturno", decisao_final="manter_pendente"),
        ]
        records, counters = process_decisions(copy.deepcopy(base), decisions, TIMESTAMP)

        self.assertEqual(counters["erro"], 1)
        self.assertEqual(counters["manter_pendente"], 1)
        erro_rec = next(r for r in records if r["campo"] == "piso_salarial")
        self.assertEqual(erro_rec["resultado"], "erro")
        self.assertIn("inválida", erro_rec["motivo"])

    def test_decisao_invalida_nao_altera_base(self):
        base = _make_base(("piso_salarial", CAMPO_PISO))
        original_status = base["registros"][0]["itens_cct"]["piso_salarial"]["status_parametro"]
        decisions = [_row(campo="piso_salarial", decisao_final="invalida")]
        process_decisions(base, decisions, TIMESTAMP)
        self.assertEqual(
            base["registros"][0]["itens_cct"]["piso_salarial"]["status_parametro"],
            original_status,
        )


# ──────────────────────────────────────────────────────────────────────────────
# Cenário 5 — Campo inexistente gera erro, demais linhas processadas (AC2)
# ──────────────────────────────────────────────────────────────────────────────

class TestCenario5CampoInexistente(unittest.TestCase):

    def test_campo_inexistente_gera_erro_demais_processadas(self):
        base = _make_base(("piso_salarial", CAMPO_PISO))
        decisions = [
            _row(campo="campo_nao_existe", decisao_final="validar"),
            _row(campo="piso_salarial", decisao_final="manter_pendente"),
        ]
        records, counters = process_decisions(copy.deepcopy(base), decisions, TIMESTAMP)

        self.assertEqual(counters["erro"], 1)
        self.assertEqual(counters["manter_pendente"], 1)
        erro_rec = next(r for r in records if r["campo"] == "campo_nao_existe")
        self.assertEqual(erro_rec["resultado"], "erro")
        self.assertIn("campo_nao_existe", erro_rec["motivo"])


# ──────────────────────────────────────────────────────────────────────────────
# Cenário 6 — registro_id inexistente gera erro, demais processadas (AC2)
# ──────────────────────────────────────────────────────────────────────────────

class TestCenario6RegistroInexistente(unittest.TestCase):

    def test_registro_inexistente_gera_erro_demais_processadas(self):
        base = _make_base(("piso_salarial", CAMPO_PISO))
        decisions = [
            _row(registro_id="REG-INEXISTENTE-9999", campo="piso_salarial"),
            _row(registro_id="REG-SP-TEST-2025", campo="piso_salarial",
                 decisao_final="manter_pendente"),
        ]
        records, counters = process_decisions(copy.deepcopy(base), decisions, TIMESTAMP)

        self.assertEqual(counters["erro"], 1)
        self.assertEqual(counters["manter_pendente"], 1)
        erro_rec = next(r for r in records if r["registro_id"] == "REG-INEXISTENTE-9999")
        self.assertEqual(erro_rec["resultado"], "erro")
        self.assertIn("REG-INEXISTENTE-9999", erro_rec["motivo"])


# ──────────────────────────────────────────────────────────────────────────────
# Cenário 7 — validar com valor_revisado vazio: apenas metadados (AC2)
# ──────────────────────────────────────────────────────────────────────────────

class TestCenario7ValidarSemValorRevisado(unittest.TestCase):

    def test_validar_sem_valor_revisado_nao_altera_valor(self):
        campo = copy.deepcopy(CAMPO_PISO)
        valor_original = campo["valor"]

        apply_decision(
            campo_data=campo,
            decisao="validar",
            valor_revisado="",
            revisor="Ana Lima",
            data_revisao="2026-06-18",
            observacao_revisor="OK",
            timestamp=TIMESTAMP,
        )

        self.assertEqual(campo["status_parametro"], "valido")
        self.assertEqual(campo["valor"], valor_original)
        self.assertNotIn("valor_original_pre_validacao", campo)

    def test_validar_com_valor_revisado_igual_ao_atual_nao_altera_valor(self):
        campo = copy.deepcopy(CAMPO_PISO)
        valor_original = campo["valor"]  # 1540.47

        apply_decision(
            campo_data=campo,
            decisao="validar",
            valor_revisado="1540.47",
            revisor="Ana Lima",
            data_revisao="2026-06-18",
            observacao_revisor="OK",
            timestamp=TIMESTAMP,
        )

        self.assertEqual(campo["status_parametro"], "valido")
        self.assertEqual(campo["valor"], valor_original)
        self.assertNotIn("valor_original_pre_validacao", campo)

    def test_validar_atualiza_metadados_validacao(self):
        campo = copy.deepcopy(CAMPO_PISO)
        apply_decision(
            campo_data=campo,
            decisao="validar",
            valor_revisado="",
            revisor="Ana Lima",
            data_revisao="2026-06-18",
            observacao_revisor="Confirmado",
            timestamp=TIMESTAMP,
        )
        self.assertEqual(campo["validado_por"], "Ana Lima")
        self.assertEqual(campo["data_validacao"], "2026-06-18")
        self.assertEqual(campo["observacao_validacao"], "Confirmado")


# ──────────────────────────────────────────────────────────────────────────────
# Cenário 8 — validar com valor_revisado diferente: preserva original + atualiza
# ──────────────────────────────────────────────────────────────────────────────

class TestCenario8ValidarComValorRevisadoDiferente(unittest.TestCase):

    def test_preserva_valor_original_pre_validacao(self):
        campo = copy.deepcopy(CAMPO_PISO)
        valor_anterior = campo["valor"]  # 1540.47

        apply_decision(
            campo_data=campo,
            decisao="validar",
            valor_revisado="1600.00",
            revisor="Ana Lima",
            data_revisao="2026-06-18",
            observacao_revisor="Valor corrigido",
            timestamp=TIMESTAMP,
        )

        self.assertEqual(campo["status_parametro"], "valido")
        self.assertEqual(campo["valor_original_pre_validacao"], valor_anterior)
        self.assertEqual(campo["valor"], 1600.0)

    def test_valor_novo_registrado_na_auditoria(self):
        base = _make_base(("piso_salarial", CAMPO_PISO))
        decisions = [_row(campo="piso_salarial", valor_revisado="1600.00")]
        records, _ = process_decisions(base, decisions, TIMESTAMP)

        rec = records[0]
        self.assertEqual(rec["resultado"], "aplicado")
        self.assertEqual(rec["valor_anterior"], 1540.47)
        self.assertEqual(rec["valor_novo"], 1600.0)


# ──────────────────────────────────────────────────────────────────────────────
# Cenário 9 — manter_pendente → status "pendente_revisao" (AC2)
# ──────────────────────────────────────────────────────────────────────────────

class TestCenario9ManterPendente(unittest.TestCase):

    def test_manter_pendente_status_pendente_revisao(self):
        campo = copy.deepcopy(CAMPO_PISO)
        apply_decision(
            campo_data=campo,
            decisao="manter_pendente",
            valor_revisado="",
            revisor="Ana Lima",
            data_revisao="2026-06-18",
            observacao_revisor="",
            timestamp=TIMESTAMP,
        )
        self.assertEqual(campo["status_parametro"], "pendente_revisao")

    def test_manter_pendente_nao_valida(self):
        campo = copy.deepcopy(CAMPO_PISO)
        apply_decision(
            campo_data=campo,
            decisao="manter_pendente",
            valor_revisado="",
            revisor="Ana Lima",
            data_revisao="2026-06-18",
            observacao_revisor="",
            timestamp=TIMESTAMP,
        )
        self.assertNotEqual(campo["status_parametro"], "valido")


# ──────────────────────────────────────────────────────────────────────────────
# Cenário 10 — rejeitar → status "rejeitado" (AC2)
# ──────────────────────────────────────────────────────────────────────────────

class TestCenario10Rejeitar(unittest.TestCase):

    def test_rejeitar_marca_como_rejeitado(self):
        campo = copy.deepcopy(CAMPO_PISO)
        apply_decision(
            campo_data=campo,
            decisao="rejeitar",
            valor_revisado="",
            revisor="Ana Lima",
            data_revisao="2026-06-18",
            observacao_revisor="Dado incorreto",
            timestamp=TIMESTAMP,
        )
        self.assertEqual(campo["status_parametro"], "rejeitado")


# ──────────────────────────────────────────────────────────────────────────────
# Cenário 11 — marcar_conflito preserva opcoes_identificadas (AC2)
# ──────────────────────────────────────────────────────────────────────────────

class TestCenario11MarcarConflito(unittest.TestCase):

    def test_marcar_conflito_preserva_opcoes_identificadas(self):
        campo = copy.deepcopy(CAMPO_JORNADA_COM_OPCOES)
        opcoes_originais = copy.deepcopy(campo["opcoes_identificadas"])

        apply_decision(
            campo_data=campo,
            decisao="marcar_conflito",
            valor_revisado="",
            revisor="Ana Lima",
            data_revisao="2026-06-18",
            observacao_revisor="Conflito confirmado",
            timestamp=TIMESTAMP,
        )

        self.assertEqual(campo["status_parametro"], "conflito")
        self.assertEqual(campo["opcoes_identificadas"], opcoes_originais)

    def test_marcar_conflito_sem_opcoes_nao_cria_lista_vazia(self):
        campo = copy.deepcopy(CAMPO_PISO)
        self.assertNotIn("opcoes_identificadas", campo)

        apply_decision(
            campo_data=campo,
            decisao="marcar_conflito",
            valor_revisado="",
            revisor="Ana Lima",
            data_revisao="2026-06-18",
            observacao_revisor="",
            timestamp=TIMESTAMP,
        )

        self.assertEqual(campo["status_parametro"], "conflito")
        # opcoes_identificadas não deve ser criado como null/lista vazia
        self.assertNotIn("opcoes_identificadas", campo)


# ──────────────────────────────────────────────────────────────────────────────
# Cenário 12 — buscar_fonte → pendente_revisao + acao_recomendada (AC2)
# ──────────────────────────────────────────────────────────────────────────────

class TestCenario12BuscarFonte(unittest.TestCase):

    def test_buscar_fonte_status_pendente_e_acao(self):
        campo = copy.deepcopy(CAMPO_PISO)
        apply_decision(
            campo_data=campo,
            decisao="buscar_fonte",
            valor_revisado="",
            revisor="Ana Lima",
            data_revisao="2026-06-18",
            observacao_revisor="Precisa de fonte oficial",
            timestamp=TIMESTAMP,
        )
        self.assertEqual(campo["status_parametro"], "pendente_revisao")
        self.assertEqual(campo["acao_recomendada"], "buscar_fonte")


# ──────────────────────────────────────────────────────────────────────────────
# Cenário 13 — Auditoria contém todos os campos obrigatórios (AC4)
# ──────────────────────────────────────────────────────────────────────────────

class TestCenario13AuditoriaCompleta(unittest.TestCase):

    REQUIRED_AUDIT_FIELDS = {
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

    def test_auditoria_contem_todos_campos_obrigatorios_em_sucesso(self):
        base = _make_base(("piso_salarial", CAMPO_PISO))
        decisions = [_row()]
        records, _ = process_decisions(base, decisions, TIMESTAMP)

        self.assertEqual(len(records), 1)
        rec = records[0]
        for field in self.REQUIRED_AUDIT_FIELDS:
            self.assertIn(field, rec, f"Campo ausente na auditoria: {field}")

    def test_auditoria_contem_todos_campos_em_erro(self):
        base = _make_base(("piso_salarial", CAMPO_PISO))
        decisions = [_row(campo="campo_inexistente")]
        records, _ = process_decisions(base, decisions, TIMESTAMP)

        rec = records[0]
        for field in self.REQUIRED_AUDIT_FIELDS:
            self.assertIn(field, rec, f"Campo ausente na auditoria de erro: {field}")
        self.assertEqual(rec["resultado"], "erro")

    def test_auditoria_registra_status_antes_e_depois(self):
        base = _make_base(("piso_salarial", CAMPO_PISO))
        decisions = [_row(decisao_final="rejeitar")]
        records, _ = process_decisions(base, decisions, TIMESTAMP)

        rec = records[0]
        self.assertEqual(rec["status_anterior"], "extraido_para_revisao")
        self.assertEqual(rec["status_novo"], "rejeitado")

    def test_auditoria_preserva_revisor_e_timestamp(self):
        base = _make_base(("piso_salarial", CAMPO_PISO))
        decisions = [_row(revisor="Carlos Souza", data_revisao="2026-06-18")]
        records, _ = process_decisions(base, decisions, TIMESTAMP)

        rec = records[0]
        self.assertEqual(rec["revisor"], "Carlos Souza")
        self.assertEqual(rec["data_revisao"], "2026-06-18")
        self.assertEqual(rec["timestamp_execucao"], TIMESTAMP)

    def test_auditoria_json_gerada_em_execucao_real(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = _make_base(("piso_salarial", CAMPO_PISO))
            json_path = _make_base_json(base, tmp)
            js_path = os.path.join(tmp, "base.js")
            audit_path = os.path.join(tmp, "audit.json")

            xlsx_path = _make_valid_xlsx([_row()], tmp)

            with patch("apply_review_decisions.BASE_JSON_PATH", json_path), \
                 patch("apply_review_decisions.BASE_JS_PATH", js_path), \
                 patch("apply_review_decisions.AUDIT_PATH", audit_path):
                main(["--decisions", xlsx_path])

            self.assertTrue(os.path.exists(audit_path))
            audit = json.load(open(audit_path, encoding="utf-8"))
            self.assertIn("timestamp_execucao", audit)
            self.assertIn("registros", audit)
            self.assertGreater(len(audit["registros"]), 0)
            for field in self.REQUIRED_AUDIT_FIELDS:
                self.assertIn(field, audit["registros"][0])


# ──────────────────────────────────────────────────────────────────────────────
# Cenário 14 — Base JS regenerada corretamente após execução real (AC5)
# ──────────────────────────────────────────────────────────────────────────────

class TestCenario14JSRegenerado(unittest.TestCase):

    def test_js_gerado_com_conteudo_correto(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = _make_base(("piso_salarial", CAMPO_PISO))
            json_path = _make_base_json(base, tmp)
            js_path = os.path.join(tmp, "base.js")
            audit_path = os.path.join(tmp, "audit.json")

            xlsx_path = _make_valid_xlsx([_row()], tmp)

            with patch("apply_review_decisions.BASE_JSON_PATH", json_path), \
                 patch("apply_review_decisions.BASE_JS_PATH", js_path), \
                 patch("apply_review_decisions.AUDIT_PATH", audit_path):
                main(["--decisions", xlsx_path])

            self.assertTrue(os.path.exists(js_path))
            js_content = open(js_path, encoding="utf-8").read()
            self.assertIn("window.BASE_PARAMETROS_SINDICAIS = ", js_content)
            self.assertTrue(js_content.strip().endswith(";"))

            # JS deve refletir o estado pós-decisão
            json_saved = json.load(open(json_path, encoding="utf-8"))
            expected_json = json.dumps(json_saved, ensure_ascii=False)
            self.assertIn(expected_json, js_content)

    def test_js_nao_gerado_em_dry_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = _make_base(("piso_salarial", CAMPO_PISO))
            json_path = _make_base_json(base, tmp)
            js_path = os.path.join(tmp, "base.js")
            audit_path = os.path.join(tmp, "audit.json")

            xlsx_path = _make_valid_xlsx([_row()], tmp)

            with patch("apply_review_decisions.BASE_JSON_PATH", json_path), \
                 patch("apply_review_decisions.BASE_JS_PATH", js_path), \
                 patch("apply_review_decisions.AUDIT_PATH", audit_path):
                main(["--decisions", xlsx_path, "--dry-run"])

            self.assertFalse(os.path.exists(js_path))


# ──────────────────────────────────────────────────────────────────────────────
# Testes adicionais de integração
# ──────────────────────────────────────────────────────────────────────────────

class TestHelpers(unittest.TestCase):

    def test_is_empty_com_none(self):
        from apply_review_decisions import _is_empty
        self.assertTrue(_is_empty(None))

    def test_is_empty_com_string_vazia(self):
        from apply_review_decisions import _is_empty
        self.assertTrue(_is_empty(""))
        self.assertTrue(_is_empty("   "))

    def test_is_empty_com_valor_real(self):
        from apply_review_decisions import _is_empty
        self.assertFalse(_is_empty("1540.47"))
        self.assertFalse(_is_empty("validar"))

    def test_coerce_value_float(self):
        self.assertEqual(_coerce_value("1600.00", 1540.47), 1600.0)

    def test_coerce_value_string_quando_atual_nao_numerico(self):
        self.assertEqual(_coerce_value("novo_valor", "antigo"), "novo_valor")

    def test_find_registro_encontra_por_id(self):
        base = _make_base(("piso_salarial", CAMPO_PISO))
        reg = _find_registro(base, "REG-SP-TEST-2025")
        self.assertIsNotNone(reg)
        self.assertEqual(reg["id_registro_reajuste"], "REG-SP-TEST-2025")

    def test_find_registro_retorna_none_quando_nao_encontrado(self):
        base = _make_base(("piso_salarial", CAMPO_PISO))
        reg = _find_registro(base, "REG-INEXISTENTE")
        self.assertIsNone(reg)

    def test_save_json_atomic_cria_arquivo(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "test.json")
            data = {"key": "value", "num": 42}
            save_json_atomic(data, path)
            self.assertTrue(os.path.exists(path))
            loaded = json.load(open(path, encoding="utf-8"))
            self.assertEqual(loaded, data)

    def test_regenerate_js_formato_correto(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = {"registros": [{"id": "X"}]}
            json_path = os.path.join(tmp, "base.json")
            js_path = os.path.join(tmp, "base.js")
            with open(json_path, "w", encoding="utf-8") as fh:
                json.dump(data, fh)
            regenerate_js(json_path, js_path)
            content = open(js_path, encoding="utf-8").read()
            self.assertIn("window.BASE_PARAMETROS_SINDICAIS = ", content)
            self.assertIn(";\n", content)


class TestProcessDecisionsContadores(unittest.TestCase):

    def test_contadores_corretos_para_multiplas_decisoes(self):
        base = _make_base(
            ("piso_salarial", CAMPO_PISO),
            ("jornada", CAMPO_JORNADA_COM_OPCOES),
            ("adicional_noturno", CAMPO_ADICIONAL_PENDENTE),
        )
        decisions = [
            _row(campo="piso_salarial", decisao_final="validar"),
            _row(campo="jornada", decisao_final="marcar_conflito"),
            _row(campo="adicional_noturno", decisao_final="buscar_fonte"),
            _row(campo="campo_inexistente", decisao_final="validar"),
            _row(campo="piso_salarial", decisao_final=""),  # ignorada
        ]
        _, counters = process_decisions(copy.deepcopy(base), decisions, TIMESTAMP)

        self.assertEqual(counters["validar"], 1)
        self.assertEqual(counters["marcar_conflito"], 1)
        self.assertEqual(counters["buscar_fonte"], 1)
        self.assertEqual(counters["erro"], 1)
        self.assertEqual(counters["ignoradas"], 1)
        self.assertEqual(counters["total_lidas"], 5)


if __name__ == "__main__":
    unittest.main()

"""Testes para o comando review-adjustments e módulos de revisão manual.

Cobre os critérios de aceitação da US-PRJ-11:
  AC1 — status aprovado e rejeitado adicionados a STATUS_VALIDACAO
  AC2 — rastreabilidade preenchida automaticamente para aprovado/rejeitado
  AC3 — rejeição preserva registro com observacao_validacao opcional
  AC4 — campos originais preservados ao salvar
  AC5 — relatório de revisão e persistência atômica
  AC6 — id_registro obrigatório; review-adjustments aborta sem ele
"""

import json
import uuid
from dataclasses import replace
from io import StringIO
from pathlib import Path

import pytest

from src.models.reajuste_para_validacao import (
    STATUS_VALIDACAO,
    STATUS_VALIDACAO_INICIAL,
    ReajusteParaValidacao,
)
from src.services.manual_review import revisar_registros
from src.services.validation_store import carregar_para_validacao, salvar_para_validacao
from src.reports.manual_review import imprimir_relatorio_revisao


# ── helpers ───────────────────────────────────────────────────────────────────

def _registro(
    status: str = "sugerido_para_aprovacao",
    id_registro: str = None,
    responsavel: str = None,
    data_hora: str = None,
    observacao: str = None,
    percentual_corrigido: str = None,
) -> ReajusteParaValidacao:
    return ReajusteParaValidacao(
        caminho="CCT/SP/Sind/a.pdf",
        nome_arquivo="a.pdf",
        uf="SP",
        sindicato="Sind",
        tipo_documento="CCT",
        ano_referencia="2025-2026",
        tipo_clausula="reajuste_salarial",
        trecho_original="Reajuste de 5%.",
        percentual_reajuste="5%",
        data_base="2025-05-01",
        vigencia_inicio="2025-05-01",
        vigencia_fim="2026-04-30",
        status_extracao_estruturada="extraido_com_sucesso",
        status_validacao=status,
        observacao_validacao=observacao,
        responsavel_validacao=responsavel,
        data_hora_validacao=data_hora,
        percentual_reajuste_corrigido=percentual_corrigido,
        data_base_corrigida=None,
        vigencia_inicio_corrigida=None,
        vigencia_fim_corrigida=None,
        id_registro=id_registro or str(uuid.uuid4()),
    )


_TIMESTAMP = "2025-05-20T12:00:00+00:00"
_RESPONSAVEL = "joao.silva"


# ── AC1: STATUS_VALIDACAO inclui aprovado e rejeitado ────────────────────────

def test_ac1_aprovado_em_status_validacao():
    assert "aprovado" in STATUS_VALIDACAO


def test_ac1_rejeitado_em_status_validacao():
    assert "rejeitado" in STATUS_VALIDACAO


def test_ac1_status_iniciais_preservados():
    assert STATUS_VALIDACAO_INICIAL.issubset(STATUS_VALIDACAO)


def test_ac1_aprovado_rejeitado_nao_estao_em_status_iniciais():
    assert "aprovado" not in STATUS_VALIDACAO_INICIAL
    assert "rejeitado" not in STATUS_VALIDACAO_INICIAL


def test_ac1_status_invalido_levanta_valor_error():
    registros = [_registro(status="status_invalido_xyz")]
    with pytest.raises(ValueError, match="Status inválido"):
        revisar_registros(registros, _RESPONSAVEL, _TIMESTAMP)


def test_ac1_status_invalido_nao_grava_nada(tmp_path):
    """Nenhum arquivo deve ser escrito se a revisão abortar por status inválido."""
    registros = [_registro(status="invalido")]
    output = tmp_path / "out.json"
    with pytest.raises(ValueError):
        revisar_registros(registros, _RESPONSAVEL, _TIMESTAMP)
    assert not output.exists()


# ── AC2: rastreabilidade preenchida para aprovado/rejeitado ───────────────────

def test_ac2_aprovado_preenche_responsavel_e_data_hora():
    registros = [_registro(status="aprovado")]
    resultado = revisar_registros(registros, _RESPONSAVEL, _TIMESTAMP)
    assert resultado[0].responsavel_validacao == _RESPONSAVEL
    assert resultado[0].data_hora_validacao == _TIMESTAMP


def test_ac2_rejeitado_preenche_responsavel_e_data_hora():
    registros = [_registro(status="rejeitado")]
    resultado = revisar_registros(registros, _RESPONSAVEL, _TIMESTAMP)
    assert resultado[0].responsavel_validacao == _RESPONSAVEL
    assert resultado[0].data_hora_validacao == _TIMESTAMP


@pytest.mark.parametrize("status", list(STATUS_VALIDACAO_INICIAL))
def test_ac2_pre_revisao_nao_altera_auditoria(status):
    registros = [_registro(status=status, responsavel="antigo", data_hora="2020-01-01")]
    resultado = revisar_registros(registros, _RESPONSAVEL, _TIMESTAMP)
    assert resultado[0].responsavel_validacao == "antigo"
    assert resultado[0].data_hora_validacao == "2020-01-01"


def test_ac2_mistura_status_preenche_apenas_finais():
    registros = [
        _registro(status="aprovado"),
        _registro(status="pendente_revisao", responsavel=None, data_hora=None),
        _registro(status="rejeitado"),
    ]
    resultado = revisar_registros(registros, _RESPONSAVEL, _TIMESTAMP)
    assert resultado[0].responsavel_validacao == _RESPONSAVEL
    assert resultado[1].responsavel_validacao is None
    assert resultado[2].responsavel_validacao == _RESPONSAVEL


# ── AC3: rejeição preserva registro ──────────────────────────────────────────

def test_ac3_rejeitado_permanece_no_arquivo(tmp_path):
    registros = [
        _registro(status="aprovado"),
        _registro(status="rejeitado", observacao="Dados incorretos"),
    ]
    resultado = revisar_registros(registros, _RESPONSAVEL, _TIMESTAMP)
    output = tmp_path / "out.json"
    salvar_para_validacao(output, resultado)

    with output.open(encoding="utf-8") as f:
        dados = json.load(f)

    assert len(dados["reajustes"]) == 2
    status_set = {r["status_validacao"] for r in dados["reajustes"]}
    assert "rejeitado" in status_set


def test_ac3_observacao_validacao_preservada():
    registros = [_registro(status="rejeitado", observacao="Revisar sindicato")]
    resultado = revisar_registros(registros, _RESPONSAVEL, _TIMESTAMP)
    assert resultado[0].observacao_validacao == "Revisar sindicato"


def test_ac3_rejeitado_tem_responsavel_e_data_hora():
    registros = [_registro(status="rejeitado")]
    resultado = revisar_registros(registros, _RESPONSAVEL, _TIMESTAMP)
    assert resultado[0].responsavel_validacao == _RESPONSAVEL
    assert resultado[0].data_hora_validacao == _TIMESTAMP


# ── AC4: campos originais preservados ao salvar ───────────────────────────────

def test_ac4_campos_imutaveis_preservados_no_json(tmp_path):
    r = _registro(status="aprovado")
    resultado = revisar_registros([r], _RESPONSAVEL, _TIMESTAMP)
    output = tmp_path / "out.json"
    salvar_para_validacao(output, resultado)

    with output.open(encoding="utf-8") as f:
        dados = json.load(f)

    salvo = dados["reajustes"][0]
    assert salvo["percentual_reajuste"] == r.percentual_reajuste
    assert salvo["data_base"] == r.data_base
    assert salvo["vigencia_inicio"] == r.vigencia_inicio
    assert salvo["vigencia_fim"] == r.vigencia_fim
    assert salvo["trecho_original"] == r.trecho_original
    assert salvo["caminho"] == r.caminho
    assert salvo["nome_arquivo"] == r.nome_arquivo
    assert salvo["uf"] == r.uf
    assert salvo["sindicato"] == r.sindicato
    assert salvo["tipo_documento"] == r.tipo_documento
    assert salvo["ano_referencia"] == r.ano_referencia
    assert salvo["tipo_clausula"] == r.tipo_clausula
    assert salvo["id_registro"] == r.id_registro


def test_ac4_campo_corrigido_preservado_ao_salvar(tmp_path):
    r = _registro(status="aprovado", percentual_corrigido="6%")
    resultado = revisar_registros([r], _RESPONSAVEL, _TIMESTAMP)
    output = tmp_path / "out.json"
    salvar_para_validacao(output, resultado)

    with output.open(encoding="utf-8") as f:
        dados = json.load(f)

    assert dados["reajustes"][0]["percentual_reajuste_corrigido"] == "6%"


# ── AC5: relatório e persistência atômica ────────────────────────────────────

def test_ac5_escrita_atomica_sem_residuo(tmp_path):
    registros = [_registro(status="aprovado")]
    resultado = revisar_registros(registros, _RESPONSAVEL, _TIMESTAMP)
    output = tmp_path / "out.json"
    salvar_para_validacao(output, resultado)

    arquivos = list(tmp_path.iterdir())
    assert output in arquivos
    assert [f for f in arquivos if f.suffix == ".tmp"] == []


def test_ac5_relatorio_exibe_contadores(capsys):
    registros = [
        _registro(status="aprovado"),
        _registro(status="aprovado"),
        _registro(status="rejeitado"),
        _registro(status="pendente_revisao"),
        _registro(status="sugerido_para_aprovacao"),
        _registro(status="aprovado", percentual_corrigido="6%"),
    ]
    resultado = revisar_registros(registros, _RESPONSAVEL, _TIMESTAMP)
    imprimir_relatorio_revisao(resultado)

    captured = capsys.readouterr()
    assert "6" in captured.out   # total
    assert "3" in captured.out   # aprovados
    assert "1" in captured.out   # rejeitados
    assert "2" in captured.out   # pendentes
    assert "1" in captured.out   # com correção


def test_ac5_relatorio_exibe_rotulos(capsys):
    imprimir_relatorio_revisao([_registro(status="aprovado")])
    captured = capsys.readouterr()
    assert "aprovado" in captured.out.lower() or "aprovados" in captured.out.lower()
    assert "rejeitado" in captured.out.lower() or "rejeitados" in captured.out.lower()
    assert "pendente" in captured.out.lower() or "pendentes" in captured.out.lower()
    assert "corre" in captured.out.lower()  # "correção"


# ── AC6: id_registro obrigatório ─────────────────────────────────────────────

def test_ac6_registro_sem_id_levanta_valor_error():
    registros = [
        ReajusteParaValidacao(
            caminho="CCT/SP/Sind/a.pdf",
            nome_arquivo="a.pdf",
            uf="SP",
            sindicato="Sind",
            tipo_documento="CCT",
            ano_referencia="2025",
            tipo_clausula="reajuste_salarial",
            trecho_original="Texto",
            percentual_reajuste="5%",
            data_base=None,
            vigencia_inicio=None,
            vigencia_fim=None,
            status_extracao_estruturada="extraido_com_sucesso",
            status_validacao="aprovado",
            observacao_validacao=None,
            responsavel_validacao=None,
            data_hora_validacao=None,
            percentual_reajuste_corrigido=None,
            data_base_corrigida=None,
            vigencia_inicio_corrigida=None,
            vigencia_fim_corrigida=None,
            id_registro=None,  # ausente
        )
    ]
    with pytest.raises(ValueError, match="id_registro"):
        revisar_registros(registros, _RESPONSAVEL, _TIMESTAMP)


def test_ac6_registro_com_id_vazio_levanta_valor_error():
    r = _registro(status="aprovado", id_registro="   ")
    with pytest.raises(ValueError, match="id_registro"):
        revisar_registros([r], _RESPONSAVEL, _TIMESTAMP)


def test_ac6_mensagem_orienta_regenerar_arquivo():
    r = _registro(status="aprovado", id_registro=None)
    r = replace(r, id_registro=None)
    with pytest.raises(ValueError, match="validate-adjustments"):
        revisar_registros([r], _RESPONSAVEL, _TIMESTAMP)


def test_ac6_id_registro_serializado_e_desserializado(tmp_path):
    r = _registro(status="sugerido_para_aprovacao")
    output = tmp_path / "out.json"
    salvar_para_validacao(output, [r])

    carregados = carregar_para_validacao(output)
    assert carregados[0].id_registro == r.id_registro


def test_ac6_json_sem_id_carregado_com_none(tmp_path):
    """Arquivo legado sem id_registro deve ser carregado com id_registro=None."""
    dados = {
        "versao": 1,
        "data_geracao": "2025-01-01T00:00:00+00:00",
        "reajustes": [{
            "caminho": "CCT/SP/Sind/a.pdf",
            "nome_arquivo": "a.pdf",
            "uf": "SP",
            "sindicato": "Sind",
            "tipo_documento": "CCT",
            "ano_referencia": "2025",
            "tipo_clausula": "reajuste_salarial",
            "trecho_original": "Texto",
            "percentual_reajuste": "5%",
            "data_base": None,
            "vigencia_inicio": None,
            "vigencia_fim": None,
            "status_extracao_estruturada": "extraido_com_sucesso",
            "status_validacao": "sugerido_para_aprovacao",
            "observacao_validacao": None,
            "responsavel_validacao": None,
            "data_hora_validacao": None,
            "percentual_reajuste_corrigido": None,
            "data_base_corrigida": None,
            "vigencia_inicio_corrigida": None,
            "vigencia_fim_corrigida": None,
            # id_registro ausente intencionalmente
        }],
    }
    legacy_file = tmp_path / "legacy.json"
    legacy_file.write_text(json.dumps(dados), encoding="utf-8")

    carregados = carregar_para_validacao(legacy_file)
    assert carregados[0].id_registro is None


# ── integração via CLI ────────────────────────────────────────────────────────

def test_cli_review_arquivo_ausente_retorna_1(tmp_path):
    from src.cli import main
    codigo = main([
        "review-adjustments",
        "--input", str(tmp_path / "nao_existe.json"),
        "--output", str(tmp_path / "out.json"),
        "--responsavel", "op",
    ])
    assert codigo == 1


def test_cli_review_arquivo_ausente_mensagem_stderr(tmp_path, capsys):
    from src.cli import main
    main([
        "review-adjustments",
        "--input", str(tmp_path / "nao_existe.json"),
        "--output", str(tmp_path / "out.json"),
        "--responsavel", "op",
    ])
    captured = capsys.readouterr()
    assert "validate-adjustments" in captured.err


def test_cli_review_sem_id_retorna_1(tmp_path):
    from src.cli import main

    dados = {
        "versao": 1,
        "data_geracao": "2025-01-01T00:00:00+00:00",
        "reajustes": [{
            "caminho": "CCT/SP/Sind/a.pdf",
            "nome_arquivo": "a.pdf",
            "uf": "SP",
            "sindicato": "Sind",
            "tipo_documento": "CCT",
            "ano_referencia": "2025",
            "tipo_clausula": "reajuste_salarial",
            "trecho_original": "Texto",
            "percentual_reajuste": "5%",
            "data_base": None,
            "vigencia_inicio": None,
            "vigencia_fim": None,
            "status_extracao_estruturada": "extraido_com_sucesso",
            "status_validacao": "aprovado",
            "observacao_validacao": None,
            "responsavel_validacao": None,
            "data_hora_validacao": None,
            "percentual_reajuste_corrigido": None,
            "data_base_corrigida": None,
            "vigencia_inicio_corrigida": None,
            "vigencia_fim_corrigida": None,
        }],
    }
    input_file = tmp_path / "input.json"
    input_file.write_text(json.dumps(dados), encoding="utf-8")

    codigo = main([
        "review-adjustments",
        "--input", str(input_file),
        "--output", str(tmp_path / "out.json"),
        "--responsavel", "op",
    ])
    assert codigo == 1


def test_cli_review_status_invalido_retorna_1(tmp_path):
    from src.cli import main
    from src.services.validation_store import salvar_para_validacao
    from src.services.validation_preparer import preparar_para_validacao
    from src.models.reajuste_extraido import ReajusteExtraido

    r = ReajusteExtraido(
        caminho="CCT/SP/Sind/a.pdf",
        nome_arquivo="a.pdf",
        uf="SP",
        sindicato="Sind",
        tipo_documento="CCT",
        ano_referencia="2025",
        origem_texto="texto_nativo",
        tipo_clausula="reajuste_salarial",
        trecho_original="Texto",
        percentual_reajuste="5%",
        data_base=None,
        vigencia_inicio=None,
        vigencia_fim=None,
        status_extracao_estruturada="extraido_com_sucesso",
        metodo_extracao="regex",
        data_hora_processamento="2025-01-01T00:00:00+00:00",
    )
    registros = preparar_para_validacao([r])
    # forçar status inválido diretamente no JSON
    dados_dict = {
        "versao": 1,
        "data_geracao": "2025-01-01T00:00:00+00:00",
        "reajustes": [{
            "id_registro": registros[0].id_registro,
            "caminho": "CCT/SP/Sind/a.pdf",
            "nome_arquivo": "a.pdf",
            "uf": "SP",
            "sindicato": "Sind",
            "tipo_documento": "CCT",
            "ano_referencia": "2025",
            "tipo_clausula": "reajuste_salarial",
            "trecho_original": "Texto",
            "percentual_reajuste": "5%",
            "data_base": None,
            "vigencia_inicio": None,
            "vigencia_fim": None,
            "status_extracao_estruturada": "extraido_com_sucesso",
            "status_validacao": "status_completamente_invalido",
            "observacao_validacao": None,
            "responsavel_validacao": None,
            "data_hora_validacao": None,
            "percentual_reajuste_corrigido": None,
            "data_base_corrigida": None,
            "vigencia_inicio_corrigida": None,
            "vigencia_fim_corrigida": None,
        }],
    }
    input_file = tmp_path / "input.json"
    input_file.write_text(json.dumps(dados_dict), encoding="utf-8")

    codigo = main([
        "review-adjustments",
        "--input", str(input_file),
        "--output", str(tmp_path / "out.json"),
        "--responsavel", "op",
    ])
    assert codigo == 1


def test_cli_review_fluxo_completo(tmp_path):
    """Fluxo completo: validate-adjustments + edição manual + review-adjustments."""
    from src.cli import main
    from src.services.adjustment_store import salvar_reajustes
    from src.models.reajuste_extraido import ReajusteExtraido

    r = ReajusteExtraido(
        caminho="CCT/SP/Sind/a.pdf",
        nome_arquivo="a.pdf",
        uf="SP",
        sindicato="Sind",
        tipo_documento="CCT",
        ano_referencia="2025",
        origem_texto="texto_nativo",
        tipo_clausula="reajuste_salarial",
        trecho_original="Reajuste de 5%.",
        percentual_reajuste="5%",
        data_base="2025-05-01",
        vigencia_inicio="2025-05-01",
        vigencia_fim="2026-04-30",
        status_extracao_estruturada="extraido_com_sucesso",
        metodo_extracao="regex",
        data_hora_processamento="2025-01-01T00:00:00+00:00",
    )
    adj_file = tmp_path / "reajustes_extraidos.json"
    val_file = tmp_path / "reajustes_para_validacao.json"
    salvar_reajustes(adj_file, [r])

    # passo 1: validate-adjustments
    assert main([
        "validate-adjustments",
        "--input", str(adj_file),
        "--output", str(val_file),
    ]) == 0

    # simular edição manual: aprovar o registro
    with val_file.open(encoding="utf-8") as f:
        dados = json.load(f)
    dados["reajustes"][0]["status_validacao"] = "aprovado"
    val_file.write_text(json.dumps(dados), encoding="utf-8")

    # passo 2: review-adjustments
    assert main([
        "review-adjustments",
        "--input", str(val_file),
        "--output", str(val_file),
        "--responsavel", "joao.silva",
    ]) == 0

    with val_file.open(encoding="utf-8") as f:
        final = json.load(f)

    r_final = final["reajustes"][0]
    assert r_final["status_validacao"] == "aprovado"
    assert r_final["responsavel_validacao"] == "joao.silva"
    assert r_final["data_hora_validacao"] is not None
    # campos imutáveis preservados
    assert r_final["percentual_reajuste"] == "5%"
    assert r_final["id_registro"] is not None

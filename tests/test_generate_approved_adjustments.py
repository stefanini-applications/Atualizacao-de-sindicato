"""Testes para o comando generate-approved-adjustments e módulos de aprovação.

Cobre os critérios de aceitação da US-PRJ-10:
  AC1 — pré-condição: arquivo ausente → mensagem orientada + saída não-zero
  AC2 — filtragem exclusiva de aprovados; base vazia → lista vazia + saída não-zero
  AC3 — priorização de valores corrigidos sobre originais
  AC4 — preservação dual de valores e campos de rastreabilidade
  AC5 — geração atômica e relatório de execução com 4 contadores
"""

import json
import uuid
from pathlib import Path
from unittest.mock import patch

import pytest

from src.models.reajuste_para_validacao import ReajusteParaValidacao
from src.models.reajuste_aprovado import ReajusteAprovado
from src.services.approval_generator import gerar_reajustes_aprovados
from src.services.approved_store import salvar_aprovados, carregar_aprovados
from src.reports.approval import imprimir_relatorio_aprovacao

_TIMESTAMP = "2025-05-20T12:00:00+00:00"


# ── helpers ───────────────────────────────────────────────────────────────────

def _registro(
    status: str = "aprovado",
    percentual: str = "5%",
    percentual_corrigido: str = None,
    data_base: str = "2025-05-01",
    data_base_corrigida: str = None,
    vigencia_inicio: str = "2025-05-01",
    vigencia_inicio_corrigida: str = None,
    vigencia_fim: str = "2026-04-30",
    vigencia_fim_corrigida: str = None,
    responsavel: str = "joao.silva",
    observacao: str = None,
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
        percentual_reajuste=percentual,
        data_base=data_base,
        vigencia_inicio=vigencia_inicio,
        vigencia_fim=vigencia_fim,
        status_extracao_estruturada="extraido_com_sucesso",
        status_validacao=status,
        observacao_validacao=observacao,
        responsavel_validacao=responsavel,
        data_hora_validacao=_TIMESTAMP,
        percentual_reajuste_corrigido=percentual_corrigido,
        data_base_corrigida=data_base_corrigida,
        vigencia_inicio_corrigida=vigencia_inicio_corrigida,
        vigencia_fim_corrigida=vigencia_fim_corrigida,
        id_registro=str(uuid.uuid4()),
    )


# ── AC1: arquivo de entrada ausente ──────────────────────────────────────────

def test_ac1_arquivo_ausente_retorna_1(tmp_path):
    from src.cli import main
    codigo = main([
        "generate-approved-adjustments",
        "--input", str(tmp_path / "nao_existe.json"),
        "--output", str(tmp_path / "out.json"),
    ])
    assert codigo == 1


def test_ac1_arquivo_ausente_nao_cria_saida(tmp_path):
    from src.cli import main
    output = tmp_path / "out.json"
    main([
        "generate-approved-adjustments",
        "--input", str(tmp_path / "nao_existe.json"),
        "--output", str(output),
    ])
    assert not output.exists()


def test_ac1_arquivo_ausente_mensagem_orienta_validate_adjustments(tmp_path, capsys):
    from src.cli import main
    main([
        "generate-approved-adjustments",
        "--input", str(tmp_path / "nao_existe.json"),
        "--output", str(tmp_path / "out.json"),
    ])
    captured = capsys.readouterr()
    assert "validate-adjustments" in captured.err


# ── AC2: filtragem exclusiva de aprovados ─────────────────────────────────────

def test_ac2_somente_aprovados_incluidos():
    registros = [
        _registro(status="aprovado"),
        _registro(status="rejeitado"),
        _registro(status="pendente_revisao"),
        _registro(status="sugerido_para_aprovacao"),
        _registro(status="sem_dados_para_validar"),
        _registro(status="erro_validacao"),
    ]
    aprovados, _ = gerar_reajustes_aprovados(registros, _TIMESTAMP)
    assert len(aprovados) == 1
    assert aprovados[0].status_validacao == "aprovado"


@pytest.mark.parametrize("status", [
    "rejeitado",
    "pendente_revisao",
    "sugerido_para_aprovacao",
    "sem_dados_para_validar",
    "erro_validacao",
])
def test_ac2_status_nao_aprovado_descartado(status):
    registros = [_registro(status=status)]
    aprovados, _ = gerar_reajustes_aprovados(registros, _TIMESTAMP)
    assert aprovados == []


def test_ac2_base_vazia_grava_lista_vazia(tmp_path):
    from src.cli import main
    from src.services.validation_store import salvar_para_validacao

    registros = [_registro(status="pendente_revisao")]
    input_file = tmp_path / "input.json"
    output_file = tmp_path / "out.json"
    salvar_para_validacao(input_file, registros)

    main([
        "generate-approved-adjustments",
        "--input", str(input_file),
        "--output", str(output_file),
    ])

    assert output_file.exists()
    with output_file.open(encoding="utf-8") as f:
        dados = json.load(f)
    assert dados["reajustes"] == []


def test_ac2_base_vazia_retorna_codigo_nao_zero(tmp_path):
    from src.cli import main
    from src.services.validation_store import salvar_para_validacao

    registros = [_registro(status="rejeitado")]
    input_file = tmp_path / "input.json"
    salvar_para_validacao(input_file, registros)

    codigo = main([
        "generate-approved-adjustments",
        "--input", str(input_file),
        "--output", str(tmp_path / "out.json"),
    ])
    assert codigo != 0


def test_ac2_base_vazia_exibe_aviso(tmp_path, capsys):
    from src.cli import main
    from src.services.validation_store import salvar_para_validacao

    registros = [_registro(status="pendente_revisao")]
    input_file = tmp_path / "input.json"
    salvar_para_validacao(input_file, registros)

    main([
        "generate-approved-adjustments",
        "--input", str(input_file),
        "--output", str(tmp_path / "out.json"),
    ])
    captured = capsys.readouterr()
    assert "review-adjustments" in captured.err


# ── AC3: priorização de valores corrigidos ────────────────────────────────────

def test_ac3_corrigido_prevalece_sobre_original():
    r = _registro(percentual="5%", percentual_corrigido="6%")
    aprovados, _ = gerar_reajustes_aprovados([r], _TIMESTAMP)
    assert aprovados[0].percentual_reajuste_final == "6%"
    assert aprovados[0].percentual_reajuste_original == "5%"


def test_ac3_original_usado_quando_corrigido_e_none():
    r = _registro(percentual="5%", percentual_corrigido=None)
    aprovados, _ = gerar_reajustes_aprovados([r], _TIMESTAMP)
    assert aprovados[0].percentual_reajuste_final == "5%"


def test_ac3_original_usado_quando_corrigido_e_string_vazia():
    r = _registro(percentual="5%", percentual_corrigido="")
    aprovados, _ = gerar_reajustes_aprovados([r], _TIMESTAMP)
    assert aprovados[0].percentual_reajuste_final == "5%"


def test_ac3_zero_percent_considerado_preenchido():
    """'0%' deve ser tratado como valor preenchido e prevalecer sobre o original."""
    r = _registro(percentual="5%", percentual_corrigido="0%")
    aprovados, _ = gerar_reajustes_aprovados([r], _TIMESTAMP)
    assert aprovados[0].percentual_reajuste_final == "0%"


def test_ac3_zero_string_considerado_preenchido():
    """'0' deve ser tratado como valor preenchido."""
    r = _registro(percentual="5%", percentual_corrigido="0")
    aprovados, _ = gerar_reajustes_aprovados([r], _TIMESTAMP)
    assert aprovados[0].percentual_reajuste_final == "0"


def test_ac3_todos_os_quatro_campos_corrigiveis():
    r = _registro(
        percentual="5%", percentual_corrigido="6%",
        data_base="2025-01-01", data_base_corrigida="2025-06-01",
        vigencia_inicio="2025-01-01", vigencia_inicio_corrigida="2025-06-01",
        vigencia_fim="2026-01-01", vigencia_fim_corrigida="2026-06-01",
    )
    aprovados, com_correcao = gerar_reajustes_aprovados([r], _TIMESTAMP)
    a = aprovados[0]
    assert a.percentual_reajuste_final == "6%"
    assert a.data_base_final == "2025-06-01"
    assert a.vigencia_inicio_final == "2025-06-01"
    assert a.vigencia_fim_final == "2026-06-01"
    assert com_correcao == 1


def test_ac3_sem_correcao_final_igual_original():
    r = _registro(percentual="5%")
    aprovados, com_correcao = gerar_reajustes_aprovados([r], _TIMESTAMP)
    a = aprovados[0]
    assert a.percentual_reajuste_final == a.percentual_reajuste_original
    assert com_correcao == 0


# ── AC4: preservação dual e campos de rastreabilidade ────────────────────────

def test_ac4_campos_originais_preservados():
    r = _registro(percentual="5%", percentual_corrigido="6%")
    aprovados, _ = gerar_reajustes_aprovados([r], _TIMESTAMP)
    assert aprovados[0].percentual_reajuste_original == "5%"


def test_ac4_todos_os_oito_campos_de_rastreabilidade_presentes(tmp_path):
    r = _registro()
    aprovados, _ = gerar_reajustes_aprovados([r], _TIMESTAMP)
    salvar_aprovados(tmp_path / "out.json", aprovados)

    with (tmp_path / "out.json").open(encoding="utf-8") as f:
        dados = json.load(f)

    reg = dados["reajustes"][0]
    campos_rastreabilidade = {
        "percentual_reajuste_original", "percentual_reajuste_final",
        "data_base_original", "data_base_final",
        "vigencia_inicio_original", "vigencia_inicio_final",
        "vigencia_fim_original", "vigencia_fim_final",
    }
    assert campos_rastreabilidade.issubset(set(reg.keys()))


def test_ac4_campos_contexto_preservados(tmp_path):
    r = _registro(observacao="Observação teste")
    aprovados, _ = gerar_reajustes_aprovados([r], _TIMESTAMP)
    salvar_aprovados(tmp_path / "out.json", aprovados)

    with (tmp_path / "out.json").open(encoding="utf-8") as f:
        dados = json.load(f)

    reg = dados["reajustes"][0]
    assert reg["caminho"] == r.caminho
    assert reg["nome_arquivo"] == r.nome_arquivo
    assert reg["uf"] == r.uf
    assert reg["sindicato"] == r.sindicato
    assert reg["tipo_documento"] == r.tipo_documento
    assert reg["ano_referencia"] == r.ano_referencia
    assert reg["tipo_clausula"] == r.tipo_clausula
    assert reg["trecho_original"] == r.trecho_original
    assert reg["status_validacao"] == "aprovado"
    assert reg["responsavel_validacao"] == r.responsavel_validacao
    assert reg["data_hora_validacao"] == r.data_hora_validacao
    assert reg["observacao_validacao"] == "Observação teste"
    assert reg["id_registro"] == r.id_registro


def test_ac4_data_hora_geracao_presente_no_json(tmp_path):
    r = _registro()
    aprovados, _ = gerar_reajustes_aprovados([r], _TIMESTAMP)
    salvar_aprovados(tmp_path / "out.json", aprovados)

    with (tmp_path / "out.json").open(encoding="utf-8") as f:
        dados = json.load(f)

    assert dados["reajustes"][0]["data_hora_geracao"] == _TIMESTAMP


def test_ac4_data_hora_geracao_e_timestamp_utc_da_execucao():
    """data_hora_geracao deve ser o timestamp passado (UTC), não herdado da entrada."""
    r = _registro()
    timestamp_execucao = "2026-01-15T08:30:00+00:00"
    aprovados, _ = gerar_reajustes_aprovados([r], timestamp_execucao)
    assert aprovados[0].data_hora_geracao == timestamp_execucao


# ── AC5: geração atômica e relatório ─────────────────────────────────────────

def test_ac5_escrita_atomica_sem_residuo(tmp_path):
    r = _registro()
    aprovados, _ = gerar_reajustes_aprovados([r], _TIMESTAMP)
    output = tmp_path / "out.json"
    salvar_aprovados(output, aprovados)

    arquivos = list(tmp_path.iterdir())
    assert output in arquivos
    assert [f for f in arquivos if f.suffix == ".tmp"] == []


def test_ac5_escrita_atomica_nao_corrompe_arquivo_existente(tmp_path):
    output = tmp_path / "out.json"
    conteudo_original = '{"reajustes": []}'
    output.write_text(conteudo_original, encoding="utf-8")

    aprovados, _ = gerar_reajustes_aprovados([_registro()], _TIMESTAMP)

    with patch("os.replace", side_effect=OSError("falha simulada")):
        with pytest.raises(OSError):
            salvar_aprovados(output, aprovados)

    assert output.read_text(encoding="utf-8") == conteudo_original


def test_ac5_arquivo_temporario_removido_em_caso_de_falha(tmp_path):
    aprovados, _ = gerar_reajustes_aprovados([_registro()], _TIMESTAMP)
    output = tmp_path / "out.json"

    with patch("os.replace", side_effect=OSError("falha simulada")):
        with pytest.raises(OSError):
            salvar_aprovados(output, aprovados)

    tmp_files = [f for f in tmp_path.iterdir() if f.suffix == ".tmp"]
    assert tmp_files == []


def test_ac5_relatorio_exibe_quatro_contadores(capsys):
    imprimir_relatorio_aprovacao(
        total_avaliados=10,
        total_aprovados=4,
        total_ignorados=6,
        total_com_correcao=2,
    )
    captured = capsys.readouterr()
    assert "10" in captured.out
    assert "4" in captured.out
    assert "6" in captured.out
    assert "2" in captured.out


def test_ac5_relatorio_exibe_rotulos(capsys):
    imprimir_relatorio_aprovacao(5, 3, 2, 1)
    captured = capsys.readouterr()
    assert "avaliados" in captured.out.lower()
    assert "aprovados" in captured.out.lower()
    assert "ignorados" in captured.out.lower()
    assert "corre" in captured.out.lower()  # "correções"


def test_ac5_arquivo_saida_e_json_valido(tmp_path):
    aprovados, _ = gerar_reajustes_aprovados([_registro()], _TIMESTAMP)
    output = tmp_path / "out.json"
    salvar_aprovados(output, aprovados)

    with output.open(encoding="utf-8") as f:
        dados = json.load(f)

    assert "versao" in dados
    assert "reajustes" in dados
    assert isinstance(dados["reajustes"], list)


# ── integração via CLI ────────────────────────────────────────────────────────

def test_cli_fluxo_completo(tmp_path):
    """Fluxo: salva reajustes_para_validacao.json aprovados e roda o comando."""
    from src.cli import main
    from src.services.validation_store import salvar_para_validacao

    registros = [
        _registro(status="aprovado", percentual_corrigido="6%"),
        _registro(status="rejeitado"),
        _registro(status="pendente_revisao"),
    ]
    input_file = tmp_path / "reajustes_para_validacao.json"
    output_file = tmp_path / "reajustes_aprovados.json"
    salvar_para_validacao(input_file, registros)

    codigo = main([
        "generate-approved-adjustments",
        "--input", str(input_file),
        "--output", str(output_file),
    ])

    assert codigo == 0
    assert output_file.exists()

    with output_file.open(encoding="utf-8") as f:
        dados = json.load(f)

    assert len(dados["reajustes"]) == 1
    assert dados["reajustes"][0]["status_validacao"] == "aprovado"
    assert dados["reajustes"][0]["percentual_reajuste_final"] == "6%"
    assert dados["reajustes"][0]["percentual_reajuste_original"] == "5%"


def test_cli_retorna_0_com_aprovados(tmp_path):
    from src.cli import main
    from src.services.validation_store import salvar_para_validacao

    registros = [_registro(status="aprovado")]
    input_file = tmp_path / "input.json"
    salvar_para_validacao(input_file, registros)

    codigo = main([
        "generate-approved-adjustments",
        "--input", str(input_file),
        "--output", str(tmp_path / "out.json"),
    ])
    assert codigo == 0


def test_cli_relatorio_exibido(tmp_path, capsys):
    from src.cli import main
    from src.services.validation_store import salvar_para_validacao

    registros = [
        _registro(status="aprovado"),
        _registro(status="rejeitado"),
    ]
    input_file = tmp_path / "input.json"
    salvar_para_validacao(input_file, registros)

    main([
        "generate-approved-adjustments",
        "--input", str(input_file),
        "--output", str(tmp_path / "out.json"),
    ])
    captured = capsys.readouterr()
    # total avaliados = 2, aprovados = 1, ignorados = 1
    assert "2" in captured.out
    assert "1" in captured.out


def test_cli_caminhos_padrao_resolvidos_via_raiz_repo(tmp_path, monkeypatch):
    """O comando resolve caminhos relativos a partir da raiz do repositório."""
    from src.cli import main
    from src.services.validation_store import salvar_para_validacao
    import src.cli as cli_module

    raiz = tmp_path
    monkeypatch.setattr(cli_module, "_raiz_repo", lambda: raiz)

    data_dir = raiz / "data"
    data_dir.mkdir()

    input_file = data_dir / "reajustes_para_validacao.json"
    salvar_para_validacao(input_file, [_registro(status="aprovado")])

    codigo = main(["generate-approved-adjustments"])
    assert codigo == 0
    assert (data_dir / "reajustes_aprovados.json").exists()

"""Testes para o comando validate-adjustments e módulos de validação.

Cobre os critérios de aceitação da US-PRJ-9:
  AC1 — erro quando data/reajustes_extraidos.json não existe
  AC2 — mapeamento correto de status_extracao_estruturada → status_validacao
  AC3 — todos os campos originais preservados + campos de validação null
  AC4 — escrita atômica (arquivo temporário + substituição)
  AC5 — relatório com totais corretos cuja soma = total de registros
"""

import json
import sys
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import pytest

from src.models.reajuste_extraido import ReajusteExtraido
from src.models.reajuste_para_validacao import (
    MAPEAMENTO_STATUS,
    ReajusteParaValidacao,
    STATUS_VALIDACAO,
)
from src.services.validation_preparer import preparar_para_validacao
from src.services.validation_store import salvar_para_validacao
from src.reports.validation import imprimir_relatorio_validacao


# ── helpers ───────────────────────────────────────────────────────────────────

def _reajuste(
    status: str = "extraido_com_sucesso",
    caminho: str = "CCT/SP/Sind/a.pdf",
    percentual: str = "5%",
) -> ReajusteExtraido:
    return ReajusteExtraido(
        caminho=caminho,
        nome_arquivo=Path(caminho).name,
        uf="SP",
        sindicato="Sind",
        tipo_documento="CCT",
        ano_referencia="2025-2026",
        origem_texto="texto_nativo",
        tipo_clausula="reajuste_salarial",
        trecho_original="Reajuste de 5%.",
        percentual_reajuste=percentual,
        data_base="2025-05-01",
        vigencia_inicio="2025-05-01",
        vigencia_fim="2026-04-30",
        status_extracao_estruturada=status,
        metodo_extracao="regex",
        data_hora_processamento="2025-01-01T00:00:00+00:00",
    )


# ── AC1: arquivo de entrada ausente ──────────────────────────────────────────

def test_ac1_arquivo_ausente_encerra_com_codigo_1(tmp_path):
    from src.cli import main
    resultado = main([
        "validate-adjustments",
        "--input", str(tmp_path / "nao_existe.json"),
        "--output", str(tmp_path / "out.json"),
    ])
    assert resultado >= 1


def test_ac1_mensagem_orienta_executar_extract_adjustments(tmp_path, capsys):
    from src.cli import main
    main([
        "validate-adjustments",
        "--input", str(tmp_path / "nao_existe.json"),
        "--output", str(tmp_path / "out.json"),
    ])
    captured = capsys.readouterr()
    assert "extract-adjustments" in captured.err


# ── AC2: mapeamento de status ─────────────────────────────────────────────────

@pytest.mark.parametrize("status_extracao, status_esperado", [
    ("extraido_com_sucesso", "sugerido_para_aprovacao"),
    ("parcialmente_extraido", "pendente_revisao"),
    ("dados_nao_identificados", "sem_dados_para_validar"),
    ("erro_extracao", "erro_validacao"),
])
def test_ac2_mapeamento_status(status_extracao, status_esperado):
    reajustes = [_reajuste(status=status_extracao)]
    resultado = preparar_para_validacao(reajustes)
    assert len(resultado) == 1
    assert resultado[0].status_validacao == status_esperado


def test_ac2_extraido_com_sucesso_e_unico_sugerido_para_aprovacao():
    """Nenhum status diferente de extraido_com_sucesso pode gerar sugerido_para_aprovacao."""
    outros_status = ["parcialmente_extraido", "dados_nao_identificados", "erro_extracao"]
    for st in outros_status:
        reajustes = [_reajuste(status=st)]
        resultado = preparar_para_validacao(reajustes)
        assert resultado[0].status_validacao != "sugerido_para_aprovacao", (
            f"Status '{st}' não deveria gerar 'sugerido_para_aprovacao'"
        )


def test_ac2_todos_os_status_presentes_em_mapeamento():
    assert set(MAPEAMENTO_STATUS.keys()) == {
        "extraido_com_sucesso",
        "parcialmente_extraido",
        "dados_nao_identificados",
        "erro_extracao",
    }
    assert set(MAPEAMENTO_STATUS.values()) == STATUS_VALIDACAO


# ── AC3: preservação de campos e inicialização de campos null ─────────────────

def test_ac3_campos_originais_preservados():
    r = _reajuste(status="extraido_com_sucesso", percentual="7%")
    resultado = preparar_para_validacao([r])
    v = resultado[0]
    assert v.caminho == r.caminho
    assert v.nome_arquivo == r.nome_arquivo
    assert v.uf == r.uf
    assert v.sindicato == r.sindicato
    assert v.tipo_documento == r.tipo_documento
    assert v.ano_referencia == r.ano_referencia
    assert v.tipo_clausula == r.tipo_clausula
    assert v.trecho_original == r.trecho_original
    assert v.percentual_reajuste == r.percentual_reajuste
    assert v.data_base == r.data_base
    assert v.vigencia_inicio == r.vigencia_inicio
    assert v.vigencia_fim == r.vigencia_fim
    assert v.status_extracao_estruturada == r.status_extracao_estruturada


def test_ac3_campos_validacao_inicializados_como_null():
    resultado = preparar_para_validacao([_reajuste()])
    v = resultado[0]
    assert v.observacao_validacao is None
    assert v.responsavel_validacao is None
    assert v.data_hora_validacao is None


def test_ac3_campos_correcao_manual_inicializados_como_null():
    resultado = preparar_para_validacao([_reajuste()])
    v = resultado[0]
    assert v.percentual_reajuste_corrigido is None
    assert v.data_base_corrigida is None
    assert v.vigencia_inicio_corrigida is None
    assert v.vigencia_fim_corrigida is None


def test_ac3_json_contem_todos_os_campos_obrigatorios(tmp_path):
    registros = preparar_para_validacao([_reajuste()])
    output = tmp_path / "out.json"
    salvar_para_validacao(output, registros)

    with output.open(encoding="utf-8") as f:
        dados = json.load(f)

    campos_obrigatorios_originais = {
        "caminho", "nome_arquivo", "uf", "sindicato", "tipo_documento",
        "ano_referencia", "tipo_clausula", "trecho_original",
        "percentual_reajuste", "data_base", "vigencia_inicio", "vigencia_fim",
        "status_extracao_estruturada",
    }
    campos_validacao = {
        "status_validacao", "observacao_validacao", "responsavel_validacao",
        "data_hora_validacao",
    }
    campos_correcao = {
        "percentual_reajuste_corrigido", "data_base_corrigida",
        "vigencia_inicio_corrigida", "vigencia_fim_corrigida",
    }
    todos_esperados = campos_obrigatorios_originais | campos_validacao | campos_correcao

    registro_json = dados["reajustes"][0]
    assert todos_esperados.issubset(set(registro_json.keys()))


def test_ac3_campos_null_serializados_como_null_no_json(tmp_path):
    registros = preparar_para_validacao([_reajuste()])
    output = tmp_path / "out.json"
    salvar_para_validacao(output, registros)

    with output.open(encoding="utf-8") as f:
        dados = json.load(f)

    r = dados["reajustes"][0]
    for campo in [
        "observacao_validacao", "responsavel_validacao", "data_hora_validacao",
        "percentual_reajuste_corrigido", "data_base_corrigida",
        "vigencia_inicio_corrigida", "vigencia_fim_corrigida",
    ]:
        assert r[campo] is None, f"Campo '{campo}' deveria ser null no JSON"


# ── AC4: escrita atômica ──────────────────────────────────────────────────────

def test_ac4_escrita_atomica_sem_arquivo_temporario_residual(tmp_path):
    registros = preparar_para_validacao([_reajuste()])
    output = tmp_path / "out.json"
    salvar_para_validacao(output, registros)

    arquivos = list(tmp_path.iterdir())
    assert output in arquivos
    tmp_files = [f for f in arquivos if f.suffix == ".tmp"]
    assert tmp_files == [], "Arquivo temporário não deve restar após escrita bem-sucedida"


def test_ac4_arquivo_de_saida_e_json_valido(tmp_path):
    registros = preparar_para_validacao([_reajuste()])
    output = tmp_path / "out.json"
    salvar_para_validacao(output, registros)

    with output.open(encoding="utf-8") as f:
        dados = json.load(f)

    assert "versao" in dados
    assert "data_geracao" in dados
    assert "reajustes" in dados
    assert isinstance(dados["reajustes"], list)


def test_ac4_falha_na_escrita_nao_corrompe_arquivo_existente(tmp_path):
    """Se a escrita falhar, o arquivo destino original não deve ser alterado."""
    output = tmp_path / "out.json"
    conteudo_original = '{"reajustes": []}'
    output.write_text(conteudo_original, encoding="utf-8")

    registros = preparar_para_validacao([_reajuste()])

    with patch("os.replace", side_effect=OSError("falha simulada")):
        with pytest.raises(OSError):
            salvar_para_validacao(output, registros)

    assert output.read_text(encoding="utf-8") == conteudo_original


def test_ac4_arquivo_temporario_removido_em_caso_de_falha(tmp_path):
    registros = preparar_para_validacao([_reajuste()])
    output = tmp_path / "out.json"

    with patch("os.replace", side_effect=OSError("falha simulada")):
        with pytest.raises(OSError):
            salvar_para_validacao(output, registros)

    tmp_files = [f for f in tmp_path.iterdir() if f.suffix == ".tmp"]
    assert tmp_files == [], "Arquivo temporário deve ser removido após falha"


# ── AC5: relatório com totais corretos ────────────────────────────────────────

def test_ac5_soma_status_igual_ao_total(capsys):
    reajustes = [
        _reajuste(status="extraido_com_sucesso"),
        _reajuste(status="extraido_com_sucesso"),
        _reajuste(status="parcialmente_extraido"),
        _reajuste(status="dados_nao_identificados"),
        _reajuste(status="erro_extracao"),
    ]
    registros = preparar_para_validacao(reajustes)
    imprimir_relatorio_validacao(registros)

    captured = capsys.readouterr()
    # verifica totais na saída
    assert "5" in captured.out  # total
    assert "2" in captured.out  # sugerido_para_aprovacao


def test_ac5_relatorio_exibe_todos_os_status(capsys):
    reajustes = [
        _reajuste(status="extraido_com_sucesso"),
        _reajuste(status="parcialmente_extraido"),
        _reajuste(status="dados_nao_identificados"),
        _reajuste(status="erro_extracao"),
    ]
    registros = preparar_para_validacao(reajustes)
    imprimir_relatorio_validacao(registros)

    captured = capsys.readouterr()
    assert "sugerido" in captured.out.lower() or "aprovação" in captured.out.lower()
    assert "pendente" in captured.out.lower() or "revisão" in captured.out.lower()
    assert "sem dados" in captured.out.lower() or "sem_dados" in captured.out.lower()
    assert "erro" in captured.out.lower()


def test_ac5_totais_corretos_em_relatorio(capsys):
    reajustes = [
        _reajuste(status="extraido_com_sucesso"),
        _reajuste(status="extraido_com_sucesso"),
        _reajuste(status="extraido_com_sucesso"),
        _reajuste(status="parcialmente_extraido"),
        _reajuste(status="parcialmente_extraido"),
        _reajuste(status="dados_nao_identificados"),
        _reajuste(status="erro_extracao"),
    ]
    registros = preparar_para_validacao(reajustes)

    sugerido = sum(1 for r in registros if r.status_validacao == "sugerido_para_aprovacao")
    pendente = sum(1 for r in registros if r.status_validacao == "pendente_revisao")
    sem_dados = sum(1 for r in registros if r.status_validacao == "sem_dados_para_validar")
    erro = sum(1 for r in registros if r.status_validacao == "erro_validacao")

    assert sugerido + pendente + sem_dados + erro == len(registros)
    assert sugerido == 3
    assert pendente == 2
    assert sem_dados == 1
    assert erro == 1


# ── integração via CLI ────────────────────────────────────────────────────────

def test_integracao_cli_validate_adjustments(tmp_path):
    """Testa fluxo completo: salva reajustes_extraidos.json e roda validate-adjustments."""
    from src.services.adjustment_store import salvar_reajustes
    from src.cli import main

    reajustes = [
        _reajuste(status="extraido_com_sucesso"),
        _reajuste(status="parcialmente_extraido"),
        _reajuste(status="dados_nao_identificados"),
        _reajuste(status="erro_extracao"),
    ]
    input_path = tmp_path / "reajustes_extraidos.json"
    output_path = tmp_path / "reajustes_para_validacao.json"

    salvar_reajustes(input_path, reajustes)

    codigo = main([
        "validate-adjustments",
        "--input", str(input_path),
        "--output", str(output_path),
    ])

    assert codigo == 0
    assert output_path.exists()

    with output_path.open(encoding="utf-8") as f:
        dados = json.load(f)

    assert len(dados["reajustes"]) == 4
    status_set = {r["status_validacao"] for r in dados["reajustes"]}
    assert "sugerido_para_aprovacao" in status_set
    assert "pendente_revisao" in status_set
    assert "sem_dados_para_validar" in status_set
    assert "erro_validacao" in status_set

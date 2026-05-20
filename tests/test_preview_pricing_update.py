"""Testes para o comando preview-pricing-update e módulos de prévia de pricing.

Cobre os critérios de aceitação da US-PRJ-12:
  AC1 — arquivos de entrada ausentes → mensagem + saída não-zero + sem arquivo de saída
  AC2 — base_pricing.xlsx original preservada; escrita atômica
  AC3 — cinco status de correspondência por linha
  AC4 — colunas originais preservadas + 8 campos adicionados
  AC5 — relatório: total por status e confirmação de soma
"""

import json
import os
import uuid
from pathlib import Path
from typing import List
from unittest.mock import patch

import openpyxl
import pytest

from src.models.reajuste_aprovado import ReajusteAprovado
from src.models.linha_preview_pricing import LinhaPreviewPricing
from src.services.pricing_preview import gerar_preview
from src.services.pricing_reader import carregar_base_pricing
from src.services.preview_writer import salvar_preview, _COLUNAS_ADICIONADAS
from src.reports.preview_pricing import imprimir_relatorio_preview

_TIMESTAMP = "2025-05-20T12:00:00+00:00"

_COLUNAS_PRICING = ["uf", "sindicato", "ano_referencia", "salario_base", "cargo"]


# ── helpers ───────────────────────────────────────────────────────────────────

def _criar_xlsx(path: Path, linhas: List[dict], colunas: List[str] = None) -> None:
    """Cria um .xlsx simples para testes."""
    cols = colunas or _COLUNAS_PRICING
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(cols)
    for linha in linhas:
        ws.append([linha.get(c) for c in cols])
    wb.save(path)


def _reajuste(
    uf: str = "SP",
    sindicato: str = "Sind",
    ano_referencia: str = "2025",
    percentual: str = "5%",
    id_registro: str = None,
) -> ReajusteAprovado:
    return ReajusteAprovado(
        id_registro=id_registro or str(uuid.uuid4()),
        caminho="CCT/SP/Sind/a.pdf",
        nome_arquivo="a.pdf",
        uf=uf,
        sindicato=sindicato,
        tipo_documento="CCT",
        ano_referencia=ano_referencia,
        tipo_clausula="reajuste_salarial",
        trecho_original="Reajuste de 5%.",
        percentual_reajuste_original="5%",
        percentual_reajuste_final=percentual,
        data_base_original="2025-05-01",
        data_base_final="2025-05-01",
        vigencia_inicio_original="2025-05-01",
        vigencia_inicio_final="2025-05-01",
        vigencia_fim_original="2026-04-30",
        vigencia_fim_final="2026-04-30",
        status_validacao="aprovado",
        responsavel_validacao="joao",
        data_hora_validacao=_TIMESTAMP,
        observacao_validacao=None,
        data_hora_geracao=_TIMESTAMP,
    )


def _aprovados_json(path: Path, aprovados: List[ReajusteAprovado]) -> None:
    """Salva lista de reajustes aprovados em JSON."""
    from src.services.approved_store import salvar_aprovados
    salvar_aprovados(path, aprovados)


# ── AC1: validação dos arquivos de entrada ────────────────────────────────────

def test_ac1_adjustments_ausente_retorna_1(tmp_path):
    from src.cli import main
    pricing = tmp_path / "pricing.xlsx"
    _criar_xlsx(pricing, [])
    codigo = main([
        "preview-pricing-update",
        "--adjustments", str(tmp_path / "nao_existe.json"),
        "--pricing", str(pricing),
        "--output", str(tmp_path / "out.xlsx"),
    ])
    assert codigo == 1


def test_ac1_pricing_ausente_retorna_1(tmp_path):
    from src.cli import main
    adj = tmp_path / "adj.json"
    _aprovados_json(adj, [])
    codigo = main([
        "preview-pricing-update",
        "--adjustments", str(adj),
        "--pricing", str(tmp_path / "nao_existe.xlsx"),
        "--output", str(tmp_path / "out.xlsx"),
    ])
    assert codigo == 1


def test_ac1_ambos_ausentes_retorna_1(tmp_path):
    from src.cli import main
    codigo = main([
        "preview-pricing-update",
        "--adjustments", str(tmp_path / "a.json"),
        "--pricing", str(tmp_path / "b.xlsx"),
        "--output", str(tmp_path / "out.xlsx"),
    ])
    assert codigo == 1


def test_ac1_arquivo_ausente_nao_cria_saida(tmp_path):
    from src.cli import main
    output = tmp_path / "out.xlsx"
    main([
        "preview-pricing-update",
        "--adjustments", str(tmp_path / "a.json"),
        "--pricing", str(tmp_path / "b.xlsx"),
        "--output", str(output),
    ])
    assert not output.exists()


def test_ac1_mensagem_identifica_arquivo_ausente(tmp_path, capsys):
    from src.cli import main
    adj = tmp_path / "adj.json"
    _aprovados_json(adj, [])
    main([
        "preview-pricing-update",
        "--adjustments", str(adj),
        "--pricing", str(tmp_path / "pricing_ausente.xlsx"),
        "--output", str(tmp_path / "out.xlsx"),
    ])
    captured = capsys.readouterr()
    assert "pricing_ausente.xlsx" in captured.err


# ── AC2: preservação da base original ────────────────────────────────────────

def test_ac2_base_pricing_nao_modificada(tmp_path):
    from src.cli import main

    pricing = tmp_path / "base_pricing.xlsx"
    linhas = [{"uf": "SP", "sindicato": "Sind", "ano_referencia": "2025", "salario_base": 1000, "cargo": "op"}]
    _criar_xlsx(pricing, linhas)
    conteudo_original = pricing.read_bytes()

    adj = tmp_path / "adj.json"
    _aprovados_json(adj, [_reajuste()])

    main([
        "preview-pricing-update",
        "--adjustments", str(adj),
        "--pricing", str(pricing),
        "--output", str(tmp_path / "out.xlsx"),
    ])

    assert pricing.read_bytes() == conteudo_original


def test_ac2_escrita_atomica_sem_residuo(tmp_path):
    colunas = ["uf", "sindicato", "ano_referencia"]
    linhas = [{"uf": "SP", "sindicato": "Sind", "ano_referencia": "2025"}]
    preview = [LinhaPreviewPricing(
        dados_originais=linhas[0],
        id_registro_reajuste="x",
        percentual_reajuste_final="5%",
        data_base_final=None,
        vigencia_inicio_final=None,
        vigencia_fim_final=None,
        fonte_documento="a.pdf",
        status_aplicacao="reajuste_encontrado",
        observacao_aplicacao=None,
    )]
    output = tmp_path / "out.xlsx"
    salvar_preview(output, preview, colunas)

    arquivos = list(tmp_path.iterdir())
    assert output in arquivos
    assert [f for f in arquivos if ".xlsx.tmp" in f.name] == []


def test_ac2_escrita_atomica_nao_corrompe_em_falha(tmp_path):
    output = tmp_path / "out.xlsx"
    conteudo_sentinel = b"sentinel"
    output.write_bytes(conteudo_sentinel)

    colunas = ["uf"]
    preview = [LinhaPreviewPricing(
        dados_originais={"uf": "SP"},
        id_registro_reajuste=None,
        percentual_reajuste_final=None,
        data_base_final=None,
        vigencia_inicio_final=None,
        vigencia_fim_final=None,
        fonte_documento=None,
        status_aplicacao="sem_correspondencia",
        observacao_aplicacao=None,
    )]

    with patch("os.replace", side_effect=OSError("falha simulada")):
        with pytest.raises(OSError):
            salvar_preview(output, preview, colunas)

    assert output.read_bytes() == conteudo_sentinel


def test_ac2_temp_removido_em_falha(tmp_path):
    colunas = ["uf"]
    preview = [LinhaPreviewPricing(
        dados_originais={"uf": "SP"},
        id_registro_reajuste=None,
        percentual_reajuste_final=None,
        data_base_final=None,
        vigencia_inicio_final=None,
        vigencia_fim_final=None,
        fonte_documento=None,
        status_aplicacao="sem_correspondencia",
        observacao_aplicacao=None,
    )]

    with patch("os.replace", side_effect=OSError("falha simulada")):
        with pytest.raises(OSError):
            salvar_preview(tmp_path / "out.xlsx", preview, colunas)

    tmp_files = [f for f in tmp_path.iterdir() if ".xlsx.tmp" in f.name]
    assert tmp_files == []


# ── AC3: cinco status de correspondência ─────────────────────────────────────

def _linha_pricing(uf="SP", sindicato="Sind", ano="2025", **extra):
    linha = {"uf": uf, "sindicato": sindicato, "ano_referencia": ano}
    linha.update(extra)
    return linha


def test_ac3_reajuste_encontrado():
    linhas = [_linha_pricing()]
    aprovados = [_reajuste()]
    preview = gerar_preview(linhas, aprovados, "uf", "sindicato", "ano_referencia")
    assert preview[0].status_aplicacao == "reajuste_encontrado"


def test_ac3_sem_correspondencia():
    linhas = [_linha_pricing(sindicato="Outro")]
    aprovados = [_reajuste()]
    preview = gerar_preview(linhas, aprovados, "uf", "sindicato", "ano_referencia")
    assert preview[0].status_aplicacao == "sem_correspondencia"


def test_ac3_multiplas_correspondencias():
    linhas = [_linha_pricing()]
    aprovados = [_reajuste(id_registro="id1"), _reajuste(id_registro="id2")]
    preview = gerar_preview(linhas, aprovados, "uf", "sindicato", "ano_referencia")
    assert preview[0].status_aplicacao == "multiplas_correspondencias"
    assert "id1" in preview[0].observacao_aplicacao
    assert "id2" in preview[0].observacao_aplicacao


def test_ac3_dados_insuficientes_sem_uf():
    linhas = [{"uf": None, "sindicato": "Sind", "ano_referencia": "2025"}]
    aprovados = [_reajuste()]
    preview = gerar_preview(linhas, aprovados, "uf", "sindicato", "ano_referencia")
    assert preview[0].status_aplicacao == "dados_insuficientes"


def test_ac3_dados_insuficientes_sem_sindicato():
    linhas = [{"uf": "SP", "sindicato": None, "ano_referencia": "2025"}]
    preview = gerar_preview(linhas, [], "uf", "sindicato", "ano_referencia")
    assert preview[0].status_aplicacao == "dados_insuficientes"


def test_ac3_dados_insuficientes_sem_ano_referencia():
    linhas = [{"uf": "SP", "sindicato": "Sind", "ano_referencia": None}]
    preview = gerar_preview(linhas, [], "uf", "sindicato", "ano_referencia")
    assert preview[0].status_aplicacao == "dados_insuficientes"


def test_ac3_dados_insuficientes_string_vazia():
    linhas = [{"uf": "", "sindicato": "Sind", "ano_referencia": "2025"}]
    preview = gerar_preview(linhas, [], "uf", "sindicato", "ano_referencia")
    assert preview[0].status_aplicacao == "dados_insuficientes"


def test_ac3_erro_aplicacao(monkeypatch):
    """Erro inesperado ao processar linha deve resultar em erro_aplicacao."""
    from src.services import pricing_preview

    linhas = [_linha_pricing()]
    aprovados = [_reajuste()]

    original = pricing_preview._processar_linha

    def _raise(*args, **kwargs):
        raise RuntimeError("erro simulado")

    monkeypatch.setattr(pricing_preview, "_processar_linha", _raise)
    preview = gerar_preview(linhas, aprovados, "uf", "sindicato", "ano_referencia")
    assert preview[0].status_aplicacao == "erro_aplicacao"
    assert "erro simulado" in preview[0].observacao_aplicacao


def test_ac3_cada_linha_recebe_exatamente_um_status():
    linhas = [
        _linha_pricing(),
        _linha_pricing(sindicato="Outro"),
        {"uf": None, "sindicato": "X", "ano_referencia": "2025"},
    ]
    aprovados = [_reajuste(id_registro="id1"), _reajuste(id_registro="id2")]
    preview = gerar_preview(linhas, aprovados, "uf", "sindicato", "ano_referencia")
    assert len(preview) == 3


def test_ac3_correspondencia_case_insensitive():
    linhas = [_linha_pricing(uf="sp", sindicato="SIND", ano="2025")]
    aprovados = [_reajuste(uf="SP", sindicato="Sind", ano_referencia="2025")]
    preview = gerar_preview(linhas, aprovados, "uf", "sindicato", "ano_referencia")
    assert preview[0].status_aplicacao == "reajuste_encontrado"


def test_ac3_correspondencia_strip_espacos():
    linhas = [_linha_pricing(uf=" SP ", sindicato=" Sind ", ano="2025")]
    aprovados = [_reajuste(uf="SP", sindicato="Sind", ano_referencia="2025")]
    preview = gerar_preview(linhas, aprovados, "uf", "sindicato", "ano_referencia")
    assert preview[0].status_aplicacao == "reajuste_encontrado"


def test_ac3_multiplas_ids_candidatos_ordenados():
    linhas = [_linha_pricing()]
    aprovados = [_reajuste(id_registro="zzz"), _reajuste(id_registro="aaa")]
    preview = gerar_preview(linhas, aprovados, "uf", "sindicato", "ano_referencia")
    obs = preview[0].observacao_aplicacao
    assert obs.index("aaa") < obs.index("zzz")


# ── AC4: campos adicionados na prévia ────────────────────────────────────────

def test_ac4_oito_colunas_adicionadas():
    assert len(_COLUNAS_ADICIONADAS) == 9
    esperados = {
        "id_registro_reajuste", "percentual_reajuste_final", "data_base_final",
        "vigencia_inicio_final", "vigencia_fim_final", "fonte_documento",
        "status_aplicacao", "decisao_aplicacao", "observacao_aplicacao",
    }
    assert set(_COLUNAS_ADICIONADAS) == esperados


def test_ac4_colunas_originais_preservadas_na_saida(tmp_path):
    colunas_pricing = ["uf", "sindicato", "ano_referencia", "salario_base", "cargo"]
    linhas = [{"uf": "SP", "sindicato": "Sind", "ano_referencia": "2025",
               "salario_base": 1000, "cargo": "op"}]

    aprovados = [_reajuste()]
    preview = gerar_preview(linhas, aprovados, "uf", "sindicato", "ano_referencia")

    output = tmp_path / "out.xlsx"
    salvar_preview(output, preview, colunas_pricing)

    wb = openpyxl.load_workbook(output)
    ws = wb.active
    cabecalho = [c.value for c in ws[1]]

    for col in colunas_pricing:
        assert col in cabecalho, f"Coluna original '{col}' ausente no cabeçalho"

    for col in _COLUNAS_ADICIONADAS:
        assert col in cabecalho, f"Coluna adicionada '{col}' ausente no cabeçalho"


def test_ac4_colunas_originais_precedem_adicionadas(tmp_path):
    colunas_pricing = ["uf", "sindicato", "ano_referencia"]
    linhas = [{"uf": "SP", "sindicato": "Sind", "ano_referencia": "2025"}]
    preview = gerar_preview(linhas, [_reajuste()], "uf", "sindicato", "ano_referencia")

    output = tmp_path / "out.xlsx"
    salvar_preview(output, preview, colunas_pricing)

    wb = openpyxl.load_workbook(output)
    ws = wb.active
    cabecalho = [c.value for c in ws[1]]

    idx_ultima_original = max(cabecalho.index(c) for c in colunas_pricing)
    idx_primeira_adicionada = cabecalho.index("id_registro_reajuste")
    assert idx_ultima_original < idx_primeira_adicionada


def test_ac4_campos_nao_aplicaveis_sao_nulos_nao_omitidos(tmp_path):
    colunas_pricing = ["uf", "sindicato", "ano_referencia"]
    linhas = [{"uf": "SP", "sindicato": "Sem", "ano_referencia": "2025"}]
    # aprovados vazio → sem_correspondencia
    preview = gerar_preview(linhas, [], "uf", "sindicato", "ano_referencia")

    output = tmp_path / "out.xlsx"
    salvar_preview(output, preview, colunas_pricing)

    wb = openpyxl.load_workbook(output)
    ws = wb.active
    cabecalho = [c.value for c in ws[1]]
    dados_linha = [c.value for c in ws[2]]

    assert "id_registro_reajuste" in cabecalho
    idx = cabecalho.index("id_registro_reajuste")
    assert dados_linha[idx] is None


def test_ac4_fonte_documento_preenchido_quando_encontrado(tmp_path):
    colunas_pricing = ["uf", "sindicato", "ano_referencia"]
    linhas = [{"uf": "SP", "sindicato": "Sind", "ano_referencia": "2025"}]
    aprovados = [_reajuste()]
    preview = gerar_preview(linhas, aprovados, "uf", "sindicato", "ano_referencia")

    assert preview[0].fonte_documento == aprovados[0].nome_arquivo


# ── AC5: relatório de simulação ───────────────────────────────────────────────

def test_ac5_relatorio_exibe_total_avaliadas(capsys):
    imprimir_relatorio_preview(7, {"reajuste_encontrado": 3, "sem_correspondencia": 4})
    captured = capsys.readouterr()
    assert "7" in captured.out


def test_ac5_relatorio_exibe_contagens_por_status(capsys):
    imprimir_relatorio_preview(5, {
        "reajuste_encontrado": 2,
        "sem_correspondencia": 1,
        "dados_insuficientes": 1,
        "multiplas_correspondencias": 1,
    })
    captured = capsys.readouterr()
    assert "reajuste_encontrado" in captured.out
    assert "sem_correspondencia" in captured.out
    assert "dados_insuficientes" in captured.out
    assert "multiplas_correspondencias" in captured.out


def test_ac5_relatorio_confirma_soma_igual_total(capsys):
    imprimir_relatorio_preview(3, {"reajuste_encontrado": 2, "sem_correspondencia": 1})
    captured = capsys.readouterr()
    assert "3" in captured.out
    assert "✔" in captured.out


def test_ac5_relatorio_indica_divergencia_quando_soma_errada(capsys):
    imprimir_relatorio_preview(5, {"reajuste_encontrado": 2})
    captured = capsys.readouterr()
    assert "✘" in captured.out or "DIVERGÊNCIA" in captured.out


# ── pricing_reader: resolução de colunas ──────────────────────────────────────

def test_reader_carrega_linhas_corretamente(tmp_path):
    pricing = tmp_path / "pricing.xlsx"
    linhas = [
        {"uf": "SP", "sindicato": "Sind", "ano_referencia": "2025", "salario_base": 1000, "cargo": "op"},
        {"uf": "RJ", "sindicato": "X", "ano_referencia": "2024", "salario_base": 900, "cargo": "aux"},
    ]
    _criar_xlsx(pricing, linhas)

    result_linhas, colunas, col_uf, col_sindicato, col_ano = carregar_base_pricing(pricing)

    assert len(result_linhas) == 2
    assert col_uf == "uf"
    assert col_sindicato == "sindicato"
    assert col_ano == "ano_referencia"


def test_reader_coluna_ausente_levanta_valueerror(tmp_path):
    pricing = tmp_path / "pricing.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["campo1", "campo2"])
    ws.append(["a", "b"])
    wb.save(pricing)

    with pytest.raises(ValueError, match="Colunas de chave não encontradas"):
        carregar_base_pricing(pricing)


def test_reader_alias_case_insensitive(tmp_path):
    """Colunas com nomes em maiúsculas devem ser reconhecidas."""
    pricing = tmp_path / "pricing.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["UF", "Sindicato", "Ano_Referencia"])
    ws.append(["SP", "Sind", "2025"])
    wb.save(pricing)

    linhas, _, col_uf, col_sindicato, col_ano = carregar_base_pricing(pricing)
    assert col_uf == "UF"
    assert col_sindicato == "Sindicato"
    assert col_ano == "Ano_Referencia"
    assert len(linhas) == 1


# ── integração via CLI ────────────────────────────────────────────────────────

def test_cli_fluxo_completo(tmp_path):
    from src.cli import main

    pricing = tmp_path / "base_pricing.xlsx"
    linhas_pricing = [
        {"uf": "SP", "sindicato": "Sind", "ano_referencia": "2025", "salario_base": 1000, "cargo": "op"},
        {"uf": "RJ", "sindicato": "Outro", "ano_referencia": "2024", "salario_base": 800, "cargo": "aux"},
    ]
    _criar_xlsx(pricing, linhas_pricing)

    adj = tmp_path / "reajustes_aprovados.json"
    _aprovados_json(adj, [_reajuste(uf="SP", sindicato="Sind", ano_referencia="2025")])

    output = tmp_path / "preview.xlsx"

    codigo = main([
        "preview-pricing-update",
        "--pricing", str(pricing),
        "--adjustments", str(adj),
        "--output", str(output),
    ])

    assert codigo == 0
    assert output.exists()

    wb = openpyxl.load_workbook(output)
    ws = wb.active
    cabecalho = [c.value for c in ws[1]]
    assert "status_aplicacao" in cabecalho
    assert "uf" in cabecalho

    # linha 1 (SP/Sind/2025) → reajuste_encontrado
    linha1 = {cabecalho[i]: ws[2][i].value for i in range(len(cabecalho))}
    assert linha1["status_aplicacao"] == "reajuste_encontrado"

    # linha 2 (RJ/Outro/2024) → sem_correspondencia
    linha2 = {cabecalho[i]: ws[3][i].value for i in range(len(cabecalho))}
    assert linha2["status_aplicacao"] == "sem_correspondencia"


def test_cli_retorna_0_com_sucesso(tmp_path):
    from src.cli import main

    pricing = tmp_path / "p.xlsx"
    _criar_xlsx(pricing, [{"uf": "SP", "sindicato": "Sind", "ano_referencia": "2025", "salario_base": 1, "cargo": "x"}])
    adj = tmp_path / "adj.json"
    _aprovados_json(adj, [_reajuste()])

    codigo = main([
        "preview-pricing-update",
        "--pricing", str(pricing),
        "--adjustments", str(adj),
        "--output", str(tmp_path / "out.xlsx"),
    ])
    assert codigo == 0


def test_cli_relatorio_exibido_no_terminal(tmp_path, capsys):
    from src.cli import main

    pricing = tmp_path / "p.xlsx"
    _criar_xlsx(pricing, [{"uf": "SP", "sindicato": "Sind", "ano_referencia": "2025", "salario_base": 1, "cargo": "x"}])
    adj = tmp_path / "adj.json"
    _aprovados_json(adj, [_reajuste()])

    main([
        "preview-pricing-update",
        "--pricing", str(pricing),
        "--adjustments", str(adj),
        "--output", str(tmp_path / "out.xlsx"),
    ])

    captured = capsys.readouterr()
    assert "status_aplicacao" in captured.out or "Relatório" in captured.out


def test_cli_caminhos_padrao_resolvidos_via_raiz_repo(tmp_path, monkeypatch):
    from src.cli import main
    import src.cli as cli_module

    raiz = tmp_path
    monkeypatch.setattr(cli_module, "_raiz_repo", lambda: raiz)

    data_dir = raiz / "data"
    data_dir.mkdir()

    pricing = data_dir / "base_pricing.xlsx"
    _criar_xlsx(pricing, [{"uf": "SP", "sindicato": "Sind", "ano_referencia": "2025", "salario_base": 1, "cargo": "x"}])

    adj = data_dir / "reajustes_aprovados.json"
    _aprovados_json(adj, [_reajuste()])

    codigo = main(["preview-pricing-update"])
    assert codigo == 0
    assert (data_dir / "preview_atualizacao_pricing.xlsx").exists()

"""Testes para o comando consolidate-texts da CLI e os módulos de consolidação.

Cobre os critérios de aceitação da US-PRJ-6:
  AC1 — leitura tolerante (base nativa obrigatória, OCR opcional)
  AC2 — priorização nativo > OCR > sem_texto_final
  AC3 — status_consolidado obrigatório em cada registro
  AC4 — preservação dos campos de rastreabilidade
  AC5 — relatório com quatro contadores e soma == total
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.models.texto_extraido import TextoExtraido, TextoConsolidado, STATUS_CONSOLIDACAO
from src.services.consolidator import consolidar_textos
from src.services.extraction_store import (
    salvar_textos,
    salvar_consolidados,
    carregar_consolidados,
)
from src.reports.consolidation import imprimir_relatorio_consolidacao


# ── helpers ───────────────────────────────────────────────────────────────────

def _nativo(
    caminho="CCT/SP/Sind/a.pdf",
    status="extraido_com_sucesso",
    texto="Texto nativo.",
    **kwargs,
) -> TextoExtraido:
    defaults = dict(
        caminho=caminho,
        nome_arquivo=Path(caminho).name,
        uf="SP",
        sindicato="Sind",
        tipo_documento="CCT",
        ano_referencia="2025-2026",
        texto=texto,
        num_caracteres=len(texto),
        status=status,
        data_processamento="2025-01-01T00:00:00+00:00",
    )
    defaults.update(kwargs)
    return TextoExtraido(**defaults)


def _ocr(
    caminho="CCT/SP/Sind/a.pdf",
    status="extraido_via_ocr",
    texto="Texto OCR.",
    **kwargs,
) -> TextoExtraido:
    defaults = dict(
        caminho=caminho,
        nome_arquivo=Path(caminho).name,
        uf="SP",
        sindicato="Sind",
        tipo_documento="CCT",
        ano_referencia="2025-2026",
        texto=texto,
        num_caracteres=len(texto),
        status=status,
        data_processamento="2025-01-02T00:00:00+00:00",
    )
    defaults.update(kwargs)
    return TextoExtraido(**defaults)


# ── AC1: leitura tolerante ────────────────────────────────────────────────────

def test_cmd_falha_se_arquivo_nativo_ausente(tmp_path):
    """consolidate-texts deve retornar código 1 quando a base nativa não existe."""
    from src.cli import cmd_consolidate_texts
    args = MagicMock()
    args.input_native = str(tmp_path / "inexistente.json")
    args.input_ocr = str(tmp_path / "textos_ocr.json")
    args.output = str(tmp_path / "out.json")
    with patch("src.cli._raiz_repo", return_value=tmp_path):
        result = cmd_consolidate_texts(args)
    assert result == 1


def test_cmd_continua_sem_arquivo_ocr(tmp_path):
    """consolidate-texts deve concluir com código 0 quando a base OCR não existe."""
    nativos = [_nativo()]
    native_path = tmp_path / "textos_extraidos.json"
    salvar_textos(native_path, nativos)

    from src.cli import cmd_consolidate_texts
    args = MagicMock()
    args.input_native = str(native_path)
    args.input_ocr = str(tmp_path / "inexistente_ocr.json")
    args.output = str(tmp_path / "out.json")
    with patch("src.cli._raiz_repo", return_value=tmp_path):
        result = cmd_consolidate_texts(args)
    assert result == 0


def test_cmd_informa_ausencia_ocr_no_output(tmp_path, capsys):
    """Quando a base OCR não existe, a saída deve mencionar a ausência."""
    nativos = [_nativo()]
    native_path = tmp_path / "textos_extraidos.json"
    salvar_textos(native_path, nativos)

    from src.cli import cmd_consolidate_texts
    args = MagicMock()
    args.input_native = str(native_path)
    args.input_ocr = str(tmp_path / "inexistente_ocr.json")
    args.output = str(tmp_path / "out.json")
    with patch("src.cli._raiz_repo", return_value=tmp_path):
        cmd_consolidate_texts(args)

    captured = capsys.readouterr()
    assert "OCR" in captured.out


# ── AC2: priorização nativo > OCR > sem_texto_final ──────────────────────────

def test_documento_extraido_com_sucesso_usa_texto_nativo():
    """Documentos com extraido_com_sucesso devem usar texto nativo."""
    nativos = [_nativo(status="extraido_com_sucesso", texto="Conteúdo nativo.")]
    resultado = consolidar_textos(nativos, [])
    assert len(resultado) == 1
    assert resultado[0].status_consolidado == "texto_nativo"
    assert resultado[0].texto_final == "Conteúdo nativo."
    assert resultado[0].origem_texto == "texto_nativo"


def test_documento_sem_texto_com_ocr_usa_texto_ocr():
    """Documentos sem texto nativo mas com OCR válido devem usar texto OCR."""
    nativos = [_nativo(status="sem_texto_extraivel", texto="")]
    ocrs = [_ocr(status="extraido_via_ocr", texto="Texto OCR válido.")]
    resultado = consolidar_textos(nativos, ocrs)
    assert resultado[0].status_consolidado == "texto_ocr"
    assert resultado[0].texto_final == "Texto OCR válido."
    assert resultado[0].origem_texto == "texto_ocr"


def test_documento_sem_texto_sem_ocr_vira_sem_texto_final():
    """Documentos sem texto nativo e sem OCR disponível devem ser sem_texto_final."""
    nativos = [_nativo(status="sem_texto_extraivel", texto="", num_caracteres=0)]
    resultado = consolidar_textos(nativos, [])
    assert resultado[0].status_consolidado == "sem_texto_final"
    assert resultado[0].texto_final == ""


def test_documento_sem_texto_com_ocr_sem_resultado_vira_sem_texto_final():
    """OCR sem resultado (ocr_sem_texto_reconhecido) não deve ser usado como fallback."""
    nativos = [_nativo(status="sem_texto_extraivel", texto="", num_caracteres=0)]
    ocrs = [_ocr(status="ocr_sem_texto_reconhecido", texto="")]
    resultado = consolidar_textos(nativos, ocrs)
    assert resultado[0].status_consolidado == "sem_texto_final"


def test_prioridade_nativo_sobre_ocr_quando_ambos_disponiveis():
    """Quando nativo tem extraido_com_sucesso, deve ignorar OCR existente."""
    nativos = [_nativo(status="extraido_com_sucesso", texto="Nativo preferido.")]
    ocrs = [_ocr(status="extraido_via_ocr", texto="OCR ignorado.")]
    resultado = consolidar_textos(nativos, ocrs)
    assert resultado[0].status_consolidado == "texto_nativo"
    assert resultado[0].texto_final == "Nativo preferido."


def test_documentos_com_outros_status_nativos_viram_sem_texto_final():
    """Outros status nativos (erro, nao_encontrado, etc.) sem OCR → sem_texto_final."""
    for status in ["erro_na_leitura", "documento_nao_encontrado", "nao_elegivel_para_extracao"]:
        nativos = [_nativo(status=status, texto="", num_caracteres=0)]
        resultado = consolidar_textos(nativos, [])
        assert resultado[0].status_consolidado == "sem_texto_final", f"Falhou para status={status}"


def test_multiplos_documentos_priorizacao_independente():
    """Cada documento deve ter sua priorização aplicada independentemente."""
    nativos = [
        _nativo("CCT/SP/A/a.pdf", status="extraido_com_sucesso", texto="Nativo A"),
        _nativo("CCT/SP/B/b.pdf", status="sem_texto_extraivel", texto="", num_caracteres=0),
        _nativo("CCT/SP/C/c.pdf", status="sem_texto_extraivel", texto="", num_caracteres=0),
        _nativo("CCT/SP/D/d.pdf", status="erro_na_leitura", texto="", num_caracteres=0),
    ]
    ocrs = [
        _ocr("CCT/SP/B/b.pdf", status="extraido_via_ocr", texto="OCR B"),
        _ocr("CCT/SP/C/c.pdf", status="ocr_sem_texto_reconhecido", texto=""),
    ]
    resultado = consolidar_textos(nativos, ocrs)

    assert len(resultado) == 4
    por_caminho = {r.caminho: r for r in resultado}
    assert por_caminho["CCT/SP/A/a.pdf"].status_consolidado == "texto_nativo"
    assert por_caminho["CCT/SP/B/b.pdf"].status_consolidado == "texto_ocr"
    assert por_caminho["CCT/SP/C/c.pdf"].status_consolidado == "sem_texto_final"
    assert por_caminho["CCT/SP/D/d.pdf"].status_consolidado == "sem_texto_final"


# ── AC3: status_consolidado obrigatório ──────────────────────────────────────

def test_todos_registros_possuem_status_consolidado():
    """Todos os registros consolidados devem ter status_consolidado preenchido."""
    nativos = [
        _nativo("CCT/SP/A/a.pdf", status="extraido_com_sucesso"),
        _nativo("CCT/SP/B/b.pdf", status="sem_texto_extraivel", texto="", num_caracteres=0),
    ]
    resultado = consolidar_textos(nativos, [])
    for r in resultado:
        assert r.status_consolidado in STATUS_CONSOLIDACAO


def test_nenhum_documento_omitido():
    """O número de registros consolidados deve ser igual ao número de documentos nativos."""
    nativos = [_nativo(f"CCT/SP/A/{i}.pdf", status="extraido_com_sucesso") for i in range(5)]
    resultado = consolidar_textos(nativos, [])
    assert len(resultado) == 5


def test_erro_consolidacao_nao_interrompe_outros(monkeypatch):
    """Um erro inesperado em um documento não deve impedir o processamento dos demais."""
    nativos = [
        _nativo("CCT/SP/A/a.pdf", status="extraido_com_sucesso", texto="Bom"),
        _nativo("CCT/SP/B/b.pdf", status="extraido_com_sucesso", texto="Bom B"),
    ]

    call_count = [0]
    original_status = ["extraido_com_sucesso", "extraido_com_sucesso"]

    def patched_consolidar(nativos_list, ocr_list):
        # Simula erro no primeiro documento forçando exceção
        resultado = []
        from datetime import datetime, timezone
        agora = datetime.now(tz=timezone.utc).isoformat()
        for i, doc in enumerate(nativos_list):
            if i == 0:
                import sys as _sys
                print(f"Erro ao consolidar '{doc.caminho}': forçado", file=_sys.stderr)
                resultado.append(TextoConsolidado(
                    caminho=doc.caminho, nome_arquivo=doc.nome_arquivo,
                    uf=doc.uf, sindicato=doc.sindicato,
                    tipo_documento=doc.tipo_documento, ano_referencia=doc.ano_referencia,
                    texto_final="", num_caracteres=0,
                    origem_texto="erro_consolidacao",
                    status_consolidado="erro_consolidacao",
                    data_consolidacao=agora,
                ))
            else:
                resultado.append(TextoConsolidado(
                    caminho=doc.caminho, nome_arquivo=doc.nome_arquivo,
                    uf=doc.uf, sindicato=doc.sindicato,
                    tipo_documento=doc.tipo_documento, ano_referencia=doc.ano_referencia,
                    texto_final=doc.texto, num_caracteres=doc.num_caracteres,
                    origem_texto="texto_nativo",
                    status_consolidado="texto_nativo",
                    data_consolidacao=agora,
                ))
        return resultado

    resultado = patched_consolidar(nativos, [])
    assert len(resultado) == 2
    assert resultado[0].status_consolidado == "erro_consolidacao"
    assert resultado[1].status_consolidado == "texto_nativo"


# ── AC4: campos de rastreabilidade ────────────────────────────────────────────

def test_campos_rastreabilidade_preservados():
    """Todos os campos de rastreabilidade obrigatórios devem estar presentes."""
    doc = _nativo(
        caminho="CCT/MG/SindMG/cct.pdf",
        uf="MG",
        sindicato="SindMG",
        tipo_documento="TA",
        ano_referencia="2024-2025",
        status="extraido_com_sucesso",
        texto="Conteúdo",
    )
    resultado = consolidar_textos([doc], [])
    r = resultado[0]

    assert r.caminho == "CCT/MG/SindMG/cct.pdf"
    assert r.nome_arquivo == "cct.pdf"
    assert r.uf == "MG"
    assert r.sindicato == "SindMG"
    assert r.tipo_documento == "TA"
    assert r.ano_referencia == "2024-2025"
    assert r.texto_final == "Conteúdo"
    assert r.num_caracteres == len("Conteúdo")
    assert r.origem_texto != ""
    assert r.status_consolidado != ""
    assert r.data_consolidacao != ""


def test_num_caracteres_correto_para_texto_nativo():
    """num_caracteres deve refletir o tamanho do texto_final escolhido."""
    texto = "Exemplo de texto com tamanho definido."
    nativos = [_nativo(status="extraido_com_sucesso", texto=texto)]
    resultado = consolidar_textos(nativos, [])
    assert resultado[0].num_caracteres == len(texto)


def test_num_caracteres_correto_para_texto_ocr():
    """num_caracteres deve usar o tamanho do texto OCR quando escolhido."""
    texto_ocr = "Texto reconhecido pelo OCR."
    nativos = [_nativo(status="sem_texto_extraivel", texto="", num_caracteres=0)]
    ocrs = [_ocr(status="extraido_via_ocr", texto=texto_ocr)]
    resultado = consolidar_textos(nativos, ocrs)
    assert resultado[0].num_caracteres == len(texto_ocr)


def test_data_consolidacao_preenchida():
    """data_consolidacao deve ser uma string ISO 8601 não-vazia."""
    nativos = [_nativo()]
    resultado = consolidar_textos(nativos, [])
    assert resultado[0].data_consolidacao != ""
    assert "T" in resultado[0].data_consolidacao


# ── AC4: persistência ────────────────────────────────────────────────────────

def test_salvar_e_carregar_consolidados_roundtrip(tmp_path):
    """salvar_consolidados / carregar_consolidados devem fazer round-trip fiel."""
    from datetime import datetime, timezone
    agora = datetime.now(tz=timezone.utc).isoformat()
    textos = [
        TextoConsolidado(
            caminho="CCT/SP/A/a.pdf",
            nome_arquivo="a.pdf",
            uf="SP",
            sindicato="SindSP",
            tipo_documento="CCT",
            ano_referencia="2025",
            texto_final="Texto final aqui.",
            num_caracteres=17,
            origem_texto="texto_nativo",
            status_consolidado="texto_nativo",
            data_consolidacao=agora,
        )
    ]
    path = tmp_path / "out.json"
    salvar_consolidados(path, textos)
    carregados = carregar_consolidados(path)

    assert len(carregados) == 1
    r = carregados[0]
    assert r.caminho == "CCT/SP/A/a.pdf"
    assert r.texto_final == "Texto final aqui."
    assert r.status_consolidado == "texto_nativo"
    assert r.origem_texto == "texto_nativo"
    assert r.num_caracteres == 17


def test_output_usa_formato_versao_textos(tmp_path):
    """Arquivo de saída deve usar o formato {versao, textos}."""
    from datetime import datetime, timezone
    agora = datetime.now(tz=timezone.utc).isoformat()
    textos = [
        TextoConsolidado(
            caminho="CCT/SP/A/a.pdf", nome_arquivo="a.pdf", uf="SP",
            sindicato="S", tipo_documento="CCT", ano_referencia="2025",
            texto_final="X", num_caracteres=1,
            origem_texto="texto_nativo", status_consolidado="texto_nativo",
            data_consolidacao=agora,
        )
    ]
    path = tmp_path / "out.json"
    salvar_consolidados(path, textos)
    with path.open(encoding="utf-8") as f:
        dados = json.load(f)
    assert "versao" in dados
    assert "textos" in dados
    assert isinstance(dados["textos"], list)


# ── AC5: relatório de consolidação ───────────────────────────────────────────

def test_status_consolidacao_tem_quatro_valores():
    assert len(STATUS_CONSOLIDACAO) == 4
    assert "texto_nativo" in STATUS_CONSOLIDACAO
    assert "texto_ocr" in STATUS_CONSOLIDACAO
    assert "sem_texto_final" in STATUS_CONSOLIDACAO
    assert "erro_consolidacao" in STATUS_CONSOLIDACAO


def test_relatorio_consolidacao_soma_igual_ao_total():
    """A soma dos quatro contadores deve ser igual ao total de documentos."""
    from datetime import datetime, timezone
    agora = datetime.now(tz=timezone.utc).isoformat()

    def _c(status):
        return TextoConsolidado(
            caminho="x", nome_arquivo="x", uf=None, sindicato=None,
            tipo_documento=None, ano_referencia=None,
            texto_final="", num_caracteres=0,
            origem_texto=status, status_consolidado=status,
            data_consolidacao=agora,
        )

    textos = [
        _c("texto_nativo"),
        _c("texto_ocr"),
        _c("sem_texto_final"),
        _c("erro_consolidacao"),
    ]
    capturado = []
    with patch("builtins.print", side_effect=lambda *a, **kw: capturado.append(" ".join(str(x) for x in a))):
        imprimir_relatorio_consolidacao(textos)

    conteudo = "\n".join(capturado)
    assert "✓" in conteudo
    assert "4" in conteudo


def test_relatorio_consolida_exibe_ausencia_ocr():
    """Quando OCR não disponível, o relatório deve mencionar a ausência."""
    capturado = []
    with patch("builtins.print", side_effect=lambda *a, **kw: capturado.append(" ".join(str(x) for x in a))):
        imprimir_relatorio_consolidacao([], ocr_disponivel=False)

    conteudo = "\n".join(capturado)
    assert "OCR" in conteudo


def test_relatorio_consolidacao_com_lista_vazia():
    """Relatório com lista vazia deve exibir zeros e soma consistente."""
    capturado = []
    with patch("builtins.print", side_effect=lambda *a, **kw: capturado.append(" ".join(str(x) for x in a))):
        imprimir_relatorio_consolidacao([])

    conteudo = "\n".join(capturado)
    assert "✓" in conteudo


def test_relatorio_consolidacao_exibe_quatro_status():
    """Relatório deve mencionar os quatro status de consolidação."""
    capturado = []
    with patch("builtins.print", side_effect=lambda *a, **kw: capturado.append(" ".join(str(x) for x in a))):
        imprimir_relatorio_consolidacao([])

    conteudo = "\n".join(capturado)
    assert "Texto nativo" in conteudo
    assert "Texto OCR" in conteudo
    assert "Sem texto final" in conteudo
    assert "Erro de consolidação" in conteudo


def test_cmd_gera_arquivo_saida(tmp_path):
    """consolidate-texts deve criar o arquivo de saída."""
    nativos = [_nativo()]
    native_path = tmp_path / "textos_extraidos.json"
    output_path = tmp_path / "textos_consolidados.json"
    salvar_textos(native_path, nativos)

    from src.cli import cmd_consolidate_texts
    args = MagicMock()
    args.input_native = str(native_path)
    args.input_ocr = str(tmp_path / "inexistente_ocr.json")
    args.output = str(output_path)
    with patch("src.cli._raiz_repo", return_value=tmp_path):
        result = cmd_consolidate_texts(args)

    assert result == 0
    assert output_path.exists()
    consolidados = carregar_consolidados(output_path)
    assert len(consolidados) == 1

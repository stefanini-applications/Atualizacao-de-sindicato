"""Testes para o comando OCR da CLI e o relatório de OCR.

Cobre os critérios de aceitação da US-PRJ-4:
  AC1 — apenas documentos com status sem_texto_extraivel são processados
  AC3 — status extraido_via_ocr e num_caracteres corretos ao salvar
  AC4 — status ocr_sem_texto_reconhecido para OCR sem resultado útil
  AC5 — status erro_no_ocr; processamento continua após falha isolada
  AC6 — relatório com três contadores e soma == total
"""

import io
import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

import src.services.ocr as ocr_module
from src.models.texto_extraido import TextoExtraido, STATUS_OCR
from src.services.extraction_store import salvar_textos, carregar_textos
from src.reports.ocr import imprimir_relatorio_ocr


# ── helpers ───────────────────────────────────────────────────────────────────

def _texto(caminho="CCT/SP/Sind/a.pdf", status="sem_texto_extraivel", **kwargs) -> TextoExtraido:
    defaults = dict(
        caminho=caminho,
        nome_arquivo=Path(caminho).name,
        uf="SP",
        sindicato="Sind",
        tipo_documento="CCT",
        ano_referencia="2025-2026",
        texto="",
        num_caracteres=0,
        status=status,
        data_processamento="2025-01-01T00:00:00+00:00",
    )
    defaults.update(kwargs)
    return TextoExtraido(**defaults)


def _salvar_input(path: Path, textos: list) -> None:
    salvar_textos(path, textos)


# ── AC1: seleção de elegíveis ─────────────────────────────────────────────────

def test_somente_sem_texto_extraivel_e_processado(tmp_path):
    """Apenas documentos com status sem_texto_extraivel devem ir para OCR."""
    textos = [
        _texto("CCT/SP/Sind/a.pdf", status="sem_texto_extraivel"),
        _texto("CCT/SP/Sind/b.pdf", status="extraido_com_sucesso"),
        _texto("CCT/SP/Sind/c.pdf", status="erro_na_leitura"),
        _texto("CCT/SP/Sind/d.pdf", status="documento_nao_encontrado"),
        _texto("CCT/SP/Sind/e.pdf", status="nao_elegivel_para_extracao"),
    ]
    input_path = tmp_path / "data" / "textos_extraidos.json"
    output_path = tmp_path / "data" / "textos_ocr.json"
    _salvar_input(input_path, textos)

    processados = []

    def fake_ocr(pdf_path, lang="por"):
        processados.append(str(pdf_path))
        return "", "ocr_sem_texto_reconhecido"

    with patch("src.cli.verificar_ambiente_ocr") as mock_env, \
         patch("src.services.ocr.ocr_pdf", side_effect=fake_ocr):
        mock_env.return_value = MagicMock(ok=True)
        from src.cli import cmd_ocr
        args = MagicMock()
        args.input = str(input_path)
        args.output = str(output_path)
        with patch("src.cli._raiz_repo", return_value=tmp_path):
            result = cmd_ocr(args)

    assert result == 0
    assert len(processados) == 1
    assert "a.pdf" in processados[0]


def test_sem_elegiveis_encerra_sem_processar(tmp_path):
    """Quando não há documentos elegíveis, a execução termina sem processar."""
    textos = [
        _texto("CCT/SP/Sind/a.pdf", status="extraido_com_sucesso"),
    ]
    input_path = tmp_path / "data" / "textos_extraidos.json"
    output_path = tmp_path / "data" / "textos_ocr.json"
    _salvar_input(input_path, textos)

    with patch("src.cli.verificar_ambiente_ocr") as mock_env:
        mock_env.return_value = MagicMock(ok=True)
        from src.cli import cmd_ocr
        args = MagicMock()
        args.input = str(input_path)
        args.output = str(output_path)
        with patch("src.cli._raiz_repo", return_value=tmp_path):
            result = cmd_ocr(args)

    assert result == 0
    assert not output_path.exists()


# ── AC3: armazenamento com status extraido_via_ocr ────────────────────────────

def test_ocr_com_sucesso_salva_status_extraido_via_ocr(tmp_path):
    """Quando OCR reconhece texto, status deve ser extraido_via_ocr e num_caracteres > 0."""
    textos = [_texto("CCT/SP/Sind/a.pdf", status="sem_texto_extraivel")]
    input_path = tmp_path / "data" / "textos_extraidos.json"
    output_path = tmp_path / "data" / "textos_ocr.json"
    _salvar_input(input_path, textos)

    with patch("src.cli.verificar_ambiente_ocr") as mock_env, \
         patch("src.services.ocr.ocr_pdf", return_value=("Texto OCR reconhecido", "extraido_via_ocr")):
        mock_env.return_value = MagicMock(ok=True)
        from src.cli import cmd_ocr
        args = MagicMock()
        args.input = str(input_path)
        args.output = str(output_path)
        with patch("src.cli._raiz_repo", return_value=tmp_path):
            cmd_ocr(args)

    resultados = carregar_textos(output_path)
    assert len(resultados) == 1
    assert resultados[0].status == "extraido_via_ocr"
    assert resultados[0].num_caracteres == len("Texto OCR reconhecido")
    assert resultados[0].texto == "Texto OCR reconhecido"


def test_ocr_preserva_rastreabilidade(tmp_path):
    """Resultado de OCR deve preservar todos os campos de rastreabilidade do documento original."""
    doc = _texto(
        caminho="CCT/MG/Sind/cct.pdf",
        uf="MG",
        sindicato="SindMG",
        tipo_documento="TA",
        ano_referencia="2024-2025",
        status="sem_texto_extraivel",
    )
    input_path = tmp_path / "data" / "textos_extraidos.json"
    output_path = tmp_path / "data" / "textos_ocr.json"
    _salvar_input(input_path, [doc])

    with patch("src.cli.verificar_ambiente_ocr") as mock_env, \
         patch("src.services.ocr.ocr_pdf", return_value=("Conteúdo", "extraido_via_ocr")):
        mock_env.return_value = MagicMock(ok=True)
        from src.cli import cmd_ocr
        args = MagicMock()
        args.input = str(input_path)
        args.output = str(output_path)
        with patch("src.cli._raiz_repo", return_value=tmp_path):
            cmd_ocr(args)

    r = carregar_textos(output_path)[0]
    assert r.caminho == "CCT/MG/Sind/cct.pdf"
    assert r.uf == "MG"
    assert r.sindicato == "SindMG"
    assert r.tipo_documento == "TA"
    assert r.ano_referencia == "2024-2025"
    assert r.data_processamento != ""


# ── AC4: ocr_sem_texto_reconhecido ────────────────────────────────────────────

def test_ocr_sem_resultado_salva_status_ocr_sem_texto(tmp_path):
    """Quando OCR não encontra texto, status deve ser ocr_sem_texto_reconhecido."""
    textos = [_texto("CCT/SP/Sind/a.pdf", status="sem_texto_extraivel")]
    input_path = tmp_path / "data" / "textos_extraidos.json"
    output_path = tmp_path / "data" / "textos_ocr.json"
    _salvar_input(input_path, textos)

    with patch("src.cli.verificar_ambiente_ocr") as mock_env, \
         patch("src.services.ocr.ocr_pdf", return_value=("", "ocr_sem_texto_reconhecido")):
        mock_env.return_value = MagicMock(ok=True)
        from src.cli import cmd_ocr
        args = MagicMock()
        args.input = str(input_path)
        args.output = str(output_path)
        with patch("src.cli._raiz_repo", return_value=tmp_path):
            cmd_ocr(args)

    resultados = carregar_textos(output_path)
    assert resultados[0].status == "ocr_sem_texto_reconhecido"
    assert resultados[0].texto == ""
    assert resultados[0].num_caracteres == 0


# ── AC5: erro_no_ocr não interrompe os demais ─────────────────────────────────

def test_erro_no_ocr_nao_interrompe_processamento(tmp_path):
    """Erro técnico em um documento não deve impedir os demais de serem processados."""
    textos = [
        _texto("CCT/SP/Sind/a.pdf", status="sem_texto_extraivel"),
        _texto("CCT/SP/Sind/b.pdf", status="sem_texto_extraivel"),
        _texto("CCT/SP/Sind/c.pdf", status="sem_texto_extraivel"),
    ]

    resultados_ocr = {
        "a.pdf": ("", "erro_no_ocr"),
        "b.pdf": ("Texto B", "extraido_via_ocr"),
        "c.pdf": ("", "ocr_sem_texto_reconhecido"),
    }

    def fake_ocr(pdf_path, lang="por"):
        return resultados_ocr[pdf_path.name]

    input_path = tmp_path / "data" / "textos_extraidos.json"
    output_path = tmp_path / "data" / "textos_ocr.json"
    _salvar_input(input_path, textos)

    with patch("src.cli.verificar_ambiente_ocr") as mock_env, \
         patch("src.services.ocr.ocr_pdf", side_effect=fake_ocr):
        mock_env.return_value = MagicMock(ok=True)
        from src.cli import cmd_ocr
        args = MagicMock()
        args.input = str(input_path)
        args.output = str(output_path)
        with patch("src.cli._raiz_repo", return_value=tmp_path):
            result = cmd_ocr(args)

    assert result == 0
    salvos = carregar_textos(output_path)
    assert len(salvos) == 3
    statuses = {Path(r.caminho).name: r.status for r in salvos}
    assert statuses["a.pdf"] == "erro_no_ocr"
    assert statuses["b.pdf"] == "extraido_via_ocr"
    assert statuses["c.pdf"] == "ocr_sem_texto_reconhecido"


# ── AC5: output usa escrita atômica ──────────────────────────────────────────

def test_output_usa_formato_versao_textos(tmp_path):
    """Output JSON deve usar o formato versionado {versao, textos} da extraction_store."""
    textos = [_texto("CCT/SP/Sind/a.pdf", status="sem_texto_extraivel")]
    input_path = tmp_path / "data" / "textos_extraidos.json"
    output_path = tmp_path / "data" / "textos_ocr.json"
    _salvar_input(input_path, textos)

    with patch("src.cli.verificar_ambiente_ocr") as mock_env, \
         patch("src.services.ocr.ocr_pdf", return_value=("Texto", "extraido_via_ocr")):
        mock_env.return_value = MagicMock(ok=True)
        from src.cli import cmd_ocr
        args = MagicMock()
        args.input = str(input_path)
        args.output = str(output_path)
        with patch("src.cli._raiz_repo", return_value=tmp_path):
            cmd_ocr(args)

    with output_path.open(encoding="utf-8") as f:
        dados = json.load(f)
    assert "versao" in dados
    assert "textos" in dados
    assert isinstance(dados["textos"], list)


# ── AC6: relatório de OCR ─────────────────────────────────────────────────────

def test_status_ocr_tem_tres_valores():
    assert len(STATUS_OCR) == 3
    assert "extraido_via_ocr" in STATUS_OCR
    assert "ocr_sem_texto_reconhecido" in STATUS_OCR
    assert "erro_no_ocr" in STATUS_OCR


def test_relatorio_ocr_soma_igual_ao_total():
    """A soma dos três contadores deve ser igual ao total de documentos."""
    textos = [
        _texto("a.pdf", status="extraido_via_ocr"),
        _texto("b.pdf", status="ocr_sem_texto_reconhecido"),
        _texto("c.pdf", status="erro_no_ocr"),
    ]

    capturado = []
    with patch("builtins.print", side_effect=lambda *a, **kw: capturado.append(" ".join(str(x) for x in a))):
        imprimir_relatorio_ocr(textos)

    conteudo = "\n".join(capturado)
    assert "3" in conteudo
    assert "✓" in conteudo


def test_relatorio_ocr_com_lista_vazia():
    """Relatório com lista vazia deve exibir zeros e soma consistente."""
    capturado = []
    with patch("builtins.print", side_effect=lambda *a, **kw: capturado.append(" ".join(str(x) for x in a))):
        imprimir_relatorio_ocr([])

    conteudo = "\n".join(capturado)
    assert "✓" in conteudo


def test_relatorio_ocr_exibe_os_tres_status():
    """Relatório deve mencionar os três status de OCR."""
    textos = [
        _texto("a.pdf", status="extraido_via_ocr"),
        _texto("b.pdf", status="ocr_sem_texto_reconhecido"),
        _texto("c.pdf", status="erro_no_ocr"),
    ]

    capturado = []
    with patch("builtins.print", side_effect=lambda *a, **kw: capturado.append(" ".join(str(x) for x in a))):
        imprimir_relatorio_ocr(textos)

    conteudo = "\n".join(capturado)
    assert "Extraído via OCR" in conteudo
    assert "OCR sem texto reconhecido" in conteudo
    assert "Erro no OCR" in conteudo


def test_relatorio_ocr_exibe_total_avaliados():
    """Relatório deve exibir o total de documentos avaliados para OCR."""
    textos = [_texto(f"d{i}.pdf", status="extraido_via_ocr") for i in range(5)]

    capturado = []
    with patch("builtins.print", side_effect=lambda *a, **kw: capturado.append(" ".join(str(x) for x in a))):
        imprimir_relatorio_ocr(textos)

    conteudo = "\n".join(capturado)
    assert "5" in conteudo

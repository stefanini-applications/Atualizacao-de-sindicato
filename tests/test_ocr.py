"""Testes do processamento OCR de PDFs sindicais escaneados.

Cobre os critérios de aceitação da US-PRJ-4:
  AC1 — seleção apenas de documentos com status sem_texto_extraivel
  AC2 — preservação de rastreabilidade (caminho, UF, sindicato, etc.)
  AC3 — armazenamento do texto reconhecido via OCR com status extraido_via_ocr
  AC4 — OCR sem resultado: status ocr_sem_texto_reconhecido
  AC5 — erro técnico: status erro_no_ocr, sem interromper demais documentos
  AC6 — relatório consolidado com soma == total avaliados
"""

import io
import sys
import os
import tempfile
import json
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from src.models.texto_extraido import TextoExtraido, STATUS_EXTRACAO, STATUS_OCR
from src.services.ocr import aplicar_ocr_pdf, processar_ocr
from src.reports.ocr import imprimir_relatorio_ocr


# ── helpers ───────────────────────────────────────────────────────────────────

def _texto(**kwargs) -> TextoExtraido:
    defaults = dict(
        caminho="CCT/SP/Sindpd/CCT_2025-2026_Sindpd-SP.pdf",
        nome_arquivo="CCT_2025-2026_Sindpd-SP.pdf",
        uf="SP",
        sindicato="Sindpd",
        tipo_documento="CCT",
        ano_referencia="2025-2026",
        texto="",
        num_caracteres=0,
        status="sem_texto_extraivel",
        data_processamento="2025-01-01T00:00:00+00:00",
    )
    defaults.update(kwargs)
    return TextoExtraido(**defaults)


# ── Modelo: STATUS_OCR ────────────────────────────────────────────────────────

def test_status_ocr_tem_tres_valores():
    assert len(STATUS_OCR) == 3
    assert "extraido_via_ocr" in STATUS_OCR
    assert "ocr_sem_texto_reconhecido" in STATUS_OCR
    assert "erro_no_ocr" in STATUS_OCR


def test_status_ocr_nao_sobrepoe_status_extracao():
    """Os status de OCR devem ser distintos dos status de extração original."""
    assert STATUS_OCR.isdisjoint(STATUS_EXTRACAO)


# ── AC1: seleção de documentos elegíveis para OCR ────────────────────────────

def test_processar_ocr_ignora_extraido_com_sucesso():
    """Documentos com status extraido_com_sucesso não devem ser reprocessados."""
    t = _texto(status="extraido_com_sucesso", texto="Texto existente.", num_caracteres=16)
    with tempfile.TemporaryDirectory() as tmpdir:
        processados = processar_ocr([t], Path(tmpdir))
    assert processados == []
    assert t.status == "extraido_com_sucesso"


def test_processar_ocr_ignora_erro_na_leitura():
    t = _texto(status="erro_na_leitura")
    with tempfile.TemporaryDirectory() as tmpdir:
        processados = processar_ocr([t], Path(tmpdir))
    assert processados == []


def test_processar_ocr_ignora_documento_nao_encontrado():
    t = _texto(status="documento_nao_encontrado")
    with tempfile.TemporaryDirectory() as tmpdir:
        processados = processar_ocr([t], Path(tmpdir))
    assert processados == []


def test_processar_ocr_ignora_nao_elegivel():
    t = _texto(status="nao_elegivel_para_extracao")
    with tempfile.TemporaryDirectory() as tmpdir:
        processados = processar_ocr([t], Path(tmpdir))
    assert processados == []


def test_processar_ocr_seleciona_apenas_sem_texto_extraivel():
    """Somente sem_texto_extraivel deve ser selecionado para OCR."""
    t_sem = _texto(caminho="CCT/SP/X/a.pdf", status="sem_texto_extraivel")
    t_ok = _texto(caminho="CCT/SP/X/b.pdf", status="extraido_com_sucesso", texto="Texto.", num_caracteres=6)
    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("src.services.ocr.aplicar_ocr_pdf", return_value=("OCR text", "extraido_via_ocr")):
            processados = processar_ocr([t_sem, t_ok], Path(tmpdir))
    assert len(processados) == 1
    assert processados[0].caminho == "CCT/SP/X/a.pdf"


# ── AC2: rastreabilidade preservada ──────────────────────────────────────────

def test_ocr_preserva_campos_rastreabilidade():
    """OCR deve preservar caminho, UF, sindicato, tipo e ano do documento original."""
    t = _texto(
        caminho="CCT/MG/Metroviarios/CCT_2024-2025.pdf",
        nome_arquivo="CCT_2024-2025.pdf",
        uf="MG",
        sindicato="Metroviarios",
        tipo_documento="CCT",
        ano_referencia="2024-2025",
    )
    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("src.services.ocr.aplicar_ocr_pdf", return_value=("Texto OCR.", "extraido_via_ocr")):
            processar_ocr([t], Path(tmpdir))
    assert t.caminho == "CCT/MG/Metroviarios/CCT_2024-2025.pdf"
    assert t.nome_arquivo == "CCT_2024-2025.pdf"
    assert t.uf == "MG"
    assert t.sindicato == "Metroviarios"
    assert t.tipo_documento == "CCT"
    assert t.ano_referencia == "2024-2025"


def test_ocr_atualiza_data_processamento():
    """A data_processamento deve ser atualizada após o OCR."""
    original_data = "2025-01-01T00:00:00+00:00"
    t = _texto(data_processamento=original_data)
    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("src.services.ocr.aplicar_ocr_pdf", return_value=("Texto.", "extraido_via_ocr")):
            processar_ocr([t], Path(tmpdir))
    assert t.data_processamento != original_data
    assert "T" in t.data_processamento  # ISO 8601 format


# ── AC3: armazenamento do texto OCR ──────────────────────────────────────────

def test_ocr_com_texto_recebe_status_extraido_via_ocr():
    """OCR que reconhece texto deve resultar em extraido_via_ocr."""
    t = _texto()
    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("src.services.ocr.aplicar_ocr_pdf", return_value=("Cláusula 1: Remuneração.", "extraido_via_ocr")):
            processar_ocr([t], Path(tmpdir))
    assert t.status == "extraido_via_ocr"
    assert t.texto == "Cláusula 1: Remuneração."
    assert t.num_caracteres == len("Cláusula 1: Remuneração.")


def test_ocr_num_caracteres_consistente_com_texto():
    """num_caracteres deve ser igual a len(texto) após OCR."""
    t = _texto()
    texto_ocr = "Acordo coletivo de trabalho 2025."
    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("src.services.ocr.aplicar_ocr_pdf", return_value=(texto_ocr, "extraido_via_ocr")):
            processar_ocr([t], Path(tmpdir))
    assert t.num_caracteres == len(t.texto)


# ── AC4: OCR sem texto reconhecido ───────────────────────────────────────────

def test_ocr_sem_texto_recebe_status_ocr_sem_texto_reconhecido():
    """OCR que não reconhece texto deve resultar em ocr_sem_texto_reconhecido."""
    t = _texto()
    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("src.services.ocr.aplicar_ocr_pdf", return_value=("", "ocr_sem_texto_reconhecido")):
            processar_ocr([t], Path(tmpdir))
    assert t.status == "ocr_sem_texto_reconhecido"
    assert t.texto == ""
    assert t.num_caracteres == 0


def test_aplicar_ocr_pdf_paginas_sem_texto_retorna_ocr_sem_texto():
    """PDF processado sem erro mas sem texto deve retornar ocr_sem_texto_reconhecido."""
    with tempfile.TemporaryDirectory() as tmpdir:
        pdf_path = Path(tmpdir) / "vazio.pdf"
        pdf_path.touch()

        mock_img = MagicMock()
        with patch("src.services.ocr._DEPENDENCIAS_OCR_DISPONIVEIS", True), \
             patch("src.services.ocr.pdf2image") as mock_pdf2image, \
             patch("src.services.ocr.pytesseract") as mock_tess:
            mock_pdf2image.convert_from_path.return_value = [mock_img]
            mock_tess.image_to_string.return_value = "   \n\t  "
            texto, status = aplicar_ocr_pdf(pdf_path)

    assert status == "ocr_sem_texto_reconhecido"
    assert texto == ""


# ── AC5: tratamento de erros técnicos ────────────────────────────────────────

def test_ocr_com_erro_recebe_status_erro_no_ocr():
    """Falha técnica no OCR deve resultar em erro_no_ocr."""
    t = _texto()
    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("src.services.ocr.aplicar_ocr_pdf", return_value=("", "erro_no_ocr")):
            processar_ocr([t], Path(tmpdir))
    assert t.status == "erro_no_ocr"
    assert t.texto == ""
    assert t.num_caracteres == 0


def test_ocr_continua_apos_erro_em_um_documento():
    """Erro em um documento não deve interromper o processamento dos demais."""
    t1 = _texto(caminho="CCT/SP/X/a.pdf", nome_arquivo="a.pdf")
    t2 = _texto(caminho="CCT/RJ/Y/b.pdf", nome_arquivo="b.pdf")

    resultados = iter([
        ("", "erro_no_ocr"),
        ("Texto OCR b.", "extraido_via_ocr"),
    ])

    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("src.services.ocr.aplicar_ocr_pdf", side_effect=resultados):
            processados = processar_ocr([t1, t2], Path(tmpdir))

    assert len(processados) == 2
    assert t1.status == "erro_no_ocr"
    assert t2.status == "extraido_via_ocr"


def test_aplicar_ocr_pdf_arquivo_inexistente_retorna_erro():
    """Arquivo ausente deve retornar erro_no_ocr."""
    pdf_path = Path("/tmp/nao_existe_jamais_ocr.pdf")
    with patch("src.services.ocr._DEPENDENCIAS_OCR_DISPONIVEIS", True):
        texto, status = aplicar_ocr_pdf(pdf_path)
    assert status == "erro_no_ocr"
    assert texto == ""


def test_aplicar_ocr_pdf_dependencias_indisponiveis_retorna_erro():
    """Quando dependências não estão disponíveis, deve retornar erro_no_ocr."""
    with tempfile.TemporaryDirectory() as tmpdir:
        pdf_path = Path(tmpdir) / "test.pdf"
        pdf_path.touch()
        with patch("src.services.ocr._DEPENDENCIAS_OCR_DISPONIVEIS", False):
            texto, status = aplicar_ocr_pdf(pdf_path)
    assert status == "erro_no_ocr"
    assert texto == ""


def test_aplicar_ocr_pdf_falha_na_conversao_retorna_erro():
    """Exceção ao converter PDF em imagem deve retornar erro_no_ocr."""
    with tempfile.TemporaryDirectory() as tmpdir:
        pdf_path = Path(tmpdir) / "test.pdf"
        pdf_path.touch()
        with patch("src.services.ocr._DEPENDENCIAS_OCR_DISPONIVEIS", True), \
             patch("src.services.ocr.pdf2image") as mock_pdf2image:
            mock_pdf2image.convert_from_path.side_effect = Exception("Poppler error")
            texto, status = aplicar_ocr_pdf(pdf_path)
    assert status == "erro_no_ocr"
    assert texto == ""


def test_aplicar_ocr_pdf_todas_paginas_com_erro_retorna_erro():
    """Quando todas as páginas falham no OCR, deve retornar erro_no_ocr."""
    with tempfile.TemporaryDirectory() as tmpdir:
        pdf_path = Path(tmpdir) / "test.pdf"
        pdf_path.touch()
        mock_img = MagicMock()
        with patch("src.services.ocr._DEPENDENCIAS_OCR_DISPONIVEIS", True), \
             patch("src.services.ocr.pdf2image") as mock_pdf2image, \
             patch("src.services.ocr.pytesseract") as mock_tess:
            mock_pdf2image.convert_from_path.return_value = [mock_img, mock_img]
            mock_tess.image_to_string.side_effect = Exception("Tesseract error")
            texto, status = aplicar_ocr_pdf(pdf_path)
    assert status == "erro_no_ocr"
    assert texto == ""


def test_aplicar_ocr_pdf_pagina_parcial_com_texto_retorna_extraido():
    """Uma página com erro e outra com texto deve retornar extraido_via_ocr."""
    with tempfile.TemporaryDirectory() as tmpdir:
        pdf_path = Path(tmpdir) / "test.pdf"
        pdf_path.touch()
        mock_img = MagicMock()
        with patch("src.services.ocr._DEPENDENCIAS_OCR_DISPONIVEIS", True), \
             patch("src.services.ocr.pdf2image") as mock_pdf2image, \
             patch("src.services.ocr.pytesseract") as mock_tess:
            mock_pdf2image.convert_from_path.return_value = [mock_img, mock_img]
            mock_tess.image_to_string.side_effect = ["Texto da página 1.", Exception("erro")]
            texto, status = aplicar_ocr_pdf(pdf_path)
    assert status == "extraido_via_ocr"
    assert "Texto da página 1." in texto


def test_aplicar_ocr_pdf_pagina_parcial_sem_texto_retorna_erro():
    """Uma página com erro técnico e outras sem texto: deve retornar erro_no_ocr."""
    with tempfile.TemporaryDirectory() as tmpdir:
        pdf_path = Path(tmpdir) / "test.pdf"
        pdf_path.touch()
        mock_img = MagicMock()
        with patch("src.services.ocr._DEPENDENCIAS_OCR_DISPONIVEIS", True), \
             patch("src.services.ocr.pdf2image") as mock_pdf2image, \
             patch("src.services.ocr.pytesseract") as mock_tess:
            mock_pdf2image.convert_from_path.return_value = [mock_img, mock_img]
            mock_tess.image_to_string.side_effect = ["   ", Exception("erro")]
            texto, status = aplicar_ocr_pdf(pdf_path)
    assert status == "erro_no_ocr"
    assert texto == ""


# ── AC6: relatório consolidado ────────────────────────────────────────────────

def test_relatorio_ocr_soma_igual_ao_total():
    """A soma dos três contadores deve ser igual ao total de documentos avaliados."""
    processados = [
        _texto(caminho="a.pdf", status="extraido_via_ocr", texto="Texto.", num_caracteres=6),
        _texto(caminho="b.pdf", status="ocr_sem_texto_reconhecido"),
        _texto(caminho="c.pdf", status="erro_no_ocr"),
    ]
    capturado = []
    with patch("builtins.print", side_effect=lambda *a, **kw: capturado.append(" ".join(str(x) for x in a))):
        imprimir_relatorio_ocr(processados)

    conteudo = "\n".join(capturado)
    assert "3" in conteudo
    assert "✓" in conteudo


def test_relatorio_ocr_contadores_corretos():
    """Os contadores individuais devem refletir os status dos documentos."""
    processados = [
        _texto(caminho="a.pdf", status="extraido_via_ocr", texto="Texto.", num_caracteres=6),
        _texto(caminho="b.pdf", status="extraido_via_ocr", texto="Mais.", num_caracteres=5),
        _texto(caminho="c.pdf", status="ocr_sem_texto_reconhecido"),
        _texto(caminho="d.pdf", status="erro_no_ocr"),
    ]
    capturado = []
    with patch("builtins.print", side_effect=lambda *a, **kw: capturado.append(" ".join(str(x) for x in a))):
        imprimir_relatorio_ocr(processados)

    conteudo = "\n".join(capturado)
    assert "✓" in conteudo
    assert "4" in conteudo


def test_relatorio_ocr_com_lista_vazia():
    """Relatório com lista vazia deve exibir zeros e soma consistente."""
    capturado = []
    with patch("builtins.print", side_effect=lambda *a, **kw: capturado.append(" ".join(str(x) for x in a))):
        imprimir_relatorio_ocr([])

    conteudo = "\n".join(capturado)
    assert "✓" in conteudo
    assert "0" in conteudo


# ── runner ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import traceback

    tests = [name for name, obj in list(globals().items()) if name.startswith("test_")]
    passed = 0
    failed = 0
    for name in tests:
        try:
            globals()[name]()
            print(f"  ✓ {name}")
            passed += 1
        except AssertionError as e:
            print(f"  ✗ {name}: {e}")
            traceback.print_exc()
            failed += 1
        except Exception as e:
            print(f"  ✗ {name}: {type(e).__name__}: {e}")
            traceback.print_exc()
            failed += 1

    print(f"\n{passed} passou(ram), {failed} falhou(aram)")
    sys.exit(0 if failed == 0 else 1)

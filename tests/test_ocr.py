"""Testes para o serviço de OCR (ocr.py).

Cobre os critérios de aceitação da US-PRJ-4:
  AC3 — status extraido_via_ocr quando OCR reconhece texto
  AC4 — status ocr_sem_texto_reconhecido quando OCR não encontra texto
  AC5 — status erro_no_ocr em falhas técnicas, sem interrupção do processamento
"""

from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

import src.services.ocr as ocr_module
from src.services.ocr import ocr_pdf


class TestOcrPdf:
    def test_retorna_erro_quando_pdf2image_indisponivel(self, tmp_path):
        pdf = tmp_path / "doc.pdf"
        pdf.touch()
        with patch.object(ocr_module, "_PDF2IMAGE_DISPONIVEL", False):
            texto, status = ocr_pdf(pdf)
        assert texto == ""
        assert status == "erro_no_ocr"

    def test_retorna_erro_quando_pytesseract_indisponivel(self, tmp_path):
        pdf = tmp_path / "doc.pdf"
        pdf.touch()
        with patch.object(ocr_module, "_PDF2IMAGE_DISPONIVEL", True), \
             patch.object(ocr_module, "_PYTESSERACT_DISPONIVEL", False):
            texto, status = ocr_pdf(pdf)
        assert texto == ""
        assert status == "erro_no_ocr"

    def test_retorna_erro_quando_arquivo_ausente(self, tmp_path):
        pdf = tmp_path / "inexistente.pdf"
        with patch.object(ocr_module, "_PDF2IMAGE_DISPONIVEL", True), \
             patch.object(ocr_module, "_PYTESSERACT_DISPONIVEL", True):
            texto, status = ocr_pdf(pdf)
        assert texto == ""
        assert status == "erro_no_ocr"

    def test_retorna_erro_quando_convert_falha(self, tmp_path):
        pdf = tmp_path / "doc.pdf"
        pdf.touch()
        with patch.object(ocr_module, "_PDF2IMAGE_DISPONIVEL", True), \
             patch.object(ocr_module, "_PYTESSERACT_DISPONIVEL", True), \
             patch.object(ocr_module, "convert_from_path", side_effect=Exception("falha")):
            texto, status = ocr_pdf(pdf)
        assert texto == ""
        assert status == "erro_no_ocr"

    def test_retorna_texto_quando_ocr_sucesso(self, tmp_path):
        pdf = tmp_path / "doc.pdf"
        pdf.touch()
        imagem_mock = MagicMock()
        mock_tesseract = MagicMock()
        mock_tesseract.image_to_string.return_value = "Texto extraído"

        with patch.object(ocr_module, "_PDF2IMAGE_DISPONIVEL", True), \
             patch.object(ocr_module, "_PYTESSERACT_DISPONIVEL", True), \
             patch.object(ocr_module, "convert_from_path", return_value=[imagem_mock]), \
             patch.object(ocr_module, "pytesseract", mock_tesseract):
            texto, status = ocr_pdf(pdf)

        assert "Texto extraído" in texto
        assert status == "extraido_via_ocr"

    def test_retorna_ocr_sem_texto_quando_ocr_vazio(self, tmp_path):
        pdf = tmp_path / "doc.pdf"
        pdf.touch()
        imagem_mock = MagicMock()
        mock_tesseract = MagicMock()
        mock_tesseract.image_to_string.return_value = "   "

        with patch.object(ocr_module, "_PDF2IMAGE_DISPONIVEL", True), \
             patch.object(ocr_module, "_PYTESSERACT_DISPONIVEL", True), \
             patch.object(ocr_module, "convert_from_path", return_value=[imagem_mock]), \
             patch.object(ocr_module, "pytesseract", mock_tesseract):
            texto, status = ocr_pdf(pdf)

        assert texto == ""
        assert status == "ocr_sem_texto_reconhecido"

    def test_pagina_com_excecao_e_ignorada(self, tmp_path):
        """Página que lança exceção no Tesseract não impede as demais."""
        pdf = tmp_path / "doc.pdf"
        pdf.touch()
        imagem_boa = MagicMock()
        imagem_ruim = MagicMock()

        mock_tesseract = MagicMock()

        def tesseract_side_effect(img, lang):
            if img is imagem_ruim:
                raise RuntimeError("falha na página")
            return "Texto válido"

        mock_tesseract.image_to_string.side_effect = tesseract_side_effect

        with patch.object(ocr_module, "_PDF2IMAGE_DISPONIVEL", True), \
             patch.object(ocr_module, "_PYTESSERACT_DISPONIVEL", True), \
             patch.object(ocr_module, "convert_from_path", return_value=[imagem_ruim, imagem_boa]), \
             patch.object(ocr_module, "pytesseract", mock_tesseract):
            texto, status = ocr_pdf(pdf)

        assert "Texto válido" in texto
        assert status == "extraido_via_ocr"

    def test_todas_paginas_com_excecao_retorna_erro_no_ocr(self, tmp_path):
        """Quando todas as páginas falham no Tesseract, deve retornar erro_no_ocr."""
        pdf = tmp_path / "doc.pdf"
        pdf.touch()
        imagem_mock = MagicMock()

        mock_tesseract = MagicMock()
        mock_tesseract.image_to_string.side_effect = RuntimeError("falha total")

        with patch.object(ocr_module, "_PDF2IMAGE_DISPONIVEL", True), \
             patch.object(ocr_module, "_PYTESSERACT_DISPONIVEL", True), \
             patch.object(ocr_module, "convert_from_path", return_value=[imagem_mock, imagem_mock]), \
             patch.object(ocr_module, "pytesseract", mock_tesseract):
            texto, status = ocr_pdf(pdf)

        assert texto == ""
        assert status == "erro_no_ocr"

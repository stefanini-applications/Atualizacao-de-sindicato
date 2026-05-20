"""Testes para o serviço de OCR (ocr.py)."""

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
        assert status == "erro_na_leitura"

    def test_retorna_erro_quando_pytesseract_indisponivel(self, tmp_path):
        pdf = tmp_path / "doc.pdf"
        pdf.touch()
        with patch.object(ocr_module, "_PDF2IMAGE_DISPONIVEL", True), \
             patch.object(ocr_module, "_PYTESSERACT_DISPONIVEL", False):
            texto, status = ocr_pdf(pdf)
        assert texto == ""
        assert status == "erro_na_leitura"

    def test_retorna_nao_encontrado_quando_arquivo_ausente(self, tmp_path):
        pdf = tmp_path / "inexistente.pdf"
        with patch.object(ocr_module, "_PDF2IMAGE_DISPONIVEL", True), \
             patch.object(ocr_module, "_PYTESSERACT_DISPONIVEL", True):
            texto, status = ocr_pdf(pdf)
        assert texto == ""
        assert status == "documento_nao_encontrado"

    def test_retorna_erro_quando_convert_falha(self, tmp_path):
        pdf = tmp_path / "doc.pdf"
        pdf.touch()
        with patch.object(ocr_module, "_PDF2IMAGE_DISPONIVEL", True), \
             patch.object(ocr_module, "_PYTESSERACT_DISPONIVEL", True), \
             patch("src.services.ocr.convert_from_path", side_effect=Exception("falha")):
            texto, status = ocr_pdf(pdf)
        assert texto == ""
        assert status == "erro_na_leitura"

    def test_retorna_texto_quando_ocr_sucesso(self, tmp_path):
        pdf = tmp_path / "doc.pdf"
        pdf.touch()
        imagem_mock = MagicMock()

        with patch.object(ocr_module, "_PDF2IMAGE_DISPONIVEL", True), \
             patch.object(ocr_module, "_PYTESSERACT_DISPONIVEL", True), \
             patch("src.services.ocr.convert_from_path", return_value=[imagem_mock]), \
             patch("src.services.ocr.pytesseract.image_to_string", return_value="Texto extraído"):
            texto, status = ocr_pdf(pdf)

        assert "Texto extraído" in texto
        assert status == "extraido_com_sucesso"

    def test_retorna_sem_texto_extraivel_quando_ocr_vazio(self, tmp_path):
        pdf = tmp_path / "doc.pdf"
        pdf.touch()
        imagem_mock = MagicMock()

        with patch.object(ocr_module, "_PDF2IMAGE_DISPONIVEL", True), \
             patch.object(ocr_module, "_PYTESSERACT_DISPONIVEL", True), \
             patch("src.services.ocr.convert_from_path", return_value=[imagem_mock]), \
             patch("src.services.ocr.pytesseract.image_to_string", return_value="   "):
            texto, status = ocr_pdf(pdf)

        assert texto == ""
        assert status == "sem_texto_extraivel"

    def test_pagina_com_excecao_e_ignorada(self, tmp_path):
        """Página que lança exceção no Tesseract não impede as demais."""
        pdf = tmp_path / "doc.pdf"
        pdf.touch()
        imagem_boa = MagicMock()
        imagem_ruim = MagicMock()

        def tesseract_side_effect(img, lang):
            if img is imagem_ruim:
                raise RuntimeError("falha na página")
            return "Texto válido"

        with patch.object(ocr_module, "_PDF2IMAGE_DISPONIVEL", True), \
             patch.object(ocr_module, "_PYTESSERACT_DISPONIVEL", True), \
             patch("src.services.ocr.convert_from_path", return_value=[imagem_ruim, imagem_boa]), \
             patch("src.services.ocr.pytesseract.image_to_string", side_effect=tesseract_side_effect):
            texto, status = ocr_pdf(pdf)

        assert "Texto válido" in texto
        assert status == "extraido_com_sucesso"

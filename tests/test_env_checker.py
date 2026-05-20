"""Testes para verificação de ambiente OCR (env_checker)."""

import sys
from unittest.mock import patch, MagicMock

import pytest

from src.services.env_checker import (
    ResultadoVerificacao,
    verificar_ambiente_ocr,
    imprimir_resultado_verificacao,
)


# ---------------------------------------------------------------------------
# ResultadoVerificacao
# ---------------------------------------------------------------------------

class TestResultadoVerificacao:
    def test_ok_por_padrao(self):
        r = ResultadoVerificacao()
        assert r.ok is True
        assert r.erros == []
        assert r.avisos == []

    def test_registrar_erro_marca_nok(self):
        r = ResultadoVerificacao()
        r.registrar_erro("falha X")
        assert r.ok is False
        assert "falha X" in r.erros

    def test_registrar_aviso_nao_altera_ok(self):
        r = ResultadoVerificacao()
        r.registrar_aviso("aviso Y")
        assert r.ok is True
        assert "aviso Y" in r.avisos


# ---------------------------------------------------------------------------
# verificar_ambiente_ocr — ambiente completo (tudo presente)
# ---------------------------------------------------------------------------

def _mock_completo():
    """Retorna mocks que simulam ambiente completo."""
    return {
        "shutil.which": lambda cmd: f"/usr/bin/{cmd}",
        "subprocess.run": MagicMock(return_value=MagicMock(
            stdout="List of available languages:\npor\neng\n",
            stderr="",
        )),
        "builtins.__import__": None,  # pytesseract e pdf2image disponíveis
    }


class TestVerificarAmbienteOcrCompleto:
    def test_ambiente_completo_retorna_ok(self):
        proc_mock = MagicMock()
        proc_mock.stdout = "List of available languages:\npor\neng\n"
        proc_mock.stderr = ""

        with patch("src.services.env_checker.shutil.which", return_value="/usr/bin/tesseract"), \
             patch("src.services.env_checker.subprocess.run", return_value=proc_mock), \
             patch("builtins.__import__", wraps=__import__):
            resultado = verificar_ambiente_ocr()

        assert resultado.ok is True
        assert resultado.erros == []


# ---------------------------------------------------------------------------
# verificar_ambiente_ocr — dependências ausentes
# ---------------------------------------------------------------------------

class TestVerificarAmbienteOcrFalhas:
    def test_tesseract_ausente(self):
        with patch("src.services.env_checker.shutil.which", side_effect=lambda cmd: None if cmd == "tesseract" else "/usr/bin/pdftoppm"), \
             patch("builtins.__import__", wraps=__import__):
            resultado = verificar_ambiente_ocr()

        assert not resultado.ok
        assert any("Tesseract" in e for e in resultado.erros)

    def test_idioma_por_ausente(self):
        proc_mock = MagicMock()
        proc_mock.stdout = "List of available languages:\neng\n"
        proc_mock.stderr = ""

        with patch("src.services.env_checker.shutil.which", return_value="/usr/bin/tesseract"), \
             patch("src.services.env_checker.subprocess.run", return_value=proc_mock), \
             patch("builtins.__import__", wraps=__import__):
            resultado = verificar_ambiente_ocr()

        assert not resultado.ok
        assert any("por" in e for e in resultado.erros)

    def test_poppler_ausente(self):
        proc_mock = MagicMock()
        proc_mock.stdout = "List of available languages:\npor\neng\n"
        proc_mock.stderr = ""

        with patch("src.services.env_checker.shutil.which", side_effect=lambda cmd: "/usr/bin/tesseract" if cmd == "tesseract" else None), \
             patch("src.services.env_checker.subprocess.run", return_value=proc_mock), \
             patch("builtins.__import__", wraps=__import__):
            resultado = verificar_ambiente_ocr()

        assert not resultado.ok
        assert any("Poppler" in e or "pdftoppm" in e for e in resultado.erros)

    def test_pytesseract_ausente(self):
        proc_mock = MagicMock()
        proc_mock.stdout = "List of available languages:\npor\neng\n"
        proc_mock.stderr = ""

        original_import = __import__

        def import_mock(name, *args, **kwargs):
            if name == "pytesseract":
                raise ImportError("No module named 'pytesseract'")
            return original_import(name, *args, **kwargs)

        with patch("src.services.env_checker.shutil.which", return_value="/usr/bin/tesseract"), \
             patch("src.services.env_checker.subprocess.run", return_value=proc_mock), \
             patch("builtins.__import__", side_effect=import_mock):
            resultado = verificar_ambiente_ocr()

        assert not resultado.ok
        assert any("pytesseract" in e for e in resultado.erros)

    def test_pdf2image_ausente(self):
        proc_mock = MagicMock()
        proc_mock.stdout = "List of available languages:\npor\neng\n"
        proc_mock.stderr = ""

        original_import = __import__

        def import_mock(name, *args, **kwargs):
            if name == "pdf2image":
                raise ImportError("No module named 'pdf2image'")
            return original_import(name, *args, **kwargs)

        with patch("src.services.env_checker.shutil.which", return_value="/usr/bin/tesseract"), \
             patch("src.services.env_checker.subprocess.run", return_value=proc_mock), \
             patch("builtins.__import__", side_effect=import_mock):
            resultado = verificar_ambiente_ocr()

        assert not resultado.ok
        assert any("pdf2image" in e for e in resultado.erros)

    def test_multiplas_dependencias_ausentes_geram_multiplos_erros(self):
        with patch("src.services.env_checker.shutil.which", return_value=None):
            resultado = verificar_ambiente_ocr()

        assert not resultado.ok
        assert len(resultado.erros) >= 2


# ---------------------------------------------------------------------------
# imprimir_resultado_verificacao
# ---------------------------------------------------------------------------

class TestImprimirResultado:
    def test_imprime_sucesso_quando_ok(self, capsys):
        r = ResultadoVerificacao()
        imprimir_resultado_verificacao(r)
        out = capsys.readouterr().out
        assert "✔" in out

    def test_imprime_erros_quando_nok(self, capsys):
        r = ResultadoVerificacao()
        r.registrar_erro("Tesseract não encontrado")
        imprimir_resultado_verificacao(r)
        err = capsys.readouterr().err
        assert "Tesseract não encontrado" in err

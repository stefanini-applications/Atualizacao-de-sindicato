"""Verificação de dependências de sistema e Python necessárias para o pipeline de OCR.

Verifica:
  - Tesseract OCR instalado e acessível
  - Idioma português (por) disponível no Tesseract
  - Poppler (pdftoppm) instalado e acessível
  - Pacotes Python pytesseract e pdf2image instalados
"""

import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from typing import List


@dataclass
class ResultadoVerificacao:
    """Resultado agregado da verificação de ambiente para OCR."""

    ok: bool = True
    erros: List[str] = field(default_factory=list)
    avisos: List[str] = field(default_factory=list)

    def registrar_erro(self, mensagem: str) -> None:
        self.ok = False
        self.erros.append(mensagem)

    def registrar_aviso(self, mensagem: str) -> None:
        self.avisos.append(mensagem)


def _verificar_tesseract(resultado: ResultadoVerificacao) -> None:
    if not shutil.which("tesseract"):
        resultado.registrar_erro(
            "Tesseract OCR não encontrado. "
            "Instale com: sudo apt-get install tesseract-ocr"
        )
        return

    try:
        proc = subprocess.run(
            ["tesseract", "--list-langs"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        saida = proc.stdout + proc.stderr
        if "por" not in saida.splitlines():
            resultado.registrar_erro(
                "Idioma português (por) não encontrado no Tesseract. "
                "Instale com: sudo apt-get install tesseract-ocr-por"
            )
    except Exception as exc:
        resultado.registrar_erro(
            f"Erro ao consultar idiomas do Tesseract: {exc}. "
            "Verifique se o Tesseract está instalado corretamente."
        )


def _verificar_poppler(resultado: ResultadoVerificacao) -> None:
    if not shutil.which("pdftoppm"):
        resultado.registrar_erro(
            "Poppler (pdftoppm) não encontrado. "
            "Instale com: sudo apt-get install poppler-utils"
        )


def _verificar_pacote_python(nome: str, resultado: ResultadoVerificacao) -> None:
    try:
        __import__(nome)
    except ImportError:
        resultado.registrar_erro(
            f"Pacote Python '{nome}' não instalado. "
            f"Instale com: pip install {nome}"
        )


def verificar_ambiente_ocr() -> ResultadoVerificacao:
    """Executa todas as verificações e retorna o resultado consolidado."""
    resultado = ResultadoVerificacao()
    _verificar_tesseract(resultado)
    _verificar_poppler(resultado)
    _verificar_pacote_python("pytesseract", resultado)
    _verificar_pacote_python("pdf2image", resultado)
    return resultado


def imprimir_resultado_verificacao(resultado: ResultadoVerificacao) -> None:
    """Exibe o resultado da verificação de ambiente no terminal."""
    if resultado.ok:
        print("✔  Ambiente OCR configurado corretamente.")
        print("   Tesseract, idioma 'por', Poppler e pacotes Python estão disponíveis.")
    else:
        print("✘  Dependências ausentes para execução do OCR:\n", file=sys.stderr)
        for erro in resultado.erros:
            print(f"   • {erro}", file=sys.stderr)
        print(file=sys.stderr)
    for aviso in resultado.avisos:
        print(f"⚠  {aviso}")

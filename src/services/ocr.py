"""Serviço de OCR para PDFs classificados como sem_texto_extraivel.

Responsabilidades:
  - Converter páginas de PDF em imagem com pdf2image (requer Poppler).
  - Aplicar Tesseract OCR com idioma português (por) em cada página.
  - Retornar texto extraído e status de extração (STATUS_OCR).
  - Nunca lançar exceção não tratada; falhas são capturadas e registradas.

Status retornados:
  extraido_via_ocr          — OCR reconheceu texto útil.
  ocr_sem_texto_reconhecido — OCR executou sem erros, mas não reconheceu texto.
  erro_no_ocr               — Falha técnica durante conversão, leitura ou OCR.
"""

from pathlib import Path
from typing import Tuple

try:
    from pdf2image import convert_from_path
    _PDF2IMAGE_DISPONIVEL = True
except ImportError:
    convert_from_path = None  # type: ignore[assignment]
    _PDF2IMAGE_DISPONIVEL = False

try:
    import pytesseract
    _PYTESSERACT_DISPONIVEL = True
except ImportError:
    pytesseract = None  # type: ignore[assignment]
    _PYTESSERACT_DISPONIVEL = False


def ocr_pdf(pdf_path: Path, lang: str = "por") -> Tuple[str, str]:
    """Executa OCR em todas as páginas de um PDF e retorna (texto, status).

    Requer pdf2image (Poppler) e pytesseract (Tesseract com idioma `lang`).
    Status retornados: extraido_via_ocr | ocr_sem_texto_reconhecido | erro_no_ocr.
    """
    if not _PDF2IMAGE_DISPONIVEL:
        return "", "erro_no_ocr"
    if not _PYTESSERACT_DISPONIVEL:
        return "", "erro_no_ocr"
    if not pdf_path.exists():
        return "", "erro_no_ocr"

    try:
        imagens = convert_from_path(str(pdf_path))
    except Exception:
        return "", "erro_no_ocr"

    partes: list = []
    teve_erro_de_pagina = False
    for imagem in imagens:
        try:
            trecho = pytesseract.image_to_string(imagem, lang=lang)
            partes.append(trecho)
        except Exception:
            teve_erro_de_pagina = True

    texto = "\n".join(partes)
    if texto.strip():
        return texto, "extraido_via_ocr"
    if teve_erro_de_pagina:
        return "", "erro_no_ocr"
    return "", "ocr_sem_texto_reconhecido"

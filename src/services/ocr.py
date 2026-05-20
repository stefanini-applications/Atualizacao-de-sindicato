"""Serviço de OCR para PDFs classificados como sem_texto_extraivel.

Responsabilidades:
  - Converter páginas de PDF em imagem com pdf2image (requer Poppler).
  - Aplicar Tesseract OCR com idioma português (por) em cada página.
  - Retornar texto extraído e status de extração.
  - Nunca lançar exceção não tratada; falhas são capturadas e registradas.
"""

from pathlib import Path
from typing import Tuple

try:
    from pdf2image import convert_from_path
    _PDF2IMAGE_DISPONIVEL = True
except ImportError:
    _PDF2IMAGE_DISPONIVEL = False

try:
    import pytesseract
    _PYTESSERACT_DISPONIVEL = True
except ImportError:
    _PYTESSERACT_DISPONIVEL = False


def ocr_pdf(pdf_path: Path, lang: str = "por") -> Tuple[str, str]:
    """Executa OCR em todas as páginas de um PDF e retorna (texto, status).

    Requer pdf2image (Poppler) e pytesseract (Tesseract com idioma `lang`).
    """
    if not _PDF2IMAGE_DISPONIVEL:
        return "", "erro_na_leitura"
    if not _PYTESSERACT_DISPONIVEL:
        return "", "erro_na_leitura"
    if not pdf_path.exists():
        return "", "documento_nao_encontrado"

    try:
        imagens = convert_from_path(str(pdf_path))
    except Exception:
        return "", "erro_na_leitura"

    partes = []
    for imagem in imagens:
        try:
            trecho = pytesseract.image_to_string(imagem, lang=lang)
            partes.append(trecho)
        except Exception:
            pass

    texto = "\n".join(partes)
    if texto.strip():
        return texto, "extraido_com_sucesso"
    return "", "sem_texto_extraivel"

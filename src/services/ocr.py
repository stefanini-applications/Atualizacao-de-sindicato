"""Extração de texto via OCR em PDFs sindicais escaneados.

Responsabilidades:
  - Converter páginas de PDF em imagem com pdf2image/Poppler.
  - Aplicar OCR (pytesseract/Tesseract) para reconhecer texto das imagens.
  - Atualizar registros com status `sem_texto_extraivel` na base de textos
    extraídos, atribuindo um dos três status de OCR a cada documento.
  - Nunca lançar exceção não tratada; falhas técnicas são capturadas e
    registradas como `erro_no_ocr`.

Status de saída possíveis:
  extraido_via_ocr          — OCR reconheceu ao menos um caractere útil
  ocr_sem_texto_reconhecido — OCR executou sem erro, mas não encontrou texto
  erro_no_ocr               — falha técnica ao converter páginas ou executar OCR

Dependências externas obrigatórias (além dos pacotes Python):
  - Tesseract OCR  (apt install tesseract-ocr)
  - Dados de língua portuguesa  (apt install tesseract-ocr-por)
  - Poppler utilities  (apt install poppler-utils)
"""

from datetime import datetime, timezone
from pathlib import Path
from typing import List, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    pass

from src.models.texto_extraido import TextoExtraido

try:
    import pdf2image
    import pytesseract
    _DEPENDENCIAS_OCR_DISPONIVEIS = True
except ImportError:
    _DEPENDENCIAS_OCR_DISPONIVEIS = False

_LANG_OCR = "por"


def aplicar_ocr_pdf(pdf_path: Path) -> Tuple[str, str]:
    """Converte as páginas do PDF em imagem e aplica OCR, retornando (texto, status).

    Trata falhas por arquivo e por página sem propagar exceções.
    """
    if not _DEPENDENCIAS_OCR_DISPONIVEIS:
        return "", "erro_no_ocr"

    if not pdf_path.exists():
        return "", "erro_no_ocr"

    try:
        imagens = pdf2image.convert_from_path(str(pdf_path))
    except Exception:
        return "", "erro_no_ocr"

    partes: List[str] = []
    pagina_falhou = False

    for img in imagens:
        try:
            trecho = pytesseract.image_to_string(img, lang=_LANG_OCR)
            partes.append(trecho)
        except Exception:
            pagina_falhou = True

    texto_completo = "\n".join(partes)

    if texto_completo.strip():
        return texto_completo, "extraido_via_ocr"
    if pagina_falhou:
        return "", "erro_no_ocr"
    return "", "ocr_sem_texto_reconhecido"


def processar_ocr(textos: List[TextoExtraido], raiz: Path) -> List[TextoExtraido]:
    """Aplica OCR a todos os documentos com status `sem_texto_extraivel`.

    Atualiza os objetos TextoExtraido em vigor (mutação direta) e retorna
    o subconjunto processado para uso no relatório.
    """
    processados: List[TextoExtraido] = []

    for t in textos:
        if t.status != "sem_texto_extraivel":
            continue

        pdf_path = raiz / t.caminho
        texto, status = aplicar_ocr_pdf(pdf_path)
        agora = datetime.now(tz=timezone.utc).isoformat()

        t.texto = texto
        t.num_caracteres = len(texto)
        t.status = status
        t.data_processamento = agora

        processados.append(t)

    return processados

"""Relatório consolidado do processamento OCR de PDFs sindicais.

Exibe os três contadores de status de OCR e valida que a soma
é igual ao total de documentos avaliados — conforme AC6.
"""

from typing import List

from src.models.texto_extraido import TextoExtraido, STATUS_OCR

_STATUS_ORDENADOS = [
    "extraido_via_ocr",
    "ocr_sem_texto_reconhecido",
    "erro_no_ocr",
]

_LABELS = {
    "extraido_via_ocr":           "Extraído via OCR          ",
    "ocr_sem_texto_reconhecido":  "OCR sem texto reconhecido ",
    "erro_no_ocr":                "Erro no OCR               ",
}


def imprimir_relatorio_ocr(textos: List[TextoExtraido]) -> None:
    """Imprime resumo do OCR com os três contadores de status (AC6)."""
    total = len(textos)

    contadores = {s: 0 for s in _STATUS_ORDENADOS}
    for t in textos:
        if t.status in contadores:
            contadores[t.status] += 1

    soma = sum(contadores.values())

    print("\n=== Relatório de OCR ===")
    print(f"  Total de documentos avaliados para OCR : {total}")
    print()
    for status in _STATUS_ORDENADOS:
        label = _LABELS.get(status, status)
        print(f"  {label}: {contadores[status]}")
    print()

    if soma != total:
        print(f"  ⚠  Inconsistência: soma dos contadores ({soma}) ≠ total ({total})")
    else:
        print(f"  ✓  Soma dos contadores ({soma}) = total ({total})")
    print()

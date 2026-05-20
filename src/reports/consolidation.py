"""Relatório de consolidação da base textual dos documentos sindicais.

Exibe os quatro contadores de status consolidado e valida que a soma
é igual ao total de documentos avaliados — conforme AC5.
"""

from typing import List

from src.models.texto_extraido import TextoConsolidado, STATUS_CONSOLIDACAO

_STATUS_ORDENADOS = [
    "texto_nativo",
    "texto_ocr",
    "sem_texto_final",
    "erro_consolidacao",
]

_LABELS = {
    "texto_nativo":      "Texto nativo              ",
    "texto_ocr":         "Texto OCR                 ",
    "sem_texto_final":   "Sem texto final           ",
    "erro_consolidacao": "Erro de consolidação      ",
}


def imprimir_relatorio_consolidacao(
    textos: List[TextoConsolidado],
    ocr_disponivel: bool = True,
) -> None:
    """Imprime resumo da consolidação com os quatro contadores de status (AC5)."""
    total = len(textos)

    contadores = {s: 0 for s in _STATUS_ORDENADOS}
    for t in textos:
        if t.status_consolidado in contadores:
            contadores[t.status_consolidado] += 1

    soma = sum(contadores.values())

    print("\n=== Relatório de Consolidação Textual ===")
    if not ocr_disponivel:
        print("  ⚠  Base OCR não encontrada — complementação via OCR ignorada.")
    print(f"  Total de documentos avaliados : {total}")
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

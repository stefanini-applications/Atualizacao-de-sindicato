"""Relatório consolidado da extração de texto de PDFs sindicais.

Exibe os cinco contadores de status obrigatórios e valida que a soma
é igual ao total de documentos avaliados — conforme AC5.
"""

from typing import List

from src.models.texto_extraido import TextoExtraido, STATUS_EXTRACAO

_STATUS_ORDENADOS = [
    "extraido_com_sucesso",
    "sem_texto_extraivel",
    "erro_na_leitura",
    "documento_nao_encontrado",
    "nao_elegivel_para_extracao",
]

_LABELS = {
    "extraido_com_sucesso":      "Extraído com sucesso      ",
    "sem_texto_extraivel":       "Sem texto extraível       ",
    "erro_na_leitura":           "Erro na leitura           ",
    "documento_nao_encontrado":  "Documento não encontrado  ",
    "nao_elegivel_para_extracao": "Não elegível p/ extração  ",
}


def imprimir_relatorio_extracao(textos: List[TextoExtraido]) -> None:
    """Imprime resumo da extração com os cinco contadores de status (AC5)."""
    total = len(textos)

    contadores = {s: 0 for s in _STATUS_ORDENADOS}
    for t in textos:
        if t.status in contadores:
            contadores[t.status] += 1

    soma = sum(contadores.values())

    print("\n=== Relatório de Extração de Texto ===")
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

"""Relatório da prévia de atualização de pricing.

Exibe o total de linhas avaliadas, o total por valor de ``status_aplicacao``
e confirma que a soma dos totais por status é igual ao total avaliado — AC5.
"""

from collections import Counter
from typing import List

from src.models.linha_preview_pricing import LinhaPreviewPricing


def imprimir_relatorio_preview(linhas: List[LinhaPreviewPricing]) -> None:
    """Imprime relatório consolidado da prévia de atualização de pricing (AC5)."""
    total = len(linhas)
    contagem = Counter(l.status_aplicacao for l in linhas)

    print("\n=== Relatório de Prévia de Atualização de Pricing ===")
    print(f"  Total de linhas avaliadas: {total}")
    print()
    print("  Resultado por status:")

    soma = 0
    for status, count in sorted(contagem.items()):
        print(f"    {status:<35}: {count}")
        soma += count

    print()
    confirmacao = "✔ OK" if soma == total else f"✘ DIVERGÊNCIA (soma={soma}, total={total})"
    print(f"  Soma dos totais por status = total avaliado: {confirmacao}")
    print()

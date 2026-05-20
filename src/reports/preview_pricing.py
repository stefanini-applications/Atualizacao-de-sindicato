"""Relatório de simulação de aplicação de reajustes à base de pricing.

Exibe o total de linhas avaliadas, o total por cada valor de status_aplicacao
e a confirmação de que a soma dos totais por status é igual ao total avaliado — AC5.
"""

from typing import Dict

_STATUS_ORDEM = [
    "reajuste_encontrado",
    "sem_correspondencia",
    "multiplas_correspondencias",
    "dados_insuficientes",
    "erro_aplicacao",
]


def imprimir_relatorio_preview(
    total_avaliadas: int,
    contagens_por_status: Dict[str, int],
) -> None:
    """Imprime relatório de simulação da prévia de pricing (AC5)."""
    print("\n=== Relatório de Simulação — Prévia de Atualização de Pricing ===")
    print(f"  Total de linhas avaliadas         : {total_avaliadas}")
    print()
    print("  Resultado por status:")

    soma = 0
    for status in _STATUS_ORDEM:
        contagem = contagens_por_status.get(status, 0)
        soma += contagem
        print(f"    {status:<35}: {contagem}")

    for status in sorted(contagens_por_status):
        if status not in _STATUS_ORDEM:
            contagem = contagens_por_status[status]
            soma += contagem
            print(f"    {status:<35}: {contagem}")

    print()
    confirmacao = "✔" if soma == total_avaliadas else "✘ DIVERGÊNCIA"
    print(f"  Soma dos totais por status        : {soma} {confirmacao}")
    print()

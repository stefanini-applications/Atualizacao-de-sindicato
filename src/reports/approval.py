"""Relatório de geração da base final de reajustes aprovados.

Exibe totais de registros avaliados, aprovados incluídos, ignorados por status
e com valores corrigidos aplicados — AC5.
"""


def imprimir_relatorio_aprovacao(
    total_avaliados: int,
    total_aprovados: int,
    total_ignorados: int,
    total_com_correcao: int,
) -> None:
    """Imprime relatório consolidado da geração de reajustes aprovados (AC5)."""
    print("\n=== Relatório de Geração de Reajustes Aprovados ===")
    print(f"  Total de registros avaliados      : {total_avaliados}")
    print()
    print("  Resultado da geração:")
    print(f"    Aprovados incluídos             : {total_aprovados}")
    print(f"    Ignorados por status            : {total_ignorados}")
    print(f"    Com correções aplicadas         : {total_com_correcao}")
    print()

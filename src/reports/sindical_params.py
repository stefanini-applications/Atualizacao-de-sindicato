"""Relatório de exportação da base de parâmetros sindicais para o Ratecard.

Exibe o total de registros exportados (válidos + conflito), o caminho absoluto
do arquivo gerado e a contagem de grupos com conflito — AC4.
"""


def imprimir_relatorio_exportacao(
    total_exportados: int,
    total_conflitos: int,
    output_path_absoluto: str,
) -> None:
    """Imprime resumo da exportação de parâmetros sindicais (AC4)."""
    print("\n=== Relatório de Exportação de Parâmetros Sindicais ===")
    print(f"  Total de registros exportados     : {total_exportados}")
    print(f"    Válidos                         : {total_exportados - total_conflitos}")
    print(f"    Com conflito                    : {total_conflitos}")
    print()
    print(f"  Arquivo salvo em: {output_path_absoluto}")
    print()

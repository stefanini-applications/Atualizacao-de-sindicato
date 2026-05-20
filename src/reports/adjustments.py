"""Relatório de extração estruturada de reajustes salariais e vigências.

Exibe totais de cláusulas avaliadas, escopo, ignoradas por categoria e os
quatro contadores de status de extração — conforme AC5.
"""

from typing import List

from src.models.reajuste_extraido import ReajusteExtraido

_TIPOS_ESCOPO = frozenset(["reajuste_salarial", "vigencia_data_base"])


def imprimir_relatorio_reajustes(
    total_avaliadas: int,
    total_escopo: int,
    total_ignoradas_categoria: int,
    reajustes: List[ReajusteExtraido],
) -> None:
    """Imprime relatório de cobertura da extração estruturada (AC5).

    A soma dos quatro contadores de status é igual a ``total_escopo``.
    """
    extraido_com_sucesso = sum(
        1 for r in reajustes if r.status_extracao_estruturada == "extraido_com_sucesso"
    )
    parcialmente_extraido = sum(
        1 for r in reajustes if r.status_extracao_estruturada == "parcialmente_extraido"
    )
    dados_nao_identificados = sum(
        1 for r in reajustes if r.status_extracao_estruturada == "dados_nao_identificados"
    )
    erro_extracao = sum(
        1 for r in reajustes if r.status_extracao_estruturada == "erro_extracao"
    )

    print("\n=== Relatório de Extração Estruturada ===")
    print(f"  Total de cláusulas avaliadas      : {total_avaliadas}")
    print(f"  Cláusulas no escopo               : {total_escopo}")
    print(f"  Ignoradas por categoria           : {total_ignoradas_categoria}")
    print()
    print("  Status da extração:")
    print(f"    Extraído com sucesso            : {extraido_com_sucesso}")
    print(f"    Parcialmente extraído           : {parcialmente_extraido}")
    print(f"    Dados não identificados         : {dados_nao_identificados}")
    print(f"    Erro na extração                : {erro_extracao}")
    print()

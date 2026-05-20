"""Relatório de validação humana dos reajustes salariais extraídos.

Exibe totais por status_validacao — conforme AC5.
"""

from typing import List

from src.models.reajuste_para_validacao import ReajusteParaValidacao


def imprimir_relatorio_validacao(registros: List[ReajusteParaValidacao]) -> None:
    """Imprime relatório com totais por status_validacao (AC5).

    A soma dos quatro contadores de status é igual ao total de registros avaliados.
    """
    total = len(registros)
    sugerido_para_aprovacao = sum(
        1 for r in registros if r.status_validacao == "sugerido_para_aprovacao"
    )
    pendente_revisao = sum(
        1 for r in registros if r.status_validacao == "pendente_revisao"
    )
    sem_dados_para_validar = sum(
        1 for r in registros if r.status_validacao == "sem_dados_para_validar"
    )
    erro_validacao = sum(
        1 for r in registros if r.status_validacao == "erro_validacao"
    )

    print("\n=== Relatório de Validação ===")
    print(f"  Total de registros avaliados      : {total}")
    print()
    print("  Status de validação inicial:")
    print(f"    Sugerido para aprovação         : {sugerido_para_aprovacao}")
    print(f"    Pendente de revisão             : {pendente_revisao}")
    print(f"    Sem dados para validar          : {sem_dados_para_validar}")
    print(f"    Erro de validação               : {erro_validacao}")
    print()

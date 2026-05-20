"""Relatório de revisão manual dos reajustes salariais.

Exibe totais de aprovados, rejeitados, pendentes e com correção manual — AC5.
"""

from typing import List

from src.models.reajuste_para_validacao import ReajusteParaValidacao

_STATUS_FINAIS = frozenset(["aprovado", "rejeitado"])
_CAMPOS_CORRECAO = (
    "percentual_reajuste_corrigido",
    "data_base_corrigida",
    "vigencia_inicio_corrigida",
    "vigencia_fim_corrigida",
)


def imprimir_relatorio_revisao(registros: List[ReajusteParaValidacao]) -> None:
    """Imprime relatório consolidado da revisão manual (AC5)."""
    total = len(registros)
    aprovados = sum(1 for r in registros if r.status_validacao == "aprovado")
    rejeitados = sum(1 for r in registros if r.status_validacao == "rejeitado")
    pendentes = sum(1 for r in registros if r.status_validacao not in _STATUS_FINAIS)
    com_correcao = sum(
        1 for r in registros
        if any(getattr(r, campo) for campo in _CAMPOS_CORRECAO)
    )

    print("\n=== Relatório de Revisão Manual ===")
    print(f"  Total de registros avaliados      : {total}")
    print()
    print("  Resultado da revisão:")
    print(f"    Aprovados                       : {aprovados}")
    print(f"    Rejeitados                      : {rejeitados}")
    print(f"    Pendentes                       : {pendentes}")
    print(f"    Com correção manual             : {com_correcao}")
    print()

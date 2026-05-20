"""Relatório de simulação de aplicação de reajustes à base de pricing.

Exibe o total de linhas avaliadas, o total por cada valor de status_aplicacao
e a confirmação de que a soma dos totais por status é igual ao total avaliado — AC5.

Também exibe a distribuição de ``decisao_aplicacao`` e instrui o operador
sobre o campo a editar antes de executar ``generate-pricing-application-base`` — AC1 PRJ-13.
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


def imprimir_relatorio_revisao_preview(
    total_linhas: int,
    contagens_por_status: Dict[str, int],
    contagens_decisao: Dict[str, int],
    coluna_adicionada: bool,
) -> None:
    """Imprime relatório de revisão da prévia de pricing (AC1 PRJ-13).

    Exibe a distribuição de ``status_aplicacao``, a distribuição de
    ``decisao_aplicacao`` e orienta o operador sobre o próximo passo.
    """
    print("\n=== Revisão da Prévia de Atualização de Pricing ===")
    print(f"  Total de linhas na prévia         : {total_linhas}")

    if coluna_adicionada:
        print()
        print("  ℹ  Coluna 'decisao_aplicacao' adicionada ao arquivo (estava ausente).")

    print()
    print("  Distribuição por status_aplicacao:")
    for status in _STATUS_ORDEM:
        contagem = contagens_por_status.get(status, 0)
        print(f"    {status:<35}: {contagem}")
    for status in sorted(contagens_por_status):
        if status not in _STATUS_ORDEM:
            print(f"    {status:<35}: {contagens_por_status[status]}")

    print()
    print("  Distribuição atual de decisao_aplicacao:")
    aprovado = contagens_decisao.get("aprovado", 0)
    rejeitado = contagens_decisao.get("rejeitado", 0)
    em_branco = contagens_decisao.get("", 0)
    print(f"    {'aprovado':<35}: {aprovado}")
    print(f"    {'rejeitado':<35}: {rejeitado}")
    print(f"    {'(em branco / não decidido)':<35}: {em_branco}")

    print()
    print("  ── Próximo passo ──────────────────────────────────────────────────")
    print("  Abra o arquivo 'data/preview_atualizacao_pricing.xlsx' e preencha")
    print("  a coluna 'decisao_aplicacao' com 'aprovado' nas linhas com")
    print("  'status_aplicacao = reajuste_encontrado' que devem entrar na base")
    print("  de aplicação. Em seguida execute:")
    print("    python -m src generate-pricing-application-base")
    print()

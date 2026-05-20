"""Geração da base final de reajustes aprovados para uso no pricing.

Filtra exclusivamente os registros com ``status_validacao = aprovado``,
aplica a regra de precedência (valor corrigido prevalece sobre o original
quando não for ``None`` nem string vazia) e constrói a lista de
``ReajusteAprovado`` com rastreabilidade completa — AC2, AC3.
"""

from typing import List, Tuple

from src.models.reajuste_aprovado import ReajusteAprovado
from src.models.reajuste_para_validacao import ReajusteParaValidacao


def _valor_final(original, corrigido) -> object:
    """Retorna o valor corrigido quando preenchido; caso contrário, o original.

    Um valor corrigido é considerado preenchido quando não for ``None`` e não
    for string vazia (``""``).  Qualquer outro valor — inclusive ``"0"`` ou
    ``"0%"`` — é tratado como preenchido e prevalece sobre o original (AC3).
    """
    if corrigido is not None and corrigido != "":
        return corrigido
    return original


def _tem_correcao_aplicada(r: ReajusteParaValidacao) -> bool:
    """Retorna True quando ao menos um campo corrigido foi preenchido pelo revisor."""
    return any(
        v is not None and v != ""
        for v in (
            r.percentual_reajuste_corrigido,
            r.data_base_corrigida,
            r.vigencia_inicio_corrigida,
            r.vigencia_fim_corrigida,
        )
    )


def _criar_aprovado(r: ReajusteParaValidacao, data_hora_geracao: str) -> ReajusteAprovado:
    return ReajusteAprovado(
        id_registro=r.id_registro,
        caminho=r.caminho,
        nome_arquivo=r.nome_arquivo,
        uf=r.uf,
        sindicato=r.sindicato,
        tipo_documento=r.tipo_documento,
        ano_referencia=r.ano_referencia,
        tipo_clausula=r.tipo_clausula,
        trecho_original=r.trecho_original,
        percentual_reajuste_original=r.percentual_reajuste,
        percentual_reajuste_final=_valor_final(r.percentual_reajuste, r.percentual_reajuste_corrigido),
        data_base_original=r.data_base,
        data_base_final=_valor_final(r.data_base, r.data_base_corrigida),
        vigencia_inicio_original=r.vigencia_inicio,
        vigencia_inicio_final=_valor_final(r.vigencia_inicio, r.vigencia_inicio_corrigida),
        vigencia_fim_original=r.vigencia_fim,
        vigencia_fim_final=_valor_final(r.vigencia_fim, r.vigencia_fim_corrigida),
        status_validacao=r.status_validacao,
        responsavel_validacao=r.responsavel_validacao,
        data_hora_validacao=r.data_hora_validacao,
        observacao_validacao=r.observacao_validacao,
        data_hora_geracao=data_hora_geracao,
    )


def gerar_reajustes_aprovados(
    registros: List[ReajusteParaValidacao],
    data_hora_geracao: str,
) -> Tuple[List[ReajusteAprovado], int]:
    """Filtra aprovados, aplica precedência e devolve (lista, qtd_com_correcao).

    Args:
        registros: lista completa lida de ``reajustes_para_validacao.json``.
        data_hora_geracao: timestamp UTC da execução (ISO 8601).

    Returns:
        Tupla ``(aprovados, com_correcao)`` onde ``com_correcao`` é o número
        de registros em que ao menos um campo corrigido foi aplicado.
    """
    aprovados: List[ReajusteAprovado] = []
    com_correcao = 0

    for r in registros:
        if r.status_validacao != "aprovado":
            continue
        if _tem_correcao_aplicada(r):
            com_correcao += 1
        aprovados.append(_criar_aprovado(r, data_hora_geracao))

    return aprovados, com_correcao

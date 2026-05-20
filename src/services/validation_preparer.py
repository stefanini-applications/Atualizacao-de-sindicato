"""Serviço de preparação dos reajustes extraídos para validação humana.

Aplica o mapeamento de status_extracao_estruturada → status_validacao inicial
e constrói a lista de ReajusteParaValidacao, preservando todos os campos
originais (AC2, AC3).
"""

from typing import List

from src.models.reajuste_extraido import ReajusteExtraido
from src.models.reajuste_para_validacao import MAPEAMENTO_STATUS, ReajusteParaValidacao


def preparar_para_validacao(
    reajustes: List[ReajusteExtraido],
) -> List[ReajusteParaValidacao]:
    """Converte cada ReajusteExtraido em ReajusteParaValidacao com status inicial (AC2, AC3)."""
    resultado: List[ReajusteParaValidacao] = []
    for r in reajustes:
        status_validacao = MAPEAMENTO_STATUS.get(r.status_extracao_estruturada, "erro_validacao")
        resultado.append(
            ReajusteParaValidacao(
                # campos originais
                caminho=r.caminho,
                nome_arquivo=r.nome_arquivo,
                uf=r.uf,
                sindicato=r.sindicato,
                tipo_documento=r.tipo_documento,
                ano_referencia=r.ano_referencia,
                tipo_clausula=r.tipo_clausula,
                trecho_original=r.trecho_original,
                percentual_reajuste=r.percentual_reajuste,
                data_base=r.data_base,
                vigencia_inicio=r.vigencia_inicio,
                vigencia_fim=r.vigencia_fim,
                status_extracao_estruturada=r.status_extracao_estruturada,
                # campos de validação — null nesta etapa
                status_validacao=status_validacao,
                observacao_validacao=None,
                responsavel_validacao=None,
                data_hora_validacao=None,
                # campos de correção manual — null nesta etapa
                percentual_reajuste_corrigido=None,
                data_base_corrigida=None,
                vigencia_inicio_corrigida=None,
                vigencia_fim_corrigida=None,
            )
        )
    return resultado

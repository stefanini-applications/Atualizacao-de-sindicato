"""Lógica de cruzamento entre a base de pricing e os reajustes aprovados.

Cada linha da base de pricing recebe exatamente um ``status_aplicacao``
conforme as regras definidas na AC3:

  reajuste_encontrado      — exatamente um registro correspondente
  sem_correspondencia      — nenhum registro encontrado
  multiplas_correspondencias — mais de um registro encontrado
  dados_insuficientes      — linha sem uf, sindicato ou ano_referencia
  erro_aplicacao           — falha inesperada ao processar a linha
"""

from typing import Dict, List, Optional, Tuple

from src.models.linha_preview_pricing import LinhaPreviewPricing
from src.models.reajuste_aprovado import ReajusteAprovado
from src.utils.text_normalizer import normalizar

# Tipo da chave de cruzamento
_Chave = Tuple[str, str, str]


def _normalizar_chave(uf: Optional[str], sindicato: Optional[str], ano: Optional[str]) -> Optional[_Chave]:
    """Retorna tupla normalizada (uf, sindicato, ano) ou None se algum campo estiver vazio."""
    if not uf or not sindicato or not ano:
        return None
    return (normalizar(str(uf)), normalizar(str(sindicato)), normalizar(str(ano)))


def _construir_indice(aprovados: List[ReajusteAprovado]) -> Dict[_Chave, List[ReajusteAprovado]]:
    """Constrói índice {chave_normalizada: [ReajusteAprovado]} para busca rápida."""
    indice: Dict[_Chave, List[ReajusteAprovado]] = {}
    for r in aprovados:
        chave = _normalizar_chave(r.uf, r.sindicato, r.ano_referencia)
        if chave is None:
            continue
        indice.setdefault(chave, []).append(r)
    return indice


def _processar_linha(
    linha: dict,
    col_uf: str,
    col_sindicato: str,
    col_ano: str,
    indice: Dict[_Chave, List[ReajusteAprovado]],
) -> LinhaPreviewPricing:
    """Processa uma linha individual e retorna LinhaPreviewPricing."""
    uf_val = linha.get(col_uf)
    sindicato_val = linha.get(col_sindicato)
    ano_val = linha.get(col_ano)

    # AC3: dados_insuficientes — uf, sindicato ou ano_referencia ausentes/vazios
    uf_str = str(uf_val).strip() if uf_val is not None else ""
    sindicato_str = str(sindicato_val).strip() if sindicato_val is not None else ""
    ano_str = str(ano_val).strip() if ano_val is not None else ""

    if not uf_str or not sindicato_str or not ano_str:
        campos_faltantes = []
        if not uf_str:
            campos_faltantes.append("uf")
        if not sindicato_str:
            campos_faltantes.append("sindicato")
        if not ano_str:
            campos_faltantes.append("ano_referencia")
        return LinhaPreviewPricing(
            dados_originais=linha,
            id_registro_reajuste=None,
            percentual_reajuste_final=None,
            data_base_final=None,
            vigencia_inicio_final=None,
            vigencia_fim_final=None,
            fonte_documento=None,
            status_aplicacao="dados_insuficientes",
            observacao_aplicacao=f"Campos ausentes ou vazios: {', '.join(campos_faltantes)}",
        )

    chave = (normalizar(uf_str), normalizar(sindicato_str), normalizar(ano_str))
    candidatos = indice.get(chave, [])

    if len(candidatos) == 0:
        return LinhaPreviewPricing(
            dados_originais=linha,
            id_registro_reajuste=None,
            percentual_reajuste_final=None,
            data_base_final=None,
            vigencia_inicio_final=None,
            vigencia_fim_final=None,
            fonte_documento=None,
            status_aplicacao="sem_correspondencia",
            observacao_aplicacao=None,
        )

    if len(candidatos) > 1:
        ids_candidatos = ", ".join(
            sorted(str(r.id_registro) for r in candidatos if r.id_registro)
        )
        return LinhaPreviewPricing(
            dados_originais=linha,
            id_registro_reajuste=None,
            percentual_reajuste_final=None,
            data_base_final=None,
            vigencia_inicio_final=None,
            vigencia_fim_final=None,
            fonte_documento=None,
            status_aplicacao="multiplas_correspondencias",
            observacao_aplicacao=f"Candidatos: {ids_candidatos}",
        )

    # exatamente um candidato
    reajuste = candidatos[0]
    return LinhaPreviewPricing(
        dados_originais=linha,
        id_registro_reajuste=reajuste.id_registro,
        percentual_reajuste_final=reajuste.percentual_reajuste_final,
        data_base_final=reajuste.data_base_final,
        vigencia_inicio_final=reajuste.vigencia_inicio_final,
        vigencia_fim_final=reajuste.vigencia_fim_final,
        fonte_documento=reajuste.nome_arquivo,
        status_aplicacao="reajuste_encontrado",
        observacao_aplicacao=None,
    )


def gerar_preview(
    linhas_pricing: List[dict],
    aprovados: List[ReajusteAprovado],
    col_uf: str,
    col_sindicato: str,
    col_ano: str,
) -> List[LinhaPreviewPricing]:
    """Cruza cada linha da base de pricing com os reajustes aprovados.

    Returns:
        Lista de LinhaPreviewPricing, uma por linha da base de pricing.
        O comprimento é sempre igual ao de linhas_pricing.
    """
    indice = _construir_indice(aprovados)
    resultado: List[LinhaPreviewPricing] = []

    for linha in linhas_pricing:
        try:
            preview = _processar_linha(linha, col_uf, col_sindicato, col_ano, indice)
        except Exception as exc:  # noqa: BLE001
            preview = LinhaPreviewPricing(
                dados_originais=linha,
                id_registro_reajuste=None,
                percentual_reajuste_final=None,
                data_base_final=None,
                vigencia_inicio_final=None,
                vigencia_fim_final=None,
                fonte_documento=None,
                status_aplicacao="erro_aplicacao",
                observacao_aplicacao=f"Erro inesperado: {exc}",
            )
        resultado.append(preview)

    return resultado

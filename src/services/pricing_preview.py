"""Lógica de cruzamento entre a base de pricing e os reajustes aprovados.

Para cada linha da base de pricing atribui exatamente um ``status_aplicacao``
conforme as regras de correspondência pela chave ``uf + sindicato + ano_referencia``
(AC3). Quando a coluna ``ano_referencia`` não está presente na planilha, o
cruzamento é feito apenas por ``uf + sindicato``.
"""

from typing import Dict, List, Optional, Tuple

from src.models.linha_preview_pricing import LinhaPreviewPricing
from src.models.reajuste_aprovado import ReajusteAprovado

# ── valores de status_aplicacao (AC3) ────────────────────────────────────────
STATUS_ENCONTRADO = "reajuste_encontrado"
STATUS_SEM_CORRESPONDENCIA = "sem_correspondencia"
STATUS_MULTIPLAS = "multiplas_correspondencias"
STATUS_INSUFICIENTE = "dados_insuficientes"
STATUS_ERRO = "erro_aplicacao"


def _normalizar_chave(valor) -> str:
    """Normaliza um valor de célula para uso como chave de cruzamento."""
    if valor is None:
        return ""
    # Converte floats inteiros (e.g. 2024.0 → "2024") antes de stringificar.
    if isinstance(valor, float) and valor.is_integer():
        valor = int(valor)
    return str(valor).strip().lower()


def _detectar_coluna(headers: List[str], nome_canônico: str) -> Optional[str]:
    """Retorna o nome exato do cabeçalho que corresponde ao nome canônico (case-insensitive)."""
    alvo = nome_canônico.lower().strip()
    for h in headers:
        if h.lower().strip() == alvo:
            return h
    return None


def _construir_indice(
    aprovados: List[ReajusteAprovado],
    usar_ano: bool,
) -> Dict[Tuple, List[ReajusteAprovado]]:
    """Constrói índice de cruzamento a partir dos reajustes aprovados."""
    indice: Dict[Tuple, List[ReajusteAprovado]] = {}
    for r in aprovados:
        uf = _normalizar_chave(r.uf)
        sindicato = _normalizar_chave(r.sindicato)
        if not uf or not sindicato:
            continue
        if usar_ano:
            ano = _normalizar_chave(r.ano_referencia)
            chave = (uf, sindicato, ano)
        else:
            chave = (uf, sindicato)
        indice.setdefault(chave, []).append(r)
    return indice


def _linha_vazia() -> dict:
    return {
        "id_registro_reajuste": None,
        "percentual_reajuste_final": None,
        "data_base_final": None,
        "vigencia_inicio_final": None,
        "vigencia_fim_final": None,
        "fonte_documento": None,
    }


def _linha_de_reajuste(r: ReajusteAprovado) -> dict:
    return {
        "id_registro_reajuste": r.id_registro,
        "percentual_reajuste_final": r.percentual_reajuste_final,
        "data_base_final": r.data_base_final,
        "vigencia_inicio_final": r.vigencia_inicio_final,
        "vigencia_fim_final": r.vigencia_fim_final,
        "fonte_documento": r.nome_arquivo,
    }


def gerar_preview(
    headers: List[str],
    rows: List[dict],
    aprovados: List[ReajusteAprovado],
) -> List[LinhaPreviewPricing]:
    """Cruza cada linha da base de pricing com os reajustes aprovados.

    Args:
        headers: lista de cabeçalhos originais da base de pricing.
        rows: lista de dicionários ``{header: valor}`` por linha.
        aprovados: reajustes aprovados carregados de ``reajustes_aprovados.json``.

    Returns:
        Lista de ``LinhaPreviewPricing`` com ``status_aplicacao`` preenchido.
    """
    col_uf = _detectar_coluna(headers, "uf")
    col_sindicato = _detectar_coluna(headers, "sindicato")
    col_ano = _detectar_coluna(headers, "ano_referencia")

    usar_ano = col_ano is not None
    indice = _construir_indice(aprovados, usar_ano)

    resultado: List[LinhaPreviewPricing] = []

    for row in rows:
        try:
            uf_val = row.get(col_uf) if col_uf else None
            sindicato_val = row.get(col_sindicato) if col_sindicato else None

            uf_norm = _normalizar_chave(uf_val)
            sindicato_norm = _normalizar_chave(sindicato_val)

            if not uf_norm or not sindicato_norm:
                resultado.append(LinhaPreviewPricing(
                    dados_originais=row,
                    **_linha_vazia(),
                    status_aplicacao=STATUS_INSUFICIENTE,
                    observacao_aplicacao="Campos 'uf' e/ou 'sindicato' ausentes ou vazios.",
                ))
                continue

            if usar_ano:
                ano_val = row.get(col_ano)
                ano_norm = _normalizar_chave(ano_val)
                chave = (uf_norm, sindicato_norm, ano_norm)
            else:
                chave = (uf_norm, sindicato_norm)

            candidatos = indice.get(chave, [])

            if len(candidatos) == 0:
                resultado.append(LinhaPreviewPricing(
                    dados_originais=row,
                    **_linha_vazia(),
                    status_aplicacao=STATUS_SEM_CORRESPONDENCIA,
                    observacao_aplicacao=None,
                ))
            elif len(candidatos) == 1:
                r = candidatos[0]
                resultado.append(LinhaPreviewPricing(
                    dados_originais=row,
                    **_linha_de_reajuste(r),
                    status_aplicacao=STATUS_ENCONTRADO,
                    observacao_aplicacao=None,
                ))
            else:
                ids = ", ".join(
                    str(c.id_registro) for c in candidatos if c.id_registro
                )
                resultado.append(LinhaPreviewPricing(
                    dados_originais=row,
                    **_linha_vazia(),
                    status_aplicacao=STATUS_MULTIPLAS,
                    observacao_aplicacao=f"Candidatos: {ids}",
                ))

        except Exception as exc:  # noqa: BLE001
            resultado.append(LinhaPreviewPricing(
                dados_originais=row,
                **_linha_vazia(),
                status_aplicacao=STATUS_ERRO,
                observacao_aplicacao=f"Erro ao processar linha: {exc}",
            ))

    return resultado

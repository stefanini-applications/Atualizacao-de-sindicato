"""Aplicação de reajustes aprovados sobre a base de pricing.

Para cada linha da base de pricing cruza pela chave composta
``uf + sindicato + ano_referencia`` com a base de aplicações aprovadas
e aplica o percentual de reajuste, produzindo os 7 campos de rastreabilidade.

Status possíveis em ``status_atualizacao``:
  atualizado        — correspondência única, coluna válida, percentual parseável,
                      reajuste aplicado com sucesso
  nao_atualizado    — nenhuma correspondência encontrada na base aprovada
  erro_atualizacao  — coluna ausente/vazia/não-numérica, falha no parsing do
                      percentual ou duplicidade de correspondências
"""

from typing import Dict, List, Optional, Tuple

from src.utils.text_normalizer import normalizar

STATUS_ATUALIZADO = "atualizado"
STATUS_NAO_ATUALIZADO = "nao_atualizado"
STATUS_ERRO = "erro_atualizacao"

OBS_NAO_ATUALIZADO = "nenhuma aplicação aprovada encontrada para esta linha"
OBS_MULTIPLOS = "múltiplos registros aprovados encontrados para esta chave"

COLUNAS_SAIDA = [
    "valor_original",
    "percentual_reajuste_aplicado",
    "valor_reajustado",
    "id_registro_reajuste",
    "data_hora_aplicacao",
    "status_atualizacao",
    "observacao_atualizacao",
]

_Chave = Tuple[str, str, str]


def _normalizar_chave(
    uf: Optional[object],
    sindicato: Optional[object],
    ano: Optional[object],
) -> Optional[_Chave]:
    """Retorna tupla normalizada (uf, sindicato, ano) ou None se algum campo estiver vazio."""
    if uf is None or sindicato is None or ano is None:
        return None
    uf_s = str(uf).strip()
    sin_s = str(sindicato).strip()
    ano_s = str(ano).strip()
    if not uf_s or not sin_s or not ano_s:
        return None
    return (normalizar(uf_s), normalizar(sin_s), normalizar(ano_s))


def _construir_indice(
    aprovacoes: List[dict],
    col_uf: str,
    col_sindicato: str,
    col_ano: str,
) -> Dict[_Chave, List[dict]]:
    """Constrói índice {chave_normalizada: [row]} a partir da base de aprovações."""
    indice: Dict[_Chave, List[dict]] = {}
    for row in aprovacoes:
        chave = _normalizar_chave(
            row.get(col_uf),
            row.get(col_sindicato),
            row.get(col_ano),
        )
        if chave is None:
            continue
        indice.setdefault(chave, []).append(row)
    return indice


def _parsear_percentual(valor: object) -> Tuple[Optional[float], Optional[str]]:
    """Faz parsing e normalização do campo ``percentual_reajuste_final``.

    Formatos suportados: ``"5"``, ``"5.0"``, ``"5,0"``, ``"5%"``, ``"5,0%"``, ``"5.0%"``.

    Returns:
        (float, None) em caso de sucesso.
        (None, mensagem_de_erro) em caso de falha.
    """
    if valor is None:
        return None, f"percentual_reajuste_final não pôde ser convertido para número: 'None'"
    s = str(valor).strip().replace("%", "").replace(",", ".").strip()
    try:
        return float(s), None
    except ValueError:
        return None, f"percentual_reajuste_final não pôde ser convertido para número: '{valor}'"


def _validar_valor_coluna(
    linha: dict,
    value_column: str,
) -> Tuple[Optional[float], Optional[object], Optional[str]]:
    """Valida e extrai o valor numérico da coluna indicada.

    Returns:
        (float, raw_value, None)  — sucesso; raw_value é o valor original da célula.
        (None,  raw_value, erro)  — falha; raw_value é o valor bruto (pode ser None).
    """
    if value_column not in linha:
        return None, None, f"coluna '{value_column}' não encontrada"
    raw = linha[value_column]
    if raw is None or (isinstance(raw, str) and raw.strip() == ""):
        return None, raw, f"valor ausente na coluna '{value_column}'"
    try:
        return float(raw), raw, None
    except (ValueError, TypeError):
        return None, raw, f"valor não numérico na coluna '{value_column}': '{raw}'"


def aplicar_reajustes(
    linhas_pricing: List[dict],
    aprovacoes: List[dict],
    col_uf: str,
    col_sindicato: str,
    col_ano: str,
    value_column: str,
    timestamp: str,
) -> List[dict]:
    """Cruza a base de pricing com as aprovações e aplica os percentuais.

    Args:
        linhas_pricing  — linhas da base de pricing (dicts com colunas originais).
        aprovacoes      — linhas da base de aplicações aprovadas (dicts).
        col_uf          — nome da coluna de UF na base de pricing.
        col_sindicato   — nome da coluna de sindicato na base de pricing.
        col_ano         — nome da coluna de ano_referencia na base de pricing.
        value_column    — coluna sobre a qual o percentual será aplicado.
        timestamp       — timestamp ISO 8601 do momento de execução.

    Returns:
        Lista de dicts com colunas originais mais os 7 campos de rastreabilidade.
        O comprimento é sempre igual ao de ``linhas_pricing``.
    """
    indice = _construir_indice(aprovacoes, col_uf, col_sindicato, col_ano)
    resultado: List[dict] = []

    for linha in linhas_pricing:
        enriquecido = dict(linha)

        # AC7 — validação da coluna de valor
        valor_float, raw_valor, erro_valor = _validar_valor_coluna(linha, value_column)
        if erro_valor:
            enriquecido.update(
                valor_original=raw_valor,
                percentual_reajuste_aplicado=None,
                valor_reajustado=None,
                id_registro_reajuste=None,
                data_hora_aplicacao=None,
                status_atualizacao=STATUS_ERRO,
                observacao_atualizacao=erro_valor,
            )
            resultado.append(enriquecido)
            continue

        chave = _normalizar_chave(
            linha.get(col_uf),
            linha.get(col_sindicato),
            linha.get(col_ano),
        )
        candidatos: List[dict] = [] if chave is None else indice.get(chave, [])

        # AC8 — duplicidade de correspondências
        if len(candidatos) > 1:
            enriquecido.update(
                valor_original=valor_float,
                percentual_reajuste_aplicado=None,
                valor_reajustado=None,
                id_registro_reajuste=None,
                data_hora_aplicacao=None,
                status_atualizacao=STATUS_ERRO,
                observacao_atualizacao=OBS_MULTIPLOS,
            )
            resultado.append(enriquecido)
            continue

        # AC3 — sem correspondência
        if len(candidatos) == 0:
            enriquecido.update(
                valor_original=valor_float,
                percentual_reajuste_aplicado=None,
                valor_reajustado=valor_float,
                id_registro_reajuste=None,
                data_hora_aplicacao=None,
                status_atualizacao=STATUS_NAO_ATUALIZADO,
                observacao_atualizacao=OBS_NAO_ATUALIZADO,
            )
            resultado.append(enriquecido)
            continue

        # exatamente uma correspondência — AC2/AC10
        aprovado = candidatos[0]
        id_registro = aprovado.get("id_registro_reajuste")
        percentual_raw = aprovado.get("percentual_reajuste_final")

        percentual, erro_perc = _parsear_percentual(percentual_raw)
        if erro_perc:
            enriquecido.update(
                valor_original=valor_float,
                percentual_reajuste_aplicado=None,
                valor_reajustado=None,
                id_registro_reajuste=None,
                data_hora_aplicacao=None,
                status_atualizacao=STATUS_ERRO,
                observacao_atualizacao=erro_perc,
            )
            resultado.append(enriquecido)
            continue

        valor_reajustado = valor_float * (1 + percentual / 100)
        enriquecido.update(
            valor_original=valor_float,
            percentual_reajuste_aplicado=percentual,
            valor_reajustado=valor_reajustado,
            id_registro_reajuste=id_registro,
            data_hora_aplicacao=timestamp,
            status_atualizacao=STATUS_ATUALIZADO,
            observacao_atualizacao=None,
        )
        resultado.append(enriquecido)

    return resultado

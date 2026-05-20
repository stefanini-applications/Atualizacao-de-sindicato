"""Leitura e normalização da base de pricing a partir de arquivo .xlsx.

Processa apenas a primeira planilha (aba ativa) do arquivo.
Retorna as linhas como dicionários com os nomes de coluna originais,
sem modificar os valores — AC2.
"""

from pathlib import Path
from typing import List, Optional, Tuple

import openpyxl

from src.utils.text_normalizer import normalizar

# Aliases aceitos para cada coluna de chave de correspondência.
# A resolução é case-insensitive e sem acentos (via normalizar()).
_ALIASES_UF = frozenset(["uf", "estado", "uf_sindicato"])
_ALIASES_SINDICATO = frozenset(["sindicato", "nome_sindicato", "sind", "entidade"])
_ALIASES_ANO = frozenset(["ano_referencia", "ano", "ano_ref", "ano referencia", "anoreferencia"])


def _resolver_coluna(cabecalhos: List[str], aliases: frozenset) -> Optional[str]:
    """Retorna o nome original da coluna que corresponde a um dos aliases, ou None."""
    for cab in cabecalhos:
        if normalizar(cab) in aliases:
            return cab
    return None


def carregar_base_pricing(
    path: Path,
) -> Tuple[List[dict], List[str], str, str, str]:
    """Carrega a primeira aba do arquivo xlsx e resolve colunas de chave.

    Returns:
        linhas          — lista de dicts {coluna_original: valor}
        colunas         — lista ordenada de nomes de colunas originais
        col_uf          — nome da coluna mapeada para 'uf'
        col_sindicato   — nome da coluna mapeada para 'sindicato'
        col_ano         — nome da coluna mapeada para 'ano_referencia'

    Raises:
        ValueError se alguma coluna de chave não for encontrada.
    """
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb.active

    rows = list(ws.iter_rows(values_only=True))
    wb.close()

    if not rows:
        return [], [], None, None, None

    cabecalhos_raw = [str(c) if c is not None else "" for c in rows[0]]
    colunas = cabecalhos_raw

    col_uf = _resolver_coluna(colunas, _ALIASES_UF)
    col_sindicato = _resolver_coluna(colunas, _ALIASES_SINDICATO)
    col_ano = _resolver_coluna(colunas, _ALIASES_ANO)

    ausentes = []
    if col_uf is None:
        ausentes.append("uf")
    if col_sindicato is None:
        ausentes.append("sindicato")
    if col_ano is None:
        ausentes.append("ano_referencia")

    if ausentes:
        raise ValueError(
            f"Colunas de chave não encontradas na base de pricing: {', '.join(ausentes)}. "
            f"Cabeçalhos disponíveis: {colunas}"
        )

    linhas = []
    for row in rows[1:]:
        linha = {colunas[i]: row[i] for i in range(len(colunas))}
        linhas.append(linha)

    return linhas, colunas, col_uf, col_sindicato, col_ano

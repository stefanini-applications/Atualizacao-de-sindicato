"""Leitura da base de pricing a partir de arquivo XLSX.

Retorna cabeçalhos originais e linhas como dicionários, preservando os nomes
de coluna exatos da planilha para que a prévia possa reconstruir o layout
original — AC2, AC4.
"""

from pathlib import Path
from typing import List, Tuple

import openpyxl


class ErroCabecalhoPricing(ValueError):
    """Cabeçalho obrigatório ausente ou duplicado na planilha de pricing."""


def _verificar_cabecalhos(headers: List[str]) -> None:
    """Levanta ErroCabecalhoPricing se cabeçalhos inválidos forem detectados."""
    # Detecta células de cabeçalho em branco
    vazios = [i + 1 for i, h in enumerate(headers) if not h or not str(h).strip()]
    if vazios:
        raise ErroCabecalhoPricing(
            f"Cabeçalhos em branco detectados nas colunas: {vazios}. "
            "A primeira linha da planilha deve conter todos os nomes de coluna."
        )

    # Detecta duplicatas
    vistos: set = set()
    duplicatas: set = set()
    for h in headers:
        if h in vistos:
            duplicatas.add(h)
        vistos.add(h)
    if duplicatas:
        raise ErroCabecalhoPricing(
            f"Cabeçalhos duplicados detectados: {sorted(duplicatas)}. "
            "Cada coluna deve ter um nome único."
        )


def ler_base_pricing(path: Path) -> Tuple[List[str], List[dict]]:
    """Lê a base de pricing de um arquivo XLSX.

    A primeira linha é tratada como cabeçalho. Células vazias tornam-se ``None``.

    Returns:
        (headers, rows) onde ``headers`` é a lista de nomes originais de coluna
        e ``rows`` é a lista de dicionários ``{header: valor}`` por linha.

    Raises:
        ErroCabecalhoPricing: se houver cabeçalhos em branco ou duplicados.
    """
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb.active

    rows_iter = ws.iter_rows(values_only=True)

    header_row = next(rows_iter, None)
    if header_row is None:
        return [], []

    headers = [str(h).strip() if h is not None else "" for h in header_row]
    _verificar_cabecalhos(headers)

    rows: List[dict] = []
    for raw in rows_iter:
        row_dict = {headers[i]: (raw[i] if i < len(raw) else None) for i in range(len(headers))}
        rows.append(row_dict)

    wb.close()
    return headers, rows

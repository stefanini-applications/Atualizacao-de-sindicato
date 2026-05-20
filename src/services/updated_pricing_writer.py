"""Gravação atômica da base de pricing atualizada em formato .xlsx.

Usa tempfile + os.replace para garantir que nenhum arquivo corrompido seja
deixado em disco caso a escrita falhe — padrão consolidado no repositório.
"""

import os
import tempfile
from pathlib import Path
from typing import List

import openpyxl

from src.services.pricing_applier import COLUNAS_SAIDA


def salvar_base_atualizada(
    output_path: Path,
    linhas: List[dict],
    colunas_originais: List[str],
) -> None:
    """Grava a base de pricing atualizada em ``output_path`` de forma atômica.

    O workbook de saída contém todas as colunas originais da base de pricing
    seguidas dos 7 campos de rastreabilidade definidos em ``COLUNAS_SAIDA``.

    Args:
        output_path      — destino do arquivo .xlsx.
        linhas           — lista de dicts enriquecidos (originais + 7 campos novos).
        colunas_originais — lista ordenada dos nomes de colunas originais.
    """
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "base_pricing_atualizada"

    cabecalho = list(colunas_originais) + COLUNAS_SAIDA
    ws.append(cabecalho)

    for linha in linhas:
        valores_originais = [linha.get(col) for col in colunas_originais]
        valores_novos = [linha.get(col) for col in COLUNAS_SAIDA]
        ws.append(valores_originais + valores_novos)

    output_path.parent.mkdir(parents=True, exist_ok=True)

    fd, tmp_path = tempfile.mkstemp(dir=output_path.parent, suffix=".xlsx.tmp")
    try:
        os.close(fd)
        wb.save(tmp_path)
        os.replace(tmp_path, output_path)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise

"""Gravação atômica da prévia de atualização de pricing em formato .xlsx.

Usa tempfile + os.replace para garantir que o arquivo original não seja
modificado e que não haja arquivo corrompido em caso de falha — AC2.
"""

import os
import tempfile
from pathlib import Path
from typing import List

import openpyxl

from src.models.linha_preview_pricing import LinhaPreviewPricing

_COLUNAS_ADICIONADAS = [
    "id_registro_reajuste",
    "percentual_reajuste_final",
    "data_base_final",
    "vigencia_inicio_final",
    "vigencia_fim_final",
    "fonte_documento",
    "status_aplicacao",
    "decisao_aplicacao",
    "observacao_aplicacao",
]


def salvar_preview(
    output_path: Path,
    linhas: List[LinhaPreviewPricing],
    colunas_originais: List[str],
) -> None:
    """Grava prévia em output_path de forma atômica.

    O workbook de saída contém todas as colunas originais da base de pricing
    seguidas dos 8 campos de simulação — AC4.
    """
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "preview_atualizacao"

    cabecalho = list(colunas_originais) + _COLUNAS_ADICIONADAS
    ws.append(cabecalho)

    for linha in linhas:
        valores_originais = [linha.dados_originais.get(col) for col in colunas_originais]
        valores_adicionados = [
            linha.id_registro_reajuste,
            linha.percentual_reajuste_final,
            linha.data_base_final,
            linha.vigencia_inicio_final,
            linha.vigencia_fim_final,
            linha.fonte_documento,
            linha.status_aplicacao,
            linha.decisao_aplicacao,
            linha.observacao_aplicacao,
        ]
        ws.append(valores_originais + valores_adicionados)

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

"""Modelo de dados para cada linha da prévia de atualização de pricing.

Preserva todos os dados originais da base de pricing e acrescenta os campos
de reajuste simulado e o status de correspondência — AC4.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class LinhaPreviewPricing:
    """Uma linha da base de pricing enriquecida com dados da simulação de reajuste."""

    # dados originais da planilha de pricing (preservados sem modificação)
    dados_originais: dict

    # campos adicionados pelo cruzamento — AC4
    id_registro_reajuste: Optional[str]
    percentual_reajuste_final: Optional[str]
    data_base_final: Optional[str]
    vigencia_inicio_final: Optional[str]
    vigencia_fim_final: Optional[str]
    fonte_documento: Optional[str]
    status_aplicacao: str
    observacao_aplicacao: Optional[str]

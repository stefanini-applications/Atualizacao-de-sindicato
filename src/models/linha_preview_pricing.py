"""Modelo de dados para uma linha da prévia de atualização de pricing.

Combina os dados originais de uma linha da base de pricing com os campos
de simulação de reajuste derivados do cruzamento com ``ReajusteAprovado``.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class LinhaPreviewPricing:
    """Linha da prévia, preservando dados originais e acrescentando campos simulados."""

    # ── dados originais da base de pricing (todas as colunas) ────────────────
    dados_originais: dict

    # ── campos adicionados pelo cruzamento (AC4) ──────────────────────────────
    id_registro_reajuste: Optional[str]
    percentual_reajuste_final: Optional[str]
    data_base_final: Optional[str]
    vigencia_inicio_final: Optional[str]
    vigencia_fim_final: Optional[str]
    fonte_documento: Optional[str]
    status_aplicacao: str
    observacao_aplicacao: Optional[str]


# Nomes das colunas adicionadas na prévia, em ordem de saída (AC4).
COLUNAS_PREVIEW = [
    "id_registro_reajuste",
    "percentual_reajuste_final",
    "data_base_final",
    "vigencia_inicio_final",
    "vigencia_fim_final",
    "fonte_documento",
    "status_aplicacao",
    "observacao_aplicacao",
]

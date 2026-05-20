"""Modelo de dados para reajustes salariais e vigências extraídos das CCTs.

Cada registro representa um trecho de cláusula candidata processado pelo
comando ``extract-adjustments``, com os campos extraídos por padrões textuais
e o status da extração estruturada (AC3, AC4).
"""

from dataclasses import dataclass
from typing import Optional

STATUS_EXTRACAO: frozenset = frozenset([
    "extraido_com_sucesso",
    "parcialmente_extraido",
    "dados_nao_identificados",
    "erro_extracao",
])


@dataclass
class ReajusteExtraido:
    """Resultado da extração estruturada de uma cláusula candidata."""

    caminho: str
    nome_arquivo: str
    uf: Optional[str]
    sindicato: Optional[str]
    tipo_documento: Optional[str]
    ano_referencia: Optional[str]
    origem_texto: str
    tipo_clausula: str
    trecho_original: str
    percentual_reajuste: Optional[str]   # valor extraído ou null
    data_base: Optional[str]             # ISO YYYY-MM-DD ou null
    vigencia_inicio: Optional[str]       # ISO YYYY-MM-DD ou null
    vigencia_fim: Optional[str]          # ISO YYYY-MM-DD ou null
    status_extracao_estruturada: str     # um dos valores em STATUS_EXTRACAO
    metodo_extracao: str
    data_hora_processamento: str         # ISO 8601

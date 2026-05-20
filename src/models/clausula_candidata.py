"""Modelo de dados para cláusulas candidatas identificadas nas CCTs.

Uma cláusula candidata representa um trecho de texto de um documento sindical
que contém termos associados a remuneração ou benefícios, classificado por tipo
de tema para uso em etapas futuras de extração de valores.
"""

from dataclasses import dataclass
from typing import Optional

TIPOS_CLAUSULA: frozenset = frozenset([
    "reajuste_salarial",
    "piso_salarial",
    "vale_refeicao",
    "vale_alimentacao",
    "beneficios",
    "adicionais",
    "plr",
    "auxilio_home_office",
    "vigencia_data_base",
    "outros_remuneracao",
])


@dataclass
class ClausulaCandidata:
    """Trecho de texto identificado como candidato a cláusula de remuneração ou benefício."""

    trecho: str                    # texto original não normalizado (AC3, AC6)
    caminho: str
    nome_arquivo: str
    uf: Optional[str]
    sindicato: Optional[str]
    tipo_documento: Optional[str]
    ano_referencia: Optional[str]
    origem_texto: str              # origem_texto do TextoConsolidado de origem
    status_consolidado: str        # status_consolidado do TextoConsolidado de origem
    tipo_clausula: str             # um dos valores em TIPOS_CLAUSULA
    metodo_identificacao: str      # ex.: "keyword_match_normalized"
    data_hora_processamento: str   # ISO 8601

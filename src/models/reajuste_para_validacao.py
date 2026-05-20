"""Modelo de dados para reajustes salariais preparados para validação humana.

Cada registro preserva todos os campos da extração original e acrescenta campos
de validação (status, observação, responsável, data/hora) e campos de correção
manual — todos inicializados como ``None`` nesta etapa (AC3).
"""

from dataclasses import dataclass
from typing import Optional

STATUS_VALIDACAO: frozenset = frozenset([
    "sugerido_para_aprovacao",
    "pendente_revisao",
    "sem_dados_para_validar",
    "erro_validacao",
])

# Mapeamento de status_extracao_estruturada → status_validacao inicial (AC2)
MAPEAMENTO_STATUS: dict = {
    "extraido_com_sucesso": "sugerido_para_aprovacao",
    "parcialmente_extraido": "pendente_revisao",
    "dados_nao_identificados": "sem_dados_para_validar",
    "erro_extracao": "erro_validacao",
}


@dataclass
class ReajusteParaValidacao:
    """Reajuste extraído enriquecido com campos para revisão humana."""

    # ── campos originais da extração ──────────────────────────────────────────
    caminho: str
    nome_arquivo: str
    uf: Optional[str]
    sindicato: Optional[str]
    tipo_documento: Optional[str]
    ano_referencia: Optional[str]
    tipo_clausula: str
    trecho_original: str
    percentual_reajuste: Optional[str]
    data_base: Optional[str]
    vigencia_inicio: Optional[str]
    vigencia_fim: Optional[str]
    status_extracao_estruturada: str

    # ── campos de auditoria de validação (null nesta etapa) ───────────────────
    status_validacao: Optional[str]
    observacao_validacao: Optional[str]
    responsavel_validacao: Optional[str]
    data_hora_validacao: Optional[str]

    # ── campos de correção manual (null nesta etapa) ──────────────────────────
    percentual_reajuste_corrigido: Optional[str]
    data_base_corrigida: Optional[str]
    vigencia_inicio_corrigida: Optional[str]
    vigencia_fim_corrigida: Optional[str]

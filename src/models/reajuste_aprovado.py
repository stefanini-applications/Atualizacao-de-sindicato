"""Modelo de dados para reajustes salariais aprovados prontos para uso no pricing.

Cada registro preserva os valores originais extraídos, os valores finais aplicados
(corrigidos pelo revisor quando disponíveis) e todos os campos de rastreabilidade
necessários para auditoria — AC4.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class ReajusteAprovado:
    """Reajuste aprovado pelo operador, com valores finais e rastreabilidade completa."""

    # ── identificador único imutável ──────────────────────────────────────────
    id_registro: Optional[str]

    # ── campos de contexto e origem ───────────────────────────────────────────
    caminho: str
    nome_arquivo: str
    uf: Optional[str]
    sindicato: Optional[str]
    tipo_documento: Optional[str]
    ano_referencia: Optional[str]
    tipo_clausula: str
    trecho_original: str

    # ── rastreabilidade dual: original (extraído) e final (aplicado) ──────────
    percentual_reajuste_original: Optional[str]
    percentual_reajuste_final: Optional[str]
    data_base_original: Optional[str]
    data_base_final: Optional[str]
    vigencia_inicio_original: Optional[str]
    vigencia_inicio_final: Optional[str]
    vigencia_fim_original: Optional[str]
    vigencia_fim_final: Optional[str]

    # ── campos de auditoria de validação ──────────────────────────────────────
    status_validacao: str
    responsavel_validacao: Optional[str]
    data_hora_validacao: Optional[str]
    observacao_validacao: Optional[str]

    # ── timestamp de geração da base aprovada ─────────────────────────────────
    data_hora_geracao: str

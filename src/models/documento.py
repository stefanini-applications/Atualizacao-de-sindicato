"""Modelo de dados para documentos sindicais."""

from dataclasses import dataclass, field
from typing import Optional, List

TIPOS_VALIDOS: frozenset = frozenset([
    "CCT",
    "termo aditivo",
    "acordo coletivo",
    "outro documento sindical",
])

STATUS_VALIDOS: frozenset = frozenset([
    "pendente de validação",
    "vigente",
    "substituído",
    "vencido",
    "erro de classificação",
])

# Subconjunto crítico: ausência de qualquer um invalida para extração
CAMPOS_CRITICOS: List[str] = ["uf", "sindicato", "tipo_documento"]

# Campos completos esperados para cadastro íntegro
CAMPOS_ESPERADOS: List[str] = [
    "nome_arquivo",
    "caminho",
    "uf",
    "sindicato",
    "tipo_documento",
    "ano_referencia",
    "status",
    "data_inclusao",
    "responsavel",
]

UFS_VALIDAS: frozenset = frozenset([
    "AC", "AL", "AM", "AP", "BA", "CE", "DF", "ES", "GO",
    "MA", "MG", "MS", "MT", "PA", "PB", "PE", "PI", "PR",
    "RJ", "RN", "RO", "RR", "RS", "SC", "SE", "SP", "TO",
])


@dataclass
class DocumentoSindical:
    """Representa um documento sindical com seus metadados de cadastro e rastreabilidade."""

    id: str
    nome_arquivo: str
    caminho: str  # caminho relativo POSIX a partir da raiz do repositório
    uf: Optional[str]
    sindicato: Optional[str]
    tipo_documento: Optional[str]  # restrito a TIPOS_VALIDOS
    ano_referencia: Optional[str]
    status: str  # restrito a STATUS_VALIDOS
    data_inclusao: str  # ISO 8601
    responsavel: Optional[str]
    # campos de auditoria (armazenados mas não exibidos na lista consolidada)
    vigencia_inicial: Optional[str]
    vigencia_final: Optional[str]

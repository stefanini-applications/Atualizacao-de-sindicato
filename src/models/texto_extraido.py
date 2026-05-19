"""Modelo de dados para texto extraído de documentos sindicais."""

from dataclasses import dataclass
from typing import Optional

STATUS_EXTRACAO: frozenset = frozenset([
    "extraido_com_sucesso",
    "sem_texto_extraivel",
    "erro_na_leitura",
    "documento_nao_encontrado",
    "nao_elegivel_para_extracao",
])


@dataclass
class TextoExtraido:
    """Texto bruto extraído de um PDF sindical com rastreabilidade completa ao documento de origem."""

    caminho: str           # caminho relativo POSIX a partir da raiz do repositório
    nome_arquivo: str
    uf: Optional[str]
    sindicato: Optional[str]
    tipo_documento: Optional[str]
    ano_referencia: Optional[str]
    texto: str             # texto extraído; "" para status não-sucesso
    num_caracteres: int    # len(texto); 0 para status não-sucesso
    status: str            # um dos valores em STATUS_EXTRACAO
    data_processamento: str  # ISO 8601

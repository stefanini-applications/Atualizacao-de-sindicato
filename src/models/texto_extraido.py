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

STATUS_OCR: frozenset = frozenset([
    "extraido_via_ocr",
    "ocr_sem_texto_reconhecido",
    "erro_no_ocr",
])

STATUS_CONSOLIDACAO: frozenset = frozenset([
    "texto_nativo",
    "texto_ocr",
    "sem_texto_final",
    "erro_consolidacao",
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


@dataclass
class TextoConsolidado:
    """Registro consolidado de texto de um PDF sindical, combinando extração nativa e OCR."""

    caminho: str
    nome_arquivo: str
    uf: Optional[str]
    sindicato: Optional[str]
    tipo_documento: Optional[str]
    ano_referencia: Optional[str]
    texto_final: str          # texto escolhido; "" quando sem_texto_final ou erro_consolidacao
    num_caracteres: int       # len(texto_final)
    origem_texto: str         # um dos valores em STATUS_CONSOLIDACAO
    status_consolidado: str   # um dos valores em STATUS_CONSOLIDACAO
    data_consolidacao: str    # ISO 8601

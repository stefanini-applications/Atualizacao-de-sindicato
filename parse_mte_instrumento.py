#!/usr/bin/env python3
"""
Parser independente de instrumentos coletivos oficiais do MTE (Sistema Mediador).

Este módulo é totalmente isolado da lógica de extração dos PDFs CCT existentes
no produto. Sua única responsabilidade é receber o caminho de um arquivo oficial
MTE (PDF local) ou uma fonte textual, e retornar um dicionário de campos no
formato esperado por enrich_from_mte_fallback().

Separação obrigatória (AC7 — PRJ-66):
- Nenhuma função ou módulo responsável pelo parsing dos PDFs CCT originais é
  importado, reutilizado ou modificado aqui.
- Mudanças neste parser não afetam o pipeline de ingestão de CCTs em produção.

Tipos de referência suportados:
  - "arquivo": processa o arquivo e extrai campos com evidência textual.
  - "url":     apenas registra a referência; não altera itens_cct.
  - "codigo_instrumento": apenas registra a referência; não altera itens_cct.
  - "manual":  registra metadados; não preenche itens_cct sem fonte_textual extraída.

Formato de retorno de parse_mte_instrumento():
    {
        "numero_registro": str | None,
        "tipo": str | None,
        "vigencia_inicio": str | None,     # YYYY-MM-DD
        "vigencia_fim": str | None,        # YYYY-MM-DD
        "url_documento": str | None,
        "campos": {
            "<nome_campo>": {
                "valor": float | None,
                "percentual": float | None,
                "fonte_textual": str,       # trecho do instrumento
                "observacao": str,
            }
        }
    }
    Retorna None quando o arquivo não é processável ou não há evidência textual
    suficiente para preencher campos de itens_cct.
"""

import logging
import os
import re
from datetime import date
from typing import Any

logger = logging.getLogger("parse_mte_instrumento")

# ──────────────────────────────────────────────────────────────────────────────
# Campos elegíveis e seus padrões de extração
# ──────────────────────────────────────────────────────────────────────────────

# Mapping: campo → lista de regexes para captura de valor monetário ou percentual.
# Cada padrão deve capturar um grupo nomeado "valor" (float ou int) ou
# "percentual" (float). Os padrões são aplicados ao texto completo do instrumento.
_FIELD_PATTERNS: dict[str, list[dict[str, Any]]] = {
    "piso_salarial": [
        {
            "regex": re.compile(
                r"piso\s+salarial[^\n]{0,120}?R\$\s*(?P<valor>[\d]{1,3}(?:[.,]\d{3})*(?:[.,]\d{2}))",
                re.IGNORECASE,
            ),
            "type": "valor",
        },
        {
            "regex": re.compile(
                r"sal[aá]rio[\s\-]+base[^\n]{0,120}?R\$\s*(?P<valor>[\d]{1,3}(?:[.,]\d{3})*(?:[.,]\d{2}))",
                re.IGNORECASE,
            ),
            "type": "valor",
        },
    ],
    "adicional_noturno": [
        {
            "regex": re.compile(
                r"adicional\s+noturno[^\n]{0,120}?(?P<percentual>[\d]+(?:[.,]\d+)?)\s*%",
                re.IGNORECASE,
            ),
            "type": "percentual",
        },
    ],
    "auxilio_alimentacao": [
        {
            "regex": re.compile(
                r"aux[íi]lio[\s\-]+alimenta[çc][aã]o[^\n]{0,120}?R\$\s*(?P<valor>[\d]{1,3}(?:[.,]\d{3})*(?:[.,]\d{2}))",
                re.IGNORECASE,
            ),
            "type": "valor",
        },
        {
            "regex": re.compile(
                r"vale[\s\-]+refei[çc][aã]o[^\n]{0,120}?R\$\s*(?P<valor>[\d]{1,3}(?:[.,]\d{3})*(?:[.,]\d{2}))",
                re.IGNORECASE,
            ),
            "type": "valor",
        },
    ],
    "plr": [
        {
            "regex": re.compile(
                r"PLR[^\n]{0,160}?R\$\s*(?P<valor>[\d]{1,3}(?:[.,]\d{3})*(?:[.,]\d{2}))",
                re.IGNORECASE,
            ),
            "type": "valor",
        },
        {
            "regex": re.compile(
                r"participa[çc][aã]o\s+nos\s+lucros[^\n]{0,160}?R\$\s*(?P<valor>[\d]{1,3}(?:[.,]\d{3})*(?:[.,]\d{2}))",
                re.IGNORECASE,
            ),
            "type": "valor",
        },
    ],
    "hora_extra": [
        {
            "regex": re.compile(
                r"hora\s+extra(?:\s+de)?\s*(?:50|100)[\s%]",
                re.IGNORECASE,
            ),
            "type": "percentual",
            "static_percentual": None,  # extracted from match group when present
        },
        {
            "regex": re.compile(
                r"hora\s+extraordin[aá]ria[^\n]{0,120}?(?P<percentual>[\d]+(?:[.,]\d+)?)\s*%",
                re.IGNORECASE,
            ),
            "type": "percentual",
        },
    ],
    "sobreaviso": [
        {
            "regex": re.compile(
                r"sobreaviso[^\n]{0,120}?(?P<percentual>[\d]+(?:[.,]\d+)?)\s*%",
                re.IGNORECASE,
            ),
            "type": "percentual",
        },
    ],
    "jornada": [
        {
            "regex": re.compile(
                r"jornada[^\n]{0,120}?(?P<valor>[\d]+)\s*(?:horas?|h(?:\s|\/|\b))",
                re.IGNORECASE,
            ),
            "type": "valor",
        },
    ],
}

# ──────────────────────────────────────────────────────────────────────────────
# Padrões de metadados do instrumento
# ──────────────────────────────────────────────────────────────────────────────

_VIGENCIA_INICIO_PATTERN = re.compile(
    r"vig[êe]ncia\s+(?:de\s+)?(?P<inicio>\d{2}/\d{2}/\d{4})",
    re.IGNORECASE,
)
_VIGENCIA_FIM_PATTERN = re.compile(
    r"(?:at[eé]|a\s+)?(?P<fim>\d{2}/\d{2}/\d{4})",
    re.IGNORECASE,
)
_NUMERO_REGISTRO_PATTERN = re.compile(
    r"(?:n[uú]mero\s+(?:do\s+)?registro|registro\s+n[uú]mero)[:\s]+(?P<num>[\w\-/\.]+)",
    re.IGNORECASE,
)


def _parse_br_float(text: str) -> float | None:
    """Convert Brazilian-formatted number string to float."""
    try:
        cleaned = text.replace(".", "").replace(",", ".")
        return float(cleaned)
    except (ValueError, AttributeError):
        return None


def _parse_br_date(text: str) -> str | None:
    """Convert DD/MM/YYYY to YYYY-MM-DD. Returns None on failure."""
    try:
        d, m, y = text.strip().split("/")
        return f"{y}-{m.zfill(2)}-{d.zfill(2)}"
    except (ValueError, AttributeError):
        return None


def _extract_surrounding_line(text: str, match: re.Match, context_chars: int = 200) -> str:
    """Extract the surrounding line/context for a regex match as fonte_textual."""
    start = max(0, match.start() - context_chars // 2)
    end = min(len(text), match.end() + context_chars // 2)
    snippet = text[start:end].strip()
    # Collapse excessive whitespace / newlines for readability
    snippet = re.sub(r"\s{3,}", " … ", snippet)
    return snippet


def _extract_text_from_pdf(file_path: str) -> str | None:
    """
    Extract raw text from a PDF file using pdfminer.six (if available) or
    PyPDF2 as fallback. Returns None when no library is available or extraction
    fails.

    This function is intentionally isolated from extract_cct_items.py and any
    other CCT PDF parsing modules. It does NOT call, import, or depend on any
    function from those modules.
    """
    # Attempt pdfminer.six first (better text extraction quality)
    try:
        from pdfminer.high_level import extract_text as pdfminer_extract  # type: ignore

        text = pdfminer_extract(file_path)
        if text and text.strip():
            logger.debug("Texto extraído via pdfminer.six: %d chars", len(text))
            return text
    except ImportError:
        logger.debug("pdfminer.six não disponível; tentando PyPDF2.")
    except Exception as exc:  # noqa: BLE001
        logger.warning("pdfminer.six falhou para %s: %s", file_path, exc)

    # Fallback: PyPDF2
    try:
        import PyPDF2  # type: ignore

        with open(file_path, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            pages = [page.extract_text() or "" for page in reader.pages]
        text = "\n".join(pages)
        if text.strip():
            logger.debug("Texto extraído via PyPDF2: %d chars", len(text))
            return text
    except ImportError:
        logger.debug("PyPDF2 não disponível.")
    except Exception as exc:  # noqa: BLE001
        logger.warning("PyPDF2 falhou para %s: %s", file_path, exc)

    logger.warning(
        "Nenhuma biblioteca de extração de PDF disponível ou extração falhou para: %s. "
        "Instale pdfminer.six (pip install pdfminer.six) para habilitar o parser MTE.",
        file_path,
    )
    return None


def _extract_campos_from_text(text: str) -> dict[str, dict[str, Any]]:
    """
    Apply field extraction patterns to the instrument text.
    Returns a dict of campo_nome → {valor, percentual, fonte_textual, observacao}.
    Only fields with a valid match and extractable value are included.
    """
    campos: dict[str, dict[str, Any]] = {}

    for campo_nome, patterns in _FIELD_PATTERNS.items():
        for pat_def in patterns:
            regex: re.Pattern = pat_def["regex"]
            pat_type: str = pat_def["type"]
            match = regex.search(text)
            if match is None:
                continue

            fonte_textual = _extract_surrounding_line(text, match)
            valor: float | None = None
            percentual: float | None = None

            try:
                raw = match.group("valor") if pat_type == "valor" else match.group("percentual")
                parsed = _parse_br_float(raw)
            except IndexError:
                # Pattern has no capture group (e.g., static hour_extra pattern)
                parsed = pat_def.get("static_percentual")

            if parsed is None:
                continue

            if pat_type == "valor":
                valor = parsed
            else:
                percentual = parsed

            campos[campo_nome] = {
                "valor": valor,
                "percentual": percentual,
                "fonte_textual": fonte_textual,
                "observacao": (
                    f"Extraído do instrumento oficial MTE por parser independente "
                    f"(campo: {campo_nome}). Requer validação com o documento original."
                ),
            }
            break  # first matching pattern wins for this campo

    return campos


def _extract_metadata_from_text(text: str) -> dict[str, str | None]:
    """Extract instrument metadata (vigencia, numero_registro) from text."""
    numero_registro: str | None = None
    vigencia_inicio: str | None = None
    vigencia_fim: str | None = None

    m = _NUMERO_REGISTRO_PATTERN.search(text)
    if m:
        numero_registro = m.group("num").strip()

    m_ini = _VIGENCIA_INICIO_PATTERN.search(text)
    if m_ini:
        vigencia_inicio = _parse_br_date(m_ini.group("inicio"))
        # Look for end date after the start date match
        remaining = text[m_ini.end():]
        m_fim = _VIGENCIA_FIM_PATTERN.search(remaining)
        if m_fim:
            vigencia_fim = _parse_br_date(m_fim.group("fim"))

    return {
        "numero_registro": numero_registro,
        "vigencia_inicio": vigencia_inicio,
        "vigencia_fim": vigencia_fim,
    }


# ──────────────────────────────────────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────────────────────────────────────


def parse_mte_instrumento(
    file_path: str | None = None,
    tipo_referencia: str = "arquivo",
    url: str | None = None,
    codigo_instrumento: str | None = None,
    observacao: str | None = None,
) -> dict | None:
    """
    Parse an official MTE instrument and return a dict compatible with
    enrich_from_mte_fallback().

    This function is a completely independent component — it does NOT import
    or call any function from extract_cct_items.py or any other module
    responsible for parsing the original CCT PDFs already loaded in the product.

    Args:
        file_path:          Path to the MTE instrument file (PDF). Required when
                            tipo_referencia == "arquivo".
        tipo_referencia:    One of "arquivo", "url", "codigo_instrumento", "manual".
        url:                Official MTE URL for reference registration.
        codigo_instrumento: MTE instrument code for reference registration.
        observacao:         Operator note (used only for "manual" type).

    Returns:
        dict compatible with enrich_from_mte_fallback() when the file is
        processable and contains extractable field values, or:
            {
                "numero_registro": None,
                "tipo": None,
                "vigencia_inicio": None,
                "vigencia_fim": None,
                "url_documento": url,
                "campos": {},          # empty — reference only, no itens_cct changes
                "tipo_referencia": tipo_referencia,
                "observacao": ...,
            }
        for url/codigo_instrumento/manual types (AC4 / AC6).
        Returns None only on unrecoverable errors.
    """
    if tipo_referencia not in ("arquivo", "url", "codigo_instrumento", "manual"):
        logger.error(
            "tipo_referencia inválido: %r. Valores aceitos: arquivo, url, "
            "codigo_instrumento, manual.",
            tipo_referencia,
        )
        return None

    # ── Non-processable reference types (AC4) ─────────────────────────────────
    if tipo_referencia in ("url", "codigo_instrumento"):
        logger.info(
            "Referência do tipo %r registrada (url=%r, codigo=%r). "
            "Nenhum campo itens_cct será alterado.",
            tipo_referencia,
            url,
            codigo_instrumento,
        )
        return {
            "numero_registro": codigo_instrumento,
            "tipo": None,
            "vigencia_inicio": None,
            "vigencia_fim": None,
            "url_documento": url,
            "campos": {},
            "tipo_referencia": tipo_referencia,
            "observacao": observacao or f"Referência {tipo_referencia} registrada; sem conteúdo processável.",
        }

    # ── Manual type (AC6) ─────────────────────────────────────────────────────
    if tipo_referencia == "manual":
        logger.info(
            "Referência do tipo 'manual' registrada. Metadados do operador armazenados "
            "em fonte_oficial_mte. Nenhum campo itens_cct será preenchido sem fonte_textual "
            "extraída de arquivo processável."
        )
        return {
            "numero_registro": codigo_instrumento,
            "tipo": None,
            "vigencia_inicio": None,
            "vigencia_fim": None,
            "url_documento": url,
            "campos": {},  # AC6: campos vazio — nunca preenche itens_cct via manual
            "tipo_referencia": "manual",
            "observacao": observacao or "Metadados manuais registrados pelo operador.",
        }

    # ── Arquivo type: parse the PDF ───────────────────────────────────────────
    if not file_path:
        logger.error(
            "tipo_referencia='arquivo' requer file_path. Nenhum arquivo informado."
        )
        return None

    if not os.path.isfile(file_path):
        logger.error("Arquivo MTE não encontrado: %s", file_path)
        return None

    logger.info("Processando arquivo MTE: %s", file_path)

    text = _extract_text_from_pdf(file_path)
    if not text or not text.strip():
        logger.warning(
            "Não foi possível extrair texto do arquivo MTE: %s. "
            "Nenhum campo itens_cct será preenchido.",
            file_path,
        )
        return {
            "numero_registro": None,
            "tipo": None,
            "vigencia_inicio": None,
            "vigencia_fim": None,
            "url_documento": url,
            "campos": {},
            "tipo_referencia": tipo_referencia,
            "observacao": f"Arquivo não processável: {os.path.basename(file_path)}",
        }

    metadata = _extract_metadata_from_text(text)
    campos = _extract_campos_from_text(text)

    logger.info(
        "Parser MTE: %d campo(s) extraído(s) de %s",
        len(campos),
        os.path.basename(file_path),
    )
    for nome in campos:
        logger.debug("  campo extraído: %s", nome)

    return {
        "numero_registro": metadata["numero_registro"],
        "tipo": "CCT",  # default; can be overridden by caller if known
        "vigencia_inicio": metadata["vigencia_inicio"],
        "vigencia_fim": metadata["vigencia_fim"],
        "url_documento": url,
        "campos": campos,
        "tipo_referencia": tipo_referencia,
        "observacao": observacao,
    }


def build_fonte_oficial_mte(
    tipo_referencia: str,
    instrumento: dict | None,
    arquivo_origem: str | None = None,
    url: str | None = None,
    codigo_instrumento: str | None = None,
    observacao: str | None = None,
) -> dict:
    """
    Build the `fonte_oficial_mte` metadata block to be stored in a CCT/ACT record.

    Args:
        tipo_referencia:    "arquivo", "url", "codigo_instrumento", or "manual".
        instrumento:        Result of parse_mte_instrumento(), or None.
        arquivo_origem:     Basename of the source file, if applicable.
        url:                MTE URL reference.
        codigo_instrumento: MTE instrument code.
        observacao:         Operator note.

    Returns:
        A dict with `fonte_oficial_mte` fields (AC2 / AC4 / AC6).
    """
    today = date.today().isoformat()

    if instrumento is None:
        status_consulta = "nao_localizado"
        disponivel = False
    else:
        # "localizado" even for url/codigo/manual — the reference itself was registered
        status_consulta = "localizado"
        disponivel = bool(instrumento.get("campos"))

    return {
        "disponivel": disponivel,
        "tipo_referencia": tipo_referencia,
        "url": url or (instrumento.get("url_documento") if instrumento else None),
        "codigo_instrumento": codigo_instrumento or (
            instrumento.get("numero_registro") if instrumento else None
        ),
        "arquivo_origem": arquivo_origem,
        "data_consulta": today,
        "status_consulta": status_consulta,
        "observacao": observacao or (
            instrumento.get("observacao") if instrumento else None
        ),
    }

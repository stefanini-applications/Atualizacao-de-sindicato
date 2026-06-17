#!/usr/bin/env python3
"""
Parser independente de instrumentos oficiais do MTE (Sistema Mediador).

Este módulo é completamente isolado da lógica de extração dos PDFs CCT
existente no produto (extract_cct_items.py). Sua única responsabilidade é
receber o caminho de um arquivo oficial do MTE e retornar um dicionário de
campos no formato esperado por enrich_from_mte_fallback().

Nenhuma função ou módulo de extract_cct_items.py é importado ou reutilizado.

Formato de retorno (compatível com enrich_from_mte_fallback):
    {
        "numero_registro": str | None,
        "tipo": str,                    # "CCT" | "ACT" | "termo_aditivo" | "instrumento"
        "vigencia_inicio": str | None,  # YYYY-MM-DD
        "vigencia_fim": str | None,     # YYYY-MM-DD
        "url_documento": str | None,
        "campos": {
            "<nome_campo>": {
                "valor": float | None,
                "percentual": float | None,
                "valor_textual": str | None,
                "fonte_textual": str,   # trecho literal do instrumento oficial
                "observacao": str,
            }
        }
    }

Retorna None quando o arquivo não pode ser processado ou não contém texto
suficiente para extração confiável.

Uso direto (diagnóstico):
    python3 parse_mte_instrumento.py caminho/instrumento.pdf
"""

import logging
import os
import re
import sys
from typing import Any

logger = logging.getLogger("parse_mte_instrumento")

# ──────────────────────────────────────────────────────────────────────────────
# Padrões de extração por campo
# ──────────────────────────────────────────────────────────────────────────────

# Janela de contexto em caracteres ao redor do valor para fonte_textual
_CONTEXT_WINDOW = 200

# Campos elegíveis e suas configurações de busca
_FIELD_PATTERNS: dict[str, dict[str, Any]] = {
    "piso_salarial": {
        "keywords": [
            r"piso\s+salarial",
            r"sal[aá]rio[\s\-]+m[ií]nimo[\s\-]+(?:profissional|categorial|da\s+categoria)",
            r"piso\s+(?:único|unico|cct|b[aá]sico)",
            r"remunera[cç][aã]o\s+m[ií]nima",
        ],
        "value_pattern": r"R\$\s*([\d.,]+)",
        "value_type": "valor",
    },
    "adicional_noturno": {
        "keywords": [
            r"adicional\s+noturno",
            r"hora\s+noturna",
            r"trabalho\s+noturno",
        ],
        "value_pattern": r"(\d{1,3}(?:[.,]\d+)?)\s*%",
        "value_type": "percentual",
    },
    "auxilio_alimentacao": {
        "keywords": [
            r"aux[ií]lio[\s\-]+alimenta[cç][aã]o",
            r"vale[\s\-]+refei[cç][aã]o",
            r"ticket[\s\-]+alimenta[cç][aã]o",
            r"cesta[\s\-]+b[aá]sica",
        ],
        "value_pattern": r"R\$\s*([\d.,]+)",
        "value_type": "valor",
    },
    "plr": {
        "keywords": [
            r"participa[cç][aã]o\s+nos\s+lucros",
            r"\bPLR\b",
            r"PLR\s*[\-/]",
        ],
        "value_pattern": r"R\$\s*([\d.,]+)|(\d{1,3}(?:[.,]\d+)?)\s*%",
        "value_type": "auto",
    },
    "hora_extra": {
        "keywords": [
            r"hora\s+extra",
            r"horas?\s+extraordin[aá]rias?",
            r"adicional\s+de\s+hora\s+extra",
        ],
        "value_pattern": r"(\d{1,3}(?:[.,]\d+)?)\s*%",
        "value_type": "percentual",
    },
    "sobreaviso": {
        "keywords": [
            r"sobreaviso",
            r"sobre[\s\-]+aviso",
        ],
        "value_pattern": r"(\d{1,3}(?:[.,]\d+)?)\s*%|R\$\s*([\d.,]+)",
        "value_type": "auto",
    },
    "jornada": {
        "keywords": [
            r"jornada\s+de\s+trabalho",
            r"carga\s+hor[aá]ria",
            r"(\d{2})\s*h(?:oras?)?\s*/?\s*semana",
        ],
        "value_pattern": r"(\d{2,3})\s*(?:h(?:oras?)?\s*/?\s*(?:semana|semanal|mensais?))",
        "value_type": "valor",
    },
}

# Padrões para metadados do instrumento
_META_PATTERNS = {
    "numero_registro": [
        r"n[úu]mero\s+de\s+registro\s*[:\-]?\s*([A-Z0-9\-/\.]+)",
        r"processo\s+n[°º\.]\s*([\d\./\-]+)",
        r"registro\s+MTE\s*[:\-]?\s*([A-Z0-9\-/\.]+)",
    ],
    "tipo": [
        r"\b(CCT)\b",
        r"\b(ACT)\b",
        r"acordo\s+coletivo\s+de\s+trabalho",
        r"conven[cç][aã]o\s+coletiva\s+de\s+trabalho",
        r"termo\s+aditivo",
    ],
    "vigencia": [
        r"vig[êe]ncia\s*(?:de\s*)?(\d{2}/\d{2}/\d{4})\s+a\s+(\d{2}/\d{2}/\d{4})",
        r"per[ií]odo\s*[:\-]?\s*(\d{2}/\d{2}/\d{4})\s+(?:a|até)\s+(\d{2}/\d{2}/\d{4})",
    ],
}


# ──────────────────────────────────────────────────────────────────────────────
# Utilitários internos
# ──────────────────────────────────────────────────────────────────────────────


def _normalize_br_float(raw: str) -> float | None:
    """Convert Brazilian-format number string to float.

    Handles both "1.234,56" and "1234.56" formats.
    """
    raw = raw.strip()
    if not raw:
        return None
    # Brazilian format: dots as thousands separator, comma as decimal
    if "," in raw:
        raw = raw.replace(".", "").replace(",", ".")
    try:
        return float(raw)
    except ValueError:
        return None


def _extract_context(text: str, match_start: int, match_end: int) -> str:
    """Extract a snippet of text around a match for fonte_textual."""
    start = max(0, match_start - _CONTEXT_WINDOW // 2)
    end = min(len(text), match_end + _CONTEXT_WINDOW // 2)
    snippet = text[start:end].strip()
    # Collapse multiple whitespace/newlines for readability
    snippet = re.sub(r"\s+", " ", snippet)
    return snippet


def _find_field_in_text(
    text: str, field_name: str, config: dict[str, Any]
) -> dict[str, Any] | None:
    """Search for a field's value in the extracted text.

    Returns a compatible field dict or None if not found.
    """
    text_lower = text.lower()
    keywords = config["keywords"]
    value_pattern = config["value_pattern"]
    value_type = config["value_type"]

    for keyword in keywords:
        keyword_re = re.compile(keyword, re.IGNORECASE)
        kw_match = keyword_re.search(text)
        if not kw_match:
            continue

        # Search for value in the 500-character window after the keyword
        search_start = kw_match.start()
        search_end = min(len(text), kw_match.end() + 500)
        window = text[search_start:search_end]

        val_match = re.search(value_pattern, window, re.IGNORECASE)
        if not val_match:
            continue

        # Determine value and type
        valor: float | None = None
        percentual: float | None = None
        valor_textual: str | None = None

        if value_type == "valor":
            raw = val_match.group(1)
            valor = _normalize_br_float(raw)
            if valor is None:
                continue
        elif value_type == "percentual":
            raw = val_match.group(1)
            percentual = _normalize_br_float(raw)
            if percentual is None:
                continue
        elif value_type == "auto":
            # Try both: R$ → valor, % → percentual
            groups = val_match.groups()
            for g in groups:
                if g is not None:
                    num = _normalize_br_float(g)
                    if num is not None:
                        if "%" in val_match.group(0):
                            percentual = num
                        else:
                            valor = num
                        break
            if valor is None and percentual is None:
                continue

        # Build fonte_textual from surrounding context
        abs_val_start = search_start + val_match.start()
        abs_val_end = search_start + val_match.end()
        fonte_textual = _extract_context(text, kw_match.start(), abs_val_end)

        logger.debug("  campo '%s' encontrado: valor=%s percentual=%s", field_name, valor, percentual)
        return {
            "valor": valor,
            "percentual": percentual,
            "valor_textual": valor_textual,
            "fonte_textual": fonte_textual,
            "observacao": (
                f"Extraído do instrumento oficial MTE via parser independente. "
                f"Campo: {field_name}."
            ),
        }

    return None


def _extract_metadata(text: str) -> dict[str, str | None]:
    """Extract instrument-level metadata (registration number, type, validity)."""
    meta: dict[str, str | None] = {
        "numero_registro": None,
        "tipo": "instrumento",
        "vigencia_inicio": None,
        "vigencia_fim": None,
    }

    # Número de registro
    for pattern in _META_PATTERNS["numero_registro"]:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            meta["numero_registro"] = m.group(1).strip()
            break

    # Tipo do instrumento
    tipo_map = {
        "CCT": "CCT",
        "ACT": "ACT",
        "acordo coletivo de trabalho": "ACT",
        "convenção coletiva de trabalho": "CCT",
        "convencao coletiva de trabalho": "CCT",
        "termo aditivo": "termo_aditivo",
    }
    for pattern in _META_PATTERNS["tipo"]:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            matched_text = m.group(0).upper().strip()
            # Normalize
            for key, val in tipo_map.items():
                if key.upper() in matched_text:
                    meta["tipo"] = val
                    break
            break

    # Vigência
    for pattern in _META_PATTERNS["vigencia"]:
        m = re.search(pattern, text, re.IGNORECASE)
        if m and len(m.groups()) >= 2:
            def _to_iso(date_str: str) -> str | None:
                parts = date_str.split("/")
                if len(parts) == 3:
                    return f"{parts[2]}-{parts[1]}-{parts[0]}"
                return None

            meta["vigencia_inicio"] = _to_iso(m.group(1))
            meta["vigencia_fim"] = _to_iso(m.group(2))
            break

    return meta


def _extract_text_from_pdf(file_path: str) -> str | None:
    """Extract plain text from a PDF file using pdfplumber.

    Returns None if the file cannot be read or produces no text.
    """
    try:
        import pdfplumber  # type: ignore[import]
    except ImportError:
        logger.error(
            "pdfplumber não está instalado. Instale com: pip install pdfplumber"
        )
        return None

    try:
        pages: list[str] = []
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    pages.append(page_text)
        full_text = "\n".join(pages)
        if not full_text.strip():
            logger.warning("Nenhum texto extraído do PDF: %s", file_path)
            return None
        return full_text
    except Exception as exc:  # noqa: BLE001
        logger.error("Erro ao processar PDF '%s': %s", file_path, exc)
        return None


# ──────────────────────────────────────────────────────────────────────────────
# API pública
# ──────────────────────────────────────────────────────────────────────────────


def parse_mte_pdf(file_path: str) -> dict | None:
    """Parse an official MTE instrument PDF and extract eligible CCT fields.

    This function is completely independent from the CCT PDF extraction logic
    in extract_cct_items.py. It uses its own text extraction and field-search
    pipeline to produce a dict compatible with enrich_from_mte_fallback().

    Args:
        file_path: Absolute or relative path to the MTE instrument PDF file.

    Returns:
        A dict in the instrumento_mte format, or None if:
          - the file does not exist
          - pdfplumber is not installed
          - the file produces no extractable text
          - no eligible fields are found

        On success the dict contains at least one entry in "campos".
    """
    if not os.path.isfile(file_path):
        logger.error("Arquivo não encontrado: %s", file_path)
        return None

    logger.info("Iniciando parse do instrumento MTE: %s", file_path)
    text = _extract_text_from_pdf(file_path)
    if text is None:
        return None

    logger.debug("Texto extraído: %d caracteres", len(text))

    # Extract instrument-level metadata
    meta = _extract_metadata(text)
    logger.info(
        "  Metadados: numero_registro=%s tipo=%s vigencia=%s → %s",
        meta["numero_registro"],
        meta["tipo"],
        meta["vigencia_inicio"],
        meta["vigencia_fim"],
    )

    # Extract eligible fields
    campos: dict[str, dict] = {}
    for field_name, config in _FIELD_PATTERNS.items():
        result = _find_field_in_text(text, field_name, config)
        if result is not None:
            campos[field_name] = result
            logger.info("  Campo extraído: %s → %s", field_name, result.get("valor") or result.get("percentual"))

    if not campos:
        logger.warning(
            "Nenhum campo elegível encontrado no instrumento MTE: %s", file_path
        )
        return None

    instrumento: dict = {
        "numero_registro": meta["numero_registro"],
        "tipo": meta["tipo"],
        "vigencia_inicio": meta["vigencia_inicio"],
        "vigencia_fim": meta["vigencia_fim"],
        "url_documento": None,
        "arquivo_origem": os.path.basename(file_path),
        "campos": campos,
    }
    logger.info(
        "Parse MTE concluído: %d campo(s) extraído(s) de '%s'",
        len(campos),
        file_path,
    )
    return instrumento


# ──────────────────────────────────────────────────────────────────────────────
# CLI de diagnóstico
# ──────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import json

    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    if len(sys.argv) < 2:
        print(f"Uso: python3 {os.path.basename(__file__)} <caminho/instrumento.pdf>")
        sys.exit(1)

    resultado = parse_mte_pdf(sys.argv[1])
    if resultado is None:
        print("Nenhum dado extraído.")
        sys.exit(1)

    print(json.dumps(resultado, ensure_ascii=False, indent=2))

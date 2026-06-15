#!/usr/bin/env python3
"""
Parser independente de instrumentos oficiais MTE (CCT/ACT do Sistema Mediador).

Este módulo é um componente NOVO e INDEPENDENTE.
Ele NÃO importa nem reutiliza nenhuma função dos módulos de extração de PDFs CCT
(extract_cct_items.py ou qualquer outro módulo do pipeline de ingestão existente).

Responsabilidade única: receber o caminho de um arquivo oficial MTE e retornar
um dicionário de campos no formato esperado por enrich_from_mte_fallback().

Formato de retorno:
    {
        "status_extracao": "ok" | "sem_texto" | "arquivo_ausente" | "nao_processavel",
        "campos": {
            "<nome_campo>": {
                "valor": float | None,
                "percentual": float | None,
                "fonte_textual": str,
                "observacao": str,
            }
        }
    }

Campos elegíveis para extração (devem corresponder a ELIGIBLE_FIELDS em enrich_mte_fallback.py):
    piso_salarial, adicional_noturno, auxilio_alimentacao, plr,
    hora_extra, sobreaviso, jornada
"""

import logging
import os
import re
import subprocess
import unicodedata

logger = logging.getLogger("parse_mte_instrumento")

# Observação padrão para campos extraídos do instrumento oficial MTE
_OBS_MTE = (
    "Informação extraída do instrumento oficial MTE por não ter sido "
    "localizada no PDF original da CCT."
)

# ─────────────────────────────────────────────────────────────────────────────
# Extração de texto do arquivo
# ─────────────────────────────────────────────────────────────────────────────


def extract_text_from_mte_file(file_path: str) -> tuple[str, str]:
    """
    Extract raw text from a file (PDF or plain text).

    Supports:
      - Plain text files (.txt) — read directly.
      - PDF files — attempt extraction via pdftotext subprocess.

    Returns:
        (text, status) where status is one of:
            "ok"              — text extracted successfully
            "sem_texto"       — file found but no readable text extracted
            "arquivo_ausente" — file not found at path
            "nao_processavel" — tool unavailable or unrecognised format
    """
    if not os.path.isfile(file_path):
        logger.warning("Arquivo MTE não encontrado: %s", file_path)
        return "", "arquivo_ausente"

    ext = os.path.splitext(file_path)[1].lower()

    # Plain text: read directly
    if ext in (".txt",):
        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as fh:
                text = fh.read()
            if text.strip():
                return text, "ok"
            return "", "sem_texto"
        except OSError as exc:
            logger.error("Erro ao ler arquivo de texto: %s — %s", file_path, exc)
            return "", "nao_processavel"

    # PDF: try pdftotext
    if ext == ".pdf":
        try:
            result = subprocess.run(
                ["pdftotext", "-layout", os.path.abspath(file_path), "-"],
                capture_output=True,
                text=True,
                timeout=60,
                check=False,
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout, "ok"
            if result.returncode == 0:
                return "", "sem_texto"
            logger.warning("pdftotext falhou (código %d): %s", result.returncode, result.stderr.strip())
            return "", "nao_processavel"
        except FileNotFoundError:
            logger.warning(
                "pdftotext não disponível. Instale poppler-utils para processar PDFs MTE."
            )
            return "", "nao_processavel"
        except subprocess.TimeoutExpired:
            logger.error("pdftotext excedeu o tempo limite para: %s", file_path)
            return "", "nao_processavel"
        except OSError as exc:
            logger.error("Erro ao invocar pdftotext: %s", exc)
            return "", "nao_processavel"

    logger.warning("Formato de arquivo não suportado pelo parser MTE: %s", ext)
    return "", "nao_processavel"


# ─────────────────────────────────────────────────────────────────────────────
# Utilitários de texto
# ─────────────────────────────────────────────────────────────────────────────


def _norm(text: str) -> str:
    """Lowercase and strip accents — for search purposes only."""
    nfkd = unicodedata.normalize("NFD", text)
    stripped = "".join(ch for ch in nfkd if unicodedata.category(ch) != "Mn")
    return stripped.lower()


def _extract_context(text: str, match: re.Match, window: int = 200) -> str:
    """Return the surrounding context of a regex match as the fonte_textual."""
    start = max(0, match.start() - window)
    end = min(len(text), match.end() + window)
    fragment = text[start:end].strip()
    # Collapse whitespace runs for readability
    fragment = re.sub(r"[ \t]{2,}", " ", fragment)
    return fragment


def _parse_brl_value(raw: str) -> float | None:
    """Parse a Brazilian Real value string (e.g. '1.620,00' or '1620,00') → float."""
    clean = raw.strip().replace(".", "").replace(",", ".")
    try:
        return float(clean)
    except ValueError:
        return None


def _parse_percent(raw: str) -> float | None:
    """Parse a percentage string (e.g. '25,00' or '25.5') → float."""
    clean = raw.strip().replace(",", ".")
    try:
        return float(clean)
    except ValueError:
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Extratores independentes por campo
# ─────────────────────────────────────────────────────────────────────────────


def _extract_piso_salarial(text: str, norm_text: str) -> dict | None:
    """
    Attempt to extract piso_salarial (base salary floor) from MTE instrument text.

    Looks for: PISO SALARIAL / SALÁRIO BASE / REMUNERAÇÃO MÍNIMA followed by a BRL value.
    Returns field dict or None if not found.
    Note: patterns use lowercase since norm_text is already lowercased via _norm().
    """
    patterns = [
        # "piso salarial de r$ 1.620,00"
        r"piso\s+salarial[^r\d]{0,30}r\$\s*([\d.,]+)",
        # "salário base de r$ 1.620,00"
        r"sal[a]rio\s+(?:base|m[i]nimo)[^r\d]{0,30}r\$\s*([\d.,]+)",
        # "remuneracao minima de r$ 1.620,00"
        r"remuneracao\s+minima[^r\d]{0,30}r\$\s*([\d.,]+)",
        # "piso: r$ 1.620,00"
        r"piso[:\s]+r\$\s*([\d.,]+)",
    ]
    for pattern in patterns:
        m = re.search(pattern, norm_text)
        if m:
            valor = _parse_brl_value(m.group(1))
            if valor and valor > 100:
                ctx = _extract_context(norm_text, m)
                return {
                    "valor": valor,
                    "percentual": None,
                    "fonte_textual": ctx,
                    "observacao": _OBS_MTE,
                }
    return None


def _extract_adicional_noturno(text: str, norm_text: str) -> dict | None:
    """
    Attempt to extract adicional_noturno (night shift premium %) from MTE instrument text.

    Looks for: ADICIONAL NOTURNO / HORA NOTURNA followed by a percentage value.
    """
    patterns = [
        # "adicional noturno de 25%"
        r"adicional\s+noturno[^%\d]{0,30}([\d.,]+)\s*%",
        # "hora noturna 25%"
        r"hora\s+noturna[^%\d]{0,30}([\d.,]+)\s*%",
        # "adicional noturno: 25%"
        r"adicional\s+noturno[:\s]+([\d.,]+)\s*%",
    ]
    for pattern in patterns:
        m = re.search(pattern, norm_text)
        if m:
            percentual = _parse_percent(m.group(1))
            if percentual is not None and 0 < percentual <= 100:
                ctx = _extract_context(norm_text, m)
                return {
                    "valor": None,
                    "percentual": percentual,
                    "fonte_textual": ctx,
                    "observacao": _OBS_MTE,
                }
    return None


def _extract_auxilio_alimentacao(text: str, norm_text: str) -> dict | None:
    """
    Attempt to extract auxilio_alimentacao (food allowance) from MTE instrument text.

    Returns a BRL value or None.
    """
    patterns = [
        r"auxilio\s+alimentacao[^r\d]{0,30}r\$\s*([\d.,]+)",
        r"auxilio[- ]refeicao[^r\d]{0,30}r\$\s*([\d.,]+)",
        r"vale[- ]refeicao[^r\d]{0,30}r\$\s*([\d.,]+)",
        r"vale[- ]alimentacao[^r\d]{0,30}r\$\s*([\d.,]+)",
    ]
    for pattern in patterns:
        m = re.search(pattern, norm_text)
        if m:
            valor = _parse_brl_value(m.group(1))
            if valor and valor > 0:
                ctx = _extract_context(norm_text, m)
                return {
                    "valor": valor,
                    "percentual": None,
                    "fonte_textual": ctx,
                    "observacao": _OBS_MTE,
                }
    return None


def _extract_plr(text: str, norm_text: str) -> dict | None:
    """
    Attempt to extract PLR (profit sharing) from MTE instrument text.

    May be a fixed value or percentage.
    """
    patterns_value = [
        r"participacao\s+nos\s+lucros[^r\d]{0,30}r\$\s*([\d.,]+)",
        r"\bplr\b[^r\d]{0,30}r\$\s*([\d.,]+)",
        r"p\.l\.r\.[^r\d]{0,30}r\$\s*([\d.,]+)",
    ]
    patterns_percent = [
        r"participacao\s+nos\s+lucros[^%\d]{0,30}([\d.,]+)\s*%",
        r"\bplr\b[^%\d]{0,30}([\d.,]+)\s*%",
    ]

    for pattern in patterns_value:
        m = re.search(pattern, norm_text)
        if m:
            valor = _parse_brl_value(m.group(1))
            if valor and valor > 0:
                ctx = _extract_context(norm_text, m)
                return {"valor": valor, "percentual": None, "fonte_textual": ctx, "observacao": _OBS_MTE}

    for pattern in patterns_percent:
        m = re.search(pattern, norm_text)
        if m:
            percentual = _parse_percent(m.group(1))
            if percentual is not None and percentual > 0:
                ctx = _extract_context(norm_text, m)
                return {"valor": None, "percentual": percentual, "fonte_textual": ctx, "observacao": _OBS_MTE}

    return None


def _extract_hora_extra(text: str, norm_text: str) -> dict | None:
    """
    Attempt to extract hora_extra (overtime premium %) from MTE instrument text.
    """
    patterns = [
        r"hora\s+extra(?:ordinaria)?[^%\d]{0,40}([\d.,]+)\s*%",
        r"horas?\s+extras?[^%\d]{0,40}([\d.,]+)\s*%",
        r"adicional\s+de\s+hora\s+extra[^%\d]{0,30}([\d.,]+)\s*%",
        r"hora\s+extra(?:ordinaria)?[:\s]+([\d.,]+)\s*%",
    ]
    for pattern in patterns:
        m = re.search(pattern, norm_text)
        if m:
            percentual = _parse_percent(m.group(1))
            if percentual is not None and percentual > 0:
                ctx = _extract_context(norm_text, m)
                return {
                    "valor": None,
                    "percentual": percentual,
                    "fonte_textual": ctx,
                    "observacao": _OBS_MTE,
                }
    return None


def _extract_sobreaviso(text: str, norm_text: str) -> dict | None:
    """
    Attempt to extract sobreaviso (on-call) percentage from MTE instrument text.
    """
    patterns = [
        r"sobreaviso[^%\d]{0,40}([\d.,]+)\s*%",
        r"regime\s+de\s+sobreaviso[^%\d]{0,40}([\d.,]+)\s*%",
        r"sobreaviso[:\s]+([\d.,]+)\s*%",
    ]
    for pattern in patterns:
        m = re.search(pattern, norm_text)
        if m:
            percentual = _parse_percent(m.group(1))
            if percentual is not None and percentual > 0:
                ctx = _extract_context(norm_text, m)
                return {
                    "valor": None,
                    "percentual": percentual,
                    "fonte_textual": ctx,
                    "observacao": _OBS_MTE,
                }
    return None


def _extract_jornada(text: str, norm_text: str) -> dict | None:
    """
    Attempt to extract jornada (working hours) from MTE instrument text.

    Returns a dict with valor = hours as float.
    """
    patterns = [
        # "jornada de 44 horas semanais"
        r"jornada[^0-9]{0,40}(\d{2,3})\s*horas?\s*(?:semanais?|semana)",
        # "jornada semanal de 44h"
        r"jornada\s+semanal[^0-9]{0,20}(\d{2,3})\s*h(?:oras?)?",
        # "carga horaria semanal de 44h"
        r"carga\s+horaria\s+(?:semanal\s+)?(?:de\s+)?(\d{2,3})\s*h(?:oras?)?",
    ]
    for pattern in patterns:
        m = re.search(pattern, norm_text)
        if m:
            horas = int(m.group(1))
            if 20 <= horas <= 60:  # Sanity: between 20h and 60h/week
                ctx = _extract_context(norm_text, m)
                return {
                    "valor": float(horas),
                    "percentual": None,
                    "fonte_textual": ctx,
                    "observacao": _OBS_MTE,
                }
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

# Mapping of ELIGIBLE_FIELDS names → extractor functions
# Each extractor takes (text: str, norm_text: str) -> dict | None
_FIELD_EXTRACTORS: dict[str, callable] = {
    "piso_salarial": _extract_piso_salarial,
    "adicional_noturno": _extract_adicional_noturno,
    "auxilio_alimentacao": _extract_auxilio_alimentacao,
    "plr": _extract_plr,
    "hora_extra": _extract_hora_extra,
    "sobreaviso": _extract_sobreaviso,
    "jornada": _extract_jornada,
}


def parse_mte_instrumento(file_path: str) -> dict:
    """
    Parse an official MTE instrument file and return a dict compatible with
    enrich_from_mte_fallback().

    This function is COMPLETELY INDEPENDENT of the CCT PDF pipeline.
    It does not call or import anything from the existing CCT extraction modules.

    Args:
        file_path: Absolute or relative path to the MTE instrument file
                   (PDF or .txt).

    Returns:
        {
            "status_extracao": "ok" | "sem_texto" | "arquivo_ausente" | "nao_processavel",
            "campos": {
                "<nome_campo>": {
                    "valor": float | None,
                    "percentual": float | None,
                    "fonte_textual": str,
                    "observacao": str,
                }
                ...
            }
        }
        When status_extracao != "ok" or no campos found, "campos" is {}.
    """
    text, status = extract_text_from_mte_file(file_path)

    if not text.strip():
        logger.info(
            "Parser MTE: nenhum texto extraível de '%s' (status=%s). "
            "Nenhum campo será preenchido.",
            file_path,
            status,
        )
        return {"status_extracao": status, "campos": {}}

    norm_text = _norm(text)

    campos: dict = {}
    for nome_campo, extractor in _FIELD_EXTRACTORS.items():
        result = extractor(text, norm_text)
        if result is not None:
            campos[nome_campo] = result
            logger.info(
                "  Parser MTE: campo '%s' extraído — valor=%s percentual=%s",
                nome_campo,
                result.get("valor"),
                result.get("percentual"),
            )

    final_status = "ok" if campos else "sem_texto"
    logger.info(
        "Parser MTE: '%s' → status=%s campos_encontrados=%d",
        file_path,
        final_status,
        len(campos),
    )
    return {"status_extracao": final_status, "campos": campos}

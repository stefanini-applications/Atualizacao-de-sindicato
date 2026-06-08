#!/usr/bin/env python3
"""
Extrai itens compostos das CCTs (piso salarial, adicional noturno,
auxílio alimentação, PLR, hora extra, sobreaviso, jornada) a partir
dos PDFs armazenados na pasta CCT/.

Os dados são gravados no campo `itens_cct` de cada registro em
data/base_parametros_sindicais.json.

Regras de governança:
- Itens já marcados como "valido" não são sobrescritos.
- Valores não encontrados recebem status "pendente_revisao".
- Valores identificados recebem status "extraido_para_revisao".
- Divergência entre múltiplos valores distintos gera status "conflito".
- Nenhum valor é inventado; apenas transcrição de trechos do PDF.

Uso:
    python3 extract_cct_items.py [--dry-run] [--ids ID1 ID2 ...]

Opções:
    --dry-run   Exibe o que seria alterado sem salvar.
    --ids       Processa apenas os registros com os IDs informados.
"""

import argparse
import json
import os
import re
import subprocess
import sys
import unicodedata
from datetime import datetime, timezone

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
JSON_PATH = os.path.join(REPO_ROOT, "data", "base_parametros_sindicais.json")
EXPORT_SCRIPT = os.path.join(REPO_ROOT, "export_inline_data.py")

# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────


def normalize(text: str) -> str:
    """Lowercase, remove accents — used only for searching."""
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    return text.lower()


def extract_pdf_text(pdf_path: str) -> tuple[str, str]:
    """
    Extract raw text from a PDF using pdftotext.

    Returns:
        (raw_text, status)  where status is one of:
            "ok" | "arquivo_ausente" | "pdf_sem_texto" | "erro_pdftotext"
    """
    if not pdf_path:
        return "", "arquivo_ausente"

    abs_path = os.path.join(REPO_ROOT, pdf_path)
    if not os.path.exists(abs_path):
        return "", "arquivo_ausente"

    try:
        result = subprocess.run(
            ["pdftotext", "-layout", abs_path, "-"],
            capture_output=True,
            timeout=30,
        )
        text = result.stdout.decode("utf-8", errors="replace")
        if len(text.strip()) < 50:
            return "", "pdf_sem_texto"
        return text, "ok"
    except subprocess.TimeoutExpired:
        return "", "erro_pdftotext"
    except FileNotFoundError:
        return "", "erro_pdftotext"


def parse_clauses(text: str) -> list[dict]:
    """
    Split PDF text into a list of clauses.

    Each clause dict has:
        "heading"   : str  — the raw heading line (e.g. "CLÁUSULA TERCEIRA - PISO SALARIAL")
        "heading_n" : str  — normalized heading for pattern matching
        "body"      : str  — clause body until the next clause heading
    """
    # Match clause headings: "CLÁUSULA <ordinal> - <title>" (Portuguese ordinals)
    heading_pattern = re.compile(
        r"(CL[AÁ]USULA\s+\w[\w\s]*?(?:–|-)\s*.+?)(?=\n)",
        re.IGNORECASE,
    )

    clauses = []
    last_end = 0
    last_heading = None
    last_heading_n = None

    for m in heading_pattern.finditer(text):
        if last_heading is not None:
            body = text[last_end:m.start()].strip()
            clauses.append(
                {
                    "heading": last_heading,
                    "heading_n": last_heading_n,
                    "body": body,
                }
            )
        last_heading = m.group(1).strip()
        last_heading_n = normalize(last_heading)
        last_end = m.end()

    # Append final clause
    if last_heading is not None:
        clauses.append(
            {
                "heading": last_heading,
                "heading_n": last_heading_n,
                "body": text[last_end:].strip(),
            }
        )

    return clauses


def find_clauses(clauses: list[dict], *patterns: str) -> list[dict]:
    """Return all clauses whose normalized heading matches any of the patterns."""
    compiled = [re.compile(p, re.IGNORECASE) for p in patterns]
    found = []
    for clause in clauses:
        if any(pat.search(clause["heading_n"]) for pat in compiled):
            found.append(clause)
    return found


def first_brl_values(text: str) -> list[float]:
    """Extract all distinct BRL currency values from text. e.g. 'R$ 1.540,47'"""
    # Match R$ 1.540,47 or R$1540,47 or R$ 1.540 or 1.540,47
    # We look specifically for R$ prefix to avoid false positives
    raw_values = re.findall(r"R\$\s*([\d.,]+)", text)
    results = []
    seen = set()
    for raw in raw_values:
        # Normalize Brazilian number format: 1.540,47 → 1540.47
        clean = raw.replace(".", "").replace(",", ".")
        try:
            val = float(clean)
            # Filter out very small values likely to be article/law references
            # (R$ 5,00 is the practical minimum for any real benefit)
            if val >= 5:
                key = round(val, 2)
                if key not in seen:
                    seen.add(key)
                    results.append(val)
        except ValueError:
            pass
    return results


def first_percentuals(text: str, min_val: float = 1.0, max_val: float = 300.0) -> list[float]:
    """Extract distinct percentage values from text."""
    raw_values = re.findall(r"(\d+(?:[,.]?\d+)?)\s*%", text)
    results = []
    seen = set()
    for raw in raw_values:
        clean = raw.replace(",", ".")
        try:
            val = float(clean)
            if min_val <= val <= max_val:
                key = round(val, 2)
                if key not in seen:
                    seen.add(key)
                    results.append(val)
        except ValueError:
            pass
    return results


def hours_semanais(text: str) -> list[float]:
    """Extract distinct 'X horas semanais' values from text."""
    text_n = normalize(text)
    raw_values = re.findall(r"(\d+)\s*(?:\([^)]+\)\s*)?horas?\s+semanais", text_n)
    results = []
    seen = set()
    for raw in raw_values:
        val = float(raw)
        if val not in seen:
            seen.add(val)
            results.append(val)
    return results


def sobreaviso_values(text: str) -> list[str]:
    """Extract sobreaviso indicators: fractions and percentuals."""
    results = []
    text_n = normalize(text)
    if re.search(r"1\s*/\s*3|um\s+terce?[oi]", text_n):
        results.append("1/3")
    pcts = first_percentuals(text, min_val=1, max_val=60)
    results += [f"{p}%" for p in pcts]
    return list(dict.fromkeys(results))  # deduplicate preserving order


def build_item(
    values: list,
    regra_textual: str,
    tipo: str,
    unidade: str,
    fonte_documento: str,
    clausula_heading: str,
    trecho_fonte: str,
    observacao: str | None = None,
    param_type: str | None = None,
) -> dict:
    """
    Assemble a single itens_cct item dict, choosing the appropriate
    status based on the number of values found.

    When param_type is supplied and multiple distinct values are present,
    classify_by_dimension is invoked to attempt structured classification
    into por_cargo / por_jornada / por_modalidade / por_escala.  If at
    least one dimension is resolved, status_parametro becomes
    "extraido_para_revisao" instead of "conflito".
    """
    if not values:
        obs = observacao or "Cláusula localizada, mas valor/percentual não pôde ser identificado automaticamente"
        return _item_not_found(fonte_documento, trecho_fonte, obs)

    distinct_vals = list(dict.fromkeys(str(v) for v in values))

    # Determine numeric fields
    valor = None
    percentual = None
    valor_textual = None

    if unidade.startswith("BRL") and isinstance(values[0], float):
        valor = values[0]
    elif unidade == "%" and isinstance(values[0], float):
        percentual = values[0]
    else:
        valor_textual = distinct_vals[0] if distinct_vals else None

    # Multiple values: attempt dimension classification when param_type is given
    classification: dict = {}
    if len(distinct_vals) > 1 and param_type and regra_textual:
        float_values = [v for v in values if isinstance(v, float)]
        if float_values:
            classification = classify_by_dimension(regra_textual, float_values, param_type)

    if len(distinct_vals) > 1:
        if classification:
            # Successfully classified — upgrade status and set valor to minimum
            status = "extraido_para_revisao"
            obs = observacao
            # Top-level valor holds the minimum classified value for BRL items
            if unidade.startswith("BRL"):
                all_classified_vals = [
                    entry["valor"]
                    for entries in classification.values()
                    for entry in entries
                    if isinstance(entry.get("valor"), float)
                ]
                if all_classified_vals:
                    valor = min(all_classified_vals)
        else:
            status = "conflito"
            obs = f"Múltiplos valores identificados: {', '.join(distinct_vals)}"
            if observacao:
                obs = f"{observacao}; {obs}"
    else:
        status = "extraido_para_revisao"
        obs = observacao

    item = {
        "valor": valor,
        "percentual": percentual,
        "valor_textual": valor_textual,
        "regra_textual": _truncate(regra_textual, 800),
        "tipo": tipo,
        "unidade": unidade,
        "fonte_documento": fonte_documento,
        "clausula": _truncate(clausula_heading, 200),
        "trecho_fonte": _truncate(trecho_fonte, 600),
        "observacao": obs,
        "status_parametro": status,
    }

    # Embed classification sub-structures directly into the item
    item.update(classification)

    return item


def _item_not_found(
    fonte_documento: str,
    trecho_fonte: str | None = None,
    observacao: str | None = None,
) -> dict:
    return {
        "valor": None,
        "percentual": None,
        "valor_textual": None,
        "regra_textual": None,
        "tipo": None,
        "unidade": None,
        "fonte_documento": fonte_documento,
        "clausula": None,
        "trecho_fonte": trecho_fonte,
        "observacao": observacao,
        "status_parametro": "pendente_revisao",
    }


def _truncate(text: str | None, max_len: int) -> str | None:
    if not text:
        return text
    text = " ".join(text.split())  # normalize whitespace
    if len(text) > max_len:
        return text[:max_len] + "…"
    return text


# ──────────────────────────────────────────────────────────────────────────────
# Dimension classification — generic, parameter-agnostic
# ──────────────────────────────────────────────────────────────────────────────

# Pattern registries: param_type → list of (label, regex_string).
# Use "_default" as a fallback for unknown/unlisted param types.
# Patterns are normalized (no accents, lowercase) before matching.

_CARGO_PATTERNS: dict[str, list[tuple[str, str]]] = {
    "_default": [
        ("Administrativo", r"piso\s+administrativo|auxiliar\s+administrativo|analista\s+administrativo"),
        ("Técnico", r"piso\s+tecnico|tecnico\s+de\s+suporte"),
        ("Operador", r"\boperador(?:\s+de)?\b"),
        ("Atendente", r"\batendente\b"),
        ("Recepcionista", r"\brecepcionista\b"),
        ("Analista", r"\banalista\b"),
        ("Supervisor", r"\bsupervisor\b"),
    ],
    "plr": [
        ("Técnico", r"(?:cargo|funcao|nivel)\s+tecnico"),
        ("Operacional", r"(?:cargo|funcao|nivel)\s+operacional"),
        ("Administrativo", r"(?:cargo|funcao|nivel)\s+administrativo"),
    ],
}

_JORNADA_PATTERNS: dict[str, list[tuple[str, str]]] = {
    "_default": [
        ("44h semanais", r"44\s*horas?\s*semanais?|jornada\s+de\s+44"),
        ("40h semanais", r"40\s*horas?\s*semanais?|jornada\s+de\s+40"),
        ("36h semanais", r"36\s*horas?\s*semanais?|jornada\s+de\s+36"),
        ("30h semanais", r"30\s*horas?\s*semanais?|jornada\s+de\s+30"),
        ("Mensalista", r"\bmensalista\b"),
        ("Horista", r"\bhorista\b"),
    ],
    "auxilio_alimentacao": [
        ("6 horas", r"6\s*(?:h\b|horas?)(?:\s*diarias?|\s*por\s+dia)?"),
        ("8 horas", r"8\s*(?:h\b|horas?)(?:\s*diarias?|\s*por\s+dia)?"),
        ("Integral", r"jornada\s+integral|turno\s+integral|regime\s+integral"),
        ("Parcial", r"jornada\s+parcial|turno\s+parcial|regime\s+parcial"),
    ],
    "adicional_noturno": [
        ("Horário Noturno", r"horario\s+noturno|periodo\s+noturno|turno\s+noturno"),
        ("Escala 12x36", r"12\s*[xX]\s*36"),
    ],
    "jornada": [
        ("36h semanais", r"36\s*horas?\s*semanais?"),
        ("40h semanais", r"40\s*horas?\s*semanais?"),
        ("44h semanais", r"44\s*horas?\s*semanais?"),
    ],
}

_MODALIDADE_PATTERNS: dict[str, list[tuple[str, str]]] = {
    "_default": [
        ("Presencial", r"\bpresencial\b"),
        ("Remoto", r"\bremoto\b|teletrabalho|home\s*office"),
        ("Híbrido", r"\bhibrido\b"),
    ],
    "hora_extra": [
        ("Dia Útil", r"dia\s+util|dias?\s+uteis?"),
        ("Sábado", r"\bsabados?\b"),
        ("Domingo", r"\bdomingos?\b"),
        ("Feriado", r"\bferiados?\b"),
    ],
    "sobreaviso": [
        ("Acionado", r"sobreaviso\s+acionado|quando\s+acionado"),
        ("Disponível", r"sobreaviso\s+disponivel|apenas\s+disponivel|sem\s+acionamento"),
    ],
}

_ESCALA_PATTERNS: dict[str, list[tuple[str, str]]] = {
    "_default": [
        ("12x36", r"12\s*[xX]\s*36"),
        ("6x1", r"6\s*[xX]\s*1"),
        ("5x1", r"5\s*[xX]\s*1"),
        ("5x2", r"5\s*[xX]\s*2"),
    ],
    "adicional_noturno": [
        ("12x36", r"12\s*[xX]\s*36"),
        ("6x1", r"6\s*[xX]\s*1"),
    ],
    "jornada": [
        ("12x36", r"12\s*[xX]\s*36"),
        ("6x1", r"6\s*[xX]\s*1"),
        ("5x1", r"5\s*[xX]\s*1"),
        ("5x2", r"5\s*[xX]\s*2"),
    ],
}

# Dimension config: (registry, result_key, object_field_name)
_DIMENSION_CONFIG = [
    (_CARGO_PATTERNS,     "por_cargo",      "cargo"),
    (_JORNADA_PATTERNS,   "por_jornada",    "jornada"),
    (_MODALIDADE_PATTERNS, "por_modalidade", "label"),
    (_ESCALA_PATTERNS,    "por_escala",     "label"),
]


def _segment_text(text: str) -> list[tuple[str, str]]:
    """
    Split text into (original, normalized) pairs at sentence/line boundaries.
    Produces segments suitable for proximity-based pattern matching.
    """
    parts = re.split(r"[\n;]+", text)
    return [(p.strip(), normalize(p.strip())) for p in parts if p.strip()]


def _find_labeled_values(
    text: str,
    patterns: list[tuple[str, re.Pattern, str]],
    target_values: list[float],
) -> list[dict]:
    """
    For each (label, compiled_pattern, field_key), find the nearest target BRL
    value in the clause text. Returns a list of classified items. A value is
    only assigned to the first matching label (used_values guard).
    """
    segments = _segment_text(text)
    target_set = {round(v, 2) for v in target_values}
    used_values: set[float] = set()
    results = []

    for label, pattern, field_key in patterns:
        found_val = None
        found_excerpt = None

        # Pass 1 — same segment contains both pattern and a target value
        for orig, norm in segments:
            if pattern.search(norm):
                for val in first_brl_values(orig):
                    rounded = round(val, 2)
                    if rounded in target_set and rounded not in used_values:
                        found_val = val
                        found_excerpt = orig
                        break
            if found_val is not None:
                break

        # Pass 2 — pattern found; look ±2 segments for the value
        if found_val is None:
            for i, (orig, norm) in enumerate(segments):
                if pattern.search(norm):
                    ctx_start = max(0, i - 2)
                    ctx_end = min(len(segments), i + 3)
                    ctx_orig = " ".join(s[0] for s in segments[ctx_start:ctx_end])
                    for val in first_brl_values(ctx_orig):
                        rounded = round(val, 2)
                        if rounded in target_set and rounded not in used_values:
                            found_val = val
                            found_excerpt = ctx_orig
                            break
                if found_val is not None:
                    break

        if found_val is not None:
            used_values.add(round(found_val, 2))
            results.append(
                {
                    field_key: label,
                    "valor": found_val,
                    "trecho_fonte": _truncate(found_excerpt, 300),
                }
            )

    return results


def classify_by_dimension(text: str, values: list[float], param_type: str) -> dict:
    """
    Classify multiple CCT values by dimension (cargo, jornada, modalidade, escala).

    Operates independently of any specific parameter, receiving only:
      - text:       clause text from the PDF
      - values:     BRL/numeric values already identified in the clause
      - param_type: identifier selecting the applicable pattern set
                    (e.g. "piso_salarial", "hora_extra", "auxilio_alimentacao")

    Returns a dict with zero or more of:
      por_cargo     : list of {cargo, valor, trecho_fonte}
      por_jornada   : list of {jornada, valor, trecho_fonte}
      por_modalidade: list of {label, valor, trecho_fonte}
      por_escala    : list of {label, valor, trecho_fonte}

    Only dimensions where at least 2 distinct values are classified are included.
    When no dimension matches, an empty dict is returned (caller preserves "conflito").
    """
    if not values or len(values) < 2:
        return {}

    result = {}

    for registry, result_key, field_key in _DIMENSION_CONFIG:
        pattern_list = registry.get(param_type) or registry.get("_default", [])
        compiled = [
            (label, re.compile(regex, re.IGNORECASE), field_key)
            for label, regex in pattern_list
        ]
        classified = _find_labeled_values(text, compiled, values)
        if len(classified) >= 2:
            result[result_key] = classified

    return result


def has_negative_clause(text: str) -> bool:
    """
    Returns True only if the clause text *wholly* negates or defers the benefit
    (e.g. "não haverá PLR", "fica mantida a cláusula anterior").
    Partial exceptions like "esta cláusula não se aplica a aprendizes" are NOT negative.
    """
    neg_patterns = [
        r"nao\s+haver[aa]\s+(?:plr|piso|adicional|auxilio|sobreaviso|jornada)",
        r"fica\s+mantida\s+a\s+clausula\s+anterior",
        r"inexist[ea]ncia\s+de",
        r"nao\s+se\s+aplica\s+a\s+presente",
    ]
    text_n = normalize(text)
    return any(re.search(p, text_n) for p in neg_patterns)


# ──────────────────────────────────────────────────────────────────────────────
# Per-item extractors
# ──────────────────────────────────────────────────────────────────────────────


def extract_piso_salarial(clauses: list[dict], fonte: str) -> dict:
    """Extract piso salarial (salary floor)."""
    matched = find_clauses(
        clauses,
        r"piso\s+salarial",
        r"salario\s+normativo",
        r"salarios\s+normativos",
        r"pisos?\s+salariais",
    )
    if not matched:
        return _item_not_found(fonte, observacao="Cláusula de piso salarial não localizada no PDF")

    clause = matched[0]
    full_text = clause["heading"] + "\n" + clause["body"]

    if has_negative_clause(full_text):
        return _item_not_found(
            fonte,
            trecho_fonte=_truncate(full_text, 600),
            observacao="Cláusula encontrada, mas indica negação ou remissão",
        )

    values = first_brl_values(full_text)

    # Detect piso type hints
    text_n = normalize(full_text)
    if re.search(r"piso\s+tecnico", text_n):
        tipo = "piso_tecnico"
    elif re.search(r"piso\s+administrativo", text_n):
        tipo = "piso_administrativo"
    elif len(values) == 1:
        tipo = "piso_unico"
    else:
        tipo = "piso_cct"

    return build_item(
        values=values,
        regra_textual=full_text,
        tipo=tipo,
        unidade="BRL",
        fonte_documento=fonte,
        clausula_heading=clause["heading"],
        trecho_fonte=full_text,
        param_type="piso_salarial",
    )


def extract_adicional_noturno(clauses: list[dict], fonte: str) -> dict:
    """Extract night shift additional (%)."""
    matched = find_clauses(
        clauses,
        r"adicional\s+noturno",
        r"horas?\s+noturnas?",
        r"trabalho\s+noturno",
    )
    if not matched:
        return _item_not_found(fonte, observacao="Cláusula de adicional noturno não localizada no PDF")

    clause = matched[0]
    full_text = clause["heading"] + "\n" + clause["body"]

    if has_negative_clause(full_text):
        return _item_not_found(
            fonte,
            trecho_fonte=_truncate(full_text, 600),
            observacao="Cláusula encontrada, mas indica negação",
        )

    # Extract percentuals specifically tied to additional noturno
    # Filter for relevant range (20% to 50% is normal for night shift)
    values = first_percentuals(full_text, min_val=10, max_val=100)

    # Try to find the primary adicional noturno % more precisely
    text_n = normalize(full_text)
    precise = re.findall(
        r"adicional\s+(?:de\s+)?(\d+(?:[,.]?\d+)?)\s*%|(\d+(?:[,.]?\d+)?)\s*%\s*.*?adicional\s+noturno",
        text_n,
    )
    if precise:
        flat = [g for pair in precise for g in pair if g]
        try:
            primary = float(flat[0].replace(",", "."))
            values = [primary] + [v for v in values if v != primary]
        except (ValueError, IndexError):
            pass

    return build_item(
        values=values,
        regra_textual=full_text,
        tipo="adicional_noturno",
        unidade="%",
        fonte_documento=fonte,
        clausula_heading=clause["heading"],
        trecho_fonte=full_text,
    )


def extract_auxilio_alimentacao(clauses: list[dict], fonte: str) -> dict:
    """Extract meal/food allowance (BRL)."""
    matched = find_clauses(
        clauses,
        r"auxilio\s+alimenta[cç]ao",
        r"auxilio\s+refei[cç]ao",
        r"vale.refei[cç]ao",
        r"vale.alimenta[cç]ao",
        r"alimenta[cç]ao\s+.*auxilio",
        r"refei[cç]ao\s+.*auxilio",
    )
    if not matched:
        return _item_not_found(fonte, observacao="Cláusula de auxílio alimentação não localizada no PDF")

    clause = matched[0]
    full_text = clause["heading"] + "\n" + clause["body"]

    if has_negative_clause(full_text):
        return _item_not_found(
            fonte,
            trecho_fonte=_truncate(full_text, 600),
            observacao="Cláusula encontrada, mas indica negação",
        )

    values = first_brl_values(full_text)

    # Detect per-day vs monthly
    text_n = normalize(full_text)
    if re.search(r"por\s+dia|diario|dia\s+util", text_n):
        unidade = "BRL/dia"
        tipo = "vale_refeicao"
    else:
        unidade = "BRL/mes"
        tipo = "auxilio_alimentacao"

    return build_item(
        values=values,
        regra_textual=full_text,
        tipo=tipo,
        unidade=unidade,
        fonte_documento=fonte,
        clausula_heading=clause["heading"],
        trecho_fonte=full_text,
    )


def extract_plr(clauses: list[dict], fonte: str) -> dict:
    """Extract PLR / profit sharing clause."""
    matched = find_clauses(
        clauses,
        r"participa[cç]ao\s+nos\s+lucros",
        r"\bplr\b",
        r"lucros\s+(?:e\s+)?resultados",
    )
    if not matched:
        return _item_not_found(fonte, observacao="Cláusula de PLR não localizada no PDF")

    clause = matched[0]
    full_text = clause["heading"] + "\n" + clause["body"]

    if has_negative_clause(full_text):
        return _item_not_found(
            fonte,
            trecho_fonte=_truncate(full_text, 600),
            observacao="Cláusula de PLR encontrada, mas indica negação ou ausência",
        )

    # PLR often has no fixed numeric value; the clause is mostly textual rules
    brl_values = first_brl_values(full_text)
    pct_values = first_percentuals(full_text, min_val=1, max_val=200)

    if brl_values:
        values = brl_values
        unidade = "BRL"
    elif pct_values:
        values = pct_values
        unidade = "%"
    else:
        # Clause found, but purely textual rules — still mark as extraido_para_revisao
        return {
            "valor": None,
            "percentual": None,
            "valor_textual": None,
            "regra_textual": _truncate(full_text, 800),
            "tipo": "plr",
            "unidade": None,
            "fonte_documento": fonte,
            "clausula": _truncate(clause["heading"], 200),
            "trecho_fonte": _truncate(full_text, 600),
            "observacao": "Cláusula de PLR encontrada; valor/regra específica requer revisão",
            "status_parametro": "extraido_para_revisao",
        }

    return build_item(
        values=values,
        regra_textual=full_text,
        tipo="plr",
        unidade=unidade,
        fonte_documento=fonte,
        clausula_heading=clause["heading"],
        trecho_fonte=full_text,
    )


def extract_hora_extra(clauses: list[dict], fonte: str) -> dict:
    """Extract overtime rates (%)."""
    matched = find_clauses(
        clauses,
        r"hora\s+extraordinaria",
        r"hora\s+extra",
        r"horas?\s+extras?",
        r"adicional\s+de\s+hora",
    )
    if not matched:
        return _item_not_found(fonte, observacao="Cláusula de hora extra não localizada no PDF")

    clause = matched[0]
    full_text = clause["heading"] + "\n" + clause["body"]

    if has_negative_clause(full_text):
        return _item_not_found(
            fonte,
            trecho_fonte=_truncate(full_text, 600),
            observacao="Cláusula encontrada, mas indica negação",
        )

    # Overtime percentuals: typically 50%, 60%, 75%, 100%, 120%
    values = first_percentuals(full_text, min_val=30, max_val=200)

    # Try to capture primary "dias úteis" rate as first value
    text_n = normalize(full_text)
    primary_match = re.search(
        r"(\d+)\s*%.*?dias?\s+uteis?|dias?\s+uteis?.*?(\d+)\s*%",
        text_n,
    )
    if primary_match:
        g = primary_match.group(1) or primary_match.group(2)
        if g:
            try:
                primary = float(g)
                values = [primary] + [v for v in values if v != primary]
            except ValueError:
                pass

    obs = None
    if len(values) > 1:
        obs = "Percentuais diferentes para dias úteis, sábados, domingos e feriados"

    return build_item(
        values=values,
        regra_textual=full_text,
        tipo="hora_extra",
        unidade="%",
        fonte_documento=fonte,
        clausula_heading=clause["heading"],
        trecho_fonte=full_text,
        observacao=obs,
    )


def extract_sobreaviso(clauses: list[dict], fonte: str) -> dict:
    """Extract on-call (sobreaviso) rate."""
    matched = find_clauses(clauses, r"sobreaviso")
    if not matched:
        return _item_not_found(fonte, observacao="Cláusula de sobreaviso não localizada no PDF")

    clause = matched[0]
    full_text = clause["heading"] + "\n" + clause["body"]

    if has_negative_clause(full_text):
        return _item_not_found(
            fonte,
            trecho_fonte=_truncate(full_text, 600),
            observacao="Cláusula encontrada, mas indica negação",
        )

    sob_vals = sobreaviso_values(full_text)

    if not sob_vals:
        return {
            "valor": None,
            "percentual": None,
            "valor_textual": None,
            "regra_textual": _truncate(full_text, 800),
            "tipo": "sobreaviso",
            "unidade": None,
            "fonte_documento": fonte,
            "clausula": _truncate(clause["heading"], 200),
            "trecho_fonte": _truncate(full_text, 600),
            "observacao": "Cláusula de sobreaviso encontrada; valor/regra requer revisão",
            "status_parametro": "extraido_para_revisao",
        }

    # Determine primary value and unit
    first = sob_vals[0]
    if first == "1/3":
        percentual = None
        valor_textual = "1/3 da hora normal"
        unidade = "fração"
    else:
        try:
            percentual = float(first.replace("%", ""))
        except ValueError:
            percentual = None
        valor_textual = first
        unidade = "%"

    status = "conflito" if len(sob_vals) > 1 else "extraido_para_revisao"
    obs = f"Múltiplos valores: {', '.join(sob_vals)}" if len(sob_vals) > 1 else None

    return {
        "valor": None,
        "percentual": percentual,
        "valor_textual": valor_textual,
        "regra_textual": _truncate(full_text, 800),
        "tipo": "sobreaviso",
        "unidade": unidade,
        "fonte_documento": fonte,
        "clausula": _truncate(clause["heading"], 200),
        "trecho_fonte": _truncate(full_text, 600),
        "observacao": obs,
        "status_parametro": status,
    }


def extract_jornada(clauses: list[dict], fonte: str) -> dict:
    """Extract work schedule (hours/week)."""
    matched = find_clauses(
        clauses,
        r"jornada\s+de\s+trabalho",
        r"duracao\s+e\s+horario",
        r"duracao\s+da\s+jornada",
    )
    if not matched:
        return _item_not_found(fonte, observacao="Cláusula de jornada de trabalho não localizada no PDF")

    # Prefer the first clause with actual hour values in its body
    clause = matched[0]
    for c in matched:
        if re.search(r"\d+\s*(?:\([^)]+\)\s*)?horas?\s+semanais", normalize(c["body"])):
            clause = c
            break

    full_text = clause["heading"] + "\n" + clause["body"]

    if has_negative_clause(full_text):
        return _item_not_found(
            fonte,
            trecho_fonte=_truncate(full_text, 600),
            observacao="Cláusula encontrada, mas indica negação",
        )

    hours = hours_semanais(full_text)

    # Build jornada value representation
    if not hours:
        # Look for 12x36 or similar
        text_n = normalize(full_text)
        if re.search(r"12\s*[xX×]\s*36", text_n):
            return {
                "valor": None,
                "percentual": None,
                "valor_textual": "12x36",
                "regra_textual": _truncate(full_text, 800),
                "tipo": "jornada",
                "unidade": "regime",
                "fonte_documento": fonte,
                "clausula": _truncate(clause["heading"], 200),
                "trecho_fonte": _truncate(full_text, 600),
                "observacao": None,
                "status_parametro": "extraido_para_revisao",
            }
        return {
            "valor": None,
            "percentual": None,
            "valor_textual": None,
            "regra_textual": _truncate(full_text, 800),
            "tipo": "jornada",
            "unidade": None,
            "fonte_documento": fonte,
            "clausula": _truncate(clause["heading"], 200),
            "trecho_fonte": _truncate(full_text, 600),
            "observacao": "Cláusula de jornada encontrada; carga horária requer revisão",
            "status_parametro": "extraido_para_revisao",
        }

    primary = hours[0]
    status = "conflito" if len(set(hours)) > 1 else "extraido_para_revisao"
    obs = f"Múltiplas jornadas identificadas: {', '.join(str(h) for h in hours)}h/sem" if status == "conflito" else None

    return {
        "valor": primary,
        "percentual": None,
        "valor_textual": f"{primary:.0f}h/semana",
        "regra_textual": _truncate(full_text, 800),
        "tipo": "jornada",
        "unidade": "h/semana",
        "fonte_documento": fonte,
        "clausula": _truncate(clause["heading"], 200),
        "trecho_fonte": _truncate(full_text, 600),
        "observacao": obs,
        "status_parametro": status,
    }


# ──────────────────────────────────────────────────────────────────────────────
# Main extraction logic
# ──────────────────────────────────────────────────────────────────────────────

EXTRACTORS = {
    "piso_salarial": extract_piso_salarial,
    "adicional_noturno": extract_adicional_noturno,
    "auxilio_alimentacao": extract_auxilio_alimentacao,
    "plr": extract_plr,
    "hora_extra": extract_hora_extra,
    "sobreaviso": extract_sobreaviso,
    "jornada": extract_jornada,
}


def extract_itens_cct(record: dict) -> tuple[dict, str]:
    """
    Extract all CCT items for a record.

    Returns:
        (itens_cct dict, extraction_status string)
    """
    fonte = record.get("fonte_documento") or ""
    text, status = extract_pdf_text(fonte)

    if status != "ok":
        obs_prefix = f"Extração de PDF falhou: {status}"
        itens = {}
        for key in EXTRACTORS:
            existing = (record.get("itens_cct") or {}).get(key, {})
            if existing.get("status_parametro") == "valido":
                itens[key] = existing
            else:
                item = _item_not_found(
                    fonte,
                    observacao=f"{obs_prefix}. {existing.get('observacao') or ''}".strip(". ") or obs_prefix,
                )
                itens[key] = item
        return itens, status

    clauses = parse_clauses(text)
    itens = {}

    for key, extractor in EXTRACTORS.items():
        existing = (record.get("itens_cct") or {}).get(key, {})

        # Governance: never overwrite a validated item
        if existing.get("status_parametro") == "valido":
            itens[key] = existing
            continue

        extracted = extractor(clauses, fonte)
        itens[key] = extracted

    return itens, status


def merge_itens_cct(existing: dict | None, new_itens: dict) -> dict:
    """
    Merge newly extracted items into existing itens_cct.

    Items already marked 'valido' are never overwritten.
    """
    if not existing:
        return new_itens

    merged = dict(existing)
    for key, new_item in new_itens.items():
        current = merged.get(key, {})
        if current.get("status_parametro") == "valido":
            continue  # preserve validated items
        merged[key] = new_item

    return merged


# ──────────────────────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Mostra mudanças sem salvar")
    parser.add_argument(
        "--ids",
        nargs="+",
        metavar="ID",
        help="Processa apenas os IDs de registro informados",
    )
    args = parser.parse_args()

    with open(JSON_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    records = data.get("registros", [])
    id_filter = set(args.ids) if args.ids else None

    stats = {
        "processados": 0,
        "sem_pdf": 0,
        "pdf_sem_texto": 0,
        "extraidos": 0,
        "pendentes": 0,
        "conflitos": 0,
        "validos_preservados": 0,
    }

    for record in records:
        rid = record.get("id_registro_reajuste", "?")
        if id_filter and rid not in id_filter:
            continue

        stats["processados"] += 1
        print(f"\n── {rid} ({record.get('uf')} / {record.get('sindicato')})")

        new_itens, extraction_status = extract_itens_cct(record)

        if extraction_status == "arquivo_ausente":
            print(f"   ⚠  PDF ausente: {record.get('fonte_documento')}")
            stats["sem_pdf"] += 1
        elif extraction_status == "pdf_sem_texto":
            print(f"   ⚠  PDF sem texto extraível (possivelmente digitalizado): {record.get('fonte_documento')}")
            stats["pdf_sem_texto"] += 1
        else:
            print(f"   ✓  PDF processado: {record.get('fonte_documento')}")

        # Merge with existing
        merged = merge_itens_cct(record.get("itens_cct"), new_itens)

        # Summarize items
        for key, item in merged.items():
            s = item.get("status_parametro", "?")
            v = item.get("valor") or item.get("percentual") or item.get("valor_textual") or "—"
            marker = {"valido": "✓ valido", "extraido_para_revisao": "↗ extraído", "conflito": "⚡ conflito", "pendente_revisao": "· pendente"}.get(s, s)
            print(f"     {key:<25} {marker:<22} {v}")
            if s == "valido":
                stats["validos_preservados"] += 1
            elif s == "extraido_para_revisao":
                stats["extraidos"] += 1
            elif s == "conflito":
                stats["conflitos"] += 1
            else:
                stats["pendentes"] += 1

        if not args.dry_run:
            record["itens_cct"] = merged

    print("\n" + "=" * 60)
    print(f"Registros processados : {stats['processados']}")
    print(f"  PDFs ausentes       : {stats['sem_pdf']}")
    print(f"  PDFs sem texto      : {stats['pdf_sem_texto']}")
    print(f"Itens extraídos       : {stats['extraidos']}")
    print(f"Itens pendentes       : {stats['pendentes']}")
    print(f"Itens em conflito     : {stats['conflitos']}")
    print(f"Itens válidos preserv.: {stats['validos_preservados']}")

    if args.dry_run:
        print("\n[dry-run] Nenhuma alteração foi salva.")
        return

    data["data_geracao"] = datetime.now(timezone.utc).astimezone().isoformat()

    with open(JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"\nArquivo salvo: {JSON_PATH}")

    # Regenerate JS
    result = subprocess.run(
        [sys.executable, EXPORT_SCRIPT],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        print(result.stdout.strip())
    else:
        print(f"Aviso: falha ao regenerar JS: {result.stderr.strip()}", file=sys.stderr)


if __name__ == "__main__":
    main()

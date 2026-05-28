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
) -> dict:
    """
    Assemble a single itens_cct item dict, choosing the appropriate
    status based on the number of values found.
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

    if len(distinct_vals) > 1:
        status = "conflito"
        obs = f"Múltiplos valores identificados: {', '.join(distinct_vals)}"
        if observacao:
            obs = f"{observacao}; {obs}"
    else:
        status = "extraido_para_revisao"
        obs = observacao

    return {
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
# Piso salarial helpers — per-cargo/função extraction
# ──────────────────────────────────────────────────────────────────────────────

# Named piso patterns (normalized text): (pattern, named_field_key)
_NAMED_PISO_PAT: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\bpiso\s+tecnico\b"), "piso_tecnico"),
    (re.compile(r"\bpiso\s+administrativo\b"), "piso_administrativo"),
    (re.compile(r"\bpiso\s+unico\b"), "piso_unico"),
    (re.compile(r"\bpiso\s+(?:geral|base|cct|minimo)\b"), "valor_piso_cct"),
]

# Pattern for a colon/dash-separated label–value pair on a single line.
# Captures: group(1) = label (3–60 chars), group(2) = BRL raw value
_LINE_LABEL_VALUE_PAT = re.compile(
    r"^(.{3,60}?)\s*[:–—-]\s*R\$\s*([\d.,]+)",
    re.MULTILINE | re.IGNORECASE,
)

# Jornada hint pattern (normalised text)
_JORNADA_HINT_PAT = re.compile(
    r"(\d+)\s*(?:horas?\s+semanais|horas?\s+mensais|h(?:oras?)?\s*/\s*semana"
    r"|h(?:oras?)?\s*/\s*mes|h\s+semanais|h\s+mensais)",
)


def _jornada_hint(line_n: str) -> str | None:
    """Extract a human-readable jornada string from a normalised line."""
    m = _JORNADA_HINT_PAT.search(line_n)
    if not m:
        return None
    return m.group(0).strip()


def _extract_named_piso_fields(full_text: str) -> dict[str, float | None]:
    """
    Search each line of the clause for known named piso patterns adjacent to
    a BRL value (same line). Returns a dict with four keys.
    """
    named: dict[str, float | None] = {
        "valor_piso_cct": None,
        "piso_tecnico": None,
        "piso_administrativo": None,
        "piso_unico": None,
    }
    for line in full_text.split("\n"):
        line_n = normalize(line)
        brl = first_brl_values(line)
        if not brl:
            continue
        for pat, field in _NAMED_PISO_PAT:
            if pat.search(line_n) and named[field] is None:
                named[field] = brl[0]
    return named


def _extract_por_cargo_entries(
    full_text: str, fonte: str, clausula_heading: str
) -> list[dict]:
    """
    Extract per-cargo/função/jornada piso entries from clause text.

    Uses two strategies:
    1. Explicit label–value patterns: lines matching "<label>: R$ <value>" or
       "<label> — R$ <value>" (colon/dash separated, same line).
    2. Named-piso-keyword lines: "piso técnico" or "piso administrativo" etc.
       where the role keyword acts as the cargo_ou_funcao.

    Only high-confidence same-line matches are included.
    """
    entries: list[dict] = []
    seen: set[tuple[str, float]] = set()

    for line in full_text.split("\n"):
        line_stripped = line.strip()
        if not line_stripped:
            continue

        brl_vals = first_brl_values(line_stripped)
        if not brl_vals:
            continue

        line_n = normalize(line_stripped)
        val = brl_vals[0]
        val_key = round(val, 2)

        # Strategy 1: "label: R$ value" or "label – R$ value" patterns
        m = _LINE_LABEL_VALUE_PAT.match(line_stripped)
        if m:
            label_raw = m.group(1).strip(" \t:–—-")
            label_n = normalize(label_raw)
            # Skip very generic headings that aren't cargo names
            if label_n and not re.search(
                r"^(?:valor|salario|remuneracao|empregado|trabalhador"
                r"|empresa|nos\s+termos|conforme|apos|durante|exceto"
                r"|exclusive|nao\s+se\s+aplica)\b",
                label_n,
            ):
                key = (label_n, val_key)
                if key not in seen:
                    seen.add(key)
                    entries.append({
                        "cargo_ou_funcao": label_raw,
                        "valor": val,
                        "jornada": _jornada_hint(line_n),
                        "fonte_documento": fonte,
                        "clausula": _truncate(clausula_heading, 200),
                        "status_parametro": "extraido_para_revisao",
                    })
            continue

        # Strategy 2: named-piso-keyword lines
        for pat, _ in _NAMED_PISO_PAT:
            if pat.search(line_n):
                # Use the matched keyword as cargo name
                m2 = pat.search(line_n)
                if m2:
                    cargo_label = m2.group(0).replace("\t", " ").strip().title()
                    key = (normalize(cargo_label), val_key)
                    if key not in seen:
                        seen.add(key)
                        entries.append({
                            "cargo_ou_funcao": cargo_label,
                            "valor": val,
                            "jornada": _jornada_hint(line_n),
                            "fonte_documento": fonte,
                            "clausula": _truncate(clausula_heading, 200),
                            "status_parametro": "extraido_para_revisao",
                        })
                break

    return entries


# ──────────────────────────────────────────────────────────────────────────────
# Per-item extractors
# ──────────────────────────────────────────────────────────────────────────────


def extract_piso_salarial(clauses: list[dict], fonte: str) -> dict:
    """
    Extract piso salarial (salary floor) with per-cargo/função/modalidade breakdown.

    Returns a dict with:
    - Named piso fields: valor_piso_cct, piso_tecnico, piso_administrativo, piso_unico
    - por_cargo: list of per-cargo entries (display-only preview, not canonical)
    - Legacy fields (valor, tipo) for backward compatibility — only set when a
      single unambiguous piso exists
    """
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
        item = _item_not_found(
            fonte,
            trecho_fonte=_truncate(full_text, 600),
            observacao="Cláusula encontrada, mas indica negação ou remissão",
        )
        item.update({
            "valor_piso_cct": None,
            "piso_tecnico": None,
            "piso_administrativo": None,
            "piso_unico": None,
            "por_cargo": [],
        })
        return item

    all_values = first_brl_values(full_text)
    named = _extract_named_piso_fields(full_text)
    por_cargo = _extract_por_cargo_entries(full_text, fonte, clause["heading"])

    # ── Determine legacy tipo + valor (only when one unambiguous piso exists) ──
    named_nonull = {k: v for k, v in named.items() if v is not None}
    named_count = len(named_nonull)

    if named_count == 1:
        field_name = next(iter(named_nonull))
        valor_legacy = named_nonull[field_name]
        tipo = {
            "piso_tecnico": "piso_tecnico",
            "piso_administrativo": "piso_administrativo",
            "piso_unico": "piso_unico",
            "valor_piso_cct": "piso_cct",
        }.get(field_name, "piso_cct")
    elif named_count == 0 and len(all_values) == 1:
        # Single value with no named-field match → piso único
        named["piso_unico"] = all_values[0]
        valor_legacy = all_values[0]
        tipo = "piso_unico"
    else:
        # Multiple pisos or zero values — no single legacy value
        valor_legacy = None
        tipo = "piso_cct" if all_values else None

    # ── Status ────────────────────────────────────────────────────────────────
    if not all_values and not por_cargo:
        obs = "Cláusula localizada, mas valor/percentual não pôde ser identificado automaticamente"
        item = _item_not_found(fonte, _truncate(full_text, 600), obs)
        item.update({
            "valor_piso_cct": None,
            "piso_tecnico": None,
            "piso_administrativo": None,
            "piso_unico": None,
            "por_cargo": [],
        })
        return item

    if named_count > 1:
        status = "extraido_para_revisao"
        obs_parts = [
            f"{k.replace('_', ' ')}: R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            for k, v in named_nonull.items()
        ]
        obs = f"Múltiplos pisos identificados: {'; '.join(obs_parts)}"
    elif named_count == 0 and len(all_values) > 1:
        status = "conflito"
        obs = f"Múltiplos valores identificados: {', '.join(str(v) for v in all_values)}"
    else:
        status = "extraido_para_revisao"
        obs = None

    return {
        # Named piso fields (structured breakdown)
        "valor_piso_cct": named["valor_piso_cct"],
        "piso_tecnico": named["piso_tecnico"],
        "piso_administrativo": named["piso_administrativo"],
        "piso_unico": named["piso_unico"],
        # Per-cargo preview (display-only, non-canonical)
        "por_cargo": por_cargo,
        # Legacy/backward-compat fields
        "valor": valor_legacy,
        "percentual": None,
        "valor_textual": None,
        "regra_textual": _truncate(full_text, 800),
        "tipo": tipo,
        "unidade": "BRL",
        "fonte_documento": fonte,
        "clausula": _truncate(clause["heading"], 200),
        "trecho_fonte": _truncate(full_text, 600),
        "observacao": obs,
        "status_parametro": status,
    }


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
            # For piso_salarial, show a structured summary of named fields
            if key == "piso_salarial":
                named_parts = [
                    f"{k.replace('piso_', 'tec=' if k == 'piso_tecnico' else 'adm=' if k == 'piso_administrativo' else 'único=' if k == 'piso_unico' else 'cct=')}{v:,.2f}"
                    for k, v in {
                        "piso_tecnico": item.get("piso_tecnico"),
                        "piso_administrativo": item.get("piso_administrativo"),
                        "piso_unico": item.get("piso_unico"),
                        "valor_piso_cct": item.get("valor_piso_cct"),
                    }.items()
                    if v is not None
                ]
                n_cargo = len(item.get("por_cargo") or [])
                v = " | ".join(named_parts) if named_parts else (item.get("valor") or "—")
                if n_cargo:
                    v = f"{v} [{n_cargo} cargo(s)]" if named_parts else f"[{n_cargo} cargo(s)]"
            else:
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

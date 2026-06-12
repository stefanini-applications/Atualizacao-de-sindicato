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
from datetime import date, datetime, timezone

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
JSON_PATH = os.path.join(REPO_ROOT, "data", "base_parametros_sindicais.json")
EXPORT_SCRIPT = os.path.join(REPO_ROOT, "export_inline_data.py")

# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────


def today_str() -> str:
    """Return today's date in YYYY-MM-DD format (used for data_extracao)."""
    return date.today().isoformat()


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

    When ``param_type`` is supplied and multiple distinct values are found,
    ``classify_by_dimension`` is attempted.  A successful classification
    populates ``por_cargo`` / ``por_jornada`` / ``por_modalidade`` /
    ``por_escala`` sub-structures and sets ``status_parametro`` to
    ``"extraido_para_revisao"`` instead of ``"conflito"``.
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

    classification: dict = {}
    if len(distinct_vals) > 1 and param_type and trecho_fonte:
        float_values = [v for v in values if isinstance(v, float)]
        classification = classify_by_dimension(trecho_fonte, float_values, param_type)

    if len(distinct_vals) > 1:
        if classification:
            # Structured classification succeeded — use minimum BRL value at top level
            if unidade.startswith("BRL"):
                float_values = [v for v in values if isinstance(v, float)]
                if float_values:
                    valor = min(float_values)
            status = "extraido_para_revisao"
            obs = observacao
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
        # Traceability fields (PRJ-59)
        "origem": "pdf_cct",
        "fonte": "PDF da CCT",
        "fonte_textual": _truncate(trecho_fonte, 600),
        "pagina": None,
        "data_extracao": today_str(),
    }
    item.update(classification)
    return item


def _item_not_found(
    fonte_documento: str,
    trecho_fonte: str | None = None,
    observacao: str | None = None,
) -> dict:
    obs = observacao or "Informação não localizada no PDF processado. Elegível para fallback em fonte oficial."
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
        "observacao": obs,
        "status_parametro": "pendente_revisao",
        # Traceability fields (PRJ-59)
        "origem": "nao_identificado_pdf",
        "fonte": None,
        "fonte_textual": None,
        "pagina": None,
        "data_extracao": today_str(),
    }


def _truncate(text: str | None, max_len: int) -> str | None:
    if not text:
        return text
    text = " ".join(text.split())  # normalize whitespace
    if len(text) > max_len:
        return text[:max_len] + "…"
    return text


# ──────────────────────────────────────────────────────────────────────────────
# Dimension classification
# ──────────────────────────────────────────────────────────────────────────────

# Pattern dictionaries for each classification dimension.
# Each entry is (regex, label) where regex is matched against normalized text.
# Extend these dicts to support new parameters without touching classify_by_dimension.
DIMENSION_PATTERNS: dict[str, list[tuple[str, str]]] = {
    "cargo": [
        (r"piso\s+(?:salarial\s+)?(?:do\s+)?t[eé]cnicos?", "piso_tecnico"),
        (r"piso\s+(?:salarial\s+)?(?:do\s+)?administrativos?", "piso_administrativo"),
        (r"auxiliar\s+administrativo", "auxiliar_administrativo"),
        (r"t[eé]cnico\s+de\s+suporte", "tecnico_suporte"),
        (r"t[eé]cnico\s+em\s+inform[aá]tica", "tecnico_informatica"),
        (r"operador(?:es)?\s+de\s+(?:sistema|equipamento|m[aá]quina|terminal|rede|ti\b|inform[aá]tica|telemarketing|call\s*center|produ[cç][aã]o|servi[cç]os?)", "operador"),
        (r"atendente[s]?", "atendente"),
        (r"recepcionista[s]?", "recepcionista"),
        (r"analista[s]?", "analista"),
        (r"supervisor(?:es)?", "supervisor"),
        (r"cargo\s+t[eé]cnico", "cargo_tecnico"),
        (r"cargo\s+operacional", "cargo_operacional"),
        (r"cargo\s+administrativo", "cargo_administrativo"),
        (r"\bleiturista[s]?\b", "leiturista"),
        (r"\bmensageiro[s]?\b", "mensageiro"),
        (r"\bfaxineiro[s]?\b", "faxineiro"),
        (r"\bcopeiro[s]?\b", "copeiro"),
        (r"\bcontinuo[s]?\b", "continuo"),
        (r"\bdigitador(?:es)?\b", "digitador"),
        (r"\bprogramador(?:es)?\b", "programador"),
        (r"\bdesenvolvedor(?:es)?\b", "desenvolvedor"),
        (r"\bgerente[s]?\b", "gerente"),
        (r"\bcoordenador(?:es)?\b", "coordenador"),
        (r"\bdemais\s+fun[cç][oõ]es?\b", "demais_funcoes"),
        (r"\bfun[cç][aã]o\s+de\s+(?:nível\s+)?(?:i+|[0-9]+)\b", "cargo_nivel"),
        (r"\bescrit[uú]r[aá]rio[s]?\b", "escriturario"),
        (r"\bcaixa[s]?\b", "caixa"),
        (r"\bcontador(?:es)?\b", "contador"),
    ],
    "jornada": [
        (r"44\s*(?:\([^)]+\)\s*)?horas?\s+semanais?", "44h_semanal"),
        (r"40\s*(?:\([^)]+\)\s*)?horas?\s+semanais?", "40h_semanal"),
        (r"36\s*(?:\([^)]+\)\s*)?horas?\s+semanais?", "36h_semanal"),
        (r"30\s*(?:\([^)]+\)\s*)?horas?\s+semanais?", "30h_semanal"),
        (r"20\s*(?:\([^)]+\)\s*)?horas?\s+semanais?", "20h_semanal"),
        (r"\bhorista[s]?\b", "horista"),
        (r"\bmensalista[s]?\b", "mensalista"),
        (r"jornada\s+de\s+6\s*(?:horas?|h)\b", "6h_diario"),
        (r"jornada\s+de\s+8\s*(?:horas?|h)\b", "8h_diario"),
        (r"\b6\s*(?:horas?|h)\s+di[aá]rias?\b", "6h_diario"),
        (r"\b8\s*(?:horas?|h)\s+di[aá]rias?\b", "8h_diario"),
        (r"jornada\s+integral", "jornada_integral"),
        (r"jornada\s+parcial", "jornada_parcial"),
        (r"hor[aá]rio\s+noturno", "horario_noturno"),
    ],
    "modalidade": [
        (r"\bpresencial\b", "presencial"),
        (r"\bremoto\b|\bhome[\s-]*office\b", "remoto"),
        (r"\bh[ií]brido\b", "hibrido"),
        # hora_extra: order matters — longer/more-specific patterns first
        (r"segunda.{0,20}(?:sexta|sexta-feira).{0,20}s[aá]bado", "dia_util_e_sabado"),
        (r"segunda.{0,20}s[aá]bado(?!\s*\w{0,5}s[aá]bado)", "dia_util_e_sabado"),
        (r"dias?\s+[uú]teis?", "dia_util"),
        (r"segunda.{0,20}(?:sexta|sexta-feira)(?!.{0,20}s[aá]bado)", "dia_util"),
        (r"\bs[aá]bados?\b", "sabado"),
        (r"\bdomingos?\b", "domingo"),
        (r"\bferiados?\b", "feriado"),
        (r"\bdia\s+de\s+repouso\b", "domingo"),
        (r"\bacionado\b", "acionado"),
        (r"\bdispon[ií]vel\b", "disponivel"),
    ],
    "escala": [
        (r"12\s*[xX×]\s*36", "12x36"),
        (r"5\s*[xX×]\s*1\b", "5x1"),
        (r"6\s*[xX×]\s*1\b", "6x1"),
        (r"5\s*[xX×]\s*2\b", "5x2"),
        (r"4\s*[xX×]\s*3\b", "4x3"),
        (r"4\s*[xX×]\s*2\b", "4x2"),
    ],
}

# Maps each param_type to the dimensions that should be attempted for classification.
# Extend to enable classification for new parameters in future stories.
PARAM_DIMENSIONS: dict[str, list[str]] = {
    "piso_salarial": ["cargo", "jornada", "modalidade", "escala"],
    "auxilio_alimentacao": ["jornada"],
    "hora_extra": ["modalidade"],
    "adicional_noturno": ["jornada", "escala"],
    "sobreaviso": ["modalidade"],
    "plr": ["cargo"],
    "jornada": ["jornada", "escala"],
}

# Proximity window (characters): max distance between a dimension label and a BRL value
# for the association to be considered valid.
_PROXIMITY_WINDOW = 350


def _find_brl_with_positions(text_n: str) -> list[tuple[float, int, int]]:
    """
    Find all distinct BRL values in normalized text, returning (value, start, end).
    Keeps only the first occurrence of each rounded value.
    """
    seen: dict[float, tuple[float, int, int]] = {}
    for m in re.finditer(r"r\$\s*([\d.,]+)", text_n):
        raw = m.group(1)
        clean = raw.replace(".", "").replace(",", ".")
        try:
            val = float(clean)
            if val >= 5:
                key = round(val, 2)
                if key not in seen:
                    seen[key] = (val, m.start(), m.end())
        except ValueError:
            pass
    return list(seen.values())


def _find_pct_with_positions(text_n: str) -> list[tuple[float, int, int]]:
    """
    Find all distinct percentage values in normalized text, returning (value, start, end).
    Keeps only the first occurrence of each rounded value.
    """
    seen: dict[float, tuple[float, int, int]] = {}
    for m in re.finditer(r"(\d+(?:[,.]?\d+)?)\s*%", text_n):
        raw = m.group(1).replace(",", ".")
        try:
            val = float(raw)
            if 1 <= val <= 300:
                key = round(val, 2)
                if key not in seen:
                    seen[key] = (val, m.start(), m.end())
        except ValueError:
            pass
    return list(seen.values())


# Parameters whose values are percentages rather than BRL amounts.
_PCT_PARAMS: frozenset[str] = frozenset({"hora_extra", "adicional_noturno"})


def classify_by_dimension(text: str, values: list[float], param_type: str) -> dict:
    """
    Classify multiple values by dimension (cargo, jornada, modalidade, escala).

    Generic and decoupled from any specific parameter. The ``param_type``
    argument selects which dimensions (from ``PARAM_DIMENSIONS``) to attempt.

    Args:
        text:        Raw clause text (normalization is applied internally).
        values:      List of float values extracted from the clause.
        param_type:  Parameter identifier used to select applicable dimensions.

    Returns:
        A dict with any combination of:
            por_cargo      — list[{cargo, valor, trecho_fonte}]
            por_jornada    — list[{jornada, valor, trecho_fonte}]
            por_modalidade — list[{label, valor, trecho_fonte}]
            por_escala     — list[{label, valor, trecho_fonte}]
        Returns {} when no dimension classification is possible.
    """
    if not values or param_type not in PARAM_DIMENSIONS:
        return {}

    text_n = normalize(text)
    values_set = {round(v, 2) for v in values}
    brl_positions = (
        _find_pct_with_positions(text_n)
        if param_type in _PCT_PARAMS
        else _find_brl_with_positions(text_n)
    )

    result: dict = {}

    for dim_name in PARAM_DIMENSIONS[param_type]:
        patterns = DIMENSION_PATTERNS.get(dim_name, [])
        classified: list[dict] = []
        matched_val_keys: set[float] = set()

        for pattern, label in patterns:
            for pm in re.finditer(pattern, text_n, re.IGNORECASE):
                # Find the BRL value nearest to this pattern match within the window
                best_val: float | None = None
                best_dist = _PROXIMITY_WINDOW + 1
                best_vspan: tuple[int, int] | None = None

                for val, vstart, vend in brl_positions:
                    if round(val, 2) not in values_set:
                        continue
                    dist = min(abs(pm.start() - vend), abs(pm.end() - vstart))
                    if dist < best_dist:
                        best_dist = dist
                        best_val = val
                        best_vspan = (vstart, vend)

                if best_val is None:
                    continue

                val_key = round(best_val, 2)
                if val_key in matched_val_keys:
                    continue  # already claimed by an earlier pattern

                matched_val_keys.add(val_key)

                # Extract a readable source snippet centred around the match
                win_start = max(0, min(pm.start(), best_vspan[0]) - 80)
                win_end = min(len(text), max(pm.end(), best_vspan[1]) + 80)
                trecho = " ".join(text[win_start:win_end].split())

                if dim_name == "cargo":
                    entry: dict = {
                        "cargo": label,
                        "valor": round(best_val, 2),
                        "trecho_fonte": _truncate(trecho, 300),
                    }
                elif dim_name == "jornada":
                    entry = {
                        "jornada": label,
                        "valor": round(best_val, 2),
                        "trecho_fonte": _truncate(trecho, 300),
                    }
                else:  # modalidade or escala
                    entry = {
                        "label": label,
                        "valor": round(best_val, 2),
                        "trecho_fonte": _truncate(trecho, 300),
                    }
                classified.append(entry)

        if classified:
            result[f"por_{dim_name}"] = classified

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
        param_type="adicional_noturno",
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
        param_type="auxilio_alimentacao",
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
            # Traceability fields (PRJ-59)
            "origem": "pdf_cct",
            "fonte": "PDF da CCT",
            "fonte_textual": _truncate(full_text, 600),
            "pagina": None,
            "data_extracao": today_str(),
        }

    return build_item(
        values=values,
        regra_textual=full_text,
        tipo="plr",
        unidade=unidade,
        fonte_documento=fonte,
        clausula_heading=clause["heading"],
        trecho_fonte=full_text,
        param_type="plr",
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
        param_type="hora_extra",
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
            # Traceability fields (PRJ-59)
            "origem": "pdf_cct",
            "fonte": "PDF da CCT",
            "fonte_textual": _truncate(full_text, 600),
            "pagina": None,
            "data_extracao": today_str(),
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
        # Traceability fields (PRJ-59)
        "origem": "pdf_cct",
        "fonte": "PDF da CCT",
        "fonte_textual": _truncate(full_text, 600),
        "pagina": None,
        "data_extracao": today_str(),
    }


def _classify_jornada_multiple(full_text: str) -> dict:
    """
    Build structured por_jornada / por_escala sub-dicts when multiple schedule
    types are found in the clause.  Replaces "conflito" for jornada items.
    """
    text_n = normalize(full_text)
    result: dict = {}

    # --- por_jornada: named weekly-hours patterns ---
    jornada_entries = []
    matched_labels: set[str] = set()
    for pattern, label in DIMENSION_PATTERNS["jornada"]:
        for m in re.finditer(pattern, text_n):
            if label in matched_labels:
                continue
            matched_labels.add(label)
            win_start = max(0, m.start() - 80)
            win_end = min(len(full_text), m.end() + 120)
            trecho = " ".join(full_text[win_start:win_end].split())
            hour_match = re.match(r"(\d+)h_", label)
            valor = float(hour_match.group(1)) if hour_match else None
            jornada_entries.append(
                {
                    "jornada": label,
                    "valor": valor,
                    "trecho_fonte": _truncate(trecho, 300),
                }
            )
    if jornada_entries:
        result["por_jornada"] = jornada_entries

    # --- por_escala: NxM regime patterns ---
    escala_entries = []
    matched_escala: set[str] = set()
    for pattern, label in DIMENSION_PATTERNS["escala"]:
        for m in re.finditer(pattern, text_n):
            if label in matched_escala:
                continue
            matched_escala.add(label)
            win_start = max(0, m.start() - 80)
            win_end = min(len(full_text), m.end() + 120)
            trecho = " ".join(full_text[win_start:win_end].split())
            escala_entries.append(
                {
                    "label": label,
                    "valor_textual": label.replace("x", "×"),
                    "trecho_fonte": _truncate(trecho, 300),
                }
            )
    if escala_entries:
        result["por_escala"] = escala_entries

    return result


def _calc_horas_diarias(horas_semanais: float, por_escala: list[dict]) -> tuple:
    """
    Calculate horas_diarias based on weekly hours and detected scale regime.

    Returns (horas_diarias_value, observacao_note) where horas_diarias_value is float|None.
    """
    if not por_escala:
        return None, "Horas diárias não calculadas: regime não identificável"

    labels = {e.get("label", "") for e in por_escala}

    if "12x36" in labels:
        return None, "Horas diárias não calculadas: regime 12×36 não permite cálculo direto"
    if "5x2" in labels:
        return round(horas_semanais / 5, 1), None
    if "6x1" in labels:
        return round(horas_semanais / 6, 1), None
    if "5x1" in labels:
        return round(horas_semanais / 5, 1), None

    return None, "Horas diárias não calculadas: regime não identificável"


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
    text_n = normalize(full_text)

    # Build jornada value representation
    if not hours:
        # Look for NxM scale patterns before giving up
        structured = _classify_jornada_multiple(full_text)
        if structured.get("por_escala"):
            first_escala = structured["por_escala"][0]
            item = {
                "valor": None,
                "percentual": None,
                "horas_semanais": None,
                "horas_mensais": None,
                "horas_diarias": None,
                "opcoes_identificadas": [],
                "valor_textual": first_escala.get("valor_textual") or first_escala.get("label"),
                "regra_textual": _truncate(full_text, 800),
                "tipo": "jornada",
                "unidade": "regime",
                "fonte_documento": fonte,
                "clausula": _truncate(clause["heading"], 200),
                "trecho_fonte": _truncate(full_text, 600),
                "observacao": None,
                "status_parametro": "extraido_para_revisao",
                # Traceability fields (PRJ-59)
                "origem": "pdf_cct",
                "fonte": "PDF da CCT",
                "fonte_textual": _truncate(full_text, 600),
                "pagina": None,
                "data_extracao": today_str(),
            }
            item.update(structured)
            return item
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
            # Traceability fields (PRJ-59)
            "origem": "pdf_cct",
            "fonte": "PDF da CCT",
            "fonte_textual": _truncate(full_text, 600),
            "pagina": None,
            "data_extracao": today_str(),
        }

    primary = hours[0]
    unique_hours = list(dict.fromkeys(hours))

    if len(unique_hours) > 1:
        # Multiple schedules — produce structured sub-items instead of "conflito"
        structured = _classify_jornada_multiple(full_text)
        horas_mensais = round(primary * 4.3333)
        horas_diarias_val, hd_obs = _calc_horas_diarias(primary, structured.get("por_escala", []))
        obs_parts = [f"Múltiplas jornadas identificadas: {', '.join(str(h) for h in unique_hours)}h/sem"]
        if hd_obs:
            obs_parts.append(hd_obs)
        item = {
            "valor": primary,
            "percentual": None,
            "horas_semanais": int(primary),
            "horas_mensais": horas_mensais,
            "horas_diarias": horas_diarias_val,
            "opcoes_identificadas": [f"{h:.0f}h/semana" for h in unique_hours],
            "valor_textual": f"{primary:.0f}h/sem · {horas_mensais}h/mês",
            "regra_textual": _truncate(full_text, 800),
            "tipo": "jornada",
            "unidade": "h/semana",
            "fonte_documento": fonte,
            "clausula": _truncate(clause["heading"], 200),
            "trecho_fonte": _truncate(full_text, 600),
            "observacao": "; ".join(obs_parts),
            "status_parametro": "extraido_para_revisao",
            # Traceability fields (PRJ-59)
            "origem": "pdf_cct",
            "fonte": "PDF da CCT",
            "fonte_textual": _truncate(full_text, 600),
            "pagina": None,
            "data_extracao": today_str(),
        }
        if structured:
            item.update(structured)
        return item

    structured = _classify_jornada_multiple(full_text)
    horas_mensais = round(primary * 4.3333)
    horas_diarias_val, hd_obs = _calc_horas_diarias(primary, structured.get("por_escala", []))
    item = {
        "valor": primary,
        "percentual": None,
        "horas_semanais": int(primary),
        "horas_mensais": horas_mensais,
        "horas_diarias": horas_diarias_val,
        "opcoes_identificadas": [f"{primary:.0f}h/semana"],
        "valor_textual": f"{primary:.0f}h/sem · {horas_mensais}h/mês",
        "regra_textual": _truncate(full_text, 800),
        "tipo": "jornada",
        "unidade": "h/semana",
        "fonte_documento": fonte,
        "clausula": _truncate(clause["heading"], 200),
        "trecho_fonte": _truncate(full_text, 600),
        "observacao": hd_obs,
        "status_parametro": "extraido_para_revisao",
        # Traceability fields (PRJ-59)
        "origem": "pdf_cct",
        "fonte": "PDF da CCT",
        "fonte_textual": _truncate(full_text, 600),
        "pagina": None,
        "data_extracao": today_str(),
    }
    if structured:
        item.update(structured)
    return item


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


def apply_piso_nacional_fallback(record: dict, piso_nacional_value: float | None) -> None:
    """
    Apply national wage floor as fallback for records whose piso_nacional is
    absent or has no usable value.

    Governance (AC2): the fallback is ONLY applied when piso_nacional is absent,
    None, or has status_parametro of None or "pendente_revisao".  Records that
    already carry a filled piso_nacional with any other status (e.g. "valido",
    "extraido_para_revisao") are left completely untouched, so a previously
    validated or extracted national floor is never silently overwritten.
    """
    if piso_nacional_value is None:
        return

    current = record.get("piso_nacional")

    if isinstance(current, dict):
        current_status = current.get("status_parametro")
        current_valor = current.get("valor")
        # Preserve if there is already a usable value with a non-trivial status
        if current_valor is not None and current_status not in (None, "pendente_revisao"):
            return
    elif current is not None:
        # Non-dict non-None value: treat as usable and preserve it
        return

    record["piso_nacional"] = {
        "valor": piso_nacional_value,
        "status_parametro": "pendente_revisao",
        "origem": "fallback_piso_nacional",
        "observacao": (
            "Valor de fallback do piso nacional aplicado automaticamente; "
            "requer validação."
        ),
        "data_extracao": today_str(),
    }


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
        "com_pdf": 0,
        "sem_pdf": 0,
        "pdf_sem_texto": 0,
        "extraidos": 0,
        "pendentes": 0,
        "conflitos": 0,
        "validos_preservados": 0,
        # Per-param extraction counters
        "piso_salarial_extraido": 0,
        "auxilio_alimentacao_extraido": 0,
        "hora_extra_extraido": 0,
        "jornada_extraido": 0,
        # Sub-structure counters
        "com_por_cargo": 0,
        "com_por_jornada": 0,
        "com_por_modalidade": 0,
        "com_por_escala": 0,
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
            stats["com_pdf"] += 1

        # Merge with existing
        merged = merge_itens_cct(record.get("itens_cct"), new_itens)

        # Summarize items
        has_por_cargo = has_por_jornada = has_por_modalidade = has_por_escala = False
        for key, item in merged.items():
            s = item.get("status_parametro", "?")
            v = item.get("valor") or item.get("percentual") or item.get("valor_textual") or "—"
            sub = ""
            if "por_cargo" in item:
                sub += " [por_cargo]"
                has_por_cargo = True
            if "por_jornada" in item:
                sub += " [por_jornada]"
                has_por_jornada = True
            if "por_modalidade" in item:
                sub += " [por_modalidade]"
                has_por_modalidade = True
            if "por_escala" in item:
                sub += " [por_escala]"
                has_por_escala = True
            marker = {"valido": "✓ valido", "extraido_para_revisao": "↗ extraído", "conflito": "⚡ conflito", "pendente_revisao": "· pendente"}.get(s, s)
            print(f"     {key:<25} {marker:<22} {v}{sub}")
            if s == "valido":
                stats["validos_preservados"] += 1
            elif s == "extraido_para_revisao":
                stats["extraidos"] += 1
                if key == "piso_salarial":
                    stats["piso_salarial_extraido"] += 1
                elif key == "auxilio_alimentacao":
                    stats["auxilio_alimentacao_extraido"] += 1
                elif key == "hora_extra":
                    stats["hora_extra_extraido"] += 1
                elif key == "jornada":
                    stats["jornada_extraido"] += 1
            elif s == "conflito":
                stats["conflitos"] += 1
            else:
                stats["pendentes"] += 1
        if has_por_cargo:
            stats["com_por_cargo"] += 1
        if has_por_jornada:
            stats["com_por_jornada"] += 1
        if has_por_modalidade:
            stats["com_por_modalidade"] += 1
        if has_por_escala:
            stats["com_por_escala"] += 1

        if not args.dry_run:
            record["itens_cct"] = merged

    print("\n" + "=" * 60)
    print(f"Registros processados : {stats['processados']}")
    print(f"  Com PDF encontrado  : {stats['com_pdf']}")
    print(f"  PDFs ausentes       : {stats['sem_pdf']}")
    print(f"  PDFs sem texto      : {stats['pdf_sem_texto']}")
    print(f"Itens extraídos       : {stats['extraidos']}")
    print(f"Itens pendentes       : {stats['pendentes']}")
    print(f"Itens em conflito     : {stats['conflitos']}")
    print(f"Itens válidos preserv.: {stats['validos_preservados']}")
    print(f"\n── Por parâmetro (extraídos) ──────────────────────────")
    print(f"  piso_salarial       : {stats['piso_salarial_extraido']}")
    print(f"  auxilio_alimentacao : {stats['auxilio_alimentacao_extraido']}")
    print(f"  hora_extra          : {stats['hora_extra_extraido']}")
    print(f"  jornada             : {stats['jornada_extraido']}")
    print(f"\n── Sub-estruturas ─────────────────────────────────────")
    print(f"  registros c/ por_cargo     : {stats['com_por_cargo']}")
    print(f"  registros c/ por_jornada   : {stats['com_por_jornada']}")
    print(f"  registros c/ por_modalidade: {stats['com_por_modalidade']}")
    print(f"  registros c/ por_escala    : {stats['com_por_escala']}")

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

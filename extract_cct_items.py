#!/usr/bin/env python3
"""
Extrai itens compostos das CCTs (piso salarial, adicional noturno, auxílio
alimentação, PLR, hora extra, sobreaviso, jornada) a partir dos PDFs em CCT/,
gravando os dados no campo itens_cct de cada registro em
data/base_parametros_sindicais.json e regenerando data/base_parametros_sindicais.js.

Governança:
  - Itens com status "valido" não são sobrescritos.
  - Dado extraído → status "extraido_para_revisao".
  - Não encontrado/interpretável → status "pendente_revisao".
  - Divergência entre documentos ou regras → status "conflito".
  - O script nunca inventa valores.

Uso:
    python3 extract_cct_items.py [--dry-run] [--force]

Flags:
  --dry-run   Apenas imprime o que seria alterado, sem salvar.
  --force     Re-extrai mesmo registros que já possuem itens_cct.
"""

import json
import os
import re
import sys
import unicodedata

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
JSON_PATH = os.path.join(REPO_ROOT, "data", "base_parametros_sindicais.json")
JS_PATH = os.path.join(REPO_ROOT, "data", "base_parametros_sindicais.js")
CCT_ROOT = os.path.join(REPO_ROOT, "CCT")

DRY_RUN = "--dry-run" in sys.argv
FORCE = "--force" in sys.argv

# ---------------------------------------------------------------------------
# PDF text extraction
# ---------------------------------------------------------------------------

def extract_pdf_text(pdf_path: str) -> str:
    """Extract text from a PDF file. Returns empty string on failure."""
    try:
        from pdfminer.high_level import extract_text
        return extract_text(pdf_path) or ""
    except Exception as exc:
        print(f"  [WARN] Falha ao ler {pdf_path}: {exc}", file=sys.stderr)
        return ""


def gather_pdf_texts(record: dict) -> list[tuple[str, str]]:
    """
    Return list of (relative_pdf_path, text) for all PDFs associated with a record.
    Strategy:
      1. If fonte_documento points to a .pdf file, use its parent folder.
      2. If fonte_documento points to a folder, use that folder.
      3. Fall back to CCT/<UF>/<sindicato_folder> matching.
    """
    fonte = record.get("fonte_documento") or ""
    results = []

    candidate_folder = None

    if fonte:
        abs_fonte = os.path.join(REPO_ROOT, fonte)
        if fonte.lower().endswith(".pdf") and os.path.isfile(abs_fonte):
            candidate_folder = os.path.dirname(abs_fonte)
        elif os.path.isdir(abs_fonte):
            candidate_folder = abs_fonte
        elif not fonte.lower().endswith(".pdf"):
            # might be a folder path without trailing slash
            if os.path.isdir(abs_fonte.rstrip("/")):
                candidate_folder = abs_fonte.rstrip("/")

    if candidate_folder is None:
        # Try to find folder via UF + sindicato name matching
        uf = record.get("uf", "").upper()
        sindicato = record.get("sindicato", "")
        candidate_folder = _find_folder_by_sindicato(uf, sindicato)

    if candidate_folder is None or not os.path.isdir(candidate_folder):
        return []

    for entry in sorted(os.listdir(candidate_folder)):
        if entry.lower().endswith(".pdf"):
            abs_path = os.path.join(candidate_folder, entry)
            rel_path = os.path.relpath(abs_path, REPO_ROOT)
            text = extract_pdf_text(abs_path)
            if text.strip():
                results.append((rel_path, text))

    return results


def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]", "", text.lower())


def _find_folder_by_sindicato(uf: str, sindicato: str) -> str | None:
    uf_path = os.path.join(CCT_ROOT, uf)
    if not os.path.isdir(uf_path):
        # Case-insensitive UF lookup
        for entry in os.listdir(CCT_ROOT):
            if entry.upper() == uf:
                uf_path = os.path.join(CCT_ROOT, entry)
                break
        else:
            return None

    norm_sind = _normalize(sindicato)
    norm_uf = _normalize(uf)
    # Strip UF from sindicato name
    if norm_sind.endswith(norm_uf):
        norm_sind_stripped = norm_sind[: -len(norm_uf)]
    else:
        norm_sind_stripped = norm_sind

    best = None
    best_score = 0
    for folder in os.listdir(uf_path):
        folder_path = os.path.join(uf_path, folder)
        if not os.path.isdir(folder_path):
            continue
        norm_folder = _normalize(folder)
        if norm_folder == norm_sind or norm_folder == norm_sind_stripped:
            return folder_path
        min_len = min(len(norm_folder), len(norm_sind_stripped))
        if min_len >= 4:
            prefix_match = 0
            for a, b in zip(norm_folder, norm_sind_stripped):
                if a == b:
                    prefix_match += 1
                else:
                    break
            score = prefix_match / max(len(norm_folder), len(norm_sind_stripped))
            if score > best_score:
                best_score = score
                best = folder_path

    if best_score >= 0.7:
        return best
    return None


# ---------------------------------------------------------------------------
# Text helpers
# ---------------------------------------------------------------------------

def _clean(text: str) -> str:
    """Collapse whitespace and normalize to plain text."""
    return re.sub(r"\s+", " ", text).strip()


def _find_section(text: str, keywords: list[str], window: int = 1200) -> str | None:
    """
    Return a text window around the first keyword match (case-insensitive).
    """
    lower = text.lower()
    for kw in keywords:
        idx = lower.find(kw.lower())
        if idx != -1:
            start = max(0, idx - 100)
            end = min(len(text), idx + window)
            return text[start:end]
    return None


def _find_all_sections(text: str, keywords: list[str], window: int = 1200) -> list[str]:
    """Return all windows around keyword matches."""
    lower = text.lower()
    sections = []
    for kw in keywords:
        start = 0
        while True:
            idx = lower.find(kw.lower(), start)
            if idx == -1:
                break
            sec_start = max(0, idx - 100)
            sec_end = min(len(text), idx + window)
            sections.append(text[sec_start:sec_end])
            start = idx + len(kw)
    return sections


def _extract_brl(text: str) -> tuple[float | None, str | None]:
    """
    Return (float_value, raw_match) for the first R$ amount found.
    Handles formats like R$ 1.540,47 or R$1540,47.
    """
    pattern = r"R\$\s*([\d]{1,3}(?:\.[\d]{3})*(?:,\d{1,2})?|\d+(?:,\d{1,2})?)"
    m = re.search(pattern, text)
    if m:
        raw = m.group(1).replace(".", "").replace(",", ".")
        try:
            return float(raw), _clean(text[m.start():m.end() + 60])
        except ValueError:
            pass
    return None, None


def _extract_percent(text: str) -> tuple[float | None, str | None]:
    """Return (float_pct, raw) for the first percentage found (e.g. 20%, 33,33%)."""
    pattern = r"(\d{1,3}(?:[,\.]\d{1,2})?)\s*%"
    m = re.search(pattern, text)
    if m:
        raw_val = m.group(1).replace(",", ".")
        try:
            return float(raw_val), _clean(text[m.start():m.end() + 60])
        except ValueError:
            pass
    return None, None


def _extract_hours(text: str) -> tuple[int | None, str | None]:
    """Return weekly hours from patterns like '44 horas', '44h semanais'."""
    pattern = r"(\d{2,3})\s*(?:h(?:oras?)?\s*(?:semanais?|mensais?|por\s*semana)?)"
    m = re.search(pattern, text, re.IGNORECASE)
    if m:
        try:
            val = int(m.group(1))
            if 20 <= val <= 300:  # sanity check
                return val, _clean(text[m.start():m.end() + 80])
        except ValueError:
            pass
    return None, None


def _truncate_at_next_clause(text: str, start_offset: int = 100) -> str:
    """
    Truncate text at the start of the NEXT clause header (after an initial
    offset to skip the current clause header itself).
    """
    m = re.search(
        r"\bCL[ÁA]USULA\b",
        text[start_offset:],
        re.IGNORECASE,
    )
    if m:
        return text[: start_offset + m.start()]
    return text


def _clause_header(text: str) -> str | None:
    """Extract the clause header closest to the start of the text window."""
    m = re.search(
        r"CL[ÁA]USULA\s+[\wÀ-Ú]+\s*[-–]\s*[^\n]{5,80}",
        text,
        re.IGNORECASE,
    )
    return _clean(m.group(0)) if m else None


def _build_item(
    valor=None,
    percentual=None,
    regra: str | None = None,
    tipo: str | None = None,
    unidade: str | None = None,
    fonte_documento: str | None = None,
    clausula: str | None = None,
    observacao: str | None = None,
    status: str = "extraido_para_revisao",
) -> dict:
    return {
        "valor": valor,
        "percentual": percentual,
        "regra": regra,
        "tipo": tipo,
        "unidade": unidade,
        "fonte_documento": fonte_documento,
        "clausula": clausula,
        "observacao": observacao,
        "status_parametro": status,
    }


def _pending(observacao: str | None = None, fonte: str | None = None) -> dict:
    return _build_item(
        observacao=observacao,
        fonte_documento=fonte,
        status="pendente_revisao",
    )


# ---------------------------------------------------------------------------
# Item extractors
# ---------------------------------------------------------------------------

def _extract_brl_values(text: str) -> list[float]:
    """Return all BRL values >= 900 found in text (wage-range sanity filter)."""
    pattern = r"R\$\s*([\d]{1,3}(?:\.[\d]{3})*(?:,\d{1,2})?|\d+(?:,\d{1,2})?)"
    values = []
    for m in re.finditer(pattern, text):
        raw = m.group(1).replace(".", "").replace(",", ".")
        try:
            v = float(raw)
            if v >= 900:  # sanity: pisos are above minimum wage range
                values.append(v)
        except ValueError:
            pass
    return values


def extract_piso_salarial(pdf_texts: list[tuple[str, str]]) -> list[dict]:
    """
    Returns list of piso items (may be empty, one, or multiple for técnico/admin/único).
    Looks for R$ values >= 900 in piso salarial sections only.
    """
    results = []
    seen_values: set[float] = set()

    piso_kws = ["piso salarial", "salário mínimo da categoria", "piso da categoria"]

    for rel_path, text in pdf_texts:
        sections = _find_all_sections(text, piso_kws, window=1500)
        for sec in sections:
            clausula = _clause_header(sec)
            lower_sec = sec.lower()

            # Detect tipo
            tipo_default = "piso_unico"
            if "técnico" in lower_sec or "tecnico" in lower_sec:
                tipo_default = "piso_tecnico"
            elif "administrat" in lower_sec:
                tipo_default = "piso_administrativo"

            # Try to find multi-jornada pisos:
            # Pattern: "R$ value ... N horas" OR "N horas ... R$ value" within 150 chars
            jornada_piso: list[tuple[float, str]] = []
            brl_iter = list(re.finditer(
                r"R\$\s*([\d]{1,3}(?:\.[\d]{3})*,\d{2}|\d+,\d{2})", sec
            ))
            hour_iter = list(re.finditer(
                r"\b(\d{2,3})\s*(?:h(?:oras?)?\s*(?:semanais?|mensais?)?)", sec, re.IGNORECASE
            ))

            for brl_m in brl_iter:
                raw = brl_m.group(1).replace(".", "").replace(",", ".")
                try:
                    val = float(raw)
                except ValueError:
                    continue
                if val < 900:
                    continue
                # Find closest hour mention within ±200 chars
                best_h = None
                best_dist = 9999
                for hour_m in hour_iter:
                    h = int(hour_m.group(1))
                    if not (20 <= h <= 300):
                        continue
                    dist = abs(brl_m.start() - hour_m.start())
                    if dist < best_dist:
                        best_dist = dist
                        best_h = h
                jornada_label = f"piso_{best_h}h" if (best_h and best_dist <= 200) else tipo_default
                jornada_piso.append((val, jornada_label))

            if jornada_piso:
                for val, jlabel in jornada_piso:
                    if val in seen_values:
                        continue
                    seen_values.add(val)
                    results.append(
                        _build_item(
                            valor=val,
                            tipo=jlabel,
                            unidade="BRL_mensal",
                            regra=_clean(sec[:400]),
                            fonte_documento=rel_path,
                            clausula=clausula,
                            status="extraido_para_revisao",
                        )
                    )
                continue

            # Single piso fallback
            vals = _extract_brl_values(sec)
            if vals:
                val = vals[0]
                if val not in seen_values:
                    seen_values.add(val)
                    results.append(
                        _build_item(
                            valor=val,
                            tipo=tipo_default,
                            unidade="BRL_mensal",
                            regra=_clean(sec[:400]),
                            fonte_documento=rel_path,
                            clausula=clausula,
                            status="extraido_para_revisao",
                        )
                    )

    if not results:
        return [_pending("Piso salarial não encontrado no(s) PDF(s)")]
    return results


def extract_adicional_noturno(pdf_texts: list[tuple[str, str]]) -> dict:
    kws = ["adicional noturno", "adicional  noturno"]
    candidates = []

    for rel_path, text in pdf_texts:
        sec = _find_section(text, kws, window=600)
        if sec is None:
            continue
        pct, _ = _extract_percent(sec)
        clausula = _clause_header(sec)
        if pct is not None:
            candidates.append(
                _build_item(
                    percentual=pct,
                    tipo="adicional_noturno",
                    unidade="percentual_hora",
                    regra=_clean(sec[:400]),
                    fonte_documento=rel_path,
                    clausula=clausula,
                    status="extraido_para_revisao",
                )
            )

    if not candidates:
        return _pending("Adicional noturno não encontrado no(s) PDF(s)")
    if len(candidates) > 1:
        pcts = {c["percentual"] for c in candidates}
        if len(pcts) > 1:
            merged = candidates[0].copy()
            merged["status_parametro"] = "conflito"
            merged["observacao"] = (
                f"Percentuais divergentes encontrados: {sorted(pcts)}"
            )
            return merged
    return candidates[0]


def extract_auxilio_alimentacao(pdf_texts: list[tuple[str, str]]) -> dict:
    kws = [
        "auxílio alimentação",
        "auxilio alimentacao",
        "vale refeição",
        "vale refeicao",
        "vale-refeição",
        "vale alimentação",
        "vale-alimentação",
        "vr/va",
        "va/vr",
    ]
    candidates = []

    for rel_path, text in pdf_texts:
        sec = _find_section(text, kws, window=800)
        if sec is None:
            continue
        val, _ = _extract_brl(sec)
        clausula = _clause_header(sec)
        if val is not None:
            tipo = "vale_refeicao"
            lower_sec = sec.lower()
            if "alimentaç" in lower_sec and "refeic" not in lower_sec:
                tipo = "vale_alimentacao"
            elif "alimentaç" in lower_sec and "refeic" in lower_sec:
                tipo = "vale_refeicao_alimentacao"
            candidates.append(
                _build_item(
                    valor=val,
                    tipo=tipo,
                    unidade="BRL_diario",
                    regra=_clean(sec[:400]),
                    fonte_documento=rel_path,
                    clausula=clausula,
                    status="extraido_para_revisao",
                )
            )

    if not candidates:
        return _pending("Auxílio alimentação/vale refeição não encontrado no(s) PDF(s)")
    if len(candidates) > 1:
        vals = {c["valor"] for c in candidates}
        if len(vals) > 1:
            merged = candidates[0].copy()
            merged["status_parametro"] = "conflito"
            merged["observacao"] = f"Valores divergentes encontrados: {sorted(vals)}"
            return merged
    return candidates[0]


def extract_plr(pdf_texts: list[tuple[str, str]]) -> dict:
    kws = [
        "participação nos lucros",
        "participacao nos lucros",
        "plr",
        "ppr",
        "plr/ppr",
        "ppr/plr",
    ]

    for rel_path, text in pdf_texts:
        sec = _find_section(text, kws, window=1200)
        if sec is None:
            continue
        # Truncate at next clause to avoid picking up values from adjacent clauses
        sec = _truncate_at_next_clause(sec)
        clausula = _clause_header(sec)
        regra = _clean(sec[:500])

        # Look for percentage (e.g., "5% do salário")
        pct, _ = _extract_percent(sec)
        # Look for a BRL value that is >= 200 (PLR is never a few reais)
        brl_vals = _extract_brl_values(sec)
        val = brl_vals[0] if brl_vals else None

        if pct is not None or val is not None:
            return _build_item(
                valor=val,
                percentual=pct,
                tipo="plr",
                unidade="percentual_salario" if pct and not val else "BRL",
                regra=regra,
                fonte_documento=rel_path,
                clausula=clausula,
                status="extraido_para_revisao",
            )
        else:
            # Found section but no numeric value — extract rule as text
            return _build_item(
                tipo="plr",
                regra=regra,
                fonte_documento=rel_path,
                clausula=clausula,
                observacao="Regra qualitativa — verificar negociação específica",
                status="extraido_para_revisao",
            )

    return _pending("PLR não encontrado no(s) PDF(s)")


def extract_hora_extra(pdf_texts: list[tuple[str, str]]) -> list[dict]:
    kws = ["hora extra", "horas extras", "hora extraordinária", "horas extraordinárias"]
    results = []
    seen: set[tuple] = set()

    day_patterns = [
        (r"s[áa]bado", "sabado"),
        (r"domingo", "domingo"),
        (r"feriado", "feriado"),
        (r"(?:dia\s+)?(?:útil|util)", "dia_util"),
    ]

    for rel_path, text in pdf_texts:
        sections = _find_all_sections(text, kws, window=800)
        for sec in sections:
            clausula = _clause_header(sec)

            # Look for day-specific percentages
            for day_pattern, day_label in day_patterns:
                # Find window around day mention
                m = re.search(day_pattern, sec, re.IGNORECASE)
                if m:
                    window_start = max(0, m.start() - 100)
                    window_end = min(len(sec), m.end() + 200)
                    day_window = sec[window_start:window_end]
                    pct, _ = _extract_percent(day_window)
                    if pct is not None:
                        key = (pct, day_label)
                        if key not in seen:
                            seen.add(key)
                            results.append(
                                _build_item(
                                    percentual=pct,
                                    tipo=f"hora_extra_{day_label}",
                                    unidade="percentual_hora_normal",
                                    regra=_clean(day_window[:300]),
                                    fonte_documento=rel_path,
                                    clausula=clausula,
                                    status="extraido_para_revisao",
                                )
                            )

            # General hora extra percentage (first found in section)
            pct, _ = _extract_percent(sec)
            if pct is not None:
                key = (pct, "geral")
                if key not in seen:
                    seen.add(key)
                    results.append(
                        _build_item(
                            percentual=pct,
                            tipo="hora_extra",
                            unidade="percentual_hora_normal",
                            regra=_clean(sec[:400]),
                            fonte_documento=rel_path,
                            clausula=clausula,
                            status="extraido_para_revisao",
                        )
                    )

    if not results:
        return [_pending("Hora extra não encontrada no(s) PDF(s)")]
    return results


def extract_sobreaviso(pdf_texts: list[tuple[str, str]]) -> dict:
    kws = ["sobreaviso", "sobre aviso"]

    for rel_path, text in pdf_texts:
        sec = _find_section(text, kws, window=800)
        if sec is None:
            continue
        clausula = _clause_header(sec)
        regra = _clean(sec[:500])
        pct, _ = _extract_percent(sec)
        # Sobreaviso is often defined as 1/3 (art 244 CLT) — look for fraction
        fraction_match = re.search(r"1/3|um\s*terço|33[\.,]3", sec, re.IGNORECASE)

        if pct is not None:
            return _build_item(
                percentual=pct,
                tipo="sobreaviso",
                unidade="percentual_hora_normal",
                regra=regra,
                fonte_documento=rel_path,
                clausula=clausula,
                status="extraido_para_revisao",
            )
        elif fraction_match:
            return _build_item(
                percentual=33.33,
                tipo="sobreaviso",
                unidade="percentual_hora_normal",
                regra=regra,
                fonte_documento=rel_path,
                clausula=clausula,
                observacao="Percentual 1/3 conforme CLT art. 244 extraído da regra textual",
                status="extraido_para_revisao",
            )
        else:
            return _build_item(
                tipo="sobreaviso",
                regra=regra,
                fonte_documento=rel_path,
                clausula=clausula,
                observacao="Regra qualitativa — percentual não identificado automaticamente",
                status="extraido_para_revisao",
            )

    return _pending("Sobreaviso não encontrado no(s) PDF(s)")


def extract_jornada(pdf_texts: list[tuple[str, str]]) -> list[dict]:
    """Extract working hours (jornada) from CCT text."""
    kws = [
        "jornada de trabalho",
        "carga horária",
        "carga  horária",
        "jornada semanal",
        "horas semanais",
        "horas mensais",
    ]
    results = []
    seen_hours: set[int] = set()

    # Common jornada values to search for explicitly
    fixed_hours = [36, 40, 44, 180, 200, 220]

    for rel_path, text in pdf_texts:
        for kw in kws:
            sections = _find_all_sections(text, [kw], window=600)
            for sec in sections:
                clausula = _clause_header(sec)
                hours, _ = _extract_hours(sec)
                if hours is not None and hours not in seen_hours:
                    seen_hours.add(hours)
                    unidade = "horas_semanais" if hours <= 50 else "horas_mensais"
                    results.append(
                        _build_item(
                            valor=hours,
                            tipo="jornada",
                            unidade=unidade,
                            regra=_clean(sec[:400]),
                            fonte_documento=rel_path,
                            clausula=clausula,
                            status="extraido_para_revisao",
                        )
                    )

        # Search for explicit hour values in full text
        for h in fixed_hours:
            if h in seen_hours:
                continue
            pattern = rf"\b{h}\s*(?:h(?:oras?)?\s*(?:semanais?|mensais?)?)"
            if re.search(pattern, text, re.IGNORECASE):
                seen_hours.add(h)
                unidade = "horas_semanais" if h <= 50 else "horas_mensais"
                results.append(
                    _build_item(
                        valor=h,
                        tipo="jornada",
                        unidade=unidade,
                        regra=f"Jornada de {h} horas identificada no documento",
                        fonte_documento=rel_path,
                        status="extraido_para_revisao",
                    )
                )

    if not results:
        return [_pending("Jornada não encontrada no(s) PDF(s)")]
    return results


# ---------------------------------------------------------------------------
# Main extraction for one record
# ---------------------------------------------------------------------------

def extract_itens_cct(record: dict) -> dict:
    """
    Returns a new itens_cct dict for the record.
    Respects existing 'valido' items.
    """
    existing_itens = record.get("itens_cct") or {}

    pdf_texts = gather_pdf_texts(record)

    if not pdf_texts:
        # No PDFs found → all items pending
        def _p(key):
            ex = existing_itens.get(key)
            if isinstance(ex, dict) and ex.get("status_parametro") == "valido":
                return ex
            if isinstance(ex, list):
                if any(i.get("status_parametro") == "valido" for i in ex):
                    return ex
            return _pending("Nenhum PDF localizado para este sindicato")

        return {
            "piso_salarial": _p("piso_salarial"),
            "adicional_noturno": _p("adicional_noturno"),
            "auxilio_alimentacao": _p("auxilio_alimentacao"),
            "plr": _p("plr"),
            "hora_extra": _p("hora_extra"),
            "sobreaviso": _p("sobreaviso"),
            "jornada": _p("jornada"),
        }

    def _keep_or_extract(key, extracted):
        """Preserve valido items; otherwise use extracted."""
        ex = existing_itens.get(key)
        if isinstance(ex, dict) and ex.get("status_parametro") == "valido":
            return ex
        if isinstance(ex, list):
            validos = [i for i in ex if i.get("status_parametro") == "valido"]
            if validos:
                return validos  # keep only validated ones
        return extracted

    piso = extract_piso_salarial(pdf_texts)
    adicional = extract_adicional_noturno(pdf_texts)
    alimentacao = extract_auxilio_alimentacao(pdf_texts)
    plr = extract_plr(pdf_texts)
    hora_extra = extract_hora_extra(pdf_texts)
    sobreaviso = extract_sobreaviso(pdf_texts)
    jornada = extract_jornada(pdf_texts)

    return {
        "piso_salarial": _keep_or_extract("piso_salarial", piso),
        "adicional_noturno": _keep_or_extract("adicional_noturno", adicional),
        "auxilio_alimentacao": _keep_or_extract("auxilio_alimentacao", alimentacao),
        "plr": _keep_or_extract("plr", plr),
        "hora_extra": _keep_or_extract("hora_extra", hora_extra),
        "sobreaviso": _keep_or_extract("sobreaviso", sobreaviso),
        "jornada": _keep_or_extract("jornada", jornada),
    }


# ---------------------------------------------------------------------------
# Regenerate JS file
# ---------------------------------------------------------------------------

def regenerate_js(data: dict):
    js_content = (
        "// Gerado automaticamente por export_inline_data.py — não editar manualmente.\n"
        "window.BASE_PARAMETROS_SINDICAIS = "
        + json.dumps(data, ensure_ascii=False)
        + ";\n"
    )
    with open(JS_PATH, "w", encoding="utf-8") as f:
        f.write(js_content)
    print(f"JS regenerado: {JS_PATH}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    with open(JSON_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    registros = data.get("registros", [])
    updated = 0

    for i, record in enumerate(registros):
        rid = record.get("id_registro_reajuste", f"[{i}]")
        uf = record.get("uf", "?")
        sind = record.get("sindicato", "?")

        # Skip records that already have itens_cct unless --force
        if not FORCE and record.get("itens_cct"):
            print(f"  [SKIP] {uf} / {sind} — itens_cct já presente (use --force para re-extrair)")
            continue

        print(f"  [PROC] {uf} / {sind} ({rid})")
        itens = extract_itens_cct(record)

        if DRY_RUN:
            print(json.dumps(itens, ensure_ascii=False, indent=4))
        else:
            record["itens_cct"] = itens
            updated += 1

    if not DRY_RUN:
        import datetime
        data["data_geracao"] = datetime.datetime.now().astimezone().isoformat()
        with open(JSON_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"\nJSON atualizado: {JSON_PATH} ({updated} registros processados)")
        regenerate_js(data)
    else:
        print(f"\n[DRY-RUN] Nenhum arquivo alterado. {updated} registros seriam atualizados.")


if __name__ == "__main__":
    main()

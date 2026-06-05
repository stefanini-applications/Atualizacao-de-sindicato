#!/usr/bin/env python3
"""
Popula os campos de variação estruturada (`por_cargo`, `por_jornada`,
`por_modalidade`, `por_escala`) nos itens CCT da base sindical real.

Os campos de primeiro nível (valor base) nunca são sobrescritos.
Itens já marcados como "valido" são preservados integralmente.
Cada subitem criado recebe:
    status_parametro = "extraido_para_revisao"
    origem_regra     = "cct_extraida"

Uso:
    python3 populate_cct_variations.py [--dry-run] [--ids ID1 ID2 ...]

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

ORIGEM_REGRA = "cct_extraida"
STATUS = "extraido_para_revisao"

# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────


def normalize(text: str) -> str:
    """Lowercase without accents — used for pattern matching only."""
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    return text.lower()


def truncate(text: str | None, max_len: int) -> str | None:
    if not text:
        return text
    text = " ".join(text.split())
    return text[:max_len] + "…" if len(text) > max_len else text


def extract_pdf_text(pdf_path: str) -> tuple[str, str]:
    """Extract raw text from a PDF using pdftotext."""
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
        return (text, "ok") if len(text.strip()) >= 50 else ("", "pdf_sem_texto")
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return "", "erro_pdftotext"


def brl_to_float(raw: str) -> float | None:
    """Convert Brazilian BRL string to float. e.g. '1.540,47' → 1540.47"""
    clean = raw.replace(".", "").replace(",", ".")
    try:
        val = float(clean)
        return val if val >= 5 else None
    except ValueError:
        return None


def _subitem(
    cargo_ou_funcao: str,
    valor: float | None,
    jornada: str | None,
    tipo: str,
    unidade: str,
    fonte: str,
    observacao: str | None = None,
) -> dict:
    return {
        "cargo_ou_funcao": cargo_ou_funcao,
        "valor": valor,
        "jornada": jornada,
        "tipo": tipo,
        "unidade": unidade,
        "status_parametro": STATUS,
        "origem_regra": ORIGEM_REGRA,
        "fonte_documento": fonte,
        "observacao": observacao,
    }


# ──────────────────────────────────────────────────────────────────────────────
# Variation extractors
# ──────────────────────────────────────────────────────────────────────────────


def extract_por_cargo(text: str, fonte: str) -> list[dict]:
    """
    Extract per-cargo salary variants from the PDF text.

    Handles two common formats:
    1. Annexo table rows:  "12 Encarregado Geral   4101-05  4%  2.177,75"
    2. Inline sentence:    "a) Analista de Suporte o valor de R$ 2.434,07"
    """
    subitens: list[dict] = []
    seen: set[str] = set()

    # ── Format 1: table rows (Annexo) ──────────────────────────────────────
    # Matches lines with: [optional_seq] CARGO_NAME [CBO_code] [pct%] BRL_value
    # CBO codes like 4101-05 are 4 digits dash 2 digits
    # NOTE: must not cross line boundaries — cargo name lives on a single line.
    TABLE_ROW = re.compile(
        r"^\s*(?:\d+\s+)?"                              # optional seq number
        r"([A-ZÀ-ÿ][A-ZÀ-ÿa-z][A-ZÀ-ÿa-z ().,/ºª-]{2,55}?)"  # cargo name
        r"\s+(?:\d{4}-\d{2}\s+)?"                       # optional CBO code
        r"(?:\d+%\s+)?"                                  # optional reajuste%
        r"([\d]{1,3}(?:[.,]\d{3})*[.,]\d{2})"           # BRL value (requires cents)
        r"\s*$",
        re.MULTILINE,
    )

    # Keywords that indicate the match is a header/section label, not a real cargo
    SKIP_KEYWORDS = (
        "classe", "categoria", "tabela", "piso salarial", "funcao",
        "cargo", "salario", "descricao", "reajuste", "cbo", "minimo",
        "estabelecido", "clausula", "convenção",
    )

    # Deduplicate by (cargo, valor)
    for m in TABLE_ROW.finditer(text):
        cargo_raw = m.group(1).strip().rstrip("., ")
        valor_raw = m.group(2).strip()

        # Skip lines with newlines in cargo name (shouldn't happen with ^$ but guard anyway)
        if "\n" in cargo_raw or "\r" in cargo_raw:
            continue

        cargo_n = normalize(cargo_raw)
        if any(kw in cargo_n for kw in SKIP_KEYWORDS):
            continue
        if len(cargo_raw) < 5:
            continue

        val = brl_to_float(valor_raw)
        if val is None or val < 500 or val > 100_000:
            continue

        key = (normalize(cargo_raw), round(val, 2))
        if key in seen:
            continue
        seen.add(key)

        subitens.append(_subitem(
            cargo_ou_funcao=cargo_raw,
            valor=val,
            jornada=None,
            tipo="valor_mensal",
            unidade="BRL",
            fonte=fonte,
        ))

    # ── Format 2: inline sentences ──────────────────────────────────────────
    # "a) Analista de Suporte o valor correspondente a R$ 2.434,07"
    # "exclusivamente ao Técnico R$ 1.900,00"
    # NOTE: cargo name uses [ \t] (not \s) to avoid crossing line boundaries.
    INLINE_CARGO = re.compile(
        r"(?:ao|à|para o|para a|para os|para as|exclusivamente ao?|"
        r"trabalhadores(?:[ \t]+da(?:s)?[ \t]+função)?)\s+"
        r"([A-ZÀ-ÿ][A-ZÀ-ÿa-z /().,ºª-]{3,60}?)"
        r"[ \t]+(?:o valor(?:\s+correspondente)?(?:\s+a)?|de)\s+"
        r"R\$[ \t]*([\d.,]+)",
        re.IGNORECASE,
    )
    for m in INLINE_CARGO.finditer(text):
        cargo_raw = m.group(1).strip().rstrip("., ")
        val = brl_to_float(m.group(2))
        if not cargo_raw or val is None or val < 500 or val > 100_000:
            continue
        # Guard: must not contain line breaks
        if "\n" in cargo_raw or "\r" in cargo_raw:
            continue
        key = (normalize(cargo_raw), round(val, 2))
        if key in seen:
            continue
        seen.add(key)
        subitens.append(_subitem(
            cargo_ou_funcao=cargo_raw,
            valor=val,
            jornada=None,
            tipo="valor_mensal",
            unidade="BRL",
            fonte=fonte,
        ))

    return subitens


def extract_por_jornada(text: str, fonte: str, item_tipo: str) -> list[dict]:
    """
    Extract benefit variants by jornada (hours/month or hours/week).

    Covers auxilio_alimentacao and piso_salarial variations where value
    differs by jornada.  Patterns like:
      "jornada de 44 horas semanais ... R$ 20,00"
      "jornada de 200/220 horas mensais ... R$ 10,50"
      "trabalhadores com jornada de 36 horas ... R$ 15,00 por dia"
    """
    subitens: list[dict] = []
    seen: set[tuple] = set()
    text_n = normalize(text)

    # Pattern: "jornada de X horas [semanais|mensais]" near a BRL value in the same sentence
    JORNADA_SENTENCE = re.compile(
        r"(?:jornada\s+(?:de\s+)?|carga\s+hor[aá]ria\s+de\s+)"
        r"([\d/]+)\s*(?:horas?\s+)?(?:semanais?|mensais?|di[aá]rias?)?"
        r"[^.]*?"
        r"R\$\s*([\d.,]+)",
        re.IGNORECASE,
    )
    for m in JORNADA_SENTENCE.finditer(text):
        jornada_raw = m.group(1).strip()
        val = brl_to_float(m.group(2))
        if val is None or val < 1:
            continue

        # Build jornada label
        snippet_n = normalize(m.group(0))
        if "semanal" in snippet_n:
            jornada_label = f"{jornada_raw}h/semana"
        elif "mensal" in snippet_n:
            jornada_label = f"{jornada_raw}h/mês"
        elif "diaria" in snippet_n or "diário" in snippet_n:
            jornada_label = f"{jornada_raw}h/dia"
        else:
            jornada_label = f"{jornada_raw}h"

        # Detect unit
        if "por dia" in snippet_n or "dia efetiv" in snippet_n or "dia util" in snippet_n:
            unidade = "BRL/dia"
            tipo = item_tipo if item_tipo else "auxilio_alimentacao"
        else:
            unidade = "BRL/mês"
            tipo = item_tipo if item_tipo else "valor_mensal"

        key = (jornada_label, round(val, 2))
        if key in seen:
            continue
        seen.add(key)

        subitens.append(_subitem(
            cargo_ou_funcao=f"Jornada {jornada_label}",
            valor=val,
            jornada=jornada_label,
            tipo=tipo,
            unidade=unidade,
            fonte=fonte,
        ))

    return subitens


def extract_por_modalidade(text: str, fonte: str) -> list[dict]:
    """
    Extract hora_extra variants by day type (modalidade).

    Patterns:
      "50% (cinquenta) nos dias úteis ... 75% ... sábados ... 100% domingos/feriados"
      separate sentences each mentioning day type + percentage
    """
    subitens: list[dict] = []
    seen: set[tuple] = set()

    # Map of day-type keywords → canonical label
    DAY_TYPES = [
        (r"domingos?\s+e\s+feriados?|feriados?\s+e\s+domingos?", "Domingo/Feriado"),
        (r"domingos?(?!\s+e\s+feriados?)", "Domingo"),
        (r"feriados?(?!\s+e\s+domingos?)", "Feriado"),
        (r"s[aá]bados?", "Sábado"),
        (r"dias?\s+[uú]teis?", "Dia útil"),
    ]

    text_n = normalize(text)

    for pattern, label in DAY_TYPES:
        # Find "X% ... day-type" or "day-type ... X%" in nearby text (same sentence)
        combined = re.compile(
            rf"(?:(\d+(?:[,.]?\d+)?)\s*%[^.{{0,80}}]*?{pattern}"
            rf"|{pattern}[^.{{0,80}}]*?(\d+(?:[,.]?\d+)?)\s*%)",
            re.IGNORECASE,
        )
        for m in combined.finditer(text_n):
            raw_pct = m.group(1) or m.group(2)
            if not raw_pct:
                continue
            try:
                pct = float(raw_pct.replace(",", "."))
            except ValueError:
                continue
            if not (30 <= pct <= 300):
                continue

            key = (label, round(pct, 2))
            if key in seen:
                continue
            seen.add(key)

            subitens.append(_subitem(
                cargo_ou_funcao=label,
                valor=pct,
                jornada=None,
                tipo="percentual_hora_extra",
                unidade="%",
                fonte=fonte,
                observacao=f"Hora extra — {label}",
            ))

    return subitens


def extract_por_escala(text: str, fonte: str) -> list[dict]:
    """
    Extract jornada variants by work schedule/scale (escala).

    Handles:
      - 12x36 shifts
      - named jornadas: 36h/sem, 44h/sem etc. with different rules
      - sobreaviso/on-call per-scale differences
    """
    subitens: list[dict] = []
    seen: set[str] = set()
    text_n = normalize(text)

    # ── 12x36 scale ──────────────────────────────────────────────────────────
    if re.search(r"12\s*[x×]\s*36", text_n):
        # See if there's a specific BRL or % value tied to 12x36
        m = re.search(
            r"12\s*[x×]\s*36[^.]{0,200}?(?:R\$\s*([\d.,]+)|(\d+(?:[,.]?\d+)?)\s*%)",
            text_n,
        )
        key = "12x36"
        if key not in seen:
            seen.add(key)
            val = None
            unidade = "regime"
            tipo = "jornada_escala"
            obs = "Regime 12x36 identificado na CCT"
            if m:
                raw = m.group(1) or m.group(2)
                if raw:
                    try:
                        val = float(raw.replace(".", "").replace(",", "."))
                        unidade = "BRL" if m.group(1) else "%"
                    except ValueError:
                        pass
            subitens.append(_subitem(
                cargo_ou_funcao="Escala 12x36",
                valor=val,
                jornada="12x36",
                tipo=tipo,
                unidade=unidade,
                fonte=fonte,
                observacao=obs,
            ))

    # ── Named weekly jornadas ────────────────────────────────────────────────
    # Look for "jornada de X horas semanais" as distinct scales (not near BRL — those go to por_jornada)
    WEEKLY_PATTERN = re.compile(
        r"jornada\s+de\s+(\d+)\s*(?:\([^)]+\)\s*)?horas?\s+semanais?",
        re.IGNORECASE,
    )
    for m in WEEKLY_PATTERN.finditer(text_n):
        hrs = int(m.group(1))
        if not (20 <= hrs <= 60):
            continue
        key = f"{hrs}h/semana"
        if key in seen:
            continue
        seen.add(key)
        subitens.append(_subitem(
            cargo_ou_funcao=f"Jornada {hrs}h/semana",
            valor=float(hrs),
            jornada=key,
            tipo="jornada_semanal",
            unidade="h/semana",
            fonte=fonte,
            observacao=f"Escala de {hrs}h semanais identificada na CCT",
        ))

    return subitens


# ──────────────────────────────────────────────────────────────────────────────
# Item-level dispatcher
# ──────────────────────────────────────────────────────────────────────────────


def build_variations(item_key: str, text: str, fonte: str) -> dict[str, list[dict]]:
    """
    For a given itens_cct key, return a dict of the variation fields to populate.
    Returns only non-empty lists.
    """
    result: dict[str, list[dict]] = {}

    if item_key == "piso_salarial":
        por_cargo = extract_por_cargo(text, fonte)
        if por_cargo:
            result["por_cargo"] = por_cargo
        por_jornada = extract_por_jornada(text, fonte, "piso_salarial")
        if por_jornada:
            result["por_jornada"] = por_jornada

    elif item_key == "auxilio_alimentacao":
        por_jornada = extract_por_jornada(text, fonte, "auxilio_alimentacao")
        if por_jornada:
            result["por_jornada"] = por_jornada
        por_escala = extract_por_escala(text, fonte)
        if por_escala:
            result["por_escala"] = por_escala

    elif item_key == "hora_extra":
        por_modalidade = extract_por_modalidade(text, fonte)
        if por_modalidade:
            result["por_modalidade"] = por_modalidade

    elif item_key == "jornada":
        por_escala = extract_por_escala(text, fonte)
        if por_escala:
            result["por_escala"] = por_escala

    elif item_key == "adicional_noturno":
        por_escala = extract_por_escala(text, fonte)
        if por_escala:
            result["por_escala"] = por_escala

    elif item_key == "sobreaviso":
        por_escala = extract_por_escala(text, fonte)
        if por_escala:
            result["por_escala"] = por_escala

    elif item_key == "plr":
        por_cargo = extract_por_cargo(text, fonte)
        if por_cargo:
            # PLR per-cargo only if explicitly listed; keep small
            por_cargo = [c for c in por_cargo if any(
                kw in normalize(c["cargo_ou_funcao"])
                for kw in ("plr", "participacao", "lucro")
            )]
            if por_cargo:
                result["por_cargo"] = por_cargo

    return result


def complement_item(item: dict, variations: dict[str, list[dict]]) -> tuple[dict, list[str]]:
    """
    Additively complement an itens_cct item with variation subitems.

    Base-level fields are never altered.
    Returns (updated_item, list_of_changed_field_names).
    """
    if item.get("status_parametro") == "valido":
        return item, []

    changed: list[str] = []
    updated = dict(item)

    for field, subitems in variations.items():
        if not subitems:
            continue
        existing = updated.get(field)
        # Only populate if field is absent or empty
        if not existing:
            updated[field] = subitems
            changed.append(field)

    return updated, changed


# ──────────────────────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Exibe mudanças sem salvar")
    parser.add_argument("--ids", nargs="+", metavar="ID", help="Processar apenas esses IDs")
    args = parser.parse_args()

    with open(JSON_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    records = data.get("registros", [])
    id_filter = set(args.ids) if args.ids else None

    stats = {
        "processados": 0,
        "sem_pdf": 0,
        "populados": 0,
        "campos_preenchidos": 0,
    }

    for record in records:
        rid = record.get("id_registro_reajuste", "?")
        if id_filter and rid not in id_filter:
            continue

        stats["processados"] += 1
        fonte = record.get("fonte_documento") or ""
        print(f"\n── {rid} ({record.get('uf')} / {record.get('sindicato')})")

        text, pdf_status = extract_pdf_text(fonte)
        if pdf_status != "ok":
            print(f"   ⚠  PDF indisponível ({pdf_status}): {fonte}")
            stats["sem_pdf"] += 1
            continue

        print(f"   ✓  PDF lido: {fonte}")

        itens = record.get("itens_cct") or {}
        record_changed = False

        for item_key, item in itens.items():
            if not isinstance(item, dict):
                continue
            if item.get("status_parametro") == "valido":
                print(f"     {item_key:<25} ✓ valido — preservado")
                continue

            variations = build_variations(item_key, text, fonte)
            if not variations:
                continue

            updated_item, changed_fields = complement_item(item, variations)

            if changed_fields:
                if not args.dry_run:
                    record["itens_cct"][item_key] = updated_item
                record_changed = True
                stats["campos_preenchidos"] += len(changed_fields)
                for field in changed_fields:
                    count = len(updated_item[field])
                    marker = "[dry-run] " if args.dry_run else ""
                    print(f"     {item_key:<25} ↗ {marker}{field}: {count} subitem(s)")

        if record_changed:
            stats["populados"] += 1

    print("\n" + "=" * 60)
    print(f"Registros processados : {stats['processados']}")
    print(f"  PDFs indisponíveis  : {stats['sem_pdf']}")
    print(f"Registros populados   : {stats['populados']}")
    print(f"Campos preenchidos    : {stats['campos_preenchidos']}")

    if args.dry_run:
        print("\n[dry-run] Nenhuma alteração salva.")
        return

    data["data_geracao"] = datetime.now(timezone.utc).astimezone().isoformat()

    with open(JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"\nArquivo salvo: {JSON_PATH}")

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

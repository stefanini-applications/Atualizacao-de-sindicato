#!/usr/bin/env python3
"""
Lê o Excel revisado (review_decisions_template.xlsx) e aplica as decisões
explícitas do revisor diretamente em data/base_parametros_sindicais.json e
data/base_parametros_sindicais.js, gerando reports/review_decisions_audit.json
com o registro completo de antes/depois de cada alteração.

⚠️  Esta é a PRIMEIRA rotina que altera a base real. Execuções reais são
    irreversíveis; use --dry-run para conferir o impacto antes.

Formato de entrada suportado (XLSX):
  - Formato por-campo: colunas `registro_id`, `campo`, `decisao_final`,
    `valor_revisado`, `observacao_revisor`, `revisor`, `data_revisao`
    (mais quaisquer colunas extras ignoradas).
  - Formato de negócio (template atual): coluna `CODIGO DO SINDICATO` +
    colunas de parâmetros (e.g. "Piso administrativo") + colunas de revisão.
    O script un-pivota usando o inverso de CAMPO_TO_XLSX_COL.

Decisões válidas:
  validar, manter_pendente, rejeitar, marcar_conflito, buscar_fonte

Uso:
    python3 apply_review_decisions.py --decisions reports/review_decisions_template.xlsx
    python3 apply_review_decisions.py --decisions reports/review_decisions_template.xlsx --dry-run
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
BASE_JSON_PATH = os.path.join(REPO_ROOT, "data", "base_parametros_sindicais.json")
BASE_JS_PATH = os.path.join(REPO_ROOT, "data", "base_parametros_sindicais.js")
AUDIT_PATH = os.path.join(REPO_ROOT, "reports", "review_decisions_audit.json")

VALID_DECISIONS = frozenset(
    {"validar", "manter_pendente", "rejeitar", "marcar_conflito", "buscar_fonte"}
)

# Colunas obrigatórias de revisão (sempre requeridas no XLSX — AC1)
REQUIRED_REVIEW_COLS = frozenset(
    {"decisao_final", "valor_revisado", "observacao_revisor", "revisor", "data_revisao"}
)

# Inverso de CAMPO_TO_XLSX_COL (gerado em generate_review_decisions_template.py)
XLSX_COL_TO_CAMPO: dict[str, str] = {
    "Piso administrativo": "piso_salarial",
    "ADICIONAL NOTURNO": "adicional_noturno",
    "VR Remuneração": "auxilio_alimentacao",
    "PLR": "plr",
    "HR SegSex": "hora_extra",
    "Sobreaviso": "sobreaviso",
    "JORNADA DE TRABALHO": "jornada",
}


# ──────────────────────────────────────────────────────────────────────────────
# I/O
# ──────────────────────────────────────────────────────────────────────────────


def load_base(path: str) -> dict:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def save_base_json(data: dict, path: str) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
        fh.write("\n")


def regenerate_js(data: dict, js_path: str) -> None:
    """Regenera o arquivo .js a partir dos dados já carregados em memória."""
    js_content = (
        "// Gerado automaticamente por export_inline_data.py — não editar manualmente.\n"
        "window.BASE_PARAMETROS_SINDICAIS = "
        + json.dumps(data, ensure_ascii=False)
        + ";\n"
    )
    with open(js_path, "w", encoding="utf-8") as fh:
        fh.write(js_content)


def save_audit(records: list[dict], path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(records, fh, ensure_ascii=False, indent=2)
        fh.write("\n")


# ──────────────────────────────────────────────────────────────────────────────
# Leitura do Excel (AC1)
# ──────────────────────────────────────────────────────────────────────────────


def read_xlsx_decisions(path: str) -> list[dict]:
    """
    Lê decisões do XLSX e retorna lista de dicts com campos normalizados.

    Suporta dois layouts:
    1. Por-campo: colunas `registro_id` + `campo` + colunas de revisão.
    2. De negócio: coluna `CODIGO DO SINDICATO` + colunas de parâmetros +
       colunas de revisão — un-pivota por XLSX_COL_TO_CAMPO.

    Levanta ValueError com mensagem descritiva se colunas obrigatórias de
    revisão estiverem ausentes (AC1).
    """
    # Verifica existência antes de tentar importar openpyxl
    if not os.path.exists(path):
        raise FileNotFoundError(f"Arquivo não encontrado: {path}")

    import openpyxl  # import tardio para permitir testes sem openpyxl

    wb = openpyxl.load_workbook(path, data_only=True)
    ws = wb.active
    headers = [cell.value for cell in ws[1]]

    # Valida colunas de revisão obrigatórias (AC1)
    header_set = set(h for h in headers if h is not None)
    missing = REQUIRED_REVIEW_COLS - header_set
    if missing:
        raise ValueError(
            f"Colunas obrigatórias ausentes no Excel: {', '.join(sorted(missing))}"
        )

    # Detecta formato
    if "registro_id" in header_set and "campo" in header_set:
        return _read_per_campo_format(ws, headers)
    elif "CODIGO DO SINDICATO" in header_set:
        return _read_business_format(ws, headers)
    else:
        raise ValueError(
            "Colunas obrigatórias ausentes: `registro_id` e `campo` "
            "(ou `CODIGO DO SINDICATO` para formato de negócio)"
        )


def _normalise_str(val) -> str:
    if val is None:
        return ""
    return str(val).strip()


def _read_per_campo_format(ws, headers: list) -> list[dict]:
    """Formato por-campo: uma linha por (registro_id, campo)."""
    rows = []
    for row in ws.iter_rows(min_row=2, values_only=True):
        if all(v is None for v in row):
            continue
        rec = {headers[i]: row[i] for i in range(len(headers)) if headers[i] is not None}
        rows.append(
            {
                "registro_id": _normalise_str(rec.get("registro_id")),
                "campo": _normalise_str(rec.get("campo")),
                "decisao_final": _normalise_str(rec.get("decisao_final")),
                "valor_revisado": rec.get("valor_revisado"),
                "observacao_revisor": _normalise_str(rec.get("observacao_revisor")),
                "revisor": _normalise_str(rec.get("revisor")),
                "data_revisao": rec.get("data_revisao"),
            }
        )
    return rows


def _read_business_format(ws, headers: list) -> list[dict]:
    """
    Formato de negócio: uma linha por registro.
    Un-pivota via XLSX_COL_TO_CAMPO para gerar uma decisão por campo não vazio.
    """
    rows = []
    for row in ws.iter_rows(min_row=2, values_only=True):
        if all(v is None for v in row):
            continue
        rec = {headers[i]: row[i] for i in range(len(headers)) if headers[i] is not None}

        registro_id = _normalise_str(rec.get("CODIGO DO SINDICATO"))
        if not registro_id:
            continue

        decisao_final = _normalise_str(rec.get("decisao_final"))
        valor_revisado = rec.get("valor_revisado")
        observacao_revisor = _normalise_str(rec.get("observacao_revisor"))
        revisor = _normalise_str(rec.get("revisor"))
        data_revisao = rec.get("data_revisao")

        for xlsx_col, campo in XLSX_COL_TO_CAMPO.items():
            if xlsx_col in rec and rec[xlsx_col] is not None:
                rows.append(
                    {
                        "registro_id": registro_id,
                        "campo": campo,
                        "decisao_final": decisao_final,
                        "valor_revisado": valor_revisado,
                        "observacao_revisor": observacao_revisor,
                        "revisor": revisor,
                        "data_revisao": data_revisao,
                    }
                )
    return rows


# ──────────────────────────────────────────────────────────────────────────────
# Motor de decisões (AC2)
# ──────────────────────────────────────────────────────────────────────────────


def _coerce_valor(valor_revisado, valor_anterior):
    """
    Tenta converter valor_revisado para o mesmo tipo numérico de valor_anterior.

    Regras de detecção de formato numérico:
    - Ambos ponto e vírgula ("1.500,47") → formato BR: ponto=milhar, vírgula=decimal
    - Apenas vírgula ("1500,47")          → vírgula=decimal
    - Apenas ponto ou nenhum ("1500.50")  → ponto=decimal (formato EN padrão)
    """
    if isinstance(valor_revisado, (int, float)):
        return float(valor_revisado) if isinstance(valor_anterior, float) else valor_revisado

    if isinstance(valor_revisado, str):
        s = valor_revisado.strip()
        if "," in s and "." in s:
            # Formato BR: "1.500,47" → remove ponto (milhar), substitui vírgula por ponto
            cleaned = s.replace(".", "").replace(",", ".")
        elif "," in s:
            # Apenas vírgula decimal: "1500,47"
            cleaned = s.replace(",", ".")
        else:
            # Ponto decimal ou número sem separador: "1500.50", "1500"
            cleaned = s

        try:
            as_float = float(cleaned)
            if isinstance(valor_anterior, int) and as_float == int(as_float):
                return int(as_float)
            return as_float
        except ValueError:
            pass

    return valor_revisado


def _normalise_data_revisao(data_revisao) -> str | None:
    if data_revisao is None:
        return None
    if hasattr(data_revisao, "isoformat"):
        return data_revisao.isoformat()
    return str(data_revisao).strip() or None


def apply_decisions(
    base: dict, decisions: list[dict], timestamp: str | None = None
) -> tuple[dict, list[dict]]:
    """
    Aplica as decisões do Excel na base em memória.

    Parâmetros
    ----------
    base      : conteúdo de base_parametros_sindicais.json (modificado in-place)
    decisions : lista de dicts retornada por read_xlsx_decisions()
    timestamp : ISO-8601 UTC para o campo timestamp_execucao (padrão: agora)

    Retorna
    -------
    (base_modificada, registros_de_auditoria)
    """
    if timestamp is None:
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    registros_by_id: dict[str, dict] = {
        r["id_registro_reajuste"]: r for r in base.get("registros", [])
    }

    audit_records: list[dict] = []

    for decision in decisions:
        registro_id = _normalise_str(decision.get("registro_id"))
        campo = _normalise_str(decision.get("campo"))
        decisao_final = _normalise_str(decision.get("decisao_final"))
        valor_revisado = decision.get("valor_revisado")
        observacao_revisor = _normalise_str(decision.get("observacao_revisor"))
        revisor = _normalise_str(decision.get("revisor"))
        data_revisao = _normalise_data_revisao(decision.get("data_revisao"))

        audit: dict = {
            "registro_id": registro_id,
            "campo": campo,
            "decisao_final": decisao_final,
            "status_anterior": None,
            "status_novo": None,
            "valor_anterior": None,
            "valor_novo": None,
            "revisor": revisor,
            "data_revisao": data_revisao,
            "observacao_revisor": observacao_revisor,
            "resultado": None,
            "motivo": None,
            "timestamp_execucao": timestamp,
        }

        # Validação: decisao_final
        if not decisao_final:
            audit["resultado"] = "erro"
            audit["motivo"] = "decisao_final ausente ou vazia"
            audit_records.append(audit)
            continue

        if decisao_final not in VALID_DECISIONS:
            audit["resultado"] = "erro"
            audit["motivo"] = f"decisao_final inválida: '{decisao_final}'"
            audit_records.append(audit)
            continue

        # Validação: registro_id
        if not registro_id or registro_id not in registros_by_id:
            audit["resultado"] = "erro"
            audit["motivo"] = f"registro_id não encontrado na base: '{registro_id}'"
            audit_records.append(audit)
            continue

        registro = registros_by_id[registro_id]
        itens_cct: dict = registro.get("itens_cct", {})

        # Validação: campo
        if not campo or campo not in itens_cct:
            audit["resultado"] = "erro"
            audit["motivo"] = f"campo não encontrado em itens_cct['{registro_id}']: '{campo}'"
            audit_records.append(audit)
            continue

        item: dict = itens_cct[campo]
        status_anterior = item.get("status_parametro")
        valor_anterior = item.get("valor")

        audit["status_anterior"] = status_anterior
        audit["valor_anterior"] = valor_anterior

        # Aplica a decisão
        _apply_single_decision(
            item=item,
            decisao_final=decisao_final,
            valor_revisado=valor_revisado,
            valor_anterior=valor_anterior,
            revisor=revisor,
            data_revisao=data_revisao,
            observacao_revisor=observacao_revisor,
        )

        audit["status_novo"] = item.get("status_parametro")
        audit["valor_novo"] = item.get("valor")
        audit["resultado"] = "aplicado"
        audit_records.append(audit)

    return base, audit_records


def _apply_single_decision(
    item: dict,
    decisao_final: str,
    valor_revisado,
    valor_anterior,
    revisor: str,
    data_revisao,
    observacao_revisor: str,
) -> None:
    """Aplica uma única decisão ao dict de um campo em itens_cct."""

    if decisao_final == "validar":
        item["status_parametro"] = "valido"
        item["validado_por"] = revisor
        item["data_validacao"] = data_revisao
        item["observacao_validacao"] = observacao_revisor

        # Atualiza valor apenas se valor_revisado for diferente do atual
        if valor_revisado is not None and str(valor_revisado).strip() != "":
            coerced = _coerce_valor(valor_revisado, valor_anterior)
            if coerced != valor_anterior:
                item["valor_original_pre_validacao"] = valor_anterior
                item["valor"] = coerced

    elif decisao_final == "manter_pendente":
        item["status_parametro"] = "pendente_revisao"

    elif decisao_final == "rejeitar":
        item["status_parametro"] = "rejeitado"

    elif decisao_final == "marcar_conflito":
        item["status_parametro"] = "conflito"
        # opcoes_identificadas é preservado intacto (AC2 / seção Additional Context)

    elif decisao_final == "buscar_fonte":
        item["status_parametro"] = "pendente_revisao"
        item["acao_recomendada"] = "buscar_fonte"


# ──────────────────────────────────────────────────────────────────────────────
# Sumário de auditoria
# ──────────────────────────────────────────────────────────────────────────────


def _build_summary(audit_records: list[dict]) -> dict[str, int]:
    summary: dict[str, int] = {
        "total_lidas": len(audit_records),
        "validar": 0,
        "manter_pendente": 0,
        "rejeitar": 0,
        "marcar_conflito": 0,
        "buscar_fonte": 0,
        "ignoradas": 0,
        "erro": 0,
    }
    for rec in audit_records:
        if rec["resultado"] == "erro":
            summary["erro"] += 1
        elif rec["resultado"] == "aplicado":
            decisao = rec.get("decisao_final", "")
            if decisao in summary:
                summary[decisao] += 1
        else:
            summary["ignoradas"] += 1
    return summary


def _print_summary(summary: dict[str, int], dry_run: bool) -> None:
    prefix = "⚠️  [DRY-RUN] " if dry_run else ""
    print(f"{prefix}Total de decisões lidas:              {summary['total_lidas']}")
    print(f"{prefix}  → seriam/foram validadas:           {summary['validar']}")
    print(f"{prefix}  → seriam/foram mantidas pendentes:  {summary['manter_pendente']}")
    print(f"{prefix}  → seriam/foram rejeitadas:          {summary['rejeitar']}")
    print(f"{prefix}  → seriam/foram marcadas conflito:   {summary['marcar_conflito']}")
    print(f"{prefix}  → seriam/foram buscar_fonte:        {summary['buscar_fonte']}")
    print(f"{prefix}  → ignoradas:                        {summary['ignoradas']}")
    print(f"{prefix}  → com erro:                         {summary['erro']}")


# ──────────────────────────────────────────────────────────────────────────────
# Ponto de entrada
# ──────────────────────────────────────────────────────────────────────────────


def _parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Aplica decisões humanas do Excel revisado na base sindical com auditoria. "
            "Use --dry-run para conferir o impacto sem alterar arquivos."
        )
    )
    parser.add_argument(
        "--decisions",
        required=True,
        metavar="ARQUIVO.xlsx",
        help="Caminho para o Excel com decisões preenchidas (review_decisions_template.xlsx).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Exibe sumário sem criar ou modificar qualquer arquivo.",
    )
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = _parse_args(argv)

    # ── 1. Leitura do Excel (aborta em caso de falha estrutural — AC1) ──────
    try:
        decisions = read_xlsx_decisions(args.decisions)
    except (FileNotFoundError, ValueError) as exc:
        print(f"❌  {exc}", file=sys.stderr)
        return 1

    # ── 2. Leitura da base ──────────────────────────────────────────────────
    if not os.path.exists(BASE_JSON_PATH):
        print(f"❌  Base não encontrada: {BASE_JSON_PATH}", file=sys.stderr)
        return 1

    base = load_base(BASE_JSON_PATH)

    # ── 3. Aplica decisões em memória e constrói auditoria (AC4) ───────────
    _, audit_records = apply_decisions(base, decisions)
    summary = _build_summary(audit_records)

    # ── 4. Dry-run: exibe sumário e encerra sem tocar arquivos (AC3) ────────
    if args.dry_run:
        print("⚠️  Modo dry-run: nenhum arquivo será criado ou modificado.\n")
        _print_summary(summary, dry_run=True)
        return 0

    # ── 5. Escrita em ordem segura: JSON → JS → auditoria (AC4 / AC5) ──────
    save_base_json(base, BASE_JSON_PATH)
    print(f"✅  Base JSON atualizada: {BASE_JSON_PATH}")

    regenerate_js(base, BASE_JS_PATH)
    print(f"✅  Base JS regenerada:   {BASE_JS_PATH}")

    save_audit(audit_records, AUDIT_PATH)
    print(f"✅  Auditoria persistida: {AUDIT_PATH}")

    print()
    _print_summary(summary, dry_run=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())

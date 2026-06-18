#!/usr/bin/env python3
"""
Aplica decisões humanas do Excel de revisão na base sindical com auditoria completa.

Lê um arquivo Excel (.xlsx) com colunas obrigatórias (registro_id, campo,
decisao_final, valor_revisado, observacao_revisor, revisor, data_revisao) e
aplica as decisões explícitas do revisor diretamente em:
  - data/base_parametros_sindicais.json
  - data/base_parametros_sindicais.js  (regenerado automaticamente)

e gera reports/review_decisions_audit.json com auditoria completa antes/depois.

Ordem de escrita garantida:
  (1) auditoria construída em memória
  (2) base_parametros_sindicais.json salvo atomicamente
  (3) base_parametros_sindicais.js regenerado
  (4) reports/review_decisions_audit.json persistido

⚠️  Com --dry-run nenhum arquivo é criado ou modificado.

Uso:
    python3 apply_review_decisions.py --decisions reports/review_decisions_template.xlsx
    python3 apply_review_decisions.py --decisions reports/review_decisions_template.xlsx --dry-run
"""

import argparse
import json
import os
import sys
import tempfile
from datetime import datetime, timezone

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
BASE_JSON_PATH = os.path.join(REPO_ROOT, "data", "base_parametros_sindicais.json")
BASE_JS_PATH = os.path.join(REPO_ROOT, "data", "base_parametros_sindicais.js")
AUDIT_PATH = os.path.join(REPO_ROOT, "reports", "review_decisions_audit.json")

REQUIRED_COLUMNS = frozenset({
    "registro_id",
    "campo",
    "decisao_final",
    "valor_revisado",
    "observacao_revisor",
    "revisor",
    "data_revisao",
})

VALID_DECISIONS = frozenset({
    "validar",
    "manter_pendente",
    "rejeitar",
    "marcar_conflito",
    "buscar_fonte",
})


# ──────────────────────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────────────────────

def _parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Aplica decisões humanas do Excel de revisão na base sindical "
            "com auditoria completa (PRJ-72)."
        )
    )
    parser.add_argument(
        "--decisions",
        required=True,
        metavar="ARQUIVO.xlsx",
        help="Caminho para o arquivo Excel (.xlsx) com as decisões de revisão.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Exibe sumário no terminal sem criar ou modificar nenhum arquivo.",
    )
    return parser.parse_args(argv)


# ──────────────────────────────────────────────────────────────────────────────
# Leitura do Excel (AC1)
# ──────────────────────────────────────────────────────────────────────────────

def load_excel_decisions(path: str) -> list[dict]:
    """
    Lê o arquivo Excel e retorna lista de dicionários por linha.

    Aborta a execução inteira (sys.exit com código não-zero) se:
    - o arquivo não existir
    - qualquer coluna obrigatória estiver ausente
    """
    try:
        import openpyxl
    except ImportError:
        print("❌  Erro: biblioteca openpyxl não instalada.", file=sys.stderr)
        sys.exit(1)

    if not os.path.exists(path):
        print(f"❌  Arquivo não encontrado: {path}", file=sys.stderr)
        sys.exit(1)

    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb.active

    rows_iter = ws.iter_rows(values_only=True)
    header_row = next(rows_iter, None)
    if header_row is None:
        print("❌  Arquivo Excel vazio ou sem linha de cabeçalho.", file=sys.stderr)
        wb.close()
        sys.exit(1)

    header_normalized = [
        str(c).strip().lower() if c is not None else "" for c in header_row
    ]
    col_index: dict[str, int] = {col: idx for idx, col in enumerate(header_normalized)}

    missing = REQUIRED_COLUMNS - set(col_index.keys())
    if missing:
        missing_str = ", ".join(sorted(missing))
        print(
            f"❌  Colunas obrigatórias ausentes no Excel: {missing_str}",
            file=sys.stderr,
        )
        wb.close()
        sys.exit(1)

    decisions: list[dict] = []
    for raw_row in rows_iter:
        record: dict = {}
        for col, idx in col_index.items():
            val = raw_row[idx] if idx < len(raw_row) else None
            if val is None:
                record[col] = ""
            elif isinstance(val, str):
                record[col] = val.strip()
            else:
                record[col] = str(val).strip()
        decisions.append(record)

    wb.close()
    return decisions


# ──────────────────────────────────────────────────────────────────────────────
# Helpers de base
# ──────────────────────────────────────────────────────────────────────────────

def load_base(path: str) -> dict:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _find_registro(base: dict, registro_id: str) -> dict | None:
    for reg in base.get("registros", []):
        if reg.get("id_registro_reajuste") == registro_id:
            return reg
    return None


def _is_empty(value) -> bool:
    return value is None or (isinstance(value, str) and value.strip() == "")


def _coerce_value(valor_revisado: str, current_value):
    """
    Tenta coagir valor_revisado para o mesmo tipo do valor atual
    (int/float) para comparação e persistência corretas.
    """
    if isinstance(current_value, (int, float)):
        try:
            coerced = float(valor_revisado)
            if coerced == int(coerced) and isinstance(current_value, int):
                return int(coerced)
            return coerced
        except (ValueError, TypeError):
            pass
    return valor_revisado


# ──────────────────────────────────────────────────────────────────────────────
# Motor de aplicação de decisões (AC2)
# ──────────────────────────────────────────────────────────────────────────────

def apply_decision(
    campo_data: dict,
    decisao: str,
    valor_revisado: str,
    revisor: str,
    data_revisao: str,
    observacao_revisor: str,
    timestamp: str,
) -> dict:
    """
    Aplica a decisão ao dict do campo modificando-o in-place.

    Retorna dict com status_anterior, status_novo, valor_anterior, valor_novo.
    """
    status_anterior = campo_data.get("status_parametro")
    valor_anterior = campo_data.get("valor")
    valor_novo = valor_anterior

    if decisao == "validar":
        campo_data["status_parametro"] = "valido"
        campo_data["validado_por"] = revisor
        campo_data["data_validacao"] = data_revisao if data_revisao else timestamp[:10]
        campo_data["observacao_validacao"] = observacao_revisor

        if not _is_empty(valor_revisado):
            coerced = _coerce_value(valor_revisado, valor_anterior)
            if coerced != valor_anterior:
                campo_data["valor_original_pre_validacao"] = valor_anterior
                campo_data["valor"] = coerced
                valor_novo = coerced

    elif decisao == "manter_pendente":
        campo_data["status_parametro"] = "pendente_revisao"

    elif decisao == "rejeitar":
        campo_data["status_parametro"] = "rejeitado"

    elif decisao == "marcar_conflito":
        campo_data["status_parametro"] = "conflito"
        # opcoes_identificadas mantido intacto — não sobrescrever

    elif decisao == "buscar_fonte":
        campo_data["status_parametro"] = "pendente_revisao"
        campo_data["acao_recomendada"] = "buscar_fonte"

    return {
        "status_anterior": status_anterior,
        "status_novo": campo_data.get("status_parametro"),
        "valor_anterior": valor_anterior,
        "valor_novo": valor_novo,
    }


def process_decisions(
    base: dict,
    decisions: list[dict],
    timestamp: str,
) -> tuple[list[dict], dict]:
    """
    Aplica todas as decisões à base (in-place) e constrói a auditoria em memória.

    Erros em linhas individuais não interrompem o processamento das demais.
    Retorna (audit_records, counters).
    """
    counters: dict[str, int] = {
        "total_lidas": len(decisions),
        "validar": 0,
        "manter_pendente": 0,
        "rejeitar": 0,
        "marcar_conflito": 0,
        "buscar_fonte": 0,
        "ignoradas": 0,
        "erro": 0,
    }
    audit_records: list[dict] = []

    for row in decisions:
        registro_id = row.get("registro_id", "").strip()
        campo = row.get("campo", "").strip()
        decisao = row.get("decisao_final", "").strip()
        valor_revisado = row.get("valor_revisado", "")
        observacao_revisor = row.get("observacao_revisor", "")
        revisor = row.get("revisor", "")
        data_revisao = row.get("data_revisao", "")

        audit: dict = {
            "registro_id": registro_id,
            "campo": campo,
            "decisao_final": decisao,
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

        if _is_empty(decisao):
            audit["resultado"] = "ignorada"
            audit["motivo"] = "decisao_final ausente"
            counters["ignoradas"] += 1
            audit_records.append(audit)
            continue

        if decisao not in VALID_DECISIONS:
            audit["resultado"] = "erro"
            audit["motivo"] = f"decisao_final inválida: '{decisao}'"
            counters["erro"] += 1
            audit_records.append(audit)
            continue

        registro = _find_registro(base, registro_id)
        if registro is None:
            audit["resultado"] = "erro"
            audit["motivo"] = f"registro_id não encontrado na base: '{registro_id}'"
            counters["erro"] += 1
            audit_records.append(audit)
            continue

        itens_cct = registro.get("itens_cct") or {}
        if campo not in itens_cct:
            audit["resultado"] = "erro"
            audit["motivo"] = f"campo não encontrado em itens_cct: '{campo}'"
            counters["erro"] += 1
            audit_records.append(audit)
            continue

        campo_data = itens_cct[campo]
        result = apply_decision(
            campo_data=campo_data,
            decisao=decisao,
            valor_revisado=valor_revisado,
            revisor=revisor,
            data_revisao=data_revisao,
            observacao_revisor=observacao_revisor,
            timestamp=timestamp,
        )

        audit["status_anterior"] = result["status_anterior"]
        audit["status_novo"] = result["status_novo"]
        audit["valor_anterior"] = result["valor_anterior"]
        audit["valor_novo"] = result["valor_novo"]
        audit["resultado"] = "aplicado"
        counters[decisao] += 1
        audit_records.append(audit)

    return audit_records, counters


# ──────────────────────────────────────────────────────────────────────────────
# Escrita atômica e regeneração do JS (AC4, AC5)
# ──────────────────────────────────────────────────────────────────────────────

def save_json_atomic(data: dict, path: str) -> None:
    """Salva JSON atomicamente via arquivo temporário + rename."""
    dir_path = os.path.dirname(os.path.abspath(path))
    os.makedirs(dir_path, exist_ok=True)
    tmp_fd, tmp_path = tempfile.mkstemp(dir=dir_path, suffix=".tmp.json")
    try:
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2)
        os.replace(tmp_path, path)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def regenerate_js(json_path: str, js_path: str) -> None:
    """Regenera base_parametros_sindicais.js a partir do JSON (AC5)."""
    with open(json_path, encoding="utf-8") as fh:
        data = json.load(fh)

    js_content = (
        "// Gerado automaticamente por export_inline_data.py — não editar manualmente.\n"
        "window.BASE_PARAMETROS_SINDICAIS = "
        + json.dumps(data, ensure_ascii=False)
        + ";\n"
    )
    with open(js_path, "w", encoding="utf-8") as fh:
        fh.write(js_content)


# ──────────────────────────────────────────────────────────────────────────────
# Dry-run summary (AC3)
# ──────────────────────────────────────────────────────────────────────────────

def print_dry_run_summary(counters: dict) -> None:
    print("⚠️  Modo dry-run: nenhum arquivo foi criado ou modificado.\n")
    print(f"Total de decisões lidas:              {counters['total_lidas']}")
    print(f"  que seriam validadas:                {counters['validar']}")
    print(f"  mantidas pendentes:                  {counters['manter_pendente']}")
    print(f"  rejeitadas:                          {counters['rejeitar']}")
    print(f"  marcadas como conflito:              {counters['marcar_conflito']}")
    print(f"  enviadas para buscar_fonte:          {counters['buscar_fonte']}")
    print(f"  ignoradas (decisao_final ausente):   {counters['ignoradas']}")
    print(f"  com erro:                            {counters['erro']}")


# ──────────────────────────────────────────────────────────────────────────────
# Entrada principal
# ──────────────────────────────────────────────────────────────────────────────

def main(argv=None) -> int:
    args = _parse_args(argv)

    # AC1: leitura e validação do Excel (aborta em caso de falha estrutural)
    decisions = load_excel_decisions(args.decisions)

    if not os.path.exists(BASE_JSON_PATH):
        print(f"❌  Base JSON não encontrada: {BASE_JSON_PATH}", file=sys.stderr)
        return 1

    base = load_base(BASE_JSON_PATH)
    timestamp = datetime.now(timezone.utc).isoformat()

    # AC4: auditoria construída em memória ANTES de qualquer escrita
    audit_records, counters = process_decisions(base, decisions, timestamp)

    if args.dry_run:
        # AC3: dry-run — zero efeitos colaterais
        print_dry_run_summary(counters)
        return 0

    # Ordem de escrita segura (AC4):
    # (1) base JSON, (2) base JS, (3) auditoria
    save_json_atomic(base, BASE_JSON_PATH)
    print(f"✅  Base JSON salva: {BASE_JSON_PATH}")

    regenerate_js(BASE_JSON_PATH, BASE_JS_PATH)
    print(f"✅  Base JS regenerada: {BASE_JS_PATH}")

    audit_data = {
        "timestamp_execucao": timestamp,
        "arquivo_decisoes": str(args.decisions),
        "total_lidas": counters["total_lidas"],
        "resumo": {k: v for k, v in counters.items() if k != "total_lidas"},
        "registros": audit_records,
    }
    os.makedirs(os.path.dirname(AUDIT_PATH), exist_ok=True)
    save_json_atomic(audit_data, AUDIT_PATH)
    print(f"✅  Auditoria salva: {AUDIT_PATH}")

    print(
        f"\nResumo: {counters['validar']} validados, "
        f"{counters['manter_pendente']} mantidos pendentes, "
        f"{counters['rejeitar']} rejeitados, "
        f"{counters['marcar_conflito']} conflitos, "
        f"{counters['buscar_fonte']} buscar_fonte, "
        f"{counters['ignoradas']} ignorados, "
        f"{counters['erro']} erros."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

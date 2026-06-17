#!/usr/bin/env python3
"""
Gera o template CSV pré-preenchido de decisões a partir da fila de revisão
de parâmetros sindicais (PRJ-70).

Lê `reports/parametros_revisao.json` (gerado pelo PRJ-69) e grava
`reports/review_decisions_template.csv` com todos os 22 campos definidos,
incluindo `decisao_sugerida` por regra, `decisao_final` como ponto de partida
editável e `valor_revisado` pré-populado com o valor atual quando disponível.

⚠️  Este script é estritamente operacional — geração de template:
    - Não aplica decisões à base de dados.
    - `data/base_parametros_sindicais.json` e `.js` não são lidos nem escritos.
    - `app.js`, `index.html` e `style.css` não são tocados.

Uso:
    python3 generate_review_decisions_template.py [--dry-run]

Opções:
    --dry-run   Exibe totais no terminal sem criar ou modificar arquivos.
"""

import argparse
import csv
import json
import os
import sys

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
QUEUE_PATH = os.path.join(REPO_ROOT, "reports", "parametros_revisao.json")
REPORTS_DIR = os.path.join(REPO_ROOT, "reports")
OUTPUT_PATH = os.path.join(REPORTS_DIR, "review_decisions_template.csv")

# Ordem exata das 22 colunas (AC1)
CSV_COLUMNS = [
    "registro_id",
    "uf",
    "sindicato",
    "categoria",
    "ano",
    "campo",
    "valor_atual",
    "status_atual",
    "origem",
    "fonte",
    "fonte_textual",
    "data_extracao",
    "observacao",
    "opcoes_identificadas",
    "prioridade_revisao",
    "acao_sugerida",
    "decisao_sugerida",
    "decisao_final",
    "valor_revisado",
    "observacao_revisor",
    "revisor",
    "data_revisao",
]

# Mapeamento acao_sugerida → decisao_sugerida (AC2)
DECISAO_MAP: dict[str, str] = {
    "validar": "validar",
    "revisar_conflito": "marcar_conflito",
    "buscar_fonte": "buscar_fonte",
    "manter_pendente": "manter_pendente",
}

# Sentinelas que representam ausência real de valor (AC3)
_VALOR_AUSENTE = frozenset({"Não identificado", "", None})


# ──────────────────────────────────────────────────────────────────────────────
# Lógica de mapeamento
# ──────────────────────────────────────────────────────────────────────────────

def _map_decisao_sugerida(acao_sugerida: str | None) -> str:
    """Mapeia acao_sugerida para decisao_sugerida conforme AC2."""
    return DECISAO_MAP.get(acao_sugerida or "", "manter_pendente")


def _calc_valor_revisado(valor_atual) -> str:
    """
    Retorna o valor_atual como string quando é um valor real.
    Retorna string vazia quando é nulo, vazio ou 'Não identificado' (AC3).
    """
    if valor_atual is None or valor_atual in _VALOR_AUSENTE:
        return ""
    return str(valor_atual)


def _serialize_opcoes(opcoes) -> str:
    """
    Serializa opcoes_identificadas para string legível no CSV (AC4).
    Listas e objetos são convertidos para JSON; outros tipos ficam como string.
    """
    if opcoes is None:
        return ""
    if isinstance(opcoes, (list, dict)):
        return json.dumps(opcoes, ensure_ascii=False)
    return str(opcoes)


# ──────────────────────────────────────────────────────────────────────────────
# Construção das linhas do template
# ──────────────────────────────────────────────────────────────────────────────

def build_template_rows(itens: list[dict]) -> list[dict]:
    """
    Converte itens da fila em linhas do template CSV.
    Cada item da fila origina exatamente uma linha (AC1).
    """
    rows = []
    for item in itens:
        decisao_sugerida = _map_decisao_sugerida(item.get("acao_sugerida"))
        valor_revisado = _calc_valor_revisado(item.get("valor"))

        row = {
            "registro_id": item.get("registro_id", ""),
            "uf": item.get("uf", ""),
            "sindicato": item.get("sindicato", ""),
            "categoria": item.get("categoria", ""),
            "ano": item.get("ano", ""),
            "campo": item.get("campo", ""),
            "valor_atual": "" if item.get("valor") is None else item.get("valor"),
            "status_atual": item.get("status_parametro", ""),
            "origem": item.get("origem", ""),
            "fonte": item.get("fonte", ""),
            "fonte_textual": item.get("fonte_textual", ""),
            "data_extracao": item.get("data_extracao", ""),
            "observacao": item.get("observacao", ""),
            "opcoes_identificadas": _serialize_opcoes(item.get("opcoes_identificadas")),
            "prioridade_revisao": item.get("prioridade_revisao", ""),
            "acao_sugerida": item.get("acao_sugerida", ""),
            "decisao_sugerida": decisao_sugerida,
            "decisao_final": decisao_sugerida,  # ponto de partida editável (AC2)
            "valor_revisado": valor_revisado,
            "observacao_revisor": "",
            "revisor": "",
            "data_revisao": "",
        }
        rows.append(row)
    return rows


# ──────────────────────────────────────────────────────────────────────────────
# Contagens para dry-run (AC5)
# ──────────────────────────────────────────────────────────────────────────────

def _count_decisoes(rows: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {
        "validar": 0,
        "marcar_conflito": 0,
        "buscar_fonte": 0,
        "manter_pendente": 0,
    }
    for row in rows:
        decisao = row.get("decisao_sugerida", "")
        if decisao in counts:
            counts[decisao] += 1
    return counts


# ──────────────────────────────────────────────────────────────────────────────
# I/O
# ──────────────────────────────────────────────────────────────────────────────

def load_queue(path: str) -> list[dict]:
    """Lê a fila de revisão e retorna a lista de itens."""
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    return data.get("itens", [])


def save_template(rows: list[dict], path: str) -> None:
    """Grava o template CSV em disco."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _print_dry_run_summary(total: int, counts: dict[str, int]) -> None:
    """Exibe o sumário obrigatório do dry-run (AC5)."""
    print(f"Total de itens lidos da fila: {total}")
    print(f"decisao_sugerida = validar: {counts['validar']}")
    print(f"decisao_sugerida = marcar_conflito: {counts['marcar_conflito']}")
    print(f"decisao_sugerida = buscar_fonte: {counts['buscar_fonte']}")
    print(f"decisao_sugerida = manter_pendente: {counts['manter_pendente']}")


# ──────────────────────────────────────────────────────────────────────────────
# Entrada principal
# ──────────────────────────────────────────────────────────────────────────────

def _parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Gera template CSV pré-preenchido de decisões para revisão de parâmetros sindicais (PRJ-70)."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Exibe totais no terminal sem criar ou modificar arquivos.",
    )
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = _parse_args(argv)

    if not os.path.exists(QUEUE_PATH):
        print(f"❌  Arquivo não encontrado: {QUEUE_PATH}", file=sys.stderr)
        return 1

    itens = load_queue(QUEUE_PATH)
    rows = build_template_rows(itens)
    counts = _count_decisoes(rows)

    if args.dry_run:
        print("⚠️  Modo dry-run: nenhum arquivo será criado ou modificado.\n")
        _print_dry_run_summary(len(rows), counts)
    else:
        save_template(rows, OUTPUT_PATH)
        print(f"✅  Template gravado em: {OUTPUT_PATH}")
        print(f"    Total de linhas: {len(rows)}")
        _print_dry_run_summary(len(rows), counts)

    return 0


if __name__ == "__main__":
    sys.exit(main())

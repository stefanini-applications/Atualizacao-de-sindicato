#!/usr/bin/env python3
"""
Gera o template Excel (.xlsx) pré-preenchido de decisões a partir da fila de
revisão de parâmetros sindicais (PRJ-70/PRJ-71).

Lê `reports/parametros_revisao.json` (gerado pelo PRJ-69) e grava:
  - `reports/review_decisions_template.xlsx`  ← entrega operacional principal
  - `reports/review_decisions_template.csv`   ← apoio técnico (mantido)

O Excel inclui as colunas do modelo de negócio (Pricing/RH) seguidas das
colunas operacionais de revisão, com cabeçalho destacado e filtros habilitados.

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

import openpyxl
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
QUEUE_PATH = os.path.join(REPO_ROOT, "reports", "parametros_revisao.json")
REPORTS_DIR = os.path.join(REPO_ROOT, "reports")
OUTPUT_PATH = os.path.join(REPORTS_DIR, "review_decisions_template.csv")
OUTPUT_XLSX_PATH = os.path.join(REPORTS_DIR, "review_decisions_template.xlsx")

# Ordem exata das 22 colunas do CSV (mantido para apoio técnico)
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

# Colunas do modelo de negócio (Pricing/RH) — conforme modelo Excel enviado
XLSX_BUSINESS_COLUMNS = [
    "CODIGO DO SINDICATO",
    "ESTADO/ SINDICATO",
    "SINDICATO",
    "ESTADO",
    "APLICÁVEL Á:",
    "HR SegSex",
    "HR Sabado",
    "HR Domingo",
    "ADICIONAL NOTURNO",
    "SOBREAVISO",
    "JORNADA DE TRABALHO",
    "DATA VIGENCIA PISO",
    "INÍCIO VIGÊNCIA CCT",
    "FIM VIGÊNCIA CCT",
    "REAJUSTE SALARIAL (%)",
    "TECNICO SUPORTE I",
    "TECNICO SUPORTE II",
    "TECNICO SUPORTE III",
    "VR Remuneração",
    "Salário <= 2999,99",
    "Salário >= 3000,00",
    "VR Custo",
    "VT",
    "OUTROS CUSTOS",
    "PLR",
    "ATUALIZAÇÃO",
    "Data piso",
    "Piso administrativo",
]

# Colunas operacionais de revisão — adicionadas ao final
XLSX_REVIEW_COLUMNS = [
    "status_parametro",
    "origem",
    "fonte",
    "fonte_textual",
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

# Todas as colunas do Excel (negócio + revisão)
XLSX_COLUMNS = XLSX_BUSINESS_COLUMNS + XLSX_REVIEW_COLUMNS

# Mapeamento de campo JSON → coluna de negócio no Excel
_CAMPO_TO_XLSX_COL: dict[str, str] = {
    "piso_salarial": "Piso administrativo",
    "adicional_noturno": "ADICIONAL NOTURNO",
    "auxilio_alimentacao": "VR Remuneração",
    "plr": "PLR",
    "hora_extra": "HR SegSex",
    "sobreaviso": "SOBREAVISO",
    "jornada": "JORNADA DE TRABALHO",
}

# Estilos Excel
_HEADER_FILL_BUSINESS = PatternFill("solid", fgColor="1F4E79")   # azul escuro
_HEADER_FILL_REVIEW = PatternFill("solid", fgColor="375623")    # verde escuro
_HEADER_FONT = Font(bold=True, color="FFFFFF", size=10)
_DATA_FONT = Font(size=10)
_WRAP = Alignment(wrap_text=True, vertical="top")

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


def build_xlsx_row(item: dict) -> dict:
    """
    Constrói um dict com todas as colunas do Excel (negócio + revisão) para
    um item da fila de revisão.
    """
    decisao_sugerida = _map_decisao_sugerida(item.get("acao_sugerida"))
    valor_revisado = _calc_valor_revisado(item.get("valor"))
    campo = item.get("campo", "")

    # Linha base com colunas de negócio — a maioria começa vazia
    row: dict = {col: "" for col in XLSX_COLUMNS}

    # Colunas de identificação do sindicato
    row["CODIGO DO SINDICATO"] = item.get("registro_id", "")
    row["ESTADO/ SINDICATO"] = (
        f"{item.get('uf', '')} - {item.get('sindicato', '')}".strip(" -")
    )
    row["SINDICATO"] = item.get("sindicato", "")
    row["ESTADO"] = item.get("uf", "")
    row["APLICÁVEL Á:"] = item.get("categoria", "")

    # Preenche a coluna de negócio correspondente ao campo extraído
    xlsx_col = _CAMPO_TO_XLSX_COL.get(campo)
    if xlsx_col:
        valor = item.get("valor")
        row[xlsx_col] = "" if valor is None else valor

    # Colunas operacionais de revisão
    row["status_parametro"] = item.get("status_parametro", "")
    row["origem"] = item.get("origem") or ""
    row["fonte"] = item.get("fonte") or ""
    row["fonte_textual"] = item.get("fonte_textual") or ""
    row["opcoes_identificadas"] = _serialize_opcoes(item.get("opcoes_identificadas"))
    row["prioridade_revisao"] = item.get("prioridade_revisao", "")
    row["acao_sugerida"] = item.get("acao_sugerida", "")
    row["decisao_sugerida"] = decisao_sugerida
    row["decisao_final"] = decisao_sugerida   # ponto de partida editável
    row["valor_revisado"] = valor_revisado
    row["observacao_revisor"] = ""
    row["revisor"] = ""
    row["data_revisao"] = ""

    return row


def save_xlsx_template(itens: list[dict], path: str) -> None:
    """Grava o template Excel (.xlsx) pré-preenchido em disco."""
    os.makedirs(os.path.dirname(path), exist_ok=True)

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Revisão Sindicatos"

    # ── Cabeçalho ──────────────────────────────────────────────────────────────
    for col_idx, col_name in enumerate(XLSX_COLUMNS, start=1):
        cell = ws.cell(row=1, column=col_idx, value=col_name)
        cell.font = _HEADER_FONT
        cell.alignment = Alignment(wrap_text=True, vertical="center", horizontal="center")
        if col_idx <= len(XLSX_BUSINESS_COLUMNS):
            cell.fill = _HEADER_FILL_BUSINESS
        else:
            cell.fill = _HEADER_FILL_REVIEW

    # ── Dados ──────────────────────────────────────────────────────────────────
    for row_idx, item in enumerate(itens, start=2):
        xlsx_row = build_xlsx_row(item)
        for col_idx, col_name in enumerate(XLSX_COLUMNS, start=1):
            cell = ws.cell(row=row_idx, column=col_idx, value=xlsx_row.get(col_name, ""))
            cell.font = _DATA_FONT
            cell.alignment = _WRAP

    # ── Filtros automáticos e larguras de coluna ────────────────────────────────
    ws.auto_filter.ref = ws.dimensions
    for col_idx, col_name in enumerate(XLSX_COLUMNS, start=1):
        # Largura mínima adaptada ao conteúdo do cabeçalho
        width = max(12, min(len(col_name) + 4, 40))
        ws.column_dimensions[get_column_letter(col_idx)].width = width

    # Altura da linha de cabeçalho
    ws.row_dimensions[1].height = 36

    # Congela a linha de cabeçalho para facilitar a navegação
    ws.freeze_panes = "A2"

    wb.save(path)


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
        description=(
            "Gera template Excel (.xlsx) pré-preenchido de decisões para revisão de "
            "parâmetros sindicais (PRJ-70/PRJ-71)."
        )
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
        # Entrega operacional principal: Excel
        save_xlsx_template(itens, OUTPUT_XLSX_PATH)
        print(f"✅  Template Excel gravado em: {OUTPUT_XLSX_PATH}")
        # Apoio técnico: CSV (mantido da PRJ-70)
        save_template(rows, OUTPUT_PATH)
        print(f"✅  Template CSV gravado em: {OUTPUT_PATH}")
        print(f"    Total de linhas: {len(rows)}")
        _print_dry_run_summary(len(rows), counts)

    return 0


if __name__ == "__main__":
    sys.exit(main())

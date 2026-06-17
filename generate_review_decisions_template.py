#!/usr/bin/env python3
"""
Gera o template Excel (.xlsx) e CSV pré-preenchido de decisões a partir da
fila de revisão de parâmetros sindicais (PRJ-70 / PRJ-71).

Lê `reports/parametros_revisao.json` e grava:
  - `reports/review_decisions_template.xlsx`  ← entrega operacional principal
  - `reports/review_decisions_template.csv`   ← apoio técnico (mantido)

O Excel segue o layout do modelo enviado pelo negócio (PRJ-71), com cabeçalho
destacado, filtros automáticos habilitados e colunas de revisão editáveis.

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
OUTPUT_XLSX_PATH = os.path.join(REPORTS_DIR, "review_decisions_template.xlsx")

# ──────────────────────────────────────────────────────────────────────────────
# Colunas do modelo de negócio (layout Excel — PRJ-71)
# ──────────────────────────────────────────────────────────────────────────────

# Colunas do modelo enviado pelo negócio (ordem exata)
BUSINESS_COLUMNS = [
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

# Colunas operacionais de revisão (acrescentadas após o modelo de negócio)
REVIEW_COLUMNS = [
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

# Cabeçalhos completos do Excel (modelo negócio + revisão)
XLSX_COLUMNS = BUSINESS_COLUMNS + REVIEW_COLUMNS

# Mapeamento: campo do JSON → coluna de negócio correspondente
_CAMPO_TO_BUSINESS_COL: dict[str, str] = {
    "adicional_noturno": "ADICIONAL NOTURNO",
    "sobreaviso": "SOBREAVISO",
    "jornada": "JORNADA DE TRABALHO",
    "piso_salarial": "Piso administrativo",
    "auxilio_alimentacao": "VR Remuneração",
    "plr": "PLR",
    "hora_extra": "HR SegSex",
}

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


def save_xlsx(rows: list[dict], path: str) -> None:
    """
    Grava o template Excel (.xlsx) seguindo o modelo de negócio (PRJ-71).

    Cada item da fila gera uma linha.  As colunas do modelo de negócio são
    preenchidas via mapeamento de campo; as colunas de revisão operacional
    são preenchidas diretamente.  O arquivo vem com filtros automáticos
    habilitados e cabeçalho destacado para uso imediato pelo usuário final.
    """
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font, PatternFill, Alignment
        from openpyxl.utils import get_column_letter
    except ImportError as exc:
        raise ImportError(
            "openpyxl é necessário para gerar o Excel. "
            "Instale com: apt-get install python3-openpyxl"
        ) from exc

    os.makedirs(os.path.dirname(path), exist_ok=True)
    wb = Workbook()
    ws = wb.active
    ws.title = "Revisão Sindicatos"

    # ── Estilos de cabeçalho ──────────────────────────────────────────────────
    header_fill_business = PatternFill(
        start_color="1F4E79", end_color="1F4E79", fill_type="solid"
    )
    header_fill_review = PatternFill(
        start_color="375623", end_color="375623", fill_type="solid"
    )
    header_font = Font(color="FFFFFF", bold=True, size=10)
    center_align = Alignment(horizontal="center", vertical="center", wrap_text=True)

    # ── Escrever cabeçalhos ───────────────────────────────────────────────────
    for col_idx, col_name in enumerate(XLSX_COLUMNS, start=1):
        cell = ws.cell(row=1, column=col_idx, value=col_name)
        cell.font = header_font
        cell.alignment = center_align
        if col_name in BUSINESS_COLUMNS:
            cell.fill = header_fill_business
        else:
            cell.fill = header_fill_review

    # ── Escrever dados ────────────────────────────────────────────────────────
    for row_idx, item in enumerate(rows, start=2):
        # Monta dict completo para a linha (todas as colunas → vazio por padrão)
        row_data: dict[str, object] = {col: "" for col in XLSX_COLUMNS}

        # Preenche colunas de negócio a partir do campo do item
        campo = item.get("campo", "")
        valor_atual = item.get("valor_atual", "")
        if campo in _CAMPO_TO_BUSINESS_COL:
            row_data[_CAMPO_TO_BUSINESS_COL[campo]] = valor_atual

        # Colunas de negócio com mapeamento direto de campos do item
        row_data["CODIGO DO SINDICATO"] = item.get("registro_id", "")
        row_data["ESTADO/ SINDICATO"] = (
            f"{item.get('uf', '')} - {item.get('sindicato', '')}".strip(" -")
        )
        row_data["SINDICATO"] = item.get("sindicato", "")
        row_data["ESTADO"] = item.get("uf", "")
        row_data["APLICÁVEL Á:"] = item.get("categoria", "")
        row_data["ATUALIZAÇÃO"] = item.get("data_extracao", "")
        row_data["Data piso"] = item.get("data_extracao", "")

        # Colunas operacionais de revisão
        row_data["status_parametro"] = item.get("status_atual", "")
        row_data["origem"] = item.get("origem", "")
        row_data["fonte"] = item.get("fonte", "")
        row_data["fonte_textual"] = item.get("fonte_textual", "")
        row_data["opcoes_identificadas"] = item.get("opcoes_identificadas", "")
        row_data["prioridade_revisao"] = item.get("prioridade_revisao", "")
        row_data["acao_sugerida"] = item.get("acao_sugerida", "")
        row_data["decisao_sugerida"] = item.get("decisao_sugerida", "")
        row_data["decisao_final"] = item.get("decisao_final", "")
        row_data["valor_revisado"] = item.get("valor_revisado", "")
        row_data["observacao_revisor"] = item.get("observacao_revisor", "")
        row_data["revisor"] = item.get("revisor", "")
        row_data["data_revisao"] = item.get("data_revisao", "")

        for col_idx, col_name in enumerate(XLSX_COLUMNS, start=1):
            ws.cell(row=row_idx, column=col_idx, value=row_data[col_name])

    # ── Filtros automáticos ───────────────────────────────────────────────────
    last_col_letter = get_column_letter(len(XLSX_COLUMNS))
    ws.auto_filter.ref = f"A1:{last_col_letter}1"

    # ── Larguras de coluna ────────────────────────────────────────────────────
    for col_idx, col_name in enumerate(XLSX_COLUMNS, start=1):
        letter = get_column_letter(col_idx)
        if col_name in ("fonte_textual", "observacao_revisor"):
            ws.column_dimensions[letter].width = 50
        elif col_name in ("SINDICATO", "ESTADO/ SINDICATO", "APLICÁVEL Á:"):
            ws.column_dimensions[letter].width = 30
        elif col_name in ("opcoes_identificadas", "decisao_sugerida", "decisao_final"):
            ws.column_dimensions[letter].width = 22
        else:
            ws.column_dimensions[letter].width = 18
    ws.row_dimensions[1].height = 40

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
        save_xlsx(rows, OUTPUT_XLSX_PATH)
        print(f"✅  Template Excel gravado em: {OUTPUT_XLSX_PATH}")
        print(f"✅  Template CSV gravado em:   {OUTPUT_PATH}")
        print(f"    Total de linhas: {len(rows)}")
        _print_dry_run_summary(len(rows), counts)

    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""
Gera a fila de revisão dos parâmetros sindicais extraídos e enriquecidos
automaticamente (PRJ-69).

Lê `data/base_parametros_sindicais.json`, filtra os campos que exigem
validação humana, calcula prioridade e ação sugerida por item, e grava o
resultado em `reports/parametros_revisao.json`.

⚠️  Este script é estritamente informativo/operacional:
    - Não aprova, não rejeita e não altera nenhum campo da base.
    - `data/base_parametros_sindicais.json` e `.js` nunca são escritos.

Uso:
    python3 generate_review_queue.py [--dry-run]

Opções:
    --dry-run   Exibe a fila no terminal sem criar ou modificar arquivos.
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
JSON_PATH = os.path.join(REPO_ROOT, "data", "base_parametros_sindicais.json")
REPORTS_DIR = os.path.join(REPO_ROOT, "reports")
REPORT_PATH = os.path.join(REPORTS_DIR, "parametros_revisao.json")

# ──────────────────────────────────────────────────────────────────────────────
# Constantes de governança
# ──────────────────────────────────────────────────────────────────────────────

# status_parametro que tornam o campo elegível para a fila
ELIGIBLE_STATUSES: frozenset[str] = frozenset({
    "extraido_para_revisao",
    "pendente_revisao",
    "conflito",
})

# origens que tornam o campo elegível para a fila (mesmo que status seja valido)
ELIGIBLE_ORIGENS: frozenset[str] = frozenset({
    "fonte_oficial_mte",
    "conflito_pdf_mte",
    "nao_identificado_pdf",
    "nao_identificado_pdf_mte",
})

# Campos considerados críticos → prioridade alta quando pendentes ou via MTE
CAMPOS_CRITICOS: frozenset[str] = frozenset({
    "piso_salarial",
    "piso_nacional",
    "piso_tecnico",
    "piso_administrativo",
    "analista_suporte_i",
    "analista_suporte_ii",
    "analista_suporte_iii",
    "vr",
    "va",
    "hora_extra",
    "jornada",
    "adicional_noturno",
})


# ──────────────────────────────────────────────────────────────────────────────
# Lógica de filtragem
# ──────────────────────────────────────────────────────────────────────────────

def _is_eligible(field: dict) -> bool:
    """Retorna True se o campo deve entrar na fila de revisão."""
    status = field.get("status_parametro")
    origem = field.get("origem")
    return status in ELIGIBLE_STATUSES or origem in ELIGIBLE_ORIGENS


# ──────────────────────────────────────────────────────────────────────────────
# Cálculo de prioridade e ação sugerida
# ──────────────────────────────────────────────────────────────────────────────

def _calc_prioridade(campo_nome: str, field: dict) -> str:
    """
    Calcula prioridade_revisao conforme as regras de negócio:
      - conflito → alta
      - campo crítico pendente ou preenchido por MTE → alta
      - extraído com fonte_textual → média
      - demais → baixa
    """
    status = field.get("status_parametro")
    origem = field.get("origem")

    if status == "conflito" or origem == "conflito_pdf_mte":
        return "alta"

    if campo_nome in CAMPOS_CRITICOS:
        if status in {"pendente_revisao", "conflito"} or origem in {
            "fonte_oficial_mte", "nao_identificado_pdf", "nao_identificado_pdf_mte"
        }:
            return "alta"

    if status == "extraido_para_revisao" and field.get("fonte_textual"):
        return "média"

    return "baixa"


def _calc_acao_sugerida(field: dict) -> str:
    """
    Calcula acao_sugerida conforme as regras de negócio:
      - conflito → revisar_conflito
      - pendente / nao_identificado_* → buscar_fonte
      - extraido_para_revisao com fonte_textual → validar
      - sem evidência → manter_pendente
    """
    status = field.get("status_parametro")
    origem = field.get("origem")

    if status == "conflito" or origem == "conflito_pdf_mte":
        return "revisar_conflito"

    if status in {"pendente_revisao"} or origem in {
        "nao_identificado_pdf", "nao_identificado_pdf_mte"
    }:
        return "buscar_fonte"

    if status == "extraido_para_revisao" and field.get("fonte_textual"):
        return "validar"

    return "manter_pendente"


# ──────────────────────────────────────────────────────────────────────────────
# Construção dos itens da fila
# ──────────────────────────────────────────────────────────────────────────────

def _build_item(registro: dict, campo_nome: str, field: dict) -> dict:
    """Constrói um item da fila de revisão a partir de um campo de itens_cct."""
    prioridade = _calc_prioridade(campo_nome, field)
    acao = _calc_acao_sugerida(field)

    return {
        "registro_id": registro.get("id_registro_reajuste"),
        "uf": registro.get("uf"),
        "sindicato": registro.get("sindicato"),
        "categoria": registro.get("categoria"),
        "ano": registro.get("ano_referencia"),
        "campo": campo_nome,
        "valor": field.get("valor"),
        "status_parametro": field.get("status_parametro"),
        "origem": field.get("origem"),
        "fonte": field.get("fonte"),
        "fonte_textual": field.get("fonte_textual"),
        "data_extracao": field.get("data_extracao"),
        "observacao": field.get("observacao"),
        "opcoes_identificadas": field.get("opcoes_identificadas"),
        "prioridade_revisao": prioridade,
        "acao_sugerida": acao,
    }


def build_review_queue(base: dict) -> list[dict]:
    """
    Lê `registros` da base e retorna a lista de itens elegíveis para revisão.
    A base nunca é modificada.
    """
    itens: list[dict] = []
    for registro in base.get("registros", []):
        itens_cct = registro.get("itens_cct") or {}
        for campo_nome, field in itens_cct.items():
            if not isinstance(field, dict):
                continue
            if _is_eligible(field):
                itens.append(_build_item(registro, campo_nome, field))
    return itens


# ──────────────────────────────────────────────────────────────────────────────
# Totais agregados
# ──────────────────────────────────────────────────────────────────────────────

def _build_totals(itens: list[dict]) -> dict:
    """Calcula todos os totais agregados exigidos pelo AC6."""
    total_por_origem: dict[str, int] = {}
    total_por_campo: dict[str, int] = {}
    total_por_uf: dict[str, int] = {}
    total_por_sindicato: dict[str, int] = {}

    total_alta = total_media = total_baixa = 0
    total_conflitos = total_pendentes = total_extraidos = 0

    for item in itens:
        p = item["prioridade_revisao"]
        if p == "alta":
            total_alta += 1
        elif p == "média":
            total_media += 1
        else:
            total_baixa += 1

        st = item["status_parametro"]
        if st == "conflito":
            total_conflitos += 1
        elif st == "pendente_revisao":
            total_pendentes += 1
        elif st == "extraido_para_revisao":
            total_extraidos += 1

        origem = item["origem"] or "desconhecido"
        total_por_origem[origem] = total_por_origem.get(origem, 0) + 1

        campo = item["campo"]
        total_por_campo[campo] = total_por_campo.get(campo, 0) + 1

        uf = item["uf"] or "desconhecido"
        total_por_uf[uf] = total_por_uf.get(uf, 0) + 1

        sindicato = item["sindicato"] or "desconhecido"
        total_por_sindicato[sindicato] = total_por_sindicato.get(sindicato, 0) + 1

    return {
        "total_itens_revisao": len(itens),
        "total_prioridade_alta": total_alta,
        "total_prioridade_media": total_media,
        "total_prioridade_baixa": total_baixa,
        "total_conflitos": total_conflitos,
        "total_pendentes": total_pendentes,
        "total_extraidos_para_revisao": total_extraidos,
        "total_por_origem": total_por_origem,
        "total_por_campo": total_por_campo,
        "total_por_uf": total_por_uf,
        "total_por_sindicato": total_por_sindicato,
    }


# ──────────────────────────────────────────────────────────────────────────────
# Geração do relatório
# ──────────────────────────────────────────────────────────────────────────────

def generate_report(base: dict, dry_run: bool) -> dict:
    """
    Gera o relatório de revisão.
    Retorna o dicionário do relatório (sem gravar em disco quando dry_run=True).
    A base nunca é modificada.
    """
    itens = build_review_queue(base)
    totals = _build_totals(itens)

    report = {
        "data_execucao": datetime.now(tz=timezone.utc).isoformat(),
        "dry_run": dry_run,
        **totals,
        "itens": itens,
    }
    return report


def save_report(report: dict) -> None:
    """Grava o relatório em reports/parametros_revisao.json."""
    os.makedirs(REPORTS_DIR, exist_ok=True)
    with open(REPORT_PATH, "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2)
    print(f"✅  Relatório gravado em: {REPORT_PATH}")
    print(f"    Total de itens para revisão: {report['total_itens_revisao']}")
    print(f"    Prioridade alta: {report['total_prioridade_alta']}")
    print(f"    Prioridade média: {report['total_prioridade_media']}")
    print(f"    Prioridade baixa: {report['total_prioridade_baixa']}")


# ──────────────────────────────────────────────────────────────────────────────
# Entrada principal
# ──────────────────────────────────────────────────────────────────────────────

def _parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Gera fila de revisão dos parâmetros sindicais (PRJ-69)."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Exibe a fila no terminal sem gravar arquivos.",
    )
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = _parse_args(argv)

    if not os.path.exists(JSON_PATH):
        print(f"❌  Arquivo não encontrado: {JSON_PATH}", file=sys.stderr)
        return 1

    with open(JSON_PATH, encoding="utf-8") as fh:
        base = json.load(fh)

    report = generate_report(base, dry_run=args.dry_run)

    if args.dry_run:
        print("⚠️  Modo dry-run: nenhum arquivo será criado ou modificado.\n")
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        save_report(report)

    return 0


if __name__ == "__main__":
    sys.exit(main())

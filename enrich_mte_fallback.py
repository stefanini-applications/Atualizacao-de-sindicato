#!/usr/bin/env python3
"""
Módulo de enriquecimento complementar de campos não identificados no PDF
via fonte oficial do Ministério do Trabalho e Emprego (MTE) — Sistema Mediador.

Este módulo é estritamente aditivo: nenhum componente existente é modificado.
Apenas campos com status_parametro "pendente_revisao" ou origem "nao_identificado_pdf"
são elegíveis. Campos com status_parametro "valido" ou com origem "pdf_cct" e
valor não nulo nunca são sobrescritos.

═══════════════════════════════════════════════════════════════════════════════
PRJ-66 — Associar instrumento oficial MTE aos registros CCT
═══════════════════════════════════════════════════════════════════════════════
Mecanismo operacional alternativo: cada registro CCT/ACT pode receber uma
referência oficial do instrumento MTE via --mte-file (arquivo PDF local) ou
--mte-source (URL/código). A referência é armazenada na seção `fonte_oficial_mte`
de cada registro processado.

Tipos de referência suportados:
  - "arquivo":            arquivo PDF local processado pelo parser MTE independente.
  - "url":                apenas registra a referência; não altera itens_cct.
  - "codigo_instrumento": apenas registra a referência; não altera itens_cct.
  - "manual":             registra metadados do operador; nunca preenche itens_cct
                          sem fonte_textual extraída de arquivo processável.

LIMITAÇÃO TÉCNICA (AC3 / AC7 — PRJ-65, mantida):
  - lookup_mte_instrumento_coletivo() retorna None quando nenhum arquivo é
    fornecido (API pública do Sistema Mediador não disponível).
  - Quando --mte-file é fornecido, o parser independente (parse_mte_instrumento.py)
    é usado para extrair campos com evidência textual rastreável.

Uso:
    python3 enrich_mte_fallback.py [--dry-run] [--ids ID1 ID2 ...]
    python3 enrich_mte_fallback.py --ids REG-SP-SINDPD-2025 --mte-file caminho/instrumento.pdf --dry-run
    python3 enrich_mte_fallback.py --ids REG-SP-SINDPD-2025 --mte-source https://... --mte-tipo url

Opções:
    --dry-run       Exibe o que seria alterado sem gravar arquivos (sempre seguro).
    --ids           Processa apenas os registros com os IDs informados.
    --mte-file      Caminho para o arquivo PDF oficial do instrumento MTE.
    --mte-source    URL ou código do instrumento MTE (referência sem arquivo local).
    --mte-tipo      Tipo de referência: arquivo | url | codigo_instrumento | manual
                    (padrão: "arquivo" quando --mte-file é fornecido, "url" para --mte-source).
═══════════════════════════════════════════════════════════════════════════════
"""

import argparse
import json
import logging
import os
import subprocess
import sys
from datetime import date
from typing import Any

from parse_mte_instrumento import build_fonte_oficial_mte, parse_mte_instrumento

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
JSON_PATH = os.path.join(REPO_ROOT, "data", "base_parametros_sindicais.json")
EXPORT_SCRIPT = os.path.join(REPO_ROOT, "export_inline_data.py")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger("enrich_mte_fallback")

# ──────────────────────────────────────────────────────────────────────────────
# Constantes de governança
# ──────────────────────────────────────────────────────────────────────────────

MTE_FONTE_LABEL = "Sistema Mediador / Ministério do Trabalho e Emprego"

# Campos de itens_cct elegíveis para enriquecimento via MTE.
# Cada entrada: nome_campo → True/False indica elegibilidade para Piso Nacional
ELIGIBLE_FIELDS: dict[str, bool] = {
    "piso_salarial": True,   # elegível para Piso Nacional (apenas tipo geral)
    "adicional_noturno": False,
    "auxilio_alimentacao": False,
    "plr": False,
    "hora_extra": False,
    "sobreaviso": False,
    "jornada": False,
}

# Tipos de piso que NÃO permitem Piso Nacional (são cargos específicos)
PISO_TIPOS_BLOQUEADOS_NACIONAL: frozenset[str] = frozenset({
    "piso_tecnico",
    "piso_administrativo",
    "analista_suporte_i",
    "analista_suporte_ii",
    "analista_suporte_iii",
    "cargo",
    "por_cargo",
})

# Status que indicam campo já preenchido e protegido
PROTECTED_STATUSES: frozenset[str] = frozenset({"valido"})

# Statuses elegíveis para enriquecimento
ENRICHABLE_STATUSES: frozenset[str] = frozenset({
    "pendente_revisao",
    None,
})

# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────


def _today() -> str:
    """Return today's date as YYYY-MM-DD."""
    return date.today().isoformat()


def _is_field_pdf_protected(field: dict) -> bool:
    """
    Return True if field has origem "pdf_cct" AND a non-null value.
    Such fields must never be overwritten, regardless of status_parametro.
    """
    if not isinstance(field, dict):
        return False
    if field.get("origem") != "pdf_cct":
        return False
    valor = field.get("valor")
    percentual = field.get("percentual")
    valor_textual = field.get("valor_textual")
    return any(v is not None for v in (valor, percentual, valor_textual))


def _is_field_valid_protected(field: dict) -> bool:
    """Return True if field has status_parametro == "valido"."""
    if not isinstance(field, dict):
        return False
    return field.get("status_parametro") in PROTECTED_STATUSES


def _is_field_enrichable(field: dict) -> bool:
    """
    Return True if a field is eligible for MTE enrichment.
    A field is enrichable when:
      - It is not protected as valido (status_parametro == "valido")
      - It is not from pdf_cct with a non-null value

    Note: a field may have status_parametro "extraido_para_revisao" and still be
    enrichable when origem is "pdf_cct" but valor/percentual/valor_textual are all
    null (clause located but no value extracted). The protection rules above are
    sufficient — no additional status filter is needed.
    """
    if not isinstance(field, dict):
        return False
    if _is_field_valid_protected(field):
        return False
    if _is_field_pdf_protected(field):
        return False
    return True


def _piso_nacional_eligible(field: dict) -> bool:
    """
    Return True if the piso_salarial field is eligible for Piso Nacional fallback.

    AC1 / AC5: Piso Nacional ONLY applies to piso geral (piso_unico or untyped).
    It must NOT be applied when:
      - field has por_cargo sub-structure (cargo-specific pisos)
      - field tipo indicates a specific cargo
    """
    if not isinstance(field, dict):
        return False
    tipo = field.get("tipo")
    if tipo is not None and tipo not in ("piso_unico", "piso_cct", "piso_salarial"):
        if tipo in PISO_TIPOS_BLOQUEADOS_NACIONAL:
            return False
    if field.get("por_cargo"):
        return False
    return True


# ──────────────────────────────────────────────────────────────────────────────
# Stub / Adapter MTE — preparado para evolução futura
# ──────────────────────────────────────────────────────────────────────────────


def lookup_mte_instrumento_coletivo(
    uf: str,
    sindicato: str,
    categoria: str,
    ano: int,
    cnpj: str | None = None,
    tipo_instrumento: str | None = None,
) -> dict | None:
    """
    Consulta o instrumento coletivo correspondente no Sistema Mediador / MTE.

    LIMITAÇÃO TÉCNICA (PRJ-65 / AC3):
    Não existe API pública estável e documentada para consulta automatizada ao
    Sistema Mediador do MTE na data desta implementação. Esta função registra a
    limitação explicitamente, retorna None e não modifica nenhum dado.

    Quando uma API oficial for disponibilizada, esta função deve ser atualizada
    para realizar a consulta real, mantendo a interface de retorno:
        {
            "numero_registro": str,
            "tipo": str,            # "CCT" | "ACT" | "termo_aditivo"
            "vigencia_inicio": str, # YYYY-MM-DD
            "vigencia_fim": str,    # YYYY-MM-DD
            "url_documento": str | None,
            "campos": {
                "<nome_campo>": {
                    "valor": float | str | None,
                    "percentual": float | None,
                    "fonte_textual": str,   # trecho do instrumento
                }
            }
        }

    Args:
        uf:                Unidade federativa (ex: "SP").
        sindicato:         Nome do sindicato.
        categoria:         Categoria econômica/profissional.
        ano:               Ano de referência da CCT/ACT.
        cnpj:              CNPJ da entidade sindical (opcional).
        tipo_instrumento:  "CCT", "ACT" ou "termo_aditivo" (opcional).

    Returns:
        None — API MTE indisponível.
    """
    logger.warning(
        "MTE API indisponível: consulta automatizada ao Sistema Mediador não é "
        "possível na versão atual (PRJ-65). UF=%s sindicato=%r categoria=%r ano=%s. "
        "Nenhum valor será simulado. Todos os campos elegíveis permanecem como "
        "pendente_revisao.",
        uf,
        sindicato,
        categoria,
        ano,
    )
    return None


# ──────────────────────────────────────────────────────────────────────────────
# Lógica de enriquecimento
# ──────────────────────────────────────────────────────────────────────────────


def _apply_mte_value(field: dict, mte_field_data: dict, campo_nome: str) -> str:
    """
    Apply an MTE value to an enrichable field.

    Handles conflict detection: if field has an existing pdf_cct value that
    differs from the MTE value, registers status "conflito" with opcoes_identificadas.

    Returns the resulting status: "extraido_para_revisao" | "conflito".
    """
    mte_valor = mte_field_data.get("valor")
    mte_percentual = mte_field_data.get("percentual")
    mte_fonte_textual = mte_field_data.get("fonte_textual", "")

    existing_valor = field.get("valor")
    existing_percentual = field.get("percentual")
    existing_origem = field.get("origem")

    # Conflict detection: existing non-null pdf_cct value diverges from MTE
    has_pdf_value = (
        existing_origem == "pdf_cct"
        and any(v is not None for v in (existing_valor, existing_percentual))
    )
    if has_pdf_value:
        pdf_val = existing_valor if existing_valor is not None else existing_percentual
        mte_val = mte_valor if mte_valor is not None else mte_percentual
        if pdf_val != mte_val:
            field["status_parametro"] = "conflito"
            field["origem"] = "conflito_pdf_mte"
            field["opcoes_identificadas"] = [
                {
                    "fonte": "pdf_cct",
                    "valor": pdf_val,
                },
                {
                    "fonte": "fonte_oficial_mte",
                    "valor": mte_val,
                    "fonte_textual": mte_fonte_textual,
                },
            ]
            field["observacao"] = (
                f"Divergência detectada entre PDF e MTE para {campo_nome}. "
                "Revisão manual necessária."
            )
            logger.info(
                "  conflito %s: PDF=%s vs MTE=%s", campo_nome, pdf_val, mte_val
            )
            return "conflito"

    # No conflict: apply MTE value
    if mte_valor is not None:
        field["valor"] = mte_valor
    if mte_percentual is not None:
        field["percentual"] = mte_percentual
    field["status_parametro"] = "extraido_para_revisao"
    field["origem"] = "fonte_oficial_mte"
    field["fonte"] = MTE_FONTE_LABEL
    field["fonte_textual"] = mte_fonte_textual
    field["data_extracao"] = _today()
    field["observacao"] = mte_field_data.get("observacao", "Enriquecido via MTE.")
    logger.info("  preenchido %s via MTE: %s", campo_nome, mte_valor or mte_percentual)
    return "extraido_para_revisao"


def _apply_piso_nacional(field: dict, piso_nacional_valor: float) -> None:
    """
    Apply Piso Nacional as last-resort fallback to an eligible piso_salarial field.

    AC1 / AC5: only for piso_cct / piso_unico (general piso), never for cargos,
    benefícios, adicionais, PLR, hora extra, sobreaviso, or jornada.
    """
    field["valor"] = piso_nacional_valor
    field["status_parametro"] = "extraido_para_revisao"
    field["origem"] = "fonte_oficial_nacional"
    field["fonte"] = "Piso Nacional / Salário Mínimo"
    field["fonte_textual"] = (
        "Piso Nacional aplicado como fallback de último recurso; "
        "campo de piso geral não encontrado no PDF nem no MTE."
    )
    field["data_extracao"] = _today()
    field["observacao"] = (
        "Piso Nacional aplicado como fallback; requer validação com instrumento coletivo vigente."
    )
    logger.info("  piso_salarial preenchido com Piso Nacional: %s", piso_nacional_valor)


def enrich_from_mte_fallback(
    record: dict,
    instrumento_mte: dict | None,
    piso_nacional_valor: float | None = None,
) -> dict:
    """
    Enrich a single record's itens_cct using MTE instrument data and, as last
    resort for piso geral, the Piso Nacional.

    Governance rules (AC1 / AC2 / AC4):
      - Fields with status_parametro "valido" are NEVER overwritten.
      - Fields with origem "pdf_cct" and non-null value are NEVER overwritten
        unless the MTE value diverges, in which case "conflito" is registered.
      - Piso Nacional is ONLY applied to piso_salarial when:
          (a) tipo is null, "piso_unico", or "piso_cct" (no por_cargo structure),
          (b) the field was not filled by PDF or MTE,
          (c) piso_nacional_valor is provided.

    Args:
        record:              A single record dict from base_parametros_sindicais.json.
        instrumento_mte:     Result of lookup_mte_instrumento_coletivo(), or None.
        piso_nacional_valor: Piso Nacional value for last-resort fallback, or None.

    Returns:
        A metrics dict:
            {
                "preenchidos_mte": int,
                "pendentes": int,
                "conflitos": int,
                "preenchidos_piso_nacional": int,
            }
    """
    metrics = {
        "preenchidos_mte": 0,
        "pendentes": 0,
        "conflitos": 0,
        "preenchidos_piso_nacional": 0,
    }

    itens = record.get("itens_cct")
    if not isinstance(itens, dict):
        return metrics

    mte_campos: dict[str, Any] = {}
    if instrumento_mte and isinstance(instrumento_mte.get("campos"), dict):
        mte_campos = instrumento_mte["campos"]

    for campo_nome, piso_nacional_ok in ELIGIBLE_FIELDS.items():
        field = itens.get(campo_nome)
        if not isinstance(field, dict):
            continue

        if _is_field_valid_protected(field):
            continue

        if _is_field_pdf_protected(field):
            # Has pdf_cct value — only process if MTE conflicts
            if campo_nome in mte_campos:
                result = _apply_mte_value(field, mte_campos[campo_nome], campo_nome)
                if result == "conflito":
                    metrics["conflitos"] += 1
                elif result == "extraido_para_revisao":
                    metrics["preenchidos_mte"] += 1
            continue

        if not _is_field_enrichable(field):
            continue

        # Try MTE enrichment
        if campo_nome in mte_campos:
            result = _apply_mte_value(field, mte_campos[campo_nome], campo_nome)
            if result == "conflito":
                metrics["conflitos"] += 1
            elif result == "extraido_para_revisao":
                metrics["preenchidos_mte"] += 1
            continue

        # MTE did not supply this field — try Piso Nacional for eligible piso
        if (
            piso_nacional_ok
            and piso_nacional_valor is not None
            and campo_nome == "piso_salarial"
            and _piso_nacional_eligible(field)
        ):
            _apply_piso_nacional(field, piso_nacional_valor)
            metrics["preenchidos_piso_nacional"] += 1
            continue

        # Field remains as pendente_revisao
        metrics["pendentes"] += 1

    return metrics


# ──────────────────────────────────────────────────────────────────────────────
# Persistência
# ──────────────────────────────────────────────────────────────────────────────


def _save_json(data: dict, json_path: str) -> None:
    """Write updated JSON to disk."""
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    logger.info("JSON gravado: %s", json_path)


def _export_js(export_script: str) -> None:
    """Invoke export_inline_data.py to regenerate the .js file."""
    try:
        result = subprocess.run(
            [sys.executable, export_script],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            logger.info("JS exportado: %s", result.stdout.strip())
        else:
            logger.error("Erro ao exportar JS: %s", result.stderr.strip())
    except Exception as exc:  # noqa: BLE001
        logger.error("Falha ao invocar export_inline_data.py: %s", exc)


# ──────────────────────────────────────────────────────────────────────────────
# Rotina principal de enriquecimento
# ──────────────────────────────────────────────────────────────────────────────


def run_enrichment(
    json_path: str = JSON_PATH,
    dry_run: bool = False,
    ids: list[str] | None = None,
    piso_nacional_valor: float | None = None,
    mte_file: str | None = None,
    mte_source: str | None = None,
    mte_tipo: str | None = None,
) -> dict:
    """
    Main enrichment routine.

    Loads base_parametros_sindicais.json, obtains MTE instrument data (via
    --mte-file parser, --mte-source reference, or the API stub), applies
    enrichment rules, and saves the result only when real data is found.

    PRJ-66 additions:
      - mte_file:   path to a local MTE PDF → parsed by parse_mte_instrumento()
                    independently of the CCT PDF pipeline.
      - mte_source: URL or instrument code registered in fonte_oficial_mte without
                    processing itens_cct (AC4).
      - mte_tipo:   reference type override ("arquivo", "url",
                    "codigo_instrumento", "manual").

    AC3: If no MTE data is found AND Piso Nacional is not provided, the
    JSON/JS files are NOT modified.

    AC5: Returns a comprehensive metrics dict including json_js_atualizado flag.

    Args:
        json_path:           Path to base_parametros_sindicais.json.
        dry_run:             If True, do not write any files.
        ids:                 If provided, process only records with these IDs.
        piso_nacional_valor: Piso Nacional value for last-resort fallback.
        mte_file:            Path to local MTE instrument PDF (AC2 / AC7).
        mte_source:          URL or instrument code for reference registration (AC4).
        mte_tipo:            Reference type override.

    Returns:
        Metrics dict with per-run totals and per-record breakdown.
    """
    logger.info("═══════════════════════════════════════════════════════")
    logger.info("Iniciando rotina de enriquecimento MTE (PRJ-66)")
    logger.info("dry_run=%s  ids=%s", dry_run, ids)
    if mte_file:
        logger.info("mte_file=%s", mte_file)
    if mte_source:
        logger.info("mte_source=%s", mte_source)
    logger.info("═══════════════════════════════════════════════════════")

    # ── Resolve tipo_referencia ───────────────────────────────────────────────
    if mte_tipo is None:
        if mte_file:
            mte_tipo = "arquivo"
        elif mte_source:
            # Heuristic: if it looks like a URL use "url", else "codigo_instrumento"
            mte_tipo = "url" if (mte_source.startswith("http://") or mte_source.startswith("https://")) else "codigo_instrumento"
        else:
            mte_tipo = "arquivo"  # default; lookup_mte_instrumento_coletivo stub used

    # ── Parse MTE instrument once (shared across all filtered records) ────────
    instrumento_mte_from_file: dict | None = None
    if mte_file or mte_source:
        instrumento_mte_from_file = parse_mte_instrumento(
            file_path=mte_file,
            tipo_referencia=mte_tipo,
            url=mte_source if mte_tipo == "url" else None,
            codigo_instrumento=mte_source if mte_tipo == "codigo_instrumento" else None,
        )

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    records = data.get("registros", [])
    id_filter = set(ids) if ids else None

    total_metrics = {
        "preenchidos_mte": 0,
        "pendentes": 0,
        "conflitos": 0,
        "preenchidos_piso_nacional": 0,
        "registros_processados": 0,
        "registros_com_dados_reais": 0,
        "instrumentos_mte_localizados": 0,
        "instrumentos_mte_nao_localizados": 0,
        "api_mte_disponivel": False,
        "json_js_atualizado": False,
    }
    per_record: list[dict] = []
    any_real_data = False

    for record in records:
        rid = record.get("id_registro_reajuste", "?")
        if id_filter and rid not in id_filter:
            continue

        total_metrics["registros_processados"] += 1
        logger.info("── %s (%s / %s)", rid, record.get("uf"), record.get("sindicato"))

        # ── Determine instrument source for this record ───────────────────────
        if instrumento_mte_from_file is not None:
            # Provided via --mte-file / --mte-source
            instrumento = instrumento_mte_from_file
            total_metrics["api_mte_disponivel"] = True
        else:
            # Fallback: API stub (currently returns None — AC3 / PRJ-65)
            instrumento = lookup_mte_instrumento_coletivo(
                uf=record.get("uf", ""),
                sindicato=record.get("sindicato", ""),
                categoria=record.get("categoria", ""),
                ano=record.get("ano_referencia", 0),
                tipo_instrumento="CCT",
            )
            if instrumento is not None:
                total_metrics["api_mte_disponivel"] = True

        # ── Track MTE localizado/nao_localizado (AC5) ─────────────────────────
        if instrumento is not None:
            total_metrics["instrumentos_mte_localizados"] += 1
        else:
            total_metrics["instrumentos_mte_nao_localizados"] += 1

        # ── Store fonte_oficial_mte in record (AC1 / AC2 / AC4 / AC6) ─────────
        arquivo_origem = os.path.basename(mte_file) if mte_file else None
        fonte_oficial = build_fonte_oficial_mte(
            tipo_referencia=mte_tipo,
            instrumento=instrumento,
            arquivo_origem=arquivo_origem,
            url=mte_source if mte_tipo == "url" else None,
            codigo_instrumento=mte_source if mte_tipo == "codigo_instrumento" else None,
        )
        record["fonte_oficial_mte"] = fonte_oficial

        # ── Enrich itens_cct (skipped for url/codigo_instrumento/manual) ──────
        # AC4 / AC6: only "arquivo" type with non-empty campos enriches itens_cct
        instrumento_para_enriquecer = instrumento
        if mte_tipo in ("url", "codigo_instrumento", "manual"):
            instrumento_para_enriquecer = None

        rec_metrics = enrich_from_mte_fallback(
            record=record,
            instrumento_mte=instrumento_para_enriquecer,
            piso_nacional_valor=piso_nacional_valor,
        )
        per_record.append({"id": rid, **rec_metrics})

        for key in ("preenchidos_mte", "pendentes", "conflitos", "preenchidos_piso_nacional"):
            total_metrics[key] += rec_metrics[key]

        if rec_metrics["preenchidos_mte"] > 0 or rec_metrics["preenchidos_piso_nacional"] > 0:
            total_metrics["registros_com_dados_reais"] += 1
            any_real_data = True
        elif mte_tipo in ("url", "codigo_instrumento", "manual") and instrumento is not None:
            # Reference was registered in fonte_oficial_mte — still counts as real data
            # for persistence when the record was updated (fonte_oficial_mte added).
            any_real_data = True

    total_metrics["per_record"] = per_record

    # ── Report ────────────────────────────────────────────────────────────────
    _print_metrics_report(total_metrics)

    # ── Persistence: only when real data was found (AC3 / AC5) ────────────────
    if any_real_data and not dry_run:
        logger.info("Dados reais encontrados — gravando base.")
        _save_json(data, json_path)
        _export_js(EXPORT_SCRIPT)
        total_metrics["json_js_atualizado"] = True
    elif any_real_data and dry_run:
        logger.info("[dry-run] Dados reais encontrados — nenhum arquivo gravado.")
    else:
        logger.info(
            "Nenhum dado real encontrado via MTE ou Piso Nacional. "
            "base_parametros_sindicais.json e .js NÃO foram modificados. "
            "Nenhum valor foi simulado."
        )

    return total_metrics


def _print_metrics_report(metrics: dict) -> None:
    """Print AC5 (PRJ-66) mandatory execution metrics report."""
    sep = "═" * 60
    logger.info(sep)
    logger.info("RELATÓRIO DE ENRIQUECIMENTO MTE — PRJ-66")
    logger.info(sep)
    logger.info("  Registros processados:                 %d", metrics["registros_processados"])
    logger.info(
        "  Instrumentos MTE localizados:          %d",
        metrics.get("instrumentos_mte_localizados", 0),
    )
    logger.info(
        "  Instrumentos MTE não localizados:      %d",
        metrics.get("instrumentos_mte_nao_localizados", 0),
    )
    logger.info(sep)
    logger.info("  Campos preenchidos via MTE:            %d", metrics["preenchidos_mte"])
    logger.info("  Campos mantidos como pendente:         %d", metrics["pendentes"])
    logger.info("  Campos marcados como conflito:         %d", metrics["conflitos"])
    logger.info("  Campos preenchidos (Piso Nacional):    %d", metrics["preenchidos_piso_nacional"])
    logger.info(sep)
    json_js_str = "sim" if metrics.get("json_js_atualizado") else "não"
    logger.info("  Arquivos JSON/JS atualizados:          %s", json_js_str)
    logger.info(sep)
    if not metrics.get("api_mte_disponivel") and metrics["preenchidos_piso_nacional"] == 0:
        logger.info(
            "  DECLARAÇÃO: API MTE indisponível. Nenhum valor simulado. "
            "base_parametros_sindicais.json e .js NÃO modificados."
        )
    logger.info(sep)


# ──────────────────────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Exibe o que seria alterado sem gravar arquivos.",
    )
    parser.add_argument(
        "--ids",
        nargs="+",
        metavar="ID",
        help="Processa apenas os registros com os IDs informados.",
    )
    parser.add_argument(
        "--mte-file",
        metavar="CAMINHO",
        help=(
            "Caminho para o arquivo PDF oficial do instrumento MTE. "
            "Processado pelo parser independente (parse_mte_instrumento.py)."
        ),
    )
    parser.add_argument(
        "--mte-source",
        metavar="URL_OU_CODIGO",
        help=(
            "URL ou código do instrumento MTE para registro em fonte_oficial_mte "
            "sem processamento de itens_cct (AC4)."
        ),
    )
    parser.add_argument(
        "--mte-tipo",
        metavar="TIPO",
        choices=("arquivo", "url", "codigo_instrumento", "manual"),
        help=(
            "Tipo de referência MTE: arquivo | url | codigo_instrumento | manual. "
            "Padrão: 'arquivo' quando --mte-file é fornecido; 'url' para --mte-source "
            "começando com http(s)://."
        ),
    )
    args = parser.parse_args()

    metrics = run_enrichment(
        json_path=JSON_PATH,
        dry_run=args.dry_run,
        ids=args.ids,
        mte_file=args.mte_file,
        mte_source=args.mte_source,
        mte_tipo=args.mte_tipo,
    )

    # Exit code: 0 if all went well (even with zero enrichments)
    sys.exit(0)


if __name__ == "__main__":
    main()

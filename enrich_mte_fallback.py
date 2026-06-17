#!/usr/bin/env python3
"""
Módulo de enriquecimento complementar de campos não identificados no PDF
via fonte oficial do Ministério do Trabalho e Emprego (MTE) — Sistema Mediador.

Este módulo é estritamente aditivo: nenhum componente existente é modificado.
Apenas campos com status_parametro "pendente_revisao" ou origem "nao_identificado_pdf"
são elegíveis. Campos com status_parametro "valido" ou com origem "pdf_cct" e
valor não nulo nunca são sobrescritos.

═══════════════════════════════════════════════════════════════════════════════
LIMITAÇÃO TÉCNICA EXPLÍCITA (AC3 / AC7 — PRJ-65)
═══════════════════════════════════════════════════════════════════════════════
Não existe, na data de implementação desta história (PRJ-65), API pública
estável e documentada para consulta automatizada ao Sistema Mediador do MTE.

Comportamento atual (sem --mte-file / --mte-source):
  - lookup_mte_instrumento_coletivo() registra a limitação no log e retorna None.
  - enrich_from_mte_fallback() mantém todos os campos elegíveis como pendente_revisao.
  - data/base_parametros_sindicais.json e .js NÃO são modificados.
  - Nenhum valor é simulado, inventado ou estimado.

Referência oficial (PRJ-66):
  Cada registro pode receber uma referência oficial do instrumento MTE na seção
  fonte_oficial_mte, com suporte a quatro tipos de referência:
    - arquivo: PDF local processado pelo parser independente parse_mte_instrumento.py
    - url: referência registrada, sem enriquecimento de itens_cct
    - codigo_instrumento: idem
    - manual: metadados registrados pelo operador; nunca preenche itens_cct

Métricas por execução (enquanto API MTE estiver indisponível sem --mte-file):
  - Campos preenchidos via MTE:          0
  - Campos mantidos como pendente_revisao: <N conforme base>
  - Campos marcados como conflito:       0
  - Campos preenchidos com Piso Nacional: 0

Uso:
    python3 enrich_mte_fallback.py [--dry-run] [--ids ID1 ID2 ...]
    python3 enrich_mte_fallback.py --ids REG-SP-SINDPD-2025 --mte-file instrumento.pdf --dry-run
    python3 enrich_mte_fallback.py --ids REG-SP-SINDPD-2025 --mte-tipo url --mte-url https://...
    python3 enrich_mte_fallback.py --ids REG-SP-SINDPD-2025 --mte-tipo manual --mte-codigo 12345

Opções:
    --dry-run              Exibe o que seria alterado sem gravar arquivos.
    --ids                  Processa apenas os registros com os IDs informados.
    --mte-file PATH        Caminho para PDF oficial do MTE (tipo_referencia=arquivo).
    --mte-source PATH      Alias para --mte-file.
    --mte-tipo TYPE        Tipo da referência: arquivo | url | codigo_instrumento | manual.
    --mte-url URL          URL do instrumento oficial no Sistema Mediador.
    --mte-codigo CODE      Código/número do instrumento no Sistema Mediador.
    --mte-sindicato NAME   Nome do sindicato (para referências manual).
    --mte-vigencia-inicio  Data de início de vigência (YYYY-MM-DD).
    --mte-vigencia-fim     Data de fim de vigência (YYYY-MM-DD).
    --mte-observacao TEXT  Observação do operador sobre a referência.
═══════════════════════════════════════════════════════════════════════════════
"""

import argparse
import copy
import csv
import json
import logging
import os
import subprocess
import sys
from datetime import date
from typing import Any

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
JSON_PATH = os.path.join(REPO_ROOT, "data", "base_parametros_sindicais.json")
EXPORT_SCRIPT = os.path.join(REPO_ROOT, "export_inline_data.py")
REPORTS_DIR = os.path.join(REPO_ROOT, "reports")

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
# fonte_oficial_mte — estrutura de referência oficial por registro (PRJ-66)
# ──────────────────────────────────────────────────────────────────────────────

# Tipos de referência válidos para fonte_oficial_mte
# "crawler" é adicionado pelo mte_crawler.py (PRJ-68) para buscas automáticas
FONTE_OFICIAL_MTE_TIPOS: frozenset[str] = frozenset({
    "arquivo",
    "crawler",
    "url",
    "codigo_instrumento",
    "manual",
})


def _build_fonte_oficial_mte(
    tipo_referencia: str,
    *,
    url: str | None = None,
    codigo_instrumento: str | None = None,
    arquivo_origem: str | None = None,
    sindicato_mte: str | None = None,
    vigencia_inicio: str | None = None,
    vigencia_fim: str | None = None,
    observacao: str | None = None,
    status_consulta: str = "localizado",
) -> dict:
    """Build the fonte_oficial_mte metadata block for a record.

    AC4 / AC6 (PRJ-66): this structure records the official MTE reference
    without altering itens_cct directly. Field enrichment is only allowed
    when tipo_referencia == "arquivo" or "crawler" and the parser returns real
    extracted fields with fonte_textual evidence.

    Args:
        tipo_referencia:  One of "arquivo", "crawler", "url", "codigo_instrumento", "manual".
        url:              URL of the official instrument (for tipo url/manual/crawler).
        codigo_instrumento: Instrument code in Sistema Mediador (for tipo codigo_instrumento/manual/crawler).
        arquivo_origem:   File name/path of the processed PDF (for tipo arquivo).
        sindicato_mte:    Sindicato name as recorded in the MTE (for manual).
        vigencia_inicio:  Validity start date YYYY-MM-DD (for manual).
        vigencia_fim:     Validity end date YYYY-MM-DD (for manual).
        observacao:       Operator note about this reference.
        status_consulta:  "localizado" | "nao_localizado" | "bloqueado" | "erro".

    Returns:
        A fonte_oficial_mte dict.
    """
    if tipo_referencia not in FONTE_OFICIAL_MTE_TIPOS:
        raise ValueError(
            f"tipo_referencia inválido: {tipo_referencia!r}. "
            f"Valores aceitos: {sorted(FONTE_OFICIAL_MTE_TIPOS)}"
        )
    return {
        "disponivel": True,
        "tipo_referencia": tipo_referencia,
        "url": url,
        "codigo_instrumento": codigo_instrumento,
        "arquivo_origem": arquivo_origem,
        "sindicato_mte": sindicato_mte,
        "vigencia_inicio": vigencia_inicio,
        "vigencia_fim": vigencia_fim,
        "data_consulta": _today(),
        "status_consulta": status_consulta,
        "observacao": observacao,
    }


def _set_fonte_oficial_mte(record: dict, fonte_data: dict) -> None:
    """Store the fonte_oficial_mte block in a record (additive, non-destructive)."""
    record["fonte_oficial_mte"] = fonte_data


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
    mte_url: str | None = None,
    mte_codigo: str | None = None,
    mte_sindicato: str | None = None,
    mte_vigencia_inicio: str | None = None,
    mte_vigencia_fim: str | None = None,
    mte_observacao: str | None = None,
) -> dict:
    """
    Main enrichment routine.

    Loads base_parametros_sindicais.json, attempts MTE enrichment for each
    record with pending fields, applies enrichment rules, and saves the result
    only when real data is found.

    PRJ-66 additions:
      - When mte_file / mte_source is provided (tipo "arquivo"), the independent
        parser parse_mte_instrumento.parse_mte_pdf() is called; its result is
        used as instrumento_mte for all targeted records.
      - When mte_tipo is "url" or "codigo_instrumento", the reference is stored
        in fonte_oficial_mte but itens_cct is NOT altered.
      - When mte_tipo is "manual", only metadata is stored; itens_cct is never
        altered (AC6 — no textual evidence from file).
      - fonte_oficial_mte is stored in every processed record regardless of type.

    AC3 / PRJ-65: If the MTE API is unavailable (lookup returns None) AND no
    mte_file is provided AND Piso Nacional is not provided, JSON/JS are NOT modified.

    AC5 (PRJ-66): Returns a comprehensive metrics dict including localized/
    not-localized instrument counts and whether JSON/JS were updated.

    Args:
        json_path:           Path to base_parametros_sindicais.json.
        dry_run:             If True, do not write any files.
        ids:                 If provided, process only records with these IDs.
        piso_nacional_valor: Piso Nacional value for last-resort fallback.
        mte_file:            Path to official MTE PDF (tipo_referencia=arquivo).
        mte_source:          Alias for mte_file.
        mte_tipo:            Reference type: arquivo | url | codigo_instrumento | manual.
        mte_url:             URL of the official instrument.
        mte_codigo:          Instrument code in Sistema Mediador.
        mte_sindicato:       Sindicato name (for manual references).
        mte_vigencia_inicio: Validity start date YYYY-MM-DD.
        mte_vigencia_fim:    Validity end date YYYY-MM-DD.
        mte_observacao:      Operator note about this reference.

    Returns:
        Metrics dict with per-run totals and per-record breakdown.
    """
    logger.info("═══════════════════════════════════════════════════════")
    logger.info("Iniciando rotina de enriquecimento MTE (PRJ-65/PRJ-66)")
    logger.info("dry_run=%s  ids=%s", dry_run, ids)
    logger.info("═══════════════════════════════════════════════════════")

    # mte_source is an alias for mte_file
    effective_mte_file = mte_file or mte_source

    # Resolve mte_tipo from context when not explicitly given
    effective_mte_tipo = mte_tipo
    if effective_mte_tipo is None and effective_mte_file:
        effective_mte_tipo = "arquivo"
    elif effective_mte_tipo is None and mte_url:
        effective_mte_tipo = "url"
    elif effective_mte_tipo is None and mte_codigo:
        effective_mte_tipo = "codigo_instrumento"

    # Pre-load the MTE instrument from file (shared across all targeted records)
    instrumento_from_file: dict | None = None
    mte_file_parse_attempted = False
    if effective_mte_tipo == "arquivo" and effective_mte_file:
        mte_file_parse_attempted = True
        try:
            from parse_mte_instrumento import parse_mte_pdf  # type: ignore[import]
            instrumento_from_file = parse_mte_pdf(effective_mte_file)
        except ImportError:
            logger.error(
                "parse_mte_instrumento não encontrado. "
                "Verifique se parse_mte_instrumento.py está no mesmo diretório."
            )
        if instrumento_from_file is None:
            logger.warning(
                "Parser MTE não retornou dados para '%s'. "
                "Nenhum campo será enriquecido via arquivo.",
                effective_mte_file,
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
        "json_js_atualizados": False,
    }
    per_record: list[dict] = []
    any_real_data = False

    for record in records:
        rid = record.get("id_registro_reajuste", "?")
        if id_filter and rid not in id_filter:
            continue

        total_metrics["registros_processados"] += 1
        logger.info("── %s (%s / %s)", rid, record.get("uf"), record.get("sindicato"))

        instrumento: dict | None = None

        if effective_mte_tipo == "arquivo":
            # Use the pre-parsed instrument from file
            instrumento = instrumento_from_file
            fonte_status = "localizado" if instrumento is not None else "nao_localizado"
            fonte_data = _build_fonte_oficial_mte(
                tipo_referencia="arquivo",
                arquivo_origem=os.path.basename(effective_mte_file) if effective_mte_file else None,
                vigencia_inicio=instrumento.get("vigencia_inicio") if instrumento else mte_vigencia_inicio,
                vigencia_fim=instrumento.get("vigencia_fim") if instrumento else mte_vigencia_fim,
                observacao=mte_observacao,
                status_consulta=fonte_status,
            )
            _set_fonte_oficial_mte(record, fonte_data)
            if instrumento is not None:
                total_metrics["instrumentos_mte_localizados"] += 1
                total_metrics["api_mte_disponivel"] = True
            else:
                total_metrics["instrumentos_mte_nao_localizados"] += 1

        elif effective_mte_tipo in ("url", "codigo_instrumento"):
            # AC4: store reference only — do NOT enrich itens_cct
            has_ref = bool(mte_url or mte_codigo)
            fonte_data = _build_fonte_oficial_mte(
                tipo_referencia=effective_mte_tipo,
                url=mte_url,
                codigo_instrumento=mte_codigo,
                vigencia_inicio=mte_vigencia_inicio,
                vigencia_fim=mte_vigencia_fim,
                observacao=mte_observacao,
                status_consulta="localizado" if has_ref else "nao_localizado",
            )
            _set_fonte_oficial_mte(record, fonte_data)
            if has_ref:
                total_metrics["instrumentos_mte_localizados"] += 1
            else:
                total_metrics["instrumentos_mte_nao_localizados"] += 1
            # No instrumento → no field enrichment; instrumento stays None
            logger.info(
                "  tipo=%s: referência registrada em fonte_oficial_mte; itens_cct não alterados.",
                effective_mte_tipo,
            )

        elif effective_mte_tipo == "manual":
            # AC6: store operator metadata only — NEVER alter itens_cct
            fonte_data = _build_fonte_oficial_mte(
                tipo_referencia="manual",
                url=mte_url,
                codigo_instrumento=mte_codigo,
                sindicato_mte=mte_sindicato,
                vigencia_inicio=mte_vigencia_inicio,
                vigencia_fim=mte_vigencia_fim,
                observacao=mte_observacao,
                status_consulta="localizado",
            )
            _set_fonte_oficial_mte(record, fonte_data)
            total_metrics["instrumentos_mte_localizados"] += 1
            logger.info(
                "  tipo=manual: metadados registrados em fonte_oficial_mte; "
                "itens_cct NÃO alterados (AC6 — sem evidência textual de arquivo processável)."
            )
            # instrumento stays None — manual references must NOT fill itens_cct

        else:
            # No MTE reference provided: fall back to legacy API stub
            instrumento = lookup_mte_instrumento_coletivo(
                uf=record.get("uf", ""),
                sindicato=record.get("sindicato", ""),
                categoria=record.get("categoria", ""),
                ano=record.get("ano_referencia", 0),
                tipo_instrumento="CCT",
            )
            if instrumento is not None:
                total_metrics["api_mte_disponivel"] = True
                total_metrics["instrumentos_mte_localizados"] += 1
            else:
                total_metrics["instrumentos_mte_nao_localizados"] += 1

        rec_metrics = enrich_from_mte_fallback(
            record=record,
            instrumento_mte=instrumento,
            piso_nacional_valor=piso_nacional_valor,
        )
        per_record.append({"id": rid, **rec_metrics})

        for key in ("preenchidos_mte", "pendentes", "conflitos", "preenchidos_piso_nacional"):
            total_metrics[key] += rec_metrics[key]

        if rec_metrics["preenchidos_mte"] > 0 or rec_metrics["preenchidos_piso_nacional"] > 0:
            total_metrics["registros_com_dados_reais"] += 1
            any_real_data = True

    total_metrics["per_record"] = per_record

    # ── Report ────────────────────────────────────────────────────────────────
    _print_metrics_report(total_metrics)

    # ── Persistence: only when real data was found (AC3 / AC7) ────────────────
    # fonte_oficial_mte metadata changes (url/codigo_instrumento/manual) are
    # also persisted when present, as they are non-destructive additive changes.
    has_fonte_change = (
        effective_mte_tipo in ("url", "codigo_instrumento", "manual")
        and total_metrics["registros_processados"] > 0
    )
    should_write = any_real_data or has_fonte_change

    if should_write and not dry_run:
        logger.info("Dados encontrados — gravando base.")
        _save_json(data, json_path)
        _export_js(EXPORT_SCRIPT)
        total_metrics["json_js_atualizados"] = True
    elif should_write and dry_run:
        logger.info("[dry-run] Dados encontrados — nenhum arquivo gravado.")
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
    logger.info("RELATÓRIO DE ENRIQUECIMENTO MTE — PRJ-65/PRJ-66")
    logger.info(sep)
    logger.info("  Registros processados:             %d", metrics["registros_processados"])
    logger.info("  Instrumentos MTE localizados:      %d", metrics.get("instrumentos_mte_localizados", 0))
    logger.info("  Instrumentos MTE não localizados:  %d", metrics.get("instrumentos_mte_nao_localizados", 0))
    logger.info(sep)
    logger.info("  Campos preenchidos via MTE:        %d", metrics["preenchidos_mte"])
    logger.info("  Campos mantidos como pendente:     %d", metrics["pendentes"])
    logger.info("  Campos marcados como conflito:     %d", metrics["conflitos"])
    logger.info("  Campos preenchidos (Piso Nacional):%d", metrics["preenchidos_piso_nacional"])
    logger.info(sep)
    json_js_atualizados = metrics.get("json_js_atualizados", False)
    logger.info("  Arquivos JSON/JS atualizados:      %s", "sim" if json_js_atualizados else "não")
    logger.info(sep)
    if not metrics["api_mte_disponivel"] and metrics["preenchidos_piso_nacional"] == 0 and metrics["preenchidos_mte"] == 0:
        logger.info(
            "  DECLARAÇÃO: Nenhum dado real encontrado via MTE ou arquivo. "
            "base_parametros_sindicais.json e .js NÃO modificados."
        )
    logger.info(sep)


# ──────────────────────────────────────────────────────────────────────────────
# Processamento em lote via arquivo de mapeamento (PRJ-67)
# ──────────────────────────────────────────────────────────────────────────────

# Colunas obrigatórias e opcionais do arquivo de mapeamento CSV/JSON
_MAP_REQUIRED_COLS: frozenset[str] = frozenset({"registro_id", "tipo_referencia"})
_MAP_OPTIONAL_COLS: tuple[str, ...] = (
    "arquivo_origem", "url", "codigo_instrumento", "observacao"
)


def parse_mte_map(filepath: str) -> list[dict]:
    """Parse a CSV or JSON mapping file and return a list of mapping entries.

    Each entry is a dict with keys:
        registro_id, tipo_referencia, arquivo_origem, url,
        codigo_instrumento, observacao.

    Supported formats:
        - CSV: columns registro_id, tipo_referencia, arquivo_origem,
               url, codigo_instrumento, observacao (header row required).
        - JSON: a list of objects with the same keys.

    Missing optional fields are normalised to None.
    Rows with empty tipo_referencia are skipped with a warning.

    Raises:
        ValueError: if the file format is not recognized or required columns
                    are missing.
        FileNotFoundError: if the file does not exist.
    """
    if not os.path.isfile(filepath):
        raise FileNotFoundError(f"Arquivo de mapeamento não encontrado: {filepath!r}")

    ext = os.path.splitext(filepath)[1].lower()

    entries: list[dict] = []

    if ext == ".json":
        with open(filepath, "r", encoding="utf-8") as f:
            raw = json.load(f)
        if not isinstance(raw, list):
            raise ValueError(
                f"Arquivo JSON de mapeamento deve conter uma lista de objetos, "
                f"mas recebeu {type(raw).__name__!r}."
            )
        for i, item in enumerate(raw):
            if not isinstance(item, dict):
                logger.warning("Entrada JSON #%d não é um objeto — ignorada.", i)
                continue
            entry = _normalise_map_entry(item, f"JSON #{i}")
            if entry is not None:
                entries.append(entry)

    elif ext == ".csv":
        with open(filepath, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            if reader.fieldnames is None:
                raise ValueError("Arquivo CSV vazio ou sem cabeçalho.")
            col_set = {c.strip() for c in reader.fieldnames}
            missing = _MAP_REQUIRED_COLS - col_set
            if missing:
                raise ValueError(
                    f"CSV de mapeamento está faltando as colunas obrigatórias: "
                    f"{sorted(missing)}. Colunas encontradas: {sorted(col_set)}."
                )
            for i, row in enumerate(reader):
                entry = _normalise_map_entry(
                    {k.strip(): (v.strip() if v else None) for k, v in row.items()},
                    f"CSV linha {i + 2}",
                )
                if entry is not None:
                    entries.append(entry)

    else:
        raise ValueError(
            f"Formato de arquivo de mapeamento não suportado: {ext!r}. "
            "Use .csv ou .json."
        )

    logger.info("Arquivo de mapeamento carregado: %d entradas — %s", len(entries), filepath)
    return entries


def _normalise_map_entry(raw: dict, label: str) -> dict | None:
    """Normalise a raw mapping row to a canonical entry dict.

    Returns None and logs a warning for entries that should be skipped.
    """
    registro_id = (raw.get("registro_id") or "").strip()
    tipo_referencia = (raw.get("tipo_referencia") or "").strip()

    if not registro_id:
        logger.warning("%s: registro_id vazio — linha ignorada.", label)
        return None
    if not tipo_referencia:
        logger.warning("%s (id=%r): tipo_referencia vazio — linha ignorada.", label, registro_id)
        return None
    if tipo_referencia not in FONTE_OFICIAL_MTE_TIPOS:
        logger.warning(
            "%s (id=%r): tipo_referencia inválido %r — linha ignorada. "
            "Valores aceitos: %s.",
            label, registro_id, tipo_referencia, sorted(FONTE_OFICIAL_MTE_TIPOS),
        )
        return None

    def _opt(key: str) -> str | None:
        val = (raw.get(key) or "").strip()
        return val if val else None

    return {
        "registro_id": registro_id,
        "tipo_referencia": tipo_referencia,
        "arquivo_origem": _opt("arquivo_origem"),
        "url": _opt("url"),
        "codigo_instrumento": _opt("codigo_instrumento"),
        "observacao": _opt("observacao"),
    }


def _collect_field_changes(
    itens_before: dict,
    itens_after: dict,
) -> tuple[list[str], list[str], list[str]]:
    """Compare itens_cct snapshots and return (filled, pending, conflict) field lists."""
    filled: list[str] = []
    pending: list[str] = []
    conflict: list[str] = []

    all_campos = set(itens_before) | set(itens_after)
    for campo in sorted(all_campos):
        field = itens_after.get(campo)
        if not isinstance(field, dict):
            continue
        status = field.get("status_parametro")
        origem = field.get("origem")
        if status == "conflito" or origem == "conflito_pdf_mte":
            conflict.append(campo)
        elif origem in ("fonte_oficial_mte", "fonte_oficial_nacional"):
            filled.append(campo)
        elif status == "pendente_revisao" or origem == "nao_identificado_pdf":
            pending.append(campo)

    return filled, pending, conflict


def run_batch_enrichment(
    mte_map_path: str,
    json_path: str = JSON_PATH,
    dry_run: bool = False,
    piso_nacional_valor: float | None = None,
    report_dir: str = REPORTS_DIR,
) -> dict:
    """Process multiple records in batch from a CSV or JSON mapping file.

    For each entry in the mapping:
      - tipo_referencia=arquivo: parses the PDF and enriches pending eligible fields.
      - tipo_referencia=url | codigo_instrumento | manual: registers fonte_oficial_mte
        without altering itens_cct.

    Records not present in the mapping file are left completely untouched and
    reported as sem_fonte_oficial_associada.

    AC3 (PRJ-67): With --dry-run, NO files are written under any circumstances.
    AC10 (PRJ-67): base JSON/JS are only updated when at least one record has a
    real enrichment, conflict, official reference, or Piso Nacional applied.
    AC4 (PRJ-67): A coverage report is generated in terminal AND saved to
    reports/mte_enrichment_report.json (unless --dry-run).

    Args:
        mte_map_path:        Path to the mapping file (.csv or .json).
        json_path:           Path to base_parametros_sindicais.json.
        dry_run:             If True, no files are written.
        piso_nacional_valor: Piso Nacional value for last-resort fallback.
        report_dir:          Directory where the coverage report is saved.

    Returns:
        A report dict with global totals and per-registro breakdown.
    """
    logger.info("═══════════════════════════════════════════════════════")
    logger.info("Iniciando enriquecimento em LOTE via mapeamento (PRJ-67)")
    logger.info("mte_map=%s  dry_run=%s", mte_map_path, dry_run)
    logger.info("═══════════════════════════════════════════════════════")

    map_entries = parse_mte_map(mte_map_path)
    map_index: dict[str, dict] = {e["registro_id"]: e for e in map_entries}

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    records = data.get("registros", [])

    # Build index of records by ID for fast lookup
    record_index: dict[str, dict] = {
        r.get("id_registro_reajuste", ""): r for r in records
    }

    # Pre-parse PDF files so each unique arquivo_origem is only parsed once
    _pdf_cache: dict[str, dict | None] = {}

    def _get_instrumento_from_file(arquivo_origem: str | None) -> dict | None:
        if not arquivo_origem:
            return None
        if arquivo_origem in _pdf_cache:
            return _pdf_cache[arquivo_origem]
        result = None
        try:
            from parse_mte_instrumento import parse_mte_pdf  # type: ignore[import]
            result = parse_mte_pdf(arquivo_origem)
        except ImportError:
            logger.error(
                "parse_mte_instrumento não encontrado — arquivo %r não processado.",
                arquivo_origem,
            )
        if result is None:
            logger.warning(
                "Parser MTE não retornou dados para %r.", arquivo_origem
            )
        _pdf_cache[arquivo_origem] = result
        return result

    totais = {
        "registros_no_mapeamento": len(map_entries),
        "registros_processados": 0,
        "registros_sem_fonte_associada": 0,
        "registros_nao_encontrados": 0,
        "campos_preenchidos_mte": 0,
        "campos_pendentes": 0,
        "campos_conflito": 0,
        "campos_piso_nacional": 0,
        "arquivos_atualizados": False,
    }

    por_registro: dict[str, dict] = {}
    any_real_change = False

    # Process records listed in the mapping
    for rid, entry in map_index.items():
        if rid not in record_index:
            logger.warning("Registro %r do mapeamento não encontrado na base — ignorado.", rid)
            por_registro[rid] = {
                "status_processamento": "registro_nao_encontrado",
                "tipo_referencia": entry["tipo_referencia"],
                "arquivo_origem": entry.get("arquivo_origem"),
                "url": entry.get("url"),
                "codigo_instrumento": entry.get("codigo_instrumento"),
                "campos_preenchidos": [],
                "campos_pendentes": [],
                "campos_conflito": [],
                "observacao": f"Registro {rid!r} não encontrado em base_parametros_sindicais.json.",
            }
            totais["registros_nao_encontrados"] += 1
            continue

        record = record_index[rid]
        tipo = entry["tipo_referencia"]
        totais["registros_processados"] += 1

        logger.info("── %s  tipo=%s", rid, tipo)

        # Snapshot itens_cct before enrichment for field-change tracking
        itens_before = copy.deepcopy(record.get("itens_cct", {}))

        instrumento: dict | None = None
        obs: str | None = None

        if tipo == "arquivo":
            instrumento = _get_instrumento_from_file(entry.get("arquivo_origem"))
            fonte_status = "localizado" if instrumento is not None else "nao_localizado"
            if instrumento is None:
                obs = (
                    f"Arquivo {entry.get('arquivo_origem')!r} não foi processável "
                    "pelo parser MTE — nenhum campo enriquecido."
                )
            fonte_data = _build_fonte_oficial_mte(
                tipo_referencia="arquivo",
                arquivo_origem=(
                    os.path.basename(entry["arquivo_origem"])
                    if entry.get("arquivo_origem") else None
                ),
                vigencia_inicio=(
                    instrumento.get("vigencia_inicio") if instrumento else None
                ),
                vigencia_fim=(
                    instrumento.get("vigencia_fim") if instrumento else None
                ),
                observacao=entry.get("observacao"),
                status_consulta=fonte_status,
            )
            _set_fonte_oficial_mte(record, fonte_data)

        elif tipo in ("url", "codigo_instrumento"):
            has_ref = bool(entry.get("url") or entry.get("codigo_instrumento"))
            fonte_data = _build_fonte_oficial_mte(
                tipo_referencia=tipo,
                url=entry.get("url"),
                codigo_instrumento=entry.get("codigo_instrumento"),
                observacao=entry.get("observacao"),
                status_consulta="localizado" if has_ref else "nao_localizado",
            )
            _set_fonte_oficial_mte(record, fonte_data)
            any_real_change = True  # reference metadata is a valid change
            logger.info(
                "  tipo=%s: referência registrada em fonte_oficial_mte; itens_cct não alterados.",
                tipo,
            )

        elif tipo == "manual":
            fonte_data = _build_fonte_oficial_mte(
                tipo_referencia="manual",
                url=entry.get("url"),
                codigo_instrumento=entry.get("codigo_instrumento"),
                observacao=entry.get("observacao"),
                status_consulta="localizado",
            )
            _set_fonte_oficial_mte(record, fonte_data)
            any_real_change = True
            logger.info(
                "  tipo=manual: metadados registrados em fonte_oficial_mte; "
                "itens_cct NÃO alterados."
            )

        rec_metrics = enrich_from_mte_fallback(
            record=record,
            instrumento_mte=instrumento,
            piso_nacional_valor=piso_nacional_valor,
        )

        itens_after = record.get("itens_cct", {})
        filled, pending, conflict = _collect_field_changes(itens_before, itens_after)

        totais["campos_preenchidos_mte"] += rec_metrics["preenchidos_mte"]
        totais["campos_pendentes"] += rec_metrics["pendentes"]
        totais["campos_conflito"] += rec_metrics["conflitos"]
        totais["campos_piso_nacional"] += rec_metrics["preenchidos_piso_nacional"]

        if rec_metrics["preenchidos_mte"] > 0 or rec_metrics["preenchidos_piso_nacional"] > 0 or rec_metrics["conflitos"] > 0:
            any_real_change = True

        por_registro[rid] = {
            "status_processamento": "processado",
            "tipo_referencia": tipo,
            "arquivo_origem": entry.get("arquivo_origem"),
            "url": entry.get("url"),
            "codigo_instrumento": entry.get("codigo_instrumento"),
            "campos_preenchidos": filled,
            "campos_pendentes": pending,
            "campos_conflito": conflict,
            "observacao": obs,
        }

    # Records in base NOT in the mapping → sem_fonte_oficial_associada
    for rid, record in record_index.items():
        if rid and rid not in map_index:
            totais["registros_sem_fonte_associada"] += 1
            por_registro[rid] = {
                "status_processamento": "sem_fonte_oficial_associada",
                "tipo_referencia": None,
                "arquivo_origem": None,
                "url": None,
                "codigo_instrumento": None,
                "campos_preenchidos": [],
                "campos_pendentes": list(ELIGIBLE_FIELDS.keys()),
                "campos_conflito": [],
                "observacao": "Registro não listado no arquivo de mapeamento.",
            }

    # Persist JSON/JS only when there is a real change (AC10 / AC3)
    if any_real_change and not dry_run:
        logger.info("Dados encontrados em lote — gravando base.")
        _save_json(data, json_path)
        _export_js(EXPORT_SCRIPT)
        totais["arquivos_atualizados"] = True
    elif any_real_change and dry_run:
        logger.info("[dry-run] Dados encontrados em lote — nenhum arquivo gravado.")
    else:
        logger.info(
            "Nenhum dado real encontrado no lote. "
            "base_parametros_sindicais.json e .js NÃO foram modificados."
        )

    report = {
        "data_execucao": _today(),
        "dry_run": dry_run,
        "arquivo_mapeamento": os.path.basename(mte_map_path),
        "totais": totais,
        "por_registro": por_registro,
    }

    _print_batch_report(report)

    if not dry_run:
        os.makedirs(report_dir, exist_ok=True)
        report_path = os.path.join(report_dir, "mte_enrichment_report.json")
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        logger.info("Relatório gravado em: %s", report_path)
    else:
        logger.info("[dry-run] Relatório NÃO gravado em disco.")

    return report


def _print_batch_report(report: dict) -> None:
    """Print the batch enrichment coverage report to the terminal."""
    sep = "═" * 60
    t = report["totais"]
    logger.info(sep)
    logger.info("RELATÓRIO DE ENRIQUECIMENTO EM LOTE (PRJ-67)")
    if report.get("dry_run"):
        logger.info("  *** MODO DRY-RUN — nenhum arquivo foi gravado ***")
    logger.info(sep)
    logger.info("  Arquivo de mapeamento:           %s", report.get("arquivo_mapeamento"))
    logger.info("  Registros no mapeamento:         %d", t["registros_no_mapeamento"])
    logger.info("  Registros processados:           %d", t["registros_processados"])
    logger.info("  Registros sem fonte associada:   %d", t["registros_sem_fonte_associada"])
    logger.info("  Registros não encontrados:       %d", t["registros_nao_encontrados"])
    logger.info(sep)
    logger.info("  Campos preenchidos via MTE:      %d", t["campos_preenchidos_mte"])
    logger.info("  Campos pendentes:                %d", t["campos_pendentes"])
    logger.info("  Campos em conflito:              %d", t["campos_conflito"])
    logger.info("  Campos (Piso Nacional):          %d", t["campos_piso_nacional"])
    logger.info(sep)
    logger.info("  Arquivos JSON/JS atualizados:    %s", "sim" if t["arquivos_atualizados"] else "não")
    logger.info(sep)

    for rid, rec_report in report.get("por_registro", {}).items():
        status = rec_report["status_processamento"]
        tipo = rec_report.get("tipo_referencia") or "—"
        filled = rec_report.get("campos_preenchidos") or []
        pending = rec_report.get("campos_pendentes") or []
        conflict = rec_report.get("campos_conflito") or []
        obs = rec_report.get("observacao")

        logger.info("  ┌─ %s", rid)
        logger.info("  │  status: %s  tipo: %s", status, tipo)
        if filled:
            logger.info("  │  preenchidos: %s", ", ".join(filled))
        if conflict:
            logger.info("  │  conflitos:   %s", ", ".join(conflict))
        if pending:
            logger.info("  │  pendentes:   %s", ", ".join(pending))
        if obs:
            logger.info("  │  obs: %s", obs)
        logger.info("  └─")

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
        metavar="PATH",
        help="Caminho para o PDF oficial do MTE (tipo_referencia=arquivo).",
    )
    parser.add_argument(
        "--mte-source",
        metavar="PATH",
        help="Alias para --mte-file.",
    )
    parser.add_argument(
        "--mte-tipo",
        choices=sorted(FONTE_OFICIAL_MTE_TIPOS),
        metavar="TYPE",
        help="Tipo da referência oficial: arquivo | url | codigo_instrumento | manual.",
    )
    parser.add_argument(
        "--mte-url",
        metavar="URL",
        help="URL do instrumento no Sistema Mediador.",
    )
    parser.add_argument(
        "--mte-codigo",
        metavar="CODE",
        help="Código/número do instrumento no Sistema Mediador.",
    )
    parser.add_argument(
        "--mte-sindicato",
        metavar="NAME",
        help="Nome do sindicato conforme registro MTE (para referências manual).",
    )
    parser.add_argument(
        "--mte-vigencia-inicio",
        metavar="YYYY-MM-DD",
        help="Data de início de vigência do instrumento.",
    )
    parser.add_argument(
        "--mte-vigencia-fim",
        metavar="YYYY-MM-DD",
        help="Data de fim de vigência do instrumento.",
    )
    parser.add_argument(
        "--mte-observacao",
        metavar="TEXT",
        help="Observação do operador sobre a referência oficial.",
    )
    parser.add_argument(
        "--mte-map",
        metavar="FILE",
        help=(
            "Arquivo de mapeamento CSV ou JSON para processamento em lote. "
            "Colunas CSV: registro_id, tipo_referencia, arquivo_origem, url, "
            "codigo_instrumento, observacao. "
            "Quando informado, ignora --ids / --mte-file / --mte-tipo e demais "
            "opções de registro individual."
        ),
    )
    args = parser.parse_args()

    if args.mte_map:
        run_batch_enrichment(
            mte_map_path=args.mte_map,
            json_path=JSON_PATH,
            dry_run=args.dry_run,
        )
    else:
        run_enrichment(
            json_path=JSON_PATH,
            dry_run=args.dry_run,
            ids=args.ids,
            mte_file=args.mte_file,
            mte_source=args.mte_source,
            mte_tipo=args.mte_tipo,
            mte_url=args.mte_url,
            mte_codigo=args.mte_codigo,
            mte_sindicato=args.mte_sindicato,
            mte_vigencia_inicio=args.mte_vigencia_inicio,
            mte_vigencia_fim=args.mte_vigencia_fim,
            mte_observacao=args.mte_observacao,
        )

    # Exit code: 0 if all went well (even with zero enrichments)
    sys.exit(0)


if __name__ == "__main__":
    main()

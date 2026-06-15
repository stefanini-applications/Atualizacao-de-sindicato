#!/usr/bin/env python3
"""
Módulo de enriquecimento complementar de campos não identificados no PDF
via fonte oficial do Ministério do Trabalho e Emprego (MTE) — Sistema Mediador.

Este módulo é estritamente aditivo: nenhum componente existente é modificado.
Apenas campos com status_parametro "pendente_revisao" ou origem "nao_identificado_pdf"
são elegíveis. Campos com status_parametro "valido" ou com origem "pdf_cct" e
valor não nulo nunca são sobrescritos.

═══════════════════════════════════════════════════════════════════════════════
PRJ-66 — Associar instrumento oficial MTE a registros CCT
═══════════════════════════════════════════════════════════════════════════════
Cada registro CCT/ACT pode receber uma referência oficial MTE armazenada na
nova seção `fonte_oficial_mte`. Tipos de referência suportados:

  arquivo          — PDF/texto local; o parser independente extrai campos com
                     evidência textual rastreável (fonte_textual obrigatória).
  url              — URL do instrumento; apenas a referência é registrada.
  codigo_instrumento — Código do instrumento; apenas a referência é registrada.
  manual           — Metadados informados pelo operador (número, URL, sindicato,
                     vigência, observação). NÃO preenche itens_cct sem evidência
                     textual extraída de arquivo processável.

Uso:
    python3 enrich_mte_fallback.py [--dry-run] [--ids ID1 ID2 ...]
        [--mte-file CAMINHO] [--mte-source SOURCE]
        [--mte-tipo {arquivo,url,codigo_instrumento,manual}]
        [--mte-codigo CODIGO] [--mte-url URL]
        [--mte-sindicato SINDICATO]
        [--mte-vigencia-inicio AAAA-MM-DD]
        [--mte-vigencia-fim AAAA-MM-DD]
        [--mte-observacao TEXTO]

Exemplos:
    python3 enrich_mte_fallback.py --ids REG-SP-SINDPD-2025 \\
        --mte-file caminho/instrumento.pdf --dry-run

    python3 enrich_mte_fallback.py --ids REG-SP-SINDPD-2025 \\
        --mte-source https://mediador.mte.gov.br/instrumento/123 \\
        --mte-tipo url

    python3 enrich_mte_fallback.py --ids REG-SP-SINDPD-2025 \\
        --mte-tipo manual --mte-codigo MTE-CCT-2025-SP \\
        --mte-sindicato "Sindicato dos Trabalhadores" \\
        --mte-vigencia-inicio 2025-01-01 --mte-vigencia-fim 2025-12-31

═══════════════════════════════════════════════════════════════════════════════
LIMITAÇÃO TÉCNICA EXPLÍCITA (AC3 / AC7 — PRJ-65)
═══════════════════════════════════════════════════════════════════════════════
Não existe API pública estável do Sistema Mediador para consulta automatizada.
Quando nenhum --mte-file ou --mte-source for informado, o comportamento é:
  - lookup_mte_instrumento_coletivo() registra a limitação no log e retorna None.
  - data/base_parametros_sindicais.json e .js NÃO são modificados.
  - Nenhum valor é simulado, inventado ou estimado.
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
# fonte_oficial_mte — estrutura de referência oficial MTE (PRJ-66)
# ──────────────────────────────────────────────────────────────────────────────

# Tipos de referência suportados em fonte_oficial_mte
TIPOS_REFERENCIA_MTE: frozenset[str] = frozenset({
    "arquivo",
    "url",
    "codigo_instrumento",
    "manual",
})

# Tipos que permitem enriquecimento de itens_cct (requerem arquivo processável)
TIPOS_COM_PROCESSAMENTO: frozenset[str] = frozenset({"arquivo"})


def _build_fonte_oficial_mte(
    tipo_referencia: str,
    status_consulta: str,
    arquivo_origem: str | None = None,
    url: str | None = None,
    codigo_instrumento: str | None = None,
    sindicato: str | None = None,
    vigencia_inicio: str | None = None,
    vigencia_fim: str | None = None,
    observacao: str | None = None,
) -> dict:
    """
    Build the fonte_oficial_mte structure for a record.

    Args:
        tipo_referencia: One of "arquivo", "url", "codigo_instrumento", "manual".
        status_consulta: "localizado" when the reference is registered/found,
                         "nao_localizado" when not found or not processable.
        arquivo_origem:  File path (for tipo "arquivo").
        url:             URL of the official instrument (for tipo "url" or "manual").
        codigo_instrumento: Instrument registration code.
        sindicato:       Union name (for tipo "manual").
        vigencia_inicio: Validity start date YYYY-MM-DD (for tipo "manual").
        vigencia_fim:    Validity end date YYYY-MM-DD (for tipo "manual").
        observacao:      Operator notes.

    Returns:
        A dict representing the fonte_oficial_mte section.
    """
    return {
        "disponivel": status_consulta == "localizado",
        "tipo_referencia": tipo_referencia,
        "url": url,
        "codigo_instrumento": codigo_instrumento,
        "arquivo_origem": arquivo_origem,
        "data_consulta": _today(),
        "status_consulta": status_consulta,
        "sindicato": sindicato,
        "vigencia_inicio": vigencia_inicio,
        "vigencia_fim": vigencia_fim,
        "observacao": observacao,
    }


def _store_fonte_oficial_mte(record: dict, fonte: dict) -> None:
    """Store the fonte_oficial_mte structure in a record (non-destructive)."""
    record["fonte_oficial_mte"] = fonte


def _load_mte_from_file(mte_file: str) -> tuple[dict | None, str]:
    """
    Parse an MTE instrument file using the independent parse_mte_instrumento module.

    Returns:
        (instrumento_dict | None, status_extracao)
        instrumento_dict is None when the file produced no usable campos.
    """
    try:
        from parse_mte_instrumento import parse_mte_instrumento  # noqa: PLC0415
    except ImportError:
        logger.error(
            "Módulo parse_mte_instrumento não encontrado. "
            "Verifique se parse_mte_instrumento.py está presente no diretório raiz."
        )
        return None, "nao_processavel"

    parsed = parse_mte_instrumento(mte_file)
    status = parsed.get("status_extracao", "nao_processavel")
    campos = parsed.get("campos", {})

    if campos:
        return {"campos": campos}, status
    return None, status


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
    mte_metadata: dict | None = None,
) -> dict:
    """
    Main enrichment routine.

    Loads base_parametros_sindicais.json, attempts MTE lookup (or processes a
    provided MTE file/source) for each record, applies enrichment rules, and
    saves the result only when real data is found.

    PRJ-66 — fonte_oficial_mte support:
      When mte_file is provided, the independent MTE parser extracts campos and
      the result is stored in fonte_oficial_mte. If the file yields usable text,
      itens_cct fields may be enriched. Types url/codigo_instrumento/manual only
      store a reference in fonte_oficial_mte; they do NOT alter itens_cct.
      Manual references NEVER populate itens_cct — only arquivo type can enrich.

    AC3: If the MTE API is unavailable (lookup returns None) AND Piso Nacional
    is not provided AND no mte_file was processed, the JSON/JS files are NOT
    modified.

    AC5: Returns a comprehensive metrics dict for reporting including
    instrumentos_localizados, instrumentos_nao_localizados, json_js_atualizados.

    Args:
        json_path:           Path to base_parametros_sindicais.json.
        dry_run:             If True, do not write any files.
        ids:                 If provided, process only records with these IDs.
        piso_nacional_valor: Piso Nacional value for last-resort fallback.
        mte_file:            Path to local MTE instrument file (PDF or .txt).
                             Implies tipo_referencia="arquivo". Enables enrichment
                             when the file yields processable text with evidence.
        mte_source:          URL or instrument code reference (no file parsing).
                             Stores the reference in fonte_oficial_mte only.
        mte_tipo:            Explicit tipo_referencia override. When combined with
                             mte_file, defaults to "arquivo". With mte_source,
                             defaults to "url". With neither, defaults to "manual".
        mte_metadata:        Extra metadata dict for fonte_oficial_mte
                             (keys: url, codigo_instrumento, sindicato,
                             vigencia_inicio, vigencia_fim, observacao).

    Returns:
        Metrics dict with per-run totals and per-record breakdown.
    """
    logger.info("═══════════════════════════════════════════════════════")
    logger.info("Iniciando rotina de enriquecimento MTE (PRJ-66)")
    logger.info("dry_run=%s  ids=%s  mte_file=%s  mte_source=%s  mte_tipo=%s",
                dry_run, ids, mte_file, mte_source, mte_tipo)
    logger.info("═══════════════════════════════════════════════════════")

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
        "api_mte_disponivel": False,
        "instrumentos_localizados": 0,
        "instrumentos_nao_localizados": 0,
        "json_js_atualizados": False,
    }
    per_record: list[dict] = []
    any_real_data = False
    any_fonte_mte_stored = False  # True when fonte_oficial_mte reference was added to any record

    # ── Pre-process mte_file once outside the record loop ─────────────────────
    # The parsed instrumento is shared across all filtered records (one file
    # typically corresponds to one instrument, applied to the specified --ids).
    _mte_instrumento_from_file: dict | None = None
    _mte_file_status: str = ""
    if mte_file:
        _mte_instrumento_from_file, _mte_file_status = _load_mte_from_file(mte_file)
        if _mte_instrumento_from_file:
            logger.info(
                "Parser MTE: arquivo '%s' processado com sucesso (%d campos).",
                mte_file,
                len(_mte_instrumento_from_file.get("campos", {})),
            )
        else:
            logger.info(
                "Parser MTE: arquivo '%s' não produziu campos utilizáveis (status=%s).",
                mte_file,
                _mte_file_status,
            )

    for record in records:
        rid = record.get("id_registro_reajuste", "?")
        if id_filter and rid not in id_filter:
            continue

        total_metrics["registros_processados"] += 1
        logger.info("── %s (%s / %s)", rid, record.get("uf"), record.get("sindicato"))

        # ── Determine instrumento and fonte_oficial_mte for this record ────────
        instrumento: dict | None = None
        fonte_mte: dict | None = None
        meta = mte_metadata or {}

        if mte_file:
            # tipo = "arquivo" — independent parser result
            tipo_ref = mte_tipo or "arquivo"
            if _mte_instrumento_from_file:
                instrumento = _mte_instrumento_from_file
                fonte_mte = _build_fonte_oficial_mte(
                    tipo_referencia=tipo_ref,
                    status_consulta="localizado",
                    arquivo_origem=mte_file,
                    url=meta.get("url"),
                    codigo_instrumento=meta.get("codigo_instrumento"),
                    sindicato=meta.get("sindicato"),
                    vigencia_inicio=meta.get("vigencia_inicio"),
                    vigencia_fim=meta.get("vigencia_fim"),
                    observacao=meta.get("observacao"),
                )
                total_metrics["instrumentos_localizados"] += 1
                total_metrics["api_mte_disponivel"] = True
            else:
                # File found but not processable — register reference, no enrichment
                fonte_mte = _build_fonte_oficial_mte(
                    tipo_referencia=tipo_ref,
                    status_consulta="nao_localizado",
                    arquivo_origem=mte_file,
                    observacao=(
                        meta.get("observacao")
                        or f"Arquivo não processável: {_mte_file_status}"
                    ),
                )
                total_metrics["instrumentos_nao_localizados"] += 1

        elif mte_source:
            # URL or instrument code reference — no file to parse, no enrichment
            tipo_ref = mte_tipo or "url"
            fonte_mte = _build_fonte_oficial_mte(
                tipo_referencia=tipo_ref,
                status_consulta="localizado",
                url=mte_source if tipo_ref == "url" else meta.get("url"),
                codigo_instrumento=(
                    mte_source if tipo_ref == "codigo_instrumento"
                    else meta.get("codigo_instrumento")
                ),
                sindicato=meta.get("sindicato"),
                vigencia_inicio=meta.get("vigencia_inicio"),
                vigencia_fim=meta.get("vigencia_fim"),
                observacao=meta.get("observacao"),
            )
            total_metrics["instrumentos_localizados"] += 1
            # instrumento remains None — no content to enrich itens_cct

        elif mte_tipo == "manual":
            # Manual metadata — never enriches itens_cct (AC6)
            fonte_mte = _build_fonte_oficial_mte(
                tipo_referencia="manual",
                status_consulta="localizado",
                url=meta.get("url"),
                codigo_instrumento=meta.get("codigo_instrumento"),
                sindicato=meta.get("sindicato"),
                vigencia_inicio=meta.get("vigencia_inicio"),
                vigencia_fim=meta.get("vigencia_fim"),
                observacao=meta.get("observacao"),
            )
            total_metrics["instrumentos_localizados"] += 1
            # instrumento remains None — manual type never fills itens_cct without
            # fonte_textual extracted from a processable file (AC6)

        else:
            # Fallback: attempt API lookup (currently returns None — PRJ-65 stub)
            instrumento = lookup_mte_instrumento_coletivo(
                uf=record.get("uf", ""),
                sindicato=record.get("sindicato", ""),
                categoria=record.get("categoria", ""),
                ano=record.get("ano_referencia", 0),
                tipo_instrumento="CCT",
            )
            if instrumento is not None:
                total_metrics["api_mte_disponivel"] = True
                total_metrics["instrumentos_localizados"] += 1
            else:
                total_metrics["instrumentos_nao_localizados"] += 1

        # ── Store fonte_oficial_mte in record if we have reference data ────────
        if fonte_mte is not None:
            _store_fonte_oficial_mte(record, fonte_mte)
            any_fonte_mte_stored = True

        # ── Enrich itens_cct ───────────────────────────────────────────────────
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

    # ── Persistence: save when real enrichment occurred OR fonte_oficial_mte was stored ──
    # AC2/AC3: JSON/JS updated only when meaningful updates were made (enrichment or
    # fonte_oficial_mte reference stored). Never writes when nothing was changed.
    should_save = any_real_data or any_fonte_mte_stored
    if should_save and not dry_run:
        logger.info(
            "Atualizações detectadas (dados_reais=%s, fonte_mte=%s) — gravando base.",
            any_real_data,
            any_fonte_mte_stored,
        )
        _save_json(data, json_path)
        _export_js(EXPORT_SCRIPT)
        total_metrics["json_js_atualizados"] = True
    elif should_save and dry_run:
        logger.info("[dry-run] Atualizações detectadas — nenhum arquivo gravado.")
    else:
        logger.info(
            "Nenhum dado real encontrado via MTE ou Piso Nacional. "
            "base_parametros_sindicais.json e .js NÃO foram modificados. "
            "Nenhum valor foi simulado."
        )

    return total_metrics


def _print_metrics_report(metrics: dict) -> None:
    """Print AC5 mandatory execution metrics report."""
    sep = "═" * 60
    logger.info(sep)
    logger.info("RELATÓRIO DE ENRIQUECIMENTO MTE — PRJ-66")
    logger.info(sep)
    logger.info("  Registros processados:             %d", metrics["registros_processados"])
    logger.info(
        "  Instrumentos MTE localizados:      %d",
        metrics.get("instrumentos_localizados", 0),
    )
    logger.info(
        "  Instrumentos MTE não localizados:  %d",
        metrics.get("instrumentos_nao_localizados", 0),
    )
    logger.info(sep)
    logger.info("  Campos preenchidos via MTE:        %d", metrics["preenchidos_mte"])
    logger.info("  Campos mantidos como pendente:     %d", metrics["pendentes"])
    logger.info("  Campos marcados como conflito:     %d", metrics["conflitos"])
    logger.info("  Campos preenchidos (Piso Nacional):%d", metrics["preenchidos_piso_nacional"])
    logger.info(sep)
    json_js_ok = metrics.get("json_js_atualizados", False)
    logger.info("  JSON/JS atualizados:               %s", "Sim" if json_js_ok else "Não")
    logger.info(sep)
    if not metrics.get("api_mte_disponivel") and metrics["preenchidos_piso_nacional"] == 0 \
            and metrics["preenchidos_mte"] == 0:
        logger.info(
            "  DECLARAÇÃO: Nenhum instrumento MTE processável disponível. "
            "Nenhum valor simulado. "
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
    # PRJ-66 — MTE source arguments
    parser.add_argument(
        "--mte-file",
        metavar="CAMINHO",
        default=None,
        help=(
            "Caminho para arquivo oficial MTE (PDF ou .txt) a ser parseado. "
            "Quando processável, enriquece campos pendentes dos registros informados em --ids."
        ),
    )
    parser.add_argument(
        "--mte-source",
        metavar="SOURCE",
        default=None,
        help=(
            "URL ou código do instrumento oficial MTE. Apenas registra a referência em "
            "fonte_oficial_mte sem alterar itens_cct (conteúdo não processável localmente)."
        ),
    )
    parser.add_argument(
        "--mte-tipo",
        choices=list(TIPOS_REFERENCIA_MTE),
        default=None,
        help=(
            "Tipo de referência MTE: arquivo, url, codigo_instrumento ou manual. "
            "Inferido automaticamente quando --mte-file ou --mte-source são informados."
        ),
    )
    # Manual metadata arguments (for --mte-tipo manual or extra metadata)
    parser.add_argument("--mte-codigo", metavar="CODIGO", default=None,
                        help="Número/código do instrumento MTE.")
    parser.add_argument("--mte-url", metavar="URL", default=None,
                        help="URL do instrumento MTE (para referência manual).")
    parser.add_argument("--mte-sindicato", metavar="SINDICATO", default=None,
                        help="Nome do sindicato (metadado manual).")
    parser.add_argument("--mte-vigencia-inicio", metavar="AAAA-MM-DD", default=None,
                        help="Data de início de vigência (metadado manual).")
    parser.add_argument("--mte-vigencia-fim", metavar="AAAA-MM-DD", default=None,
                        help="Data de fim de vigência (metadado manual).")
    parser.add_argument("--mte-observacao", metavar="TEXTO", default=None,
                        help="Observação para a referência MTE (metadado manual).")

    args = parser.parse_args()

    # Build mte_metadata from optional manual args
    mte_metadata: dict | None = None
    manual_fields = {
        "url": args.mte_url,
        "codigo_instrumento": args.mte_codigo,
        "sindicato": args.mte_sindicato,
        "vigencia_inicio": args.mte_vigencia_inicio,
        "vigencia_fim": args.mte_vigencia_fim,
        "observacao": args.mte_observacao,
    }
    if any(v is not None for v in manual_fields.values()):
        mte_metadata = {k: v for k, v in manual_fields.items() if v is not None}

    metrics = run_enrichment(
        json_path=JSON_PATH,
        dry_run=args.dry_run,
        ids=args.ids,
        mte_file=args.mte_file,
        mte_source=args.mte_source,
        mte_tipo=args.mte_tipo,
        mte_metadata=mte_metadata,
    )

    # Exit code: 0 if all went well (even with zero enrichments)
    sys.exit(0)


if __name__ == "__main__":
    main()

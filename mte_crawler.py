#!/usr/bin/env python3
"""
Módulo de busca automática de instrumentos coletivos no Sistema Mediador / MTE.

Este módulo é completamente isolado de extract_cct_items.py, app.js, index.html
e style.css. Sua responsabilidade é localizar instrumentos coletivos (CCT/ACT)
no Sistema Mediador usando os metadados disponíveis na base, integrar o resultado
ao pipeline de enriquecimento existente e gerar o relatório de busca automática.

Regras invioláveis (PRJ-68):
  - Nenhum campo é preenchido sem fonte_textual oficial.
  - Campos com status_parametro "valido" nunca são alterados.
  - Campos com origem "pdf_cct" e valor não nulo nunca são sobrescritos.
  - CAPTCHA / bloqueio / erro: registra status_consulta correspondente sem contornar.
  - Nenhum valor é inventado, inferido ou assumido sem evidência real.

Uso:
    python3 mte_crawler.py [--pending-only] [--dry-run] [--ids ID1 ID2 ...]

Opções:
    --pending-only   Processa apenas registros com campos pendente_revisao.
    --dry-run        Exibe o que seria feito sem gravar nenhum arquivo.
    --ids ID ...     Processa apenas os registros com os IDs informados.
    --json-path PATH Caminho para base_parametros_sindicais.json (padrão: data/).
"""

import argparse
import copy
import json
import logging
import os
import sys
import tempfile
from datetime import date
from typing import Any

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
JSON_PATH = os.path.join(REPO_ROOT, "data", "base_parametros_sindicais.json")
EXPORT_SCRIPT = os.path.join(REPO_ROOT, "export_inline_data.py")
REPORTS_DIR = os.path.join(REPO_ROOT, "reports")
REPORT_FILENAME = "mte_auto_lookup_report.json"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger("mte_crawler")

# ──────────────────────────────────────────────────────────────────────────────
# Constantes do Sistema Mediador / MTE
# ──────────────────────────────────────────────────────────────────────────────

MTE_MEDIADOR_BASE_URL = "https://www3.mte.gov.br/sistemas/mediador/"
MTE_MEDIADOR_SEARCH_URL = (
    "https://www3.mte.gov.br/sistemas/mediador/ConsultarInstColetivo"
)
MTE_REQUEST_TIMEOUT = 20  # seconds

# Indicadores de bloqueio / CAPTCHA na resposta HTML
_BLOCK_INDICATORS: tuple[str, ...] = (
    "captcha",
    "recaptcha",
    "robot",
    "acesso negado",
    "access denied",
    "bloqueado",
    "não autorizado",
    "nao autorizado",
    "403 forbidden",
    "service unavailable",
)

# UF → código numérico usado pelos formulários MTE
_UF_TO_COD: dict[str, str] = {
    "AC": "12", "AL": "27", "AM": "13", "AP": "16", "BA": "29",
    "CE": "23", "DF": "53", "ES": "32", "GO": "52", "MA": "21",
    "MG": "31", "MS": "50", "MT": "51", "PA": "15", "PB": "25",
    "PE": "26", "PI": "22", "PR": "41", "RJ": "33", "RN": "24",
    "RO": "11", "RR": "14", "RS": "43", "SC": "42", "SE": "28",
    "SP": "35", "TO": "17",
}


# ──────────────────────────────────────────────────────────────────────────────
# Helpers internos
# ──────────────────────────────────────────────────────────────────────────────


def _today() -> str:
    """Return today's date as YYYY-MM-DD."""
    return date.today().isoformat()


def _has_pending_fields(record: dict) -> bool:
    """Return True if the record has at least one field with pendente_revisao."""
    itens = record.get("itens_cct")
    if not isinstance(itens, dict):
        return False
    for field in itens.values():
        if isinstance(field, dict) and field.get("status_parametro") == "pendente_revisao":
            return True
    return False


def _detect_block(status_code: int, html: str) -> bool:
    """Return True if the response indicates a CAPTCHA / IP block."""
    if status_code in (403, 429, 503):
        return True
    lower = html.lower()
    return any(indicator in lower for indicator in _BLOCK_INDICATORS)


def _build_search_params(record: dict) -> dict[str, str]:
    """Build HTTP search parameters from record metadata."""
    uf = record.get("uf", "")
    ano = str(record.get("ano_referencia", ""))
    tipo_instrumento = record.get("tipo_instrumento", "CCT") or "CCT"
    cnpj = record.get("cnpj_entidade") or record.get("cnpj") or ""

    params: dict[str, str] = {}
    if uf:
        params["CodUF"] = _UF_TO_COD.get(uf.upper(), uf)
        params["SiglaUF"] = uf.upper()
    if ano:
        params["AnoInstCo"] = ano
    tipo_map = {"CCT": "C", "ACT": "A", "ACORDO": "A", "CONVENCAO": "C"}
    params["TipoInstCo"] = tipo_map.get(tipo_instrumento.upper(), "C")
    if cnpj:
        params["NrCNPJ"] = cnpj.replace(".", "").replace("/", "").replace("-", "")

    vigencia_inicio = record.get("vigencia_inicio", "")
    if vigencia_inicio:
        # Convert YYYY-MM-DD → DD/MM/YYYY for MTE form
        parts = str(vigencia_inicio).split("-")
        if len(parts) == 3:
            params["DtVigenciaIni"] = f"{parts[2]}/{parts[1]}/{parts[0]}"

    return params


# ──────────────────────────────────────────────────────────────────────────────
# API pública — três funções obrigatórias (AC1)
# ──────────────────────────────────────────────────────────────────────────────


def search_mte_instrument(record: dict) -> dict:
    """Search for the official collective instrument in Sistema Mediador / MTE.

    Uses the metadata available in the record (UF, sindicato, categoria, ano,
    CNPJ, tipo de instrumento) to perform an HTTP search against the Sistema
    Mediador public portal.

    If the portal returns CAPTCHA, HTTP 403/429/503, or any anti-automation
    mechanism, registers status_consulta "bloqueado" without attempting to
    bypass. If a network error or unexpected response occurs, registers
    status_consulta "erro". No value is invented or inferred.

    Args:
        record: A record dict from base_parametros_sindicais.json.

    Returns:
        A result dict with keys:
            disponivel (bool), tipo_referencia ("crawler"), url (str|None),
            codigo_instrumento (str|None), data_consulta (str),
            status_consulta ("localizado"|"nao_localizado"|"bloqueado"|"erro"),
            _content (bytes|None), _text (str|None).
    """
    rid = record.get("id_registro_reajuste", "?")
    result: dict[str, Any] = {
        "disponivel": False,
        "tipo_referencia": "crawler",
        "url": None,
        "codigo_instrumento": None,
        "data_consulta": _today(),
        "status_consulta": "nao_localizado",
        "_content": None,
        "_text": None,
    }

    try:
        import requests  # type: ignore[import]
    except ImportError:
        logger.warning(
            "[%s] requests não instalado — busca MTE indisponível. "
            "Instale com: pip install requests",
            rid,
        )
        result["status_consulta"] = "erro"
        result["_error"] = "requests não instalado"
        return result

    params = _build_search_params(record)
    logger.info(
        "[%s] Buscando no Sistema Mediador: UF=%s ano=%s tipo=%s",
        rid,
        record.get("uf"),
        record.get("ano_referencia"),
        record.get("tipo_instrumento", "CCT"),
    )

    session = requests.Session()
    session.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (compatible; MTE-crawler/1.0; "
            "+https://github.com/stefanini-applications/Atualizacao-de-sindicato)"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
    })

    try:
        response = session.get(
            MTE_MEDIADOR_SEARCH_URL,
            params=params,
            timeout=MTE_REQUEST_TIMEOUT,
            allow_redirects=True,
        )
        html = response.text

        if _detect_block(response.status_code, html):
            logger.warning(
                "[%s] Sistema Mediador retornou bloqueio/CAPTCHA (HTTP %d). "
                "status_consulta=bloqueado; campos permanecem pendente_revisao.",
                rid,
                response.status_code,
            )
            result["status_consulta"] = "bloqueado"
            result["_error"] = f"HTTP {response.status_code} / bloqueio detectado"
            return result

        if response.status_code != 200:
            logger.warning(
                "[%s] Resposta inesperada HTTP %d do Sistema Mediador.",
                rid,
                response.status_code,
            )
            result["status_consulta"] = "erro"
            result["_error"] = f"HTTP {response.status_code}"
            return result

        # Parse the HTML response to find instrument links
        instrument_url, codigo = _extract_instrument_link(html, record)

        if instrument_url:
            result["disponivel"] = True
            result["url"] = instrument_url
            result["codigo_instrumento"] = codigo
            result["status_consulta"] = "localizado"
            logger.info("[%s] Instrumento localizado: %s", rid, instrument_url)
        else:
            logger.info(
                "[%s] Instrumento não localizado no Sistema Mediador.", rid
            )

    except requests.exceptions.Timeout:
        logger.warning(
            "[%s] Timeout ao acessar Sistema Mediador (>%ds).",
            rid,
            MTE_REQUEST_TIMEOUT,
        )
        result["status_consulta"] = "erro"
        result["_error"] = "timeout"
    except requests.exceptions.ConnectionError as exc:
        logger.warning("[%s] Erro de conexão ao Sistema Mediador: %s", rid, exc)
        result["status_consulta"] = "erro"
        result["_error"] = f"connection error: {exc}"
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "[%s] Erro inesperado ao buscar no Sistema Mediador: %s", rid, exc
        )
        result["status_consulta"] = "erro"
        result["_error"] = str(exc)

    return result


def download_mte_instrument(result: dict) -> dict:
    """Download the instrument content from a localizado search result.

    If the result status_consulta is not "localizado" or no URL is available,
    returns the result unchanged. On CAPTCHA, block, or any network failure,
    updates status_consulta appropriately without attempting to bypass.

    Args:
        result: A result dict returned by search_mte_instrument().

    Returns:
        The result dict updated with _content (bytes) and _text (str) when
        download succeeds, or with an updated status_consulta on failure.
    """
    if result.get("status_consulta") != "localizado":
        return result
    url = result.get("url")
    if not url:
        return result

    rid = "(crawler)"
    try:
        import requests  # type: ignore[import]
    except ImportError:
        result["status_consulta"] = "erro"
        result["_error"] = "requests não instalado"
        return result

    logger.info("Baixando instrumento: %s", url)

    try:
        session = requests.Session()
        session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (compatible; MTE-crawler/1.0; "
                "+https://github.com/stefanini-applications/Atualizacao-de-sindicato)"
            ),
        })
        response = session.get(url, timeout=MTE_REQUEST_TIMEOUT, stream=True)

        if _detect_block(response.status_code, response.text[:2000]):
            logger.warning(
                "Bloqueio ao baixar instrumento %s (HTTP %d).",
                url,
                response.status_code,
            )
            result["status_consulta"] = "bloqueado"
            result["_error"] = f"download blocked: HTTP {response.status_code}"
            return result

        if response.status_code != 200:
            logger.warning(
                "HTTP %d ao baixar instrumento %s.", response.status_code, url
            )
            result["status_consulta"] = "erro"
            result["_error"] = f"download HTTP {response.status_code}"
            return result

        content_type = response.headers.get("Content-Type", "")
        raw_content = response.content

        if not raw_content:
            logger.warning("Conteúdo vazio ao baixar instrumento: %s", url)
            result["status_consulta"] = "nao_localizado"
            return result

        result["_content"] = raw_content
        result["_content_type"] = content_type

        # Extract inline text for HTML responses
        if "text/html" in content_type:
            result["_text"] = _extract_text_from_html(response.text)

        logger.info(
            "Download concluído: %d bytes (tipo: %s)", len(raw_content), content_type
        )

    except requests.exceptions.Timeout:
        logger.warning("Timeout ao baixar instrumento %s.", url)
        result["status_consulta"] = "erro"
        result["_error"] = "download timeout"
    except requests.exceptions.ConnectionError as exc:
        logger.warning("Erro de conexão ao baixar instrumento %s: %s", url, exc)
        result["status_consulta"] = "erro"
        result["_error"] = f"download connection error: {exc}"
    except Exception as exc:  # noqa: BLE001
        logger.warning("Erro inesperado ao baixar instrumento %s: %s", url, exc)
        result["status_consulta"] = "erro"
        result["_error"] = str(exc)

    return result


def extract_mte_text_or_pdf(result: dict) -> dict | None:
    """Extract eligible CCT fields from a downloaded MTE instrument.

    Uses parse_mte_instrumento.parse_mte_pdf() for PDF content and a
    lightweight HTML parser for HTML content. Returns a dict compatible
    with enrich_from_mte_fallback's instrumento_mte format.

    AC2: Only returns data when at least one field has fonte_textual populated.
    Returns None when:
      - result is not localizado
      - no content was downloaded
      - parse_mte_instrumento cannot extract any fields
      - no field has fonte_textual evidence

    Args:
        result: A result dict updated by download_mte_instrument().

    Returns:
        An instrumento_mte-compatible dict, or None.
    """
    if result.get("status_consulta") not in ("localizado",):
        return None

    content = result.get("_content")
    text = result.get("_text")
    content_type = result.get("_content_type", "")
    url = result.get("url")

    instrumento: dict | None = None

    # PDF content: delegate to parse_mte_instrumento
    if content and ("pdf" in content_type.lower() or _is_pdf_bytes(content)):
        instrumento = _parse_pdf_content(content, url)

    # HTML content: use extracted plain text
    elif text:
        instrumento = _parse_html_text(text, url)

    if instrumento is None:
        logger.info(
            "Nenhum campo elegível extraído do instrumento localizado em %s.", url
        )
        return None

    # AC2: verify at least one campo has fonte_textual populated
    campos = instrumento.get("campos") or {}
    campos_com_fonte = {
        k: v for k, v in campos.items()
        if isinstance(v, dict) and v.get("fonte_textual")
    }
    if not campos_com_fonte:
        logger.info(
            "Instrumento localizado mas nenhum campo contém fonte_textual — "
            "campos permanecem pendente_revisao (AC2)."
        )
        return None

    instrumento["campos"] = campos_com_fonte
    return instrumento


# ──────────────────────────────────────────────────────────────────────────────
# Helpers de parsing / extração
# ──────────────────────────────────────────────────────────────────────────────


def _extract_instrument_link(html: str, record: dict) -> tuple[str | None, str | None]:
    """Parse HTML search results to extract instrument URL and code.

    Returns (url, codigo_instrumento) or (None, None) when not found.
    """
    import re

    # Common patterns for instrument links in Sistema Mediador HTML
    # Patterns may match href attributes pointing to PDF documents or detail pages
    url_patterns = [
        # Direct PDF links
        r'href=["\']([^"\']*(?:\.pdf|instrumento|documento|CCT|ACT)[^"\']*)["\']',
        # Download links with numeric IDs
        r'href=["\']([^"\']*(?:DownloadArquivo|DownloadInstrumento)[^"\']*)["\']',
        # Generic instrument detail page
        r'href=["\']([^"\']*ConsultarInstColetivo[^"\']*(?:nr=|id=|codigo=)(\d+)[^"\']*)["\']',
    ]

    # Try to find an instrument URL in the HTML
    for pattern in url_patterns:
        matches = re.findall(pattern, html, re.IGNORECASE)
        if matches:
            first_match = matches[0]
            if isinstance(first_match, tuple):
                url_candidate = first_match[0]
                codigo_candidate = first_match[1] if len(first_match) > 1 else None
            else:
                url_candidate = first_match
                codigo_candidate = None

            # Resolve relative URLs
            if url_candidate.startswith("http"):
                return url_candidate, codigo_candidate
            elif url_candidate.startswith("/"):
                return f"https://www3.mte.gov.br{url_candidate}", codigo_candidate

    # Try to extract a numeric code from common result table patterns
    code_match = re.search(r'(?:NR|N[°º]|C[óo]digo)[:\s]+(\d{6,})', html, re.IGNORECASE)
    if code_match:
        codigo = code_match.group(1)
        # Build a URL using the known query pattern
        uf = record.get("uf", "")
        ano = str(record.get("ano_referencia", ""))
        constructed_url = (
            f"{MTE_MEDIADOR_BASE_URL}ConsultarInstColetivo"
            f"?CodUF={_UF_TO_COD.get(uf.upper(), '')}&AnoInstCo={ano}&nr={codigo}"
        )
        return constructed_url, codigo

    return None, None


def _is_pdf_bytes(content: bytes) -> bool:
    """Return True if content starts with PDF magic bytes."""
    return content[:4] == b"%PDF"


def _parse_pdf_content(content: bytes, url: str | None) -> dict | None:
    """Write PDF bytes to a temp file and parse with parse_mte_instrumento."""
    try:
        from parse_mte_instrumento import parse_mte_pdf  # type: ignore[import]
    except ImportError:
        logger.error(
            "parse_mte_instrumento não encontrado — PDF não processado. "
            "Verifique se parse_mte_instrumento.py está no diretório do projeto."
        )
        return None

    try:
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp_pdf:
            tmp_pdf.write(content)
            tmp_path = tmp_pdf.name

        instrumento = parse_mte_pdf(tmp_path)
        if instrumento and url:
            instrumento["url_documento"] = url
        return instrumento
    except Exception as exc:  # noqa: BLE001
        logger.error("Erro ao processar PDF do instrumento MTE: %s", exc)
        return None
    finally:
        try:
            os.unlink(tmp_path)
        except Exception:  # noqa: BLE001
            pass


def _extract_text_from_html(html: str) -> str:
    """Extract visible plain text from HTML using a lightweight regex approach."""
    import re

    # Remove script and style blocks
    html = re.sub(r"<(?:script|style)[^>]*>.*?</(?:script|style)>", " ", html, flags=re.DOTALL | re.IGNORECASE)
    # Remove HTML tags
    text = re.sub(r"<[^>]+>", " ", html)
    # Decode common HTML entities
    entities = {
        "&amp;": "&", "&lt;": "<", "&gt;": ">", "&quot;": '"',
        "&nbsp;": " ", "&apos;": "'", "&#231;": "ç", "&#227;": "ã",
        "&#245;": "õ", "&#224;": "à", "&#225;": "á", "&#234;": "ê",
        "&#233;": "é", "&#237;": "í", "&#243;": "ó", "&#250;": "ú",
    }
    for entity, char in entities.items():
        text = text.replace(entity, char)
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _parse_html_text(text: str, url: str | None) -> dict | None:
    """Parse plain text extracted from an HTML instrument page."""
    # Delegate to parse_mte_instrumento logic via its internal helpers
    try:
        from parse_mte_instrumento import (  # type: ignore[import]
            _FIELD_PATTERNS,
            _extract_metadata,
            _find_field_in_text,
        )
    except ImportError:
        logger.error(
            "parse_mte_instrumento não encontrado — texto HTML não processado."
        )
        return None

    if not text or len(text.strip()) < 100:
        return None

    meta = _extract_metadata(text)
    campos: dict[str, dict] = {}
    for field_name, config in _FIELD_PATTERNS.items():
        field_result = _find_field_in_text(text, field_name, config)
        if field_result is not None:
            campos[field_name] = field_result

    if not campos:
        return None

    return {
        "numero_registro": meta.get("numero_registro"),
        "tipo": meta.get("tipo", "instrumento"),
        "vigencia_inicio": meta.get("vigencia_inicio"),
        "vigencia_fim": meta.get("vigencia_fim"),
        "url_documento": url,
        "campos": campos,
    }


# ──────────────────────────────────────────────────────────────────────────────
# Pipeline de integração com enrich_mte_fallback
# ──────────────────────────────────────────────────────────────────────────────


def _process_record(record: dict) -> dict:
    """Run the full crawler pipeline for a single record.

    Returns a per-record summary dict for the auto-lookup report.
    """
    from enrich_mte_fallback import (  # type: ignore[import]
        _build_fonte_oficial_mte,
        _collect_field_changes,
        _set_fonte_oficial_mte,
        enrich_from_mte_fallback,
    )

    rid = record.get("id_registro_reajuste", "?")
    uf = record.get("uf", "")
    sindicato = record.get("sindicato", "")
    categoria = record.get("categoria", "")
    ano = record.get("ano_referencia")

    logger.info("── [%s] %s / %s / %s / %s", rid, uf, sindicato, categoria, ano)

    itens_before = copy.deepcopy(record.get("itens_cct", {}))

    # Step 1: search
    search_result = search_mte_instrument(record)
    status = search_result.get("status_consulta", "nao_localizado")

    # Step 2: download (only when localizado)
    if status == "localizado":
        search_result = download_mte_instrument(search_result)
        status = search_result.get("status_consulta", "nao_localizado")

    # Step 3: extract fields (only when still localizado with content)
    instrumento: dict | None = None
    if status == "localizado":
        instrumento = extract_mte_text_or_pdf(search_result)

    # Build fonte_oficial_mte block for this record
    fonte_data = _build_fonte_oficial_mte(
        tipo_referencia="crawler",
        url=search_result.get("url"),
        codigo_instrumento=search_result.get("codigo_instrumento"),
        status_consulta=status,
        observacao=(
            search_result.get("_error")
            if status in ("erro", "bloqueado")
            else None
        ),
    )
    # Override disponivel: only True when the instrument was actually found
    fonte_data["disponivel"] = search_result.get("disponivel", False)
    _set_fonte_oficial_mte(record, fonte_data)

    # Step 4: enrich fields (only when instrumento has campos with fonte_textual)
    rec_metrics: dict = {
        "preenchidos_mte": 0,
        "pendentes": 0,
        "conflitos": 0,
        "preenchidos_piso_nacional": 0,
    }
    if instrumento is not None:
        rec_metrics = enrich_from_mte_fallback(
            record=record,
            instrumento_mte=instrumento,
        )

    # Collect field changes for the report
    itens_after = record.get("itens_cct", {})
    filled, pending, conflict = _collect_field_changes(itens_before, itens_after)

    per_record_report = {
        "registro_id": rid,
        "uf": uf,
        "sindicato": sindicato,
        "categoria": categoria,
        "ano": ano,
        "status_busca": status,
        "url_localizada": search_result.get("url"),
        "codigo_instrumento": search_result.get("codigo_instrumento"),
        "campos_preenchidos": filled,
        "campos_pendentes": pending,
        "campos_conflito": conflict,
        "observacao": search_result.get("_error") if status in ("erro", "bloqueado") else None,
        "_metrics": rec_metrics,
    }

    logger.info(
        "  [%s] status=%s preenchidos=%d pendentes=%d conflitos=%d",
        rid,
        status,
        rec_metrics["preenchidos_mte"],
        rec_metrics["pendentes"],
        rec_metrics["conflitos"],
    )

    return per_record_report


def run_auto_lookup(
    json_path: str = JSON_PATH,
    dry_run: bool = False,
    pending_only: bool = True,
    ids: list[str] | None = None,
    report_dir: str = REPORTS_DIR,
) -> dict:
    """Run the automated MTE instrument lookup pipeline.

    Loads base_parametros_sindicais.json, filters records as requested,
    runs the crawler for each record, integrates enrichment results, and
    persists changes only when real data is found (AC3).

    Args:
        json_path:    Path to base_parametros_sindicais.json.
        dry_run:      If True, do not write any files (AC3).
        pending_only: If True, skip records without pendente_revisao fields.
        ids:          If provided, process only these record IDs.
        report_dir:   Directory for the auto-lookup report.

    Returns:
        Report dict (AC5) with global totals and per-record details.
    """
    logger.info("═══════════════════════════════════════════════════════")
    logger.info("Iniciando busca automática MTE (PRJ-68 / mte_crawler)")
    logger.info("dry_run=%s  pending_only=%s  ids=%s", dry_run, pending_only, ids)
    logger.info("═══════════════════════════════════════════════════════")

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    records = data.get("registros", [])
    id_filter = set(ids) if ids else None

    totais = {
        "registros_avaliados": 0,
        "instrumentos_localizados": 0,
        "instrumentos_nao_localizados": 0,
        "instrumentos_com_erro": 0,
        "instrumentos_bloqueados": 0,
        "campos_preenchidos": 0,
        "campos_pendentes": 0,
        "campos_conflito": 0,
        "campos_piso_nacional": 0,
        "arquivos_atualizados": False,
    }
    detalhes: list[dict] = []
    any_real_data = False
    any_status_change = False

    for record in records:
        rid = record.get("id_registro_reajuste", "?")

        if id_filter and rid not in id_filter:
            continue

        if pending_only and not _has_pending_fields(record):
            logger.debug("[%s] Sem campos pendentes — ignorado (--pending-only).", rid)
            continue

        totais["registros_avaliados"] += 1
        per_record = _process_record(record)

        status = per_record["status_busca"]
        if status == "localizado":
            totais["instrumentos_localizados"] += 1
            any_status_change = True
        elif status == "erro":
            totais["instrumentos_com_erro"] += 1
            any_status_change = True
        elif status == "bloqueado":
            totais["instrumentos_bloqueados"] += 1
            any_status_change = True
        else:
            totais["instrumentos_nao_localizados"] += 1

        m = per_record.get("_metrics", {})
        totais["campos_preenchidos"] += m.get("preenchidos_mte", 0)
        totais["campos_pendentes"] += m.get("pendentes", 0)
        totais["campos_conflito"] += m.get("conflitos", 0)
        totais["campos_piso_nacional"] += m.get("preenchidos_piso_nacional", 0)

        if m.get("preenchidos_mte", 0) > 0 or m.get("conflitos", 0) > 0:
            any_real_data = True

        # Remove internal metrics key before including in report
        detail = {k: v for k, v in per_record.items() if k != "_metrics"}
        detalhes.append(detail)

    # AC3: persist only when real data found or status was registered
    should_write = any_real_data or any_status_change

    if should_write and not dry_run:
        import subprocess
        logger.info("Dados ou status registrados — gravando base.")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info("JSON gravado: %s", json_path)
        try:
            result = subprocess.run(
                [sys.executable, EXPORT_SCRIPT],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0:
                logger.info("JS exportado com sucesso.")
            else:
                logger.error("Erro ao exportar JS: %s", result.stderr.strip())
        except Exception as exc:  # noqa: BLE001
            logger.error("Falha ao invocar export_inline_data.py: %s", exc)
        totais["arquivos_atualizados"] = True
    elif should_write and dry_run:
        logger.info("[dry-run] Dados/status encontrados — nenhum arquivo gravado.")
    else:
        logger.info(
            "Nenhum dado real encontrado. "
            "base_parametros_sindicais.json e .js NÃO foram modificados."
        )

    report = {
        "data_execucao": _today(),
        "dry_run": dry_run,
        "pending_only": pending_only,
        "totais": totais,
        "detalhes": detalhes,
    }

    _print_auto_lookup_report(report)

    # AC5: save report (never in dry_run)
    if not dry_run:
        os.makedirs(report_dir, exist_ok=True)
        report_path = os.path.join(report_dir, REPORT_FILENAME)
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        logger.info("Relatório gravado em: %s", report_path)
    else:
        logger.info("[dry-run] Relatório NÃO gravado em disco.")

    return report


def _print_auto_lookup_report(report: dict) -> None:
    """Print the auto-lookup report to the terminal."""
    sep = "═" * 60
    t = report["totais"]
    logger.info(sep)
    logger.info("RELATÓRIO DE BUSCA AUTOMÁTICA MTE (PRJ-68)")
    if report.get("dry_run"):
        logger.info("  *** MODO DRY-RUN — nenhum arquivo foi gravado ***")
    logger.info(sep)
    logger.info("  Registros avaliados:             %d", t["registros_avaliados"])
    logger.info("  Instrumentos localizados:        %d", t["instrumentos_localizados"])
    logger.info("  Instrumentos não localizados:    %d", t["instrumentos_nao_localizados"])
    logger.info("  Instrumentos com erro:           %d", t["instrumentos_com_erro"])
    logger.info("  Instrumentos bloqueados:         %d", t["instrumentos_bloqueados"])
    logger.info(sep)
    logger.info("  Campos preenchidos via MTE:      %d", t["campos_preenchidos"])
    logger.info("  Campos pendentes:                %d", t["campos_pendentes"])
    logger.info("  Campos em conflito:              %d", t["campos_conflito"])
    logger.info("  Campos (Piso Nacional):          %d", t["campos_piso_nacional"])
    logger.info(sep)
    logger.info("  Arquivos JSON/JS atualizados:    %s", "sim" if t["arquivos_atualizados"] else "não")
    logger.info(sep)

    for detail in report.get("detalhes", []):
        rid = detail.get("registro_id", "?")
        status = detail.get("status_busca", "?")
        url = detail.get("url_localizada") or "—"
        filled = detail.get("campos_preenchidos") or []
        pending = detail.get("campos_pendentes") or []
        conflict = detail.get("campos_conflito") or []
        obs = detail.get("observacao")

        logger.info("  ┌─ %s", rid)
        logger.info("  │  status: %-20s  url: %s", status, url)
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
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--pending-only",
        action="store_true",
        default=True,
        help=(
            "Processa apenas registros com campos pendente_revisao "
            "(padrão: ativado). Use --no-pending-only para desabilitar."
        ),
    )
    parser.add_argument(
        "--no-pending-only",
        dest="pending_only",
        action="store_false",
        help="Processa todos os registros independentemente de campos pendentes.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Exibe o que seria alterado sem gravar nenhum arquivo.",
    )
    parser.add_argument(
        "--ids",
        nargs="+",
        metavar="ID",
        help="Processa apenas os registros com os IDs informados.",
    )
    parser.add_argument(
        "--json-path",
        metavar="PATH",
        default=JSON_PATH,
        help=f"Caminho para base_parametros_sindicais.json (padrão: {JSON_PATH}).",
    )
    args = parser.parse_args()

    run_auto_lookup(
        json_path=args.json_path,
        dry_run=args.dry_run,
        pending_only=args.pending_only,
        ids=args.ids,
    )
    sys.exit(0)


if __name__ == "__main__":
    main()

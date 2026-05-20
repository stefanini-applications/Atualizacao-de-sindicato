"""Serviço de extração estruturada de reajustes salariais e vigências das CCTs.

Lê cláusulas candidatas do tipo ``reajuste_salarial`` e ``vigencia_data_base``
e extrai — por padrões textuais (regex e extenso) — percentual de reajuste,
data-base, vigência inicial e vigência final.  Datas são normalizadas para ISO
``YYYY-MM-DD``; campos não encontrados são persistidos como ``None`` (AC2).

O status da extração é atribuído por tipo de cláusula (AC3):
  - ``reajuste_salarial``:   avalia apenas ``percentual_reajuste``
  - ``vigencia_data_base``:  avalia ``data_base``, ``vigencia_inicio``,
                             ``vigencia_fim`` — usando detecção de campos
                             esperados no trecho para não penalizar registros
                             válidos por ausência de campos que não lhes
                             pertencem.
"""

import re
import traceback
from datetime import date as date_type, datetime, timezone
from typing import List, Optional, Tuple

from src.models.clausula_candidata import ClausulaCandidata
from src.models.reajuste_extraido import ReajusteExtraido
from src.utils.text_normalizer import normalizar

_METODO = "regex_pattern_match"
_TIPOS_ESCOPO: frozenset = frozenset(["reajuste_salarial", "vigencia_data_base"])

# ---------------------------------------------------------------------------
# Mês → número
# ---------------------------------------------------------------------------

_MESES: dict = {
    "janeiro": 1, "fevereiro": 2, "marco": 3, "abril": 4,
    "maio": 5, "junho": 6, "julho": 7, "agosto": 8,
    "setembro": 9, "outubro": 10, "novembro": 11, "dezembro": 12,
}

# ---------------------------------------------------------------------------
# Números por extenso para percentuais
# ---------------------------------------------------------------------------

_EXTENSO_MAP: dict = {
    "zero": "0", "um": "1", "uma": "1", "dois": "2", "duas": "2",
    "tres": "3", "quatro": "4", "cinco": "5", "seis": "6",
    "sete": "7", "oito": "8", "nove": "9", "dez": "10",
    "onze": "11", "doze": "12", "treze": "13", "quatorze": "14",
    "catorze": "14", "quinze": "15", "dezesseis": "16",
    "dezessete": "17", "dezoito": "18", "dezenove": "19",
    "vinte": "20", "trinta": "30", "quarenta": "40",
    "cinquenta": "50", "sessenta": "60", "setenta": "70",
    "oitenta": "80", "noventa": "90", "cem": "100", "cento": "100",
}

# ---------------------------------------------------------------------------
# Padrões compilados — percentuais
# ---------------------------------------------------------------------------

# Numérico: "5%", "5,00%", "5.00%", "5 por cento", "5,00 por cento"
# Nota: % não é um caractere de palavra, então \b depois de % falharia; usa (?!\d) em vez disso.
_RE_PERCENT_NUMERIC = re.compile(
    r'\b(\d{1,3}(?:[.,]\d{1,2})?)\s*(?:%(?!\d)|por\s+cento\b)',
    re.IGNORECASE,
)

# Extenso: "cinco por cento", "vinte e cinco por cento", etc.
# Sorted longest-first to avoid prefix ambiguity.
_EXTENSO_WORDS = sorted(_EXTENSO_MAP.keys(), key=len, reverse=True)
_RE_PERCENT_EXTENSO = re.compile(
    r'\b(' + '|'.join(_EXTENSO_WORDS) + r')\s+por\s+cento\b',
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Padrões compilados — datas
# ---------------------------------------------------------------------------

# DD/MM/YYYY ou D/MM/YYYY
_RE_DATE_SLASH = re.compile(r'(?<!\d)(\d{1,2})/(\d{2})/(\d{4})(?!\d)')

# "1º de maio de 2025" / "01 de maio de 2025" / "1 de maio 2025"
# º (U+00BA) é preservado pela normalização (não é marca de acento)
_RE_DATE_EXTENSO = re.compile(
    r'(?<!\d)(\d{1,2})[°oº]?\s+de\s+(\w+)(?:\s+de)?\s+(\d{4})(?!\d)',
    re.IGNORECASE,
)

# Conectores de intervalo de datas (após normalização)
_RE_RANGE_CONNECTOR = re.compile(r'\b(?:a|ate|ao)\b')

# Padrão textual de data (não valida a data, apenas detecta a forma) para
# identificar indicadores de intervalo com datas potencialmente inválidas.
_RE_DATE_LIKE = re.compile(
    r'(?:\d{1,2}/\d{2}/\d{4}|\d{1,2}[°oº]?\s+de\s+\w+(?:\s+de)?\s+\d{4})',
    re.IGNORECASE,
)

# Indicadores de vigência no texto normalizado
_RE_VIGENCIA_IND = re.compile(r'\b(?:vigencia|periodo|prazo)\b')

# ---------------------------------------------------------------------------
# Helpers de parse de data
# ---------------------------------------------------------------------------


def _parse_date_slash(m: re.Match) -> Optional[str]:
    try:
        return date_type(int(m.group(3)), int(m.group(2)), int(m.group(1))).isoformat()
    except ValueError:
        return None


def _parse_date_extenso(m: re.Match) -> Optional[str]:
    mes_str = normalizar(m.group(2))
    mes_num = _MESES.get(mes_str)
    if not mes_num:
        return None
    try:
        return date_type(int(m.group(3)), mes_num, int(m.group(1))).isoformat()
    except ValueError:
        return None


def _encontrar_datas(texto_norm: str) -> List[Tuple[int, int, str]]:
    """Retorna lista de (inicio, fim, iso_date) para cada data válida no texto."""
    resultados: List[Tuple[int, int, str]] = []
    visto: set = set()

    for m in _RE_DATE_SLASH.finditer(texto_norm):
        iso = _parse_date_slash(m)
        if iso and m.start() not in visto:
            resultados.append((m.start(), m.end(), iso))
            visto.add(m.start())

    for m in _RE_DATE_EXTENSO.finditer(texto_norm):
        iso = _parse_date_extenso(m)
        if iso and m.start() not in visto:
            resultados.append((m.start(), m.end(), iso))
            visto.add(m.start())

    resultados.sort(key=lambda t: t[0])
    return resultados

# ---------------------------------------------------------------------------
# Extração de percentual
# ---------------------------------------------------------------------------


def _extrair_percentual(trecho: str) -> Optional[str]:
    """Extrai o primeiro percentual encontrado no trecho (original e extenso)."""
    # Tenta no texto original para preservar formatação ("5,00%")
    m = _RE_PERCENT_NUMERIC.search(trecho)
    if m:
        return m.group(0).strip()
    # Tenta extenso no texto normalizado
    trecho_norm = normalizar(trecho)
    m = _RE_PERCENT_EXTENSO.search(trecho_norm)
    if m:
        return m.group(0).strip()
    return None

# ---------------------------------------------------------------------------
# Extração de campos de vigência
# ---------------------------------------------------------------------------


def _campos_esperados_vigencia(
    texto_norm: str,
    all_date_matches: List[Tuple[int, int, str]],
) -> frozenset:
    """Detecta quais campos-alvo estão referenciados no trecho para avaliar status."""
    expected: set = set()

    if "data base" in texto_norm:
        expected.add("data_base")

    has_vigencia = bool(_RE_VIGENCIA_IND.search(texto_norm))
    if has_vigencia:
        expected.add("vigencia_inicio")
        # Espera vigencia_fim se houver dois padrões de data (mesmo inválidas)
        # com conector de intervalo entre elas.
        raw_date_matches = list(_RE_DATE_LIKE.finditer(texto_norm))
        for i in range(len(raw_date_matches) - 1):
            between = texto_norm[raw_date_matches[i].end():raw_date_matches[i + 1].start()]
            if _RE_RANGE_CONNECTOR.search(between):
                expected.add("vigencia_fim")
                break

    return frozenset(expected)


def _extrair_campos_vigencia(
    trecho: str,
) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """Extrai data_base, vigencia_inicio e vigencia_fim do trecho.

    Usa posição dos padrões de data no texto normalizado para determinar
    qual data corresponde a qual campo.
    """
    texto_norm = normalizar(trecho)
    all_dates = _encontrar_datas(texto_norm)

    data_base: Optional[str] = None
    vigencia_inicio: Optional[str] = None
    vigencia_fim: Optional[str] = None

    if not all_dates:
        return data_base, vigencia_inicio, vigencia_fim

    used_indices: set = set()

    # Extrai data_base: "data base" + primeira data em janela de 100 chars
    if "data base" in texto_norm:
        db_keyword_pos = texto_norm.find("data base")
        for idx, (start, end, iso) in enumerate(all_dates):
            if db_keyword_pos <= start <= db_keyword_pos + 100:
                data_base = iso
                used_indices.add(idx)
                break

    # Extrai vigencia_inicio e vigencia_fim: par de datas com conector de intervalo
    has_vigencia = bool(_RE_VIGENCIA_IND.search(texto_norm))
    remaining = [
        (idx, start, end, iso)
        for idx, (start, end, iso) in enumerate(all_dates)
        if idx not in used_indices
    ]

    if has_vigencia and remaining:
        found_range = False
        for i, (idx1, start1, end1, iso1) in enumerate(remaining):
            for _idx2, start2, _end2, iso2 in remaining[i + 1:]:
                between = texto_norm[end1:start2]
                if _RE_RANGE_CONNECTOR.search(between):
                    vigencia_inicio = iso1
                    vigencia_fim = iso2
                    found_range = True
                    break
            if found_range:
                break

        if not found_range:
            vigencia_inicio = remaining[0][3]
    elif not has_vigencia and not used_indices and all_dates:
        # Sem indicador de vigência e data_base não capturada:
        # única data disponível vai para data_base se "data base" aparece de qualquer forma
        # (já tratado acima). Caso contrário, deixa campos como None.
        pass

    return data_base, vigencia_inicio, vigencia_fim

# ---------------------------------------------------------------------------
# Avaliação de status por tipo de cláusula
# ---------------------------------------------------------------------------


def _status_reajuste(percentual: Optional[str]) -> str:
    return "extraido_com_sucesso" if percentual is not None else "dados_nao_identificados"


def _status_vigencia(
    data_base: Optional[str],
    vigencia_inicio: Optional[str],
    vigencia_fim: Optional[str],
    texto_norm: str,
    all_date_matches: List[Tuple[int, int, str]],
) -> str:
    extracted = frozenset(
        f for f, v in [
            ("data_base", data_base),
            ("vigencia_inicio", vigencia_inicio),
            ("vigencia_fim", vigencia_fim),
        ]
        if v is not None
    )

    if not extracted:
        return "dados_nao_identificados"

    expected = _campos_esperados_vigencia(texto_norm, all_date_matches)

    # Se não há indicadores estruturais claros ou todos os campos esperados
    # foram extraídos → sucesso
    if not expected or extracted >= expected:
        return "extraido_com_sucesso"

    return "parcialmente_extraido"

# ---------------------------------------------------------------------------
# Função principal de extração
# ---------------------------------------------------------------------------


def extrair_reajustes(
    clausulas: List[ClausulaCandidata],
) -> List[ReajusteExtraido]:
    """Extrai dados estruturados das cláusulas no escopo (AC1, AC2, AC3).

    Filtra apenas ``reajuste_salarial`` e ``vigencia_data_base``; demais tipos
    são ignorados (não geram registros na saída).
    """
    resultados: List[ReajusteExtraido] = []
    agora = datetime.now(tz=timezone.utc).isoformat()

    for clausula in clausulas:
        if clausula.tipo_clausula not in _TIPOS_ESCOPO:
            continue

        percentual: Optional[str] = None
        data_base: Optional[str] = None
        vigencia_inicio: Optional[str] = None
        vigencia_fim: Optional[str] = None
        status: str

        try:
            if clausula.tipo_clausula == "reajuste_salarial":
                percentual = _extrair_percentual(clausula.trecho)
                status = _status_reajuste(percentual)

            else:  # vigencia_data_base
                data_base, vigencia_inicio, vigencia_fim = _extrair_campos_vigencia(
                    clausula.trecho
                )
                texto_norm = normalizar(clausula.trecho)
                all_dates = _encontrar_datas(texto_norm)
                status = _status_vigencia(
                    data_base, vigencia_inicio, vigencia_fim, texto_norm, all_dates
                )

        except Exception:
            status = "erro_extracao"
            percentual = None
            data_base = None
            vigencia_inicio = None
            vigencia_fim = None

        resultados.append(ReajusteExtraido(
            caminho=clausula.caminho,
            nome_arquivo=clausula.nome_arquivo,
            uf=clausula.uf,
            sindicato=clausula.sindicato,
            tipo_documento=clausula.tipo_documento,
            ano_referencia=clausula.ano_referencia,
            origem_texto=clausula.origem_texto,
            tipo_clausula=clausula.tipo_clausula,
            trecho_original=clausula.trecho,
            percentual_reajuste=percentual,
            data_base=data_base,
            vigencia_inicio=vigencia_inicio,
            vigencia_fim=vigencia_fim,
            status_extracao_estruturada=status,
            metodo_extracao=_METODO,
            data_hora_processamento=agora,
        ))

    return resultados

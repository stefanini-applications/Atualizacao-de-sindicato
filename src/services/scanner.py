"""Varredura da estrutura de pastas CCT/<UF>/<sindicato>/ para
reconhecimento automático de documentos sindicais.

Reconhece automaticamente UF e sindicato a partir do caminho do arquivo,
infere tipo_documento e ano_referencia a partir do nome do arquivo.
"""

import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from src.models.documento import DocumentoSindical, UFS_VALIDAS


# ── Inferência de tipo de documento ──────────────────────────────────────────

_PATTERN_ADITIVO = re.compile(r'(?<![A-Za-z])aditivo(?![A-Za-z])', re.IGNORECASE)
_PATTERN_ACORDO = re.compile(r'acordo\s+coletivo', re.IGNORECASE)
# ACT = Acordo Coletivo de Trabalho; evita falsos positivos em palavras longas
_PATTERN_ACT = re.compile(r'(?<![A-Za-z])ACT(?![A-Za-z])')
_PATTERN_CCT = re.compile(r'(?<![A-Za-z])CCT(?![A-Za-z])')


def _inferir_tipo(nome: str) -> str:
    """Infere o tipo de documento a partir do nome do arquivo."""
    if _PATTERN_ADITIVO.search(nome):
        return "termo aditivo"
    if _PATTERN_ACORDO.search(nome):
        return "acordo coletivo"
    if _PATTERN_ACT.search(nome):
        # ACT = Acordo Coletivo de Trabalho
        return "acordo coletivo"
    if _PATTERN_CCT.search(nome):
        return "CCT"
    return "outro documento sindical"


# ── Inferência de ano de referência ──────────────────────────────────────────

_PATTERN_ANO_RANGE_SEP = re.compile(r'(20\d{2})[_\-](20\d{2})')
_PATTERN_ANO_UNICO = re.compile(r'(20\d{2})')


def _inferir_anos(nome: str):
    """Retorna (ano_referencia, vigencia_inicial, vigencia_final)."""
    match_range = _PATTERN_ANO_RANGE_SEP.search(nome)
    if match_range:
        inicio, fim = match_range.group(1), match_range.group(2)
        return f"{inicio}-{fim}", inicio, fim

    match_unico = _PATTERN_ANO_UNICO.search(nome)
    if match_unico:
        ano = match_unico.group(1)
        return ano, ano, None

    return None, None, None


# ── Inferência de sindicato a partir do nome do arquivo ──────────────────────

# Padrão: palavras que seguem o ano (ex: "Sindpd-AP", "SINTTEL RJ", "Senalba-MG")
_PATTERN_SIND_NO_NOME = re.compile(
    r'(?:20\d{2}[_\-]20\d{2}|20\d{2})[_\-\s]+([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ0-9\-\s]+?)(?:\s*[\(\.]|$)',
    re.IGNORECASE,
)


def _inferir_sindicato_do_nome(nome_sem_ext: str) -> Optional[str]:
    """Tenta extrair nome de sindicato do nome do arquivo como fallback."""
    match = _PATTERN_SIND_NO_NOME.search(nome_sem_ext)
    if match:
        candidato = match.group(1).strip()
        # Remove sufixo de UF (ex: "-SP", "-AP", " RJ")
        candidato = re.sub(r'[-\s][A-Z]{2}$', '', candidato).strip()
        if len(candidato) >= 3:
            return candidato
    return None


# ── Scanner principal ─────────────────────────────────────────────────────────

def _caminho_relativo(caminho_abs: Path, raiz: Path) -> str:
    """Retorna caminho relativo POSIX a partir da raiz."""
    return caminho_abs.relative_to(raiz).as_posix()


def _criar_documento(
    caminho_abs: Path,
    raiz: Path,
    uf: Optional[str],
    sindicato: Optional[str],
    responsavel: Optional[str],
) -> DocumentoSindical:
    """Cria um DocumentoSindical a partir das informações do arquivo."""
    nome = caminho_abs.name
    nome_sem_ext = caminho_abs.stem
    caminho_rel = _caminho_relativo(caminho_abs, raiz)

    tipo = _inferir_tipo(nome)
    ano_ref, vig_ini, vig_fim = _inferir_anos(nome_sem_ext)

    # Fallback: tenta inferir sindicato do nome do arquivo quando não veio do path
    sindicato_efetivo = sindicato
    if not sindicato_efetivo:
        sindicato_efetivo = _inferir_sindicato_do_nome(nome_sem_ext)

    # Status inicial: sempre "pendente de validação" para novos documentos
    # (o validador confirmará ou manterá conforme campos críticos)
    status = "pendente de validação"

    return DocumentoSindical(
        id=str(uuid.uuid4()),
        nome_arquivo=nome,
        caminho=caminho_rel,
        uf=uf,
        sindicato=sindicato_efetivo,
        tipo_documento=tipo,
        ano_referencia=ano_ref,
        status=status,
        data_inclusao=datetime.now(timezone.utc).isoformat(),
        responsavel=responsavel,
        vigencia_inicial=vig_ini,
        vigencia_final=vig_fim,
    )


def varrer_pasta_cct(
    cct_dir: Path,
    raiz: Path,
    responsavel: Optional[str] = None,
) -> List[DocumentoSindical]:
    """Varre a estrutura CCT/<UF>/<sindicato>/ e retorna lista de DocumentoSindical.

    Reconhece automaticamente UF e sindicato a partir da hierarquia de pastas.
    Lida com casos em que o PDF está diretamente em CCT/<UF>/ sem subpasta de sindicato.
    """
    documentos: List[DocumentoSindical] = []

    for entrada in sorted(cct_dir.iterdir()):
        if not entrada.is_dir():
            continue

        uf_candidato = entrada.name
        uf = uf_candidato if uf_candidato in UFS_VALIDAS else None

        for item in sorted(entrada.iterdir()):
            if item.is_file():
                # Arquivo diretamente em CCT/<UF>/ — sem subpasta de sindicato
                if item.suffix.lower() == '.pdf':
                    doc = _criar_documento(item, raiz, uf, None, responsavel)
                    documentos.append(doc)

            elif item.is_dir():
                sindicato = item.name

                for arquivo in sorted(item.iterdir()):
                    if arquivo.is_file() and arquivo.suffix.lower() == '.pdf':
                        doc = _criar_documento(arquivo, raiz, uf, sindicato, responsavel)
                        documentos.append(doc)

    return documentos

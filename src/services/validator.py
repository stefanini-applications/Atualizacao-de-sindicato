"""Validação de documentos sindicais.

Separa claramente dois grupos de regras:
  - Campos críticos (UF, sindicato, tipo_documento): ausência ou valor inválido
    bloqueia o uso do documento em extrações automáticas e força status
    'pendente de validação'.
  - Campos esperados de cadastro (demais): ausência gera sinalização de
    incompletude mas não impede salvamento nem extração.
"""

from typing import List, TYPE_CHECKING

if TYPE_CHECKING:
    from src.models.documento import DocumentoSindical

from src.models.documento import (
    CAMPOS_CRITICOS,
    CAMPOS_ESPERADOS,
    TIPOS_VALIDOS,
    UFS_VALIDAS,
)


def campos_criticos_ausentes_ou_invalidos(doc: "DocumentoSindical") -> List[str]:
    """Retorna lista de campos críticos ausentes ou com valor inválido."""
    problemas: List[str] = []

    if not doc.uf:
        problemas.append("uf (ausente)")
    elif doc.uf not in UFS_VALIDAS:
        problemas.append(f"uf (inválido: '{doc.uf}')")

    if not doc.sindicato:
        problemas.append("sindicato (ausente)")

    if not doc.tipo_documento:
        problemas.append("tipo_documento (ausente)")
    elif doc.tipo_documento not in TIPOS_VALIDOS:
        problemas.append(f"tipo_documento (inválido: '{doc.tipo_documento}')")

    return problemas


def valido_para_extracao(doc: "DocumentoSindical") -> bool:
    """Retorna True somente quando todos os campos críticos estão presentes e válidos."""
    return len(campos_criticos_ausentes_ou_invalidos(doc)) == 0


def campos_incompletos(doc: "DocumentoSindical") -> List[str]:
    """Retorna campos esperados de cadastro que estão ausentes (não críticos)."""
    nao_criticos = [c for c in CAMPOS_ESPERADOS if c not in CAMPOS_CRITICOS]
    return [c for c in nao_criticos if not getattr(doc, c, None)]


def status_obrigatorio(doc: "DocumentoSindical") -> str:
    """Retorna o status que o documento deve ter com base na validação dos campos críticos."""
    if campos_criticos_ausentes_ou_invalidos(doc):
        return "pendente de validação"
    return doc.status

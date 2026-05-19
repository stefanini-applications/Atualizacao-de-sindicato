"""Relatório consolidado de documentos sindicais.

Exibe lista com colunas: UF, Sindicato, Tipo, Nome do Arquivo,
Ano Ref., Status, Caminho — conforme AC3.
"""

from typing import List, Optional, Dict

from src.models.documento import DocumentoSindical, STATUS_VALIDOS
from src.services.validator import (
    valido_para_extracao,
    campos_incompletos,
    campos_criticos_ausentes_ou_invalidos,
)

# Marcadores visuais
_OK = "✓"
_WARN = "⚠"
_ERR = "✗"


def _truncar(texto: Optional[str], largura: int) -> str:
    if not texto:
        return "—"
    if len(texto) <= largura:
        return texto
    return texto[: largura - 1] + "…"


def _linha(doc: DocumentoSindical, col_widths: List[int]) -> str:
    valido = valido_para_extracao(doc)
    incompleto = bool(campos_incompletos(doc))

    if not valido:
        indicador = _ERR
    elif incompleto:
        indicador = _WARN
    else:
        indicador = _OK

    colunas = [
        indicador,
        _truncar(doc.uf, col_widths[0]),
        _truncar(doc.sindicato, col_widths[1]),
        _truncar(doc.tipo_documento, col_widths[2]),
        _truncar(doc.nome_arquivo, col_widths[3]),
        _truncar(doc.ano_referencia, col_widths[4]),
        _truncar(doc.status, col_widths[5]),
        _truncar(doc.caminho, col_widths[6]),
    ]

    return "  ".join(
        col.ljust(w) if i > 0 else col
        for i, (col, w) in enumerate(zip(colunas, [2] + col_widths))
    )


def imprimir_lista(
    documentos: List[DocumentoSindical],
    apenas_invalidos: bool = False,
    apenas_incompletos: bool = False,
) -> None:
    """Imprime a lista consolidada de documentos no terminal."""
    filtrados = documentos

    if apenas_invalidos:
        filtrados = [d for d in filtrados if not valido_para_extracao(d)]
    elif apenas_incompletos:
        filtrados = [d for d in filtrados if campos_incompletos(d)]

    if not filtrados:
        print("Nenhum documento encontrado com os filtros aplicados.")
        return

    # Cabeçalhos
    headers = ["UF", "Sindicato", "Tipo", "Nome do Arquivo", "Ano Ref.", "Status", "Caminho"]
    col_widths = [4, 28, 22, 50, 9, 22, 55]

    separador = "  ".join("-" * w for w in [2] + col_widths)
    cabecalho = "  ".join(
        h.ljust(w) if i > 0 else h.ljust(2)
        for i, (h, w) in enumerate(zip([""] + headers, [2] + col_widths))
    )

    print(f"\nTotal: {len(filtrados)} documento(s)\n")
    print(cabecalho)
    print(separador)

    for doc in sorted(filtrados, key=lambda d: (d.uf or "", d.sindicato or "", d.nome_arquivo)):
        print(_linha(doc, col_widths))

    print()
    print(f"Legenda: {_OK} válido para extração  {_WARN} válido mas campos incompletos  {_ERR} inválido para extração")


def imprimir_resumo(documentos: List[DocumentoSindical]) -> None:
    """Imprime resumo estatístico do registro."""
    total = len(documentos)
    validos = sum(1 for d in documentos if valido_para_extracao(d))
    invalidos = total - validos
    incompletos = sum(1 for d in documentos if campos_incompletos(d))

    por_status: Dict[str, int] = {}
    for d in documentos:
        por_status[d.status] = por_status.get(d.status, 0) + 1

    por_uf: Dict[str, int] = {}
    for d in documentos:
        chave = d.uf or "(sem UF)"
        por_uf[chave] = por_uf.get(chave, 0) + 1

    print("\n=== Resumo do Registro ===")
    print(f"  Total de documentos : {total}")
    print(f"  Válidos p/ extração : {validos}")
    print(f"  Inválidos p/ extração: {invalidos}")
    print(f"  Com campos incompletos: {incompletos}")
    print()
    print("  Por status:")
    for status in sorted(STATUS_VALIDOS):
        n = por_status.get(status, 0)
        if n:
            print(f"    {status}: {n}")
    print()
    print("  Por UF:")
    for uf in sorted(por_uf):
        print(f"    {uf}: {por_uf[uf]}")
    print()

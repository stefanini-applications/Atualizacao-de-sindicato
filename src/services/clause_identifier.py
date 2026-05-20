"""Serviço de identificação de cláusulas candidatas nas CCTs consolidadas.

Para cada documento com texto disponível, percorre os segmentos textuais e
verifica correspondência com os termos-chave de cada categoria, após normalização
de texto (AC6). Cada correspondência (segmento × categoria) gera um registro
independente de ClausulaCandidata (AC2, AC3).
"""

from datetime import datetime, timezone
from typing import List

from src.models.clausula_candidata import ClausulaCandidata
from src.models.texto_extraido import TextoConsolidado
from src.utils.text_normalizer import normalizar

_METODO = "keyword_match_normalized"

# Termos-chave já em forma normalizada (minúsculas, sem acentos, hifens→espaço).
# Incluem variações de plural comuns para frases compostas (AC6).
_TERMOS_POR_CATEGORIA: dict = {
    "reajuste_salarial": [
        "reajuste",
        "reajustar",
        "correcao salarial",
        "correcoes salariais",
        "aumento salarial",
        "aumentos salariais",
        "salario normativo",
    ],
    "piso_salarial": [
        "piso salarial",
        "pisos salariais",
        "menor salario",
        "remuneracao minima",
    ],
    "vale_refeicao": [
        "vale refeicao",
        "vales refeicao",
        "auxilio refeicao",
    ],
    "vale_alimentacao": [
        "vale alimentacao",
        "vales alimentacao",
        "auxilio alimentacao",
    ],
    "beneficios": [
        "beneficios",
        "beneficio",
    ],
    "adicionais": [
        "adicional noturno",
        "hora extra",
        "horas extras",
        "periculosidade",
        "insalubridade",
    ],
    "plr": [
        "plr",
        "participacao nos lucros",
        "participacao nos lucros e resultados",
    ],
    "auxilio_home_office": [
        "auxilio home office",
    ],
    "vigencia_data_base": [
        "data base",
        "vigencia",
    ],
    "outros_remuneracao": [
        "remuneracao",
        "salario",
    ],
}

# Status que tornam o documento elegível para análise (AC1)
_STATUS_ELEGIVEIS = frozenset(["texto_nativo", "texto_ocr"])


def _segmentar_texto(texto: str) -> List[str]:
    """Divide o texto em segmentos (parágrafos) para análise individual."""
    segmentos = [s.strip() for s in texto.split("\n\n") if s.strip()]
    if len(segmentos) <= 1:
        segmentos = [s.strip() for s in texto.split("\n") if s.strip()]
    return segmentos


def _categorias_do_segmento(texto_normalizado: str) -> List[str]:
    """Retorna as categorias cujos termos-chave foram encontrados no texto normalizado."""
    categorias = []
    for categoria, termos in _TERMOS_POR_CATEGORIA.items():
        for termo in termos:
            if termo in texto_normalizado:
                categorias.append(categoria)
                break  # uma correspondência por categoria é suficiente
    return categorias


def identificar_clausulas(
    consolidados: List[TextoConsolidado],
) -> List[ClausulaCandidata]:
    """Identifica cláusulas candidatas em todos os documentos consolidados elegíveis.

    Retorna lista de ClausulaCandidata — pode haver múltiplos registros por documento.
    """
    clausulas: List[ClausulaCandidata] = []
    agora = datetime.now(tz=timezone.utc).isoformat()

    for doc in consolidados:
        if doc.status_consolidado not in _STATUS_ELEGIVEIS:
            continue

        if not doc.texto_final:
            continue

        segmentos = _segmentar_texto(doc.texto_final)

        for segmento in segmentos:
            texto_norm = normalizar(segmento)
            categorias = _categorias_do_segmento(texto_norm)

            for categoria in categorias:
                clausulas.append(ClausulaCandidata(
                    trecho=segmento,
                    caminho=doc.caminho,
                    nome_arquivo=doc.nome_arquivo,
                    uf=doc.uf,
                    sindicato=doc.sindicato,
                    tipo_documento=doc.tipo_documento,
                    ano_referencia=doc.ano_referencia,
                    origem_texto=doc.origem_texto,
                    status_consolidado=doc.status_consolidado,
                    tipo_clausula=categoria,
                    metodo_identificacao=_METODO,
                    data_hora_processamento=agora,
                ))

    return clausulas

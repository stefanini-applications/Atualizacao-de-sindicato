"""Serviço de consolidação textual dos documentos sindicais.

Combina a base de textos extraídos nativamente com a base de textos obtidos via OCR,
aplicando a regra de priorização: nativo > OCR > sem_texto_final.
"""

import sys
from datetime import datetime, timezone
from typing import List

from src.models.texto_extraido import TextoExtraido, TextoConsolidado


def consolidar_textos(
    nativos: List[TextoExtraido],
    ocr: List[TextoExtraido],
) -> List[TextoConsolidado]:
    """Consolida as bases nativa e OCR em uma única lista de registros.

    Regras de priorização (AC2):
      1. status nativo == 'extraido_com_sucesso' → origem texto_nativo
      2. status nativo == 'sem_texto_extraivel' e OCR status == 'extraido_via_ocr' → origem texto_ocr
      3. Demais → sem_texto_final

    Erros individuais de processamento resultam em status erro_consolidacao (AC3),
    sem interromper os demais documentos.
    """
    ocr_index = {t.caminho: t for t in ocr}
    agora = datetime.now(tz=timezone.utc).isoformat()
    resultado: List[TextoConsolidado] = []

    for doc in nativos:
        try:
            if doc.status == "extraido_com_sucesso":
                resultado.append(TextoConsolidado(
                    caminho=doc.caminho,
                    nome_arquivo=doc.nome_arquivo,
                    uf=doc.uf,
                    sindicato=doc.sindicato,
                    tipo_documento=doc.tipo_documento,
                    ano_referencia=doc.ano_referencia,
                    texto_final=doc.texto,
                    num_caracteres=doc.num_caracteres,
                    origem_texto="texto_nativo",
                    status_consolidado="texto_nativo",
                    data_consolidacao=agora,
                ))
            elif (
                doc.status == "sem_texto_extraivel"
                and doc.caminho in ocr_index
                and ocr_index[doc.caminho].status == "extraido_via_ocr"
            ):
                ocr_doc = ocr_index[doc.caminho]
                resultado.append(TextoConsolidado(
                    caminho=doc.caminho,
                    nome_arquivo=doc.nome_arquivo,
                    uf=doc.uf,
                    sindicato=doc.sindicato,
                    tipo_documento=doc.tipo_documento,
                    ano_referencia=doc.ano_referencia,
                    texto_final=ocr_doc.texto,
                    num_caracteres=ocr_doc.num_caracteres,
                    origem_texto="texto_ocr",
                    status_consolidado="texto_ocr",
                    data_consolidacao=agora,
                ))
            else:
                resultado.append(TextoConsolidado(
                    caminho=doc.caminho,
                    nome_arquivo=doc.nome_arquivo,
                    uf=doc.uf,
                    sindicato=doc.sindicato,
                    tipo_documento=doc.tipo_documento,
                    ano_referencia=doc.ano_referencia,
                    texto_final="",
                    num_caracteres=0,
                    origem_texto="sem_texto_final",
                    status_consolidado="sem_texto_final",
                    data_consolidacao=agora,
                ))
        except Exception as e:
            print(
                f"Erro ao consolidar '{getattr(doc, 'caminho', '<desconhecido>')}': {e}",
                file=sys.stderr,
            )
            resultado.append(TextoConsolidado(
                caminho=getattr(doc, "caminho", ""),
                nome_arquivo=getattr(doc, "nome_arquivo", ""),
                uf=getattr(doc, "uf", None),
                sindicato=getattr(doc, "sindicato", None),
                tipo_documento=getattr(doc, "tipo_documento", None),
                ano_referencia=getattr(doc, "ano_referencia", None),
                texto_final="",
                num_caracteres=0,
                origem_texto="erro_consolidacao",
                status_consolidado="erro_consolidacao",
                data_consolidacao=agora,
            ))

    return resultado

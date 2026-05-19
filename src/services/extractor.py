"""Extração de texto bruto a partir de PDFs de documentos sindicais.

Responsabilidades:
  - Tentar abrir cada PDF elegível e extrair texto página a página com pypdf.
  - Atribuir exatamente um dos cinco status de extração a cada documento.
  - Nunca lançar exceção não tratada; falhas de leitura são capturadas e registradas.

Status possíveis:
  extraido_com_sucesso    — texto (stripped) > 0 caracteres
  sem_texto_extraivel     — PDF abriu, páginas processadas, mas sem texto detectável (escaneado)
  erro_na_leitura         — falha ao abrir o PDF ou em todas as páginas
  documento_nao_encontrado — arquivo físico ausente no disco
  nao_elegivel_para_extracao — documento sem campos críticos válidos
"""

from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from src.models.documento import DocumentoSindical

from src.models.texto_extraido import TextoExtraido
from src.services.validator import valido_para_extracao

try:
    import pypdf
    _PYPDF_DISPONIVEL = True
except ImportError:
    _PYPDF_DISPONIVEL = False


def extrair_texto_pdf(pdf_path: Path) -> Tuple[str, str]:
    """Lê um PDF e retorna (texto_extraido, status).

    Trata falhas por arquivo e por página sem propagar exceções.
    """
    if not _PYPDF_DISPONIVEL:
        return "", "erro_na_leitura"

    if not pdf_path.exists():
        return "", "documento_nao_encontrado"

    try:
        reader = pypdf.PdfReader(str(pdf_path))
    except Exception:
        return "", "erro_na_leitura"

    partes: List[str] = []
    pagina_falhou = False

    for page in reader.pages:
        try:
            trecho = page.extract_text() or ""
            partes.append(trecho)
        except Exception:
            pagina_falhou = True

    texto_completo = "\n".join(partes)

    if texto_completo.strip():
        return texto_completo, "extraido_com_sucesso"
    elif pagina_falhou:
        return "", "erro_na_leitura"
    else:
        return "", "sem_texto_extraivel"


def processar_extracao(
    registro: Dict[str, "DocumentoSindical"],
    raiz: Path,
) -> List[TextoExtraido]:
    """Processa todos os documentos do registro, extraindo texto dos PDFs elegíveis.

    Documentos inelegíveis recebem status 'nao_elegivel_para_extracao' imediatamente,
    sem tentar abrir o arquivo. Todos os demais passam pela extração.

    Retorna lista ordenada por caminho para saída determinística.
    """
    resultados: List[TextoExtraido] = []

    for doc in sorted(registro.values(), key=lambda d: d.caminho):
        agora = datetime.now(tz=timezone.utc).isoformat()

        if not valido_para_extracao(doc):
            resultados.append(TextoExtraido(
                caminho=doc.caminho,
                nome_arquivo=doc.nome_arquivo,
                uf=doc.uf,
                sindicato=doc.sindicato,
                tipo_documento=doc.tipo_documento,
                ano_referencia=doc.ano_referencia,
                texto="",
                num_caracteres=0,
                status="nao_elegivel_para_extracao",
                data_processamento=agora,
            ))
            continue

        pdf_path = raiz / doc.caminho
        texto, status = extrair_texto_pdf(pdf_path)

        resultados.append(TextoExtraido(
            caminho=doc.caminho,
            nome_arquivo=doc.nome_arquivo,
            uf=doc.uf,
            sindicato=doc.sindicato,
            tipo_documento=doc.tipo_documento,
            ano_referencia=doc.ano_referencia,
            texto=texto,
            num_caracteres=len(texto),
            status=status,
            data_processamento=agora,
        ))

    return resultados

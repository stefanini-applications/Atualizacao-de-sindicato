"""Persistência dos textos extraídos de PDFs sindicais.

Armazena e recupera a lista de TextoExtraido em formato JSON estruturado,
usando escrita atômica para evitar corrupção em caso de interrupção.
"""

import json
import os
import tempfile
from pathlib import Path
from typing import List

from src.models.texto_extraido import TextoExtraido

_STORE_VERSION = 1


def _texto_para_dict(t: TextoExtraido) -> dict:
    return {
        "caminho": t.caminho,
        "nome_arquivo": t.nome_arquivo,
        "uf": t.uf,
        "sindicato": t.sindicato,
        "tipo_documento": t.tipo_documento,
        "ano_referencia": t.ano_referencia,
        "texto": t.texto,
        "num_caracteres": t.num_caracteres,
        "status": t.status,
        "data_processamento": t.data_processamento,
    }


def _dict_para_texto(d: dict) -> TextoExtraido:
    return TextoExtraido(
        caminho=d.get("caminho") or "",
        nome_arquivo=d.get("nome_arquivo") or "",
        uf=d.get("uf"),
        sindicato=d.get("sindicato"),
        tipo_documento=d.get("tipo_documento"),
        ano_referencia=d.get("ano_referencia"),
        texto=d.get("texto") or "",
        num_caracteres=d.get("num_caracteres") or 0,
        status=d.get("status") or "",
        data_processamento=d.get("data_processamento") or "",
    )


def salvar_textos(output_path: Path, textos: List[TextoExtraido]) -> None:
    """Salva lista de textos extraídos no disco de forma atômica."""
    dados = {
        "versao": _STORE_VERSION,
        "textos": [_texto_para_dict(t) for t in textos],
    }
    payload = json.dumps(dados, ensure_ascii=False, indent=2)

    output_path.parent.mkdir(parents=True, exist_ok=True)

    dir_destino = output_path.parent
    fd, tmp_path = tempfile.mkstemp(dir=dir_destino, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(payload)
        os.replace(tmp_path, output_path)
    except Exception:
        os.unlink(tmp_path)
        raise


def carregar_textos(output_path: Path) -> List[TextoExtraido]:
    """Carrega textos extraídos do disco. Retorna lista vazia se arquivo não existe."""
    if not output_path.exists():
        return []
    with output_path.open(encoding="utf-8") as f:
        dados = json.load(f)
    return [_dict_para_texto(d) for d in dados.get("textos", [])]

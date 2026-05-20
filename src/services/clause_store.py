"""Persistência das cláusulas candidatas identificadas nas CCTs.

Armazena e recupera a lista de ClausulaCandidata em formato JSON estruturado,
usando escrita atômica para evitar corrupção em caso de interrupção (AC4).
"""

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import List

from src.models.clausula_candidata import ClausulaCandidata

_STORE_VERSION = 1


def _clausula_para_dict(c: ClausulaCandidata) -> dict:
    return {
        "trecho": c.trecho,
        "caminho": c.caminho,
        "nome_arquivo": c.nome_arquivo,
        "uf": c.uf,
        "sindicato": c.sindicato,
        "tipo_documento": c.tipo_documento,
        "ano_referencia": c.ano_referencia,
        "origem_texto": c.origem_texto,
        "status_consolidado": c.status_consolidado,
        "tipo_clausula": c.tipo_clausula,
        "metodo_identificacao": c.metodo_identificacao,
        "data_hora_processamento": c.data_hora_processamento,
    }


def _dict_para_clausula(d: dict) -> ClausulaCandidata:
    return ClausulaCandidata(
        trecho=d.get("trecho") or "",
        caminho=d.get("caminho") or "",
        nome_arquivo=d.get("nome_arquivo") or "",
        uf=d.get("uf"),
        sindicato=d.get("sindicato"),
        tipo_documento=d.get("tipo_documento"),
        ano_referencia=d.get("ano_referencia"),
        origem_texto=d.get("origem_texto") or "",
        status_consolidado=d.get("status_consolidado") or "",
        tipo_clausula=d.get("tipo_clausula") or "",
        metodo_identificacao=d.get("metodo_identificacao") or "",
        data_hora_processamento=d.get("data_hora_processamento") or "",
    )


def salvar_clausulas(output_path: Path, clausulas: List[ClausulaCandidata]) -> None:
    """Salva lista de cláusulas candidatas no disco de forma atômica (AC4)."""
    dados = {
        "versao": _STORE_VERSION,
        "data_geracao": datetime.now(tz=timezone.utc).isoformat(),
        "clausulas": [_clausula_para_dict(c) for c in clausulas],
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


def carregar_clausulas(output_path: Path) -> List[ClausulaCandidata]:
    """Carrega cláusulas candidatas do disco. Retorna lista vazia se arquivo não existe."""
    if not output_path.exists():
        return []
    with output_path.open(encoding="utf-8") as f:
        dados = json.load(f)
    return [_dict_para_clausula(d) for d in dados.get("clausulas", [])]

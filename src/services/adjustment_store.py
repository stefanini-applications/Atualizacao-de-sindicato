"""Persistência dos reajustes extraídos das cláusulas candidatas das CCTs.

Armazena e recupera a lista de ReajusteExtraido em formato JSON estruturado,
usando escrita atômica via tempfile + os.replace para evitar corrupção em
caso de interrupção (AC4).
"""

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import List

from src.models.reajuste_extraido import ReajusteExtraido

_STORE_VERSION = 1


def _reajuste_para_dict(r: ReajusteExtraido) -> dict:
    return {
        "caminho": r.caminho,
        "nome_arquivo": r.nome_arquivo,
        "uf": r.uf,
        "sindicato": r.sindicato,
        "tipo_documento": r.tipo_documento,
        "ano_referencia": r.ano_referencia,
        "origem_texto": r.origem_texto,
        "tipo_clausula": r.tipo_clausula,
        "trecho_original": r.trecho_original,
        "percentual_reajuste": r.percentual_reajuste,
        "data_base": r.data_base,
        "vigencia_inicio": r.vigencia_inicio,
        "vigencia_fim": r.vigencia_fim,
        "status_extracao_estruturada": r.status_extracao_estruturada,
        "metodo_extracao": r.metodo_extracao,
        "data_hora_processamento": r.data_hora_processamento,
    }


def _dict_para_reajuste(d: dict) -> ReajusteExtraido:
    return ReajusteExtraido(
        caminho=d.get("caminho") or "",
        nome_arquivo=d.get("nome_arquivo") or "",
        uf=d.get("uf"),
        sindicato=d.get("sindicato"),
        tipo_documento=d.get("tipo_documento"),
        ano_referencia=d.get("ano_referencia"),
        origem_texto=d.get("origem_texto") or "",
        tipo_clausula=d.get("tipo_clausula") or "",
        trecho_original=d.get("trecho_original") or "",
        percentual_reajuste=d.get("percentual_reajuste"),
        data_base=d.get("data_base"),
        vigencia_inicio=d.get("vigencia_inicio"),
        vigencia_fim=d.get("vigencia_fim"),
        status_extracao_estruturada=d.get("status_extracao_estruturada") or "",
        metodo_extracao=d.get("metodo_extracao") or "",
        data_hora_processamento=d.get("data_hora_processamento") or "",
    )


def salvar_reajustes(output_path: Path, reajustes: List[ReajusteExtraido]) -> None:
    """Salva lista de reajustes extraídos no disco de forma atômica (AC4)."""
    dados = {
        "versao": _STORE_VERSION,
        "data_geracao": datetime.now(tz=timezone.utc).isoformat(),
        "reajustes": [_reajuste_para_dict(r) for r in reajustes],
    }
    payload = json.dumps(dados, ensure_ascii=False, indent=2)

    output_path.parent.mkdir(parents=True, exist_ok=True)

    fd, tmp_path = tempfile.mkstemp(dir=output_path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(payload)
        os.replace(tmp_path, output_path)
    except Exception:
        os.unlink(tmp_path)
        raise


def carregar_reajustes(input_path: Path) -> List[ReajusteExtraido]:
    """Carrega reajustes extraídos do disco. Retorna lista vazia se arquivo não existe."""
    if not input_path.exists():
        return []
    with input_path.open(encoding="utf-8") as f:
        dados = json.load(f)
    return [_dict_para_reajuste(d) for d in dados.get("reajustes", [])]

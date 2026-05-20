"""Persistência da base final de reajustes aprovados.

Armazena e recupera a lista de ``ReajusteAprovado`` em formato JSON estruturado,
usando escrita atômica via ``tempfile + os.replace`` para evitar corrupção em
caso de interrupção — AC5.
"""

import json
import os
import tempfile
from pathlib import Path
from typing import List

from src.models.reajuste_aprovado import ReajusteAprovado

_STORE_VERSION = 1


def _aprovado_para_dict(r: ReajusteAprovado) -> dict:
    return {
        "id_registro": r.id_registro,
        "caminho": r.caminho,
        "nome_arquivo": r.nome_arquivo,
        "uf": r.uf,
        "sindicato": r.sindicato,
        "tipo_documento": r.tipo_documento,
        "ano_referencia": r.ano_referencia,
        "tipo_clausula": r.tipo_clausula,
        "trecho_original": r.trecho_original,
        # rastreabilidade dual
        "percentual_reajuste_original": r.percentual_reajuste_original,
        "percentual_reajuste_final": r.percentual_reajuste_final,
        "data_base_original": r.data_base_original,
        "data_base_final": r.data_base_final,
        "vigencia_inicio_original": r.vigencia_inicio_original,
        "vigencia_inicio_final": r.vigencia_inicio_final,
        "vigencia_fim_original": r.vigencia_fim_original,
        "vigencia_fim_final": r.vigencia_fim_final,
        # auditoria
        "status_validacao": r.status_validacao,
        "responsavel_validacao": r.responsavel_validacao,
        "data_hora_validacao": r.data_hora_validacao,
        "observacao_validacao": r.observacao_validacao,
        "data_hora_geracao": r.data_hora_geracao,
    }


def salvar_aprovados(output_path: Path, registros: List[ReajusteAprovado]) -> None:
    """Salva lista de reajustes aprovados no disco de forma atômica (AC5)."""
    dados = {
        "versao": _STORE_VERSION,
        "reajustes": [_aprovado_para_dict(r) for r in registros],
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


def _dict_para_aprovado(d: dict) -> ReajusteAprovado:
    return ReajusteAprovado(
        id_registro=d.get("id_registro"),
        caminho=d["caminho"],
        nome_arquivo=d["nome_arquivo"],
        uf=d.get("uf"),
        sindicato=d.get("sindicato"),
        tipo_documento=d.get("tipo_documento"),
        ano_referencia=d.get("ano_referencia"),
        tipo_clausula=d["tipo_clausula"],
        trecho_original=d["trecho_original"],
        percentual_reajuste_original=d.get("percentual_reajuste_original"),
        percentual_reajuste_final=d.get("percentual_reajuste_final"),
        data_base_original=d.get("data_base_original"),
        data_base_final=d.get("data_base_final"),
        vigencia_inicio_original=d.get("vigencia_inicio_original"),
        vigencia_inicio_final=d.get("vigencia_inicio_final"),
        vigencia_fim_original=d.get("vigencia_fim_original"),
        vigencia_fim_final=d.get("vigencia_fim_final"),
        status_validacao=d["status_validacao"],
        responsavel_validacao=d.get("responsavel_validacao"),
        data_hora_validacao=d.get("data_hora_validacao"),
        observacao_validacao=d.get("observacao_validacao"),
        data_hora_geracao=d["data_hora_geracao"],
    )


def carregar_aprovados(input_path: Path) -> List[ReajusteAprovado]:
    """Carrega lista de reajustes aprovados a partir do disco."""
    with input_path.open(encoding="utf-8") as f:
        dados = json.load(f)
    return [_dict_para_aprovado(d) for d in dados.get("reajustes", [])]

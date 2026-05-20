"""Persistência dos reajustes preparados para validação humana.

Armazena e recupera a lista de ReajusteParaValidacao em formato JSON
estruturado, usando escrita atômica via tempfile + os.replace para evitar
corrupção em caso de interrupção (AC4).
"""

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import List

from src.models.reajuste_para_validacao import ReajusteParaValidacao

_STORE_VERSION = 1


def _validacao_para_dict(r: ReajusteParaValidacao) -> dict:
    return {
        # campos originais da extração
        "caminho": r.caminho,
        "nome_arquivo": r.nome_arquivo,
        "uf": r.uf,
        "sindicato": r.sindicato,
        "tipo_documento": r.tipo_documento,
        "ano_referencia": r.ano_referencia,
        "tipo_clausula": r.tipo_clausula,
        "trecho_original": r.trecho_original,
        "percentual_reajuste": r.percentual_reajuste,
        "data_base": r.data_base,
        "vigencia_inicio": r.vigencia_inicio,
        "vigencia_fim": r.vigencia_fim,
        "status_extracao_estruturada": r.status_extracao_estruturada,
        # campos de validação
        "status_validacao": r.status_validacao,
        "observacao_validacao": r.observacao_validacao,
        "responsavel_validacao": r.responsavel_validacao,
        "data_hora_validacao": r.data_hora_validacao,
        # campos de correção manual
        "percentual_reajuste_corrigido": r.percentual_reajuste_corrigido,
        "data_base_corrigida": r.data_base_corrigida,
        "vigencia_inicio_corrigida": r.vigencia_inicio_corrigida,
        "vigencia_fim_corrigida": r.vigencia_fim_corrigida,
    }


def salvar_para_validacao(output_path: Path, registros: List[ReajusteParaValidacao]) -> None:
    """Salva lista de registros para validação no disco de forma atômica (AC4)."""
    dados = {
        "versao": _STORE_VERSION,
        "data_geracao": datetime.now(tz=timezone.utc).isoformat(),
        "reajustes": [_validacao_para_dict(r) for r in registros],
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

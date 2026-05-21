"""Exportador de parâmetros sindicais para o Ratecard.

Lê a base de reajustes aprovados, filtra exclusivamente os registros com
``status_validacao = "aprovado"``, agrupa pela chave composta normalizada
(UF + Sindicato + Ano de Referência) e produz um registro determinístico
por chave:

  - ``"valido"``   — exatamente um registro aprovado para a chave.
  - ``"conflito"`` — múltiplos registros aprovados para a mesma chave;
                     campos de reajuste são nulos e ``ids_registros_conflitantes``
                     lista todos os ids conflitantes.

A persistência segue o mesmo padrão de escrita atômica de ``approved_store.py``
(``tempfile.mkstemp`` + ``os.replace`` + ``os.fdopen``) — AC5.
"""

import json
import os
import tempfile
from pathlib import Path
from typing import List, Tuple

from src.models.reajuste_aprovado import ReajusteAprovado
from src.utils.text_normalizer import normalizar

STATUS_VALIDO = "valido"
STATUS_CONFLITO = "conflito"
OBS_CONFLITO = "múltiplos registros aprovados encontrados para esta chave"

_STORE_VERSION = 1


def _normalizar_chave(r: ReajusteAprovado) -> str:
    """Retorna a chave normalizada concatenada para agrupamento e lookup."""
    uf = normalizar(str(r.uf or "").strip())
    sindicato = normalizar(str(r.sindicato or "").strip())
    ano = normalizar(str(r.ano_referencia or "").strip())
    return f"{uf}|{sindicato}|{ano}"


def _registro_valido(r: ReajusteAprovado, chave: str) -> dict:
    return {
        "chave_parametro": chave,
        "uf": r.uf,
        "sindicato": r.sindicato,
        "ano_referencia": r.ano_referencia,
        "percentual_reajuste": r.percentual_reajuste_final,
        "data_base": r.data_base_final,
        "vigencia_inicio": r.vigencia_inicio_final,
        "vigencia_fim": r.vigencia_fim_final,
        "fonte_documento": r.nome_arquivo,
        "status_aprovacao": r.status_validacao,
        "data_ultima_atualizacao": r.data_hora_geracao,
        "status_parametro": STATUS_VALIDO,
        "conflito": False,
        "id_registro_reajuste": r.id_registro,
        "ids_registros_conflitantes": [],
        "observacao": None,
    }


def _registro_conflito(registros: List[ReajusteAprovado], chave: str) -> dict:
    # Use original (non-normalised) key values from the first record for readability.
    primeiro = registros[0]
    return {
        "chave_parametro": chave,
        "uf": primeiro.uf,
        "sindicato": primeiro.sindicato,
        "ano_referencia": primeiro.ano_referencia,
        "percentual_reajuste": None,
        "data_base": None,
        "vigencia_inicio": None,
        "vigencia_fim": None,
        "fonte_documento": None,
        "status_aprovacao": None,
        "data_ultima_atualizacao": None,
        "status_parametro": STATUS_CONFLITO,
        "conflito": True,
        "id_registro_reajuste": None,
        "ids_registros_conflitantes": [r.id_registro for r in registros],
        "observacao": OBS_CONFLITO,
    }


def exportar_parametros(
    registros: List[ReajusteAprovado],
) -> Tuple[List[dict], int]:
    """Filtra, agrupa e constrói os registros de parâmetros sindicais.

    Args:
        registros: lista completa de ``ReajusteAprovado`` (pode conter qualquer status).

    Returns:
        (parametros, total_conflitos) onde ``parametros`` é a lista de dicts
        determinística (um registro por chave) e ``total_conflitos`` é o número
        de grupos com ``status_parametro = "conflito"``.
    """
    aprovados = [r for r in registros if r.status_validacao == "aprovado"]

    grupos: dict[str, List[ReajusteAprovado]] = {}
    for r in aprovados:
        chave = _normalizar_chave(r)
        grupos.setdefault(chave, []).append(r)

    parametros: List[dict] = []
    total_conflitos = 0

    for chave, grupo in grupos.items():
        if len(grupo) == 1:
            parametros.append(_registro_valido(grupo[0], chave))
        else:
            parametros.append(_registro_conflito(grupo, chave))
            total_conflitos += 1

    return parametros, total_conflitos


def salvar_parametros(output_path: Path, parametros: List[dict], data_geracao: str) -> None:
    """Persiste a base de parâmetros sindicais em disco de forma atômica (AC5)."""
    dados = {
        "versao": _STORE_VERSION,
        "data_geracao": data_geracao,
        "parametros": parametros,
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

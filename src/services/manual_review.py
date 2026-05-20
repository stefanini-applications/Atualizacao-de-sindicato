"""Serviço de revisão manual dos reajustes preparados para validação humana.

Valida os status informados pelo operador, aborta se algum registro não possuir
id_registro, preenche responsavel_validacao e data_hora_validacao para registros
aprovados ou rejeitados, e preserva todos os demais campos intactos (AC1–AC6).
"""

from dataclasses import replace
from typing import List

from src.models.reajuste_para_validacao import STATUS_VALIDACAO, ReajusteParaValidacao

_STATUS_FINAIS = frozenset(["aprovado", "rejeitado"])


def revisar_registros(
    registros: List[ReajusteParaValidacao],
    responsavel: str,
    timestamp: str,
) -> List[ReajusteParaValidacao]:
    """Aplica a revisão manual sobre a lista de registros.

    Args:
        registros: Lista carregada do arquivo editado pelo operador.
        responsavel: Valor do argumento --responsavel do CLI.
        timestamp: Timestamp UTC da execução (ISO 8601).

    Returns:
        Lista atualizada com rastreabilidade preenchida para aprovados/rejeitados.

    Raises:
        ValueError: Se algum status_validacao for inválido ou algum registro
                    não possuir id_registro.
    """
    # AC6: abortar se algum registro não tiver id_registro preenchido
    sem_id = [
        i for i, r in enumerate(registros)
        if not (r.id_registro or "").strip()
    ]
    if sem_id:
        indices = ", ".join(str(i) for i in sem_id[:5])
        suffix = f" (e mais {len(sem_id) - 5})" if len(sem_id) > 5 else ""
        raise ValueError(
            f"{len(sem_id)} registro(s) sem 'id_registro' (índice(s): {indices}{suffix}). "
            "Execute 'python -m src validate-adjustments' para regenerar o arquivo com os UUIDs."
        )

    # AC1: validar todos os status_validacao antes de gravar qualquer alteração
    invalidos = [
        (i, r.status_validacao)
        for i, r in enumerate(registros)
        if r.status_validacao not in STATUS_VALIDACAO
    ]
    if invalidos:
        detalhes = "; ".join(f"índice {i}: '{sv}'" for i, sv in invalidos[:5])
        raise ValueError(
            f"Status inválido em {len(invalidos)} registro(s): {detalhes}. "
            f"Valores aceitos: {sorted(STATUS_VALIDACAO)}."
        )

    # AC2: preencher rastreabilidade apenas para registros aprovados/rejeitados
    resultado: List[ReajusteParaValidacao] = []
    for r in registros:
        if r.status_validacao in _STATUS_FINAIS:
            r = replace(
                r,
                responsavel_validacao=responsavel,
                data_hora_validacao=timestamp,
            )
        resultado.append(r)

    return resultado

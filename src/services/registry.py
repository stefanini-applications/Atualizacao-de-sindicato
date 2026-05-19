"""Registro persistente de documentos sindicais em JSON.

Regras de upsert ao re-escanear:
  - Identificação por caminho relativo POSIX (chave estável).
  - Campos derivados de path (uf, sindicato) são sempre atualizados do scanner.
  - Campos inferidos do nome (tipo_documento, ano_referencia, vigencia_*) só
    atualizam se o valor atual for None/vazio, preservando correções manuais.
  - data_inclusao nunca é sobrescrita após a primeira inserção.
  - status: se campos críticos ficarem ausentes, força "pendente de validação";
    caso contrário preserva o status existente.
  - responsavel: nunca sobrescrito por varredura automática.
"""

import json
import os
import tempfile
from pathlib import Path
from typing import Dict, List, Optional

from src.models.documento import DocumentoSindical
from src.services.validator import campos_criticos_ausentes_ou_invalidos


_REGISTRY_VERSION = 1


def _doc_para_dict(doc: DocumentoSindical) -> dict:
    return {
        "id": doc.id,
        "nome_arquivo": doc.nome_arquivo,
        "caminho": doc.caminho,
        "uf": doc.uf,
        "sindicato": doc.sindicato,
        "tipo_documento": doc.tipo_documento,
        "ano_referencia": doc.ano_referencia,
        "status": doc.status,
        "data_inclusao": doc.data_inclusao,
        "responsavel": doc.responsavel,
        "vigencia_inicial": doc.vigencia_inicial,
        "vigencia_final": doc.vigencia_final,
    }


def _dict_para_doc(d: dict) -> DocumentoSindical:
    return DocumentoSindical(
        id=d["id"],
        nome_arquivo=d.get("nome_arquivo") or "",
        caminho=d.get("caminho") or "",
        uf=d.get("uf"),
        sindicato=d.get("sindicato"),
        tipo_documento=d.get("tipo_documento"),
        ano_referencia=d.get("ano_referencia"),
        status=d.get("status") or "pendente de validação",
        data_inclusao=d.get("data_inclusao") or "",
        responsavel=d.get("responsavel"),
        vigencia_inicial=d.get("vigencia_inicial"),
        vigencia_final=d.get("vigencia_final"),
    )


def carregar(registry_path: Path) -> Dict[str, DocumentoSindical]:
    """Carrega registro do disco. Retorna dicionário caminho→DocumentoSindical."""
    if not registry_path.exists():
        return {}
    with registry_path.open(encoding="utf-8") as f:
        dados = json.load(f)
    documentos = dados.get("documentos", [])
    return {d["caminho"]: _dict_para_doc(d) for d in documentos}


def salvar(registry_path: Path, registro: Dict[str, DocumentoSindical]) -> None:
    """Salva registro no disco de forma atômica."""
    dados = {
        "versao": _REGISTRY_VERSION,
        "documentos": [_doc_para_dict(doc) for doc in registro.values()],
    }
    payload = json.dumps(dados, ensure_ascii=False, indent=2)

    registry_path.parent.mkdir(parents=True, exist_ok=True)

    # Escrita atômica via arquivo temporário no mesmo diretório
    dir_destino = registry_path.parent
    fd, tmp_path = tempfile.mkstemp(dir=dir_destino, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(payload)
        os.replace(tmp_path, registry_path)
    except Exception:
        os.unlink(tmp_path)
        raise


def upsert(
    registro: Dict[str, DocumentoSindical],
    novos: List[DocumentoSindical],
) -> Dict[str, int]:
    """Insere ou atualiza documentos no registro em memória.

    Retorna estatísticas: {"inseridos": N, "atualizados": M}.
    """
    inseridos = 0
    atualizados = 0

    for novo in novos:
        chave = novo.caminho
        existente = registro.get(chave)

        if existente is None:
            registro[chave] = novo
            inseridos += 1
        else:
            _mesclar(existente, novo)
            atualizados += 1

    return {"inseridos": inseridos, "atualizados": atualizados}


def _mesclar(existente: DocumentoSindical, novo: DocumentoSindical) -> None:
    """Atualiza `existente` com dados de `novo` respeitando regras de preservação."""
    # Sempre atualiza: campos derivados de path e nome do arquivo
    existente.nome_arquivo = novo.nome_arquivo
    existente.caminho = novo.caminho
    existente.uf = novo.uf
    existente.sindicato = novo.sindicato or existente.sindicato

    # Preserva correções manuais: só atualiza se campo ainda vazio
    if not existente.tipo_documento:
        existente.tipo_documento = novo.tipo_documento
    if not existente.ano_referencia:
        existente.ano_referencia = novo.ano_referencia
    if not existente.vigencia_inicial:
        existente.vigencia_inicial = novo.vigencia_inicial
    if not existente.vigencia_final:
        existente.vigencia_final = novo.vigencia_final

    # Nunca sobrescreve data_inclusao nem responsavel
    # existente.data_inclusao permanece inalterado
    # existente.responsavel permanece inalterado

    # Status: se campos críticos estiverem ausentes, força pendente
    if campos_criticos_ausentes_ou_invalidos(existente):
        existente.status = "pendente de validação"
    # Caso contrário, preserva o status que o usuário definiu

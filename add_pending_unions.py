#!/usr/bin/env python3
"""
Varre a estrutura CCT/<UF>/<Sindicato>/ e insere registros com
status_parametro = "pendente_revisao" em data/base_parametros_sindicais.json
para todos os sindicatos ainda não presentes na base.

Registros existentes com status "valido" ou "conflito" são preservados integralmente.

Uso:
    python3 add_pending_unions.py
"""

import json
import os
import re
import unicodedata

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
JSON_PATH = os.path.join(REPO_ROOT, "data", "base_parametros_sindicais.json")
CCT_ROOT = os.path.join(REPO_ROOT, "CCT")
PENDING_OBS = (
    "Sindicato encontrado na pasta CCT, mas sem parâmetro aprovado disponível"
)


def normalize(text: str) -> str:
    """Lowercase, remove accents, keep only alphanumeric chars."""
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]", "", text.lower())


def first_pdf(folder: str) -> str | None:
    """Return relative path of first PDF found inside folder, or None."""
    for entry in sorted(os.listdir(folder)):
        if entry.lower().endswith(".pdf"):
            return os.path.relpath(os.path.join(folder, entry), REPO_ROOT)
    return None


def is_matched(uf: str, folder_name: str, existing_records: list) -> bool:
    """
    Return True if there is already a record in existing_records whose UF
    matches and whose sindicato name is sufficiently similar to folder_name.

    Matching strategy (conservative):
      - Normalize both names (no accents, no spaces, lowercase).
      - Strip the UF suffix from the existing sindicato (e.g. "SEAC AC" → "seac").
      - A match occurs when:
          (a) normalized folder == normalized existing sindicato (full), OR
          (b) normalized existing sindicato (stripped of UF) == normalized folder, OR
          (c) one is a prefix of the other with length >= 5 characters.
    """
    norm_folder = normalize(folder_name)
    norm_uf = normalize(uf)

    for rec in existing_records:
        if rec.get("uf", "").upper() != uf.upper():
            continue
        sindicato = rec.get("sindicato", "")
        norm_sind = normalize(sindicato)
        # Strip UF suffix from normalized sindicato (e.g. "seacac" → "seac")
        norm_sind_stripped = (
            norm_sind[: -len(norm_uf)]
            if norm_sind.endswith(norm_uf)
            else norm_sind
        )

        if norm_folder == norm_sind:
            return True
        if norm_folder == norm_sind_stripped:
            return True
        min_len = min(len(norm_folder), len(norm_sind_stripped))
        if min_len >= 5 and norm_folder[:min_len] == norm_sind_stripped[:min_len]:
            return True

    return False


def build_pending_id(uf: str, folder_name: str) -> str:
    """Build a stable, unique ID for a pending record."""
    slug = re.sub(r"[^a-zA-Z0-9]", "-", folder_name).strip("-")
    slug = re.sub(r"-{2,}", "-", slug)
    return f"PEND-{uf.upper()}-{slug.upper()}"


def main():
    with open(JSON_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    existing = data.get("registros", [])
    existing_ids = {r.get("id_registro_reajuste") for r in existing}

    new_records = []

    for uf_entry in sorted(os.listdir(CCT_ROOT)):
        uf_path = os.path.join(CCT_ROOT, uf_entry)
        if not os.path.isdir(uf_path):
            continue
        uf = uf_entry.upper()

        for sind_entry in sorted(os.listdir(uf_path)):
            sind_path = os.path.join(uf_path, sind_entry)
            if not os.path.isdir(sind_path):
                continue

            if is_matched(uf, sind_entry, existing):
                continue

            pending_id = build_pending_id(uf, sind_entry)
            if pending_id in existing_ids:
                continue

            pdf_path = first_pdf(sind_path)

            record = {
                "id_registro_reajuste": pending_id,
                "ids_registros_conflitantes": None,
                "uf": uf,
                "sindicato": sind_entry,
                "categoria": None,
                "ano_referencia": None,
                "percentual_reajuste": None,
                "data_base": None,
                "vigencia_inicio": None,
                "vigencia_fim": None,
                "status_parametro": "pendente_revisao",
                "conflito": False,
                "fonte_documento": pdf_path,
                "observacao": PENDING_OBS,
            }

            new_records.append(record)
            existing_ids.add(pending_id)
            print(f"  + Adicionado: {uf} / {sind_entry}")

    if not new_records:
        print("Nenhum sindicato novo encontrado. Base já está completa.")
        return

    data["registros"] = existing + new_records
    with open(JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    total = len(data["registros"])
    print(
        f"\nBase atualizada: {len(existing)} registros existentes + "
        f"{len(new_records)} novos = {total} total"
    )
    print(f"Arquivo salvo: {JSON_PATH}")


if __name__ == "__main__":
    main()

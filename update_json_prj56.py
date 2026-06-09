#!/usr/bin/env python3
import json
import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent
JSON_PATH = REPO_ROOT / "data" / "base_parametros_sindicais.json"

MANUAL_PISOS = {
    "REG-AM-SINDPD-2025": [
        {
            "cargo": "Técnico de Atendimento / Aux. Processamento",
            "valor": 1479.21,
            "status_parametro": "extraido_para_revisao",
        },
        {
            "cargo": "Técnico de Suporte",
            "valor": 1487.48,
            "status_parametro": "extraido_para_revisao",
        },
        {
            "cargo": "Analista de Suporte",
            "valor": 2434.07,
            "status_parametro": "extraido_para_revisao",
        },
    ]
}

PISO_TIPO_TO_CARGO = {
    "piso_unico": "Piso Único",
    "piso_tecnico": "Piso Técnico",
    "piso_administrativo": "Piso Adm.",
    "piso_cct": "Piso CCT",
}

MULTIPLOS_RE = re.compile(r"Múltiplos valores identificados:\s*([0-9.,\s]+)")


def parse_multiplos(observacao):
    if not observacao or "Múltiplos valores identificados:" not in observacao:
        return None
    match = MULTIPLOS_RE.search(observacao)
    if not match:
        return None
    values = []
    for part in match.group(1).split(","):
        part = part.strip()
        if not part:
            continue
        try:
            values.append(float(part))
        except ValueError:
            continue
    if not values:
        return None
    return sorted(set(values))


def build_pisos(record, piso_item):
    record_id = record.get("id_registro_reajuste")
    if record_id in MANUAL_PISOS:
        return MANUAL_PISOS[record_id]

    valor = piso_item.get("valor")
    if valor is None:
        return []

    cargo = PISO_TIPO_TO_CARGO.get(piso_item.get("tipo"))
    if not cargo:
        return []

    return [
        {
            "cargo": cargo,
            "valor": valor,
            "status_parametro": piso_item.get("status_parametro"),
        }
    ]


def update_piso(record):
    piso_item = (record.get("itens_cct") or {}).get("piso_salarial")
    if not isinstance(piso_item, dict):
        return False
    if "pisos" in piso_item:
        return False
    piso_item["pisos"] = build_pisos(record, piso_item)
    return True


def update_hora_extra(record):
    hora_extra = (record.get("itens_cct") or {}).get("hora_extra")
    if not isinstance(hora_extra, dict):
        return False
    if "percentual_padrao" in hora_extra:
        return False

    changed = False
    valores = parse_multiplos(hora_extra.get("observacao"))
    if valores:
        if len(valores) == 3:
            hora_extra["percentual_padrao"] = valores[0]
            hora_extra["percentual_sabado"] = valores[1]
            hora_extra["percentual_domingo_feriado"] = valores[2]
            changed = True
        elif len(valores) == 2 and valores[1] == 100.0:
            hora_extra["percentual_padrao"] = valores[0]
            hora_extra["percentual_domingo_feriado"] = valores[1]
            changed = True
    elif hora_extra.get("percentual") is not None:
        hora_extra["percentual_padrao"] = hora_extra.get("percentual")
        changed = True

    return changed


def main():
    data = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    registros = data.get("registros", [])

    piso_updates = 0
    hora_extra_updates = 0
    for record in registros:
        if update_piso(record):
            piso_updates += 1
        if update_hora_extra(record):
            hora_extra_updates += 1

    JSON_PATH.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        f"Atualizado {JSON_PATH} | pisos adicionados: {piso_updates} | "
        f"hora_extra enriquecidos: {hora_extra_updates}"
    )


if __name__ == "__main__":
    main()

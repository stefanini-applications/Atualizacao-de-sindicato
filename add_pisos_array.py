#!/usr/bin/env python3
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
JSON_PATH = REPO_ROOT / 'data' / 'base_parametros_sindicais.json'

DEFAULT_PISOS = [{'cargo': 'Piso Único', 'valor': None, 'status_parametro': 'pendente'}]


def derive_pisos(record):
    itens_cct = record.get('itens_cct') or {}
    piso = itens_cct.get('piso_salarial') or {}
    tipo = piso.get('tipo')
    valor = piso.get('valor')
    status = piso.get('status_parametro')

    if tipo == 'piso_unico' and valor is not None:
        return [{'cargo': 'Piso Único', 'valor': valor, 'status_parametro': status}]
    if tipo == 'piso_cct' and valor is not None:
        return [{'cargo': 'Piso CCT', 'valor': valor, 'status_parametro': status}]
    if tipo == 'piso_tecnico' and valor is not None:
        return [{'cargo': 'Piso Técnico', 'valor': valor, 'status_parametro': status}]
    return [dict(DEFAULT_PISOS[0])]


def insert_pisos_after_fonte(record):
    pisos = derive_pisos(record)
    updated = {}
    inserted = False
    for key, value in record.items():
        updated[key] = value
        if key == 'fonte_documento':
            updated['pisos'] = pisos
            inserted = True
    if not inserted:
        updated['pisos'] = pisos
    return updated


def main():
    with JSON_PATH.open('r', encoding='utf-8') as f:
        data = json.load(f)

    records = data.get('registros', [])
    data['registros'] = [insert_pisos_after_fonte(record) for record in records]

    with JSON_PATH.open('w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write('\n')

    print(f'Updated {len(records)} registros in {JSON_PATH}')


if __name__ == '__main__':
    main()

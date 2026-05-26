#!/usr/bin/env python3
"""
Gera data/base_parametros_sindicais.js a partir de data/base_parametros_sindicais.json.

O arquivo .js exporta window.BASE_PARAMETROS_SINDICAIS, permitindo que index.html
carregue a base real mesmo quando aberto via protocolo file://, onde fetch() falha.

Uso:
    python3 export_inline_data.py
"""

import json
import os
import sys

SRC = os.path.join(os.path.dirname(__file__), 'data', 'base_parametros_sindicais.json')
DST = os.path.join(os.path.dirname(__file__), 'data', 'base_parametros_sindicais.js')


def main():
    if not os.path.exists(SRC):
        print(f'Erro: arquivo de origem não encontrado: {SRC}', file=sys.stderr)
        sys.exit(1)

    with open(SRC, encoding='utf-8') as f:
        data = json.load(f)

    n = len(data.get('registros', []))
    js_payload = json.dumps(data, ensure_ascii=False, indent=2)

    js_content = (
        '// Gerado automaticamente por export_inline_data.py\n'
        '// NÃO edite este arquivo diretamente — edite base_parametros_sindicais.json\n'
        '// e execute: python3 export_inline_data.py\n'
        'window.BASE_PARAMETROS_SINDICAIS = '
        + js_payload
        + ';\n'
    )

    with open(DST, 'w', encoding='utf-8') as f:
        f.write(js_content)

    print(f'Gerado: {DST} ({n} registros)')


if __name__ == '__main__':
    main()

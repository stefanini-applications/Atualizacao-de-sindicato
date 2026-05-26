#!/usr/bin/env python3
"""
Gera data/base_parametros_sindicais.js a partir de data/base_parametros_sindicais.json.

Esse arquivo JS injeta os dados como variável global (window.BASE_PARAMETROS_SINDICAIS),
permitindo que index.html carregue a base real mesmo quando aberto diretamente
pelo navegador via protocolo file://.

Uso:
    python3 export_inline_data.py
"""

import json
import os
import sys

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
JSON_PATH = os.path.join(REPO_ROOT, "data", "base_parametros_sindicais.json")
JS_PATH = os.path.join(REPO_ROOT, "data", "base_parametros_sindicais.js")


def generate():
    if not os.path.exists(JSON_PATH):
        print(f"Erro: arquivo não encontrado: {JSON_PATH}", file=sys.stderr)
        sys.exit(1)

    with open(JSON_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    js_content = (
        "// Gerado automaticamente por export_inline_data.py — não editar manualmente.\n"
        "window.BASE_PARAMETROS_SINDICAIS = "
        + json.dumps(data, ensure_ascii=False)
        + ";\n"
    )

    with open(JS_PATH, "w", encoding="utf-8") as f:
        f.write(js_content)

    n = len(data.get("registros", data) if isinstance(data, dict) else data)
    print(f"Gerado: {JS_PATH} ({n} registros)")


if __name__ == "__main__":
    generate()
